"""Phase 0.13.2 done-bar — build ``defense_team_week`` / ``defense_player_week`` and state B2.

★ **B2 is the headline bar of this session and it runs here: prove the trap is real FIRST, then
prove the gate closes it.** The naive blitz rate and the gated one are computed side by side, per
season, and the gap is printed. A fix whose effect is unmeasured is a claim, not a fix.
"""

from __future__ import annotations

import json
from pathlib import Path

from fantasy_quant.data import breaks, db
from fantasy_quant.situation import defense_scheme as ds

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis" / "phase0_13_2_defense_facts.json"


def main() -> None:
    con = db.connect()
    bm = breaks.build_break_map(con, tables=["participation"])

    rates = ds.blitz_rate(con, bm)
    team = ds.build_defense_team_week(con, bm)
    player = ds.build_defense_player_week(con, bm)

    # ---- B2: the size of the trap, stated -------------------------------------------------
    pre = rates[rates["season"] <= 2022]
    post = rates[rates["season"] >= 2023]
    b2 = {
        "naive_rate_pre2023": round(float(pre["naive_rate"].mean()), 4),
        "naive_rate_post2023": round(float(post["naive_rate"].mean()), 4),
        "gated_rate_pre2023": round(float(pre["gated_rate"].mean()), 4),
        "gated_rate_post2023": round(float(post["gated_rate"].mean()), 4),
        "naive_rushers_pre2023": round(float(pre["naive_rushers"].mean()), 3),
        "naive_rushers_post2023": round(float(post["naive_rushers"].mean()), 3),
        "gated_rushers_pre2023": round(float(pre["gated_rushers"].mean()), 3),
        "gated_rushers_post2023": round(float(post["gated_rushers"].mean()), 3),
    }
    b2["naive_break_size"] = round(b2["naive_rate_post2023"] - b2["naive_rate_pre2023"], 4)
    b2["gated_break_size"] = round(b2["gated_rate_post2023"] - b2["gated_rate_pre2023"], 4)
    b2["trap_closed"] = abs(b2["gated_break_size"]) < abs(b2["naive_break_size"]) / 2

    # a league-wide blitz rate has a known plausible range; assert we are inside football
    plausible = (0.15 <= b2["gated_rate_pre2023"] <= 0.45
                 and 0.15 <= b2["gated_rate_post2023"] <= 0.45)

    # ---- the identities that decide whether the two tables can be trusted -----------------
    coverage_floor = bm.floor("participation", "defense_man_zone_type")
    checks = con.execute(f"""
        select
          (select count(*) from {ds.TEAM_WEEK_TABLE} where team is null)          as null_team,
          (select count(*) from {ds.TEAM_WEEK_TABLE}
            where share_base + share_nickel + share_dime + share_quarter
                + share_heavy_box > 1.0001)                                       as share_overflow,
          (select count(*) from {ds.TEAM_WEEK_TABLE}
            where man_zone_denom > 0 and season < 2018)                     as manzone_before_floor,
          (select max(snap_share) from {ds.PLAYER_WEEK_TABLE})                    as max_snap_share,
          (select count(distinct team) from {ds.TEAM_WEEK_TABLE} where season = 2024) as teams_2024
    """).df().iloc[0].to_dict()

    out = {
        "step": "0.13.2 — the defensive fact tables",
        "team_week": team,
        "player_week": player,
        "personnel_strings": int(con.execute(
            f"select count(*) from {ds.PERSONNEL_MAP_TABLE}").fetchone()[0]),
        "unparsed_personnel_strings": int(con.execute(
            f"select count(*) from {ds.PERSONNEL_MAP_TABLE} where package is null").fetchone()[0]),
        "B2_blitz_naive_vs_gated": b2,
        "B2_rate_is_plausible": bool(plausible),
        "per_season": rates.round(4).to_dict("records"),
        "man_zone_floor": coverage_floor,
        "checks": {k: (None if v is None else float(v)) for k, v in checks.items()},
    }
    ANALYSIS.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps({k: out[k] for k in
                      ("team_week", "player_week", "personnel_strings",
                       "unparsed_personnel_strings", "B2_blitz_naive_vs_gated",
                       "B2_rate_is_plausible", "man_zone_floor", "checks")},
                     indent=2, default=str))


if __name__ == "__main__":
    main()
