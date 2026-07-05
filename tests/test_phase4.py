"""Unit tests for Phase 4 pure pieces — consensus parsing/scoring, value-board ranking, rookie
ridge, calibration statistics (no DB)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.projections import calibration, rookie
from fantasy_quant.projections.consensus import (
    consensus_points,
    flatten_fp_table,
    parse_player_team,
)
from fantasy_quant.valuation.value_board import CONTRACT_COLS, _rank_and_seal


# --------------------------------------------------------------------------------------------
# 4.1 consensus parsing + full-PPR reconstruction
# --------------------------------------------------------------------------------------------
def test_parse_player_team_splits_trailing_abbrev():
    assert parse_player_team("Jahmyr Gibbs DET") == ("Jahmyr Gibbs", "DET")
    assert parse_player_team("Amon-Ra St. Brown DET") == ("Amon-Ra St. Brown", "DET")
    assert parse_player_team("Somebody") == ("Somebody", None)      # no team token
    assert parse_player_team(float("nan")) == ("", None)


def test_flatten_fp_table_maps_grouped_columns_to_weekly_stats():
    cols = pd.MultiIndex.from_tuples([
        ("Unnamed: 0_level_0", "Player"), ("RUSHING", "ATT"), ("RUSHING", "YDS"),
        ("RUSHING", "TDS"), ("RECEIVING", "REC"), ("RECEIVING", "YDS"), ("RECEIVING", "TDS"),
        ("MISC", "FL"), ("MISC", "FPTS")])
    raw = pd.DataFrame([["Jahmyr Gibbs DET", 274, 1380, 13, 70, 580, 4, 1, 372.5]], columns=cols)
    out = flatten_fp_table(raw, "rb")
    row = out.iloc[0]
    assert row["name"] == "Jahmyr Gibbs" and row["team"] == "DET" and row["position"] == "RB"
    assert row["rushing_yards"] == 1380 and row["receiving_yards"] == 580
    assert row["receptions"] == 70 and row["rushing_fumbles_lost"] == 1  # FL -> one fumble bucket


def test_consensus_points_reconstructs_full_ppr():
    df = pd.DataFrame({"position": ["WR"], "receptions": [100.0], "receiving_yards": [1200.0],
                       "receiving_tds": [10.0]})
    # 100*1 + 1200*0.1 + 10*6 = 100 + 120 + 60 = 280
    assert consensus_points(df).iloc[0] == 280.0


def test_consensus_points_kicker_falls_back_to_fp_fpts():
    df = pd.DataFrame({"position": ["K"], "fp_fpts": [140.0]})
    assert consensus_points(df).iloc[0] == 140.0


# --------------------------------------------------------------------------------------------
# 4.2 value board ranking + frozen contract
# --------------------------------------------------------------------------------------------
def test_rank_and_seal_orders_by_vbd_and_freezes_contract():
    board = pd.DataFrame({
        "player_key": ["a", "b", "c", "d"], "pos": ["RB", "RB", "WR", "QB"],
        "cpos": ["RB", "RB", "WR", "QB"], "proj_points": [200.0, 180.0, 210.0, 300.0],
        "source": ["consensus"] * 4, "vbd": [120.0, 100.0, 90.0, 60.0]})
    out = _rank_and_seal(board)
    assert list(out.columns) == CONTRACT_COLS
    assert list(out["player_key"]) == ["a", "b", "c", "d"]        # by descending vbd
    assert list(out["overall_rank"]) == [1, 2, 3, 4]
    assert list(out[out["pos"] == "RB"]["pos_rank"]) == [1, 2]    # within-position rank by vbd


# --------------------------------------------------------------------------------------------
# 4.3 rookie ridge (closed-form) recovers a linear signal
# --------------------------------------------------------------------------------------------
def test_ridge_recovers_linear_signal():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(200, 2))
    y = 3.0 * x[:, 0] - 2.0 * x[:, 1] + 5.0        # exact linear
    model = rookie.fit_ridge(x, y, lam=1.0)
    pred = rookie.predict_ridge(model, x)
    assert np.corrcoef(pred, y)[0, 1] > 0.99        # ridge tracks the signal
    assert model["w"][0] > 0 and model["w"][1] < 0  # signs recovered


def test_ridge_intercept_is_mean_of_y():
    x = np.zeros((10, 1))
    y = np.arange(10.0)
    assert rookie.fit_ridge(x, y)["b"] == y.mean()


# --------------------------------------------------------------------------------------------
# 4.4 calibration statistics
# --------------------------------------------------------------------------------------------
def test_bias_ratio_is_realized_over_predicted():
    assert calibration.bias_ratio([100.0, 100.0], [60.0, 60.0]) == 0.6
    assert np.isnan(calibration.bias_ratio([0.0], [5.0]))       # zero predicted -> nan, not crash


def test_reliability_table_bins_ascending_by_prediction():
    m = pd.DataFrame({"proj_points": np.arange(1, 21.0), "points": np.arange(1, 21.0) * 0.5})
    rel = calibration.reliability_table(m, n_bins=5)
    assert rel["mean_pred"].is_monotonic_increasing
    assert rel["mean_real"].is_monotonic_increasing
    assert int(rel["n"].sum()) == 20


def test_apply_correction_scales_by_position_factor():
    m = pd.DataFrame({"pos": ["QB", "RB", "TE"], "proj_points": [300.0, 200.0, 100.0]})
    corr = {"QB": 0.5, "RB": 0.6}                    # TE missing -> factor 1.0
    out = calibration.apply_correction(m, corr)
    assert list(out) == [150.0, 120.0, 100.0]
