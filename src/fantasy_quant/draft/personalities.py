"""Phase 11.3 / 16.14 — realistic mock opponents with configurable personalities.

The behavioral opponent model (11.1) predicts the *average* manager. A realistic mock also wants
*heterogeneous* opponents — a chalk ADP-drafter, a zero-RB zealot, a wild reacher — so drafts you
practice against feel like a real room. A :class:`Personality` is a light, interpretable tilt on
the fitted β (scale/override a coefficient, add a round-dependent positional penalty, or heat up
the softmax); :func:`make_opponent_pick_fn` turns a ``(model, personality)`` pair into an
``opponent_pick_fn(state, team)`` that plugs straight into
:func:`~fantasy_quant.draft.simulator.simulate_draft`.

**16.14 — the risk/value tilts.** Until 16.13 a live board carried only ``adp``/``pos``, so the two
managers every real league actually has — the one chasing ceiling and the one buying floor — were
unbuildable: there was no ceiling or floor on the board to tilt on. With the board enriched
(:mod:`fantasy_quant.draft.enrichment`), ``signal_weights`` adds a linear bonus on those columns
and the **five headline personalities** ship:

    autopilot · balanced · upside_chaser · safe_floor · homer

Three properties make that bonus behave rather than run away:

* **Within-position z-scores.** ``q90`` lives on 100–300 points, ``boom_prob`` on [0, 1]. Weights
  would be unreadable magic constants on raw columns, so each signal is standardized *within
  position, across the live candidate pool* — a weight of ``+0.45`` means "+0.45 utility per
  standard deviation of that signal among the RBs actually on the clock". Standardizing within
  position also stops a risk tilt from doubling as a positional lean (QBs have the fattest ``q90``
  in raw points; that is a scoring artifact, not an upside opinion), and it cancels any *uniform*
  multiplicative bias in the underlying column — which matters, see T17.
* **A reach ceiling.** ``max_reach_picks`` caps the seat's **own opinion** at what the fitted model
  would pay to move a player that many ADP picks earlier, converted through the model's own
  ``β_adp_s`` exactly as :func:`~fantasy_quant.adp.hype_board.apply_hype` does. So a personality
  *prefers* its kind of player but will not reach an absurd distance for one, and when nothing on
  the board fits its taste the bonus is ≈ 0 and it quietly takes the best value available. That
  fallback is the requested behaviour, and it falls out of the design rather than being
  special-cased.
* **Capped means capped, leaned does not.** The ceiling covers the **player-specific discretionary**
  tilt this seat forms for itself — ``signal_weights`` and a homer's fandom excess. It deliberately
  does *not* cover β reshaping (``scale``/``override``) or ``early_pos_penalty``: "I don't take RBs
  early" and "I only follow ADP" are **strategies**, not reaches for a particular name, and capping
  them would silently neuter ``zero_rb`` and ``autopilot``. Nor does it cover the **shared 16.9
  narrative shock**, which is the room's story rather than this seat's opinion and carries its own
  fitted scale — 16.15 measured what folding it into the clip costs; see
  :func:`make_opponent_pick_fn`.

Scope note: Tier-B tilts (``fandom``, ``rookie``) only express when the board carries ``team`` /
``rookie``; the Tier-A tilts (``chalk``, ``zero_rb``, ``reacher``, positional leans) always express.
Before 16.13 nothing in the mock path supplied either column *or* passed ``fav``, so ``homer`` and
``rookie_hawk`` were silently inert — both are live now.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from fantasy_quant.draft.opponent_model import (
    _ADP_SCALE,
    SKILL_POSITIONS,
    OpponentModel,
)
from fantasy_quant.draft.opponent_model import (
    AdpSpec as _AdpSpec,
)

_NEED_TARGET = {"QB": 1, "RB": 4, "WR": 4, "TE": 1}


#: **Frozen measurement — the 95th percentile of realized human *reaching*, per round, in 10-team
#: ADP picks**, over the 1,144-draft FFC-boarded Sleeper corpus (2017–2024). Rounds 1–15.
#:
#: ★ This is the "hard per-round deviation ceiling at the corpus p95" 16.14R's done-when asks for,
#: and it is deliberately part of the **mechanism**, not only of the measurement: a *count* budget
#: ("three big reaches a draft") bounds how often, never how far, so without this the seat's third
#: allowed swing was a 78-pick reach that no human draft has ever contained. The two controls are
#: complementary and both are needed.
#:
#: ⚠ **Reach side only.** ``mock.reach_profile`` pools |drift| — reaches *and* falls — because that
#: is how T15's published corpus figures were computed, and at round 15 that p90 is 52 picks,
#: almost all of it elite players **falling**. A ceiling on how far a manager may *jump* cannot be
#: read off a number that is mostly about players sliding, and using it would license a reacher
#: three times wilder than any human.
#:
#: The shape is worth reading: reaching peaks in **round 5** (50 picks) and shrinks to 19 by round
#: 15 — a real drafter's big swings happen once the elite tier is gone and the board is flat, then
#: stop when there is nothing left to reach past.
CORPUS_REACH_P95: tuple[float, ...] = (14.6, 24.1, 33.9, 43.5, 50.0, 46.6, 46.7, 47.8,
                                       44.1, 39.1, 33.7, 30.8, 30.0, 27.1, 19.0)


def ceiling_only(window_mult: float = 1.0) -> ReachBudget:
    """A budget that is **only** the per-round corpus ceiling: no count tiers, no early clamp.

    ``window_mult`` scales it — 1.0 means "reaches as far as the 95th-percentile real manager and
    no further". This is the shape :data:`ROOM_CEILING` uses for every seat and the shape the value
    hawk's window uses; the count tiers are relaxed away because a *how far* control and a *how
    often* control are different objects and neither implies the other.
    """
    return ReachBudget(
        large_max=10 ** 6, large_from_round=1, medium_max=10 ** 6, medium_from_round=1,
        early_rounds=0, early_max_picks=np.inf,
        round_ceiling=tuple(float(window_mult) * x for x in CORPUS_REACH_P95),
    )


def unbounded_budget() -> ReachBudget:
    """No discipline at all — the pre-T25 behaviour of a seat with ``reach_budget=None``.

    ⚠ **Only for A/B controls.** ``reach_budget=None`` now means *inherit* :data:`ROOM_CEILING`, so
    a step that wants a genuinely unconstrained seat (``steps/phase16_14r_5_reacher.py`` measures
    the reacher against one) has to ask for it explicitly. Silently re-pointing those controls at
    the room ceiling would change what an already-run done-bar measured.
    """
    return ReachBudget(large_max=10 ** 6, large_from_round=1, medium_max=10 ** 6,
                       medium_from_round=1, early_rounds=0, early_max_picks=np.inf,
                       round_ceiling=None)


def value_hawk_budget(window_mult: float) -> ReachBudget:
    """The value hawk's reach window: ``window_mult`` x the realized human p95, per round.

    ★ **Stated as a multiple of what humans actually do**, so ``window_mult = 1.0`` means "reaches
    as far as the 95th-percentile real manager and no further" and the acceptance constraint
    ("realized reach p95 <= the corpus p95") is a *measured outcome* rather than an identity — a
    seat given a 1.25x ceiling may still land under the corpus p95 simply because its objective
    rarely wants to reach that far. That is what makes the step-7 sweep over
    ``{1.00, 1.15, 1.25}`` informative instead of circular.

    The count tiers are relaxed away: a value argmax does not "take three swings a draft", it takes
    the best available player inside its window at every pick, so the window *is* the whole control.
    """
    return ceiling_only(window_mult)


@dataclass(frozen=True)
class ReachBudget:
    """16.14R step 5b — how many big reaches a seat is allowed, and when (user spec, 2026-07-27).

    A real reacher does not reach uniformly. He takes two or three swings a draft, mostly after the
    early rounds have thinned the board, and he does not open with one. ``width_mult`` cannot say
    that: it is a *distributional* control, so a seat with a wide width reaches a little on every
    pick instead of a lot on a few. This is the shape control that goes with it.

    Tiers are in **ADP picks** of deviation (``adp − overall_pick``, positive = reaching):

    ``> large_picks``               a swing. ``large_max`` per draft, none before
                                    ``large_from_round``.
    ``medium_picks … large_picks``  a lean. ``medium_max`` per draft, none before
                                    ``medium_from_round``.
    ``<= medium_picks``             ordinary drafting, never counted or capped.

    Rounds ``1 … early_rounds`` are clamped to ``early_max_picks`` whatever the budget says —
    the top of the board is where a nonsense reach is most visible and most expensive.

    ★ **Stateful per seat, computed statelessly.** The budget depends on what this seat has
    already done, but ``make_opponent_pick_fn`` returns a pure softmax and the 9.5 win-prob policy
    runs whole drafts on a :meth:`~fantasy_quant.draft.simulator.DraftState.clone`. Carrying
    mutable per-seat memory alongside would mean ``clone`` has to deep-copy it or every rollout
    silently diverges — a bug that would surface as a modelling result, which is this repo's most
    expensive failure mode. So :meth:`used` re-derives the count from the draft log at every pick.
    It is O(picks so far), it is exactly reproducible under a seed, and it is correct on a clone by
    construction.

    ★ **Applied as a filter *before* utility**, the same class of object as ``BandSpec`` and T20's
    mandatory needs. A budget that worked by penalising utility would be traded off against a
    strong enough opinion, which is not what a budget is.
    """
    large_picks: float = 25.0
    large_max: int = 3
    large_from_round: int = 5
    medium_picks: float = 8.0
    medium_max: int = 5
    medium_from_round: int = 3
    early_rounds: int = 3
    early_max_picks: float = 8.0
    round_ceiling: tuple[float, ...] | None = CORPUS_REACH_P95

    def used(self, state, team: int) -> tuple[int, int]:
        """``(large, medium)`` reaches this seat has already spent, re-read from the draft log."""
        large = medium = 0
        for row in state.log:
            if row["team"] != team:
                continue
            d = float(row["adp"]) - float(row["overall_pick"])
            if d > self.large_picks:
                large += 1
            elif d > self.medium_picks:
                medium += 1
        return large, medium

    def cap(self, state, team: int) -> float:
        """The largest deviation, in ADP picks, this seat may make at the pick on the clock."""
        rnd = state.round()
        large, medium = self.used(state, team)
        if rnd >= self.large_from_round and large < self.large_max:
            allowed = np.inf
        elif rnd >= self.medium_from_round and medium < self.medium_max:
            allowed = self.large_picks
        else:
            allowed = self.medium_picks
        if rnd <= self.early_rounds:
            allowed = min(allowed, self.early_max_picks)
        if self.round_ceiling:
            # the count budget says how *often*; this says how *far*. Neither implies the other,
            # and without this the third permitted swing was a 78-pick reach (see CORPUS_REACH_P95).
            allowed = min(allowed, float(self.round_ceiling[min(rnd, len(self.round_ceiling)) - 1]))
        return float(allowed)


#: **T25 — the floor of discipline every seat inherits.** A seat whose ``reach_budget`` is ``None``
#: drafts under this: the corpus's own per-round p95 reach and nothing else.
#:
#: ★ **The asymmetry was the bug, not the budget.** Until 2026-07-28 a budget was attached to
#: ``reacher`` and ``value_hawk`` alone, so ``CORPUS_REACH_P95[0]`` = 14.6 picks bound the two seats
#: that had been *given* discipline and nothing bound ``balanced`` — which is **4 of 10** seats in
#: :data:`REALISTIC_ROOM`. The seat asked to be disciplined looked tamer than the seat representing
#: the average human, and the R1-3 ``pool_rank`` ordering inverted (reacher 4.94, balanced 6.36).
#:
#: ⚠ It is a **ceiling only** — no count tiers and no early clamp. The reacher's quiet opening
#: (``early_rounds=3``, ``early_max_picks=8.0``) is a deliberate spec, not a default to spread
#: around, and imposing it room-wide would flatten every seat into the same opening.
ROOM_CEILING: ReachBudget = ceiling_only()


def effective_budget(pers: Personality) -> ReachBudget:
    """This seat's budget: its own if it has one, else the room-wide :data:`ROOM_CEILING`."""
    return pers.reach_budget if pers.reach_budget is not None else ROOM_CEILING


