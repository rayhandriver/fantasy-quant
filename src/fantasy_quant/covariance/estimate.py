"""Phase 8.1 — the player-week covariance estimate (the tracking-error machinery, repurposed).

A roster is a portfolio: its season variance is ``1ᵀΣ1``, not the sum of player variances. With
only ~17 weeks per season a raw k×k sample covariance over ~500 board players is hopeless
(n ≪ k), so we do what the intern-repo's factor covariance did — impose structure and estimate the
few parameters the sample *can* support:

    Σ = D^{1/2} · R · D^{1/2}

* **D** (the diagonal) comes from the Phase-5 per-player season distributions — the ``sd`` the risk
  dial already prices. Nothing here re-estimates a player's own variance.
* **R** is a **relationship-typed correlation**: every same-team pair belongs to a small family of
  relationships (QB1–WR1 stack, RB1–RB2 backfield, WR1–WR2 target competition, …) whose weekly-point
  correlation we pool across every such pair in every training season — hundreds of pairs per
  relationship instead of 17 weeks per pair. Cross-team pairs are 0 (schedule-level dependence is
  second-order for season totals and unresolvable at our sample).

Correlations are estimated on weeks **both players were active** — the performance co-movement a
stack/committee is about. Availability dependence (the handcuff payoff) is deliberately *not* in R;
it lives in the 8.3 copula, so it is never double-counted.

Scaling note (documented assumption): with weeks ≈ i.i.d. and only contemporaneous dependence, the
correlation of two players' season *totals* equals their weekly correlation, so R applies directly
to the Phase-5 season sds. Season-level shared shocks (a whole offense over/under-performing its
projection) likely push true teammate correlations *above* the weekly estimate; the 8.2 shrinkage
toward structural priors partially compensates, and the roster floor/ceiling is read as directional
(§7 humility).

Every Σ passes the **hard gate** (finite, symmetric, PSD — the intern covariance gate) before any
consumer sees it; assembly from typed blocks can produce small negative eigenvalues, which the
Higham-style repair clips while preserving each player's own variance.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from fantasy_quant.backtest import scoring
from fantasy_quant.backtest.scoring import RuleSet

OFFENSE = ("QB", "RB", "WR", "TE")
_CANON = {"QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "FB": "RB", "HB": "RB"}
MAX_ROLE_RANK = 3        # depth beyond 3 pools into the "3" bucket (WR4 ≈ WR3 statistically)


# ------------------------------------------------------------------------------------------------
# the weekly panel + within-team roles
# ------------------------------------------------------------------------------------------------
def weekly_offense_panel(con, seasons: Iterable[int], ruleset: RuleSet | None = None,
                         min_weeks: int = 4) -> pd.DataFrame:
    """Long panel of offensive player-weeks: ``season · week · gsis_id · pos · team · points``.

    One row per week actually played (REG). ``team`` is the week's team, so mid-season trades
    split a player across teams — pairs are formed on *shared team-weeks*, which is exactly right.
    Players with fewer than ``min_weeks`` appearances in a season are dropped (their correlations
    are pure noise and their depth role is unstable).
    """
    frames = []
    for season in seasons:
        wk = scoring.weekly_points(con, int(season), ruleset)
        wk = wk.assign(pos=wk["position"].astype(str).str.upper().map(_CANON))
        wk = wk.dropna(subset=["pos", "gsis_id", "team"])
        frames.append(wk[["season", "week", "gsis_id", "pos", "team", "points"]])
    panel = pd.concat(frames, ignore_index=True)
    counts = panel.groupby(["season", "gsis_id"])["week"].transform("nunique")
    return panel[counts >= min_weeks].reset_index(drop=True)


def role_ranks(panel: pd.DataFrame) -> pd.DataFrame:
    """Within-(season, team, pos) depth role by season points: 1 = the top scorer (WR1), capped at
    :data:`MAX_ROLE_RANK`. A player's role is per (season, team) so trades re-rank cleanly."""
    totals = (panel.groupby(["season", "team", "pos", "gsis_id"], as_index=False)
              .agg(pts=("points", "sum")))
    totals["role"] = (totals.groupby(["season", "team", "pos"])["pts"]
                      .rank(ascending=False, method="first").astype(int)
                      .clip(upper=MAX_ROLE_RANK))
    return totals[["season", "team", "pos", "gsis_id", "role"]]


def relationship_key(pos_a: str, role_a: int, pos_b: str, role_b: int) -> str:
    """Canonical same-team relationship label, order-free: ``"QB1-WR1"``, ``"RB1-RB2"``, …"""
    a = (pos_a, min(int(role_a), MAX_ROLE_RANK))
    b = (pos_b, min(int(role_b), MAX_ROLE_RANK))
    (pa, ra), (pb, rb) = sorted([a, b])
    return f"{pa}{ra}-{pb}{rb}"


def generic_key(pos_a: str, pos_b: str) -> str:
    """The role-free fallback family: ``"QB-WR"``, ``"RB-RB"``, …"""
    pa, pb = sorted([pos_a, pos_b])
    return f"{pa}-{pb}"


