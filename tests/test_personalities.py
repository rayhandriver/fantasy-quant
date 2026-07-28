"""Offline tests for Session H — 16.13 board enrichment + 16.14 the risk/value personality set.

No DB: synthetic boards only, so these run fast and — more importantly — **deterministically**.
T13 (the Phase-5 cloud is not reproducible across processes) means a face-validity test that named
a real player, or asserted on a real ``q90``, would be flaky by construction. Everything here fixes
the signals itself and asserts on the *shape* of what each personality drafts.

The synthetic boards deliberately make each signal **orthogonal to ADP**, so a tilt that shows up
cannot be the ADP coefficient wearing a disguise.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from fantasy_quant.draft.enrichment import (
    COS_WEIGHTS,
    DIST_COLS,
    SHAPE_COLS,
    SHAPE_METHODS,
    VALUE_COLS,
    attach_enrichment,
    enrichment_coverage,
    residual_shape,
    role_shares,
    shape_inputs,
)
from fantasy_quant.draft.opponent_model import _ADP_SCALE, ALL_FEATURES, OpponentModel
from fantasy_quant.draft.personalities import (
    DEFAULT_ROOM,
    HEADLINERS,
    MIN_Z_GROUP,
    SIGNAL_COLS,
    Personality,
    make_opponent_pick_fn,
    make_room,
    make_room_pick_fn,
    normalized_hype_gains,
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


_FACE_COLS = ["upside", "floor", "tail_risk", "games_played_mean", "rookie", "cos"]


def test_upside_chaser_skews_to_ceiling_and_youth():
    board = _enriched_board(240, seed=7)
    up = _mean_signal_z(personalities()["upside_chaser"], board, _FACE_COLS)
    bal = _mean_signal_z(personalities()["balanced"], board, _FACE_COLS)
    assert up["upside"] > bal["upside"]
    assert up["rookie"] > bal["rookie"]


def test_safe_floor_skews_to_floor_and_away_from_the_bust_tail():
    """T19/T22: the "away from the bust tail" half is now measured on ``tail_risk``.

    ``bust_prob`` used to carry it and cannot: on a live board it is the **2022** season's realized
    rate with 56 % of its values manufactured by ``fillna(0.0)``, so a seat weighting it was
    tilting on four-year-old data where it was not tilting on nothing.
    """
    board = _enriched_board(240, seed=7)
    safe = _mean_signal_z(personalities()["safe_floor"], board, _FACE_COLS)
    bal = _mean_signal_z(personalities()["balanced"], board, _FACE_COLS)
    assert safe["floor"] > bal["floor"]
    assert safe["tail_risk"] < bal["tail_risk"]


def test_upside_and_safe_disagree_with_each_other():
    """The two tilts must be genuinely opposed, not merely both different from balanced — the
    assertion that failed on real data when both were built on raw quantiles."""
    board = _enriched_board(240, seed=7)
    up = _mean_signal_z(personalities()["upside_chaser"], board, _FACE_COLS)
    safe = _mean_signal_z(personalities()["safe_floor"], board, _FACE_COLS)
    assert up["upside"] > safe["upside"]
    assert safe["floor"] > up["floor"]
    assert safe["tail_risk"] < up["tail_risk"], "the ceiling-chaser must want the wider outcome"


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
    whole pick log, not a tendency — with nothing to chase the tilt is identically zero.

    ⚠ **T15 split this into two properties and the test now pins the right one.** ``width_mult`` is
    a standing property of the seat, not a reaction to a story, so a homer at his shipped width
    (1.2) legitimately drafts differently from ``balanced`` even with nothing to chase. The claim
    being tested is that *the discretionary tilt* is zero, so the comparison holds width fixed.
    Left as an equality against ``balanced`` it would have failed for a correct reason, which is the
    least useful kind of red.
    """
    board = _enriched_board(240, seed=5)
    board["cos"] = 0.0                                   # nothing has changed for anybody
    kw = dict(n_teams=10, rounds=8, seed=8)
    flat_homer = replace(personalities()["homer"], width_mult=1.0)
    homer = simulate_draft(board, opponent_pick_fn=make_opponent_pick_fn(
        _model(), flat_homer), **kw)
    bal = simulate_draft(board, opponent_pick_fn=make_opponent_pick_fn(
        _model(), personalities()["balanced"]), **kw)
    assert list(homer.pick_log()["player_key"]) == list(bal.pick_log()["player_key"])


