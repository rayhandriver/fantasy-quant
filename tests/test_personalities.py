"""Offline tests for Session H — 16.13 board enrichment + 16.14 the risk/value personality set.

No DB: synthetic boards only, so these run fast and — more importantly — **deterministically**.
T13 (the Phase-5 cloud is not reproducible across processes) means a face-validity test that named
a real player, or asserted on a real ``q90``, would be flaky by construction. Everything here fixes
the signals itself and asserts on the *shape* of what each personality drafts.

The synthetic boards deliberately make each signal **orthogonal to ADP**, so a tilt that shows up
cannot be the ADP coefficient wearing a disguise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fantasy_quant.draft.enrichment import (
    COS_WEIGHTS,
    DIST_COLS,
    SHAPE_COLS,
    VALUE_COLS,
    attach_enrichment,
    enrichment_coverage,
    residual_shape,
)
from fantasy_quant.draft.opponent_model import _ADP_SCALE, ALL_FEATURES, OpponentModel
from fantasy_quant.draft.personalities import (
    HEADLINERS,
    MIN_Z_GROUP,
    SIGNAL_COLS,
    Personality,
    make_opponent_pick_fn,
    personalities,
    pos_z,
    signal_bonus,
)
from fantasy_quant.draft.simulator import PASSTHROUGH_COLS, board_player_key, simulate_draft

# a plausible fitted β in ALL_FEATURES order; fandom is non-zero so the homer tilt has something
# to scale (the 11.3-era fixture used 0.0, which is why homer's no-op went unnoticed for a phase).
BETA = np.array([-0.85, -0.3, -0.2, 0.4, 0.2, 0.07, 0.0, 0.4, 0.4, 0.3])


def _model() -> OpponentModel:
    return OpponentModel(list(ALL_FEATURES), beta=BETA.copy())


def _raw_board(n: int = 120) -> pd.DataFrame:
    """A plain ADP board in the shape ``adp_asof`` returns."""
    return pd.DataFrame({
        "gsis_id": [f"00-{i:07d}" for i in range(n)],
        "name": [f"P{i}" for i in range(n)],
        "position": (["RB", "WR", "QB", "TE"] * (n // 4 + 1))[:n],
        "team": [f"T{i % 8}" for i in range(n)],
        "adp": np.arange(1, n + 1, dtype=float),
        "pos_rank": list(range(1, n + 1)),
    })


def _enriched_board(n: int = 120, seed: int = 0) -> pd.DataFrame:
    """An enriched board shaped like the real one, in the way that matters.

    Every signal is uncorrelated with **ADP** — so a drafted-pool skew is the personality and not
    the ADP term wearing a disguise. The quantiles, though, are built from two latent factors that
    reproduce what the frozen board actually measures: a **level** (which ``q90`` tracks at ~0.98
    and ``q10`` at ~0.70) and a **shape** that trades ceiling against floor at fixed level. An
    earlier version drew ``q90`` and ``q10`` independently, which made ``upside_chaser`` and
    ``safe_floor`` look cleanly opposed here while they agreed on real data. A fixture that is
    easier than reality is a fixture that certifies bugs.
    """
    rng = np.random.default_rng(seed)
    b = _raw_board(n)
    level = rng.normal(200, 50, n)
    shape = rng.normal(0, 1, n)                         # + = right-skewed: fat ceiling, thin floor
    b["mean"] = level
    b["q90"] = 1.40 * level + 13.0 * shape + rng.normal(0, 5, n)
    b["q10"] = 0.30 * level - 14.0 * shape + rng.normal(0, 6, n)
    b["boom_prob"] = rng.uniform(0, 0.6, n)
    b["bust_prob"] = rng.uniform(0, 0.6, n)
    b["games_played_mean"] = rng.uniform(6, 16, n)
    b["vbd"] = rng.normal(50, 30, n)
    b["overall_rank"] = rng.permutation(n) + 1.0
    b["rookie"] = (rng.random(n) < 0.2).astype(float)
    b["cos"] = rng.choice([0.0, 0.4, 0.6, 1.0], n)
    return b.join(residual_shape(b))


def _drafted(state, board, cols):
    """The rows every *opponent* took (your seat is the ADP default and is not a personality)."""
    keys = set(state.pick_log().query("not is_you")["player_key"])
    return board[board_player_key(board).astype(str).isin(keys)][cols]


#: Face-validity budget. A personality reaches at most ~1–2 rounds, so it does not change *whether*
#: the top of the board goes early — it changes *which* of a similar set of players each seat takes.
#: Read on one seeded draft that difference is inside the softmax's own noise (measured: the sign
#: flips between seeds), so every face-validity assertion below pools this many drafts. This is the
#: same discipline the rest of the repo applies to a single-season result.
FACE_SEEDS = range(8)


def _mean_signal_z(pers, board, cols, *, rounds: int = 6, seeds=FACE_SEEDS) -> pd.Series:
    """Mean **within-position z-score** of the signals an opponent room drafted, pooled over seeds.

    z rather than raw units so the number is scale-free and reads in the same units the personality
    optimizes in ("this room drafted +0.15 sd of ceiling"), and so the assertion does not silently
    depend on the synthetic board's arbitrary means.
    """
    zboard = board.copy()
    for c in cols:
        zboard[c] = pos_z(board[c], board["position"].to_numpy())
    return pd.concat(
        [_drafted(simulate_draft(board, n_teams=10, rounds=rounds, seed=s,
                                 opponent_pick_fn=make_opponent_pick_fn(_model(), pers)),
                  zboard, cols).mean() for s in seeds],
        axis=1).mean(axis=1)


# ================================================================================================
# 16.13 — the read-only enrichment
# ================================================================================================
def test_board_player_key_prefers_gsis_and_falls_back_to_name():
    b = pd.DataFrame({"gsis_id": ["00-1", None], "name": ["Real Guy", "Chicago Bears"],
                      "position": ["RB", "DST"], "adp": [1.0, 2.0]})
    assert list(board_player_key(b)) == ["00-1", "Chicago Bears"]


def test_attach_enrichment_joins_by_key_and_leaves_misses_nan():
    b = _raw_board(6)
    dist = pd.DataFrame({"player_key": ["00-0000000", "00-0000002"],
                         "q90": [300.0, 100.0], "q10": [50.0, 10.0], "boom_prob": [0.5, 0.1],
                         "bust_prob": [0.1, 0.5], "games_played_mean": [15.0, 8.0]})
    out = attach_enrichment(b, dist=dist)
    assert out.loc[0, "q90"] == 300.0
    assert out.loc[2, "q90"] == 100.0
    assert out["q90"].isna().sum() == 4          # the four the frozen board does not cover
    assert not b.columns.intersection(DIST_COLS).size, "the input board must not be mutated"


def test_attach_enrichment_omits_columns_whose_source_is_absent():
    """A partial enrichment says 'I don't know', it does not say 'zero'."""
    out = attach_enrichment(_raw_board(6))
    for c in (*DIST_COLS, *SHAPE_COLS, *VALUE_COLS, "rookie", "cos"):
        assert c not in out.columns


