"""16.14R step 6 — build ``value_hawk`` properly: a bounded-window portfolio-CE argmax.

    uv run python steps/phase16_14r_6_value_hawk.py
    uv run python steps/phase16_14r_6_value_hawk.py --seeds 30 --windows 1.0 1.15 1.25

Done when: the seat drafts by **marginal portfolio CE** on the step-3 board inside a measured reach
window, the window is **selected by the pre-registered rule** (max CE surplus subject to realized
reach p95 <= the corpus p95), and its projection ranking is reported as **descriptive**.

★ **Open decision #1 is settled here, and the argument is measured rather than aesthetic.** A
``signal_weights`` value hawk cannot work: ``signal_bonus`` z-scores *within position*, and within
position ``corr(vbd, adp)`` is **−0.955 RB / −0.933 WR / −0.907 TE / −0.859 QB**, so ``pos_z(vbd)``
deletes the only content ``vbd`` carries that ADP does not — the cross-position comparison. What
survives is ADP with a sign flip. Built that way in the 2x5 mock the seat gained +0.065 vbd-z over
``balanced`` and finished **5.5 / 10**, behind ``safe_floor``. The objective must be roster-level,
so it is the **Phase-9 greedy in an opponent seat**.

★ **The window is measured, not chosen** (user decision, 2026-07-27): sweep
``{1.00, 1.15, 1.25}`` x the realized human p95 and keep the largest CE surplus whose realized reach
p95 still clears the corpus. Stated as a multiple of what humans actually do, the constraint is a
real outcome rather than an identity — a seat allowed 1.25x may still land under the ceiling.

⚠⚠ **THE EVALUATION TRAP, and it is sharpest for this seat.** The value hawk maximizes our board,
so scored *on our board* it wins by construction — that is arithmetic, not evidence. The lockbox
already settled the underlying question: personalization is **noise-dominated on realized points**
(every archetype-cost CI contained 0). So the CE/projection numbers below are **descriptive** —
they say what this manager is, not that he is right — and the realized-points column is the only
one an evaluative claim may cite.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from fantasy_quant.draft import mock, optimizer
from fantasy_quant.draft.config import DraftConfig
from fantasy_quant.draft.personalities import (
    CORPUS_REACH_P95,
    REALISTIC_ROOM,
    personalities,
    value_hawk_budget,
)
from fantasy_quant.draft.simulator import board_player_key

DB = Path("data/fantasy_quant.duckdb")
OUT = Path("analysis/phase16_14r_value_hawk.json")
CACHE = Path("analysis/cache")

#: The window multiples swept (user decision 2026-07-27), as multiples of the realized human p95.
WINDOWS: tuple[float, ...] = (1.0, 1.15, 1.25)


def _seat_metrics(state, board_idx: pd.DataFrame, risk) -> pd.DataFrame:
    """Per-seat descriptive value of a finished draft: portfolio CE proxy + reach behaviour."""
    log = state.pick_log()
    rows = []
    for t in range(state.n_teams):
        r = state.roster(t)
        keys = list(r["player_key"])
        bv = np.array([risk.bv.get(k, np.nan) for k in keys], float)
        mine = log[log["team"] == t]
        reach = (mine["adp"] - mine["overall_pick"]).to_numpy(float)
        rows.append({"team": t,
                     "base_value": float(np.nansum(bv)),
                     "n_valued": int(np.isfinite(bv).sum()),
                     "mean_reach": float(np.mean(reach)),
                     "p95_reach": float(np.quantile(reach[reach > 0], 0.95))
                     if (reach > 0).any() else 0.0})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--windows", type=float, nargs="*", default=list(WINDOWS))
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    model = mock.load_opponent_model()
    board, src = mock.room_board(con, args.season, cache_dir=CACHE)

    # the Phase-9 machinery, unchanged — this seat is that greedy, in somebody else's chair
    config = DraftConfig()
    value_index = optimizer.assemble_value(con, args.season, config)
    attached = optimizer.attach_value(board, value_index)
    corr = optimizer.assemble_correlation(con, args.season)
    risk = optimizer.build_risk_model(attached, value_index, corr, lam=config.risk_lambda)
    print(f"{args.season} board {len(board)} rows ({src}); value index {len(value_index)} rows, "
          f"lam={config.risk_lambda}")

    key = board_player_key(board).astype(str)
    board_idx = board.assign(_key=key)

    results = []
    for w in args.windows:
        lib_hawk = replace(personalities()["value_hawk"], reach_budget=value_hawk_budget(w))
        room = tuple(lib_hawk if p.name == "value_hawk" else p
                     for p in mock.full_room(REALISTIC_ROOM, n_teams=10, seed=17))
        seat = [i for i, p in enumerate(room) if p.name == "value_hawk"][0]
        per_seed = []
        for s in range(args.seeds):
            st = mock.simulate_room_draft(attached, room, model, n_teams=10,
                                          rounds=args.rounds, seed=s, risk=risk)
            m = _seat_metrics(st, board_idx, risk)
            others = m[m["team"] != seat]["base_value"].mean()
            per_seed.append({"surplus": m.loc[seat, "base_value"] - others,
                             "p95_reach": m.loc[seat, "p95_reach"],
                             "mean_reach": m.loc[seat, "mean_reach"]})
        d = pd.DataFrame(per_seed)
        # the seat's realized reach p95 against the round-pooled corpus p95
        ceiling = float(np.mean(CORPUS_REACH_P95[:args.rounds]))
        row = {"window_mult": w,
               "ce_surplus": round(float(d["surplus"].mean()), 2),
               "ce_surplus_se": round(float(d["surplus"].std(ddof=1) / np.sqrt(len(d))), 2),
               "p95_reach": round(float(d["p95_reach"].mean()), 2),
               "mean_reach": round(float(d["mean_reach"].mean()), 2),
               "corpus_ceiling": round(ceiling, 2),
               "within_ceiling": bool(d["p95_reach"].mean() <= ceiling)}
        results.append(row)
        print(f"  window {w:.2f}x -> CE surplus {row['ce_surplus']:+.1f} "
              f"(se {row['ce_surplus_se']:.1f}), realized reach p95 {row['p95_reach']:.1f} "
              f"vs ceiling {ceiling:.1f} -> {'ok' if row['within_ceiling'] else 'OVER'}")

    tab = pd.DataFrame(results)
    print("\n=== the sweep (descriptive — see the module docstring's evaluation trap) ===")
    print(tab.to_string(index=False))

    eligible = tab[tab["within_ceiling"]]
    chosen = resolved = None
    if not eligible.empty:
        best = eligible.loc[eligible["ce_surplus"].idxmax()]
        tightest = eligible.loc[eligible["window_mult"].idxmin()]
        # ★ Is the argmax real, or is it the noise draw? The same question T15 asked of the title
        # objective at 60 sims, and it has to be asked BEFORE reading the winner. Two standard
        # errors of separation between the best window and the tightest eligible one, or the sweep
        # has not resolved anything and the tighter constraint wins on principle — an unresolved
        # choice should not buy itself a wider licence to reach.
        gap = float(best["ce_surplus"] - tightest["ce_surplus"])
        pooled_se = float(np.hypot(best["ce_surplus_se"], tightest["ce_surplus_se"]))
        resolved = bool(gap > 2 * pooled_se)
        chosen = float(best["window_mult"] if resolved else tightest["window_mult"])
        print(f"\n  argmax {best['window_mult']:.2f}x beats the tightest eligible "
              f"{tightest['window_mult']:.2f}x by {gap:+.1f} CE against a pooled se of "
              f"{pooled_se:.1f} -> {'RESOLVED' if resolved else 'NOT RESOLVED'}")
    print(f"\nSELECTED window_mult = {chosen}  "
          f"({'max CE surplus' if resolved else 'sweep unresolved -> tightest eligible window'}, "
          f"s.t. realized reach p95 <= corpus p95)")

    # -- the step-3 context must MOVE something ("an inert thing still passes") -------------------
    print("\n=== ablation — the step-3 context weights against themselves off ===")
    ctx_rows, rosters = {}, {}
    for lab, p in (("with context", personalities()["value_hawk"]),
                   ("context OFF", replace(personalities()["value_hawk"], context_weights={}))):
        room = tuple(p if q.name == "value_hawk" else q
                     for q in mock.full_room(REALISTIC_ROOM, n_teams=10, seed=17))
        seat = [i for i, q in enumerate(room) if q.name == "value_hawk"][0]
        vals, picks = [], []
        for s in range(min(args.seeds, 12)):
            st = mock.simulate_room_draft(attached, room, model, n_teams=10,
                                          rounds=args.rounds, seed=s, risk=risk)
            r = st.roster(seat)
            picks.append(set(r["player_key"]))
            vals.append({c: float(pd.to_numeric(r[c], errors="coerce").mean())
                         for c in ("role_share", "role_delta", "td_regression") if c in r.columns})
        ctx_rows[lab] = pd.DataFrame(vals).mean().round(4).to_dict()
        rosters[lab] = picks
    overlap = float(np.mean([len(a & b) / len(a | b) for a, b in
                             zip(rosters["with context"], rosters["context OFF"], strict=True)]))
    print(pd.DataFrame(ctx_rows).T.to_string())
    print(f"  roster overlap with vs without: {overlap:.1%} "
          f"(100 % would mean the weights are inert)")
    ctx_moves = bool(overlap < 0.95
                     and ctx_rows["with context"].get("role_share", 0)
                     > ctx_rows["context OFF"].get("role_share", 0)
                     and ctx_rows["with context"].get("td_regression", 0)
                     < ctx_rows["context OFF"].get("td_regression", 0))
    print(f"  -> context weights move the roster in the intended direction: {ctx_moves}")

    verdict = {"sweep_resolved": bool(resolved),
               "context_weights_move_the_roster": ctx_moves,
               "objective_is_portfolio_ce":
               personalities()["value_hawk"].objective == "portfolio_ce",
               "window_selected": chosen is not None,
               "reported_as_descriptive": True}
    print("\n=== VERDICT ===")
    for k, v in verdict.items():
        print(f"  {k:<28} {'PASS' if v else 'FAIL'}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "generated": pd.Timestamp.now("UTC").isoformat(),
        "season": args.season, "board_source": src,
        "config": {"seeds": args.seeds, "rounds": args.rounds, "windows": args.windows,
                   "lam": config.risk_lambda},
        "sweep": results, "selected_window_mult": chosen, "sweep_resolved": resolved,
        "context_ablation": {"signals": ctx_rows, "roster_overlap": round(overlap, 4)},
        "context_weights": personalities()["value_hawk"].context_weights,
        "note": "CE/projection numbers are DESCRIPTIVE: this seat maximizes our own board.",
        "verdict": verdict,
    }, indent=2, default=float))
    print(f"\nwrote {args.out}")
    con.close()


if __name__ == "__main__":
    main()
