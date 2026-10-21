"""The metrics ``pbp`` + FTN can carry, computed from those sources — **for every season**.

★ **Why this module recomputes what the scheme panel already has.** ``offense_team_week`` reads
``FROM participation``, so it has no row for a season whose participation file is not out yet —
which is every live season. Computing the pbp/FTN family once, here, from ``pbp`` and
``ftn_charting`` gives 2018 and the season being played **one definition**, so a trend line never
changes source at the season the participation file stops. The parity test
(``tests/test_teambook.py``) holds this module to the panel wherever the two define a number the
same way.

⚠ **Ratio of sums, at play grain.** The panel's season table re-weights weekly rates by snaps,
which is exact for a rate over all snaps (pass rate, EPA/play) and a mean-of-ratios approximation
for a rate over a filtered denominator (neutral-script pass rate, play-action share of dropbacks).
Here every rate is numerator over its own denominator across the season's plays.

Every query takes the relations it reads by name, so the same SQL runs against the project store
(tables ``pbp``/``ftn_charting``/``weekly``/``snaps``/``schedules``) and against the in-memory
store :mod:`~fantasy_quant.teambook.inseason` builds from the nflverse releases.
"""

from __future__ import annotations

import pandas as pd

from fantasy_quant.data.teams import canon_team_sql as canon
from fantasy_quant.situation.special_teams import st_team_season_sql

#: A play the offense chose: the population ``offense_team_week`` uses (pass + run, posteam set).
SCRIMMAGE = "play_type in ('pass', 'run') and posteam is not null"

#: Neutral script, the same predicate as ``offense_scheme.build_offense_team_week``.
NEUTRAL = "abs(score_differential) <= 7 and game_seconds_remaining > 300"


def reg_pbp(season: int) -> str:
    """The regular-season plays of one season, as a subquery."""
    return f"(select * from pbp where season = {int(season)} and season_type = 'REG')"


def offense(con, season: int) -> pd.DataFrame:
    """One row per offense: volume, efficiency, tendencies, and FTN play design."""
    return con.execute(f"""
        with p as (
            select {canon('b.posteam')} as team, b.*,
                   f.ftn_play_id is not null as ftn_charted,
                   f.is_motion, f.is_play_action, f.is_rpo, f.is_screen_pass,
                   f.n_offense_backfield, f.qb_location
            from {reg_pbp(season)} b
            left join ftn_charting f using (game_id, play_id)
            where b.play_type in ('pass', 'run') and b.posteam is not null
        )
        select team,
               count(distinct game_id)                                   as games,
               count(*)                                                  as off_snaps,
               count(*) / count(distinct game_id)                        as snaps_per_game,
               count(*) filter (where qb_dropback = 1)
                   / count(distinct game_id)                             as dropbacks_per_game,
               avg(epa)                                                  as epa_per_play,
               avg(epa) filter (where qb_dropback = 1)                   as pass_epa,
               avg(epa) filter (where play_type = 'run' and qb_dropback = 0) as rush_epa,
               avg(success)                                              as success_rate,
               avg(case when (play_type = 'pass' and yards_gained >= 20)
                          or (play_type = 'run' and yards_gained >= 10)
                        then 1.0 else 0.0 end)                           as explosive_rate,
               avg(case when play_type = 'pass' then 1.0 else 0.0 end)   as pass_rate,
               avg(case when play_type = 'pass' then 1.0 else 0.0 end)
                   filter (where {NEUTRAL})                              as pass_rate_neutral,
               avg(pass_oe)                                              as pass_oe_mean,
               avg(case when play_type = 'pass' then 1.0 else 0.0 end)
                   filter (where down in (1, 2) and {NEUTRAL})           as early_down_pass_rate,
               avg(case when shotgun = 1 then 1.0 else 0.0 end)          as shotgun_rate,
               avg(case when no_huddle = 1 then 1.0 else 0.0 end)        as no_huddle_rate,
               -- FTN: NULL where nothing was charted (pre-2022), never 0 (the T50 rule)
               avg(case when is_motion then 1.0 else 0.0 end)
                   filter (where ftn_charted)                            as motion_rate,
               avg(case when is_play_action then 1.0 else 0.0 end)
                   filter (where ftn_charted and qb_dropback = 1)        as play_action_rate,
               avg(case when is_rpo then 1.0 else 0.0 end)
                   filter (where ftn_charted)                            as rpo_rate,
               avg(case when is_screen_pass then 1.0 else 0.0 end)
                   filter (where ftn_charted and qb_dropback = 1)        as screen_rate,
               avg(case when qb_location = 'U' then 1.0 else 0.0 end)
                   filter (where ftn_charted and qb_location in ('U', 'S', 'P'))
                                                                         as qb_under_center_ftn,
               avg(n_offense_backfield) filter (where ftn_charted)       as backfield_mean,
               count(*) filter (where ftn_charted)                       as ftn_snaps
        from p
        group by 1
        order by 1
    """).df()