#: Enriched board columns (16.13) a personality may weight in ``signal_weights``. Note
#: ``overall_rank`` is a **rank** — lower is better — so wanting good players means a *negative*
#: weight on it.
#:
#: ⚠ **Use ``upside``/``floor``/``durability``, not ``q90``/``q10``/``games_played_mean``, for a
#: ceiling-, floor- or durability-seeking manager.** Within position the raw columns are collinear
#: with the projected *level* (quantiles ~0.98; games-played +0.46…+0.90 once T17 was fixed), so
#: weighting them buys good players rather than shaped ones — and two personalities built that way
#: agree instead of opposing. :func:`~fantasy_quant.draft.enrichment.residual_shape` has the
#: measurement. The raw columns stay available because a *reporting* consumer legitimately wants
#: them.
#: ⚠⚠ **``boom_prob``/``bust_prob`` are stale by construction on a live board — do not weight
#: them (T22).** They are the *prior season's* realized weekly rates, where "prior" means
#: ``max(train_seasons)``, and ``train_seasons`` for a live season is ``DEV_SEASONS``, which ends at
#: **2022**. On the 2026 board they are the 2022 rates, and **292 of the 306 zeros are
#: ``fillna(0.0)``** — anyone absent in 2022 is recorded as never booming *and* never busting. Use
#: ``tail_risk`` (T19), which is built from the current quantiles. They stay listed because a
#: *reporting* consumer may legitimately want them, with the staleness stated.
#: 16.14R step 3 adds ``role_share``/``role_delta``/``td_regression`` — structural context a value
#: objective is blind to. Every seat's default weight on them is **0.0**; only the value hawk asks.
SIGNAL_COLS: tuple[str, ...] = ("boom_prob", "q90", "bust_prob", "q10", "games_played_mean",
                                "mean", "upside", "floor", "durability", "tail_risk", "vbd",
                                "overall_rank", "cos", "role_share", "role_delta", "td_regression")

#: Minimum members a position group needs before its z-scores mean anything. Below this (or at zero
#: variance) the group contributes 0 — no tilt, rather than a tilt built on one observation.
MIN_Z_GROUP: int = 3

#: Default reach ceilings, in **ADP picks**, for the three tilting headliners. Read them as "this
#: manager will happily take his kind of player up to N picks ahead of where the room would, and no
#: further" — roughly one to two rounds in a 10-team league. The upper bound is
#: :data:`~fantasy_quant.adp.hype_board.MAX_PICK_DELTA` (24), the largest claim the curated hype
#: board is allowed to make about a single player; the homer, who is the whole point of that board,
#: is allowed to spend all of it.
#:
#: These are behavioural constants, not fitted ones, and they were **measured, not guessed**: at a
#: 10-pick ceiling the tilts are real but not legible — over 8 seeds, ``upside_chaser`` and
#: ``safe_floor`` land within noise of ``balanced`` on every signal they weight, because a ±0.17
#: utility clip is small against a softmax over 40 candidates. At 18 the ordering separates cleanly
#: and stays there. If you lower them, expect the face-validity tests to go quiet before they go
#: red — an inert personality is the failure mode to watch for here, not a wrong one.
REACH_UPSIDE: float = 18.0
REACH_SAFE: float = 15.0
REACH_HOMER: float = 24.0

#: **The width half of the 16.14R contract, pulled forward into T15** (user decision 2026-07-27).
#: Multiples of the fitted average manager's deviation width; see ``Personality.width_mult``. Only
#: the *width* half is built here — ``signal_weights`` (the **direction** half) is untouched and
#: stays with the 16.14R session, whose three open questions are unsettled.
#:
#: ★ **These exist because step 0 measured a room with no moderate drafters**: 54.3 % of realized
#: human seats sit at ``pool_rank`` 2–8 and the simulated room put **2.2 %** there, being bimodal
#: between two ``autopilot`` seats at 1.28 and everything else past 11. Curvature alone fixes the
#: *depth profile* of deviation without spreading the *population* across it; that is what these do.
#:
#: The contract fixes autopilot 0 · safe ~0.8 · balanced 1.0 · reacher <=2.0. ``upside_chaser``,
#: ``homer`` and ``chalk`` are **declared judgments**, not fitted, placed to fill the 2–8 band
#: rather than to express a new belief about those seats: an upside chaser strays somewhat more than
#: the average manager, a homer slightly more, and ``chalk`` (an 11.3 library seat, not a headliner)
#: sits between ``autopilot`` and ``safe_floor`` where its cooled softmax already put it.
WIDTH_SAFE: float = 0.8
WIDTH_UPSIDE: float = 1.35
WIDTH_HOMER: float = 1.2
WIDTH_REACHER: float = 2.0


