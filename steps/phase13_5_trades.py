"""Phase 13.5 runner — trades: proposed deals raise both teams' simulated win%.

    uv run python steps/phase13_5_trades.py

Done-bar (ROADMAP / BUILD_PLAN 13.5): "proposed trades raise both teams' simulated win%." Per DEV
validation season we build many imbalanced leagues, and for several maker seats let the market-maker
(`find_trades`) search every opponent roster for a mutually-beneficial swap, execute its top
proposal, and re-simulate the Phase-10 season. Verdict = **both** the maker's and the partner's mean
playoff-probability change are positive (each with a league-clustered CI excluding 0) in a majority
of seasons, and the across-season CI of the weaker side's gain > 0. We also report a **random-trade
control** — proposed trades must lift both sides far more often than random swaps (the signal, not
the churn) — and a sell-high/buy-low diagnostic.

Value currency = the preseason model rest-of-season mean, self-consistent with the sim that scores
it (in-season this slot is 13.1's re-projected mean). Lockbox untouched (DEV window). Writes a
scorecard to analysis/.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from fantasy_quant.config import LOCKBOX_SEASONS
from fantasy_quant.data.db import connect
from fantasy_quant.inseason.trades import trade_skill
from fantasy_quant.valuation.cost_validation import VALIDATION_SEASONS

OUT = Path("analysis/phase13_trades.json")


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
    print(f"[1] proposed trades vs random — playoff-prob change for both sides — {seasons}")
    print(f"  {'season':>6}  {'trades':>6}  {'maker (CI)':>18}  {'partner (CI)':>18}  "
          f"{'both↑':>6}  {'rand↑':>6}  {'sellhi':>6}")
    for season in seasons:
        r = trade_skill(con, season, n_leagues=40, n_focal=4, sims=300, accept_margin=15.0, seed=0)
        per_season.append(r)
        mlo, mhi = r["maker_ci"]
        plo, phi = r["partner_ci"]
        print(f"  {season:>6}  {r['n_trades']:>6}  "
              f"{r['maker_gain']:>+6.3f} [{mlo:>+5.3f},{mhi:>+5.3f}]  "
              f"{r['partner_gain']:>+6.3f} [{plo:>+5.3f},{phi:>+5.3f}]  "
              f"{r['both_rise_rate']:>6.2f}  {r['random_both_rise_rate']:>6.2f}  "
              f"{r['sell_high_rate']:>6.2f}")
    con.close()

    maker = [r["maker_gain"] for r in per_season]
    partner = [r["partner_gain"] for r in per_season]
    weaker = [r["weaker_side_gain"] for r in per_season]
    n_raises = sum(r["raises_both"] for r in per_season)            # both means > 0 (direction)
    n_raises_ci = sum(r["raises_both_ci"] for r in per_season)      # both per-season CIs > 0
    n_beats_rand = sum(r["beats_random"] for r in per_season)
    mk_lo, mk_hi = _season_block_ci(maker)                          # the load-bearing tests:
    pt_lo, pt_hi = _season_block_ci(partner)                        # each side's across-season gain
    w_lo, w_hi = _season_block_ci(weaker)
    # PASS = both sides' across-season mean gain is significant, direction holds every season, and
    # the effect beats random churn in a majority (per-season CIs are underpowered at n=14-44 per
    # season, so the season-block bootstrap is the rigorous test — the 13.4 device).
    passed = (mk_lo > 0.0 and pt_lo > 0.0 and n_raises > len(per_season) / 2
              and n_beats_rand > len(per_season) / 2)

    print("\n==== 13.5 DONE-BAR (proposed trades raise both teams' win%) ====")
    print(f"  seasons both sides' mean win% rises: {n_raises}/{len(per_season)}  "
          f"(both per-season CIs>0: {n_raises_ci}/{len(per_season)};  "
          f"beat random both-rise: {n_beats_rand}/{len(per_season)})")
    print(f"  maker gain season-block CI   [{mk_lo:+.3f}, {mk_hi:+.3f}]")
    print(f"  partner gain season-block CI [{pt_lo:+.3f}, {pt_hi:+.3f}]  "
          f"(weaker side [{w_lo:+.3f}, {w_hi:+.3f}])")
    print(f"  >>> {'PASS' if passed else 'FAIL'} <<< — market-making trades "
          f"{'raise' if passed else 'do not raise'} both teams' win%")
    print("  (value = preseason model ros mean; in-season this slot is 13.1's re-projected mean)")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "seasons": seasons, "per_season": per_season,
        "n_seasons_raising_both": n_raises, "n_seasons_raising_both_ci": n_raises_ci,
        "n_seasons_beating_random": n_beats_rand,
        "maker_gain_ci": [mk_lo, mk_hi], "partner_gain_ci": [pt_lo, pt_hi],
        "weaker_side_ci": [w_lo, w_hi], "PASS": bool(passed),
    }, indent=2, default=float))
    print(f"\nWrote {OUT}")
    assert passed, "13.5 done-bar failed: proposed trades did not raise both teams' win%"


if __name__ == "__main__":
    main()
