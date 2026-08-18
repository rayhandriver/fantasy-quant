"""Session K1 — the app, and the bars it was pre-registered against.

Offline throughout: a synthetic board, a stub connection, no DuckDB, no Streamlit runtime. The app's
*rendering* is verified live by ``steps/session_k1_app.py`` (which boots the server and drives it);
what is tested here is the property the whole session rests on — **the app and the CLI are one
computation and two renderers**, so a number cannot move between them.

⚠ The B1 test is deliberately *not* "call both and compare the output strings". Two implementations
that agree today are two implementations that can disagree tomorrow; the repo has that failure on
file three times (T18, F.5, T27). The test asserts the **structure** that makes disagreement
impossible — both surfaces resolve to the same function object — and then, separately, that a real
draft driven through the app's own entry points reproduces the CLI's frames exactly.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fantasy_quant.draft import session
from fantasy_quant.draft.config import LeagueSettings

# `app` is a top-level package; pytest's `pythonpath = ["src", "."]` puts it on the path.
app_engine = pytest.importorskip("app.engine")
settings_form = pytest.importorskip("app.settings_form")


def behavioral_room(n: int) -> str:
    """``n`` seats, none of which needs a risk model.

    ★ Why the tests cannot just say ``"realistic"``: the shipped room contains ``value_hawk``,
    whose ``objective="portfolio_ce"`` routes it to the Phase-9 greedy, which needs a real
    ``RiskModel`` built from a real value index. Handing it ``risk=None`` **raises** rather than
    silently falling back to the behavioural softmax — that guard *is* T27, and an offline test
    that quietly disabled it would be testing a room the app never runs. So these tests use a room
    of behavioural seats and the live driver (``steps/session_k1_app.py``) exercises the real one.
    """
    return ",".join((["balanced", "chalk", "autopilot", "safe_floor", "upside_chaser",
                      "reacher", "homer", "zero_rb", "rookie_hawk", "balanced"])[:n])


@pytest.fixture
def board() -> pd.DataFrame:
    """A synthetic board deep enough for a 10-team, 15-round draft with legal rosters."""
    rng = np.random.default_rng(0)
    pos = (["RB"] * 60 + ["WR"] * 70 + ["QB"] * 24 + ["TE"] * 24 + ["K"] * 12 + ["DST"] * 12)
    rng.shuffle(pos)
    n = len(pos)
    return pd.DataFrame({
        "gsis_id": [f"00-{i:07d}" for i in range(n)],
        "name": [f"Player {i}" for i in range(n)],
        "position": pos,
        "team": ["FA"] * n,
        "adp": np.arange(1, n + 1, dtype=float),
        "stdev": rng.uniform(1, 12, n),
        "pos_rank": np.arange(1, n + 1),
        "snapshot_date": pd.Timestamp("2026-07-30"),
        "proj_points": np.linspace(320, 40, n),
        "mean": np.linspace(300, 30, n),
        "games_played_mean": rng.uniform(8, 17, n),
        "base_value": np.linspace(140, -60, n),
        "vbd": np.linspace(150, -50, n),
        "overall_rank": np.arange(1, n + 1),
        "upside": rng.uniform(-1, 1, n),
        "floor": rng.uniform(-1, 1, n),
        "tail_risk": rng.uniform(0, 2, n),
        "boom_prob_live": np.where(np.arange(n) % 7 == 0, np.nan, rng.uniform(0, 0.5, n)),
        "bust_prob_live": np.where(np.arange(n) % 7 == 0, np.nan, rng.uniform(0, 0.5, n)),
    })


@pytest.fixture
def built(board) -> dict:
    return {"board": board, "value_index": pd.DataFrame(), "risk": None,
            "source": "ffc", "n_base_value": int(board["base_value"].notna().sum()), "lam": 0.01}


# ------------------------------------------------------------------------------------------------
# B1 — the app and the CLI cannot disagree
# ------------------------------------------------------------------------------------------------
def test_b1_the_cli_and_the_app_resolve_to_the_same_functions():
    """★ B1, structurally: there is ONE computation, and every surface is a renderer over it.

    Comparing two implementations' *output* proves they agree on the case tested. Comparing their
    *identity* proves they cannot disagree at all — which is the claim Session K1 actually makes,
    and the only version of it that survives someone editing one file next month.

    K1.5 broadened it out of necessity and the breadth is an improvement: ``app/main.py`` is a
    router now (14.K) and imports no engine function at all, so the assertion moved onto the four
    modules that actually render. Checking every renderer is a stronger statement than checking
    the one file that happened to hold them in K1.
    """
    import app.draft_room as room
    import app.room_grid as grid
    import app.views as app_views
    import steps.mock_draft as cli

    # `app/screens.py` is deliberately absent: it holds the Settings/Board/Cost pages and reaches
    # every derived frame through `app/views.py`, so it has no `session` import to check. That it
    # cannot get one wrong is the point of the layering, not a gap in the test.
    surfaces = [cli, room, grid, app_views]
    for name in ("board_view", "explain_chain", "summary_table", "roster_view", "odds_table",
                 "drift_frames", "seat_map_from", "seat_label", "advance", "room_mix",
                 "resolve_pick", "room_grid", "project_view", "advance_one"):
        for mod in surfaces:
            assert getattr(mod.session, name) is getattr(session, name), f"{mod.__name__}.{name}"

    # ...and the CLI's re-exports are the session objects themselves, not copies of them
    assert cli.advance is session.advance
    assert cli.seat_map_from is session.seat_map_from
    assert cli.room_mix is session.room_mix


def test_b1_a_draft_driven_through_the_app_reproduces_the_cli_frames(built):
    """★ B1, end to end: same season/seats/room/seed -> identical picks and identical summary.

    The app drives ``engine.start_draft`` + ``engine.make_pick``; the reference drives the same
    ``DraftState`` through ``session.advance`` the way ``steps/mock_draft.py`` does. Both are run
    to completion by ADP autopick so the comparison is deterministic end to end rather than only
    over the room's picks.
    """
    from fantasy_quant.draft.simulator import _apply_pick, pick_by_adp

    def run(**kw):
        st_, meta = app_engine.start_draft(built, human_seats=[2, 6], room_arg=behavioral_room(8),
                                           settings=LeagueSettings(), seed=7, room_seed=1,
                                           season=2026, **kw)
        session.advance(st_, meta, None)
        while not st_.is_done() and st_.available:
            t = st_.team_on_clock()
            _apply_pick(st_, t, int(pick_by_adp(st_, t, noise=0.0)))
            session.advance(st_, meta, None)
        return st_, meta

    a, meta_a = run()
    b, meta_b = run()
    assert [p["player_name"] for p in a.log] == [p["player_name"] for p in b.log]

    sm = session.seat_map_from(meta_a)
    pd.testing.assert_frame_equal(session.summary_table(a, sm, None),
                                  session.summary_table(b, session.seat_map_from(meta_b), None))
    # the board frame the two surfaces render is one function, so the columns are one contract
    #
    # ⚠ **Amended by Session K2, and the amendment is disclosed rather than quiet.** K1 asserted
    # the frame's columns *equal* `BOARD_VIEW_COLS`, because there were two views and the advanced
    # one was the frame itself. 14.G adds a third projection, so `board_view` now returns the
    # **union** of what the three modes show and each mode is a named subset — which is the same
    # property one level up, and is what keeps "the modes cannot disagree about who is available"
    # true by construction. The equality that still has to hold is on the *rendered* advanced view.
    frame = session.board_view(a, 2)
    assert set(lbl for _, lbl in session.BOARD_VIEW_COLS) <= set(frame.columns)
    assert list(session.project_view(frame, advanced=True).columns) == \
        [lbl for _, lbl in session.BOARD_VIEW_COLS]


def test_the_app_writes_a_state_the_cli_can_read(built, tmp_path):
    """Export/resume: the app's pickle is the CLI's pickle, so a draft moves between them."""
    st_, meta = app_engine.start_draft(built, human_seats=[4], settings=LeagueSettings(),
                                       season=2026, seed=3)
    p = app_engine.export_state(st_, meta, None, None, path=tmp_path / "draft_state.pkl")
    back = app_engine.import_state(p)
    assert back["meta"]["human_teams"] == [4]
    assert back["state"].n_teams == st_.n_teams
    # the CLI rebuilds the room from `meta` alone — if a key were missing this raises
    assert len(session.seat_map_from(back["meta"]).seats) == st_.n_teams


# ------------------------------------------------------------------------------------------------
# B4 — any k of n seats runs end to end
# ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("k", [0, 1, 4, 9, 10])
def test_b4_any_k_of_n_completes_and_fills_every_starting_slot(built, k):
    """16.17's legality bar, re-run through the app's entry points rather than the CLI's."""
    from fantasy_quant.draft.simulator import RosterSlots, _apply_pick, pick_by_adp

    seats = list(range(k))
    st_, meta = app_engine.start_draft(built, human_seats=seats, room_arg=behavioral_room(10 - k),
                                       settings=LeagueSettings(), season=2026, seed=5, room_seed=2)
    session.advance(st_, meta, None)
    while not st_.is_done() and st_.available:
        t = st_.team_on_clock()
        _apply_pick(st_, t, int(pick_by_adp(st_, t, noise=0.0)))
        session.advance(st_, meta, None)

    assert st_.is_done() or not st_.available
    need = RosterSlots().base_demand()
    for t in range(st_.n_teams):
        counts = st_.roster(t)["pos"].value_counts()
        for pos, want in need.items():
            assert int(counts.get(pos, 0)) >= want, f"k={k}: T{t + 1} short at {pos}"


def test_the_room_shrinks_by_one_seat_per_human(built):
    """``realistic`` gives up one ``balanced`` per human seat — never a character seat."""
    for k in (1, 2, 3):
        st_, meta = app_engine.start_draft(built, human_seats=list(range(k)),
                                           settings=LeagueSettings(), season=2026)
        assert len(meta["room"]) == 10 - k
        assert len(session.seat_map_from(meta).human_teams) == k


def test_t55_the_app_hands_the_season_to_the_seat_map(built):
    """★ **T55 — 16.18's PIT gate was inert on the one path a human uses.**

    ``make_room`` degrades a ``requires_profile`` seat to ``balanced`` on a season the profile does
    not describe (T54), and it can only do that if it is *told* the season. ``start_draft`` did not
    tell it, so the 2026 belief board sat in every historical mock the app can start — and the
    season selector offers fifteen, two of them lockbox seasons. The leak was graded, so it read as
    a seat with a mild opinion rather than as a defect: exactly the reason it needs a test and not
    a comment.

    ⚠ The first assertion is the one that keeps this honest. Without it the test passes when the
    profile fails to load at all — *an inert thing still passes*, and the fallback for an unloaded
    profile is the very ``balanced`` the second assertion looks for.
    """
    from fantasy_quant.draft.personalities import personalities

    assert personalities()["fitted_manager"].manager_profile is not None, (
        "no profile loaded, so this test cannot tell the gate from an empty seat")

    _, covered = app_engine.start_draft(built, human_seats=[5], settings=LeagueSettings(),
                                        season=2026, seed=7, room_seed=1)
    _, uncovered = app_engine.start_draft(built, human_seats=[5], settings=LeagueSettings(),
                                          season=2020, seed=7, room_seed=1)
    assert "fitted_manager" in covered["room"]
    assert "fitted_manager" not in uncovered["room"]
    # and it degrades in place: an uncovered season is the pre-16.18 room, seat for seat
    assert [("balanced" if n == "fitted_manager" else n) for n in covered["room"]] \
        == uncovered["room"]
    # the gate must survive the meta round-trip, since that is what a resumed draft rebuilds from
    assert "fitted_manager" not in [p.name for p in session.seat_map_from(uncovered).room()]


