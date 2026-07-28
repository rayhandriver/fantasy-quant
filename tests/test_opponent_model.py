"""Offline tests for the Phase 11 behavioral opponent model / availability / personalities.

No DB — synthetic choice sets only, so these run fast in CI.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fantasy_quant.draft.availability import _draft_blocks, _softmax, simulate_survival
from fantasy_quant.draft.opponent_model import (
    ALL_FEATURES,
    BAND_SPEC,
    CHOICE_TOP_K,
    AdpSpec,
    BandSpec,
    OpponentModel,
    _group_ptr,
    _softmax_by_group,
    build_choice_frame,
)
from fantasy_quant.draft.personalities import make_opponent_pick_fn, personalities
from fantasy_quant.draft.simulator import simulate_draft


def test_group_softmax_matches_manual():
    u = np.array([0.0, np.log(3.0), 0.0, 0.0])   # group0: {1,3} -> .25/.75 ; group1: {1,1}->.5/.5
    ptr = _group_ptr(np.array([0, 0, 1, 1]))
    soft, lse = _softmax_by_group(u, ptr)
    assert np.allclose(soft, [0.25, 0.75, 0.5, 0.5])
    assert np.allclose(lse, [np.log(4.0), np.log(2.0)])


def _synthetic_choices(n_groups=400, k=8, seed=0):
    """Groups where the chosen row is driven by low adp + a rookie bonus (recoverable signal)."""
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(n_groups):
        adp = rng.uniform(1, 200, k)
        rookie = (rng.random(k) < 0.2).astype(float)
        util = -adp / 50.0 * 1.0 + rookie * 1.5 + rng.gumbel(size=k)   # true logit DGP
        chosen = int(np.argmax(util))
        for i in range(k):
            rows.append({
                "group": g, "season": 2000 + g % 5, "chosen": 1 if i == chosen else 0,
                "adp_s": adp[i] / 50.0, "is_RB": 0.0, "is_WR": 0.0, "is_TE": 0.0, "is_QB": 0.0,
                "pos_run3": 0.0, "mgr_lean": 0.0, "rookie": rookie[i], "fandom": 0.0, "need": 0.0,
            })
    return pd.DataFrame(rows)


def test_fit_recovers_signal_and_beats_random():
    frame = _synthetic_choices()
    m = OpponentModel(list(ALL_FEATURES), l2=0.5).fit(frame)
    coefs = dict(zip(ALL_FEATURES, m.beta, strict=False))
    assert coefs["adp_s"] < -0.3       # lower adp -> picked
    assert coefs["rookie"] > 0.5       # rookie bonus recovered
    sc = m.score(frame)
    assert sc["logloss"] < np.log(8)   # better than uniform-over-8


def test_candidate_utility_ignores_absent_features_for_adp_only():
    m = OpponentModel(["adp_s"], beta=np.array([-1.0]))
    cand = pd.DataFrame({"adp": [10.0, 100.0], "pos": ["RB", "WR"]})
    u = m.candidate_utility(cand)
    assert u[0] > u[1]                 # adp 10 preferred over adp 100


def test_simulate_survival_bounds_and_monotone():
    m = OpponentModel(["adp_s"], beta=np.array([-1.0]))
    cand = pd.DataFrame({"adp": [5.0, 15.0, 25.0, 40.0, 60.0], "pos": ["RB"] * 5})
    avail0 = np.ones(5, bool)
    plan = [{}, {}, {}]                 # three neutral opponent picks
    surv = simulate_survival(cand, avail0, plan, m, n_sims=300, rng=np.random.default_rng(0))
    assert np.all((surv >= 0) & (surv <= 1))
    assert surv[0] <= surv[-1] + 0.05  # the best (lowest-adp) player survives least


def _simulate_survival_reference(cand, avail0, seat_plan, model, *, n_sims, rng, recent0=None):
    """The pre-T14 implementation: rebuild the feature matrix from pandas at every simulated pick.

    Kept verbatim as the oracle for :func:`simulate_survival`, whose T14 optimization is a pure
    refactor — hoisting invariant work out of the loop must not move a single probability.
    """
    m = len(cand)
    idx_all = np.arange(m)
    surv = np.zeros(m)
    pos_arr = cand["pos"].to_numpy()
    for _ in range(n_sims):
        avail = avail0.copy()
        recent = list(recent0 or [])
        for ctx in seat_plan:
            ai = idx_all[avail]
            if ai.size == 0:
                break
            rp: dict[str, int] = {}
            for p in recent[-3:]:
                rp[p] = rp.get(p, 0) + 1
            u = model.candidate_utility(cand.iloc[ai], recent_pos=rp, lean=ctx.get("lean"),
                                        fav=ctx.get("fav"), need=ctx.get("need"))
            choice = int(rng.choice(ai, p=_softmax(u)))
            avail[choice] = False
            recent.append(pos_arr[choice])
        surv += avail
    return surv / n_sims


def _survival_case(seed=7, m=120):
    rng = np.random.default_rng(seed)
    pos = rng.choice(["QB", "RB", "WR", "TE"], m, p=[0.12, 0.32, 0.44, 0.12])
    cand = pd.DataFrame({
        "adp": np.sort(rng.uniform(1, 260, m)), "pos": pos,
        "team": rng.choice(["KC", "SF", "PHI", "BAL"], m),
        "rookie": (rng.random(m) < 0.15).astype(float),
    })
    avail0 = np.ones(m, bool)
    avail0[rng.choice(m, 20, replace=False)] = False
    plan = [{"lean": {p: float(rng.normal(0, 0.05)) for p in ("QB", "RB", "WR", "TE")},
             "fav": {"KC"} if i % 3 else set(),
             "need": {"QB": 1.0, "RB": 2.0, "WR": 1.0, "TE": 0.0}} for i in range(9)]
    return cand, avail0, plan


def test_candidate_matrix_row_subset_identity():
    """The invariant the T14 hoist rests on: every feature column is row-wise, so building the
    matrix for the whole board and slicing == building it on the slice. If a future feature reads
    across rows (a rank, a share, a z-score), this test is what catches it."""
    cand, _, plan = _survival_case()
    m = OpponentModel(list(ALL_FEATURES), beta=np.arange(len(ALL_FEATURES), dtype=float))
    rows = np.array([3, 17, 40, 41, 99])
    ctx = plan[0]
    kw = dict(recent_pos={"RB": 2, "WR": 1}, lean=ctx["lean"], fav=ctx["fav"], need=ctx["need"])
    full = m.candidate_matrix(cand, **kw)[rows]
    subset = m.candidate_matrix(cand.iloc[rows], **kw)
    assert np.array_equal(full, subset)


def test_simulate_survival_matches_reference_bitwise():
    """T14: the optimized loop reproduces the reference implementation exactly — same utilities,
    same RNG stream, same probabilities. Not `allclose`: a refactor that moves a probability is a
    behaviour change, and 11.2's committed Brier would no longer mean what it says."""
    cand, avail0, plan = _survival_case()
    model = OpponentModel(list(ALL_FEATURES),
                          beta=np.array([-1.7, -0.4, -0.1, 0.6, 0.0, 0.05, 0.06, 0.11, 1.2, 0.47]))
    # the oracle predates the Session-G choice-set band, so compare against `top_k=None`; the band
    # itself is a deliberate behaviour change, covered by test_choice_band_* below.
    kw = dict(n_sims=25, recent0=["RB", "WR", "RB"])
    ref = _simulate_survival_reference(cand, avail0, plan, model,
                                       rng=np.random.default_rng(3), **kw)
    got = simulate_survival(cand, avail0, plan, model, rng=np.random.default_rng(3),
                            top_k=None, **kw)
    assert np.array_equal(ref, got)

    # the ADP-only model has no `pos_run3` column at all -> the in-place run update is skipped
    adp_only = OpponentModel(["adp_s"], beta=np.array([-1.7]))
    ref2 = _simulate_survival_reference(cand, avail0, plan, adp_only,
                                        rng=np.random.default_rng(5), **kw)
    got2 = simulate_survival(cand, avail0, plan, adp_only, rng=np.random.default_rng(5),
                             top_k=None, **kw)
    assert np.array_equal(ref2, got2)

    # positions absent from the board (K/DST/None) must contribute no run count, not wrap around
    ref3 = _simulate_survival_reference(cand, avail0, plan, model, n_sims=10,
                                        recent0=["K", "DST", None], rng=np.random.default_rng(9))
    got3 = simulate_survival(cand, avail0, plan, model, n_sims=10, top_k=None,
                             recent0=["K", "DST", None], rng=np.random.default_rng(9))
    assert np.array_equal(ref3, got3)


