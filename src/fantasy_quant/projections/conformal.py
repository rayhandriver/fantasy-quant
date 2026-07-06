"""Phase 5.2 — conformalized quantile regression (finite-sample coverage guarantee).

Quantile regression (5.1) gives *estimated* intervals, but nothing forces them to actually contain
the outcome 80% of the time out-of-sample — a small, biased fit can be systematically too tight.
**Conformal prediction** fixes that with a distribution-free correction: on a held-out calibration
set, measure how far the true outcome falls outside the estimated interval, then inflate (or
shrink) the interval by the empirical (1−α) quantile of that miss. The result has **guaranteed
≈(1−α) marginal coverage** regardless of whether the quantile model was right.

We use **CQR** (Romano et al. 2019): conformity score ``E = max(q_lo − y, y − q_hi)`` (positive
when the outcome is outside the band, negative when comfortably inside), and adjustment ``d =
⌈(1−α)(n+1)⌉/n`` empirical quantile of ``E``; the calibrated band is ``[q_lo − d, q_hi + d]``. One
``d`` per position (spreads differ by position). PIT: the calibration split is a strictly-prior
season; final coverage is read once on the 2025 holdout.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_ALPHA = 0.20   # 80% target interval (two-sided p10–p90)


def cqr_adjustment(q_lo: np.ndarray, q_hi: np.ndarray, y: np.ndarray,
                   alpha: float = DEFAULT_ALPHA) -> float:
    """The CQR conformity adjustment ``d`` (Romano 2019) for one group.

    ``E_i = max(q_lo_i − y_i, y_i − q_hi_i)``; ``d`` = the ``⌈(1−α)(n+1)⌉/n`` empirical quantile of
    E. Positive ``d`` widens the band (model too tight); negative shrinks it (too loose). Pure.
    """
    q_lo, q_hi, y = (np.asarray(a, dtype=float) for a in (q_lo, q_hi, y))
    e = np.maximum(q_lo - y, y - q_hi)
    n = len(e)
    if n == 0:
        return 0.0
    # rank of the desired quantile with the finite-sample (n+1) correction, clipped to [0,1].
    level = min(1.0, np.ceil((1 - alpha) * (n + 1)) / n)
    return float(np.quantile(e, level, method="higher"))


def fit_cqr(cal: pd.DataFrame, lo_col: str, hi_col: str, y_col: str = "points",
            alpha: float = DEFAULT_ALPHA) -> dict:
    """Per-position CQR adjustment from a calibration frame (predicted band + realized
    ``y_col``)."""
    return {pos: cqr_adjustment(g[lo_col], g[hi_col], g[y_col], alpha)
            for pos, g in cal.groupby("pos")}


def apply_cqr(df: pd.DataFrame, adj: dict, lo_col: str, hi_col: str,
              out_lo: str = "lo", out_hi: str = "hi") -> pd.DataFrame:
    """Widen each row's band by its position adjustment ``d`` (floored at 0 on the low side)."""
    out = df.copy()
    d = out["pos"].map(adj).fillna(0.0)
    out[out_lo] = (out[lo_col] - d).clip(lower=0.0)
    out[out_hi] = out[hi_col] + d
    return out


def empirical_coverage(lo: np.ndarray, hi: np.ndarray, y: np.ndarray) -> float:
    """Fraction of outcomes inside ``[lo, hi]`` (inclusive) — the calibration check."""
    lo, hi, y = (np.asarray(a, dtype=float) for a in (lo, hi, y))
    if len(y) == 0:
        return float("nan")
    return float(((y >= lo) & (y <= hi)).mean())
