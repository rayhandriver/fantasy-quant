"""Phase 0.13.2 — the **defensive fact tables**: the half DATA-1 left on the table.

``build_participation_player_week`` filters ``where side = 'offense'`` and says why in its own
docstring — *"the defensive record is available through the view, but the fantasy questions are all
offensive"*. That was right for DATA-1 and it is exactly what blocks every defensive question now.
This module materializes the other side: ``defense_team_week`` (fronts, blitz, box, man/zone,
pressure) and ``defense_player_week`` (snaps, package usage, alignment).

★ **Every rate here routes its denominator through the 0.13.0 break map.** From 2023 the vendor
stopped emitting ``NULL`` on non-pass plays and started emitting ``False``/``0``, so the obvious
way to find dropbacks — *"rows where ``number_of_pass_rushers`` is populated"* — silently starts
including every run play in the denominator. :func:`blitz_rate` computes the naive and the gated
number side by side, because a fix whose effect is unmeasured is a claim (B2).

★ **ONE canonical grouping function.** ``defense_personnel`` is not one encoding, it is two:
``4 DL, 2 LB, 5 DB`` for most rows and a position-level ``3 CB, 2 DE, 2 DT, 1 FS, 1 MLB, 1 OLB,
1 SS`` for others. Anything that parses only the first form silently drops the second — the rows
are not missing, they are *shaped differently*, which is the harder failure to notice.
:func:`parse_defense_personnel` collapses both to (DL, LB, DB) counts and a package label, and it
is the only place in the repo that reads those strings.
"""

from __future__ import annotations

import logging
import re

import pandas as pd

from fantasy_quant.data import db
from fantasy_quant.data.breaks import BreakMap, sentinel_exclusion_sql

log = logging.getLogger(__name__)

TEAM_WEEK_TABLE = "defense_team_week"
PLAYER_WEEK_TABLE = "defense_player_week"
PERSONNEL_MAP_TABLE = "defense_personnel_map"
DEFENSE_PLAY_VIEW = "participation_defense_player_play"

#: Position token → unit. The detailed encoding uses real position names; the aggregated one uses
#: the unit names directly, so both land in the same three buckets.
_UNIT: dict[str, str] = {
    "DL": "dl", "DE": "dl", "DT": "dl", "NT": "dl", "EDGE": "dl",
    "LB": "lb", "ILB": "lb", "OLB": "lb", "MLB": "lb",
    "DB": "db", "CB": "db", "FS": "db", "SS": "db", "S": "db",
}

_TOKEN = re.compile(r"(\d+)\s+([A-Z]+)")

#: Package by defensive-back count — the league's own vocabulary, and the reason DB count is the
#: primary axis rather than DL count: substitution happens in the secondary.
_PACKAGE_BY_DB = {0: "heavy", 1: "heavy", 2: "heavy", 3: "heavy", 4: "base",
                  5: "nickel", 6: "dime", 7: "quarter"}


def parse_defense_personnel(text: str | None) -> dict[str, object]:
    """Collapse either ``defense_personnel`` encoding to unit counts and a package label.

    ``other`` counts men who are neither DL, LB nor DB — a kicker or a receiver on the field means
    the row is a special-teams play, and :func:`build_defense_team_week` filters on it rather than
    trusting play_type alone.
    """
    out = {"dl": 0, "lb": 0, "db": 0, "other": 0, "package": None, "n_men": 0}
    if not text or not isinstance(text, str):
        return out
    for count, token in _TOKEN.findall(text.upper()):
        unit = _UNIT.get(token)
        n = int(count)
        out[unit if unit else "other"] += n
        out["n_men"] += n
    if out["n_men"] == 0:
        return out
    out["package"] = _PACKAGE_BY_DB.get(out["db"], "quarter" if out["db"] > 7 else None)
    return out


def build_personnel_map(con) -> pd.DataFrame:
    """Materialize the distinct-string → units lookup, so the parse happens once per *string*."""
    distinct = con.execute(
        'select distinct defense_personnel from participation where defense_personnel is not null'
    ).df()
    parsed = [parse_defense_personnel(s) for s in distinct["defense_personnel"]]
    out = pd.concat([distinct.reset_index(drop=True), pd.DataFrame(parsed)], axis=1)
    db.write_df(con, PERSONNEL_MAP_TABLE, out)
    return out


