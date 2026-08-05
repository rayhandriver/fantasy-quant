"""Phase 0.13.6 done-bar — ``st_team_season`` + ``kicking_env_week``, head-coach attributed.

The bar with content here is the **attribution cross-check**: this module derives the head coach
from ``pbp`` independently of ``reference/coaches.csv``, which 0.13.1 audited against the same
source at zero mismatches. Two independent derivations agreeing is worth more than either one
asserting; a disagreement would mean the majority rule differs, which matters before a fingerprint
keys on either.
"""

from __future__ import annotations

import json
from pathlib import Path

from fantasy_quant.data import db
from fantasy_quant.situation import special_teams as st

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis" / "phase0_13_6_special_teams.json"


def main() -> None:
    con = db.connect()

    team_season = st.build_st_team_season(con)
    kick_env = st.build_kicking_env_week(con)

    mismatches = st.coach_attribution_check(con)
    agg = st.aggression_denominator_check(con)

    # ---- the behavioural denominator trap, stated ------------------------------------------
    trap = {
        "naive_go_rate_mean": round(float(agg["naive_go_rate"].mean()), 4),
        "conditioned_go_rate_mean": round(float(agg["conditioned_go_rate"].mean()), 4),
    }
    trap["ratio"] = round(
        trap["conditioned_go_rate_mean"] / max(trap["naive_go_rate_mean"], 1e-9), 2)

    # ---- the 4th-down era trend, which is the face-validity check ----------------------------
    era = con.execute(f"""
        select season,
               round(avg(fourth_go_rate), 4)   as go_rate,
               round(avg(two_point_rate), 4)   as two_point_rate,
               round(avg(rz_stall_rate), 4)    as rz_stall_rate,
               round(avg(fg_pct), 4)           as fg_pct,
               round(avg(fg_pct_long), 4)      as fg_pct_long
        from {st.ST_TABLE} group by 1 order by 1
    """).df()

    # ---- dome vs outdoors, the K-relevant split ----------------------------------------------
    # ⚠ every mean here ships with the count it was taken over. The first version reported a dome
    # temp of 46.0 F, which was the mean of TWO rows — a single 2025 game where the vendor logged
    # outdoor conditions on a closed roof — and read as a dome climate. *A mean without its n is a
    # number without a claim*, and this is the same defect class as a fill rate without its
    # denominator (DATA-1's lesson) one level down.
    env = con.execute(f"""
        select case when is_dome then 'dome' when is_outdoors then 'outdoors' else 'other' end
                   as venue,
               count(*)                                       as team_weeks,
               count(temp)                                    as temp_observed,
               round(avg(temp), 1)                            as temp_mean,
               count(wind)                                    as wind_observed,
               round(avg(wind), 2)                            as wind_mean,
               round(sum(fg_made) / nullif(sum(fg_att), 0), 4) as fg_pct,
               round(avg(fg_att), 3)                          as fg_att_per_week
        from {st.KICK_ENV_TABLE}
        where season between 2014 and 2025
        group by 1 order by 2 desc
    """).df()

    # ★ a negative result worth recording: the weather columns are NULL inside a dome, not
    # zero-filled — the OPPOSITE of T50, checked rather than assumed. Zero degrees and zero wind
    # would have read as the coldest, stillest venues in the league.
    dome_encoding = con.execute(f"""
        select count(*)                                   as dome_team_weeks,
               count(*) filter (where temp = 0)           as temp_zero_filled,
               count(*) filter (where wind = 0)           as wind_zero_filled,
               count(temp)                                as temp_populated,
               count(*) filter (where temp is null)       as temp_null
        from {st.KICK_ENV_TABLE} where is_dome
    """).df().iloc[0].to_dict()

    checks = con.execute(f"""
        select
          (select count(*) from {st.ST_TABLE} where head_coach is null)     as null_head_coach,
          (select count(distinct team) from {st.ST_TABLE} where season = 2024) as teams_2024,
          (select count(*) from {st.ST_TABLE}
            where fourth_go_rate > 1.0 or two_point_rate > 1.0)             as impossible_rate,
          (select count(*) from {st.ST_TABLE} where fg_made > fg_att)       as more_made_than_att,
          (select count(*) from {st.KICK_ENV_TABLE}
            where is_dome and wind is not null and wind > 0)          as wind_inside_a_closed_roof,
          (select count(*) from {st.KICK_ENV_TABLE} where team is null)     as null_team
    """).df().iloc[0].to_dict()

    out = {
        "step": "0.13.6 — special teams and the kicking environment",
        "st_team_season": team_season,
        "kicking_env_week": kick_env,
        "coach_attribution": {
            "mismatches_vs_coaches_csv": int(len(mismatches)),
            "rows": mismatches.head(20).to_dict("records"),
            "PASS": bool(len(mismatches) == 0),
        },
        "aggression_denominator_trap": trap,
        "by_season": era.to_dict("records"),
        "kicking_environment": env.to_dict("records"),
        "dome_weather_encoding": {k: (None if v is None else int(v))
                                  for k, v in dome_encoding.items()},
        "no_st_coordinator_table": (
            "user decision at scoping: 4th-down and 2-point aggression are head-coach decisions "
            "and pbp carries the head coach exactly and PIT, so a curated ST-coordinator CSV "
            "would spend human verification on a variable already attributable"
        ),
        "checks": {k: (None if v is None else float(v)) for k, v in checks.items()},
    }
    ANALYSIS.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps({k: out[k] for k in
                      ("st_team_season", "kicking_env_week", "coach_attribution",
                       "aggression_denominator_trap", "kicking_environment",
                       "dome_weather_encoding", "checks")},
                     indent=2, default=str))


if __name__ == "__main__":
    main()
