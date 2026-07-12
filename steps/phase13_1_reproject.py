"""Phase 13.1 runner — weekly re-projection beats the static preseason forecast (walk-forward).

    uv run python steps/phase13_1_reproject.py

Done-bar (ROADMAP / BUILD_PLAN 13.1): "weekly forecasts beat preseason-static OOS." For each DEV
validation season we re-project every offense player's per-week level from the weeks played so far
(a scalar Kalman fold of results into the PIT preseason prior) at several split weeks, and score the
forecast on the *future* played weeks by MAE. The static baseline is the frozen preseason level.
Verdict = re-projection's MAE is lower in a majority of seasons and the across-season gain CI (a
season-block bootstrap) excludes 0. Lockbox untouched (DEV window only). Writes a scorecard to
analysis/.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from fantasy_quant.config import LOCKBOX_SEASONS
from fantasy_quant.data.db import connect
from fantasy_quant.inseason.reproject import reprojection_skill
from fantasy_quant.valuation.cost_validation import VALIDATION_SEASONS

OUT = Path("analysis/phase13_reproject.json")


def _season_block_ci(vals, n_boot: int = 10000, seed: int = 0, alpha: float = 0.05):
    """Percentile CI of the mean by resampling whole seasons (the spine convention)."""
    v = np.asarray(vals, float)
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, len(v), (n_boot, len(v)))].mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def main() -> None:
    seasons = [s for s in VALIDATION_SEASONS if s not in set(LOCKBOX_SEASONS)]
    assert not (set(seasons) & set(LOCKBOX_SEASONS)), "lockbox must stay untouched"
    con = connect(read_only=True)

    per_season = []
    print(f"Walk-forward re-projection skill on {seasons} (re-project<=t, score future weeks) ...")
    print(f"  {'season':>6}  {'n_pw':>6}  {'static_mae':>10}  {'reproj_mae':>10}  "
          f"{'gain':>7}  {'CI':>18}  beats")
    for season in seasons:
        r = reprojection_skill(con, season, n_draws=600, n_boot=2000, seed=0)
        per_season.append(r)
        lo, hi = r["mae_gain_ci"]
        print(f"  {season:>6}  {r['n_player_weeks']:>6}  {r['static_mae']:>10.3f}  "
              f"{r['reproj_mae']:>10.3f}  {r['mae_gain']:>+7.3f}  "
              f"[{lo:>+6.3f},{hi:>+6.3f}]  {'YES' if r['beats_static'] else 'no'}")
    con.close()

    gains = [r["mae_gain"] for r in per_season]
    n_beat = sum(r["beats_static"] for r in per_season)
    mean_gain = float(np.mean(gains))
    lo, hi = _season_block_ci(gains)
    majority = n_beat > len(per_season) / 2
    passed = majority and lo > 0.0

    print("\n==== 13.1 DONE-BAR ====")
    print(f"  seasons beating static preseason: {n_beat}/{len(per_season)}")
    print(f"  mean MAE gain {mean_gain:+.3f} ppg/week  season-block CI [{lo:+.3f}, {hi:+.3f}]")
    print(f"  >>> {'PASS' if passed else 'FAIL'} <<< — re-projection "
          f"{'beats' if passed else 'does not beat'} the static preseason forecast OOS")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "seasons": seasons, "per_season": per_season,
        "n_seasons_beating_static": n_beat, "mean_mae_gain": mean_gain,
        "mean_mae_gain_ci": [lo, hi], "PASS": bool(passed),
    }, indent=2, default=float))
    print(f"\nWrote {OUT}")
    assert passed, "13.1 done-bar failed: re-projection did not beat the static preseason forecast"


if __name__ == "__main__":
    main()
