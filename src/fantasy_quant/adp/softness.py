"""Phase 6 → cost report wiring — the market-softness credit (2026-07-09).

The Phase-6 scorecard found exactly one **stable, FDR-surviving** ADP bias: prior-season games
played (durability) is under-priced by the crowd — **+14.6 realized VOR per SD** of last year's
games, 100 % sign-stable across 8 DEV seasons. This module turns that finding into the cost
report's *softness credit* (decision 2026-07-09: **credit + net line — the raw projected headline
is never silently moved**):

    credit = (durability exposure of YOUR roster − benchmark's) × coef

* **Exposure** is the sum over a roster's offensive players of the z-scored trait, standardized by
  the *frozen DEV-panel* μ/σ — the same scale the regression coefficient was estimated on, so
  "exposure × coef" is unit-honest (VOR points).
* A **positive** credit means your preferences tilted you toward the under-priced trait — history
  says the raw projected cost *overstates* what those preferences will really cost. Negative means
  your roster is more fragile than the benchmark and the raw cost understates.
* The credit is a **historical-bias estimate, not a projection** — it rides with its bootstrap CI
  and is reported as a separate line under the untouched headline.

The signal is **frozen with provenance** below; ``signals_from_scorecard`` regenerates it and the
Phase-6 step script asserts the frozen numbers still match the data (drift check).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from fantasy_quant.adp.panel import _prior_features
from fantasy_quant.backtest.scoring import RuleSet

OFFENSE = ("QB", "RB", "WR", "TE")


@dataclass(frozen=True)
class SoftnessSignal:
    """One stable ADP bias, ready to price a roster's exposure. ``coef`` is realized-VOR-alpha per
    SD of the raw trait; ``mu``/``sd`` are the DEV-panel moments that define that SD (the
    regression's own standardization — never recompute them on a new season)."""
    term: str                   # the raw panel column (e.g. "prior_games")
    label: str
    coef: float                 # VOR per SD (season-block-bootstrap pooled estimate)
    ci_lo: float
    ci_hi: float
    p_fdr: float
    stability: float
    mu: float                   # DEV-panel mean of the raw trait
    sd: float                   # DEV-panel std (ddof=0), matching regression.prepare
    fitted_on: str              # provenance


# The one survivor of the 2026-07-08 scorecard (BH-FDR α=0.05 + ≥60 % sign stability), refit and
# frozen 2026-07-09 with n_boot=5000 on the 1,504-row DEV panel. steps/phase6_adp_bias.py asserts
# these numbers against a fresh recompute — if the data moves, the drift check fails loudly.
DURABILITY = SoftnessSignal(
    term="prior_games", label="durability (prior-yr games)",
    coef=14.5856, ci_lo=11.3604, ci_hi=20.9767, p_fdr=0.0010, stability=1.00,
    mu=10.5665, sd=6.3706,
    fitted_on="DEV 2014-2022, 1504 drafted offense players (scorecard 2026-07-08)",
)
STABLE_BIASES: tuple[SoftnessSignal, ...] = (DURABILITY,)


def signals_from_scorecard(scorecard, panel: pd.DataFrame) -> tuple[SoftnessSignal, ...]:
    """Regenerate :class:`SoftnessSignal` objects from a fresh Phase-6 scorecard + its panel — the
    drift-check counterpart of the frozen constants."""
    out = []
    for r in scorecard.significant.itertuples(index=False):
        raw = r.term.removeprefix("z_")
        out.append(SoftnessSignal(
            term=raw, label=r.label, coef=float(r.coef), ci_lo=float(r.ci_lo),
            ci_hi=float(r.ci_hi), p_fdr=float(r.p_fdr), stability=float(r.stability),
            mu=float(panel[raw].mean()), sd=float(panel[raw].std(ddof=0)),
            fitted_on=f"recomputed on {panel['season'].nunique()} DEV seasons, {len(panel)} rows",
        ))
    return tuple(out)


# ------------------------------------------------------------------------------------------------
# roster exposure + the credit (pure given the trait map)
# ------------------------------------------------------------------------------------------------
def prior_trait_map(con, season: int, ruleset: RuleSet | None = None) -> dict[str, float]:
    """PIT trait values for pricing ``season``'s rosters: prior-season games per gsis_id (fully
    known before the draft; reuses the Phase-6 panel's own feature builder)."""
    prev = _prior_features(con, season, ruleset)
    return dict(zip(prev["gsis_id"], prev["prior_games"].astype(float), strict=False))


def roster_exposure(roster: pd.DataFrame, trait_map: dict[str, float],
                    signal: SoftnessSignal) -> float:
    """A roster's summed z-exposure to ``signal`` over its offensive players (SD units).

    Players with no prior-season line (rookies) take the panel's own convention — raw trait 0 —
    so exposure is computed exactly as the regression saw the world."""
    off = roster[roster["pos"].isin(OFFENSE)] if "pos" in roster.columns else roster
    z = [(trait_map.get(pk, 0.0) - signal.mu) / signal.sd for pk in off["player_key"]]
    return float(sum(z))


def softness_credit(pers_rosters: list[pd.DataFrame], bench_rosters: list[pd.DataFrame],
                    trait_map: dict[str, float],
                    signals: tuple[SoftnessSignal, ...] = STABLE_BIASES) -> pd.DataFrame:
    """The credit table: per stable bias, the personalized-vs-benchmark exposure gap (mean over the
    paired drafts) × the frozen coefficient, with the coefficient's CI carried through.

    Positive ``credit_points`` = your preferences tilted toward the under-priced trait — the raw
    projected cost overstates the real cost by ≈ this much (historical-bias estimate).
    """
    rows = []
    for sig in signals:
        e_pers = sum(roster_exposure(r, trait_map, sig) for r in pers_rosters) / len(pers_rosters)
        e_bench = (sum(roster_exposure(r, trait_map, sig) for r in bench_rosters)
                   / len(bench_rosters))
        delta = e_pers - e_bench
        rows.append({
            "label": sig.label, "exposure_yours": e_pers, "exposure_bench": e_bench,
            "delta_sd": delta, "credit_points": delta * sig.coef,
            "credit_lo": delta * (sig.ci_lo if delta >= 0 else sig.ci_hi),
            "credit_hi": delta * (sig.ci_hi if delta >= 0 else sig.ci_lo),
        })
    return pd.DataFrame(rows, columns=["label", "exposure_yours", "exposure_bench", "delta_sd",
                                       "credit_points", "credit_lo", "credit_hi"])