@dataclass(frozen=True)
class WidthCurve:
    """How far the room strays from the board **as a function of draft round** — T15's width law.

    ★ **Why this exists, measured.** Realized human reach width grows monotonically with depth:
    **2.87 ADP picks in round 1 to 27.1 in round 15** (1,144 FFC-boarded drafts). T15 first tried to
    produce that shape with curvature in ``adp_s`` alone, on the derivation that width in picks goes
    as ``a^(1-p)``. It does not work, and the measurement says why: the exponent that tightens the
    top of the board enough to pass the elite-fall gate (p=0.15) leaves the room **uniformly
    too narrow** — every round from 2 on lands at 0.94 -> 0.26x the corpus width, and the 16.9
    dispersion match goes from +8.8 % to **-53.6 %**. One knob, two ends, opposite requirements.

    The reason the derivation over-promises is **pool exhaustion**, which it ignores: ``a^(1-p)``
    assumes an unbounded local candidate pool, but by round 15 only ~30 boarded players remain and a
    seat physically cannot deviate 27 picks from a board that no longer has 27 picks of depth below
    it. Curvature therefore buys far less late width than the algebra implies, while costing full
    price at the top.

    So width by **depth** is separated from width by **seat** — the 16.14R contract stated
    exactly: ``width(round) x multiplier``. This class is the first factor and
    ``Personality.width_mult`` the second. Both act on ``β_adp_s`` (width ``∝ 1/|β_adp_s|``), so
    they compose multiplicatively and each means what it says in picks.

    ``gamma=0`` is a flat curve — the pre-T15 behaviour exactly, so nothing moves until a caller
    ships a fitted curve.

    ★ **``base`` (T24) is the third factor, and it exists because the curve is a *shape*.**
    ``width(1) == base``: the curve says how width grows with depth, ``base`` says how wide round 1
    is. They were one number while the only lever was depth; T24 needs to narrow the whole room and
    hand the deviation back **per player** through :func:`private_adp`, which is a different
    statement from "flatten the depth profile". ``base=1.0`` reproduces the committed curve exactly.
    """

    kind: str = "power"
    gamma: float = 0.0
    max_round: int = 15
    base: float = 1.0

    def __post_init__(self) -> None:
        if self.kind != "power":
            raise ValueError(f"unknown WidthCurve kind {self.kind!r}")
        if not 0.0 <= self.gamma <= 3.0:
            raise ValueError(f"implausible WidthCurve gamma {self.gamma}")
        if not 0.0 < self.base <= 5.0:
            raise ValueError(f"implausible WidthCurve base {self.base}")

    def width(self, rnd: int) -> float:
        """Width multiplier at ``rnd`` (1-based): ``base·round^gamma``, clamped past ``max_round``.
        """
        r = min(max(int(rnd), 1), int(self.max_round))
        return float(self.base) * float(r) ** float(self.gamma)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "gamma": float(self.gamma), "max_round": int(self.max_round),
                "base": float(self.base)}

    @classmethod
    def from_dict(cls, d: dict | None) -> WidthCurve:
        if not d:
            return WidthCurve()
        return cls(kind=str(d.get("kind", "power")), gamma=float(d.get("gamma", 0.0)),
                   max_round=int(d.get("max_round", 15)), base=float(d.get("base", 1.0)))


#: The shipped depth-width curve. Fitted by ``steps/t15_4_width_curve.py`` and, like `AdpSpec`, it
#: travels with the model rather than being edited by hand.
WIDTH_CURVE = WidthCurve()


# ==================================================================================================
# T24 — the per-seat private board: width per **player**, not only per round
# ==================================================================================================
#: How many of a player's own ``adp_stdev`` a seat's private opinion is worth, before the seat's
#: ``width_mult``. **Room-level, one scalar**, calibrated against the corpus law below rather than
#: set by eye; ``0.0`` reproduces the pre-T24 room bit-for-bit.
#:
#: ★ **The law it is calibrated against** (1,144 FFC-boarded human drafts / 157,349 picks):
#: **|drift| ≈ 2 × adp_stdev**, near-constant from stdev 1 to 12 (2.57 / 2.13 / 2.04 / 1.98 / 1.88
#: by band) and decaying above that only because the pool runs out — T15's pool-exhaustion finding
#: arriving from the other direction. Spearman(``adp_stdev``, |drift|) is **0.484** against
#: Spearman(round, |drift|) **0.535**, so board disagreement is nearly as strong as depth *and*
#: carries what depth cannot: **within rounds 1–3 the stdev terciles drift 2.11 / 3.33 / 8.91**, a
#: 4.2× spread no round-indexed curve can express.
#:
#: ★ **Why a private board and not another width knob.** A softmax has one width for every candidate
#: on the clock, so the only way a *flat* room reproduces late-round spread is to be too wide at the
#: top — which is exactly the objection: with the top few ADPs separated by less than the softmax's
#: own width, the consensus #1 and #6 are near-interchangeable and an elite lands past pick 4 21 %
#: of the time against a realized 12 %. Moving the dispersion into a per-player draw makes the room
#: narrow where the crowd agrees (Bijan, stdev 0.7) and wide where it does not (Jeanty, 2.5) without
#: hard-coding a tier.
PRIVATE_KAPPA: float = 0.0

#: Draws are clipped to ±this many sd. T24's own warning: the corpus far tail (p99 = pick 33 for an
#: ADP 1–2.5 player) is a **data question first** — a post-snapshot injury or a keeper/dynasty room,
#: not a manager's opinion — so the body is fitted and the tail is left alone rather than chased.
PRIVATE_CLIP: float = 3.0


def private_adp(board: pd.DataFrame, kappa: float, rng: np.random.Generator, *,
                clip: float = PRIVATE_CLIP) -> np.ndarray | None:
    """One seat's private view of the board: ``adp + κ·adp_stdev·ε``, ``ε ~ N(0,1)``.

    Drawn **once per seat per draft** (a manager holds one opinion for a whole draft, not a fresh
    one every pick) and **independently across seats** — the shared component of a draft's mood is
    16.9's narrative shock, which is a different object and already fitted; drawing a common
    component here would double-count it.

    Returns ``None`` when there is nothing to model — ``κ = 0``, or a board with no ``stdev``
    column (an ADP-only board carries no disagreement, so the seat simply reads the public one).
    Missing per-player values are median-filled, following ``adp/drift_model.py``: an unknown stdev
    is an *unknown*, and filling it with 0 would fabricate a consensus this board never expressed.

    ⚠ **Aligned positionally to ``board`` rows**, matching the ``level_z`` convention in
    :func:`make_opponent_pick_fn` — the simulator's boards carry a 0..n-1 index, so a pool's index
    labels are row positions.
    """
    if not kappa or "stdev" not in board.columns:
        return None
    adp = pd.to_numeric(board["adp"], errors="coerce").to_numpy(float)
    sd = pd.to_numeric(board["stdev"], errors="coerce")
    med = float(sd.median()) if np.isfinite(sd.median()) else 0.0
    sd = sd.fillna(med).to_numpy(float)
    eps = np.clip(rng.standard_normal(len(board)), -abs(clip), abs(clip))
    return adp + float(kappa) * sd * eps


