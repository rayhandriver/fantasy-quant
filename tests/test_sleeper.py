"""Step 0.10 — offline unit tests for the Sleeper draft ingest (no network, no DB).

Drives the pure parse/crosswalk/aggregate helpers and the pure validation gates against a
committed real-payload fixture (draft ``1381667884610109440``: a 10-team/15-round PPR bot mock,
human at slot 3). The network + DuckDB wrappers are exercised by ``steps/phase0_10_sleeper_ingest``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from fantasy_quant.data.sources import sleeper
from fantasy_quant.data.validate import (
    sleeper_human_slot_gate,
    sleeper_no_dup_picks_gate,
    sleeper_picks_gate,
)

FIX = Path(__file__).parent / "fixtures" / "sleeper"
DID = "1381667884610109440"


def _draft() -> dict:
    return json.loads((FIX / f"draft_{DID}.json").read_text())


def _picks() -> list[dict]:
    return json.loads((FIX / f"picks_{DID}.json").read_text())


# --- parsing -------------------------------------------------------------------------------
def test_parse_draft_meta():
    meta = sleeper.parse_draft_meta(_draft())
    assert meta["draft_id"] == DID
    assert meta["teams"] == 10 and meta["rounds"] == 15
    assert meta["draft_type"] == "snake" and meta["scoring"] == "ppr"
    assert meta["source"] == "mock"          # solo mock -> not a real league
    assert meta["human_slot"] == 3           # draft_order's single entry (the user)
    assert meta["human_user_id"] == "1381536159267573760"


def test_parse_picks_shape_and_human_flag():
    df = sleeper.parse_picks(_draft(), _picks())
    assert len(df) == 150
    assert sorted(df["pick_no"]) == list(range(1, 151))   # contiguous, no gap/dup
    # exactly one team's worth of picks (15) are the human's, and only those carry picked_by
    assert df["is_human_slot"].sum() == 15
    assert df.loc[df["is_human_slot"], "picked_by"].notna().all()
    assert df.loc[~df["is_human_slot"], "picked_by"].isna().all()
    assert (df.loc[df["is_human_slot"], "draft_slot"] == 3).all()


# --- crosswalk -----------------------------------------------------------------------------
def _stub_ids(picks: pd.DataFrame) -> pd.DataFrame:
    """A tiny player_ids stub: map the first skill pick to a whitespace-padded gsis (stored as a
    DOUBLE sleeper_id, like nflverse) so the cast + strip paths are exercised."""
    skill = picks[picks["position"].isin(["QB", "RB", "WR", "TE"])].iloc[0]
    return pd.DataFrame({
        "sleeper_id": [float(skill["sleeper_player_id"])],   # DOUBLE, like nflverse
        "gsis_id": ["  00-0012345 "],                        # whitespace-padded, like nflverse
    })


def test_crosswalk_casts_double_and_strips_whitespace():
    picks = sleeper.parse_picks(_draft(), _picks())
    out = sleeper.crosswalk_picks_to_gsis(picks, _stub_ids(picks))
    skill = picks[picks["position"].isin(["QB", "RB", "WR", "TE"])].iloc[0]
    hit = out[out["sleeper_player_id"] == skill["sleeper_player_id"]].iloc[0]
    assert hit["gsis_id"] == "00-0012345"      # matched, stripped


def test_crosswalk_bridges_def_to_team_key():
    picks = sleeper.parse_picks(_draft(), _picks())
    out = sleeper.crosswalk_picks_to_gsis(picks, _stub_ids(picks))
    defs = out[out["position"].isin(["DEF", "DST"])]
    assert len(defs) > 0
    assert defs["gsis_id"].isna().all()                       # team D has no gsis
    assert (defs["dst_team"] == defs["sleeper_player_id"]).all()


def test_skill_match_rate_reports_cohort():
    picks = sleeper.parse_picks(_draft(), _picks())
    out = sleeper.crosswalk_picks_to_gsis(picks, _stub_ids(picks))
    cov = sleeper.skill_match_rate(out)
    assert cov["skill_rows"] > 0
    assert 0.0 <= cov["skill_match_rate"] <= 1.0    # stub matches exactly one -> low but valid


# --- derived board + tendencies ------------------------------------------------------------
def test_build_mock_adp_contract_and_single_draft_values():
    picks = sleeper.parse_picks(_draft(), _picks())
    out = sleeper.crosswalk_picks_to_gsis(picks, _stub_ids(picks))
    board = sleeper.build_mock_adp(out, snapshot_date="2026-07-11", season=2026)
    expected_cols = {"season", "snapshot_date", "source", "format", "scoring", "teams",
                     "gsis_id", "name", "position", "team", "adp", "pos_rank",
                     "times_drafted", "stdev", "high", "low", "total_drafts"}
    assert expected_cols.issubset(board.columns)
    assert (board["source"] == "sleeper_mock").all()
    assert (board["total_drafts"] == 1).all()
    # one draft -> adp == the pick number, no spread, high == low == pick
    assert (board["stdev"] == 0).all()
    assert (board["high"] == board["low"]).all()
    assert board["pos_rank"].min() == 1
    assert board["adp"].is_monotonic_increasing


def test_build_tendencies_keys_by_slot_for_a_mock():
    picks = sleeper.parse_picks(_draft(), _picks())
    out = sleeper.crosswalk_picks_to_gsis(picks, _stub_ids(picks))
    tend = sleeper.build_tendencies(out)
    # a solo mock has <2 distinct managers -> keyed by slot, all ten seats present
    assert (tend["key_type"] == "slot").all()
    assert tend["drafter"].nunique() == 10


def test_build_tendencies_keys_by_manager_when_multi_manager():
    picks = sleeper.parse_picks(_draft(), _picks())
    # simulate a real league: two distinct managers own the picks
    picks = picks.copy()
    picks["picked_by"] = ["mgrA" if i % 2 else "mgrB" for i in range(len(picks))]
    tend = sleeper.build_tendencies(picks)
    assert (tend["key_type"] == "manager").all()
    assert set(tend["drafter"]) == {"mgrA", "mgrB"}


# --- pure gates ----------------------------------------------------------------------------
def test_sleeper_picks_gate_pass_and_fail():
    ok = sleeper_picks_gate("g", n_picks=150, expected_picks=150, min_pick=1,
                            max_pick=150, n_distinct=150)
    assert ok["passed"]
    short = sleeper_picks_gate("g", n_picks=149, expected_picks=150, min_pick=1,
                               max_pick=149, n_distinct=149)
    assert not short["passed"]
    dup = sleeper_picks_gate("g", n_picks=150, expected_picks=150, min_pick=1,
                             max_pick=150, n_distinct=149)   # a duplicate pick_no
    assert not dup["passed"]


def test_sleeper_no_dup_picks_gate():
    # incompleteness is reported, not failed (a crawled corpus has abandoned drafts); dups fail.
    ok = sleeper_no_dup_picks_gate("g", 0, n_incomplete=116, n_total=266)
    assert ok["passed"] and ok["incomplete_drafts"] == 116
    assert not sleeper_no_dup_picks_gate("g", 2)["passed"]


def test_sleeper_human_slot_gate():
    assert sleeper_human_slot_gate("g", 3, 3)["passed"]
    assert not sleeper_human_slot_gate("g", 3, 2)["passed"]
    na = sleeper_human_slot_gate("g", 0, 0)          # no mocks -> not applicable, passes
    assert na["passed"] and na["applicable"] is False


# --- corpus crawler (offline, fake client) -------------------------------------------------
def test_participants_from_draft():
    # the real bot-mock fixture has one seated user (the human); a synthetic lobby has many.
    assert sleeper.participants_from_draft(_draft()) == {"1381536159267573760"}
    lobby = {"draft_order": {"U1": 1, "U2": 2, "U3": 3}}
    assert sleeper.participants_from_draft(lobby) == {"U1", "U2", "U3"}
    assert sleeper.participants_from_draft({}) == set()


def test_build_mock_adp_accepts_source_label():
    picks = sleeper.parse_picks(_draft(), _picks())
    out = sleeper.crosswalk_picks_to_gsis(picks, _stub_ids(picks))
    board = sleeper.build_mock_adp(out, snapshot_date="2026-07-11", season=2026,
                                   source="sleeper_human")
    assert (board["source"] == "sleeper_human").all()


def test_manager_profiles():
    df = pd.DataFrame({
        "picked_by": ["A", "A", "A", "B", "B", None],
        "draft_id": ["d1", "d1", "d2", "d1", "d1", "d1"],
        "pick_no": [1, 21, 3, 2, 19, 5],
        "position": ["RB", "WR", "RB", "QB", "WR", "TE"],
        "nfl_team": ["ATL", "LAR", "ATL", "PHI", "LAR", "KC"],
        "gsis_id": [None, None, None, None, None, None],
        "_adp": [3.0, 18.0, 4.0, 10.0, 22.0, 8.0],
    })
    prof = sleeper.manager_profiles(df)
    assert set(prof["manager"]) == {"A", "B"}            # the null (bot) row is excluded
    a = prof[prof["manager"] == "A"].iloc[0]
    assert a["n_drafts"] == 2 and a["n_picks"] == 3
    assert a["pos_share_RB"] == pytest.approx(66.7, abs=0.2)
    assert "ATL" in a["fav_teams"]
    assert a["avg_reach"] == pytest.approx(((3 - 1) + (18 - 21) + (4 - 3)) / 3, abs=0.01)


def test_load_seeds(tmp_path, monkeypatch):
    f = tmp_path / "seeds.txt"
    f.write_text("# comment\n123456\nalice  # a friend\n\nbob\nleague:999\ndraft:777\n")
    monkeypatch.setattr(sleeper, "SEEDS_FILE", f)
    seeds = sleeper.load_seeds()
    assert seeds["draft_ids"] == ["123456", "777"]
    assert seeds["usernames"] == ["alice", "bob"]
    assert seeds["league_ids"] == ["999"]


class _Resp:
    def __init__(self, data, status=200):
        self._d, self.status_code = data, status

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


class _FakeClient:
    """Minimal stand-in for httpx.Client keyed on the API path (returns 404 for unknown paths)."""
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def get(self, url):
        path = url.replace(sleeper.BASE, "")
        self.calls.append(path)
        return _Resp(self.routes.get(path)) if path in self.routes else _Resp(None, 404)


def test_crawl_expand_discovers_and_participant_expands(monkeypatch, tmp_path):
    monkeypatch.setattr(sleeper, "SLEEPER_RAW", tmp_path)    # keep payload archival out of data/
    routes = {
        "/user/alice": {"user_id": "U1"},
        "/user/U1/leagues/nfl/2024": [{"league_id": "L1"}],
        "/league/L1/drafts": [{"draft_id": "D1"}],
        "/user/U1/drafts/nfl/2024": [],
        # D1 is a real 2-manager draft -> participant expansion reaches U2
        "/draft/D1": {"draft_id": "D1", "draft_order": {"U1": 1, "U2": 2}},
        "/user/U2/leagues/nfl/2024": [{"league_id": "L2"}],
        "/league/L2/drafts": [{"draft_id": "D2"}],
        "/user/U2/drafts/nfl/2024": [],
        "/draft/D2": {"draft_id": "D2", "draft_order": {"U2": 1}},
    }
    client = _FakeClient(routes)
    found = sleeper.crawl_expand(client, seed_usernames=["alice"], seasons=["2024"], max_drafts=50)
    assert set(found) == {"D1", "D2"}          # D1 from alice's history, D2 via U2 expansion


def test_crawl_expand_league_seed_snowballs(monkeypatch, tmp_path):
    """Seed one league_id -> its draft + members, then snowball through a co-manager (U3)
    discovered inside a downstream human draft (D2) to reach D3."""
    monkeypatch.setattr(sleeper, "SLEEPER_RAW", tmp_path)
    routes = {
        "/league/LG1/drafts": [{"draft_id": "D1"}],
        "/league/LG1/users": [{"user_id": "U1"}, {"user_id": "U2"}],
        "/user/U1/leagues/nfl/2024": [{"league_id": "LG2"}],
        "/league/LG2/drafts": [{"draft_id": "D2"}],
        "/user/U1/drafts/nfl/2024": [],
        "/draft/D2": {"draft_id": "D2", "draft_order": {"U1": 1, "U3": 2}},  # human -> queue U3
        "/user/U2/leagues/nfl/2024": [],
        "/user/U2/drafts/nfl/2024": [],
        "/user/U3/leagues/nfl/2024": [{"league_id": "LG3"}],
        "/league/LG3/drafts": [{"draft_id": "D3"}],
        "/user/U3/drafts/nfl/2024": [],
        "/draft/D3": {"draft_id": "D3", "draft_order": {"U3": 1}},          # solo -> stop
    }
    client = _FakeClient(routes)
    found = sleeper.crawl_expand(client, seed_league_ids=["LG1"], seasons=["2024"], max_drafts=50)
    assert set(found) == {"D1", "D2", "D3"}


def test_crawl_expand_skips_existing_ids(monkeypatch, tmp_path):
    monkeypatch.setattr(sleeper, "SLEEPER_RAW", tmp_path)
    routes = {"/draft/D1": {"draft_id": "D1", "draft_order": {"U1": 1}}}  # a bot mock (1 seat)
    client = _FakeClient(routes)
    found = sleeper.crawl_expand(client, seed_draft_ids=["D1"], seasons=["2024"],
                                 existing_ids={"D1"})
    assert found == []                          # already in the store -> not re-crawled


# --- crawl resumability (Session F.5) ---------------------------------------------------------
def _mem_con():
    """An in-memory DuckDB — the crawl-state helpers are the one part that needs a real store."""
    import duckdb
    return duckdb.connect()


def test_crawl_state_enqueue_is_idempotent_and_retires():
    con = _mem_con()
    sleeper.ensure_crawl_state(con)
    sleeper.enqueue_drafts(con, ["D1", "D2", "D1"])       # dup within the call
    sleeper.enqueue_drafts(con, ["D2", "D3"])             # dup across calls
    assert sorted(sleeper.queue_todo(con)) == ["D1", "D2", "D3"]
    sleeper.mark_queue(con, ["D1"], "done")
    sleeper.mark_queue(con, ["D2"], "dead")
    assert sleeper.queue_todo(con) == ["D3"]              # neither done nor dead comes back


def test_crawled_users_round_trips_for_resume():
    con = _mem_con()
    assert sleeper.crawled_users(con) == set()
    sleeper.mark_user_crawled(con, "U1")
    sleeper.mark_user_crawled(con, "U1")                  # idempotent
    sleeper.mark_user_crawled(con, "U2")
    assert sleeper.crawled_users(con) == {"U1", "U2"}


def test_seed_users_from_profiles_orders_by_picks():
    con = _mem_con()
    assert sleeper.seed_users_from_profiles(con) == []    # no table yet -> no seeds
    con.execute("CREATE TABLE sleeper_manager_profiles (manager VARCHAR, n_picks INTEGER)")
    con.execute("INSERT INTO sleeper_manager_profiles VALUES ('quiet', 15), ('busy', 300)")
    assert sleeper.seed_users_from_profiles(con) == ["busy", "quiet"]


def test_crawl_expand_still_expands_through_an_already_ingested_draft(monkeypatch, tmp_path):
    """The dead-end regression: D1 is already in the store, so it is *not* a new find — but its
    participants must still be queued, or a re-run's frontier collapses to nothing."""
    monkeypatch.setattr(sleeper, "SLEEPER_RAW", tmp_path)
    routes = {
        "/user/U1/leagues/nfl/2024": [{"league_id": "L1"}],
        "/league/L1/drafts": [{"draft_id": "D1"}],
        "/user/U1/drafts/nfl/2024": [],
        "/draft/D1": {"draft_id": "D1", "draft_order": {"U1": 1, "U2": 2}},
        "/user/U2/leagues/nfl/2024": [{"league_id": "L2"}],
        "/league/L2/drafts": [{"draft_id": "D2"}],
        "/user/U2/drafts/nfl/2024": [],
        "/draft/D2": {"draft_id": "D2", "draft_order": {"U2": 1}},
    }
    routes["/user/alice"] = {"user_id": "U1"}
    found = sleeper.crawl_expand(_FakeClient(routes), seed_usernames=["alice"], seasons=["2024"],
                                 max_drafts=50, existing_ids={"D1"})
    assert "D2" in found          # reached only by expanding through the pre-existing D1
    assert "D1" not in found      # ...without re-ingesting it


