"""Phase 11.2 — MCTS draft engine: pure/synthetic unit tests (no DB/network).

Mechanics only — the *empirical* claim (does search beat the greedy?) is the job of the
`steps/phase11_2_mcts.py` gate on real DEV seasons. Here we check that the search is well-formed:
it returns a legal top-K pick, is reproducible, collapses to the greedy at ``k=1``, fills a roster
legally without mutating the live draft, and — the one behavioural check — **follows the leaf
value function even when it disagrees with the myopic greedy's ordering** (that's the whole point of
searching)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.covariance.shrinkage import neutral_model
from fantasy_quant.draft.config import DraftConfig, LeagueSetup
from fantasy_quant.draft.mcts import _top_k_candidates, mcts_pick, mcts_pick_fn
from fantasy_quant.draft.optimizer import (
    attach_value,
    build_risk_model,
    personalized_pick_fn,
    team_value,
)
from fantasy_quant.draft.simulator import (
    DRAFTABLE,
    DraftState,
    RosterSlots,
    _prepare_board,
)

UNCAPPED = RosterSlots(pos_caps=dict.fromkeys(DRAFTABLE, 99))
_POS_CYCLE = ["RB", "WR", "RB", "WR", "TE", "QB"]


def _board_and_vi(n: int = 40):
    """A synthetic ADP board + value index: base_value descends with ADP (so the greedy's order is
    ADP order), each player on their own team (no covariance cross-terms)."""
    board = pd.DataFrame([
        {"name": f"P{i}", "position": _POS_CYCLE[i % len(_POS_CYCLE)], "adp": float(i + 1),
         "pos_rank": i + 1, "gsis_id": f"p_{i}"} for i in range(n)])
    vi = pd.DataFrame({
        "player_key": [f"p_{i}" for i in range(n)],
        "pos": [_POS_CYCLE[i % len(_POS_CYCLE)] for i in range(n)],
        "team": [f"T{i}" for i in range(n)],
        "role_rank": [1] * n,
        "mean": [200.0 - i for i in range(n)], "sd": [30.0] * n,
        "base_value": [float(100 - i) for i in range(n)],
    })
    return board, vi


def _state(board_valued, n_teams=6, rounds=5, seat=0, slots=None):
    b = _prepare_board(board_valued)
    return DraftState(board=b, n_teams=n_teams, rounds=rounds, slots=slots or RosterSlots(bench=0),
                      your_team=seat, rng=np.random.default_rng(0), noise=5.0,
                      available=set(b.index), rosters=[[] for _ in range(n_teams)])


def _risk(board_valued, vi, lam=0.0, scarcity_w=0.0):
    return build_risk_model(board_valued, vi, neutral_model(), lam=lam, scarcity_w=scarcity_w,
                            noise=5.0)


def test_mcts_returns_legal_top_k_pick():
    board, vi = _board_and_vi()
    bv = attach_value(board, vi)
    cfg = DraftConfig(league=LeagueSetup(draft_slot=1, n_teams=6))
    st = _state(bv)
    risk = _risk(bv, vi)
    value_fn = lambda r: team_value(r, vi)  # noqa: E731
    top_k = _top_k_candidates(st, cfg, risk, k=5)
    pick = mcts_pick(st, cfg, risk, value_fn, n_iter=40, k=5,
                     rng=np.random.default_rng(7))
    assert pick in st.available                       # legal
    assert pick in top_k                              # the search only branches over top-K


def test_mcts_reproducible_under_same_seed():
    board, vi = _board_and_vi()
    bv = attach_value(board, vi)
    cfg = DraftConfig(league=LeagueSetup(draft_slot=1, n_teams=6))
    risk = _risk(bv, vi)
    value_fn = lambda r: team_value(r, vi)  # noqa: E731
    a = mcts_pick(_state(bv), cfg, risk, value_fn, n_iter=50, k=5, rng=np.random.default_rng(3))
    b = mcts_pick(_state(bv), cfg, risk, value_fn, n_iter=50, k=5, rng=np.random.default_rng(3))
    assert a == b                                     # deterministic given the seed


def test_mcts_k1_collapses_to_greedy():
    board, vi = _board_and_vi()
    bv = attach_value(board, vi)
    cfg = DraftConfig(league=LeagueSetup(draft_slot=1, n_teams=6))
    risk = _risk(bv, vi)
    value_fn = lambda r: team_value(r, vi)  # noqa: E731
    st = _state(bv)
    greedy_pick = personalized_pick_fn(cfg, 0.0, risk)(st.clone())
    mcts1 = mcts_pick(st, cfg, risk, value_fn, n_iter=30, k=1, rng=np.random.default_rng(1))
    assert mcts1 == greedy_pick                       # only one candidate → the greedy's pick


def test_mcts_follows_the_leaf_value_over_the_myopic_order():
    """The search's raison d'être: with a value function that rewards rostering ``p_3`` (a *lower*
    base_value than the greedy's #1 pick ``p_0``), MCTS must return ``p_3`` — it optimises the leaf
    value, not the myopic priority. A single-pick draft isolates the choice."""
    board, vi = _board_and_vi(n=12)
    bv = attach_value(board, vi)
    cfg = DraftConfig(league=LeagueSetup(draft_slot=1, n_teams=6))
    risk = _risk(bv, vi)
    st = _state(bv, rounds=1, slots=UNCAPPED)
    greedy_pick = personalized_pick_fn(cfg, 0.0, risk)(st.clone())
    assert st.board.loc[greedy_pick, "player_key"] == "p_0"     # myopic: highest base_value

    # value_fn prefers any roster containing p_3 (which the greedy ranks 4th)
    reward = lambda r: 1.0 if "p_3" in set(r["player_key"]) else 0.0  # noqa: E731
    pick = mcts_pick(st, cfg, risk, reward, n_iter=60, k=5, rng=np.random.default_rng(0))
    assert st.board.loc[pick, "player_key"] == "p_3"            # search overrides the myopic order


def test_mcts_pick_fn_fills_roster_without_mutating_live_draft():
    board, vi = _board_and_vi(n=60)
    bv = attach_value(board, vi)
    cfg = DraftConfig(league=LeagueSetup(draft_slot=3, n_teams=6))
    risk = _risk(bv, vi)
    value_fn = lambda r: team_value(r, vi)  # noqa: E731
    from fantasy_quant.draft.simulator import simulate_draft
    pick_fn = mcts_pick_fn(cfg, risk, value_fn, n_iter=24, k=4, noise=5.0, seed=0)
    res = simulate_draft(bv, your_pick_fn=pick_fn, n_teams=6, rounds=5,
                         slots=RosterSlots(bench=0), your_team=2, noise=5.0, seed=1)
    mine = res.pick_log().query("is_you")
    assert len(mine) == 5                             # my roster fully drafted
    assert mine["player_key"].is_unique               # no player drafted twice
    assert all(len(res.rosters[t]) == 5 for t in range(6))     # every team full
