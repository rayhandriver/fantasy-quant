"""Phase 2.3 — props-implied projection, run + verify (repackage the sharp market as points).

    uv run python steps/phase2_3_props.py

Done when (BUILD_PLAN.md 2.3): the props->points math is correct and ready; the historical-props
data gap is documented (props are the paid gap — see findings 0.5); the board no-ops to ADP for now.
"""

from __future__ import annotations

import pandas as pd

from fantasy_quant.data import db
from fantasy_quant.markets.props_projection import (
    props_available,
    props_projection,
    season_props_projection,
)


def main() -> None:
    # -- the math works on (synthetic) de-vig'd season props ---------------------------------
    print("=== props -> fantasy points (synthetic de-vig'd season props) ===")
    props = pd.DataFrame({
        "player_key": ["wr_elite", "rb_bell", "qb1"],
        "pos": ["WR", "RB", "QB"],
        "rec_yds": [1275.0, 450.0, 0.0], "receptions": [95.0, 55.0, 0.0],
        "rec_tds": [8.0, 2.0, 0.0], "rush_yds": [0.0, 1100.0, 350.0], "rush_tds": [0.0, 9.0, 3.0],
        "pass_yds": [0.0, 0.0, 4600.0], "pass_tds": [0.0, 0.0, 34.0],
        "interceptions": [0.0, 0.0, 11.0],
    })
    out = props_projection(props)
    for _, r in out.iterrows():
        print(f"  {r['pos']:<3} {r['player_key']:<10} -> {r['proj_points']:.1f} projected pts")
    # WR: 1275*.1 + 95 + 8*6 = 270.5 ; QB: 4600*.04 + 34*4 - 11*2 + 350*.1 + 3*6 = 351.0
    assert abs(out.loc[out["player_key"] == "wr_elite", "proj_points"].iloc[0] - 270.5) < 1e-6
    assert abs(out.loc[out["player_key"] == "qb1", "proj_points"].iloc[0] - 351.0) < 1e-6
    print("  [PASS] the market->fantasy-points mapping is correct and ready.\n")

    # -- the documented data gap: no historical preseason props for free ---------------------
    con = db.connect(read_only=True)
    have = props_available(con)
    empty = season_props_projection(con, 2023, "2023-09-04")
    print("=== historical props availability (the paid gap) ===")
    print(f"  props_available(con) = {have}")
    print(f"  season_props_projection(2023) rows = {len(empty)} (empty -> ADP fallback)")
    assert have is False and empty.empty, "expected the free-data no-op until props are wired"
    print("  [PASS] no historical preseason props on free data (the-odds-api live-only; win totals")
    print("         empty; game_lines are gameday-dated). The path is built + tested; a key/paid")
    print("         archive activates vbd_rank_fn(season_props_projection) with no code change.")

    print("\nPhase 2.3 (props-implied projection) — math ready, data gap documented: PASS.")
    con.close()


if __name__ == "__main__":
    main()