def test_autopicked_seats_must_be_your_own(built):
    with pytest.raises(ValueError, match="seats you drive"):
        app_engine.start_draft(built, human_seats=[2], auto=[5], settings=LeagueSettings(),
                               season=2026)


# ------------------------------------------------------------------------------------------------
# B3 / B6 — the settings contract
# ------------------------------------------------------------------------------------------------
def test_b3_the_lockbox_case_rebuilds_the_engine_defaults_exactly():
    """The 17.3 round-trip: the default league IS the engine's default objects, not a lookalike.

    Reuses ``steps/phase17_formats.py``'s own assertion, because a second, subtly different
    equality check here would be a private opinion about what "the same league" means.
    """
    from fantasy_quant.backtest.scoring import DEFAULT_RULESET
    from fantasy_quant.draft.simulator import RosterSlots
    from fantasy_quant.simulation.season import LeagueFormat

    s = LeagueSettings()
    assert s.roster_slots() == RosterSlots()
    assert s.league_format() == LeagueFormat()
    assert s.ruleset() == DEFAULT_RULESET
    assert s.lockbox_validated() is True


def test_b3_a_superflex_league_is_supported_and_says_it_is_not_validated():
    # 16 roster spots need 16 rounds — the engine refuses `rounds=15` here, correctly, and that
    # refusal is itself part of what "supported" means: the format is checked, not just accepted.
    s = LeagueSettings(superflex=1, rounds=16)
    assert s.lockbox_validated() is False, "a superflex league must not claim the lockbox result"
    assert s.roster_slots().superflex == 1
    assert settings_form.validation_message(s) is None, "superflex is supported, not rejected"


def test_b6_the_default_preset_returns_the_ruleset_object_itself():
    """★ B6's real content: a cosmetic scoring change must not split the distribution cache.

    ``RuleSet`` is serialized into ``cached_distribution``'s cache key. If ``full_ppr`` returned an
    *equal-but-differently-named* ruleset, selecting the preset a user is already on would silently
    force a nine-season rebuild — roughly six minutes per season, for nothing. Hence the form's
    confirmation checkbox, and hence this assertion that the no-op case really is a no-op.
    """
    from fantasy_quant.backtest.scoring import RuleSet, ruleset_from_preset

    assert ruleset_from_preset("full_ppr") == RuleSet()
    assert ruleset_from_preset("full_ppr").name == RuleSet().name
    assert LeagueSettings().ruleset() == RuleSet()
    # a real change is a real change — this one SHOULD invalidate
    assert LeagueSettings(scoring_preset="half_ppr").ruleset() != RuleSet()


def test_an_unplayable_league_is_refused_with_a_reason():
    """Phase 17 is strict on purpose: a league that configures cleanly and then produces a silently
    wrong board is the failure the whole track exists to avoid."""
    msg = settings_form.validation_message(LeagueSettings(n_teams=11))
    assert msg and "team" in msg.lower()


# ------------------------------------------------------------------------------------------------
# the display rules that are load-bearing, not cosmetic
# ------------------------------------------------------------------------------------------------
def test_t22_an_unseen_player_keeps_a_null_boom_rate_all_the_way_to_the_view(built):
    """A player we have never seen play must stay NaN — ``0.00`` reads as *never busts* (T22)."""
    st_, _ = app_engine.start_draft(built, human_seats=[0], settings=LeagueSettings(), season=2026)
    view = session.board_view(st_, 0, n=60)
    assert view["BOOM"].isna().any(), "the null boom rate was filled in somewhere on the way out"
    assert view["BUST"].isna().any()


def test_the_why_chain_is_read_from_the_contracts_not_recomputed():
    """★ B5's content: every line is an identity on stored quantities.

    ``lambda*Var`` must equal ``mean - ce_value`` and the replacement must equal
    ``ce_value - ce_vbd`` **exactly**, because that is what makes the panel an audit trail. A
    display layer that applied λ to a variance itself could disagree with the frozen stack, and
    nobody reading it would be able to tell which number was wrong.
    """
    board = pd.DataFrame({"player_name": ["Test Player"], "pos": ["RB"], "adp": [3.0],
                          "player_key": ["00-0000001"], "games_played_mean": [15.2]})
    vi = pd.DataFrame({"player_key": ["00-0000001"], "proj_points": [280.0], "mean": [240.0],
                       "sd": [55.0], "ce_value": [210.0], "ce_vbd": [90.0], "vbd": [100.0]})
    (entry,) = session.explain_chain(board, vi, "Test", lam=0.01)
    assert entry["ok"]
    by = {r["label"]: r["value"] for r in entry["rows"]}
    lam_var = next(v for k, v in by.items() if k.startswith("- lambda*Var"))
    repl = next(v for k, v in by.items() if k.startswith("- replacement CE"))
    assert lam_var == pytest.approx(-(240.0 - 210.0))
    assert repl == pytest.approx(-(210.0 - 90.0))
    # the chain closes: PROJ -> ... -> BASE_VALUE lands on the stored ce_vbd
    assert by["= BASE_VALUE — what seats optimize"] == pytest.approx(90.0)


def test_a_player_with_no_distribution_is_reported_not_hidden():
    board = pd.DataFrame({"player_name": ["Ghost"], "pos": ["WR"], "adp": [190.0],
                          "player_key": ["00-9999999"], "games_played_mean": [np.nan]})
    (entry,) = session.explain_chain(board, pd.DataFrame(
        {"player_key": [], "proj_points": [], "mean": [], "sd": [], "ce_value": [],
         "ce_vbd": [], "vbd": []}), "Ghost", lam=0.01)
    assert entry["ok"] is False and "ADP fallback" in entry["reason"]


# ------------------------------------------------------------------------------------------------
# K1.5 — B0: a mock draft must be a NEW draft (T34)
# ------------------------------------------------------------------------------------------------
def test_b0_two_app_drafts_from_the_same_seat_are_different_drafts(built):
    """★ T34: the app's default draws both seeds, so re-drafting your slot is a new room.

    Twenty draws, and the assertion is on the *first five picks* because that is the sequence the
    user recognised — "from seat 6 the room always opens Gibbs · Chase · Taylor · McCaffrey ·
    Cook". A weaker assertion (the drafts differ *somewhere*) would have passed on the broken
    build too, since the seating alone moves late picks around.
    """
    opens = set()
    for _ in range(20):
        st_, meta = app_engine.start_draft(built, human_seats=[5], room_arg=behavioral_room(9),
                                           settings=LeagueSettings(), season=2026)
        session.advance(st_, meta, None)
        opens.add(tuple(p["player_name"] for p in st_.log[:5]))
    assert len(opens) > 1, "every app draft opened identically — T34 is back"


def test_b0_a_locked_pair_of_seeds_replays_the_same_draft(built):
    """Randomize is only honest if it is replayable: the drawn seeds go into ``meta``."""
    a, meta_a = app_engine.start_draft(built, human_seats=[5], room_arg=behavioral_room(9),
                                       settings=LeagueSettings(), season=2026)
    session.advance(a, meta_a, None)
    assert isinstance(meta_a["seed"], int) and isinstance(meta_a["room_seed"], int)

    b, meta_b = app_engine.start_draft(built, human_seats=[5], room_arg=behavioral_room(9),
                                       settings=LeagueSettings(), season=2026,
                                       seed=meta_a["seed"], room_seed=meta_a["room_seed"])
    session.advance(b, meta_b, None)
    assert [p["player_name"] for p in a.log] == [p["player_name"] for p in b.log]
    assert meta_a["room"] == meta_b["room"], "the seating draw did not replay"


def test_b0_the_cli_measurement_defaults_do_not_move():
    """⚠ The other half of T34: ``steps/`` keeps ``--seed 7``.

    T24's sweep, 16.17's 1,014-triple mapping check and every committed bar sheet are differenced
    against it, so the entropy default is the *app's* and stops at the seam. This asserts the CLI's
    parser, not a comment about it — *a measurement default and a human default are different
    objects.*
    """
    import argparse
    import contextlib
    import io

    import steps.mock_draft as cli

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), pytest.raises(SystemExit):
        cli.main()                       # no subcommand -> argparse exits after printing usage

    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    del ap, sub                          # the real parser is built inside cli.main; parse instead

    parsed = _cli_start_defaults(cli)
    assert parsed["seed"] == 7, "the CLI's measurement seed moved"
    assert parsed["room_seed"] is None, "the CLI's seating default moved"


def _cli_start_defaults(cli) -> dict:
    """The ``start`` subcommand's defaults, read off a parse with no flags."""
    import sys
    from unittest.mock import patch

    captured = {}
    with patch.object(cli, "cmd_start", lambda a: captured.update(vars(a))), \
            patch.object(sys, "argv", ["mock_draft.py", "start"]):
        cli.main()
    return captured


# ------------------------------------------------------------------------------------------------
# K1.5 — B2: the slim board and the advanced board are one query
# ------------------------------------------------------------------------------------------------
def test_b2_slim_and_advanced_are_two_projections_of_one_frame(built):
    st_, _ = app_engine.start_draft(built, human_seats=[0], settings=LeagueSettings(), season=2026)
    for pos in (None, "RB", "WR,TE"):
        view = session.board_view(st_, 0, pos=pos, n=30)
        slim = session.project_view(view, advanced=False)
        adv = session.project_view(view, advanced=True)
        assert list(slim.index) == list(adv.index), f"rows diverged at pos={pos}"
        assert list(slim.columns) == list(session.SLIM_VIEW_COLS)
        assert list(adv.columns) == [lbl for _, lbl in session.BOARD_VIEW_COLS]
        # the slim view keeps the `#` pick handle: it is the CLI's typed handle and the index
        # `_apply_pick` wants, and dropping it is called out as a "do not" in the build plan
        assert slim.index.name == view.index.name


def test_b2_a_row_selection_and_a_typed_query_resolve_to_the_same_board_index(built):
    """Both routes into a pick land on the same board index.

    The name query is asserted as *membership* rather than equality because a substring can be
    genuinely ambiguous — the fixture's "Player 5" also matches "Player 50" — and that ambiguity
    is exactly why the UI renders the match list under the box instead of drafting the top hit.
    The `#` handle, which the slim board must never drop, has to resolve exactly.
    """
    st_, _ = app_engine.start_draft(built, human_seats=[0], settings=LeagueSettings(), season=2026)
    view = session.board_view(st_, 0, n=20)
    for row in (0, 5, 19):
        idx = int(view.index[row])                       # what a row-select yields
        assert session.resolve_pick(st_, 0, str(idx)) == idx, "the # handle did not resolve"
        typed = session.resolve_pick(st_, 0, str(view.iloc[row]["PLAYER"]))
        found = {typed} if isinstance(typed, int) else {m["index"] for m in typed}
        assert idx in found, "row-select and typed search disagree about who that is"


# ------------------------------------------------------------------------------------------------
# K1.5 — B3: the clock changes when picks happen, never which
# ------------------------------------------------------------------------------------------------
def test_b3_a_clocked_draft_and_an_unclocked_draft_are_the_same_draft(built):
    """``advance`` is the loop over ``advance_one``, so this holds by construction — and the test
    asserts the construction rather than hoping two loops agree (T18/F.5/T27, one level down)."""
    def run(one_at_a_time: bool):
        st_, meta = app_engine.start_draft(built, human_seats=[3], room_arg=behavioral_room(9),
                                           settings=LeagueSettings(), season=2026, seed=11,
                                           room_seed=4)
        from fantasy_quant.draft.simulator import _apply_pick, pick_by_adp
        while not st_.is_done() and st_.available:
            if one_at_a_time:                            # the clock: one modelled pick per tick
                while session.advance_one(st_, meta, None) is not None:
                    pass
            else:
                session.advance(st_, meta, None)
            if st_.is_done() or not st_.available:
                break
            t = st_.team_on_clock()
            _apply_pick(st_, t, int(pick_by_adp(st_, t, noise=0.0)))
        return [p["player_name"] for p in st_.log]

    assert run(True) == run(False)


