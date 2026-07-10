"""Phase 10.2 — the playoff bracket → championship probability (the north-star metric).

Seeding = regular-season wins, points-for tiebreak (the common house rule; exact double-ties
fall to the lower team index, documented). Brackets supported: **6-team** (top-2 first-round
byes; round one 3v6 / 4v5; semifinals **reseeded** — the 1-seed draws the worst surviving
seed; final) and **4-team** (1v4 / 2v3, final). Playoff ties advance the better seed.
"""

from __future__ import annotations

import numpy as np


def playoff_seeds(wins: np.ndarray, points_for: np.ndarray, n_playoff: int) -> np.ndarray:
    """Top-``n_playoff`` team indices per sim, best seed first: ``(n_playoff, n_sims)``.

    ``wins`` and ``points_for`` are ``(n_teams, n_sims)``; points-for breaks win ties.
    """
    key = wins * 1e9 + points_for
    order = np.argsort(-key, axis=0, kind="stable")
    return order[:n_playoff]


def _h2h(a: int, ra: int, b: int, rb: int, wk: np.ndarray) -> tuple[int, int]:
    """One matchup: (team, seed-rank) of the winner; a tie advances the better seed."""
    if wk[a] > wk[b]:
        return a, ra
    if wk[b] > wk[a]:
        return b, rb
    return (a, ra) if ra < rb else (b, rb)


def bracket_champion(seeds: np.ndarray, playoff_scores: np.ndarray,
                     first_round_byes: int) -> np.ndarray:
    """Champion team index per sim.

    ``seeds`` is ``(n_playoff, n_sims)`` (best first, from :func:`playoff_seeds`);
    ``playoff_scores`` is ``(n_teams, n_sims, n_rounds)`` weekly totals for the playoff weeks.
    """
    n_playoff, n_sims = seeds.shape
    if n_playoff == 6 and first_round_byes != 2:
        raise ValueError("6-team bracket requires 2 first-round byes")
    if n_playoff == 4 and first_round_byes != 0:
        raise ValueError("4-team bracket requires 0 first-round byes")

    champ = np.empty(n_sims, dtype=int)
    for s in range(n_sims):
        order = seeds[:, s]
        rounds = playoff_scores[:, s, :]
        if n_playoff == 6:
            m1 = _h2h(order[2], 2, order[5], 5, rounds[:, 0])
            m2 = _h2h(order[3], 3, order[4], 4, rounds[:, 0])
            worse, better = (m1, m2) if m1[1] > m2[1] else (m2, m1)
            s1 = _h2h(order[0], 0, worse[0], worse[1], rounds[:, 1])
            s2 = _h2h(order[1], 1, better[0], better[1], rounds[:, 1])
            champ[s] = _h2h(*s1, *s2, rounds[:, 2])[0]
        else:
            s1 = _h2h(order[0], 0, order[3], 3, rounds[:, 0])
            s2 = _h2h(order[1], 1, order[2], 2, rounds[:, 0])
            champ[s] = _h2h(*s1, *s2, rounds[:, 1])[0]
    return champ
