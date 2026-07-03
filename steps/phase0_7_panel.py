"""Phase 0.7 — PIT panel assembly, run + verify.

    uv run python steps/phase0_7_panel.py

Done when: two different as-of dates yield different panels, no field dated after as_of survives
(assert), and the same gsis_id lines up across sources (BUILD_PLAN.md 0.7).
"""

from __future__ import annotations

import logging

import pandas as pd

from fantasy_quant.data import db
from fantasy_quant.data.panel import assert_panel_pit, preseason_panel, weekly_panel


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    con = db.connect()

    print("=== done-criterion #1: two as-of dates yield different weekly panels ===")
    early = weekly_panel(con, 2023, "2023-10-15")
    late = weekly_panel(con, 2023, "2023-12-10", materialize=True)
    print(f"  as_of 2023-10-15: {len(early):,} rows, weeks 1–{int(early['week'].max())}, "
          f"max week_end={early['week_end_date'].max()}")
    print(f"  as_of 2023-12-10: {len(late):,} rows, weeks 1–{int(late['week'].max())}, "
          f"max week_end={late['week_end_date'].max()}")
    ok1 = len(late) > len(early) and late["week"].max() > early["week"].max()
    print(f"  -> {'PASS' if ok1 else 'REVIEW'} (later as_of strictly includes more weeks)")

    print("\n=== done-criterion #2: no field dated after as_of (PIT) ===")
    # the panel functions already assert internally; prove the guard also *catches* a leak.
    leaked = early.copy()
    leaked.loc[leaked.index[0], "week_end_date"] = pd.Timestamp("2024-01-01")
    caught = False
    try:
        assert_panel_pit(leaked, "2023-10-15", ["week_end_date"])
    except AssertionError:
        caught = True
    print(f"  real panels asserted clean on build; planted future value caught = {caught}")
    print(f"  -> {'PASS' if caught else 'REVIEW'}")

    print("\n=== done-criterion #3: gsis lines up across sources (spot check) ===")
    # a well-known 2023 WR week: stats + ADP + odds + injury all on one row.
    row = late[(late["player_name"].str.contains("Jefferson", na=False)) &
               (late["week"] == 5)]
    if len(row):
        r = row.iloc[0]
        print(f"  {r['player_name']} wk5: pts_ppr={r['fantasy_points_ppr']}, tgt={r['targets']}, "
              f"snap%={r['offense_pct']}, team_implied={r['team_implied_total']}, "
              f"adp={r['adp']}, sep={r['ngs_avg_separation']}")
    print("  columns joined:", len(late.columns))

    # FFC's season-aggregate ADP is dated ~Sep 1 (end of the preseason draft window), so a realistic
    # Labor-Day-weekend draft as-of picks it up; an earlier as_of correctly returns an empty board.
    print("\n=== preseason panel (2023 draft board as-of 2023-09-04) ===")
    pre = preseason_panel(con, 2023, "2023-09-04", materialize=True)
    print(f"  {len(pre):,} draftable players; top-5 by ADP:")
    for _, r in pre.head(5).iterrows():
        print(f"    {r['adp']:>5.1f}  {r['player_name']:<22} {r['position']:<3} "
              f"age={r['age_years']}  status={r['report_status']}")
    con.close()


if __name__ == "__main__":
    main()
