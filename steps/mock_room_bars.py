"""The mock room's full bar sheet — the before/after harness for T23 / T25 / T24.

    uv run python steps/mock_room_bars.py --label baseline
    uv run python steps/mock_room_bars.py --label t23_t25
    uv run python steps/mock_room_bars.py --label t24 --seeds 60

Writes ``analysis/mock_room_bars_<label>.json`` and prints every bar side by side with the corpus.
Re-run it after each fix: the point of a labelled artifact is that the *after* column is produced by
the same code as the *before* one, which is the only way a claim like "T23 moved no T15 bar" is
worth anything (T20's register entry says exactly this and says **verify, do not assume**).

★ **What this harness adds over ``steps/phase16_14r_7_room.py``, and why.** Both run the shipped
room on the shipped measurement path. This one additionally runs the two measurements that were
missing on 2026-07-28 — the session where a human read the picks and found three defects every
green gate had passed:

  ``landing``   the **signed companion** to bar #1. Round-1 mean |reach| passes at 2.91 sim vs 2.87
                corpus while the consensus #2 lands at a median pick of 4 and clears pick 4 42 % of
                the time against a realized 12 %, because a reach and a fall have the same absolute
                value and cancel inside a mean. **T24.**
  ``legality``  the roster guarantee stated over the **whole** starting lineup rather than over the
                K and DST that motivated T20 — the filter that guards those two skips TE, and 12.2 %
                of seats finished unable to field a lineup. **T23.**

and it reports per-personality behaviour as ``pool_rank`` **by round bucket** (**T25**'s reporting
rule) rather than as a 15-round mean reach, which is dominated by late-board ADP noise and by when a
seat takes its kicker.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import duckdb
import pandas as pd

from fantasy_quant.adp import boards
from fantasy_quant.adp.drift_panel import build_drift_panel
from fantasy_quant.draft import mock, optimizer
from fantasy_quant.draft.config import DraftConfig
from fantasy_quant.draft.personalities import PRIVATE_KAPPA, REALISTIC_ROOM

DB = Path("data/fantasy_quant.duckdb")
CACHE = Path("analysis/cache")
OUT_DIR = Path("analysis")

#: The seasons the sim and the corpus are compared on — 16.14R step 7's set, unchanged, so every
#: number here is a before/after against a committed one. The 2026 board is simulated too but scored
#: separately: it has no realized counterpart, so it is an **eyeball readout, never a gate**.
MATCHED_SEASONS: tuple[int, ...] = (2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024)
READOUT_SEASON: int = 2026

#: The committed numbers this harness is a before/after against (16.14R step 7, `analysis/
#: phase16_14r_room.json`). Bar 2 is the one deliberately left failing at +0.12 se.
SHIPPED = {"round1_sim_mean": 3.70, "profile_distance": 0.1156, "elite_p95": 19.0,
           "elite_past10": 0.3007, "median_pool_rank": 9.38, "moderate_share": 0.278,
           "chalk_share": 0.106}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--label", required=True, help="artifact label, e.g. baseline / t23_t25 / t24")
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--room-seed", type=int, default=17)
    ap.add_argument("--seasons", type=int, nargs="*", default=None)
    ap.add_argument("--no-readout", action="store_true", help="skip the 2026 eyeball season")
    ap.add_argument("--kappa", type=float, default=None,
                    help="T24 private-board scale (default: the shipped PRIVATE_KAPPA)")
    ap.add_argument("--width-base", type=float, default=None,
                    help="T24 width narrowing: WidthCurve.base (default: the model's own curve)")
    ap.add_argument("--shuffle-room", action="store_true",
                    help="re-seat the room every seed (marginalizes seating; see the note below)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = args.out or OUT_DIR / f"mock_room_bars_{args.label}.json"

    con = duckdb.connect(str(DB), read_only=True)
    model = mock.load_opponent_model()
    if args.width_base is not None:
        model.width_curve = replace(model.width_curve, base=float(args.width_base))
    kw = {} if args.kappa is None else {"kappa": float(args.kappa)}
    room = mock.full_room(REALISTIC_ROOM, n_teams=10, seed=args.room_seed)
    seasons = tuple(args.seasons) if args.seasons else MATCHED_SEASONS
    # ⚠ The room's κ lives on the **model** (T24 ships it beside the width curve); `PRIVATE_KAPPA`
    # is only the no-op fallback for a hand-built model. Reading the constant here would label a
    # κ=2.0 run as κ=0 in its own artifact — the mislabelled-artifact failure this repo keeps
    # finding (`_refresh_board`'s hardcoded `scoring="ppr"`, Session F.5).
    kappa = (float(getattr(model, "private_kappa", PRIVATE_KAPPA)) if args.kappa is None
             else float(args.kappa))
    print(f"label={args.label} · room {[p.name for p in room]}")
    print(f"width curve {model.width_curve} · kappa {kappa} · {args.seeds} drafts x 10 seats x "
          f"{len(seasons)} seasons")

    corpus = build_drift_panel(con)
    ffc = corpus[corpus["board_source"] == boards.FFC]
    corpus_matched = ffc[ffc["season"].isin(seasons)]

    sim_frames, logs, supply = [], [], {}
    run_seasons = seasons if args.no_readout else (*seasons, READOUT_SEASON)
    for season in run_seasons:
        board, src = mock.room_board(con, season, cache_dir=CACHE)
        if board.empty:
            print(f"  {season}: no board, skipped")
            continue
        supply[season] = mock.board_supply(board)
        config = DraftConfig()
        vi = optimizer.assemble_value(con, season, config)
        attached = optimizer.attach_value(board, vi)
        risk = optimizer.build_risk_model(attached, vi, optimizer.assemble_correlation(con, season),
                                          lam=config.risk_lambda)
        # ★ `--shuffle-room` re-draws the seating for every seed instead of holding one arrangement
        # for the whole batch. T24's sweep found why it matters: with a fixed arrangement the
        # **round-1 half-split** measures *where the reachy seats happen to sit*, not the width law
        # — at room seed 17 the sim "rises" 1.26 across round 1 and at room seed 18 the same code
        # *falls* to 0.82. The corpus averages over 1,144 independently-seated drafts, so the sim
        # has to marginalize seating too or the two sides are not the same statistic.
        # Default OFF: the committed baseline/t23/t25 sheets are fixed-room, and an after column
        # produced by different code than its before column is the thing this harness exists to
        # prevent. Run the pair.
        if args.shuffle_room:
            def seating(s: int):
                return mock.full_room(REALISTIC_ROOM, n_teams=10, seed=args.room_seed + 1000 * s)
            per = [mock.batch_drafts(
                attached, seating(s), model, season=season, seeds=[s], n_teams=10,
                rounds=args.rounds, board_source=src, risk=risk, **kw)
                for s in range(args.seeds)]
            panel = pd.concat([p for p, _ in per], ignore_index=True)
            log = pd.concat([lg for _, lg in per], ignore_index=True)
        else:
            panel, log = mock.batch_drafts(attached, room, model, season=season,
                                           seeds=range(args.seeds), n_teams=10, rounds=args.rounds,
                                           board_source=src, risk=risk, **kw)
        sim_frames.append(panel)
        logs.append(log)
        print(f"  {season}: {args.seeds} drafts -> {len(panel):,} boarded picks", flush=True)

    sim = pd.concat(sim_frames, ignore_index=True)
    log = pd.concat(logs, ignore_index=True)
    sim_matched = sim[sim["season"].isin(seasons)]

    # ===== T15's five bars, unchanged ============================================================
    cmp = mock.compare_profiles(sim_matched, corpus_matched)
    dist = mock.profile_distance(sim_matched, corpus_matched)
    r1 = cmp[cmp["round"] == 1].iloc[0]
    bar1 = {"pass": bool(r1["sim_mean"] <= 5.0 and 0.5 <= r1["mean_ratio"] <= 2.0),
            "round1_sim_mean": float(r1["sim_mean"]),
            "round1_corpus_mean": float(r1["corpus_mean"]),
            "profile_distance": dist, "shipped_round1": SHIPPED["round1_sim_mean"],
            "shipped_distance": SHIPPED["profile_distance"]}
    g2 = mock.gate_elite_fall(sim_matched)
    g3 = mock.gate_autopilot_surplus(sim_matched, corpus_matched)
    sd_sim = float(sim_matched.groupby("draft_id")["drift_centered"].std().mean())
    sd_cor = float(corpus_matched.groupby("draft_id")["drift_centered"].std().mean())
    bar5 = {"sd_drift_sim": sd_sim, "sd_drift_corpus": sd_cor,
            "level_error": (sd_sim - sd_cor) / sd_cor}
    bar5["pass"] = bool(abs(bar5["level_error"]) <= 0.20)

    print("\n=== T15 BARS ===")
    print(f"  1 profile  distance {dist:.4f} (shipped {SHIPPED['profile_distance']:.4f}) · "
          f"round-1 {r1['sim_mean']:.2f} vs corpus {r1['corpus_mean']:.2f} "
          f"-> {'PASS' if bar1['pass'] else 'FAIL'}")
    print(f"  2 elite    p95 {g2['p95_slot']:.1f} (max {g2['p95_max']}) · past-10 "
          f"{g2['share_past_10']:.2%} (max {g2['past10_max']:.0%}) "
          f"-> {'PASS' if g2['pass'] else 'FAIL'}")
    print(f"  3 harvest  worst excess {g3['worst_excess_sds']:+.2f} sds "
          f"-> {'PASS' if g3['pass'] else 'FAIL'}")
    print(f"  5 disp     sim {sd_sim:.3f} vs corpus {sd_cor:.3f} ({bar5['level_error']:+.1%}) "
          f"-> {'PASS' if bar5['pass'] else 'FAIL'}")

    # ===== T24 — the signed companion ============================================================
    land_sim = mock.landing_profile(sim_matched)
    land_cor = mock.landing_profile(corpus_matched)
    gl = mock.gate_elite_landing(sim_matched, corpus_matched)
    print("\n=== T24 — LANDING SPOTS (10-team picks), the signed companion to bar 1 ===")
    print("  corpus:")
    print("    " + land_cor.round(2).to_string(index=False).replace("\n", "\n    "))
    print("  sim:")
    print("    " + land_sim.round(2).to_string(index=False).replace("\n", "\n    "))
    print(f"  gate: top band past pick {int(mock.LANDING_GATE_PAST)} — sim {gl['sim_share']:.1%} "
          f"vs corpus {gl['corpus_share']:.1%} (+{gl['margin']:.0%} allowed) · median slot "
          f"{gl['sim_median_slot']:.1f} vs {gl['corpus_median_slot']:.1f} "
          f"-> {'PASS' if gl['pass'] else 'FAIL'}")
    s1, c1 = mock.round1_split(sim_matched), mock.round1_split(corpus_matched)
    print("  round-1 halves (mean |drift|, corpus RISES — a flat sim is the defect):")
    for lab, t in (("corpus", c1), ("sim", s1)):
        vals = "  ".join(f"{r.half} {r.mean_abs:.2f}" for r in t.itertuples())
        print(f"    {lab:<7} {vals}")

    # ===== T23 — roster legality over the whole lineup ===========================================
    leg = mock.roster_legality(log, supply=supply)
    print("\n=== T23 — ROSTER LEGALITY (whole starting lineup) ===")
    print(f"  illegal {leg['n_illegal']} / {leg['n_seats']} ({leg['share_illegal']:.1%})"
          f" · AVOIDABLE {leg.get('share_avoidable', float('nan')):.1%}")
    print("  unfilled by position: " + "  ".join(
        f"{p} {v:.1%}" for p, v in leg["by_position"].items() if v))
    if "avoidable_by_position" in leg:
        print("  of which the board could have supplied: " + "  ".join(
            f"{p} {v:.1%}" for p, v in leg["avoidable_by_position"].items() if v))
    if leg["by_personality"]:
        print("  worst seats: " + "  ".join(
            f"{k} {v:.1%}" for k, v in list(leg["by_personality"].items())[:4] if v))

    # ===== T25 — seat behaviour, pool_rank by bucket ==============================================
    buckets = mock.personality_buckets(sim_matched)
    print("\n=== T25 — pool_rank BY ROUND BUCKET (1 = best available; lead with this) ===")
    print("  " + buckets.round(2).to_string().replace("\n", "\n  "))

    fa_sim = mock.faithfulness_summary(sim_matched)
    fa_cor = mock.faithfulness_summary(corpus_matched)
    print("\n=== THE ROOM'S POPULATION ===")
    for lab, f in (("corpus", fa_cor), ("sim", fa_sim)):
        print(f"  {lab:<8} median pool_rank {f['median_pool_rank']:5.2f}  "
              f"moderate(2-8) {f['moderate_share']:6.1%}  chalk(<2) {f['chalk_share']:6.1%}")

    readout = {}
    if not args.no_readout and (sim["season"] == READOUT_SEASON).any():
        r26 = sim[sim["season"] == READOUT_SEASON]
        players = mock.landing_by_player(r26, top_n=10)
        print(f"\n=== {READOUT_SEASON} EYEBALL (no realized counterpart — never a gate) ===")
        print("  " + players.round(2).to_string(index=False).replace("\n", "\n  "))
        r26_split = mock.round1_split(r26)
        print("  round-1 halves (2026): " + "  ".join(
            f"{r.half} {r.mean_abs:.2f}" for r in r26_split.itertuples()))
        readout = {"elite_fall": mock.gate_elite_fall(r26),
                   "landing": json.loads(mock.landing_profile(r26).to_json(orient="records")),
                   "round1_split": json.loads(r26_split.to_json(orient="records")),
                   "by_player": json.loads(players.to_json(orient="records")),
                   "legality": mock.roster_legality(
                       log[log["season"] == READOUT_SEASON], supply=supply)}

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated": pd.Timestamp.now("UTC").isoformat(),
        "label": args.label,
        "room": [p.name for p in room],
        "config": {"seeds": args.seeds, "rounds": args.rounds, "seasons": list(seasons),
                   "room_seed": args.room_seed, "width_curve": model.width_curve.to_dict(),
                   "kappa": kappa, "shuffle_room": bool(args.shuffle_room)},
        "bar1": bar1, "bar1_table": json.loads(cmp.to_json(orient="records")),
        "bar2_elite_fall": g2, "bar3_harvest": g3, "bar5_dispersion": bar5,
        "landing": {"sim": json.loads(land_sim.to_json(orient="records")),
                    "corpus": json.loads(land_cor.to_json(orient="records")),
                    "gate": gl,
                    "round1_split": {"sim": json.loads(s1.to_json(orient="records")),
                                     "corpus": json.loads(c1.to_json(orient="records"))}},
        "legality": leg,
        "personality_buckets": json.loads(buckets.to_json(orient="index")),
        "faithfulness": {"sim": fa_sim, "corpus": fa_cor, "shipped": SHIPPED},
        "readout_2026": readout,
    }, indent=2, default=float))
    print(f"\nwrote {out}")
    con.close()


if __name__ == "__main__":
    main()