def pos_z(values, pos) -> np.ndarray:
    """Standardize ``values`` within each position group; NaN and degenerate groups give 0.

    0 is the honest fill for a missing signal — it is the group mean, i.e. "this player gives me no
    reason to move", which is the same marginalization
    :meth:`~fantasy_quant.draft.opponent_model.OpponentModel.candidate_utility` already applies to
    unknown Tier-B context. Rookies and team defenses reach here as NaN by design (Phase 5 has no
    distribution for them) and must not be read as *bad*, only as *unknown*.
    """
    v = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(float)
    p = np.asarray(pos)
    z = np.zeros(len(v), float)
    for g in np.unique(p):
        m = p == g
        col = v[m]
        ok = np.isfinite(col)
        if int(ok.sum()) < MIN_Z_GROUP:
            continue
        sd = float(col[ok].std())
        if not np.isfinite(sd) or sd <= 0:
            continue
        zz = np.zeros(len(col), float)
        zz[ok] = (col[ok] - float(col[ok].mean())) / sd
        z[m] = zz
    return z


def signal_bonus(pool: pd.DataFrame, weights: dict) -> np.ndarray:
    """The ``signal_weights`` utility bonus for a candidate pool (see the module note on scaling).

    Signals the board does not carry are skipped, so the same personality runs unchanged against an
    ADP-only board — it simply has nothing to tilt on and drafts like the fitted average manager.
    """
    if not weights:
        return np.zeros(len(pool), float)
    pos = pool["pos"].to_numpy()
    bonus = np.zeros(len(pool), float)
    for name, w in weights.items():
        if not w or name not in pool.columns:
            continue
        bonus = bonus + float(w) * pos_z(pool[name], pos)
    return bonus


@dataclass(frozen=True)
class Personality:
    """A named tilt on a fitted opponent model.

    ``scale`` multiplies and ``override`` replaces individual β entries; ``temperature`` heats (>1,
    more random/reachy) or cools (<1, chalkier) the choice softmax; ``early_pos_penalty`` subtracts
    utility from a position in early rounds.

    16.14 adds the risk/value half:

    ``signal_weights``   utility per within-position sd of an enriched board column
                         (:data:`SIGNAL_COLS`); absent columns are skipped.
    ``hype_gain``        multiplier on the shared per-draft narrative/hype offset — how much *more*
                         than the average manager this seat chases the story. ``0`` ignores it
                         entirely, which is what an autopick bot does.
    ``fav_teams``        teams the fitted ``fandom`` feature fires on for this seat. Empty (the
                         default) leaves ``fandom`` at 0, exactly as before 16.14.
    ``max_reach_picks``  ceiling on this seat's **own opinion** (``signal_weights`` + the ``fandom``
                         excess), in ADP picks; ``None`` = uncapped. It does **not** bound the
                         shared narrative shock, which 16.9 scales for itself — see
                         :func:`make_opponent_pick_fn`.
    ``sample``           ``False`` makes this personality deterministic (argmax) wherever it is
                         used, so a seat carries its own determinism instead of the caller having to
                         remember. ``None`` defers to the caller.

    **T15 / 16.14R — the width half of the contract:**

    ``level_floor``      within-position z of the projected ``mean`` below which this seat applies
                         ``level_floor_penalty`` utility. ``None`` = off. **16.14R step 4** — a
                         *minimum projected level*, so that "reliably useless" cannot win a
                         downside contest. It is deliberately **not** expressible as a
                         ``signal_weights`` entry: a linear weight on ``mean`` is a quality tilt
                         that trades off against everything else, whereas this is a **threshold**
                         that says a player below it is not a candidate for *this* manager however
                         safe he looks. Applied inside the reach ceiling, since declining to draft
                         a replacement-level player is an opinion like any other.

    ``width_mult``       how far this seat strays from the board, as a multiple of the fitted
                         average manager. Implemented as ``β_adp_s / width_mult``, because the
                         derived width law says deviation width in ADP picks is ``∝ 1/|β_adp_s|`` —
                         so a multiplier here means exactly what it says in picks, **at every board
                         depth**, once the ADP term carries curvature. ``1.0`` = the fitted average
                         (``balanced``, unchanged); ``0`` = deterministic best-available.

    ★ **Why this replaces ``max_reach_picks`` as the primary reach control** (T15, measured): a
    single pick-count ceiling is wrong at one end by construction, because realized human reach
    width *grows* with depth (2.9 picks in round 1 to 27.1 in round 15). A multiplier on the width
    *law* is depth-correct by construction. ``max_reach_picks`` is kept — it still bounds a seat's
    own **opinion** (signals + fandom excess), which is a different quantity — but it is no longer
    the thing that decides how far a seat strays from ADP.
    """
    name: str
    scale: dict = field(default_factory=dict)
    override: dict = field(default_factory=dict)
    temperature: float = 1.0
    early_pos_penalty: dict = field(default_factory=dict)   # pos -> utility penalty
    early_rounds: int = 4
    signal_weights: dict = field(default_factory=dict)
    hype_gain: float = 1.0
    fav_teams: tuple[str, ...] = ()
    max_reach_picks: float | None = None
    sample: bool | None = None
    width_mult: float = 1.0
    level_floor: float | None = None
    level_floor_penalty: float = 1.0
    #: This seat's *how far / how often* budget. ``None`` means **inherit** :data:`ROOM_CEILING`
    #: (T25) — it does **not** mean unconstrained; ask for :func:`unbounded_budget` if you want
    #: that, which only an A/B control should.
    reach_budget: ReachBudget | None = None
    objective: str = "behavioral"
    context_weights: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        unknown = set(self.signal_weights) - set(SIGNAL_COLS)
        if unknown:
            raise ValueError(f"{self.name}: unknown signal_weights {sorted(unknown)} — "
                             f"a typo here fails silently forever, so it fails loudly here. "
                             f"Known signals: {list(SIGNAL_COLS)}")

    def adjusted_beta(self, feature_cols, base_beta) -> np.ndarray:
        """This seat's β: ``scale``/``override`` per feature, then the ``width_mult`` on ``adp_s``.

        ``width_mult`` divides the ADP coefficient (flatter ADP term = strays further). It is
        applied *after* ``scale``/``override`` so a personality that explicitly overrides ``adp_s``
        still gets its width honoured. ``width_mult <= 0`` means "no width at all" — the β would be
        infinite, so it is left untouched and the seat is expected to carry ``sample=False``
        (``autopilot`` does); an asserting guard would fire on a legal, meaningful configuration.
        """
        b = np.asarray(base_beta, float).copy()
        for i, c in enumerate(feature_cols):
            if c in self.scale:
                b[i] *= self.scale[c]
            if c in self.override:
                b[i] = self.override[c]
        m = float(self.width_mult)
        if m > 0 and m != 1.0 and "adp_s" in feature_cols:
            b[list(feature_cols).index("adp_s")] /= m
        return b

    def reach_cap(self, beta_adp_s: float, *, adp_spec=None, at_adp: float = _ADP_SCALE
                  ) -> float | None:
        """``max_reach_picks`` in utility units, via the model's own ADP coefficient.

        The same conversion :func:`~fantasy_quant.adp.hype_board.apply_hype` uses, and for the same
        reason: a ceiling stated in picks means the same thing to the simulator as it does to the
        human who set it, and it re-derives itself automatically if 11.1 is ever refit.

        Bounds the seat's own opinion only. A shared story can still carry a seat past this ceiling,
        which is the point of a story — see :func:`make_opponent_pick_fn`.

        ⚠ **T15: picks -> utility is depth-dependent once ``adp_s`` carries curvature**, so the
        conversion needs the board position it is being applied at. ``at_adp`` is where the ceiling
        is evaluated; the default reproduces the historical constant exactly under a linear spec.
        This is a scalar cap on a whole candidate pool, so one representative depth is the honest
        approximation — a per-candidate cap would make the ceiling mean different things to the two
        ends of the same pool.
        """
        if self.max_reach_picks is None:
            return None
        spec = adp_spec if adp_spec is not None else _AdpSpec()
        per_pick = float(np.asarray(spec.utility_per_pick(at_adp)).reshape(-1)[0])
        return abs(float(beta_adp_s)) * float(self.max_reach_picks) * per_pick


# the five headliners, plus the 11.3 library extras -------------------------------------------
#: The 16.14 headline room, in the order a user meets them.
HEADLINERS: tuple[str, ...] = ("autopilot", "balanced", "upside_chaser", "safe_floor", "homer")