# ------------------------------------------------------------------------------------------------
# the collinearity trap that 16.14's first cut walked into — regression-tested so it stays shut
# ------------------------------------------------------------------------------------------------
def test_raw_quantiles_are_a_level_signal_not_a_shape_signal():
    """Documents *why* ``SIGNAL_COLS`` steers to ``upside``/``floor``: on a board shaped like the
    real one, weighting ``q90`` buys quality, and so does weighting ``q10``."""
    b = _enriched_board(240, seed=11)
    pos = b["position"].to_numpy()
    z = pd.DataFrame({c: pos_z(b[c], pos) for c in ("q90", "q10", "mean")})
    assert z["q90"].corr(z["mean"]) > 0.9
    assert z["q10"].corr(z["mean"]) > 0.5
    assert z["q90"].corr(z["q10"]) > 0.3, "ceiling and floor point the *same* way on raw levels"


def test_residual_shape_removes_the_level_and_opposes_upside_to_floor():
    b = _enriched_board(240, seed=11)
    pos = b["position"].to_numpy()
    z = pd.DataFrame({c: pos_z(b[c], pos) for c in ("upside", "floor", "mean")})
    assert abs(z["upside"].corr(z["mean"])) < 0.05      # 0 by construction
    assert abs(z["floor"].corr(z["mean"])) < 0.05
    assert z["upside"].corr(z["floor"]) < -0.3, "level-controlled, they finally disagree"


def test_residual_shape_is_a_no_op_without_a_level_column():
    b = _raw_board(8)
    b["q90"] = np.arange(8.0)
    assert residual_shape(b).empty, "no `mean` to control for -> no shape claim, not a fake one"


