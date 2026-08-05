"""Phase 0.13.6 — **special teams and the kicking environment**, attributed to the head coach.

★ **No special-teams coordinator table** (user decision, taken at scoping). The two ST-adjacent
facts a fantasy model actually wants — 4th-down go-rate and 2-point aggression — are **head-coach**
decisions, and ``pbp`` carries the head coach exactly and PIT. Curating a third
research-and-review CSV to attribute a variable we can already attribute would be spending the
scarce resource (human verification) on the one thing a feed already answers: the 16.5
derived-vs-curated rule, applied to a table we chose not to build.

What this module *does* build:

* ``st_team_season`` — 4th-down aggression, 2-point aggression, field-goal profile by distance,
  punt and return profile, red-zone stall rate, each keyed to the season's head coach so a regime
  can be fingerprinted;
* ``kicking_env_week`` — the environment a kicker actually kicked in (``roof``/``surface``/
  ``temp``/``wind``), because dome-vs-outdoor and wind are the two things that move a K
  projection and neither is in any of our existing tables.

⚠ **Aggression must be measured against OPPORTUNITY, not against plays.** A team that trails all
year faces more 4th-and-short and attempts more 2-point conversions without being any more
aggressive. Every rate here is conditioned on the situation that offered the choice — 4th down in
"go" range, and a touchdown that permitted a 2-point try — which is the same denominator discipline
0.13.2 applied to the blitz rate, in a place where the trap is behavioural rather than a vendor
encoding.
"""

from __future__ import annotations

import logging

import pandas as pd

from fantasy_quant.data.teams import canon_team_sql as canon

log = logging.getLogger(__name__)

ST_TABLE = "st_team_season"
KICK_ENV_TABLE = "kicking_env_week"

#: A 4th-down "go" opportunity: close enough to matter, short enough that going is a live choice,
#: and not garbage time. Deliberately narrow — the rate is meaningless over all 4th downs, where
#: punting from your own 20 on 4th-and-15 dominates the denominator.
GO_MAX_DISTANCE = 5
GO_MIN_YARDLINE = 30       # opponent's 30 or closer is FG range; beyond it, punting competes
GO_MAX_YARDLINE = 70       # inside our own 30 the choice is not really open
NEUTRAL_SCORE_MARGIN = 14  # outside two scores, aggression is a function of the scoreboard


