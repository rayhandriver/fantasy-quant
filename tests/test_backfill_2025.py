"""Unit tests for Phase 0.9 — the new-release stats conform + append primitive (no network)."""

from __future__ import annotations

import pandas as pd

from fantasy_quant.data import db
from fantasy_quant.data.sources.nflverse import conform_stats_player


def test_conform_renames_new_release_columns():
    # a minimal new-release ("stats_player") row with the post-2024 column names.
    new = pd.DataFrame([{
        "player_id": "00-0036322", "team": "MIN", "season": 2025, "week": 1,
        "passing_interceptions": 0, "sacks_suffered": 0, "sack_yards_lost": 0,
        "receptions": 9, "fantasy_points_ppr": 39.4,
    }])
    target = ["gsis_id", "recent_team", "season", "week", "interceptions", "sacks",
              "receptions", "fantasy_points_ppr", "dakota"]
    out = conform_stats_player(new, target)
    assert list(out.columns) == target                 # reindexed to legacy schema
    assert out["gsis_id"].iloc[0] == "00-0036322"      # player_id -> gsis_id
    assert out["recent_team"].iloc[0] == "MIN"         # team -> recent_team
    assert out["interceptions"].iloc[0] == 0           # passing_interceptions -> interceptions
    assert out["dakota"].isna().all()                  # dropped-by-new-release col -> NA-filled


def test_conform_drops_extra_new_columns():
    # columns the new release has but our legacy schema doesn't are dropped by the reindex.
    new = pd.DataFrame([{"player_id": "x", "season": 2025, "def_sacks": 3, "extra_new_col": 1}])
    out = conform_stats_player(new, ["gsis_id", "season"])
    assert list(out.columns) == ["gsis_id", "season"]
    assert "extra_new_col" not in out.columns and "def_sacks" not in out.columns


def test_append_df_matches_by_name_and_null_fills():
    con = db.connect(":memory:")
    con.execute('CREATE TABLE t (a INTEGER, b VARCHAR, c INTEGER, pulled_at TIMESTAMP)')
    con.execute("INSERT INTO t BY NAME SELECT 1 AS a, 'x' AS b, 9 AS c, NULL AS pulled_at")
    # append a frame missing column c -> c should NULL-fill, pulled_at stamped.
    n = db.append_df(con, "t", pd.DataFrame([{"a": 2, "b": "y"}]))
    assert n == 2
    row = con.execute("SELECT a, b, c FROM t WHERE a = 2").fetchone()
    assert row == (2, "y", None)
    assert con.execute("SELECT COUNT(*) FROM t WHERE pulled_at IS NOT NULL").fetchone()[0] == 1
    con.close()
