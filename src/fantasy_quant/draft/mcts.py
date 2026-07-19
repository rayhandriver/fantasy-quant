"""Phase 11.2 — the MCTS draft engine (the research-gate benchmark).

A **determinized** Monte-Carlo Tree Search (a.k.a. single-observer information-set MCTS / PIMC)
over snake-draft states, built to *answer one question*: does lookahead search beat a good greedy
in a snake draft? The reframe's standing hypothesis (ROADMAP Phase 11) is that a snake draft is
**near-perfect-information**, so a covariance-aware greedy with 9.1/9.4 scarcity+lookahead already
captures most of the plannable value and heavy search does not pay (and carries live-latency risk;
CFR was dropped for the same reason). This module lets us *measure* that instead of asserting it —
``steps/phase11_2_mcts.py`` is the keep-or-drop done-bar and the verdict is recorded in
``findings.md`` alongside Phase 7 / props / CFR.

Design (deliberately lightweight, maximal reuse of the Phase-9 machinery):

* **Actions** at each of your decision nodes = the **top-K greedy candidates** at that state
  (:func:`~fantasy_quant.draft.optimizer._greedy_eff` — the exact 9.5 prefilter), so the tree only
  ever branches over plausible picks, not the whole pool.
* **Chance** (opponents between your turns) is **determinized** per iteration: each rollout samples
  one realization of the ADP+noise room (the same room the greedy plans against), turning the
  imperfect-information draft into a deterministic one for that iteration. Candidates that an
  opponent happens to take in a given determinization simply don't appear that iteration
  (SO-ISMCTS availability handling).
* **Rollout** finishes the draft with the **greedy policy** for your seat + the determinized room,
  i.e. the tree searches *on top of* the very policy it is benchmarked against.
* **Leaf value** = your final roster's **portfolio certainty-equivalent**
  (:func:`~fantasy_quant.draft.optimizer.portfolio_value`) — the same covariance-aware objective the
  greedy climbs, so a win here is unambiguously "search found a better plan for the same objective".
* **Selection** = UCB1 with the exploitation term min-max-normalised over the values seen in the
  search (leaf values are on the VBD-points scale, so a fixed exploration constant is meaningless
  without normalisation); the returned pick is the **most-visited** root action.

``k=1`` (only ever one candidate) or ``n_iter`` small collapses toward the greedy; the gate reports
whether real search (K>1, many iterations) moves the needle.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from fantasy_quant.draft.config import DraftConfig
from fantasy_quant.draft.optimizer import (
    DEFAULT_NOISE,
    RiskModel,
    _greedy_eff,
    personalized_pick_fn,
)
from fantasy_quant.draft.simulator import (
    DraftState,
    _apply_pick,
    pick_by_adp,
    run_to_completion,
)

ValueFn = Callable[[pd.DataFrame], float]


# ------------------------------------------------------------------------------------------------
# snake-draft flow helpers
# ------------------------------------------------------------------------------------------------
def _advance_to_your_pick(state: DraftState, opponent_pick_fn=None) -> None:
    """Drive every non-your seat (in place) until it is your turn again or the draft ends.

    Opponents pick via ``opponent_pick_fn(state, team)`` when supplied (a behavioural room), else
    the MVP ADP+noise baseline drawing from ``state.rng`` — so all determinization randomness flows
    from the clone's rng, never the live draft's."""
    while (not state.is_done() and state.available
           and state.team_on_clock() != state.your_team):
        team = state.team_on_clock()
        idx = (int(opponent_pick_fn(state, team)) if opponent_pick_fn is not None
               else pick_by_adp(state, team, noise=state.noise))
        _apply_pick(state, team, idx)


def _top_k_candidates(state: DraftState, config: DraftConfig, risk: RiskModel | None,
                      k: int) -> list[int]:
    """The top-``k`` greedy candidates at your current turn (board row-labels), best first — the
    same ordering :func:`personalized_pick_fn` takes the argmin of, so the tree branches exactly
    over the picks the greedy would consider."""
    pool, eff = _greedy_eff(state, config, risk)
    order = np.argsort(eff)[:max(1, k)]
    return [int(pool.index[int(i)]) for i in order]


# ------------------------------------------------------------------------------------------------
# the search tree
# ------------------------------------------------------------------------------------------------
@dataclass
class _Node:
    """One of *your* decision points. Children are keyed by the board row-label (candidate player)
    picked to reach them; stats are Monte-Carlo estimates of the leaf value reachable here."""
    visits: int = 0
    value_sum: float = 0.0
    children: dict[int, _Node] = field(default_factory=dict)

    @property
    def mean(self) -> float:
        return self.value_sum / self.visits if self.visits else 0.0


def _ucb_select(node: _Node, cands: list[int], vmin: float, vspan: float,
                c_uct: float) -> int:
    """UCB1 over the currently-legal candidate children, exploitation min-max-normalised into
    ``[0,1]`` by the search's observed value range (so ``c_uct`` is on a meaningful scale)."""
    logN = math.log(node.visits + 1.0)
    best_c, best_u = cands[0], -np.inf
    for c in cands:
        ch = node.children[c]
        exploit = (ch.mean - vmin) / vspan
        explore = c_uct * math.sqrt(logN / ch.visits)
        u = exploit + explore
        if u > best_u:
            best_c, best_u = c, u
    return best_c


