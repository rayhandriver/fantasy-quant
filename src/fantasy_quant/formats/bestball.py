"""Phase 15.2 — best-ball (pure draft + variance; no in-season management).

Best-ball flips the risk dial. In a managed league you start a lineup each week and a boom/bust
player
can burn you with a dud you were forced to start; in **best-ball** your optimal lineup is scored
*automatically* from realized results every week — you only draft, then the format captures each
player's
good weeks for free. That makes the weekly total a **convex** function of a player's spread: two
players
with the same season mean are not equal, the streakier one contributes more because best-ball keeps
his
ceiling weeks and discards his duds. And it rewards **de-correlated** rosters — you want different
players
booming on different weeks so *some* starter always spikes — which is exactly the Phase-8
covariance the
season sim already imposes on the weekly draws.

So best-ball is where "variance is good" — the opposite of the managed-lineup finding (13.2, where
the
variance tilt did not pay because you're forced to start your choice). This module proves it: a
**ceiling-aware** drafter (rank on ``mean·(1 + κ·wk_cov)``, a *weekly*-volatility-seeking tilt)
beats a
**mean-only** drafter at best-ball scoring, using the same board and the same Phase-8-correlated
cloud.
The signal is **weekly** CoV (the boom-week rate best-ball captures), *not* season-total sd —
season sd
conflates injury/bust downside and tilting on it drafts worse players, so it must not be used here.

Reuse: the draft simulator (1.2) for the snake + ADP opponents, the Phase-10 ``WeeklyModel`` for the
Σ-correlated weekly draws, and the Phase-10 ``lineup_points_matrix`` for the weekly optimal lineup.
The
done-bar (:func:`bestball_skill`) is a **paired A/B**: the same focal seat drafts once
ceiling-aware, once
mean-only, against identical opponents, and we compare best-ball season totals on shared draws.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.backtest.scoring import RuleSet
from fantasy_quant.draft.simulator import RosterSlots, simulate_draft
from fantasy_quant.simulation.season import lineup_points_matrix
from fantasy_quant.simulation.weekly import OFFENSE, build_weekly_model

# a classic offense-only best-ball roster (Underdog-style): 1QB/2RB/3WR/1TE/1FLEX + a deep bench
# whose
# boom weeks best-ball auto-captures. No K/DST (best-ball is a skill-position game).
BESTBALL_SLOTS = RosterSlots(qb=1, rb=2, wr=3, te=1, flex=1, k=0, dst=0, bench=10,
                             pos_caps={"QB": 3, "RB": 8, "WR": 9, "TE": 3})
# the variance-seeking tilt: rank on mean·(1 + κ·wk_cov). Small — it breaks ties toward weekly
# upside
# without sacrificing the mean on the early studs (whose best-ball value ≈ their season total
# anyway;
# the convex boom-capture accrues to swing/depth slots). DEV-tuned; larger κ over-tilts and loses.
CEILING_KAPPA = 0.1


# ------------------------------------------------------------------------------------------------
# pure kernels (unit-test targets)
# ------------------------------------------------------------------------------------------------
def bestball_season_points(weekly: np.ndarray, positions, slots: RosterSlots) -> np.ndarray:
    """Best-ball season totals per sim: the sum over weeks of each week's **optimal** lineup.

    ``weekly`` is ``(n_players, n_sims, n_weeks)`` realized/drawn points. Each week we take the
    optimal
    starting lineup (:func:`lineup_points_matrix`, which drops the roster axis) and sum across
    weeks — so
    a player's dud weeks are automatically benched and his boom weeks kept. Returns ``(n_sims,)``.
    """
    weekly = np.asarray(weekly, float)
    per_week = lineup_points_matrix(weekly, positions, slots)   # (n_sims, n_weeks)
    return per_week.sum(axis=1)


def ceiling_value(mean, wk_cov, kappa: float = CEILING_KAPPA) -> np.ndarray:
    """The best-ball draft value: ``mean·(1 + κ·wk_cov)`` — a *weekly*-volatility-seeking tilt (κ >
    0
    lifts streaky, high-boom-week players at a given mean), the mirror image of the risk-averse
    certainty equivalent ``mean − λ·Var``. Uses **weekly** CoV, not season sd (see the module
    docstring:
    season sd carries injury downside and tilting on it drafts worse players). Pure."""
    return np.asarray(mean, float) * (1.0 + kappa * np.asarray(wk_cov, float))


# ------------------------------------------------------------------------------------------------
# drafting: a focal seat drafts by an objective, opponents follow ADP (= mean rank)
# ------------------------------------------------------------------------------------------------
def _board_from_model(model) -> pd.DataFrame:
    """An offense-only ADP board from the ``WeeklyModel`` summary: ADP = rank by season mean (the
    consensus order opponents draft), ``player_key`` carried through as the gsis-style key."""
    s = model.summary
    s = s[s["pos"].isin(OFFENSE)].copy()
    s = s.sort_values("mean", ascending=False).reset_index(drop=True)
    return pd.DataFrame({
        "gsis_id": s["player_key"].to_numpy(),
        "player_name": s["player_key"].to_numpy(),
        "position": s["pos"].to_numpy(),
        "adp": np.arange(1, len(s) + 1, dtype=float),
    })


def _value_pick_fn(value_map: dict[str, float]):
    """A your_pick_fn that drafts the available player maximising ``value_map`` (ceiling or mean).
    """
    def fn(state):
        pool = state.draftable_pool(state.your_team)
        vals = pool["player_key"].map(lambda k: value_map.get(k, -1e18)).to_numpy(float)
        return int(pool.index[int(np.argmax(vals))])
    return fn


def draft_focal_roster(board: pd.DataFrame, value_map: dict[str, float], *, focal_seat: int,
                       n_teams: int, slots: RosterSlots, noise: float, seed: int) -> list[str]:
    """Snake-draft with the focal seat using ``value_map`` and opponents following ADP+noise;
    return the
    focal seat's roster (player_keys). Same ``seed`` ⇒ identical opponent behaviour (the A/B
    pairing)."""
    state = simulate_draft(board, your_pick_fn=_value_pick_fn(value_map), n_teams=n_teams,
                           rounds=slots.total, slots=slots, your_team=focal_seat, noise=noise,
                           seed=seed)
    return list(state.your_roster()["player_key"])


def _bestball_total(model, roster_keys, positions, sim_cols, slots, rng) -> float:
    """Mean best-ball season total for a roster over the shared weekly draws."""
    weekly = np.stack([model.player_weekly(k, p, sim_cols, rng)
                       for k, p in zip(roster_keys, positions, strict=False)])
    return float(bestball_season_points(weekly, positions, slots).mean())


# ------------------------------------------------------------------------------------------------
# the done-bar: ceiling-aware drafting beats mean-only at best-ball scoring
# ------------------------------------------------------------------------------------------------
def _boot_ci(diff: np.ndarray, n_boot: int, seed: int, alpha: float = 0.05):
    rng = np.random.default_rng(seed)
    means = diff[rng.integers(0, len(diff), (n_boot, len(diff)))].mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def bestball_skill(con, season: int, *, n_drafts: int = 40, n_teams: int = 12,
                   kappa: float = CEILING_KAPPA, noise: float = 6.0, n_sims: int = 400,
                   ruleset: RuleSet | None = None, slots: RosterSlots | None = None,
                   n_draws: int = 800, n_boot: int = 2000, seed: int = 0) -> dict:
    """Walk-forward: does ceiling-aware drafting beat mean-only at best-ball, for one ``season``?

    Builds the season's Σ-correlated ``WeeklyModel``, an offense-only ADP board, and a mean map + a
    ceiling map (``mean + κ·sd``). For each of ``n_drafts`` a random focal seat drafts **twice
    against
    identical opponents** (same seed) — once ceiling-aware, once mean-only — and both rosters are
    scored
    on the **same** weekly draws (:func:`_bestball_total`). The paired difference isolates the
    variance
    tilt. Done-when: the ceiling roster's best-ball total beats the mean roster's with a CI
    excluding 0.
    Scored on the model's own calibrated, correlated draws (best-ball is about the variance
    structure),
    PIT board; lockbox unread.
    """
    slots = slots or BESTBALL_SLOTS
    model = build_weekly_model(con, season, ruleset, n_draws=n_draws, seed=seed)
    board = _board_from_model(model)
    s = model.summary.set_index("player_key")
    mean_map = s["mean"].to_dict()
    ceil_map = dict(zip(s.index, ceiling_value(s["mean"], s["wk_cov"], kappa), strict=False))
    pos_of = s["pos"].to_dict()

    rng = np.random.default_rng(seed)
    cols = rng.choice(model.n_draws, min(n_sims, model.n_draws), replace=False)
    diffs, ceil_tot, mean_tot = [], [], []
    for d in range(n_drafts):
        focal = int(rng.integers(0, n_teams))
        seed_d = seed * 1000 + d
        r_ceil = draft_focal_roster(board, ceil_map, focal_seat=focal, n_teams=n_teams,
                                    slots=slots, noise=noise, seed=seed_d)
        r_mean = draft_focal_roster(board, mean_map, focal_seat=focal, n_teams=n_teams,
                                    slots=slots, noise=noise, seed=seed_d)
        pos_c = [pos_of[k] for k in r_ceil]
        pos_m = [pos_of[k] for k in r_mean]
        t_ceil = _bestball_total(model, r_ceil, pos_c, cols, slots, rng)
        t_mean = _bestball_total(model, r_mean, pos_m, cols, slots, rng)
        ceil_tot.append(t_ceil)
        mean_tot.append(t_mean)
        diffs.append(t_ceil - t_mean)

    diff = np.asarray(diffs)
    lo, hi = _boot_ci(diff, n_boot, seed)
    return {
        "season": int(season), "n_drafts": int(n_drafts), "n_teams": int(n_teams),
        "kappa": float(kappa),
        "ceiling_total": float(np.mean(ceil_tot)), "mean_total": float(np.mean(mean_tot)),
        "bestball_gain": float(diff.mean()), "gain_ci": (lo, hi),
        "frac_drafts_ceiling_wins": float((diff > 0).mean()),
        "beats_mean_only": bool(lo > 0.0),
    }
