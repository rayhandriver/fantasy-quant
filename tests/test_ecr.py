"""Phase 0.11 — offline unit tests for the FantasyPros ECR ingest (no network, no DB).

Drives the pure parse half against a committed real-payload fixture (the 2020 PPR cheatsheet,
trimmed to its meta block + the first 12 players). The network pull and the DuckDB write are
exercised by ``steps/phase0_11_ecr.py``.

The tests that matter most here are the **PIT** ones: the archive is a kickoff-dated snapshot, and
the whole design rests on that being visible in the data and enforced by ``ecr_asof`` rather than
merely documented.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from fantasy_quant.data.sources import ecr

FIX = Path(__file__).parent / "fixtures" / "ecr" / "ecr_ppr_2020.html"


def _html() -> str:
    return FIX.read_text()


# --- parsing ------------------------------------------------------------------------------------
def test_extract_ecr_json_finds_the_payload():
    data = ecr.extract_ecr_json(_html())
    assert data["year"] == "2020"
    assert data["ranking_type_name"] == "draft"
    assert len(data["players"]) == 12


def test_extract_ecr_json_raises_without_payload():
    with pytest.raises(ValueError, match="no ecrData"):
        ecr.extract_ecr_json("<html><body>no rankings here</body></html>")


def test_parse_ecr_shape_and_ordering():
    df = ecr.parse_ecr(_html(), scoring="ppr")
    assert len(df) == 12
    assert df["season"].eq(2020).all()
    assert df["scoring"].eq("ppr").all()
    assert df["source"].eq(ecr.SOURCE).all()
    # rank 1 is the consensus #1 overall, and the board is served in rank order
    assert df["ecr"].is_monotonic_increasing
    assert df.iloc[0]["name"] == "Christian McCaffrey"
    assert df.iloc[0]["ecr"] == 1


def test_parse_ecr_keeps_the_disagreement_columns():
    """``ecr_std``/min/max are the reason to scrape the rank pages at all — the projection
    pages we already had carry points, not the experts' spread."""
    df = ecr.parse_ecr(_html(), scoring="ppr")
    for col in ("ecr_min", "ecr_max", "ecr_avg", "ecr_std"):
        assert df[col].notna().all(), f"{col} did not survive the parse"
    assert (df["ecr_max"] >= df["ecr_min"]).all()
    assert (df["ecr_std"] >= 0).all()


def test_parse_ecr_pos_rank_is_an_integer():
    """FantasyPros ships pos_rank as "RB1"/"WR12"; it has to become an int to join the ADP board."""
    df = ecr.parse_ecr(_html(), scoring="ppr")
    assert pd.api.types.is_numeric_dtype(df["pos_rank"])
    rb1 = df[(df["position"] == "RB") & (df["pos_rank"] == 1)]
    assert len(rb1) == 1 and rb1.iloc[0]["name"] == "Christian McCaffrey"


# --- the PIT property -----------------------------------------------------------------------------
def test_as_of_is_the_boards_own_timestamp_not_today():
    """The archived 2020 board is stamped in September 2020 — this is what makes it unusable as a
    draft-day feature, so the parse must carry the real stamp rather than the scrape date."""
    df = ecr.parse_ecr(_html(), scoring="ppr")
    as_of = df["as_of"].iloc[0]
    assert isinstance(as_of, dt.date)
    assert as_of.year == 2020
    assert as_of >= dt.date(2020, 9, 1), "a draft-season board should be stamped at/after kickoff"


def test_is_preseason_flags_a_board_retouched_after_its_season():
    """The live 2023 PPR board carries as_of 2024-02-12 — re-touched after the Super Bowl. Such a
    board is not a preseason consensus and must be flagged, not silently mixed in."""
    assert ecr._is_preseason(pd.Series([dt.date(2020, 9, 7)]), 2020).iloc[0]
    assert ecr._is_preseason(pd.Series([dt.date(2020, 9, 15)]), 2020).iloc[0]
    assert not ecr._is_preseason(pd.Series([dt.date(2021, 2, 12)]), 2020).iloc[0]
    assert not ecr._is_preseason(pd.Series([dt.date(2020, 11, 1)]), 2020).iloc[0]


def test_parse_ecr_sets_is_preseason():
    df = ecr.parse_ecr(_html(), scoring="ppr")
    assert df["is_preseason"].all()


def test_ecr_asof_refuses_a_future_board(tmp_path):
    """The core guard: a draft-day as-of must come back EMPTY rather than silently returning a
    board stamped after the draft. This is what stops 16.8 from quietly using look-ahead."""
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect(str(tmp_path / "t.duckdb"))
    df = ecr.parse_ecr(_html(), scoring="ppr")
    df["gsis_id"] = None
    con.register("_f", df[[c for c in ecr.CONTRACT_COLS if c in df.columns]])
    con.execute("CREATE TABLE ecr_snapshots AS SELECT * FROM _f")

    assert ecr.ecr_asof(con, 2020, "2020-08-15").empty       # a typical draft day
    assert len(ecr.ecr_asof(con, 2020, "2020-09-30")) == 12   # after the board's own stamp
    con.close()
