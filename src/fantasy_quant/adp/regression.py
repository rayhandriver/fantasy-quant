"""Phase 6.2 — the cross-sectional ADP-alpha regression (which traits beat the draft slot).

Regress each drafted player's **ADP-alpha** (Phase 6.1, realized value-over-replacement minus their
ADP-implied baseline) on point-in-time traits: rookie status, experience, ADP dispersion, and prior-
season durability/productivity, with position dummies as controls. A coefficient is the fantasy
analog of a **factor loading** — how much a trait systematically moves realized value *beyond what
ADP already priced in*. Positive ⇒ the crowd under-drafts that trait (cheap to prefer); negative ⇒
over-drafts it (costly to chase).

Because the ~1,500 player rows are **clustered within ~9 seasons** (a boom year lifts everyone), iid
standard errors would badly overstate certainty. So the CIs come from a **season block bootstrap**
(resample whole seasons with replacement, refit) — the same discipline as the Phase-1.5 harness.
Continuous features are z-scored so each coefficient reads as "alpha per 1 SD of the trait" and the
Phase-6.3 multiple-testing correction compares like with like.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from fantasy_quant.adp.panel import FEATURES

_CONTINUOUS = ("experience", "adp_stdev", "prior_games", "prior_ppg")
_POS_DUMMIES = ("RB", "WR", "TE")   # QB is the baseline


# ------------------------------------------------------------------------------------------------
# design matrix + a bare-metal OLS (fast enough to refit thousands of times)
# ------------------------------------------------------------------------------------------------
def prepare(panel: pd.DataFrame,
            features: Sequence[str] = FEATURES) -> tuple[pd.DataFrame, list[str]]:
    """Return (augmented panel, design-column names): z-score the continuous features on the **full
    panel** (so pooled and per-season fits share one scale) and one-hot the position controls."""
    aug = panel.copy()
    cols: list[str] = []
    for f in features:
        if f in _CONTINUOUS:
            mu, sd = aug[f].mean(), aug[f].std(ddof=0) or 1.0
            aug[f"z_{f}"] = (aug[f] - mu) / sd
            cols.append(f"z_{f}")
        else:                                   # already 0/1 (rookie)
            cols.append(f)
    for p in _POS_DUMMIES:
        aug[f"pos_{p}"] = (aug["pos"] == p).astype(float)
        cols.append(f"pos_{p}")
    return aug, cols


def _ols(aug: pd.DataFrame, cols: Sequence[str], target: str = "alpha") -> np.ndarray:
    """OLS coefficients (intercept first) via least squares. Rows with any NaN design cell go."""
    use = aug[[target, *cols]].dropna()
    X = np.column_stack([np.ones(len(use)), use[list(cols)].to_numpy(float)])
    y = use[target].to_numpy(float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def _r2(aug: pd.DataFrame, cols: Sequence[str], beta: np.ndarray, target: str = "alpha") -> float:
    use = aug[[target, *cols]].dropna()
    X = np.column_stack([np.ones(len(use)), use[list(cols)].to_numpy(float)])
    y = use[target].to_numpy(float)
    resid = y - X @ beta
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return 1.0 - float((resid ** 2).sum()) / ss_tot if ss_tot > 0 else 0.0


# ------------------------------------------------------------------------------------------------
# the fit (point estimate + season block-bootstrap CIs)
# ------------------------------------------------------------------------------------------------
@dataclass
class RegressionResult:
    """ADP-alpha regression with season-block-bootstrap uncertainty. ``terms`` aligns with ``coef``,
    ``ci_lo``, ``ci_hi``, ``p_value`` (intercept first). ``p_value`` is a two-sided bootstrap p."""
    terms: list[str]
    coef: np.ndarray
    ci_lo: np.ndarray
    ci_hi: np.ndarray
    p_value: np.ndarray
    r2: float
    n: int
    n_seasons: int
    n_boot: int
    ci: float

    def table(self) -> pd.DataFrame:
        return pd.DataFrame({
            "term": self.terms, "coef": self.coef, "ci_lo": self.ci_lo, "ci_hi": self.ci_hi,
            "p_value": self.p_value,
        })


def fit_alpha_regression(panel: pd.DataFrame, features: Sequence[str] = FEATURES,
                         n_boot: int = 2000, seed: int = 0, ci: float = 0.95) -> RegressionResult:
    """Fit alpha ~ traits on the pooled panel; bootstrap CIs by resampling whole **seasons** (so the
    uncertainty respects the ~9-season effective sample, not the ~1,500 correlated player rows)."""
    aug, cols = prepare(panel, features)
    terms = ["intercept", *cols]
    beta = _ols(aug, cols)

    seasons = aug["season"].unique()
    rng = np.random.default_rng(seed)
    boot = np.empty((n_boot, len(terms)))
    for b in range(n_boot):
        draw = rng.choice(seasons, size=len(seasons), replace=True)
        samp = pd.concat([aug[aug["season"] == s] for s in draw], ignore_index=True)
        boot[b] = _ols(samp, cols)

    alpha = (1 - ci) / 2
    lo, hi = np.quantile(boot, [alpha, 1 - alpha], axis=0)
    # two-sided bootstrap p: twice the smaller tail mass on either side of 0.
    p = 2.0 * np.minimum((boot <= 0).mean(axis=0), (boot >= 0).mean(axis=0))
    p = np.clip(p, 1.0 / n_boot, 1.0)
    return RegressionResult(terms=terms, coef=beta, ci_lo=lo, ci_hi=hi, p_value=p,
                            r2=_r2(aug, cols, beta), n=int(len(aug)), n_seasons=int(len(seasons)),
                            n_boot=n_boot, ci=ci)
