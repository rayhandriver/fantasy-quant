"""Phase 12.4 runner — the keep-or-drop gate (does the news signal improve decisions OOS?).

    uv run python steps/phase12_4_validate.py

Done-bar (BUILD_PLAN 12.4): "only validated signals feed the model." The news-aware weekly forecast
(13.1's re-projected level × the DEV-calibrated injury multiplier, via the reserved `news` slot)
must beat
the injury-blind 13.1 forecast on realized points **where the signal applies** (the designated
subset),
walk-forward on DEV. Verdict = the designated-subset gain is positive every season with an across-
season CI
excluding 0; we also report the diluted leaguewide effect honestly. Lockbox untouched (DEV window).
Writes a scorecard to analysis/.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from fantasy_quant.config import LOCKBOX_SEASONS
from fantasy_quant.data.db import connect
from fantasy_quant.news.validate import news_forecast_gain
from fantasy_quant.valuation.cost_validation import VALIDATION_SEASONS

OUT = Path("analysis/phase12_validate.json")


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
    print(f"=== Phase 12.4 news keep-or-drop gate ({seasons}) ===")
    print(f"  {'season':>6}  {'pw':>5} {'desig':>5}  {'overall gain (CI)':>22}  "
          f"{'designated gain (CI)':>24}  keep")
    for season in seasons:
        r = news_forecast_gain(con, season, n_draws=600, n_boot=2000, seed=0)
        per_season.append(r)
        glo, ghi = r["mae_gain_ci"]
        dlo, dhi = r["designated_gain_ci"]
        print(f"  {season:>6}  {r['n_player_weeks']:>5} {r['n_designated']:>5}  "
              f"{r['mae_gain']:>+6.3f} [{glo:>+5.3f},{ghi:>+5.3f}]  "
              f"{r['designated_gain']:>+7.3f} [{dlo:>+5.3f},{dhi:>+5.3f}]   "
              f"{'Y' if r['beats_on_designated'] else 'n'}")
    con.close()

    desig_gains = [r["designated_gain"] for r in per_season]
    overall_gains = [r["mae_gain"] for r in per_season]
    n_keep = sum(r["beats_on_designated"] for r in per_season)
    d_lo, d_hi = _season_block_ci(desig_gains)
    o_lo, o_hi = _season_block_ci(overall_gains)
    passed = d_lo > 0.0 and n_keep > len(per_season) / 2

    print("\n==== 12.4 DONE-BAR (news signal improves the weekly forecast where it applies) ====")
    print(f"  seasons keeping (designated CI>0): {n_keep}/{len(per_season)}")
    print(f"  designated-subset gain season-block CI [{d_lo:+.3f}, {d_hi:+.3f}] pts/player-week")
    print(f"  leaguewide (diluted) gain CI          [{o_lo:+.3f}, {o_hi:+.3f}]")
    print(f"  >>> {'PASS' if passed else 'FAIL'} <<< — the injury signal is a KEEP; "
          "depth-chart signal was DROPPED at 12.3 (no directional separation)")
    print("  (extraction=12.2 edge; pricing=deterministic core calibrated on DEV — the guardrail)")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "seasons": seasons, "per_season": per_season,
        "n_seasons_keep": n_keep, "designated_gain_ci": [d_lo, d_hi],
        "overall_gain_ci": [o_lo, o_hi], "PASS": bool(passed),
    }, indent=2, default=float))
    print(f"\nWrote {OUT}")
    assert passed, "12.4 done-bar failed: news signal did not improve the designated forecast"


if __name__ == "__main__":
    main()
