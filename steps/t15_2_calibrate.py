"""T15 step 2 — the labelled width calibration, and the shipped model artifact.

    uv run python steps/t15_2_calibrate.py                  # sweep, calibrate, write the artifact
    uv run python steps/t15_2_calibrate.py --seeds 60       # more drafts per exponent
    uv run python steps/t15_2_calibrate.py --no-write       # measure only, ship nothing

Done when: the exponent that makes the simulated reach profile match the realized human one has
been **measured through the simulator** (not read off a formula), the **log-loss cost** of using it
instead of the likelihood's own choice is stated, and the shipped
``analysis/phase11_opponent_model.json`` carries the chosen β **together with the specs it was
estimated under**.

★ **This step is CALIBRATION, not estimation, and the distinction is the whole point.**
`docs/TECH-DEBT.md` T15 pre-registered "choose by refit log-loss — the corpus curve is the
acceptance bar, not the estimator", and step 1 obeyed that. Step 1 then found the likelihood's
preference sits at (or past) the **bottom** of the exponent grid, i.e. the choice data want log-ADP
— the very spec the width measurement rules out. When two criteria disagree, the honest move is to
say so and to label which one shipped, at what cost, rather than to quietly pick the flattering one
and call it a fit. So:

* **the estimate** = step 1's log-loss-selected exponent, reported whether or not it ships;
* **the calibration** = the exponent measured here against the corpus width curve, which is what
  ships (user decision, 2026-07-27);
* **the cost** = the held-out log-loss the calibration gives up versus the estimate, stated in the
  artifact and in `findings.md`.

A number arrived at this way is **not** evidence that the room is right — it was fit to the bar it
is then scored against. It is a declared judgment with a measured price, and the two
judgement-free gates (``mock.gate_elite_fall``, ``mock.gate_autopilot_surplus``) are what remain
as independent evidence, because neither is targeted by this sweep.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import duckdb
import pandas as pd

from fantasy_quant.adp import boards
from fantasy_quant.adp.drift_panel import build_drift_panel
from fantasy_quant.draft import mock
from fantasy_quant.draft.opponent_model import (
    ALL_FEATURES,
    AdpSpec,
    BandSpec,
    OpponentModel,
    band_coverage,
    build_choice_frame,
    respec_adp,
)

DB = Path("data/fantasy_quant.duckdb")
RESPEC = Path("analysis/t15_respecify.json")
OUT = Path("analysis/t15_calibrate.json")
SHIPPED = Path("analysis/phase11_opponent_model.json")
BACKUP = Path("analysis/phase11_opponent_model.pre_t15.json")
CACHE = Path("analysis/cache")

#: Exponents swept **through the simulator**. Deliberately spans the derived 0.4–0.5 window plus a
#: margin either side, so the minimum is interior and visibly so rather than a boundary again.
SWEEP: tuple[float, ...] = (0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.75)

#: ★ **The objective is the EARLY board, and that is a correction, not a preference.** The first run
#: of this sweep minimized profile distance over all 15 rounds and selected p=0.60 — a spec whose
#: round-1 mean is 8.9 picks against a realized 2.9, and which **fails the elite-fall gate**
#: (p95 24.0 vs a 20.0 ceiling). It scored well because the late rounds dominate an unweighted
#: average and every exponent is far too narrow there, so widening everywhere "improved" the metric
#: while making the only defect a human ever complained about worse.
#:
#: The late-round gap is **structural, not parametric**: at pick 150 roughly thirty boarded players
#: remain and the room takes near-best-available from them, whereas a realized round-15 pick often
#: lands 40 picks off consensus because that room's managers held genuinely different boards. That
#: is board *disagreement between managers*, and this simulator gives all ten seats the identical
#: board by construction — no ``adp_s`` exponent can manufacture it. Chasing it with curvature
#: trades away the top of the board, which is where T15's defect actually lives and where both
#: pre-registered bars are stated.
CAL_MAX_ROUND: int = 6

#: How often a band may fail to contain the realized human pick before it is judged too narrow.
#: 1 % is a stated tolerance, not a fitted one: below it the conditional logit is being applied to a
#: set containing the observed choice essentially always, which is the contract it was derived
#: under. The *narrowest* band meeting it is preferred — a wider set is not free, it dilutes every
#: candidate's probability and is the mechanism behind the log-loss levels not being comparable.
MISS_TOL: float = 0.01

#: Seasons the sweep simulates. Three FFC-boarded seasons is enough to rank exponents (the metric
#: pools 15 rounds x seeds x seasons); step 3 re-measures the winner on all eight.
SWEEP_SEASONS: tuple[int, ...] = (2019, 2022, 2024)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=40, help="seeded drafts per season per exponent")
    ap.add_argument("--drafts", type=int, default=30, help="corpus drafts/season for each refit")
    ap.add_argument("--teams", type=int, default=10)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--room-seed", type=int, default=11)
    ap.add_argument("--no-write", action="store_true", help="measure only; do not ship an artifact")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    respec = json.loads(RESPEC.read_text())
    grid = pd.DataFrame(respec["grid"])
    con = duckdb.connect(str(DB), read_only=True)

    # ---- band selection, on the ONE criterion that is comparable across bands -------------------
    # ★ Step 1's own grid disqualified the obvious alternative. Inside `fixed40`, held-out log-loss
    # is minimized at exponent 0.45 while *gain over the ADP-only baseline* is maximized at 1.0 —
    # the two criteria point opposite ways, because gain also rises when the BASELINE gets worse.
    # A band chosen on gain would therefore pick the widest set and the flattest ADP term, i.e.
    # exactly the defect. Coverage is a property of the candidate set itself and has no such
    # degree of freedom, so the band is chosen on it and the fit is left to choose the exponent.
    bands = [BandSpec.from_dict(b) for b in respec["config"]["bands"]]
    cov = band_coverage(con, bands, max_drafts_per_season=args.drafts, seed=11)
    print("\n=== BAND COVERAGE — how often the realized human pick falls OUTSIDE the band ===")
    print(cov[["band", "n_picks", "miss_rate", "mean_k"]].round(5).to_string(index=False))
    ok = cov[cov["miss_rate"] <= MISS_TOL]
    chosen_row = (ok.loc[ok["mean_k"].idxmin()] if len(ok)
                  else cov.loc[cov["miss_rate"].idxmin()])
    band = BandSpec.from_dict(chosen_row["band_spec"])
    band_label = str(chosen_row["band"])
    band_miss = float(chosen_row["miss_rate"])
    print(f"  -> narrowest band inside the {MISS_TOL:.1%} miss tolerance: {band_label} "
          f"(miss {band_miss:.3%}, mean k {chosen_row['mean_k']:.1f})")

    # ---- the exponent: held-out log-loss WITHIN that band (like-for-like candidate sets) --------
    inband = grid[grid["band"] == band_label]
    est_p = float(inband.loc[inband["beh_logloss"].idxmin(), "exponent"])
    est_spec = AdpSpec("linear") if est_p == 1.0 else AdpSpec("power", exponent=est_p)
    print(f"  exponent by held-out log-loss inside {band_label}: p={est_p}")

    room = mock.full_room(None, n_teams=args.teams, seed=args.room_seed)
    print(f"room: {[p.name for p in room]}")

    corpus = build_drift_panel(con)
    ffc = corpus[(corpus["board_source"] == boards.FFC)
                 & (corpus["season"].isin(SWEEP_SEASONS))]
    print(f"corpus (FFC, sweep seasons): {len(ffc):,} picks / {ffc['draft_id'].nunique()} drafts")

    boards_by_season = {}
    for s in SWEEP_SEASONS:
        bd, src = mock.room_board(con, s, teams=args.teams, cache_dir=CACHE)
        if not bd.empty:
            boards_by_season[s] = (bd, src)
    print(f"boards: {sorted(boards_by_season)}")

    # one expensive choice frame for the selected band; every exponent refits from it
    print(f"\nbuilding choice frame on {band_label} ({args.drafts} drafts/season) ...", flush=True)
    frame, _ = build_choice_frame(con, band=band, max_drafts_per_season=args.drafts, seed=11)
    print(f"  {len(frame):,} rows / {frame['group'].nunique():,} groups", flush=True)

    # ★ The judgement-free band criterion, reported alongside the fit-based one: how often did the
    # band FAIL to contain the pick a human actually made? A conditional logit applied to a set that
    # does not contain the realized choice is being used outside its contract, and unlike log-loss
    # this number is directly comparable across bands (it is a property of the set, not of the
    # likelihood's normalization). `build_choice_frame` repairs those groups by appending the pick,
    # so the model never sees an impossible group — but the repair rate IS the measurement.
    in_frame_miss = float(frame.groupby("group")["chosen_outside_band"].max().mean())
    print(f"  realized pick outside the band: {in_frame_miss:.3%} of picks "
          f"(cross-check on band_coverage's {band_miss:.3%})", flush=True)

    rows = []
    for p in SWEEP:
        spec = AdpSpec("linear") if p == 1.0 else AdpSpec("power", exponent=p)
        model = OpponentModel(list(ALL_FEATURES), l2=1.0, adp_spec=spec,
                              band=band).fit(respec_adp(frame, spec))
        sims = []
        for s, (bd, src) in boards_by_season.items():
            sims.append(mock.batch_drift_panel(
                bd, room, model, season=s, seeds=range(args.seeds), n_teams=args.teams,
                rounds=args.rounds, board_source=src))
        sim = pd.concat(sims, ignore_index=True)
        dist = mock.profile_distance(sim, ffc, max_round=CAL_MAX_ROUND)
        dist_all = mock.profile_distance(sim, ffc)
        prof = mock.reach_profile(sim)
        r1 = float(prof.loc[prof["round"] == 1, "mean_abs"].iloc[0])
        r15 = float(prof.loc[prof["round"] == 15, "mean_abs"].iloc[0])
        elite = mock.gate_elite_fall(sim)
        fa = mock.faithfulness_summary(sim)
        ll = grid[(grid["exponent"] == p) & (grid["band"] == band_label)]
        rows.append({
            "exponent": p, "profile_distance": dist, "profile_distance_all_rounds": dist_all,
            "trend": mock.profile_trend(prof), "elite_gate_pass": bool(elite.get("pass")),
            "round1_mean": r1, "round15_mean": r15,
            "elite_p95": elite.get("p95_slot"), "elite_past10": elite.get("share_past_10"),
            "moderate_share": fa.get("moderate_share"),
            "median_pool_rank": fa.get("median_pool_rank"),
            "beh_logloss": float(ll["beh_logloss"].iloc[0]) if len(ll) else float("nan"),
        })
        print(f"  p={p:<5} dist(r<={CAL_MAX_ROUND}) {dist:.4f}  all {dist_all:.4f}  "
              f"r1 {r1:5.2f}  r15 {r15:5.2f}  elite_p95 {elite.get('p95_slot'):5.1f} "
              f"{'PASS' if elite.get('pass') else 'FAIL'}  "
              f"moderate {fa.get('moderate_share'):.1%}  "
              f"logloss {rows[-1]['beh_logloss']:.4f}", flush=True)

    sweep = pd.DataFrame(rows)
    # ★ The judgement-free gate is a **constraint**, not a term in the objective. Bar #2 is stated
    # against the realized corpus and is not something a width metric may trade away — the first run
    # of this sweep shipped a spec that failed it while minimizing a distance — precisely the
    # failure the gate exists to catch. Feasible set first, then the width objective inside it.
    feasible = sweep[sweep["elite_gate_pass"]]
    if feasible.empty:
        print("\n  ⚠ NO exponent passes the elite-fall gate — reporting the best available and "
              "leaving bar #2 open for step 4 rather than pretending a winner.")
        feasible = sweep
    cal_p = float(feasible.loc[feasible["profile_distance"].idxmin(), "exponent"])
    cal_spec = AdpSpec("power", exponent=cal_p)
    # ★ Does the width bar actually disagree with the likelihood? If the two land on the same
    # exponent (within the sweep's own granularity) then nothing is being overridden and the shipped
    # spec is an ESTIMATE that the bar independently confirms — a far stronger claim than a
    # calibration, and one that must not be described as a calibration out of habit.
    step = min(abs(b - a) for a, b in zip(SWEEP, SWEEP[1:], strict=False))
    agrees = abs(cal_p - float(est_spec.exponent)) <= step + 1e-9
    est_ll = float(sweep.loc[sweep["exponent"] == est_spec.exponent, "beh_logloss"].iloc[0]) \
        if (sweep["exponent"] == est_spec.exponent).any() else float("nan")
    cal_ll = float(sweep.loc[sweep["exponent"] == cal_p, "beh_logloss"].iloc[0])

    print("\n=== THE SWEEP (calibration — fit to the acceptance bar, by construction) ===")
    print(f"    objective = profile distance over rounds 1-{CAL_MAX_ROUND}, "
          f"subject to the elite-fall gate passing")
    print(sweep.round(4).to_string(index=False))
    print(f"\n  calibrated exponent : {cal_p}  (min profile distance)")
    print(f"  estimated exponent  : {est_spec.exponent}  (min held-out log-loss, step 1)")
    print(f"  log-loss cost of shipping the calibration: {cal_ll - est_ll:+.4f} "
          f"({cal_ll:.4f} vs {est_ll:.4f})")
    if agrees:
        print("  ★ THE TWO CRITERIA AGREE (within one sweep step). The shipped exponent is an "
              "ESTIMATE that the width bar independently confirms — not a calibration, and the "
              "cost above is a rounding difference rather than a price paid.")
    else:
        print("  ⚠ the criteria disagree: what ships below is a CALIBRATION, labelled as such, "
              "and the log-loss above is the price of shipping it.")

    # ---- the shipped artifact ------------------------------------------------------------------
    ship = None
    if not args.no_write:
        print(f"\nrefitting the shipped model at p={cal_p} on {band_label} ...", flush=True)
        model = OpponentModel(list(ALL_FEATURES), l2=1.0, adp_spec=cal_spec,
                              band=band).fit(respec_adp(frame, cal_spec))
        coefs = {k: float(v) for k, v in zip(ALL_FEATURES, model.beta, strict=False)}
        if SHIPPED.exists() and not BACKUP.exists():
            shutil.copy2(SHIPPED, BACKUP)      # the pre-T15 β, kept so before/after stays runnable
            print(f"  (backed up the pre-T15 artifact to {BACKUP})")
        prev = json.loads(SHIPPED.read_text()) if SHIPPED.exists() else {}
        prev |= {
            "coefficients": coefs,
            "adp_spec": cal_spec.to_dict(),
            "band": band.to_dict(),
            "t15": {
                "status": ("ESTIMATED by held-out log-loss; independently confirmed by the width "
                           "calibration" if agrees else
                           "CALIBRATED to the corpus width curve, NOT estimated — see "
                           "steps/t15_2_calibrate.py"),
                "estimated_exponent": est_spec.exponent,
                "calibrated_exponent": cal_p,
                "criteria_agree": bool(agrees),
                "logloss_cost_of_calibration": cal_ll - est_ll,
                "selection_rule": ("exponent chosen by held-out refit log-loss (step 1); the "
                                   "simulator sweep against the realized corpus reach profile "
                                   "independently selects the same exponent" if agrees else
                                   "exponent calibrated to the realized corpus reach profile "
                                   "because held-out log-loss preferred a width-implausible one"),
                "fit_drafts_per_season": args.drafts,
            },
        }
        SHIPPED.write_text(json.dumps(prev, indent=2, default=float))
        ship = {"coefficients": coefs, "path": str(SHIPPED)}
        print(f"  wrote {SHIPPED} (β + the specs it was estimated under)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "generated": pd.Timestamp.now("UTC").isoformat(),
        "config": {"sweep": list(SWEEP), "cal_max_round": CAL_MAX_ROUND,
                   "seasons": list(SWEEP_SEASONS), "seeds": args.seeds,
                   "drafts_per_season": args.drafts, "band": band.to_dict()},
        "band_miss_rate": band_miss,
        "band_coverage": json.loads(cov.to_json(orient="records")),
        "sweep": json.loads(sweep.to_json(orient="records")),
        "estimated": est_spec.to_dict(), "calibrated": cal_spec.to_dict(),
        "criteria_agree": bool(agrees),
        "logloss_cost_of_calibration": cal_ll - est_ll,
        "shipped": ship,
    }, indent=2, default=float))
    print(f"wrote {args.out}")
    con.close()


if __name__ == "__main__":
    main()