def test_crawl_expand_reports_finished_users(monkeypatch, tmp_path):
    monkeypatch.setattr(sleeper, "SLEEPER_RAW", tmp_path)
    routes = {"/user/alice": {"user_id": "U1"},
              "/user/U1/leagues/nfl/2024": [], "/user/U1/drafts/nfl/2024": []}
    seen: list[str] = []
    sleeper.crawl_expand(_FakeClient(routes), seed_usernames=["alice"], seasons=["2024"],
                         on_user_done=seen.append)
    assert seen == ["U1"]


def test_archive_payloads_flag_suppresses_raw_writes(monkeypatch, tmp_path):
    """Bulk crawls turn the T7 archive off — ~20k files is not an audit trail anyone can use."""
    monkeypatch.setattr(sleeper, "SLEEPER_RAW", tmp_path)
    client = _FakeClient({"/draft/D1": {"draft_id": "D1", "draft_order": {"U1": 1}}})
    monkeypatch.setattr(sleeper, "ARCHIVE_PAYLOADS", False)
    sleeper.fetch_draft(client, "D1")
    assert not list(tmp_path.rglob("*.json"))
    monkeypatch.setattr(sleeper, "ARCHIVE_PAYLOADS", True)
    sleeper.fetch_draft(client, "D1")
    assert len(list(tmp_path.rglob("*.json"))) == 1


