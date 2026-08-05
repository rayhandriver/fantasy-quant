"""Phase 0.13.7 done-bar — the unified scheme panel, and **B9**.

**B9 — the panel is generated and complete.** Every team-season 2016-2025 present, zero
silently-NULL columns, and fill rates recorded per column **per season** rather than whole-table
(the T50 correction applied to the panel's own register).

**B6 (panel half)** — a per-column floor request raises and names the column's floor, not its
table's.
"""

from __future__ import annotations

import json
from pathlib import Path

from fantasy_quant.data import breaks, db
from fantasy_quant.situation import scheme_panel as sp

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis" / "phase0_13_7_panel.json"


def main() -> None:
    con = db.connect()
    bm = breaks.build_break_map(con, tables=["participation", "ftn_charting"])

    week = sp.build_team_scheme_week(con)
    season = sp.build_team_scheme_season(con)
    week_z = sp.zscore_within_season(con, sp.WEEK_TABLE, sp.WEEK_Z_TABLE)
    season_z = sp.zscore_within_season(con, sp.SEASON_TABLE, sp.SEASON_Z_TABLE)
    register = sp.build_column_register(con, bm)

    # ---- B9a: every team-season present ------------------------------------------------------
    coverage = con.execute(f"""
        select season, count(distinct team) as teams, count(*) as rows_
        from {sp.SEASON_TABLE} group by 1 order by 1
    """).df()
    b9a = {
        "seasons": int(len(coverage)),
        "min_teams_in_a_season": int(coverage["teams"].min()),
        "seasons_missing_teams": coverage[coverage["teams"] != 32]["season"].tolist(),
    }
    b9a["PASS"] = bool(b9a["min_teams_in_a_season"] == 32)

    # ---- B9b: no silently-null column --------------------------------------------------------
    # a column that is null EVERYWHERE is a column that failed to build; a column null only below
    # its floor is a column doing exactly what the register says.
    dead = register[(register["fill_rate"] == 0.0)]
    below_floor_only = register[
        (register["fill_rate"] > 0)
        & register["declared_floor"].notna()
        & (register["observed_first_season"] >= register["declared_floor"])
    ]
    b9b = {
        "columns_registered": int(len(register)),
        "dead_columns": dead["column"].tolist(),
        "columns_with_a_declared_floor": int(register["declared_floor"].notna().sum()),
        "floors_respected": int(len(below_floor_only)),
        # ★ the floor bar applies only to columns that measure FOOTBALL. A coverage column
        # (charted_share, every *_denom) is honestly 0 before its floor — "none of these snaps
        # were charted" is true, and it is the column that explains the nulls beside it.
        "floor_violations": register[
            register["measures_football"]
            & register["declared_floor"].notna()
            & (register["observed_first_season"] < register["declared_floor"])
        ][["table", "column", "declared_floor", "observed_first_season"]].to_dict("records"),
        "coverage_columns_zero_before_floor": register[
            ~register["measures_football"]
            & register["declared_floor"].notna()
            & (register["observed_first_season"] < register["declared_floor"])
        ]["column"].tolist(),
    }
    b9b["PASS"] = len(dead) == 0 and len(b9b["floor_violations"]) == 0

    # ---- B9c: per-column PER-SEASON fill, not whole-table ------------------------------------
    watch = ["man_share", "charted_share", "share_cover_3", "motion_rate", "play_action_rate",
             "blitz_rate", "share_p11", "pass_rate_neutral", "proxy_two_high_share",
             "fourth_go_rate", "cap_share_wr", "continuity_offense"]
    sel = ", ".join(
        f"round(count({c}) / nullif(count(*), 0), 3) as {c}" for c in watch)
    per_season_fill = con.execute(f"""
        select season, count(*) as teams, {sel} from {sp.SEASON_TABLE} group by 1 order by 1
    """).df()

    # ---- B6 (panel half): the per-column floor is a guard -------------------------------------
    floor_guard = {}
    try:
        sp.assert_column_floor("man_share", 2016, bm)
        floor_guard["man_share_2016_raises"] = False
    except ValueError as exc:
        floor_guard["man_share_2016_raises"] = "2018" in str(exc)
    try:
        sp.assert_column_floor("man_share", 2018, bm)
        floor_guard["man_share_2018_allowed"] = True
    except ValueError:
        floor_guard["man_share_2018_allowed"] = False
    try:
        sp.assert_column_floor("motion_rate", 2019, bm)
        floor_guard["motion_2019_raises"] = False
    except ValueError as exc:
        floor_guard["motion_2019_raises"] = "2022" in str(exc)
    try:
        sp.assert_column_floor("share_p11", 2016, bm)
        floor_guard["table_floor_column_allowed"] = True
    except ValueError:
        floor_guard["table_floor_column_allowed"] = False

    # ---- the z-scores are z-scores ------------------------------------------------------------
    z_sanity = con.execute(f"""
        select round(avg(blitz_rate_z), 4)          as mean_z,
               round(stddev_samp(blitz_rate_z), 4)  as sd_z,
               count(blitz_rate_z)                  as n_z,
               (select count(*) from {sp.SEASON_Z_TABLE}
                 where season < 2018 and man_share_z is not null)  as z_before_floor
        from {sp.SEASON_Z_TABLE} where season = 2024
    """).df().iloc[0].to_dict()

    # ---- side symmetry: a team has an offense and a defense every week it plays ---------------
    symmetry = con.execute(f"""
        select count(*) filter (where not has_offense) as defense_only,
               count(*) filter (where not has_defense) as offense_only,
               count(*)                                as team_weeks
        from {sp.WEEK_TABLE}
    """).df().iloc[0].to_dict()

    out = {
        "step": "0.13.7 — the unified scheme panel",
        "team_scheme_week": week,
        "team_scheme_season": season,
        "team_scheme_week_z": week_z,
        "team_scheme_season_z": season_z,
        "column_register": {"table": sp.COLUMN_REGISTER, "n_rows": int(len(register))},
        "B9a_coverage": b9a,
        "B9b_no_dead_columns": b9b,
        "B9c_per_season_fill": per_season_fill.to_dict("records"),
        "B6_per_column_floor_guard": floor_guard,
        "z_sanity": {k: (None if v is None else float(v)) for k, v in z_sanity.items()},
        "side_symmetry": {k: int(v) for k, v in symmetry.items()},
        "coverage_by_season": coverage.to_dict("records"),
    }
    ANALYSIS.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps({k: out[k] for k in
                      ("team_scheme_week", "team_scheme_season", "team_scheme_week_z",
                       "team_scheme_season_z", "column_register", "B9a_coverage",
                       "B9b_no_dead_columns", "B6_per_column_floor_guard", "z_sanity",
                       "side_symmetry")}, indent=2, default=str))


if __name__ == "__main__":
    main()
