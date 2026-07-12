"""Phase 11.1 runner — fit + walk-forward score the behavioral opponent model.

    uv run python steps/phase11_opponent_model.py

Builds conditional-logit choice rows from the human Sleeper corpus, fits the full behavioral
model, prints the interpretable coefficients (the behavioral story), then runs leave-one-season-
out walk-forward vs the ADP-only baseline and reports the log-loss / Brier gain with a bootstrap
CI (the 11.1 done-when: beats ADP-noise on held-out picks). Writes a scorecard to analysis/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from fantasy_quant.data.db import connect
from fantasy_quant.draft.availability import availability_brier
from fantasy_quant.draft.opponent_model import (
    ADP_ONLY,
    ALL_FEATURES,
    OpponentModel,
    build_choice_frame,
    walk_forward,
)
from fantasy_quant.draft.personalities import make_opponent_pick_fn, personalities
from fantasy_quant.draft.simulator import simulate_draft

OUT = Path("analysis/phase11_opponent_model.json")


def main() -> None:
    con = connect(read_only=True)
    print("Building choice frame from the human draft corpus ...")
    frame, feats = build_choice_frame(con, board_source="ffc", top_k=40)

    n_groups = frame["group"].nunique()
    n_seasons = frame["season"].nunique()
    # coverage: fraction of picks whose realized choice is inside the candidate set
    chosen_in_set = frame.groupby("group")["chosen"].max().mean()
    print(f"  choice groups (scored picks): {n_groups:,} across {n_seasons} seasons")
    print(f"  candidate rows: {len(frame):,}  |  realized-pick-in-set: {chosen_in_set:.3f}")
    print(f"  picks per season:\n{frame.groupby('season')['group'].nunique().to_string()}")
    activ = {c: float((frame[c] != 0).mean()) for c in ALL_FEATURES}
    print("  feature activation (fraction of candidate rows != 0): "
          + ", ".join(f"{k}={v:.2f}" for k, v in activ.items()))

    # -- full-corpus fit: the interpretable behavioral coefficients -------------------------
    full = OpponentModel(list(ALL_FEATURES), l2=1.0).fit(frame)
    print("\nBehavioral coefficients (full-corpus fit; utility units, larger |β| = stronger):")
    coefs = dict(zip(ALL_FEATURES, full.beta, strict=False))
    for k, v in coefs.items():
        print(f"  {k:10s} {v:+.3f}")

    # -- walk-forward: the done-when ---------------------------------------------------------
    print("\nWalk-forward (leave-one-season-out) — behavioral vs ADP-only baseline ...")
    wf = walk_forward(frame, feats, l2=1.0, baseline_cols=list(ADP_ONLY), n_boot=500)
    ps = pd.DataFrame(wf["per_season"])
    with pd.option_context("display.float_format", lambda x: f"{x:.3f}"):
        print(ps[["season", "n_groups", "base_logloss", "beh_logloss",
                  "base_brier", "beh_brier", "base_top1", "beh_top1"]].to_string(index=False))
    p = wf["pooled"]
    llci, brci = p["logloss_gain_ci"], p["brier_gain_ci"]
    print("\nPOOLED (held-out):")
    print(f"  log-loss   base {p['base_logloss']:.4f} -> beh {p['beh_logloss']:.4f}   "
          f"gain {p['logloss_gain']:+.4f}  CI[{llci[0]:+.4f},{llci[1]:+.4f}]")
    print(f"  brier      base {p['base_brier']:.4f} -> beh {p['beh_brier']:.4f}   "
          f"gain {p['brier_gain']:+.4f}  CI[{brci[0]:+.4f},{brci[1]:+.4f}]")
    verdict = "BEATS ADP (CI excludes 0)" if p["beats_adp"] else "does NOT significantly beat ADP"
    print(f"\n  11.1 done-when: {verdict}")

    # ===== 11.2 — availability distributions: the availability Brier ===========================
    print("\n[11.2] Availability Brier — behavioral flow vs best-tuned ADP+noise "
          "(MC over real windows; ~3-4 min) ...")
    ab = availability_brier(con, full, n_sims=40, contested_k=30,
                            max_drafts_per_season=3, n_boot=400, seed=1)
    print(f"  windows={ab['n_windows']:,} over {ab['n_drafts']} drafts")
    print(f"  behavioral Brier {ab['beh_brier']:.4f}  |  ADP+noise best-tuned "
          f"{ab['base_brier_best_tuned']:.4f} (noise={ab['best_noise']:.0f}; "
          f"default-noise5 {ab['base_brier_default_noise5']:.4f})")
    print(f"  gain vs best-tuned {ab['brier_gain_vs_best']:+.4f}  "
          f"CI[{ab['brier_gain_ci'][0]:+.4f},{ab['brier_gain_ci'][1]:+.4f}]")
    av_verdict = "BEATS best ADP+noise" if ab["beats_best_adp_noise"] else "NOT significant"
    print(f"  11.2 done-when: {av_verdict}")

    # ===== 11.3 — realistic mock: personality-tilted opponents ================================
    print("\n[11.3] Configurable mock opponents (early-round positional mix on a real board) ...")
    board = con.execute(
        "SELECT name, position, team, adp, pos_rank FROM adp_snapshots "
        "WHERE source='ffc' AND season=2022 AND teams=10 "
        "QUALIFY snapshot_date=MAX(snapshot_date) OVER () ORDER BY adp"
    ).df()
    demo = {}
    configs = {"adp_noise (baseline)": None,
               "behavioral": make_opponent_pick_fn(full, personalities()["balanced"]),
               "zero_rb": make_opponent_pick_fn(full, personalities()["zero_rb"]),
               "chalk": make_opponent_pick_fn(full, personalities()["chalk"])}
    for name, opp in configs.items():
        st = simulate_draft(board, n_teams=10, rounds=15, seed=7, opponent_pick_fn=opp)
        first30 = st.pick_log().head(30)
        mix = first30["pos"].value_counts().to_dict()
        demo[name] = {k: int(mix.get(k, 0)) for k in ("RB", "WR", "QB", "TE")}
        print(f"  {name:22s} first-3-rounds: "
              + " ".join(f"{k}={demo[name][k]}" for k in ("RB", "WR", "QB", "TE")))
    print("  (zero_rb should show fewer early RBs than behavioral/baseline — capability check)")
    con.close()

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "n_groups": int(n_groups), "n_seasons": int(n_seasons),
        "chosen_in_candidate_set": float(chosen_in_set),
        "coefficients": {k: float(v) for k, v in coefs.items()},
        "walk_forward": wf,
        "availability_brier": ab,
        "personality_demo_first3rounds": demo,
    }, indent=2, default=float))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
