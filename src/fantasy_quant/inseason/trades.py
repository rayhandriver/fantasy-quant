"""Phase 13.5 — trades (market-making across the league).

A trade is the one in-season move that is **cooperative**: two managers only shake hands when
*both* rosters come out ahead. That is possible because a fantasy team scores its **optimal starting
lineup**, not its raw talent — so a player's worth is his *marginal* contribution to a team's
startable lineup, which falls off a cliff past that roster's positional need (a 4th good RB on an
RB-deep team rides the bench at ~0; the same RB fills a hole on an RB-poor team). Trades arbitrage
those **complementary surpluses**: Team A ships from a position it is deep, Team B ships where *it*
is deep, and each turns idle bench depth into a starter upgrade. The league is the
market and the model is the market-maker hunting mispriced, mutually-profitable deals. Two forces —
the pure kernels turn them into a decision:

  1. **Roster-constrained value.** :func:`lineup_value` scores a roster by its optimal starting
     lineup *only* (reusing the 13.2 greedy fill) — the diminishing-returns lesson of 13.3/13.4 made
     positional. :func:`evaluate_trade` prices a swap as the *change* in each team's lineup value; a
     deal is **mutual** only when **both** sides gain more than ``accept_margin`` — the transaction-
     cost hysteresis, so the maker demands a real upgrade for each side, not a churn of two benches.
  2. **Buy-low / sell-high.** When a **market perception** diverges from model value, the maker
     prefers to **ship** players the market over-rates (sell high) and **acquire** ones it under-
     rates (buy low): that gap is free edge. :func:`find_trades` searches every opponent roster for
     mutually-beneficial 1-for-1 (and, as a capability, 2-for-1 consolidation) deals and — given
     perceptions — ranks toward selling high / buying low.

The 13.5 done-bar (:func:`trade_skill`) is that trades the maker *proposes* actually **raise both
teams' simulated playoff probability** in the Phase-10 Monte-Carlo season engine (schedule, H2H
variance, playoffs — everything the additive lineup-value proxy ignores), on DEV seasons. A
**random-trade control** (swap at random) isolates that the *surplus logic*, not mere roster
shuffling, is what lifts both sides — the 13.3/13.4 smart-vs-naive analog.

Scope: the value currency is the preseason model's rest-of-season mean, **self-consistent** with the
sim that scores it, so the bar is PIT-trivial and fair (the model trains strictly before the
season). In-season the perceived value would be 13.1's re-projected mean over weeks ``≤ t`` — fed in
as the ``values`` argument, not re-derived here (the same 13.4→13.1 extension pattern). The done-bar
trades 1-for-1 (count-neutral, so no roster-size bookkeeping); 2-for-1 consolidation is supported by
the kernels and unit-tested, but left out of the sim to keep every roster at legal size.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from fantasy_quant.backtest.scoring import RuleSet
from fantasy_quant.draft.simulator import RosterSlots
from fantasy_quant.inseason.lineup import _fill
from fantasy_quant.simulation.season import (
    LeagueFormat,
    lineup_points_matrix,
    round_robin_schedule,
    simulate_league,
)
from fantasy_quant.simulation.weekly import OFFENSE, build_weekly_model

ACCEPT_MARGIN = 5.0     # starting-lineup value (season pts) each side must gain — anti-churn; DEV
GIVE_K = 5              # surplus give-candidates considered on the maker's roster
RECV_K = 5              # surplus receive-candidates considered per opponent roster


# ------------------------------------------------------------------------------------------------
# pure kernels (the unit-test targets)
# ------------------------------------------------------------------------------------------------
def lineup_value(values, positions, slots: RosterSlots) -> float:
    """Roster-constrained value: the sum of the **optimal starting lineup**'s player values, filling
    each slot greedily with its highest-value eligible player (dedicated slots then FLEX, the 13.2
    convention). Bench depth contributes 0 — the diminishing-returns lesson made positional."""
    values = np.asarray(values, float)
    pos = np.asarray(list(positions))
    idx = [i for i in _fill(values, pos, slots).values() if i is not None]
    return float(values[idx].sum()) if idx else 0.0


@dataclass(frozen=True)
class TradeEval:
    """The value change a swap produces for each side, and whether it clears mutual benefit."""
    delta_a: float          # change in team A's starting-lineup value
    delta_b: float          # change in team B's starting-lineup value
    mutual: bool            # both sides gain more than accept_margin


def evaluate_trade(a_values, a_pos, b_values, b_pos, give_a, give_b, slots: RosterSlots, *,
                   accept_margin: float = ACCEPT_MARGIN) -> TradeEval:
    """Price a swap of A's ``give_a`` (indices into A's roster) for B's ``give_b`` as the change in
    each team's :func:`lineup_value`. Rosters are aligned ``values``/``pos`` arrays; a value travels
    with its player (the model doesn't re-rate a player for changing teams). ``mutual`` = both
    deltas exceed ``accept_margin`` (the transaction-cost hysteresis). Pure."""
    a_values, a_pos = list(map(float, a_values)), list(a_pos)
    b_values, b_pos = list(map(float, b_values)), list(b_pos)
    ga, gb = set(give_a), set(give_b)
    a_new = ([(a_values[i], a_pos[i]) for i in range(len(a_pos)) if i not in ga]
             + [(b_values[j], b_pos[j]) for j in gb])            # A keeps the rest, gains B's give
    b_new = ([(b_values[j], b_pos[j]) for j in range(len(b_pos)) if j not in gb]
             + [(a_values[i], a_pos[i]) for i in ga])            # B keeps the rest, gains A's give
    da = lineup_value([v for v, _ in a_new], [p for _, p in a_new], slots) \
        - lineup_value(a_values, a_pos, slots)
    db = lineup_value([v for v, _ in b_new], [p for _, p in b_new], slots) \
        - lineup_value(b_values, b_pos, slots)
    return TradeEval(delta_a=da, delta_b=db,
                     mutual=bool(da > accept_margin and db > accept_margin))


@dataclass(frozen=True)
class TradeProposal:
    """A mutually-beneficial deal the maker would offer ``partner``."""
    partner: int            # index into the opponents list passed to find_trades
    give: tuple             # player_keys the maker sends
    receive: tuple          # player_keys the maker gets back
    my_gain: float          # the maker's starting-lineup value gain
    their_gain: float       # the partner's starting-lineup value gain
    edge: float             # market-vs-model edge captured (sell-high + buy-low); 0 with no market


def _benched(values, positions, slots: RosterSlots, k: int) -> list[int]:
    """The tradeable **surplus**: roster indices *not* in the optimal starting lineup, the ``k``
    highest-value first — a manager shops from the good players he cannot start."""
    values = np.asarray(values, float)
    starters = {i for i in _fill(values, np.asarray(list(positions)), slots).values()
                if i is not None}
    bench = sorted((i for i in range(len(positions)) if i not in starters),
                   key=lambda i: -values[i])
    return bench[:k]


def _legal(positions, slots: RosterSlots) -> bool:
    """A roster is legal if it can field every starting slot and violates no positional cap."""
    pos = list(positions)
    if len(pos) > slots.total:
        return False
    caps = slots.pos_caps
    counts: dict[str, int] = {}
    for p in pos:
        counts[p] = counts.get(p, 0) + 1
        if counts[p] > caps.get(p, 99):
            return False
    return all(v is not None
               for v in _fill(np.ones(len(pos)), np.asarray(pos), slots).values())


def find_trades(my_roster, opponents, values, slots: RosterSlots, *, market=None,
                accept_margin: float = ACCEPT_MARGIN, give_k: int = GIVE_K, recv_k: int = RECV_K,
                max_give: int = 1, rank: str = "balanced") -> list[TradeProposal]:
    """Search every opponent roster for mutually-beneficial deals — the market-maker.

    ``my_roster`` and each entry of ``opponents`` are ``[(player_key, pos), ...]``; ``values`` maps
    a key to its (roster-agnostic) value; ``market``, if given, maps a key to its **perceived**
    value for buy-low/sell-high. From the maker's surplus (:func:`_benched`) against each opponent's
    surplus, we enumerate 1-for-1 (and, when ``max_give ≥ 2``, 2-for-1 consolidation) swaps, keep
    the ones :func:`evaluate_trade` rates **mutual** and that leave *both* rosters legal, and rank
    them — ``rank="balanced"`` (default) by the **worse-off side's** gain ``min(mine, theirs)``, the
    fairest win-win a completed trade needs *both* GMs to sign; ``rank="mine"`` by the maker's own
    gain (a self-interested skim). Ties break toward the largest sell-high/buy-low ``edge``. Pure.
    """
    my_keys = [k for k, _ in my_roster]
    my_v = [values[k] for k in my_keys]
    my_p = [p for _, p in my_roster]
    give_pool = _benched(my_v, my_p, slots, give_k)

    def edge_of(give_keys, recv_keys) -> float:
        if market is None:
            return 0.0
        sell = sum(market.get(k, values[k]) - values[k] for k in give_keys)   # ship over-rated
        buy = sum(values[k] - market.get(k, values[k]) for k in recv_keys)    # get under-rated
        return float(sell + buy)

    give_sets = [(i,) for i in give_pool]
    if max_give >= 2:
        give_sets += [(give_pool[a], give_pool[b])
                      for a in range(len(give_pool)) for b in range(a + 1, len(give_pool))]

    proposals: list[TradeProposal] = []
    for oi, opp in enumerate(opponents):
        opp_keys = [k for k, _ in opp]
        opp_v = [values[k] for k in opp_keys]
        opp_p = [p for _, p in opp]
        recv_pool = _benched(opp_v, opp_p, slots, recv_k)
        for gset in give_sets:
            for j in recv_pool:
                ev = evaluate_trade(my_v, my_p, opp_v, opp_p, gset, (j,), slots,
                                    accept_margin=accept_margin)
                if not ev.mutual:
                    continue
                give_keys = tuple(my_keys[i] for i in gset)
                recv_keys = (opp_keys[j],)
                my_after = ([my_p[i] for i in range(len(my_p)) if i not in set(gset)]
                            + [opp_p[j]])
                opp_after = ([opp_p[x] for x in range(len(opp_p)) if x != j]
                             + [my_p[i] for i in gset])
                if not (_legal(my_after, slots) and _legal(opp_after, slots)):
                    continue
                proposals.append(TradeProposal(
                    partner=oi, give=give_keys, receive=recv_keys,
                    my_gain=ev.delta_a, their_gain=ev.delta_b,
                    edge=edge_of(give_keys, recv_keys)))
    primary = ((lambda t: min(t.my_gain, t.their_gain)) if rank == "balanced"
               else (lambda t: t.my_gain))
    proposals.sort(key=lambda t: (primary(t), t.edge, t.my_gain + t.their_gain), reverse=True)
    return proposals


# ------------------------------------------------------------------------------------------------
# the done-bar: proposed trades raise both teams' simulated playoff probability
# ------------------------------------------------------------------------------------------------
_KDST_VALUE = 80.0      # flat value for the K/DST placeholders — a dedicated slot, never surplus


def _targets(rng: np.random.Generator, n_teams: int, off_slots: int) -> list[dict]:
    """Per-team offense position targets summing to ``off_slots`` — the *deliberate* imbalance that
    creates the surpluses trades arbitrage (an RB-heavy team drafts opposite a WR-heavy one)."""
    out = []
    for _ in range(n_teams):
        qb, te = int(rng.integers(1, 3)), int(rng.integers(1, 3))
        rem = off_slots - qb - te
        lo, hi = max(3, rem - 6), min(6, rem - 3)
        rb = int(rng.integers(lo, hi + 1))
        out.append({"QB": qb, "RB": rb, "WR": rem - rb, "TE": te})
    return out


def _draft_league(keys, vals, poss, n_teams: int, slots: RosterSlots,
                  rng: np.random.Generator, jitter: float = 0.12) -> list[list[tuple[str, str]]]:
    """A need-aware snake draft of offense onto ``n_teams`` rosters (targets from :func:`_targets`,
    a per-league value jitter for variety), then a placeholder K + DST per team. Rosters come out
    fieldable with built-in positional surplus."""
    off_slots = slots.total - slots.k - slots.dst
    board = sorted(range(len(keys)), key=lambda i: -vals[i] * rng.lognormal(0.0, jitter))
    targets = _targets(rng, n_teams, off_slots)
    counts = [{"QB": 0, "RB": 0, "WR": 0, "TE": 0} for _ in range(n_teams)]
    rosters: list[list[tuple[str, str]]] = [[] for _ in range(n_teams)]
    taken: set[int] = set()
    order = list(range(n_teams))
    for rnd in range(off_slots):
        for t in (order if rnd % 2 == 0 else order[::-1]):
            need = [p for p in ("QB", "RB", "WR", "TE") if counts[t][p] < targets[t][p]]
            pick = next((i for i in board if i not in taken and poss[i] in need), None)
            if pick is None:                                     # targets met: best legal filler
                pick = next((i for i in board if i not in taken
                             and counts[t][poss[i]] < slots.pos_caps.get(poss[i], 99)), None)
            if pick is None:
                continue
            taken.add(pick)
            counts[t][poss[pick]] += 1
            rosters[t].append((keys[pick], poss[pick]))
    for t in range(n_teams):
        rosters[t] += [(f"_K{t}", "K"), (f"_DST{t}", "DST")]
    return rosters


def _cluster_ci(diff: np.ndarray, cluster: np.ndarray, n_boot: int, seed: int,
                alpha: float = 0.05) -> tuple[float, float]:
    """Percentile CI of the mean of ``diff`` resampling whole ``cluster``s (leagues) — the honest
    error bar when one league contributes several correlated trade outcomes."""
    order = np.argsort(cluster, kind="stable")
    diff = diff[order]
    _, starts = np.unique(cluster[order], return_index=True)
    groups = np.split(diff, starts[1:])
    rng = np.random.default_rng(seed)
    n = len(groups)
    means = np.array([np.concatenate([groups[i] for i in rng.integers(0, n, n)]).mean()
                      for _ in range(n_boot)])
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def _team_weekly(roster, cache: dict, slots: RosterSlots) -> np.ndarray:
    """A team's ``(n_sims, n_weeks)`` optimal-lineup points from the shared per-player cache."""
    pts = np.stack([cache[k] for k, _ in roster])
    return lineup_points_matrix(pts, [p for _, p in roster], slots)


def _resim(tw, cache, slots, fmt, schedule, base_pp, f, partner, f_roster, p_roster):
    """Playoff-prob change for the two teams a trade touches, re-scoring only their lineups against
    the *same* draws and schedule (a paired comparison) — the rest of ``tw`` is untouched."""
    tw2 = tw.copy()
    tw2[f] = _team_weekly(f_roster, cache, slots)
    tw2[partner] = _team_weekly(p_roster, cache, slots)
    pp = simulate_league(tw2, fmt, schedule).made_playoffs.mean(axis=1)
    return pp[f] - base_pp[f], pp[partner] - base_pp[partner]


def trade_skill(con, season: int, *, n_leagues: int = 40, n_teams: int = 10, reg_weeks: int = 14,
                n_focal: int = 4, sims: int = 300, accept_margin: float = ACCEPT_MARGIN,
                market_noise: float = 0.15, ruleset: RuleSet | None = None, n_draws: int = 800,
                n_boot: int = 2000, seed: int = 0) -> dict:
    """Walk-forward: do proposed trades raise **both** teams' simulated playoff probability?

    Per league we snake-draft ``n_teams`` imbalanced rosters (:func:`_draft_league`), precompute a
    shared per-player weekly-points cache and a fixed schedule (so pre/post sims differ *only* by
    the two swapped rosters — a paired, low-variance comparison), and baseline every team's playoff
    probability through the Phase-10 engine. For ``n_focal`` maker seats we call :func:`find_trades`
    (1-for-1, balanced win-win ranking, market perceptions on), execute the top proposal,
    re-simulate, and record the change in the maker's and partner's playoff probability. A
    **random-trade control** swaps equal counts at random. Done-when: **both** the maker's and the
    partner's *mean* playoff-prob change are positive with league-clustered CIs excluding 0 — i.e.
    proposed trades raise both teams' win% — and they lift both sides far more often than random
    swaps (``both_rise`` ≫ the control). ``pair_min`` (the mean per-trade worse side) is reported
    but not gated — the per-trade min of two ~+0.01 gains is dominated by Monte-Carlo noise. Value =
    the preseason model rest-of-season mean (self-consistent with the sim); PIT; lockbox unread."""
    model = build_weekly_model(con, season, ruleset, n_draws=n_draws, seed=seed)
    slots = RosterSlots()
    fmt = LeagueFormat(n_teams=n_teams, reg_weeks=reg_weeks)

    s = model.summary
    off = s[s["pos"].isin(OFFENSE)].sort_values("mean", ascending=False)
    take = min(len(off), n_teams * (slots.total - slots.k - slots.dst) + 4 * n_teams)
    off = off.head(take)
    keys = off["player_key"].tolist()
    poss = off["pos"].tolist()
    base_val = {k: float(v) for k, v in zip(off["player_key"], off["mean"], strict=False)}
    vals = [base_val[k] for k in keys]

    rng = np.random.default_rng(seed)
    cache_rng = np.random.default_rng(seed + 7)
    n_focal = min(n_focal, n_teams)

    maker_g, partner_g, pair_min = [], [], []
    both_rise, both_rise_rand, sold_high = [], [], []
    cluster = []
    n_props = 0
    for lg in range(n_leagues):
        rosters = _draft_league(keys, vals, poss, n_teams, slots, rng)
        values = dict(base_val)
        for r in rosters:                                        # K/DST placeholders: flat value
            for k, _ in r:
                values.setdefault(k, _KDST_VALUE)
        market = {k: base_val[k] * rng.lognormal(0.0, market_noise) for k in keys}

        sim_cols = rng.choice(model.n_draws, min(sims, model.n_draws), replace=False)
        cache: dict[str, np.ndarray] = {}
        for r in rosters:
            for k, p in r:
                if k not in cache:
                    cache[k] = model.player_weekly(k, p, sim_cols, cache_rng)

        schedule = round_robin_schedule(n_teams, reg_weeks, rng)
        tw = np.stack([_team_weekly(r, cache, slots) for r in rosters])
        base_pp = simulate_league(tw, fmt, schedule).made_playoffs.mean(axis=1)

        for f in rng.choice(n_teams, n_focal, replace=False):
            others = [t for t in range(n_teams) if t != f]
            props = find_trades(rosters[f], [rosters[t] for t in others], values, slots,
                                market=market, accept_margin=accept_margin)
            if not props:
                continue
            p0 = props[0]
            partner = others[p0.partner]
            give, recv = set(p0.give), set(p0.receive)
            f_new = ([(k, p) for k, p in rosters[f] if k not in give]
                     + [(k, p) for k, p in rosters[partner] if k in recv])
            p_new = ([(k, p) for k, p in rosters[partner] if k not in recv]
                     + [(k, p) for k, p in rosters[f] if k in give])
            df, dp = _resim(tw, cache, slots, fmt, schedule, base_pp, f, partner, f_new, p_new)
            maker_g.append(df)
            partner_g.append(dp)
            pair_min.append(min(df, dp))
            both_rise.append(df > 0 and dp > 0)
            sold_high.append(p0.edge > 0)
            cluster.append(lg)
            n_props += 1

            # random control: swap equal counts at random with a random partner
            q = int(rng.choice(others))
            gi = list(rng.choice(len(rosters[f]), len(give), replace=False))
            ri = list(rng.choice(len(rosters[q]), len(recv), replace=False))
            gk = {rosters[f][i][0] for i in gi}
            rk = {rosters[q][i][0] for i in ri}
            f_rand = ([(k, p) for k, p in rosters[f] if k not in gk]
                      + [(k, p) for k, p in rosters[q] if k in rk])
            q_rand = ([(k, p) for k, p in rosters[q] if k not in rk]
                      + [(k, p) for k, p in rosters[f] if k in gk])
            rdf, rdq = _resim(tw, cache, slots, fmt, schedule, base_pp, f, q, f_rand, q_rand)
            both_rise_rand.append(rdf > 0 and rdq > 0)

    mk, pt, pm = np.asarray(maker_g), np.asarray(partner_g), np.asarray(pair_min)
    cl = np.asarray(cluster)
    nan2 = (float("nan"), float("nan"))
    mk_ci = _cluster_ci(mk, cl, n_boot, seed) if n_props else nan2
    pt_ci = _cluster_ci(pt, cl, n_boot, seed) if n_props else nan2
    both_rate = float(np.mean(both_rise)) if n_props else float("nan")
    rand_rate = float(np.mean(both_rise_rand)) if both_rise_rand else float("nan")
    return {
        "season": int(season), "n_leagues": int(n_leagues), "n_trades": int(n_props),
        "maker_gain": float(mk.mean()) if n_props else float("nan"), "maker_ci": mk_ci,
        "partner_gain": float(pt.mean()) if n_props else float("nan"), "partner_ci": pt_ci,
        "weaker_side_gain": float(min(mk.mean(), pt.mean())) if n_props else float("nan"),
        "pair_min_gain": float(pm.mean()) if n_props else float("nan"),
        "both_rise_rate": both_rate, "random_both_rise_rate": rand_rate,
        "sell_high_rate": float(np.mean(sold_high)) if n_props else float("nan"),
        "raises_both": bool(n_props and mk.mean() > 0.0 and pt.mean() > 0.0),
        "raises_both_ci": bool(n_props and mk_ci[0] > 0.0 and pt_ci[0] > 0.0),
        "beats_random": bool(n_props and both_rate > rand_rate),
    }
