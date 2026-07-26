"""Board resolution + corpus eligibility — the Session-F.6 contamination guard.

These are regression tests in the strict sense: each one fails on the pre-F.6 code, which read
*every* human draft against a single hardcoded 10-team PPR board. Verified by reverting the fix,
not by inspection.
"""

from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

from fantasy_quant.adp import boards
from fantasy_quant.adp.drift_panel import build_drift_panel, eligible_drafts
from fantasy_quant.draft.opponent_model import build_choice_frame, corpus_funnel


def _ms(y: int, m: int, d: int) -> int:
    return int(dt.datetime(y, m, d, tzinfo=dt.UTC).timestamp() * 1000)


def _mem_con() -> duckdb.DuckDBPyConnection:
    """An in-memory store with the four tables the corpus readers touch."""
    con = duckdb.connect()
    con.execute("""CREATE TABLE sleeper_drafts(
        draft_id VARCHAR, league_id VARCHAR, season BIGINT, draft_type VARCHAR, status VARCHAR,
        teams BIGINT, rounds BIGINT, scoring VARCHAR, start_time_ms DOUBLE, is_human BOOLEAN)""")
    con.execute("""CREATE TABLE sleeper_draft_picks(
        draft_id VARCHAR, season BIGINT, pick_no BIGINT, round BIGINT, draft_slot BIGINT,
        picked_by VARCHAR, gsis_id VARCHAR, player_name VARCHAR, position VARCHAR,
        nfl_team VARCHAR, years_exp BIGINT)""")
    con.execute("""CREATE TABLE adp_snapshots(
        season BIGINT, source VARCHAR, scoring VARCHAR, teams BIGINT, gsis_id VARCHAR,
        name VARCHAR, position VARCHAR, team VARCHAR, adp DOUBLE, stdev DOUBLE,
        pos_rank BIGINT, snapshot_date DATE)""")
    con.execute("""CREATE TABLE ecr_snapshots(
        season BIGINT, as_of DATE, is_preseason BOOLEAN, source VARCHAR, scoring VARCHAR,
        gsis_id VARCHAR, name VARCHAR, position VARCHAR, team VARCHAR, ecr BIGINT,
        ecr_std DOUBLE, pos_rank BIGINT)""")
    return con


def _add_draft(con, draft_id: str, *, season=2023, scoring="ppr", draft_type="snake",
               status="complete", teams=10, is_human=True, start=None, n_picks=6) -> None:
    start = start or _ms(season, 8, 20)          # inside the preseason window
    con.execute("INSERT INTO sleeper_drafts VALUES (?,?,?,?,?,?,?,?,?,?)",
                [draft_id, f"L{draft_id}", season, draft_type, status, teams, 15, scoring,
                 float(start), is_human])
    for i in range(1, n_picks + 1):
        con.execute("INSERT INTO sleeper_draft_picks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    [draft_id, season, i, 1, i, f"mgr{i%2}", f"P{i:03d}", f"Player {i}",
                     "RB" if i % 2 else "WR", "KC", 3])


def _add_board(con, *, season=2023, scoring="ppr", teams=10, n=40, adp_offset=0.0) -> None:
    for i in range(1, n + 1):
        con.execute("INSERT INTO adp_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [season, "ffc", scoring, teams, f"P{i:03d}", f"Player {i}",
                     "RB" if i % 2 else "WR", "KC", float(i) + adp_offset, 2.0, i,
                     dt.date(season, 9, 1)])


def _add_ecr(con, *, season=2025, scoring="ppr", n=40, is_preseason=True, as_of=None) -> None:
    as_of = as_of or dt.date(season, 9, 5)
    for i in range(1, n + 1):
        con.execute("INSERT INTO ecr_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [season, as_of, is_preseason, "fantasypros", scoring, f"P{i:03d}",
                     f"Player {i}", "RB" if i % 2 else "WR", "KC", i, 3.0, i])