def defense_player_play_view(con) -> None:
    """Explode the defensive 11 **with their positions**, by parallel unnest.

    DATA-1's view carries the players but not ``defense_positions``; the alignment questions
    (0.13.3's derived safety count, nickel-corner usage) need the two zipped, and zipping them
    after the fact by row number is exactly the kind of positional join that goes wrong silently.
    """
    con.execute(f"""
        create or replace view {DEFENSE_PLAY_VIEW} as
        select season, week, game_id, play_id, possession_team,
               defense_personnel, defenders_in_box, number_of_pass_rushers,
               defense_man_zone_type, defense_coverage_type, was_pressure,
               unnest(str_split(defense_players, ';'))                    as gsis_id,
               -- ⚠ `defense_positions` is a 2023+ column (T49: floors are per-COLUMN — the table's
               -- floor is 2016 and the players list really does start there). coalescing to '' lets
               -- DuckDB pad the shorter list with NULLs, so 2016-2022 keeps its player rows with a
               -- null position instead of vanishing: requiring positions here silently truncated
               -- the table to three seasons, ALL of them outside the DEV window.
               unnest(str_split(coalesce(defense_positions, ''), ';'))    as position
        from participation
        where defense_players is not null
    """)


def _rate_predicates(bm: BreakMap, alias: str = "p") -> dict[str, str]:
    """The break-map-derived predicates every rate in this module shares.

    ``alias`` must name the participation-grain relation in the caller's query — the play table in
    one, the exploded view in another. Hardcoding it here bound the predicate to a table name that
    only one of the two queries uses, which the binder caught immediately; the general version of
    that mistake (a predicate silently evaluating against the wrong relation) it would not.
    """
    return {
        "rushers": sentinel_exclusion_sql(bm, "participation", "number_of_pass_rushers", alias),
        "pressure": sentinel_exclusion_sql(bm, "participation", "was_pressure", alias),
    }


def blitz_rate(con, bm: BreakMap, seasons: tuple[int, ...] | None = None) -> pd.DataFrame:
    """★ B2's instrument: the **naive** and **gated** blitz rate, per season, side by side.

    *naive* takes the vendor's populated rows as the set of dropbacks — the reading anyone would
    write, and the one that silently absorbs every run play from 2023 on. *gated* excludes the
    sentinel and requires pbp to agree the play was a dropback. The gap between them is the size
    of the trap, stated rather than asserted.
    """
    where_season = f"and p.season in {tuple(seasons)}" if seasons else ""
    excl = _rate_predicates(bm)["rushers"]
    return con.execute(f"""
        select p.season,
               count(*) filter (where p.number_of_pass_rushers is not null)          as naive_denom,
               avg(case when p.number_of_pass_rushers >= 5 then 1.0 else 0.0 end)
                   filter (where p.number_of_pass_rushers is not null)               as naive_rate,
               count(*) filter (where {excl} and b.qb_dropback = 1
                                and p.number_of_pass_rushers is not null)            as gated_denom,
               avg(case when p.number_of_pass_rushers >= 5 then 1.0 else 0.0 end)
                   filter (where {excl} and b.qb_dropback = 1
                           and p.number_of_pass_rushers is not null)                 as gated_rate,
               avg(p.number_of_pass_rushers)
                   filter (where p.number_of_pass_rushers is not null)             as naive_rushers,
               avg(p.number_of_pass_rushers)
                   filter (where {excl} and b.qb_dropback = 1)                      as gated_rushers
        from participation p
        left join pbp b using (game_id, play_id)
        where true {where_season}
        group by 1 order by 1
    """).df()


