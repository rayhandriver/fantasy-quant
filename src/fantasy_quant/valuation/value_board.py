"""Phase 4.2 — the VBD value board (the reframe's value signal, and the CONTRACT Phase 5 wraps).

Turns the consensus mean (4.1) into a **draftable, cross-position value board**: subtract the
positional replacement level (1.4) to get VBD, then rank within position and overall. This is the
single value-side object the personalization optimizer maximizes and the distribution layer (Phase
5) wraps — so its **output shape is a frozen contract**:

    player_key · pos · proj_points · source · vbd · pos_rank · overall_rank

``source`` records the mean's provenance per row (``consensus`` live board · ``proxy`` historical
baseline · ``rookie`` the 4.3 model) so a downstream consumer never guesses. Rookies absent from
the mean are filled by :func:`fantasy_quant.projections.rookie.rookie_projection` (Phase 4.3) rather
than dropped to ADP. Offense + K are covered; team defenses (no consensus board) stay on ADP in the
draft, exactly as the Phase-1 harness already handles them.
"""

from __future__ import annotations

import pandas as pd

from fantasy_quant.backtest.metrics import ReplacementLevels, replacement_ranks
from fantasy_quant.backtest.scoring import RuleSet
from fantasy_quant.draft.simulator import RosterSlots, canon_pos
from fantasy_quant.projections.consensus import consensus_projection, has_consensus
from fantasy_quant.valuation.vbd import vbd

CONTRACT_COLS = ["player_key", "pos", "proj_points", "source", "vbd", "pos_rank", "overall_rank"]


def projection_replacement(board: pd.DataFrame, slots: RosterSlots | None = None,
                           n_teams: int = 10) -> ReplacementLevels:
    """Replacement levels from **projected** points (draft-time VBD), not realized.

    The Phase-1.4 :func:`replacement_levels` reads realized season points — unavailable for a season
    being drafted. So for the forward board, replacement = the projected points at each position's
    replacement rank (QB10/RB24/… via :func:`replacement_ranks`). Positions absent from the board
    (e.g. DST) get level 0, so they contribute no VBD and stay on ADP. ``board`` needs ``cpos``.
    """
    ranks = replacement_ranks(slots or RosterSlots(), n_teams)
    by_pos = {}
    for pos, rank in ranks.items():
        vals = (board.loc[board["cpos"] == pos, "proj_points"]
                .sort_values(ascending=False).to_numpy())
        level = float(vals[min(rank - 1, len(vals) - 1)]) if len(vals) else 0.0
        by_pos[pos] = {"rank": rank, "level": level}
    return ReplacementLevels(by_pos, 0.0, n_teams)


def _rank_and_seal(board: pd.DataFrame) -> pd.DataFrame:
    """Add within-position and overall ranks (by VBD, higher = better) and freeze the contract cols.

    Pure over an already-valued frame (``player_key, pos, proj_points, source, vbd``) — the
    unit-test target for the board's shape and ordering.
    """
    out = board.drop_duplicates("player_key").copy()
    out["pos_rank"] = out.groupby("cpos")["vbd"].rank(ascending=False, method="first").astype(int)
    out["overall_rank"] = out["vbd"].rank(ascending=False, method="first").astype(int)
    out = out.sort_values("overall_rank").reset_index(drop=True)
    return out[CONTRACT_COLS]


def value_board(con, season: int, as_of=None, ruleset: RuleSet | None = None,
                slots: RosterSlots | None = None, n_teams: int = 10,
                rookie_fn=None) -> pd.DataFrame:
    """The canonical projection→VBD value board for ``season`` (contract in the module docstring).

    The mean is the two-track :func:`consensus_projection`; ``rookie_fn(con, season, as_of)`` (Phase
    4.3, injected to avoid an import cycle) fills rookies the mean misses. VBD subtracts the 1.4
    positional replacement; ranks are by VBD within position and overall.
    """
    ruleset = ruleset or RuleSet()
    mean = consensus_projection(con, season, as_of, ruleset).copy()
    mean["source"] = "consensus" if has_consensus(con, season) else "proxy"

    if rookie_fn is not None:
        rk = rookie_fn(con, season, as_of)
        if rk is not None and not rk.empty:
            rk = rk.copy()
            rk["source"] = "rookie"
            # keep the mean where it already covers a player; add only rookies it's missing.
            new = rk[~rk["player_key"].isin(set(mean["player_key"]))]
            mean = pd.concat([mean, new[["player_key", "pos", "proj_points", "source"]]],
                             ignore_index=True)

    # a 0-point projection is a listed body with no real forecast -> no value signal.
    mean = mean.dropna(subset=["proj_points"]).query("proj_points > 0").copy()
    mean["cpos"] = mean["pos"].map(canon_pos).fillna(mean["pos"])
    repl = projection_replacement(mean, slots, n_teams)   # draft-time (projected) replacement
    valued = vbd(mean, repl)
    return _rank_and_seal(valued)
