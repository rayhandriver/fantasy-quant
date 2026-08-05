"""16.18 — the manager profile: beliefs as a file, and the seat that drafts on them.

Every test here is offline and synthetic. The one that matters most is
:func:`test_fitted_manager_is_not_inert` — this repo has shipped five mechanisms that ran, passed
their suites and did nothing (``homer``'s fandom, ``rookie_hawk``'s discarded column, the 16.15
hype routing, the 16.9 shock, the ``reacher``'s missing direction), so a personality test that only
checks "a legal draft completed" is a test that cannot fail.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fantasy_quant.draft import mock
from fantasy_quant.draft import personalities as P
from fantasy_quant.draft.manager_profile import (
    ManagerProfile,
    avoid_mask,
    build_profile,
    confidence_mult,
    load_profile,
    name_key,
    personal_adp,
    profile_deltas,
)
from fantasy_quant.draft.opponent_model import ALL_FEATURES, OpponentModel

MAX_DELTA = 24.0


# ------------------------------------------------------------------------------- fixtures
@pytest.fixture
def board() -> pd.DataFrame:
    """A 120-player board with one team defense, which is the row that has no ``gsis_id``."""
    rng = np.random.default_rng(0)
    pos = ["RB"] * 34 + ["WR"] * 42 + ["QB"] * 14 + ["TE"] * 14 + ["K"] * 8 + ["DST"] * 8
    rng.shuffle(pos)
    n = len(pos)
    gsis = [f"00-{i:07d}" for i in range(n)]
    gsis[5] = None                                     # a defense-shaped row: keys on its name
    return pd.DataFrame({
        "gsis_id": gsis,
        "name": [f"Player {i}" for i in range(n)],
        "position": pos,
        "team": ["GB" if i % 17 == 0 else "FA" for i in range(n)],
        "adp": np.arange(1, n + 1, dtype=float),
        "stdev": rng.uniform(1, 12, n),
        "pos_rank": np.arange(1, n + 1),
    })


@pytest.fixture
def workbook(board) -> pd.DataFrame:
    """A filled sheet over the first 40 board rows, in the workbook's own vocabulary."""
    head = board.head(40).reset_index(drop=True)
    words = ["Very undervalued", "Undervalued", "Evenly valued", "Overvalued", "Very overvalued"]
    return pd.DataFrame({
        "Player": head["name"], "Pos": head["position"], "Team": head["team"],
        "Personal Value": [words[i % 5] for i in range(len(head))],
        "Value Score": [0] * len(head),                # deliberately wrong: the words must win
        "Confidence (1-5)": [(i % 5) + 1 for i in range(len(head))],
        # every third row is left un-annotated — the subject's "I would not draft him" convention
        "Notes — what you actually believe": [None if i % 3 == 0 else "a reason"
                                              for i in range(len(head))],
    })


@pytest.fixture
def model() -> OpponentModel:
    beta = dict.fromkeys(ALL_FEATURES, 0.0)
    beta["adp_s"] = -1.7
    beta["need"] = 0.5
    return OpponentModel(feature_cols=list(ALL_FEATURES),
                         beta=np.array([beta[c] for c in ALL_FEATURES]))


@pytest.fixture
def profile(workbook, board) -> ManagerProfile:
    return build_profile(workbook, profile_id="test", season=2026, board=board, belief_scale=3.0,
                         avoid_teams=("GB",), team_exceptions=(workbook["Player"].iloc[17],))


# ------------------------------------------------------------------------------- building a profile
def test_confidence_scales_size_but_never_gates_direction():
    assert confidence_mult(1) == pytest.approx(0.5)
    assert confidence_mult(3) == pytest.approx(1.0)
    assert confidence_mult(5) == pytest.approx(1.5)
    assert confidence_mult(None) == pytest.approx(1.0)
    # a low-confidence opinion is a SMALL opinion, not an absent one — zeroing it would delete
    # exactly the rows where the manager is least anchored to consensus.
    assert confidence_mult(1) > 0