def test_b3_advance_one_stops_on_your_seat(built):
    st_, meta = app_engine.start_draft(built, human_seats=[0], room_arg=behavioral_room(9),
                                       settings=LeagueSettings(), season=2026, seed=2, room_seed=2)
    session.advance(st_, meta, None)
    assert st_.team_on_clock() in st_.human_teams
    assert session.advance_one(st_, meta, None) is None, "the room drafted for you"


# ------------------------------------------------------------------------------------------------
# K1.5 — B4: both grids agree with the state and with the frozen solver
# ------------------------------------------------------------------------------------------------
def _finished(built, k: int = 1):
    from fantasy_quant.draft.simulator import _apply_pick, pick_by_adp

    st_, meta = app_engine.start_draft(built, human_seats=list(range(k)),
                                       room_arg=behavioral_room(10 - k),
                                       settings=LeagueSettings(), season=2026, seed=5, room_seed=2)
    session.advance(st_, meta, None)
    while not st_.is_done() and st_.available:
        t = st_.team_on_clock()
        _apply_pick(st_, t, int(pick_by_adp(st_, t, noise=0.0)))
        session.advance(st_, meta, None)
    return st_, meta


def test_b4_the_by_pick_grid_re_reads_the_log_exactly(built):
    st_, meta = _finished(built)
    sm = session.seat_map_from(meta)
    grid = session.room_grid(st_, sm, by="pick")
    assert grid.shape == (st_.rounds, st_.n_teams)
    for p in st_.log:
        cell = grid.iat[int(p["round"]) - 1, int(p["team"])]
        assert p["player_name"] in cell, f"{p['player_name']} missing from R{p['round']}"
        assert cell.startswith(f"{int(p['round'])}.{int(p['pick_in_round']):02d}")
    filled = int((grid != "").to_numpy().sum())
    assert filled == len(st_.log), "a pick appears twice, or not at all"


def test_b4_the_by_slot_grid_starters_agree_with_the_frozen_lineup_solver(built):
    """★ The grid is checked against ``starter_value`` — the T28 headline it illustrates.

    Two solvers reach the same fill order through ``RosterSlots.flex_groups()``: the labelled one
    (``inseason.lineup``) that the grid reads and the vectorized one
    (``simulation.season.lineup_points_matrix``) that ``starter_value`` scores. Asserting their
    *sum* is equal is what stops the display from quietly inventing a fourth fill order.
    """
    from fantasy_quant.draft.optimizer import starter_value

    st_, meta = _finished(built)
    sm = session.seat_map_from(meta)
    vi = st_.board[["player_key", "base_value"]].dropna().drop_duplicates("player_key")
    grid = session.room_grid(st_, sm, by="slot", vi=vi)

    slot_labels = [r for r in grid.index if not r.startswith("BN")]
    for t in range(st_.n_teams):
        roster = st_.roster(t)
        col = grid.columns[t]
        started = [c for r, c in grid[col].items() if r in slot_labels and c]
        bv = dict(zip(roster["player_name"], roster["base_value"].fillna(0.0), strict=False))
        total = sum(bv.get(c.rsplit(" (", 1)[0], 0.0) for c in started)
        assert total == pytest.approx(float(starter_value(roster, vi, st_.slots)), abs=1e-6), \
            f"T{t + 1}: the grid's starters are not the startable lineup"
        # every player appears at most once across the whole column
        names = [c for c in grid[col] if c]
        assert len(names) == len(set(names))


# ------------------------------------------------------------------------------------------------
# K1.5 — B5: every column is documented, and the rail agrees with the state
# ------------------------------------------------------------------------------------------------
def test_b5_every_board_column_has_a_stat_dictionary_entry():
    """14.O's done-bar: a new column without documentation fails a test."""
    session.assert_stat_dict_covers_board()
    for _, label in session.BOARD_VIEW_COLS:
        e = session.stat_entry(label)
        for field in ("label", "one_line", "what_it_means", "worked_example", "how_to_read_it",
                      "provenance"):
            assert e[field].strip(), f"{label}.{field} is empty"
    # the two entries that must carry their limitation in the tooltip rather than in a doc
    assert "never seen play" in session.STAT_DICT["BOOM"]["how_to_read_it"]
    assert "never seen play" in session.STAT_DICT["BUST"]["how_to_read_it"]
    assert "T31" in session.STAT_DICT["MEAN"]["how_to_read_it"]
    with pytest.raises(LookupError):
        session.stat_entry("NOT_A_COLUMN")


def test_b5_the_rail_slot_state_agrees_with_starter_needs(built):
    """The rail's open slots are the slots ``starter_needs`` says are open."""
    from fantasy_quant.draft.simulator import _apply_pick, pick_by_adp

    st_, meta = app_engine.start_draft(built, human_seats=[2], room_arg=behavioral_room(9),
                                       settings=LeagueSettings(), season=2026, seed=9, room_seed=1)
    session.advance(st_, meta, None)
    for _ in range(4):                                    # a partly-built roster is the real case
        t = st_.team_on_clock()
        _apply_pick(st_, t, int(pick_by_adp(st_, t, noise=0.0)))
        session.advance(st_, meta, None)

    sm = session.seat_map_from(meta)
    grid = session.room_grid(st_, sm, by="slot")
    col = grid.columns[2]
    needs = st_.starter_needs(2)
    for pos, owed in needs.items():
        if pos == "FLEX":
            continue
        rows = [r for r in grid.index if r.rstrip("0123456789") == pos]
        open_rows = sum(1 for r in rows if not grid.at[r, col])
        assert open_rows == owed, f"rail shows {open_rows} open {pos}, state says {owed}"


def test_the_entry_point_imports_when_run_the_way_a_human_runs_it():
    """★ The regression test for the bug that shipped: `streamlit run app/main.py` must work.

    Streamlit executes the target file with **its own directory** on ``sys.path``, not the repo
    root — so ``app/main.py``'s ``from app import engine, views`` raised ``ModuleNotFoundError``
    for the first person who opened it, while every check in this session said PASS:

    * these unit tests import ``app.engine`` under pytest's ``pythonpath = ["src", "."]``;
    * ``AppTest`` runs in a process where the done-bar had already inserted the repo root;
    * the headless-server bar fetched ``/`` — but Streamlit does not execute the script until a
      browser opens a **websocket session**, so an HTTP GET returns the same HTML shell either way.

    Every layer shared one assumption — that the repo root is importable — and it was false in
    exactly the configuration a human uses. So this runs the entry point as a bare script, from a
    different directory, with ``PYTHONPATH`` scrubbed: the harshest honest version of the question.
    """
    import os
    import subprocess
    import sys
    import tempfile

    root = Path(__file__).resolve().parents[1]
    r = subprocess.run([sys.executable, str(root / "app" / "main.py")],
                       cwd=tempfile.gettempdir(),
                       env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
                       capture_output=True, text=True, timeout=900)
    out = (r.stdout or "") + (r.stderr or "")
    assert "ModuleNotFoundError" not in out, out[-1500:]
    assert r.returncode == 0, out[-1500:]


# ================================================================================================
# Session K2 — surfacing (14.E · 14.F · 14.G · 14.I) + 16.12 + the post-draft page (14.N)
# ================================================================================================
@pytest.fixture
def k2_board(board) -> pd.DataFrame:
    """The shared board plus the columns K2 renders — quantiles, rookie flags and real NFL teams.

    A **separate** fixture rather than more columns on the shared one: the K1/K1.5 tests are
    differenced against that board's exact content, and widening it to serve a later session is how
    a fixture stops describing what any particular test meant.
    """
    rng = np.random.default_rng(7)
    n = len(board)
    mean = board["mean"].to_numpy(float)
    teams = ["KC", "SF", "DET", "PHI", "BUF", "MIA", "DAL", "CIN"]
    return board.assign(
        q50=mean * 0.98,
        q90=mean * 1.45,
        # ★ a third of the board is left-censored, which is what the live board looks like: a
        # season total cannot be negative and `enrichment.CENSOR_AT` piles those rows on 0.0.
        q10=np.where(np.arange(n) % 3 == 0, 0.0, mean * 0.45),
        rookie=np.where(np.arange(n) % 11 == 0, 1.0, 0.0),
        team=[teams[i % len(teams)] for i in range(n)],
        stdev=rng.uniform(1, 12, n),
    )


@pytest.fixture
def k2_built(k2_board) -> dict:
    """A build carrying a minimal value index, so ``STARTABLE`` and the slot solver have input."""
    vi = pd.DataFrame({
        "player_key": k2_board["gsis_id"].astype(str),
        "pos": k2_board["position"],
        "proj_points": k2_board["proj_points"],
        "vbd": k2_board["vbd"],
        "mean": k2_board["mean"],
        "sd": k2_board["mean"] * 0.3,
        "ce_value": k2_board["mean"] * 0.9,
        "ce_vbd": k2_board["base_value"],
        "base_value": k2_board["base_value"],
        "team": k2_board["team"],
        "role_rank": 1,
    })
    return {"board": k2_board, "value_index": vi, "risk": None, "source": "ffc",
            "n_base_value": int(k2_board["base_value"].notna().sum()), "lam": 0.01}


def _k2_draft(built, k: int = 1, *, finish: bool = True):
    from fantasy_quant.draft.simulator import _apply_pick, pick_by_adp

    state, meta = app_engine.start_draft(
        built, human_seats=list(range(k)), settings=LeagueSettings(),
        season=2026, seed=3, room_seed=4, room_arg=behavioral_room(10 - k))
    if finish:
        while not state.is_done() and state.available:
            t = state.team_on_clock()
            _apply_pick(state, t, int(pick_by_adp(state, t, noise=0.0)))
    return state, meta


# ------------------------------------------------------------------------------------------------
# 14.E — the cliff is read from the decision path, and it is about the pool not the screen
# ------------------------------------------------------------------------------------------------
def test_k2_the_cliff_column_is_positional_cliff_over_the_whole_pool(k2_built):
    """★ The display must not re-derive what the greedy already computes (T27, one level down)."""
    from fantasy_quant.draft.optimizer import positional_cliff

    state, _ = _k2_draft(k2_built, finish=False)
    pool = state.draftable_pool(0)
    bv = dict(zip(pool["player_key"].astype(str),
                  pd.to_numeric(pool["base_value"], errors="coerce"), strict=False))
    want = positional_cliff(pool["player_key"], pool["pos"], bv)
    got = session.board_view(state, 0)["CLIFF"].to_numpy(float)
    assert np.allclose(want, got, equal_nan=True)


def test_k2_the_cliff_does_not_move_when_the_board_is_truncated(k2_built):
    """A cliff is a fact about what is left at a position, never about how many rows are shown."""
    state, _ = _k2_draft(k2_built, finish=False)
    full = session.board_view(state, 0)["CLIFF"]
    small = session.board_view(state, 0, n=6)["CLIFF"]
    assert np.allclose(small.to_numpy(float), full.reindex(small.index).to_numpy(float),
                       equal_nan=True)
    only_rb = session.board_view(state, 0, pos="RB")["CLIFF"]
    assert np.allclose(only_rb.to_numpy(float), full.reindex(only_rb.index).to_numpy(float),
                       equal_nan=True)


def test_k2_the_cliff_strip_counts_the_players_above_the_drop(k2_built):
    state, _ = _k2_draft(k2_built, finish=False)
    tab = session.cliff_table(state, 0)
    pool = state.draftable_pool(0)
    cliffs = session.cliff_series(state, 0)
    assert not tab.empty
    for r in tab.itertuples(index=False):
        grp = pool[pool["pos"] == r.pos]
        assert list(grp.index).index(r.at_index) + 1 == r.n_before
        assert float(cliffs.loc[r.at_index]) == pytest.approx(r.drop)