def personalities() -> dict[str, Personality]:
    """The shipped roster: the five 16.14 headliners first, then the 11.3 library extras."""
    zero_out = {c: 0.0 for c in ("is_RB", "is_WR", "is_TE", "is_QB", "pos_run3",
                                 "mgr_lean", "rookie", "fandom", "need")}
    return {
        # -- the five headliners (16.14) --------------------------------------------------------
        # Sleeper's autopick: no opinions, no story, no noise — the best remaining name on the list.
        # Roster legality still comes from `draftable_pool`, which is what the real autopicker does.
        "autopilot": Personality("autopilot", override=zero_out, hype_gain=0.0, sample=False,
                                 max_reach_picks=0.0, width_mult=0.0),
        # the fitted average human — the anchor everything else is a deviation from.
        "balanced": Personality("balanced"),
        # ceiling over floor: wants the top end of the cone and the players with a story attached,
        # tolerates the bust risk that comes with it, and runs a hot softmax (he talks himself into
        # things). `rookie` rides β rather than signal_weights — liking rookies is a lean, not a
        # reach for one name.
        "upside_chaser": Personality(
            "upside_chaser",
            scale={"rookie": 2.0},
            # T19/T22: `boom_prob` was 2022's realized rate with 65 % manufactured zeros — the
            # ceiling-chaser's second weight was a stale column, not a signal. `tail_risk` is the
            # same idea on current quantiles, and *positive* here on purpose: for a manager
            # chasing ceiling, wide is the point (the 15.2 best-ball finding, "variance is GOOD",
            # from the other side of the same board).
            signal_weights={"upside": 0.45, "tail_risk": 0.35, "cos": 0.20},
            temperature=1.3, hype_gain=1.5, max_reach_picks=REACH_UPSIDE,
            width_mult=WIDTH_UPSIDE),
        # floor over ceiling: buys the tenth percentile, actively avoids the bust tail, and drafts
        # chalkier than the room (a cooled softmax) because certainty is the whole point.
        #
        # ★ The durability weight is on `durability`, NOT `games_played_mean`, and what it can
        # achieve is bounded — both facts are measured (Session H2).
        # (1) While T17 was live, `games_played_mean` held four cohort constants; standardized
        #     within position that is a draft-capital indicator, so the weight bought *capital*
        #     and every room read +0.67 on it alike. Fixing T17 made it a real forecast and, in
        #     the same move, a level proxy (+0.46…+0.90 with `mean` within position) — so the raw
        #     column had to be swapped for its level-residualized twin. Third instance of the
        #     16.14 lesson, this time arriving through an upstream data fix rather than new code.
        # (2) `durability` is **−0.34 against `floor`** and +0.23 against `bust_prob` on the 2026
        #     board (−0.28 inside the hazard group, so not a cohort artifact). At a fixed level the
        #     board says floor and availability point in OPPOSITE directions. The weight still
        #     earns its keep — turning it on gains a stable **+0.05** durability z (12/40/80
        #     drafts) and costs ~0.02 of floor — but it cannot make this manager an *above-average*
        #     durability buyer: his gap to `balanced` is +0.010 / −0.001 / −0.009 as the draft
        #     count grows, i.e. noise around zero. The done-bar therefore A/Bs the weight against
        #     itself-off rather than against `balanced`; see `steps/phase16_13_personalities.py`.
        # ★ 16.14R step 4 — the objective is **lowest downside**, not *highest floor*.
        #
        # The user's objection to this seat in the 2x5 mock was that it drafted boom-or-bust
        # players (Zay Flowers, a post-injury Malik Nabers, the rookie Carnell Tate, Quentin
        # Johnston, Jaydon Blue). Two-thirds of that was T19 — the board's `floor` column was
        # inverted at depth, so the seat drafted exactly what it was told was safest — but
        # repairing the input does not by itself make the seat *risk-averse*, because "highest
        # floor" and "lowest downside" are different objectives. This is the second half:
        #
        #   `floor`      +  the repaired retention signal (T19)
        #   `tail_risk`  -  an explicit penalty on the q90-q10 spread. A wide outcome is what
        #                   boom-or-bust *is*; a manager who wants certainty pays to avoid it,
        #                   and this is the only weight that prices width directly.
        #   `rookie`     -  via `override`, not `scale`: the fitted beta is +0.020, so scaling
        #                   cannot reach a meaningful negative and would silently do nothing.
        #                   A rookie has no NFL floor to buy, whatever his projection says.
        #   `durability` +  availability net of level (T17), the closest thing the frozen stack
        #                   has to an injury-return penalty — a player the injury model expects to
        #                   miss time reads low here whether or not anyone labelled the injury.
        #   `level_floor`   and the guard that makes the whole thing honest: without a minimum
        #                   projected level, "lowest downside" is won by a player with no upside,
        #                   no downside and no role. Reliably useless must not beat solid.
        "safe_floor": Personality(
            "safe_floor",
            override={"rookie": -0.35},
            signal_weights={"floor": 0.45, "durability": 0.30, "tail_risk": -0.40},
            level_floor=-0.60, level_floor_penalty=0.9,
            temperature=0.8, hype_gain=0.5, max_reach_picks=REACH_SAFE,
            width_mult=WIDTH_SAFE),
        # the narrative seat, and the channel 16.15 routes the 16.9 shock through. `fav_teams` is
        # empty by default: set it and he reaches for his team, leave it and he is a pure
        # story-chaser (hype board + changed situations). The ceiling holds on everything he thinks
        # for himself, so a room with no hyped or newly-relocated player on the clock gets a normal
        # pick, not a tantrum — but a loud enough story can carry him past it, which is what makes
        # him the seat the 16.9 shock is worth routing through at all (see `make_opponent_pick_fn`).
        "homer": Personality("homer", scale={"fandom": 2.5},
                             signal_weights={"cos": 0.35}, hype_gain=2.5,
                             max_reach_picks=REACH_HOMER, width_mult=WIDTH_HOMER),
        # -- 11.3 library extras (unchanged) ----------------------------------------------------
        # ★ 16.14R step 6 — the value hawk REPLACES the homer (reversing the 2026-07-23 cut).
        # Not a `signal_weights` seat: see `make_value_hawk_pick_fn` for why one cannot work.
        # Its reach window is a multiple of the realized human p95 (`window_mult`, swept in step 7);
        # `homer`'s `fandom` scaling stays fitted-but-unused rather than deleted.
        "value_hawk": Personality(
            "value_hawk",
            objective="portfolio_ce",
            context_weights=dict(DEFAULT_CONTEXT_WEIGHTS),
            reach_budget=value_hawk_budget(1.0),
            sample=False, hype_gain=0.0, width_mult=1.0),
        "chalk": Personality("chalk", override=zero_out, temperature=0.6, width_mult=0.55),
        "zero_rb": Personality("zero_rb", early_pos_penalty={"RB": 2.5}),
        # ★ 16.14R step 5 — DIRECTION first, then the budget.
        #
        # The user's objection was that this seat's reaches "are nonsensical and have no basis",
        # and the definition said exactly that: `Personality("reacher", temperature=2.2,
        # width_mult=WIDTH_REACHER)` — width with **no `signal_weights` at all**. A hot softmax over
        # a widening band with zero opinion attached is not a reacher, it is noise with a name, and
        # it measured as noise (mean `pool_rank` 20.5 against a corpus p90 of 13.1).
        #
        # A reacher that reaches **for something** is most of the fix, so the direction comes first
        # and the budget second — a budget over directed reaching is a different object from a
        # budget over noise, and capping the second one just makes quieter noise. The channels were
        # already assigned to this seat by 16.14R; they had simply never been wired:
        #   rookie  via `override` (fitted beta +0.020 — `scale` cannot reach anything meaningful)
        #   cos     the 16.5 change-of-situation loudness, inherited from the retired homer
        #   hype    the 16.10 curated board + the 16.9 per-draft narrative shock (`hype_gain`)
        # `tail_risk` positive because a reacher is buying the wide outcome, not the safe one.
        "reacher": Personality(
            "reacher",
            override={"rookie": 0.45},
            signal_weights={"cos": 0.35, "upside": 0.25, "tail_risk": 0.20},
            hype_gain=2.5, temperature=2.2, width_mult=WIDTH_REACHER,
            reach_budget=ReachBudget()),
        "rookie_hawk": Personality("rookie_hawk", scale={"rookie": 3.0}),
    }