def defense(con, season: int) -> pd.DataFrame:
    """One row per defense: results allowed from pbp, and FTN's charted pressure and box."""
    return con.execute(f"""
        with p as (
            select {canon('b.defteam')} as team, b.*,
                   f.ftn_play_id is not null as ftn_charted,
                   f.n_blitzers, f.n_pass_rushers, f.n_defense_box
            from {reg_pbp(season)} b
            left join ftn_charting f using (game_id, play_id)
            where b.play_type in ('pass', 'run') and b.defteam is not null
        )
        select team,
               count(*)                                                  as def_snaps,
               avg(epa)                                                  as def_epa_per_play,
               avg(epa) filter (where qb_dropback = 1)                   as def_pass_epa,
               avg(epa) filter (where play_type = 'run' and qb_dropback = 0)
                                                                         as def_rush_epa,
               avg(success)                                              as def_success_rate,
               avg(case when (play_type = 'pass' and yards_gained >= 20)
                          or (play_type = 'run' and yards_gained >= 10)
                        then 1.0 else 0.0 end)                           as def_explosive_rate,
               avg(case when sack = 1 then 1.0 else 0.0 end)
                   filter (where qb_dropback = 1)                        as def_sack_rate,
               (count(*) filter (where interception = 1)
                + count(*) filter (where fumble_lost = 1))
                   / count(distinct game_id)                             as takeaways_per_game,
               avg(case when play_type = 'pass' then 1.0 else 0.0 end)   as opp_pass_rate,
               -- ★ the participation blitz definition (5+ rushers on a dropback), charted by FTN
               avg(case when n_pass_rushers >= 5 then 1.0 else 0.0 end)
                   filter (where ftn_charted and qb_dropback = 1
                           and n_pass_rushers is not null)               as ftn_blitz_rate,
               avg(n_pass_rushers)
                   filter (where ftn_charted and qb_dropback = 1)        as ftn_rushers_mean,
               avg(n_defense_box) filter (where ftn_charted)             as ftn_box_mean,
               avg(case when n_defense_box >= 8 then 1.0 else 0.0 end)
                   filter (where ftn_charted and n_defense_box is not null)
                                                                         as ftn_box_8plus
        from p
        group by 1
        order by 1
    """).df()


def special(con, season: int) -> pd.DataFrame:
    """4th-down/2-point aggression and kicking — ``special_teams``' own SQL, regular season."""
    cols = ("team", "head_coach", "fourth_go_rate", "two_point_rate", "rz_stall_rate", "fg_pct",
            "fg_pct_long", "fg_dist_mean", "punt_dist_mean")
    return con.execute(
        f"select {', '.join(cols)} from ({st_team_season_sql(reg_pbp(season))}) order by team"
    ).df()


def records(con, season: int) -> pd.DataFrame:
    """Record, points for/against and bye week(s), from the regular-season schedule."""
    return con.execute(f"""
        with g as (
            select {canon('home_team')} as team, week, home_score as pf, away_score as pa
              from schedules where season = {int(season)} and game_type = 'REG'
            union all
            select {canon('away_team')} as team, week, away_score as pf, home_score as pa
              from schedules where season = {int(season)} and game_type = 'REG'
        ),
        weeks as (
            select max(week) as reg_weeks from schedules
            where season = {int(season)} and game_type = 'REG'
        )
        select team,
               count(*) filter (where pf is not null)        as games_played,
               count(*) filter (where pf > pa)                as wins,
               count(*) filter (where pf < pa)                as losses,
               count(*) filter (where pf = pa)                as ties,
               sum(pf)                                        as points_for,
               sum(pa)                                        as points_against,
               max(week) filter (where pf is not null)        as through_week,
               (select list(w order by w) from range(1, (select reg_weeks from weeks) + 1) t(w)
                 where w not in (select week from g g2 where g2.team = g.team))  as bye_weeks
        from g
        group by team
        order by team
    """).df()


