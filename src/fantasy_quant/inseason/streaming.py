"""Phase 13.4 — streaming (the weekly matchup pick over the waiver pool).

*Streaming* is the in-season move of not rostering one player at a low-scarcity, matchup-driven
position (classically **DST**, also a bye-week **QB/TE**) all year, but picking up whichever
freely-available unit has the **best matchup this week**, starting it, and moving on. It is a
**contextual bandit** over the waiver pool: each week the arms are the available streamers, the
context is the opponent they draw, and the reward is the points they score. Two forces drive the
pick — the pure :func:`stream_pick` turns them into one choice:

  1. **Own level × matchup.** A defense's expected week is its own scoring level **plus how
     generous this week's opponent offense is** to opposing defenses (:func:`matchup_projection`):
     ``own + (opp_allow − league_mean)``. Both terms are **empirical-Bayes** season-to-date rates
     shrunk toward the prior season (:func:`_shrink`) so one flukey shut-out doesn't crown a
     streamer — the shrinkage *is* the explore half of the bandit (we don't chase thin samples;
     an optional ``ucb_c`` optimism bonus makes it explicit). Exploit = start the projected best.
  2. **Transaction cost.** Every switch spends a waiver claim and roster volatility, so we keep the
     currently-held streamer unless a challenger beats it by ``switch_margin`` points (hysteresis) —
     the Phase-13.3 anti-churn lesson: without a switch cost the sim just rewards volume of moves.

The 13.4 done-bar (:func:`streaming_skill`) is that a matchup-streamer using :func:`stream_pick`
**beats static-hold** (roster the preseason-best waiver unit, start it every week, eat its bye) on
realized points, on DEV seasons. A second control — matchup-streaming vs **random**-streaming (pick
a random available unit each week) — isolates that the *matchup signal*, not merely the churn/
weekly-selection, is what adds value (the 13.3 smart-vs-naive analog).

Scope: the done-bar runs on **DST**, where the matchup signal (opponent-offense strength) is
strongest and real weekly scores exist (``scoring.dst_weekly_points``). :func:`stream_pick` is
position-agnostic — QB/TE streaming feeds 13.1 re-projected means in as ``proj`` instead — but no
separate QB/TE matchup model is built here. Everything is PIT: ratings read only weeks strictly
before the decision week; the schedule (who plays whom) is public pre-season; realized points only
ever *score* the sim.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.backtest.scoring import RuleSet, dst_weekly_points

PRIOR_GAMES = 4.0       # empirical-Bayes shrinkage strength (equivalent prior-season games), DEV
SWITCH_MARGIN = 1.0     # points a challenger must beat the held unit by before we churn the wire
UCB_C = 0.0             # optimism-under-uncertainty bonus (off by default; shrinkage explores soft)


# ------------------------------------------------------------------------------------------------
# pure kernels (the unit-test targets)
# ------------------------------------------------------------------------------------------------
def _shrink(sample_mean: float, n: int, prior_mean: float, prior_games: float) -> float:
    """Empirical-Bayes shrink a season-to-date mean toward the prior-season level: ``n`` real games
    pull toward the data, ``prior_games`` toward ``prior_mean`` (``n = 0`` ⇒ pure prior)."""
    n = float(n)
    return (n * sample_mean + prior_games * prior_mean) / (n + prior_games)


def matchup_projection(own_rating: float, opp_allow: float, league_mean: float) -> float:
    """Projected points for a streamer = its own scoring level plus how much more (or fewer) points
    this week's **opponent offense** concedes to defenses than a league-average offense."""
    return own_rating + (opp_allow - league_mean)


def stream_pick(proj, *, held: int | None = None, switch_margin: float = SWITCH_MARGIN,
                n_seen=None, ucb_c: float = UCB_C) -> int | None:
    """Which streamer to start this week, from per-candidate projected points ``proj``.

    Greedy **exploit** (start the projected best) with two knobs: an optional **UCB** optimism bonus
    ``ucb_c / sqrt(1 + n_seen)`` that favors under-observed streamers (the explicit **explore**
    half), and a **switch margin** — keep the currently-``held`` index unless a challenger beats it
    by ``switch_margin`` (transaction-cost hysteresis, so we don't churn for a trivial upgrade).
    Returns the chosen index, or ``None`` if there are no candidates. Pure."""
    proj = np.asarray(proj, float)
    if proj.size == 0:
        return None
    score = proj.copy()
    if ucb_c and n_seen is not None:
        score = score + ucb_c / np.sqrt(1.0 + np.asarray(n_seen, float))
    best = int(np.argmax(score))
    if held is not None and 0 <= held < len(score) and score[best] <= score[held] + switch_margin:
        return int(held)
    return best