def test_beliefs_come_from_the_words_not_the_formula_column(workbook, board):
    """``Value Score`` is a spreadsheet formula; a workbook opened somewhere that did not evaluate
    it reads 0 everywhere, so the words are authoritative and the column is only a fallback."""
    p = build_profile(workbook, profile_id="t", season=2026, board=board, belief_scale=3.0)
    assert any(v > 0 for v in p.beliefs.values())
    assert any(v < 0 for v in p.beliefs.values())


def test_blank_note_becomes_a_hard_avoid_and_deletes_its_own_belief(workbook, board):
    p = build_profile(workbook, profile_id="t", season=2026, board=board, belief_scale=3.0,
                      blank_note_means_avoid=True)
    blank = workbook.loc[workbook["Notes — what you actually believe"].isna(), "Player"]
    keys = {name_key(n, pp) for n, pp in zip(blank, workbook.loc[blank.index, "Pos"], strict=True)}
    resolved = {k for k in p.avoid if p.avoid[k] == "no_interest"}
    assert len(resolved) == len(keys)
    # ...and an avoided player holds no belief: a positive delta on a player the seat will never
    # consider reads to any inspector as an opinion the model holds and does not act on.
    assert not (set(p.avoid) & set(p.beliefs))
    assert p.notes["beliefs_dropped_by_avoid"] > 0


def test_blank_note_rule_is_a_parameter_not_a_constant(workbook, board):
    """One human's spreadsheet convention must not be baked into the reader (the hardcoded-label
    defect this repo has paid for four times)."""
    off = build_profile(workbook, profile_id="t", season=2026, board=board, belief_scale=3.0,
                        blank_note_means_avoid=False)
    assert not any(r == "no_interest" for r in off.avoid.values())


def test_team_rule_applies_with_its_named_exception(workbook, board):
    keep = workbook["Player"].iloc[17]
    p = build_profile(workbook, profile_id="t", season=2026, board=board, belief_scale=3.0,
                      blank_note_means_avoid=False,
                      avoid_teams=("GB",), team_exceptions=(keep,))
    gb = workbook[workbook["Team"] == "GB"]
    assert len(gb) >= 2, "fixture must contain the rule and its exception"
    avoided = {k for k, r in p.avoid.items() if r == "team_rule"}
    assert avoided, "the stated team rule produced no avoids"
    assert not any(name_key(keep, pp) in avoided for pp in gb["Pos"])


def test_a_belief_beyond_the_cap_is_refused():
    with pytest.raises(ValueError, match="exceeds"):
        ManagerProfile(profile_id="t", season=2026, beliefs={"x": MAX_DELTA + 1})


def test_policy_without_a_source_is_refused():
    """An unfitted seat must never be reportable as a fitted one."""
    with pytest.raises(ValueError, match="policy_source"):
        ManagerProfile(profile_id="t", season=2026, policy={"adp_s": 0.1})


def test_round_trip(profile, tmp_path):
    p = profile.save(tmp_path / "p.json")
    back = load_profile(p)
    assert back.beliefs == pytest.approx(profile.beliefs)
    assert back.avoid == profile.avoid
    assert back.belief_scale == pytest.approx(profile.belief_scale)


def test_rescaled_scales_and_clips(profile):
    big = profile.rescaled(1000.0)
    assert max(abs(v) for v in big.beliefs.values()) <= MAX_DELTA + 1e-9
    half = profile.rescaled(profile.belief_scale / 2)
    for k, v in half.beliefs.items():
        assert v == pytest.approx(profile.beliefs[k] / 2, abs=1e-6)


# --------------------------------------------------------------------------- applying it to a board
def test_deltas_resolve_by_gsis_and_by_name(profile, board):
    d = profile_deltas(board, profile, key="gsis_id")
    assert np.count_nonzero(d) == len(profile.beliefs)
    # the row with no gsis must still resolve, or every team defense silently drops out
    no_gsis = board["gsis_id"].isna()
    assert no_gsis.any()
    row = board[no_gsis].iloc[0]
    k = name_key(row["name"], row["position"])
    if k in profile.beliefs:
        assert d[int(np.flatnonzero(no_gsis.to_numpy())[0])] == pytest.approx(profile.beliefs[k])


