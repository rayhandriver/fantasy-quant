"""Phase 0.7 — the PIT panel / feature-store assembly (the unified join layer).

Everything downstream reads from here. Two grains:
  - :func:`weekly_panel` — ``(gsis_id, season, week)`` for variance / in-season work.
  - :func:`preseason_panel` — ``(gsis_id)`` draftable universe for draft projections.

**The PIT contract (the whole point):** a source contributes a row only if its *known-at* time
is ``<= as_of``. Weekly-grain data (stats/snaps/NGS) is known at that week's **last gameday**
(from ``game_lines``); ADP at its ``snapshot_date``; injuries at ``date_modified``; game context at
kickoff. :func:`assert_panel_pit` enforces that no field dated after ``as_of`` survives — a planted
future value trips it (the intern-repo Step 1.1 discipline).
"""

from __future__ import annotations

import pandas as pd

from fantasy_quant.config import PROCESSED_DIR

# league-baseline ADP config the panel anchors on (10-team full-PPR).
_ADP_SRC, _ADP_SCORING, _ADP_TEAMS = "ffc", "ppr", 10


# --------------------------------------------------------------------------------------------
# the PIT guard (pure, unit-tested)
# --------------------------------------------------------------------------------------------
def assert_panel_pit(df: pd.DataFrame, as_of, date_cols) -> bool:
    """Assert no ``date_cols`` value in ``df`` is dated after ``as_of`` (tz-naive comparison)."""
    as_of_ts = pd.Timestamp(pd.to_datetime(as_of)).tz_localize(None)
    violations = {}
    for c in date_cols:
        if c not in df.columns:
            continue
        s = pd.to_datetime(df[c], errors="coerce")
        if getattr(s.dtype, "tz", None) is not None:
            s = s.dt.tz_localize(None)
        mx = s.max()
        if pd.notna(mx) and mx > as_of_ts:
            violations[c] = str(mx)
    assert not violations, f"PIT leak in panel as_of {as_of_ts.date()}: {violations}"
    return True


# --------------------------------------------------------------------------------------------
# shared SQL fragments
# --------------------------------------------------------------------------------------------
def _week_end_cte() -> str:
    return (
        "week_end AS (SELECT season, week, MAX(CAST(gameday AS DATE)) AS week_end_date "
        "FROM game_lines WHERE game_type='REG' GROUP BY season, week)"
    )


def _team_week_cte() -> str:
    return """team_week AS (
        SELECT season, week, home_team AS team, away_team AS opp, TRUE AS is_home,
               total_line, spread_line AS team_spread,
               home_implied_total AS team_implied_total, home_fair_winprob AS team_winprob
        FROM game_lines WHERE game_type='REG'
        UNION ALL
        SELECT season, week, away_team AS team, home_team AS opp, FALSE AS is_home,
               total_line, -spread_line AS team_spread,
               away_implied_total AS team_implied_total, away_fair_winprob AS team_winprob
        FROM game_lines WHERE game_type='REG'
    )"""


def _board_cte(season: int, aod: str, extra_cols: str = "") -> str:
    return f"""board AS (
        SELECT gsis_id, adp, pos_rank AS adp_pos_rank,
               snapshot_date AS adp_snapshot_date{extra_cols}
        FROM adp_snapshots
        WHERE season={season} AND source='{_ADP_SRC}' AND scoring='{_ADP_SCORING}'
          AND teams={_ADP_TEAMS} AND snapshot_date <= DATE '{aod}'
        QUALIFY snapshot_date = MAX(snapshot_date) OVER ()
    )"""


