"""Phase 0.13.7 — the **unified scheme panel**: what the team-by-team deep dives actually read.

``team_scheme_week`` and ``team_scheme_season``, one row per team-week / team-season, offense
**and** defense **and** special teams **and** construction, assembled from the five fact tables
this session built. Nothing new is computed here: the panel is the join, plus the two things a
join cannot supply on its own — a **within-season z-score** and a **per-column provenance record**.

★ **Z-scored within season, and the reason has not changed since ``fingerprint.py`` first wrote it
down.** League pass rate, pace, blitz rate and personnel usage all drift hard over 2016-2025 — the
league's 11-personnel share and its 4th-down go-rate are different animals in 2016 and 2024 — so a
raw cross-season average reads **drift as personality**. A team that blitzed 28 % in 2016 was
ordinary; the same rate in 2024 is aggressive. The z-score is what makes "this team is a heavy
blitz team" mean the same thing in both seasons.

★ **Every column carries a floor and a PIT class, and the floor is per COLUMN (T49).** The panel
is the first artefact wide enough that a reader cannot hold the coverage in their head:
``man_share`` is 2018+, ``motion_rate`` is 2022+, ``share_p11`` is 2016+, ``fourth_go_rate`` is
2014+, and every one of them is a column in the same row. ``team_scheme_columns`` records which is
which, so "why is this null in 2017" has an answer in the store rather than in a person.

⚠ **A null in this panel is never zero.** A team that was not charted for man/zone in 2017 did not
play zero man coverage. Every builder here preserves the null and the column register says what
the null means — the T50 lesson in its constructive form.
"""

from __future__ import annotations

import logging

import pandas as pd

from fantasy_quant.data.breaks import BreakMap

log = logging.getLogger(__name__)

WEEK_TABLE = "team_scheme_week"
SEASON_TABLE = "team_scheme_season"
WEEK_Z_TABLE = "team_scheme_week_z"
SEASON_Z_TABLE = "team_scheme_season_z"
COLUMN_REGISTER = "team_scheme_columns"

#: Keys, provenance and identity columns — never z-scored, never treated as a metric.
_KEYS = frozenset({"season", "week", "team", "game_id", "head_coach", "pulled_at",
                   "safety_provenance", "pick_value_curve", "cap_source", "roof", "surface",
                   "is_home", "is_dome", "is_outdoors"})

#: Suffixes/prefixes that mark a **count** rather than a rate. Counts stay raw: z-scoring a snap
#: count measures how many plays a team ran, which is pace and schedule, not scheme.
_COUNT_PREFIXES = ("n_", "snaps_", "fourth_", "fg_att", "fg_made", "two_point_attempts",
                   "two_point_made", "rz_drives", "rz_tds", "rz_fg_drives", "punts")
_COUNT_SUFFIXES = ("_snaps", "_denom", "_opportunities", "_att", "_made", "_picks", "_total",
                   "_rostered", "_with_contract", "games")

#: The source tables, in join order. Week grain first; the season panel adds the two season-grain
#: tables on top of the weekly aggregate.
WEEK_SOURCES: tuple[tuple[str, str], ...] = (
    ("offense_team_week", "off"),
    ("defense_team_week", "def"),
    ("defense_coverage_week", "cov"),
)
SEASON_ONLY_SOURCES: tuple[str, ...] = ("st_team_season", "team_construction_season")

