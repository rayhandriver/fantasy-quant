"""Phase 13.4 runner — streaming: a matchup-streamer beats static-hold on DST.

    uv run python steps/phase13_4_streaming.py

Done-bar (ROADMAP / BUILD_PLAN 13.4): "beats static-hold in sims." Per DEV validation season we play
many managers, each with a random subset of the waiver-tier defenses, over the fantasy regular
season. Three strategies score realized DST points on the same subset: **matchup-streaming** (start
each week's projected-best available unit, PIT), **static-hold** (roster the preseason-best unit and
start it every week), and **random-streaming** (a random available unit each week — the signal
control). Verdict = matchup-streaming beats static-hold in a majority of seasons and the
across-season gain CI > 0. We also report the matchup-vs-random gain (does the *signal*, not just
the churn, add value?).

Scope: streaming demonstrated on DST (the strongest matchup signal + real weekly scores); the
`stream_pick` kernel is position-agnostic (QB/TE would feed 13.1 re-projected means as `proj`).

Lockbox untouched (DEV window only). Writes a scorecard to analysis/.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from fantasy_quant.config import LOCKBOX_SEASONS
from fantasy_quant.data.db import connect
from fantasy_quant.inseason.streaming import streaming_skill
from fantasy_quant.valuation.cost_validation import VALIDATION_SEASONS

OUT = Path("analysis/phase13_streaming.json")


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
    print(f"[1] matchup-streaming vs static-hold — realized DST points/week — {seasons}")
    print(f"  {'season':>6}  {'pool':>4}  {'stream':>6}  {'static':>6}  {'random':>6}  "
          f"{'vs_hold':>7}  {'CI':>16}  {'vs_rand':>7}  {'switch':>6}")
    for season in seasons:
        r = streaming_skill(con, season, n_managers=300, n_boot=2000, seed=0)
        per_season.append(r)
        lo, hi = r["static_gain_ci"]
        print(f"  {season:>6}  {r['n_pool']:>4}  {r['stream_ppw']:>6.2f}  {r['static_ppw']:>6.2f}  "
              f"{r['random_ppw']:>6.2f}  {r['stream_minus_static_ppw']:>+7.2f}  "
              f"[{lo:>+5.2f},{hi:>+5.2f}]  {r['stream_minus_random_ppw']:>+7.2f}  "
              f"{r['avg_switches']:>6.1f}")
    con.close()

    gains = [r["stream_minus_static_ppw"] for r in per_season]
    n_beat = sum(r["beats_static"] for r in per_season)
    n_beat_rand = sum(r["beats_random"] for r in per_season)
    mean_gain = float(np.mean(gains))
    lo, hi = _season_block_ci(gains)
    passed = (n_beat > len(per_season) / 2) and lo > 0.0

    print("\n==== 13.4 DONE-BAR (matchup-streaming vs static-hold) ====")
    print(f"  seasons streaming beats static-hold: {n_beat}/{len(per_season)}  "
          f"(beats random-streaming: {n_beat_rand}/{len(per_season)})")
    print(f"  mean gain {mean_gain:+.2f} DST pts/week  season-block CI [{lo:+.2f}, {hi:+.2f}]")
    print(f"  >>> {'PASS' if passed else 'FAIL'} <<< — matchup-aware streaming "
          f"{'beats' if passed else 'does not beat'} static-hold")
    print("  (DST demonstration; stream_pick is position-agnostic — QB/TE feed 13.1 means as proj)")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "seasons": seasons, "per_season": per_season,
        "n_seasons_beating_static": n_beat, "n_seasons_beating_random": n_beat_rand,
        "mean_gain_ppw": mean_gain, "mean_gain_ci": [lo, hi], "PASS": bool(passed),
    }, indent=2, default=float))
    print(f"\nWrote {OUT}")
    assert passed, "13.4 done-bar failed: matchup-streaming did not beat static-hold"


if __name__ == "__main__":
    main()
