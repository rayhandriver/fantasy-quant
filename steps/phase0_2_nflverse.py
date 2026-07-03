"""Phase 0.2 — nflverse ingest, run end-to-end + verify the done-criteria.

    uv run python steps/phase0_2_nflverse.py            # full pull (incl. PBP)
    uv run python steps/phase0_2_nflverse.py --skip-pbp # fast: everything but play-by-play
    uv run python steps/phase0_2_nflverse.py --refresh  # ignore caches, re-pull from network

Done when: tables rebuild from a fresh run, per-season counts are sane, and the weekly<->snaps
gsis join has <1% unmatched skill-player weeks (CLAUDE.md §3 discipline; BUILD_PLAN.md 0.2).
"""

from __future__ import annotations

import argparse
import logging

from fantasy_quant.data import db
from fantasy_quant.data.sources import nflverse as nv

GATE = 0.01  # <1% unmatched weekly<->snaps


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-pbp", action="store_true", help="skip the large play-by-play pull")
    ap.add_argument("--refresh", action="store_true", help="ignore raw caches; re-pull")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    con = db.connect()
    counts = nv.run_all(con, refresh=args.refresh, skip_pbp=args.skip_pbp)

    print("\n=== nflverse ingest — table row counts ===")
    for table, n in counts.items():
        print(f"  {table:<12} {n:>12,}")

    print("\n=== weekly rows per season (coverage sanity) ===")
    print(nv.per_season_counts(con, "weekly").to_string(index=False))

    print("\n=== done-criterion: weekly <-> snaps gsis match ===")
    m = nv.weekly_snaps_match_rate(con)
    verdict = "PASS" if m["unmatched_rate"] < GATE else "REVIEW"
    print(
        f"  weekly skill-weeks={m['weekly_rows']:,}  unmatched={m['unmatched']:,}  "
        f"unmatched_rate={m['unmatched_rate']:.3%}  -> {verdict} (gate <{GATE:.0%})"
    )
    con.close()


if __name__ == "__main__":
    main()
