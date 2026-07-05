"""Phase 4.4 — projection calibration (the reframe's real done-criterion: *calibration > edge*).

The reframe retired "beat ADP" as the bar; what actually matters is that the value signal is
**well-calibrated** — a number the user sees must be honest. This module measures the mean
projection against realized season points:

  * **bias ratio** ``Σ realized / Σ predicted`` per position (the intern bias-statistic analog;
    ≈ 1 is calibrated, <1 is optimistic);
  * a **reliability table** — bin players by predicted points and check realized rises monotonically
    with prediction (rank fidelity), plus mean-predicted vs mean-realized per bin;
  * a per-position **correction factor** (= the ``bias`` itself, so ``corrected = pred·bias`` pulls
    ``Σreal/Σcorrected`` to 1) — a documented miscalibration is *corrected*, not just noted.

Two universes, both reported (honesty about survivorship): **conditional** (players who played — the
standard projection check) and **unconditional** (projected players who didn't play count as 0 — the
draft-day injury/washout haircut). Development runs on ``DEV_SEASONS``; **2025 is the calibration
holdout** (``CALIBRATION_SEASONS``) — evaluated once. Coverage/interval calibration is Phase 5.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.backtest import scoring
from fantasy_quant.backtest.scoring import RuleSet


# --------------------------------------------------------------------------------------------
# pure calibration statistics (the unit-test targets)
# --------------------------------------------------------------------------------------------
def bias_ratio(pred: pd.Series | np.ndarray, real: pd.Series | np.ndarray) -> float:
    """``Σ realized / Σ predicted`` — 1.0 is calibrated, <1 optimistic, >1 conservative."""
    p = float(np.nansum(np.asarray(pred, dtype=float)))
    return float(np.nansum(np.asarray(real, dtype=float)) / p) if p else float("nan")


def reliability_table(m: pd.DataFrame, n_bins: int = 10) -> pd.DataFrame:
    """Bin by predicted points (rank-quantile), return mean predicted vs mean realized + count per
    bin. ``m`` needs ``proj_points`` and ``points``. Ascending bins (0 = lowest projected)."""
    ranks = m["proj_points"].rank(method="first")
    bins = pd.qcut(ranks, min(n_bins, max(1, len(m))), labels=False, duplicates="drop")
    return (m.assign(_bin=bins).groupby("_bin")
            .agg(mean_pred=("proj_points", "mean"), mean_real=("points", "mean"),
                 n=("points", "size")).reset_index(drop=True))


# --------------------------------------------------------------------------------------------
# assemble predicted-vs-realized + the report
# --------------------------------------------------------------------------------------------
def matched(con, projection_fn, season: int, ruleset: RuleSet | None = None,
            unconditional: bool = False) -> pd.DataFrame:
    """Predicted (``projection_fn``) joined to realized season points for ``season``.

    ``unconditional=True`` left-joins so a projected player who never played scores 0 (the honest,
    survivorship-safe draft-day universe); otherwise inner-joins (players who played)."""
    # skill positions only: K/DST realized come from separate pbp paths, not season_points.
    pred = projection_fn(con, season)[["player_key", "pos", "proj_points"]]
    pred = pred[pred["pos"].isin(["QB", "RB", "WR", "TE"])]
    real = (scoring.season_points(con, season)[["gsis_id", "points"]]
            .rename(columns={"gsis_id": "player_key"}))
    how = "left" if unconditional else "inner"
    m = pred.merge(real, on="player_key", how=how)
    if unconditional:
        m["points"] = m["points"].fillna(0.0)
    return m.dropna(subset=["proj_points", "points"])


def calibration_report(con, projection_fn, seasons, ruleset: RuleSet | None = None,
                       unconditional: bool = False) -> dict:
    """Pooled calibration of ``projection_fn`` over ``seasons``: overall + per-position bias, rank
    correlation, MAE, per-position correction factors, and the reliability table."""
    m = pd.concat([matched(con, projection_fn, s, ruleset, unconditional) for s in seasons],
                  ignore_index=True)
    by_pos = {pos: bias_ratio(g["proj_points"], g["points"]) for pos, g in m.groupby("pos")}
    return {
        "n": int(len(m)),
        "seasons": list(seasons),
        "overall_bias": bias_ratio(m["proj_points"], m["points"]),
        "by_position_bias": by_pos,
        # to pull bias to 1, deflate predictions by the bias itself (corrected = pred x bias):
        # Σreal / Σ(pred·bias) = (Σreal/Σpred)/bias = 1.
        "correction_factor": dict(by_pos),
        "spearman": float(m["proj_points"].corr(m["points"], method="spearman")),
        "mae": float((m["proj_points"] - m["points"]).abs().mean()),
        "reliability": reliability_table(m),
    }


def apply_correction(m: pd.DataFrame, correction: dict) -> pd.Series:
    """Scale each row's ``proj_points`` by its position correction factor (calibrated points)."""
    return m["proj_points"] * m["pos"].map(correction).fillna(1.0)
