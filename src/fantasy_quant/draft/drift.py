"""Phase 16.12 — consuming the availability-side drift signal.

Phase 16's availability track produced, in order: a drift model that **does not predict**
(16.8, once the sibling-derived leak was ablated away), a correlated narrative shock that is
**unidentified** and cannot move a player into the candidate set at all (16.9), a **curated**
hype board that no backtest supports (16.10), and a live momentum series that is
**structurally unbacktestable** because no historical intra-season ADP exists (16.11).

This module is what honest consumption of that looks like. It wires the two live channels into
the three places the user asked for — mock-room realism, opt-in pick advice, and an app readout —
under one rule: **every drift channel is off by default, and `DriftConfig()` is a provable no-op.**
:func:`~fantasy_quant.draft.optimizer.build_risk_model` with no hype reproduces the frozen greedy
bit-for-bit, and `tests/test_drift_consumption.py` fails if that ever stops being true. The same
"kept, not default" treatment as Phase 7, the props layer, the 13.2 win-tilt and the 16.9 shock.

**Units are picks, everywhere, and the sign convention never changes:** ``+1`` means *the room
takes him one pick EARLIER than the consensus board says*, matching 16.7's ``drift`` through
16.10's ``pick_delta`` and on to the utility offset. Two consumers want two different projections
of that one quantity, so both are provided from a single source:

* :func:`drift_utility` — pick-space → **opponent utility**, through the fitted model's own
  ``adp_s`` coefficient. This is the 16.9 channel, and it drives mock-draft realism.
* :func:`drift_adp` — pick-space → an **effective ADP**, which is what a survival/lookahead
  consumer needs (a hyped player is likelier to be gone by your next turn).

**What the drift channel actually buys, measured (16.10).** One claimed pick produces well under
one pick of realized movement — ADP is only one term in the fitted utility and ``top_k`` is a hard
rank filter applied before it. Treat a curated row as a nudge, not a repricing, and never surface
``pick_delta`` to a user as if it were a predicted change in draft slot.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from fantasy_quant.adp.hype_board import HYPE_CSV, hype_deltas, load_hype_board
from fantasy_quant.draft.opponent_model import _ADP_SCALE

#: Picks of effective-ADP shift per (round/week) of 16.11 velocity, when momentum is switched on.
#: There is no fitted value for this and there cannot be one — momentum is forward-only — so it is
#: a declared judgment sitting on an off-by-default switch, not a calibration.
DEFAULT_MOMENTUM_W = 4.0

#: Below this |p_available| a player is flagged as unlikely to reach your next pick.
REACH_RISK_GONE = 0.25
REACH_RISK_SAFE = 0.60


@dataclass(frozen=True)
class DriftConfig:
    """Which drift channels are live. **All default off** — the constructed default is a no-op.

    ``hype`` applies the curated 16.10 board (and still honours its review gate: an unsigned board
    contributes nothing even with ``hype=True``). ``momentum_w`` scales the live 16.11 velocity
    into picks; ``0`` disables it.
    """
    hype: bool = False
    momentum_w: float = 0.0
    require_reviewed: bool = True
    hype_path: Path = HYPE_CSV

    @property
    def enabled(self) -> bool:
        return bool(self.hype) or abs(self.momentum_w) > 0

    def describe(self) -> dict:
        """Provenance, for anything that surfaces a drift-adjusted number to a human. A curated,
        unbacktested adjustment must never reach a user without saying so."""
        return {
            "enabled": self.enabled,
            "hype_board": bool(self.hype),
            "momentum_w": float(self.momentum_w),
            "backtested": False,
            "caveat": "curated / forward-only inputs: 16.8 found no per-player drift signal and "
                      "16.9 could not identify a shock size; these channels are opt-in and "
                      "default off",
        }


def drift_picks(board: pd.DataFrame, *, cfg: DriftConfig | None = None, season: int | None = None,
                con=None, velocity: pd.DataFrame | None = None,
                key: str = "player_key") -> np.ndarray:
    """Total drift per board row, **in picks**, positive = taken earlier. Zero everywhere when
    ``cfg`` is the default, which is the property the whole module rests on.

    ``velocity`` may be passed directly (the 16.11 frame) or fetched via ``con``/``season``.
    """
    cfg = NO_DRIFT if cfg is None else cfg
    out = np.zeros(len(board))
    if not cfg.enabled:
        return out

    if cfg.hype:
        hype = load_hype_board(cfg.hype_path, season, require_reviewed=cfg.require_reviewed)
        out = out + hype_deltas(board, hype, key=key)

    if abs(cfg.momentum_w) > 0:
        if velocity is None and con is not None and season is not None:
            from fantasy_quant.adp.momentum import adp_velocity
            velocity = adp_velocity(con, season)
        if velocity is not None and not velocity.empty:
            # velocity_shrunk, never the raw slope: three snapshots give one residual degree of
            # freedom per player, and the unshrunk spread is mostly sampling noise.
            lut = dict(zip(velocity["gsis_id"].astype(str),
                           velocity["velocity_shrunk"].astype(float), strict=False))
            ids = board[key].astype(str).to_numpy()
            out = out + cfg.momentum_w * np.array([lut.get(i, 0.0) for i in ids])
    return out


def drift_utility(board: pd.DataFrame, *, beta_adp_s: float, **kw) -> np.ndarray:
    """Drift as an **opponent-utility offset** — the 16.9 channel, for mock-draft realism.

    Converted through the fitted model's own ADP coefficient so "three picks early" means exactly
    what it would have meant had his ADP been three picks lower, and so the units follow
    automatically if 11.1 is ever refit.
    """
    return -float(beta_adp_s) * drift_picks(board, **kw) / _ADP_SCALE


def drift_adp(board: pd.DataFrame, *, adp_col: str = "adp", **kw) -> np.ndarray:
    """Drift as an **effective ADP** — what a survival / 9.4-lookahead consumer needs."""
    adp = pd.to_numeric(board[adp_col], errors="coerce").to_numpy(float)
    return adp - drift_picks(board, **kw)


# ------------------------------------------------------------------------------------------------
# 16.12 (c) — the engine-side availability readout the Phase-14 app will render
# ------------------------------------------------------------------------------------------------
def reach_risk_label(p_available: float) -> str:
    """Three honest buckets. Deliberately not a yes/no 'will he fall' — replacing a binary with a
    probability is the entire point of the readout (see `docs/PLAYER-VIEW.md`)."""
    if not np.isfinite(p_available):
        return "unknown"
    if p_available < REACH_RISK_GONE:
        return "likely gone"
    if p_available < REACH_RISK_SAFE:
        return "coin flip"
    return "likely available"


def availability_readout(board: pd.DataFrame, model, *, window_picks: int,
                         cfg: DriftConfig | None = None, season: int | None = None, con=None,
                         velocity: pd.DataFrame | None = None, available: np.ndarray | None = None,
                         n_sims: int = 200, seed: int = 0, top_k: int | None = None,
                         pick0: int | None = None, n_teams: int = 10,
                         key: str = "player_key") -> pd.DataFrame:
    """``P(available at your next pick)`` per board row, with and without drift.

    Built on 11.2's :func:`~fantasy_quant.draft.availability.simulate_survival` — the *validated*
    availability oracle (it beats a best-tuned ADP+noise baseline on real Sleeper windows) — rather
    than on the crude ``survival_prob`` placeholder. ``window_picks`` is how many opponent picks
    fall before your next turn.

    Returns both ``p_available`` (drift-adjusted, if ``cfg`` enables anything) and
    ``p_available_baseline``, because the honest presentation of an unbacktested adjustment is the
    pair, not the adjusted number alone. ``drift_picks``/``reach_risk`` complete the
    `docs/PLAYER-VIEW.md` contract.
    """
    from fantasy_quant.draft.availability import simulate_survival
    from fantasy_quant.draft.opponent_model import CHOICE_TOP_K

    cfg = NO_DRIFT if cfg is None else cfg

    # T15: take the candidate set from the fitted model's own band. Pinning CHOICE_TOP_K here
    # regardless of what the model was fit on is the Session-G fit/use mismatch — it was harmless
    # only while every band was the same fixed 40. An explicit `top_k` still overrides.
    band = getattr(model, "band", None) if top_k is None else None
    if top_k is None and band is None:
        top_k = CHOICE_TOP_K
    cand = board[[c for c in ("adp", "pos", "team", "rookie") if c in board.columns]].copy()
    if available is None:
        available = np.ones(len(board), bool)
    seat_plan = [{} for _ in range(max(int(window_picks), 0))]

    def _survive(c: pd.DataFrame) -> np.ndarray:
        if not seat_plan:
            return np.ones(len(c))          # no intervening picks -> everyone survives
        return simulate_survival(c, available.copy(), seat_plan, model, n_sims=n_sims,
                                 rng=np.random.default_rng(seed), top_k=top_k, band=band,
                                 pick0=pick0, n_teams=n_teams)

    base = _survive(cand)
    picks = drift_picks(board, cfg=cfg, season=season, con=con, velocity=velocity, key=key)
    if cfg.enabled and np.any(picks != 0):
        shifted = cand.copy()
        shifted["adp"] = pd.to_numeric(cand["adp"], errors="coerce").to_numpy(float) - picks
        adj = _survive(shifted)
    else:
        adj = base

    out = pd.DataFrame({
        key: board[key].to_numpy() if key in board.columns else np.arange(len(board)),
        "pos": board["pos"] if "pos" in board.columns else None,
        "adp": pd.to_numeric(board["adp"], errors="coerce").to_numpy(float),
        "drift_picks": picks,
        "p_available": adj,
        "p_available_baseline": base,
    })
    out["p_available_delta"] = out["p_available"] - out["p_available_baseline"]
    out["reach_risk"] = [reach_risk_label(p) for p in out["p_available"]]
    # a flag rather than a silent number: this row's advice moved on an unbacktested input
    out["drift_material"] = (out["p_available_delta"].abs() >= 0.05) & (out["drift_picks"] != 0)
    return out


#: The all-off configuration, as a module-level singleton so it can serve as an argument default.
#: Every consumer that takes a ``cfg`` falls back to this, which is what makes "drift is opt-in" a
#: property of the code rather than a convention each caller has to remember.
NO_DRIFT = DriftConfig()