def build_defense_team_week(con, bm: BreakMap) -> dict:
    """One row per (season, week, defending team): fronts, blitz, box, man/zone, pressure.

    The defending team comes from ``pbp.defteam``, not from ``possession_team`` — participation
    names the offense, and inverting that by hand per game is how a team-week table ends up with
    every fact attributed to its opponent.
    """
    build_personnel_map(con)
    pred = _rate_predicates(bm)
    con.execute(f"""
        create or replace table {TEAM_WEEK_TABLE} as
        with plays as (
            select p.season, p.week, b.defteam as team,
                   m.dl, m.lb, m.db, m.other, m.package,
                   p.defenders_in_box, p.number_of_pass_rushers, p.was_pressure,
                   p.defense_man_zone_type, p.defense_coverage_type,
                   b.qb_dropback, b.play_type,
                   -- ★ the break-map gates, applied at the row rather than the aggregate: a
                   -- sentinel row must not reach a numerator OR a denominator.
                   ({pred['rushers']}) as rushers_usable,
                   ({pred['pressure']}) as pressure_usable
            from participation p
            left join pbp b using (game_id, play_id)
            left join {PERSONNEL_MAP_TABLE} m using (defense_personnel)
            where b.defteam is not null
              -- ★ Special teams is identified by PLAY TYPE, never by vocabulary. The first version
              -- of this filter dropped any play whose personnel string named an offensive position
              -- ("1 WR" among the eleven) on the theory that it must be a kick unit. It is not: the
              -- string carries LISTED ROSTER positions, so a two-way player reads as an offensive
              -- one. It deleted 55 of 78 defensive snaps for JAX in a single 2025 week — 0.5 % of
              -- the league's scrimmage plays, but concentrated in the one team that has such a
              -- player. `other` is kept below as provenance, and never as a filter.
              and b.play_type in ('pass', 'run')
        )
        select
            season, week, team,
            count(*)                                                    as def_snaps,
            count(*) filter (where qb_dropback = 1)                     as dropbacks,
            avg(dl)                                                     as dl_mean,
            avg(lb)                                                     as lb_mean,
            avg(db)                                                     as db_mean,
            avg(case when package = 'base'    then 1.0 else 0.0 end)    as share_base,
            avg(case when package = 'nickel'  then 1.0 else 0.0 end)    as share_nickel,
            avg(case when package = 'dime'    then 1.0 else 0.0 end)    as share_dime,
            avg(case when package = 'quarter' then 1.0 else 0.0 end)    as share_quarter,
            avg(case when package = 'heavy'   then 1.0 else 0.0 end)    as share_heavy_box,
            count(package)                                              as snaps_with_personnel,
            -- provenance, not a filter: scrimmage snaps whose eleven included a player listed at
            -- an offensive position. Non-zero means a two-way player, and it is worth seeing.
            count(*) filter (where coalesce(other, 0) > 0)              as snaps_two_way_listed,
            -- ★ blitz: numerator and denominator BOTH gated, and the denominator is pbp's
            -- dropback flag rather than "the column is populated".
            avg(case when number_of_pass_rushers >= 5 then 1.0 else 0.0 end)
                filter (where rushers_usable and qb_dropback = 1
                        and number_of_pass_rushers is not null)         as blitz_rate,
            avg(case when number_of_pass_rushers >= 6 then 1.0 else 0.0 end)
                filter (where rushers_usable and qb_dropback = 1
                        and number_of_pass_rushers is not null)         as big_blitz_rate,
            avg(case when number_of_pass_rushers <= 3 then 1.0 else 0.0 end)
                filter (where rushers_usable and qb_dropback = 1
                        and number_of_pass_rushers is not null)         as rush3_rate,
            avg(number_of_pass_rushers)
                filter (where rushers_usable and qb_dropback = 1)       as rushers_mean,
            count(*) filter (where rushers_usable and qb_dropback = 1
                             and number_of_pass_rushers is not null)    as rushers_denom,
            avg(defenders_in_box)                                       as box_mean,
            avg(defenders_in_box) filter (where play_type = 'run')      as box_mean_vs_run,
            avg(case when defenders_in_box >= 8 then 1.0 else 0.0 end)  as share_box_8plus,
            avg(case when defense_man_zone_type = 'MAN_COVERAGE' then 1.0 else 0.0 end)
                filter (where defense_man_zone_type is not null
                        and defense_man_zone_type <> '')                as man_share,
            count(*) filter (where defense_man_zone_type is not null
                             and defense_man_zone_type <> '')           as man_zone_denom,
            avg(case when was_pressure then 1.0 else 0.0 end)
                filter (where pressure_usable and qb_dropback = 1)      as pressure_rate,
            count(*) filter (where pressure_usable and qb_dropback = 1) as pressure_denom,
            current_localtimestamp()                                    as pulled_at
        from plays
        group by 1, 2, 3
    """)
    n, teams, seasons = con.execute(
        f"select count(*), count(distinct team), count(distinct season) from {TEAM_WEEK_TABLE}"
    ).fetchone()
    return {"table": TEAM_WEEK_TABLE, "n_rows": int(n), "n_teams": int(teams),
            "n_seasons": int(seasons)}


