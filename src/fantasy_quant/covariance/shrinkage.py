"""Phase 8.2 — structured correlation priors + shrinkage → the CorrelationModel.

The 8.1 pooled estimates are honest but uneven: QB1–WR1 has ~250 training pairs, TE2–TE3 has a
handful. The intern-repo answer is **shrinkage toward a structured target** (the Ledoit-Wolf
philosophy). We deviate from *literal* Ledoit-Wolf — that estimator stabilizes a raw high-dimension
sample covariance, which our 17-week seasons can't even produce — and instead shrink each pooled
relationship correlation toward its documented **structural prior** with an empirical-Bayes weight:

    ρ̂ = w·ρ_emp + (1−w)·ρ_prior,      w = n_pairs / (n_pairs + κ)

Same bias–variance trade, adapted to the typed-block structure: relationships the data has seen
hundreds of times are essentially empirical; rare ones lean on the prior. ``κ = 25`` means ~25
observed pairs buy the data half the say.

Priors are the fantasy-community folk numbers the BUILD_PLAN names (QB–WR1 ≈ +0.4 stack, RB1–RB2
≈ −0.3 backfield competition) plus mild same/cross-position defaults — they are *targets to shrink
toward*, not truths, and the step script prints emp vs prior vs shrunk so drift is visible.

The product is a :class:`CorrelationModel`: the one lookup every consumer (Σ assembly, roster risk,
the covariance-aware pick penalty) shares, with an exact-role → generic-pair → 0 fallback. PIT:
:func:`estimate_correlation_model` trains on strictly-prior DEV seasons only.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import pandas as pd

from fantasy_quant.backtest.scoring import RuleSet
from fantasy_quant.covariance.estimate import (
    generic_key,
    pair_correlations,
    relationship_key,
    weekly_offense_panel,
)

# Structural priors (same team). Role-specific entries override the generic position pair.
# Sources: BUILD_PLAN §8.2 constants + standard fantasy stacking/committee folk values. These are
# shrink targets — the data overrides them wherever it has pairs.
STRUCTURED_PRIOR: dict[str, float] = {
    # generic position pairs
    "QB-WR": 0.35, "QB-TE": 0.30, "QB-RB": 0.05, "QB-QB": -0.30,
    "RB-RB": -0.25, "RB-WR": -0.05, "RB-TE": -0.05,
    "WR-WR": 0.05, "TE-WR": 0.00, "TE-TE": -0.15,
    # role-specific overrides
    "QB1-WR1": 0.40, "RB1-RB2": -0.30,
}
DEFAULT_KAPPA = 25.0
_RHO_CAP = 0.85          # no same-team pair is priced as near-duplicate risk


def prior_for(rel: str, generic: str) -> float:
    """The structural prior for a relationship: exact role key → generic pair → 0."""
    return STRUCTURED_PRIOR.get(rel, STRUCTURED_PRIOR.get(generic, 0.0))


def shrink_correlations(emp: pd.DataFrame, kappa: float = DEFAULT_KAPPA) -> pd.DataFrame:
    """Shrink each pooled empirical relationship correlation toward its structural prior.

    ``emp`` is 8.1's ``pair_correlations`` output. Adds ``prior · weight · rho`` where ``weight``
    is the data's share and ``rho`` the shrunk (and ±cap clipped) correlation the model serves.
    """
    out = emp.copy()
    out["prior"] = [prior_for(r, g) for r, g in zip(out["rel"], out["generic"], strict=False)]
    out["weight"] = out["n_pairs"] / (out["n_pairs"] + float(kappa))
    out["rho"] = (out["weight"] * out["corr"] + (1.0 - out["weight"]) * out["prior"]).clip(
        -_RHO_CAP, _RHO_CAP)
    return out


@dataclass(frozen=True)
class CorrelationModel:
    """The same-team correlation lookup every Phase-8 consumer shares.

    ``table`` keeps the full emp/prior/shrunk audit trail for display; ``rho()`` is the runtime
    lookup: exact role relationship → generic position pair → prior → 0. Cross-team pairs are the
    caller's 0 (this model is only ever asked about teammates).
    """
    table: pd.DataFrame
    _lookup: dict[str, float] = field(default_factory=dict, repr=False)

    @classmethod
    def from_table(cls, shrunk: pd.DataFrame) -> CorrelationModel:
        return cls(table=shrunk,
                   _lookup=dict(zip(shrunk["rel"], shrunk["rho"], strict=False)))

    def rho(self, pos_a: str, role_a: int, pos_b: str, role_b: int) -> float:
        rel = relationship_key(pos_a, role_a, pos_b, role_b)
        gen = generic_key(pos_a, pos_b)
        if rel in self._lookup:
            return self._lookup[rel]
        if gen in self._lookup:
            return self._lookup[gen]
        return prior_for(rel, gen)

    def render(self, min_pairs: int = 20) -> str:
        """Compact emp-vs-prior-vs-shrunk audit table (role-specific rows with real support)."""
        t = self.table
        t = t[(t["rel"] != t["generic"]) & (t["n_pairs"] >= min_pairs)]
        lines = [f"  {'relationship':14s} {'emp':>6s} {'prior':>6s} {'shrunk':>7s} {'pairs':>6s}"]
        for r in t.sort_values("n_pairs", ascending=False).itertuples(index=False):
            lines.append(f"  {r.rel:14s} {r.corr:+6.2f} {r.prior:+6.2f} {r.rho:+7.2f} "
                         f"{r.n_pairs:6d}")
        return "\n".join(lines)


def neutral_model() -> CorrelationModel:
    """A prior-only model (no data): every relationship at its structural prior. The fallback when
    no training seasons exist, and a useful synthetic-test fixture."""
    rows = [{"rel": k, "generic": k if "-" in k and not any(c.isdigit() for c in k)
             else generic_key(*_split(k)), "corr": v, "n_pairs": 0, "n_weeks": 0,
             "prior": v, "weight": 0.0, "rho": v}
            for k, v in STRUCTURED_PRIOR.items()]
    return CorrelationModel.from_table(pd.DataFrame(rows))


def _split(rel: str) -> tuple[str, str]:
    a, b = rel.split("-")
    return a.rstrip("0123456789"), b.rstrip("0123456789")


def estimate_correlation_model(con, seasons: Iterable[int], ruleset: RuleSet | None = None,
                               kappa: float = DEFAULT_KAPPA) -> CorrelationModel:
    """The one-call PIT builder: weekly panel over ``seasons`` (strictly before the draft season —
    the caller owns that) → pooled pair correlations → shrink toward priors → model."""
    seasons = sorted(int(s) for s in seasons)
    if not seasons:
        return neutral_model()
    panel = weekly_offense_panel(con, seasons, ruleset)
    emp = pair_correlations(panel)
    if emp.empty:
        return neutral_model()
    return CorrelationModel.from_table(shrink_correlations(emp, kappa))
