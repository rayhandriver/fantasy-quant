"""Phase 10.1 — the Monte-Carlo season engine.

A fantasy league is ``n_teams`` rosters, a head-to-head schedule, and weekly optimal-lineup
scores. This module owns the league structure (:class:`LeagueFormat` — 2026-07-09 decision:
14-week regular season + 6-team playoff, weeks 15–17, top-2 byes), a circle-method round-robin
schedule, a **vectorized** optimal-lineup evaluator (regression-tested equal to the Phase-1.3
reference ``optimal_lineup_points``), and standings.

Lineup convention (documented): every team starts its optimal lineup every week — the Phase-1
harness convention, symmetric across teams; realistic imperfect start/sit is Phase 13's job.
The same engine scores **simulated** weekly draws (n_sims worlds) and **realized** weekly points
(n_sims = 1), which is exactly how the calibration gate compares them.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from fantasy_quant.draft.simulator import RosterSlots
from fantasy_quant.simulation.playoffs import bracket_champion, playoff_seeds


@dataclass(frozen=True)
class LeagueFormat:
    """League structure: regular season weeks ``1..reg_weeks``; ``playoff_teams`` advance
    (top ``first_round_byes`` seeds skip round one) through ``playoff_weeks``."""
    n_teams: int = 10
    reg_weeks: int = 14
    playoff_teams: int = 6
    playoff_weeks: tuple[int, ...] = (15, 16, 17)
    first_round_byes: int = 2

    def __post_init__(self) -> None:
        if self.playoff_teams not in (4, 6):
            raise ValueError("playoff_teams must be 4 or 6")
        rounds = 2 if self.playoff_teams == 4 else 3
        if len(self.playoff_weeks) != rounds:
            raise ValueError(f"{self.playoff_teams}-team playoff needs {rounds} weeks")
        if self.first_round_byes != (0 if self.playoff_teams == 4 else 2):
            raise ValueError("byes: 4-team -> 0, 6-team -> 2")
        if self.playoff_weeks[0] != self.reg_weeks + 1:
            raise ValueError("playoffs must start the week after the regular season")

    @property
    def n_weeks(self) -> int:
        return self.playoff_weeks[-1]


def round_robin_schedule(n_teams: int, weeks: int, rng: np.random.Generator) -> np.ndarray:
    """``(weeks, n_teams)`` opponent indices: circle-method round robin (each team plays every
    other once per ``n_teams−1`` weeks) under a random seat permutation, cycled as needed."""
    if n_teams % 2:
        raise ValueError("n_teams must be even")
    base = []
    for r in range(n_teams - 1):
        arr = [0] + [1 + (i + r) % (n_teams - 1) for i in range(n_teams - 1)]
        opp = np.empty(n_teams, dtype=int)
        for k in range(n_teams // 2):
            a, b = arr[k], arr[n_teams - 1 - k]
            opp[a], opp[b] = b, a
        base.append(opp)
    perm = rng.permutation(n_teams)
    sched = np.empty((weeks, n_teams), dtype=int)
    for w in range(weeks):
        opp = base[w % (n_teams - 1)]
        for i in range(n_teams):
            sched[w, perm[i]] = perm[opp[i]]
    return sched


def lineup_points_matrix(points: np.ndarray, positions, slots: RosterSlots) -> np.ndarray:
    """Optimal-starting-lineup totals, vectorized: ``points`` is ``(n_roster, ...)`` and the
    result drops the roster axis (any trailing shape — ``(n_sims, n_weeks)`` in the sim).

    Greedy = optimal for a single FLEX (the 1.3 argument): fill each dedicated slot with its
    top scorers, then the FLEX takes the best *next-ranked* player across flex positions.
    Regression-tested equal to ``walkforward.optimal_lineup_points`` per week.
    """
    if slots.flex > 1:
        raise NotImplementedError("vectorized lineup assumes a single FLEX")
    pos = np.asarray(list(positions))
    pts = np.asarray(points, float)
    total = np.zeros(pts.shape[1:])
    flex_next = []
    for p, need in slots.base_demand().items():
        rows = pts[pos == p]
        if rows.shape[0] == 0:
            continue
        srt = np.sort(rows, axis=0)[::-1]                      # descending along the roster axis
        total += srt[:need].sum(axis=0)
        if p in slots.flex_positions and srt.shape[0] > need:
            flex_next.append(srt[need])                        # next-best after dedicated slots
    if slots.flex and flex_next:
        total += np.maximum.reduce(flex_next)
    return total


@dataclass
class LeagueSim:
    """Per-team outcome distributions over the simulated worlds."""
    wins: np.ndarray             # (n_teams, n_sims) regular-season wins (ties = 0.5)
    points_for: np.ndarray       # (n_teams, n_sims) regular-season points
    made_playoffs: np.ndarray    # (n_teams, n_sims) bool
    champion: np.ndarray         # (n_sims,) winning team index

    @property
    def playoff_prob(self) -> np.ndarray:
        return self.made_playoffs.mean(axis=1)

    @property
    def title_prob(self) -> np.ndarray:
        n_teams = self.wins.shape[0]
        return np.bincount(self.champion, minlength=n_teams) / len(self.champion)

    @property
    def expected_wins(self) -> np.ndarray:
        return self.wins.mean(axis=1)


def simulate_league(team_weekly: np.ndarray, fmt: LeagueFormat, schedule: np.ndarray,
                    start_week: int = 0, wins0: np.ndarray | None = None,
                    pf0: np.ndarray | None = None) -> LeagueSim:
    """Play out the league: H2H regular season → seeds (wins, points-for tiebreak) → bracket.

    ``team_weekly`` is ``(n_teams, n_sims, n_weeks)`` — realized scoring is the ``n_sims = 1``
    special case. ``start_week``/``wins0``/``pf0`` resume from a mid-season state (10.3): weeks
    before ``start_week`` are ignored and the carried standings are added.
    """
    n_teams, n_sims, n_weeks = team_weekly.shape
    if n_weeks < fmt.n_weeks:
        raise ValueError(f"need {fmt.n_weeks} weeks of scores, got {n_weeks}")
    wins = np.zeros((n_teams, n_sims)) if wins0 is None else \
        np.repeat(np.asarray(wins0, float)[:, None], n_sims, axis=1)
    pf = np.zeros((n_teams, n_sims)) if pf0 is None else \
        np.repeat(np.asarray(pf0, float)[:, None], n_sims, axis=1)

    for w in range(start_week, fmt.reg_weeks):
        mine = team_weekly[:, :, w]
        theirs = mine[schedule[w]]
        wins += np.where(mine > theirs, 1.0, np.where(mine == theirs, 0.5, 0.0))
        pf += mine
    seeds = playoff_seeds(wins, pf, fmt.playoff_teams)            # (n_playoff, n_sims)

    made = np.zeros((n_teams, n_sims), dtype=bool)
    np.put_along_axis(made, seeds, True, axis=0)
    playoff_scores = team_weekly[:, :, [w - 1 for w in fmt.playoff_weeks]]
    champion = bracket_champion(seeds, playoff_scores, fmt.first_round_byes)
    return LeagueSim(wins=wins, points_for=pf, made_playoffs=made, champion=champion)


def rosters_weekly(rosters: list[pd.DataFrame], model, sim_cols: np.ndarray,
                   slots: RosterSlots, rng: np.random.Generator) -> np.ndarray:
    """Expand drafted rosters to team weekly optimal-lineup scores, ``(n_teams, n_sims,
    n_weeks)`` — the bridge from a :class:`~fantasy_quant.simulation.weekly.WeeklyModel` to
    :func:`simulate_league`."""
    out = np.empty((len(rosters), len(sim_cols), model.n_weeks))
    for t, roster in enumerate(rosters):
        pts = np.stack([model.player_weekly(r.player_key, r.pos, sim_cols, rng)
                        for r in roster.itertuples(index=False)])
        out[t] = lineup_points_matrix(pts, roster["pos"].tolist(), slots)
    return out