# --------------------------------------------------------------------------------------------
# weekly grain
# --------------------------------------------------------------------------------------------
def weekly_panel(con, season: int, as_of, materialize: bool = False) -> pd.DataFrame:
    """PIT ``(gsis_id, season, week)`` panel: weekly stats + snaps + NGS + odds + ADP + injuries,
    restricted to weeks whose games finished on or before ``as_of``."""
    season = int(season)
    aod = pd.to_datetime(as_of).date().isoformat()
    sql = f"""
    WITH {_week_end_cte()},
    {_team_week_cte()},
    ngs_rec AS (
        SELECT gsis_id, season, week, avg_separation AS ngs_avg_separation,
               avg_cushion AS ngs_avg_cushion, avg_yac_above_expectation AS ngs_yac_oe
        FROM ngs WHERE stat_type='receiving'
    ),
    inj AS (
        SELECT gsis_id, season, week, report_status, report_primary_injury, practice_status,
               date_modified,
               ROW_NUMBER() OVER (PARTITION BY gsis_id, season, week
                                  ORDER BY date_modified DESC NULLS LAST) AS rn
        FROM injuries WHERE CAST(date_modified AS DATE) <= DATE '{aod}'
    ),
    {_board_cte(season, aod)}
    SELECT
        w.gsis_id, w.season, w.week, we.week_end_date,
        w.player_display_name AS player_name, w.position, w.recent_team AS team,
        w.fantasy_points, w.fantasy_points_ppr,
        w.targets, w.receptions, w.receiving_yards, w.receiving_tds,
        w.carries, w.rushing_yards, w.rushing_tds,
        w.attempts, w.passing_yards, w.passing_tds, w.interceptions,
        w.target_share, w.air_yards_share,
        s.offense_snaps, s.offense_pct,
        n.ngs_avg_separation, n.ngs_avg_cushion, n.ngs_yac_oe,
        tw.opp, tw.is_home, tw.total_line, tw.team_spread,
        tw.team_implied_total, tw.team_winprob,
        b.adp, b.adp_pos_rank, b.adp_snapshot_date,
        i.report_status, i.report_primary_injury, i.practice_status,
        i.date_modified AS injury_date_modified,
        DATE '{aod}' AS as_of
    FROM weekly w
    JOIN week_end we ON we.season=w.season AND we.week=w.week
    LEFT JOIN snaps s ON s.gsis_id=w.gsis_id AND s.season=w.season AND s.week=w.week
                         AND s.game_type='REG'
    LEFT JOIN ngs_rec n ON n.gsis_id=w.gsis_id AND n.season=w.season AND n.week=w.week
    LEFT JOIN team_week tw ON tw.season=w.season AND tw.week=w.week AND tw.team=w.recent_team
    LEFT JOIN board b ON b.gsis_id=w.gsis_id
    LEFT JOIN inj i ON i.gsis_id=w.gsis_id AND i.season=w.season AND i.week=w.week AND i.rn=1
    WHERE w.season={season} AND w.season_type='REG' AND we.week_end_date <= DATE '{aod}'
    ORDER BY w.week, w.gsis_id
    """
    df = con.execute(sql).df()
    assert_panel_pit(df, aod, ["week_end_date", "adp_snapshot_date", "injury_date_modified"])
    if materialize:
        _materialize(df, "weekly", season, aod)
    return df


# --------------------------------------------------------------------------------------------
# preseason grain
# --------------------------------------------------------------------------------------------
def preseason_panel(con, season: int, as_of, materialize: bool = False) -> pd.DataFrame:
    """PIT draftable-universe panel: the ADP board as-of ``as_of`` + player identity/age +
    latest injury status known as-of. No season-``S`` on-field data (it doesn't exist yet)."""
    season = int(season)
    aod = pd.to_datetime(as_of).date().isoformat()
    extra = ", name AS adp_name, position AS adp_position, team AS adp_team"
    sql = f"""
    WITH {_board_cte(season, aod, extra)},
    inj AS (
        SELECT gsis_id, report_status, report_primary_injury, practice_status, date_modified,
               ROW_NUMBER() OVER (PARTITION BY gsis_id ORDER BY date_modified DESC) AS rn
        FROM injuries WHERE CAST(date_modified AS DATE) <= DATE '{aod}'
    ),
    pid AS (
        SELECT gsis_id, name AS player_name, position, team, birthdate,
               draft_year, draft_round, draft_pick
        FROM player_ids
    )
    SELECT
        b.gsis_id, {season} AS season,
        COALESCE(p.player_name, b.adp_name) AS player_name,
        COALESCE(p.position, b.adp_position) AS position,
        COALESCE(p.team, b.adp_team) AS team,
        b.adp, b.adp_pos_rank, b.adp_snapshot_date,
        TRY_CAST(p.birthdate AS DATE) AS birthdate,
        date_diff('year', TRY_CAST(p.birthdate AS DATE), DATE '{aod}') AS age_years,
        p.draft_year, p.draft_round, p.draft_pick,
        i.report_status, i.report_primary_injury, i.practice_status,
        i.date_modified AS injury_date_modified,
        DATE '{aod}' AS as_of
    FROM board b
    LEFT JOIN pid p ON p.gsis_id=b.gsis_id
    LEFT JOIN inj i ON i.gsis_id=b.gsis_id AND i.rn=1
    WHERE b.gsis_id IS NOT NULL
    ORDER BY b.adp
    """
    df = con.execute(sql).df()
    assert_panel_pit(df, aod, ["adp_snapshot_date", "injury_date_modified"])
    if materialize:
        _materialize(df, "preseason", season, aod)
    return df


def build_panel(con, as_of, grain: str = "weekly", season: int | None = None,
                materialize: bool = False) -> pd.DataFrame:
    """Dispatch to :func:`weekly_panel` / :func:`preseason_panel`."""
    if season is None:
        raise ValueError("season is required")
    if grain == "weekly":
        return weekly_panel(con, season, as_of, materialize=materialize)
    if grain in ("preseason", "season"):
        return preseason_panel(con, season, as_of, materialize=materialize)
    raise ValueError(f"unknown grain: {grain!r}")


def _materialize(df: pd.DataFrame, grain: str, season: int, aod: str) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / f"panel_{grain}_{season}_{aod}.parquet"
    df.to_parquet(path, index=False)