def test_rate_limiter_paces_calls():
    import time as _t
    lim = sleeper._RateLimiter(50.0)          # 20 ms apart
    t0 = _t.monotonic()
    for _ in range(5):
        lim.wait()
    assert _t.monotonic() - t0 >= 0.06        # 4 enforced gaps, first call is free
    assert sleeper._RateLimiter(0).wait() is None   # disabled -> no sleep


def test_discover_draft_ids_skips_already_expanded_leagues():
    """League expansion is the dominant discovery cost and co-managers share leagues, so the
    /league/<id>/drafts call must be spent once per league per run, not once per member."""
    routes = {
        "/user/U1/leagues/nfl/2024": [{"league_id": "L1"}],
        "/user/U2/leagues/nfl/2024": [{"league_id": "L1"}],   # same league, different member
        "/league/L1/drafts": [{"draft_id": "D1"}],
        "/user/U1/drafts/nfl/2024": [], "/user/U2/drafts/nfl/2024": [],
    }
    client = _FakeClient(routes)
    seen: set[str] = set()
    a = sleeper.discover_draft_ids(client, user_id="U1", seasons=["2024"], seen_leagues=seen)
    b = sleeper.discover_draft_ids(client, user_id="U2", seasons=["2024"], seen_leagues=seen)
    assert a == ["D1"] and b == []                       # U2 adds nothing new
    assert client.calls.count("/league/L1/drafts") == 1   # ...and costs no second league call
    assert seen == {"L1"}


