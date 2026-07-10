"""Stage 0 — recurring FFC ADP snapshot for the live season (default 2026), run + verify.

    uv run python steps/stage0_adp_snapshot.py             # bank today's board
    uv run python steps/stage0_adp_snapshot.py --season N  # a different live season

The 2026 board is unrecoverable after the season, so this banks a PIT snapshot series now
(THE PIPELINE, stage 0). Scheduled weekly; safe to run any time — appends only snapshot dates
the store doesn't have yet (idempotent), and replays the raw snapshot cache so a 0.4 table
rebuild can't lose the series.

Done when: new snapshot rows landed (or today's snapshot already exists), the gsis match rate
on the live board is sane (rookies may be unmatched until nflverse rosters update — logged,
not dropped), and ``adp_asof`` is PIT on the live season.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging

from fantasy_quant.data import db
from fantasy_quant.data.sources import adp


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026, help="live season to snapshot")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    con = db.connect()
    res = adp.snapshot_adp(con, args.season)
    print(f"\n=== snapshot_adp({args.season}) ===")
    print(f"  pulled configs : {len(res['pulled'])} ({', '.join(res['pulled']) or 'none'})")
    print(f"  new rows       : {res['new_rows']:,}")
    print(f"  new snapshots  : {res['snapshot_dates'] or '(none — already banked)'}")

    rows = con.execute(
        "SELECT scoring, teams, snapshot_date, COUNT(*) AS n FROM adp_snapshots "
        "WHERE season = ? GROUP BY ALL ORDER BY snapshot_date, scoring, teams",
        [args.season],
    ).df()
    print(f"\n=== {args.season} snapshot series in the store ===")
    print(rows.to_string(index=False) if len(rows) else "  (empty)")

    ok_rows = len(rows) > 0
    ok_match = True
    if ok_rows:
        total, matched = con.execute(
            "SELECT COUNT(*), COUNT(gsis_id) FROM adp_snapshots "
            "WHERE season = ? AND position NOT IN ('DEF','PK','K')", [args.season]
        ).fetchone()
        rate = matched / total if total else 0.0
        ok_match = rate >= 0.75  # live-season bar: rookies unmatched until rosters update
        print(f"\n  gsis match (skill rows): {matched}/{total} = {rate:.1%} "
              f"({'OK' if ok_match else 'LOW — check unmatched log'})")

        # PIT guard on the live season: day-before-first-snapshot must be empty.
        first = con.execute(
            "SELECT MIN(snapshot_date) FROM adp_snapshots WHERE season = ?", [args.season]
        ).fetchone()[0]
        before = len(adp.adp_asof(con, args.season, first - dt.timedelta(days=1)))
        latest = len(adp.adp_asof(con, args.season, dt.date.today()))
        print(f"  adp_asof PIT: day-before-first={before} rows (expect 0), today={latest} rows")
        ok_rows = before == 0 and latest > 50
    con.close()

    verdict = "PASS" if (ok_rows and ok_match) else "REVIEW"
    print(f"\n=== stage0_adp_snapshot: {verdict} ===")


if __name__ == "__main__":
    main()
