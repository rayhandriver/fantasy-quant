"""Unit tests for Phase 3 feature modules — pure transforms (no DB/network)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fantasy_quant.features import efficiency, environment, exposures, opportunity, player


def test_opportunity_finalize_per_game_rates_and_finite():
    raw = pd.DataFrame([{
        "gsis_id": "a", "season": 2022, "position": "WR", "team": "MIN", "games": 10,
        "targets": 100, "receptions": 70, "carries": 0, "rush_att": 0, "rec_air_yards": 900,
        "tgt_share": 0.30, "air_yards_share": 0.35, "wopr": 0.75, "racr": 1.1,
        "snap_pct": 0.9, "carry_share": np.nan, "rz_targets": 12, "rz_carries": 0,
    }])
    out = opportunity._finalize(raw)
    r = out.iloc[0]
    assert r["targets_pg"] == 10.0 and r["receptions_pg"] == 7.0     # 100/10, 70/10
    assert r["touches_pg"] == 7.0                                    # (0 carries + 70 rec)/10
    assert r["rz_tgt_pg"] == 1.2                                     # 12/10
    assert round(r["adot"], 1) == 9.0                               # 900/100
    assert r["carry_share"] == 0.0                                  # NaN opportunity -> 0
    assert np.isfinite(out[opportunity.FEATURE_COLS].to_numpy(float)).all()


def test_opportunity_adot_clipped_for_tiny_samples():
    # 1 target, one 51-yard bomb -> raw aDOT 51, clipped to 30.
    raw = pd.DataFrame([{
        "gsis_id": "b", "season": 2020, "position": "WR", "team": "X", "games": 1,
        "targets": 1, "receptions": 1, "carries": 0, "rush_att": 0, "rec_air_yards": 51,
        "tgt_share": 0.05, "air_yards_share": 0.1, "wopr": 0.1, "racr": 1.0,
        "snap_pct": 0.1, "carry_share": 0.0, "rz_targets": 0, "rz_carries": 0,
    }])
    assert opportunity._finalize(raw)["adot"].iloc[0] == 30.0


def test_opportunity_zero_games_no_divide_error():
    raw = pd.DataFrame([{
        "gsis_id": "c", "season": 2019, "position": "RB", "team": "Y", "games": 0,
        "targets": 0, "receptions": 0, "carries": 0, "rush_att": 0, "rec_air_yards": 0,
        "tgt_share": np.nan, "air_yards_share": np.nan, "wopr": np.nan, "racr": np.nan,
        "snap_pct": np.nan, "carry_share": np.nan, "rz_targets": 0, "rz_carries": 0,
    }])
    out = opportunity._finalize(raw)  # games clipped to 1 -> no inf/nan
    assert np.isfinite(out[opportunity.FEATURE_COLS].to_numpy(float)).all()


def _eff_row(**kw):
    base = {"gsis_id": "a", "season": 2022, "games": 16, "targets": 0, "receptions": 0,
            "rec_yds": 0, "yac": 0, "rec_tds": 0, "carries": 0, "rush_yds": 0, "rush_tds": 0,
            "rz_targets": 0, "rz_carries": 0, "qb_epa_per_play": np.nan, "qb_cpoe": np.nan}
    base.update(kw)
    return pd.DataFrame([base])


def test_efficiency_rates_and_catch_rate():
    out = efficiency._finalize(
        _eff_row(targets=100, receptions=65, rec_yds=845, yac=300, rec_tds=6))
    r = out.iloc[0]
    assert r["catch_rate"] == 0.65 and r["ypr"] == 13.0 and r["yptgt"] == 8.45
    assert round(r["yac_per_rec"], 4) == round(300 / 65, 4)
    assert np.isfinite(out[efficiency.FEATURE_COLS].to_numpy(float)).all()


def test_efficiency_td_over_expected_flag():
    # 10 rec TDs on 20 RZ targets -> expected 20*0.20=4 -> td_oe = 10-4 = +6 (lucky, regresses).
    out = efficiency._finalize(_eff_row(receptions=60, rec_tds=10, rz_targets=20, games=16))
    r = out.iloc[0]
    assert r["exp_tds"] == 4.0 and r["td_oe"] == 6.0
    assert r["td_regression_flag"] > 0  # positive luck


def test_efficiency_rates_clipped_and_qb_nan_zeroed():
    # 1 carry for 40 yds -> ypc 40 clipped to 15; no QB pass data -> qb cols 0.
    out = efficiency._finalize(_eff_row(carries=1, rush_yds=40)).iloc[0]
    assert out["ypc"] == 15.0
    assert out["qb_epa_per_play"] == 0.0 and out["qb_cpoe"] == 0.0


def _plr_row(**kw):
    base = {"gsis_id": "a", "season": 2023, "position": "WR", "birthdate": "1998-09-01",
            "draft_year": 2022, "draft_round": 1, "draft_ovr": 20, "height": 74.0,
            "weight": 200.0, "first_season": 2022,
            "forty": 4.4, "vertical": 36.0, "broad_jump": 120.0, "cone": 6.9,
            "shuttle": 4.2, "bench": 15.0}
    base.update(kw)
    return pd.DataFrame([base])


def test_player_age_asof_sep1_and_experience():
    # born 1998-09-01, as-of 2023-09-01 -> exactly 25.0; drafted 2022 -> experience 1.
    out = player._finalize(_plr_row(season=2023, birthdate="1998-09-01", draft_year=2022)).iloc[0]
    assert abs(out["age"] - 25.0) < 0.05
    assert out["experience"] == 1 and out["is_rookie"] == 0
    assert out["draft_ovr"] == 20 and out["is_undrafted"] == 0


def test_player_rookie_flag_and_undrafted_sentinels():
    rookie = player._finalize(_plr_row(season=2022, draft_year=2022)).iloc[0]
    assert rookie["is_rookie"] == 1 and rookie["experience"] == 0
    udfa = player._finalize(_plr_row(draft_year=None, draft_round=None, draft_ovr=None,
                                     first_season=2021)).iloc[0]
    assert udfa["is_undrafted"] == 1
    assert udfa["draft_ovr"] == player.UNDRAFTED_OVR
    assert udfa["draft_round"] == player.UNDRAFTED_ROUND


def test_player_bogus_draft_year_falls_back_to_first_season():
    # draft_year=0 (bad crosswalk value) -> use first_season, not season-0. born 1990 -> age ok.
    out = player._finalize(_plr_row(season=2016, draft_year=0, first_season=2014,
                                    birthdate="1990-06-01")).iloc[0]
    assert out["experience"] == 2                 # 2016 - 2014, not 2016


def test_player_missing_birthdate_is_nan_not_error():
    out = player._finalize(_plr_row(birthdate=None)).iloc[0]
    assert pd.isna(out["age"])                    # NaN, handled in 3.5 (not a crash)
    assert out["experience"] == 1                 # non-age features still computed


def _env_row(**kw):
    base = {"team": "KC", "season": 2023, "games": 17, "pass_plays": 680, "rush_plays": 320,
            "ed_pass": 360, "ed_plays": 600, "pass_epa": 0.15, "rush_epa": -0.05,
            "points_pg": 27.0, "implied_team_total": 25.0, "tgt_hhi": 0.14}
    base.update(kw)
    return pd.DataFrame([base])


def test_environment_pass_rate_pace_and_early_down():
    out = environment._finalize(_env_row()).iloc[0]
    assert out["pass_rate"] == 0.68                       # 680 / 1000
    assert out["early_down_pass_rate"] == 0.6             # 360 / 600
    assert round(out["plays_pg"], 3) == round(1000 / 17, 3)
    assert np.isfinite(list(out[environment.FEATURE_COLS].to_numpy(float))).all()


def test_environment_missing_implied_falls_back_then_median():
    # one row missing implied -> falls back to its points_pg; still finite.
    df = pd.concat([_env_row(team="A", implied_team_total=np.nan, points_pg=24.0),
                    _env_row(team="B")], ignore_index=True)
    out = environment._finalize(df)
    a = out[out["team"] == "A"].iloc[0]
    assert a["implied_team_total"] == 24.0
    assert np.isfinite(out[environment.FEATURE_COLS].to_numpy(float)).all()


def test_standardize_within_position_zscores_and_imputes():
    df = pd.DataFrame({
        "position": ["WR", "WR", "WR", "WR", "RB", "RB"],
        "x": [1.0, 2.0, 3.0, np.nan, 10.0, 20.0],
    })
    out = exposures.standardize_within_position(df, ["x"], winsor=(0.0, 1.0))
    # WR z is mean-centered (the NaN imputed to the WR median=2 before z).
    wr = out[out["position"] == "WR"]["x_z"]
    assert abs(wr.mean()) < 1e-9
    assert np.isfinite(out["x_z"].to_numpy(float)).all()
    # groups standardized independently: RB mean also ~0.
    assert abs(out[out["position"] == "RB"]["x_z"].mean()) < 1e-9


def test_standardize_constant_column_is_zero_not_nan():
    df = pd.DataFrame({"position": ["QB", "QB"], "x": [5.0, 5.0]})
    out = exposures.standardize_within_position(df, ["x"])
    assert (out["x_z"] == 0.0).all()  # zero variance -> 0, never NaN/inf


def test_exposures_pit_guard():
    assert exposures.assert_exposures_pit(2022, 2022, 2023) is True
    with pytest.raises(AssertionError):
        exposures.assert_exposures_pit(2023, 2022, 2023)   # production not lagged
    with pytest.raises(AssertionError):
        exposures.assert_exposures_pit(2022, 2024, 2023)   # environment from the future