# ------------------------------------------------------------------------------------------------
# pooled pair correlations by relationship
# ------------------------------------------------------------------------------------------------
def pair_correlations(panel: pd.DataFrame, min_shared_weeks: int = 6) -> pd.DataFrame:
    """Pooled weekly-point correlation per same-team relationship type.

    For every (season, team) and every within-team player pair with ≥ ``min_shared_weeks`` weeks
    *both active*, compute the Pearson correlation of their weekly points over those shared weeks,
    then pool within each relationship key weighted by shared weeks. Returns one row per
    relationship: ``rel · generic · corr · n_pairs · n_weeks`` (plus the role-free ``generic``
    aggregate rows the lookup falls back to).
    """
    roles = role_ranks(panel)
    p = panel.merge(roles, on=["season", "team", "pos", "gsis_id"])
    rows = []
    for (season, _team), g in p.groupby(["season", "team"]):
        wide = g.pivot_table(index="week", columns="gsis_id", values="points")
        meta = g.drop_duplicates("gsis_id").set_index("gsis_id")[["pos", "role"]]
        ids = list(wide.columns)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = wide[ids[i]], wide[ids[j]]
                both = a.notna() & b.notna()
                n = int(both.sum())
                if n < min_shared_weeks:
                    continue
                x, y = a[both].to_numpy(float), b[both].to_numpy(float)
                if x.std() < 1e-9 or y.std() < 1e-9:
                    continue
                (pa, ra), (pb, rb) = meta.loc[ids[i]], meta.loc[ids[j]]
                rows.append({"season": season, "rel": relationship_key(pa, ra, pb, rb),
                             "generic": generic_key(pa, pb),
                             "corr": float(np.corrcoef(x, y)[0, 1]), "weeks": n})
    pairs = pd.DataFrame(rows, columns=["season", "rel", "generic", "corr", "weeks"])
    if pairs.empty:
        return pd.DataFrame(columns=["rel", "generic", "corr", "n_pairs", "n_weeks"])

    def _pool(g: pd.DataFrame) -> pd.Series:
        w = g["weeks"].to_numpy(float)
        return pd.Series({"corr": float(np.average(g["corr"], weights=w)),
                          "n_pairs": int(len(g)), "n_weeks": int(w.sum())})

    by_rel = (pairs.groupby(["rel", "generic"]).apply(_pool, include_groups=False)
              .reset_index())
    by_gen = (pairs.groupby("generic").apply(_pool, include_groups=False)
              .reset_index().assign(rel=lambda d: d["generic"]))
    out = (pd.concat([by_rel, by_gen], ignore_index=True)
           [["rel", "generic", "corr", "n_pairs", "n_weeks"]]
           .sort_values(["generic", "rel"]).reset_index(drop=True))
    out[["n_pairs", "n_weeks"]] = out[["n_pairs", "n_weeks"]].astype(int)
    return out


# ------------------------------------------------------------------------------------------------
# Σ assembly + the hard gate (the intern covariance gate, ported)
# ------------------------------------------------------------------------------------------------
class CovarianceGateError(ValueError):
    """A covariance matrix failed the hard gate — never hand it to a consumer."""


def validate_covariance(cov: np.ndarray, tol: float = 1e-8) -> None:
    """Hard gate: finite everywhere, symmetric, positive diagonal, PSD (within ``tol``).
    Raises :class:`CovarianceGateError` — consumers only ever see a gated Σ."""
    cov = np.asarray(cov, float)
    if not np.all(np.isfinite(cov)):
        raise CovarianceGateError("covariance has non-finite entries")
    if not np.allclose(cov, cov.T, atol=1e-8):
        raise CovarianceGateError("covariance is not symmetric")
    if np.any(np.diag(cov) <= 0):
        raise CovarianceGateError("covariance has non-positive variances on the diagonal")
    eig = np.linalg.eigvalsh(cov)
    if eig[0] < -tol * max(eig[-1], 1.0):
        raise CovarianceGateError(f"covariance is not PSD (min eigenvalue {eig[0]:.3g})")


def nearest_psd(cov: np.ndarray) -> np.ndarray:
    """Higham-style PSD repair: clip negative eigenvalues to 0, re-symmetrize, then rescale to
    restore the original diagonal (a player's own variance is Phase-5 truth — never distorted)."""
    cov = np.asarray(cov, float)
    sym = (cov + cov.T) / 2.0
    eigval, eigvec = np.linalg.eigh(sym)
    fixed = eigvec @ np.diag(np.clip(eigval, 0.0, None)) @ eigvec.T
    d_orig, d_new = np.diag(sym).copy(), np.diag(fixed).copy()
    scale = np.sqrt(d_orig / np.where(d_new > 1e-12, d_new, 1.0))
    out = fixed * np.outer(scale, scale)
    np.fill_diagonal(out, d_orig)
    return (out + out.T) / 2.0


def player_covariance(sd, teams, positions, roles, rho_fn) -> np.ndarray:
    """Assemble the k×k season-total covariance ``Σ = D^{1/2} R D^{1/2}``.

    ``sd`` — Phase-5 season sds; ``teams``/``positions``/``roles`` aligned arrays; ``rho_fn(pos_a,
    role_a, pos_b, role_b)`` — the same-team correlation lookup (8.2's CorrelationModel.rho).
    Cross-team pairs are 0. The result is PSD-repaired if needed and always passes the hard gate.
    """
    sd = np.asarray(sd, float)
    teams = np.asarray(teams, object)
    positions = np.asarray(positions, object)
    roles = np.asarray(roles, int)
    k = len(sd)
    corr = np.eye(k)
    for i in range(k):
        same = np.flatnonzero((teams == teams[i]) & (np.arange(k) > i))
        for j in same:
            r = float(rho_fn(positions[i], roles[i], positions[j], roles[j]))
            corr[i, j] = corr[j, i] = r
    cov = corr * np.outer(sd, sd)
    eig = np.linalg.eigvalsh((cov + cov.T) / 2.0)
    if eig[0] < -1e-8 * max(eig[-1], 1.0):
        cov = nearest_psd(cov)
    validate_covariance(cov)
    return cov
