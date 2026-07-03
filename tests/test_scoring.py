"""Unit tests for Phase 1.1 — the pure scoring functions (no DB/network)."""

from __future__ import annotations

import pandas as pd

from fantasy_quant.backtest.scoring import (
    DEFAULT_RULESET,
    OffenseRules,
    dst_team_from_adp_name,
    kick_play_points,
    pa_tier_points,
    score_dst,
    score_offense,
)


def test_offense_matches_known_ppr_lines():
    # Justin Jefferson 2022 wk1 (9-184-2 receiving) -> 39.4 ppr; Stafford (240 pass, 1 TD, 3 INT,
    # 2 rush yds) -> 7.8. These are the exact nflverse fantasy_points_ppr values.
    df = pd.DataFrame([
        {"receptions": 9, "receiving_yards": 184, "receiving_tds": 2},
        {"passing_yards": 240, "passing_tds": 1, "interceptions": 3, "rushing_yards": 2},
    ]).fillna(0)
    pts = score_offense(df)
    assert round(pts.iloc[0], 2) == 39.40
    assert round(pts.iloc[1], 2) == 7.80


def test_offense_standard_drops_receptions():
    df = pd.DataFrame([{"receptions": 9, "receiving_yards": 184, "receiving_tds": 2}])
    standard = score_offense(df, OffenseRules(rec=0.0))
    assert round(standard.iloc[0], 2) == 30.40  # 39.4 ppr - 9 receptions


def test_offense_missing_columns_are_zero():
    # a row with only rushing stats; absent columns must be treated as 0, not error.
    df = pd.DataFrame([{"rushing_yards": 100, "rushing_tds": 1}])
    assert round(score_offense(df).iloc[0], 2) == 16.00


def test_kick_play_points_distance_buckets():
    plays = pd.DataFrame([
        {"field_goal_attempt": 1, "field_goal_result": "made", "kick_distance": 24},   # 3
        {"field_goal_attempt": 1, "field_goal_result": "made", "kick_distance": 45},   # 4
        {"field_goal_attempt": 1, "field_goal_result": "made", "kick_distance": 55},   # 5
        {"field_goal_attempt": 1, "field_goal_result": "missed", "kick_distance": 50}, # 0
        {"extra_point_attempt": 1, "extra_point_result": "good"},                      # 1
        {"extra_point_attempt": 1, "extra_point_result": "failed"},                    # 0
    ]).fillna(0)
    pts = kick_play_points(plays)
    assert list(pts) == [3.0, 4.0, 5.0, 0.0, 1.0, 0.0]
    assert pts.sum() == 13.0


def test_pa_tier_points_boundaries():
    pa = pd.Series([0, 3, 6, 7, 13, 20, 27, 31, 35, 60])
    # tiers: 0->10, 1-6->7, 7-13->4, 14-20->1, 21-27->0, 28-34->-1, 35+->-4
    assert list(pa_tier_points(pa)) == [10, 7, 7, 4, 4, 1, 0, -1, -4, -4]


def test_score_dst_combines_events_and_pa():
    df = pd.DataFrame([
        # 4 sacks(4) + 2 int(4) + 1 fum(2) + 1 td(6) + 0 saf + PA=3 -> tier 7  => 23
        {"sacks": 4, "ints": 2, "fum_rec": 1, "def_tds": 1, "safeties": 0, "pa": 3},
        # shutout: 3 sacks(3) + PA=0 -> tier 10 => 13
        {"sacks": 3, "ints": 0, "fum_rec": 0, "def_tds": 0, "safeties": 0, "pa": 0},
    ])
    pts = score_dst(df)
    assert list(pts) == [23.0, 13.0]


def test_dst_name_mapping_incl_relocations():
    assert dst_team_from_adp_name("Philadelphia Defense") == "PHI"
    assert dst_team_from_adp_name("Green Bay Packers") == "GB"
    assert dst_team_from_adp_name("Las Vegas Defense") == "LV"
    assert dst_team_from_adp_name("San Diego Chargers") == "SD"
    assert dst_team_from_adp_name(float("nan")) is None


def test_default_ruleset_is_full_ppr():
    assert DEFAULT_RULESET.offense.rec == 1.0
    assert DEFAULT_RULESET.offense.pass_td == 4.0
    assert DEFAULT_RULESET.offense.interception == -2.0