def test_width_mult_is_the_only_thing_separating_that_homer_from_balanced():
    """The other half of the split above: at his shipped width the homer *does* stray further.

    Stated as an opposition (the 16.14 lesson), because "differs from balanced" would also pass on a
    seat that merely drafts a different legal draft.
    """
    board = _enriched_board(240, seed=5)
    board["cos"] = 0.0
    kw = dict(n_teams=10, rounds=10, seed=8)

    def mean_abs_reach(pers):
        st = simulate_draft(board, opponent_pick_fn=make_opponent_pick_fn(_model(), pers), **kw)
        log = st.pick_log()
        return float((log["adp"] - log["overall_pick"]).abs().mean())

    wide = mean_abs_reach(replace(personalities()["homer"], width_mult=2.0))
    narrow = mean_abs_reach(replace(personalities()["homer"], width_mult=0.5))
    assert wide > narrow


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


# --------------------------------------------------------------------------------------------
# the no-op guard: a weightable signal that never reaches the pool (Session H2)
# --------------------------------------------------------------------------------------------
def test_every_weightable_signal_survives_prepare_board():
    """``signal_bonus`` skips columns the pool does not carry, so a signal that is weightable but
    not passed through is a **silent no-op** — the weight validates, the draft completes, and the
    personality does nothing. That shipped three times (``fandom``, ``rookie``, ``durability``).
    This containment is the assertion that ends the bug class."""
    missing = set(SIGNAL_COLS) - set(PASSTHROUGH_COLS)
    assert not missing, (
        f"weightable but dropped by _prepare_board: {sorted(missing)} — add them to "
        f"simulator.PASSTHROUGH_COLS or they are inert")


def test_durability_is_a_shape_signal_not_a_level_proxy():
    """T17 turned ``games_played_mean`` into a real forecast **and** into a level proxy; the
    level-controlled column is what a durability tilt must weight.

    ★ **This asserts the signal's meaning, not the estimator's construction.** It used to demand
    ``corr(durability, mean) < 1e-9`` — true *by construction* of an OLS residual and of nothing
    else. T19 replaced that estimator (a residual of a censored variable is not a shape signal at
    all), and the exact-zero assertion failed on an estimator that is **better** on the real board:
    ``corr(durability, adp)`` runs +0.63/+0.19/+0.29/+0.52 by position under ``linear`` and
    +0.02/−0.05/−0.05/+0.00 under the shipped ``rank``. A test that pins the mechanism fails the
    upgrade and passes the bug — the same lesson T17 itself recorded.

    The fixture is also realistic on purpose. A *noiseless monotone* input is the one case a local
    rank provably cannot detrend (every window sees the same ordering), and the old fixture was
    exactly that. Real boards are not, which is why the measured numbers above are what they are.
    """
    rng = np.random.default_rng(3)
    n = 40
    board = pd.DataFrame({
        "position": ["RB"] * n + ["WR"] * n,
        "adp": np.r_[np.linspace(5, 190, n), np.linspace(4, 195, n)],
        "mean": np.r_[np.linspace(230, 40, n), np.linspace(240, 45, n)] + rng.normal(0, 12, 2 * n),
    })
    # games tracks the level (the post-T17 defect) with real idiosyncratic spread on top
    board["games_played_mean"] = np.clip(
        6.0 + 0.04 * board["mean"] + rng.normal(0, 1.8, 2 * n), 1, 17)
    board["q90"] = 1.40 * board["mean"] + rng.normal(0, 18, 2 * n)
    board["q10"] = np.clip(0.30 * board["mean"] + rng.normal(0, 22, 2 * n), 0, None)

    shape = residual_shape(board)
    assert "durability" in shape.columns
    wide = board.assign(d=shape["durability"])
    for _pos, g in wide.groupby("position"):
        raw = abs(np.corrcoef(g["games_played_mean"], g["mean"])[0, 1])
        res = abs(np.corrcoef(g["d"], g["mean"])[0, 1])
        assert raw > 0.5, "fixture must reproduce the post-T17 level entanglement"
        assert res < 0.5 * raw, f"level not controlled: raw {raw:.2f} -> {res:.2f}"


