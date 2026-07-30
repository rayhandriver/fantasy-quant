"""Phase 13.2 — start/sit (the weekly lineup, refreshed by 13.1; win-probability tilt as an option).

The start/sit decision is *who you start each week*. Two levers were on the table:

  1. **A better mean** — start your highest-*projected* players, but on the **re-projected** weekly
     means from 13.1 (results-informed) rather than the frozen preseason projection. This is the
     load-bearing edge: the weekly co-pilot's mean-max lineup **beats set-and-forget by ~+1.8
     pts/week** OOS (``weekly_lineup_gain``; DEV 2014–22) — because 13.1's re-projected means simply
     have lower error. This is the 13.2 done-bar and the default (``objective="mean"``).
  2. **A variance tilt** — a fantasy week is one H2H game, so trailing a strong opponent you might
     *add variance* (the boom/bust bench player who sometimes clears their total) and protecting a
     lead *cut it* (the safe floor) — the Phase-10.3 leverage idea at the lineup grain. **Finding
     (2026-07-12): it does not pay here.** A single legal start/sit swap moves team spread by a tiny
     fraction of the ~35-pt team sd, so the second-order variance benefit is swamped by the
     first-order mean cost — the win-objective tilt fails to beat mean-max OOS **even for big
     underdogs** (``start_sit_skill``; consistent with Phase-10.3, where leverage only bit at
     *whole-team* spread changes of 1.6×). So the tilt is retained as **opt-in** (``objective=
     "win"``) but **off by default**, like Phase 7 (kept, not the default) and props (shelved).

:func:`optimal_lineup` is pure (arrays in, a :class:`LineupChoice` out): it fills the mean-max
lineup and — only when ``objective="win"`` — applies the leverage tilt under a do-no-harm guard.
Feasibility is trivial because each slot carries its allowed positions. It reuses the Phase-10
:func:`~fantasy_quant.simulation.season.lineup_points_matrix` slot convention and the Phase-10
``WeeklyModel`` draws.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from fantasy_quant.backtest.scoring import RuleSet
from fantasy_quant.draft.simulator import RosterSlots
from fantasy_quant.inseason.reproject import (
    PRIOR_WEEKS,
    preseason_prior,
    realized_weekly,
    reproject_week,
)
from fantasy_quant.simulation.weekly import build_weekly_model

LEV_GAMMA = 0.6      # strength of the leverage tilt (fraction of a player's sd traded for mean)
LEV_SCALE = 20.0     # H2H point edge at which the tilt half-saturates (tanh); tuned on DEV


@dataclass(frozen=True)
class LineupChoice:
    """A chosen starting lineup: ``slots`` maps each slot label → the roster row it starts (or
    ``None`` if unfillable). ``win_prob`` is against the opponent distribution supplied to
    :func:`optimal_lineup` (NaN if none), ``exp_points`` the lineup's mean total under the draws."""
    slots: dict
    win_prob: float
    exp_points: float

    def indices(self) -> list[int]:
        return [i for i in self.slots.values() if i is not None]


def _slot_plan(slots: RosterSlots) -> list[tuple[str, tuple[str, ...]]]:
    """Ordered ``(label, allowed_positions)`` — dedicated slots first, then each flex group
    most-restrictive-first, matching :func:`lineup_points_matrix`'s fill order.

    17.1: the group order comes from :meth:`RosterSlots.flex_groups`, the single place it is
    defined. A superflex is labelled ``SUPERFLEX`` because a user reading a lineup needs to see
    *which* flex a quarterback is occupying."""
    plan = [(f"{p}{k + 1}" if need > 1 else p, (p,))
            for p, need in slots.base_demand().items() for k in range(need)]
    for count, eligible in slots.flex_groups():
        label = "SUPERFLEX" if "QB" in eligible else "FLEX"
        plan += [(f"{label}{k + 1}" if count > 1 else label, tuple(eligible))
                 for k in range(count)]
    return plan


def _fill(scores: np.ndarray, pos: np.ndarray, slots: RosterSlots) -> dict:
    """Greedy mean-max fill: each slot takes its highest-``scores`` eligible unused player."""
    used, assign = set(), {}
    for label, allowed in _slot_plan(slots):
        cand = [i for i in range(len(scores)) if i not in used and pos[i] in allowed]
        assign[label] = max(cand, key=lambda i: scores[i]) if cand else None
        if assign[label] is not None:
            used.add(assign[label])
    return assign