def mcts_pick(state: DraftState, config: DraftConfig, risk: RiskModel | None,
              value_fn: ValueFn, *, n_iter: int = 120, k: int = 5,
              rng: np.random.Generator | None = None, opponent_pick_fn=None,
              rollout_pick_fn=None, c_uct: float = 1.4) -> int:
    """Return the board row-label MCTS recommends at ``state`` (which must be your turn).

    ``value_fn`` scores a finished roster (``state.your_roster()`` shape) — the portfolio-CE leaf
    value in the gate. ``rollout_pick_fn`` is your seat's rollout policy (defaults to the greedy
    :func:`personalized_pick_fn`, so the tree searches on top of the policy it is benchmarked
    against). ``rng`` seeds the determinizations; each iteration clones ``state`` so the live draft
    is never mutated or its rng consumed."""
    rng = rng if rng is not None else np.random.default_rng(0)
    rollout_pick_fn = rollout_pick_fn or personalized_pick_fn(config, state.noise, risk)
    root = _Node()

    # fixed candidate set at the root (the recommended pick is chosen among these); deeper nodes
    # regenerate their candidates per determinization since the available pool varies.
    root_cands = _top_k_candidates(state, config, risk, k)
    if len(root_cands) == 1:
        return root_cands[0]

    vmin, vmax = np.inf, -np.inf
    for _ in range(n_iter):
        s = state.clone(np.random.default_rng(rng.integers(1 << 63)))
        node, path = root, [root]
        cands = root_cands
        # --- selection + one expansion, over your decision points -------------------------------
        while True:
            cands = [c for c in cands if c in s.available]
            if not cands:
                break
            untried = [c for c in cands if c not in node.children]
            if untried:                                   # EXPAND (greedy-best untried first)
                c = untried[0]
                _apply_pick(s, s.your_team, c)
                child = node.children.setdefault(c, _Node())
                node, _ = child, path.append(child)
                break
            span = (vmax - vmin) or 1.0                   # SELECT via UCB1
            c = _ucb_select(node, cands, vmin, span, c_uct)
            _apply_pick(s, s.your_team, c)
            node = node.children[c]
            path.append(node)
            _advance_to_your_pick(s, opponent_pick_fn)
            if s.is_done() or not s.available:
                break
            cands = _top_k_candidates(s, config, risk, k)
        # --- rollout (greedy you + determinized room) + backup ----------------------------------
        run_to_completion(s, rollout_pick_fn, opponent_pick_fn)
        v = float(value_fn(s.your_roster()))
        vmin, vmax = min(vmin, v), max(vmax, v)
        for n in path:
            n.visits += 1
            n.value_sum += v

    # most-visited root action (robust child); ties broken by mean value
    return max(root_cands, key=lambda c: (root.children[c].visits if c in root.children else -1,
                                          root.children[c].mean if c in root.children else -np.inf))


def mcts_pick_fn(config: DraftConfig, risk: RiskModel | None, value_fn: ValueFn, *,
                 n_iter: int = 120, k: int = 5, noise: float = DEFAULT_NOISE, seed: int = 0,
                 opponent_pick_fn=None, c_uct: float = 1.4):
    """Build the ``your_pick_fn`` the simulator drives your seat with, running :func:`mcts_pick`
    each turn. Per-pick rng is seeded from ``seed + overall_pick`` for reproducibility (mirroring
    :func:`~fantasy_quant.draft.optimizer.winprob_pick_fn`)."""
    rollout_pick_fn = personalized_pick_fn(config, noise, risk)

    def pick_fn(state: DraftState) -> int:
        rng = np.random.default_rng(seed + state.overall_pick)
        return mcts_pick(state, config, risk, value_fn, n_iter=n_iter, k=k, rng=rng,
                         opponent_pick_fn=opponent_pick_fn, rollout_pick_fn=rollout_pick_fn,
                         c_uct=c_uct)

    return pick_fn
