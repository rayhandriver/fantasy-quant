"""Phase 10.3 — variance as a lever, given the standings (DFS-GPP leverage, season-long).

The classic result the engine must reproduce (the done-bar): a **trailing** team should add
variance — it needs tail outcomes to reach the playoffs at all, and a fatter right tail buys
more title probability than the fatter left tail costs; a **favorite** should cut variance and
protect its lead. The lever here is a mean-preserving spread on a team's remaining weekly
score distribution (``scale`` < 1 tightens, > 1 widens; clipped at 0, a documented edge
effect); Phase 13 maps the recommendation to actual moves (stack/handcuff/boom-bust starts).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.simulation.season import LeagueFormat, simulate_league

DEFAULT_SCALES = (0.6, 0.8, 1.0, 1.2, 1.4)


def scale_team_spread(team_weekly: np.ndarray, team: int, scale: float,
                      start_week: int = 0) -> np.ndarray:
    """Mean-preserving spread on ``team``'s weekly draws from ``start_week`` on: each week's
    cross-sim mean is fixed, deviations scale by ``scale`` (floored at 0)."""
    out = np.array(team_weekly, float, copy=True)
    x = out[team, :, start_week:]
    mu = x.mean(axis=0, keepdims=True)
    out[team, :, start_week:] = np.clip(mu + scale * (x - mu), 0.0, None)
    return out


def variance_leverage(team_weekly: np.ndarray, fmt: LeagueFormat, schedule: np.ndarray,
                      team: int, scales=DEFAULT_SCALES, start_week: int = 0,
                      wins0: np.ndarray | None = None,
                      pf0: np.ndarray | None = None) -> pd.DataFrame:
    """Title/playoff probability for ``team`` as a function of its variance ``scale``
    (optionally conditional on a mid-season state via ``start_week``/``wins0``/``pf0``)."""
    rows = []
    for s in scales:
        sim = simulate_league(scale_team_spread(team_weekly, team, s, start_week),
                              fmt, schedule, start_week=start_week, wins0=wins0, pf0=pf0)
        rows.append({"scale": float(s), "title_prob": float(sim.title_prob[team]),
                     "playoff_prob": float(sim.playoff_prob[team])})
    return pd.DataFrame(rows)


def leverage_advice(team_weekly: np.ndarray, fmt: LeagueFormat, schedule: np.ndarray,
                    team: int, start_week: int = 0, wins0: np.ndarray | None = None,
                    pf0: np.ndarray | None = None, scales=DEFAULT_SCALES,
                    min_edge: float = 0.005) -> dict:
    """The 10.3 deliverable: given the (possibly mid-season) state, should ``team`` add or cut
    variance? Returns the full curve plus a verdict — ``add``/``cut`` when the best scale beats
    the status quo by ``min_edge`` of title probability, else ``hold``."""
    scales = sorted({*map(float, scales), 1.0})  # the status quo is always on the curve
    curve = variance_leverage(team_weekly, fmt, schedule, team, scales, start_week, wins0, pf0)
    base = float(curve.loc[np.isclose(curve["scale"], 1.0), "title_prob"].iloc[0])
    best = curve.loc[curve["title_prob"].idxmax()]
    if best["title_prob"] - base < min_edge:
        verdict = "hold"
    else:
        verdict = "add variance" if best["scale"] > 1.0 else "cut variance"
    return {"curve": curve, "verdict": verdict, "best_scale": float(best["scale"]),
            "title_prob_base": base, "title_prob_best": float(best["title_prob"])}
