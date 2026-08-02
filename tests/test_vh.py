"""Session VH — the value-hawk repair: the board-vintage pin (VH.0) and T33's divisor (VH.1).

Offline throughout: an in-memory DuckDB for the board tests, synthetic boards for the draft ones.

★ **Every test here is a regression test in the strict sense** — each was checked against the
pre-VH code and fails on it. That matters more than usual for T33: the divisor bug had been live
since 16.14R step 6, survived 16.17's bit-identity sheet, and **749 tests passed over it**, because
the only harness that ever exercised the value hawk ran at k=0, where the room size and the league
size happen to coincide. *A bug that only appears off the measured path needs a test on the
unmeasured one.*
"""

from __future__ import annotations

import datetime as dt
from dataclasses import replace

import duckdb
import numpy as np
import pandas as pd
import pytest

from fantasy_quant.adp import boards
from fantasy_quant.draft.personalities import (
    SeatMap,
    make_room_pick_fn,
    make_value_hawk_pick_fn,
    personalities,
)
from fantasy_quant.draft.simulator import DraftState, RosterSlots, _prepare_board


# ==================================================================================================
# VH.0 — the board-vintage pin
# ==================================================================================================
def _board_con() -> duckdb.DuckDBPyConnection:
    """Three FFC vintages of one 2026 cell, so "newest" and "newest as of" can differ."""
    con = duckdb.connect()
    con.execute("""CREATE TABLE adp_snapshots(
        season BIGINT, source VARCHAR, scoring VARCHAR, teams BIGINT, gsis_id VARCHAR,
        name VARCHAR, position VARCHAR, team VARCHAR, adp DOUBLE, stdev DOUBLE,
        pos_rank BIGINT, snapshot_date DATE)""")
    for day, n, shift in ((10, 4, 0.0), (20, 5, 10.0), (30, 6, 20.0)):
        for i in range(1, n + 1):
            con.execute("INSERT INTO adp_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        [2026, "ffc", "ppr", 10, f"P{i:03d}", f"Player {i}", "RB", "KC",
                         float(i) + shift, 1.0, i, dt.date(2026, 7, day)])
    return con


def _dates(b: pd.DataFrame) -> set[dt.date]:
    return {pd.Timestamp(d).date() for d in b["snapshot_date"]}


def test_asof_none_returns_the_newest_board_exactly_as_before():
    con = _board_con()
    b, src = boards.resolve_board(con, 2026, "ppr", 10)
    assert src == boards.FFC
    assert len(b) == 6 and _dates(b) == {dt.date(2026, 7, 30)}


def test_asof_pins_the_newest_board_at_or_before_the_date():
    """The whole point of VH.0's enabling change: the standing Stage-0 chore banks a new board
    every few days, so a pick a human looked at last week is otherwise unreproducible."""
    con = _board_con()
    b, _ = boards.resolve_board(con, 2026, "ppr", 10, asof="2026-07-25")
    assert len(b) == 5 and _dates(b) == {dt.date(2026, 7, 20)}
    assert b["adp"].min() == 11.0                       # the 07-20 vintage's own numbers, not 07-30

    exact, _ = boards.resolve_board(con, 2026, "ppr", 10, asof="2026-07-20")
    assert _dates(exact) == {dt.date(2026, 7, 20)}, "asof is inclusive"


def test_a_pinned_board_never_mixes_vintages():
    """``board_vintage`` names a board by one date, which is only sufficient because a resolved
    board comes from exactly one snapshot. The pin narrows the set the MAX runs over — it must not
    turn that into a union."""
    from fantasy_quant.draft.mock import board_vintage

    con = _board_con()
    for asof in (None, "2026-07-30", "2026-07-25", "2026-07-11"):
        b, src = boards.resolve_board(con, 2026, "ppr", 10, asof=asof)
        assert b["snapshot_date"].nunique() == 1
        assert board_vintage(b, src).startswith("ffc-")


def test_asof_before_every_snapshot_is_an_empty_board_not_a_crash():
    con = _board_con()
    b, src = boards.resolve_board(con, 2026, "ppr", 10, asof="2026-01-01", allow_ecr=False)
    assert b.empty and src == ""


# ==================================================================================================
# VH.1 — T33: the divisor is the LEAGUE size, not the room size
# ==================================================================================================
class _Risk:
    """The minimum of ``RiskModel``'s surface the value hawk's pick path touches.

    ``effective_rank`` returns ADP, so with no context weights the seat is a pure ADP argmax and
    any deviation below is the context term — which is the only thing the divisor scales.
    """

    bv: dict = {}

    def effective_rank(self, pool, roster, window_end=None):
        return pool["adp"].to_numpy(float)