# ------------------------------------------------------------------------------------------------
# PIT data: per team-week DST points scored (`pts_for`) and conceded by that team's offense
# (`pts_against` = the opposing defense's points), plus the schedule opponent
# ------------------------------------------------------------------------------------------------
def _dst_matchup_table(con, season: int, ruleset: RuleSet | None = None) -> pd.DataFrame:
    """``team · week · opp · pts_for · pts_against`` for one season (REG). ``pts_for`` is the team's
    own DST points; ``pts_against`` is the DST points its **offense conceded** (the opponent
    defense's ``pts_for`` that week) — the raw material for the opponent-generosity rating."""
    dst = (dst_weekly_points(con, season, ruleset)[["team", "week", "points"]]
           .rename(columns={"points": "pts_for"}))
    dst["week"] = dst["week"].astype(int)
    sched = con.execute(
        "SELECT week, home_team, away_team FROM game_lines "
        "WHERE season = ? AND game_type = 'REG'", [int(season)]).df()
    sched["week"] = sched["week"].astype(int)
    directed = pd.concat([
        sched.rename(columns={"home_team": "team", "away_team": "opp"}),
        sched.rename(columns={"away_team": "team", "home_team": "opp"}),
    ], ignore_index=True)[["week", "team", "opp"]]
    t = dst.merge(directed, on=["week", "team"], how="inner")
    against = t[["week", "team", "pts_for"]].rename(
        columns={"team": "opp", "pts_for": "pts_against"})
    return t.merge(against, on=["week", "opp"], how="left")


def _streamer_pool(prior_tbl: pd.DataFrame, n_teams: int) -> list[str]:
    """The waiver-tier defenses: teams **outside** the top ``n_teams`` by prior-season total DST
    points — the elite units are rostered, the rest are the realistic streaming wire (PIT)."""
    totals = prior_tbl.groupby("team")["pts_for"].sum().sort_values(ascending=False)
    return list(totals.index[n_teams:])


def _ratings_asof(tbl: pd.DataFrame, prior_own: dict, prior_allow: dict, league_mean: float,
                  through_week: int, prior_games: float) -> tuple[dict, dict, dict]:
    """Shrunk own/opp-allow ratings from weeks ``≤ through_week`` (``through_week = 0`` ⇒ pure
    prior). Returns ``(own, allow, n_seen)`` dicts over every team seen this or last season."""
    sub = tbl[tbl["week"] <= through_week]
    own_m = sub.groupby("team")["pts_for"].agg(["mean", "count"])
    allow_m = sub.groupby("team")["pts_against"].agg(["mean", "count"])
    teams = set(prior_own) | set(prior_allow) | set(own_m.index)
    own, allow, n_seen = {}, {}, {}
    for team in teams:
        po, pa = prior_own.get(team, league_mean), prior_allow.get(team, league_mean)
        if team in own_m.index:
            n = int(own_m.loc[team, "count"])
            own[team] = _shrink(float(own_m.loc[team, "mean"]), n, po, prior_games)
            allow[team] = _shrink(float(allow_m.loc[team, "mean"]), n, pa, prior_games)
            n_seen[team] = n
        else:
            own[team], allow[team], n_seen[team] = po, pa, 0
    return own, allow, n_seen


def _cluster_ci(diff: np.ndarray, cluster: np.ndarray, n_boot: int, seed: int,
                alpha: float = 0.05) -> tuple[float, float]:
    """Percentile CI of the mean of ``diff`` resampling whole ``cluster``s (managers) — the honest
    error bar when one manager contributes many correlated weekly diffs."""
    order = np.argsort(cluster, kind="stable")
    diff = diff[order]
    _, starts = np.unique(cluster[order], return_index=True)
    groups = np.split(diff, starts[1:])
    rng = np.random.default_rng(seed)
    n = len(groups)
    means = np.array([np.concatenate([groups[i] for i in rng.integers(0, n, n)]).mean()
                      for _ in range(n_boot)])
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