def build_defense_player_week(con, bm: BreakMap) -> dict:
    """One row per (season, week, defender): snaps, package usage, alignment, coverage faced."""
    defense_player_play_view(con)
    pred = _rate_predicates(bm, alias="v")
    con.execute(f"""
        create or replace table {PLAYER_WEEK_TABLE} as
        with pp as (
            -- ★ One row per (play, defender). The vendor's `defense_players` list sometimes names
            -- the same gsis_id TWICE on one play — a 2019 Jets defender is listed twice on 44 of
            -- 57 snaps in a week, which read as a 1.54 snap share. A player is on the field for a
            -- play or he is not, so the duplicate is collapsed here rather than divided away later.
            select distinct on (v.game_id, v.play_id, v.gsis_id)
                   v.season, v.week, v.gsis_id, b.defteam as team, v.position,
                   m.package, v.defenders_in_box, v.number_of_pass_rushers, v.was_pressure,
                   v.defense_man_zone_type, b.qb_dropback,
                   ({pred['rushers']}) as rushers_usable
            from {DEFENSE_PLAY_VIEW} v
            left join pbp b using (game_id, play_id)
            left join {PERSONNEL_MAP_TABLE} m using (defense_personnel)
            where v.gsis_id is not null and v.gsis_id <> '' and b.defteam is not null
              -- the SAME scrimmage definition as the team table, so snap_share has a denominator
              -- it actually divides into. Mismatched filters here produced shares above 3.0.
              and b.play_type in ('pass', 'run')
        )
        select
            season, week, gsis_id, team,
            count(*)                                                     as snaps,
            mode(position)                                               as position_modal,
            count(distinct position)                                     as n_positions,
            count(*) filter (where package = 'base')                     as snaps_base,
            count(*) filter (where package = 'nickel')                   as snaps_nickel,
            count(*) filter (where package = 'dime')                     as snaps_dime,
            count(*) filter (where package = 'quarter')                  as snaps_quarter,
            count(*) filter (where qb_dropback = 1)                      as snaps_dropback,
            avg(case when number_of_pass_rushers >= 5 then 1.0 else 0.0 end)
                filter (where rushers_usable and qb_dropback = 1
                        and number_of_pass_rushers is not null)          as blitz_rate_on_field,
            avg(case when defense_man_zone_type = 'MAN_COVERAGE' then 1.0 else 0.0 end)
                filter (where defense_man_zone_type is not null
                        and defense_man_zone_type <> '')                 as man_share_on_field,
            avg(defenders_in_box)                                        as box_mean_on_field,
            current_localtimestamp()                                     as pulled_at
        from pp
        group by 1, 2, 3, 4
    """)
    # snap share needs the team-week denominator, which only exists after the team table is built
    con.execute(f"""
        create or replace table {PLAYER_WEEK_TABLE} as
        select w.*, round(w.snaps / nullif(t.def_snaps, 0), 4) as snap_share
        from {PLAYER_WEEK_TABLE} w
        left join {TEAM_WEEK_TABLE} t using (season, week, team)
    """)
    n, players, seasons = con.execute(
        f"select count(*), count(distinct gsis_id), count(distinct season) from {PLAYER_WEEK_TABLE}"
    ).fetchone()
    return {"table": PLAYER_WEEK_TABLE, "n_rows": int(n), "n_players": int(players),
            "n_seasons": int(seasons)}