def test_safe_floor_weights_the_residual_not_the_raw_games_column():
    w = personalities()["safe_floor"].signal_weights
    assert "durability" in w and "games_played_mean" not in w


# ================================================================================================
# 16.15 — the mock room: composition, gain normalization, seat routing
# ================================================================================================
def test_make_room_defaults_to_the_listed_nine_seats():
    room = make_room()
    assert [p.name for p in room] == list(DEFAULT_ROOM)
    assert len(room) == 9, "a 10-team league has nine opponents"


def test_make_room_rejects_a_mix_that_does_not_fill_the_room():
    with pytest.raises(ValueError, match="exactly 9"):
        make_room(("balanced", "chalk"))


def test_make_room_rejects_an_unknown_personality():
    """A typo in a room spec must not silently degrade to 'balanced' — the same argument
    ``Personality.__post_init__`` makes for ``signal_weights``."""
    with pytest.raises(ValueError, match="unknown personalities"):
        make_room(("balanced",) * 8 + ("upside_chazer",))


def test_make_room_seed_shuffles_reproducibly():
    """Seats are shuffled so a personality is not confounded with a draft slot; the same seed must
    still give the same room, or a 'seeded' comparison across builds means nothing."""
    a = [p.name for p in make_room(seed=7)]
    b = [p.name for p in make_room(seed=7)]
    assert a == b
    assert sorted(a) == sorted(DEFAULT_ROOM), "a shuffle, not a resample"
    assert any(a != [p.name for p in make_room(seed=s)] for s in (1, 2, 3)), "seed must matter"


def test_make_room_attaches_fav_teams_to_the_homer_seat_only():
    room = make_room(fav_teams=("KC",))
    fav = {p.name: p.fav_teams for p in room if p.fav_teams}
    assert fav == {"homer": ("KC",)}


def test_normalized_hype_gains_have_mean_one_and_preserve_ratios():
    """16.9 fitted the shock's size with the draw applied uniformly, so a room must redistribute
    it, never rescale it."""
    room = make_room()
    g = normalized_hype_gains(room)
    assert g.mean() == pytest.approx(1.0)
    raw = np.array([p.hype_gain for p in room])
    nz = raw > 0
    assert np.allclose(g[nz] / raw[nz], g[nz][0] / raw[nz][0]), "one scale factor for the room"


def test_normalized_hype_gains_leave_an_all_autopilot_room_at_zero():
    """The degenerate room has no hype channel at all; it must be left alone, not divided by 0."""
    g = normalized_hype_gains(make_room(("autopilot",) * 9))
    assert np.all(g == 0.0) and np.all(np.isfinite(g))


def test_make_room_pick_fn_maps_seats_around_your_own_team():
    """Seat ``i`` is the ``i``-th *other* team, so the mapping has to skip your seat. Off by one
    here silently gives every seat someone else's personality, and every draft still completes."""
    board = _enriched_board(60, seed=1)
    seen: list[int] = []
    room = make_room()

    def spy(state, team):
        seen.append(team)
        return make_room_pick_fn(_model(), room)(state, team)

    st = simulate_draft(board, n_teams=10, rounds=2, seed=0, your_team=3, opponent_pick_fn=spy)
    assert 3 not in seen, "your own seat is never routed to a personality"
    assert set(seen) == set(range(10)) - {3}
    assert st.your_team == 3


def test_make_room_pick_fn_rejects_a_team_outside_the_room():
    board = _enriched_board(40, seed=1)
    st = simulate_draft(board, n_teams=4, rounds=1, seed=0)
    with pytest.raises(ValueError, match="the room has 9 seats"):
        make_room_pick_fn(_model(), make_room())(st, 12)


def test_a_room_of_one_personality_matches_broadcasting_that_personality():
    """The routing layer must add nothing of its own: nine identical seats have to reproduce the
    single-personality path exactly, pick for pick."""
    board = _enriched_board(120, seed=2)
    kw = dict(n_teams=10, rounds=6, seed=4)
    room = simulate_draft(board, opponent_pick_fn=make_room_pick_fn(
        _model(), make_room(("balanced",) * 9)), **kw)
    solo = simulate_draft(board, opponent_pick_fn=make_opponent_pick_fn(
        _model(), personalities()["balanced"]), **kw)
    assert list(room.pick_log()["player_key"]) == list(solo.pick_log()["player_key"])


