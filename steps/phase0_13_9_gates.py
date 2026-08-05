"""Phase 0.13.9 done-bar — per-column floors, PIT classes, the register, and **B5**, **B6**, **B8**.

The closing substep. Three bars land here:

- **B5 — the deep-dive questions return answers, end to end.** One printed query each, for the six
  questions that motivated the session. *A source is not ingested until the question that motivated
  it returns an answer.*
- **B6 — per-column floors are asserted, not documented.** A man/zone request for 2016 raises and
  names 2018. A prose warning is not a guard.
- **B8 — PIT classes hold**, and the assertion is **written to fail and verified failing**.
"""

from __future__ import annotations

import json
from pathlib import Path

from fantasy_quant.data import breaks, db, registry, validate
from fantasy_quant.situation import scheme_panel as sp

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis" / "phase0_13_9_gates.json"

#: The six questions from the ask, each as one query. Named so a failure says which question broke.
B5_QUESTIONS: dict[str, str] = {
    "most_played_front_and_coverage_per_team_season": """
        select team, season,
               round(share_nickel, 3) as nickel, round(share_base, 3) as base,
               round(share_dime, 3)   as dime,
               round(man_share, 3)    as man,
               round(share_cover_3, 3) as cover3, round(share_cover_1, 3) as cover1
        from team_scheme_season where season = 2024 order by share_nickel desc limit 5
    """,
    "blitz_pct_per_team_week": """
        select season, week, team, round(blitz_rate, 3) as blitz_rate, rushers_denom
        from defense_team_week
        where season = 2024 and rushers_denom >= 20 order by blitz_rate desc limit 5
    """,
    "single_high_vs_two_high_share": """
        select team, round(proxy_single_high_share, 3) as single_high,
               round(proxy_two_high_share, 3) as two_high,
               round(proxy_safeties_mean, 2)  as safeties_mean
        from team_scheme_season where season = 2024 order by proxy_two_high_share desc limit 5
    """,
    "cap_allocation_by_position_group": """
        select team, round(cap_share_qb, 3) as qb, round(cap_share_rb, 3) as rb,
               round(cap_share_wr, 3) as wr, round(cap_share_te, 3) as te,
               round(cap_share_ol, 3) as ol, round(cap_share_defense, 3) as def_
        from team_construction_season where season = 2024 order by cap_share_wr desc limit 5
    """,
    "backfield_carry_split": """
        select o.team, p.display_name, sum(o.carries) as carries,
               round(sum(o.carries) * 1.0 / sum(sum(o.carries)) over (partition by o.team), 3)
                   as carry_share
        from offense_player_week o
        left join players_master p on p.gsis_id = o.gsis_id
        where o.season = 2024 and o.team = 'PHI'
        group by 1, 2 having sum(o.carries) > 0 order by carries desc limit 5
    """,
    "target_share_within_personnel_grouping": """
        select o.team, p.display_name,
               sum(o.targets_p11) as tgt_11, sum(o.targets_p12) as tgt_12,
               round(sum(o.targets_p11) * 1.0
                     / nullif(sum(sum(o.targets_p11)) over (partition by o.team), 0), 3)
                   as share_in_11
        from offense_player_week o
        left join players_master p on p.gsis_id = o.gsis_id
        where o.season = 2024 and o.team = 'CIN'
        group by 1, 2 having sum(o.targets_p11) > 0 order by tgt_11 desc limit 5
    """,
}

#: The DATA-2 tables the standing gates must now cover.
DATA2_TABLES: tuple[str, ...] = (
    "defense_team_week", "defense_player_week", "defense_coverage_week",
    "offense_team_week", "offense_player_week", "team_construction_season",
    "st_team_season", "kicking_env_week", "team_scheme_week", "team_scheme_season",
)


