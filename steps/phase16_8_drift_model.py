"""Phase 16.8 — the drift-predictability verdict (survive or drop).

    uv run python steps/phase16_8_drift_model.py

Fits ``drift_centered ~ features`` on the Phase-16.7 panel and scores it **leave-one-season-out**
against the only baseline that counts — ``drift = 0``, "everyone goes at ADP". Reports:

1. the **headline** fit (all features, ``source_divergence`` computed leave-one-draft-out),
2. the **ablation** without ``source_divergence`` — because that feature is derived from the
   target's own sibling drafts, a verdict that survives only *with* it is a leak, not a signal,
3. per-feature coefficients (rounds of drift per 1 SD) with season-block-bootstrap CIs, and
4. leave-one-season-out **sign stability**, the Phase-6.3 guard against a feature that flips.

The metric and the baseline are fixed here before the numbers are read, and nothing is retuned
afterwards. A null is a publishable result in this project — 16.1/16.2 returned one on the value
side and were reported as such.
"""

from __future__ import annotations

import json
from pathlib import Path

from fantasy_quant.adp import drift_model as dm
from fantasy_quant.adp import drift_panel as dp
from fantasy_quant.data import db
from fantasy_quant.projections.rookie import rookie_projection
from fantasy_quant.valuation.value_board import value_board

OUT = Path(__file__).resolve().parents[1] / "analysis" / "phase16_8_drift_model.json"

#: the bar, set before the result is seen: beat drift=0 by this much MAE, with a CI clear of zero.
SKILL_BAR = 0.02