def test_an_autopilot_seat_still_takes_best_available_inside_a_mixed_room():
    """The room must not homogenize its seats. Asserted as the autopicker's own invariant —
    lowest ADP still on the board at each of its turns — rather than against an all-autopilot
    draft, which diverges after round 1 for the honest reason that the other eight seats are
    different people."""
    board = _enriched_board(120, seed=2)
    room = make_room(("autopilot",) + ("balanced",) * 8)
    st = simulate_draft(board, n_teams=10, rounds=6, seed=4,
                        opponent_pick_fn=make_room_pick_fn(_model(), room))
    log = st.pick_log()
    adp = dict(zip(board_player_key(board).astype(str), board["adp"], strict=True))
    taken: set[str] = set()
    for _, row in log.iterrows():
        key = str(row["player_key"])
        if row["team"] == 1:                       # seat 0 = the first team after yours (team 0)
            best = min(set(adp) - taken, key=lambda k: adp[k])
            assert adp[key] == adp[best], f"autopilot reached at overall pick {row['overall_pick']}"
        taken.add(key)


def test_the_reach_ceiling_does_not_swallow_the_shared_shock():
    """★ The 16.15 regression. The ceiling bounds a seat's OWN opinion; the shared 16.9 draw is
    applied outside it. Folded into the same clip, a seat whose ``signal_weights`` already saturate
    its ceiling cannot express the story at all — and nothing fails, because a personality that
    ignores the shock still completes a legal draft. Here the signal tilt is deliberately
    saturating and the shock is unmissable, so a build that clips them together drafts as if the
    shock were not there."""
    board = _enriched_board(120, seed=6)
    # deep enough that nothing but a story reaches him, but inside `CHOICE_TOP_K` — the candidate
    # set is a hard ADP-rank filter applied *before* utility, so a shock on player 90 of a 120-man
    # board can express nothing at all. (Session G's contract lesson, from the other side.)
    target = 38
    hype = np.zeros(len(board))
    hype[target] = 40.0
    pers = Personality("capped", signal_weights={"floor": 3.0}, max_reach_picks=1.0,
                       hype_gain=1.0, sample=False)
    kw = dict(n_teams=10, rounds=2, seed=0)
    with_hype = simulate_draft(board, opponent_pick_fn=make_opponent_pick_fn(
        _model(), pers, hype=hype), **kw)
    without = simulate_draft(board, opponent_pick_fn=make_opponent_pick_fn(_model(), pers), **kw)
    key = str(board_player_key(board).iloc[target])
    assert key in set(with_hype.pick_log().query("not is_you")["player_key"])
    assert key not in set(without.pick_log().query("not is_you")["player_key"])


def test_the_story_routes_in_proportion_to_seat_gain():
    """The substep's claim, at a shock size big enough to resolve. The done-bar runs this on the
    live board and reports the *shipped* 16.9 size separately, where it is a null."""
    board = _enriched_board(150, seed=9)
    keys = board_player_key(board).astype(str)
    gains = (0.0, 0.5, 1.0, 2.0, 4.0)
    room = tuple(replace(personalities()["balanced"], name=f"g{g}", hype_gain=g)
                 for g in gains) + tuple(
        replace(personalities()["balanced"], name=f"g{g}b", hype_gain=g) for g in gains[:4])
    norm = normalized_hype_gains(room)
    hit, tot = np.zeros(9), np.zeros(9)
    for s in range(6):
        rng = np.random.default_rng(500 + s)
        shock = rng.normal(0, 1.0, len(board))       # ~30 picks: the mechanism, not 16.9's size
        loud = set(keys.iloc[np.argsort(-shock)[:25]])
        st = simulate_draft(board, n_teams=10, rounds=10, seed=s,
                            opponent_pick_fn=make_room_pick_fn(_model(), room, hype=shock))
        log = st.pick_log().query("not is_you")
        team = log["team"].to_numpy()
        seats = np.where(team > st.your_team, team - 1, team)
        is_loud = log["player_key"].astype(str).isin(loud).to_numpy()
        for seat, ld in zip(seats, is_loud, strict=True):
            tot[seat] += 1
            hit[seat] += float(ld)
    share = hit / np.maximum(tot, 1)
    rho = pd.Series(share).corr(pd.Series(norm), method="spearman")
    assert rho > 0.7, f"story did not route in proportion to gain (spearman {rho:+.3f})"
    assert share[np.argmax(norm)] > share[np.argmin(norm)]


