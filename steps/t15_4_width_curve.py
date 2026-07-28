"""T15 step 4 — fit the depth-width curve jointly with the ADP exponent.

    uv run python steps/t15_4_width_curve.py                 # the joint sweep, then ship
    uv run python steps/t15_4_width_curve.py --no-write      # measure only

Done when: a ``(AdpSpec.exponent, WidthCurve.gamma)`` pair is chosen that clears **both**
judgement-free gates *and* does not degrade the 16.9 dispersion match, or — if no pair does — the
frontier is reported and the failure is named.

★ **Why a second knob, and why it is not tuning-until-green.** Step 2 shipped ``p = 0.15`` because
the elite-fall gate admitted nothing flatter. Step 3 then measured what that costs everywhere else:
the room came out **uniformly too narrow** (rounds 2–15 at 0.94 → 0.26× the corpus width) and the
16.9 dispersion match went **+8.8 % → −53.6 %** — a pre-registered bar (#5) failing. That is not a
tuning problem but an identification problem: **ADP curvature sets top-of-board tightness and depth
dispersion with one parameter, and the corpus wants opposite values at the two ends.**

The reason curvature cannot do both is **pool exhaustion**, which the ``w_a ∝ a^(1-p)`` derivation
ignores. By round 15 roughly thirty boarded players remain, so a seat cannot deviate 27 picks from a
board that no longer has 27 picks of depth beneath it — curvature buys far less late width than the
algebra promises while costing full price at the top.

`docs/BUILD_PLAN.md` §16.14R already specifies the resolution and names T15 as its owner:
**``width(round) × multiplier``**. Step 1 built the per-seat multiplier; this builds the round
function. Two parameters for two independent requirements is the *identified* specification, not a
richer one — and the gates stay constraints, never terms in the objective.
"""

from __future__ import annotations

import argparse
import json
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
    build_choice_frame,
    respec_adp,
)
from fantasy_quant.draft.personalities import WidthCurve

DB = Path("data/fantasy_quant.duckdb")
CALIB = Path("analysis/t15_calibrate.json")
OUT = Path("analysis/t15_width_curve.json")
SHIPPED = Path("analysis/phase11_opponent_model.json")
CACHE = Path("analysis/cache")

#: Exponents kept from step 2's sweep: the gate-feasible pair, plus two flatter ones that only
#: become viable once the width curve carries the depth requirement instead of curvature.
EXPONENTS: tuple[float, ...] = (0.15, 0.25, 0.35, 0.45)

#: Depth-width curve. The corpus grows 2.87 -> 27.1 picks over 15 rounds, i.e. ~``round^0.83`` if
#: the room responded linearly to ``1/β``. It does not (pool exhaustion again), so the grid runs
#: well past that and the fit decides.
GAMMAS: tuple[float, ...] = (0.0, 0.4, 0.8, 1.2)

SWEEP_SEASONS: tuple[int, ...] = (2019, 2022, 2024)