# ------------------------------------------------------------------------------------------------
# 14.G — three projections of one frame; a censored floor is flagged, never printed as zero
# ------------------------------------------------------------------------------------------------
def test_k2_slim_ranges_and_advanced_are_three_projections_of_one_frame(k2_built):
    state, _ = _k2_draft(k2_built, finish=False)
    view = session.board_view(state, 0, n=40)
    frames = {m: session.project_view(view, mode=m) for m in session.VIEW_MODES}
    for f in frames.values():
        assert list(f.index) == list(view.index)
    assert list(frames["slim"].columns) == list(session.SLIM_VIEW_COLS)
    assert list(frames["ranges"].columns) == list(session.RANGE_VIEW_COLS)
    assert list(frames["advanced"].columns) == [lbl for _, lbl in session.BOARD_VIEW_COLS]
    # K1.5's two-state control is unchanged — its committed sheet differences against it
    assert list(session.project_view(view).columns) == list(session.SLIM_VIEW_COLS)
    assert list(session.project_view(view, advanced=True).columns) == \
        [lbl for _, lbl in session.BOARD_VIEW_COLS]
    with pytest.raises(ValueError):
        session.project_view(view, mode="nonsense")


def test_k2_a_censored_floor_is_flagged_rather_than_printed_as_a_floor_of_zero(k2_built):
    """★ T22's rule with the other sign: ``q10 = 0`` does not mean *his downside is zero*."""
    from fantasy_quant.draft.enrichment import CENSOR_AT

    state, _ = _k2_draft(k2_built, finish=False)
    view = session.project_view(session.board_view(state, 0, n=60), mode="ranges")
    at_floor = view["Q10"].le(CENSOR_AT) & view["Q10"].notna()
    assert at_floor.any(), "the fixture is meant to contain censored rows"
    assert view.loc[at_floor, "FLAGS"].str.contains("censored floor").all()
    assert not view.loc[~at_floor, "FLAGS"].str.contains("censored floor").any()


def test_k2_a_player_with_no_distribution_is_flagged_and_not_called_censored():
    """Two different disclosures: *we have no cloud* vs *the cloud is left-censored*."""
    pool = pd.DataFrame({"mean": [np.nan, 200.0, 150.0], "q10": [np.nan, 0.0, 60.0],
                         "rookie": [0.0, 0.0, 1.0]})
    flags = session.range_flags(pool).tolist()
    assert flags[0] == "no distribution"
    assert flags[1] == "censored floor"
    assert flags[2] == "rookie"


def test_k2_coin_flags_mark_adjacent_overlapping_bands_only():
    """Parameter-free by design: the only resolution claim the frozen contract supports."""
    q10 = [100.0, 90.0, 10.0, np.nan]
    q90 = [200.0, 150.0, 20.0, 30.0]
    assert session.coin_flags(q10, q90).tolist() == [True, False, False, False]
    assert session.coin_flags([1.0], [2.0]).tolist() == [False]
    assert session.coin_flags([], []).tolist() == []


# ------------------------------------------------------------------------------------------------
# 14.F — bye clustering, concentration, handcuff gaps
# ------------------------------------------------------------------------------------------------
def test_k2_an_unknown_bye_stays_unknown_and_is_never_week_zero(k2_built):
    """★ The store has no schedule table, so ~1 board row in 10 has no bye. A ``fillna(0)`` would
    file those players under "week 0", which a human reads as *no bye at all*."""
    state, _ = _k2_draft(k2_built)
    roster = state.roster(0)
    partial = pd.Series([7.0] * 2, index=[str(k) for k in roster["player_key"][:2]])
    risk = session.roster_construction_risk(state, 0, vi=k2_built["value_index"], byes=partial)
    slots, _ = session.lineup_choice(state, roster, k2_built["value_index"])
    n_starters = len({i for i in slots.values() if i is not None})
    counted = int(risk["byes"]["n"].sum()) if len(risk["byes"]) else 0
    assert counted + risk["unknown_byes"] == n_starters
    assert risk["unknown_byes"] > 0
    if len(risk["byes"]):
        assert (risk["byes"]["week"] != 0).all()


def test_k2_bye_clustering_is_over_starters_not_the_whole_roster(k2_built):
    """A bench player's bye costs nothing; counting him would make a deep roster look fragile."""
    state, _ = _k2_draft(k2_built)
    roster = state.roster(0)
    everyone = pd.Series([11.0] * len(roster), index=[str(k) for k in roster["player_key"]])
    risk = session.roster_construction_risk(state, 0, vi=k2_built["value_index"], byes=everyone)
    slots, _ = session.lineup_choice(state, roster, k2_built["value_index"])
    n_starters = len({i for i in slots.values() if i is not None})
    assert risk["max_bye_starters"] == n_starters < len(roster)


class _StubState:
    """Just enough ``DraftState`` for :func:`session._handcuff_gaps` — it reads ``st.board``.

    Written as a stub rather than driven through a full draft because the first version of this
    test *was* driven through one, and the synthetic board happened to seat no lead back at all:
    it asserted over an empty frame and passed while proving nothing. A test that cannot fail is
    the same defect as a bar that cannot fail.
    """

    def __init__(self, board):
        self.board = board


def _backfield_board() -> pd.DataFrame:
    """Two backfields in board order: ATL (Lead A, Backup A) and BUF (Lead B, Backup B)."""
    return pd.DataFrame({
        "player_key": ["a1", "a2", "b1", "b2"],
        "player_name": ["Lead A", "Backup A", "Lead B", "Backup B"],
        "pos": ["RB"] * 4,
        "team": ["ATL", "ATL", "BUF", "BUF"],
        "mean": [220.0, 90.0, 210.0, 80.0],
        "games_played_mean": [13.0, 16.0, 14.0, 16.0],
    })


def test_k2_the_handcuff_is_the_backfields_rb2_never_its_rb1():
    """★ The first live run had the depth chart upside down — it reported the RB2's "handcuff" as
    the RB1, i.e. priced insurance on the wrong life. Holding the backup is not a gap; it *is* the
    handcuff."""
    board = _backfield_board()
    roster = board[board["player_key"].isin(["a1", "b2"])].reset_index(drop=True)
    out = session._handcuff_gaps(_StubState(board), roster, 1.8)
    hc = out["handcuffs"]
    assert len(hc) == 1, "only the lead back you hold generates a row"
    assert hc.iloc[0]["starter"] == "Lead A" and hc.iloc[0]["backup"] == "Backup A"
    assert hc.iloc[0]["held"] is False or not bool(hc.iloc[0]["held"])
    assert out["n_handcuff_gaps"] == 1
    assert hc.iloc[0]["option_premium"] > 0


def test_k2_holding_both_halves_of_a_backfield_is_not_a_gap():
    board = _backfield_board()
    roster = board[board["player_key"].isin(["a1", "a2"])].reset_index(drop=True)
    out = session._handcuff_gaps(_StubState(board), roster, 1.8)
    assert len(out["handcuffs"]) == 1
    assert bool(out["handcuffs"].iloc[0]["held"]) is True
    assert out["n_handcuff_gaps"] == 0


def test_k2_the_option_premium_is_absent_rather_than_invented_without_an_elevation_ratio():
    board = _backfield_board()
    roster = board[board["player_key"] == "a1"].reset_index(drop=True)
    out = session._handcuff_gaps(_StubState(board), roster, None)
    assert len(out["handcuffs"]) == 1
    assert out["handcuffs"]["option_premium"].isna().all()


def test_k2_construction_risk_and_the_room_grid_agree_about_who_starts(k2_built):
    """17.1's rule, one altitude down: ``flex_groups`` is the single fill-order rule, and 14.F,
    14.L and the rail all reach it through :func:`session.lineup_choice`."""
    state, meta = _k2_draft(k2_built)
    sm = session.seat_map_from(meta)
    grid = session.room_grid(state, sm, by="slot", vi=k2_built["value_index"])
    col = grid.columns[0]
    from_grid = {c.rsplit(" (", 1)[0] for r, c in grid[col].items()
                 if c and not str(r).startswith("BN")}
    risk = session.roster_construction_risk(state, 0, vi=k2_built["value_index"])
    assert from_grid == set(risk["starters"])


# ------------------------------------------------------------------------------------------------
# 14.I — the grade is exactly the sum of its printed parts
# ------------------------------------------------------------------------------------------------
def _fake_odds(n_teams: int = 10) -> pd.DataFrame:
    fair = np.linspace(2.0, 0.2, n_teams)
    return pd.DataFrame({"team": np.arange(1, n_teams + 1), "title_fair": fair,
                         "playoff_fair": fair, "title": fair / n_teams,
                         "playoff": np.clip(fair / 2, 0, 1)})


def test_k2_the_grade_reproduces_from_the_components_printed_beside_it(k2_built):
    """★ The blend is a presentation choice with nothing validating it, which is allowed only for
    as long as a reader can re-add it by hand."""
    state, meta = _k2_draft(k2_built)
    sm = session.seat_map_from(meta)
    grade = session.draft_grade(state, meta, sm, odds=_fake_odds(),
                                vi=k2_built["value_index"])
    assert sum(session.GRADE_WEIGHTS.values()) == pytest.approx(100.0)
    parts = sum(grade[f"points_{c}"] for c in session.GRADE_WEIGHTS)
    assert np.allclose(parts.to_numpy(float), grade["total"].to_numpy(float))
    assert grade["total"].between(0.0, 100.0).all()
    assert all(ltr == session.grade_letter(t)
               for ltr, t in zip(grade["letter"], grade["total"], strict=False))


def test_k2_the_bands_put_the_middle_of_the_room_at_c_not_at_d(k2_built):
    """★ Caught by the first live run: on plain 90/80/70/60 bands the median team in a ten-team
    room graded **D+**, because the letters assumed 50 % was a fail when on a curve 50 is the
    middle. A scale and its labels have to be anchored to the same thing."""
    assert session.grade_letter(50.0) == "C"
    assert session.grade_letter(100.0) == "A+"
    assert session.grade_letter(0.0) == "F"
    assert session.grade_letter(float("nan")) == "—"


def test_k2_a_component_the_room_does_not_separate_on_cannot_decide_a_grade():
    comps = pd.DataFrame({"team": [1, 2], "who": ["a", "b"], "human": [True, False],
                          "odds": [1.0, 1.0], "starters": [5.0, 9.0],
                          "value": [np.nan, np.nan], "construction": [0.0, 0.0]})
    out = session.apply_grade(comps)
    assert (out["score_odds"] == 0.5).all()
    assert (out["score_value"] == 0.5).all()
    assert (out["score_construction"] == 0.5).all()
    assert sorted(out["score_starters"]) == [0.0, 1.0]


def test_k2_there_is_no_combined_grade_across_your_own_seats(k2_built):
    """16.17: k human teams in one draft are ONE observation — their picks depleted each other's
    pools, so averaging their grades would report the depletion as skill."""
    state, meta = _k2_draft(k2_built, k=4)
    sm = session.seat_map_from(meta)
    grade = session.draft_grade(state, meta, sm, odds=_fake_odds(), vi=k2_built["value_index"])
    assert len(grade) == 10
    assert int(grade["human"].sum()) == 4
    assert not any(str(c).startswith(("mean_", "avg_", "combined")) for c in grade.columns)


# ------------------------------------------------------------------------------------------------
# 16.12 + the player card + 14.N's wiring
# ------------------------------------------------------------------------------------------------
def test_k2_the_reach_risk_labels_are_the_engines_own(k2_built):
    from fantasy_quant.draft import drift

    state, meta = _k2_draft(k2_built, finish=False)
    frame = session.reach_risk_view(state, meta, 0, n=12, n_sims=40)
    assert {"p_available", "p_available_baseline"} <= set(frame.columns)
    assert frame["p_available"].between(0.0, 1.0).all()
    assert all(drift.reach_risk_label(p) == lbl
               for p, lbl in zip(frame["p_available"], frame["reach_risk"], strict=False))


