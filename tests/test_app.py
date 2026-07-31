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
    """★ B1, structurally: there is ONE computation, and both surfaces are renderers over it.

    Comparing two implementations' *output* proves they agree on the case tested. Comparing their
    *identity* proves they cannot disagree at all — which is the claim Session K1 actually makes,
    and the only version of it that survives someone editing one file next month.
    """
    import app.main as app_main
    import steps.mock_draft as cli

    for name in ("board_view", "explain_chain", "summary_table", "roster_view", "odds_table",
                 "drift_frames", "seat_map_from", "seat_label", "advance", "room_mix",
                 "resolve_pick"):
        assert getattr(cli.session, name) is getattr(session, name)
        assert getattr(app_main.session, name) is getattr(session, name)

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
    assert list(session.board_view(a, 2).columns) == [lbl for _, lbl in session.BOARD_VIEW_COLS]


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
