"""Phase 3.1 — opportunity / volume features (the dominant fantasy predictors).

One row per **(gsis_id, season)** for skill players (QB/RB/WR/TE): the realized *opportunity* a
player earned that season — target/carry share, snap rate, weighted opportunity (WOPR), air-yards
share, aDOT, and red-zone volume. These are **descriptive season facts**; the point-in-time *lag*
(use season S-1 to project S) is applied by the exposure assembly in :mod:`features.exposures`, not
here — so each module stays a clean, testable "what happened in season S".

Sources: ``weekly`` (targets/carries/shares/WOPR), ``snaps`` (offense %), ``pbp`` (red zone).
Traded players collapse to one (gsis, season) row (counts summed; primary team = most games).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SKILL = ("QB", "RB", "WR", "TE")

# the columns this module contributes to the exposure matrix (the manifest downstream reads).
FEATURE_COLS = [
    "snap_pct", "tgt_share", "air_yards_share", "wopr", "racr", "adot",
    "targets_pg", "receptions_pg", "carries_pg", "carry_share", "touches_pg",
    "rz_tgt_pg", "rz_carry_pg",
]
_COUNTING = ["games", "targets", "receptions", "carries", "rush_att",
             "rec_air_yards", "rz_targets", "rz_carries"]


def opportunity_features(con, seasons=None) -> pd.DataFrame:
    """Realized per-(gsis_id, season) opportunity features for skill players.

    Returns identity (gsis_id, season, position, team, games) + :data:`FEATURE_COLS`. Per-game
    rates guard against divide-by-zero; all feature columns are finite.
    """
    where_season = ""
    if seasons is not None:
        yrs = ", ".join(str(int(s)) for s in seasons)
        where_season = f"AND w.season IN ({yrs})"

    sql = f"""
    WITH wk AS (
        SELECT gsis_id, season,
               COUNT(*) AS games,
               SUM(targets) AS targets, SUM(receptions) AS receptions,
               SUM(carries) AS carries, SUM(attempts) AS rush_att,
               SUM(receiving_air_yards) AS rec_air_yards,
               AVG(target_share) AS tgt_share, AVG(air_yards_share) AS air_yards_share,
               AVG(wopr) AS wopr, AVG(racr) AS racr
        FROM weekly w
        WHERE season_type='REG' AND position IN ('QB','RB','WR','TE') AND gsis_id IS NOT NULL
              {where_season}
        GROUP BY gsis_id, season
    ),
    -- primary team + position = the one with the most games that season (traded players)
    prim AS (
        SELECT gsis_id, season, recent_team AS team, position
        FROM (
            SELECT gsis_id, season, recent_team, position, COUNT(*) AS g,
                   ROW_NUMBER() OVER (PARTITION BY gsis_id, season ORDER BY COUNT(*) DESC) AS rn
            FROM weekly
            WHERE season_type='REG' AND position IN ('QB','RB','WR','TE') AND gsis_id IS NOT NULL
            GROUP BY gsis_id, season, recent_team, position
        ) WHERE rn=1
    ),
    -- team-week carries -> a trade-robust weekly carry share, averaged over the player's games
    tw AS (
        SELECT recent_team AS team, season, week, SUM(carries) AS team_carries
        FROM weekly WHERE season_type='REG' GROUP BY recent_team, season, week
    ),
    csh AS (
        SELECT w.gsis_id, w.season,
               AVG(CASE WHEN tw.team_carries > 0 THEN w.carries / tw.team_carries END)
                   AS carry_share
        FROM weekly w
        JOIN tw ON tw.team=w.recent_team AND tw.season=w.season AND tw.week=w.week
        WHERE w.season_type='REG' AND w.position IN ('QB','RB','WR','TE') AND w.gsis_id IS NOT NULL
        GROUP BY w.gsis_id, w.season
    ),
    snp AS (
        SELECT gsis_id, season, AVG(offense_pct) AS snap_pct
        FROM snaps WHERE game_type='REG' AND gsis_id IS NOT NULL
        GROUP BY gsis_id, season
    ),
    rz AS (
        SELECT gsis_id, season, SUM(rz_tgt) AS rz_targets, SUM(rz_car) AS rz_carries FROM (
            SELECT receiver_player_id AS gsis_id, season, 1 AS rz_tgt, 0 AS rz_car
            FROM pbp WHERE season_type='REG' AND yardline_100 <= 20
                     AND receiver_player_id IS NOT NULL
            UNION ALL
            SELECT rusher_player_id AS gsis_id, season, 0 AS rz_tgt, 1 AS rz_car
            FROM pbp WHERE season_type='REG' AND yardline_100 <= 20 AND rusher_player_id IS NOT NULL
        ) GROUP BY gsis_id, season
    )
    SELECT p.gsis_id, wk.season, p.position, p.team, wk.games,
           wk.targets, wk.receptions, wk.carries, wk.rush_att, wk.rec_air_yards,
           wk.tgt_share, wk.air_yards_share, wk.wopr, wk.racr,
           snp.snap_pct, csh.carry_share,
           COALESCE(rz.rz_targets, 0) AS rz_targets, COALESCE(rz.rz_carries, 0) AS rz_carries
    FROM wk
    JOIN prim p ON p.gsis_id=wk.gsis_id AND p.season=wk.season
    LEFT JOIN snp ON snp.gsis_id=wk.gsis_id AND snp.season=wk.season
    LEFT JOIN csh ON csh.gsis_id=wk.gsis_id AND csh.season=wk.season
    LEFT JOIN rz  ON rz.gsis_id=wk.gsis_id  AND rz.season=wk.season
    """
    df = con.execute(sql).df()
    return _finalize(df)


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Per-game rates + aDOT; NaN opportunity shares -> 0 (no opportunity), then assert finite."""
    g = df["games"].clip(lower=1)
    df["targets_pg"] = df["targets"] / g
    df["receptions_pg"] = df["receptions"] / g
    df["carries_pg"] = df["carries"] / g
    df["touches_pg"] = (df["carries"] + df["receptions"]) / g
    df["rz_tgt_pg"] = df["rz_targets"] / g
    df["rz_carry_pg"] = df["rz_carries"] / g
    # aDOT: extreme values come from tiny samples (1-2 targets, one deep bomb) -> clip to a
    # plausible band so they don't distort the cross-sectional z-scoring in 3.5.
    adot = np.where(df["targets"] > 0, df["rec_air_yards"] / df["targets"].clip(lower=1), 0.0)
    df["adot"] = np.clip(adot, -10.0, 30.0)
    # opportunity shares/rates default to 0 where a player simply had none.
    for c in ("snap_pct", "tgt_share", "air_yards_share", "wopr", "racr", "carry_share"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    out = df[["gsis_id", "season", "position", "team", *_COUNTING, *FEATURE_COLS]].copy()
    assert np.isfinite(out[FEATURE_COLS].to_numpy(dtype=float)).all(), "non-finite opp feature"
    return out
