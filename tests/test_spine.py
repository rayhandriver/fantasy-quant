"""Unit tests for the personalization spine — config contract, snake geometry, and the constrained
greedy pick policy (never/tilt/must). Pure: a synthetic board + value index, no DB/network."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fantasy_quant.draft.config import (
    ADAPTIVE_PARENTS,
    ARCHETYPES,
    DraftConfig,
    LeagueSetup,
    MustDraft,
    archetype_tilt,
)
from fantasy_quant.draft.optimizer import (
    _greedy_eff,
    _next_own_pick,
    _team_on_clock,
    attach_value,
    personalized_pick_fn,
    team_value,
)
from fantasy_quant.draft.simulator import (
    DRAFTABLE,
    DraftState,
    RosterSlots,
    _prepare_board,
    canon_pos,
    simulate_draft,
)

UNCAPPED = RosterSlots(pos_caps=dict.fromkeys(DRAFTABLE, 99))


def _board_and_values(n_per_pos: int = 30):
    """A synthetic ADP board + a value index whose value order == ADP order (clean baseline)."""
    rows, adp = [], 1.0
    for i in range(n_per_pos):
        for pos in ("RB", "WR", "QB", "TE", "K", "DEF"):
            rows.append({"name": f"{pos}{i}", "position": pos, "adp": adp,
                         "pos_rank": i + 1, "gsis_id": f"id_{pos}_{i}"})
            adp += 1.0
    board = pd.DataFrame(rows)
    vi = pd.DataFrame({"player_key": board["gsis_id"],
                       "pos": board["position"].map(canon_pos),
                       "base_value": 1000.0 - board["adp"]})   # higher value = lower ADP
    return board, vi


def _my_picks(cfg: DraftConfig, board, vi, noise: float = 0.0, seed: int = 0) -> pd.DataFrame:
    res = simulate_draft(attach_value(board, vi), your_pick_fn=personalized_pick_fn(cfg, noise),
                         n_teams=cfg.league.n_teams, rounds=cfg.league.rounds,
                         slots=cfg.league.slots, your_team=cfg.league.your_team,
                         noise=noise, seed=seed)
    return res.pick_log().query("is_you").reset_index(drop=True)


def _round_of(picks: pd.DataFrame, player_key: str) -> int | None:
    row = picks[picks["player_key"] == player_key]
    return int(row["round"].iloc[0]) if not row.empty else None


# --------------------------------------------------------------------------------------------
# config contract
# --------------------------------------------------------------------------------------------
def test_archetypes_registered_and_bpa_is_neutral():
    # every static archetype resolves to a numeric tilt; `adaptive` is board-aware (tested below).
    for a in ARCHETYPES:
        if a == "adaptive":
            continue
        assert isinstance(archetype_tilt(a, "RB", 1), float)
    assert all(archetype_tilt("bpa", p, r) == 0.0 for p in ("QB", "RB", "WR") for r in (1, 8))


def test_late_qb_fades_early_then_pounces():
    assert archetype_tilt("late_qb", "QB", 2) < 0     # wait early
    assert archetype_tilt("late_qb", "QB", 10) > 0    # then take value


def test_get_one_archetypes_stop_after_the_first():
    # roster-state-aware: "grab an anchor" archetypes must not keep reaching once you have one.
    assert archetype_tilt("elite_te", "TE", 1, have=0) > 0
    assert archetype_tilt("elite_te", "TE", 1, have=1) == 0.0     # already have the TE → stop
    assert archetype_tilt("hero_rb", "RB", 1, have=0) > 0         # one anchor RB
    assert archetype_tilt("hero_rb", "RB", 4, have=1) < 0         # then fade further RB
    assert archetype_tilt("late_qb", "QB", 10, have=1) == 0.0     # already have your QB


def test_config_rejects_must_never_clash():
    with pytest.raises(ValueError, match="both must_draft and never_draft"):
        DraftConfig(must_draft=[("id_RB_0", 2.0)], never_draft={"id_RB_0"})


def test_config_rejects_unknown_archetype_and_negative_lambda():
    with pytest.raises(ValueError, match="unknown archetype"):
        DraftConfig(archetype="hero_qb")
    with pytest.raises(ValueError, match="risk_lambda"):
        DraftConfig(risk_lambda=-0.1)


def test_must_draft_normalized_from_bare_key_and_tuple():
    cfg = DraftConfig(must_draft=["id_WR_1", ("id_RB_2", 3.0)])
    assert cfg.must_draft[0] == MustDraft("id_WR_1", 2.0)      # default reach budget
    assert cfg.must_draft[1] == MustDraft("id_RB_2", 3.0)


def test_benchmark_strips_every_preference():
    cfg = DraftConfig(archetype="zero_rb", must_draft=["id_RB_0"],
                      never_draft={"id_WR_0"}, tilts={"id_TE_0": 2.0})
    b = cfg.benchmark()
    assert b.archetype == "bpa" and not b.must_draft and not b.never_draft and not b.tilts
    assert b.risk_lambda == cfg.risk_lambda and b.league is cfg.league


def test_constraint_labels_and_leave_one_out():
    cfg = DraftConfig(archetype="zero_rb", must_draft=["id_RB_0"],
                      never_draft={"id_WR_0"}, tilts={"id_TE_0": 1.5})
    labels = cfg.constraint_labels()
    assert "archetype:zero_rb" in labels and "must:id_RB_0" in labels
    assert "never:id_WR_0" in labels and "tilt:id_TE_0+1.5" in labels
    dropped = cfg.without_constraint("tilt:id_TE_0+1.5")       # hyphen-safe label round-trip
    assert dropped.tilts == {} and dropped.archetype == "zero_rb"
    assert cfg.without_constraint("archetype:zero_rb").archetype == "bpa"


# --------------------------------------------------------------------------------------------
# spine step 6 — the adaptive archetype (melt a fade when the board breaks from ADP)
# --------------------------------------------------------------------------------------------
def test_adaptive_requires_a_valid_parent():
    for parent in ADAPTIVE_PARENTS:
        assert DraftConfig(archetype="adaptive", adaptive_parent=parent).adaptive_parent == parent
    with pytest.raises(ValueError, match="adaptive_parent"):
        DraftConfig(archetype="adaptive")                              # missing parent
    with pytest.raises(ValueError, match="adaptive_parent"):
        DraftConfig(archetype="adaptive", adaptive_parent="bpa")       # bpa has no fade to melt
    with pytest.raises(ValueError, match="adaptive_parent"):
        DraftConfig(archetype="adaptive", adaptive_parent="adaptive")  # can't wrap itself
    with pytest.raises(ValueError, match="only valid when archetype"):
        DraftConfig(archetype="zero_rb", adaptive_parent="hero_rb")    # parent without adaptive


def test_adaptive_matches_parent_when_board_tracks_adp():
    a = DraftConfig(archetype="adaptive", adaptive_parent="zero_rb")
    z = DraftConfig(archetype="zero_rb")
    # slide == 0 (available exactly at ADP) → the fade is fully trusted → identical to the parent
    for pos, rnd in (("RB", 3), ("WR", 2), ("RB", 8)):
        assert a.total_tilt_rounds("x", pos, rnd, 0, adp=25.0, overall_pick=25) == \
               z.total_tilt_rounds("x", pos, rnd, 0)
    # no board context at all → also degrades to the parent (the leave-one-out / benchmark path)
    assert a.total_tilt_rounds("x", "RB", 3, 0) == z.total_tilt_rounds("x", "RB", 3, 0)


def test_adaptive_melts_the_fade_as_value_diverges_from_adp():
    a = DraftConfig(archetype="adaptive", adaptive_parent="zero_rb")   # 10-team default league
    z = DraftConfig(archetype="zero_rb")
    parent_fade = z.total_tilt_rounds("x", "RB", 3, 0)                 # RB early = a strong fade
    assert parent_fade < -1.0
    # a stud who slid a full round (10 picks past ADP in a 10-team room) → fade fully melted → BPA
    assert a.total_tilt_rounds("x", "RB", 3, 0, adp=15.0, overall_pick=25) == pytest.approx(0.0)
    # equal-size divergence: an *active slide* melts faster than a *reach* (cheap ones already gone)
    slide_half = a.total_tilt_rounds("x", "RB", 3, 0, adp=20.0, overall_pick=25)   # +0.5 rd slide
    reach_half = a.total_tilt_rounds("x", "RB", 3, 0, adp=30.0, overall_pick=25)   # -0.5 rd reach
    assert parent_fade < reach_half < slide_half < 0.0


def test_adaptive_leaves_reaches_untouched():
    a = DraftConfig(archetype="adaptive", adaptive_parent="elite_te")
    e = DraftConfig(archetype="elite_te")
    # elite_te *reaches* for the scarce first TE (positive tilt): no fade to melt, slide irrelevant
    slid = a.total_tilt_rounds("x", "TE", 1, 0, adp=5.0, overall_pick=40)
    assert slid == e.total_tilt_rounds("x", "TE", 1, 0) > 0


def test_adaptive_labels_and_leave_one_out():
    cfg = DraftConfig(archetype="adaptive", adaptive_parent="zero_rb", tilts={"id_TE_0": 1.0})
    assert "archetype:adaptive(zero_rb)" in cfg.constraint_labels()
    dropped = cfg.without_constraint("archetype:adaptive(zero_rb)")
    assert dropped.archetype == "bpa" and dropped.adaptive_parent is None
    assert dropped.tilts == {"id_TE_0": 1.0}                     # only the archetype came off
    kept = cfg.without_constraint("tilt:id_TE_0+1")              # a different constraint
    assert kept.archetype == "adaptive" and kept.adaptive_parent == "zero_rb"
    assert cfg.benchmark().archetype == "bpa" and cfg.benchmark().adaptive_parent is None


def test_adaptive_reranks_a_slid_faded_stud_above_the_static_parent():
    board, vi = _board_and_values()
    b = _prepare_board(attach_value(board, vi))                  # canonical board with value + adp
    st = DraftState(board=b, n_teams=10, rounds=15, slots=UNCAPPED, your_team=0,
                    rng=np.random.default_rng(0), noise=0.0, available=set(b.index),
                    rosters=[[] for _ in range(10)], overall_pick=41)   # round 5: parent fades RB
    z = DraftConfig(league=LeagueSetup(draft_slot=1, slots=UNCAPPED), archetype="zero_rb")
    a = DraftConfig(league=LeagueSetup(draft_slot=1, slots=UNCAPPED),
                    archetype="adaptive", adaptive_parent="zero_rb")
    pool_z, eff_z = _greedy_eff(st, z, None)
    pool_a, eff_a = _greedy_eff(st, a, None)

    def eff_of(pool, eff, key):                                  # lower eff = drafted sooner
        return float(eff[pool["player_key"].tolist().index(key)])

    # id_RB_0 (ADP 1) has slid ~4 rounds to pick 41 → adaptive melts the fade → ranks him sooner
    assert eff_of(pool_a, eff_a, "id_RB_0") < eff_of(pool_z, eff_z, "id_RB_0")
    # a WR the parent *boosts* (positive tilt) is untouched by the adaptive wrapper
    assert eff_of(pool_a, eff_a, "id_WR_0") == eff_of(pool_z, eff_z, "id_WR_0")


# --------------------------------------------------------------------------------------------
# snake geometry
# --------------------------------------------------------------------------------------------
def test_team_on_clock_matches_snake():
    assert [_team_on_clock(o, 10) for o in range(1, 11)] == list(range(10))
    assert [_team_on_clock(o, 10) for o in range(11, 21)] == list(range(9, -1, -1))


def test_next_own_pick_for_end_seats():
    assert _next_own_pick(1, 0, 10, 150) == 20     # seat 0: 1 -> 20 (snake turn)
    assert _next_own_pick(10, 9, 10, 150) == 11    # seat 9: back-to-back at the turn
    assert _next_own_pick(141, 0, 10, 150) is None or _next_own_pick(141, 0, 10, 150) >= 141


# --------------------------------------------------------------------------------------------
# value attachment + team value
# --------------------------------------------------------------------------------------------
def test_attach_value_ranks_best_value_first():
    board, vi = _board_and_values()
    b = attach_value(board, vi)
    best_key = vi.sort_values("base_value", ascending=False)["player_key"].iloc[0]
    assert b.loc[b["gsis_id"] == best_key, "value"].iloc[0] == 1.0   # rank 1 = draft first


def test_team_value_sums_base_value_zero_for_unvalued():
    _, vi = _board_and_values()
    roster = pd.DataFrame({"player_key": ["id_RB_0", "id_WR_0", "UNKNOWN_DST"]})
    expected = float(vi.set_index("player_key").loc[["id_RB_0", "id_WR_0"], "base_value"].sum())
    assert team_value(roster, vi) == pytest.approx(expected)


# --------------------------------------------------------------------------------------------
# the constrained greedy policy (via a full simulated draft)
# --------------------------------------------------------------------------------------------
def test_never_draft_is_never_rostered():
    board, vi = _board_and_values()
    ban = "id_RB_0"                                    # the single best-value player
    cfg = DraftConfig(league=LeagueSetup(draft_slot=1, slots=UNCAPPED), never_draft={ban})
    picks = _my_picks(cfg, board, vi)
    assert ban not in set(picks["player_key"])
    assert picks.iloc[0]["player_key"] != ban          # took the next-best instead


def test_positive_tilt_drafts_a_player_earlier():
    board, vi = _board_and_values()
    target = "id_QB_2"                                  # a mid-board player seat 0 gets later
    base = DraftConfig(league=LeagueSetup(draft_slot=1, slots=UNCAPPED))
    tilted = DraftConfig(league=LeagueSetup(draft_slot=1, slots=UNCAPPED), tilts={target: 6.0})
    r_base = _round_of(_my_picks(base, board, vi), target)
    r_tilt = _round_of(_my_picks(tilted, board, vi), target)
    assert r_tilt is not None
    assert r_base is None or r_tilt < r_base           # a big tilt pulls him up the board


def test_must_draft_secures_a_player_the_baseline_would_lose():
    board, vi = _board_and_values()
    target = "id_WR_1"                                  # ADP ~8; gone before seat 0's 2nd pick
    seat1 = LeagueSetup(draft_slot=1, slots=UNCAPPED)
    assert _round_of(_my_picks(DraftConfig(league=seat1), board, vi), target) is None
    cfg = DraftConfig(league=seat1, must_draft=[(target, 2.0)])
    assert _round_of(_my_picks(cfg, board, vi), target) is not None   # reach budget secures him


def test_elite_te_takes_one_te_early_not_two():
    board, vi = _board_and_values()
    cfg = DraftConfig(league=LeagueSetup(draft_slot=1, slots=UNCAPPED), archetype="elite_te")
    picks = _my_picks(cfg, board, vi)
    early_te = picks[(picks["round"] <= 3) & (picks["pos"] == "TE")]
    assert len(early_te) == 1                       # one anchor TE, then it stops reaching
    assert early_te.iloc[0]["round"] == 1


def test_must_draft_waits_rather_than_overreaching():
    # a player who will clearly last should NOT be grabbed at pick 1 (value is preserved).
    board, vi = _board_and_values()
    late = "id_TE_20"                                   # deep ADP; survives many rounds
    cfg = DraftConfig(league=LeagueSetup(draft_slot=1, slots=UNCAPPED), must_draft=[(late, 2.0)])
    picks = _my_picks(cfg, board, vi)
    assert picks.iloc[0]["player_key"] != late          # did not reach on pick 1
    assert late in set(picks["player_key"])             # but still ended up secured
