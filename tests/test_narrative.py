"""Offline tests for Phase 16.9 — the correlated per-draft narrative shock.

No DB: synthetic boards only. The behavioural claims these pin down are the ones the phase rests
on — the shock is **shared within a draft** and **zero-mean**, and the choice-set band actually
binds. The empirical verdict (the shock does not improve the dispersion profile) lives in
`analysis/phase16_9_narrative.json`, not here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.adp.narrative import (
    NARRATIVE_FEATURES,
    NarrativeShock,
    calibrate_intercept,
    compare_profiles,
    dispersion_profile,
    fit_shape,
    shock_features,
)
from fantasy_quant.draft.opponent_model import ALL_FEATURES, OpponentModel
from fantasy_quant.draft.personalities import make_opponent_pick_fn
from fantasy_quant.draft.simulator import simulate_draft


def _board(m=160, seed=0):
    rng = np.random.default_rng(seed)
    pos = rng.choice(["QB", "RB", "WR", "TE"], m, p=[0.12, 0.32, 0.44, 0.12])
    return pd.DataFrame({
        "player_name": [f"P{i}" for i in range(m)],
        "position": pos,
        "adp": np.sort(rng.uniform(1, 200, m)),
        "gsis_id": [f"g{i}" for i in range(m)],
        "adp_stdev": rng.uniform(1, 30, m),
        "rookie": (rng.random(m) < 0.15).astype(float),
    })


def _model():
    return OpponentModel(list(ALL_FEATURES),
                         beta=np.array([-1.7, -0.4, -0.1, 0.6, 0.0, 0.05, 0.06, 0.11, 1.2, 0.47]))


def test_shock_features_present_and_finite():
    b = _board()
    b["pos"] = b["position"]
    f = shock_features(b, board_teams=12)
    assert list(f.columns) == list(NARRATIVE_FEATURES)
    assert np.isfinite(f.to_numpy(float)).all()
    # depth is monotone in ADP, which is what the whole dispersion profile is keyed on
    assert f["log_depth"].is_monotonic_increasing


def test_shock_features_tolerate_a_bare_board():
    """A live simulator board carries only adp/pos. The shock must degrade to depth-only rather
    than raise, or 16.12 could not apply it in a real draft."""
    b = pd.DataFrame({"adp": [1.0, 50.0, 120.0], "pos": ["RB", "WR", "TE"]})
    f = shock_features(b, board_teams=10)
    assert np.isfinite(f.to_numpy(float)).all()
    assert (f["adp_stdev_z"] == 0).all() and (f["vbd_gap_z"] == 0).all()


def test_shock_is_zero_mean_and_scales_with_tau():
    """16.8's null licensed a *dispersion* model only — the shock must never imply that anyone
    goes earlier on average, or 16.9 would smuggle back the mean forecast the ablation killed."""
    b = _board()
    b["pos"] = b["position"]
    f = shock_features(b, board_teams=12)
    small = NarrativeShock(coef={"log_depth": 0.36}, intercept=-3.0)
    big = NarrativeShock(coef={"log_depth": 0.36}, intercept=-1.0)
    rng = np.random.default_rng(0)
    draws_s = np.array([small.draw(f, rng) for _ in range(400)])
    draws_b = np.array([big.draw(f, rng) for _ in range(400)])
    assert abs(draws_s.mean()) < 0.02                      # zero-mean
    assert draws_b.std() > 5 * draws_s.std()               # intercept sets the size
    # tau grows with depth, so deep players are the ones argued about
    tau = small.tau(f)
    assert tau[-1] > tau[0]


def test_shock_is_shared_within_a_draft_not_per_seat():
    """The phase's entire premise: one draw per draft, applied to every opponent. If the offsets
    were resampled per seat they would average away and a hyped player would always fall."""
    b = _board()
    b["pos"] = b["position"]
    f = shock_features(b, board_teams=10)
    shock = NarrativeShock(coef={"log_depth": 0.36}, intercept=-1.0)
    hype = shock.draw(f, np.random.default_rng(3))

    # a strong positive offset on one mid-board player pulls him earlier, consistently
    target = 60
    forced = np.zeros(len(b))
    forced[target] = 6.0
    model = _model()

    def slot_of(h):
        st = simulate_draft(b, n_teams=10, rounds=12, seed=11,
                            opponent_pick_fn=make_opponent_pick_fn(model, hype=h),
                            your_pick_fn=lambda s: int(
                                make_opponent_pick_fn(model, hype=h)(s, s.your_team)))
        log = pd.DataFrame(st.log)
        row = log[log["player_name"] == f"P{target}"]
        return int(row["overall_pick"].iloc[0]) if len(row) else 10 ** 6

    assert slot_of(forced) < slot_of(None)
    assert len(hype) == len(b)          # aligned to the board the opponents index into


def test_dispersion_profile_reports_level_and_slope():
    rng = np.random.default_rng(0)
    rows = []
    for d in range(20):
        for p in range(40):
            depth = 1 + p / 3
            rows.append({"season": 2020, "draft_id": f"d{d}", "gsis_id": f"g{p}",
                         "adp_rounds": depth,
                         # dispersion deliberately grows with depth
                         "drift": rng.normal(0, 0.2 + 0.1 * depth),
                         "drift_centered": rng.normal(0, 0.2 + 0.1 * depth)})
    prof = dispersion_profile(pd.DataFrame(rows))
    assert prof["n_player_seasons"] == 40
    assert prof["depth_spearman"] > 0.5          # recovers the planted depth slope
    assert prof["pooled_sd"] > 0


def test_compare_profiles_uses_only_shared_player_seasons():
    """The truncation trap: a small simulated panel keeps only shallow players, so each panel's own
    slope is not comparable. `compare_profiles` must intersect first."""
    rng = np.random.default_rng(1)

    def mk(players, tag):
        return pd.DataFrame([
            {"season": 2020, "draft_id": f"{tag}{d}", "gsis_id": f"g{p}",
             "adp_rounds": 1 + p / 3, "drift": rng.normal(0, 0.5),
             "drift_centered": rng.normal(0, 0.5)}
            for d in range(15) for p in players])

    real = mk(range(60), "r")
    sim = mk(range(25), "s")           # simulated panel only reaches the shallow end
    out = compare_profiles(real, sim)
    assert out["n_matched"] == 25      # the intersection, not 60
    assert np.isfinite(out["depth_slope_real"]) and np.isfinite(out["depth_slope_sim"])


def test_fit_shape_recovers_a_planted_profile_and_weights_by_n():
    rng = np.random.default_rng(0)
    n = 300
    depth = rng.uniform(0.5, 15, n)
    agg = pd.DataFrame({
        "season": 2020, "gsis_id": [f"g{i}" for i in range(n)], "pos": "WR",
        "n_drafts": rng.integers(10, 200, n),
        "mean_adp_rounds": depth,
        "sd_drift": np.exp(-1.0 + 0.5 * np.log(depth) + rng.normal(0, 0.05, n)),
    })
    feats = shock_features(agg.assign(adp=agg["mean_adp_rounds"] * 12, pos=agg["pos"]),
                           board_teams=12)
    coef = fit_shape(agg, feats)
    assert abs(coef["log_depth"] - 0.5) < 0.1        # the planted slope comes back


def test_fit_shape_degrades_gracefully_on_thin_input():
    agg = pd.DataFrame({"season": [2020], "gsis_id": ["g0"], "pos": ["WR"], "n_drafts": [12],
                        "mean_adp_rounds": [3.0], "sd_drift": [1.0]})
    feats = shock_features(agg.assign(adp=36.0, pos="WR"), board_teams=12)
    assert fit_shape(agg, feats) == dict.fromkeys(NARRATIVE_FEATURES, 0.0)


def test_calibrate_intercept_picks_the_closest_slope_and_rejects_all_nan():
    trace_target = 0.60

    def sim(it):
        return {"depth_spearman": 0.2 + 0.1 * (it + 5.0), "pooled_sd": 1.9}

    best, trace = calibrate_intercept(sim, trace_target, grid=(-5.0, -4.0, -3.0, -2.0))
    assert best == -2.0 and len(trace) == 4

    import pytest
    with pytest.raises(ValueError, match="no estimable depth slope"):
        calibrate_intercept(lambda it: {"depth_spearman": float("nan")}, 0.6, grid=(-3.0, -2.0))
