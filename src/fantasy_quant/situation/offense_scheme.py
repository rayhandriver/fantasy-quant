"""Phase 0.13.4 — the **offensive completion**: formation, personnel, tempo, and the route tree.

0.13.2 materialized the defensive half of participation. This is the offensive half that DATA-1
left at *player-week counts* — ``participation_player_week`` carries snaps, routes-run and the four
personnel-grouping snap counts, but nothing carries **team**-level formation and personnel shares,
nothing carries tempo, nothing carries the FTN charting layer, and the ``route`` column is banked
as a count rather than a **distribution**.

★ **Two encodings again, and this time the break map cannot see the seam.** ``offense_personnel``
is ``1 RB, 1 TE, 3 WR`` for 2016–2022 and a full-22 ``1 C, 2 G, 1 QB, 1 RB, 2 T, 1 TE, 3 WR`` from
2023, exactly as ``defense_personnel`` is two encodings — so :func:`parse_offense_personnel` is the
one place in the repo that reads those strings, mirroring 0.13.2's rule.

★ **The blind spot, stated because it is a defect in an instrument this session shipped yesterday.**
The naive fill rate of ``offense_personnel`` climbs **0.754 → 1.000** at 2023, which is the T50
shape — but ``breaks.probeable_columns`` skips any column above ``MAX_CARDINALITY`` (64) and this
column has **1,468** distinct strings from 2023, so the 0.13.0 map never probes it and reports no
break. The conservation test could not have fired anyway: the arriving mass does not land on **one**
sentinel value, it spreads across hundreds of special-teams personnel strings. *A detector that
keys on a single value is blind to a re-encoding that arrives as a population.*
:func:`scrimmage_fill_by_season` is the corresponding measurement — conditioned on scrimmage plays
the fill is **1.000 in every season**, so the whole jump is non-scrimmage plays gaining strings, and
the ``play_type in ('pass','run')`` filter every builder here shares is a provable no-op on the
rates rather than an assumption.

⚠ **Slot / wide / inline alignment does not exist free, and is not derived here.** The spec asked
for it "from ``offense_positions``", but that column carries the **listed roster position** — the
same fact 0.13.2 learned when a two-way player read as an offensive one in the defensive personnel
string. Roster position tells you a man is a WR, never that he lined up in the slot. This is 0.13.3
tier 3 in the offensive register: charted alignment is PFF-paid, it goes in the register as a floor,
and the honest free substitutes are NGS ``avg_cushion``/``avg_separation`` (receiver-week, 2016+)
and the personnel context this module does derive.

⚠ **FTN columns are 2022+ — ONE DEV season.** ``is_motion``, ``is_play_action``, ``is_rpo`` and
``is_screen_pass`` ship with :func:`assert_ftn_backtestable` guarding them: a descriptive live-2026
layer, never a backtest input. The assertion is the guard; the docstring is not (UI-1's lesson 4).
"""

from __future__ import annotations

import logging
import re

import pandas as pd

from fantasy_quant import config
from fantasy_quant.data import db
from fantasy_quant.data.breaks import BreakMap, sentinel_exclusion_sql

log = logging.getLogger(__name__)

TEAM_WEEK_TABLE = "offense_team_week"
PLAYER_WEEK_TABLE = "offense_player_week"
PERSONNEL_MAP_TABLE = "offense_personnel_map"
OFFENSE_PLAY_VIEW = "participation_offense_player_play"

#: The FTN charting floor. 2022 is the first charted season and ``DEV_SEASONS`` ends at 2022, so
#: exactly one development season exists — which is why these columns are descriptive only.
FTN_FLOOR = 2022

#: Position token → unit, for both ``offense_personnel`` encodings. The skill-only form names only
#: RB/TE/WR (OL and QB implied); the full-22 form names all eleven. Both land in the same buckets.
_UNIT: dict[str, str] = {
    "RB": "rb", "HB": "rb", "FB": "rb",
    "TE": "te",
    "WR": "wr",
    "QB": "qb",
    "C": "ol", "G": "ol", "T": "ol", "OL": "ol", "OT": "ol", "OG": "ol",
}

_TOKEN = re.compile(r"(\d+)\s+([A-Z]+)")