#: Sentinel for "take the candidate set from the fitted model's own :class:`BandSpec`" — the T15
#: default. An explicit ``top_k=<int>`` still pins a fixed set and ``top_k=None`` still means the
#: whole board (kept only for the Session-G comparison that measured what ignoring the band costs).
USE_MODEL_BAND = "model-band"


def make_opponent_pick_fn(model: OpponentModel, personality: Personality | None = None, *,
                          rng: np.random.Generator | None = None, sample: bool | None = None,
                          top_k: int | None | str = USE_MODEL_BAND,
                          hype: np.ndarray | None = None,
                          width_curve: WidthCurve | None = None,
                          kappa: float | None = None):
    """Build an ``opponent_pick_fn(state, team) -> board_label`` from a fitted model + personality.

    Draws from the model's choice softmax over the team's cap-respecting available pool (so rosters
    stay realistic). ``sample=False`` forces determinism (argmax) and ``sample=None`` (the default)
    lets the personality decide via :attr:`Personality.sample`, defaulting to sampling. ``rng``
    defaults to the draft state's own generator so a seeded draft stays reproducible.

    ``top_k`` narrows each pick to the top-``k`` still-available players by ADP — **the candidate
    set the model was fit on** (:data:`~fantasy_quant.draft.opponent_model.CHOICE_TOP_K`). Session G
    found this missing, which let a top-40-estimated β spread probability across the whole board
    and inflated simulated draft-slot dispersion by 59 %; ``top_k=None`` restores that behaviour for
    comparison only.

    ``hype`` is the Phase-16.9 narrative shock (or a 16.10 curated board offset): a per-board-row
    utility offset, indexed by board label, **drawn once per draft**
    (:meth:`~fantasy_quant.adp.narrative.NarrativeShock.draw`) and passed to every opponent in that
    draft, so a hyped player goes early *consistently within a room* rather than having his early
    picks averaged away by independent per-seat noise. Each seat scales it by its own
    ``hype_gain``, which is how 16.15 routes a shock through the seats that would actually chase it.

    ★ **The shock is applied OUTSIDE ``max_reach_picks``, and that separation is load-bearing**
    (measured in 16.15, Session H2). Folded into the same capped tilt — the shipped H1 build — the
    ceiling swallowed it for precisely the seats built to chase a story: ``homer``'s tilt hit the
    clip on **90 %** of candidates with only **17 %** of the shock's variation surviving,
    ``upside_chaser`` 87 % / 22 %, while ``balanced`` and ``reacher`` (``max_reach_picks=None``)
    expressed **100 %** of it. The story routed itself to the seats with no ceiling — the exact
    inverse of the substep's claim — and the room-level done-bar still passed, because the
    autopickers' share of hyped players *falls* when the channel opens (they get sniped by the
    uncapped seats), which satisfies a chasers-minus-autopickers gap for the wrong reason.
    Separating them takes routing from Spearman **+0.52 to +0.95** against seat gain.

    The justification is the one ``normalized_hype_gains`` already runs on: 16.9 fitted the shock's
    size against realized draft-slot dispersion with the draw applied **uniformly and uncapped** —
    the reach ceiling is a 16.14 concept that did not exist yet — so passing it through a 16.14 clip
    is using a fitted parameter outside its estimation conditions. *A coefficient is not
    transportable without its controls*, for the third time in this phase. The cost, stated plainly:
    ``max_reach_picks`` no longer bounds a seat's **total** reach when a big story is on the board.
    It bounds his own opinion, which is what a reach ceiling was always meant to mean.
    """
    pers = personality or personalities()["balanced"]
    cols = list(model.feature_cols)
    base_beta = np.asarray(model.beta, float)
    beta = pers.adjusted_beta(cols, base_beta)
    adj = OpponentModel(cols, beta=beta)

    fav = set(pers.fav_teams) or None
    # the fandom *excess* over the fitted β is discretionary (it is this seat reaching for his own
    # team), so it is lifted out of the β utility and into the capped tilt below.
    j_fandom = cols.index("fandom") if (fav and "fandom" in cols) else None
    d_fandom = float(beta[j_fandom] - base_beta[j_fandom]) if j_fandom is not None else 0.0
    spec = getattr(model, "adp_spec", None)
    cap = (pers.reach_cap(base_beta[cols.index("adp_s")], adp_spec=spec)
           if "adp_s" in cols else None)
    draw = sample if sample is not None else (True if pers.sample is None else pers.sample)
    # T15: the candidate set is the fitted model's own band, which may widen with board depth.
    # `top_k` still overrides it (a caller asking for a fixed set gets one) and `top_k=None` still
    # means "the whole board", the pre-Session-G behaviour kept only for the comparison.
    band = getattr(model, "band", None) if top_k is USE_MODEL_BAND else None
    fixed_k = None if top_k is USE_MODEL_BAND else top_k
    # T15's depth-width law. Applied to `adp_s` alone and re-derived per pick, so it widens the room
    # at depth without touching what any seat thinks about a player. `gamma=0` is a no-op.
    budget = effective_budget(pers)
    curve = width_curve if width_curve is not None else getattr(model, "width_curve", WIDTH_CURVE)
    j_adp = cols.index("adp_s") if "adp_s" in cols else None
    b_adp = float(beta[j_adp]) if j_adp is not None else 0.0
    # T24 — this seat's private board, MEASURED HARMFUL and shipped OFF (κ=0); see `private_adp`.
    # `width_mult` is the seat's whole width character (autopilot 0, chalk 0.55, balanced 1.0,
    # reacher 2.0), so scaling by it makes κ one **room-level** number and gives autopilot κ=0 for
    # free. κ travels on the model beside the width curve; an explicit `kappa=` still wins, which is
    # what the sweep and the A/B controls use.
    kappa_room = (float(getattr(model, "private_kappa", PRIVATE_KAPPA)) if kappa is None
                  else float(kappa))
    kappa_seat = kappa_room * float(pers.width_mult)
    #: board-wide within-position level z for `level_floor`, computed once (see the note at use).
    level_z: np.ndarray | None = None
    #: this seat's private ADP, and the state it was drawn for — held by identity so a *new* draft
    #: (or a 9.5 rollout `clone`) redraws, while every pick inside one draft sees the same opinion.
    priv: np.ndarray | None = None
    priv_state = None

    def pick(state, team) -> int:
        nonlocal level_z, priv, priv_state
        if level_z is None and pers.level_floor is not None and "mean" in state.board.columns:
            # once per draft, over the whole board — see the note where it is applied
            level_z = np.zeros(len(state.board), float)
            level_z[:] = pos_z(state.board["mean"], state.board["pos"].to_numpy())
        if kappa_seat and priv_state is not state:
            priv_state = state
            priv = private_adp(state.board, kappa_seat, rng or state.rng)
        pool = state.draftable_pool(team)
        # T21 — the choice-set contract's *position* half. β was fit under `skill_only=True`, so
        # the simulation must offer the same four positions. Applied AFTER `draftable_pool` and
        # only when it leaves something: when T20's mandatory-needs filter has already restricted
        # the pool to K/DST, that restriction wins and this is a no-op. The hard filter completes
        # the roster; the choice model never sees a position it was not estimated on.
        skill = pool[pool["pos"].isin(SKILL_POSITIONS)]
        if not skill.empty:
            pool = skill
        # 16.14R step 5b — the reach budget, a hard filter before utility (see `ReachBudget`).
        # Kept ahead of the band so the budget bounds the *candidate set* rather than fighting the
        # softmax, and always leaves the least-reachy candidate so a draft can never stall.
        # T25: every seat has one — a seat without its own inherits `ROOM_CEILING`.
        allowed = budget.cap(state, team)
        if np.isfinite(allowed):
            dev = pool["adp"].to_numpy(float) - float(state.overall_pick)
            within = pool[dev <= allowed]
            pool = within if not within.empty else pool.nsmallest(1, "adp")
        k = (band.top_k(state.overall_pick, state.n_teams) if band is not None else fixed_k)
        if k is not None and len(pool) > k:
            pool = pool.nsmallest(k, "adp")
        cand = pool.rename(columns={})[["adp", "pos"]].copy()
        # T24 — from here down the seat reads its **own** board. Deliberately after the band and the
        # reach budget, which stay on the public ADP: the budget is T25's room-wide discipline and
        # `CORPUS_REACH_P95` is measured in *public* picks, so a private opinion must not be a way
        # around it, and the band is an estimation condition β was fit under. A private board
        # reorders the seat's preferences **inside** the candidate set it was always allowed.
        if priv is not None:
            cand["adp"] = priv[pool.index.to_numpy()]
        if "team" in pool.columns:
            cand["team"] = pool["team"]
        if "rookie" in pool.columns:
            cand["rookie"] = pool["rookie"]
        # Tier-B live context: positional run (last 3 picks) + this team's roster need
        recent = [r["pos"] for r in state.log[-3:]] if state.log else []
        rp: dict[str, int] = {}
        for p in recent:
            rp[p] = rp.get(p, 0) + 1
        counts = state.roster_counts(team)
        need = {pp: max(0.0, _NEED_TARGET.get(pp, 0) - counts.get(pp, 0))
                for pp in ("QB", "RB", "WR", "TE")}
        X = adj.candidate_matrix(cand, recent_pos=rp, need=need, fav=fav)
        u = X @ adj.beta
        # widen with depth: beta_adp_s / width(round). Added as a correction to the already-computed
        # utility rather than by rebuilding beta, so the hot path stays one matmul.
        if j_adp is not None and curve.gamma:
            w = curve.width(state.round())
            if w != 1.0:
                u = u + X[:, j_adp] * b_adp * (1.0 / w - 1.0)

        # -- the discretionary tilt: this seat's OWN opinion (signals + fandom excess), capped ---
        tilt = np.zeros(len(pool), float)
        if j_fandom is not None and d_fandom:
            excess = X[:, j_fandom] * d_fandom
            u = u - excess
            tilt = tilt + excess
        if pers.signal_weights:
            tilt = tilt + signal_bonus(pool, pers.signal_weights)
        # 16.14R step 4 — the minimum projected level. A threshold, not a weight: it fires only
        # below `level_floor` and is flat above it, so it cannot be traded off against a very
        # attractive floor the way a linear `mean` weight would be.
        #
        # ⚠ The z is taken over the **whole board** within position, not over the candidate pool.
        # Pool-relative was the first implementation and it is wrong in a way that measured as
        # *inert*: inside a 40-player ADP band the worst candidate is z ~ -1.5 whoever he is, so a
        # band-relative floor fires on somebody at every pick and is just a level tilt in disguise
        # — it moved nothing because the ADP term was already declining those players. Board-wide,
        # "below -0.6 sd of all RBs" means genuinely replacement-level, which is a fact about the
        # player rather than about who happens to be on the clock beside him.
        if level_z is not None:
            tilt = tilt - pers.level_floor_penalty * (
                level_z[pool.index.to_numpy()] < pers.level_floor)
        if cap is not None:
            tilt = np.clip(tilt, -cap, cap)

        # -- the shared narrative shock, deliberately OUTSIDE the ceiling (16.15) ---------------
        # The same draw for every seat in this draft — that shared component is the phase.
        # It is added after the clip, not into it; see `make_opponent_pick_fn`'s docstring for the
        # measurement that forced this apart.
        if hype is not None and pers.hype_gain:
            tilt = tilt + pers.hype_gain * np.asarray(hype, float)[pool.index.to_numpy()]
        u = u + tilt

        # -- structural strategy, deliberately uncapped: a lean is not a reach ------------------
        if pers.early_pos_penalty and state.round() <= pers.early_rounds:
            pos = cand["pos"].to_numpy()
            for pp, pen in pers.early_pos_penalty.items():
                u = u - pen * (pos == pp)
        u = u / max(pers.temperature, 1e-3)
        u = u - u.max()
        pr = np.exp(u)
        pr = pr / pr.sum()
        g = rng or state.rng
        j = int(g.choice(len(pool), p=pr)) if draw else int(np.argmax(pr))
        return int(pool.index[j])

    return pick