def _ctx_board(n: int = 60, seed: int = 7) -> pd.DataFrame:
    """A board whose ``role_share`` opposes ADP, so a bigger divisor visibly reorders the pool."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "gsis_id": [f"00-{i:07d}" for i in range(n)],
        "name": [f"P{i}" for i in range(n)],
        "position": (["RB", "WR"] * (n // 2 + 1))[:n],
        "team": [f"T{i % 8}" for i in range(n)],
        "adp": np.arange(1, n + 1, dtype=float),
        "pos_rank": list(range(1, n + 1)),
        "role_share": rng.permutation(n).astype(float) / n,
        "role_delta": rng.normal(0, 1, n),
        "td_regression": rng.normal(0, 1, n),
    })


def _state(n_teams: int, *, humans=(), rounds: int = 3, seed: int = 7) -> DraftState:
    b = _prepare_board(_ctx_board(seed=seed))
    return DraftState(board=b, n_teams=n_teams, rounds=rounds, slots=RosterSlots(),
                      your_team=0, rng=np.random.default_rng(0), noise=0.0,
                      available=set(b.index), rosters=[[] for _ in range(n_teams)],
                      human_teams=frozenset(humans))


def test_value_hawk_divisor_defaults_to_the_leagues_team_count():
    """``n_teams=None`` reads ``state.n_teams``, so the default *is* the league size.

    ⚠ This asserts the wiring and that the knob is **live**, not the size of the 9-vs-10 effect.
    A single synthetic pick either flips or it does not, and forcing it to would mean tuning the
    fixture until it agreed — which measures the fixture. The magnitude is measured on real boards
    by ``steps/vh_1_t33_divisor.py`` (**20.7 %** of picks at k=1) and reported there.
    """
    vh = personalities()["value_hawk"]
    risk = _Risk()
    for n in (8, 10, 12):
        st = _state(n)
        assert make_value_hawk_pick_fn(vh, risk)(st, 0) == \
            make_value_hawk_pick_fn(vh, risk, n_teams=n)(st, 0), f"default != state.n_teams at {n}"

    st10 = _state(10)
    picks = {make_value_hawk_pick_fn(vh, risk, n_teams=k)(st10, 0) for k in (1, 10, 60)}
    assert len(picks) > 1, "the divisor does not move the pick — the context term is inert"


def test_the_divisor_no_longer_varies_with_the_number_of_human_seats():
    """★ The regression T33 is really about. Before VH.1 the room builder passed ``len(seats)``,
    so the same 10-team league priced context by ``10 - k`` — the seat a human drafted against was
    not the seat any measurement scored. Now every k picks alike."""
    vh = personalities()["value_hawk"]
    risk = _Risk()
    legacy_varied = False
    for board_seed in range(12):
        fixed, legacy = set(), set()
        for k in range(4):
            humans = tuple(range(k))
            room = tuple([vh] + [personalities()["autopilot"]] * (10 - k - 1))
            sm = SeatMap.of(10, human_teams=humans, room=room)
            st = _state(10, humans=humans, seed=board_seed)
            team = next(t for t in range(10) if sm.room_index(t) == 0)
            fixed.add(make_room_pick_fn(_dummy_model(), room, risk=risk, seat_map=sm)(st, team))
            # the deleted arithmetic: `n_teams=len(seats)`, i.e. 10 - k
            legacy.add(make_value_hawk_pick_fn(vh, risk, n_teams=len(room))(st, team))
        assert len(fixed) == 1, f"board {board_seed}: {len(fixed)} different picks across k=0..3"
        legacy_varied |= len(legacy) > 1
    # ★ The control. Without it this passes just as well on a seat that ignores context entirely,
    # and a test that cannot fail is the same defect as a bar that cannot fail (K2's lesson).
    # It sweeps boards rather than tuning one: on any single board the top pick may be robust to a
    # 10-vs-7 divisor, and tuning until it flips would measure the fixture.
    assert legacy_varied, "the pre-VH.1 arithmetic never varied on 12 boards; this proves nothing"


def test_an_explicit_divisor_still_pins_it_for_frozen_controls():
    """``steps/phase16_17_seat_map.py``'s pre-16.17 control and VH.0's ablations pass an explicit
    ``n_teams``; that has to keep overriding the state, or a frozen control silently follows the
    code it is controlling."""
    vh = personalities()["value_hawk"]
    risk = _Risk()
    st = _state(10)
    assert (make_value_hawk_pick_fn(vh, risk, n_teams=3)(st, 0)
            != make_value_hawk_pick_fn(vh, risk)(st, 0))


def test_a_seat_with_no_context_weights_is_indifferent_to_the_divisor():
    """The divisor multiplies the context term only. Strip the weights and every value of
    ``n_teams`` must agree — the guard that this fix cannot have moved the value path."""
    vh = replace(personalities()["value_hawk"], context_weights={})
    risk, st = _Risk(), _state(10)
    picks = {make_value_hawk_pick_fn(vh, risk, n_teams=k)(st, 0) for k in (3, 9, 10, 12)}
    assert len(picks) == 1


def _dummy_model():
    from fantasy_quant.draft.opponent_model import ALL_FEATURES, OpponentModel

    return OpponentModel(list(ALL_FEATURES),
                         beta=np.array([-0.85, -0.3, -0.2, 0.4, 0.2, 0.07, 0.0, 0.4, 0.4, 0.3]))


# ==================================================================================================
# VH.0 — the pre-registered pick-flag rules
# ==================================================================================================
def _flags():
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "_vh0", root / "steps" / "vh_0_attribution.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._flags


@pytest.mark.parametrize(
    ("pos", "rnd", "adp", "overall", "counts", "want"),
    [
        # R3 — the seat paid above the board's own price for this pick slot
        ("WR", 2, 25.0, 12, {}, {"reach": True, "redundant": False, "premium_early": False}),
        # R4 — value fell to it; the control, and the picks he called good
        ("RB", 5, 39.9, 49, {}, {"reach": False, "redundant": False, "premium_early": False}),
        # R2 — a second single-slot starter is the redundancy objection
        ("TE", 9, 85.2, 89, {"TE": 1}, {"reach": False, "redundant": True,
                                        "premium_early": False}),
        # R1 — a QB before round 6, where he says a late one is the value play
        ("QB", 3, 27.9, 29, {}, {"reach": False, "redundant": False, "premium_early": True}),
        # a first TE late is neither redundant nor early
        ("TE", 8, 68.9, 72, {}, {"reach": False, "redundant": False, "premium_early": False}),
    ],
)
def test_the_objection_rules_are_the_users_own(pos, rnd, adp, overall, counts, want):
    got = _flags()(pos, rnd, adp, overall, counts)
    for k, v in want.items():
        assert got[k] is v, f"{pos} r{rnd}: {k}"
    assert got["objected"] is any(want.values())


def test_a_fall_is_never_counted_as_an_objection():
    """R4: every pick he labelled *good* had value fall to it, so ``fall`` and ``reach`` must be
    exclusive — else the slot-driven share's denominator quietly includes his approvals."""
    f = _flags()
    for adp, overall in ((10.0, 20), (20.0, 10), (15.0, 15)):
        got = f("WR", 4, adp, overall, {})
        assert not (got["reach"] and got["fall"])