# ------------------------------------------------------------------------------------------------
# eligibility — the contamination guard
# ------------------------------------------------------------------------------------------------
def test_choice_frame_admits_only_human_complete_snake_redraft_drafts():
    """The bug this pins: pre-F.6 the frame read dynasty/2QB/IDP/auction/abandoned rooms too."""
    con = _mem_con()
    _add_board(con)
    _add_draft(con, "GOOD")                                   # the only admissible draft
    _add_draft(con, "DYNASTY", scoring="dynasty_ppr")         # a different market
    _add_draft(con, "TWOQB", scoring="2qb")
    _add_draft(con, "IDP", scoring="idp")
    _add_draft(con, "AUCTION", draft_type="auction")          # prices, not pick order
    _add_draft(con, "ABANDONED", status="paused")             # ~44 % of the crawl
    _add_draft(con, "BOT", is_human=False)                    # no opponent identity
    _add_draft(con, "OFFSEASON", start=_ms(2023, 3, 4))       # outside the preseason window

    assert set(eligible_drafts(con)["draft_id"]) == {"GOOD"}
    frame, _ = build_choice_frame(con)
    assert set(frame["draft_id"].unique()) == {"GOOD"}


def test_corpus_funnel_reports_the_gap_between_held_and_usable():
    con = _mem_con()
    _add_board(con)
    _add_draft(con, "GOOD")
    _add_draft(con, "DYNASTY", scoring="dynasty_ppr")
    f = corpus_funnel(con)
    assert f["human_drafts"] == 2          # what we hold
    assert f["eligible"] == 1              # what is redraft
    assert f["with_board"] == 1            # what has a yardstick
    assert f["by_board_source"] == {"ffc": 1}


def test_each_draft_is_scored_against_its_own_board_not_a_default_one():
    """A half-PPR 12-team room must read the half-PPR 12-team board, not 10-team PPR."""
    con = _mem_con()
    _add_board(con, scoring="ppr", teams=10, adp_offset=0.0)
    _add_board(con, scoring="half-ppr", teams=12, adp_offset=100.0)   # deliberately far apart
    _add_draft(con, "PPR10", scoring="ppr", teams=10)
    _add_draft(con, "HALF12", scoring="half_ppr", teams=12)

    frame, _ = build_choice_frame(con)
    ppr = frame[frame["draft_id"] == "PPR10"]["adp_s"]
    half = frame[frame["draft_id"] == "HALF12"]["adp_s"]
    assert not ppr.empty and not half.empty
    # the offset board is ~100 ADP points later; scaled by _ADP_SCALE=50 that is ~+2 in adp_s
    assert half.min() > ppr.max()


# ------------------------------------------------------------------------------------------------
# the ECR fallback
# ------------------------------------------------------------------------------------------------
def test_resolve_board_prefers_ffc_when_both_exist():
    con = _mem_con()
    _add_board(con, season=2024)
    _add_ecr(con, season=2024)
    board, src = boards.resolve_board(con, 2024, "ppr", 10)
    assert src == boards.FFC
    assert len(board) == 40


def test_resolve_board_falls_back_to_ecr_when_ffc_never_published():
    con = _mem_con()
    _add_ecr(con, season=2025)                     # FFC has no 2025 board, live-verified
    board, src = boards.resolve_board(con, 2025, "ppr", 10)
    assert src == boards.ECR
    assert set(board.columns) >= {"gsis_id", "adp", "stdev", "snapshot_date"}
    assert board["adp"].min() == 1.0               # ECR rank stands in for pick order


