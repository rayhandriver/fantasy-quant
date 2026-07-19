"""Phase 15.2 runner — best-ball: ceiling-aware drafting beats mean-only.

    uv run python steps/phase15_2_bestball.py

Done-bar (BUILD_PLAN 15.2): "variance-aware best-ball drafting beats a mean-only draft in best-ball
scoring sims." Per DEV season a focal seat drafts twice against identical opponents — once ranking
on
``mean·(1 + κ·wk_cov)`` (weekly-volatility-seeking), once on ``mean`` — and both rosters are scored
on the
same Σ-correlated weekly cloud, summing each week's optimal lineup (best-ball). Verdict = the
ceiling
roster wins in a majority of seasons with an across-season CI > 0.

The thematic result: **variance is good in best-ball** — the exact mirror of the 13.2 managed-lineup
finding (the variance tilt lost there because you're forced to start your pick; here best-ball
auto-keeps
the boom weeks). Uses **weekly** CoV, never season-total sd. Lockbox untouched (DEV). Writes to
analysis/.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from fantasy_quant.config import LOCKBOX_SEASONS
from fantasy_quant.data.db import connect
from fantasy_quant.formats.bestball import bestball_skill
from fantasy_quant.valuation.cost_validation import VALIDATION_SEASONS

OUT = Path("analysis/phase15_bestball.json")


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
    print(f"=== Phase 15.2 best-ball skill ({seasons}) ===")
    print(f"  {'season':>6}  {'ceiling':>8}  {'mean':>8}  {'gain (CI)':>20}  {'win%':>5}")
    for season in seasons:
        r = bestball_skill(con, season, n_drafts=40, n_sims=400, seed=0)
        per_season.append(r)
        lo, hi = r["gain_ci"]
        print(f"  {season:>6}  {r['ceiling_total']:>8.0f}  {r['mean_total']:>8.0f}  "
              f"{r['bestball_gain']:>+7.1f} [{lo:>+5.1f},{hi:>+5.1f}]  "
              f"{r['frac_drafts_ceiling_wins']:>5.2f}")
    con.close()

    gains = [r["bestball_gain"] for r in per_season]
    n_beat = sum(r["beats_mean_only"] for r in per_season)
    g_lo, g_hi = _season_block_ci(gains)
    passed = g_lo > 0.0 and n_beat > len(per_season) / 2

    print("\n==== 15.2 DONE-BAR (ceiling-aware drafting beats mean-only at best-ball) ====")
    print(f"  seasons ceiling beats mean (CI>0): {n_beat}/{len(per_season)}")
    print(f"  best-ball gain season-block CI [{g_lo:+.1f}, {g_hi:+.1f}] pts/season")
    print(f"  >>> {'PASS' if passed else 'FAIL'} <<< — variance is GOOD in best-ball "
          "(mirror of the 13.2 managed-lineup finding)")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "seasons": seasons, "per_season": per_season,
        "n_seasons_beating_mean": n_beat, "gain_ci": [g_lo, g_hi], "PASS": bool(passed),
    }, indent=2, default=float))
    print(f"\nWrote {OUT}")
    assert passed, "15.2 done-bar failed: ceiling drafting did not beat mean-only at best-ball"


if __name__ == "__main__":
    main()
