"""Phase 11.3 — realistic mock opponents with configurable personalities.

The behavioral opponent model (11.1) predicts the *average* manager. A realistic mock also wants
*heterogeneous* opponents — a chalk ADP-drafter, a zero-RB zealot, a wild reacher — so drafts you
practice against feel like a real room. A :class:`Personality` is a light, interpretable tilt on
the fitted β (scale/override a coefficient, add a round-dependent positional penalty, or heat up
the softmax); :func:`make_opponent_pick_fn` turns a ``(model, personality)`` pair into an
``opponent_pick_fn(state, team)`` that plugs straight into
:func:`~fantasy_quant.draft.simulator.simulate_draft`.

Scope note: a live :class:`~fantasy_quant.draft.simulator.DraftState` board carries only
``adp``/``pos`` (the Tier-A features), so personalities keyed on Tier-B context (``fandom``,
``rookie``) only express when the board is enriched with ``team``/``rookie`` columns; the Tier-A
tilts (``chalk``, ``zero_rb``, ``reacher``, positional leans) always express.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from fantasy_quant.draft.opponent_model import CHOICE_TOP_K, OpponentModel

_NEED_TARGET = {"QB": 1, "RB": 4, "WR": 4, "TE": 1}


@dataclass(frozen=True)
class Personality:
    """A named tilt on a fitted opponent model. ``scale`` multiplies and ``override`` replaces
    individual β entries; ``temperature`` heats (>1, more random/reachy) or cools (<1, chalkier)
    the choice softmax; ``early_pos_penalty`` subtracts utility from a position in early rounds."""
    name: str
    scale: dict = field(default_factory=dict)
    override: dict = field(default_factory=dict)
    temperature: float = 1.0
    early_pos_penalty: dict = field(default_factory=dict)   # pos -> utility penalty
    early_rounds: int = 4

    def adjusted_beta(self, feature_cols, base_beta) -> np.ndarray:
        b = np.asarray(base_beta, float).copy()
        for i, c in enumerate(feature_cols):
            if c in self.scale:
                b[i] *= self.scale[c]
            if c in self.override:
                b[i] = self.override[c]
        return b


# a small, opinionated roster of archetypes ---------------------------------------------------
def personalities() -> dict[str, Personality]:
    zero_out = {c: 0.0 for c in ("is_RB", "is_WR", "is_TE", "is_QB", "pos_run3",
                                 "mgr_lean", "rookie", "fandom", "need")}
    return {
        "balanced": Personality("balanced"),
        "chalk": Personality("chalk", override=zero_out, temperature=0.6),
        "zero_rb": Personality("zero_rb", early_pos_penalty={"RB": 2.5}),
        "reacher": Personality("reacher", temperature=2.2),
        "homer": Personality("homer", scale={"fandom": 2.5}),          # needs enriched board
        "rookie_hawk": Personality("rookie_hawk", scale={"rookie": 3.0}),  # needs enriched board
    }


def make_opponent_pick_fn(model: OpponentModel, personality: Personality | None = None, *,
                          rng: np.random.Generator | None = None, sample: bool = True,
                          top_k: int | None = CHOICE_TOP_K, hype: np.ndarray | None = None):
    """Build an ``opponent_pick_fn(state, team) -> board_label`` from a fitted model + personality.

    Draws from the model's choice softmax over the team's cap-respecting available pool (so rosters
    stay realistic). ``sample=False`` makes it deterministic (argmax). ``rng`` defaults to the
    draft state's own generator so a seeded draft stays reproducible.

    ``top_k`` narrows each pick to the top-``k`` still-available players by ADP — **the candidate
    set the model was fit on** (:data:`~fantasy_quant.draft.opponent_model.CHOICE_TOP_K`). Session G
    found this missing, which let a top-40-estimated β spread probability across the whole board
    and inflated simulated draft-slot dispersion by 59 %; ``top_k=None`` restores that behaviour for
    comparison only.

    ``hype`` is the Phase-16.9 narrative shock: a per-board-row utility offset, indexed by board
    label, **drawn once per draft** (:meth:`~fantasy_quant.adp.narrative.NarrativeShock.draw`) and
    passed to every opponent in that draft, so a hyped player goes early *consistently within a
    room* rather than having his early picks averaged away by independent per-seat noise.
    """
    pers = personality or personalities()["balanced"]
    beta = pers.adjusted_beta(model.feature_cols, model.beta)
    adj = OpponentModel(list(model.feature_cols), beta=beta)

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
        u = adj.candidate_utility(cand, recent_pos=rp, need=need)
        if hype is not None:
            # the same draw for every seat in this draft — that shared component is the phase
            u = u + np.asarray(hype, float)[pool.index.to_numpy()]
        if pers.early_pos_penalty and state.round() <= pers.early_rounds:
            pos = cand["pos"].to_numpy()
            for pp, pen in pers.early_pos_penalty.items():
                u = u - pen * (pos == pp)
        u = u / max(pers.temperature, 1e-3)
        u = u - u.max()
        pr = np.exp(u)
        pr = pr / pr.sum()
        g = rng or state.rng
        j = int(g.choice(len(pool), p=pr)) if sample else int(np.argmax(pr))
        return int(pool.index[j])

    return pick


def behavioral_pick_fn(model: OpponentModel, **kw):
    """Convenience: the plain fitted behavioral model as an opponent (balanced personality)."""
    return make_opponent_pick_fn(model, personalities()["balanced"], **kw)
