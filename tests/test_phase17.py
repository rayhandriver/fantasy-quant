"""Phase 17 — League-Format Fidelity (17.1 roster/lineup · 17.2 scoring · 17.3 settings · 17.4
keepers).

Two things are being defended here and they pull in opposite directions:

1. **Non-default formats are correct.** The multi-flex/superflex lineup solver is checked against an
   exhaustive brute force, not against the other greedy implementation — two greedies that share a
   bug agree perfectly.
2. **The default format did not move.** Phase 17 is a *config generalization*: the lockbox was spent
   on 10-team full-PPR 1-QB, and every default here must reproduce its pre-17 behaviour exactly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fantasy_quant.backtest.metrics import replacement_ranks
from fantasy_quant.backtest.scoring import (
    DEFAULT_RULESET,
    OffenseRules,
    RuleSet,
    ruleset_from_preset,
    score_offense,
)
from fantasy_quant.backtest.walkforward import optimal_lineup_points
from fantasy_quant.draft.config import Keeper, LeagueSettings
from fantasy_quant.draft.simulator import RosterSlots, simulate_draft
from fantasy_quant.simulation.season import (
    LeagueFormat,
    bracket_rounds,
    derived_byes,
    lineup_points_matrix,
)

POS = ("QB", "RB", "WR", "TE", "K", "DST")


def _brute_lineup(points, positions, slots: RosterSlots) -> float:
    """Exhaustive optimum over legal assignments, slots allowed to be **empty**.

    The ground truth for 17.1. Deliberately not greedy and deliberately not vectorized — its only
    job is to be obviously right on small rosters.
    """
    plan: list[tuple[str, ...]] = []
    for p, n in slots.base_demand().items():
        plan += [(p,)] * n
    for count, elig in slots.flex_groups():
        plan += [tuple(elig)] * count
    best = 0.0

    def rec(si: int, used: int, tot: float) -> None:
        nonlocal best
        if si == len(plan):
            best = max(best, tot)
            return
        rec(si + 1, used, tot)
        for i in range(len(points)):
            if not (used >> i) & 1 and positions[i] in plan[si]:
                rec(si + 1, used | (1 << i), tot + points[i])

    rec(0, 0, 0.0)
    return best


def _roster(rng, n=8):
    return (rng.uniform(0, 30, size=n), [POS[int(rng.integers(0, len(POS)))] for _ in range(n)])


FORMATS = {
    "default": RosterSlots(),
    "superflex": RosterSlots(superflex=1),
    "two_flex": RosterSlots(flex=2),
    "2qb_superflex": RosterSlots(qb=2, superflex=1),
    "no_k_dst_3flex": RosterSlots(k=0, dst=0, flex=3),
}


# --------------------------------------------------------------------------------------------
# 17.1 — the flex generalization
# --------------------------------------------------------------------------------------------
def test_default_flex_groups_and_starters_are_unchanged():
    """The lockbox roster: one RB/WR/TE flex, nine starters, fifteen total."""
    d = RosterSlots()
    assert d.flex_groups() == ((1, ("RB", "WR", "TE")),)
    assert (d.starters, d.total, d.total_flex()) == (9, 15, 1)
    assert d.flex_eligible() == frozenset({"RB", "WR", "TE"})


def test_superflex_adds_a_second_nested_group_ordered_narrowest_first():
    sf = RosterSlots(superflex=1)
    assert sf.flex_groups() == ((1, ("RB", "WR", "TE")), (1, ("QB", "RB", "WR", "TE")))
    assert sf.starters == 10
    assert "QB" in sf.flex_eligible()


@pytest.mark.parametrize("name", list(FORMATS))
def test_vectorized_solver_matches_brute_force(name):
    """The bar that matters: greedy-with-carry == exhaustive optimum, on every shipped format."""
    slots, rng = FORMATS[name], np.random.default_rng(7)
    for _ in range(25):
        pts, pos = _roster(rng, 8)
        got = float(np.ravel(lineup_points_matrix(np.asarray(pts)[:, None], pos, slots))[0])
        assert got == pytest.approx(_brute_lineup(pts, pos, slots), abs=1e-9)


@pytest.mark.parametrize("name", list(FORMATS))
def test_vectorized_solver_matches_the_reference_solver(name):
    """The two in-repo solvers stay in lockstep — the 1.3 regression, extended to 17.1's formats."""
    slots, rng = FORMATS[name], np.random.default_rng(11)
    for _ in range(40):
        pts, pos = _roster(rng, 12)
        vec = float(np.ravel(lineup_points_matrix(np.asarray(pts)[:, None], pos, slots))[0])
        assert vec == pytest.approx(optimal_lineup_points(pts, pos, slots), abs=1e-9)