def main() -> None:
    con = db.connect()
    bm = breaks.build_break_map(con, tables=["participation", "ftn_charting"])

    # ---- B5: the six questions ---------------------------------------------------------------
    b5 = {}
    for name, sql in B5_QUESTIONS.items():
        df = con.execute(sql).df()
        b5[name] = {"rows": int(len(df)), "answered": bool(len(df) > 0),
                    "sample": df.head(5).round(4).to_dict("records")}
    b5_pass = all(v["answered"] for v in b5.values())

    # ---- B6: per-column floors raise, and name the column ------------------------------------
    b6 = {}
    try:
        registry.assert_column_floor("participation", "defense_man_zone_type", 2016)
        b6["manzone_2016_raises"] = False
    except ValueError as exc:
        b6["manzone_2016_raises"] = "2018" in str(exc) and "per-COLUMN" in str(exc)
    try:
        registry.assert_column_floor("participation", "defense_man_zone_type", 2018)
        b6["manzone_2018_allowed"] = True
    except ValueError:
        b6["manzone_2018_allowed"] = False
    try:
        registry.assert_column_floor("participation", "offense_personnel", 2016)
        b6["table_floor_column_allowed_at_2016"] = True
    except ValueError:
        b6["table_floor_column_allowed_at_2016"] = False
    try:
        registry.assert_column_floor("ftn_charting", "is_motion", 2021)
        b6["ftn_2021_raises"] = False
    except ValueError as exc:
        b6["ftn_2021_raises"] = "2022" in str(exc)
    # the declared floor must agree with the MEASURED one — a declaration nothing checks is a note
    b6["declared_vs_measured"] = [
        {"table": t, "column": c, "declared": f, "measured": bm.floor(t, c)}
        for (t, c), f in registry.COLUMN_FLOORS.items()
    ]
    b6["declaration_matches_measurement"] = all(
        r["measured"] is None or r["declared"] == r["measured"]
        for r in b6["declared_vs_measured"])
    b6["PASS"] = bool(b6["manzone_2016_raises"] and b6["manzone_2018_allowed"]
                      and b6["table_floor_column_allowed_at_2016"] and b6["ftn_2021_raises"]
                      and b6["declaration_matches_measurement"])

    # ---- B8: PIT classes hold, and the guard is verified FAILING ------------------------------
    b8 = {"every_data2_table_declared": [], "undeclared": []}
    for t in DATA2_TABLES:
        try:
            s = registry.spec(t)
            b8["every_data2_table_declared"].append({"table": t, "pit_class": s.pit_class,
                                                     "floor": s.floor,
                                                     "backtestable": s.backtestable})
        except KeyError:
            b8["undeclared"].append(t)
    # ★ written to fail and VERIFIED failing: an in_season_weekly table used unlagged as a
    # draft feature must raise. A guard nobody has seen refuse anything is not known to work.
    try:
        registry.assert_pit_class_for_draft_feature("team_scheme_season", lagged=False)
        b8["unlagged_use_raises"] = False
    except ValueError:
        b8["unlagged_use_raises"] = True
    try:
        registry.assert_pit_class_for_draft_feature("team_scheme_season", lagged=True)
        b8["lagged_use_allowed"] = True
    except ValueError:
        b8["lagged_use_allowed"] = False
    try:
        registry.assert_backtestable("win_totals")
        b8["backtestable_false_raises"] = False
    except ValueError:
        b8["backtestable_false_raises"] = True
    b8["PASS"] = bool(not b8["undeclared"] and b8["unlagged_use_raises"]
                      and b8["lagged_use_allowed"] and b8["backtestable_false_raises"])

    # ---- the two-sided per-season fill gate, over the new tables ------------------------------
    fills = validate.store_fill_rates_by_season(con, tables=list(DATA2_TABLES))
    gate = validate.fill_rate_gate_by_season(fills, baseline=None)
    encoding = validate.encoding_break_gate(con)

    # ---- the panel's own column register ------------------------------------------------------
    register = con.execute(f"""
        select grain, count(*) as columns_,
               count(*) filter (where is_metric)          as metrics,
               count(*) filter (where declared_floor is not null) as with_floor,
               count(*) filter (where not backtestable)   as not_backtestable
        from {sp.COLUMN_REGISTER} group by 1 order by 1
    """).df()

    out = {
        "step": "0.13.9 — floors, PIT classes, register, backup",
        "B5_deep_dive_questions": {"PASS": b5_pass, **b5},
        "B6_per_column_floors": b6,
        "B8_pit_classes": b8,
        "per_season_fill_gate": {"tables": len(DATA2_TABLES), "result": gate},
        "encoding_break_gate": encoding,
        "column_register": register.to_dict("records"),
        "registry_size": len(registry.REGISTRY),
    }
    ANALYSIS.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps({
        "B5_answered": {k: v["answered"] for k, v in b5.items()},
        "B5_PASS": b5_pass,
        "B6_per_column_floors": {k: v for k, v in b6.items() if k != "declared_vs_measured"},
        "B8_pit_classes": {k: v for k, v in b8.items()
                           if k != "every_data2_table_declared"},
        "per_season_fill_gate": gate if isinstance(gate, dict) else str(gate),
        "encoding_break_gate": encoding,
        "registry_size": len(registry.REGISTRY),
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