#: The 19 charted routes. The spec said 14; the store holds 19 — enumerated rather than counted,
#: so a vendor adding a 20th shows up as an unparsed string instead of silently joining "other".
ROUTES: tuple[str, ...] = (
    "GO", "HITCH", "FLAT", "SCREEN", "OUT", "CROSS", "SLANT", "QUICK OUT", "HITCH/CURL",
    "POST", "CORNER", "IN", "IN/DIG", "ANGLE", "DEEP OUT", "SHALLOW CROSS/DRAG", "SWING",
    "WHEEL", "TEXAS/ANGLE",
)

#: Route → a coarse family, for the columns a human actually reads. Depth first, then breaking
#: direction: the distinction that matters for a receiver's role is how far downfield he works.
ROUTE_FAMILY: dict[str, str] = {
    "GO": "deep", "POST": "deep", "CORNER": "deep", "DEEP OUT": "deep", "WHEEL": "deep",
    "OUT": "intermediate", "IN": "intermediate", "IN/DIG": "intermediate",
    "CROSS": "intermediate", "HITCH/CURL": "intermediate",
    "HITCH": "short", "SLANT": "short", "QUICK OUT": "short",
    "SHALLOW CROSS/DRAG": "short",
    "FLAT": "behind_los", "SCREEN": "behind_los", "SWING": "behind_los",
    "ANGLE": "behind_los", "TEXAS/ANGLE": "behind_los",
}


def _route_col(route: str) -> str:
    """Column-safe name for a route, so ``IN/DIG`` and ``QUICK OUT`` survive as identifiers."""
    return "route_" + re.sub(r"[^a-z0-9]+", "_", route.lower()).strip("_")


def parse_offense_personnel(text: str | None) -> dict[str, object]:
    """Collapse either ``offense_personnel`` encoding to skill counts and a package label.

    ``package`` is the league's own ``RB``-then-``TE`` notation — ``11`` is 1 RB / 1 TE / 3 WR — and
    it is identical under both encodings because the extra OL and QB tokens the full-22 form carries
    are counted separately and never reach it.

    ``other`` counts men listed at neither a skill, OL nor QB position. Non-zero means a defensive
    position appeared in an offensive string, i.e. a special-teams unit or a two-way player, and
    per 0.13.2 it is kept as **provenance and never used as a filter** — the builders filter on
    ``play_type`` instead.
    """
    out: dict[str, object] = {"rb": 0, "te": 0, "wr": 0, "ol": 0, "qb": 0, "other": 0,
                              "package": None, "n_men": 0, "n_skill": 0}
    if not text or not isinstance(text, str):
        return out
    for count, token in _TOKEN.findall(text.upper()):
        unit = _UNIT.get(token)
        n = int(count)
        out[unit if unit else "other"] = int(out[unit if unit else "other"]) + n  # type: ignore[arg-type]
        out["n_men"] = int(out["n_men"]) + n
    if out["n_men"] == 0:
        return out
    out["n_skill"] = int(out["rb"]) + int(out["te"]) + int(out["wr"])  # type: ignore[arg-type]
    # ★ Package is defined only where the eleven are a scrimmage offense. A kick unit parses to
    # nonsense personnel (0 RB, 0 TE, 0 WR and eight "other"), and labelling that "00 personnel"
    # would put a punt team in the empty-formation bucket.
    if int(out["n_skill"]) == 0 and int(out["other"]) > 0:  # type: ignore[arg-type]
        return out
    out["package"] = f"{min(int(out['rb']), 9)}{min(int(out['te']), 9)}"  # type: ignore[arg-type]
    return out


def build_personnel_map(con) -> pd.DataFrame:
    """Materialize the distinct-string → units lookup, so the parse happens once per *string*.

    1,468 distinct strings from 2023 against 46k plays a season is the whole reason this is a map
    and not a scalar function applied per row.
    """
    distinct = con.execute(
        "select distinct offense_personnel from participation where offense_personnel is not null"
    ).df()
    parsed = [parse_offense_personnel(s) for s in distinct["offense_personnel"]]
    out = pd.concat([distinct.reset_index(drop=True), pd.DataFrame(parsed)], axis=1)
    db.write_df(con, PERSONNEL_MAP_TABLE, out)
    return out