def test_choice_band_restricts_to_top_k_by_adp():
    """16.9/Session G: a conditional logit's β only means anything relative to the candidate set it
    was fit on (`build_choice_frame(top_k=CHOICE_TOP_K)`). Simulating over the whole board is the
    model applied outside its contract — players far past the band must get zero pick probability,
    hence survival 1.0."""
    cand, avail0, plan = _survival_case(m=200)
    model = OpponentModel(["adp_s"], beta=np.array([-1.7]))
    # rows unavailable at the window start end at survival 0 by construction, so judge only the
    # deep rows that actually started available
    deep = np.flatnonzero(avail0)[60:]
    surv = simulate_survival(cand, avail0, plan, model, n_sims=40,
                             rng=np.random.default_rng(0), top_k=10)
    # `cand` is ADP-ascending and the window is 9 picks, so nothing past the band can be taken
    assert np.all(surv[deep] == 1.0)
    # ...and without the band they can be (the pre-Session-G behaviour)
    wide = simulate_survival(cand, avail0, plan, model, n_sims=40,
                             rng=np.random.default_rng(0), top_k=None)
    assert wide[deep].min() < 1.0


def test_choice_band_default_is_the_fit_contract():
    """Fit and every simulator must take their candidate set from the SAME object.

    Session G found 11.2 and 11.3 both simulating over the whole board against a top-40-estimated β.
    T15 turned the shared integer into a shared :class:`BandSpec` (it may now widen with depth), so
    this pins the object rather than the number — a band that can vary is exactly the kind of thing
    that drifts apart between fit and use.
    """
    import inspect

    from fantasy_quant.draft import availability
    from fantasy_quant.draft.personalities import USE_MODEL_BAND
    assert availability.CHOICE_TOP_K == CHOICE_TOP_K
    # the fit takes the module band by default ...
    assert inspect.signature(build_choice_frame).parameters["band"].default is None
    frame_band = inspect.signature(build_choice_frame).parameters["top_k"].default
    assert frame_band is None, "top_k must not shadow the band by default"
    # ... and the simulator reads the fitted model's own band rather than a constant of its own
    assert inspect.signature(make_opponent_pick_fn).parameters["top_k"].default is USE_MODEL_BAND
    assert BAND_SPEC.top_k(1, 10) == CHOICE_TOP_K, "shipped default is still the top-40"


