"""Unit tests for Phase 0.8 validate_panel hard gate (no DB/network) + the T7 scrape guards."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from fantasy_quant.data import validate as V
from fantasy_quant.data.validate import (
    adp_freshness_gate,
    board_size_gate,
    match_rate_gate,
    validate_panel,
)


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


# --- T7 scrape freshness / schema guards (pure) ---------------------------------------------
_TODAY = dt.date(2026, 8, 20)


def _fresh(latest, live=2026, completed=2024):
    return adp_freshness_gate(latest, _TODAY, live_season=live, newest_completed_season=completed)


def test_adp_freshness_passes_when_fresh():
    g = _fresh(dt.date(2026, 8, 18))
    assert g["passed"] and g["age_days"] == 2


def test_adp_freshness_fails_when_stale():
    g = _fresh(dt.date(2026, 8, 1))
    assert not g["passed"] and g["age_days"] == 19


def test_adp_freshness_not_applicable_for_historical_only():
    # a dev store whose newest board is a completed season has nothing live to keep fresh
    g = _fresh(dt.date(2024, 9, 1), live=2024)
    assert g["passed"] and g["applicable"] is False


def test_adp_freshness_fails_when_live_board_missing():
    assert not _fresh(None)["passed"]


def test_board_size_gate_bands():
    assert board_size_gate("b", 528)["passed"]        # a full board
    assert not board_size_gate("b", 40)["passed"]     # truncated shell
    assert not board_size_gate("b", 5000)["passed"]   # runaway / duped scrape


def test_match_rate_gate_floor():
    assert match_rate_gate("m", 0.99)["passed"]
    assert not match_rate_gate("m", 0.80)["passed"]
    assert not match_rate_gate("m", None)["passed"]   # no rows -> loud fail, not vacuous pass


# --- T12: the ADP uniqueness gate keys on the snapshot, not just the season ------------------
def _adp_con(rows):
    import duckdb
    import pandas as pd

    from fantasy_quant.data import validate as V
    con = duckdb.connect()
    con.register("_r", pd.DataFrame(rows))
    con.execute("CREATE TABLE adp_snapshots AS SELECT * FROM _r")
    # _dup_gates checks all three tables; the siblings just need to exist and be clean
    con.execute("CREATE TABLE weekly (gsis_id VARCHAR, season INT, week INT, season_type VARCHAR)")
    con.execute("CREATE TABLE game_lines (game_id VARCHAR)")
    return con, V


def _adp_row(**kw):
    base = {"gsis_id": "00-0000001", "season": 2026, "source": "ffc", "scoring": "ppr",
            "teams": 12, "snapshot_date": "2026-07-18"}
    base.update(kw)
    return base


def test_adp_dup_gate_allows_a_weekly_snapshot_series():
    """Stage 0 banks a weekly 2026 series on purpose: same player, same board, different dates."""
    con, V = _adp_con([_adp_row(snapshot_date="2026-07-18"),
                       _adp_row(snapshot_date="2026-07-24"),
                       _adp_row(snapshot_date="2026-07-31")])
    gate = next(g for g in V._dup_gates(con) if g["gate"].startswith("adp: unique"))
    assert gate["passed"] and gate["offending_groups"] == 0


def test_adp_dup_gate_still_catches_a_true_duplicate():
    """...but two rows for the same player on the SAME snapshot is still a real dup."""
    con, V = _adp_con([_adp_row(snapshot_date="2026-07-18"),
                       _adp_row(snapshot_date="2026-07-18")])
    gate = next(g for g in V._dup_gates(con) if g["gate"].startswith("adp: unique"))
    assert not gate["passed"] and gate["offending_groups"] == 1


# ================================================================================================
# T27 — the value-scale gate (Session H.5 step 1d)
# ================================================================================================
def _hair(rho_sign: float, n: int = 20, seed: int = 0):
    """A per-position frame whose haircut is (anti)correlated with availability by construction."""
    rng = np.random.default_rng(seed)
    avail = np.linspace(6.0, 16.0, n)
    # a real haircut is POSITIVE (mean below the consensus projection); the offset keeps it so at
    # both signs, which matters because `neg_haircut_share` is one of the numbers under test.
    base = 0.5 if rho_sign < 0 else 0.0
    haircut = base + rho_sign * avail / 40.0 + rng.normal(0, 0.005, n)
    return pd.DataFrame({"pos": ["RB"] * n, "adp": np.linspace(5, 170, n),
                         "haircut": haircut, "games_played_mean": avail,
                         "proj_points": np.full(n, 200.0),
                         "mean": 200.0 * (1 - haircut)})


def test_value_scale_gate_passes_when_availability_explains_the_haircut():
    from fantasy_quant.data.validate import value_scale_stats

    stats = value_scale_stats(_hair(-1.0))
    gate = V.value_scale_gate("value_scale", stats["drafted_range"])
    assert gate["passed"], gate
    assert gate["by_position"]["RB"]["rho"] <= -0.5
    assert isinstance(gate["by_position"]["RB"]["n"], int)   # `n` stays an integer in the report


def test_value_scale_gate_fails_when_it_does_not_and_names_the_position():
    """The bar is pre-registered and allowed to fail — a level cut we cannot attribute to
    availability is a modelling finding, not something to caption over."""
    from fantasy_quant.data.validate import value_scale_stats

    stats = value_scale_stats(_hair(+1.0))
    gate = V.value_scale_gate("value_scale", stats["drafted_range"])
    assert not gate["passed"]
    assert gate["failed_positions"] == ["RB"]


def test_value_scale_gate_skips_a_position_too_small_to_be_evidence():
    from fantasy_quant.data.validate import value_scale_stats

    stats = value_scale_stats(_hair(+1.0, n=5))
    gate = V.value_scale_gate("value_scale", stats["drafted_range"])
    assert "RB" in gate["skipped"] and not gate["failed_positions"]
    assert not gate["passed"], "nothing scored is not a pass"


def test_value_scale_stats_separates_the_drafted_range_from_the_deep_board():
    """The exclusion the gate documents has to be *measurable*: off-board rows (null ADP) are kept
    in the frame and reported under `full_board`, never silently dropped."""
    from fantasy_quant.data.validate import value_scale_stats

    good = _hair(-1.0, n=20)
    deep = good.copy()
    deep["adp"] = np.nan                      # a projection with no board row
    deep["haircut"] = -0.5                    # mean ABOVE the consensus projection
    stats = value_scale_stats(pd.concat([good, deep], ignore_index=True))
    assert stats["drafted_range"]["RB"]["n"] == 20
    assert stats["full_board"]["RB"]["n"] == 40
    assert stats["full_board"]["RB"]["neg_haircut_share"] == 0.5