def assert_ftn_backtestable(seasons) -> None:
    """Raise if FTN-derived columns are requested for a season FTN does not cover.

    ⚠ This is the ``backtestable: false`` assertion, and it is deliberately harsher than a floor
    check: FTN begins in 2022 and ``DEV_SEASONS`` ends in 2022, so **one** development season exists
    and a walk-forward over it is a single observation, not a backtest. A prose warning is not a
    guard.
    """
    wanted = sorted({int(s) for s in seasons})
    below = [s for s in wanted if s < FTN_FLOOR]
    if below:
        raise ValueError(
            f"FTN charting columns (motion / play-action / RPO / screen) have no data before "
            f"{FTN_FLOOR}; requested {below}. Per-column floor, not per-table (T49)."
        )
    dev = [s for s in wanted if s in set(config.DEV_SEASONS)]
    if len(dev) == len(wanted) and wanted:
        raise ValueError(
            f"FTN columns are backtestable: false — {FTN_FLOOR}+ overlaps DEV_SEASONS "
            f"(…{max(config.DEV_SEASONS)}) in exactly one season, so a DEV-only request "
            f"({wanted}) is a single observation, not a walk-forward. Use them descriptively."
        )


def scrimmage_fill_by_season(
        con, columns=("offense_personnel", "offense_formation")) -> pd.DataFrame:
    """★ The high-cardinality blind spot, measured: naive fill vs fill on a **stable population**.

    ``breaks.build_break_map`` skips columns above ``MAX_CARDINALITY`` and its conservation test
    keys on a single arriving value, so a re-encoding that arrives spread across hundreds of new
    strings is invisible to it twice over. Conditioning on scrimmage plays is the population-level
    version of the same question, and it is what licenses every rate below to pool across 2023.
    """
    sel = ",\n".join(
        f"""round(avg(case when p.{c} is not null and p.{c} <> '' then 1.0 else 0.0 end), 4)
                as {c}_naive,
            round(avg(case when p.{c} is not null and p.{c} <> '' then 1.0 else 0.0 end)
                filter (where b.play_type in ('pass','run')), 4) as {c}_scrimmage"""
        for c in columns
    )
    return con.execute(f"""
        select p.season,
               count(*)                                              as plays,
               count(*) filter (where b.play_type in ('pass','run')) as scrimmage_plays,
               count(distinct p.offense_personnel)                   as n_personnel_strings,
               {sel}
        from participation p
        left join pbp b using (game_id, play_id)
        group by 1 order by 1
    """).df()


def offense_player_play_view(con) -> None:
    """Explode the offensive eleven **with positions and the route**, by parallel unnest.

    DATA-1's ``participation_player_play`` carries ``gsis_id`` and the route but **not**
    ``offense_positions``; 0.13.2 hit the same gap on the defensive side and built its own view
    rather than joining the two lists back together by row number afterwards.

    ⚠ The route on a participation row is the route of **one** receiver, not of each of the eleven.
    The vendor gives one ``route`` per play, so it describes the play's charted route and is kept
    here as *play context*; the per-player route tree below attributes it only to the targeted
    receiver, which is the only attribution the column can honestly support.
    """
    con.execute(f"""
        create or replace view {OFFENSE_PLAY_VIEW} as
        select season, week, game_id, play_id, possession_team,
               offense_formation, offense_personnel, route,
               unnest(str_split(offense_players, ';'))                 as gsis_id,
               -- coalesce so the shorter list pads with NULLs rather than truncating the row:
               -- requiring positions would silently drop every pre-2023 season (0.13.2's lesson).
               unnest(str_split(coalesce(offense_positions, ''), ';')) as position
        from participation
        where offense_players is not null
    """)


