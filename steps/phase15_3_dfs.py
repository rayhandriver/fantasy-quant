"""Phase 15.3 runner — DFS GPP: a leverage lineup beats the chalk lineup in a simulated field.

    uv run python steps/phase15_3_dfs.py

Done-bar (BUILD_PLAN 15.3): "leverage-aware lineup beats chalk in a simulated GPP field." Per DEV
season we
build synthetic salaries + modeled ownership over the top offense pool, a projection-max **chalk**
lineup
and a **leverage** lineup (fades the high-owned studs), and a field that folds to chalk (a 40%
duplicate
share). Over many correlated-weekly worlds each entry's payout is computed with **prize-splitting
among
duplicates** — the load-bearing GPP mechanic. Verdict = the leverage entry's mean payout beats the
chalk
entry's in a majority of seasons with an across-season CI > 0.

**Honest data caveat (per the free-data constraint):** there is no free DK/FD salary or ownership
feed
(the same gap that shelved props), so salaries are synthesised (monotone in projection) and
ownership is
modeled (projection-driven). This validates the **mechanics** — leverage beats chalk under a
duplicated
top-heavy field — **not** a Brier-fit to a real slate. Wire a real DFS feed and the same kernels
become
validatable. Lockbox untouched (DEV). Writes to analysis/.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from fantasy_quant.config import LOCKBOX_SEASONS
from fantasy_quant.data.db import connect
from fantasy_quant.formats.dfs import gpp_skill
from fantasy_quant.valuation.cost_validation import VALIDATION_SEASONS

OUT = Path("analysis/phase15_dfs.json")


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
    print(f"=== Phase 15.3 DFS GPP skill ({seasons}) ===  [modeled salaries/ownership — mechanics]")
    print(f"  {'season':>6}  {'chalk$':>6}  {'lev$':>6}  {'ch_own':>6}  {'lev_own':>7}  "
          f"{'chalk_pay':>9}  {'lev_pay':>8}  {'gain (CI)':>18}")
    for season in seasons:
        r = gpp_skill(con, season, n_contests=4000, field_size=200, seed=0)
        per_season.append(r)
        lo, hi = r["payout_gain_ci"]
        print(f"  {season:>6}  {r['chalk_salary']:>6.0f}  {r['leverage_salary']:>6.0f}  "
              f"{r['chalk_own']:>6.2f}  {r['leverage_own']:>7.2f}  {r['chalk_payout']:>9.3f}  "
              f"{r['leverage_payout']:>8.3f}  {r['payout_gain']:>+6.2f} [{lo:>+5.2f},{hi:>+5.2f}]")
    con.close()

    gains = [r["payout_gain"] for r in per_season]
    n_beat = sum(r["beats_chalk"] for r in per_season)
    g_lo, g_hi = _season_block_ci(gains)
    passed = g_lo > 0.0 and n_beat > len(per_season) / 2

    print("\n==== 15.3 DONE-BAR (leverage beats chalk in a simulated GPP field) ====")
    print(f"  seasons leverage beats chalk (CI>0): {n_beat}/{len(per_season)}")
    print(f"  payout gain season-block CI [{g_lo:+.2f}, {g_hi:+.2f}] "
          "(chalk duplicated → splits its prize; the contrarian keeps it)")
    print(f"  >>> {'PASS' if passed else 'FAIL'} <<< — leverage over chalk (MECHANICS; not "
          "Brier-validated — no free DFS salary/ownership feed)")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "seasons": seasons, "per_season": per_season,
        "n_seasons_beating_chalk": n_beat, "payout_gain_ci": [g_lo, g_hi], "PASS": bool(passed),
        "data_caveat": "modeled salaries + ownership (no free DFS feed); mechanics not Brier-fit",
    }, indent=2, default=float))
    print(f"\nWrote {OUT}")
    assert passed, "15.3 done-bar failed: leverage lineup did not beat chalk in the GPP field sim"


if __name__ == "__main__":
    main()
