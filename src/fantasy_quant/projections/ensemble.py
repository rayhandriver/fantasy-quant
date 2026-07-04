"""Phase 2.4 — ensemble-with-market: blend, don't replace (the reliable way to not lose).

The Part-11 lesson: you rarely out-forecast a sharp consensus outright, but you can **blend** your
model with it and shrink toward it by confidence. Here the ensemble blends the baseline-VBD draft
board (2.1/2.2) with the **ADP consensus** — and, once historical props land, the props-implied
board (2.3) drops in as a third component with no code change. Each component's unprojected players
fall back to ADP before blending, so partial coverage degrades to the market rather than dropping
players. Weights are grid-fit through the Phase-1 harness (:func:`fit_weight`).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import pandas as pd

from fantasy_quant.backtest.walkforward import RankFn, rank_by_adp, walk_forward
from fantasy_quant.draft.simulator import RosterSlots
from fantasy_quant.projections.baseline import baseline_projection
from fantasy_quant.valuation.vbd import vbd_rank_fn


def blend_rank_fn(components: Sequence[RankFn], weights: Sequence[float]) -> RankFn:
    """Blend ``rank_fn``s into one by weighting their (ADP-scale) draft priorities. Weights
    are normalized; a component's NaNs (unprojected players) fall back to that board's ADP first."""
    total = float(sum(weights)) or 1.0
    ws = [w / total for w in weights]

    def rank_fn(board: pd.DataFrame, con=None, season=None, as_of=None) -> pd.Series:
        adp = pd.to_numeric(board["adp"], errors="coerce")
        blended = pd.Series(0.0, index=board.index)
        for comp, w in zip(components, ws, strict=False):
            v = pd.to_numeric(comp(board, con, season, as_of), errors="coerce").fillna(adp)
            blended = blended + w * v
        return blended

    return rank_fn


def ensemble_rank_fn(w_baseline: float = 0.5, baseline_fn=None,
                     market_components: Sequence[RankFn] | None = None) -> RankFn:
    """The Phase-2 ensemble: the baseline-VBD board blended with the ADP consensus.

    ``w_baseline`` in [0, 1] is the weight on the model; ``1 - w_baseline`` goes to ADP. Extra
    market components (e.g. props-implied, once available) pass via ``market_components`` and share
    the ADP weight equally.
    """
    base = vbd_rank_fn(baseline_fn or baseline_projection)
    market: list[RankFn] = [rank_by_adp, *(market_components or [])]
    comps = [base, *market]
    w_market = (1 - w_baseline) / len(market)
    return blend_rank_fn(comps, [w_baseline, *([w_market] * len(market))])


def fit_weight(con, seasons: Iterable[int] = range(2014, 2025),
               grid: Sequence[float] = (0.0, 0.25, 0.5, 0.75, 1.0), k_drafts: int = 4,
               n_teams: int = 10, rounds: int = 15, slots: RosterSlots | None = None,
               noise: float = 5.0, seed: int = 0, baseline_fn=None) -> tuple[float, dict]:
    """Grid-search the baseline weight that maximizes pooled starter points through the harness.

    Returns ``(best_w, {w: pooled_mean})``. ``grid`` includes the endpoints, so ``w=0`` is the pure
    ADP component and ``w=1`` the pure baseline — the best-of-grid is therefore ≥ either single
    component by construction. NB: this is a light **in-sample** weight pick on 11 seasons; a proper
    nested cross-validation is Phase 4's discipline.
    """
    pooled = {}
    for w in grid:
        res = walk_forward(con, ensemble_rank_fn(w, baseline_fn), seasons=seasons,
                           k_drafts=k_drafts, n_teams=n_teams, rounds=rounds, slots=slots,
                           noise=noise, seed=seed)
        pooled[w] = res.pooled["mean"]
    best = max(pooled, key=pooled.get)
    return best, pooled
