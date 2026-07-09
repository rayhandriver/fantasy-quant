"""Phase 8.3 — the handcuff copula (tail dependence a Gaussian Σ cannot see).

A handcuff's payoff is *asymmetric*: the backup is roughly worthless while the starter is healthy
and spikes exactly when the starter's weeks go to zero. A single Pearson ρ (8.1/8.2) prices average
co-movement; it cannot express "the dependence lives in the tail". The classical tool is a
**Clayton copula**, whose dependence concentrates in one corner with tail-dependence coefficient
``λ = 2^(−1/θ)``. For the handcuff direction — starter LOW ↔ backup HIGH — we use the **90°-rotated
Clayton**: sample ``(u, v)`` Clayton and return ``(u, 1−v)``.

Scope is deliberately **targeted** (decision 2026-07-09): the Gaussian shrunk Σ drives general
roster variance (8.4); the copula prices only the handcuff contingency feeding the 8.5 real option.
A full copula roster model is unvalidatable on ~17-week seasons.

Estimation: pooled **Kendall's τ** between same-backfield RB1/RB2 weekly points on the *zero-filled*
week grid — absence scores 0 because absence IS the payoff event (the one place we deliberately mix
availability into a dependence estimate; the Gaussian R conditions on both-active precisely so this
isn't double-counted). Clayton maps τ → θ via ``θ = 2τ/(1+... )`` — see :func:`clayton_theta`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from fantasy_quant.covariance.estimate import role_ranks


# ------------------------------------------------------------------------------------------------
# Clayton mechanics (pure)
# ------------------------------------------------------------------------------------------------
def clayton_theta(tau: float) -> float:
    """Clayton θ from Kendall's τ (τ = θ/(θ+2) ⇒ θ = 2τ/(1−τ)). Strength only — pass |τ| and
    express direction via the rotation."""
    tau = abs(float(tau))
    tau = min(tau, 0.95)
    return 2.0 * tau / (1.0 - tau)


def tail_dependence(theta: float) -> float:
    """Clayton lower-tail dependence ``λ_L = 2^(−1/θ)`` — the limit conditional probability the
    Gaussian copula sends to 0."""
    if theta <= 0:
        return 0.0
    return float(2.0 ** (-1.0 / theta))


def clayton_sample(theta: float, n: int, rng: np.random.Generator) -> np.ndarray:
    """``n`` draws ``(u, v)`` from a Clayton copula via the gamma-frailty construction
    (Marshall–Olkin): ``V~Γ(1/θ)``, ``U_i = (1 + E_i/V)^(−1/θ)``. θ→0 degenerates to independence.
    """
    if theta <= 1e-9:
        return rng.uniform(size=(n, 2))
    v = rng.gamma(1.0 / theta, 1.0, size=n)
    e = rng.exponential(size=(n, 2))
    return (1.0 + e / v[:, None]) ** (-1.0 / theta)


def rotated_clayton_sample(theta: float, n: int, rng: np.random.Generator) -> np.ndarray:
    """The handcuff direction: ``(u_starter, 1−v)`` — joint mass where the starter's uniform is LOW
    and the backup's is HIGH (starter busts ⇒ backup booms)."""
    uv = clayton_sample(theta, n, rng)
    return np.column_stack([uv[:, 0], 1.0 - uv[:, 1]])


def clayton_cdf(u, v, theta: float):
    """Clayton copula CDF ``C(u,v) = (u^−θ + v^−θ − 1)^(−1/θ)`` (independence at θ→0)."""
    u = np.asarray(u, float)
    v = np.asarray(v, float)
    if theta <= 1e-9:
        return u * v
    return np.clip(u ** -theta + v ** -theta - 1.0, 1e-300, None) ** (-1.0 / theta)


def boom_given_bust_clayton(q: float, theta: float) -> float:
    """P(backup above their (1−q) quantile | starter below their q quantile) under the rotated
    Clayton — analytically ``C(q, q)/q``, which → λ_L as q → 0."""
    return float(clayton_cdf(q, q, theta) / q)


def boom_given_bust_gaussian(q: float, tau: float) -> float:
    """The same conditional under a **Gaussian** copula matched to the same Kendall τ
    (``ρ = sin(πτ/2)``, sign flipped for the handcuff direction) — the comparison that shows what
    the linear-correlation world misses in the tail."""
    rho = float(np.sin(np.pi * abs(tau) / 2.0))
    z = stats.norm.ppf(q)
    # rotated: P(U≤q, 1−V≤q) with (U,V) Gaussian(ρ) == P(Z1≤z, Z2≤z) with correlation ρ
    joint = stats.multivariate_normal(mean=[0.0, 0.0],
                                      cov=[[1.0, rho], [rho, 1.0]]).cdf([z, z])
    return float(joint / q)


# ------------------------------------------------------------------------------------------------
# the empirical handcuff dependence (zero-filled backfield pairs)
# ------------------------------------------------------------------------------------------------
def handcuff_pairs(panel: pd.DataFrame) -> pd.DataFrame:
    """Every (season, team) RB1/RB2 pair's zero-filled weekly points: one row per team-week with
    ``starter_pts``/``backup_pts`` (0 when inactive — absence is the event)."""
    roles = role_ranks(panel)
    rb = roles[roles["pos"] == "RB"]
    team_weeks = panel[["season", "team", "week"]].drop_duplicates()
    rows = []
    for (season, team), g in rb.groupby(["season", "team"]):
        g = g.set_index("role")["gsis_id"]
        if 1 not in g.index or 2 not in g.index:
            continue
        tw = team_weeks[(team_weeks["season"] == season) & (team_weeks["team"] == team)]
        pts = panel[(panel["season"] == season) & (panel["team"] == team)]
        s = pts[pts["gsis_id"] == g[1]].set_index("week")["points"]
        b = pts[pts["gsis_id"] == g[2]].set_index("week")["points"]
        for w in tw["week"]:
            rows.append({"season": season, "team": team, "week": w,
                         "starter_pts": float(s.get(w, 0.0)),
                         "backup_pts": float(b.get(w, 0.0)),
                         "starter_active": bool(w in s.index)})
    return pd.DataFrame(rows, columns=["season", "team", "week", "starter_pts", "backup_pts",
                                       "starter_active"])


def handcuff_dependence(panel: pd.DataFrame, min_weeks: int = 10) -> dict:
    """Pooled handcuff dependence: per-pair Kendall τ between zero-filled RB1/RB2 weekly points,
    week-weighted across pairs. Returns ``tau`` (pooled, typically negative), ``theta`` (Clayton,
    from |τ|), ``tail`` (λ_L), ``n_pairs``."""
    pairs = handcuff_pairs(panel)
    if pairs.empty:
        return {"tau": 0.0, "theta": 0.0, "tail": 0.0, "n_pairs": 0}
    taus, weights = [], []
    for _, g in pairs.groupby(["season", "team"]):
        if len(g) < min_weeks or g["starter_pts"].std() < 1e-9 or g["backup_pts"].std() < 1e-9:
            continue
        t, _ = stats.kendalltau(g["starter_pts"], g["backup_pts"])
        if np.isfinite(t):
            taus.append(float(t))
            weights.append(len(g))
    if not taus:
        return {"tau": 0.0, "theta": 0.0, "tail": 0.0, "n_pairs": 0}
    tau = float(np.average(taus, weights=weights))
    theta = clayton_theta(tau)
    return {"tau": tau, "theta": theta, "tail": tail_dependence(theta), "n_pairs": len(taus)}
