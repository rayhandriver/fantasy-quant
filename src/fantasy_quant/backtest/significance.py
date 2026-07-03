"""Phase 1.5 — significance (don't declare a winner on noise). The last brick of the harness.

A method that scores 20 PAR above ADP in one season proves nothing — that's within seasonal noise.
This module answers *"is the method − ADP edge real?"* with a **block bootstrap** CI on the
per-season difference series, so autocorrelation across seasons is respected (iid resampling would
understate the uncertainty). The intern-repo ``te_diff_bootstrap`` analog.

  - :func:`block_bootstrap_ci` — the **stationary bootstrap** (Politis–Romano): random-length blocks
    (expected length ≈ n^{1/3}) preserve short-range dependence. ``expected_block=1`` degrades to
    the iid bootstrap, so the two are directly comparable.
  - :func:`compare_to_baseline` — runs a **paired** walk-forward (method and baseline drafted in the
    *same* seeded opponent contexts, so the difference isolates the method), builds the per-season
    mean PAR-difference series, and returns its effect size + 95% CI. Since both sides share the
    season's replacement level, a PAR difference equals a raw starter-points difference (cancels).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from fantasy_quant.backtest.scoring import RuleSet
from fantasy_quant.backtest.walkforward import RankFn, rank_by_adp, walk_forward
from fantasy_quant.draft.simulator import RosterSlots


# --------------------------------------------------------------------------------------------
# the bootstrap (pure, unit-tested)
# --------------------------------------------------------------------------------------------
@dataclass
class BootstrapCI:
    point: float        # the statistic on the observed series
    lo: float           # lower CI bound
    hi: float           # upper CI bound
    mean: float         # bootstrap-distribution mean
    se: float           # bootstrap standard error
    ci: float           # coverage (e.g. 0.95)
    block: int          # expected block length used
    n_boot: int
    n: int              # length of the input series

    @property
    def significant(self) -> bool:
        """The CI excludes 0 (the effect is unlikely to be noise)."""
        return self.lo > 0 or self.hi < 0


def _stationary_bootstrap_index(n: int, block: float, rng: np.random.Generator) -> np.ndarray:
    """One stationary-bootstrap index sample of length ``n`` (wrap-around, geometric blocks)."""
    p = 1.0 / max(block, 1.0)
    idx = np.empty(n, dtype=int)
    i = int(rng.integers(n))
    for t in range(n):
        idx[t] = i
        i = int(rng.integers(n)) if rng.random() < p else (i + 1) % n
    return idx


def block_bootstrap_ci(x, n_boot: int = 10000, expected_block: int | None = None, ci: float = 0.95,
                       statistic: Callable = np.mean, seed: int = 0) -> BootstrapCI:
    """Block-bootstrap CI for ``statistic`` (default the mean) of a time series ``x``.

    Uses the stationary bootstrap with expected block length ≈ ``n**(1/3)`` (override via
    ``expected_block``; ``1`` gives the iid bootstrap). Percentile CI at level ``ci``.
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n == 0:
        raise ValueError("empty series")
    block = expected_block or max(1, int(round(n ** (1 / 3))))
    rng = np.random.default_rng(seed)
    boot = np.array([statistic(x[_stationary_bootstrap_index(n, block, rng)])
                     for _ in range(n_boot)])
    alpha = (1 - ci) / 2
    lo, hi = np.quantile(boot, [alpha, 1 - alpha])
    return BootstrapCI(point=float(statistic(x)), lo=float(lo), hi=float(hi),
                       mean=float(boot.mean()), se=float(boot.std(ddof=1) if n_boot > 1 else 0.0),
                       ci=ci, block=block, n_boot=n_boot, n=n)


# --------------------------------------------------------------------------------------------
# method vs baseline comparison (paired walk-forward)
# --------------------------------------------------------------------------------------------
@dataclass
class Comparison:
    per_season: pd.Series   # season -> mean PAR difference (method - baseline)
    ci: BootstrapCI
    method_mean: float      # pooled mean starter points (method)
    baseline_mean: float    # pooled mean starter points (baseline)

    @property
    def edge(self) -> float:
        return self.ci.point

    def __repr__(self) -> str:
        verdict = "SIGNIFICANT" if self.ci.significant else "not significant"
        return (f"Comparison(edge={self.edge:+.1f} PAR/season, "
                f"95% CI [{self.ci.lo:+.1f}, {self.ci.hi:+.1f}], {verdict})")


def compare_to_baseline(con, method: RankFn, baseline: RankFn = rank_by_adp,
                        seasons: Iterable[int] = range(2014, 2025), k_drafts: int = 10,
                        n_teams: int = 10, rounds: int = 15, slots: RosterSlots | None = None,
                        noise: float = 5.0, seed: int = 0, ruleset: RuleSet | None = None,
                        n_boot: int = 10000) -> Comparison:
    """Is ``method`` better than ``baseline`` (default ADP) across ``seasons``? Runs both through a
    **paired** walk-forward (identical seeds → matched opponents/seats), forms the per-season mean
    PAR-difference series, and bootstraps its 95% CI. Plug a market-implied ``baseline`` (Phase 2.3)
    to test against the sharp market the same way.
    """
    slots = slots or RosterSlots()
    common = dict(seasons=seasons, k_drafts=k_drafts, n_teams=n_teams, rounds=rounds,
                  slots=slots, noise=noise, seed=seed, ruleset=ruleset)
    m = walk_forward(con, method, **common)
    b = walk_forward(con, baseline, **common)
    merged = m.per_draft.merge(b.per_draft, on=["season", "draft", "your_seat"],
                               suffixes=("_m", "_b"))
    merged["diff"] = merged["starter_points_m"] - merged["starter_points_b"]
    per_season = merged.groupby("season")["diff"].mean()
    cires = block_bootstrap_ci(per_season.to_numpy(), n_boot=n_boot, seed=seed)
    return Comparison(per_season=per_season, ci=cires,
                      method_mean=m.pooled["mean"], baseline_mean=b.pooled["mean"])