def test_unrated_players_are_neutral_not_avoided(profile, board):
    """A player who was never on the sheet was never declined — the rule is about rows he SAW."""
    tail = board.tail(40)
    assert profile_deltas(tail, profile, key="gsis_id").tolist() == [0.0] * len(tail)
    assert not avoid_mask(tail, profile, key="gsis_id").any()


def test_personal_adp_is_adp_minus_belief(profile, board):
    padp = personal_adp(board, profile, key="gsis_id")
    d = profile_deltas(board, profile, key="gsis_id")
    assert padp == pytest.approx(np.clip(board["adp"].to_numpy(float) - d, 0.5, None))
    assert (padp > 0).all()


# ------------------------------------------------------------------------------------- the seat
def test_seat_requires_a_profile_and_says_so(model):
    """A ``fitted_manager`` with nothing loaded is a ``balanced`` wearing someone's name."""
    bare = P.Personality("fitted_manager", requires_profile=True)
    with pytest.raises(ValueError, match="manager profile"):
        P.make_opponent_pick_fn(model, bare)
    with pytest.raises(ValueError, match="manager profile"):
        P.assert_room_profiles([bare])


def test_a_profile_without_the_flag_is_refused(profile):
    """The guard keys on ``requires_profile``, so a seat with one and not the other is unguarded."""
    with pytest.raises(ValueError, match="requires_profile"):
        P.Personality("x", manager_profile=profile)


def test_profile_and_private_board_cannot_both_rewrite_adp(model, profile):
    seat = P.Personality("fitted_manager", requires_profile=True, manager_profile=profile)
    with pytest.raises(ValueError, match="private board"):
        P.make_opponent_pick_fn(model, seat, kappa=1.0)


def test_fitted_manager_is_not_inert(board, model, profile):
    """★ The bar that matters: the seat must draft a DIFFERENT roster from the ``balanced`` it
    replaced, on the same seed. An inert personality still completes a legal draft."""
    seat = P.Personality("fitted_manager", requires_profile=True, manager_profile=profile)
    room_a = (seat,) + (P.personalities()["balanced"],) * 9
    room_b = (P.personalities()["balanced"],) * 10
    a = mock.simulate_room_draft(board, room_a, model, n_teams=10, rounds=8, seed=3)
    b = mock.simulate_room_draft(board, room_b, model, n_teams=10, rounds=8, seed=3)
    ra = [r["player_name"] for r in a.log if r["team"] == 0]
    rb = [r["player_name"] for r in b.log if r["team"] == 0]
    assert ra != rb, "the profile changed nothing — the seat is inert"


def test_the_seat_never_drafts_an_avoided_player_it_could_have_declined(board, model, profile):
    seat = P.Personality("fitted_manager", requires_profile=True, manager_profile=profile)
    room = (seat,) + (P.personalities()["balanced"],) * 9
    st = mock.simulate_room_draft(board, room, model, n_teams=10, rounds=8, seed=5)
    mine = {r["player_name"] for r in st.log if r["team"] == 0}
    pos = dict(zip(board["name"], board["position"], strict=True))
    took_avoided = {n for n in mine if name_key(n, pos[n]) in profile.avoid}
    assert not took_avoided, f"drafted declared avoids: {sorted(took_avoided)}"


def test_avoids_can_never_deadlock_a_draft(board, model):
    """A roster has to be completable. An avoid list covering the whole board must degrade to
    ordinary drafting, not raise three rounds in."""
    everyone = {name_key(n, p): "no_interest"
                for n, p in zip(board["name"], board["position"], strict=True)}
    prof = ManagerProfile(profile_id="paranoid", season=2026, avoid=everyone)
    seat = P.Personality("fitted_manager", requires_profile=True, manager_profile=prof)
    room = (seat,) + (P.personalities()["balanced"],) * 9
    st = mock.simulate_room_draft(board, room, model, n_teams=10, rounds=8, seed=1)
    assert len([r for r in st.log if r["team"] == 0]) == 8