def build_offense_team_week(con, bm: BreakMap) -> dict:
    """One row per (season, week, offensive team): formation, personnel, tempo, FTN charting.

    The offense is ``pbp.posteam``. Participation's ``possession_team`` names it too, but every
    other table in this session keys off pbp and a second source for the same fact is a second
    thing to reconcile.
    """
    build_personnel_map(con)
    # participation's own sentinel columns are not read here, but the predicate is threaded so the
    # module has one place to add one; `route` carries no classified break (it is ~0.38 throughout,
    # which is the pass-play share, not missingness — DATA-1's denominator lesson).
    _ = sentinel_exclusion_sql(bm, "participation", "was_pressure", "p")
    con.execute(f"""
        create or replace table {TEAM_WEEK_TABLE} as
        with plays as (
            select p.season, p.week, b.posteam as team,
                   p.offense_formation, m.package, m.rb, m.te, m.wr, m.other,
                   b.qb_dropback, b.play_type, b.no_huddle, b.shotgun, b.down,
                   b.score_differential, b.half_seconds_remaining, b.game_seconds_remaining,
                   b.xpass, b.pass_oe, b.epa, b.yardline_100, b.fixed_drive_result,
                   f.is_motion, f.is_play_action, f.is_rpo, f.is_screen_pass,
                   f.n_offense_backfield, f.qb_location,
                   -- FTN coverage as a column, so a consumer can see the floor rather than read
                   -- a null share and guess whether the team never motioned or was never charted.
                   case when f.ftn_play_id is not null then 1 else 0 end as ftn_charted
            from participation p
            left join pbp b using (game_id, play_id)
            left join {PERSONNEL_MAP_TABLE} m using (offense_personnel)
            left join ftn_charting f using (game_id, play_id)
            where b.posteam is not null
              -- ★ The one filter that makes 2016-2022 and 2023+ the same population. Measured, not
              -- assumed: `scrimmage_fill_by_season` shows offense_personnel at 1.000 in every
              -- season under it, against a naive 0.754 -> 1.000 jump without it.
              and b.play_type in ('pass', 'run')
        )
        select
            season, week, team,
            count(*)                                                     as off_snaps,
            count(*) filter (where qb_dropback = 1)                      as dropbacks,
            avg(case when play_type = 'pass' then 1.0 else 0.0 end)      as pass_rate,
            -- neutral script: the pass rate a team chooses, not the one the scoreboard forces.
            avg(case when play_type = 'pass' then 1.0 else 0.0 end)
                filter (where abs(score_differential) <= 7
                        and game_seconds_remaining > 300)                as pass_rate_neutral,
            avg(pass_oe)                                                 as pass_oe_mean,
            avg(xpass)                                                   as xpass_mean,
            -- formation
            avg(case when offense_formation = 'SHOTGUN' then 1.0 else 0.0 end)
                                                                        as share_shotgun,
            avg(case when offense_formation = 'SINGLEBACK' then 1.0 else 0.0 end)
                                                                        as share_singleback,
            avg(case when offense_formation = 'UNDER CENTER' then 1.0 else 0.0 end)
                                                                        as share_under_center,
            avg(case when offense_formation = 'I_FORM'       then 1.0 else 0.0 end) as share_i_form,
            avg(case when offense_formation = 'EMPTY'        then 1.0 else 0.0 end) as share_empty,
            avg(case when offense_formation = 'PISTOL'       then 1.0 else 0.0 end) as share_pistol,
            avg(case when offense_formation = 'JUMBO'        then 1.0 else 0.0 end) as share_jumbo,
            avg(case when offense_formation = 'WILDCAT' then 1.0 else 0.0 end)
                                                                        as share_wildcat,
            count(offense_formation)                                     as snaps_with_formation,
            -- personnel
            avg(case when package = '11' then 1.0 else 0.0 end)          as share_p11,
            avg(case when package = '12' then 1.0 else 0.0 end)          as share_p12,
            avg(case when package = '21' then 1.0 else 0.0 end)          as share_p21,
            avg(case when package = '13' then 1.0 else 0.0 end)          as share_p13,
            avg(case when package = '22' then 1.0 else 0.0 end)          as share_p22,
            avg(case when package = '10' then 1.0 else 0.0 end)          as share_p10,
            avg(case when package not in ('11','12','21','13','22','10')
                     then 1.0 else 0.0 end)                              as share_p_other,
            count(package)                                               as snaps_with_personnel,
            avg(rb)                                                      as rb_mean,
            avg(te)                                                      as te_mean,
            avg(wr)                                                      as wr_mean,
            count(*) filter (where coalesce(other, 0) > 0)               as snaps_two_way_listed,
            -- tempo: pbp, so it covers 2016-2025 rather than FTN's 2022+
            avg(case when no_huddle = 1 then 1.0 else 0.0 end)           as no_huddle_rate,
            avg(case when shotgun = 1 then 1.0 else 0.0 end)             as shotgun_rate,
            -- ★ FTN, 2022+ only. NULL before the floor by construction: the filter is on the
            -- charted flag, so a pre-2022 row reports NULL (never charted) rather than 0 (charted,
            -- no motion). The distinction is the entire T50 lesson.
            avg(case when is_motion then 1.0 else 0.0 end)
                filter (where ftn_charted = 1)                           as motion_rate,
            avg(case when is_play_action then 1.0 else 0.0 end)
                filter (where ftn_charted = 1 and qb_dropback = 1)       as play_action_rate,
            avg(case when is_rpo then 1.0 else 0.0 end)
                filter (where ftn_charted = 1)                           as rpo_rate,
            avg(case when is_screen_pass then 1.0 else 0.0 end)
                filter (where ftn_charted = 1 and qb_dropback = 1)       as screen_rate,
            avg(n_offense_backfield) filter (where ftn_charted = 1)      as backfield_mean,
            avg(case when qb_location = 'S' then 1.0 else 0.0 end)
                filter (where ftn_charted = 1)                           as qb_shotgun_ftn_rate,
            count(*) filter (where ftn_charted = 1)                      as ftn_snaps,
            -- red-zone workload, the 0.13.6 sibling that belongs at offensive team-week
            count(*) filter (where yardline_100 <= 20)                   as rz_snaps,
            avg(epa)                                                     as epa_per_play,
            current_localtimestamp()                                     as pulled_at
        from plays
        group by 1, 2, 3
    """)
    n, teams, seasons = con.execute(
        f"select count(*), count(distinct team), count(distinct season) from {TEAM_WEEK_TABLE}"
    ).fetchone()
    return {"table": TEAM_WEEK_TABLE, "n_rows": int(n), "n_teams": int(teams),
            "n_seasons": int(seasons)}


