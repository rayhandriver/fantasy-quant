"""Phase 0.13.5 — **team construction**: money, draft capital, age and continuity.

Four tables DATA-1's register listed at ``readers: 0`` — ``contracts`` (51,793), ``weekly_rosters``
(533,275), ``depth_charts_all`` (955,989), ``draft_picks`` (3,077) — become one row per
(season, team). This is T45/T47's pattern for a third and fourth time, and the consumer column
existing is what made it visible.

★ **The architecture that makes this work: the roster names the team, the contract names the
money.** ``contracts.team`` is *not* a team code — it is an OTC **nickname** ("Ravens", "49ers")
for 50,134 rows and a **career-path string** ("ARI/ATL/NYJ") for the other 1,659, so 90 distinct
values come out of a 32-team league. Attributing money through it directly gives a per-team cap
sheet that is wrong in a way that looks right. Team membership therefore comes from
``weekly_rosters`` (real codes, per season, per week) and the contract is joined to the **player**.
88–97 % of rostered players resolve to a contract in force, per season, and the rate ships as a
column rather than as a footnote.

⚠ **``contracts`` has no unique row key** — the register's own note; groups of up to 9
byte-identical rows exist. Every read here deduplicates **before** aggregating, because a naive
``sum(apy)`` multiplies a player's money by his duplicate count, and it does so worst for exactly
the expensive veterans whose rows repeat most.

⚠ **This is not a cap sheet, and the columns say so.** OTC gives a contract's signing year, length
and average-per-year; it does not give per-season cap hits, dead money, restructures or the June-1
mechanics. A contract is treated as in force over its **nominal window** ``[year_signed,
year_signed + years)`` — the standard OTC-derived approximation — so ``cap_pct_*`` is *accounted
APY as a share of that season's cap*, and ``cap_accounted_pct`` states how much of the cap the
accounting reaches. The **normalized** ``cap_share_*`` columns are the ones a deep dive should
read: they answer "how much of its money does this team put in the receiver room", which survives
the coverage gap, where "what fraction of the cap" does not.
"""

from __future__ import annotations

import logging

import pandas as pd

from fantasy_quant.data.teams import canon_team_sql as canon

log = logging.getLogger(__name__)

CONSTRUCTION_TABLE = "team_construction_season"
CONTRACT_SEASON_TABLE = "contract_season"

#: The position groups. Specialists collapse to one; the rest stand alone.
POSITION_GROUPS: tuple[str, ...] = ("QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB", "ST")

#: ★ **``weekly_rosters.position`` is TWO vocabularies, and the seam is 2016.** 2014-2015 use
#: fine-grained positions (CB, FS, SS, DE, DT, NT, ILB, MLB, OLB, C, G, T, FB); 2016+ use the
#: already-grouped ones (DB, DL, LB, OL). The third two-encodings column this session has met,
#: after ``defense_personnel`` and ``offense_personnel`` — and the one that hurt, because the
#: unmapped fine-grained positions fell into **no** group and silently vanished from every share,
#: which is how 64 team-seasons came to have position shares that did not sum to 1.
#:
#: ⚠ The 0.13.0 break map does not flag this either: at 27 distinct values it is under
#: ``MAX_CARDINALITY``, but the change is a **vocabulary swap** among observed values, not a null
#: collapsing onto a sentinel, so the conservation test has nothing to conserve. *Two of this
#: session's three encoding seams are invisible to the detector built for encoding seams* — one
#: over the cardinality ceiling, one under the conservation test.
_POSITION_TO_GROUP: dict[str, str] = {
    # already-grouped (2016+) — identity, stated rather than assumed
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "OL": "OL", "DL": "DL", "LB": "LB", "DB": "DB",
    # fine-grained (2014-2015)
    "FB": "RB",
    "C": "OL", "G": "OL", "T": "OL", "OT": "OL", "OG": "OL",
    "DE": "DL", "DT": "DL", "NT": "DL",
    "ILB": "LB", "MLB": "LB", "OLB": "LB",
    "CB": "DB", "FS": "DB", "SS": "DB", "S": "DB",
    # specialists, both eras
    "K": "ST", "P": "ST", "LS": "ST", "PK": "ST",
    # return specialists appear twice in the whole table; they are not a room
    "PR": "ST", "KR": "ST",
}

