"""Unit tests for Phase 1.2 — the draft simulator (no DB/network; synthetic board)."""

from __future__ import annotations

import pandas as pd
import pytest

from fantasy_quant.draft.simulator import (
    RosterSlots,
    canon_pos,
    simulate_draft,
)


def _synthetic_board(n_per_pos: int = 40) -> pd.DataFrame:
    """A clean ADP board with plenty of every position (no supply constraints)."""
    rows = []
    adp = 1.0
    # interleave so ADP order mixes positions realistically
    for i in range(n_per_pos):
        for pos in ("RB", "WR", "QB", "TE", "K", "DEF"):
            rows.append({"name": f"{pos}{i}", "position": pos, "adp": adp,
                         "pos_rank": i + 1, "gsis_id": f"id_{pos}_{i}"})
            adp += 1.0
    return pd.DataFrame(rows)


def test_canon_pos_maps_ffc_positions():
    assert canon_pos("PK") == "K"
    assert canon_pos("DEF") == "DST"
    assert canon_pos("wr") == "WR"
    assert canon_pos("LS") is None


def test_snake_order_and_full_draft():
    res = simulate_draft(_synthetic_board(), n_teams=10, rounds=15, seed=1)
    log = res.pick_log()
    assert len(log) == 150
    assert list(log[log["round"] == 1]["team"]) == list(range(10))
    assert list(log[log["round"] == 2]["team"]) == list(range(9, -1, -1))
    assert list(log[log["round"] == 3]["team"]) == list(range(10))
    # every team ends with a full roster; no player drafted twice
    assert all(len(r) == 15 for r in res.rosters)
    assert log["player_key"].is_unique


def test_position_caps_respected_with_ample_supply():
    # 70/pos > max cap-demand (10 teams x 6) so no position is exhausted -> soft caps hold hard.
    slots = RosterSlots()
    res = simulate_draft(_synthetic_board(n_per_pos=70), n_teams=10, rounds=15, slots=slots, seed=2)
    for team in range(10):
        counts = res.roster(team)["pos"].value_counts().to_dict()
        for pos, cap in slots.pos_caps.items():
            assert counts.get(pos, 0) <= cap, f"team {team} {pos} over cap"


def test_caps_are_soft_when_supply_exhausted():
    # only RB/WR available, capped at 6 each (12 < 15 roster) -> teams MUST exceed a cap to fill.
    b = _synthetic_board(n_per_pos=80)
    b = b[b["position"].isin(["RB", "WR"])].reset_index(drop=True)
    res = simulate_draft(b, n_teams=10, rounds=15, seed=4)
    assert len(res.pick_log()) == 150  # completes despite caps
    over = max(res.roster(t)["pos"].value_counts().max() for t in range(10))
    assert over > 6, "expected a soft-cap overflow when only RB/WR are available"


def test_reproducible_with_seed():
    b = _synthetic_board()
    a = simulate_draft(b, seed=123).pick_log()["player_key"]
    c = simulate_draft(b, seed=123).pick_log()["player_key"]
    d = simulate_draft(b, seed=999).pick_log()["player_key"]
    assert a.equals(c)
    assert not a.equals(d)


def test_no_noise_is_pure_adp_order():
    # noise=0 + no caps -> every pick is the global best-available -> strict ADP order.
    b = _synthetic_board()
    uncapped = RosterSlots(pos_caps={p: 99 for p in ("QB", "RB", "WR", "TE", "K", "DST")})
    res = simulate_draft(b, noise=0.0, slots=uncapped, seed=0)
    picked = res.pick_log()["adp"].tolist()
    assert picked == sorted(picked), "noise=0 + uncapped should draft in strict ADP order"


def test_pluggable_your_pick_fn():
    # a custom your_pick_fn overrides ADP: always grab the best available QB for seat 0. Custom
    # policies are NOT cap-bound (caps are the opponent-realism knob), so seat 0 loads up on QBs.
    def qb_homer(state):
        avail = state.available_board()
        qbs = avail[avail["pos"] == "QB"]
        return int((qbs if not qbs.empty else avail).index[0])

    res = simulate_draft(_synthetic_board(), your_pick_fn=qb_homer, your_team=0, seed=5)
    counts = res.your_roster()["pos"].value_counts().to_dict()
    assert counts.get("QB", 0) >= 10, f"custom fn should QB-load the roster, got {counts}"


def test_undersupplied_kdst_leaves_slots_open():
    # only 2 kickers / 2 defenses for 10 teams -> at most 2 teams get each; draft still completes.
    b = _synthetic_board(n_per_pos=40)
    b = b[~((b["position"].isin(["K", "DEF"])) & (b["pos_rank"] > 2))].reset_index(drop=True)
    res = simulate_draft(b, n_teams=10, rounds=15, seed=3)
    assert len(res.pick_log()) == 150
    got_k = sum(bool(res.roster(t)["pos"].eq("K").any()) for t in range(10))
    assert got_k <= 2


def test_rejects_unavailable_pick():
    def bad(state):
        return 999999  # not on the board
    with pytest.raises(ValueError, match="unavailable pick"):
        simulate_draft(_synthetic_board(), your_pick_fn=bad, seed=0)