# ==================================================================================================
# 16.14R step 6 — the value hawk: a bounded-window portfolio-CE argmax, not a signal_weights tilt
# ==================================================================================================
#: Board context the value hawk prices, in **utility per within-neighbourhood sd**, negative =
#: avoid. These are the three blind spots step 3 put on the board; see
#: :data:`~fantasy_quant.draft.enrichment.CONTEXT_COLS`.
DEFAULT_CONTEXT_WEIGHTS: dict[str, float] = {
    "role_share": 0.30,        # own your backfield — a contested role is a discount, not a bonus
    "role_delta": 0.25,        # the signed situation change `cos` could never express
    "td_regression": -0.30,    # last year's touchdown luck is next year's regression
}


def _local_z(values, key, pos, *, window: int = 24) -> np.ndarray:
    """Within-position, **neighbourhood-local** z of a board column (see the note below).

    ★ The context columns are partly a level restatement — ``corr(role_share, vbd)`` is +0.88 RB /
    +0.67 WR and ``corr(td_regression, vbd)`` +0.63 RB — so a flat within-position z would let the
    value hawk pay twice for the same fact and, worse, would make "avoid TD regression" a tilt away
    from good players. Standardizing against a player's **ADP neighbours** asks the question that
    is actually wanted: *more contested / luckier than the players going around him*. Same
    construction as the T19 shape signals, for the same reason, one layer along.
    """
    v = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(float)
    k = pd.to_numeric(pd.Series(key), errors="coerce").to_numpy(float)
    p = np.asarray(pos)
    out = np.zeros(len(v), float)
    for g in np.unique(p):
        idx = np.flatnonzero((p == g) & np.isfinite(v) & np.isfinite(k))
        if len(idx) < MIN_Z_GROUP:
            continue
        order = idx[np.argsort(k[idx], kind="stable")]
        vv = v[order]
        n = len(order)
        w = max(MIN_Z_GROUP, min(int(window), int(n * 0.5)))
        for i in range(n):
            nb = vv[max(0, i - w):min(n, i + w + 1)]
            sd = float(nb.std())
            out[order[i]] = 0.0 if sd <= 0 else (vv[i] - float(nb.mean())) / sd
    return out


def make_value_hawk_pick_fn(personality: Personality, risk, *, n_teams: int = 10):
    """``pick(state, team)`` for a seat that drafts the **best available portfolio value**.

    ★ **Why this cannot be a ``signal_weights`` personality, measured rather than argued.**
    ``signal_bonus`` z-scores *within position*, and within position ``corr(vbd, adp)`` is
    **−0.955 RB / −0.933 WR / −0.907 TE / −0.859 QB** — so ``pos_z(vbd)`` throws away the only
    content ``vbd`` has that ADP does not, namely the **cross-position** comparison, and what
    survives is ADP with a sign flip. Built that way in the 2x5 mock the seat gained +0.065 vbd-z
    over ``balanced`` and finished **5.5 / 10**, behind ``safe_floor``: a chalk tilt with extra
    width. The objective has to be **roster-level**, and the repo already has one.

    So this is the **Phase-9 greedy in an opponent seat**: :meth:`RiskModel.effective_rank` scores
    each candidate by its *marginal* contribution to portfolio CE — value over replacement, minus
    ``2λσ`` against the same-team covariance this roster already carries, plus the 9.1/9.4 scarcity
    urgency. It is the same code the user's own optimizer runs, pointed at somebody else's roster,
    which is exactly what "the manager who always takes the best value on the board" means.

    Two things bound it, and both are the session's own rules:

    * a **reach window** (``personality.reach_budget``) — an unbounded value argmax is not a
      manager, it is our board with a seat number, and it would reach past every human profile;
    * **step-3 context**, priced through :func:`_local_z` so the seat is not paying twice for the
      level it is already maximizing.

    ⚠ **The evaluation trap, restated because it is easy to fall into here:** this seat optimizes
    our board, so any comparison scored *on our board* it wins by construction. The lockbox already
    settled that personalization is noise-dominated on realized points. Report its projection
    ranking as **descriptive**; evaluative claims run on realized points.
    """
    weights = dict(personality.context_weights or {})

    def pick(state, team: int) -> int:
        pool = state.draftable_pool(team)
        skill = pool[pool["pos"].isin(SKILL_POSITIONS)]
        if not skill.empty:
            pool = skill
        allowed = effective_budget(personality).cap(state, team)
        if np.isfinite(allowed):
            dev = pool["adp"].to_numpy(float) - float(state.overall_pick)
            within = pool[dev <= allowed]
            pool = within if not within.empty else pool.nsmallest(1, "adp")
        if len(pool) == 1:
            return int(pool.index[0])

        last = state.n_teams * state.rounds
        nxt = None
        for p in range(state.overall_pick + 1, last + 1):        # my next turn on the clock
            rnd0 = (p - 1) // state.n_teams
            idx = (p - 1) % state.n_teams
            seat = idx if rnd0 % 2 == 0 else state.n_teams - 1 - idx
            if seat == team:
                nxt = p
                break
        eff = risk.effective_rank(pool, state.roster(team), None if nxt is None else nxt - 1)
        eff = np.where(np.isnan(eff), pool["adp"].to_numpy(float), eff)   # ADP fallback

        # step-3 context, neighbourhood-local so it does not re-price the level (see `_local_z`).
        # `effective_rank` is a *priority rank* (lower = sooner), so a desirable trait subtracts.
        if weights:
            adp = pool["adp"].to_numpy(float)
            pos = pool["pos"].to_numpy()
            for col, w in weights.items():
                if col in pool.columns and w:
                    eff = eff - w * n_teams * _local_z(pool[col], adp, pos)
        return int(pool.index[int(np.argmin(eff))])

    return pick


