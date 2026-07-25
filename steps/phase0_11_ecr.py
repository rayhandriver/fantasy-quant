"""Phase 0.11 — ingest the FantasyPros ECR (expert consensus **rank**) archive.

    uv run python steps/phase0_11_ecr.py            # cached pull (idempotent)
    uv run python steps/phase0_11_ecr.py --refresh  # re-scrape every (scoring, year)

Banks the expert-consensus *rank* board — rank, expert disagreement (``ecr_std``), tier, and ECR
delta — for every season FantasyPros archives (2017→current) across PPR / half-PPR / standard.
This is data we never stored: ``projections/consensus.py`` keeps FantasyPros *points*, not rank.

**★ The honest framing (measured 2026-07-25, and it is why 16.8 does not consume this).** The
``?year=`` archive is real — 2020 serves McCaffrey/Barkley/Elliott, 2018 serves Gurley/Johnson/
Brown — but each archived board is a single **end-of-preseason** snapshot: every
``last_updated_ts`` lands 9/06–9/11, i.e. at kickoff. On the Phase-16.7 draft corpus, **1 of 38**
preseason drafts starts on or after its own season's ECR timestamp. So ECR cannot explain draft-day
behaviour without look-ahead, and :func:`ecr_asof` enforces that structurally by returning empty
for an earlier as-of.

It is banked anyway because it is free, deletable-by-the-vendor, and genuinely PIT-clean for
anything scored on the **season outcome** (a ~Sep-7 board precedes Week 1) — a real expert baseline
for the Phase-6/16.1 value work, and the live-2026 input for 16.10/16.11.

Underdog ADP, 0.11's other half as scoped, is **deferred**: no keyless endpoint (marketing routes
404, board is a JS app on an unpublished API). Not attempted rather than half-built.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fantasy_quant.data import db
from fantasy_quant.data.sources import ecr
from fantasy_quant.data.validate import board_size_gate, match_rate_gate

OUT = Path(__file__).resolve().parents[1] / "analysis" / "phase0_11_ecr.json"

# a real cheatsheet board sits well inside this band; outside it the scrape is broken, not thin.
ECR_ROW_BAND = (150, 1200)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-scrape instead of using the cache")
    args = ap.parse_args()

    con = db.connect()
    n = ecr.ingest_ecr(con, refresh=args.refresh)
    print(f"ecr_snapshots: {n:,} rows\n")

    cov = ecr.coverage(con)
    print(cov.to_string(index=False))

    rate = ecr.match_rate(con)
    print(f"\ngsis match rate (top-150 skill): {rate:.1%}")

    # ---- gates (T7 pattern: schema/size/match, so a silently-broken scrape fails loudly) -------
    gates = [board_size_gate(f"ecr_{r.season}_{r.scoring}", int(r.n_rows), band=ECR_ROW_BAND)
             for r in cov.itertuples()]
    gates.append(match_rate_gate("ecr_gsis_match", rate))
    failed = [g for g in gates if not g["passed"]]
    for g in failed:
        print(f"  GATE FAIL: {g}")
    assert not failed, f"{len(failed)} ECR gate(s) failed"

    # ---- boards that are not actually preseason -------------------------------------------------
    # A board stamped after its own season's kickoff was re-touched mid/post-season and is NOT a
    # preseason consensus. Observed: 2023 PPR carries as_of 2024-02-12 (post-Super-Bowl). Report
    # it loudly and flag the row; only a *systemic* break (most boards late) should fail the step.
    late_boards = cov[~cov["is_preseason"].astype(bool)]
    if len(late_boards):
        print("\n  ⚠ NOT preseason boards (re-touched during/after their own season) — "
              "`is_preseason=False`, exclude from any draft-season expert baseline:")
        for r in late_boards.itertuples():
            print(f"      {r.season} {r.scoring:9s} as_of={r.as_of}")
    share_preseason = float(cov["is_preseason"].astype(bool).mean())
    assert share_preseason >= 0.90, \
        f"only {share_preseason:.0%} of ECR boards are preseason — the archive changed shape"

    # ---- the PIT property this module exists to make structural --------------------------------
    # Every archived historical board post-dates the drafts it would explain, so a draft-day as-of
    # must come back EMPTY. Assert it rather than trusting the docstring. The "reachable" probe
    # keys off each board's own stamp (the 2023 PPR outlier is only reachable in 2024).
    seasons = sorted(int(s) for s in cov["season"].unique())
    hist = [s for s in seasons if s < max(seasons)]
    probe = {}
    for s in hist:
        stamp = cov.loc[cov["season"] == s, "as_of"].max()
        early = ecr.ecr_asof(con, s, f"{s}-08-15")   # a typical draft day
        late = ecr.ecr_asof(con, s, stamp)           # exactly at the latest board's own stamp
        probe[s] = {"draft_day_rows": int(len(early)), "at_stamp_rows": int(len(late)),
                    "stamp": str(stamp)}
        assert early.empty, f"{s}: ECR returned a board for an Aug-15 as-of — PIT guard broken"
        assert not late.empty, f"{s}: ECR board unreachable even at its own stamp"
    print(f"\nPIT guard: {len(hist)} historical seasons — all empty at an Aug-15 as-of, "
          f"all reachable at their own stamp.")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "n_rows": int(n),
        "seasons": seasons,
        "scorings": sorted(cov["scoring"].unique().tolist()),
        "coverage": cov.to_dict(orient="records"),
        "gsis_match_top150": float(rate),
        "share_preseason_boards": share_preseason,
        "non_preseason_boards": late_boards[["season", "scoring", "as_of"]].to_dict("records"),
        "pit_probe": probe,
        "underdog": "deferred — no keyless endpoint (see module docstring)",
    }, indent=2, default=str))
    print(f"  wrote {OUT.relative_to(OUT.parents[1])}")
    print("\nPhase 0.11 (ECR ingest) — all gates PASS.")
    con.close()


if __name__ == "__main__":
    main()