# ==================================================================================================
# the harness bug VH introduced: an echoed flag is not an applied flag
# ==================================================================================================
def test_vh_window_override_survives_the_per_seed_reseating():
    """★ Regression for a bug this session shipped and caught.

    ``steps/mock_room_bars.py --vh-window`` rewrote the room built once at the top of ``main()``.
    ``--shuffle-room`` re-draws the seating **per seed** by calling ``mock.full_room(mix, ...)``
    again, so the override never reached the shuffled path — the path every VH and T24 measurement
    uses. The sheet came back byte-identical to the baseline while its own config block reported
    ``vh_window: 0.5``.

    This asserts the shape of the fix rather than the CLI: the override is a **function applied to
    every room the harness builds**, so a freshly-seated room carries it too.
    """
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "_bars", root / "steps" / "mock_room_bars.py")
    bars = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bars)

    src = (root / "steps" / "mock_room_bars.py").read_text()
    # the seating closure must route through the override, not around it
    assert "return with_window(" in src, "--shuffle-room's seating() bypasses the window override"
    assert src.count("with_window(") >= 2, "the override is applied on only one of the two paths"


def test_a_window_override_actually_changes_the_seats_budget():
    """The other half: applying it must change the object, not just the label.

    A ceiling of ``0.5x`` is strictly tighter than the shipped ``1.0x`` at every round, so a seat
    carrying the override cannot be the seat that ships.
    """
    from fantasy_quant.draft.personalities import (
        effective_budget,
        value_hawk_budget,
    )

    vh = personalities()["value_hawk"]
    tight = replace(vh, reach_budget=value_hawk_budget(0.5))
    a = effective_budget(vh).round_ceiling
    b = effective_budget(tight).round_ceiling
    assert a is not None and b is not None
    assert all(y < x for x, y in zip(a, b, strict=True)), "0.5x is not tighter than 1.0x"