#: Which upstream column each panel metric's floor should be read from. A panel column inherits the
#: floor of the **participation column it is computed from**, which is the whole point of T49 —
#: ``man_share`` cannot be older than ``defense_man_zone_type``.
FLOOR_SOURCE: dict[str, tuple[str, str]] = {
    "man_share": ("participation", "defense_man_zone_type"),
    "man_zone_denom": ("participation", "defense_man_zone_type"),
    "charted_share": ("participation", "defense_coverage_type"),
    "proxy_safeties_mean": ("participation", "defense_positions"),
    "proxy_single_high_share": ("participation", "defense_positions"),
    "proxy_two_high_share": ("participation", "defense_positions"),
    "proxy_three_deep_share": ("participation", "defense_positions"),
    "pressure_rate": ("participation", "was_pressure"),
    "pressure_denom": ("participation", "was_pressure"),
    "blitz_rate": ("participation", "number_of_pass_rushers"),
    "big_blitz_rate": ("participation", "number_of_pass_rushers"),
    "rush3_rate": ("participation", "number_of_pass_rushers"),
    "rushers_mean": ("participation", "number_of_pass_rushers"),
    "box_mean": ("participation", "defenders_in_box"),
    "box_mean_vs_run": ("participation", "defenders_in_box"),
    "share_box_8plus": ("participation", "defenders_in_box"),
}

#: Panel columns sourced from FTN charting — 2022+, one DEV season, descriptive only.
FTN_COLUMNS: frozenset[str] = frozenset({
    "motion_rate", "play_action_rate", "rpo_rate", "screen_rate", "backfield_mean",
    "qb_shotgun_ftn_rate", "ftn_snaps",
})

#: Coverage-shell shares all inherit the charted-coverage floor.
_SHELL_PREFIX = "share_cover_"

#: ★ Columns that measure **our coverage of football**, not football. The distinction decides what
#: a pre-floor value is allowed to be, and it is the constructive half of the T50 lesson:
#:
#: * a column that measures football (``man_share``, ``share_cover_3``) must be **NULL** before its
#:   floor — a team that was never charted did not play zero man coverage;
#: * a column that measures coverage (``charted_share``, every ``*_denom``) is honestly **0** —
#:   "none of this team's snaps were charted in 2016" is a true statement, and nulling it would
#:   throw away the only column that says why the rates beside it are missing.
#:
#: Conflating the two made the floor bar fire on the four columns doing exactly the right thing.
COVERAGE_INDICATORS: frozenset[str] = frozenset({"charted_share"})


def measures_football(column: str) -> bool:
    """Must this column be NULL below its floor, rather than 0? See :data:`COVERAGE_INDICATORS`."""
    return is_metric(column) and column not in COVERAGE_INDICATORS


def is_metric(column: str) -> bool:
    """Is this a **rate-like** column that should be z-scored within season?

    Counts and keys are excluded: a z-scored snap count says a team ran more plays than the league
    that year, which is pace and game script, not scheme, and it would make the panel's headline
    columns disagree with what a reader means by "this team is unusual".
    """
    if column in _KEYS or column.endswith("_z"):
        return False
    if any(column.startswith(p) for p in _COUNT_PREFIXES):
        return False
    return not any(column.endswith(s) for s in _COUNT_SUFFIXES)


def _numeric_columns(con, table: str) -> list[str]:
    return con.execute(f"""
        select column_name from information_schema.columns
        where table_name = '{table}'
          and data_type in ('DOUBLE','FLOAT','BIGINT','INTEGER','HUGEINT','DECIMAL')
        order by ordinal_position
    """).df()["column_name"].tolist()


