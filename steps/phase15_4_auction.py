"""Phase 15.4 runner — auction draft: a budget-state bidder beats naive budget-splitting.

    uv run python steps/phase15_4_auction.py

Done-bar (BUILD_PLAN 15.4): "beats naive budget-splitting in auction sims." Per DEV season we play
many
English auctions in which the smart seat bids each player's **marginal** auction value (value to
its own
roster, in dollars) capped by the **$1 endgame** (the exact stochastic-knapsack continuation), vs a
naive
seat that bids ``budget/slots`` on whatever's up (value-blind). Verdict = the smart seat's realized
starting-lineup value beats the naive seat's in a majority of seasons, with an across-season CI > 0.

This also **discharges TECH-DEBT T9**: ``draft/auction.py`` now exists, and
``inseason/waivers.faab_bid``
consumes its ``endgame_cap`` continuation (``faab_skill(use_auction=True)``) — the FAAB sim passes
identically to the validated default (winner-selection is scale-invariant among symmetric bidders,
so the
continuation form changes prices, not the value done-bar). Value currency = projected VBD
(allocation skill,
not projection accuracy). Lockbox untouched (DEV window). Writes a scorecard to analysis/.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from fantasy_quant.config import LOCKBOX_SEASONS
from fantasy_quant.data.db import connect
from fantasy_quant.draft.auction import auction_skill
from fantasy_quant.valuation.cost_validation import VALIDATION_SEASONS

OUT = Path("analysis/phase15_auction.json")


def _season_block_ci(vals, n_boot: int = 10000, seed: int = 0, alpha: float = 0.05):
    v = np.asarray(vals, float)
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, len(v), (n_boot, len(v)))].mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def main() -> None:
    seasons = [s for s in VALIDATION_SEASONS if s not in set(LOCKBOX_SEASONS)]
    assert not (set(seasons) & set(LOCKBOX_SEASONS)), "lockbox must stay untouched"
    con = connect(read_only=True)

    per_season = []
    print(f"=== Phase 15.4 auction skill ({seasons}) ===")
    print(f"  {'season':>6}  {'pool':>4}  {'top$':>5}  {'smart':>7}  {'naive':>7}  "
          f"{'gain (CI)':>20}  {'win%':>5}")
    for season in seasons:
        r = auction_skill(con, season, n_auctions=40, seed=0)
        per_season.append(r)
        lo, hi = r["value_gain_ci"]
        print(f"  {season:>6}  {r['n_pool']:>4}  {r['top_value_dollars']:>5.0f}  "
              f"{r['smart_value']:>7.1f}  {r['naive_value']:>7.1f}  "
              f"{r['value_gain']:>+7.1f} [{lo:>+5.1f},{hi:>+5.1f}]  "
              f"{r['frac_auctions_smart_wins']:>5.2f}")
    con.close()

    gains = [r["value_gain"] for r in per_season]
    n_beat = sum(r["beats_naive"] for r in per_season)
    g_lo, g_hi = _season_block_ci(gains)
    passed = g_lo > 0.0 and n_beat > len(per_season) / 2

    print("\n==== 15.4 DONE-BAR (auction bidder beats naive budget-splitting) ====")
    print(f"  seasons beating naive (CI>0): {n_beat}/{len(per_season)}")
    print(f"  value gain season-block CI [{g_lo:+.1f}, {g_hi:+.1f}] lineup pts/roster")
    print(f"  >>> {'PASS' if passed else 'FAIL'} <<< — budget-state bidding (marginal value + $1 "
          "endgame) beats value-blind equal-splitting")
    print("  (T9 discharged: faab_bid now consumes auction.endgame_cap; value = projected VBD)")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "seasons": seasons, "per_season": per_season,
        "n_seasons_beating_naive": n_beat, "value_gain_ci": [g_lo, g_hi], "PASS": bool(passed),
    }, indent=2, default=float))
    print(f"\nWrote {OUT}")
    assert passed, "15.4 done-bar failed: auction bidder did not beat naive budget-splitting"


if __name__ == "__main__":
    main()