def test_solver_is_vectorized_over_the_trailing_axes():
    """Shape contract: the roster axis drops and any trailing ``(n_sims, n_weeks)`` survives."""
    slots = RosterSlots(superflex=1)
    rng = np.random.default_rng(3)
    pts = rng.uniform(0, 30, size=(12, 5, 4))
    pos = [POS[i % len(POS)] for i in range(12)]
    out = lineup_points_matrix(pts, pos, slots)
    assert out.shape == (5, 4)
    for s in range(5):                       # each cell equals the scalar solve of that cell
        for w in range(4):
            one = float(np.ravel(lineup_points_matrix(pts[:, s, w][:, None], pos, slots))[0])
            assert out[s, w] == pytest.approx(one, abs=1e-9)


def test_non_nested_flex_eligibility_is_refused():
    """Greedy is only optimal for nested slots, so a roster it cannot solve is rejected outright
    rather than answered wrongly."""
    bad = RosterSlots(flex=1, flex_positions=("WR", "TE"),
                      superflex=1, superflex_positions=("RB", "WR"))
    with pytest.raises(ValueError, match="nested"):
        bad.assert_nested()
    RosterSlots().assert_nested()
    RosterSlots(superflex=1).assert_nested()


# --------------------------------------------------------------------------------------------
# 17.1 — format-aware replacement levels
# --------------------------------------------------------------------------------------------
def test_default_replacement_ranks_are_the_documented_baseline():
    assert replacement_ranks(RosterSlots(), 10) == {
        "QB": 10, "RB": 24, "WR": 24, "TE": 12, "K": 10, "DST": 10}


def test_superflex_doubles_the_qb_replacement_rank():
    """The headline of 17.1: a superflex slot is the *only* thing the wider group newly admits, so
    it goes to QB — QB10 (last starter) becomes QB20 (last second starter). Nothing else moves."""
    base = replacement_ranks(RosterSlots(), 10)
    sf = replacement_ranks(RosterSlots(superflex=1), 10)
    assert sf["QB"] == 20 and base["QB"] == 10
    assert {p: sf[p] for p in ("RB", "WR", "TE", "K", "DST")} == \
           {p: base[p] for p in ("RB", "WR", "TE", "K", "DST")}


def test_extra_flex_spreads_across_flex_positions_not_onto_qb():
    two = replacement_ranks(RosterSlots(flex=2), 10)
    assert two["QB"] == 10                                    # a plain flex never reaches QB
    assert two["RB"] > 24 and two["WR"] > 24 and two["TE"] > 12


# --------------------------------------------------------------------------------------------
# 17.2 — custom scoring
# --------------------------------------------------------------------------------------------
def test_full_ppr_preset_is_the_default_ruleset_object():
    """Equality here is load-bearing: ``RuleSet`` is serialized into the distribution cache key, so
    a same-scoring-different-name preset would silently split the cache and force a rebuild."""
    assert ruleset_from_preset("full_ppr") == DEFAULT_RULESET
    assert ruleset_from_preset("full_ppr").name == RuleSet().name


def test_ppr_presets_set_the_reception_rate():
    assert ruleset_from_preset("standard").offense.rec == 0.0
    assert ruleset_from_preset("half_ppr").offense.rec == 0.5
    assert ruleset_from_preset("full_ppr").offense.rec == 1.0


def test_te_premium_pays_tight_ends_only():
    df = pd.DataFrame({"position": ["TE", "WR"], "receptions": [10.0, 10.0]})
    plain = score_offense(df, DEFAULT_RULESET.offense)
    prem = score_offense(df, ruleset_from_preset("te_premium").offense)
    assert prem[0] - plain[0] == pytest.approx(5.0)        # TE: +0.5 x 10 receptions
    assert prem[1] == pytest.approx(plain[1])              # WR: untouched


def test_te_premium_without_a_position_column_falls_back_to_plain_ppr():
    """Some derived frames carry no position; the bonus is skipped rather than mis-applied."""
    df = pd.DataFrame({"receptions": [10.0]})
    assert score_offense(df, ruleset_from_preset("te_premium").offense)[0] == \
        pytest.approx(score_offense(df, DEFAULT_RULESET.offense)[0])


def test_yardage_milestone_bonus_is_a_threshold_not_a_rate():
    rules = OffenseRules(rec_yd_bonus=3.0, rec_yd_bonus_at=100.0)
    df = pd.DataFrame({"receiving_yards": [99.0, 100.0, 180.0]})
    got = score_offense(df, rules) - score_offense(df, DEFAULT_RULESET.offense)
    assert list(got) == pytest.approx([0.0, 3.0, 3.0])     # once, not per 100


def test_a_misspelled_scoring_field_raises_instead_of_scoring_zero():
    """Why 17.2 chose a bounded field set over an open ``{stat: value}`` map."""
    with pytest.raises(ValueError):
        OffenseRules(rec_typo=1.0)


# --------------------------------------------------------------------------------------------
# 17.3 — the settings contract + the bracket
# --------------------------------------------------------------------------------------------
def test_bracket_byes_and_rounds_are_derived_not_tabulated():
    assert [derived_byes(n) for n in (4, 6, 8)] == [0, 2, 0]
    assert [bracket_rounds(n) for n in (4, 6, 8)] == [2, 3, 3]