OFFENSE_GROUPS = ("QB", "RB", "WR", "TE", "OL")
DEFENSE_GROUPS = ("DL", "LB", "DB")

#: Pick-value curves available in ``draft_values``. ``johnson`` is the Jimmy Johnson trade chart,
#: the league's own lingua franca; the others are surplus-value curves. It is a **parameter** so
#: that changing the curve is a decision at the call site rather than an edit to a query.
PICK_VALUE_CURVES: tuple[str, ...] = ("johnson", "stuart", "hill", "otc", "pff")
DEFAULT_CURVE = "johnson"

#: Trailing window for draft capital. Three years is the span over which a draft class is still
#: the reason a room looks the way it does.
DRAFT_WINDOW = 3


def position_group(pos: str | None) -> str | None:
    """Map either roster-position vocabulary to a position group. The **only** place that maps."""
    if not pos or not isinstance(pos, str):
        return None
    return _POSITION_TO_GROUP.get(pos.strip().upper())


def _group_case(col: str = "r.position") -> str:
    """The same mapping as SQL, generated from :data:`_POSITION_TO_GROUP`.

    Generated, not written twice — the whole defect this replaces was a mapping that covered one
    vocabulary and quietly dropped the other.
    """
    whens = " ".join(f"when '{k}' then '{v}'" for k, v in _POSITION_TO_GROUP.items())
    return f"(case upper({col}) {whens} else null end)"


def build_contract_season(con) -> dict:
    """One row per (player, season) — the contract in force, deduplicated.

    Two hazards are handled here rather than at every call site:

    1. **the duplicate rows** — ``select distinct`` over the contract's identifying columns runs
       *before* anything aggregates, so a player with 9 identical rows contributes his APY once;
    2. **overlapping contracts** — an extension signed mid-deal leaves two nominal windows covering
       the same season, so the most recently signed one wins (``qualify row_number``), which is
       what "the contract in force" means.
    """
    con.execute(f"""
        create or replace table {CONTRACT_SEASON_TABLE} as
        with deduped as (
            select distinct gsis_id, year_signed, years, value, apy, guaranteed, apy_cap_pct,
                            position as contract_position, otc_id
            from contracts
            where gsis_id is not null and gsis_id <> ''
              -- 1,121 rows carry year_signed = 0; a nominal window from year zero covers every
              -- season and would put a junk row in force for all of them.
              and year_signed between 1990 and 2026
        ),
        seasons as (select unnest(generate_series(2014, 2026)) as season),
        in_force as (
            select s.season, d.*
            from deduped d cross join seasons s
            where d.year_signed <= s.season
              and d.year_signed + coalesce(nullif(d.years, 0), 1) > s.season
        )
        select * from in_force
        qualify row_number() over (
            partition by gsis_id, season order by year_signed desc, apy desc nulls last
        ) = 1
    """)
    n, players = con.execute(
        f"select count(*), count(distinct gsis_id) from {CONTRACT_SEASON_TABLE}").fetchone()
    return {"table": CONTRACT_SEASON_TABLE, "n_rows": int(n), "n_players": int(players)}


