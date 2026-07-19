"""Phase 13.3 — waivers / FAAB (allocating a season-long budget across a stream of pickups).

The waiver wire is a **sequential budget auction**. Each week a few free agents appear; you have a
fixed FAAB budget for the whole rest of the season and every dollar you spend now is a dollar you
cannot spend on a better pickup later. Bidding well means balancing three forces — the pure
:func:`faab_bid` turns them into one number:

  1. **Marginal value.** What a pickup is *worth to you* is his rest-of-season points **above the
     freely-available replacement** at his position (13.1's re-projected level × the weeks left),
     not a flat fraction of your wallet. A league-winning breakout and a bye-week fill-in should not
     draw the same bid.
  2. **The option value of budget.** A dollar has an *opportunity cost*: the better pickup it could
     win later. Early in the season, with many weeks (and many future breakouts) ahead, you
     **ration** — shade every bid down. As the season ends the option value vanishes
     (use-it-or-lose-it) and you spend freely up to full value. ``option_kappa`` sets how hard you
     hoard early.
  3. **First-price shading.** FAAB is a sealed first-price auction: you pay what you bid, so you
     never bid your full value — you bid just enough to *probably* win, capturing the surplus. Given
     a belief about the field's bids (``opp_bids``) we pick the bid that maximises expected surplus
     ``(value − bid) · P(win | bid)``.

Naive "%-of-budget" bidding ignores all three (same bid for a stud and a streamer, no rationing, no
shading). The 13.3 done-bar (:func:`faab_skill`) is that a bidder using :func:`faab_bid` **beats
naive %-of-budget** for total realized value acquired, in a *mixed* league (both sharp and naive
opponents), on DEV seasons.

Scope note (user decision 2026-07-12): this shipped as the **pragmatic** FAAB bidder — a
marginal-value
+ option-value + fixed-belief-shading heuristic. **T9 discharged (2026-07-13):**
``draft/auction.py``
(Phase 15.4) now exists, so :func:`faab_bid` can consume the rigorous **budget-state continuation
cap**
(:func:`fantasy_quant.draft.auction.endgame_cap`, the exact stochastic-knapsack "$1 endgame") in
place
of the closed-form option-value ration — pass ``slots_remaining`` (the number of useful pickups
still
ahead) and the willingness-to-pay is capped so you can always still make them. The closed-form
ration
stays the default (so the validated 13.3 done-bar is untouched); :func:`faab_skill` exercises the
upgraded path under ``use_auction=True``. Everything here is PIT: perceived values come from 13.1
re-projection on weeks ``≤ t``; realized value (weeks ``> t``) is only ever used to *score* the sim.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.backtest.scoring import RuleSet
from fantasy_quant.inseason.reproject import (
    PRIOR_WEEKS,
    preseason_prior,
    realized_weekly,
    reproject_week,
)
from fantasy_quant.simulation.weekly import OFFENSE, build_weekly_model

OPTION_KAPPA = 0.15     # budget-rationing strength: ration = 1/(1+kappa·(weeks_left−1)); DEV-tuned
SHADE_FRAC = 0.9        # fixed first-price shade when no opponent-bid belief is supplied
NAIVE_FRAC = 0.25       # the baseline strategy: bid this fraction of remaining budget on the top FA


def faab_bid(value: float, budget_remaining: float, weeks_remaining: int, *,
             value_scale: float, opp_bids=None, option_kappa: float = OPTION_KAPPA,
             shade_frac: float = SHADE_FRAC, slots_remaining: int | None = None) -> float:
    """The bid (in $) for one free agent — marginal value, rationed and shaded.

    ``value`` is the pickup's marginal rest-of-season value **in points** (points over replacement ×
    weeks left; ``≤ 0`` ⇒ don't bid). ``value_scale`` is the pool's **points-per-dollar** — it maps
    points to a willingness-to-pay so a marquee pickup is worth roughly a full budget. ``opp_bids``,
    if given, is a sample of anticipated opponent bids ($) used to shade in a first-price auction;
    if omitted we fall back to a flat ``shade_frac``.

    The pipeline: ``wtp = value / value_scale`` (dollar willingness-to-pay) → cap it by the option
    value of budget → ``v_eff`` → **shade** to the surplus-maximising bid against ``opp_bids`` (or
    ``shade_frac·v_eff``). The cap has two forms: the default **closed-form ration**
    ``1/(1 + option_kappa·(weeks_remaining − 1))`` × budget; or, when ``slots_remaining`` is given
    (T9), the **exact budget-state continuation cap**
    :func:`~fantasy_quant.draft.auction.endgame_cap`
    — never spend so much you can't still make ``slots_remaining − 1`` future pickups at $1.
    Returns 0
    when the pickup isn't worth bidding. Pure; callers round to integer dollars if their league
    does."""
    if value <= 0 or budget_remaining <= 0 or value_scale <= 0:
        return 0.0
    wtp = value / value_scale
    if slots_remaining is not None:                     # T9: rigorous budget-state continuation cap
        from fantasy_quant.draft.auction import endgame_cap
        v_eff = min(wtp, endgame_cap(budget_remaining, slots_remaining))
    else:                                               # default: closed-form option-value ration
        ration = 1.0 / (1.0 + max(option_kappa, 0.0) * max(weeks_remaining - 1, 0))
        v_eff = min(wtp * ration, float(budget_remaining))
    if v_eff <= 0:
        return 0.0

    opp = np.asarray(opp_bids, float) if opp_bids is not None else None
    if opp is None or opp.size == 0:
        return float(min(shade_frac * v_eff, budget_remaining))

    # first-price surplus max: bid just enough to clear the field. Candidates = a grid plus each
    # opponent bid nudged up (the "just outbid them" points), all within [0, v_eff].
    grid = np.linspace(0.0, v_eff, 21)
    cands = np.unique(np.concatenate([grid, opp + 1e-6]))
    cands = cands[(cands >= 0.0) & (cands <= v_eff)]
    p_win = (cands[:, None] > opp[None, :]).mean(axis=1)
    surplus = (v_eff - cands) * p_win
    return float(min(cands[int(np.argmax(surplus))], budget_remaining))


# ------------------------------------------------------------------------------------------------
# the done-bar: a faab_bid agent beats naive %-of-budget for value acquired, in a mixed league
# ------------------------------------------------------------------------------------------------
_OFFENSE_STARTERS = 6           # 1QB·2RB·2WR·1TE — the obvious starters a league drafts per team


def _replacement_ppw(prior: pd.DataFrame, pct: float = 40.0) -> dict[str, float]:
    """Per-position waiver replacement level (points/week): a low percentile of the preseason
    per-week levels. It only sets a common zero-point for value — the smart-vs-naive comparison is
    invariant to its exact level (both strategies see the same values)."""
    return {pos: float(np.percentile(g["m0"], pct)) for pos, g in prior.groupby("pos")}


def _waiver_universe(prior: pd.DataFrame, n_teams: int) -> list[str]:
    """The free-agent pool: offense players **outside** the top ``n_teams·6`` by preseason level —
    i.e. not the obvious drafted starters, the realistic waiver wire (breakouts live here)."""
    off = prior[prior["pos"].isin(OFFENSE)].sort_values("m0", ascending=False)
    return list(off["player_key"].to_numpy()[n_teams * _OFFENSE_STARTERS:])


def _round_values(prior, realized, universe, repl, pos_of, t, reg_weeks, rp):
    """Perceived (PIT, 13.1) and realized (weeks > t) rest-of-season value-over-replacement per free
    agent available at decision week ``t``. ``v_perc`` drives bids; ``v_real`` scores the sim."""
    weeks_left = reg_weeks - t
    perc = reproject_week(prior, realized, t).week_mean()
    v_perc, v_real = {}, {}
    for k in universe:
        base = repl.get(pos_of[k], 0.0)
        v_perc[k] = max(0.0, perc.get(k, 0.0) - base) * weeks_left
        realized_total = sum(rp.get((k, w), 0.0) for w in range(t + 1, reg_weeks + 1))
        v_real[k] = realized_total - base * weeks_left
    return v_perc, v_real


def _naive_bid(budget_remaining: float, frac: float) -> float:
    """The baseline: a flat fraction of remaining budget, regardless of how good the pickup is."""
    return frac * budget_remaining


def _topk_sum(vals: list[float], k: int) -> float:
    """Season value from a set of pickups = the sum of the best ``k`` (positive) — only the pickups
    that crack a startable slot contribute (diminishing returns; the rest ride the bench at ~0)."""
    return float(sum(sorted((v for v in vals if v > 0), reverse=True)[:k]))


def _run_league(rounds, v_perc, v_real, universe, *, n_teams, total_budget, value_scale,
                naive_frac, option_kappa, opp_bids_ref, perc_noise, reg_weeks, n_useful, rng,
                use_auction=False):
    """One league: N teams bid into the shared, depleting FA pool across the waiver ``rounds``.

    Seat 0 is the sharp :func:`faab_bid` agent, seat 1 the naive %-of-budget baseline, the rest
    alternate (a *mixed* field — the sharp agent competes with equally-sharp opponents, not only
    fish). Each team targets its highest **perceived** FA (its own perception noise); the naive team
    bids a flat fraction of its wallet, the sharp team bids the **marginal** value over the pickups
    it already holds (so once it holds ``n_useful`` studs it stops overpaying and conserves budget
    for a genuine upgrade). Highest bid wins and pays it (first-price). A team's season value is its
    **top-``n_useful``** realized pickups (:func:`_topk_sum`); returns that and dollars spent."""
    strat = ["smart" if (s == 0 or s % 2 == 0) else "naive" for s in range(n_teams)]
    budgets = [float(total_budget)] * n_teams
    held_perc: list[list[float]] = [[] for _ in range(n_teams)]   # perceived values already held
    held_real: list[list[float]] = [[] for _ in range(n_teams)]   # realized values already held
    spent = [0.0] * n_teams
    acquired: set[str] = set()

    for t in rounds:
        avail = [k for k in universe if k not in acquired]
        if not avail:
            break
        weeks_left = reg_weeks - t
        vtrue = np.array([v_perc[t][k] for k in avail])
        bids_by_target: dict[str, list[tuple[int, float]]] = {}
        for seat in range(n_teams):
            if budgets[seat] <= 0:
                continue
            seen = vtrue * rng.lognormal(0.0, perc_noise, len(avail))   # this team's perception
            j = int(np.argmax(seen))
            if seen[j] <= 0:
                continue
            target = avail[j]
            if strat[seat] == "naive":
                bid = _naive_bid(budgets[seat], naive_frac)
            else:
                # marginal value = the upgrade over the weakest of the n_useful the team already
                # holds (0 until it holds that many) — a pickup that won't start is worth nothing.
                held = sorted(held_perc[seat], reverse=True)
                floor = held[n_useful - 1] if len(held) >= n_useful else 0.0
                marginal = max(0.0, float(seen[j]) - floor)
                # T9: the auction path caps by the exact budget-state continuation (slots still
                # ahead = useful pickups not yet held); the default path uses the closed-form
                # ration.
                slots_left = max(1, n_useful - len(held_perc[seat])) if use_auction else None
                bid = faab_bid(marginal, budgets[seat], weeks_left, value_scale=value_scale,
                               opp_bids=opp_bids_ref, option_kappa=option_kappa,
                               slots_remaining=slots_left)
            if bid > 0:
                bids_by_target.setdefault(target, []).append((seat, bid))

        for target, entries in bids_by_target.items():
            # highest bid wins; ties -> deeper wallet -> coin flip
            seat, bid = max(entries, key=lambda e: (e[1], budgets[e[0]], rng.random()))
            budgets[seat] -= bid
            spent[seat] += bid
            held_perc[seat].append(v_perc[t][target])
            held_real[seat].append(v_real[t][target])
            acquired.add(target)

    values = [_topk_sum(hr, n_useful) for hr in held_real]
    return values, spent


def _league_ci(diff: np.ndarray, n_boot: int, seed: int, alpha: float = 0.05):
    rng = np.random.default_rng(seed)
    means = diff[rng.integers(0, len(diff), (n_boot, len(diff)))].mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def faab_skill(con, season: int, *, n_leagues: int = 200, n_teams: int = 10,
               total_budget: float = 100.0, reg_weeks: int = 14, rounds=None, n_useful: int = 4,
               naive_frac: float = NAIVE_FRAC, option_kappa: float = OPTION_KAPPA,
               perc_noise: float = 0.25, ruleset: RuleSet | None = None, n_draws: int = 600,
               prior_weeks: float = PRIOR_WEEKS, n_boot: int = 2000, seed: int = 0,
               use_auction: bool = False) -> dict:
    """Walk-forward: does :func:`faab_bid` beat naive %-of-budget over a season of waivers?

    Builds the season's weekly model + 13.1 prior, defines the FA universe
    (:func:`_waiver_universe`) and each pickup's PIT perceived / realized value, then plays
    ``n_leagues`` independent mixed-field waiver seasons (:func:`_run_league`). The metric is the
    **top-``n_useful`` realized rest-of-season value acquired**; we compare the sharp seat (0) to
    the naive seat (1) **paired within each league** (same FA stream, same field). Done-when: the
    sharp agent's mean value gain > 0 with a league-clustered CI excluding 0. PIT; lockbox unread.
    """
    model = build_weekly_model(con, season, ruleset, n_draws=n_draws, seed=seed)
    prior = preseason_prior(model, prior_weeks=prior_weeks)
    pos_of = dict(zip(prior["player_key"], prior["pos"], strict=False))
    repl = _replacement_ppw(prior)
    universe = _waiver_universe(prior, n_teams)

    realized = realized_weekly(con, season, ruleset)
    realized = realized[realized["player_key"].isin(set(universe))]
    rp = {(r.player_key, int(r.week)): float(r.points) for r in realized.itertuples(index=False)}

    rounds = list(rounds) if rounds is not None else list(range(2, reg_weeks))
    v_perc, v_real = {}, {}
    for t in rounds:
        v_perc[t], v_real[t] = _round_values(prior, realized, universe, repl, pos_of, t,
                                              reg_weeks, rp)
    # value_scale: a marquee pickup (95th pct perceived value) ≈ a full budget of willingness-to-pay
    allv = np.array([v for d in v_perc.values() for v in d.values() if v > 0])
    ref = float(np.percentile(allv, 95)) if allv.size else 0.0
    value_scale = ref / total_budget if ref > 0 else 1.0
    # a belief about the field's bids: a naive opponent spends ~naive_frac of a 40–100% wallet
    opp_bids_ref = naive_frac * total_budget * np.array([0.4, 0.6, 0.8, 1.0])

    rng = np.random.default_rng(seed)
    smart_v, naive_v, smart_sp, naive_sp = [], [], [], []
    for _ in range(n_leagues):
        values, spent = _run_league(
            rounds, v_perc, v_real, universe, n_teams=n_teams, total_budget=total_budget,
            value_scale=value_scale, naive_frac=naive_frac, option_kappa=option_kappa,
            opp_bids_ref=opp_bids_ref, perc_noise=perc_noise, reg_weeks=reg_weeks,
            n_useful=n_useful, rng=rng, use_auction=use_auction)
        smart_v.append(values[0])
        naive_v.append(values[1])
        smart_sp.append(spent[0])
        naive_sp.append(spent[1])

    smart_v = np.asarray(smart_v)
    naive_v = np.asarray(naive_v)
    diff = smart_v - naive_v
    lo, hi = _league_ci(diff, n_boot, seed)
    eff = lambda v, s: float(np.sum(v) / max(np.sum(s), 1e-9))          # noqa: E731 — realized $ eff
    return {
        "season": int(season), "n_leagues": int(n_leagues), "n_teams": int(n_teams),
        "n_pool": int(len(universe)), "value_scale": float(value_scale),
        "smart_value": float(smart_v.mean()), "naive_value": float(naive_v.mean()),
        "value_gain": float(diff.mean()), "value_gain_ci": (lo, hi),
        "frac_leagues_smart_wins": float((diff > 0).mean()),
        "smart_value_per_dollar": eff(smart_v, smart_sp),
        "naive_value_per_dollar": eff(naive_v, naive_sp),
        "beats_naive": bool(lo > 0.0),
    }
