"""Phase 15.4 — auction-draft support (budget as a stochastic knapsack; the $1 endgame).

A snake draft asks *who to pick*; an **auction** draft asks *how much to pay* — every owner can bid
on
every player, so the whole roster is a budget-allocation problem. This module is the auction analog
of the
snake optimizer, and it also **discharges TECH-DEBT T9**: the pragmatic FAAB bidder (13.3) was
shipped with
a fixed points→dollar scale and a closed-form budget ration because this engine didn't exist yet;
the same
math (an auction value + a budget-state continuation cap) lives here now for both to consume.

Three ideas, three kernels:

* **Auction values** (:func:`auction_values`) — turn value-over-replacement into dollars. Every
rosterable
  player costs at least ``$min_bid``; the *surplus* budget (total wallets − the $1-per-slot floor)
  is split
  in proportion to VOR. So the studs soak up most of the money and the last roster slots go for a
  buck —
  the shape every published auction-value engine produces.
* **The $1 endgame** (:func:`endgame_cap`) — the budget-state constraint that makes it a *stochastic
  knapsack*: never bid so much that you can't still fill every remaining roster slot at
  ``$min_bid``. This
  is the continuation value in its hardest, exact form (a dollar you can't spend later is worth its
  option
  value), and it is what a naive bidder forgets — blowing the budget early and fielding $1 scrubs.
* **Winner's-curse-aware bidding** (:func:`auction_bid`) — you only win when everyone else drops,
which is
  evidence your estimate was high; a shade factor tempers the max bid toward the field. In an
  *English*
  (open-outcry) auction the winner pays the second price, so the load-bearing skill is bidding your
  true
  **marginal** value (value over your *own* current roster, not standalone VOR — a 4th RB is worth
  $1 to a
  full backfield) and respecting the endgame cap; the shade is a small extra guard.

:func:`nominate` rounds it out (put up a player you don't need to drain rivals' budgets; hoard your
targets
for when the field is cash-poor). The done-bar (:func:`auction_skill`): a smart bidder beats **naive
budget-splitting** (bid ``budget/slots`` on whatever's up, value-blind) for realized
starting-lineup value,
paired within each simulated auction. Pure kernels + a self-contained English-auction sim,
mirroring 13.3.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.backtest.scoring import RuleSet
from fantasy_quant.draft.simulator import RosterSlots
from fantasy_quant.inseason.lineup import _fill  # the shared greedy optimal-lineup fill (13.2)

DEFAULT_BUDGET = 200.0
MIN_BID = 1.0
SHADE = 0.95            # winner's-curse temper on the max bid (English auction ⇒ small)


# ------------------------------------------------------------------------------------------------
# pure kernels (unit-test targets)
# ------------------------------------------------------------------------------------------------
def auction_values(vor, positions=None, *, n_teams: int = 10, budget: float = DEFAULT_BUDGET,
                   roster_size: int = 15, min_bid: float = MIN_BID) -> np.ndarray:
    """Dollar auction value per player from value-over-replacement.

    The top ``n_teams·roster_size`` players by ``vor`` are **rosterable** (everyone gets drafted);
    each
    costs at least ``min_bid`` and the surplus budget ``n_teams·budget − n_slots·min_bid`` is
    distributed
    in proportion to (non-negative) VOR. Non-rosterable players are worth ``0`` (waiver fodder —
    don't
    bid). ``positions`` is accepted for symmetry with the board and unused here (VOR already prices
    scarcity). Pure; the shape every auction-value table has (studs ≫ replacement, last slots ≈
    $1)."""
    vor = np.asarray(vor, float)
    n = len(vor)
    n_slots = min(n, int(n_teams) * int(roster_size))
    rosterable = np.zeros(n, bool)
    rosterable[np.argsort(-vor)[:n_slots]] = True
    pos_vor = np.clip(vor, 0.0, None) * rosterable
    surplus = max(0.0, n_teams * budget - n_slots * min_bid)
    denom = pos_vor.sum()
    share = (pos_vor / denom * surplus) if denom > 0 else np.zeros(n)
    return np.where(rosterable, min_bid + share, 0.0)


def endgame_cap(budget_remaining: float, slots_remaining: int, min_bid: float = MIN_BID) -> float:
    """The most you may bid now and still fill every *other* remaining slot at ``min_bid`` (the $1
    endgame / exact budget-state continuation constraint). ``budget − min_bid·(slots−1)``, floored
    at
    ``min_bid``; ``0`` when there is no slot to fill."""
    if slots_remaining <= 0:
        return 0.0
    return max(min_bid, float(budget_remaining) - min_bid * max(0, int(slots_remaining) - 1))


def auction_bid(auction_value: float, budget_remaining: float, slots_remaining: int, *,
                shade: float = SHADE, min_bid: float = MIN_BID) -> float:
    """The max bid for one player: the (winner's-curse-shaded) auction value, capped by the $1
    endgame
    and the wallet. Returns ``0`` when the player isn't worth a roster slot or the budget is spent.

    ``auction_value`` should already be the player's value **to this roster** (marginal), in
    dollars —
    :func:`auction_values` gives the standalone version; the sim scales it by marginal lineup gain.
    """
    if slots_remaining <= 0 or budget_remaining < min_bid or auction_value < min_bid:
        return 0.0
    cap = endgame_cap(budget_remaining, slots_remaining, min_bid)
    return float(np.clip(shade * auction_value, min_bid, cap))


def _lineup_value(values, positions, slots: RosterSlots) -> float:
    """A roster's value = the sum of its optimal starting lineup only (reuses the 13.2 greedy fill;
    the
    diminishing-returns lesson made positional — a benched player contributes ~0)."""
    values = np.asarray(values, float)
    pos = np.asarray(list(positions))
    idx = [i for i in _fill(values, pos, slots).values() if i is not None]
    return float(values[idx].sum()) if idx else 0.0


def nominate(available_value: dict[str, float], my_needs: set[str],
             player_pos: dict[str, str]) -> str:
    """Which player to put up for auction (price enforcement / target hoarding).

    Nominate the highest-value player at a position you **don't** still need (make rivals spend on
    him);
    if every remaining player fills a need of yours, nominate the cheapest (preserve cash for your
    targets). ``my_needs`` is the set of positions you still have open. Pure."""
    if not available_value:
        raise ValueError("no players available to nominate")
    not_needed = {k: v for k, v in available_value.items() if player_pos.get(k) not in my_needs}
    if not_needed:
        return max(not_needed, key=not_needed.get)
    return min(available_value, key=available_value.get)


# ------------------------------------------------------------------------------------------------
# the done-bar: a smart bidder beats naive budget-splitting for realized lineup value
# ------------------------------------------------------------------------------------------------
def _open_needs(counts: dict[str, int], slots: RosterSlots) -> set[str]:
    """Positions the roster still wants a startable body at (starter demand not yet met,
    FLEX-aware)."""
    base = slots.base_demand()
    needs = {p for p, d in base.items() if counts.get(p, 0) < d}
    # 17.1: "flex-eligible" is the union over groups, and the budget is every flex slot — so a
    # superflex league correctly reports QB as a still-fillable need after the QB1 slot is met.
    eligible = slots.flex_eligible()
    flex_used = sum(max(0, counts.get(p, 0) - base.get(p, 0)) for p in eligible)
    if flex_used < slots.total_flex():
        needs |= set(eligible)
    return needs


def _run_auction(values, positions, keys, *, n_teams, budget, slots, vor_per_dollar, rng):
    """One English auction: seats nominate in rotation, everyone bids their marginal auction value,
    the
    high bid wins and pays the **second price + $1**. Seat 0 is the smart bidder, seat 1 the naive
    budget-splitter, the rest alternate (a mixed field). Returns each seat's realized
    starting-lineup
    value. Smart = bid marginal-lineup-gain-in-dollars, capped by the endgame; naive =
    ``budget/slots``,
    value-blind, same endgame cap so the *only* difference is where the money goes."""
    n = len(values)
    val = np.asarray(values, float)
    pos = np.asarray(list(positions))
    roster_size = slots.total
    strat = ["smart" if (s == 0 or s % 2 == 0) else "naive" for s in range(n_teams)]
    budgets = [float(budget)] * n_teams
    rosters: list[list[int]] = [[] for _ in range(n_teams)]
    taken = np.zeros(n, bool)
    order = 0

    for _ in range(n_teams * roster_size):
        avail = np.flatnonzero(~taken)
        if avail.size == 0:
            break
        # seats that still have room and budget
        live = [s for s in range(n_teams)
                if len(rosters[s]) < roster_size and budgets[s] >= MIN_BID]
        if not live:
            break
        # nominator = next live seat in rotation; nominate a player it doesn't need, else priciest.
        nominator = live[order % len(live)]
        order += 1
        counts = pd.Series(pos[rosters[nominator]]).value_counts().to_dict() if rosters[nominator] \
            else {}
        needs = _open_needs(counts, slots)
        not_needed = [i for i in avail if pos[i] not in needs]
        pool = not_needed if not_needed else list(avail)
        player = int(max(pool, key=lambda i: val[i]))

        bids = []
        for s in live:
            slots_left = roster_size - len(rosters[s])
            if strat[s] == "naive":
                bid = min(budgets[s] / slots_left, endgame_cap(budgets[s], slots_left))
                bid = float(bid) if val[player] > 0 else 0.0
            else:
                # marginal lineup gain of adding this player (true value to THIS roster) → dollars.
                cur = _lineup_value(val[rosters[s]], pos[rosters[s]], slots) if rosters[s] else 0.0
                cand = rosters[s] + [player]
                gain = _lineup_value(val[cand], pos[cand], slots) - cur
                av = MIN_BID + max(0.0, gain) / vor_per_dollar if vor_per_dollar > 0 else MIN_BID
                bid = auction_bid(av, budgets[s], slots_left)
            bids.append((s, float(bid)))

        bids = [b for b in bids if b[1] >= MIN_BID]
        if not bids:
            taken[player] = True                       # nobody bids ⇒ undrafted this pass
            continue
        bids.sort(key=lambda b: (b[1], rng.random()), reverse=True)
        winner, top = bids[0]
        second = bids[1][1] if len(bids) > 1 else 0.0
        price = float(np.clip(min(top, second + MIN_BID), MIN_BID,
                              endgame_cap(budgets[winner], roster_size - len(rosters[winner]))))
        budgets[winner] -= price
        rosters[winner].append(player)
        taken[player] = True

    return [_lineup_value(val[r], pos[r], slots) for r in rosters], budgets


def _auction_ci(diff: np.ndarray, n_boot: int, seed: int, alpha: float = 0.05):
    rng = np.random.default_rng(seed)
    means = diff[rng.integers(0, len(diff), (n_boot, len(diff)))].mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def auction_skill(con, season: int, *, n_auctions: int = 40, n_teams: int = 10,
                  budget: float = DEFAULT_BUDGET, pool_mult: int = 12, as_of=None,
                  ruleset: RuleSet | None = None, slots: RosterSlots | None = None,
                  n_boot: int = 2000, seed: int = 0) -> dict:
    """Walk-forward: does the auction bidder beat naive budget-splitting for realized lineup value?

    Builds the season's projection→VBD board (the underlying value = VOR), takes the top
    ``n_teams·pool_mult`` players, and plays ``n_auctions`` English auctions (:func:`_run_auction`),
    each with the smart seat (0) vs the naive seat (1) in a mixed field. Metric = the acquired
    roster's
    optimal-starting-lineup value; we compare seat 0 to seat 1 **paired within each auction** (same
    pool,
    same field). Done-when: the smart bidder's mean value gain > 0 with a CI excluding 0. PIT
    (board is
    as-of draft day); the value is projected VBD, so this measures **allocation skill under a
    budget**,
    not projection accuracy (the self-consistent 13.5/trades convention). Lockbox unread.
    """
    from fantasy_quant.backtest.walkforward import draft_date
    from fantasy_quant.valuation.value_board import value_board
    slots = slots or RosterSlots()
    if as_of is None:
        as_of = draft_date(con, season)
    board = value_board(con, season, as_of, ruleset=ruleset, slots=slots, n_teams=n_teams)
    board = board[board["vbd"] > 0].sort_values("vbd", ascending=False).head(n_teams * pool_mult)
    values = board["vbd"].to_numpy(float)
    positions = board["pos"].to_numpy()
    keys = board["player_key"].to_numpy()
    # global VOR-per-dollar scale (studs soak the surplus) — the smart bidder's points→$ map.
    av = auction_values(values, positions, n_teams=n_teams, budget=budget, roster_size=slots.total)
    surplus = max(1.0, n_teams * budget - min(len(values), n_teams * slots.total) * MIN_BID)
    vor_per_dollar = float(np.clip(values, 0, None).sum()) / surplus

    rng = np.random.default_rng(seed)
    smart_v, naive_v = [], []
    for _ in range(n_auctions):
        vals, _budgets = _run_auction(values, positions, keys, n_teams=n_teams, budget=budget,
                                      slots=slots, vor_per_dollar=vor_per_dollar, rng=rng)
        smart_v.append(vals[0])
        naive_v.append(vals[1])

    smart_v = np.asarray(smart_v)
    naive_v = np.asarray(naive_v)
    diff = smart_v - naive_v
    lo, hi = _auction_ci(diff, n_boot, seed)
    return {
        "season": int(season), "n_auctions": int(n_auctions), "n_pool": int(len(values)),
        "vor_per_dollar": vor_per_dollar,
        "top_value_dollars": float(np.max(av)) if len(av) else 0.0,
        "smart_value": float(smart_v.mean()), "naive_value": float(naive_v.mean()),
        "value_gain": float(diff.mean()), "value_gain_ci": (lo, hi),
        "frac_auctions_smart_wins": float((diff > 0).mean()),
        "beats_naive": bool(lo > 0.0),
    }
