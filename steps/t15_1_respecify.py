"""T15 step 1 — respecify ``adp_s`` (+ the candidate band) and refit 11.1.

    uv run python steps/t15_1_respecify.py                    # the grid, then the winner's refit
    uv run python steps/t15_1_respecify.py --drafts 20        # cheaper grid (default 20)
    uv run python steps/t15_1_respecify.py --final-drafts 60  # the pre-registered final-fit budget

Done when: an ``AdpSpec`` (and ``BandSpec``) has been **selected by held-out refit log-loss**, not
by curve-fitting the corpus width table, and the winner is refit at the pre-registered budget and
written to ``analysis/t15_respecify.json``.

★ **The pre-registration this obeys** (`docs/TECH-DEBT.md` T15): *choose by refit log-loss — the
corpus curve is the acceptance bar, not the estimator.* Bar #1 is therefore not consulted anywhere
in this file. Whether the winner clears it is measured afterwards, by re-running step 0's harness.

★ **The comparability trap, and how selection avoids it.** A conditional logit's log-loss depends on
how many alternatives it is choosing between, so a wider band scores worse *by construction* — its
raw log-loss is not comparable to a narrow band's. Two consequences, both load-bearing:

1. **Within a band**, exponents are compared on held-out log-loss directly (same candidate sets, so
   the comparison is clean). This is how the ADP transform is chosen.
2. **Across bands**, the only comparable quantity is the **gain over an ADP-only baseline fit and
   scored on that same band** — both terms move together, so the mechanical penalty cancels. A band
   is preferred only if it makes the *behavioural* part of the model do more work.

Reporting raw log-loss across bands and picking the minimum would select the narrowest band every
time, and would look exactly like a result.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from fantasy_quant.data.db import connect
from fantasy_quant.draft.opponent_model import (
    ADP_ONLY,
    ALL_FEATURES,
    AdpSpec,
    BandSpec,
    build_choice_frame,
    respec_adp,
    walk_forward,
)

OUT = Path("analysis/t15_respecify.json")

#: The exponent grid. Brackets the derived p ≈ 0.4–0.5 on both sides and includes **1.0 (the
#: shipped linear spec)** so the incumbent competes in its own grid rather than being assumed worse.
#:
#: ★ **It reaches down to 0.05 on purpose, and that end of the grid is log-ADP.** For small p,
#: ``(a/s)^p = 1 + p·ln(a/s) + O(p²)`` — a constant (which cancels in the softmax) plus ``p·log a``.
#: So the p→0 limit of this family **is** the log spec T15 ruled out on width grounds, reached
#: continuously. Running the grid down there is what lets the two criteria disagree *visibly*
#: instead of the disagreement hiding at a boundary: if held-out log-loss keeps improving all the
#: way down, that is the likelihood asking for log-ADP, and it must be reported as such rather than
#: quietly truncated at a value that happens to suit the acceptance bar.
EXPONENTS: tuple[float, ...] = (0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.45, 0.5, 0.6, 0.75, 1.0)

#: The bands. ``fixed/40`` is the shipped Session-G contract; the widening variants add ``growth``
#: candidates per round on top of the same base, so round 1 is identical in all of them and they
#: differ only in how much deeper the set reaches later — which is exactly the T16 question.
BANDS: tuple[BandSpec, ...] = (
    BandSpec(kind="fixed", k0=40),
    BandSpec(kind="widening", k0=40, growth=5, k_max=160),
    BandSpec(kind="widening", k0=40, growth=10, k_max=160),
    BandSpec(kind="widening", k0=40, growth=20, k_max=160),
)


def _label(band: BandSpec) -> str:
    return "fixed40" if band.kind == "fixed" else f"widen+{band.growth:g}"


def evaluate(frame: pd.DataFrame, spec: AdpSpec, *, n_boot: int) -> dict:
    """Walk-forward the behavioural model and its ADP-only baseline under one ADP spec."""
    f = respec_adp(frame, spec)
    wf = walk_forward(f, list(ALL_FEATURES), l2=1.0, baseline_cols=list(ADP_ONLY), n_boot=n_boot)
    p = wf["pooled"]
    return {"beh_logloss": p["beh_logloss"], "base_logloss": p["base_logloss"],
            "logloss_gain": p["logloss_gain"], "logloss_gain_ci": p["logloss_gain_ci"],
            "beh_brier": p["beh_brier"], "brier_gain": p["brier_gain"],
            "beats_adp": bool(p["beats_adp"])}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--drafts", type=int, default=20,
                    help="drafts/season for the SELECTION grid (kept small; 4 bands x 8 exponents)")
    ap.add_argument("--final-drafts", type=int, default=60,
                    help="drafts/season for the winner's refit — the pre-registered 11.1 budget")
    ap.add_argument("--boot", type=int, default=200, help="bootstrap draws inside the grid")
    ap.add_argument("--final-boot", type=int, default=500)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    con = connect(read_only=True)
    rows: list[dict] = []

    # ---- the grid: one expensive frame per band, every exponent refit from it -------------------
    for band in BANDS:
        print(f"\n=== band {_label(band)} — building choice frame "
              f"({args.drafts} drafts/season) ...", flush=True)
        frame, _ = build_choice_frame(con, band=band, max_drafts_per_season=args.drafts, seed=11)
        n_groups = int(frame["group"].nunique())
        mean_k = float(frame.groupby("group").size().mean())
        print(f"    {len(frame):,} candidate rows / {n_groups:,} groups "
              f"(mean candidate set {mean_k:.1f})", flush=True)
        for p in EXPONENTS:
            spec = AdpSpec("linear") if p == 1.0 else AdpSpec("power", exponent=p)
            r = evaluate(frame, spec, n_boot=args.boot)
            r |= {"band": _label(band), "band_spec": band.to_dict(), "exponent": p,
                  "adp_spec": spec.to_dict(), "n_groups": n_groups, "mean_candidates": mean_k}
            rows.append(r)
            print(f"    p={p:<5} logloss {r['beh_logloss']:.4f}  base {r['base_logloss']:.4f}  "
                  f"gain {r['logloss_gain']:+.4f}", flush=True)
        del frame

    grid = pd.DataFrame(rows)

    # ---- selection, in the two stages the comparability trap forces ----------------------------
    # 1. the exponent: lowest held-out log-loss inside the shipped fixed band (like-for-like sets)
    fixed = grid[grid["band"] == "fixed40"]
    best_p = float(fixed.loc[fixed["beh_logloss"].idxmin(), "exponent"])
    # 2. the band: largest gain over an ADP-only baseline scored on that same band, at that exponent
    at_p = grid[grid["exponent"] == best_p]
    best_band_label = str(at_p.loc[at_p["logloss_gain"].idxmax(), "band"])
    best_band = next(b for b in BANDS if _label(b) == best_band_label)
    best_spec = AdpSpec("linear") if best_p == 1.0 else AdpSpec("power", exponent=best_p)

    print("\n=== GRID (held-out, walk-forward) ===")
    print(grid.pivot(index="exponent", columns="band",
                     values="beh_logloss").round(4).to_string())
    print("\n  gain over ADP-only (the band-comparable quantity):")
    print(grid.pivot(index="exponent", columns="band",
                     values="logloss_gain").round(4).to_string())
    # ★ Report whether the likelihood actually has an interior optimum. If the minimum sits at the
    # smallest exponent in the grid, the "selection" is a boundary, not an estimate — the data are
    # asking for log-ADP (or steeper) and the honest statement is that log-loss does not identify a
    # width-plausible exponent at all. Silently shipping a boundary as a fitted value is the exact
    # move that would turn a disagreement between two criteria into a fake modelling result.
    fx = fixed.sort_values("exponent")
    at_boundary = bool(best_p == float(fx["exponent"].min()))
    print(f"\n  SELECTED: exponent {best_p} (by log-loss inside fixed40), "
          f"band {best_band_label} (by gain at that exponent)")
    if at_boundary:
        print("  ⚠ the log-loss minimum sits at the GRID BOUNDARY — the likelihood prefers "
              "log-ADP or steeper, and does not identify an interior exponent. Reported as such; "
              "the width calibration (step 2) is what decides the shipped spec.")

    # ---- the winner, refit at the pre-registered budget -----------------------------------------
    print(f"\n=== FINAL REFIT — {best_spec.to_dict()} / {best_band.to_dict()} "
          f"at {args.final_drafts} drafts/season ...", flush=True)
    frame, feats = build_choice_frame(con, band=best_band, adp_spec=best_spec,
                                      max_drafts_per_season=args.final_drafts, seed=11)
    from fantasy_quant.draft.opponent_model import OpponentModel
    full = OpponentModel(list(ALL_FEATURES), l2=1.0, adp_spec=best_spec, band=best_band).fit(frame)
    coefs = dict(zip(ALL_FEATURES, (float(b) for b in full.beta), strict=False))
    final_wf = walk_forward(frame, feats, l2=1.0, baseline_cols=list(ADP_ONLY),
                            n_boot=args.final_boot)

    # ★ the interpretable table: every coefficient in ADP picks, at the top of the board and deep.
    # Under curvature "how many picks is `is_TE` worth" has no single answer, and that IS the fix —
    # so it is reported at both ends rather than as one number that would now be wrong twice.
    per_pick = {d: float(np.asarray(best_spec.utility_per_pick(d)).reshape(-1)[0])
                for d in (5.0, 50.0, 150.0)}
    b_adp = abs(coefs["adp_s"])
    # `adp_s` is excluded: "how many ADP picks is one unit of adp_s worth" is a tautology, and
    # printing it invites reading 1/f'(a) as a behavioural coefficient.
    other = {k: v for k, v in coefs.items() if k != "adp_s"}
    picks_tbl = pd.DataFrame({
        "beta": other,
        **{f"picks@adp{int(d)}": {k: (abs(v) / (b_adp * pp)) for k, v in other.items()}
           for d, pp in per_pick.items()},
    })
    print("\nFitted coefficients, and what each is worth in ADP picks at three board depths:")
    print(picks_tbl.round(3).to_string())
    p = final_wf["pooled"]
    print(f"\n  11.1 walk-forward: log-loss gain {p['logloss_gain']:+.4f} "
          f"CI[{p['logloss_gain_ci'][0]:+.4f},{p['logloss_gain_ci'][1]:+.4f}]  "
          f"({'BEATS' if p['beats_adp'] else 'does NOT beat'} ADP)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "generated": pd.Timestamp.now("UTC").isoformat(),
        "config": {"exponents": list(EXPONENTS), "bands": [b.to_dict() for b in BANDS],
                   "grid_drafts_per_season": args.drafts,
                   "final_drafts_per_season": args.final_drafts},
        "grid": json.loads(grid.to_json(orient="records")),
        "selected": {"adp_spec": best_spec.to_dict(), "band": best_band.to_dict(),
                     "logloss_minimum_at_grid_boundary": at_boundary,
                     "selection_rule": "exponent by held-out log-loss within the fixed band; "
                                       "band by gain over an ADP-only baseline at that exponent"},
        "final_fit": {"coefficients": coefs, "meta": full.meta,
                      "picks_per_unit": json.loads(picks_tbl.to_json(orient="index")),
                      "walk_forward": final_wf},
    }, indent=2, default=float))
    print(f"\nwrote {args.out}")
    con.close()


if __name__ == "__main__":
    main()