def build_offense_player_week(con, bm: BreakMap) -> dict:
    """One row per (season, week, offensive player): the route tree, and usage **by personnel**.

    Two derivations DATA-1's ``participation_player_week`` does not carry:

    - **the route tree** — 19 charted routes as counts, plus four depth families. The route is
      attributed to the **targeted receiver only**, because the vendor gives one route per play and
      spreading it over the other four eligibles would invent four routes that were never charted.
    - **usage within a personnel grouping** — snaps and targets split by the offense's package,
      which is the "target share within personnel grouping" deep-dive question at its own grain
      rather than as a one-off query.

    ⚠ **13 personnel carries a denominator column and the others do not.** ``snaps_p13`` shipped
    from the start, but targets and carries in the package did not, so the productivity half of
    the question had to drop to the play view. It is a column now — with ``team_targets_p13``
    beside it, because a ~3-5% package throws one target in a team-week often enough that an
    ungated ``target_share_p13`` reads 1.0000 off a denominator of 1.
    """
    offense_player_play_view(con)
    route_cols = ",\n            ".join(
        f"count(*) filter (where targeted and route = '{r}') as {_route_col(r)}" for r in ROUTES
    )
    fam_cols = ",\n            ".join(
        f"""count(*) filter (where targeted and route in
            ({','.join(chr(39) + r + chr(39) for r, f in ROUTE_FAMILY.items() if f == fam)}))
            as routes_{fam}"""
        for fam in ("deep", "intermediate", "short", "behind_los")
    )
    con.execute(f"""
        create or replace table {PLAYER_WEEK_TABLE} as
        with pp as (
            -- distinct: the vendor lists the same gsis_id twice on some plays (0.13.2 found a
            -- defender listed twice on 44 of 57 snaps). A man is on the field or he is not.
            select distinct on (v.game_id, v.play_id, v.gsis_id)
                   v.season, v.week, v.gsis_id, b.posteam as team, v.position, v.route,
                   m.package, b.qb_dropback, b.play_type,
                   (b.receiver_player_id = v.gsis_id)                   as targeted,
                   (b.rusher_player_id  = v.gsis_id)                    as carried,
                   b.yardline_100, b.air_yards, b.yards_gained, b.complete_pass
            from {OFFENSE_PLAY_VIEW} v
            left join pbp b using (game_id, play_id)
            left join {PERSONNEL_MAP_TABLE} m using (offense_personnel)
            where v.gsis_id is not null and v.gsis_id <> '' and b.posteam is not null
              and b.play_type in ('pass', 'run')
        )
        select
            season, week, gsis_id, team,
            count(*)                                                     as snaps,
            mode(position)                                               as position_listed,
            count(distinct position)                                     as n_positions_listed,
            count(*) filter (where qb_dropback = 1)                      as snaps_dropback,
            -- usage by personnel grouping
            count(*) filter (where package = '11')                       as snaps_p11,
            count(*) filter (where package = '12')                       as snaps_p12,
            count(*) filter (where package = '21')                       as snaps_p21,
            count(*) filter (where package = '13')                       as snaps_p13,
            count(*) filter (where targeted)                             as targets,
            count(*) filter (where targeted and package = '11')          as targets_p11,
            count(*) filter (where targeted and package = '12')          as targets_p12,
            count(*) filter (where targeted and package = '21')          as targets_p21,
            count(*) filter (where targeted and package = '13')          as targets_p13,
            count(*) filter (where carried)                              as carries,
            count(*) filter (where carried and package = '11')           as carries_p11,
            count(*) filter (where carried and package = '12')           as carries_p12,
            count(*) filter (where carried and package = '21')           as carries_p21,
            count(*) filter (where carried and package = '13')           as carries_p13,
            count(*) filter (where targeted and yardline_100 <= 20)      as targets_rz,
            count(*) filter (where carried and yardline_100 <= 20)       as carries_rz,
            avg(air_yards) filter (where targeted)                       as adot,
            -- the route tree, targeted receiver only
            count(*) filter (where targeted and route is not null and route <> '')
                                                                         as routes_charted,
            {route_cols},
            {fam_cols},
            current_localtimestamp()                                     as pulled_at
        from pp
        group by 1, 2, 3, 4
    """)
    con.execute(f"""
        create or replace table {PLAYER_WEEK_TABLE} as
        select w.*,
               round(w.snaps   / nullif(t.off_snaps, 0), 4)  as snap_share,
               round(w.targets / nullif(t.dropbacks, 0), 4)  as target_rate,
               -- ★ target share WITHIN a personnel grouping: the deep-dive question as a column.
               -- Denominator is the team's targets in that grouping, so a 12-personnel TE is
               -- measured against the snaps he was actually on the field for.
               round(w.targets_p11 / nullif(sum(w.targets_p11) over (partition by w.season, w.week,
                     w.team), 0), 4)                          as target_share_p11,
               round(w.targets_p12 / nullif(sum(w.targets_p12) over (partition by w.season, w.week,
                     w.team), 0), 4)                          as target_share_p12,
               round(w.targets_p13 / nullif(sum(w.targets_p13) over (partition by w.season, w.week,
                     w.team), 0), 4)                          as target_share_p13,
               -- ⚠ the p13 denominator is small enough to be dangerous, which is why it ships as
               -- a column rather than staying implicit. 13 personnel is a ~3-5% package league-
               -- wide, so a team-week often throws one target from it and the share reads 1.0000
               -- off a denominator of 1. Gate on this before ranking anyone by target_share_p13;
               -- p11/p12 need no such guard because their denominators are never that thin.
               sum(w.targets_p13) over (partition by w.season, w.week, w.team)
                                                              as team_targets_p13
        from {PLAYER_WEEK_TABLE} w
        left join {TEAM_WEEK_TABLE} t using (season, week, team)
    """)
    n, players, seasons = con.execute(
        f"select count(*), count(distinct gsis_id), count(distinct season) from {PLAYER_WEEK_TABLE}"
    ).fetchone()
    return {"table": PLAYER_WEEK_TABLE, "n_rows": int(n), "n_players": int(players),
            "n_seasons": int(seasons)}