def weekly_series(con, season: int) -> pd.DataFrame:
    """Per-week offense and defense — the in-season view and the season's shape."""
    return con.execute(f"""
        with off as (
            select {canon('posteam')} as team, week,
                   count(*) as off_snaps, avg(epa) as epa_per_play,
                   avg(case when play_type = 'pass' then 1.0 else 0.0 end) as pass_rate,
                   avg(case when play_type = 'pass' then 1.0 else 0.0 end)
                       filter (where {NEUTRAL}) as pass_rate_neutral
            from {reg_pbp(season)} where {SCRIMMAGE}
            group by 1, 2
        ),
        def as (
            select {canon('defteam')} as team, week, avg(epa) as def_epa_per_play
            from {reg_pbp(season)} where play_type in ('pass', 'run') and defteam is not null
            group by 1, 2
        ),
        sched as (
            select {canon('home_team')} as team, week, {canon('away_team')} as opponent,
                   home_score as pf, away_score as pa, true as home
              from schedules where season = {int(season)} and game_type = 'REG'
            union all
            select {canon('away_team')}, week, {canon('home_team')}, away_score, home_score, false
              from schedules where season = {int(season)} and game_type = 'REG'
        )
        select s.team, s.week, s.opponent, s.home, s.pf, s.pa,
               o.off_snaps, o.epa_per_play, o.pass_rate, o.pass_rate_neutral, d.def_epa_per_play
        from sched s
        left join off o using (team, week)
        left join def d using (team, week)
        where s.pf is not null
        order by s.team, s.week
    """).df()


# --- players ----------------------------------------------------------------------------------
SKILL = ("QB", "RB", "FB", "WR", "TE")


def offense_players(con, season: int) -> pd.DataFrame:
    """Per (player, team): usage, production and full-PPR points, regular season.

    Box score from ``weekly`` (the nflverse player-stats release), snap share from ``snaps``
    (PFR via nflverse), red-zone work from ``pbp``. A player traded mid-season gets one row per
    team, because a team book describes that team's usage.
    """
    return con.execute(f"""
        with w as (
            select gsis_id, {canon('recent_team')} as team,
                   any_value(player_display_name) as name, any_value(position) as position,
                   count(*)                       as games,
                   sum(attempts)                  as pass_att,
                   sum(passing_yards)             as pass_yds,
                   sum(passing_tds)               as pass_td,
                   sum(interceptions)             as ints,
                   sum(carries)                   as carries,
                   sum(rushing_yards)             as rush_yds,
                   sum(rushing_tds)               as rush_td,
                   sum(targets)                   as targets,
                   sum(receptions)                as receptions,
                   sum(receiving_yards)           as rec_yds,
                   sum(receiving_tds)             as rec_td,
                   sum(receiving_air_yards)       as air_yards,
                   sum(fantasy_points_ppr)        as ppr_points
            from weekly
            where season = {int(season)} and season_type = 'REG'
              and position in {SKILL}
            group by 1, 2
        ),
        team_tot as (
            select team, sum(targets) as team_targets, sum(carries) as team_carries,
                   sum(air_yards) as team_air_yards
            from w group by 1
        ),
        snap as (
            select gsis_id, {canon('team')} as team,
                   sum(offense_snaps) as off_snaps, avg(offense_pct) as snap_share
            from snaps
            where season = {int(season)} and game_type = 'REG' and gsis_id is not null
            group by 1, 2
        ),
        rz as (
            select id as gsis_id, team,
                   count(*) filter (where kind = 'tgt') as rz_targets,
                   count(*) filter (where kind = 'car') as rz_carries
            from (
                select receiver_player_id as id, {canon('posteam')} as team, 'tgt' as kind
                  from {reg_pbp(season)}
                 where yardline_100 <= 20 and receiver_player_id is not null
                   and play_type = 'pass'
                union all
                select rusher_player_id, {canon('posteam')}, 'car'
                  from {reg_pbp(season)}
                 where yardline_100 <= 20 and rusher_player_id is not null
                   and play_type = 'run'
            ) group by 1, 2
        )
        select w.*,
               s.off_snaps, s.snap_share,
               w.targets / nullif(t.team_targets, 0)         as target_share,
               w.carries / nullif(t.team_carries, 0)         as carry_share,
               w.air_yards / nullif(t.team_air_yards, 0)     as air_yards_share,
               w.air_yards / nullif(w.targets, 0)            as adot,
               w.ppr_points / nullif(w.games, 0)             as ppr_per_game,
               coalesce(r.rz_targets, 0)                     as rz_targets,
               coalesce(r.rz_carries, 0)                     as rz_carries
        from w
        join team_tot t using (team)
        left join snap s using (gsis_id, team)
        left join rz r using (gsis_id, team)
        where coalesce(w.targets, 0) + coalesce(w.carries, 0) + coalesce(w.pass_att, 0) > 0
        order by team, ppr_points desc nulls last, gsis_id
    """).df()


