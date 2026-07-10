"""Phase 9 — valuation & draft policy: pure/synthetic unit tests (no DB/network).

Covers the four pieces completed in Phase 9:
  - **T6** the shared Monte-Carlo draw cloud (`cached_distribution` memoizes; distinct seeds
    recompute) — so the value the greedy drafts and the value the sim scores can't diverge;
  - **9.1 scarcity** (`positional_cliff`) + **9.4 lookahead** (`survival_prob`) and their combined
    availability-gated urgency actually flipping a pick toward the scarce, vanishing player;
  - the resumable draft (`DraftState.clone` + `run_to_completion`) the win-prob rollout needs;
  - **9.5** the win-probability objective: `league_probabilities` is sane, and `winprob_pick_fn`
    prefers the roster that maximizes the objective's probability over the higher-raw-value pick.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.covariance.shrinkage import neutral_model
from fantasy_quant.draft.config import DraftConfig, LeagueSetup
from fantasy_quant.draft.optimizer import (
    attach_value,
    build_risk_model,
    personalized_pick_fn,
    positional_cliff,
    survival_prob,
    winprob_pick_fn,
)
from fantasy_quant.draft.simulator import (
    DRAFTABLE,
    DraftState,
    RosterSlots,
    _apply_pick,
    _prepare_board,
    adp_pick_fn,
    run_to_completion,
    simulate_draft,
)
from fantasy_quant.projections import distribution
from fantasy_quant.simulation.season import LeagueFormat, league_probabilities
from fantasy_quant.simulation.weekly import WeeklyModel

UNCAPPED = RosterSlots(pos_caps=dict.fromkeys(DRAFTABLE, 99))


# ------------------------------------------------------------------------------------------------
# T6 — one shared draw cloud
# ------------------------------------------------------------------------------------------------
def test_cached_distribution_memoizes_per_seed(monkeypatch):
    calls = []

    def fake_assemble(con, season, ruleset, n_draws, seed, return_games):
        calls.append((season, seed))
        summary = pd.DataFrame({"player_key": ["a"], "pos": ["RB"], "mean": [100.0], "sd": [10.0]})
        return summary, np.full((1, n_draws), float(seed)), np.full((1, n_draws), 17)

    monkeypatch.setattr(distribution, "assemble_distribution", fake_assemble)
    distribution._DIST_CACHE.clear()

    a = distribution.cached_distribution(None, 2022, seed=0)
    b = distribution.cached_distribution(None, 2022, seed=0)
    assert a is b                                    # same object served from cache
    assert calls == [(2022, 0)]                      # underlying assembler ran exactly once
    distribution.cached_distribution(None, 2022, seed=1)
    assert calls == [(2022, 0), (2022, 1)]           # a distinct seed recomputes
    distribution._DIST_CACHE.clear()


# ------------------------------------------------------------------------------------------------
# 9.1 scarcity cliff + 9.4 availability survival (pure)
# ------------------------------------------------------------------------------------------------
def test_positional_cliff_finds_the_steep_tier():
    keys = ["qb1", "qb2", "rb1", "rb2", "rb3", "rb4", "rb5"]
    pos = ["QB", "QB", "RB", "RB", "RB", "RB", "RB"]
    bv = {"qb1": 100.0, "qb2": 10.0,                 # a lone elite QB then a cliff
          "rb1": 100.0, "rb2": 99.0, "rb3": 98.0, "rb4": 97.0, "rb5": 96.0}   # flat RB tier
    cliff = positional_cliff(keys, pos, bv, horizon=3)
    assert cliff[0] > 80                             # qb1: huge drop to the next QB
    assert cliff[2] < 5                              # rb1: fungible, next tier is right there
    assert cliff[6] == 0                             # the last RB has nothing below → 0


def test_survival_prob_directions():
    # window_end = last opponent pick before my next turn
    s = survival_prob([5.0, 30.0], window_end=19.0, noise=5.0)
    assert s[0] < 0.05 and s[1] > 0.95              # ADP 5 gone; ADP 30 safely survives
    assert (survival_prob([5.0, 30.0], window_end=None, noise=5.0) == 1.0).all()  # no next pick


def _scarcity_board():
    """A lone elite QB (steep cliff, low ADP → vanishes) vs a slightly-higher-value RB atop a flat,
    late-ADP tier (fungible, survives)."""
    rows = [{"name": "QB_A", "position": "QB", "adp": 5.0, "pos_rank": 1, "gsis_id": "qb_a"},
            {"name": "QB_B", "position": "QB", "adp": 130.0, "pos_rank": 2, "gsis_id": "qb_b"},
            {"name": "RB_A", "position": "RB", "adp": 30.0, "pos_rank": 1, "gsis_id": "rb_a"}]
    rows += [{"name": f"RB{i}", "position": "RB", "adp": 31.0 + i, "pos_rank": 2 + i,
              "gsis_id": f"rb_{i}"} for i in range(40)]
    board = pd.DataFrame(rows)
    vi = pd.DataFrame({
        "player_key": ["qb_a", "qb_b", "rb_a"] + [f"rb_{i}" for i in range(40)],
        "pos": ["QB", "QB", "RB"] + ["RB"] * 40,
        "team": ["A", "B", "C"] + [f"T{i}" for i in range(40)],
        "role_rank": [1, 1, 1] + [1] * 40,
        "mean": [200.0, 110.0, 201.0] + [200.0 - i for i in range(40)],
        "sd": [40.0] * 43,
        "base_value": [100.0, 10.0, 101.0] + list(np.linspace(100.0, 60.0, 40)),
    })
    return board, vi


def _first_pick(vi, board, scarcity_w):
    cfg = DraftConfig(league=LeagueSetup(draft_slot=1, slots=UNCAPPED))
    b = attach_value(board, vi)
    risk = build_risk_model(b, vi, neutral_model(), lam=0.0, scarcity_w=scarcity_w, noise=5.0)
    res = simulate_draft(b, your_pick_fn=personalized_pick_fn(cfg, 0.0, risk),
                         n_teams=10, rounds=15, slots=UNCAPPED, your_team=0, noise=0.0, seed=1)
    return res.pick_log().query("is_you")["player_key"].iloc[0]


def test_scarcity_lookahead_grabs_the_vanishing_scarce_player():
    board, vi = _scarcity_board()
    assert _first_pick(vi, board, scarcity_w=0.0) == "rb_a"   # value-first: the higher base_value
    assert _first_pick(vi, board, scarcity_w=0.5) == "qb_a"   # scarce + about to vanish → take now


# ------------------------------------------------------------------------------------------------
# resumable draft (clone + run_to_completion) — the win-prob rollout substrate
# ------------------------------------------------------------------------------------------------
_POS_CYCLE = ["RB", "WR", "RB", "WR", "TE", "QB"]


def _simple_board(n: int = 60) -> pd.DataFrame:
    return pd.DataFrame([
        {"name": f"P{i}", "position": _POS_CYCLE[i % len(_POS_CYCLE)], "adp": float(i + 1),
         "pos_rank": i + 1, "gsis_id": f"p_{i}"} for i in range(n)])


def test_clone_isolates_and_run_to_completion_fills_rosters():
    b = _prepare_board(_simple_board())
    state = DraftState(board=b, n_teams=6, rounds=5, slots=RosterSlots(bench=0), your_team=0,
                       rng=np.random.default_rng(0), noise=5.0, available=set(b.index),
                       rosters=[[] for _ in range(6)])
    # take a few picks, then clone and finish only the clone
    for _ in range(3):
        idx = adp_pick_fn(state)
        _apply_pick(state, state.team_on_clock(), idx)
    snapshot_avail = set(state.available)
    clone = state.clone(np.random.default_rng(1))
    run_to_completion(clone, adp_pick_fn)
    assert state.available == snapshot_avail                 # original untouched by the rollout
    assert clone.is_done() and len(clone.available) < len(snapshot_avail)
    assert all(len(clone.rosters[t]) == 5 for t in range(6))  # every team fully drafted


# ------------------------------------------------------------------------------------------------
# 9.5 win-probability objective
# ------------------------------------------------------------------------------------------------
# 4-of-6 playoff format: not everyone advances, so playoff_prob actually differentiates rosters
FMT_4OF6 = LeagueFormat(n_teams=6, playoff_teams=4, playoff_weeks=(15, 16), first_round_byes=0)


def _model_with_star() -> WeeklyModel:
    """A WeeklyModel where 'p_9' (star) scores ~24/wk and 'p_8' (freq) ~7/wk; everyone else routes
    to the replacement constant. Player positions match ``_simple_board`` (p_9 WR, p_8 RB)."""
    rng = np.random.default_rng(4)
    summary = pd.DataFrame({
        "player_key": ["p_9", "p_8"], "pos": ["WR", "RB"], "team": ["A", "B"],
        "role_rank": [1, 1], "mean": [400.0, 120.0], "sd": [30.0, 20.0], "wk_cov": [0.4, 0.5],
    })
    samples = np.vstack([rng.normal(400.0, 30.0, 80), rng.normal(120.0, 20.0, 80)]).clip(min=1.0)
    games = np.full((2, 80), 17)
    return WeeklyModel(summary=summary, samples=samples, games=games, byes={},
                       kdst={"K": 7.0, "DST": 6.0},
                       repl_weekly={"QB": 7.0, "RB": 7.0, "WR": 7.0, "TE": 4.0}, n_weeks=17)


def test_league_probabilities_are_sane():
    model = _model_with_star()
    rosters = []
    for t in range(6):
        keys = [f"p_{t * 3 + 1}", f"p_{t * 3 + 2}", f"p_{t * 3 + 3}"]
        if t == 0:
            keys[0] = "p_9"                                  # only team 0 rosters the star
        rosters.append(pd.DataFrame({"player_key": keys, "pos": ["WR", "RB", "WR"]}))
    pp, tp = league_probabilities(rosters, model, FMT_4OF6, RosterSlots(bench=0),
                                  np.random.default_rng(0), sims=40)
    assert pp.shape == (6,) and tp.shape == (6,)
    assert ((pp >= 0) & (pp <= 1)).all()
    assert abs(tp.sum() - 1.0) < 1e-9                        # exactly one champion per world
    assert pp[0] > pp[1:].mean()                            # the team with the star advances more


def test_winprob_objective_prefers_the_higher_win_prob_pick():
    # 'p_8' (fringe RB) carries a hair more raw value, so the myopic greedy takes it; but rostering
    # the dominant 'p_9' (star) yields a higher playoff prob, so the win-prob policy takes it. Both
    # sit atop the ADP board, so passing the star means an opponent grabs it (it can't be recovered
    # later) — the win-prob rollout sees that and takes it now.
    board = _simple_board(60)
    board.loc[8, "adp"] = 1.0                                # p_8 fringe: tempting by ADP too
    board.loc[9, "adp"] = 2.0                                # p_9 star: gone if you pass on it
    vi = pd.DataFrame({
        "player_key": [f"p_{i}" for i in range(60)],
        "pos": [_POS_CYCLE[i % len(_POS_CYCLE)] for i in range(60)],
        "team": [f"T{i}" for i in range(60)],
        "role_rank": [1] * 60,
        "mean": [100.0] * 60, "sd": [10.0] * 60,
        "base_value": [50.0] * 60,
    })
    vi.loc[vi["player_key"] == "p_8", "base_value"] = 101.0   # fringe RB: highest raw value
    vi.loc[vi["player_key"] == "p_9", "base_value"] = 100.0   # star WR: a hair lower
    bv_board = attach_value(board, vi)
    risk = build_risk_model(bv_board, vi, neutral_model(), lam=0.0, scarcity_w=0.0, noise=5.0)
    b = _prepare_board(bv_board)                              # what simulate_draft does internally
    state = DraftState(board=b, n_teams=6, rounds=5, slots=RosterSlots(bench=0), your_team=0,
                       rng=np.random.default_rng(0), noise=5.0, available=set(b.index),
                       rosters=[[] for _ in range(6)])
    cfg = DraftConfig(league=LeagueSetup(draft_slot=1, n_teams=6))

    myopic = personalized_pick_fn(cfg, 0.0, risk)(state.clone())
    assert b.loc[myopic, "player_key"] == "p_8"              # raw value

    win = winprob_pick_fn(cfg, _model_with_star(), FMT_4OF6, risk,
                          noise=5.0, k=4, sims=30, base_seed=0)(state.clone())
    assert b.loc[win, "player_key"] == "p_9"                 # the win-prob-maximizing pick
