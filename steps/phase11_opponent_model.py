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
    corpus_funnel,
    walk_forward,
)
from fantasy_quant.draft.personalities import make_opponent_pick_fn, personalities
from fantasy_quant.draft.simulator import simulate_draft

OUT = Path("analysis/phase11_opponent_model.json")

#: Choice-frame sampling budget. The eligible pool is ~1,420 drafts; the full frame would be ~8M
#: candidate rows, which does not fit in this box's memory. 60/season is ~9x the pre-F.6 corpus and
#: leaves the walk-forward comfortably inside RAM. Sampling is per season so no held-out season is
#: lost, and the seed makes the draw reproducible.
DRAFTS_PER_SEASON = 60

#: 11.2 sampling budget. The n_drafts=21 that stood through Session F.5 was THIS number (3), not
#: the size of the corpus — the thinnest result in the repo was a default argument.
BRIER_DRAFTS_PER_SEASON = 28


def main() -> None:
    con = connect(read_only=True)
    print("=== corpus funnel (Session F.6: eligibility is enforced here now) ===")
    funnel = corpus_funnel(con)
    print(f"  human drafts held                      : {funnel['human_drafts']:,}")
    print(f"  ... eligible (complete/snake/redraft/window): {funnel['eligible']:,}")
    print(f"  ... with a consensus board             : {funnel['with_board']:,}  "
          f"{funnel['by_board_source']}")
    print(f"\nBuilding choice frame (sampling {DRAFTS_PER_SEASON}/season — an explicit budget, "
          f"the eligible pool is larger) ...")
    frame, feats = build_choice_frame(con, top_k=40,
                                      max_drafts_per_season=DRAFTS_PER_SEASON, seed=11)

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
                            max_drafts_per_season=BRIER_DRAFTS_PER_SEASON, n_boot=400, seed=1)
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
    # `scoring` is not optional: without it this unions the ppr / half-ppr / standard boards and
    # the demo drafts from a board with every player on it three times (the F.5 lesson, again).
    board = con.execute(
        "SELECT name, position, team, adp, pos_rank FROM adp_snapshots "
        "WHERE source='ffc' AND season=2022 AND teams=10 AND scoring='ppr' "
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
        "corpus_funnel": funnel,
        "sampling": {"drafts_per_season": DRAFTS_PER_SEASON,
                     "brier_drafts_per_season": BRIER_DRAFTS_PER_SEASON, "seed": 11},
        "board_source_split": {str(k): int(v) for k, v in
                               frame.groupby("board_source", observed=True)["draft_id"]
                               .nunique().items()},
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
