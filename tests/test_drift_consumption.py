"""Offline tests for Phase 16.12 (drift consumption) and 16.16 (run detection).

The load-bearing property in this file is **isolation**: the frozen value / distribution /
optimizer / VBD / cost-report stack — the one the lockbox was spent on, once, in Session D — must
be bit-identical whether or not Phase 16 exists. Every drift channel is opt-in, and
``DriftConfig()`` is a no-op. If one of these tests fails, an unbacktested curated signal has
leaked into a validated result, which is a strictly worse failure than the feature not working.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fantasy_quant.adp.hype_board import HYPE_COLS
from fantasy_quant.covariance.shrinkage import CorrelationModel
from fantasy_quant.draft.availability import simulate_survival
from fantasy_quant.draft.drift import (
    DriftConfig,
    availability_readout,
    drift_adp,
    drift_picks,
    drift_utility,
    reach_risk_label,
)
from fantasy_quant.draft.opponent_model import (
    ALL_FEATURES,
    RUN_WINDOW,
    OpponentModel,
    detect_run,
    run_bonus,
)
from fantasy_quant.draft.optimizer import RiskModel


def _board(m=60):
    rng = np.random.default_rng(3)
    return pd.DataFrame({
        "player_key": [f"g{i}" for i in range(m)],
        "adp": np.sort(rng.uniform(1, 180, m)),
        "pos": rng.choice(["QB", "RB", "WR", "TE"], m, p=[0.12, 0.32, 0.44, 0.12]),
    })


def _hype_csv(tmp_path, rows, reviewed=True):
    p = tmp_path / "hype.csv"
    base = dict(season=2026, player="X", position="WR", team="SF", adp=50.0, note="n",
                source="s", evidence="derived+web", confidence="med", reviewed=reviewed)
    pd.DataFrame([{**base, **r} for r in rows], columns=HYPE_COLS).to_csv(p, index=False)
    return p


# =================================================================================================
# isolation — the property that protects the spent lockbox
# =================================================================================================
def test_default_config_is_a_noop():
    b = _board()
    cfg = DriftConfig()
    assert not cfg.enabled
    assert np.array_equal(drift_picks(b, cfg=cfg), np.zeros(len(b)))
    assert np.array_equal(drift_utility(b, beta_adp_s=-1.68, cfg=cfg), np.zeros(len(b)))
    assert np.array_equal(drift_adp(b, cfg=cfg), b["adp"].to_numpy(float))


def _risk(**extra):
    b = _board()
    keys = list(b["player_key"])
    return b, RiskModel(lam=0.0, corr=CorrelationModel(table=pd.DataFrame(columns=["rel", "rho"])),
                        bv={k: 200.0 - i for i, k in enumerate(keys)},
                        sd={}, team={}, pos={}, role={},
                        rank_x=np.array([0.0, 200.0]), rank_y=np.array([200.0, 1.0]),
                        scarcity_w=0.5, **extra)


def test_risk_model_without_hype_is_bit_identical_to_the_frozen_path():
    """`RiskModel` constructed the pre-16.12 way (no `hype` argument at all) and one constructed
    with an explicit empty map must agree exactly — not approximately."""
    b, frozen = _risk()
    _, explicit = _risk(hype={})
    roster = pd.DataFrame({"player_key": []})
    a = frozen.effective_rank(b, roster, 60.0)
    c = explicit.effective_rank(b, roster, 60.0)
    assert np.array_equal(a, c, equal_nan=True)


def test_hype_makes_a_player_more_urgent_but_touches_no_one_else():
    b, frozen = _risk()
    target = b["player_key"].iloc[30]
    _, hyped = _risk(hype={target: 15.0})
    roster = pd.DataFrame({"player_key": []})
    a = frozen.effective_rank(b, roster, 60.0)
    c = hyped.effective_rank(b, roster, 60.0)
    i = 30
    assert c[i] != a[i]
    assert c[i] < a[i]                       # lower effective rank = draft sooner
    others = [j for j in range(len(b)) if j != i]
    assert np.array_equal(a[others], c[others], equal_nan=True)


def test_hype_is_inert_when_scarcity_is_off():
    """The drift term rides the 9.1/9.4 urgency path, so a covariance-only greedy (scarcity_w=0)
    must be untouched — that is the configuration several frozen results were produced under."""
    b = _board()
    keys = list(b["player_key"])
    corr = CorrelationModel(table=pd.DataFrame(columns=["rel", "rho"]))
    kw = dict(lam=0.0, corr=corr, bv={k: 200.0 - i for i, k in enumerate(keys)},
              sd={}, team={}, pos={}, role={}, rank_x=np.array([0.0, 200.0]),
              rank_y=np.array([200.0, 1.0]), scarcity_w=0.0)
    roster = pd.DataFrame({"player_key": []})
    a = RiskModel(**kw).effective_rank(b, roster, 60.0)
    c = RiskModel(**kw, hype={keys[10]: 20.0}).effective_rank(b, roster, 60.0)
    assert np.array_equal(a, c, equal_nan=True)


def test_unreviewed_board_contributes_nothing_even_with_hype_on(tmp_path):
    """Switching the channel on must not bypass the review gate — the two are independent."""
    b = _board()
    p = _hype_csv(tmp_path, [{"gsis_id": "g5", "pick_delta": 9.0}], reviewed=False)
    on = DriftConfig(hype=True, hype_path=p)
    assert np.array_equal(drift_picks(b, cfg=on, season=2026), np.zeros(len(b)))
    bypass = DriftConfig(hype=True, hype_path=p, require_reviewed=False)
    assert drift_picks(b, cfg=bypass, season=2026)[5] == 9.0


# =================================================================================================
# the drift channels themselves
# =================================================================================================
def test_hype_and_momentum_add_in_pick_space(tmp_path):
    b = _board()
    p = _hype_csv(tmp_path, [{"gsis_id": "g5", "pick_delta": 6.0}])
    vel = pd.DataFrame({"gsis_id": ["g5", "g7"], "velocity_shrunk": [2.0, -1.0]})
    cfg = DriftConfig(hype=True, hype_path=p, momentum_w=3.0)
    d = drift_picks(b, cfg=cfg, season=2026, velocity=vel)
    assert d[5] == pytest.approx(6.0 + 3.0 * 2.0)
    assert d[7] == pytest.approx(-3.0)
    assert d[0] == 0.0


def test_drift_adp_moves_a_hyped_player_earlier(tmp_path):
    b = _board()
    p = _hype_csv(tmp_path, [{"gsis_id": "g5", "pick_delta": 6.0}])
    cfg = DriftConfig(hype=True, hype_path=p)
    assert drift_adp(b, cfg=cfg, season=2026)[5] == pytest.approx(b["adp"].iloc[5] - 6.0)


def test_describe_always_says_it_is_not_backtested():
    d = DriftConfig(hype=True).describe()
    assert d["backtested"] is False and d["enabled"] is True


def test_reach_risk_buckets():
    assert reach_risk_label(0.05) == "likely gone"
    assert reach_risk_label(0.4) == "coin flip"
    assert reach_risk_label(0.9) == "likely available"
    assert reach_risk_label(float("nan")) == "unknown"


def _model():
    return OpponentModel(list(ALL_FEATURES),
                         beta=np.array([-1.7, -0.4, -0.1, 0.6, 0.0, 0.05, 0.06, 0.11, 1.2, 0.47]))


def test_readout_reports_the_pair_not_just_the_adjusted_number(tmp_path):
    """An unbacktested adjustment reaches a human only alongside its baseline."""
    b = _board()
    p = _hype_csv(tmp_path, [{"gsis_id": "g5", "pick_delta": 20.0}])
    ro = availability_readout(b, _model(), window_picks=12,
                              cfg=DriftConfig(hype=True, hype_path=p), season=2026,
                              n_sims=40, seed=1)
    assert {"p_available", "p_available_baseline", "reach_risk", "drift_picks"} <= set(ro.columns)
    assert ((ro["p_available"] >= 0) & (ro["p_available"] <= 1)).all()
    # hyping a player can only make him less likely to survive
    assert ro.loc[5, "p_available"] <= ro.loc[5, "p_available_baseline"] + 1e-9


def test_readout_with_no_window_says_everyone_survives():
    ro = availability_readout(_board(), _model(), window_picks=0, n_sims=10)
    assert (ro["p_available"] == 1.0).all()


# =================================================================================================
# 16.16 — run detection
# =================================================================================================
def test_detect_run_fires_on_a_run_and_not_on_a_balanced_room():
    """Intensity is measured against the CANDIDATE SET, not the whole board — scored against the
    remaining pool the detector fired on 61 % of real windows and discriminated nothing."""
    cand = ["RB"] * 10 + ["WR"] * 20 + ["QB"] * 5 + ["TE"] * 5
    run = detect_run(["RB"] * 8 + ["WR", "WR"], cand)
    assert run["RB"] > 0.4
    balanced = detect_run(["RB", "WR", "WR", "QB", "TE"] * 2, cand)
    assert balanced["RB"] < run["RB"]


def test_detect_run_is_scale_free():
    """Both terms are shares, so doubling the candidate set cannot change the answer."""
    cand = ["RB"] * 10 + ["WR"] * 20
    a = detect_run(["RB"] * 6 + ["WR"] * 4, cand)
    b = detect_run(["RB"] * 6 + ["WR"] * 4, cand * 2)
    assert a["RB"] == pytest.approx(b["RB"])


def test_detect_run_handles_empty_inputs():
    assert detect_run([], ["RB", "WR"]) == {}
    assert detect_run(["RB"], []) != {}       # no supply -> everything looks like a run


def test_run_bonus_is_exactly_zero_when_off():
    pos = np.array(["RB", "WR", "QB"])
    assert np.array_equal(run_bonus(pos, {"RB": 0.5}, 0.0), np.zeros(3))
    assert run_bonus(pos, {"RB": 0.5}, 2.0)[0] == pytest.approx(1.0)


def test_simulate_survival_is_unchanged_when_run_detection_is_off():
    """The 11.2 forecast is validated against the real corpus; adding 16.16 must not perturb it
    unless a caller opts in."""
    b = _board(50)
    cand = b[["adp", "pos"]].copy()
    avail = np.ones(len(cand), bool)
    plan = [{} for _ in range(8)]
    m = _model()
    a = simulate_survival(cand, avail, plan, m, n_sims=25, rng=np.random.default_rng(0))
    c = simulate_survival(cand, avail, plan, m, n_sims=25, rng=np.random.default_rng(0),
                          run_w=0.0)
    assert np.array_equal(a, c)


def test_simulate_survival_reacts_when_run_detection_is_on():
    b = _board(50)
    cand = b[["adp", "pos"]].copy()
    avail = np.ones(len(cand), bool)
    plan = [{} for _ in range(8)]
    m = _model()
    a = simulate_survival(cand, avail, plan, m, n_sims=40, rng=np.random.default_rng(0))
    c = simulate_survival(cand, avail, plan, m, n_sims=40, rng=np.random.default_rng(0),
                          run_w=3.0)
    assert not np.array_equal(a, c)


def test_run_window_is_longer_than_the_fitted_pos_run3():
    """`pos_run3` is a local texture the fitted β already prices; a run is a room-level regime. If
    these ever coincide, 16.16 is re-measuring something 11.1 already has."""
    assert RUN_WINDOW > 3
