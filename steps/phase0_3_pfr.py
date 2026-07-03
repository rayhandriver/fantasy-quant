"""Phase 0.3 — PFR advanced season panels, run + verify.

    uv run python steps/phase0_3_pfr.py            # use raw cache if present
    uv run python steps/phase0_3_pfr.py --refresh  # re-pull from the nflverse PFR mirror

Done when: PFR season yards reconcile with nflverse ``seasonal`` within a few % (validating the
pfr_id->gsis mapping) and unmatched ids are logged, not silently dropped (BUILD_PLAN.md 0.3).
"""

from __future__ import annotations

import argparse
import logging

from fantasy_quant.data import db
from fantasy_quant.data.sources import pfr

RECONCILE_GATE = 0.02  # median abs % diff vs nflverse seasonal


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="ignore raw caches; re-pull")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    con = db.connect()
    counts = pfr.ingest_pfr_seasonal(con, refresh=args.refresh)

    print("\n=== PFR ingest — table row counts ===")
    for table, n in counts.items():
        print(f"  {table:<10} {n:>8,}")

    print("\n=== gsis match rate (unmatched logged, not dropped) ===")
    for table, m in pfr.match_rate(con).items():
        print(f"  {table:<10} rows={m['rows']:>6,}  matched={m['matched']:>6,}  "
              f"unmatched={m['unmatched_rate']:.2%}")

    print("\n=== done-criterion: PFR yards vs nflverse seasonal (matched players, REG) ===")
    rec = pfr.reconcile(con)
    ok = True
    for st, r in rec.items():
        if r.get("matched", 0) == 0:
            print(f"  {st}: no overlap")
            ok = False
            continue
        passed = r["median_abs_pct"] < RECONCILE_GATE
        ok = ok and passed
        print(f"  {st}: matched={r['matched']:,}  median_abs_pct={r['median_abs_pct']:.3%}  "
              f"p90={r['p90_abs_pct']:.2%}  -> {'PASS' if passed else 'REVIEW'}")
    print(f"\n  overall: {'PASS' if ok else 'REVIEW'} (gate median<{RECONCILE_GATE:.0%})")
    con.close()


if __name__ == "__main__":
    main()
