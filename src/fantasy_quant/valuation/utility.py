"""Phase 5.5 — mean-variance utility: the risk dial that turns a distribution into a *decision*.

A distribution (Phase-5 assembler) is not yet a ranking. Two players with the same mean are not
equally draftable: a boom/bust dart and a steady floor play suit different managers and different
roster contexts. The **certainty equivalent** collapses the cloud to the single number the
optimizer maximizes, under an explicit risk appetite:

    CE(λ) = E[Y] − λ · Var[Y]

``λ`` is the **risk dial** (units 1/points): λ=0 is risk-neutral (rank on the mean); larger λ
penalizes variance, pulling volatile players down and floor players up. ``risk_premium = λ·Var`` is
the *cost of a player's uncertainty* in points — the honest, per-player price the reframe promises.
This is the mean-variance form the user chose; it slots straight into the Phase-8 covariance work
(there ``Var`` becomes the roster's covariance-aware portfolio variance, and the same λ prices
*tracking error*). CVaR/tail objectives (Phase 10 leverage) can layer on later from the same sample
cloud.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# a default that makes the penalty a meaningful-but-not-dominant share of a starter's projection
# (a 40-pt-sd season ⇒ Var≈1600 ⇒ ~16-pt haircut). The app exposes this as the user-facing dial.
DEFAULT_LAMBDA = 0.01


def certainty_equivalent(mean, var, lam: float = DEFAULT_LAMBDA) -> np.ndarray:
    """Mean-variance certainty equivalent ``E[Y] − λ·Var[Y]`` (floored at 0)."""
    mean = np.asarray(mean, dtype=float)
    var = np.asarray(var, dtype=float)
    return np.clip(mean - lam * var, 0.0, None)


def cvar(samples: np.ndarray, alpha: float = 0.1) -> np.ndarray:
    """Lower-tail CVaR (mean of the worst ``alpha`` fraction) per row — a downside-floor read for
    the narrative; not the ranking objective. ``samples`` is ``(n_players, n_draws)``."""
    s = np.sort(np.asarray(samples, dtype=float), axis=1)
    k = max(1, int(alpha * s.shape[1]))
    return s[:, :k].mean(axis=1)


def risk_adjusted_board(dist: pd.DataFrame, lam: float = DEFAULT_LAMBDA) -> pd.DataFrame:
    """Attach ``ce_value``, ``risk_premium`` and a CE-based overall/positional rank to a
    distribution.

    ``dist`` needs ``mean``/``sd`` (from the assembler). Ranks are by ``ce_value`` (higher =
    better) — the risk-dial ordering the optimizer drafts against.
    """
    out = dist.copy()
    var = out["sd"].to_numpy(float) ** 2
    out["ce_value"] = certainty_equivalent(out["mean"], var, lam)
    out["risk_premium"] = out["mean"].to_numpy(float) - out["ce_value"].to_numpy(float)
    out["ce_rank"] = out["ce_value"].rank(ascending=False, method="first").astype(int)
    out["ce_pos_rank"] = out.groupby("pos")["ce_value"].rank(ascending=False,
                                                             method="first").astype(int)
    return out.sort_values("ce_rank").reset_index(drop=True)