def _total(assign: dict, weekly: np.ndarray) -> np.ndarray:
    idx = [i for i in assign.values() if i is not None]
    return weekly[idx].sum(axis=0) if idx else np.zeros(weekly.shape[1])


def _winprob(total: np.ndarray, opp: np.ndarray) -> float:
    return float((total > opp).mean() + 0.5 * (total == opp).mean())


def optimal_lineup(roster_weekly, positions, slots: RosterSlots, opponent_weekly=None, *,
                   objective: str = "mean") -> LineupChoice:
    """The start/sit choice for one week.

    ``roster_weekly`` is ``(n_roster, n_sims)`` weekly points, ``positions`` the aligned canonical
    positions, ``opponent_weekly`` the opponent's ``(n_sims,)`` total. ``objective='mean'`` (the
    **default** and validated behaviour — highest projected, on 13.1's re-projected means) or no
    opponent returns the mean-max lineup. ``objective='win'`` (opt-in; does not beat mean-max OOS —
    see the module docstring) applies the **leverage tilt** — score
    each player by ``mean + lever·sd`` where ``lever`` is + when you're the underdog (add variance,
    take tail shots at their total) and − when you're favored (cut variance, protect the lead), its
    size set by the H2H point edge (``tanh``) — then keeps that lineup only if it does not lower the
    belief win probability (a do-no-harm guard, so a near-50/50 game just returns mean-max). This is
    a *directional* rule, not an argmax over noisy Monte-Carlo swaps, so it doesn't overfit the
    draws it's chosen on."""
    weekly = np.asarray(roster_weekly, float)
    pos = np.asarray(list(positions))
    mu, sd = weekly.mean(axis=1), weekly.std(axis=1)
    base = _fill(mu, pos, slots)

    def choice(assign: dict) -> LineupChoice:
        tot = _total(assign, weekly)
        wp = _winprob(tot, opponent_weekly) if opponent_weekly is not None else float("nan")
        return LineupChoice(dict(assign), wp, float(tot.mean()))

    if objective == "mean" or opponent_weekly is None:
        return choice(base)

    edge = float(_total(base, weekly).mean() - np.mean(opponent_weekly))
    lever = -LEV_GAMMA * float(np.tanh(edge / LEV_SCALE))     # + = add variance (behind), − = cut
    tilted = choice(_fill(mu + lever * sd, pos, slots))
    plain = choice(base)
    return tilted if tilted.win_prob >= plain.win_prob else plain


# ------------------------------------------------------------------------------------------------
# diagnostic: does the win-objective *tilt* beat mean-max on OOS win%? (finding: no, at this grain)
# ------------------------------------------------------------------------------------------------
_ROSTER_MIX = (("QB", 2), ("RB", 5), ("WR", 5), ("TE", 2))   # offense pool; +1 K +1 DST (constants)


def _sample_roster(model, rng) -> tuple[list[str], list[str]]:
    keys: list[str] = []
    poss: list[str] = []
    s = model.summary
    for pos, n in _ROSTER_MIX:
        pool = s.loc[s["pos"] == pos, "player_key"].to_numpy()
        take = rng.choice(pool, size=min(n, len(pool)), replace=False)
        keys += list(take)
        poss += [pos] * len(take)
    keys += ["_K", "_DST"]                                    # constant weekly units (13.2 ignores)
    poss += ["K", "DST"]
    return keys, poss


def _weekly_matrix(model, keys, poss, week, sim_cols, rng) -> np.ndarray:
    return np.stack([model.player_weekly(k, p, sim_cols, rng)[:, week]
                     for k, p in zip(keys, poss, strict=False)])


