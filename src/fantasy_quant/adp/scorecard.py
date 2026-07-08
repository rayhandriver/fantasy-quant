"""Phase 6.3 — the ADP-bias scorecard (which biases survive scrutiny, honestly).

The regression (6.2) will always report *some* nonzero coefficients; the job here is to separate a
**stable, real** bias from one the ~9-season sample coughed up by chance. Two guards, both ported
from the intern-repo discipline:

  1. **Multiple-testing correction** — we test a handful of traits at once, so a raw 5% p-value is
     too generous. Benjamini-Hochberg FDR controls the false-discovery rate across the trait family
     (position controls are nuisance, excluded from the family).
  2. **Walk-forward sign stability** — refit the model season by season and ask how often each
     trait's coefficient keeps the pooled sign. A bias that flips sign across seasons is not
     actionable, no matter its pooled p-value. (Seasons where a trait is constant — e.g. 2014 has
     no prior-year line — are not counted for that trait.)

A surviving trait is reported with its CI **and** a plain-English reading in the reframe's terms:
positive alpha ⇒ the crowd **under**-drafts that trait (cheap/free to indulge a preference toward
it); negative ⇒ **over**-drafts it (costly to chase). Traits that fail either guard are honestly
**ruled out**, which is itself a finding. Nothing here reads the 2023/24 lockbox.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests

from fantasy_quant.adp.panel import FEATURES
from fantasy_quant.adp.regression import (
    RegressionResult,
    _ols,
    fit_alpha_regression,
    prepare,
)

# human-readable trait labels + which direction of alpha the reframe cares about.
_LABELS: dict[str, str] = {
    "rookie": "rookie",
    "z_experience": "experience (years)",
    "z_adp_stdev": "ADP disagreement (stdev)",
    "z_prior_games": "prior-season games (durability)",
    "z_prior_ppg": "prior-season pts/game (efficiency)",
}


def _is_trait(term: str) -> bool:
    """A tested hypothesis (not the intercept or a position nuisance control)."""
    return term != "intercept" and not term.startswith("pos_")


# ------------------------------------------------------------------------------------------------
# walk-forward sign stability
# ------------------------------------------------------------------------------------------------
def _season_stability(aug: pd.DataFrame, cols: Sequence[str], terms: Sequence[str],
                      pooled: np.ndarray) -> dict[str, tuple[int, float]]:
    """Per trait: (# seasons it was identifiable, fraction of those matching the pooled sign)."""
    pooled_sign = {t: np.sign(pooled[i]) for i, t in enumerate(terms)}
    hits: dict[str, list[bool]] = {t: [] for t in terms}
    for _s, g in aug.groupby("season"):
        live = [c for c in cols if g[c].std(ddof=0) > 1e-9]   # drop constant-in-season columns
        if not live:
            continue
        beta = _ols(g, live)
        season_sign = dict(zip(["intercept", *live], np.sign(beta), strict=False))
        for t in terms:
            if t in season_sign and pooled_sign[t] != 0:
                hits[t].append(season_sign[t] == pooled_sign[t])
    return {t: (len(h), float(np.mean(h)) if h else float("nan")) for t, h in hits.items()}


# ------------------------------------------------------------------------------------------------
# the scorecard
# ------------------------------------------------------------------------------------------------
@dataclass
class Scorecard:
    """The verdict table over the trait hypotheses + the human reading. ``table`` has one row per
    trait with coef, CI, raw & FDR-adjusted p, per-season stability, and a significance flag."""
    table: pd.DataFrame
    reg: RegressionResult
    fdr_alpha: float
    stability_min: float

    @property
    def significant(self) -> pd.DataFrame:
        return self.table[self.table["significant"]]

    def reading(self, row: pd.Series) -> str:
        if not row["significant"]:
            return "no stable ADP bias (ruled out)"
        direction = "UNDER-drafted → cheap to prefer" if row["coef"] > 0 \
            else "OVER-drafted → costly to chase"
        return f"{direction} ({row['coef']:+.0f} VOR/SD, stable {row['stability']:.0%})"

    def render(self) -> str:
        lines = [
            f"ADP-bias scorecard — {self.reg.n} drafted players, {self.reg.n_seasons} DEV seasons, "
            f"R²={self.reg.r2:.3f}  (FDR α={self.fdr_alpha:g}, stab ≥ {self.stability_min:.0%})",
        ]
        for r in self.table.itertuples(index=False):
            row = pd.Series(r._asdict())
            flag = "✓" if row["significant"] else "·"
            lines.append(
                f"  {flag} {row['label']:34s} {row['coef']:+7.1f}  "
                f"[95% CI {row['ci_lo']:+6.1f},{row['ci_hi']:+6.1f}]  "
                f"p_fdr={row['p_fdr']:.3f}  {self.reading(row)}"
            )
        surviving = self.significant["label"].tolist()
        lines.append(f"  → {len(surviving)} stable bias(es) after FDR + stability: {surviving}"
                     if surviving else
                     "  → no ADP bias survives FDR + stability; the crowd is efficient on these "
                     "traits (honestly ruled out).")
        return "\n".join(lines)


def bias_scorecard(panel: pd.DataFrame, features: Sequence[str] = FEATURES, n_boot: int = 2000,
                   seed: int = 0, fdr_alpha: float = 0.05, stability_min: float = 0.6,
                   reg: RegressionResult | None = None) -> Scorecard:
    """Build the scorecard: fit the regression, FDR-correct the trait p-values, score per-season
    sign stability, and flag a bias **significant** only if it clears both FDR and the stability
    floor."""
    reg = reg or fit_alpha_regression(panel, features, n_boot=n_boot, seed=seed)
    aug, cols = prepare(panel, features)
    stab = _season_stability(aug, cols, reg.terms, reg.coef)

    traits = [t for t in reg.terms if _is_trait(t)]
    idx = {t: reg.terms.index(t) for t in traits}
    p_raw = np.array([reg.p_value[idx[t]] for t in traits])
    rej, p_fdr, _, _ = multipletests(p_raw, alpha=fdr_alpha, method="fdr_bh")

    rows = []
    for j, t in enumerate(traits):
        i = idx[t]
        n_seasons, stability = stab[t]
        sig = bool(rej[j]) and (stability >= stability_min)
        rows.append({
            "term": t, "label": _LABELS.get(t, t), "coef": reg.coef[i],
            "ci_lo": reg.ci_lo[i], "ci_hi": reg.ci_hi[i], "p_raw": p_raw[j], "p_fdr": p_fdr[j],
            "n_seasons": n_seasons, "stability": stability, "significant": sig,
        })
    table = (pd.DataFrame(rows)
             .sort_values(["significant", "p_fdr"], ascending=[False, True])
             .reset_index(drop=True))
    return Scorecard(table=table, reg=reg, fdr_alpha=fdr_alpha, stability_min=stability_min)
