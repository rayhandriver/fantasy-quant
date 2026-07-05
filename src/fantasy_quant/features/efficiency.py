"""Phase 3.2 — efficiency features (partly skill, partly mean-reverting).

One row per **(gsis_id, season)** for skill players: how *well* a player converted opportunity —
catch rate, yards per target/reception/carry, YAC, and TD rate — plus a **TD-regression flag**
(realized TDs minus opportunity-expected TDs) flagging unsustainable TD luck. QB rows carry EPA/play
and CPOE. Efficiency is treated as partly mean-reverting (used differently from opportunity).

Sources: ``weekly`` (yardage/TDs/YAC/EPA), ``pbp`` (red-zone opportunity for the TD baseline, QB
EPA/CPOE). Descriptive season facts; the PIT lag is applied in :mod:`features.exposures`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# league-average TD conversion rates per red-zone opportunity — the regression baseline. Estimated
# from data (see steps/phase3_2_efficiency.py); refined values are documented, not magic.
RZ_TD_RATE = {"rec": 0.20, "rush": 0.12}

FEATURE_COLS = [
    "catch_rate", "ypr", "yptgt", "ypc", "yac_per_rec",
    "rec_td_rate", "rush_td_rate", "td_oe", "td_regression_flag",
    "qb_epa_per_play", "qb_cpoe",
]
_RAW = ["rec_tds", "rush_tds", "exp_tds", "rz_targets", "rz_carries"]


def efficiency_features(con, seasons=None) -> pd.DataFrame:
    """Realized per-(gsis_id, season) efficiency features for skill players (FEATURE_COLS)."""
    where_season = ""
    if seasons is not None:
        yrs = ", ".join(str(int(s)) for s in seasons)
        where_season = f"AND w.season IN ({yrs})"

    sql = f"""
    WITH wk AS (
        SELECT gsis_id, season, COUNT(*) AS games,
               SUM(targets) AS targets, SUM(receptions) AS receptions,
               SUM(receiving_yards) AS rec_yds, SUM(receiving_yards_after_catch) AS yac,
               SUM(receiving_tds) AS rec_tds,
               SUM(carries) AS carries, SUM(rushing_yards) AS rush_yds,
               SUM(rushing_tds) AS rush_tds,
               SUM(attempts) AS pass_att, AVG(passing_epa) AS pass_epa_wk
        FROM weekly w
        WHERE season_type='REG' AND position IN ('QB','RB','WR','TE') AND gsis_id IS NOT NULL
              {where_season}
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
    ),
    qb AS (  -- QB EPA/play + CPOE from pbp dropbacks; require >=100 to exclude trick-play throwers
        SELECT passer_player_id AS gsis_id, season,
               AVG(qb_epa) AS qb_epa_per_play, AVG(cpoe) AS qb_cpoe
        FROM pbp
        WHERE season_type='REG' AND passer_player_id IS NOT NULL AND pass=1
        GROUP BY passer_player_id, season
        HAVING COUNT(*) >= 100
    )
    SELECT wk.gsis_id, wk.season, wk.games,
           wk.targets, wk.receptions, wk.rec_yds, wk.yac, wk.rec_tds,
           wk.carries, wk.rush_yds, wk.rush_tds,
           COALESCE(rz.rz_targets, 0) AS rz_targets, COALESCE(rz.rz_carries, 0) AS rz_carries,
           qb.qb_epa_per_play, qb.qb_cpoe
    FROM wk
    LEFT JOIN rz ON rz.gsis_id=wk.gsis_id AND rz.season=wk.season
    LEFT JOIN qb ON qb.gsis_id=wk.gsis_id AND qb.season=wk.season
    """
    return _finalize(con.execute(sql).df())


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Rate features + the opportunity-expected-TD regression flag; NaN eff -> 0; assert finite."""
    tgt = df["targets"].clip(lower=1)
    rec = df["receptions"].clip(lower=1)
    car = df["carries"].clip(lower=1)
    # rate features: clip to plausible physical bands — tiny-sample extremes (1 carry for 30 yds)
    # would otherwise dominate the cross-sectional z-scoring in 3.5. Real p1..p99 sit well inside.
    df["catch_rate"] = np.clip(np.where(df["targets"] > 0, df["receptions"] / tgt, 0.0), 0.0, 1.2)
    df["ypr"] = np.clip(np.where(df["receptions"] > 0, df["rec_yds"] / rec, 0.0), 0.0, 30.0)
    df["yptgt"] = np.clip(np.where(df["targets"] > 0, df["rec_yds"] / tgt, 0.0), 0.0, 25.0)
    df["ypc"] = np.clip(np.where(df["carries"] > 0, df["rush_yds"] / car, 0.0), -10.0, 15.0)
    df["yac_per_rec"] = np.clip(np.where(df["receptions"] > 0, df["yac"] / rec, 0.0), -5.0, 25.0)
    df["rec_td_rate"] = np.where(df["receptions"] > 0, df["rec_tds"] / rec, 0.0)
    df["rush_td_rate"] = np.where(df["carries"] > 0, df["rush_tds"] / car, 0.0)

    # TD-regression: expected TDs from red-zone opportunity; td_oe = actual - expected (positive =
    # got lucky, likely to regress DOWN next year). Flag = sign-carrying, opportunity-normalized.
    df["exp_tds"] = df["rz_targets"] * RZ_TD_RATE["rec"] + df["rz_carries"] * RZ_TD_RATE["rush"]
    actual_tds = df["rec_tds"] + df["rush_tds"]
    df["td_oe"] = actual_tds - df["exp_tds"]
    # normalize by games so it's comparable across usage; clip to a sane band for z-scoring.
    df["td_regression_flag"] = np.clip(df["td_oe"] / df["games"].clip(lower=1), -1.5, 1.5)

    df["qb_epa_per_play"] = pd.to_numeric(df["qb_epa_per_play"], errors="coerce").fillna(0.0)
    df["qb_cpoe"] = pd.to_numeric(df["qb_cpoe"], errors="coerce").fillna(0.0)

    keep = ["gsis_id", "season", "games", *_RAW, *FEATURE_COLS]
    out = df[[c for c in keep if c in df.columns]].copy()
    assert np.isfinite(out[FEATURE_COLS].to_numpy(dtype=float)).all(), "non-finite eff feature"
    return out
