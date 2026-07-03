"""Phase 0.4 — ADP ingest (FFCalculator, PIT snapshots), run + verify.

    uv run python steps/phase0_4_adp.py            # use raw cache if present
    uv run python steps/phase0_4_adp.py --refresh  # re-pull from the FFC API

Done when: coverage spans >=2015->present for >=1 source, gsis matching is high for draftable
players, and ``adp_asof`` never returns a snapshot dated after the as-of (BUILD_PLAN.md 0.4).
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging

from fantasy_quant.data import db
from fantasy_quant.data.sources import adp


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="ignore raw caches; re-pull")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    con = db.connect()
    n = adp.ingest_adp(con, refresh=args.refresh)
    print(f"\n=== adp_snapshots rows: {n:,} ===")

    cov = adp.coverage(con)
    print(f"coverage: {cov['min']}–{cov['max']} ({len(cov['seasons'])} seasons)")

    m = adp.match_rate(con)
    print("\n=== gsis match (skill players; unmatched logged, not dropped) ===")
    print(f"  all skill rows : {m['skill_rows']:,}  unmatched={m['skill_unmatched_rate']:.2%}")
    print(f"  top-150 ADP    : {m['top150_rows']:,}  unmatched={m['top150_unmatched_rate']:.3%}")

    print("\n=== done-criterion: adp_asof PIT behavior (season 2020, ppr 10-team) ===")
    snap = con.execute(
        "SELECT DISTINCT snapshot_date FROM adp_snapshots "
        "WHERE season=2020 AND source='ffc' AND scoring='ppr' AND teams=10"
    ).fetchone()
    snap_date = snap[0]
    before = snap_date - dt.timedelta(days=1)
    after = snap_date + dt.timedelta(days=1)
    n_before = len(adp.adp_asof(con, 2020, before))
    n_after = len(adp.adp_asof(con, 2020, after))
    print(f"  snapshot_date={snap_date}")
    print(f"  as_of day-before ({before}): {n_before} rows  (expect 0 — no leak)")
    print(f"  as_of day-after  ({after}): {n_after} rows  (expect full board)")
    verdict = "PASS" if (n_before == 0 and n_after > 100) else "REVIEW"
    print(f"  -> {verdict}")
    con.close()


if __name__ == "__main__":
    main()
