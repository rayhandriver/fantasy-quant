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
* **A reach ceiling.** ``max_reach_picks`` caps the whole discretionary tilt at what the fitted
  model would pay to move a player that many ADP picks earlier, converted through the model's own
  ``β_adp_s`` exactly as :func:`~fantasy_quant.adp.hype_board.apply_hype` does. So a personality
  *prefers* its kind of player but will not reach an absurd distance for one, and when nothing on
  the board fits its taste the bonus is ≈ 0 and it quietly takes the best value available. That
  fallback is the requested behaviour, and it falls out of the design rather than being
  special-cased.
* **Capped means capped, leaned does not.** The ceiling covers the **player-specific discretionary**
  tilt — hype, ``signal_weights``, and a homer's fandom excess. It deliberately does *not* cover β
  reshaping (``scale``/``override``) or ``early_pos_penalty``: "I don't take RBs early" and "I only
  follow ADP" are **strategies**, not reaches for a particular name, and capping them would silently
  neuter ``zero_rb`` and ``autopilot``.

Scope note: Tier-B tilts (``fandom``, ``rookie``) only express when the board carries ``team`` /
``rookie``; the Tier-A tilts (``chalk``, ``zero_rb``, ``reacher``, positional leans) always express.
Before 16.13 nothing in the mock path supplied either column *or* passed ``fav``, so ``homer`` and
``rookie_hawk`` were silently inert — both are live now.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from fantasy_quant.draft.opponent_model import _ADP_SCALE, CHOICE_TOP_K, OpponentModel

_NEED_TARGET = {"QB": 1, "RB": 4, "WR": 4, "TE": 1}

