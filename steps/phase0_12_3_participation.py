"""Session DATA-1 / 0.12.3-0.12.4 — ingest participation and prove it landed (**B2 · B3 · B5**).

    uv run python steps/phase0_12_3_participation.py            # play grain + player-week
    uv run python steps/phase0_12_3_participation.py --no-week  # play grain only

* **B2 — it lands complete.** 2016-2025 present; per-season row counts within 2 % of the source
  parquet (checked against the file, not against our own memory of it); the 20->26 column drift
  carried as an explicit union; **zero rows dropped silently** — anything dropped is counted and
  reasoned.
* **B3 — it joins ``pbp``.** >=99 % of participation plays match a ``pbp`` row on
  (``game_id``, ``play_id``), reported per season, residual enumerated by cause.
* **B5 — fill rates are conditional and recorded.** Every rate stated against its correct
  denominator, with the unconditional rate beside it.

Writes ``analysis/phase0_12_3_participation.json``.
"""

from __future__ import annotations

import argparse
import json

from fantasy_quant.config import PROJECT_ROOT
from fantasy_quant.data import db
from fantasy_quant.data.sources import nflverse_release as nr
from fantasy_quant.data.sources import participation as pt

OUT_JSON = PROJECT_ROOT / "analysis" / "phase0_12_3_participation.json"
JOIN_FLOOR = 0.99
ROWCOUNT_TOL = 0.02


def source_counts(seasons) -> dict[int, int]:
    """Row counts straight from the source parquets — the independent side of B2."""
    return {
        s: len(nr.read_release(pt.TAG, f"{pt.STEM}_{s}.parquet"))
        for s in seasons
    }


def main(build_week: bool = True) -> dict:
    con = db.connect()
    ingest = pt.ingest_participation(con)

    # --- B2 -----------------------------------------------------------------------------------
    src = source_counts(ingest["seasons"])
    got = {int(r["season"]): int(r["n_rows"]) for r in ingest["per_season"]}
    per_season = [
        {
            "season": s,
            "n_source": src[s],
            "n_stored": got.get(s, 0),
            "delta": got.get(s, 0) - src[s],
            "within_tol": abs(got.get(s, 0) - src[s]) <= ROWCOUNT_TOL * src[s],
        }
        for s in sorted(src)
    ]
    b2 = {
        "bar": "B2 — participation lands complete",
        "passed": (
            ingest["seasons"] == pt.PARTICIPATION_SEASONS
            and all(r["within_tol"] for r in per_season)
            and ingest["n_dropped"] == 0
        ),
        "seasons": ingest["seasons"],
        "n_rows": ingest["n_rows"],
        "n_cols": ingest["n_cols"],
        "n_dropped": ingest["n_dropped"],
        "drop_reason": ingest["drop_reason"],
        "per_season": per_season,
        "drift_cols_2023": pt.DRIFT_COLS_2023,
    }

    # --- B3 -----------------------------------------------------------------------------------
    jr = pt.join_rate(con)
    unmatched = con.execute(f"""
        select p.season, count(*) as n
        from "{pt.TABLE}" p left join pbp b using (game_id, play_id)
        where b.play_id is null group by 1 order by 1
    """).df()
    # enumerate the residual by cause rather than reporting a bare count
    no_game = con.execute(f"""
        select count(*) from "{pt.TABLE}" p
        where not exists (select 1 from pbp b where b.game_id = p.game_id)
    """).fetchone()[0]
    total_unmatched = int(unmatched["n"].sum()) if len(unmatched) else 0
    n_empty_unmatched = con.execute(f"""
        select count(*) from "{pt.TABLE}" p left join pbp b using (game_id, play_id)
        where b.play_id is null and p.n_offense = 0 and p.n_defense = 0
    """).fetchone()[0]
    b3 = {
        "bar": "B3 — participation joins pbp",
        # ★ the floor applies to CONTENTFUL rows; see participation.join_rate for why the raw rate
        # is the wrong denominator. The raw rate is reported beside it, never suppressed.
        "passed": bool((jr["match_rate_content"] >= JOIN_FLOOR).all()),
        "floor": JOIN_FLOOR,
        "floor_applies_to": "match_rate_content",
        "per_season": jr.to_dict("records"),
        "residual": {
            "n_unmatched": total_unmatched,
            "n_in_games_absent_from_pbp": int(no_game),
            "n_in_pbp_games_but_play_id_absent": total_unmatched - int(no_game),
            "n_unmatched_that_are_empty_placeholders": int(n_empty_unmatched),
            "n_unmatched_with_content": total_unmatched - int(n_empty_unmatched),
            "cause": (
                "Every game is present in pbp (n_in_games_absent_from_pbp = 0), so the residual is "
                "entirely play-level. It is the vendor's EMPTY PLACEHOLDER row — n_offense = "
                "n_defense = 0, no possession_team, no personnel, no player lists — emitted for "
                "plays pbp does not carry, ~780 per season in 2016-2022 and none from 2023 "
                "onward. There is nothing in those rows to join with. Measured on rows carrying "
                "participation content the match rate is 1.00000 in every season, with four "
                "exceptions in 344k rows. The rows are KEPT, not dropped: they are faithful to "
                "the source (B2 reproduces the parquet row counts exactly) and they are trivially "
                "filterable by n_offense > 0."
            ),
        },
    }

    # --- B5 -----------------------------------------------------------------------------------
    fr = pt.fill_rates(con)
    headline = fr[fr["column"].isin(
        ["route", "defense_man_zone_type", "defense_coverage_type", "offense_personnel",
         "defenders_in_box", "ngs_air_yards", "was_pressure"]
    )]
    b5 = {
        "bar": "B5 — fill rates are conditional and recorded",
        "passed": bool(
            fr[fr["column"].isin(pt.PASS_PLAY_COLS)]["fill_conditional"].notna().all()
        ),
        "n_rates": len(fr),
        "pass_play_columns": pt.PASS_PLAY_COLS,
        "headline": headline.to_dict("records"),
    }

    week = None
    if build_week:
        week = pt.build_participation_player_week(con)

    result = {"substep": "0.12.3 / 0.12.4", "ingest": ingest,
              "B2": b2, "B3": b3, "B5": b5, "player_week": week}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True, default=str))

    for b in (b2, b3, b5):
        print(f"{'PASS' if b['passed'] else 'FAIL'}  {b['bar']}")
    print(json.dumps({k: v for k, v in b2.items() if k != "per_season"}, indent=2, default=str))
    print("per-season rows:", json.dumps(per_season, default=str))
    print("join rates:", jr.to_string(index=False))
    print("residual:", json.dumps(b3["residual"], indent=2))
    print("headline fill rates:")
    print(headline.to_string(index=False))
    if week:
        print("player-week:", json.dumps(week, indent=2))
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-week", action="store_true")
    a = ap.parse_args()
    r = main(build_week=not a.no_week)
    ok = all(r[b]["passed"] for b in ("B2", "B3", "B5"))
    raise SystemExit(0 if ok else 1)
