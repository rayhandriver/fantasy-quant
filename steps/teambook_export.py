"""Team book step 3 — write the site's data.

    uv run python steps/teambook_export.py --history      # 2018–2025 from the store (local only)
    uv run python steps/teambook_export.py --live         # 2026 from nflverse, no store (CI)
    uv run python steps/teambook_export.py --history --live

``--history`` must have run once (its league files and carry file are committed) before
``--live`` can: the live season's comps and trends are drawn from them.
"""

from __future__ import annotations

import argparse
import json
import time

from fantasy_quant.teambook import export as E


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", action="store_true")
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()
    if not (args.history or args.live):
        ap.error("pass --history, --live, or both")
    report = {}
    if args.history:
        from fantasy_quant.data import db  # the store is only needed here

        t0 = time.time()
        report["history"] = E.export_history(db.connect(read_only=True))
        report["history"]["seconds"] = round(time.time() - t0, 1)
    if args.live:
        t0 = time.time()
        report["live"] = E.export_live()
        report["live"]["seconds"] = round(time.time() - t0, 1)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
