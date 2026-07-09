"""Phase 8.4 — roster risk: a drafted roster read as a portfolio, ``Var = 1ᵀΣ1``.

The per-player risk dial (5.5) prices each player's own variance; this module prices how the
variances *combine*. A QB stacked with his WR1 concentrates the same offense's outcomes (higher
ceiling, lower floor); an anti-correlated backfield hedges (higher floor). That difference is
exactly the off-diagonal of Σ — the tracking-error machinery from the internship, repurposed.

Two consumers, two tools:

* **Cheap moments** for reports and the optimizer: portfolio mean/variance from the 8.1/8.2 Σ,
  floor/ceiling as Gaussian quantiles of the team total (defensible for a sum of ~10 marginals;
  documented approximation).
* **Sample-faithful** floor/ceiling for analysis: **Iman–Conover** re-ordering imposes the target
  rank correlation on the Phase-5 Monte-Carlo clouds *without touching any marginal* — the skewed
  per-player distributions stay exactly as assembled, only their joint ordering changes.

The roster universe is every rostered player with a Phase-5 distribution (same convention as
``team_value``: bench included, K/DST carry no distribution and contribute zero variance).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from fantasy_quant.covariance.estimate import nearest_psd, player_covariance
from fantasy_quant.covariance.shrinkage import CorrelationModel

STACK_MIN_RHO = 0.15         # same-team pair flagged as a stack
HEDGE_MAX_RHO = -0.10        # same-team pair flagged as a hedge (backfield committee/handcuff)


# ------------------------------------------------------------------------------------------------
# Σ for one roster + portfolio moments (pure given a value index)
# ------------------------------------------------------------------------------------------------
def roster_sigma(roster: pd.DataFrame, value_index: pd.DataFrame,
                 corr: CorrelationModel) -> tuple[pd.DataFrame, np.ndarray]:
    """The roster's covariance. Returns ``(members, Σ)`` where ``members`` is the subset of the
    roster with a distribution (``player_key · pos · team · role_rank · mean · sd``) and Σ is the
    gated ``m×m`` season-total covariance."""
    vi = (value_index.dropna(subset=["sd"]).drop_duplicates("player_key")
          .set_index("player_key"))
    keys = [k for k in roster["player_key"] if k in vi.index]
    members = vi.loc[keys].reset_index()[["player_key", "pos", "team", "role_rank",
                                          "mean", "sd"]]
    if members.empty:
        return members, np.zeros((0, 0))
    sigma = player_covariance(
        members["sd"], members["team"].fillna("?"), members["pos"],
        members["role_rank"].fillna(1).astype(int), corr.rho)
    return members, sigma


def portfolio_moments(means, cov) -> tuple[float, float]:
    """Team-total mean and sd: ``μ = Σμ_i``, ``σ = √(1ᵀΣ1)``."""
    mu = float(np.asarray(means, float).sum())
    var = float(np.asarray(cov, float).sum())
    return mu, float(np.sqrt(max(var, 0.0)))


def floor_ceiling(mu: float, sd: float, q: float = 0.10) -> tuple[float, float]:
    """Gaussian ``(q, 1−q)`` quantiles of the team total (documented approximation — a sum of ~10
    marginals is near-normal even when each is skewed)."""
    from scipy import stats
    z = stats.norm.ppf(1.0 - q)
    return mu - z * sd, mu + z * sd


# ------------------------------------------------------------------------------------------------
# Iman–Conover: impose Σ's correlation on the Phase-5 sample clouds (marginals untouched)
# ------------------------------------------------------------------------------------------------
def correlate_samples(samples: np.ndarray, corr: np.ndarray,
                      rng: np.random.Generator) -> np.ndarray:
    """Re-order each player's Monte-Carlo draws so the joint ranks follow ``corr`` (Iman–Conover).

    ``samples`` is ``(k, n)``; each row's *values* are preserved exactly (a permutation), so every
    Phase-5 marginal — skew, conformal width, injury tail — survives; only the co-movement changes.
    """
    samples = np.asarray(samples, float)
    k, n = samples.shape
    c = nearest_psd(np.asarray(corr, float))
    chol = np.linalg.cholesky(c + 1e-10 * np.eye(k))
    scores = chol @ rng.standard_normal((k, n))
    out = np.empty_like(samples)
    for i in range(k):
        ranks = np.argsort(np.argsort(scores[i]))
        out[i] = np.sort(samples[i])[ranks]
    return out


# ------------------------------------------------------------------------------------------------
# the roster risk profile (what the cost report shows)
# ------------------------------------------------------------------------------------------------
@dataclass
class RosterRisk:
    """A roster's portfolio read: total mean/sd, floor/ceiling, how much of the variance came from
    co-movement, and the named same-team pairs driving it."""
    mean: float
    sd: float
    sd_independent: float          # sd if all players were independent (the diagonal-only read)
    floor: float                   # q10 of the team total
    ceiling: float                 # q90
    pairs: pd.DataFrame            # player_a · player_b · rel_rho  (same-team, |ρ| ≥ threshold)
    n_valued: int

    @property
    def covariance_share(self) -> float:
        """Fraction of portfolio variance from off-diagonal terms (sign carries direction)."""
        if self.sd_independent <= 0:
            return 0.0
        return float((self.sd ** 2 - self.sd_independent ** 2) / self.sd_independent ** 2)

    def describe_pairs(self, names: dict[str, str] | None = None) -> list[str]:
        names = names or {}
        out = []
        for r in self.pairs.itertuples(index=False):
            kind = "stack" if r.rel_rho > 0 else "hedge"
            a = names.get(r.player_a, r.player_a)
            b = names.get(r.player_b, r.player_b)
            out.append(f"{kind}: {a} + {b} (ρ={r.rel_rho:+.2f})")
        return out


def roster_risk(roster: pd.DataFrame, value_index: pd.DataFrame, corr: CorrelationModel,
                q: float = 0.10) -> RosterRisk:
    """The full portfolio read for one drafted roster (see :class:`RosterRisk`)."""
    members, sigma = roster_sigma(roster, value_index, corr)
    if members.empty:
        return RosterRisk(0.0, 0.0, 0.0, 0.0, 0.0,
                          pd.DataFrame(columns=["player_a", "player_b", "rel_rho"]), 0)
    mu, sd = portfolio_moments(members["mean"], sigma)
    sd_ind = float(np.sqrt(np.diag(sigma).sum()))
    lo, hi = floor_ceiling(mu, sd, q)

    rows = []
    sds = members["sd"].to_numpy(float)
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            if sigma[i, j] == 0.0:
                continue
            rho = sigma[i, j] / (sds[i] * sds[j])
            if rho >= STACK_MIN_RHO or rho <= HEDGE_MAX_RHO:
                rows.append({"player_a": members["player_key"].iloc[i],
                             "player_b": members["player_key"].iloc[j],
                             "rel_rho": float(rho)})
    pairs = (pd.DataFrame(rows, columns=["player_a", "player_b", "rel_rho"])
             .sort_values("rel_rho", ascending=False).reset_index(drop=True))
    return RosterRisk(mean=mu, sd=sd, sd_independent=sd_ind, floor=lo, ceiling=hi,
                      pairs=pairs, n_valued=len(members))