#: Bar #5: |sim/corpus - 1| on pooled within-draft dispersion. The pre-T15 room sat at +8.8 %, so
#: 20 % is a tolerance that cannot be met by accident but does not demand an improvement on a
#: metric T15 was never trying to improve.
DISPERSION_TOL: float = 0.20


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--drafts", type=int, default=30)
    ap.add_argument("--teams", type=int, default=10)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--room-seed", type=int, default=11)
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    calib = json.loads(CALIB.read_text())
    band = BandSpec.from_dict(calib["config"]["band"])
    con = duckdb.connect(str(DB), read_only=True)
    room = mock.full_room(None, n_teams=args.teams, seed=args.room_seed)

    corpus = build_drift_panel(con)
    ffc = corpus[(corpus["board_source"] == boards.FFC)
                 & (corpus["season"].isin(SWEEP_SEASONS))]
    sd_corpus = float(ffc.groupby("draft_id")["drift_centered"].std().mean())
    print(f"corpus: {len(ffc):,} picks / {ffc['draft_id'].nunique()} drafts · "
          f"pooled sd_drift {sd_corpus:.3f}")

    boards_by_season = {}
    for s in SWEEP_SEASONS:
        bd, src = mock.room_board(con, s, teams=args.teams, cache_dir=CACHE)
        if not bd.empty:
            boards_by_season[s] = (bd, src)

    print(f"\nbuilding choice frame on {band.to_dict()} ({args.drafts} drafts/season) ...",
          flush=True)
    frame, _ = build_choice_frame(con, band=band, max_drafts_per_season=args.drafts, seed=11)
    print(f"  {len(frame):,} rows / {frame['group'].nunique():,} groups", flush=True)

    rows = []
    for p in EXPONENTS:
        spec = AdpSpec("power", exponent=p)
        model = OpponentModel(list(ALL_FEATURES), l2=1.0, adp_spec=spec,
                              band=band).fit(respec_adp(frame, spec))
        for gamma in GAMMAS:
            curve = WidthCurve(gamma=gamma, max_round=args.rounds)
            model.width_curve = curve
            sim = pd.concat([
                mock.batch_drift_panel(bd, room, model, season=s, seeds=range(args.seeds),
                                       n_teams=args.teams, rounds=args.rounds, board_source=src)
                for s, (bd, src) in boards_by_season.items()], ignore_index=True)
            prof = mock.reach_profile(sim)
            elite = mock.gate_elite_fall(sim)
            sd_sim = float(sim.groupby("draft_id")["drift_centered"].std().mean())
            disp_err = sd_sim / sd_corpus - 1.0
            fa = mock.faithfulness_summary(sim)
            rows.append({
                "exponent": p, "gamma": gamma,
                "distance_all": mock.profile_distance(sim, ffc),
                "distance_early": mock.profile_distance(sim, ffc, max_round=6),
                "trend": mock.profile_trend(prof),
                "round1": float(prof.loc[prof["round"] == 1, "mean_abs"].iloc[0]),
                "round15": float(prof.loc[prof["round"] == 15, "mean_abs"].iloc[0]),
                "elite_p95": elite.get("p95_slot"), "elite_past10": elite.get("share_past_10"),
                "elite_pass": bool(elite.get("pass")),
                "sd_sim": sd_sim, "dispersion_err": disp_err,
                "dispersion_pass": bool(abs(disp_err) <= DISPERSION_TOL),
                "median_pool_rank": fa.get("median_pool_rank"),
                "moderate_share": fa.get("moderate_share"),
            })
            r = rows[-1]
            print(f"  p={p:<5} γ={gamma:<4} dist {r['distance_all']:.3f}  r1 {r['round1']:5.2f}  "
                  f"r15 {r['round15']:5.2f}  elite {r['elite_p95']:5.1f}"
                  f"{'✓' if r['elite_pass'] else '✗'}  sd {sd_sim:.3f} ({disp_err:+.1%})"
                  f"{'✓' if r['dispersion_pass'] else '✗'}  "
                  f"moderate {r['moderate_share']:.0%}", flush=True)

    sweep = pd.DataFrame(rows)
    print("\n=== THE JOINT SWEEP ===")
    print(sweep.round(3).to_string(index=False))

    feasible = sweep[sweep["elite_pass"] & sweep["dispersion_pass"]]
    print(f"\n  configurations clearing BOTH gates: {len(feasible)} of {len(sweep)}")
    if feasible.empty:
        print("  ⚠ NO configuration clears both. Reporting the frontier; bars #2 and #5 cannot be "
              "met together by (exponent, gamma) alone — a finding, not a tuning target.")
        best = sweep.loc[sweep["distance_all"].idxmin()]
        shipped_ok = False
    else:
        best = feasible.loc[feasible["distance_all"].idxmin()]
        shipped_ok = True
    print(f"  chosen: p={best['exponent']} gamma={best['gamma']}  "
          f"distance {best['distance_all']:.3f}  dispersion {best['dispersion_err']:+.1%}")

    ship = None
    if not args.no_write and shipped_ok:
        spec = AdpSpec("power", exponent=float(best["exponent"]))
        curve = WidthCurve(gamma=float(best["gamma"]), max_round=args.rounds)
        model = OpponentModel(list(ALL_FEATURES), l2=1.0, adp_spec=spec,
                              band=band).fit(respec_adp(frame, spec))
        coefs = {k: float(v) for k, v in zip(ALL_FEATURES, model.beta, strict=False)}
        prev = json.loads(SHIPPED.read_text())
        prev |= {"coefficients": coefs, "adp_spec": spec.to_dict(), "band": band.to_dict(),
                 "width_curve": curve.to_dict()}
        prev["t15"] = (prev.get("t15") or {}) | {
            "status": "exponent + depth-width curve chosen jointly, subject to BOTH "
                      "judgement-free gates as constraints (steps/t15_4_width_curve.py)",
            "width_curve_gamma": float(best["gamma"]),
            "why_two_parameters": "ADP curvature alone sets top-of-board tightness and depth "
                                  "dispersion with one parameter and the corpus wants opposite "
                                  "values; pool exhaustion breaks the a^(1-p) width law at depth",
        }
        SHIPPED.write_text(json.dumps(prev, indent=2, default=float))
        ship = {"coefficients": coefs, "adp_spec": spec.to_dict(),
                "width_curve": curve.to_dict()}
        print(f"  wrote {SHIPPED}")
    elif not shipped_ok:
        print("  nothing shipped — the previous artifact stands, and the gap is documented")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "generated": pd.Timestamp.now("UTC").isoformat(),
        "config": {"exponents": list(EXPONENTS), "gammas": list(GAMMAS),
                   "seasons": list(SWEEP_SEASONS), "seeds": args.seeds,
                   "band": band.to_dict(), "dispersion_tol": DISPERSION_TOL},
        "corpus_sd_drift": sd_corpus,
        "sweep": json.loads(sweep.to_json(orient="records")),
        "both_gates_clear": int(len(feasible)),
        "chosen": json.loads(pd.Series(best).to_json()), "shipped": ship,
    }, indent=2, default=float))
    print(f"wrote {args.out}")
    con.close()


if __name__ == "__main__":
    main()