def test_eight_team_playoff_is_now_expressible():
    """A 12-team league with an 8-team field — ordinary, and impossible before 17.3."""
    fmt = LeagueFormat(n_teams=12, playoff_teams=8, playoff_weeks=(15, 16, 17),
                       first_round_byes=0)
    assert fmt.playoff_teams == 8


def test_odd_league_sizes_are_refused_with_a_reason():
    with pytest.raises(ValueError, match="even"):
        LeagueFormat(n_teams=11)


def test_default_settings_round_trip_and_are_lockbox_validated():
    s = LeagueSettings()
    s.validate()
    assert s.lockbox_validated()
    assert s.ruleset() == DEFAULT_RULESET
    assert s.roster_slots() == RosterSlots()
    assert s.league_format() == LeagueFormat()


def test_a_custom_league_round_trips_and_is_flagged_unvalidated():
    s = LeagueSettings(n_teams=12, superflex=1, scoring_preset="te_premium",
                       playoff_teams=8, rounds=16)
    s.validate()
    assert not s.lockbox_validated()          # supported, but the lockbox says nothing about it
    assert s.roster_slots().superflex == 1
    assert s.ruleset().offense.te_rec_bonus == 0.5
    assert s.league_format().playoff_teams == 8
    assert replacement_ranks(s.roster_slots(), 12)["QB"] == 24


def test_superflex_settings_raise_the_qb_roster_cap():
    """A format you can configure but not legally draft would be worse than refusing it."""
    assert LeagueSettings(superflex=1).roster_slots().pos_caps["QB"] >= 3


@pytest.mark.parametrize("kwargs,match", [
    (dict(n_teams=11), "even"),
    (dict(playoff_teams=5), "playoff_teams"),
    (dict(scoring_preset="nope"), "preset"),
    (dict(scoring_overrides={"rec_typo": 1.0}), "scoring overrides"),
    (dict(rounds=3), "roster size"),
    (dict(draft_type="carousel"), "draft_type"),
    (dict(keepers=(Keeper("x", team=1, round=99),)), "round"),
    (dict(keepers=(Keeper("x", team=99, round=1),)), "team"),
])
def test_invalid_settings_are_rejected_with_a_message(kwargs, match):
    with pytest.raises(ValueError, match=match):
        LeagueSettings(**kwargs).validate()


# --------------------------------------------------------------------------------------------
# 17.4 — keepers
# --------------------------------------------------------------------------------------------
def _board(n=200):
    return pd.DataFrame({
        "player_name": [f"P{i}" for i in range(n)],
        "position": [POS[i % len(POS)] for i in range(n)],
        "adp": np.arange(1, n + 1, dtype=float),
    })


def test_keepers_leave_the_pool_and_cost_their_owner_a_pick():
    keeps = (Keeper("P0", team=1, round=1), Keeper("P5", team=1, round=2),
             Keeper("P3", team=4, round=1))
    st = simulate_draft(_board(), n_teams=10, rounds=15, seed=1, keepers=keeps)
    drafted = [e for e in st.log if not e.get("keeper")]
    assert len(drafted) == 150 - 3                     # three picks forfeited, not free
    assert not {"P0", "P5", "P3"} & {e["player_name"] for e in drafted}
    assert all(len(r) == 15 for r in st.rosters)       # keepers occupy the slots they cost


def test_keepers_shift_the_board_up_for_everyone_else():
    """No separate 'ADP adjustment': removing supply *is* the re-inflation. With the top three
    players kept, the first ordinary pick is a player who would not have gone first."""
    plain = simulate_draft(_board(), n_teams=10, rounds=15, seed=1)
    keeps = tuple(Keeper(f"P{i}", team=i + 1, round=1) for i in range(3))
    kept = simulate_draft(_board(), n_teams=10, rounds=15, seed=1, keepers=keeps)
    first_plain = next(e for e in plain.log if not e.get("keeper"))["player_name"]
    first_kept = next(e for e in kept.log if not e.get("keeper"))["player_name"]
    assert first_plain in {"P0", "P1", "P2"}
    assert first_kept not in {"P0", "P1", "P2"}


def test_a_keeper_not_on_the_board_still_costs_the_pick():
    """A stale board must not make an ordinary case fatal — but the forfeit is the league's rule,
    not the board's, so it applies either way."""
    st = simulate_draft(_board(), n_teams=10, rounds=15, seed=1,
                        keepers=(Keeper("NOT_ON_BOARD", team=2, round=3),))
    assert len([e for e in st.log if not e.get("keeper")]) == 149


def test_no_keepers_is_bit_identical_to_the_pre_17_path():
    a = simulate_draft(_board(), n_teams=10, rounds=15, seed=5)
    b = simulate_draft(_board(), n_teams=10, rounds=15, seed=5, keepers=())
    assert [e["player_name"] for e in a.log] == [e["player_name"] for e in b.log]