def test_k2_the_player_card_reads_the_board_rather_than_recomputing_it(k2_built):
    state, _ = _k2_draft(k2_built, finish=False)
    idx = int(session.board_view(state, 0, n=1).index[0])
    card = session.player_card(state, idx, vi=k2_built["value_index"], lam=0.01)
    row = state.board.loc[idx]
    assert card["name"] == row["player_name"] and card["pos"] == row["pos"]
    assert len(card["bars"]) == 8
    by_label = {b["label"]: b["value"] for b in card["bars"]}
    assert by_label["PROJ"] == pytest.approx(float(row["proj_points"]))
    assert by_label["Q90"] == pytest.approx(float(row["q90"]))
    assert all(b["help"] for b in card["bars"])
    assert card["cliff"] == pytest.approx(float(session.cliff_series(state).loc[idx]))


def test_k2_pick_drift_keeps_the_panels_sign(k2_built):
    """Positive = the seat reached. T18 is the standing reminder that a redefined reach column is
    a silent defect, so this reads the panel rather than subtracting two raw numbers."""
    state, meta = _k2_draft(k2_built)
    sm = session.seat_map_from(meta)
    frames = session.drift_frames(state, meta, sm)
    everyone = session.pick_drift_table(frames)
    mine = session.pick_drift_table(frames, 0)
    assert len(everyone) >= len(mine) > 0
    assert mine["reach_picks"].is_monotonic_decreasing
    assert set(mine["player"]) <= set(state.roster(0)["player_name"])


def test_k2_the_post_draft_page_is_registered_between_the_room_and_the_cost_page():
    """14.N is a *place*, and the last pick navigates to it (14.K's model, K2's destination)."""
    nav = pytest.importorskip("app.nav")
    main = pytest.importorskip("app.main")
    assert "post" in nav.ORDER
    assert nav.ORDER.index("post") == nav.ORDER.index("grid") + 1
    assert set(nav.ORDER) == set(main.PAGE_SPECS)
    assert main.PAGE_SPECS["post"][3] == "post-draft"


def test_k2_the_room_page_gave_the_analysis_readouts_to_14n_rather_than_copying_them():
    """★ Moved, not duplicated. Two render paths for one table is how the K1 board and the CLI
    board drifted apart; the room page keeps the grid and the log."""
    room_grid = pytest.importorskip("app.room_grid")
    assert room_grid.VIEWS == ("Room grid", "Log", "Stat dictionary")
    src = Path(room_grid.__file__).read_text()
    assert "odds_table" not in src and "summary_panel" not in src


def test_k2_the_odds_cache_key_names_the_draft_it_describes():
    """T32's lesson in miniature: a cache key that omits what changed serves a stale answer."""
    post = pytest.importorskip("app.post_draft")

    class _S:
        def __init__(self, n):
            self.log = list(range(n))

    meta = {"seed": 1, "room_seed": 2}
    assert post._odds_key(_S(150), meta) != post._odds_key(_S(149), meta)
    assert post._odds_key(_S(150), meta) != post._odds_key(_S(150), {"seed": 9, "room_seed": 2})
    assert post._odds_key(_S(150), meta) == post._odds_key(_S(150), dict(meta))


def test_k2_the_stat_dictionary_covers_every_rendered_view():
    """14.O's done-bar, widened by K2: a column documented only in the mode nobody opens is the
    defect the dictionary exists to prevent."""
    session.assert_stat_dict_covers_board()
    rendered = ({lbl for _, lbl in session.BOARD_VIEW_COLS} | set(session.RANGE_VIEW_COLS)
                | set(session.SLIM_VIEW_COLS))
    for col in rendered:
        e = session.stat_entry(col)
        assert e["worked_example"].strip() and e["provenance"].strip()
    examples = [e["worked_example"] for e in session.STAT_DICT.values()]
    assert len(examples) == len(set(examples))


# ------------------------------------------------------------------------------------------------
# Session UI-1 — the palette, the strip, the attached column, and the compression
#
# ★ Offline throughout, like the rest of this file. The *rendering* claims (five surfaces coloured,
#   seven honesty surfaces still on screen, zero expanders in the reach path) are the live driver's
#   job — `steps/session_ui_1.py`. What is unit-tested here is the arithmetic and the parsing those
#   claims sit on, because a bar that boots a server is a slow place to discover that `"BN1"` was
#   read as a position.
# ------------------------------------------------------------------------------------------------
palette = pytest.importorskip("app.palette")
app_views = pytest.importorskip("app.views")


def test_ui1_every_position_chip_clears_wcag_aa():
    """The palette is a colourblind-safe set; a set chosen for one accessibility property should
    not fail a different one.

    ⚠ The first implementation picked the ink by a luminance threshold of 0.42 and lettered QB
    (`#E69F00`, luminance 0.410) in **white at a contrast ratio of 2.3**. The break-even luminance
    is 0.179, not 0.5, and the way to not have to know that is to compute both and take the larger.
    """
    assert set(palette.POSITION_COLORS) == set(palette.POSITIONS)
    for pos, hue in palette.POSITION_COLORS.items():
        ink = palette.ink_for(hue)
        assert palette.contrast_ratio(hue, ink) >= 4.5, f"{pos} chip fails AA"
        assert ink in palette.INK
    assert palette.contrast_ratio("#FFFFFF", "#000000") == pytest.approx(21.0, abs=0.05)


def test_ui1_the_theme_and_the_palette_cannot_drift_apart():
    """``.streamlit/config.toml`` is the one unavoidable second copy of the hexes — a TOML file is
    read before any of our Python runs, so it cannot import a constant. Assert it, do not hope."""
    import tomllib

    cfg = tomllib.loads((Path(__file__).resolve().parents[1] / ".streamlit"
                         / "config.toml").read_text())
    assert cfg["theme"]["base"] == "dark"
    assert ([c.upper() for c in cfg["theme"]["chartCategoricalColors"]]
            == [h.upper() for h in palette.POSITION_COLORS.values()])


def test_ui1_a_flex_slot_is_not_a_position():
    """Colouring FLEX or a bench row as a position would assert something false about the roster."""
    assert palette.pos_in_slot("RB2") == "RB" and palette.pos_in_slot("QB") == "QB"
    assert palette.pos_in_slot("FLEX") is None
    assert palette.pos_in_slot("SUPERFLEX") is None
    assert palette.pos_in_slot("BN4") is None
    assert palette.chip_style("FLEX") == "" and palette.tint_style(None) == ""
    assert palette.pos_in_cell("3.07  Puka Nacua (WR)") == "WR"
    assert palette.pos_in_cell("1.01  Bijan Robinson (RB)") == "RB"
    assert palette.pos_in_cell("") is None
    assert palette.pos_in_cell("Somebody (XYZ)") is None


def test_ui1_the_tint_is_theme_independent_and_the_chip_is_not():
    """Two treatments, one constant: a solid hue where the cell *is* a position (opaque, so its
    contrast does not depend on the background), an rgba tint where the cell merely mentions one
    (composited by the browser over whichever theme is active)."""
    tint = palette.tint_style("WR")
    assert tint.startswith("background-color: rgba(")
    # ⚠ the declaration, not the substring — `background-color:` contains `color:`, which is what
    # the first version of this assertion tripped over.
    assert [d.split(":")[0].strip() for d in tint.split(";")] == ["background-color"]
    chip = palette.chip_style("WR")
    assert palette.POSITION_COLORS["WR"] in chip
    assert "color" in [d.split(":")[0].strip() for d in chip.split(";")]


def test_ui1_attach_reach_places_and_never_fabricates(k2_built):
    """``P(THERE)`` is a placement, not a derivation — and a row nobody simulated stays NaN.

    T22's rule with the other sign: printing 0.00 for an unsimulated player reads as *he will
    certainly be gone*, which is a claim the model never made.
    """
    state, meta = _k2_draft(k2_built, finish=False)
    reach = session.reach_risk_view(state, meta, 0, n=8, n_sims=40)
    view = session.project_view(session.board_view(state, 0, n=20), mode="slim")
    out = session.attach_reach(view, reach)

    assert session.REACH_COL in out.columns
    assert list(out.index) == list(view.index)
    want = dict(zip(reach["board_index"].astype(int), reach["p_available"], strict=False))
    for idx, val in out[session.REACH_COL].items():
        if int(idx) in want:
            assert val == pytest.approx(float(want[int(idx)]))
        else:
            assert pd.isna(val)
    # an absent or empty readout gives the column, all-NaN — never a silent 0.0 and never a
    # missing column the renderer then has to special-case
    for empty in (None, reach.iloc[0:0]):
        blank = session.attach_reach(view, empty)
        assert session.REACH_COL in blank.columns
        assert blank[session.REACH_COL].isna().all()


def test_ui1_the_snake_has_one_arithmetic(k2_built):
    """``team_for_pick`` is a second copy of ``team_on_clock``'s geometry, and the only thing that
    makes that acceptable here is that it is differenced **exhaustively** (16.17's precedent)."""
    from fantasy_quant.draft.simulator import _apply_pick, pick_by_adp

    state, _ = _k2_draft(k2_built, finish=False)
    last = state.n_teams * state.rounds
    checked = 0
    while not state.is_done() and state.available:
        t = state.team_on_clock()
        assert session.team_for_pick(state, state.overall_pick) == t
        checked += 1
        _apply_pick(state, t, int(pick_by_adp(state, t, noise=0.0)))
    assert checked == last
    assert session.team_for_pick(state, 0) is None
    assert session.team_for_pick(state, last + 1) is None


def test_ui1_next_pick_info_is_the_optimizers_own_window(k2_built):
    """The strip's "12 away" and the availability readout's simulation window are one number."""
    from fantasy_quant.draft import optimizer

    state, meta = _k2_draft(k2_built, finish=False)
    seat = state.team_on_clock()
    info = session.next_pick_info(state, seat)
    last = state.n_teams * state.rounds
    assert info["on_the_clock"] is True
    assert info["next_pick"] == optimizer._next_own_pick(state.overall_pick, seat,
                                                        state.n_teams, last)
    assert (session.reach_risk_view(state, meta, seat, n=4, n_sims=20).attrs["window_picks"]
            == info["picks_away"])
    # a seat that is not on the clock counts one more opponent than a seat that is
    other = (seat + 1) % state.n_teams
    assert (session.next_pick_info(state, other)["on_the_clock"]) is False


def test_ui1_the_seat_strip_is_the_seat_maps_order(k2_built):
    """B4's content half, offline: order, the clock, on deck, and which chips are yours."""
    state, meta = _k2_draft(k2_built, k=4, finish=False)
    sm = session.seat_map_from(meta)
    rows = app_views.seat_strip_rows(state, meta, sm)

    assert [r["team"] for r in rows] == list(range(1, state.n_teams + 1))
    assert all(r["label"] == session.seat_label(r["seat"], sm) for r in rows)
    assert [r["seat"] for r in rows if r["on_clock"]] == [state.team_on_clock()]
    assert {r["seat"] for r in rows if r["you"]} == set(sm.human_teams)
    deck = session.team_for_pick(state, state.overall_pick + 1)
    assert [r["seat"] for r in rows if r["on_deck"]] == ([deck] if deck != state.team_on_clock()
                                                         else [])
    # a finished draft has nobody on the clock, and the strip must not invent one
    done, dmeta = _finished(k2_built, k=1)
    assert not any(r["on_clock"] for r in app_views.seat_strip_rows(
        done, dmeta, session.seat_map_from(dmeta)))


