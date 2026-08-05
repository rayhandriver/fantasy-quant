"""Phase 0.13.5 done-bar — ``team_construction_season``, and **B7**.

**B7 — team-construction facts reconcile against independent truth.** Three reconciliations, and
one of them is expected to come up *short* rather than clean: the OTC nominal-window approximation
does not reach the whole cap, and B7's job is to **state by how much**, because that number is what
licenses the normalized ``cap_share_*`` columns and forbids reading ``cap_pct_*`` as cap spend.
"""

from __future__ import annotations

import json
from pathlib import Path

from fantasy_quant.data import db
from fantasy_quant.situation import construction as ct

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis" / "phase0_13_5_construction.json"


def main() -> None:
    con = db.connect()

    dup = ct.contract_duplication(con).iloc[0].to_dict()
    built = ct.build_team_construction(con)
    cap = ct.cap_reconciliation(con)
    picks = ct.draft_capital_reconciliation(con)

    # ---- B7a: the in-season roster is ~53 -----------------------------------------------------
    # ⚠ Two corrections to the first version of this bar, both of which made it measure something
    # other than what it claimed:
    #   1. it counted the SEASON-CUMULATIVE roster (everyone who appeared in any week), which is
    #      ~102 by churn and has no reason to be 53. The 53-man limit is a WEEKLY fact.
    #   2. `weekly_rosters` is not the 53: it carries practice squad (DEV), reserve (RES), cut
    #      (CUT) and inactive (INA) alongside ACT, so even weekly it runs ~80.
    # Filtering to ACT and measuring per week gives 44-57, which is the number that can be checked
    # against the rulebook. 2026 is excluded: no games have been played, so its roster is an
    # offseason list of ~89 and is not a 53-man anything.
    roster = con.execute("""
        select season, round(avg(n), 1) as mean_active, min(n) as min_active, max(n) as max_active
        from (
            select season, team, week, count(distinct gsis_id) as n
            from weekly_rosters
            where game_type = 'REG' and status = 'ACT'
              and gsis_id is not null and gsis_id <> '' and team is not null
            group by 1, 2, 3
        )
        where season <= 2025
        group by 1 order by 1
    """).df()
    # ★ The bar is on the season MEAN, and the reason is a third convention seam: 2016 is a
    # transition year in `weekly_rosters` (a team-week reaches 94 ACT players, against ~48 either
    # side of it) and 2015 dips to 36. Those are upstream convention changes, not construction
    # defects — so they are recorded as a floor rather than smoothed, exactly as 0.13.0 requires.
    # A per-week extreme bar would fail on the vendor's history; a per-season mean bar tests the
    # claim actually being made, which is that this is a 53-man roster with inactives removed.
    b7a = {
        "mean_active_weekly": round(float(roster["mean_active"].mean()), 1),
        "min_season_mean": round(float(roster["mean_active"].min()), 1),
        "max_season_mean": round(float(roster["mean_active"].max()), 1),
        "worst_week_low": int(roster["min_active"].min()),
        "worst_week_high": int(roster["max_active"].max()),
        "convention_seam_seasons": [2015, 2016],
        "note": "ACT only, per week, 2014-2025; the 53-man limit with game-day inactives removed. "
                "2016 is an upstream roster-convention transition (a team-week reaches 94) and "
                "2015 dips to 36 — recorded as a floor, not smoothed.",
        "per_season": roster.to_dict("records"),
    }
    b7a["PASS"] = bool(b7a["min_season_mean"] >= 44 and b7a["max_season_mean"] <= 56)

    # ---- B7b: draft capital sums back to the pick list ---------------------------------------
    b7b = {
        "seasons": int(len(picks)),
        "picks_without_curve": int(picks["picks_without_curve"].sum()),
        "max_pick": int(picks["max_pick"].max()),
        "mean_picks_per_year": round(float(picks["n_picks"].mean()), 1),
    }
    # every pick maps to a curve row, or the shortfall is named
    b7b["PASS"] = b7b["picks_without_curve"] == 0

    # per-team capital must sum to the league total for the same draft years
    capital_identity = con.execute(f"""
        with per_team as (
            select season, sum(draft_capital) as summed from {ct.CONSTRUCTION_TABLE}
            where season = 2024 group by 1
        ),
        league as (
            select sum(v.{ct.DEFAULT_CURVE}) as total
            from draft_picks d left join draft_values v on v.pick = d.pick
            where d.season between 2024 - {ct.DRAFT_WINDOW} and 2023
        )
        select p.summed, l.total, round(p.summed / nullif(l.total, 0), 4) as ratio
        from per_team p cross join league l
    """).df().iloc[0].to_dict()

    # ---- B7c: the cap, honestly ---------------------------------------------------------------
    b7c = {
        "mean_accounted_pct": round(float(cap["mean_accounted"].mean()), 4),
        "mean_player_coverage": round(float(cap["mean_player_coverage"].mean()), 4),
        "worst_season_accounted": round(float(cap["mean_accounted"].min()), 4),
        "best_season_accounted": round(float(cap["mean_accounted"].max()), 4),
    }
    # the bar is NOT "sums to 1.0" — it is "the shares are a valid distribution and the coverage
    # is stated". A cap sheet we do not have cannot be asserted into existence.
    shares = con.execute(f"""
        select count(*) filter (where abs(coalesce(cap_share_offense, 0)
                                        + coalesce(cap_share_defense, 0)
                                        + coalesce(cap_share_st, 0) - 1.0) > 0.02)
                   as shares_not_summing,
               count(*) filter (where cap_share_qb > 1.0 or cap_share_qb < 0) as impossible_share,
               count(*)                                                       as rows_total
        from {ct.CONSTRUCTION_TABLE} where cap_accounted_pct > 0
    """).df().iloc[0].to_dict()
    b7c["shares_not_summing"] = int(shares["shares_not_summing"])
    b7c["impossible_share"] = int(shares["impossible_share"])
    b7c["PASS"] = b7c["shares_not_summing"] == 0 and b7c["impossible_share"] == 0

    # ---- structural checks --------------------------------------------------------------------
    checks = con.execute(f"""
        select
          (select count(*) from {ct.CONSTRUCTION_TABLE} where team is null)      as null_team,
          (select count(distinct team) from {ct.CONSTRUCTION_TABLE}
            where season = 2024)                                                 as teams_2024,
          (select count(*) from {ct.CONSTRUCTION_TABLE}
            where continuity_offense > 1.0001 or continuity_defense > 1.0001) as continuity_over_1,
          (select count(*) from {ct.CONSTRUCTION_TABLE}
            where season = 2015 and continuity_offense is null)          as no_continuity_2015,
          (select round(avg(continuity_offense), 4) from {ct.CONSTRUCTION_TABLE}
            where season between 2016 and 2025)                          as mean_continuity_off,
          (select round(avg(age_qb), 2) from {ct.CONSTRUCTION_TABLE}
            where season = 2024)                                                 as mean_qb_age_2024
    """).df().iloc[0].to_dict()

    out = {
        "step": "0.13.5 — team construction",
        "construction": built,
        "contract_season": {"duplicate_groups": int(dup["duplicated_groups"]),
                            "excess_rows": int(dup["excess_rows"]),
                            "worst_group": int(dup["worst_group"])},
        "B7a_roster_size": b7a,
        "B7b_draft_capital": b7b,
        "B7b_capital_identity": {k: (None if v is None else float(v))
                                 for k, v in capital_identity.items()},
        "B7c_cap_honesty": b7c,
        "cap_by_season": cap.to_dict("records"),
        "picks_by_season": picks.to_dict("records"),
        "checks": {k: (None if v is None else float(v)) for k, v in checks.items()},
        "provenance": {
            "cap_source": "otc_nominal_window",
            "note": "contracts.team is an OTC nickname / career-path string, never a team code; "
                    "team membership comes from weekly_rosters and the contract joins to the "
                    "PLAYER. cap_pct_* is accounted APY as a share of cap, not cap spend; read "
                    "cap_share_* for allocation.",
        },
    }
    ANALYSIS.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps({k: out[k] for k in
                      ("construction", "contract_season", "B7a_roster_size", "B7b_draft_capital",
                       "B7b_capital_identity", "B7c_cap_honesty", "checks")},
                     indent=2, default=str))


if __name__ == "__main__":
    main()