def reconcile_sides(con) -> pd.DataFrame:
    """★ B4a: does every play resolve **11-and-11** where the vendor's own counts say it should?

    ``n_offense``/``n_defense`` are the vendor's assertion about how many men it listed. This
    compares that assertion against the lists it actually emitted, per season, so a truncated
    ``offense_players`` string surfaces as a count mismatch rather than as a quietly short roster.

    ⚠ **Each side gets its own denominator.** The first version of this divided the offensive
    resolve count by the number of plays claiming 11-*and*-11, i.e. a numerator counted over a
    wider set than its denominator — which produced a "resolve rate" of **1.016** and a bar that
    could not fail. A rate whose numerator is not a subset of its denominator is not a rate.
    """
    return con.execute("""
        select season,
               count(*)                                                       as plays,
               count(*) filter (where n_offense = 11)                          as offense_claims_11,
               count(*) filter (where n_offense = 11
                                and len(str_split(offense_players, ';')) = 11) as offense_resolves,
               count(*) filter (where n_defense = 11)                          as defense_claims_11,
               count(*) filter (where n_defense = 11
                                and len(str_split(defense_players, ';')) = 11) as defense_resolves,
               count(*) filter (where offense_players is null
                                   or defense_players is null)                 as missing_lists
        from participation
        group by 1 order by 1
    """).df()