def test_an_empty_profile_reproduces_balanced_exactly(board, model):
    """``beliefs={}`` and ``avoid={}`` is the identity — the control that proves the seat's effect
    is its profile and not the plumbing around it."""
    prof = ManagerProfile(profile_id="empty", season=2026)
    seat = P.Personality("fitted_manager", requires_profile=True, manager_profile=prof)
    a = mock.simulate_room_draft(board, (seat,) + (P.personalities()["balanced"],) * 9,
                                 model, n_teams=10, rounds=8, seed=11)
    b = mock.simulate_room_draft(board, (P.personalities()["balanced"],) * 10,
                                 model, n_teams=10, rounds=8, seed=11)
    assert [r["player_name"] for r in a.log] == [r["player_name"] for r in b.log]


def test_the_shipped_room_seats_the_fitted_manager_once():
    assert P.REALISTIC_ROOM.count("fitted_manager") == 1
    assert len(P.REALISTIC_ROOM) == 10
    # the seat that stepped aside is a `balanced`, not a character seat (16.14R step 7's mix)
    assert P.REALISTIC_ROOM.count("balanced") == 3
    for n in ("autopilot", "value_hawk", "safe_floor", "reacher", "upside_chaser", "chalk"):
        assert P.REALISTIC_ROOM.count(n) == 1


def test_the_room_gives_up_balanced_then_the_fitted_manager(monkeypatch):
    """★ 16.18 narrowed the room's give-up pool from 4 ``balanced`` to 3, so the give-up ORDER has
    to carry ``fitted_manager`` or a user driving four seats hits a wall this session introduced.

    The order is not arbitrary: a replica of you is worth having in the room when you drive one
    seat and worth nothing when you are already driving four. Character seats are still never given
    up — that refusal is what protects the mix 16.14R step 7 validated.
    """
    from fantasy_quant.draft import session

    assert session.realistic_mix(0).count("fitted_manager") == 1
    for k in (1, 2, 3):
        mix = session.realistic_mix(k)
        assert len(mix) == 10 - k
        assert mix.count("fitted_manager") == 1, "the replica goes last, not first"
    assert session.realistic_mix(4).count("fitted_manager") == 0
    for k in (0, 1, 2, 3, 4):
        for n in ("autopilot", "value_hawk", "safe_floor", "reacher", "upside_chaser", "chalk"):
            assert session.realistic_mix(k).count(n) == 1, f"{n} was given up at k={k}"
    with pytest.raises(ValueError, match="explicit room"):
        session.realistic_mix(5)


def test_a_profile_is_refused_on_a_season_it_does_not_describe(profile):
    """★★ The PIT guard. A belief board describes ONE season's board on one date, and this repo's
    profile was written in August 2026 by someone who watched 2017–2025 happen — so seating it in a
    2020 simulation feeds the future into a historical measurement.

    ⚠ The leak is **graded**, which is what makes it easy to miss: the 2026 profile fires on 6
    board rows in 2017 and 55 in 2024. A seat that is almost `balanced` early and increasingly
    itself toward the present looks like a seat with a mild opinion, not a bug — and measured, it
    moved the room's profile distance by 0.0007, i.e. **less than any bar in the harness can see.**
    """
    assert profile.covers(2026)
    assert profile.covers(None), "an unstated season must not be treated as a mismatch"
    assert not profile.covers(2024)
    assert not profile.covers(2017)


def test_an_uncovered_season_reproduces_the_pre_1618_room_bit_for_bit(profile):
    """The gate degrades to ``balanced`` rather than raising, and that choice is load-bearing: it is
    what keeps every committed historical bar sheet a valid reference."""
    pre_1618 = ("autopilot", "balanced", "balanced", "balanced", "balanced",
                "value_hawk", "safe_floor", "reacher", "upside_chaser", "chalk")
    for season in (2017, 2020, 2022, 2024):
        names = tuple(p.name for p in P.make_room(P.REALISTIC_ROOM, n_opponents=10,
                                                  profile=profile, season=season))
        assert names == pre_1618, f"{season} did not reproduce the pre-16.18 room"
    live = tuple(p.name for p in P.make_room(P.REALISTIC_ROOM, n_opponents=10,
                                             profile=profile, season=profile.season))
    assert "fitted_manager" in live
    # ...and the control that proves the gate can fire at all: without a season it stays seated.
    unstated = tuple(p.name for p in P.make_room(P.REALISTIC_ROOM, n_opponents=10,
                                                 profile=profile))
    assert "fitted_manager" in unstated