def test_crawled_leagues_round_trips():
    con = _mem_con()
    assert sleeper.crawled_leagues(con) == set()
    sleeper.mark_leagues_crawled(con, ["L1", "L2", "L1"])
    assert sleeper.crawled_leagues(con) == {"L1", "L2"}


def _board_con(drafts, picks):
    con = _mem_con()
    con.register("_d", pd.DataFrame(drafts))
    con.register("_p", pd.DataFrame(picks))
    con.execute("CREATE TABLE sleeper_drafts AS SELECT * FROM _d")
    con.execute("CREATE TABLE sleeper_draft_picks AS SELECT * FROM _p")
    return con


def _pick(did, n, gsis):
    return {"draft_id": did, "season": 2024, "pick_no": n, "round": 1, "draft_slot": n,
            "picked_by": f"m{n}", "sleeper_player_id": str(1000 + n), "position": "RB",
            "player_name": f"P{n}", "nfl_team": "KC", "gsis_id": gsis, "dst_team": None}


def test_adp_board_is_redraft_only_and_labels_true_scoring():
    """The crawled corpus is mostly dynasty/2QB/IDP. Pooling those onto a board labelled 'ppr'
    prices a startup dynasty room as redraft PPR — measured 82% contamination at frontier scale."""
    drafts = [
        {"draft_id": "A", "season": 2024, "teams": 10, "scoring": "ppr", "is_human": True,
         "status": "complete", "draft_type": "snake", "start_time_ms": 1_724_000_000_000},
        {"draft_id": "B", "season": 2024, "teams": 10, "scoring": "half_ppr", "is_human": True,
         "status": "complete", "draft_type": "snake", "start_time_ms": 1_724_000_000_000},
        {"draft_id": "C", "season": 2024, "teams": 10, "scoring": "dynasty_2qb", "is_human": True,
         "status": "complete", "draft_type": "snake", "start_time_ms": 1_724_000_000_000},
        {"draft_id": "D", "season": 2024, "teams": 10, "scoring": "idp", "is_human": True,
         "status": "complete", "draft_type": "snake", "start_time_ms": 1_724_000_000_000},
    ]
    picks = [_pick(d, i + 1, f"00-000{i}") for d in "ABCD" for i in range(3)]
    con = _board_con(drafts, picks)
    board = sleeper.refresh_human_adp(con)
    assert set(board["scoring"]) == {"ppr", "half-ppr"}       # FFC vocabulary, both formats kept
    assert board["source"].eq("sleeper_human").all()
    # each redraft board is built from its own draft alone, never pooled across formats
    assert set(board["total_drafts"]) == {1}
    # dynasty/IDP contributed nothing
    assert len(board) == 6


def test_adp_board_empty_when_corpus_has_no_redraft():
    drafts = [{"draft_id": "C", "season": 2024, "teams": 10, "scoring": "dynasty", "is_human": True,
               "status": "complete", "draft_type": "snake", "start_time_ms": 1_724_000_000_000}]
    con = _board_con(drafts, [_pick("C", 1, "00-0001")])
    assert sleeper.refresh_human_adp(con).empty