def build_team_scheme_week(con) -> dict:
    """One row per (season, week, team): offense, defense and coverage side by side.

    A full outer join would be wrong here and a left join from offense would be wrong too — a team
    has both an offense and a defense in every week it plays, so the two tables must cover the same
    team-weeks and an asymmetry is a defect worth surfacing rather than absorbing. The join is
    therefore from a **union of keys**, and 0.13.7's bar counts the rows that appear on only one
    side.
    """
    off_cols = [c for c in _numeric_columns(con, "offense_team_week") if c not in _KEYS]
    def_cols = [c for c in _numeric_columns(con, "defense_team_week") if c not in _KEYS]
    cov_cols = [c for c in _numeric_columns(con, "defense_coverage_week")
                if c not in _KEYS and c not in def_cols]
    # ⚠ the coverage table's bare `snaps` is its own denominator and must survive the join — it is
    # what every proxy_* and charted_share share is weighted by when the season panel aggregates.
    # Dropping it as "ambiguous" removed the denominator and left the rates unweightable.
    sel = (", ".join(f"o.{c} as off_{c}" for c in off_cols) + ", "
           + ", ".join(f"d.{c}" for c in def_cols) + ", "
           + ", ".join(f"c.{c} as cov_{c}" if c == "snaps" else f"c.{c}" for c in cov_cols))
    con.execute(f"""
        create or replace table {WEEK_TABLE} as
        with keys as (
            select season, week, team from offense_team_week
            union
            select season, week, team from defense_team_week
        )
        select k.season, k.week, k.team,
               (o.season is not null) as has_offense,
               (d.season is not null) as has_defense,
               c.safety_provenance,
               {sel},
               current_localtimestamp() as pulled_at
        from keys k
        left join offense_team_week    o using (season, week, team)
        left join defense_team_week    d using (season, week, team)
        left join defense_coverage_week c using (season, week, team)
    """)
    n, teams, seasons = con.execute(
        f"select count(*), count(distinct team), count(distinct season) from {WEEK_TABLE}"
    ).fetchone()
    ncols = len(_numeric_columns(con, WEEK_TABLE))
    return {"table": WEEK_TABLE, "n_rows": int(n), "n_teams": int(teams),
            "n_seasons": int(seasons), "n_metric_columns": ncols}


