"""Dump one season's assembled summary to CSV, so a pre-/post-T31 diff can be taken per player.

Run in a ``git worktree`` at the pre-T31 commit with ``PYTHONPATH=<worktree>/src`` (see the warning
in ``steps/t31_level_cap.py``), and again in the working tree.

    uv run python steps/t31_dump_summary.py --season 2026 --out /tmp/after.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

from fantasy_quant.data.db import connect
from fantasy_quant.projections import distribution


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    con = connect()
    summary, _ = distribution.assemble_distribution(con, args.season, seed=0)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.out, index=False)
    print(f"{args.season}: {len(summary)} rows -> {args.out}")


if __name__ == "__main__":
    main()