def defense_players(con, season: int) -> pd.DataFrame:
    """Per (player, team): defensive snap share and the splash plays ``pbp`` attributes.

    Sacks count half-sacks as 0.5, as the league does. Every stat comes from the play log rather
    than a box-score table so the live season and 2018 share one definition.
    """
    return con.execute(f"""
        with plays as (
            select {canon('defteam')} as team, *
            from {reg_pbp(season)} where defteam is not null
        ),
        credit as (
            select team, sack_player_id as id, 1.0 as sacks, 0 as qb_hits, 0 as ints, 0 as pds,
                   0 as tfl from plays where sack_player_id is not null
            union all select team, half_sack_1_player_id, 0.5, 0, 0, 0, 0 from plays
                   where half_sack_1_player_id is not null
            union all select team, half_sack_2_player_id, 0.5, 0, 0, 0, 0 from plays
                   where half_sack_2_player_id is not null
            union all select team, qb_hit_1_player_id, 0, 1, 0, 0, 0 from plays
                   where qb_hit_1_player_id is not null
            union all select team, qb_hit_2_player_id, 0, 1, 0, 0, 0 from plays
                   where qb_hit_2_player_id is not null
            union all select team, interception_player_id, 0, 0, 1, 0, 0 from plays
                   where interception_player_id is not null
            union all select team, pass_defense_1_player_id, 0, 0, 0, 1, 0 from plays
                   where pass_defense_1_player_id is not null
            union all select team, pass_defense_2_player_id, 0, 0, 0, 1, 0 from plays
                   where pass_defense_2_player_id is not null
            union all select team, tackle_for_loss_1_player_id, 0, 0, 0, 0, 1 from plays
                   where tackle_for_loss_1_player_id is not null
            union all select team, tackle_for_loss_2_player_id, 0, 0, 0, 0, 1 from plays
                   where tackle_for_loss_2_player_id is not null
        ),
        stats as (
            select id as gsis_id, team, sum(sacks) as sacks, sum(qb_hits) as qb_hits,
                   sum(ints) as ints, sum(pds) as passes_defended, sum(tfl) as tfl
            from credit group by 1, 2
        ),
        snap as (
            select gsis_id, {canon('team')} as team, any_value(player) as name,
                   any_value(position) as position, count(*) as games,
                   sum(defense_snaps) as def_snaps, avg(defense_pct) as snap_share
            from snaps
            where season = {int(season)} and game_type = 'REG' and gsis_id is not null
              and defense_snaps > 0
            group by 1, 2
        )
        select s.*, coalesce(t.sacks, 0) as sacks, coalesce(t.qb_hits, 0) as qb_hits,
               coalesce(t.ints, 0) as ints, coalesce(t.passes_defended, 0) as passes_defended,
               coalesce(t.tfl, 0) as tfl
        from snap s
        left join stats t using (gsis_id, team)
        order by team, def_snaps desc, gsis_id
    """).df()