def test_widening_band_grows_with_depth_and_clamps():
    """A widening band is a pure function of the pick number, identical for fit and simulation."""
    b = BandSpec(kind="widening", k0=40, growth=10, k_max=100)
    assert b.top_k(1, 10) == 40 and b.top_k(10, 10) == 40      # round 1
    assert b.top_k(11, 10) == 50                                # round 2
    assert b.top_k(141, 10) == 100                              # round 15, clamped at k_max
    assert BandSpec().top_k(1, 10) == BandSpec().top_k(141, 10) == CHOICE_TOP_K


def test_adp_spec_linear_reproduces_the_historical_feature_exactly():
    """The default spec must be a bit-identical no-op, or every pre-T15 number silently moves."""
    adp = np.array([1.0, 12.0, 50.0, 200.0])
    assert np.allclose(AdpSpec().feature(adp), adp / 50.0)
    assert np.allclose(AdpSpec().utility_per_pick(adp), 1.0 / 50.0)


def test_power_spec_width_law_matches_the_derivation():
    """``w_a ∝ 1/f'(a)``: a p=0.5 spec must make deviation width grow like ``a^0.5``.

    The arithmetic T15's fix rests on, so it is pinned rather than trusted — if the exponent
    convention were ever flipped the room would get *narrower* with depth, and every acceptance
    bar would move the wrong way while still looking like a modelling result.
    """
    spec = AdpSpec(kind="power", exponent=0.5)
    width = 1.0 / spec.utility_per_pick(np.array([25.0, 100.0]))
    assert width[1] / width[0] == pytest.approx((100.0 / 25.0) ** 0.5, rel=1e-9)
    # and the linear spec is flat in depth, which is the defect being fixed
    flat = 1.0 / AdpSpec().utility_per_pick(np.array([25.0, 100.0]))
    assert flat[0] == pytest.approx(flat[1])