def test_ecr_rank_is_calibrated_onto_the_adp_scale_and_truncated():
    """Raw ECR rank is not ADP: it runs ~544 deep against FFC's ~200 and is ~2x uncompressed.

    Left raw it manufactures huge fake reaches for deep players (the first F.6 panel run put a
    fringe 2025 WR at +17.5 rounds). With an overlap season present the fallback must map rank
    onto the ADP scale and stop at FFC's depth.
    """
    con = _mem_con()
    # 2024 has both sources: FFC boards 60 players compressed into ADP 1..60,
    # while ECR ranks 200 players uncompressed.
    for i in range(1, 61):
        con.execute("INSERT INTO adp_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [2024, "ffc", "ppr", 10, f"P{i:03d}", f"Player {i}", "RB", "KC",
                     float(i), 2.0, i, dt.date(2024, 9, 1)])
    _add_ecr(con, season=2024, n=200)
    _add_ecr(con, season=2025, n=200)

    board, src = boards.resolve_board(con, 2025, "ppr", 10)
    assert src == boards.ECR
    assert len(board) <= 60, "the fallback must stop at FFC's board depth, not run 200 deep"
    assert board["adp"].max() <= 61, "rank was not mapped onto the ADP scale"


def test_calibration_is_absent_rather_than_invented_without_an_overlap_season():
    con = _mem_con()
    _add_ecr(con, season=2025)
    assert boards.ecr_to_adp_calibration(con, "ppr") is None


def test_ecr_fallback_refuses_a_post_season_retouch():
    """The 2023-PPR trap: as_of 2024-02-12, is_preseason=False. It must never board a draft."""
    con = _mem_con()
    _add_ecr(con, season=2023, is_preseason=False, as_of=dt.date(2024, 2, 12))
    board, src = boards.resolve_board(con, 2023, "ppr", 10)
    assert board.empty and src == ""


def test_ecr_fallback_is_opt_out():
    con = _mem_con()
    _add_ecr(con, season=2025)
    assert boards.resolve_board(con, 2025, "ppr", 10, allow_ecr=False)[1] == ""


def test_panel_labels_every_row_with_the_source_that_boarded_it():
    con = _mem_con()
    _add_board(con, season=2023)
    _add_ecr(con, season=2025)
    _add_draft(con, "FFC23", season=2023)
    _add_draft(con, "ECR25", season=2025, start=_ms(2025, 8, 20))

    panel = build_drift_panel(con, allow_ecr=True)
    got = panel.groupby("draft_id")["board_source"].first().to_dict()
    assert got == {"FFC23": "ffc", "ECR25": "ecr"}
    # and the headline filter is a one-liner the caller can trust
    assert set(panel[panel["board_source"] == "ffc"]["season"].unique()) == {2023}


def test_panel_without_ecr_drops_the_unboarded_season_rather_than_guessing():
    con = _mem_con()
    _add_board(con, season=2023)
    _add_ecr(con, season=2025)
    _add_draft(con, "FFC23", season=2023)
    _add_draft(con, "ECR25", season=2025, start=_ms(2025, 8, 20))

    panel = build_drift_panel(con, allow_ecr=False)
    assert set(panel["season"].unique()) == {2023}


def test_nearest_board_size_maps_odd_league_sizes_to_a_published_board():
    assert boards.nearest_board_size(8) == 10
    assert boards.nearest_board_size(14) == 12
    assert boards.nearest_board_size(12) == 12


def test_resolved_boards_are_read_once_per_cell():
    con = _mem_con()
    _add_board(con, season=2023)
    keys = [(2023, "ppr", 10)] * 5
    out = boards.resolve_boards(con, keys)
    assert list(out) == [(2023, "ppr", 10)]


def test_empty_corpus_returns_an_empty_frame_not_a_crash():
    con = _mem_con()
    frame, feats = build_choice_frame(con)
    assert frame.empty and "adp_s" in feats


def test_pandas_frame_contract_survives_the_extra_columns():
    """`group`/`chosen`/features are what the fitter reads; draft_id and board_source ride along."""
    con = _mem_con()
    _add_board(con)
    _add_draft(con, "GOOD")
    frame, feats = build_choice_frame(con)
    assert {"group", "season", "draft_id", "board_source", "chosen"} <= set(frame.columns)
    assert pd.api.types.is_integer_dtype(frame["chosen"])
    assert frame.groupby("group")["chosen"].max().eq(1).all()