def _boot_ci(vals, n_boot=2000, seed=0, alpha=0.05):
    v = np.asarray(vals, float)
    if len(v) == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, len(v), (n_boot, len(v)))].mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def start_sit_skill(con, season: int, *, n_matchups: int = 400, n_sims: int = 250,
                    ruleset: RuleSet | None = None, n_draws: int = 800, n_boot: int = 2000,
                    seed: int = 0) -> dict:
    """Diagnostic: does the win-objective **tilt** beat mean-max on OOS win%, for one ``season``?

    Each of ``n_matchups`` random legal rosters faces a random opponent in a random week; both the
    mean-max and win-objective lineups are chosen on one set of belief draws and scored on a
    **disjoint** set (no circularity — the model is the DGP, choose- and score-draws are split).
    Reports the OOS win-rate gain overall and among **underdog** matchups (where leverage should
    help most). **Finding (2026-07-12): the tilt does NOT clear the bar** — the gain is ~0-to-
    slightly negative overall and negative even for big underdogs, because a single legal swap
    barely moves team spread (module docstring). Mean-max stays the default; this is evidence."""
    model = build_weekly_model(con, season, ruleset, n_draws=n_draws, seed=seed)
    slots = RosterSlots()
    rng = np.random.default_rng(seed)
    cols = rng.permutation(model.n_draws)
    n = min(n_sims, model.n_draws // 2)
    choose_cols, score_cols = cols[:n], cols[n:2 * n]

    gains: list[float] = []
    favored: list[bool] = []
    mean_wr_all: list[float] = []
    win_wr_all: list[float] = []
    for _ in range(n_matchups):
        mk, mp = _sample_roster(model, rng)
        ok, op = _sample_roster(model, rng)
        w = int(rng.integers(0, model.n_weeks))

        mine_b = _weekly_matrix(model, mk, mp, w, choose_cols, rng)
        opp_b = _weekly_matrix(model, ok, op, w, choose_cols, rng)
        # the opponent *commits* a mean-max lineup (symmetric: both sides start a fixed lineup,
        # not a per-world hindsight-optimal); I optimize against the belief of that lineup.
        opp_choice = optimal_lineup(opp_b, op, slots, objective="mean")
        opp_b_total = opp_b[opp_choice.indices()].sum(axis=0)
        mean_c = optimal_lineup(mine_b, mp, slots, opp_b_total, objective="mean")
        win_c = optimal_lineup(mine_b, mp, slots, opp_b_total, objective="win")

        mine_r = _weekly_matrix(model, mk, mp, w, score_cols, rng)          # disjoint reality draws
        opp_r_total = _weekly_matrix(model, ok, op, w, score_cols, rng)[opp_choice.indices()].sum(
            axis=0)
        mean_wr = _winprob(mine_r[mean_c.indices()].sum(axis=0), opp_r_total)
        win_wr = _winprob(mine_r[win_c.indices()].sum(axis=0), opp_r_total)

        mean_wr_all.append(mean_wr)
        win_wr_all.append(win_wr)
        gains.append(win_wr - mean_wr)
        favored.append(mean_c.exp_points >= float(opp_b_total.mean()))

    gains = np.asarray(gains)
    dog = ~np.asarray(favored)
    lo, hi = _boot_ci(gains, n_boot, seed)
    dlo, dhi = _boot_ci(gains[dog], n_boot, seed)
    return {
        "season": int(season), "n_matchups": int(n_matchups),
        "n_underdog": int(dog.sum()),
        "mean_max_winrate": float(np.mean(mean_wr_all)),
        "winobj_winrate": float(np.mean(win_wr_all)),
        "winrate_gain": float(gains.mean()), "winrate_gain_ci": (lo, hi),
        "underdog_gain": float(gains[dog].mean()) if dog.any() else float("nan"),
        "underdog_gain_ci": (dlo, dhi),
        "beats_mean_max": bool(lo >= 0.0 and dlo > 0.0),
    }


# ------------------------------------------------------------------------------------------------
# the 13.2 done-bar: the weekly co-pilot (mean-max on 13.1 re-projected means) beats set-and-forget
# ------------------------------------------------------------------------------------------------
# Offense-only lineup: K/DST are weekly constants, identical for both lineups, so they cancel — and
# start/sit is a skill-position decision. This is where 13.2 delivers: not the variance tilt, but
# feeding 13.1's results-informed means into the ordinary mean-max lineup.
_COPILOT_SLOTS = RosterSlots(qb=1, rb=2, wr=2, te=1, flex=1, k=0, dst=0, bench=0)


def _cluster_ci(diff: np.ndarray, cluster: np.ndarray, n_boot: int, seed: int,
                alpha: float = 0.05) -> tuple[float, float]:
    """Percentile CI of the mean of ``diff`` resampling whole ``cluster``s (rosters) — the honest
    error bar when one roster contributes many correlated weekly diffs."""
    order = np.argsort(cluster, kind="stable")
    diff = diff[order]
    _, starts = np.unique(cluster[order], return_index=True)
    groups = np.split(diff, starts[1:])
    rng = np.random.default_rng(seed)
    n = len(groups)
    means = np.array([np.concatenate([groups[i] for i in rng.integers(0, n, n)]).mean()
                      for _ in range(n_boot)])
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def weekly_lineup_gain(con, season: int, *, splits=(4, 6, 8, 10), reg_weeks: int = 14,
                       n_rosters: int = 300, roster_size: int = 15,
                       ruleset: RuleSet | None = None, n_draws: int = 600,
                       prior_weeks: float = PRIOR_WEEKS, process_var: float = 0.0,
                       n_boot: int = 2000, seed: int = 0) -> dict:
    """Walk-forward: does the weekly co-pilot beat set-and-forget on **realized** points, a season?

    The co-pilot starts the mean-max offense lineup ranked by 13.1's **re-projected** weekly means
    (weeks ``≤ t``); set-and-forget starts the mean-max lineup ranked by the **frozen preseason**
    level ``m0``. At each split week ``t`` we score both lineups on every *future* played week
    ``t < w ≤ reg_weeks`` with realized points, over ``n_rosters`` random offense rosters. Scored on
    **reality** (not the model), PIT throughout (re-projection reads only weeks ``≤ t``). Done-when:
    the co-pilot outscores set-and-forget and the per-roster-clustered CI excludes 0."""
    model = build_weekly_model(con, season, ruleset, n_draws=n_draws, seed=seed)
    prior = preseason_prior(model, prior_weeks=prior_weeks)
    m0 = dict(zip(prior["player_key"], prior["m0"], strict=False))
    pos_of = dict(zip(prior["player_key"], prior["pos"], strict=False))
    keys = prior["player_key"].to_numpy()

    realized = realized_weekly(con, season, ruleset)
    realized = realized[realized["player_key"].isin(set(keys))]
    rp = {(r.player_key, int(r.week)): float(r.points) for r in realized.itertuples(index=False)}

    rng = np.random.default_rng(seed)
    size = min(roster_size, len(keys))
    diffs: list[float] = []
    cluster: list[int] = []
    copilot_pts: list[float] = []
    static_pts: list[float] = []
    cid = 0
    for t in splits:
        rmean = reproject_week(prior, realized, t, process_var=process_var).week_mean()
        for _ in range(n_rosters):
            take = rng.choice(keys, size=size, replace=False)
            tp = np.array([pos_of[k] for k in take])
            static = np.array([m0.get(k, 0.0) for k in take])
            reproj = np.array([rmean.get(k, m0.get(k, 0.0)) for k in take])
            idx_s = [i for i in _fill(static, tp, _COPILOT_SLOTS).values() if i is not None]
            idx_r = [i for i in _fill(reproj, tp, _COPILOT_SLOTS).values() if i is not None]
            for w in range(t + 1, reg_weeks + 1):
                rvec = np.array([rp.get((k, w), 0.0) for k in take])
                ps, pr = float(rvec[idx_s].sum()), float(rvec[idx_r].sum())
                diffs.append(pr - ps)
                cluster.append(cid)
                static_pts.append(ps)
                copilot_pts.append(pr)
            cid += 1

    diff = np.asarray(diffs)
    lo, hi = _cluster_ci(diff, np.asarray(cluster), n_boot, seed)
    return {
        "season": int(season), "n_lineup_weeks": int(len(diff)), "n_rosters": int(n_rosters),
        "static_ppw": float(np.mean(static_pts)), "copilot_ppw": float(np.mean(copilot_pts)),
        "copilot_minus_static_ppw": float(diff.mean()), "gain_ci": (lo, hi),
        "frac_weeks_better": float((diff >= 0).mean()),
        "beats_static": bool(lo > 0.0),
    }