# ==================================================================================================
# T21 — the choice-set contract's position half
# ==================================================================================================
def test_simulation_and_fit_share_one_position_contract():
    """Fit and simulation must name the **same** candidate positions, from one constant.

    The Session-G guard in the other direction (``CHOICE_TOP_K``) already exists; this is its
    position twin. ``build_choice_frame(skill_only=True)`` — the default the shipped beta was fit
    under — and ``make_opponent_pick_fn`` now both read :data:`SKILL_POSITIONS`, so a future edit
    to one cannot silently widen the other.
    """
    import inspect

    from fantasy_quant.draft import opponent_model
    from fantasy_quant.draft import personalities as pers_mod

    assert opponent_model.SKILL_POSITIONS == ("QB", "RB", "WR", "TE")
    src = inspect.getsource(pers_mod.make_opponent_pick_fn)
    assert "SKILL_POSITIONS" in src, "the simulator must band on the fitted position set"
    assert pers_mod.SKILL_POSITIONS is opponent_model.SKILL_POSITIONS


def test_the_model_never_nominates_a_kicker():
    """T21's symptom, pinned: a fitted beta estimated on skill players only cannot pick one.

    ``value_hawk`` took Brandon Aubrey (K, ADP 128) at pick 119 in the 2x5 mock because the
    simulator banded the whole board while the fit saw four positions. Kickers are rare enough in
    15 rounds that this reads as a handful of odd picks rather than a shifted distribution — an
    aggregate metric cannot see an occasional impossible event, so it needs its own assertion.
    """
    board = _enriched_board(180, seed=5)
    board.loc[board.index[:20], "position"] = "PK"        # a fat band of kickers, mid-board
    pick_fn = make_opponent_pick_fn(_model(), personalities()["balanced"])
    res = simulate_draft(board, n_teams=10, rounds=8,     # rounds < starters: no forcing
                         opponent_pick_fn=pick_fn,
                         your_pick_fn=lambda st: int(st.draftable_pool(st.your_team).index[0]),
                         seed=3)
    log = res.pick_log()
    assert not log[~log["is_you"]]["pos"].isin(("K", "DST")).any()


# ==================================================================================================
# T19 — the repaired shape signals
# ==================================================================================================
def test_a_censored_q10_does_not_invert_the_floor_signal():
    """T19, as an opposition: censoring must not make the *safety* signal prefer *deeper* players.

    The board reproduces the real one's defect — ``q10`` floored at 0 for the deep half — and the
    assertion is the one the shipped ``linear`` estimator fails: ``corr(floor, adp) <= 0``.
    """
    rng = np.random.default_rng(11)
    n = 60
    adp = np.linspace(2, 200, n)
    mean = np.clip(300 - 1.4 * adp + rng.normal(0, 15, n), 5, None)
    q10 = np.clip(0.45 * mean - 55 + rng.normal(0, 12, n), 0, None)   # censors at depth
    board = pd.DataFrame({
        "position": ["RB"] * n, "adp": adp, "mean": mean, "q10": q10,
        "q90": 1.5 * mean + rng.normal(0, 20, n),
        "games_played_mean": np.clip(6 + 0.03 * mean + rng.normal(0, 2, n), 1, 17),
    })
    censored_share = float((q10 == 0).mean())
    assert censored_share > 0.25, "fixture must actually censor"

    shipped = residual_shape(board, method="linear")["floor"]
    fixed = residual_shape(board)["floor"]
    assert np.corrcoef(shipped, adp)[0, 1] > 0, "fixture must reproduce the T19 inversion"
    assert np.corrcoef(fixed, adp)[0, 1] <= 0, "repaired floor still prefers deeper players"