def test_rookie_and_cos_treat_absence_as_a_real_zero():
    b = _raw_board(4)
    out = attach_enrichment(b, rookie={"00-0000001"}, situation=pd.Series({"00-0000002": 1.0}))
    assert list(out["rookie"]) == [0.0, 1.0, 0.0, 0.0]
    assert list(out["cos"]) == [0.0, 0.0, 1.0, 0.0]
    assert out["cos"].notna().all()


def test_cos_weights_are_a_bounded_ordered_preference():
    assert set(COS_WEIGHTS) == {"team_change", "new_to_league", "room_change", "context_only"}
    assert all(0.0 <= v <= 1.0 for v in COS_WEIGHTS.values())
    assert (COS_WEIGHTS["team_change"] > COS_WEIGHTS["room_change"]
            > COS_WEIGHTS["context_only"])


def test_enrichment_coverage_reports_fill_rate():
    b = attach_enrichment(_raw_board(4), dist=pd.DataFrame(
        {"player_key": ["00-0000000", "00-0000001"], "q90": [1.0, 2.0], "q10": [1.0, 2.0],
         "boom_prob": [0.1, 0.2], "bust_prob": [0.1, 0.2], "games_played_mean": [9.0, 9.0]}))
    cov = enrichment_coverage(b)
    assert cov["n_rows"] == 4
    assert cov["q90"] == 0.5
    assert "vbd" not in cov              # never enriched -> never reported as 0 % coverage


def test_prepare_board_carries_enrichment_onto_the_live_board():
    board = _enriched_board(60)
    st = simulate_draft(board, n_teams=10, rounds=5, seed=1)
    for c in ("q90", "q10", "boom_prob", "vbd", "cos", "rookie", "team"):
        assert c in st.board.columns
    # and it is still aligned to the right player after the ADP sort + reindex
    src = board.set_index("name")["q90"]
    for lbl in st.board.index[:10]:
        assert st.board.loc[lbl, "q90"] == pytest.approx(src[st.board.loc[lbl, "player_name"]])


def test_adp_only_board_gains_no_enrichment_columns():
    st = simulate_draft(_raw_board(40).drop(columns=["team"]), n_teams=10, rounds=2, seed=1)
    assert not set(st.board.columns) & set(PASSTHROUGH_COLS)


# ================================================================================================
# 16.14 — mechanics
# ================================================================================================
def test_unknown_signal_weight_raises():
    with pytest.raises(ValueError, match="unknown signal_weights"):
        Personality("typo", signal_weights={"q95": 1.0})


def test_pos_z_standardizes_within_position():
    pos = np.array(["RB"] * 4 + ["WR"] * 4)
    vals = np.array([1.0, 2, 3, 4, 101, 102, 103, 104])
    z = pos_z(vals, pos)
    # the WR block is the RB block shifted by 100 -> identical z-scores, no positional lean
    assert np.allclose(z[:4], z[4:])
    assert z[:4].mean() == pytest.approx(0.0)


def test_pos_z_zeroes_unknown_and_degenerate_groups():
    pos = np.array(["RB"] * 4 + ["QB"] * 2)          # QB group is below MIN_Z_GROUP
    assert MIN_Z_GROUP > 2
    z = pos_z(np.array([1.0, 2, 3, np.nan, 10, 20]), pos)
    assert z[3] == 0.0, "a NaN signal is unknown, which is neutral — never 'bad'"
    assert np.all(z[4:] == 0.0), "a group too small to standardize contributes nothing"
    z_flat = pos_z(np.array([5.0] * 6), np.array(["RB"] * 6))
    assert np.all(z_flat == 0.0), "zero variance -> zero tilt, not a divide-by-zero"


def test_signal_bonus_skips_columns_the_board_does_not_carry():
    pool = pd.DataFrame({"pos": ["RB"] * 5, "adp": np.arange(5.0)})
    assert np.all(signal_bonus(pool, {"q90": 1.0}) == 0.0)


def test_signal_weight_shifts_utility_in_the_intended_direction():
    pool = pd.DataFrame({"pos": ["RB"] * 5, "adp": np.arange(1.0, 6.0),
                         "q90": [100.0, 150, 200, 250, 300]})
    up = signal_bonus(pool, {"q90": 0.5})
    assert up[-1] > up[0] and up[-1] > 0 > up[0]
    down = signal_bonus(pool, {"q90": -0.5})
    assert np.allclose(down, -up)


def test_reach_cap_converts_picks_through_the_models_own_adp_coefficient():
    p = Personality("x", max_reach_picks=10.0)
    assert p.reach_cap(-0.85) == pytest.approx(0.85 * 10.0 / _ADP_SCALE)
    assert Personality("y").reach_cap(-0.85) is None
    assert Personality("z", max_reach_picks=0.0).reach_cap(-0.85) == 0.0


