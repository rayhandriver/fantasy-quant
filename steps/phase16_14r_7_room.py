"""16.14R step 7 — room composition, and the full re-measure of everything 16.14R touched.

    uv run python steps/phase16_14r_7_room.py
    uv run python steps/phase16_14r_7_room.py --seeds 100 --mock-csv analysis/mock_16_14R_picks.csv

Done when: the shipped room is :data:`~fantasy_quant.draft.personalities.REALISTIC_ROOM`, all five
T15 bars are re-measured on it, the seat-faithfulness population is reported, and the 16.10 done-bar
runs at **15** rounds (closing T16).

★ **Composition is a lever, not a footnote — and the 2x5 mock proved it with no model change at
all.** Swapping ``homer`` + ``upside_chaser`` for ``value_hawk`` + a second ``safe_floor`` moved
T15's open faithfulness gap from median ``pool_rank`` **10.40 -> 8.59** (corpus 7.62) and the
moderate band **13.5 % -> 24.3 %** (corpus 54.3 %). Some of what read as a model defect was a
choice about who is in the room.

★ **Why ``autopilot`` drops from two seats to one.** Over 60 seeded drafts it finished **1.69 / 10**
and won **48.3 %** — while being **0.2 %** of real seats. That is not skill: mean drift **−19.8
picks**, i.e. it was handed the value the reaching seats spilled. Two of ten seats manufactured both
an unrealistic room and the spill that fed it.

⚠ **The measurement path is the shipped one**, deliberately: every number below comes from the same
``mock.*`` functions T15's own verification uses, over a panel emitted by ``sim_drift_panel`` in the
corpus's own frame. *If the two sides of a comparison are computed by different code, the comparison
measures the code.*
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import pandas as pd

from fantasy_quant.adp import boards
from fantasy_quant.adp.drift_panel import build_drift_panel
from fantasy_quant.draft import mock, optimizer
from fantasy_quant.draft.config import DraftConfig
from fantasy_quant.draft.personalities import REALISTIC_ROOM

DB = Path("data/fantasy_quant.duckdb")
OUT = Path("analysis/phase16_14r_room.json")
CACHE = Path("analysis/cache")

MATCHED_SEASONS: tuple[int, ...] = (2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024)
READOUT_SEASON: int = 2026

#: T15's committed numbers, so the re-measure is a before/after rather than a fresh assertion.
T15_SHIPPED = {"round1_sim_mean": 4.36, "profile_distance": 0.222, "elite_p95": 17.0,
               "elite_past10": 0.285, "sd_drift_sim": 1.977, "sd_drift_corpus": 1.690,
               "median_pool_rank": 10.40, "moderate_share": 0.135, "chalk_share": 0.196}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=60)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--room-seed", type=int, default=17)
    ap.add_argument("--mix", type=str, default="realistic", choices=("realistic", "t15"),
                    help="which room to measure — 't15' is DEFAULT_FULL_ROOM, for attribution")
    ap.add_argument("--seasons", type=int, nargs="*", default=None,
                    help="restrict the matched seasons (attribution runs use a subset)")
    ap.add_argument("--mock-csv", type=Path, default=Path("analysis/mock_16_14R_picks.csv"))
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    model = mock.load_opponent_model()
    mix = REALISTIC_ROOM if args.mix == "realistic" else mock.DEFAULT_FULL_ROOM
    room = mock.full_room(mix, n_teams=10, seed=args.room_seed)
    print(f"room: {[p.name for p in room]}")

    seasons = tuple(args.seasons) if args.seasons else MATCHED_SEASONS
    corpus = build_drift_panel(con)
    ffc = corpus[corpus["board_source"] == boards.FFC]
    corpus_matched = ffc[ffc["season"].isin(seasons)]

    sim_frames = []
    for season in (*seasons, READOUT_SEASON):
        board, src = mock.room_board(con, season, cache_dir=CACHE)
        if board.empty:
            continue
        # the value hawk needs the Phase-9 machinery in its seat; every other seat ignores it
        config = DraftConfig()
        vi = optimizer.assemble_value(con, season, config)
        attached = optimizer.attach_value(board, vi)
        risk = optimizer.build_risk_model(attached, vi, optimizer.assemble_correlation(con, season),
                                          lam=config.risk_lambda)
        panel = mock.batch_drift_panel(attached, room, model, season=season,
                                       seeds=range(args.seeds), n_teams=10, rounds=args.rounds,
                                       board_source=src, risk=risk)
        sim_frames.append(panel)
        print(f"  {season}: {args.seeds} drafts -> {len(panel):,} boarded picks", flush=True)
        if season == READOUT_SEASON and args.mock_csv:
            st = mock.simulate_room_draft(attached, room, model, n_teams=10, rounds=args.rounds,
                                          seed=0, risk=risk)
            log = st.pick_log().copy()
            log["seat_personality"] = log["team"].map({i: p.name for i, p in enumerate(room)})
            log["reach_picks"] = (log["adp"] - log["overall_pick"]).round(1)
            args.mock_csv.parent.mkdir(parents=True, exist_ok=True)
            log.to_csv(args.mock_csv, index=False)
            print(f"  wrote a full {args.rounds}-round mock to {args.mock_csv}")

    sim = pd.concat(sim_frames, ignore_index=True)
    sim_matched = sim[sim["season"].isin(seasons)]

    # ===== the five T15 bars, on the shipped measurement path ==================================
    cmp = mock.compare_profiles(sim_matched, corpus_matched)
    dist = mock.profile_distance(sim_matched, corpus_matched)
    print("\n=== BAR 1 — reach profile, 10-team ADP picks ===")
    print(cmp.round(2).to_string(index=False))
    r1 = cmp[cmp["round"] == 1].iloc[0]
    bar1 = {"pass": bool(r1["sim_mean"] <= 5.0 and 0.5 <= r1["mean_ratio"] <= 2.0),
            "round1_sim_mean": float(r1["sim_mean"]), "profile_distance": dist,
            "t15_round1_sim_mean": T15_SHIPPED["round1_sim_mean"],
            "t15_profile_distance": T15_SHIPPED["profile_distance"]}
    print(f"  distance {dist:.4f} (T15 shipped {T15_SHIPPED['profile_distance']:.4f}); "
          f"round-1 mean {r1['sim_mean']:.2f} (T15 {T15_SHIPPED['round1_sim_mean']:.2f})")

    g2 = mock.gate_elite_fall(sim_matched)
    g3 = mock.gate_autopilot_surplus(sim_matched, corpus_matched)
    print("\n=== BAR 2 — elite fall ===")
    print(f"  p95 {g2['p95_slot']:.1f} (max {g2['p95_max']}, T15 {T15_SHIPPED['elite_p95']:.1f}) · "
          f"past pick 10 {g2['share_past_10']:.1%} (max {g2['past10_max']:.0%}, "
          f"T15 {T15_SHIPPED['elite_past10']:.1%}) -> {'PASS' if g2['pass'] else 'FAIL'}")
    print("\n=== BAR 3 — harvest at matched faithfulness ===")
    print(f"  worst excess {g3['worst_excess_sds']:+.2f} sds (tol {g3['tol_sds']}) -> "
          f"{'PASS' if g3['pass'] else 'FAIL'}")

    sd_sim = float(sim_matched.groupby("draft_id")["drift_centered"].std().mean())
    sd_cor = float(corpus_matched.groupby("draft_id")["drift_centered"].std().mean())
    bar5 = {"sd_drift_sim": sd_sim, "sd_drift_corpus": sd_cor,
            "level_error": (sd_sim - sd_cor) / sd_cor,
            "t15_sim": T15_SHIPPED["sd_drift_sim"]}
    bar5["pass"] = bool(abs(bar5["level_error"]) <= 0.20)
    print(f"\n=== BAR 5 — 16.9 dispersion: sim {sd_sim:.3f} vs corpus {sd_cor:.3f} "
          f"({bar5['level_error']:+.1%}; T15 shipped {T15_SHIPPED['sd_drift_sim']:.3f}) -> "
          f"{'PASS' if bar5['pass'] else 'FAIL'}")

    # ===== the seat-faithfulness population (T15's open item) ==================================
    fa_sim = mock.faithfulness_summary(sim_matched)
    fa_cor = mock.faithfulness_summary(corpus_matched)
    print("\n=== THE ROOM'S POPULATION ===")
    for lab, f in (("corpus", fa_cor), ("sim (16.14R)", fa_sim)):
        print(f"  {lab:<14} median pool_rank {f['median_pool_rank']:5.2f}  "
              f"moderate(2-8) {f['moderate_share']:6.1%}  chalk(<2) {f['chalk_share']:6.1%}")
    print(f"  {'sim (T15)':<14} median pool_rank {T15_SHIPPED['median_pool_rank']:5.2f}  "
          f"moderate(2-8) {T15_SHIPPED['moderate_share']:6.1%}  "
          f"chalk(<2) {T15_SHIPPED['chalk_share']:6.1%}")

    print("\n=== PER-PERSONALITY (sim) ===")
    ptab = mock.personality_table(sim_matched)
    print(ptab.round(2).to_string(index=False))

    verdict = {"bar1_profile": bar1["pass"], "bar2_elite_fall": g2["pass"],
               "bar3_harvest": g3["pass"], "bar5_dispersion": bar5["pass"],
               "faithfulness_improved":
                   bool(fa_sim["median_pool_rank"] < T15_SHIPPED["median_pool_rank"])}
    print("\n=== VERDICT (bar 4 = the 11.2 Brier, run separately) ===")
    for k, v in verdict.items():
        print(f"  {k:<26} {'PASS' if v else 'FAIL'}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "generated": pd.Timestamp.now("UTC").isoformat(),
        "room": [p.name for p in room],
        "config": {"seeds": args.seeds, "rounds": args.rounds, "seasons": list(seasons),
                   "mix": args.mix},
        "bar1": bar1, "bar1_table": json.loads(cmp.to_json(orient="records")),
        "bar2_elite_fall": g2, "bar3_harvest": g3, "bar5_dispersion": bar5,
        "faithfulness": {"sim": fa_sim, "corpus": fa_cor, "t15_sim": T15_SHIPPED},
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
