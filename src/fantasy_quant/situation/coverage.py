"""Phase 0.13.3 — coverage shells and the secondary, in **three tiers that are never blurred**.

The user asked for "safety coverage" by name. It does not resolve to one thing, and the whole value
of this module is that it refuses to pretend it does:

1. **Charted shell** — ``participation.defense_coverage_type`` (COVER_0/1/2/3/4/6/9, 2_MAN, COMBO).
   A real observation of the called coverage, on ~49 % of plays, **2018+**. This is the only tier
   that is a measurement of coverage.
2. **Derived safety count** — how many safeties were on the field, from the eleven men. A
   **personnel proxy** for single-high vs two-high: it says who was out there, never where he
   lined up or where he went at the snap. It is labelled a proxy in the column names, in the
   provenance flag and here.
3. **Pre-snap alignment depth and post-snap rotation** — **does not exist free.** It goes in the
   register as a floor and the do-not-chase rule applies verbatim: *a session that ends with
   "still missing single-high alignment" has misunderstood the register.*

★ **Tier 2 has TWO provenances and they are not equally good.** The scoping doc claimed the derived
safety count runs at "~76 % pre-2023 / ~100 % after" off ``defense_positions``. Measured: that
column is **0.000 before 2023** — it is a 2023+ column whose table floors at 2016 (T49 again, one
level finer). So pre-2023 the count is resolved by looking each on-field defender up in
``weekly_rosters.depth_chart_position``, which is a **roster** position rather than a charted one
and is generically ``DB`` for ~13 % of the secondary. Both paths are recorded per row in
``safety_provenance``, because a number that changes meaning at a season boundary and does not say
so is precisely the T50 failure this session exists to fix.

⚠ **2023-2025 is where the charted path lives, and 2023+2024 is the spent lockbox.** Deriving these
facts does not spend it; building a feature on them would. The charted tier is therefore a
descriptive/live layer in practice, like FTN — DEV has only the roster-lookup path.
"""

from __future__ import annotations

import logging

from fantasy_quant.data.breaks import BreakMap

log = logging.getLogger(__name__)

COVERAGE_WEEK_TABLE = "defense_coverage_week"

#: The charted shells, in the vendor's vocabulary. PREVENT and BLOWN are kept separate rather than
#: folded into a neighbour: "blown" is a charting verdict about execution, not a called coverage.
SHELLS: tuple[str, ...] = ("COVER_0", "COVER_1", "COVER_2", "COVER_3", "COVER_4", "COVER_6",
                           "COVER_9", "2_MAN", "COMBO", "PREVENT", "BLOWN")

#: Tokens that mean "safety" in either position vocabulary. ``DB`` is deliberately NOT here: it is
#: the generic that makes the roster path a proxy, and counting it as a safety would manufacture
#: two-high looks out of nickel corners.
SAFETY_TOKENS: tuple[str, ...] = ("FS", "SS", "S", "SAF", "SAFETY")

#: ★ Registered as unobtainable. Do not re-investigate; do not approximate with tier 2 and call it
#: this. Free sources chart *which* coverage, never *where the man stood*.
NOT_OBTAINABLE_FREE: tuple[str, ...] = (
    "pre-snap safety alignment depth (yards off the ball)",
    "post-snap safety rotation (the actual single-high/two-high disguise)",
    "individual defender alignment coordinates",
)