#: Enriched board columns (16.13) a personality may weight in ``signal_weights``. Note
#: ``overall_rank`` is a **rank** — lower is better — so wanting good players means a *negative*
#: weight on it.
#:
#: ⚠ **Use ``upside``/``floor``, not ``q90``/``q10``, for a ceiling- or floor-seeking manager.**
#: Within position the raw quantiles are ~0.98-collinear with the projected *level*, so weighting
#: them buys good players rather than shaped ones — and two personalities built that way agree
#: instead of opposing. :func:`~fantasy_quant.draft.enrichment.residual_shape` has the measurement.
#: The raw columns stay available because a *reporting* consumer legitimately wants them.
SIGNAL_COLS: tuple[str, ...] = ("boom_prob", "q90", "bust_prob", "q10", "games_played_mean",
                                "mean", "upside", "floor", "vbd", "overall_rank", "cos")

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
    ``max_reach_picks``  ceiling on the discretionary tilt, in ADP picks; ``None`` = uncapped.
    ``sample``           ``False`` makes this personality deterministic (argmax) wherever it is
                         used, so a seat carries its own determinism instead of the caller having to
                         remember. ``None`` defers to the caller.
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

    def __post_init__(self) -> None:
        unknown = set(self.signal_weights) - set(SIGNAL_COLS)
        if unknown:
            raise ValueError(f"{self.name}: unknown signal_weights {sorted(unknown)} — "
                             f"a typo here fails silently forever, so it fails loudly here. "
                             f"Known signals: {list(SIGNAL_COLS)}")

    def adjusted_beta(self, feature_cols, base_beta) -> np.ndarray:
        b = np.asarray(base_beta, float).copy()
        for i, c in enumerate(feature_cols):
            if c in self.scale:
                b[i] *= self.scale[c]
            if c in self.override:
                b[i] = self.override[c]
        return b

    def reach_cap(self, beta_adp_s: float) -> float | None:
        """``max_reach_picks`` in utility units, via the model's own ADP coefficient.

        The same conversion :func:`~fantasy_quant.adp.hype_board.apply_hype` uses, and for the same
        reason: a ceiling stated in picks means the same thing to the simulator as it does to the
        human who set it, and it re-derives itself automatically if 11.1 is ever refit.
        """
        if self.max_reach_picks is None:
            return None
        return abs(float(beta_adp_s)) * float(self.max_reach_picks) / _ADP_SCALE


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
                                 max_reach_picks=0.0),
        # the fitted average human — the anchor everything else is a deviation from.
        "balanced": Personality("balanced"),
        # ceiling over floor: wants the top end of the cone and the players with a story attached,
        # tolerates the bust risk that comes with it, and runs a hot softmax (he talks himself into
        # things). `rookie` rides β rather than signal_weights — liking rookies is a lean, not a
        # reach for one name.
        "upside_chaser": Personality(
            "upside_chaser",
            scale={"rookie": 2.0},
            signal_weights={"upside": 0.45, "boom_prob": 0.35, "cos": 0.20},
            temperature=1.3, hype_gain=1.5, max_reach_picks=REACH_UPSIDE),
        # floor over ceiling: buys the tenth percentile and the games played, actively avoids the
        # bust tail, and drafts chalkier than the room (a cooled softmax) because certainty is the
        # whole point. `games_played_mean` is inert on a *live* board (T17) and carries the tilt on
        # backtest seasons — kept weighted rather than dropped, because the defect is upstream and
        # temporary while the intent is permanent.
        "safe_floor": Personality(
            "safe_floor",
            signal_weights={"floor": 0.45, "games_played_mean": 0.30, "bust_prob": -0.35},
            temperature=0.8, hype_gain=0.5, max_reach_picks=REACH_SAFE),
        # the narrative seat, and the channel 16.15 routes the 16.9 shock through. `fav_teams` is
        # empty by default: set it and he reaches for his team, leave it and he is a pure
        # story-chaser (hype board + changed situations). Either way the reach ceiling holds, so a
        # room with no hyped or newly-relocated player on the clock gets a normal pick, not a
        # tantrum.
        "homer": Personality("homer", scale={"fandom": 2.5},
                             signal_weights={"cos": 0.35}, hype_gain=2.5,
                             max_reach_picks=REACH_HOMER),
        # -- 11.3 library extras (unchanged) ----------------------------------------------------
        "chalk": Personality("chalk", override=zero_out, temperature=0.6),
        "zero_rb": Personality("zero_rb", early_pos_penalty={"RB": 2.5}),
        "reacher": Personality("reacher", temperature=2.2),
        "rookie_hawk": Personality("rookie_hawk", scale={"rookie": 3.0}),
    }


def make_opponent_pick_fn(model: OpponentModel, personality: Personality | None = None, *,
                          rng: np.random.Generator | None = None, sample: bool | None = None,
                          top_k: int | None = CHOICE_TOP_K, hype: np.ndarray | None = None):
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
    cap = pers.reach_cap(base_beta[cols.index("adp_s")]) if "adp_s" in cols else None
    draw = sample if sample is not None else (True if pers.sample is None else pers.sample)

    def pick(state, team) -> int:
        pool = state.draftable_pool(team)
        if top_k is not None and len(pool) > top_k:
            pool = pool.nsmallest(top_k, "adp")
        cand = pool.rename(columns={})[["adp", "pos"]].copy()
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

        # -- the discretionary, player-specific tilt: hype + signals + fandom excess, capped ----
        tilt = np.zeros(len(pool), float)
        if j_fandom is not None and d_fandom:
            excess = X[:, j_fandom] * d_fandom
            u = u - excess
            tilt = tilt + excess
        if hype is not None and pers.hype_gain:
            # the same draw for every seat in this draft — that shared component is the phase
            tilt = tilt + pers.hype_gain * np.asarray(hype, float)[pool.index.to_numpy()]
        if pers.signal_weights:
            tilt = tilt + signal_bonus(pool, pers.signal_weights)
        if cap is not None:
            tilt = np.clip(tilt, -cap, cap)
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


def behavioral_pick_fn(model: OpponentModel, **kw):
    """Convenience: the plain fitted behavioral model as an opponent (balanced personality)."""
    return make_opponent_pick_fn(model, personalities()["balanced"], **kw)