def build_team_construction(con, curve: str = DEFAULT_CURVE) -> dict:
    """One row per (season, team): cap allocation, draft capital, age, experience, continuity.

    ``continuity`` is snap-weighted off the ``snaps`` table (2014–2025, all three phases) rather
    than off participation: participation starts in 2016 and covers scrimmage only, and continuity
    is a **roster** property that ought to include the kicking units.
    """
    if curve not in PICK_VALUE_CURVES:
        raise ValueError(f"unknown pick-value curve {curve!r}; have {PICK_VALUE_CURVES}")
    build_contract_season(con)
    grp = _group_case()
    cap_cols = ",\n            ".join(
        f"""sum(c.apy_cap_pct) filter (where {grp} = '{g}')  as cap_pct_{g.lower()}"""
        for g in POSITION_GROUPS
    )
    age_cols = ",\n            ".join(
        f"""avg(r.age) filter (where {grp} = '{g}')          as age_{g.lower()}"""
        for g in POSITION_GROUPS
    )
    n_cols = ",\n            ".join(
        f"""count(distinct r.gsis_id) filter (where {grp} = '{g}') as n_{g.lower()}"""
        for g in POSITION_GROUPS
    )
    con.execute(f"""
        create or replace table {CONSTRUCTION_TABLE} as
        with roster as (
            -- one row per (season, team, player): a player traded mid-season belongs to both
            -- rooms, which is what a construction table should say.
            -- ★ the team code is routed through the PBP canon, not the ADP one: this table has to
            -- join to offense_team_week / defense_team_week, which are pbp-keyed (Rams = LA).
            select distinct r.season, {canon('r.team')} as team, r.gsis_id, r.position,
                   r.years_exp,
                   case when r.birth_date is null or r.birth_date = '' then null
                        else date_diff('year', try_cast(r.birth_date as date),
                                       make_date(r.season, 9, 1)) end as age
            from weekly_rosters r
            where r.gsis_id is not null and r.gsis_id <> '' and r.team is not null
              and r.game_type = 'REG'
        ),
        money as (
            select r.season, r.team,
                   {cap_cols},
                   {age_cols},
                   {n_cols},
                   avg(r.years_exp)                                    as years_exp_mean,
                   count(distinct r.gsis_id)                           as n_rostered,
                   count(distinct r.gsis_id) filter (where c.gsis_id is not null)
                                                                       as n_with_contract,
                   sum(c.apy)                                          as apy_total_m,
                   sum(c.apy_cap_pct)                                  as cap_accounted_pct
            from roster r
            left join {CONTRACT_SEASON_TABLE} c
                   on c.gsis_id = r.gsis_id and c.season = r.season
            group by 1, 2
        ),
        capital as (
            -- draft capital INVESTED by the team over a trailing 3-year window, on a named
            -- pick-value curve. `d.team` is the drafting team, which is the point: this measures
            -- what the front office spent, not who ended up on the roster.
            select s.season, {canon('d.team')} as team,
                   sum(v.{curve})                                      as draft_capital,
                   sum(v.{curve}) filter (where d.side = 'O')          as draft_capital_offense,
                   sum(v.{curve}) filter (where d.side = 'D')          as draft_capital_defense,
                   count(*)                                            as n_picks,
                   count(*) filter (where d.round = 1)                 as n_picks_r1,
                   count(*) filter (where d.round <= 3)                as n_picks_r1_3
            from (select unnest(generate_series(2014, 2026)) as season) s
            join draft_picks d
              on d.season between s.season - {DRAFT_WINDOW} and s.season - 1
            left join draft_values v on v.pick = d.pick
            where d.team is not null
            group by 1, 2
        ),
        continuity as (
            -- share of this season's snaps taken by men who were on the SAME team last season.
            -- The denominator is snaps, not bodies: a team can return 45 of 53 players and still
            -- have rebuilt, if the eight who left played every down.
            select cur.season, cur.team,
                   sum(cur.offense_snaps) filter (where prev.gsis_id is not null)
                       / nullif(sum(cur.offense_snaps), 0)             as continuity_offense,
                   sum(cur.defense_snaps) filter (where prev.gsis_id is not null)
                       / nullif(sum(cur.defense_snaps), 0)             as continuity_defense,
                   sum(cur.st_snaps) filter (where prev.gsis_id is not null)
                       / nullif(sum(cur.st_snaps), 0)                  as continuity_st,
                   sum(cur.offense_snaps + cur.defense_snaps)          as snaps_total
            from (
                select season, {canon('team')} as team, gsis_id,
                       sum(coalesce(offense_snaps, 0)) as offense_snaps,
                       sum(coalesce(defense_snaps, 0)) as defense_snaps,
                       sum(coalesce(st_snaps, 0))      as st_snaps
                from snaps where gsis_id is not null and gsis_id <> '' and game_type = 'REG'
                group by 1, 2, 3
            ) cur
            left join (
                select distinct season, {canon('team')} as team, gsis_id from snaps
                where gsis_id is not null and gsis_id <> '' and game_type = 'REG'
            ) prev
              on prev.gsis_id = cur.gsis_id and prev.team = cur.team
             and prev.season = cur.season - 1
            group by 1, 2
        )
        select m.season, m.team,
               m.n_rostered, m.n_with_contract,
               round(m.n_with_contract / nullif(m.n_rostered, 0), 4)   as contract_coverage,
               m.apy_total_m, m.cap_accounted_pct,
               {", ".join(f"m.cap_pct_{g.lower()}" for g in POSITION_GROUPS)},
               -- ★ the normalized shares: what fraction of the money it accounts for does this
               -- team put in each room. Robust to the coverage gap in a way cap_pct_* is not.
               {", ".join(f'''round(m.cap_pct_{g.lower()} / nullif(m.cap_accounted_pct, 0), 4)
                   as cap_share_{g.lower()}''' for g in POSITION_GROUPS)},
               round(({" + ".join(f"coalesce(m.cap_pct_{g.lower()}, 0)" for g in OFFENSE_GROUPS)})
                     / nullif(m.cap_accounted_pct, 0), 4)              as cap_share_offense,
               round(({" + ".join(f"coalesce(m.cap_pct_{g.lower()}, 0)" for g in DEFENSE_GROUPS)})
                     / nullif(m.cap_accounted_pct, 0), 4)              as cap_share_defense,
               {", ".join(f"m.age_{g.lower()}" for g in POSITION_GROUPS)},
               {", ".join(f"m.n_{g.lower()}" for g in POSITION_GROUPS)},
               m.years_exp_mean,
               cap.draft_capital, cap.draft_capital_offense, cap.draft_capital_defense,
               cap.n_picks, cap.n_picks_r1, cap.n_picks_r1_3,
               round(cont.continuity_offense, 4)                       as continuity_offense,
               round(cont.continuity_defense, 4)                       as continuity_defense,
               round(cont.continuity_st, 4)                            as continuity_st,
               cont.snaps_total,
               '{curve}'                                               as pick_value_curve,
               'otc_nominal_window'                                    as cap_source,
               current_localtimestamp()                                as pulled_at
        from money m
        left join capital cap on cap.season = m.season and cap.team = m.team
        left join continuity cont on cont.season = m.season and cont.team = m.team
    """)
    n, teams, seasons = con.execute(
        f"select count(*), count(distinct team), count(distinct season) from {CONSTRUCTION_TABLE}"
    ).fetchone()
    return {"table": CONSTRUCTION_TABLE, "n_rows": int(n), "n_teams": int(teams),
            "n_seasons": int(seasons), "pick_value_curve": curve}