def test_shape_inputs_are_scale_free_ratios():
    """The resolution was the *scale*, not the fit — a censored q10 lands at the bottom of a
    bounded ratio, where it belongs, instead of at the top of a residual."""
    board = pd.DataFrame({
        "position": ["RB"] * 3, "adp": [10.0, 50.0, 150.0], "mean": [200.0, 120.0, 40.0],
        "q10": [90.0, 30.0, 0.0], "q90": [320.0, 210.0, 95.0],
        "games_played_mean": [15.0, 12.0, 8.0],
    })
    raw = shape_inputs(board)
    assert raw["floor"].iloc[2] == 0.0, "a censored player has the worst possible relative floor"
    assert raw["floor"].iloc[0] > raw["floor"].iloc[1] > raw["floor"].iloc[2]
    # tail_risk is the (q90 - q10)/mean spread 16.14R step 4 asks for by name
    assert raw["tail_risk"].iloc[2] > raw["tail_risk"].iloc[0]


def test_shape_methods_are_all_runnable_and_named():
    """Every documented method must actually run — the dead ends are kept *runnable* so the
    before/after in ``steps/phase16_14r_2_floor.py`` stays reproducible, not just described."""
    board = _enriched_board(120, seed=2)
    for m in SHAPE_METHODS:
        out = residual_shape(board, method=m)
        assert list(out.columns) == list(SHAPE_COLS)
        assert out["floor"].notna().sum() > 0
    with pytest.raises(ValueError, match="unknown shape method"):
        residual_shape(board, method="nope")


def test_tail_risk_replaces_the_stale_boom_bust_weights():
    """T22: no shipped personality may weight a column four seasons stale on a live board."""
    for name in ("safe_floor", "upside_chaser"):
        w = personalities()[name].signal_weights
        assert "bust_prob" not in w and "boom_prob" not in w, f"{name} still weights a stale column"
        assert "tail_risk" in w
    # and they want opposite things from it
    assert personalities()["safe_floor"].signal_weights["tail_risk"] < 0
    assert personalities()["upside_chaser"].signal_weights["tail_risk"] > 0


# ==================================================================================================
# 16.14R step 3 — the derived context columns
# ==================================================================================================
def test_role_share_is_a_share_of_the_team_position_group():
    """A bell-cow owns his team's positional projection; a committee splits it."""
    board = pd.DataFrame({
        "gsis_id": [f"00-{i}" for i in range(5)],
        "name": ["Bell Cow", "Split A", "Split B", "Other QB", "Lone TE"],
        "position": ["RB", "RB", "RB", "QB", "TE"],
        "team": ["AAA", "BBB", "BBB", "AAA", "AAA"],
        "adp": [5.0, 40.0, 45.0, 60.0, 80.0],
        "mean": [250.0, 120.0, 110.0, 300.0, 150.0],
        "pos": ["RB", "RB", "RB", "QB", "TE"],
    })

    class _FakeCon:
        def execute(self, *_a, **_k):
            class _R:
                def df(self_inner):
                    return pd.DataFrame(columns=["gsis_id", "team", "pos", "pts"])
            return _R()

    out = role_shares(_FakeCon(), 2026, board)
    assert out.loc[0, "role_share"] == pytest.approx(1.0)          # sole RB on his team
    assert out.loc[1, "role_share"] == pytest.approx(120 / 230)    # half a committee
    assert out.loc[2, "role_share"] == pytest.approx(110 / 230)
    assert out["role_delta"].isna().all(), "no prior season -> unknown, not zero"


def test_context_columns_are_weightable_and_default_off():
    """Step 3's contract: on the board, in ``SIGNAL_COLS``, and weighted by nobody by default."""
    from fantasy_quant.draft.enrichment import CONTEXT_COLS

    for c in CONTEXT_COLS:
        assert c in SIGNAL_COLS, f"{c} must be weightable"
        assert c in PASSTHROUGH_COLS, f"{c} must survive _prepare_board"
    for name, pers in personalities().items():
        for c in CONTEXT_COLS:
            assert c not in pers.signal_weights, f"{name} weights {c} by default"


