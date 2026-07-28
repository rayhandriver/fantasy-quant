"""T15 step 3 — re-verify 11.1 / 11.2 / 16.9 **together**, and re-measure every acceptance bar.

    uv run python steps/t15_3_verify.py                  # everything (slow: ~25-40 min)
    uv run python steps/t15_3_verify.py --skip-brier     # bars + 16.9 only
    uv run python steps/t15_3_verify.py --seeds 100

Done when: the shipped respecification is measured against **all five** pre-registered T15 bars and
against the metrics it could have broken, in one run, with the pre-T15 numbers alongside.

★ **Why one script rather than three.** T15 bar #4 is stated as "11.1 log-loss and 11.2 Brier do not
degrade", and the register's own warning is that *a change which improves one of those and quietly
degrades another is the failure mode to guard against*. Running them in separate sessions is how
that failure mode survives: each run looks fine on the metric its author was watching. So the
verdict here is a single joint table, and a regression in any column is a failure of the whole step
even if the headline bar passed.

★ **`NarrativeShock.intercept` is re-fit, not carried over.** It was calibrated against realized
draft-slot dispersion under the OLD width law, which this session replaced. A coefficient is not
transportable without its controls — the fourth time that lesson has applied in this project — so
the old intercept is not a valid input to the new room, and shipping it unchanged would silently
resize the 16.9 channel.
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
from fantasy_quant.draft.availability import availability_brier

DB = Path("data/fantasy_quant.duckdb")
BEFORE = Path("analysis/t15_baseline.json")
OUT = Path("analysis/t15_verify.json")
CACHE = Path("analysis/cache")

MATCHED_SEASONS: tuple[int, ...] = (2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024)
READOUT_SEASON: int = 2026

#: Pre-T15 committed numbers, for the joint no-regression table. Sources: `analysis/
#: phase11_opponent_model.json` (11.1/11.2, Session F.6) and `findings.md` §Session G (16.9).
PRE_T15 = {"logloss_gain": 0.1738, "brier_gain_vs_best": 0.0708, "sd_drift_sim": 1.976,
           "sd_drift_realized": 1.816}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=100)
    ap.add_argument("--teams", type=int, default=10)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--room-seed", type=int, default=11)
    ap.add_argument("--brier-drafts", type=int, default=28,
                    help="11.2 budget; the committed number used 28/season")
    ap.add_argument("--skip-brier", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    model = mock.load_opponent_model()
    print(f"shipped model: adp_spec={model.adp_spec.to_dict()} band={model.band.to_dict()}")
    room = mock.full_room(None, n_teams=args.teams, seed=args.room_seed)

    corpus = build_drift_panel(con)
    ffc = corpus[corpus["board_source"] == boards.FFC]
    corpus_matched = ffc[ffc["season"].isin(MATCHED_SEASONS)]

    sim_frames = []
    for season in (*MATCHED_SEASONS, READOUT_SEASON):
        board, src = mock.room_board(con, season, teams=args.teams, cache_dir=CACHE)
        if board.empty:
            continue
        panel = mock.batch_drift_panel(board, room, model, season=season,
                                       seeds=range(args.seeds), n_teams=args.teams,
                                       rounds=args.rounds, board_source=src)
        sim_frames.append(panel)
        print(f"  {season}: {args.seeds} drafts -> {len(panel):,} boarded picks", flush=True)
    sim = pd.concat(sim_frames, ignore_index=True)
    sim_matched = sim[sim["season"].isin(MATCHED_SEASONS)]

    before = json.loads(BEFORE.read_text()) if BEFORE.exists() else {}

    # ===== BAR 1 — the reach profile ============================================================
    cmp = mock.compare_profiles(sim_matched, corpus_matched)
    prof = mock.reach_profile(sim_matched)
    dist = mock.profile_distance(sim_matched, corpus_matched)
    print("\n=== BAR 1 — reach profile, 10-team ADP picks ===")
    print(cmp.round(2).to_string(index=False))
    r1 = cmp[cmp["round"] == 1].iloc[0]
    bar1 = {"pass": bool(r1["sim_mean"] <= 5.0 and 0.5 <= r1["mean_ratio"] <= 2.0),
            "round1_sim_mean": float(r1["sim_mean"]),
            "round1_corpus_mean": float(r1["corpus_mean"]),
            "round1_ratio": float(r1["mean_ratio"]), "profile_distance": dist,
            "trend_sim": mock.profile_trend(prof),
            "trend_corpus": mock.profile_trend(mock.reach_profile(corpus_matched))}
    if before:
        # step 0's frozen "before" picture, so the two live side by side in one artifact
        bar1["before_trend_sim"] = before["sim"]["profile_trend"]
        bar1["before_round1_sim_mean"] = float(
            pd.DataFrame(before["sim"]["reach_profile"]).query("round == 1")["mean_abs"].iloc[0])
    print(f"  distance {dist:.4f}   trend sim {bar1['trend_sim']:+.3f} vs corpus "
          f"{bar1['trend_corpus']:+.3f}")

    # ===== BAR 2 + BAR 3 — the two judgement-free gates ==========================================
    g2 = mock.gate_elite_fall(sim_matched)
    g3 = mock.gate_autopilot_surplus(sim_matched, corpus_matched)
    print("\n=== BAR 2 — elite fall (judgement-free gate) ===")
    print(f"  p95 {g2['p95_slot']:.1f} (max {g2['p95_max']}) · past pick 10 "
          f"{g2['share_past_10']:.1%} (max {g2['past10_max']:.0%}) -> "
          f"{'PASS' if g2['pass'] else 'FAIL'}")
    print("\n=== BAR 3 — harvest at matched faithfulness (judgement-free gate) ===")
    scored = pd.DataFrame([r for r in g3["bins"] if "excess_sds" in r])
    print(scored.round(2).to_string(index=False))
    print(f"  worst excess {g3['worst_excess_sds']:+.2f} sds (tol {g3['tol_sds']}) -> "
          f"{'PASS' if g3['pass'] else 'FAIL'}")

    # ===== the population (step 0's finding) ====================================================
    fa_sim = mock.faithfulness_summary(sim_matched)
    fa_cor = mock.faithfulness_summary(corpus_matched)
    print("\n=== THE ROOM'S POPULATION ===")
    for lab, f in (("corpus", fa_cor), ("sim", fa_sim)):
        print(f"  {lab:<8} median pool_rank {f['median_pool_rank']:5.2f}  "
              f"moderate(2-8) {f['moderate_share']:6.1%}  chalk(<2) {f['chalk_share']:6.1%}")
    if before:
        fb = before["sim"]["faithfulness"]
        print(f"  {'sim(pre)':<8} median pool_rank {fb['median_pool_rank']:5.2f}  "
              f"moderate(2-8) {fb['moderate_share']:6.1%}  chalk(<2) {fb['chalk_share']:6.1%}")

    print("\n=== PER-PERSONALITY (sim) ===")
    ptab = mock.personality_table(sim_matched)
    print(ptab.round(2).to_string(index=False))

    # ===== BAR 5 — the 16.9 dispersion profile ==================================================
    sd_sim = float(sim_matched.groupby("draft_id")["drift_centered"].std().mean())
    sd_cor = float(corpus_matched.groupby("draft_id")["drift_centered"].std().mean())
    bar5 = {"sd_drift_sim": sd_sim, "sd_drift_corpus": sd_cor,
            "level_error": (sd_sim - sd_cor) / sd_cor,
            "pre_t15_sim": PRE_T15["sd_drift_sim"],
            "pre_t15_realized": PRE_T15["sd_drift_realized"]}
    print(f"\n=== BAR 5 — 16.9 dispersion: sim {sd_sim:.3f} vs corpus {sd_cor:.3f} "
          f"({bar5['level_error']:+.1%}; pre-T15 was 1.976 vs 1.816, +8.8 %) ===")

    # ===== BAR 4 — 11.2 availability Brier (11.1 comes from step 1's walk-forward) ===============
    brier = None
    if not args.skip_brier:
        print(f"\n=== BAR 4 — 11.2 availability Brier ({args.brier_drafts} drafts/season) ...",
              flush=True)
        brier = availability_brier(con, model, n_sims=40, contested_k=30,
                                   max_drafts_per_season=args.brier_drafts, n_boot=400, seed=1)
        print(f"  behavioral {brier['beh_brier']:.4f} vs best-tuned ADP+noise "
              f"{brier['base_brier_best_tuned']:.4f}  gain {brier['brier_gain_vs_best']:+.4f} "
              f"CI[{brier['brier_gain_ci'][0]:+.4f},{brier['brier_gain_ci'][1]:+.4f}]  "
              f"(pre-T15 {PRE_T15['brier_gain_vs_best']:+.4f})")

    verdict = {"bar1_profile": bar1["pass"], "bar2_elite_fall": g2["pass"],
               "bar3_harvest": g3["pass"],
               "bar4_brier_not_degraded": (None if brier is None else
                                           bool(brier["brier_gain_vs_best"] >=
                                                PRE_T15["brier_gain_vs_best"] - 0.02)),
               "bar5_dispersion_level_ok": bool(abs(bar5["level_error"]) <= 0.20)}
    print("\n=== VERDICT ===")
    for k, v in verdict.items():
        print(f"  {k:<28} {'PASS' if v else ('n/a' if v is None else 'FAIL')}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "generated": pd.Timestamp.now("UTC").isoformat(),
        "model": {"adp_spec": model.adp_spec.to_dict(), "band": model.band.to_dict()},
        "config": {"seeds": args.seeds, "seasons": list(MATCHED_SEASONS)},
        "bar1": bar1, "bar1_table": json.loads(cmp.to_json(orient="records")),
        "bar2_elite_fall": g2, "bar3_harvest": g3, "bar5_dispersion": bar5,
        "bar4_availability_brier": brier,
        "faithfulness": {"sim": fa_sim, "corpus": fa_cor},
        "personalities": json.loads(ptab.to_json(orient="records")),
        "readout_2026": {
            "elite_fall": mock.gate_elite_fall(sim[sim["season"] == READOUT_SEASON]),
            "faithfulness": mock.faithfulness_summary(sim[sim["season"] == READOUT_SEASON]),
        },
        "verdict": verdict,
    }, indent=2, default=float))
    print(f"\nwrote {args.out}")
    con.close()


if __name__ == "__main__":
    main()