def contract_duplication(con) -> pd.DataFrame:
    """★ The duplicate-row hazard, measured — what a naive ``sum(apy)`` would have overstated by."""
    return con.execute("""
        with g as (
            select gsis_id, year_signed, years, apy, count(*) as n
            from contracts where gsis_id is not null and gsis_id <> ''
            group by 1, 2, 3, 4
        )
        select count(*) filter (where n > 1)                as duplicated_groups,
               sum(n - 1) filter (where n > 1)              as excess_rows,
               max(n)                                       as worst_group,
               round(sum(apy * n) / nullif(sum(apy), 0), 4) as naive_sum_inflation
        from g
    """).df()


def cap_reconciliation(con) -> pd.DataFrame:
    """★ B7: the accounted cap against the real one, per season, stated rather than assumed.

    A perfect cap sheet would sum ``apy_cap_pct`` to ~1.0 per team-season. This will not, and the
    number is the deliverable: it says how much of a team's money the nominal-window approximation
    reaches, which is what licenses ``cap_share_*`` and forbids reading ``cap_pct_*`` as "percent
    of the cap spent".
    """
    return con.execute(f"""
        select season,
               count(*)                                        as team_seasons,
               round(avg(cap_accounted_pct), 4)                 as mean_accounted,
               round(min(cap_accounted_pct), 4)                 as min_accounted,
               round(max(cap_accounted_pct), 4)                 as max_accounted,
               round(avg(contract_coverage), 4)                 as mean_player_coverage,
               round(avg(n_rostered), 1)                        as mean_rostered
        from {CONSTRUCTION_TABLE}
        group by 1 order by 1
    """).df()


def draft_capital_reconciliation(con, curve: str = DEFAULT_CURVE) -> pd.DataFrame:
    """★ B7: does the per-team draft capital sum back to the whole pick list?

    Every pick belongs to exactly one team, so summing the per-team capital for a single draft year
    must reproduce the total value of that year's picks. A join that silently dropped picks — a
    missing curve row for a compensatory pick beyond 262, say — shows up here as a shortfall.
    """
    return con.execute(f"""
        with picks as (
            select d.season, count(*) as n_picks, sum(v.{curve}) as total_value,
                   count(*) filter (where v.{curve} is null) as picks_without_curve,
                   max(d.pick) as max_pick
            from draft_picks d left join draft_values v on v.pick = d.pick
            group by 1
        )
        select * from picks order by season
    """).df()