def test_ui1_the_elite_fall_table_replaces_the_json_dump():
    """T38 — the same numbers, with the label and the unit that make them readable."""
    table = app_views.elite_fall_table({"n": 12, "mean_slot": 6.5, "p95_slot": 14.0,
                                        "max_slot": 17.0, "share_past_10": 0.25})
    text = " ".join(table.iloc[:, 0].astype(str))
    assert "Consensus top-12" in text and "10-team picks" in text
    assert "25.0%" in " ".join(table.iloc[:, 1].astype(str))
    # the threshold is read off the key, never hard-coded — the profile names it after its own cut
    other = app_views.elite_fall_table({"n": 3, "share_past_8": 0.5})
    assert len(other) == 2
    assert len(app_views.elite_fall_table({"n": 0})) == 1


def test_ui1_the_attached_column_is_documented_and_reaches_the_terminal():
    """K2's rule: a column the app shows and the CLI cannot is a documented column with no
    behaviour behind it."""
    session.assert_stat_dict_covers_board()
    entry = session.stat_entry(session.REACH_COL)
    assert entry["worked_example"].strip() and entry["provenance"].strip()

    cli = _load_cli()
    assert session.REACH_COL in cli._VIEW_FMT["slim"]
    assert session.REACH_COL not in cli._VIEW_FMT["advanced"]


def test_ui1_the_prose_census_is_under_its_bar():
    """B2, as a unit test so a later session cannot quietly re-inflate the app.

    ⚠ The count is `st.caption` + the four alert primitives — 37 + 31 = the 68 `docs/UI-PLAN.md`
    §3.1 measured. `st.badge`, `st.popover` and `help=` are where the compressed text went, and
    they are *not* counted, which is the whole point: the rule is that an explanation longer than
    one line moves, and that a state-dependent fact becomes a chip.
    """
    import re as _re

    app_dir = Path(__file__).resolve().parents[1] / "app"
    pattern = _re.compile(r"\.(caption|warning|info|error|success)\(")
    total = sum(len(pattern.findall(f.read_text())) for f in app_dir.glob("*.py"))
    assert total <= 25, f"prose blocks back up to {total}"