def main() -> None:
    con = db.connect(read_only=True)

    # ★ The pre-registered headline is defined on FFC-boarded rows — the yardstick 16.8 was
    # registered against in Session F. Session F.6 added an ECR fallback board that recovers 2025
    # (which FFC never published); ECR is a calibrated *proxy* for ADP, not ADP, so it is reported
    # as a clearly separate sensitivity below and never folded into the headline. Re-asking a
    # pre-registered test on a widened definition of the data would be threshold-moving.
    full_panel = dp.build_drift_panel(con, allow_ecr=True)
    panel = full_panel[full_panel["board_source"] == "ffc"].reset_index(drop=True)
    feats = dm.build_features(con, panel,
                              lambda c, s: value_board(c, s, rookie_fn=rookie_projection))
    print(f"panel (FFC-boarded, the pre-registered population): {len(feats):,} picks · "
          f"{feats['draft_id'].nunique()} drafts · {feats['season'].nunique()} seasons")
    n_ecr = int((full_panel["board_source"] == "ecr").sum())
    print(f"  (+{n_ecr:,} ECR-boarded rows held out of the headline, reported separately)\n")

    # ---- 1/2. walk-forward verdicts -------------------------------------------------------------
    head = dm.walk_forward_drift(feats, dm.DRIFT_FEATURES)
    abl = dm.walk_forward_drift(feats, dm.ABLATION_FEATURES)
    print("=== HEADLINE (all features, held-out-draft source_divergence) ===")
    print(head.render())
    print("\n=== ABLATION (source_divergence dropped) ===")
    print(abl.render())

    print("\n  per held-out season (headline):")
    print(head.per_season.to_string(index=False))

    # ---- 3. which features, on the Phase-6 scale ------------------------------------------------
    # Reported for BOTH feature sets. The headline coefficients are conditioned on the leak-prone
    # source_divergence, so any behavioural claim has to survive in the ablation column too — that
    # is the one built entirely from data the target did not help construct.
    def _coefs(features, n_boot=2000):
        reg = dm.fit_drift(feats, features, n_boot=n_boot)
        stab = dm.sign_stability(feats, features)
        t = reg.table().merge(stab[["term", "stability"]], on="term", how="left")
        t["sig"] = (t["ci_lo"] > 0) | (t["ci_hi"] < 0)
        return reg, t

    reg, tbl = _coefs(dm.DRIFT_FEATURES)
    reg_a, tbl_a = _coefs(dm.ABLATION_FEATURES)
    fmt = lambda v: f"{v:+.4f}"  # noqa: E731
    print(f"\n=== pooled coefficients — HEADLINE (rounds per 1 SD; R²={reg.r2:.4f}) ===")
    print(tbl.to_string(index=False, float_format=fmt))
    print(f"\n=== pooled coefficients — ABLATION (no source_divergence; R²={reg_a.r2:.4f}) ===")
    print(tbl_a.to_string(index=False, float_format=fmt))

    # what stands on its own: significant + sign-stable in the ablation fit.
    survivors = tbl_a[(tbl_a["sig"]) & (tbl_a["stability"] >= 0.99)
                      & (tbl_a["term"] != "intercept")]["term"].tolist()
    print(f"\n  survive without the leak-prone feature (sig + 100% sign-stable): {survivors}")

    # ---- 4. the verdict --------------------------------------------------------------------------
    survives = (head.skill > SKILL_BAR and head.skill_ci[0] > 0)
    survives_abl = (abl.skill > SKILL_BAR and abl.skill_ci[0] > 0)
    verdict = ("PREDICTS" if survives and survives_abl else
               "PREDICTS ONLY WITH THE LEAK-PRONE FEATURE" if survives else
               "DOES NOT PREDICT (honest null)")
    print(f"\n=== VERDICT: drift {verdict} ===")
    print(f"  bar set in advance: skill > {SKILL_BAR:.0%} with a bootstrap CI clear of 0.")
    print(f"  headline skill {head.skill:+.2%} CI[{head.skill_ci[0]:+.2%},{head.skill_ci[1]:+.2%}]"
          f"  ·  ablation {abl.skill:+.2%} "
          f"CI[{abl.skill_ci[0]:+.2%},{abl.skill_ci[1]:+.2%}]")
    if not survives:
        print("  → 16.9 must NOT be given a quantitative drift prediction to amplify. It can\n"
              "    still reproduce realized draft-slot DISPERSION (a variance match needs no\n"
              "    mean signal), and 16.10's curated hype board remains the labelled-subjective\n"
              "    channel.")
        if survivors:
            print(f"  → but these DO stand on their own and are what 16.9 should shape its shock\n"
                  f"    with, as descriptive room behaviour rather than a per-player forecast:\n"
                  f"    {', '.join(survivors)}")

    # ---- 5. sensitivity: the same fit with the ECR-boarded season admitted ----------------------
    # Reported AFTER the verdict and never mixed into it. If the two disagree, the disagreement is
    # about the proxy board, not about drift.
    sens = None
    if n_ecr:
        feats_all = dm.build_features(
            con, full_panel, lambda c, s: value_board(c, s, rookie_fn=rookie_projection))
        h_all = dm.walk_forward_drift(feats_all, dm.DRIFT_FEATURES)
        a_all = dm.walk_forward_drift(feats_all, dm.ABLATION_FEATURES)
        sens = {"headline_skill": h_all.skill, "headline_ci": list(h_all.skill_ci),
                "ablation_skill": a_all.skill, "ablation_ci": list(a_all.skill_ci),
                "n": h_all.n, "n_seasons": h_all.n_seasons}
        print("\n=== SENSITIVITY — ECR-boarded 2025 admitted (NOT the pre-registered headline) ===")
        print(f"  headline {h_all.skill:+.2%} CI[{h_all.skill_ci[0]:+.2%},{h_all.skill_ci[1]:+.2%}]"
              f"  ·  ablation {a_all.skill:+.2%} "
              f"CI[{a_all.skill_ci[0]:+.2%},{a_all.skill_ci[1]:+.2%}]  (n={h_all.n:,})")

    # structural gates — the harness is sound even when the answer is 'no'.
    assert head.n > 0 and abl.n > 0, "walk-forward produced no held-out rows"
    assert head.mae_baseline > 0, "degenerate baseline"
    assert len(tbl) == len(dm.DRIFT_FEATURES) + 4, "coefficient table lost a term"

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "skill_bar": SKILL_BAR,
        "verdict": verdict,
        "headline": {"features": head.features, "mae": head.mae,
                     "mae_baseline": head.mae_baseline, "skill": head.skill,
                     "skill_ci": list(head.skill_ci), "spearman": head.spearman,
                     "spearman_p": head.spearman_p, "n": head.n, "n_seasons": head.n_seasons,
                     "per_season": head.per_season.to_dict(orient="records")},
        "ablation": {"features": abl.features, "mae": abl.mae, "mae_baseline": abl.mae_baseline,
                     "skill": abl.skill, "skill_ci": list(abl.skill_ci),
                     "spearman": abl.spearman, "spearman_p": abl.spearman_p, "n": abl.n},
        "coefficients": tbl.to_dict(orient="records"),
        "coefficients_ablation": tbl_a.to_dict(orient="records"),
        "survivors_without_leak_prone_feature": survivors,
        "r2": reg.r2,
        "r2_ablation": reg_a.r2,
        "sensitivity_with_ecr_board": sens,
    }, indent=2, default=float))
    print(f"\n  wrote {OUT.relative_to(OUT.parents[1])}")
    print("\nPhase 16.8 (drift model) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
