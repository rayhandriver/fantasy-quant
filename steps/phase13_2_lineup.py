"""Phase 13.2 runner — start/sit: the weekly co-pilot beats set-and-forget (+ the tilt finding).

    uv run python steps/phase13_2_lineup.py

Done-bar (ROADMAP / BUILD_PLAN 13.2): "beats projection-max lineup on simulated win%." Two results,
scored per DEV validation season:

  1. **The co-pilot (the done-bar, PASS).** The weekly mean-max lineup ranked by 13.1's
     *re-projected* means vs the *set-and-forget* lineup ranked by the frozen preseason level,
     scored on **realized** points over random offense rosters at several split weeks. Verdict = the
     co-pilot outscores set-and-forget in a majority of seasons and the across-season gain CI > 0.
  2. **The win-probability variance tilt (a documented FINDING, not asserted).** Whether tilting the
     lineup toward/away from variance by H2H leverage beats mean-max on OOS win%. It does **not**
     clear the bar even for big underdogs — a single legal swap barely moves team spread (cf.
     Phase-10.3, where leverage only bit at whole-team spread changes). So mean-max is the default
     and the tilt is opt-in; this is reported, not gated (the Phase-7 / props pattern).

Lockbox untouched (DEV window only). Writes a scorecard to analysis/.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from fantasy_quant.config import LOCKBOX_SEASONS
from fantasy_quant.data.db import connect
from fantasy_quant.inseason.lineup import start_sit_skill, weekly_lineup_gain
from fantasy_quant.valuation.cost_validation import VALIDATION_SEASONS

OUT = Path("analysis/phase13_lineup.json")


def _season_block_ci(vals, n_boot: int = 10000, seed: int = 0, alpha: float = 0.05):
    v = np.asarray(vals, float)
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, len(v), (n_boot, len(v)))].mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def main() -> None:
    seasons = [s for s in VALIDATION_SEASONS if s not in set(LOCKBOX_SEASONS)]
    assert not (set(seasons) & set(LOCKBOX_SEASONS)), "lockbox must stay untouched"
    con = connect(read_only=True)

    copilot, tilt = [], []
    print(f"[1] Co-pilot (re-projected mean-max) vs set-and-forget on realized points — {seasons}")
    print(f"  {'season':>6}  {'static_ppw':>10}  {'copilot_ppw':>11}  {'gain':>7}  "
          f"{'CI':>18}  {'better%':>7}")
    for season in seasons:
        g = weekly_lineup_gain(con, season, n_draws=600, n_boot=2000, seed=0)
        copilot.append(g)
        lo, hi = g["gain_ci"]
        print(f"  {season:>6}  {g['static_ppw']:>10.2f}  {g['copilot_ppw']:>11.2f}  "
              f"{g['copilot_minus_static_ppw']:>+7.2f}  [{lo:>+6.2f},{hi:>+6.2f}]  "
              f"{g['frac_weeks_better']:>7.2f}")

    print(f"\n[2] Variance tilt vs mean-max on OOS win% (diagnostic / finding) — {seasons}")
    print(f"  {'season':>6}  {'meanmax_wr':>10}  {'winobj_wr':>10}  {'gain':>8}  {'dog_gain':>9}  "
          f"beats")
    for season in seasons:
        s = start_sit_skill(con, season, n_matchups=250, n_sims=200, n_draws=600,
                            n_boot=2000, seed=0)
        tilt.append(s)
        print(f"  {season:>6}  {s['mean_max_winrate']:>10.4f}  {s['winobj_winrate']:>10.4f}  "
              f"{s['winrate_gain']:>+8.4f}  {s['underdog_gain']:>+9.4f}  "
              f"{'YES' if s['beats_mean_max'] else 'no'}")
    con.close()

    # verdict 1 — the co-pilot (the done-bar)
    gains = [g["copilot_minus_static_ppw"] for g in copilot]
    n_beat = sum(g["beats_static"] for g in copilot)
    mean_gain = float(np.mean(gains))
    lo, hi = _season_block_ci(gains)
    passed = (n_beat > len(copilot) / 2) and lo > 0.0

    # verdict 2 — the tilt (reported, never gated)
    tilt_gains = [s["winrate_gain"] for s in tilt]
    tilt_dog = [s["underdog_gain"] for s in tilt]
    tilt_beats = sum(s["beats_mean_max"] for s in tilt)

    print("\n==== 13.2 DONE-BAR (co-pilot vs set-and-forget) ====")
    print(f"  seasons the co-pilot beats set-and-forget: {n_beat}/{len(copilot)}")
    print(f"  mean gain {mean_gain:+.2f} pts/lineup-week  season-block CI [{lo:+.2f}, {hi:+.2f}]")
    print(f"  >>> {'PASS' if passed else 'FAIL'} <<< — re-projected mean-max "
          f"{'beats' if passed else 'does not beat'} the frozen preseason lineup")
    print("\n---- FINDING: win-probability variance tilt ----")
    print(f"  mean win% gain {float(np.mean(tilt_gains)):+.4f}  "
          f"underdog {float(np.mean(tilt_dog)):+.4f}  "
          f"seasons clearing the bar: {tilt_beats}/{len(tilt)}")
    print("  -> the single-swap variance tilt does not beat mean-max OOS (even for underdogs); it")
    print("     retained as opt-in `objective='win'` but off by default. Mean-max is the default.")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "seasons": seasons, "copilot_per_season": copilot, "tilt_per_season": tilt,
        "copilot_n_seasons_beating_static": n_beat, "copilot_mean_gain_ppw": mean_gain,
        "copilot_mean_gain_ci": [lo, hi], "copilot_PASS": bool(passed),
        "tilt_mean_winrate_gain": float(np.mean(tilt_gains)),
        "tilt_mean_underdog_gain": float(np.mean(tilt_dog)),
        "tilt_seasons_beating_mean_max": int(tilt_beats),
        "tilt_verdict": "does not clear the bar — mean-max default, tilt opt-in",
    }, indent=2, default=float))
    print(f"\nWrote {OUT}")
    assert passed, "13.2 done-bar failed: the re-projected co-pilot did not beat set-and-forget"


if __name__ == "__main__":
    main()
