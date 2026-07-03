"""Unit tests for Phase 0.7 — the assert_panel_pit leak guard (no DB/network)."""

from __future__ import annotations

import pandas as pd
import pytest

from fantasy_quant.data.panel import assert_panel_pit


def test_pit_guard_passes_when_all_dates_before_as_of():
    df = pd.DataFrame({
        "week_end_date": pd.to_datetime(["2023-09-10", "2023-10-08"]),
        "adp_snapshot_date": pd.to_datetime(["2023-08-30", "2023-08-30"]),
    })
    assert assert_panel_pit(df, "2023-10-15", ["week_end_date", "adp_snapshot_date"]) is True


def test_pit_guard_raises_on_future_field():
    df = pd.DataFrame({"week_end_date": pd.to_datetime(["2023-09-10", "2024-01-01"])})
    with pytest.raises(AssertionError, match="PIT leak"):
        assert_panel_pit(df, "2023-10-15", ["week_end_date"])


def test_pit_guard_handles_tz_aware_and_missing_cols():
    df = pd.DataFrame({
        "injury_date_modified": pd.to_datetime(["2023-10-11 18:00", "2023-10-13 12:00"], utc=True),
    })
    # tz-aware col in-range passes; a named-but-absent col is skipped, not an error.
    assert assert_panel_pit(df, "2023-10-15", ["injury_date_modified", "not_here"]) is True


def test_pit_guard_raises_on_tz_aware_future():
    df = pd.DataFrame({
        "injury_date_modified": pd.to_datetime(["2023-10-20 18:00"], utc=True),
    })
    with pytest.raises(AssertionError):
        assert_panel_pit(df, "2023-10-15", ["injury_date_modified"])
