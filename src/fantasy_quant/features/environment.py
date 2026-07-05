"""Phase 3.4 — team / environment features (systematic, shared across teammates).

One row per **(team, season)**: the offensive *context* a player sits in — pass tendency, early-down
pass rate (a PROE proxy), pace, scoring, pass/rush efficiency (EPA), the Vegas **implied total**,
and **target concentration** (teammate competition). In the exposure assembly these attach to each
player via their team, so pass-catchers in a pass-heavy, high-total offense get the lift.

Sources: ``pbp`` (tendencies + EPA), ``game_lines`` (points + implied team total, 0.5), ``weekly``
(target Herfindahl). Descriptive season facts; the PIT lag is applied in :mod:`features.exposures`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_COLS = [
    "pass_rate", "early_down_pass_rate", "plays_pg", "points_pg",
    "pass_epa", "rush_epa", "implied_team_total", "tgt_hhi",
]


def environment_features(con, seasons=None) -> pd.DataFrame:
    """Realized per-(team, season) offensive-environment features (see :data:`FEATURE_COLS`)."""
    where_season = ""
    if seasons is not None:
        yrs = ", ".join(str(int(s)) for s in seasons)
        where_season = f"AND season IN ({yrs})"

    sql = f"""
    WITH off AS (  -- pbp offensive tendencies + efficiency, per (team, season)
        SELECT posteam AS team, season,
               SUM(CASE WHEN pass=1 THEN 1 ELSE 0 END) AS pass_plays,
               SUM(CASE WHEN rush=1 THEN 1 ELSE 0 END) AS rush_plays,
               SUM(CASE WHEN pass=1 AND down IN (1,2) THEN 1 ELSE 0 END) AS ed_pass,
               SUM(CASE WHEN (pass=1 OR rush=1) AND down IN (1,2) THEN 1 ELSE 0 END) AS ed_plays,
               AVG(CASE WHEN pass=1 THEN qb_epa END) AS pass_epa,
               AVG(CASE WHEN rush=1 THEN epa END) AS rush_epa,
               COUNT(DISTINCT week) AS games
        FROM pbp
        WHERE season_type='REG' AND posteam IS NOT NULL AND (pass=1 OR rush=1) {where_season}
        GROUP BY posteam, season
    ),
    pts AS (  -- team points scored + Vegas implied team total, per (team, season)
        -- normalize relocated-franchise era codes to pbp's modern codes so the join matches
        -- (game_lines uses STL/SD/OAK pre-move; pbp uses LA/LAC/LV throughout).
        SELECT CASE team WHEN 'STL' THEN 'LA' WHEN 'SD' THEN 'LAC' WHEN 'OAK' THEN 'LV'
                         WHEN 'JAC' THEN 'JAX' ELSE team END AS team,
               season, AVG(points) AS points_pg, AVG(implied_total) AS implied_team_total FROM (
            SELECT home_team AS team, season, home_score AS points,
                   home_implied_total AS implied_total
            FROM game_lines WHERE game_type='REG'
            UNION ALL
            SELECT away_team AS team, season, away_score AS points,
                   away_implied_total AS implied_total
            FROM game_lines WHERE game_type='REG'
        ) t GROUP BY 1, season
    ),
    hhi AS (  -- target concentration (teammate competition): sum of squared team target shares
        SELECT team, season, SUM(share*share) AS tgt_hhi FROM (
            SELECT recent_team AS team, season, gsis_id,
                   SUM(targets)*1.0 / NULLIF(
                       SUM(SUM(targets)) OVER (PARTITION BY recent_team, season), 0) AS share
            FROM weekly WHERE season_type='REG' AND gsis_id IS NOT NULL {where_season}
            GROUP BY recent_team, season, gsis_id
        ) s GROUP BY team, season
    )
    SELECT off.team, off.season, off.pass_plays, off.rush_plays, off.games,
           off.pass_epa, off.rush_epa, off.ed_pass, off.ed_plays,
           pts.points_pg, pts.implied_team_total, hhi.tgt_hhi
    FROM off
    LEFT JOIN pts ON pts.team=off.team AND pts.season=off.season
    LEFT JOIN hhi ON hhi.team=off.team AND hhi.season=off.season
    """
    return _finalize(con.execute(sql).df())


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Rates + finiteness; team totals default sanely; assert finite."""
    total = (df["pass_plays"] + df["rush_plays"]).clip(lower=1)
    df["pass_rate"] = df["pass_plays"] / total
    df["early_down_pass_rate"] = np.where(
        df["ed_plays"] > 0, df["ed_pass"] / df["ed_plays"].clip(lower=1), df["pass_rate"])
    df["plays_pg"] = total / df["games"].clip(lower=1)
    for c in ("pass_epa", "rush_epa", "points_pg", "implied_team_total", "tgt_hhi"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # implied_team_total can be missing for older seasons' lines -> fall back to points_pg proxy.
    df["implied_team_total"] = df["implied_team_total"].fillna(df["points_pg"])
    df[["pass_epa", "rush_epa"]] = df[["pass_epa", "rush_epa"]].fillna(0.0)
    # season-median safety fill for any residual gap (e.g., a franchise code we didn't normalize).
    for c in ("points_pg", "implied_team_total", "tgt_hhi"):
        df[c] = df[c].fillna(df.groupby("season")[c].transform("median")).fillna(df[c].median())

    out = df[["team", "season", "games", *FEATURE_COLS]].copy()
    assert np.isfinite(out[FEATURE_COLS].to_numpy(dtype=float)).all(), "non-finite env feature"
    return out
