"""Phase 5.1 — quantile regression of realized points on the calibrated mean.

Phase 4 gave a **calibrated point estimate** (the value board's mean, corrected so
``Σreal/Σpred≈1``). Phase 5 turns that point into a **distribution** — the risk dial needs to know
not just *where* a player lands but *how wide* the outcome is. This module is step one: the
**conditional quantiles** of a healthy season.

Design (deliberately low-dimensional — ~a few hundred player-seasons per position, the no-overfit
rule): the single strongest predictor of a player's outcome spread is his **own projected level**
(a 300-point projection has a wider absolute spread than a 60-point one). So we fit a
**per-position linear quantile regression** of realized season points on the calibrated mean, one
line per τ ∈ {.1,.25,.5,.75,.9}. The τ=.5 line recovers the calibrated mean (slope≈1); the outer τ
lines *fan out* with level — that fan is the heteroscedastic spread the sampler (5.x) draws from.
Crossing is repaired by sorting the fitted quantiles.

**Conditional on availability:** we fit only on players who stayed on the field (``weeks ≥
0.85·season``), so this is the *if-healthy* distribution. Injury attrition is a **separate** factor
(5.4 survival) that the assembler multiplies in — keeping the two sources of downside honest and
un-double-counted (mirrors the 4.4 conditional-vs-unconditional split). PIT/lockbox: fit on
``DEV_SEASONS``, never on the target season.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.regression.quantile_regression import QuantReg

from fantasy_quant.backtest.scoring import RuleSet, season_points
from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.projections import calibration
from fantasy_quant.projections.consensus import consensus_projection
from fantasy_quant.projections.rookie import rookie_projection
from fantasy_quant.valuation.value_board import value_board

QUANTILE_TAUS: tuple[float, ...] = (0.1, 0.25, 0.5, 0.75, 0.9)
SKILL = ("QB", "RB", "WR", "TE")


def season_games(season: int) -> int:
    """Max regular-season games a player could play (16 pre-2021, 17 from the 17-game era)."""
    return 16 if int(season) < 2021 else 17


# --------------------------------------------------------------------------------------------
# the calibrated mean board (Phase-4 value board × 4.4 correction) — the Phase-5 input
# --------------------------------------------------------------------------------------------
def dev_correction(con, ruleset: RuleSet | None = None,
                   dev_seasons=None) -> dict:
    """The 4.4 per-position correction factor (bias itself), fit on DEV seasons ≥ 2016."""
    dev = [s for s in (dev_seasons or DEV_SEASONS) if s >= 2016]
    report = calibration.calibration_report(con, consensus_projection, dev, ruleset)
    return report["correction_factor"]


def calibrated_mean_board(con, season: int, ruleset: RuleSet | None = None,
                          correction: dict | None = None) -> pd.DataFrame:
    """The frozen 4.2 value board with the 4.4 calibration correction applied to the mean.

    Returns ``[player_key, pos, calibrated_mean]`` (skill positions). ``calibrated_mean`` is the
    honest *if-healthy* season expectation the distribution centers on.
    """
    ruleset = ruleset or RuleSet()
    if correction is None:
        correction = dev_correction(con, ruleset)
    board = value_board(con, season, ruleset=ruleset, rookie_fn=rookie_projection)
    board = board[board["pos"].isin(SKILL)].copy()
    board["calibrated_mean"] = board["proj_points"] * board["pos"].map(correction).fillna(1.0)
    return board[["player_key", "pos", "calibrated_mean"]].reset_index(drop=True)


def conditional_training_frame(con, seasons, ruleset: RuleSet | None = None,
                               correction: dict | None = None,
                               avail_floor: float = 0.85) -> pd.DataFrame:
    """Calibrated mean joined to realized season points, for players who stayed available.

    One row per (player, season) with ``weeks ≥ avail_floor·season_games`` — the *conditional*
    cohort whose realized total reflects a roughly full slate. ``[player_key, pos, calibrated_mean,
    points]``.
    """
    ruleset = ruleset or RuleSet()
    if correction is None:
        correction = dev_correction(con, ruleset)
    frames = []
    for s in seasons:
        board = calibrated_mean_board(con, s, ruleset, correction)
        real = (season_points(con, s, ruleset)[["gsis_id", "points", "weeks"]]
                .rename(columns={"gsis_id": "player_key"}))
        m = board.merge(real, on="player_key", how="inner")
        m = m[m["weeks"] >= avail_floor * season_games(s)]
        frames.append(m[["player_key", "pos", "calibrated_mean", "points"]])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["player_key", "pos", "calibrated_mean", "points"])


# --------------------------------------------------------------------------------------------
# per-position linear quantile regression (pure — the unit-test target)
# --------------------------------------------------------------------------------------------
def fit_quantile_models(train: pd.DataFrame, taus=QUANTILE_TAUS,
                        feature: str = "calibrated_mean", target: str = "points") -> dict:
    """One linear ``QuantReg`` per (position, τ) of ``target`` on ``feature``.

    Returns ``{pos: {tau: (intercept, slope)}}``. Positions with too few rows to fit are skipped
    (the caller falls back to a pooled/identity spread).
    """
    models: dict[str, dict[float, tuple[float, float]]] = {}
    for pos, g in train.groupby("pos"):
        if len(g) < 30:
            continue
        x = sm.add_constant(g[feature].to_numpy(float), has_constant="add")
        y = g[target].to_numpy(float)
        by_tau = {}
        for tau in taus:
            res = QuantReg(y, x).fit(q=tau, max_iter=2000)
            by_tau[tau] = (float(res.params[0]), float(res.params[1]))
        models[pos] = by_tau
    return models


def predict_quantiles(models: dict, pos: str, mean: np.ndarray, taus=QUANTILE_TAUS) -> np.ndarray:
    """Predicted quantiles for a position, shape ``(len(mean), len(taus))``, floored at 0 and made
    monotone across τ (repairs quantile crossing). Unknown position → NaN rows."""
    mean = np.asarray(mean, dtype=float)
    if pos not in models:
        return np.full((len(mean), len(taus)), np.nan)
    cols = []
    for tau in taus:
        b0, b1 = models[pos][tau]
        cols.append(np.clip(b0 + b1 * mean, 0.0, None))
    q = np.column_stack(cols)
    return np.sort(q, axis=1)   # enforce non-crossing


# --------------------------------------------------------------------------------------------
# the PIT projection
# --------------------------------------------------------------------------------------------
def quantile_projection(con, season: int, ruleset: RuleSet | None = None, taus=QUANTILE_TAUS,
                        train_seasons=None, correction: dict | None = None) -> pd.DataFrame:
    """Conditional quantiles of ``season``'s players, fit walk-forward on strictly-prior DEV
    seasons.

    Returns ``[player_key, pos, calibrated_mean, q{τ}...]``. Trains on the conditional (available)
    cohort; predicts every player on the target board.
    """
    ruleset = ruleset or RuleSet()
    if correction is None:
        correction = dev_correction(con, ruleset)
    if train_seasons is None:
        train_seasons = [s for s in DEV_SEASONS if s < season] or list(DEV_SEASONS)
    train = conditional_training_frame(con, train_seasons, ruleset, correction)
    models = fit_quantile_models(train, taus)

    board = calibrated_mean_board(con, season, ruleset, correction)
    out = board.copy()
    qcols = [f"q{int(t * 100)}" for t in taus]
    qvals = np.full((len(board), len(taus)), np.nan)
    for pos, idx in board.groupby("pos").groups.items():
        rows = board.loc[idx]
        qvals[board.index.get_indexer(idx)] = predict_quantiles(
            models, pos, rows["calibrated_mean"].to_numpy(float), taus)
    for j, c in enumerate(qcols):
        out[c] = qvals[:, j]
    return out