def behavioral_pick_fn(model: OpponentModel, **kw):
    """Convenience: the plain fitted behavioral model as an opponent (balanced personality)."""
    return make_opponent_pick_fn(model, personalities()["balanced"], **kw)


# ------------------------------------------------------------------------------------------------
# 16.15 — the mock room: who is sitting at the other nine seats
# ------------------------------------------------------------------------------------------------
# Deviation from BUILD_PLAN §16.15, which files this under `draft/simulator.py`. Composing a room
# needs `Personality`, and `simulator.py` is the draft engine every earlier phase runs on — making
# it import the Phase-16 personality library would invert the layering and put a realism feature
# underneath the frozen optimizer/sim path. `personalities.py` already imports only
# `opponent_model`, so building the room here adds no import edge at all.

#: The default room: 9 opponents for a 10-team league. Hand-set (the user's decision, 2026-07-27),
#: because the corpus cannot be asked this question directly — a manager's *tendency* is observable
#: but his personality is a latent label nothing in the data assigns. What the corpus **can** check
#: is whether the mix implies plausible behaviour, and on 3,309 eligible-redraft managers (≥30
#: picks, complete snake/linear, 8–14 teams) it does: median QB share **12.6 %** and RB share
#: **31 %**, with only **1.7 %** of managers drafting RB-light. That last number is why no
#: ``zero_rb`` seat is in the default room — a strategy roughly 1 manager in 60 runs does not belong
#: in a typical 9-seat mix, though it stays one override away.
DEFAULT_ROOM: tuple[str, ...] = (
    "autopilot", "autopilot",                 # every league has someone on autopick or asleep
    "balanced", "balanced", "balanced",       # the fitted average manager is the modal seat
    "upside_chaser", "safe_floor", "homer", "reacher",
)


#: **16.14R step 7 — the ten-seat room a fully simulated mock drafts.** Corpus-weighted:
#: ``balanced`` (the fitted average manager) dominates, one of each character seat, and — the
#: change this step exists for — **one** ``autopilot``, not two.
#:
#: ★ Two autopilot seats over-represented a behaviour that is **0.2 %** of real seats, and it
#: mattered: over 60 seeded drafts of the 2x5 mock they finished **1.69 / 10** and won **48.3 %**.
#: That is not skill, it is **harvested spill** — mean drift −19.8 picks, i.e. they were handed the
#: value the reaching seats left behind. Halving them fixes both the realism and the spill.
#:
#: ``homer`` is out because 16.14R retired it (its narrative channel moved to ``reacher``, and its
#: ``fandom`` weight is fitted-but-unused rather than deleted); ``chalk`` replaces one ``balanced``
#: because a near-ADP drafter who is not a *bot* is a real and common seat.
REALISTIC_ROOM: tuple[str, ...] = (
    "autopilot",                                       # exactly one, see above
    "balanced", "balanced", "balanced", "balanced",    # the modal manager
    "value_hawk", "safe_floor", "reacher", "upside_chaser", "chalk",
)


def make_room(mix: tuple[str, ...] | None = None, *, n_opponents: int = 9,
              seed: int | None = None, fav_teams: tuple[str, ...] = ()) -> tuple[Personality, ...]:
    """Assign ``n_opponents`` seats from a personality ``mix`` (defaults to :data:`DEFAULT_ROOM`).

    Seats are **shuffled** under ``seed`` rather than taken in listed order, so a personality is not
    confounded with a draft slot — drafting 3rd behind the same two autopickers every time is a
    property of the harness, not of the room. ``seed=None`` keeps the listed order (useful when a
    caller wants a fixed, nameable room).

    ``fav_teams`` attaches to every ``homer`` seat, which is the only personality that reads it.
    """
    names = list(mix or DEFAULT_ROOM)
    if len(names) != n_opponents:
        raise ValueError(f"room has {len(names)} seats for {n_opponents} opponents — "
                         f"pass a mix of exactly {n_opponents}")
    lib = personalities()
    unknown = [n for n in names if n not in lib]
    if unknown:
        raise ValueError(f"unknown personalities {sorted(set(unknown))}; "
                         f"available: {sorted(lib)}")
    if seed is not None:
        np.random.default_rng(seed).shuffle(names)
    seats = []
    for n in names:
        p = lib[n]
        seats.append(replace(p, fav_teams=tuple(fav_teams)) if (fav_teams and n == "homer") else p)
    return tuple(seats)


def normalized_hype_gains(room) -> np.ndarray:
    """The room's ``hype_gain`` values rescaled to **mean 1**.

    16.9 calibrated the shock's size (``NarrativeShock.intercept``) against the realized depth
    profile with the draw applied *uniformly* across seats. The shipped gains do not average to 1
    (autopilot 0.0 · safe 0.5 · balanced 1.0 · upside 1.5 · homer 2.5), so applying them raw would
    silently rescale a calibrated parameter — the room composition would move total simulated
    dispersion as a side effect of who is sitting there. Normalizing keeps the room's *total* shock
    intensity at the calibrated level and lets composition do the only thing it should do here:
    decide **which seats** chase the story. A room of all-autopilots has no hype channel at all and
    is left at zero rather than divided by it.

    This is the ``CLAUDE.md`` lesson applied before the fact: *a coefficient is not transportable
    without its controls* — here the control is the uniform application it was calibrated under.
    """
    g = np.array([float(p.hype_gain) for p in room], float)
    m = g.mean()
    return g if m <= 0 else g / m


def make_room_pick_fn(model: OpponentModel, room=None, *, hype: np.ndarray | None = None,
                      normalize_hype: bool = True, **kw):
    """One ``opponent_pick_fn(state, team)`` that routes each seat to its own personality.

    ``room`` is a tuple of :class:`Personality` (see :func:`make_room`), ordered by seat *excluding*
    your own — seat ``i`` is the ``i``-th other team in draft order. ``hype`` is the single
    per-draft narrative draw shared by the whole room (16.9); each seat scales it by its
    :func:`normalized_hype_gains` share, which is how a shock expressed by an upside chaser and a
    homer looks different from the same shock in a room of autopickers.
    """
    seats = tuple(room if room is not None else make_room())
    gains = normalized_hype_gains(seats) if normalize_hype else np.array(
        [p.hype_gain for p in seats], float)
    fns = [make_opponent_pick_fn(model, replace(p, hype_gain=float(g)), hype=hype, **kw)
           for p, g in zip(seats, gains, strict=True)]

    def pick(state, team) -> int:
        seat = team - 1 if team > state.your_team else team
        if not 0 <= seat < len(fns):
            raise ValueError(f"team {team} maps to seat {seat}, but the room has {len(fns)} seats")
        return fns[seat](state, team)

    return pick