# ------------------------------------------------------------------------------------------------
# the done-bar: matchup-streaming beats static-hold (and random-streaming) on realized DST points
# ------------------------------------------------------------------------------------------------
def streaming_skill(con, season: int, *, n_managers: int = 300, pool_size: int = 8,
                    reg_weeks: int = 14, prior_games: float = PRIOR_GAMES,
                    switch_margin: float = SWITCH_MARGIN, ruleset: RuleSet | None = None,
                    n_boot: int = 2000, seed: int = 0) -> dict:
    """Walk-forward: does matchup-streaming beat static-hold over a season of DST streaming?

    Each of ``n_managers`` managers gets a random ``pool_size`` subset of the waiver-tier defenses
    (their realistic accessible wire). Three strategies play the same subset over weeks
    ``1..reg_weeks``: **static-hold** rosters the subset's preseason-best unit and starts it every
    week (0 on its bye); **matchup-streaming** starts each week's projected best available unit
    (:func:`stream_pick`, PIT ratings through the *prior* week, switch hysteresis);
    **random-streaming** starts a random available unit. We score **realized** points and compare,
    paired within manager, with a manager-clustered CI. Done-when: matchup-streaming's realized
    points/week exceed static-hold with a CI excluding 0 (and, as a signal check, exceed random)."""
    prior_tbl = _dst_matchup_table(con, season - 1, ruleset)
    prior_own = prior_tbl.groupby("team")["pts_for"].mean().to_dict()
    prior_allow = prior_tbl.groupby("team")["pts_against"].mean().to_dict()
    league_mean = float(prior_tbl["pts_for"].mean())
    pool = _streamer_pool(prior_tbl, 10)

    tbl = _dst_matchup_table(con, season, ruleset)
    tbl = tbl[tbl["week"] <= reg_weeks]
    real = {(r.team, int(r.week)): float(r.pts_for) for r in tbl.itertuples(index=False)}
    opp_of = {(r.team, int(r.week)): r.opp for r in tbl.itertuples(index=False)}

    weeks = list(range(1, reg_weeks + 1))
    proj: dict[tuple[str, int], float] = {}       # (team, week) -> PIT matchup projection
    for t in weeks:
        own, allow, _ = _ratings_asof(tbl, prior_own, prior_allow, league_mean, t - 1, prior_games)
        for team in pool:
            o = opp_of.get((team, t))
            if o is None:                          # bye / no game this week -> not startable
                continue
            proj[(team, t)] = matchup_projection(
                own.get(team, league_mean), allow.get(o, league_mean), league_mean)

    rng = np.random.default_rng(seed)
    pool_arr = np.array(pool)
    d_static, d_random, cluster = [], [], []
    stream_pts, static_pts, random_pts, switches = [], [], [], []
    for mgr in range(n_managers):
        subset = (list(pool) if len(pool) <= pool_size
                  else list(rng.choice(pool_arr, size=pool_size, replace=False)))
        hold_unit = max(subset, key=lambda tm: prior_own.get(tm, league_mean))
        held: str | None = None
        n_switch = 0
        for t in weeks:
            cand = [tm for tm in subset if (tm, t) in proj]
            s_pts = real.get((hold_unit, t), 0.0)                    # static-hold (0 on its bye)
            if cand:
                pvec = np.array([proj[(tm, t)] for tm in cand])
                held_i = cand.index(held) if held in cand else None
                pick = cand[stream_pick(pvec, held=held_i, switch_margin=switch_margin)]
                n_switch += int(held is not None and pick != held)
                held = pick
                m_pts = real.get((pick, t), 0.0)
                r_pts = real.get((cand[int(rng.integers(len(cand)))], t), 0.0)
            else:
                m_pts = r_pts = 0.0
            stream_pts.append(m_pts)
            static_pts.append(s_pts)
            random_pts.append(r_pts)
            d_static.append(m_pts - s_pts)
            d_random.append(m_pts - r_pts)
            cluster.append(mgr)
        switches.append(n_switch)

    ds, dr, cl = np.asarray(d_static), np.asarray(d_random), np.asarray(cluster)
    lo_s, hi_s = _cluster_ci(ds, cl, n_boot, seed)
    lo_r, hi_r = _cluster_ci(dr, cl, n_boot, seed)
    return {
        "season": int(season), "n_managers": int(n_managers), "pool_size": int(pool_size),
        "n_pool": int(len(pool)),
        "stream_ppw": float(np.mean(stream_pts)), "static_ppw": float(np.mean(static_pts)),
        "random_ppw": float(np.mean(random_pts)),
        "stream_minus_static_ppw": float(ds.mean()), "static_gain_ci": (lo_s, hi_s),
        "stream_minus_random_ppw": float(dr.mean()), "random_gain_ci": (lo_r, hi_r),
        "avg_switches": float(np.mean(switches)),
        "beats_static": bool(lo_s > 0.0), "beats_random": bool(lo_r > 0.0),
    }
