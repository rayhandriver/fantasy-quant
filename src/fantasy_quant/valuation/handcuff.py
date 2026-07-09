"""Phase 8.5 — the handcuff as a real option (a contingent claim on the starter's health).

A backup RB's draft-day worth is mostly *optionality*: near-worthless while the starter plays,
lead-back value when he doesn't. Pricing that as a plain projection buries the asymmetry the 8.3
copula quantified. The real-option form (BUILD_PLAN):

    E[backup season] = G · [ (1 − p_out) · ppg_standalone  +  p_out · ppg_elevated ]

* ``p_out`` — the fraction of games the **starter** misses, straight from the 5.4 availability
  hazard (fragile starter ⇒ richer option).
* ``ppg_elevated = ppg_standalone × elevation ratio`` — how much a backup's scoring multiplies when
  the starter sits, pooled across every RB1/RB2 backfield in the training seasons (the 8.3
  zero-filled pair grid, so the estimate carries the real payoff structure).

The **option premium** — ``G · p_out · ppg_standalone · (ratio − 1)`` — is the number a draft
narrative wants: how much of this backup's value exists *only because* his starter might miss time.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


# ------------------------------------------------------------------------------------------------
# the pooled elevation ratio (estimated once on training seasons)
# ------------------------------------------------------------------------------------------------
def elevation_stats(pairs: pd.DataFrame, min_out_weeks: int = 30) -> dict:
    """Pooled backup scoring with the starter in vs out, from 8.3's zero-filled
    :func:`~fantasy_quant.covariance.copula.handcuff_pairs` frame.

    Returns ``ppg_with`` / ``ppg_without`` (backup points per team game, zero-filled — the backup's
    own missed weeks count as 0 in both regimes, symmetric), ``ratio`` and week counts. Falls back
    to ratio 1 when the sample is too thin to say anything.
    """
    if pairs.empty:
        return {"ppg_with": 0.0, "ppg_without": 0.0, "ratio": 1.0,
                "n_weeks_with": 0, "n_weeks_without": 0}
    active = pairs[pairs["starter_active"]]
    out = pairs[~pairs["starter_active"]]
    ppg_with = float(active["backup_pts"].mean()) if len(active) else 0.0
    ppg_without = float(out["backup_pts"].mean()) if len(out) else 0.0
    thin = len(out) < min_out_weeks or ppg_with <= 0
    return {"ppg_with": ppg_with, "ppg_without": ppg_without,
            "ratio": 1.0 if thin else ppg_without / ppg_with,
            "n_weeks_with": int(len(active)), "n_weeks_without": int(len(out))}


# ------------------------------------------------------------------------------------------------
# the option pricing (pure)
# ------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class HandcuffValue:
    """A priced handcuff. ``standalone_ev`` is the backup with the starter always healthy;
    ``contingent_ev`` folds in the starter's absence risk; ``option_premium`` is the difference —
    the part of the backup's value that is pure insurance."""
    p_starter_out: float
    ppg_standalone: float
    ppg_elevated: float
    games: float
    standalone_ev: float
    contingent_ev: float
    option_premium: float


def handcuff_value(p_starter_out: float, ppg_standalone: float, elevation_ratio: float,
                   games: float = 17.0) -> HandcuffValue:
    """Price the backup as a contingent claim (module docstring formula).

    ``p_starter_out`` ∈ [0,1] — expected fraction of games the starter misses (1 − his 5.4
    availability); ``ppg_standalone`` — the backup's points per game with the starter active;
    ``elevation_ratio`` — the pooled multiplier from :func:`elevation_stats`.
    """
    p = float(np.clip(p_starter_out, 0.0, 1.0))
    ppg_elev = float(ppg_standalone) * float(elevation_ratio)
    standalone = float(games) * float(ppg_standalone)
    contingent = float(games) * ((1.0 - p) * float(ppg_standalone) + p * ppg_elev)
    return HandcuffValue(
        p_starter_out=p, ppg_standalone=float(ppg_standalone), ppg_elevated=ppg_elev,
        games=float(games), standalone_ev=standalone, contingent_ev=contingent,
        option_premium=contingent - standalone,
    )