def test_signal_weights_are_bounded_by_max_reach_picks():
    """An absurd weight with a zero ceiling must draft exactly like the untilted model."""
    board = _enriched_board(80, seed=3)
    m = _model()
    greedy = Personality("greedy", signal_weights={"q90": 500.0}, max_reach_picks=0.0)
    a = simulate_draft(board, n_teams=10, rounds=6, seed=5,
                       opponent_pick_fn=make_opponent_pick_fn(m, greedy))
    b = simulate_draft(board, n_teams=10, rounds=6, seed=5,
                       opponent_pick_fn=make_opponent_pick_fn(m, personalities()["balanced"]))
    assert list(a.pick_log()["player_key"]) == list(b.pick_log()["player_key"])


def test_the_same_weight_uncapped_does_move_the_draft():
    """The companion assertion, so the cap test above cannot pass vacuously."""
    board = _enriched_board(80, seed=3)
    m = _model()
    greedy = Personality("greedy", signal_weights={"q90": 500.0})
    a = simulate_draft(board, n_teams=10, rounds=6, seed=5,
                       opponent_pick_fn=make_opponent_pick_fn(m, greedy))
    b = simulate_draft(board, n_teams=10, rounds=6, seed=5,
                       opponent_pick_fn=make_opponent_pick_fn(m, personalities()["balanced"]))
    assert list(a.pick_log()["player_key"]) != list(b.pick_log()["player_key"])


def test_enrichment_is_inert_for_a_personality_that_does_not_ask_for_it():
    """16.13's "no modelling change" claim, as an executable assertion: the risk/value columns
    change nothing for ``balanced``, which carries no ``signal_weights``. (``team``/``rookie`` are
    excluded from the comparison — those are fitted β features and 16.13 is *meant* to wake them.)
    """
    rich = _enriched_board(80, seed=1)
    lean = rich.drop(columns=[c for c in (*DIST_COLS, *VALUE_COLS, "cos") if c in rich.columns])
    kw = dict(n_teams=10, rounds=6, seed=9)
    m = _model()
    a = simulate_draft(rich, opponent_pick_fn=make_opponent_pick_fn(
        m, personalities()["balanced"]), **kw)
    b = simulate_draft(lean, opponent_pick_fn=make_opponent_pick_fn(
        m, personalities()["balanced"]), **kw)
    assert list(a.pick_log()["player_key"]) == list(b.pick_log()["player_key"])


# ================================================================================================
# 16.14 — face validity, one test per headliner
# ================================================================================================
def test_all_five_headliners_ship_and_the_library_extras_survive():
    p = personalities()
    assert set(HEADLINERS) <= set(p)
    assert {"chalk", "zero_rb", "reacher", "rookie_hawk"} <= set(p)
    assert all(set(v.signal_weights) <= set(SIGNAL_COLS) for v in p.values())


def test_autopilot_draws_pure_adp_order():
    """Autopilot must reproduce :func:`pick_by_adp` at ``noise=0`` **exactly** — the literal
    "lowest ADP my roster caps still allow" autopicker, caps and all."""
    board = _enriched_board(120, seed=2)
    kw = dict(n_teams=10, rounds=8, seed=4)
    auto = simulate_draft(board, opponent_pick_fn=make_opponent_pick_fn(
        _model(), personalities()["autopilot"]), **kw)
    reference = simulate_draft(board, noise=0.0, **kw)          # the ADP baseline opponent
    assert list(auto.pick_log()["player_key"]) == list(reference.pick_log()["player_key"])
    # determinism: the personality carries `sample=False`, so the seed cannot change its picks
    other_seed = simulate_draft(board, opponent_pick_fn=make_opponent_pick_fn(
        _model(), personalities()["autopilot"]), n_teams=10, rounds=8, seed=99)
    assert list(auto.pick_log()["player_key"]) == list(other_seed.pick_log()["player_key"])


def test_autopilot_ignores_the_narrative_shock():
    board = _enriched_board(120, seed=2)
    hype = np.zeros(len(board))
    hype[60:] = 50.0                                    # a shock nobody sane could ignore
    kw = dict(n_teams=10, rounds=8, seed=4)
    plain = simulate_draft(board, opponent_pick_fn=make_opponent_pick_fn(
        _model(), personalities()["autopilot"]), **kw)
    shocked = simulate_draft(board, opponent_pick_fn=make_opponent_pick_fn(
        _model(), personalities()["autopilot"], hype=hype), **kw)
    assert list(plain.pick_log()["player_key"]) == list(shocked.pick_log()["player_key"])


