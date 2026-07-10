"""Stage 0 — Sleeper API probe (read-only, public endpoints; NO ingestion — that's step 0.10).

    uv run python steps/stage0_sleeper_probe.py

De-risks pipeline stage 3 (0.10 Sleeper ingest -> S4/Phase 11 behavioral opponent model) months
early by answering, with evidence:

  1. Identity: does Sleeper's player dump carry ``gsis_id`` (our spine) at usable coverage?
  2. Drafts: what does a completed draft expose pick-by-pick (the S4 training data)?
  3. ADP: is a 2025/2026 ADP board recoverable (directly, or derived from drafts at scale)?

Writes ``analysis/results/sleeper_probe.json``; findings.md gets the verdict. Keyless and
read-only per Sleeper's public API docs (https://docs.sleeper.com — stay under 1000 calls/min).
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from fantasy_quant.config import PROJECT_ROOT

BASE = "https://api.sleeper.app/v1"
OUT = PROJECT_ROOT / "analysis" / "results" / "sleeper_probe.json"
FANTASY_POS = ("QB", "RB", "WR", "TE")
# public accounts to seed the league->draft->picks shape probe (read-only, public data).
SEED_USERNAMES = ("sleeper", "sleeperbot", "sleeperhq")


def _get(client: httpx.Client, path: str):
    r = client.get(f"{BASE}{path}")
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def probe_state(client) -> dict:
    st = _get(client, "/state/nfl") or {}
    return {k: st.get(k) for k in ("season", "league_season", "previous_season", "week",
                                   "season_type")}


def probe_players(client, top_n: int = 300) -> dict:
    """The full player dump + the identity answer for step 0.10.

    Sleeper's own ``gsis_id`` field is sparse (~31% even among draftables), but the nflverse
    ``player_ids`` crosswalk carries a native ``sleeper_id`` column — the real join is
    ``sleeper player_id -> player_ids.sleeper_id -> gsis_id``, measured here on the **draftable
    cohort** (Sleeper ``search_rank`` top-``top_n``). Ingest gotchas for 0.10: Sleeper pads some
    ``gsis_id`` values with leading whitespace; ``player_ids.sleeper_id`` is stored as DOUBLE
    (``4984.0``) so cast before joining."""
    players = _get(client, "/players/nfl") or {}
    active = [p for p in players.values()
              if p.get("active") and p.get("position") in FANTASY_POS]

    def _has_gsis(p) -> bool:
        return bool(str(p.get("gsis_id") or "").strip())

    ranked = sorted(active, key=lambda p: p.get("search_rank") or 10_000_000)[:top_n]

    from fantasy_quant.data import db
    con = db.connect(read_only=True)
    try:
        xw = {str(int(s)): g for s, g in con.execute(
            "SELECT sleeper_id, gsis_id FROM player_ids "
            "WHERE sleeper_id IS NOT NULL AND gsis_id IS NOT NULL").fetchall()}
    finally:
        con.close()
    hits = [p for p in ranked if xw.get(str(p.get("player_id")))]
    sample = next(iter(hits), {})
    return {
        "n_players_total": len(players),
        "n_active_fantasy": len(active),
        "gsis_coverage_all_active": round(sum(map(_has_gsis, active)) / len(active), 4)
        if active else None,
        "gsis_native_coverage_draftable":
            round(sum(map(_has_gsis, ranked)) / len(ranked), 4) if ranked else None,
        "gsis_crosswalk_coverage_draftable":
            round(len(hits) / len(ranked), 4) if ranked else None,
        "crosswalk_misses": [p["full_name"] for p in ranked
                             if not xw.get(str(p.get("player_id")))][:10],
        "top_n": top_n,
        "id_fields_on_sample": sorted(k for k in sample if k.endswith("_id")),
        "sample_mapping": {k: sample.get(k) for k in
                           ("player_id", "gsis_id", "full_name", "position", "team",
                            "search_rank")},
    }


def probe_trending(client) -> dict:
    tr = _get(client, "/players/nfl/trending/add?lookback_hours=24&limit=5") or []
    return {"n": len(tr), "shape": sorted(tr[0].keys()) if tr else None}


def probe_draft_shape(client, seasons) -> dict:
    """Walk user -> leagues -> drafts -> picks from public seed accounts to document the
    pick-by-pick contract (the S4 training data). Returns the first complete chain found."""
    for username in SEED_USERNAMES:
        user = _get(client, f"/user/{username}")
        if not user:
            continue
        uid = user["user_id"]
        for season in seasons:
            leagues = _get(client, f"/user/{uid}/leagues/nfl/{season}") or []
            for lg in leagues[:5]:
                drafts = _get(client, f"/league/{lg['league_id']}/drafts") or []
                for d in drafts:
                    picks = _get(client, f"/draft/{d['draft_id']}/picks") or []
                    if not picks:
                        continue
                    p0 = picks[0]
                    return {
                        "seed_username": username, "season": season,
                        "league_keys": sorted(lg.keys()),
                        "draft_keys": sorted(d.keys()),
                        "draft_type": d.get("type"), "draft_status": d.get("status"),
                        "draft_settings": d.get("settings"),
                        "n_picks": len(picks),
                        "pick_keys": sorted(p0.keys()),
                        "sample_pick": {k: p0.get(k) for k in
                                        ("round", "pick_no", "draft_slot", "player_id",
                                         "picked_by", "is_keeper")},
                    }
    return {"note": "no public seed account exposed a completed draft; "
                    "re-probe with a real username/league_id at step 0.10"}


def main() -> None:
    report: dict = {"base": BASE}
    with httpx.Client(timeout=60, headers={"User-Agent": "fantasy-quant stage-0 probe"}) as c:
        report["state"] = probe_state(c)
        report["players"] = probe_players(c)
        report["trending"] = probe_trending(c)
        seasons = [s for s in (report["state"].get("league_season"),
                               report["state"].get("previous_season"), "2025", "2024") if s]
        report["draft_chain"] = probe_draft_shape(c, list(dict.fromkeys(seasons)))
        # error shape for a bogus draft id (what a crawler must tolerate)
        try:
            bogus = c.get(f"{BASE}/draft/000000000000000000/picks")
            report["bogus_draft_status"] = bogus.status_code
        except httpx.HTTPError as e:  # pragma: no cover - network dependent
            report["bogus_draft_status"] = str(e)

    gsis_ok = (report["players"].get("gsis_crosswalk_coverage_draftable") or 0) >= 0.90
    picks_ok = "pick_keys" in report["draft_chain"]
    report["verdict"] = {
        "identity_join_viable": gsis_ok,
        "pick_by_pick_confirmed": picks_ok,
        "adp_via_api": False,  # no public ADP endpoint — must be derived from drafts at scale
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str))

    print(f"\n=== Sleeper probe (written to {OUT.relative_to(Path.cwd())
                                            if OUT.is_relative_to(Path.cwd()) else OUT}) ===")
    print(f"  state          : {report['state']}")
    p = report["players"]
    if p.get("gsis_crosswalk_coverage_draftable") is not None:
        print(f"  player dump    : {p['n_players_total']:,} total; active fantasy "
              f"{p['n_active_fantasy']:,}")
        print(f"  identity join  : crosswalk sleeper_id->gsis on draftable top-{p['top_n']} = "
              f"{p['gsis_crosswalk_coverage_draftable']:.1%} "
              f"(Sleeper's native gsis field: {p['gsis_native_coverage_draftable']:.1%})")
        print(f"  crosswalk miss : {p['crosswalk_misses']}")
    else:
        print("  player dump    : FAILED")
    print(f"  sample mapping : {p.get('sample_mapping')}")
    print(f"  trending       : {report['trending']}")
    d = report["draft_chain"]
    if "pick_keys" in d:
        print(f"  draft chain    : {d['seed_username']}/{d['season']} type={d['draft_type']} "
              f"picks={d['n_picks']}")
        print(f"  pick shape     : {d['pick_keys']}")
        print(f"  sample pick    : {d['sample_pick']}")
    else:
        print(f"  draft chain    : {d['note']}")
    print(f"  bogus draft id : HTTP {report.get('bogus_draft_status')}")
    v = report["verdict"]
    verdict = "PASS" if (v["identity_join_viable"] and v["pick_by_pick_confirmed"]) else \
              "PARTIAL" if v["identity_join_viable"] else "REVIEW"
    print(f"\n=== stage0_sleeper_probe: {verdict} "
          f"(identity={v['identity_join_viable']}, picks={v['pick_by_pick_confirmed']}, "
          f"adp_endpoint={v['adp_via_api']}) ===")


if __name__ == "__main__":
    main()
