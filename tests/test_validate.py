"""Unit tests for Phase 0.8 — the validate_panel hard gate (no DB/network)."""

from __future__ import annotations

import pandas as pd
import pytest

from fantasy_quant.data.validate import validate_panel


def _good_panel():
    return pd.DataFrame({
        "gsis_id": ["00-0001", "00-0002"],
        "season": [2023, 2023],
        "week": [5, 5],
        "targets": [8, 3],
        "receptions": [6, 2],
        "carries": [0, 12],
        "attempts": [0, 0],
        "offense_snaps": [55, 40],
        "offense_pct": [0.88, 0.65],
        "fantasy_points_ppr": [18.4, 9.1],
        "week_end_date": pd.to_datetime(["2023-10-08", "2023-10-08"]),
        "adp_snapshot_date": pd.to_datetime(["2023-09-01", "2023-09-01"]),
    })


def test_validate_panel_accepts_clean_panel():
    assert validate_panel(_good_panel(), "2023-10-15") is True


def test_validate_panel_rejects_negative_counting_stat():
    df = _good_panel()
    df.loc[0, "targets"] = -1
    with pytest.raises(AssertionError, match="negative targets"):
        validate_panel(df, "2023-10-15")


def test_validate_panel_rejects_duplicate_identity():
    df = _good_panel()
    df.loc[1, "gsis_id"] = "00-0001"  # duplicate (gsis, season, week)
    with pytest.raises(AssertionError, match="duplicate identity"):
        validate_panel(df, "2023-10-15")


def test_validate_panel_rejects_bad_snap_pct():
    df = _good_panel()
    df.loc[0, "offense_pct"] = 1.5
    with pytest.raises(AssertionError, match="offense_pct"):
        validate_panel(df, "2023-10-15")


def test_validate_panel_rejects_pit_leak():
    df = _good_panel()
    df.loc[0, "week_end_date"] = pd.Timestamp("2024-01-01")
    with pytest.raises(AssertionError, match="PIT leak"):
        validate_panel(df, "2023-10-15")
