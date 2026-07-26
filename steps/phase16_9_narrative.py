"""Phase 16.9 done-bar — the correlated per-draft narrative shock.

Two questions, in order:

1. **Does the simulator reproduce realized cross-draft draft-slot dispersion?** Not just the
   pooled level (which can match by cancellation) but its **slope in board depth**, which is where
   real rooms and an independent-noise simulator actually differ.
2. **Does the availability Brier regress?** The 11.2 forecast is the thing a drafter consumes, so
   nothing here is allowed to make it worse.

Run:  uv run python steps/phase16_9_narrative.py [--drafts-per-season N] [--quick]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from fantasy_quant.adp.drift_panel import (
    aggregate_player_season,
    build_drift_panel,
    eligible_drafts,
)
from fantasy_quant.adp.narrative import (
    NarrativeShock,
    calibrate_intercept,
    compare_profiles,
    dispersion_profile,
    fit_shape,
    shock_features,
    simulate_drift_panel,
)
from fantasy_quant.draft.availability import availability_brier
from fantasy_quant.draft.opponent_model import ALL_FEATURES, CHOICE_TOP_K, OpponentModel

DB = Path("data/fantasy_quant.duckdb")
OUT = Path("analysis/phase16_9_narrative.json")
COEF_JSON = Path("analysis/phase11_opponent_model.json")


def _model() -> OpponentModel:
    coef = json.loads(COEF_JSON.read_text())["coefficients"]
    return OpponentModel(feature_cols=list(ALL_FEATURES),
                         beta=np.array([coef[c] for c in ALL_FEATURES]))


def _sample(drafts: pd.DataFrame, per_season: int, seed: int = 0) -> pd.DataFrame:
    return pd.concat([g.sample(min(len(g), per_season), random_state=seed)
                      for _s, g in drafts.groupby("season")], ignore_index=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drafts-per-season", type=int, default=30)
    ap.add_argument("--quick", action="store_true", help="smaller sim + Brier budget")
    args = ap.parse_args()
    # A per-player cross-draft sd needs several drafts per player, and a player appears in roughly
    # every draft of its season — so drafts/season is directly the per-player sample size and must
    # stay above `dispersion_profile`'s `min_drafts`. `--quick` shrinks the grid, not below that.
    per_season = 12 if args.quick else args.drafts_per_season

    con = duckdb.connect(str(DB), read_only=True)
    model = _model()
    out: dict = {"config": {"drafts_per_season": per_season, "choice_top_k": CHOICE_TOP_K}}

    # ---- realized target ------------------------------------------------------------------
    print("building the realized 16.7 panel ...", flush=True)
    panel = build_drift_panel(con, None, allow_ecr=False)
    agg = aggregate_player_season(panel)
    real = dispersion_profile(panel)
    out["realized"] = real
    print(f"  realized  pooled_sd={real['pooled_sd']:.4f}  "
          f"depth_spearman={real['depth_spearman']:+.4f}  n={real['n_player_seasons']}")

    drafts = eligible_drafts(con, None)
    drafts = drafts[drafts["season"] < 2025]        # FFC-boarded seasons only
    sample = _sample(drafts, per_season)

    # ---- (a) the choice-set contract: the defect Session G found ---------------------------
    def report(label: str, sim: pd.DataFrame) -> dict:
        prof = dispersion_profile(sim)
        prof["matched"] = compare_profiles(panel, sim)
        mt = prof["matched"]
        out[label] = prof
        print(f"  pooled_sd={prof['pooled_sd']:.4f}   matched slope "
              f"real {mt.get('depth_slope_real', float('nan')):+.3f} vs sim "
              f"{mt.get('depth_slope_sim', float('nan')):+.3f}   "
              f"sd-agreement {mt.get('sd_agreement', float('nan')):+.3f}   "
              f"(n={mt.get('n_matched', 0)})", flush=True)
        return prof

    print(f"\nsimulating {len(sample)} drafts, band OFF (pre-Session-G) ...", flush=True)
    report("band_off", simulate_drift_panel(con, sample, model, top_k=None, seed=1))

    print(f"simulating {len(sample)} drafts, band ON (top_k={CHOICE_TOP_K}) ...", flush=True)
    banded = simulate_drift_panel(con, sample, model, top_k=CHOICE_TOP_K, seed=1)
    report("band_on", banded)

    # ---- (b) the narrative shock: fit the shape, calibrate the size ------------------------
    print("\nfitting the dispersion shape on the realized panel ...", flush=True)
    afeat = shock_features(
        agg.assign(adp=agg["mean_adp_rounds"] * 12, pos=agg["pos"]), board_teams=12)
    coef = fit_shape(agg, afeat)
    out["shape_coefficients"] = coef
    for k, v in coef.items():
        print(f"  {k:>14} {v:+.4f}")

    print("\ncalibrating the shock size against the realized depth slope ...", flush=True)
    cal_sample = _sample(drafts, max(12, per_season // 2), seed=7)

    def sim_at(intercept: float) -> dict:
        sh = NarrativeShock(coef=coef, intercept=intercept)
        p = simulate_drift_panel(con, cal_sample, model, shock=sh,
                                 top_k=CHOICE_TOP_K, seed=2)
        prof = dispersion_profile(p)
        mt = compare_profiles(panel, p)
        # calibrate against the MATCHED slope, not the sim's own — see compare_profiles
        prof["depth_spearman"] = mt.get("depth_slope_sim", float("nan"))
        prof["sd_agreement"] = mt.get("sd_agreement", float("nan"))
        print(f"    intercept={intercept:+.2f}  pooled_sd={prof['pooled_sd']:.4f}  "
              f"matched slope={prof['depth_spearman']:+.4f}  "
              f"sd-agreement={prof['sd_agreement']:+.4f}", flush=True)
        return prof

    grid = (-4.0, -3.0, -2.0, -1.0) if args.quick else (-5.0, -4.0, -3.0, -2.5, -2.0, -1.5, -1.0)
    best, trace = calibrate_intercept(sim_at, real["depth_spearman"], grid=grid)
    out["calibration"] = {"grid": trace.to_dict("records"), "best_intercept": best}
    print(f"  best intercept = {best:+.2f}")

    shock = NarrativeShock(coef=coef, intercept=best)
    print(f"\nsimulating {len(sample)} drafts, band ON + shock ...", flush=True)
    shocked = simulate_drift_panel(con, sample, model, shock=shock,
                                   top_k=CHOICE_TOP_K, seed=1)
    report("band_on_shock", shocked)

    # ---- (c) availability Brier: nothing here may make the drafter's forecast worse --------
    print("\navailability Brier (paired, same budget/seed) ...", flush=True)
    brier_budget = 3 if args.quick else 6
    ab = {}
    for label, tk in (("band_off", None), ("band_on", CHOICE_TOP_K)):
        r = availability_brier(con, model, n_sims=40, contested_k=30,
                               max_drafts_per_season=brier_budget, n_boot=400, seed=1, top_k=tk)
        ab[label] = r
        print(f"  {label:>9}: beh={r['beh_brier']:.4f}  gain={r['brier_gain_vs_best']:+.4f} "
              f"CI[{r['brier_gain_ci'][0]:+.4f}, {r['brier_gain_ci'][1]:+.4f}]  "
              f"n_windows={r['n_windows']}")
    out["availability_brier"] = ab

    # ---- verdict ---------------------------------------------------------------------------
    lvl_off = abs(out["band_off"]["pooled_sd"] - real["pooled_sd"]) / real["pooled_sd"]
    lvl_on = abs(out["band_on"]["pooled_sd"] - real["pooled_sd"]) / real["pooled_sd"]
    m_on, m_shock = out["band_on"]["matched"], out["band_on_shock"]["matched"]
    out["verdict"] = {
        "level_error_band_off": lvl_off,
        "level_error_band_on": lvl_on,
        "level_gate_pass": bool(lvl_on <= 0.15),
        "depth_slope_realized": m_on.get("depth_slope_real"),
        "depth_slope_band_off": out["band_off"]["matched"].get("depth_slope_sim"),
        "depth_slope_band_on": m_on.get("depth_slope_sim"),
        "depth_slope_band_on_shock": m_shock.get("depth_slope_sim"),
        "sd_agreement_band_on": m_on.get("sd_agreement"),
        "sd_agreement_band_on_shock": m_shock.get("sd_agreement"),
        # the shock earns its keep only if it moves the matched slope toward realized
        "shock_helps_slope": bool(
            abs(m_shock.get("depth_slope_sim", 0) - m_on.get("depth_slope_real", 0))
            < abs(m_on.get("depth_slope_sim", 0) - m_on.get("depth_slope_real", 0))),
        "brier_no_regression": bool(
            ab["band_on"]["brier_gain_vs_best"] >= ab["band_off"]["brier_gain_vs_best"]),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=float))
    print(f"\nwrote {OUT}")
    v = out["verdict"]
    print(f"\n  level  : band OFF {lvl_off:.1%} error -> band ON {lvl_on:.1%}  "
          f"{'PASS' if v['level_gate_pass'] else 'FAIL'}")
    print(f"  slope  : realized {v['depth_slope_realized']:+.3f} | band OFF "
          f"{v['depth_slope_band_off']:+.3f} | band ON {v['depth_slope_band_on']:+.3f} | "
          f"+shock {v['depth_slope_band_on_shock']:+.3f}")
    print(f"  shock moves the slope toward realized = {v['shock_helps_slope']}")
    print(f"  brier  : no regression = {v['brier_no_regression']}")


if __name__ == "__main__":
    main()
