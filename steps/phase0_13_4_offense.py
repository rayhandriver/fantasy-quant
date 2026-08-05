"""Phase 0.13.4 done-bar — ``offense_team_week`` / ``offense_player_week``, and **B4**.

Two bars run here:

- **B4 — offense and defense reconcile play-for-play.** Every play resolves 11-and-11 where the
  vendor's own ``n_offense``/``n_defense`` say it should, and the offensive player-week table sits
  within a stated tolerance of the defensive one built in 0.13.2.
- **the high-cardinality blind spot, measured.** ``offense_personnel``'s naive fill jumps
  0.754 → 1.000 at 2023 and the 0.13.0 break map cannot see it (the column is above
  ``MAX_CARDINALITY``, and the arriving mass spreads over hundreds of strings rather than landing
  on one sentinel). Conditioned on scrimmage plays the fill is 1.000 in **every** season, which is
  what licenses the rates to pool across the break. Same shape as B2, second instrument.
"""

from __future__ import annotations

import json
from pathlib import Path

from fantasy_quant.data import breaks, db
from fantasy_quant.situation import offense_scheme as os_

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis" / "phase0_13_4_offense.json"


def main() -> None:
    con = db.connect()
    bm = breaks.build_break_map(con, tables=["participation"])

    fill = os_.scrimmage_fill_by_season(con)
    team = os_.build_offense_team_week(con, bm)
    player = os_.build_offense_player_week(con, bm)
    recon = os_.reconcile_sides(con)

    # ---- the blind spot, stated the way B2 states the blitz trap ---------------------------
    pre = fill[fill["season"] <= 2022]
    post = fill[fill["season"] >= 2023]
    blind = {
        "naive_fill_pre2023": round(float(pre["offense_personnel_naive"].mean()), 4),
        "naive_fill_post2023": round(float(post["offense_personnel_naive"].mean()), 4),
        "scrimmage_fill_pre2023": round(float(pre["offense_personnel_scrimmage"].mean()), 4),
        "scrimmage_fill_post2023": round(float(post["offense_personnel_scrimmage"].mean()), 4),
        "n_strings_pre2023": int(pre["n_personnel_strings"].max()),
        "n_strings_post2023": int(post["n_personnel_strings"].max()),
    }
    blind["naive_break_size"] = round(
        blind["naive_fill_post2023"] - blind["naive_fill_pre2023"], 4)
    blind["scrimmage_break_size"] = round(
        blind["scrimmage_fill_post2023"] - blind["scrimmage_fill_pre2023"], 4)
    blind["population_filter_closes_it"] = abs(blind["scrimmage_break_size"]) < 0.01
    blind["break_map_sees_it"] = any(
        b.table == "participation" and b.column == "offense_personnel"
        for b in bm.breaks)

    # ---- B4a: 11-and-11, each side against ITS OWN denominator -------------------------------
    b4_rows = recon.to_dict("records")
    b4 = {
        "plays": int(recon["plays"].sum()),
        "offense_claims_11": int(recon["offense_claims_11"].sum()),
        "offense_resolves": int(recon["offense_resolves"].sum()),
        "defense_claims_11": int(recon["defense_claims_11"].sum()),
        "defense_resolves": int(recon["defense_resolves"].sum()),
        "missing_lists": int(recon["missing_lists"].sum()),
    }
    b4["offense_resolve_rate"] = round(
        b4["offense_resolves"] / max(b4["offense_claims_11"], 1), 6)
    b4["defense_resolve_rate"] = round(
        b4["defense_resolves"] / max(b4["defense_claims_11"], 1), 6)
    b4["PASS"] = (b4["offense_resolve_rate"] > 0.999
                  and b4["defense_resolve_rate"] > 0.999
                  and b4["offense_resolve_rate"] <= 1.0
                  and b4["defense_resolve_rate"] <= 1.0)

    # ---- B4b: the exploded tables account for eleven men per scrimmage play -------------------
    pw = os_.reconcile_player_weeks(con)
    b4b = {
        "offense_ratio_min": round(float(pw["offense_ratio"].min()), 4),
        "offense_ratio_max": round(float(pw["offense_ratio"].max()), 4),
        "defense_ratio_min": round(float(pw["defense_ratio"].min()), 4),
        "defense_ratio_max": round(float(pw["defense_ratio"].max()), 4),
        "dropped_offense_lists": int(pw["no_offense_list"].sum()),
        "dropped_defense_lists": int(pw["no_defense_list"].sum()),
        "offense_plays_not_eleven": int(pw["offense_not_eleven"].sum()),
        "defense_plays_not_eleven": int(pw["defense_not_eleven"].sum()),
    }
    # one-sided-tight against the LISTS, not against football's eleven: the explode collapses the
    # duplicate gsis_ids the vendor emits, so actual <= expected, and a ratio ABOVE 1 would mean a
    # man counted twice on one play — the exact defect 0.13.2's `distinct on` exists to prevent.
    b4b["PASS"] = (b4b["offense_ratio_min"] >= 0.99 and b4b["offense_ratio_max"] <= 1.0
                   and b4b["defense_ratio_min"] >= 0.99 and b4b["defense_ratio_max"] <= 1.0)

    # ---- FTN is guarded, not merely documented ----------------------------------------------
    ftn_guard = {}
    try:
        os_.assert_ftn_backtestable([2019, 2020])
        ftn_guard["raises_below_floor"] = False
    except ValueError as exc:
        ftn_guard["raises_below_floor"] = "2022" in str(exc)
    try:
        os_.assert_ftn_backtestable([2022])
        ftn_guard["raises_on_dev_only_request"] = False
    except ValueError as exc:
        ftn_guard["raises_on_dev_only_request"] = "backtestable" in str(exc)
    try:
        os_.assert_ftn_backtestable([2024, 2025])
        ftn_guard["allows_descriptive_live_use"] = True
    except ValueError:
        ftn_guard["allows_descriptive_live_use"] = False

    checks = con.execute(f"""
        select
          (select count(*) from {os_.TEAM_WEEK_TABLE} where team is null)           as null_team,
          (select count(*) from {os_.TEAM_WEEK_TABLE}
            where share_p11 + share_p12 + share_p21 + share_p13 + share_p22
                + share_p10 + share_p_other > 1.0001)                          as share_overflow,
          (select count(*) from {os_.TEAM_WEEK_TABLE}
            where season < {os_.FTN_FLOOR} and ftn_snaps > 0)                as ftn_before_floor,
          (select count(*) from {os_.TEAM_WEEK_TABLE}
            where season >= {os_.FTN_FLOOR} and motion_rate is null)          as ftn_missing_after,
          (select max(snap_share) from {os_.PLAYER_WEEK_TABLE})                as max_snap_share,
          (select count(distinct team) from {os_.TEAM_WEEK_TABLE} where season = 2024)
                                                                              as teams_2024,
          (select count(*) from {os_.PERSONNEL_MAP_TABLE} where package is null)
                                                                          as unparsed_strings,
          -- ★ "unparsed" must be read as PLAYS, not as strings, and split by population: every
          -- one of these is a kick unit (K/LS/P in the eleven), which the parser refuses a package
          -- label on purpose. The scrimmage residue is fakes, and it is the number worth watching.
          (select count(*) from participation p join {os_.PERSONNEL_MAP_TABLE} m
             using (offense_personnel) where m.package is null)            as unparsed_plays,
          (select count(*) from participation p join {os_.PERSONNEL_MAP_TABLE} m
             using (offense_personnel) left join pbp b using (game_id, play_id)
           where m.package is null and b.play_type in ('pass','run'))  as unparsed_scrimmage_plays
    """).df().iloc[0].to_dict()

    routes = con.execute(f"""
        select season,
               sum(routes_charted)      as charted,
               sum(routes_deep)         as deep,
               sum(routes_intermediate) as intermediate,
               sum(routes_short)        as short,
               sum(routes_behind_los)   as behind_los
        from {os_.PLAYER_WEEK_TABLE} group by 1 order by 1
    """).df()

    out = {
        "step": "0.13.4 — the offensive completion",
        "team_week": team,
        "player_week": player,
        "personnel_strings": int(con.execute(
            f"select count(*) from {os_.PERSONNEL_MAP_TABLE}").fetchone()[0]),
        "high_cardinality_blind_spot": blind,
        "B4a_play_for_play": b4,
        "B4a_per_season": b4_rows,
        "B4b_eleven_men_per_play": b4b,
        "B4b_per_season": pw.to_dict("records"),
        "ftn_guard": ftn_guard,
        "route_tree_by_season": routes.to_dict("records"),
        "alignment_not_obtainable_free": [
            "slot / wide / inline alignment (PFF-charted; offense_positions is the LISTED "
            "roster position, never where the man lined up)",
            "pre-snap receiver split and stack/bunch identification",
        ],
        "checks": {k: (None if v is None else float(v)) for k, v in checks.items()},
        "fill_by_season": fill.to_dict("records"),
    }
    ANALYSIS.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps({k: out[k] for k in
                      ("team_week", "player_week", "personnel_strings",
                       "high_cardinality_blind_spot", "B4a_play_for_play",
                       "B4b_eleven_men_per_play", "ftn_guard", "checks")},
                     indent=2, default=str))


if __name__ == "__main__":
    main()