def build_team_scheme_season(con) -> dict:
    """One row per (season, team): the weekly panel aggregated, plus the season-grain tables.

    ⚠ **Rates are re-derived from their own denominators, never averaged over weeks.** A team's
    season blitz rate is total blitzes over total dropbacks, not the mean of seventeen weekly
    rates — those differ whenever the weekly denominators differ, which they always do, and the
    mean-of-ratios is the wrong one. Where a stored rate has a stored denominator the pair is
    re-multiplied; where it does not, the aggregate is snap-weighted and the column is named so.
    """
    con.execute(f"""
        create or replace table {SEASON_TABLE} as
        with weekly as (
            select season, team,
                   count(*)                            as weeks,
                   sum(off_off_snaps)                  as off_snaps,
                   sum(def_snaps)                      as def_snaps,
                   sum(off_dropbacks)                  as off_dropbacks,
                   sum(dropbacks)                      as def_dropbacks,
                   -- ★ ratio of sums, not mean of ratios: reconstruct each numerator from its own
                   -- stored denominator before dividing.
                   sum(blitz_rate     * rushers_denom)  / nullif(sum(rushers_denom), 0)
                                                                            as blitz_rate,
                   sum(big_blitz_rate * rushers_denom)  / nullif(sum(rushers_denom), 0)
                                                                            as big_blitz_rate,
                   sum(rush3_rate     * rushers_denom)  / nullif(sum(rushers_denom), 0)
                                                                            as rush3_rate,
                   sum(rushers_mean   * rushers_denom)  / nullif(sum(rushers_denom), 0)
                                                                            as rushers_mean,
                   sum(rushers_denom)                                       as rushers_denom,
                   sum(man_share      * man_zone_denom) / nullif(sum(man_zone_denom), 0)
                                                                            as man_share,
                   sum(man_zone_denom)                                      as man_zone_denom,
                   sum(pressure_rate  * pressure_denom) / nullif(sum(pressure_denom), 0)
                                                                            as pressure_rate,
                   sum(pressure_denom)                                      as pressure_denom,
                   sum(charted_share  * cov_snaps)      / nullif(sum(cov_snaps), 0)
                                                                            as charted_share,
                   sum(charted_snaps)                                       as charted_snaps,
                   -- snap-weighted for the rest: the denominator IS the snap count
                   {", ".join(f'''sum({c} * def_snaps) / nullif(sum(def_snaps), 0) as {c}'''
                              for c in ("dl_mean", "lb_mean", "db_mean", "share_base",
                                        "share_nickel", "share_dime", "share_quarter",
                                        "share_heavy_box", "box_mean", "share_box_8plus"))},
                   {", ".join(f'''sum(share_cover_{s} * charted_snaps)
                        / nullif(sum(charted_snaps), 0) as share_cover_{s}'''
                              for s in ("0", "1", "2", "3", "4", "6", "9"))},
                   sum(share_2_man * charted_snaps) / nullif(sum(charted_snaps), 0) as share_2_man,
                   sum(proxy_safeties_mean * cov_snaps) / nullif(sum(cov_snaps), 0)
                                                                        as proxy_safeties_mean,
                   sum(proxy_single_high_share * cov_snaps) / nullif(sum(cov_snaps), 0)
                                                                        as proxy_single_high_share,
                   sum(proxy_two_high_share * cov_snaps) / nullif(sum(cov_snaps), 0)
                                                                        as proxy_two_high_share,
                   {", ".join(f'''sum(off_{c} * off_off_snaps) / nullif(sum(off_off_snaps), 0)
                        as {c}'''
                              for c in ("pass_rate", "pass_rate_neutral", "pass_oe_mean",
                                        "xpass_mean", "share_shotgun", "share_singleback",
                                        "share_under_center", "share_i_form", "share_empty",
                                        "share_pistol", "share_p11", "share_p12", "share_p21",
                                        "share_p13", "share_p22", "share_p10", "share_p_other",
                                        "rb_mean", "te_mean", "wr_mean", "no_huddle_rate",
                                        "shotgun_rate", "epa_per_play"))},
                   -- FTN columns weight on the FTN-charted snaps, not on all snaps: weighting a
                   -- 2022+ column by a 2016+ denominator would dilute it with never-charted plays.
                   {", ".join(f'''sum(off_{c} * off_ftn_snaps) / nullif(sum(off_ftn_snaps), 0)
                        as {c}'''
                              for c in ("motion_rate", "play_action_rate", "rpo_rate",
                                        "screen_rate", "backfield_mean"))},
                   sum(off_ftn_snaps)                                       as ftn_snaps,
                   sum(off_rz_snaps)                                        as rz_snaps
            from {WEEK_TABLE}
            group by 1, 2
        )
        select w.*,
               {", ".join(f"s.{c}" for c in
                          ("head_coach", "games", "fourth_opportunities", "fourth_go_rate",
                           "two_point_rate", "fg_pct", "fg_pct_long", "fg_dist_mean",
                           "punt_dist_mean", "rz_stall_rate"))},
               {", ".join(f"tc.{c}" for c in
                          ("n_rostered", "contract_coverage", "cap_accounted_pct",
                           "cap_share_qb", "cap_share_rb", "cap_share_wr", "cap_share_te",
                           "cap_share_ol", "cap_share_dl", "cap_share_lb", "cap_share_db",
                           "cap_share_st", "cap_share_offense", "cap_share_defense",
                           "age_qb", "age_rb", "age_wr", "age_te", "age_ol", "age_dl",
                           "age_lb", "age_db", "years_exp_mean", "draft_capital",
                           "draft_capital_offense", "draft_capital_defense", "n_picks_r1",
                           "continuity_offense", "continuity_defense"))},
               current_localtimestamp() as pulled_at
        from weekly w
        left join st_team_season s          on s.season = w.season and s.team = w.team
        left join team_construction_season tc
                                            on tc.season = w.season and tc.team = w.team
    """)
    n, teams, seasons = con.execute(
        f"select count(*), count(distinct team), count(distinct season) from {SEASON_TABLE}"
    ).fetchone()
    ncols = len(_numeric_columns(con, SEASON_TABLE))
    return {"table": SEASON_TABLE, "n_rows": int(n), "n_teams": int(teams),
            "n_seasons": int(seasons), "n_metric_columns": ncols}