_FACE_COLS = ["upside", "floor", "boom_prob", "bust_prob", "games_played_mean", "rookie", "cos"]


def test_upside_chaser_skews_to_ceiling_and_youth():
    board = _enriched_board(240, seed=7)
    up = _mean_signal_z(personalities()["upside_chaser"], board, _FACE_COLS)
    bal = _mean_signal_z(personalities()["balanced"], board, _FACE_COLS)
    assert up["upside"] > bal["upside"]
    assert up["rookie"] > bal["rookie"]


def test_safe_floor_skews_to_floor_and_away_from_the_bust_tail():
    board = _enriched_board(240, seed=7)
    safe = _mean_signal_z(personalities()["safe_floor"], board, _FACE_COLS)
    bal = _mean_signal_z(personalities()["balanced"], board, _FACE_COLS)
    assert safe["floor"] > bal["floor"]
    assert safe["bust_prob"] < bal["bust_prob"]


def test_upside_and_safe_disagree_with_each_other():
    """The two tilts must be genuinely opposed, not merely both different from balanced — the
    assertion that failed on real data when both were built on raw quantiles."""
    board = _enriched_board(240, seed=7)
    up = _mean_signal_z(personalities()["upside_chaser"], board, _FACE_COLS)
    safe = _mean_signal_z(personalities()["safe_floor"], board, _FACE_COLS)
    assert up["upside"] > safe["upside"]
    assert safe["floor"] > up["floor"]
    assert safe["bust_prob"] < up["bust_prob"]


def test_homer_reaches_for_his_own_team_when_one_is_set():
    board = _enriched_board(240, seed=5)
    fan = Personality("homer_T3", scale={"fandom": 2.5}, fav_teams=("T3",),
                      max_reach_picks=24.0)

    def fav_share(pers):
        return float(np.mean([
            (_drafted(simulate_draft(board, n_teams=10, rounds=6, seed=s,
                                     opponent_pick_fn=make_opponent_pick_fn(_model(), pers)),
                      board, ["team"])["team"] == "T3").mean() for s in FACE_SEEDS]))

    assert fav_share(fan) > fav_share(personalities()["balanced"])


def test_homer_chases_changed_situations_when_no_team_is_set():
    board = _enriched_board(240, seed=5)
    homer = _mean_signal_z(personalities()["homer"], board, _FACE_COLS)
    bal = _mean_signal_z(personalities()["balanced"], board, _FACE_COLS)
    assert homer["cos"] > bal["cos"]


def test_a_story_chaser_with_no_story_available_drafts_normally():
    """The requested fallback: no hype, no changed situation, no favourite team on the board ⇒
    take the best value rather than manufacture a reach. Note this is an *exact* equality on the
    whole pick log, not a tendency — with nothing to chase the tilt is identically zero."""
    board = _enriched_board(240, seed=5)
    board["cos"] = 0.0                                   # nothing has changed for anybody
    kw = dict(n_teams=10, rounds=8, seed=8)
    homer = simulate_draft(board, opponent_pick_fn=make_opponent_pick_fn(
        _model(), personalities()["homer"]), **kw)
    bal = simulate_draft(board, opponent_pick_fn=make_opponent_pick_fn(
        _model(), personalities()["balanced"]), **kw)
    assert list(homer.pick_log()["player_key"]) == list(bal.pick_log()["player_key"])


def test_hype_gain_scales_the_shared_shock_per_seat():
    """16.15 routes the 16.9 shock through the seats that would chase it; this is that dial."""
    board = _enriched_board(120, seed=4)
    hype = np.zeros(len(board))
    hype[40:80] = 1.5
    kw = dict(n_teams=10, rounds=10, seed=2)

    def hyped_share(pers):
        st = simulate_draft(board, opponent_pick_fn=make_opponent_pick_fn(
            _model(), pers, hype=hype), **kw)
        keys = set(st.pick_log().query("not is_you")["player_key"])
        taken = board[board_player_key(board).astype(str).isin(keys)]
        return float((taken.index.to_series().between(40, 79)).mean())

    hot = hyped_share(Personality("hot", hype_gain=3.0))
    cold = hyped_share(Personality("cold", hype_gain=0.0))
    assert hot > cold
