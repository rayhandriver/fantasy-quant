"""T15 step 0 — the mock-draft harness and the sim/corpus measurement bridge.

Offline throughout: a synthetic board and a hand-built panel, no DuckDB and no network. The point
of these tests is the *bridge* — that a simulated draft and a realized one are genuinely measured by
the same code — plus the two measures that were subtly wrong on the first attempt (``pool_rank``
and the fixed-edge harvest curve).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fantasy_quant.adp.drift_panel import PANEL_COLS
from fantasy_quant.draft import mock
from fantasy_quant.draft.opponent_model import ALL_FEATURES, OpponentModel
from fantasy_quant.draft.personalities import personalities


@pytest.fixture
def board() -> pd.DataFrame:
    """A synthetic 120-player board with a plausible positional mix and ADP 1..120."""
    rng = np.random.default_rng(0)
    pos = (["RB"] * 34 + ["WR"] * 42 + ["QB"] * 14 + ["TE"] * 14 + ["K"] * 8 + ["DST"] * 8)
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
    })


@pytest.fixture
def model() -> OpponentModel:
    """A hand-set β in the shipped feature order — no fitted artifact needed."""
    beta = {c: 0.0 for c in ALL_FEATURES}
    beta["adp_s"] = -1.7          # the live fitted value, so the fixture behaves like the real room
    beta["need"] = 0.5
    return OpponentModel(feature_cols=list(ALL_FEATURES),
                         beta=np.array([beta[c] for c in ALL_FEATURES]))


# ---------------------------------------------------------------------------------- the room
def test_full_room_has_a_personality_in_every_seat(board, model):
    """The identity seat mapping — the one line that differs from ``make_room_pick_fn``.

    Regression for the bug this harness would otherwise have: the shipped router skips
    ``your_team``, so a naive ten-seat room silently gives two teams the same personality and
    leaves one seat on the ADP autopilot default.
    """
    room = mock.full_room(("autopilot",) * 10)
    st = mock.simulate_room_draft(board, room, model, n_teams=10, rounds=5, seed=1)
    assert len(st.log) == 50
    assert {r["team"] for r in st.log} == set(range(10))

    # every seat is a *pure* autopilot, so every team's picks must be board-order best-available
    panel = mock.sim_drift_panel(st, season=2026, draft_id="d", room=room)
    ranks = mock.pool_rank(panel)
    assert ranks.max() <= 2.0, "an autopilot-only room did not draft in board order"


def test_room_size_is_checked(board, model):
    """A nine-seat room against ten teams must fail loudly, not leave a seat on the ADP default."""
    nine = mock.full_room(mock.DEFAULT_FULL_ROOM[:9], n_teams=9)
    with pytest.raises(ValueError, match="9 seats for 10 teams"):
        mock.simulate_room_draft(board, nine, model, n_teams=10, rounds=2)


def test_default_full_room_is_ten_seats():
    assert len(mock.DEFAULT_FULL_ROOM) == 10
    lib = personalities()
    assert all(n in lib for n in mock.DEFAULT_FULL_ROOM)


def test_seeded_drafts_are_reproducible_and_seeds_differ(board, model):
    room = mock.full_room(seed=3)
    a = mock.simulate_room_draft(board, room, model, rounds=6, seed=42)
    b = mock.simulate_room_draft(board, room, model, rounds=6, seed=42)
    c = mock.simulate_room_draft(board, room, model, rounds=6, seed=43)
    assert [r["player_key"] for r in a.log] == [r["player_key"] for r in b.log]
    assert [r["player_key"] for r in a.log] != [r["player_key"] for r in c.log]


# ---------------------------------------------------------------------------------- the bridge
def test_sim_panel_matches_the_corpus_panel_contract(board, model):
    """The whole design rests on this: a sim panel *is* a drift panel."""
    room = mock.full_room(seed=3)
    st = mock.simulate_room_draft(board, room, model, rounds=10, seed=7)
    panel = mock.sim_drift_panel(st, season=2026, draft_id="sim-1", room=room, seed=7)
    assert list(panel.columns) == [*PANEL_COLS, "seat_personality", "seed"]
    assert (panel["pos"].isin(["QB", "RB", "WR", "TE"])).all(), "K/DST leaked into the panel"
    assert panel["draft_slot"].between(1, 10).all()
    assert panel["seat_personality"].notna().all()


def test_drift_arithmetic_and_sign(board, model):
    """``drift > 0`` = drafted EARLIER than the board said, and centering nets to zero."""
    room = mock.full_room(seed=3)
    st = mock.simulate_room_draft(board, room, model, rounds=10, seed=7)
    p = mock.sim_drift_panel(st, season=2026, draft_id="sim-1", room=room)
    expected = p["adp"] / p["board_teams"] - p["pick_no"] / p["teams"]
    assert np.allclose(p["drift"], expected)
    assert p["drift_centered"].mean() == pytest.approx(0.0, abs=1e-9)

    # a player taken well before his ADP must show positive drift
    early = p.loc[p["drift"].idxmax()]
    assert early["adp"] / early["board_teams"] > early["pick_no"] / early["teams"]


def test_batch_panel_stacks_independent_drafts(board, model):
    room = mock.full_room(seed=3)
    panel = mock.batch_drift_panel(board, room, model, season=2026, seeds=range(4), rounds=8)
    assert panel["draft_id"].nunique() == 4
    assert set(panel["seed"]) == {0, 1, 2, 3}
    # centering is per draft, so each draft nets to zero on its own
    for _, g in panel.groupby("draft_id"):
        assert g["drift_centered"].mean() == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------------- measurement
def _panel(rows: list[dict]) -> pd.DataFrame:
    """A hand-built panel in the corpus's frame — used to pin the measures by construction."""
    df = pd.DataFrame(rows)
    df["teams"] = df.get("teams", 10)
    df["season"] = df.get("season", 2026)   # PANEL_COLS always carries it; seat_table groups on it
    df["board_teams"] = 10
    df["slot_rounds"] = df["pick_no"] / df["teams"]
    df["adp_rounds"] = df["adp"] / df["board_teams"]
    df["drift"] = df["adp_rounds"] - df["slot_rounds"]
    df["drift_centered"] = df["drift"] - df.groupby("draft_id")["drift"].transform("mean")
    df["round"] = ((df["pick_no"] - 1) // df["teams"] + 1).astype(int)
    return df


def test_pool_rank_counts_players_passed_over():
    """1 = took the best available; N = passed over N-1 better-ADP players still on the board."""
    p = _panel([
        # pick 1 takes ADP 1 (best available -> rank 1)
        {"draft_id": "d", "pick_no": 1, "draft_slot": 1, "adp": 1.0},
        # pick 2 takes ADP 5, passing over ADP 2 and 3 which go later -> rank 3
        {"draft_id": "d", "pick_no": 2, "draft_slot": 2, "adp": 5.0},
        {"draft_id": "d", "pick_no": 3, "draft_slot": 3, "adp": 2.0},
        {"draft_id": "d", "pick_no": 4, "draft_slot": 4, "adp": 3.0},
    ])
    assert list(mock.pool_rank(p)) == [1.0, 3.0, 1.0, 1.0]


def test_pool_rank_is_not_circular_with_drift():
    """★ The reason bar #3 needs ``pool_rank``: a faithful seat in a reaching room has huge |drift|.

    Seat 1 takes the best available every time; the other seats reach wildly. Seat 1's mean |drift|
    is therefore large — an |drift|-based faithfulness measure would call it the *least* faithful
    seat in the room, which is exactly backwards.
    """
    rows = []
    for r in range(5):                      # 10 seats x 5 rounds
        for slot in range(1, 11):
            pick = 10 * r + slot
            # seat 1 takes the best available every round; the other nine reach a steady 12 picks,
            # which leaves the players they skipped on the board for seat 1 to collect next round
            adp = float(r + 1) if slot == 1 else float(pick + 12)
            rows.append({"draft_id": "d", "pick_no": pick, "draft_slot": slot, "adp": adp})
    seats = mock.seat_table(_panel(rows)).set_index("draft_slot")
    faithful, reacher = seats.loc[1], seats.loc[2]

    # behaviour: seat 1 never passed on anyone, the reachers did
    assert faithful["mean_pool_rank"] == pytest.approx(1.0)
    assert reacher["mean_pool_rank"] > 1.0
    # outcome: seat 1 harvested, the reacher paid
    assert faithful["harvest_picks"] > 0 > reacher["harvest_picks"]
    # ★ the trap — the faithful seat's |drift| is the LARGER of the two, because the fall it
    #   collects accumulates round over round while a reach stays a fixed size
    assert faithful["mean_abs_drift_picks"] > reacher["mean_abs_drift_picks"]


def test_harvest_sign_names_the_value_taken():
    """``harvest_picks`` is positive for the seat that takes players later than their ADP."""
    p = _panel([
        {"draft_id": "d", "pick_no": 1, "draft_slot": 1, "adp": 30.0},   # reached: drift +2.9 rd
        {"draft_id": "d", "pick_no": 2, "draft_slot": 2, "adp": 1.0},    # harvested a faller
    ])
    seats = mock.seat_table(p).set_index("draft_slot")
    assert seats.loc[1, "mean_drift_picks"] > 0 and seats.loc[1, "harvest_picks"] < 0
    assert seats.loc[2, "mean_drift_picks"] < 0 and seats.loc[2, "harvest_picks"] > 0


def test_reach_profile_units_are_ten_team_picks():
    """A player one full round early is 10 picks of drift, not 1."""
    p = _panel([{"draft_id": "d", "pick_no": 1, "draft_slot": 1, "adp": 11.0}])
    prof = mock.reach_profile(p)
    assert prof.loc[0, "mean_abs"] == pytest.approx(10.0)
    assert prof.loc[0, "mean_signed"] == pytest.approx(10.0)


def test_profile_trend_separates_a_rising_curve_from_a_flat_one():
    rising = pd.DataFrame({"round": range(1, 8), "mean_abs": [3, 5, 7, 10, 13, 18, 27]})
    flat = pd.DataFrame({"round": range(1, 8), "mean_abs": [12, 13, 12, 14, 13, 12, 13]})
    assert mock.profile_trend(rising) == pytest.approx(1.0)
    assert abs(mock.profile_trend(flat)) < 0.6


def test_harvest_curve_uses_fixed_edges_not_quantiles():
    """★ Two populations with different faithfulness must land in the same labelled bins.

    The quantile form of bar #3 compares "the top 20 % of each", which puts a ``pool_rank`` 1.16
    robot and a ``pool_rank`` 4.3 human on the same row and calls the gap a defect.
    """
    chalk = _panel([{"draft_id": f"c{i}", "pick_no": j, "draft_slot": 1, "adp": float(j)}
                    for i in range(3) for j in range(1, 12)])
    curves = mock.harvest_curve(chalk, min_picks=5)
    assert list(curves.columns) == ["pool_rank_bin", "n_seats", "mean_pool_rank",
                                    "harvest_picks", "harvest_sd"]
    # a perfectly faithful population occupies the first fixed bin and no other
    assert len(curves) == 1
    assert curves.loc[0, "mean_pool_rank"] == pytest.approx(1.0)


def test_faithfulness_summary_reports_the_moderate_band():
    p = _panel([{"draft_id": "d", "pick_no": j, "draft_slot": 1, "adp": float(j)}
                for j in range(1, 12)])
    s = mock.faithfulness_summary(p, min_picks=5)
    assert s["n_seats"] == 1
    assert s["chalk_share"] == pytest.approx(1.0)
    assert s["moderate_share"] == pytest.approx(0.0)


def test_elite_fall_profile_is_in_ten_team_picks():
    p = _panel([
        {"draft_id": "d", "pick_no": 5, "draft_slot": 5, "adp": 4.0},
        {"draft_id": "d", "pick_no": 25, "draft_slot": 5, "adp": 9.0},   # a top-12 falling to 25
        {"draft_id": "d", "pick_no": 30, "draft_slot": 6, "adp": 40.0},  # not elite, excluded
    ])
    e = mock.elite_fall_profile(p, adp_cut=12.0)
    assert e["n"] == 2
    assert e["mean_slot"] == pytest.approx(15.0)
    assert e["share_past_10"] == pytest.approx(0.5)


def test_measures_are_empty_safe():
    empty = pd.DataFrame(columns=PANEL_COLS)
    assert mock.reach_profile(empty).empty
    assert mock.elite_fall_profile(empty) == {"n": 0}
    assert mock.seat_table(empty).empty
    assert mock.harvest_curve(empty).empty
    assert mock.faithfulness_summary(empty) == {"n_seats": 0}
    assert mock.faithful_harvest(empty) == {"n_seats": 0}


# ------------------------------------------------------------ T15 step 2: the gates themselves
def _panel(rows: list[dict]) -> pd.DataFrame:
    """A minimal drift panel: `rows` give (draft_id, draft_slot, pick_no, adp)."""
    df = pd.DataFrame(rows)
    df["season"] = 2024
    df["teams"] = df.get("teams", 10)
    df["scoring"] = "ppr"
    df["start_ts"] = pd.NaT
    df["days_to_board"] = 0.0
    df["round"] = ((df["pick_no"] - 1) // 10 + 1).astype(int)
    df["gsis_id"] = [f"00-{i:07d}" for i in range(len(df))]
    df["name"] = df["gsis_id"]
    df["pos"] = "RB"
    df["board_teams"] = 10
    df["board_source"] = "ffc"
    df["adp_stdev"] = 1.0
    df["slot_rounds"] = df["pick_no"] / df["teams"]
    df["adp_rounds"] = df["adp"] / df["board_teams"]
    df["drift"] = df["adp_rounds"] - df["slot_rounds"]
    df["drift_centered"] = df["drift"] - df.groupby("draft_id")["drift"].transform("mean")
    return df


def test_gate_elite_fall_fails_the_shipped_defect_and_passes_a_realistic_room():
    """The gate must fail the thing a human failed by eye, and pass a corpus-shaped room."""
    # every top-12 player lands near his ADP -> realistic
    good = _panel([{"draft_id": f"d{d}", "draft_slot": 1, "pick_no": i, "adp": float(i)}
                   for d in range(20) for i in range(1, 13)])
    assert mock.gate_elite_fall(good)["pass"]
    # the shipped defect: elites routinely slide 20+ picks past where they belong
    bad = _panel([{"draft_id": f"d{d}", "draft_slot": 1, "pick_no": i + 20, "adp": float(i)}
                  for d in range(20) for i in range(1, 13)])
    g = mock.gate_elite_fall(bad)
    assert not g["pass"] and g["p95_slot"] > mock.ELITE_P95_MAX


def test_gate_autopilot_surplus_is_one_sided_and_matched_on_fixed_bins():
    """Harvesting *less* than a human ADP-follower is not the defect; harvesting more is.

    Also pins the bin matching: the two populations are compared row by row on absolute
    `pool_rank` edges, so a sim whose seats are uniformly chalkier cannot pass by being compared
    against its own quantile.
    """
    rng = np.random.default_rng(0)

    def population(harvest_by_seat, n_draft=40):
        rows = []
        for d in range(n_draft):
            for s, h in enumerate(harvest_by_seat):
                # a seat with harvest h took players h picks BELOW their adp, on average
                for k in range(10):
                    pick = 1 + s * 10 + k
                    rows.append({"draft_id": f"d{d}", "draft_slot": s + 1, "pick_no": pick,
                                 "adp": pick - h + float(rng.normal(0, 0.4))})
        return _panel(rows)

    base = [12.0, 6.0, 0.0, -6.0]
    corpus = population(base)
    assert mock.gate_autopilot_surplus(population(base), corpus)["pass"]
    # a room that hands every seat ~3 corpus-sds more surplus than a human room does: the defect
    greedy = population([h + 20.0 for h in base])
    g = mock.gate_autopilot_surplus(greedy, corpus)
    assert not g["pass"] and g["worst_excess_sds"] > 2.0
    # ... and the mirror image is NOT a failure: a room whose seats harvest less than humans do is
    # not what T15 is about, so the gate must stay one-sided or it fails good rooms for free.
    stingy = population([h - 20.0 for h in base])
    assert mock.gate_autopilot_surplus(stingy, corpus)["pass"]


def test_profile_distance_is_symmetric_in_log_space():
    """2x too wide must cost exactly what 2x too narrow costs, or the metric prefers one failure."""
    corpus = _panel([{"draft_id": f"c{d}", "draft_slot": 1, "pick_no": i,
                      "adp": i + (4.0 if i % 2 else -4.0)} for d in range(30)
                     for i in range(1, 151)])
    wide = _panel([{"draft_id": f"w{d}", "draft_slot": 1, "pick_no": i,
                    "adp": i + (8.0 if i % 2 else -8.0)} for d in range(30)
                   for i in range(1, 151)])
    narrow = _panel([{"draft_id": f"n{d}", "draft_slot": 1, "pick_no": i,
                      "adp": i + (2.0 if i % 2 else -2.0)} for d in range(30)
                     for i in range(1, 151)])
    assert mock.profile_distance(wide, corpus) == pytest.approx(
        mock.profile_distance(narrow, corpus), rel=1e-6)
    assert mock.profile_distance(corpus, corpus) == pytest.approx(0.0, abs=1e-9)


# ------------------------------------------- T23/T24/T25: the two measurements 2026-07-28 lacked
def test_landing_profile_sees_the_defect_the_mean_absolute_bar_passes():
    """★ The whole argument for the signed companion, as an executable claim.

    Two rooms with **identical** mean |drift| in round 1: one is symmetric noise, the other drops
    every consensus elite and reaches for the players behind them. The |drift| bar cannot tell them
    apart — a reach and a fall have the same absolute value — and the landing profile can.
    """
    def room(swaps, tag):
        """Ten picks; ``swaps`` exchange two players' landing spots, so every room has the same
        multiset of |drift| — four picks displaced by exactly 4 — and they differ only in *who*."""
        adp = {i: float(i) for i in range(1, 11)}
        for a, b in swaps:
            adp[a], adp[b] = adp[b], adp[a]
        return _panel([{"draft_id": f"{tag}{d}", "draft_slot": i, "pick_no": i, "adp": adp[i]}
                       for d in range(30) for i in range(1, 11)])

    # symmetric: two mid-board pairs trade places, the elite land on their own picks
    sym = room([(3, 7), (4, 8)], "s")
    # one-sided: the consensus top two are the displaced ones
    one_sided = room([(1, 5), (2, 6)], "o")

    # the bar that passes: mean |drift| is identical by construction
    assert (mock.reach_profile(sym).loc[0, "mean_abs"]
            == pytest.approx(mock.reach_profile(one_sided).loc[0, "mean_abs"]))
    # the measurement that separates them: where the top tier actually landed
    top = mock.LANDING_BANDS[0]
    assert (mock.landing_profile(one_sided, bands=[top]).loc[0, "past_4"]
            > mock.landing_profile(sym, bands=[top]).loc[0, "past_4"])
    assert mock.gate_elite_landing(sym, sym)["fall_pass"]
    assert not mock.gate_elite_landing(one_sided, sym)["fall_pass"]


def test_round1_split_is_measured_at_the_same_point_in_the_round():
    """A 12-team room's pick 6 is the same *place* in round 1 as a 10-team room's pick 5.

    Splitting on a raw pick number silently compares the first half of one round to the first 42 %
    of another, which is how a corpus of 8-14-team rooms gets mis-measured against a 10-team sim.
    """
    ten = _panel([{"draft_id": "a", "draft_slot": i, "pick_no": i, "adp": float(i) + 5.0,
                   "teams": 10} for i in range(1, 11)])
    twelve = _panel([{"draft_id": "b", "draft_slot": i, "pick_no": i, "adp": float(i) + 6.0,
                      "teams": 12} for i in range(1, 13)])
    twelve["round"] = 1
    assert list(mock.round1_split(ten)["n"]) == [5, 5]
    assert list(mock.round1_split(twelve)["n"]) == [6, 6]


def test_roster_legality_is_stated_over_the_whole_lineup():
    """T23's bar: every dedicated slot, not just the ones a ticket was written about.

    ⚠ **The FLEX absorbs a surplus, not a deficit.** A seat holding one RB and three WRs cannot
    field ``RB/RB`` — nothing substitutes *into* a dedicated slot — so it is illegal here even
    though T23's prose reads the other way. That is why the fix is "mandatory need = the whole
    ``base_demand``" rather than "add TE to the exemption list": the exemption was never sound for
    RB/WR either, it was merely never binding, because RB/WR demand is always met early.

    Also pins the canonicaliser: ``panel._canon_pos`` maps K/DST to NaN, so using it here reports
    every seat as missing a kicker it did draft — a failed join that looks exactly like a missing
    entity, which is the one mistake a legality bar cannot survive.
    """
    def seat(team, positions):
        return [{"draft_id": "d", "team": team, "pos": p, "seat_personality": f"p{team}"}
                for p in positions]

    full = ["QB", "RB", "RB", "WR", "WR", "TE", "K", "DST"]
    log = pd.DataFrame([*seat(0, full),
                        *seat(1, [p for p in full if p != "TE"] + ["WR"]),   # no TE  -> illegal
                        *seat(2, [p for p in full if p != "RB"] + ["WR"]),   # one RB -> illegal
                        *seat(3, [*full, "RB", "WR"])])                      # surplus -> legal
    out = mock.roster_legality(log)
    assert out["n_seats"] == 4 and out["n_illegal"] == 2
    assert "share_avoidable" not in out            # no supply given -> no avoidability claim
    assert out["by_position"]["TE"] == pytest.approx(1 / 4)
    assert out["by_position"]["RB"] == pytest.approx(1 / 4)
    assert out["by_position"]["K"] == 0.0 and out["by_position"]["DST"] == 0.0
    assert out["by_personality"]["p1"] == 1.0 and out["by_personality"]["p3"] == 0.0


def test_roster_legality_separates_a_defect_from_a_board_that_cannot_supply_one():
    """★ 2022's board carries **5** kickers for a ten-seat room. Half the seats cannot finish with
    one and no pick policy can change that, so the raw share is not a defect count.

    Measured over 2017–2024 + 2026 the K/DST shortfalls (7.8 % / 4.4 %) match the supply shortfall
    to three decimals — which is how we know they are supply and not the deadline filter.
    """
    rows = []
    for team in range(10):
        pos = ["QB", "RB", "RB", "WR", "WR", "TE", "DST"] + (["K"] if team < 5 else ["WR"])
        rows += [{"season": 2022, "draft_id": "d", "team": team, "pos": p} for p in pos]
    log = pd.DataFrame(rows)

    thin = mock.roster_legality(log, supply={2022: {"K": 5, "DST": 10, "QB": 20, "RB": 40,
                                                    "WR": 40, "TE": 15}})
    assert thin["share_illegal"] == pytest.approx(0.5)         # five seats have no kicker
    assert thin["avoidable_by_position"]["K"] == pytest.approx(0.0)     # ...none of it fixable
    assert thin["share_avoidable"] == pytest.approx(0.0)
    # the same rosters against a board that had kickers to spare *is* a defect
    rich = mock.roster_legality(log, supply={2022: {"K": 30, "DST": 10, "QB": 20, "RB": 40,
                                                    "WR": 40, "TE": 15}})
    assert rich["avoidable_by_position"]["K"] == pytest.approx(0.5)


def test_batch_drafts_returns_a_log_the_panel_cannot_replace(board, model):
    """The panel is offense-only, so K/DST live only in the log — that is why T23 needed both."""
    room = mock.full_room(seed=3)
    panel, log = mock.batch_drafts(board, room, model, season=2026, seeds=range(3), rounds=8)
    same = mock.batch_drift_panel(board, room, model, season=2026, seeds=range(3), rounds=8)
    pd.testing.assert_frame_equal(panel, same)
    assert set(log["draft_id"]) == set(panel["draft_id"])
    assert log["seat_personality"].notna().all()
    assert len(log) == 3 * 10 * 8                      # every pick, every position
    assert not set(panel["pos"]) - set(mock.OFFENSE)   # the panel dropped the rest


def test_personality_buckets_split_the_late_rounds_out():
    """T25's reporting rule: R14-15 is *when a seat took its kicker*, not how it drafts."""
    rows = [{"draft_id": "d", "draft_slot": s, "pick_no": 10 * (r - 1) + s, "adp": float(s)}
            for r in range(1, 16) for s in range(1, 11)]
    p = _panel(rows)
    p["seat_personality"] = ["chalk" if s % 2 else "reacher"
                             for s in p["draft_slot"]]
    out = mock.personality_buckets(p)
    assert list(out.index) == ["chalk", "reacher"] or list(out.index) == ["reacher", "chalk"]
    assert {"R1-3", "R14-15", "overall"} <= set(out.columns)


def test_narrative_shock_refuses_a_model_it_was_not_calibrated_against():
    """T15: the 16.9 intercept is a size in UTILITY units, so it dies when the ADP transform moves.

    Structural rather than documented, because the failure is silent — a wrongly-sized shock still
    produces a legal draft and a plausible room, which is how the last three instances of *a
    coefficient is not transportable without its controls* reached production.
    """
    from fantasy_quant.adp.narrative import NarrativeShock
    from fantasy_quant.draft.opponent_model import AdpSpec, BandSpec

    pre_t15 = {"adp_spec": AdpSpec().to_dict(), "band": BandSpec().to_dict()}
    shock = NarrativeShock(calibrated_under=pre_t15)
    old = OpponentModel(list(ALL_FEATURES), beta=np.zeros(len(ALL_FEATURES)))
    shock.assert_transportable(old)                      # same contract -> fine

    new = OpponentModel(list(ALL_FEATURES), beta=np.zeros(len(ALL_FEATURES)),
                        adp_spec=AdpSpec("power", exponent=0.15),
                        band=BandSpec("widening", k0=40, growth=5, k_max=160))
    with pytest.raises(ValueError, match="not transportable|calibrated under"):
        shock.assert_transportable(new)
    # an explicitly uncalibrated shock is a placeholder, not a claim — it must not raise
    NarrativeShock().assert_transportable(new)