def build_st_team_season(con) -> dict:
    """One row per (season, team): the coach's decisions, and the kicking profile.

    ``head_coach`` comes from ``pbp``'s own ``home_coach``/``away_coach``, taking the coach of
    record for the majority of games — the same scaffold ``situation/coaches.py`` uses for its
    audit, reused rather than re-derived.
    """
    con.execute(f"""
        create or replace table {ST_TABLE} as
        with hc as (
            -- the head coach of record per team-season, majority of games. ⚠ from 2024 pbp emits
            -- a SEASON-level coach of record rather than the game-day coach, so a mid-season
            -- firing is invisible; `situation/coaches.py` documents this and it applies verbatim.
            select season, team, coach as head_coach, games
            from (
                select season, team, coach, count(distinct game_id) as games,
                       row_number() over (partition by season, team
                                          order by count(distinct game_id) desc, coach) as rn
                from (
                    select season, {canon('home_team')} as team, home_coach as coach, game_id
                      from pbp where home_coach is not null
                    union all
                    select season, {canon('away_team')} as team, away_coach as coach, game_id
                      from pbp where away_coach is not null
                )
                group by 1, 2, 3
            ) where rn = 1
        ),
        fourth as (
            -- ★ conditioned on the OPPORTUNITY: 4th and <= 5, in open field, inside two scores.
            select season, {canon('posteam')} as team,
                   count(*)                                                as fourth_opportunities,
                   count(*) filter (where play_type in ('pass', 'run'))    as fourth_go,
                   count(*) filter (where play_type = 'punt')              as fourth_punt,
                   count(*) filter (where play_type = 'field_goal')        as fourth_fg
            from pbp
            where down = 4 and ydstogo <= {GO_MAX_DISTANCE}
              and yardline_100 between {GO_MIN_YARDLINE} and {GO_MAX_YARDLINE}
              and abs(score_differential) <= {NEUTRAL_SCORE_MARGIN}
              and posteam is not null
              and play_type in ('pass', 'run', 'punt', 'field_goal')
            group by 1, 2
        ),
        twopt as (
            -- the denominator is touchdowns that ALLOWED a try, not all touchdowns
            select season, {canon('posteam')} as team,
                   count(*)                                             as pat_opportunities,
                   count(*) filter (where two_point_attempt = 1)        as two_point_attempts,
                   count(*) filter (where two_point_conv_result = 'success') as two_point_made
            from pbp
            where (extra_point_attempt = 1 or two_point_attempt = 1) and posteam is not null
            group by 1, 2
        ),
        kicks as (
            select season, {canon('posteam')} as team,
                   count(*) filter (where field_goal_attempt = 1)              as fg_att,
                   count(*) filter (where field_goal_result = 'made')          as fg_made,
                   count(*) filter (where field_goal_attempt = 1
                                    and kick_distance < 40)                    as fg_att_short,
                   count(*) filter (where field_goal_result = 'made'
                                    and kick_distance < 40)                    as fg_made_short,
                   count(*) filter (where field_goal_attempt = 1
                                    and kick_distance between 40 and 49)       as fg_att_mid,
                   count(*) filter (where field_goal_result = 'made'
                                    and kick_distance between 40 and 49)       as fg_made_mid,
                   count(*) filter (where field_goal_attempt = 1
                                    and kick_distance >= 50)                   as fg_att_long,
                   count(*) filter (where field_goal_result = 'made'
                                    and kick_distance >= 50)                   as fg_made_long,
                   avg(kick_distance) filter (where field_goal_attempt = 1)    as fg_dist_mean,
                   count(*) filter (where punt_attempt = 1)                    as punts,
                   avg(kick_distance) filter (where punt_attempt = 1)          as punt_dist_mean
            from pbp where posteam is not null
            group by 1, 2
        ),
        redzone as (
            -- ★ the stall rate: drives that reached the red zone and did NOT score a touchdown.
            -- One row per drive, taken at the drive's furthest penetration, so a drive is counted
            -- once however many snaps it ran inside the 20.
            select season, team,
                   count(*)                                                    as rz_drives,
                   count(*) filter (where result = 'Touchdown')                as rz_tds,
                   count(*) filter (where result in ('Field goal', 'Missed field goal'))
                                                                               as rz_fg_drives,
                   round(1.0 - count(*) filter (where result = 'Touchdown')
                         / nullif(count(*), 0), 4)                             as rz_stall_rate
            from (
                select distinct season, {canon('posteam')} as team, game_id, fixed_drive,
                       first_value(fixed_drive_result) over (
                           partition by game_id, fixed_drive order by play_id) as result
                from pbp
                where posteam is not null and yardline_100 <= 20 and fixed_drive is not null
            )
            group by 1, 2
        )
        select hc.season, hc.team, hc.head_coach, hc.games,
               f.fourth_opportunities, f.fourth_go, f.fourth_punt, f.fourth_fg,
               round(f.fourth_go / nullif(f.fourth_opportunities, 0), 4)      as fourth_go_rate,
               t.pat_opportunities, t.two_point_attempts, t.two_point_made,
               round(t.two_point_attempts / nullif(t.pat_opportunities, 0), 4) as two_point_rate,
               k.fg_att, k.fg_made, k.fg_att_short, k.fg_made_short,
               k.fg_att_mid, k.fg_made_mid, k.fg_att_long, k.fg_made_long,
               round(k.fg_made / nullif(k.fg_att, 0), 4)                      as fg_pct,
               round(k.fg_made_long / nullif(k.fg_att_long, 0), 4)            as fg_pct_long,
               k.fg_dist_mean, k.punts, k.punt_dist_mean,
               r.rz_drives, r.rz_tds, r.rz_fg_drives, r.rz_stall_rate,
               current_localtimestamp()                                       as pulled_at
        from hc
        left join fourth  f on f.season = hc.season and f.team = hc.team
        left join twopt   t on t.season = hc.season and t.team = hc.team
        left join kicks   k on k.season = hc.season and k.team = hc.team
        left join redzone r on r.season = hc.season and r.team = hc.team
    """)
    n, teams, seasons, coaches = con.execute(f"""
        select count(*), count(distinct team), count(distinct season), count(distinct head_coach)
        from {ST_TABLE}""").fetchone()
    return {"table": ST_TABLE, "n_rows": int(n), "n_teams": int(teams),
            "n_seasons": int(seasons), "n_head_coaches": int(coaches)}