def zscore_within_season(con, source: str, target: str) -> dict:
    """Materialize the within-season z-score of every metric column.

    ⚠ **A season with no signal must not produce a z-score.** Where a column is entirely null
    before its floor, ``stddev`` is null and the z is null — which is correct and is why the
    division is guarded rather than coalesced to zero. A z of 0.0 means *exactly league average*;
    filling an absent measurement with it would put every 2017 team at the league mean for man
    coverage, which is the single most misleading thing this panel could do.
    """
    metrics = [c for c in _numeric_columns(con, source) if is_metric(c)]
    keys = [c for c in ("season", "week", "team") if c in
            con.execute(f"""select column_name from information_schema.columns
                            where table_name = '{source}'""").df()["column_name"].tolist()]
    zs = ",\n            ".join(
        f"""case when stddev_samp({c}) over w > 0
                 then ({c} - avg({c}) over w) / stddev_samp({c}) over w end as {c}_z"""
        for c in metrics
    )
    con.execute(f"""
        create or replace table {target} as
        select {", ".join(keys)}, {", ".join(metrics)},
            {zs}
        from {source}
        window w as (partition by season)
    """)
    n = con.execute(f"select count(*) from {target}").fetchone()[0]
    return {"table": target, "n_rows": int(n), "n_metrics_zscored": len(metrics)}


def build_column_register(con, bm: BreakMap, tables=(SEASON_TABLE, WEEK_TABLE)) -> pd.DataFrame:
    """★ One row per (table, column): PIT class, per-column floor, break provenance, fill.

    This is the artefact that makes the panel readable by someone who was not here. T49 said floors
    are a property of the column; this is where that stops being a claim about the register and
    becomes a row a query can join to.
    """
    rows: list[dict] = []
    for table in tables:
        grain = "team-season" if table == SEASON_TABLE else "team-week"
        for col in _numeric_columns(con, table):
            src_table, src_col = FLOOR_SOURCE.get(col, (None, None))
            if col.startswith(_SHELL_PREFIX) or col == "share_2_man":
                src_table, src_col = "participation", "defense_coverage_type"
            floor = bm.floor(src_table, src_col) if src_table else None
            broke = [b for b in bm.breaks
                     if src_table and b.table == src_table and b.column == src_col]
            observed = con.execute(f"""
                select min(season) filter (where {col} is not null),
                       max(season) filter (where {col} is not null),
                       count({col}), count(*)
                from {table}""").fetchone()
            rows.append({
                "table": table,
                "column": col,
                "grain": grain,
                "is_metric": is_metric(col),
                "measures_football": measures_football(col),
                "pit_class": "in_season_weekly",
                "backtestable": col not in FTN_COLUMNS,
                "source_table": src_table,
                "source_column": src_col,
                "declared_floor": floor,
                "observed_first_season": observed[0],
                "observed_last_season": observed[1],
                "fill_rate": round(observed[2] / observed[3], 4) if observed[3] else None,
                "break_kinds": ";".join(sorted({b.kind for b in broke})) or None,
            })
    out = pd.DataFrame(rows)
    con.execute(f"create or replace table {COLUMN_REGISTER} as select * from out")
    return out


def assert_column_floor(column: str, season: int, bm: BreakMap) -> None:
    """★ B6 for the panel: asking a panel column for a season below **its own** floor raises.

    The floor named in the error is the column's, not its table's — which is the entire content of
    T49. ``participation``'s floor is 2016 and ``man_share``'s is 2018, and a query written against
    the table's floor gets two empty seasons that look like two quiet ones.
    """
    src = FLOOR_SOURCE.get(column)
    if column.startswith(_SHELL_PREFIX) or column == "share_2_man":
        src = ("participation", "defense_coverage_type")
    if column in FTN_COLUMNS:
        if season < 2022:
            raise ValueError(
                f"{column} is FTN-charted: floor 2022, requested {season}. Per-column floor (T49)."
            )
        return
    if src is None:
        return
    floor = bm.floor(*src)
    if floor is not None and season < floor:
        raise ValueError(
            f"{column} derives from {src[0]}.{src[1]}, whose floor is {floor}; requested {season}. "
            f"The TABLE's floor is older — this is a per-column floor (T49), and a query written "
            f"against the table's floor gets empty seasons that look like quiet ones."
        )