def build_coverage_week(con, bm: BreakMap) -> dict:
    """One row per (season, week, defending team): shell shares plus the safety-count proxy."""
    shell_cols = ",\n            ".join(
        f"avg(case when defense_coverage_type = '{s}' then 1.0 else 0.0 end) "
        f"filter (where charted) as share_{s.lower()}"
        for s in SHELLS
    )
    safety_in = ", ".join(f"'{t}'" for t in SAFETY_TOKENS)

    con.execute(f"""
        create or replace table {COVERAGE_WEEK_TABLE} as
        with on_field as (
            -- one row per (play, defender), with the best position we can resolve for him and a
            -- flag for WHICH source resolved it
            select distinct on (v.game_id, v.play_id, v.gsis_id)
                   v.season, v.week, v.game_id, v.play_id, b.defteam as team,
                   nullif(upper(trim(v.position)), '')                     as charted_pos,
                   upper(trim(r.depth_chart_position))                     as roster_pos
            from {"participation_defense_player_play"} v
            left join pbp b using (game_id, play_id)
            left join weekly_rosters r
                   on r.season = v.season and r.week = v.week and r.gsis_id = v.gsis_id
            where b.defteam is not null and b.play_type in ('pass', 'run')
              and v.gsis_id is not null and v.gsis_id <> ''
        ),
        per_play as (
            select season, week, game_id, play_id, team,
                   count(*) filter (where charted_pos in ({safety_in}))       as safeties_charted,
                   count(*) filter (where roster_pos in ({safety_in}))        as safeties_roster,
                   count(*) filter (where charted_pos is not null)            as n_charted,
                   count(*) filter (where roster_pos = 'DB')                  as n_generic_db,
                   count(*)                                                   as n_men
            from on_field group by 1, 2, 3, 4, 5
        ),
        joined as (
            select p.*,
                   -- ★ the charted count where it exists, the roster lookup before that, and the
                   -- provenance recorded rather than inferred from the season by the reader
                   case when p.n_charted > 0 then p.safeties_charted else p.safeties_roster end
                                                                          as safeties,
                   case when p.n_charted > 0 then 'charted_positions'
                        when p.n_generic_db < p.n_men then 'roster_lookup'
                        else 'unresolved' end                             as safety_provenance,
                   c.defense_coverage_type,
                   (c.defense_coverage_type is not null
                    and c.defense_coverage_type <> '')                    as charted
            from per_play p
            join participation c using (game_id, play_id)
        )
        select
            season, week, team,
            count(*)                                                      as snaps,
            count(*) filter (where charted)                               as charted_snaps,
            round(count(*) filter (where charted) / nullif(count(*), 0), 4) as charted_share,
            {shell_cols},
            -- tier 2: a PERSONNEL proxy. Named so in the column, not only in the docs.
            avg(safeties)                                                 as proxy_safeties_mean,
            avg(case when safeties = 1 then 1.0 else 0.0 end)            as proxy_single_high_share,
            avg(case when safeties = 2 then 1.0 else 0.0 end)             as proxy_two_high_share,
            avg(case when safeties >= 3 then 1.0 else 0.0 end)            as proxy_three_deep_share,
            mode(safety_provenance)                                       as safety_provenance,
            round(avg(case when safety_provenance = 'unresolved' then 1.0 else 0.0 end), 4)
                                                                          as proxy_unresolved_share,
            round(avg(n_generic_db), 3)                                   as generic_db_per_snap,
            current_localtimestamp()                                      as pulled_at
        from joined
        group by 1, 2, 3
    """)
    n, teams, seasons = con.execute(
        f"select count(*), count(distinct team), count(distinct season) from {COVERAGE_WEEK_TABLE}"
    ).fetchone()
    floor = bm.floor("participation", "defense_coverage_type")
    return {"table": COVERAGE_WEEK_TABLE, "n_rows": int(n), "n_teams": int(teams),
            "n_seasons": int(seasons), "charted_floor": floor}


def validate_proxy_against_charted(con, seasons: tuple[int, ...] = (2023, 2024, 2025)):
    """★ Check the **roster-lookup** safety count against the **charted** one where both exist.

    The two provenances never overlap in the shipped table by construction — charted wins from
    2023, roster is used before it — so without this the pre-2023 half of tier 2 would be an
    unvalidated assumption carried across seven seasons. 2023-2025 has both, which makes the
    earlier path testable against the later one exactly once.

    Returns per-season exact agreement, mean counts, bias and two-high agreement.
    """
    safety_in = ", ".join(f"'{t}'" for t in SAFETY_TOKENS)
    return con.execute(f"""
        with on_field as (
            select distinct on (v.game_id, v.play_id, v.gsis_id)
                   v.season, v.game_id, v.play_id,
                   nullif(upper(trim(v.position)), '')                  as charted_pos,
                   upper(trim(r.depth_chart_position))                  as roster_pos
            from participation_defense_player_play v
            left join pbp b using (game_id, play_id)
            left join weekly_rosters r
                   on r.season = v.season and r.week = v.week and r.gsis_id = v.gsis_id
            where b.defteam is not null and b.play_type in ('pass', 'run')
              and v.gsis_id is not null and v.gsis_id <> ''
              and v.season in {tuple(seasons)}
        ),
        per_play as (
            select season, game_id, play_id,
                   count(*) filter (where charted_pos in ({safety_in})) as charted,
                   count(*) filter (where roster_pos  in ({safety_in})) as roster
            from on_field group by 1, 2, 3
        )
        select season, count(*) as plays,
               round(avg(case when charted = roster then 1.0 else 0.0 end), 4)   as exact_agree,
               round(avg(charted), 3)                                            as charted_mean,
               round(avg(roster), 3)                                             as roster_mean,
               round(avg(cast(roster as double) - charted), 3)                   as bias,
               round(avg(case when (charted >= 2) = (roster >= 2) then 1.0 else 0.0 end), 4)
                                                                                 as two_high_agree
        from per_play group by 1 order by 1
    """).df()


def assert_shell_floor(season: int, bm: BreakMap) -> None:
    """★ A prose warning is not a guard (UI-1's lesson 4). Asking for a charted shell in a season
    that has none **raises**, and names the floor rather than returning zeros that look like
    "this team never played Cover 3"."""
    floor = bm.floor("participation", "defense_coverage_type") or 2018
    if season < floor:
        raise ValueError(
            f"charted coverage shells do not exist before {floor} (asked for {season}). "
            "The participation TABLE floors at 2016, but this COLUMN floors later — see T49. "
            "Use the tier-2 safety-count proxy for earlier seasons, and label it one."
        )
