"""Offline tests for the Phase 11 behavioral opponent model / availability / personalities.

No DB — synthetic choice sets only, so these run fast in CI.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.draft.availability import simulate_survival
from fantasy_quant.draft.opponent_model import (
    ALL_FEATURES,
    OpponentModel,
    _group_ptr,
    _softmax_by_group,
)
from fantasy_quant.draft.personalities import make_opponent_pick_fn, personalities
from fantasy_quant.draft.simulator import simulate_draft


def test_group_softmax_matches_manual():
    u = np.array([0.0, np.log(3.0), 0.0, 0.0])   # group0: {1,3} -> .25/.75 ; group1: {1,1}->.5/.5
    ptr = _group_ptr(np.array([0, 0, 1, 1]))
    soft, lse = _softmax_by_group(u, ptr)
    assert np.allclose(soft, [0.25, 0.75, 0.5, 0.5])
    assert np.allclose(lse, [np.log(4.0), np.log(2.0)])


def _synthetic_choices(n_groups=400, k=8, seed=0):
    """Groups where the chosen row is driven by low adp + a rookie bonus (recoverable signal)."""
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(n_groups):
        adp = rng.uniform(1, 200, k)
        rookie = (rng.random(k) < 0.2).astype(float)
        util = -adp / 50.0 * 1.0 + rookie * 1.5 + rng.gumbel(size=k)   # true logit DGP
        chosen = int(np.argmax(util))
        for i in range(k):
            rows.append({
                "group": g, "season": 2000 + g % 5, "chosen": 1 if i == chosen else 0,
                "adp_s": adp[i] / 50.0, "is_RB": 0.0, "is_WR": 0.0, "is_TE": 0.0, "is_QB": 0.0,
                "pos_run3": 0.0, "mgr_lean": 0.0, "rookie": rookie[i], "fandom": 0.0, "need": 0.0,
            })
    return pd.DataFrame(rows)


def test_fit_recovers_signal_and_beats_random():
    frame = _synthetic_choices()
    m = OpponentModel(list(ALL_FEATURES), l2=0.5).fit(frame)
    coefs = dict(zip(ALL_FEATURES, m.beta, strict=False))
    assert coefs["adp_s"] < -0.3       # lower adp -> picked
    assert coefs["rookie"] > 0.5       # rookie bonus recovered
    sc = m.score(frame)
    assert sc["logloss"] < np.log(8)   # better than uniform-over-8


def test_candidate_utility_ignores_absent_features_for_adp_only():
    m = OpponentModel(["adp_s"], beta=np.array([-1.0]))
    cand = pd.DataFrame({"adp": [10.0, 100.0], "pos": ["RB", "WR"]})
    u = m.candidate_utility(cand)
    assert u[0] > u[1]                 # adp 10 preferred over adp 100


def test_simulate_survival_bounds_and_monotone():
    m = OpponentModel(["adp_s"], beta=np.array([-1.0]))
    cand = pd.DataFrame({"adp": [5.0, 15.0, 25.0, 40.0, 60.0], "pos": ["RB"] * 5})
    avail0 = np.ones(5, bool)
    plan = [{}, {}, {}]                 # three neutral opponent picks
    surv = simulate_survival(cand, avail0, plan, m, n_sims=300, rng=np.random.default_rng(0))
    assert np.all((surv >= 0) & (surv <= 1))
    assert surv[0] <= surv[-1] + 0.05  # the best (lowest-adp) player survives least


def test_personalities_shape_utility():
    p = personalities()
    base = np.arange(len(ALL_FEATURES), dtype=float) + 1.0
    chalk = p["chalk"].adjusted_beta(list(ALL_FEATURES), base)
    # chalk zeroes every non-adp coefficient
    for i, c in enumerate(ALL_FEATURES):
        if c != "adp_s":
            assert chalk[i] == 0.0


def test_behavioral_opponent_produces_valid_full_draft():
    m = OpponentModel(list(ALL_FEATURES),
                      beta=np.array([-0.85, -0.3, -0.2, 0.4, 0.2, 0.07, 0.0, 0.4, 0.0, 0.3]))
    board = pd.DataFrame({
        "name": [f"P{i}" for i in range(120)],
        "position": (["RB", "WR", "QB", "TE"] * 30),
        "adp": np.arange(1, 121, dtype=float),
        "pos_rank": list(range(1, 121)),
    })
    opp = make_opponent_pick_fn(m, personalities()["zero_rb"])
    st = simulate_draft(board, n_teams=10, rounds=10, seed=3, opponent_pick_fn=opp)
    log = st.pick_log()
    assert len(log) == 100                          # full 10x10 draft completed
    assert log["player_key"].nunique() == 100       # no player drafted twice
