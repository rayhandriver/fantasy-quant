"""Phase 13.3 runner — waivers/FAAB: the faab_bid agent beats naive %-of-budget bidding.

    uv run python steps/phase13_3_waivers.py

Done-bar (ROADMAP / BUILD_PLAN 13.3): "beats naive %-of-budget bidding in sims." Per DEV validation
season we play many independent **mixed-field** waiver seasons (a sharp faab_bid agent in seat 0, a
naive %-of-budget bidder in seat 1, the rest alternating) into one shared, depleting free-agent
pool, and compare **realized** value acquired (top-few pickups) — sharp minus naive, within each
league. Verdict = the sharp agent wins in a majority of seasons and the across-season gain CI > 0.

Scope: pragmatic FAAB (marginal value + budget option value + fixed-belief first-price shading). The
rigorous equilibrium/auction-theory version is owed to Phase 15.4 (docs/TECH-DEBT.md T9).

Lockbox untouched (DEV window only). Writes a scorecard to analysis/.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from fantasy_quant.config import LOCKBOX_SEASONS
from fantasy_quant.data.db import connect
from fantasy_quant.inseason.waivers import faab_skill
from fantasy_quant.valuation.cost_validation import VALIDATION_SEASONS

OUT = Path("analysis/phase13_waivers.json")


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
    print(f"[1] faab_bid vs naive %-of-budget — realized value acquired, mixed field — {seasons}")
    print(f"  {'season':>6}  {'pool':>4}  {'smart_v':>8}  {'naive_v':>8}  {'gain':>7}  "
          f"{'CI':>18}  {'win%':>5}  {'smart$eff':>9}  {'naive$eff':>9}")
    for season in seasons:
        r = faab_skill(con, season, n_leagues=200, n_draws=600, n_boot=2000, seed=0)
        per_season.append(r)
        lo, hi = r["value_gain_ci"]
        print(f"  {season:>6}  {r['n_pool']:>4}  {r['smart_value']:>8.1f}  "
              f"{r['naive_value']:>8.1f}  {r['value_gain']:>+7.1f}  [{lo:>+6.1f},{hi:>+6.1f}]  "
              f"{r['frac_leagues_smart_wins']:>5.2f}  {r['smart_value_per_dollar']:>9.3f}  "
              f"{r['naive_value_per_dollar']:>9.3f}")
    con.close()

    gains = [r["value_gain"] for r in per_season]
    n_beat = sum(r["beats_naive"] for r in per_season)
    mean_gain = float(np.mean(gains))
    lo, hi = _season_block_ci(gains)
    passed = (n_beat > len(per_season) / 2) and lo > 0.0

    print("\n==== 13.3 DONE-BAR (faab_bid vs naive %-of-budget) ====")
    print(f"  seasons the sharp agent beats naive: {n_beat}/{len(per_season)}")
    print(f"  mean value gain {mean_gain:+.1f} pts-over-replacement/season  "
          f"season-block CI [{lo:+.1f}, {hi:+.1f}]")
    print(f"  >>> {'PASS' if passed else 'FAIL'} <<< — marginal-value + option-value + shaded "
          f"bidding {'beats' if passed else 'does not beat'} naive %-of-budget")
    print("  (pragmatic FAAB; rigorous auction theory owed to Phase 15.4 — docs/TECH-DEBT.md T9)")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "seasons": seasons, "per_season": per_season,
        "n_seasons_beating_naive": n_beat, "mean_value_gain": mean_gain,
        "mean_value_gain_ci": [lo, hi], "PASS": bool(passed),
    }, indent=2, default=float))
    print(f"\nWrote {OUT}")
    assert passed, "13.3 done-bar failed: faab_bid did not beat naive %-of-budget"


if __name__ == "__main__":
    main()