def reconcile_player_weeks(con) -> pd.DataFrame:
    """★ B4b: do the two exploded player-week tables account for **eleven men per scrimmage play**?

    The offensive and defensive team-week tables are built from the same pbp rows, so comparing
    their snap counts to each other is not a check — it is an identity that cannot fail, and the
    first version of this compared a team's own offensive snaps against its own *defensive* snaps,
    two genuinely different quantities that differ by the ordinary possession asymmetry (~11.6
    plays a week). It reported a "gap" that was simply football.

    The reconciliation with content is against the **lists the vendor actually emitted**:
    ``sum(snaps)`` over an exploded table must equal the total length of the player lists on the
    same plays, so the ratio is ≤ 1 by construction and anything *above* 1 means a man was counted
    twice on one play.

    ⚠ **Not 11 × plays.** The first version used that, and it failed at ratio 1.0054 — because the
    vendor lists **twelve** men on 2,739 scrimmage plays and ten on 2,171. The expected side was
    wrong, not the table. *Eleven-a-side is football's rule, not the file's*, and a bar has to be
    written against the file. The off-eleven plays are counted below rather than filtered, per
    ``assert_regime_coverage``'s dropped-rows-are-reasoned rule.
    """
    return con.execute(f"""
        with scrim as (
            select p.season, count(*) as plays,
                   count(*) filter (where p.offense_players is null)      as no_offense_list,
                   count(*) filter (where p.defense_players is null)      as no_defense_list,
                   sum(len(str_split(p.offense_players, ';')))            as offense_listed_men,
                   sum(len(str_split(p.defense_players, ';')))            as defense_listed_men,
                   count(*) filter (where p.offense_players is not null
                        and len(str_split(p.offense_players, ';')) <> 11)
                                                                          as offense_not_eleven,
                   count(*) filter (where p.defense_players is not null
                        and len(str_split(p.defense_players, ';')) <> 11)
                                                                          as defense_not_eleven
            from participation p
            left join pbp b using (game_id, play_id)
            where b.play_type in ('pass', 'run') and b.posteam is not null
            group by 1
        ),
        o as (select season, sum(snaps) as man_snaps from {PLAYER_WEEK_TABLE} group by 1),
        d as (select season, sum(snaps) as man_snaps from defense_player_week group by 1)
        select s.season, s.plays, s.no_offense_list, s.no_defense_list,
               s.offense_not_eleven, s.defense_not_eleven,
               s.offense_listed_men                              as offense_expected,
               o.man_snaps                                       as offense_actual,
               s.defense_listed_men                              as defense_expected,
               d.man_snaps                                       as defense_actual,
               round(o.man_snaps / nullif(s.offense_listed_men, 0), 4) as offense_ratio,
               round(d.man_snaps / nullif(s.defense_listed_men, 0), 4) as defense_ratio
        from scrim s left join o using (season) left join d using (season)
        order by 1
    """).df()