def build_kicking_env_week(con) -> dict:
    """One row per (season, week, team): the conditions a kicker actually kicked in.

    ⚠ ``temp`` and ``wind`` are **null for domes** in the upstream feed, and that null is
    information, not missingness — a closed roof *is* the weather. ``is_dome`` is derived from
    ``roof`` so a consumer never has to read a null and guess, and the numeric columns keep the
    null rather than being filled with a 0 that would read as freezing and windless.
    """
    con.execute(f"""
        create or replace table {KICK_ENV_TABLE} as
        with games as (
            select distinct season, week, game_id, roof, surface, temp, wind,
                   {canon('home_team')} as home_team, {canon('away_team')} as away_team
            from pbp where game_id is not null
        ),
        sided as (
            select season, week, game_id, roof, surface, temp, wind, home_team as team,
                   true as is_home from games
            union all
            select season, week, game_id, roof, surface, temp, wind, away_team as team,
                   false as is_home from games
        ),
        kicks as (
            select season, week, {canon('posteam')} as team,
                   count(*) filter (where field_goal_attempt = 1)       as fg_att,
                   count(*) filter (where field_goal_result = 'made')   as fg_made,
                   max(kick_distance) filter (where field_goal_result = 'made') as fg_long_made
            from pbp where posteam is not null group by 1, 2, 3
        )
        select s.season, s.week, s.team, s.game_id, s.is_home,
               s.roof, s.surface, s.temp, s.wind,
               -- ★ the null IS the reading: a closed roof has no weather to report.
               (s.roof in ('dome', 'closed'))                          as is_dome,
               (s.roof in ('outdoors', 'open'))                        as is_outdoors,
               coalesce(k.fg_att, 0)                                   as fg_att,
               coalesce(k.fg_made, 0)                                  as fg_made,
               k.fg_long_made,
               current_localtimestamp()                                as pulled_at
        from sided s
        left join kicks k on k.season = s.season and k.week = s.week and k.team = s.team
    """)
    n, teams, seasons = con.execute(f"""
        select count(*), count(distinct team), count(distinct season) from {KICK_ENV_TABLE}"""
    ).fetchone()
    return {"table": KICK_ENV_TABLE, "n_rows": int(n), "n_teams": int(teams),
            "n_seasons": int(seasons)}


def coach_attribution_check(con) -> pd.DataFrame:
    """★ Does the head coach this module attributes decisions to match ``coaches.csv``?

    ``reference/coaches.csv`` carries a hand-verified ``head_coach`` per team-season (audited
    against ``pbp`` at 0 mismatches in 0.13.1). Both this table and that file derive it from the
    same pbp scaffold, so a disagreement means one of them applied a different majority rule —
    which is worth knowing before a fingerprint keys on either.
    """
    return con.execute(f"""
        select s.season, s.team, s.head_coach as st_coach, c.head_coach as csv_coach
        from {ST_TABLE} s
        join read_csv_auto('reference/coaches.csv', header=true, comment='#') c
          on c.season = s.season and c.team = s.team
        where s.head_coach is distinct from c.head_coach
        order by 1, 2
    """).df()


def aggression_denominator_check(con) -> pd.DataFrame:
    """★ The behavioural trap, stated: 4th-down go-rate over **all** 4th downs vs over the choice.

    Same shape as B2's naive-vs-gated blitz rate. A team's unconditional go-rate is dominated by
    4th-and-12 from its own 20, where nobody goes, so it measures how often a team faced a hopeless
    down rather than how aggressive its coach is.
    """
    return con.execute(f"""
        select season,
               avg(case when play_type in ('pass','run') then 1.0 else 0.0 end)
                   filter (where down = 4 and play_type in ('pass','run','punt','field_goal'))
                                                                             as naive_go_rate,
               avg(case when play_type in ('pass','run') then 1.0 else 0.0 end)
                   filter (where down = 4 and ydstogo <= {GO_MAX_DISTANCE}
                           and yardline_100 between {GO_MIN_YARDLINE} and {GO_MAX_YARDLINE}
                           and abs(score_differential) <= {NEUTRAL_SCORE_MARGIN}
                           and play_type in ('pass','run','punt','field_goal'))
                                                                             as conditioned_go_rate
        from pbp
        group by 1 order by 1
    """).df()