def test_specs_round_trip_through_their_artifact_form():
    """Specs travel with β in the fitted JSON; a lossy round-trip silently restores defaults."""
    a, b = AdpSpec(kind="power", exponent=0.45), BandSpec(kind="widening", k0=40, growth=7.5)
    assert AdpSpec.from_dict(a.to_dict()) == a
    assert BandSpec.from_dict(b.to_dict()) == b
    assert AdpSpec.from_dict(None) == AdpSpec() and BandSpec.from_dict(None) == BandSpec()


def test_draft_blocks_match_scan():
    """T14: the cluster-bootstrap index blocks equal the per-draft scan they replace."""
    rng = np.random.default_rng(0)
    dow = np.sort(rng.integers(0, 40, 900))
    blocks = _draft_blocks(dow)
    assert set(blocks) == set(int(u) for u in np.unique(dow))
    for u in np.unique(dow):
        assert np.array_equal(blocks[int(u)], np.flatnonzero(dow == u))
    # a resampled replicate therefore selects exactly the same rows as the old concatenation
    pick = rng.choice(np.unique(dow), 40, replace=True)
    old = np.concatenate([np.flatnonzero(dow == u) for u in pick])
    new = np.concatenate([blocks[int(u)] for u in pick])
    assert np.array_equal(old, new)


def test_personalities_shape_utility():
    p = personalities()
    base = np.arange(len(ALL_FEATURES), dtype=float) + 1.0
    chalk = p["chalk"].adjusted_beta(list(ALL_FEATURES), base)
    # chalk zeroes every non-adp coefficient
    for i, c in enumerate(ALL_FEATURES):
        if c != "adp_s":
            assert chalk[i] == 0.0


def test_behavioral_opponent_produces_valid_full_draft():
    m = OpponentModel(list(ALL_FEATURES),
                      beta=np.array([-0.85, -0.3, -0.2, 0.4, 0.2, 0.07, 0.0, 0.4, 0.0, 0.3]))
    board = pd.DataFrame({
        "name": [f"P{i}" for i in range(120)],
        "position": (["RB", "WR", "QB", "TE"] * 30),
        "adp": np.arange(1, 121, dtype=float),
        "pos_rank": list(range(1, 121)),
    })
    opp = make_opponent_pick_fn(m, personalities()["zero_rb"])
    st = simulate_draft(board, n_teams=10, rounds=10, seed=3, opponent_pick_fn=opp)
    log = st.pick_log()
    assert len(log) == 100                          # full 10x10 draft completed
    assert log["player_key"].nunique() == 100       # no player drafted twice