def _load_cli():
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "steps" / "mock_draft.py"
    spec = importlib.util.spec_from_file_location("_mock_draft_cli_ui1", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ================================================================================================
# Session UI-2 — "the board answers the question"
# ================================================================================================
def test_ui2_delta_is_the_engines_own_pick_counter(k2_built):
    """B2's first half. ``Δ`` is ``adp − overall_pick``, and there is no second counter."""
    from fantasy_quant.draft.simulator import _apply_pick, pick_by_adp

    state, meta = _k2_draft(k2_built, finish=False)
    for _ in range(7):
        t = state.team_on_clock()
        _apply_pick(state, t, int(pick_by_adp(state, t, noise=0.0)))
    view = session.board_view(state, 0, n=20)
    expected = pd.to_numeric(view["ADP"], errors="coerce") - float(state.overall_pick)
    pd.testing.assert_series_equal(view["Δ"], expected, check_names=False)
    # and it *recomputes* — one more pick and every surviving row's Δ falls by exactly one, which
    # is the claim "no second counter" actually makes. (A frozen column would fail this; an
    # identity check alone would not, because it would hold against a stale counter too.)
    t = state.team_on_clock()
    _apply_pick(state, t, int(pick_by_adp(state, t, noise=0.0)))
    after = session.board_view(state, 0, n=200)
    common = after.index.intersection(view.index)
    assert len(common) >= 15
    assert np.allclose(after.loc[common, "Δ"], view.loc[common, "Δ"] - 1.0)


def test_ui2_bargain_is_static_and_matches_the_player_card(k2_built):
    """B2's second half — *one derivation, two surfaces*, plus the claim that it does not drift.

    The card carries it as a **field**, not a ninth bar: ``card["bars"]`` is a shape this file and
    two committed bar sheets assert the length of.
    """
    from fantasy_quant.draft.simulator import _apply_pick, pick_by_adp

    state, meta = _k2_draft(k2_built, finish=False)
    first = session.board_view(state, 0, n=25)["BARGAIN"].copy()
    for _ in range(9):
        t = state.team_on_clock()
        _apply_pick(state, t, int(pick_by_adp(state, t, noise=0.0)))
    later = session.board_view(state, 0, n=200)["BARGAIN"]
    common = first.index.intersection(later.index)
    assert len(common) >= 5
    # STATIC: both ranks are over the whole board, so emptying the pool cannot move it
    pd.testing.assert_series_equal(first.loc[common], later.loc[common], check_names=False)

    board = state.board
    idx = int(common[0])
    card = session.player_card(state, idx, vi=k2_built["value_index"], lam=0.01)
    assert len(card["bars"]) == 8, "the card's bar shape is asserted by two committed sheets"
    assert card["bargain"]["value"] == pytest.approx(float(later.loc[idx]))
    assert card["bargain"]["rounds"] == pytest.approx(float(later.loc[idx]) / state.n_teams)
    # the sign convention: positive means value the market has not charged for
    adp_rank = pd.to_numeric(board["adp"], errors="coerce").rank(method="min")
    assert float(later.loc[idx]) == pytest.approx(
        float(adp_rank.loc[idx]) - float(board.loc[idx, "overall_rank"]))


def test_ui2_the_construction_glyphs_are_the_post_draft_function(k2_built):
    """B3 — every roster-shape glyph is a delta of ``roster_construction_risk``'s own scalars."""
    from fantasy_quant.draft.simulator import _apply_pick, pick_by_adp

    state, meta = _k2_draft(k2_built, finish=False)
    for _ in range(24):
        t = state.team_on_clock()
        _apply_pick(state, t, int(pick_by_adp(state, t, noise=0.0)))
    byes = pd.Series({str(k): int(4 + i % 6)
                      for i, k in enumerate(state.board["player_key"].astype(str))})
    seat, vi = 0, k2_built["value_index"]
    pool = state.draftable_pool(seat).head(12)
    flags = session.construction_flags(state, seat, pool.index, vi=vi, byes=byes, elevation=1.5)
    base = session.roster_construction_risk(state, seat, vi=vi, byes=byes, elevation=1.5)
    roster = state.roster(seat)
    g = session.CONSTRUCTION_GLYPHS
    checked = 0
    for i in pool.index:
        hypo = session.roster_construction_risk(
            state, seat, vi=vi, byes=byes, elevation=1.5,
            roster=pd.concat([roster, state.board.loc[[i]]], ignore_index=True))
        # each glyph is the candidate's OWN row in the hypothetical readout — not a movement in
        # that readout's maximum, which fires only when he joins the already-largest cluster
        wk = byes.get(str(state.board.loc[i, "player_key"]))
        hb, hc = hypo["byes"], hypo["concentration"]
        bye_row = hb[hb["week"].astype(str) == str(int(wk))] if pd.notna(wk) and len(hb) \
            else hb.iloc[:0]
        tm = state.board.loc[i, "team"]
        tm_row = hc[hc["nfl_team"].astype(str) == str(tm)] if isinstance(tm, str) and len(hc) \
            else hc.iloc[:0]
        assert (g["bye"] in flags.loc[i]) is bool(
            str(state.board.loc[i, "player_name"]) in set(hypo["starters"])
            and len(bye_row) and int(bye_row.iloc[0]["n"]) >= 2)
        assert (g["stack"] in flags.loc[i]) is bool(
            len(tm_row) and int(tm_row.iloc[0]["n"]) >= 2
            and int(tm_row.iloc[0]["n_starters"]) >= 1)
        assert (g["handcuff"] in flags.loc[i]) is (
            hypo["n_handcuff_gaps"] < base["n_handcuff_gaps"])
        checked += 1
    assert checked == 12
    # the control: a bar that cannot fire is the same defect as a bar that cannot fail
    assert any(g["bye"] in s for s in flags), "no ⚑ fired on a board where every bye collides"


def test_ui2_an_unknown_bye_produces_silence_not_a_clean_bill(k2_built):
    """14.F's rule, on the live glyph: no bye table means no ``⚑``, never a fabricated absence."""
    from fantasy_quant.draft.simulator import _apply_pick, pick_by_adp

    state, meta = _k2_draft(k2_built, finish=False)
    for _ in range(24):
        t = state.team_on_clock()
        _apply_pick(state, t, int(pick_by_adp(state, t, noise=0.0)))
    idx = state.draftable_pool(0).head(10).index
    none = session.construction_flags(state, 0, idx, vi=k2_built["value_index"], byes=None)
    assert not any(session.CONSTRUCTION_GLYPHS["bye"] in s for s in none)


def test_ui2_risks_never_edits_the_flags_string(k2_built):
    """UI-1's rule, carried forward: K2's bar B4 matches on ``FLAGS``, so a display layer may not
    edit it. ``RISKS`` is a second column and ``FLAGS`` is byte-identical to ``range_flags``."""
    state, meta = _k2_draft(k2_built, finish=False)
    view = session.board_view(state, 0, n=30)
    pool = state.draftable_pool(0).head(30)
    pd.testing.assert_series_equal(view["FLAGS"], session.range_flags(pool), check_names=False)
    for glyph in session.CONSTRUCTION_GLYPHS.values():
        assert not any(glyph in str(f) for f in view["FLAGS"])


def test_ui2_every_mode_is_a_projection_of_one_frame(k2_built):
    """B4 — one query, N projections. K1.5's B2, two modes wider, and the ``#`` handle survives."""
    state, meta = _k2_draft(k2_built, finish=False)
    view = session.board_view(state, 0, n=30)
    seen = {}
    for mode in session.VIEW_MODES:
        proj = session.project_view(view, mode=mode)
        assert list(proj.index) == list(view.index), f"{mode} reordered or dropped rows"
        seen[mode] = list(proj.columns)
    assert seen["advanced"] == [lbl for _, lbl in session.BOARD_VIEW_COLS]
    assert seen["value"] == list(session.VALUE_VIEW_COLS)
    assert seen["risk"] == list(session.RISK_VIEW_COLS)
    assert seen["slim"] == list(session.SLIM_VIEW_COLS)
    # the split covers the fifteen it replaced, minus nothing
    assert set(seen["value"]) | set(seen["risk"]) >= set(seen["advanced"])
    # and no mode is back up at fifteen
    for mode in session.APP_VIEW_MODES:
        assert len(seen[mode]) < len(seen["advanced"])


def test_ui2_advanced_is_untouched_by_the_new_columns(k2_built):
    """B0's structural half: two committed bar sheets difference against this exact frame."""
    state, meta = _k2_draft(k2_built, finish=False)
    view = session.board_view(state, 0, n=20)
    assert list(session.project_view(view, advanced=True).columns) == [
        lbl for _, lbl in session.BOARD_VIEW_COLS]
    for col in session.UI2_COLS:
        assert col not in [lbl for _, lbl in session.BOARD_VIEW_COLS]


def test_ui2_the_overlap_tier_rule_is_a_null_and_stays_runnable(k2_built):
    """The session's finding, pinned so it cannot be quietly re-adopted.

    ``method="overlap"`` is `docs/BUILD_PLAN.md`'s recommended cut and it does not cut: an 80 %
    season band is an order of magnitude wider than the gap between neighbours, so every adjacent
    pair overlaps. This asserts the *mechanism*, not the 2026 board's exact numbers.
    """
    lo = np.array([10.0, 9.0, 8.0, 7.0])
    hi = np.array([200.0, 199.0, 198.0, 197.0])          # bands ~20x the gaps
    assert np.nanmax(session._tiers_from_bands(lo, hi)) == 1
    # it *can* cut when the bands are narrow relative to the gaps — so the null is about the data
    assert np.nanmax(session._tiers_from_bands(np.array([100.0, 10.0]),
                                               np.array([110.0, 20.0]))) == 2
    # a missing band is skipped, never a break (T22's rule on a third face)
    ids = session._tiers_from_bands(np.array([10.0, np.nan, 9.0]),
                                    np.array([200.0, np.nan, 199.0]))
    assert np.isnan(ids[1]) and ids[0] == 1 and ids[2] == 1
    # and it is not wired to any rendered view
    for cols in (session.SLIM_VIEW_COLS, session.VALUE_VIEW_COLS, session.RISK_VIEW_COLS,
                 session.RANGE_VIEW_COLS, tuple(lbl for _, lbl in session.BOARD_VIEW_COLS)):
        assert "TIER" not in cols


def test_ui2_coin_flags_false_means_two_different_things(k2_built):
    """The decomposition behind the null: ``False`` is *distinguishable* **or** *unknown*."""
    lo = pd.Series([10.0, 9.0, np.nan, 500.0])
    hi = pd.Series([200.0, 199.0, np.nan, 600.0])
    flags = session.coin_flags(lo, hi)
    assert bool(flags[0]) is True            # bands overlap
    assert bool(flags[1]) is False           # neighbour has no band  -> UNKNOWN
    assert bool(flags[2]) is False           # this row has no band   -> UNKNOWN
    # so a bare count of False conflates the two, which is what the published 146/199 does
    banded = np.isfinite(lo.to_numpy(float)) & np.isfinite(hi.to_numpy(float))
    evaluable = banded[:-1] & banded[1:]
    assert evaluable.sum() == 1 and flags[:-1][evaluable].all()


def test_ui2_positional_strength_is_starters_only_and_sums_to_the_room(k2_built):
    """A6 — the chart's derivation. Slot-aware (T28), and the median is the room's own."""
    from fantasy_quant.draft import optimizer as draft_optimizer

    state, meta = _k2_draft(k2_built)
    sm = session.seat_map_from(meta)
    tab = session.positional_strength(state, sm, k2_built["value_index"])
    assert set(tab["pos"]) == {"QB", "RB", "WR", "TE", "K", "DST"}
    assert len(tab) == state.n_teams * 6
    for _pos, grp in tab.groupby("pos"):
        assert float(grp["room_median"].iloc[0]) == pytest.approx(float(grp["value"].median()))
        assert np.allclose(grp["delta"], grp["value"] - grp["room_median"])
    # starters only: a team's total here cannot exceed its slot-blind capital
    for t in range(state.n_teams):
        mine = tab[tab["team"] == t + 1]["value"].sum()
        capital = draft_optimizer.team_value(state.roster(t), k2_built["value_index"])
        assert mine <= capital + 1e-6


def test_ui2_the_stat_dictionary_covers_the_new_columns():
    """B5 — a column with no entry fails the build, and one with no CLI home has no behaviour."""
    session.assert_stat_dict_covers_board()
    cli = _load_cli()
    for col in session.UI2_COLS:
        assert col in session.STAT_DICT, col
        assert session.stat_entry(col)["worked_example"]
        assert any(col in fmt or col in ("RISKS",) for fmt in cli._VIEW_FMT.values()), col
    assert set(cli._VIEW_FMT) == set(session.VIEW_MODES)


def test_ui2_the_signed_ink_is_a_tint_that_survives_both_themes():
    """UI-1's two-treatments rule, on the value pair: a colour that works in one theme is a bug."""
    from app import palette as pal

    assert pal.signed_style(3.0).startswith("background-color: rgba")
    assert pal.signed_style(-3.0).startswith("background-color: rgba")
    assert pal.signed_style(0.0) == "" and pal.signed_style(None) == ""
    assert "; color:" not in pal.signed_style(3.0), "a tint must not set the text colour"
    assert pal.VALUE_GOOD not in pal.POSITION_COLORS.values()
    assert pal.VALUE_BAD not in pal.POSITION_COLORS.values()
    # the measured floor: both poles clear 3.0 against both surfaces and white
    for surface in ("#0F1115", "#181B21", "#FFFFFF"):
        for hue in (pal.VALUE_GOOD, pal.VALUE_BAD):
            assert pal.contrast_ratio(hue, surface) >= 3.0, (hue, surface)


# ------------------------------------------------------------------------------------------------
# UI-3 step 1 (A1) — the tags and the queue: a preference is an object, and it gets priced
# ------------------------------------------------------------------------------------------------
def test_ui3_a_tag_produces_the_config_the_multiselects_produced():
    """★ **B1's core, as a unit test: the tag path and the deleted multiselect path are the same
    object.** The four ``st.multiselect``s cannot be re-run — they are gone — so the config they
    built was recorded before the deletion (``analysis/ui3_cost_multiselect_baseline.json``) and
    this differences against the record. *A replacement for a deleted path is only checkable if the
    deleted path was written down first.*
    """
    import json

    rec = json.loads(Path("analysis/ui3_cost_multiselect_baseline.json").read_text())
    keys, want = rec["keys"], rec["config"]
    cfg = session.tag_config(
        {keys["must"]: "must", keys["never"]: "never",
         keys["reach"]: "reach", keys["wait"]: "wait"},
        archetype=want["archetype"], risk_lambda=want["risk_lambda"])
    assert [[m.player_key, m.reach_budget] for m in cfg.must_draft] == want["must_draft"]
    assert sorted(cfg.never_draft) == want["never_draft"]
    assert dict(cfg.tilts) == want["tilts"]
    assert cfg.archetype == want["archetype"] and cfg.risk_lambda == want["risk_lambda"]


def test_ui3_an_unknown_tag_raises_rather_than_being_dropped():
    """A preference the engine silently ignores is worse than one it refuses: the user sees the
    tag, the report prices a league without it, and nothing says so."""
    with pytest.raises(ValueError, match="unknown tag"):
        session.tag_config({"00-0000001": "sleeper"})


def test_ui3_tags_render_on_the_board_and_untagged_rows_stay_blank(k2_built):
    state, _ = _k2_draft(k2_built, finish=False)
    view = session.board_view(state, 0, n=10)
    keys = state.board["player_key"].astype(str)
    first, second = str(keys.loc[view.index[0]]), str(keys.loc[view.index[1]])
    out = session.attach_tags(view, state.board, {first: "must"}, queue=[second])
    assert out.loc[view.index[0], session.TAG_COL] == session.TAGS["must"]["glyph"]
    assert out.loc[view.index[1], session.TAG_COL] == session.QUEUE_GLYPH
    assert out.loc[view.index[2], session.TAG_COL] == ""
    # and the frame it was placed on is otherwise untouched — a placement, not a projection
    assert list(out.columns)[:-1] == list(view.columns)
    assert out.drop(columns=[session.TAG_COL]).equals(view)


def test_ui3_the_queue_skips_the_gone_and_never_takes_a_never(k2_built):
    """★ **B4's hard half.** ``never_draft`` is a hard constraint in the S1 preference contract, so
    the queue button must not be the place it becomes soft — asserted against a queue whose *first*
    entry is the tagged player, i.e. the case where skipping him actually costs something."""
    from fantasy_quant.draft.simulator import _apply_pick

    state, _ = _k2_draft(k2_built, finish=False)
    pool = state.draftable_pool(0)
    refused, taken, wanted = (str(pool["player_key"].iloc[i]) for i in (0, 1, 2))
    taken_idx = int(pool.index[1])
    _apply_pick(state, 1, taken_idx)                       # somebody else drafts the second man

    res = session.queue_next(state, 0, [refused, taken, wanted], {refused: "never"})
    assert res["player_key"] == wanted
    assert [s["player_key"] for s in res["skipped"]] == [refused, taken]
    assert "never" in res["skipped"][0]["why"] and "drafted" in res["skipped"][1]["why"]
    # the refusal is absolute: alone in the queue, he is still not offered
    assert session.queue_next(state, 0, [refused], {refused: "never"})["board_index"] is None


def test_ui3_the_queue_only_offers_a_legal_pick(k2_built):
    """Roster legality is the engine's, not the UI's: the candidate set IS ``draftable_pool``."""
    state, _ = _k2_draft(k2_built, finish=False)
    legal = set(state.draftable_pool(0).index)
    every_key = list(state.board["player_key"].astype(str))
    res = session.queue_next(state, 0, every_key, {})
    assert res["board_index"] in legal


def test_ui3_the_tag_column_is_documented_and_the_dictionary_still_covers_the_board():
    session.assert_stat_dict_covers_board()
    assert session.stat_entry(session.TAG_COL)["worked_example"]
    # every tag the vocabulary offers is explained in the one place a column is explained
    entry = session.stat_entry(session.TAG_COL)["what_it_means"]
    for spec in session.TAGS.values():
        assert spec["glyph"] in entry, spec
    assert session.QUEUE_GLYPH in entry


def test_ui3_tags_are_preferences_and_survive_a_new_draft():
    """``clear_draft`` drops everything derived from a draft. A tag is not derived from a draft —
    it is a statement about a player, and starting a new mock does not change your mind."""
    import app.state as app_state

    class _FakeState(dict):
        pass

    fake = _FakeState()
    real = app_state.st.session_state
    app_state.st.session_state = fake                       # no Streamlit runtime in a unit test
    try:
        app_state.set_tag("00-0000001", "must")
        app_state.toggle_queue("00-0000002")
        fake["draft"] = {"state": None}
        app_state.clear_draft()
        assert fake.get("draft") is None
        assert app_state.tags() == {"00-0000001": "must"}
        assert app_state.queue() == ["00-0000002"]
        app_state.set_tag("00-0000001", None)
        app_state.toggle_queue("00-0000002")
        assert app_state.tags() == {} and app_state.queue() == []
    finally:
        app_state.st.session_state = real


# ------------------------------------------------------------------------------------------------
# UI-3 step 2 (A2) — the selected-player strip
# ------------------------------------------------------------------------------------------------
def test_ui3_the_impact_bar_is_the_value_rank_and_never_the_market_one(k2_built):
    """★ The trap A2 walked into: the board carries **two** positional ranks and they disagree.

    ``board["pos_rank"]`` is filled from ``adp_pos_rank`` — the market's order, i.e. the
    *availability* signal — while PLAYER-VIEW bar #1 is *Impact / value*. On the live 2026 board
    the ADP RB1 is our RB2, so a renderer that reached for the column sitting right there would
    have put the availability signal into the value channel under a label saying otherwise, which
    the 2026-07-04 reframe forbids by name.

    The assertion is structural, not incidental: scribble on ``pos_rank`` and **nothing moves.**
    """
    state, _ = _k2_draft(k2_built, finish=False)
    vpr = session.value_pos_rank(state)
    board = state.board
    for pos, grp in board.groupby("pos"):
        ranks = vpr.loc[grp.index].dropna()
        assert ranks.min() == 1.0, pos
        assert vpr.loc[grp["overall_rank"].astype(float).idxmin()] == 1.0, pos

    scrambled = board.copy()
    scrambled["pos_rank"] = scrambled["pos_rank"].to_numpy()[::-1]
    state.board = scrambled
    pd.testing.assert_series_equal(session.value_pos_rank(state), vpr)
    state.board = board

    idx = int(board.index[3])
    card = session.player_card(state, idx, vi=k2_built["value_index"], lam=0.01)
    assert card["impact"]["value"] == pytest.approx(float(vpr.loc[idx]))
    assert card["impact"]["text"] == f"{board.loc[idx, 'pos']}{int(vpr.loc[idx])}"


def test_ui3_the_strip_is_five_numbers_lifted_out_of_the_card(k2_built):
    """B2, structurally — the strip is a *projection of the card*, so it cannot hold a number the
    dialog does not. Comparing two renderings proves they agree today; taking one from the other
    proves they cannot disagree, which is the same argument K1's B1 makes one layer up."""
    state, _ = _k2_draft(k2_built, finish=False)
    idx = int(state.board.index[3])
    card = session.player_card(state, idx, vi=k2_built["value_index"], lam=0.01)
    strip = session.card_strip(card)

    assert [e["label"] for e in strip] == [lbl for lbl, _ in session.STRIP_BARS]
    assert len(strip) == 5, "PLAYER-VIEW §3 is five, and the deep-page-only three stay off it"
    assert len(card["bars"]) == 8, "the card's bar shape is asserted by two committed sheets"

    bars = {b["label"]: b for b in card["bars"]}
    for e in strip:
        if e["label"] in bars:
            assert e["value"] == bars[e["label"]]["value"], e["label"]
    assert strip[0]["value"] == card["impact"]["value"]
    # #5 is carried in **rounds**, which is §2's own worked example ("+1.5 rounds of value")
    assert strip[-1]["value"] == card["bargain"]["rounds"]
    assert strip[-1]["text"].endswith("rounds")
    assert all(e["help"] for e in strip), "every number on the glance carries its 14.O tooltip"


def test_ui3_a_strip_number_that_does_not_exist_is_blank_and_not_zero(k2_built):
    """T22's rule, on the newest surface. A player nobody simulated has no boom rate; rendering
    him at ``0.00`` reads as *never booms*, which is a claim the board never made."""
    state, _ = _k2_draft(k2_built, finish=False)
    missing = state.board.index[state.board["boom_prob_live"].isna()]
    assert len(missing), "the fixture is meant to contain unseen players"
    card = session.player_card(state, int(missing[0]), vi=k2_built["value_index"], lam=0.01)
    boom = {e["label"]: e for e in session.card_strip(card)}["BOOM"]
    assert boom["value"] is None and boom["text"] is None


def test_ui3_every_strip_label_is_documented():
    """14.O's rule reaches the strip: a number on screen with no dictionary entry is a number a
    reader has to guess at, and ``IMPACT`` is a new one this session invented."""
    for label, _ in session.STRIP_BARS:
        assert session.stat_entry(label)["one_line"]
    assert "ADP" in session.stat_entry("IMPACT")["how_to_read_it"], \
        "the entry must carry the pos_rank collision, because that is the trap"


# ------------------------------------------------------------------------------------------------
# UI-3 step 3 (A3) — the bars are drawn, and §5 is asserted on the HTML
# ------------------------------------------------------------------------------------------------
def test_ui3_green_is_good_always_and_the_risk_trait_is_inverted(k2_built):
    """★ B3's core, on the **rendered HTML** rather than on the spec.

    ``BUST`` is the one readout of the ten whose number is a rate of *failure*, so it is the one
    §5's "green = good for the drafter, always" has to invert. Un-inverted, the player most likely
    to bust draws the longest greenest bar on the page — praise, for the warning.
    """
    from app import palette as pal
    from app import views as app_views

    state, _ = _k2_draft(k2_built, finish=False)
    bust = pd.to_numeric(state.board["bust_prob_live"], errors="coerce")
    worst, best = int(bust.idxmax()), int(bust.idxmin())

    seen = {}
    for idx in (worst, best):
        card = session.player_card(state, idx, vi=k2_built["value_index"], lam=0.01)
        b = {x["label"]: x for x in card["bars"]}["BUST"]
        seen[idx] = b
        html = app_views.bar_html("BUST", f"{b['value']:.2f}", b["pct_overall"], b["pct_pos"],
                                  help=b["help"], n_pos=b["n_pos"])
        assert pal.tier_color(b["pct_overall"]) in html

    assert seen[worst]["pct_overall"] < seen[best]["pct_overall"], "the inversion is the claim"
    assert pal.tier_color(seen[worst]["pct_overall"]) == pal.VALUE_BAD
    assert pal.tier_color(seen[best]["pct_overall"]) == pal.VALUE_GOOD
    # and the length agrees with the colour, which is §5's "same scale" clause
    assert seen[worst]["pct_overall"] < pal.TIER_CUTS[0] < pal.TIER_CUTS[1] \
        < seen[best]["pct_overall"]


def test_ui3_both_baselines_are_on_the_bar_and_neither_moves_as_the_draft_empties(k2_built):
    """§5's dual baseline — fill = overall, tick = within-position — and the user's 2026-08-17
    decision that both are taken over the **whole board**. A pool-relative fill would rise every
    time somebody else was drafted: the bar would be measuring the draft, not the player."""
    from app import views as app_views

    from fantasy_quant.draft.simulator import _apply_pick, pick_by_adp

    state, _ = _k2_draft(k2_built, finish=False)
    idx = int(state.board.index[5])
    before = session.bar_percentiles(state, idx)
    for _ in range(20):
        t = state.team_on_clock()
        _apply_pick(state, t, int(pick_by_adp(state, t, noise=0.0)))
    assert session.bar_percentiles(state, idx) == before, "static, by construction"

    b = {x["label"]: x for x in
         session.player_card(state, idx, vi=k2_built["value_index"], lam=0.01)["bars"]}["PROJ"]
    html = app_views.bar_html("PROJ", "300", b["pct_overall"], b["pct_pos"], n_pos=b["n_pos"])
    assert f"width:{b['pct_overall'] * 100:.1f}%" in html, "the fill is the overall percentile"
    assert f"left:{b['pct_pos'] * 100:.1f}%" in html, "the tick is the within-position percentile"
    assert "at his position" in html, "§5's secondary baseline is spelled, not only ticked"


def test_ui3_a_bar_with_no_reading_is_not_a_bar_of_zero(k2_built):
    """T22 in a new medium. A zero-width fill is not *unknown*, it renders as **worst on the
    board** — a claim about a player nobody measured."""
    from app import palette as pal
    from app import views as app_views

    state, _ = _k2_draft(k2_built, finish=False)
    missing = state.board.index[state.board["boom_prob_live"].isna()]
    assert len(missing)
    card = session.player_card(state, int(missing[0]), vi=k2_built["value_index"], lam=0.01)
    b = {x["label"]: x for x in card["bars"]}["BOOM"]
    assert b["pct_overall"] is None and b["pct_pos"] is None
    html = app_views.bar_html("BOOM", "—", b["pct_overall"], b["pct_pos"])
    assert "dashed" in html and "width:" not in html
    assert not any(h in html for h in (pal.VALUE_GOOD, pal.VALUE_BAD, pal.TIER_MID))
    assert pal.tier_color(None) is None


def test_ui3_the_eight_bars_are_spelled_in_exactly_one_place(k2_built):
    """``CARD_BARS`` replaced a literal list inside ``player_card`` so the percentiles could not
    hold a second opinion about which column ``BUST`` reads. The values must be unchanged."""
    state, _ = _k2_draft(k2_built, finish=False)
    idx = int(state.board.index[4])
    card = session.player_card(state, idx, vi=k2_built["value_index"], lam=0.01)
    assert [b["label"] for b in card["bars"]] == [lbl for lbl, *_ in session.CARD_BARS]
    for label, col, fmt, _good in session.CARD_BARS:
        b = {x["label"]: x for x in card["bars"]}[label]
        raw = pd.to_numeric(pd.Series([state.board.loc[idx, col]]), errors="coerce").iloc[0]
        assert (b["value"] is None) if pd.isna(raw) else b["value"] == pytest.approx(float(raw))
        assert b["fmt"] == fmt
    inverted = [lbl for lbl, _c, _f, good in session.CARD_BARS if good < 0]
    assert inverted == ["BUST"], "the risk-trait list is a decision, not an accident"


def test_ui3_the_third_tier_colour_survives_both_themes():
    """The same measured floor UI-2 held its value pair to. Okabe-Ito's own yellow — the obvious
    pick — scores **1.32 against white**, i.e. invisible the moment a reader flips the theme."""
    from app import palette as pal

    for surface in ("#0F1115", "#181B21", "#FFFFFF"):
        assert pal.contrast_ratio(pal.TIER_MID, surface) >= 3.0, surface
    assert pal.contrast_ratio("#F0E442", "#FFFFFF") < 2.0, "the rejected candidate, on the record"
    assert pal.TIER_MID not in pal.POSITION_COLORS.values()
    assert pal.tier_color(0.9) == pal.VALUE_GOOD
    assert pal.tier_color(0.5) == pal.TIER_MID
    assert pal.tier_color(0.1) == pal.VALUE_BAD


def test_ui3_the_grade_bars_read_the_score_on_its_own_scale():
    """★ The regression for the defect A3 found in its own first draft.

    ``score_*`` is **0–1** and the bar divided it by 100, drawing every contribution as a
    near-empty red bar. The number itself had been correct on screen for two sessions — as a table
    column formatted ``%.2f`` its scale never had to be known. *Drawing a number is the first thing
    that asks what its maximum is.*

    Built on ``apply_grade`` directly rather than on a finished draft: the scale is a property of
    the scoring, and a test that needed a season simulation to reach it would not be run.
    """
    from app import views as app_views

    rng = np.random.default_rng(1)
    comps = pd.DataFrame({"team": np.arange(1, 11), "who": [f"T{i}" for i in range(1, 11)],
                          **{c: rng.uniform(0, 50, 10) for c in session.GRADE_WEIGHTS}})
    grade = session.apply_grade(comps)
    r = grade.iloc[0]

    entries = app_views.grade_bars(r)
    assert [e["label"] for e in entries] == [c.upper() for c in session.GRADE_WEIGHTS]
    for (name, w), e in zip(session.GRADE_WEIGHTS.items(), entries, strict=True):
        assert 0.0 <= e["pct_overall"] <= 1.0, (name, e["pct_overall"])
        assert e["pct_overall"] == pytest.approx(float(r[f"score_{name}"]))
        # points = score × weight is B5's identity; the bar must not invent a third scale
        assert float(r[f"points_{name}"]) == pytest.approx(e["pct_overall"] * w)
        assert e["text"] == f"{r[f'points_{name}']:.1f} / {w:.0f}"

    # the property the /100 broke: the room's best on a component fills its bar and banks its
    # whole weight, and the room's worst empties it
    top = session.apply_grade(comps).sort_values("odds", ascending=False).iloc[0]
    best = {e["label"]: e for e in app_views.grade_bars(top)}["ODDS"]
    w_odds = session.GRADE_WEIGHTS["odds"]
    assert best["pct_overall"] == pytest.approx(1.0)
    assert best["text"] == f"{w_odds:.1f} / {w_odds:.0f}"


# ------------------------------------------------------------------------------------------------
# UI-3 step 4 (A7) — fewer taps to a pick
# ------------------------------------------------------------------------------------------------
def test_ui3_there_is_one_way_into_a_pick_and_the_confirm_survived(k2_built):
    """A7 — three routes collapse to one, and the thing that got deleted is a *step*, not the
    confirmation.

    ⚠ Asserted on the **AST**, not on the text. UI-1's lesson: a grep cannot tell doing from
    describing, and this module's comments name ``_confirm_bar`` and the quick row precisely to
    record why they are gone — a text search would find both and report the deletion as undone.
    """
    import ast

    import app.draft_room as room

    tree = ast.parse(Path(room.__file__).read_text())
    fns = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "_pick_selector" in fns, "A7's one control"
    assert "_confirm_bar" not in fns, "deleted — `views.selected_strip` is the confirm bar now"
    assert "_card_button" not in fns, "deleted — the strip's footer opens the deep page"
    assert not hasattr(room, "_confirm_bar") and not hasattr(room, "_card_button")

    # the pick still goes through exactly one function, and it is the one that reruns
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_apply"]
    assert len(calls) == 1, "one call site: the strip's action. Autopick has its own engine path."

    # ★ `resolve_pick` is **kept, not default** — the CLI still types a name at it, and the app
    # simply no longer needs to parse one because a selectbox never hands it a free-text query.
    state, _ = _k2_draft(k2_built, finish=False)
    idx = int(state.board.index[7])
    found = session.resolve_pick(state, 0, str(state.board.loc[idx, "player_name"]))
    # the fixture's names are substrings of each other ("Player 7" is in "Player 70"), which is
    # exactly the ambiguity the CLI's two-step exists for — so the claim is that he is *in* the
    # match set, not that a prefix resolves to one man.
    assert idx in ([found] if isinstance(found, int) else [m["index"] for m in found])
    import steps.mock_draft as cli
    assert cli.session.resolve_pick is session.resolve_pick