# ==================================================================================================
# 16.14R steps 4-7 — the reworked seats
# ==================================================================================================
def test_reach_budget_counts_from_the_draft_log_not_from_memory():
    """The budget is stateful per seat but re-derived every pick, so a clone cannot diverge."""
    from fantasy_quant.draft.personalities import ReachBudget

    b = ReachBudget(round_ceiling=None)
    board = _enriched_board(120, seed=1)
    st = simulate_draft(board, n_teams=10, rounds=15, seed=0)
    st.log = [
        {"team": 3, "adp": 100.0, "overall_pick": 30.0},     # +70 -> large
        {"team": 3, "adp": 40.0, "overall_pick": 28.0},      # +12 -> medium
        {"team": 4, "adp": 200.0, "overall_pick": 20.0},     # another seat's, ignored
    ]
    assert b.used(st, 3) == (1, 1)
    assert b.used(st, 4) == (1, 0)


def test_reach_budget_gates_by_round_and_by_count():
    from fantasy_quant.draft.personalities import ReachBudget

    b = ReachBudget(round_ceiling=None)
    board = _enriched_board(120, seed=1)
    st = simulate_draft(board, n_teams=10, rounds=15, seed=0)
    st.log = []

    st.overall_pick = 5                                       # round 1: clamped early
    assert b.cap(st, 0) == b.early_max_picks
    st.overall_pick = 45                                      # round 5: a swing is allowed
    assert b.cap(st, 0) == float("inf")
    st.log = [{"team": 0, "adp": 200.0, "overall_pick": 40.0}] * 3   # three swings spent
    assert b.cap(st, 0) == b.large_picks


def test_the_round_ceiling_bounds_how_far_not_just_how_often():
    """A count budget cannot bound magnitude; ``CORPUS_REACH_P95`` is why the seat is possible."""
    from fantasy_quant.draft.personalities import CORPUS_REACH_P95, ReachBudget

    b = ReachBudget()
    board = _enriched_board(120, seed=1)
    st = simulate_draft(board, n_teams=10, rounds=15, seed=0)
    st.log = []
    st.overall_pick = 45                                      # round 5, budget says "unlimited"
    assert b.cap(st, 0) == CORPUS_REACH_P95[4]                # ... the ceiling says otherwise
    assert len(CORPUS_REACH_P95) == 15


def test_level_floor_is_a_threshold_over_the_board_not_the_pool():
    """A pool-relative floor fires on somebody at every pick and is a level tilt in disguise."""
    board = _enriched_board(200, seed=4)
    p = replace(personalities()["safe_floor"], level_floor=5.0, level_floor_penalty=50.0)
    res = simulate_draft(board, n_teams=10, rounds=6, seed=1,
                         opponent_pick_fn=make_opponent_pick_fn(_model(), p))
    assert len(res.pick_log()) == 60, "an extreme floor must not stall or crash the draft"


def test_value_hawk_is_not_a_signal_weights_seat():
    """Open decision #1, pinned: ``pos_z(vbd)`` deletes VBD's only non-ADP content."""
    vh = personalities()["value_hawk"]
    assert vh.objective == "portfolio_ce"
    assert not vh.signal_weights, "a signal_weights value hawk is a chalk tilt with extra width"
    assert vh.context_weights, "it must price the step-3 blind spots"


def test_a_portfolio_ce_seat_without_a_risk_model_fails_loudly():
    """*An inert thing still passes* — so this refuses to run instead of drafting as balanced."""
    from fantasy_quant.draft import mock as mock_mod

    room = mock_mod.full_room(("value_hawk", *["balanced"] * 9), n_teams=10)
    with pytest.raises(ValueError, match="portfolio_ce"):
        mock_mod.assert_room_objectives(room, None)
    mock_mod.assert_room_objectives(room, object())            # any risk model satisfies it


def test_realistic_room_has_one_autopilot_and_ten_seats():
    """Step 7's composition decision, pinned with the reason it was made."""
    from fantasy_quant.draft.personalities import REALISTIC_ROOM

    assert len(REALISTIC_ROOM) == 10
    assert REALISTIC_ROOM.count("autopilot") == 1, "two autopilot seats manufacture their own spill"
    assert "homer" not in REALISTIC_ROOM, "16.14R retired the homer in favour of the value hawk"
    assert "value_hawk" in REALISTIC_ROOM
