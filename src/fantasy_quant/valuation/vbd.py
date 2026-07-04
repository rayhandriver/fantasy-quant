"""Phase 2.1 — Value-Based Drafting (VBD): projected points → draftable cross-position value.

A QB projected for 320 points and an RB for 220 aren't directly comparable at the draft table — you
draft the one whose points are scarcest *above the freely-available replacement* at his position.
VBD = projected points − positional replacement level (1.4). This module computes VBD and adapts
**any projection into a harness `rank_fn`** (:func:`vbd_rank_fn`), so a projection method backtests
through Phase 1 with a one-line wrap. Projections cover who they can; everyone else (rookies, DST,
the unprojected) falls back to ADP.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from fantasy_quant.backtest.metrics import ReplacementLevels, replacement_levels
from fantasy_quant.backtest.walkforward import RankFn
from fantasy_quant.draft.simulator import RosterSlots, canon_pos


def board_key(board: pd.DataFrame) -> pd.Series:
    """The join key a projection uses to line up with the draft board: gsis_id where present
    (offense/K), else the ADP name (team defenses carry no gsis)."""
    gsis = board["gsis_id"] if "gsis_id" in board.columns else pd.Series(pd.NA, index=board.index)
    name = board["name"] if "name" in board.columns else board.get("player_name")
    return gsis.where(gsis.notna(), name)


def vbd(proj: pd.DataFrame, replacement: ReplacementLevels) -> pd.DataFrame:
    """Add a ``vbd`` column = ``proj_points`` − replacement level for the row's canonical position.

    ``proj`` needs ``pos`` (canonical or FFC) and ``proj_points``. Positions without a replacement
    level (shouldn't happen for QB/RB/WR/TE/K/DST) get 0.
    """
    out = proj.copy()
    cpos = out["pos"].map(canon_pos).fillna(out["pos"])
    out["vbd"] = out["proj_points"] - cpos.map(
        lambda p: replacement.level(p) if p in replacement.by_pos else 0.0)
    return out


def replacement_baseline(con, season: int, slots: RosterSlots | None = None, n_teams: int = 10,
                         ruleset=None) -> ReplacementLevels:
    """The per-position replacement levels VBD subtracts (thin re-export of 1.4's, so callers import
    it from the valuation layer)."""
    return replacement_levels(con, season, slots, n_teams, ruleset)


def vbd_rank_fn(projection_fn: Callable, slots: RosterSlots | None = None,
                n_teams: int = 10) -> RankFn:
    """Wrap a projection into a harness ``rank_fn``: rank the board by VBD (higher = sooner).

    ``projection_fn(con, season, as_of)`` returns a frame with ``player_key`` (gsis, or the ADP name
    for DST), ``pos`` and ``proj_points``. Board rows the projection doesn't cover get NaN → the
    harness's ``value_pick_fn`` falls back to their ADP. VBD ranks are on the pick-number scale, so
    they interleave sensibly with the ADP fallbacks.
    """
    def rank_fn(board: pd.DataFrame, con=None, season=None, as_of=None) -> pd.Series:
        proj = projection_fn(con, season, as_of)
        if proj is None or proj.empty:
            return pd.to_numeric(board["adp"], errors="coerce")
        repl = replacement_levels(con, season, slots, n_teams)
        proj = vbd(proj, repl)
        vbd_by_key = (proj.dropna(subset=["player_key"]).drop_duplicates("player_key")
                      .set_index("player_key")["vbd"])
        board_vbd = board_key(board).map(vbd_by_key)
        # higher VBD -> lower (sooner) draft value; unprojected rows stay NaN (ADP fallback).
        return (-board_vbd).rank(method="first")

    return rank_fn
