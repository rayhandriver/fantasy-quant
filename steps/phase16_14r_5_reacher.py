"""16.14R step 5 — the ``reacher`` gets a direction, then a budget.

    uv run python steps/phase16_14r_5_reacher.py
    uv run python steps/phase16_14r_5_reacher.py --seeds 40

Done when:

1. the reacher's **max reach <= 2x balanced's at every round** (16.14R's own done-when), and
2. its per-round deviation stays under the **corpus p95** — a hard ceiling read off 1,144 realized
   human drafts, not chosen here.

★ **Direction is the headline, not the cap.** Before this step the seat was literally
``Personality("reacher", temperature=2.2, width_mult=WIDTH_REACHER)`` — no ``signal_weights`` at
all. Every "nonsensical" reach the user objected to was a hot softmax over a widening band with no
opinion attached, so the ablation below reports what the *direction* buys separately from what the
*budget* costs. A budget over directed reaching is a different object from a budget over noise.

★ **Bar 2 is judgement-free by construction**: the ceiling is the realized human p95 per round, so
"is this reacher possible?" is answered by drafts that happened rather than by an opinion about how
reachy is too reachy. Same design as T15's elite-fall gate, and for the same reason — an aggregate
metric cannot see an impossible event.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from fantasy_quant.adp import boards
from fantasy_quant.adp.drift_panel import build_drift_panel
from fantasy_quant.draft import mock
from fantasy_quant.draft.personalities import (
    make_opponent_pick_fn,
    personalities,
    pos_z,
    unbounded_budget,
)
from fantasy_quant.draft.simulator import board_player_key, simulate_draft

DB = Path("data/fantasy_quant.duckdb")
OUT = Path("analysis/phase16_14r_reacher.json")
CACHE = Path("analysis/cache")

#: 16.14R's own done-when for this seat.
MAX_VS_BALANCED: float = 2.0

#: Signals reported for the drafted pool — the *direction* half.
COLS: tuple[str, ...] = ("rookie", "cos", "upside", "tail_risk", "floor", "mean")


def reach_ceiling(panel: pd.DataFrame, *, max_round: int = 15) -> pd.DataFrame:
    """Per-round **reach-side** profile in 10-team ADP picks — one code path, both sides.

    ★ Deliberately *not* a re-derivation. An earlier cut of this step recomputed the round from
    ``ceil(pick_no / teams)`` and the picks from ``drift * 10``, and produced a "corpus p95" of
    **8.8** at round 15 against T15's already-published p90 of **52.3** — a ceiling wrong by 6x,
    which duly failed the shipped reacher on 11 of 15 rounds. The panel carries its own ``round``
    and :func:`~fantasy_quant.draft.mock._picks` is the one place the 10-team scaling lives; both
    are used here.

    ``reach_profile`` reports **|drift|**, pooling reaches with falls, because that is how T15's
    corpus figures were computed. A ceiling for a *reacher* has to be the reach side alone — a
    round-15 corpus p90 of 52 picks is mostly elite players **falling**, which bounds nothing about
    how far a manager may jump.
    """
    if panel.empty:
        return pd.DataFrame(columns=["round", "n", "p95", "mx", "mean"])
    p = panel[panel["round"] <= max_round]
    d = mock._picks(p["drift"])
    df = pd.DataFrame({"round": p["round"], "reach": d})
    df = df[df["reach"] > 0]                              # the reach side only
    g = df.groupby("round")["reach"]
    return pd.DataFrame({"n": g.size(), "mean": g.mean(),
                         "p95": g.quantile(0.95), "mx": g.max()}).reset_index()


def _drafted_z(board: pd.DataFrame, pers, *, seeds, rounds: int, model) -> pd.Series:
    z = board.copy()
    pos = board["position"].to_numpy()
    for c in COLS:
        if c in board.columns:
            z[c] = pos_z(board[c], pos)
    key = board_player_key(board).astype(str)
    rows = []
    for s in seeds:
        st = simulate_draft(board, n_teams=10, rounds=rounds, seed=s,
                            opponent_pick_fn=make_opponent_pick_fn(model, pers))
        keys = set(st.pick_log().query("not is_you")["player_key"])
        rows.append(z[key.isin(keys)][[c for c in COLS if c in z.columns]].mean())
    return pd.DataFrame(rows).mean()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    model = mock.load_opponent_model()
    board, src = mock.room_board(con, args.season, cache_dir=CACHE)
    seeds = range(args.seeds)
    pers = personalities()

    # the judgement-free ceiling, from realized human drafts
    corpus = build_drift_panel(con)
    corpus = corpus[corpus["board_source"] == boards.FFC]
    ceiling = reach_ceiling(corpus)[["round", "p95"]].rename(columns={"p95": "corpus_p95"})
    print(f"{args.season} board {len(board)} rows ({src}); corpus {corpus['draft_id'].nunique()} "
          f"drafts for the p95 ceiling")

    # -- the direction half -----------------------------------------------------------------------
    print("\n=== drafted pool, mean within-position z — DIRECTION ===")
    directed = _drafted_z(board, pers["reacher"], seeds=seeds, rounds=args.rounds, model=model)
    # ⚠ T25: `reach_budget=None` now means *inherit* the room ceiling, so the pre-16.14R control
    # has to name `unbounded_budget()` explicitly or this ablation quietly stops being one.
    undirected = _drafted_z(board, replace(pers["reacher"], signal_weights={}, override={},
                                           hype_gain=0.0, reach_budget=unbounded_budget()),
                            seeds=seeds, rounds=args.rounds, model=model)
    bal = _drafted_z(board, pers["balanced"], seeds=seeds, rounds=args.rounds, model=model)
    dirtab = pd.DataFrame({"reacher (shipped)": directed, "reacher (pre-16.14R: width only)":
                           undirected, "balanced": bal}).T
    print(dirtab.round(3).to_string())
    moved = {c: bool(abs(directed[c] - undirected[c]) > 0.01) for c in COLS if c in directed}
    print(f"  signals the direction actually moves: "
          f"{[c for c, v in moved.items() if v] or 'NONE — the seat is still noise'}")

    # -- the two bars -----------------------------------------------------------------------------
    # measured in the room T15 validated, so the reacher's numbers sit against a known baseline.
    # Step 7 re-measures every seat in the room it actually ships.
    room = mock.full_room(mock.DEFAULT_FULL_ROOM, n_teams=10, seed=17)
    sim = mock.batch_drift_panel(board, room, model, season=args.season, seeds=seeds,
                                 n_teams=10, rounds=args.rounds, board_source=src)
    r_reach = reach_ceiling(sim[sim["seat_personality"] == "reacher"])
    b_reach = reach_ceiling(sim[sim["seat_personality"] == "balanced"])
    tab = (r_reach.merge(b_reach, on="round", suffixes=("_reach", "_bal"))
           .merge(ceiling, on="round", how="left"))
    tab["ratio_max"] = tab["mx_reach"] / tab["mx_bal"].replace(0, np.nan)
    tab["over_ceiling"] = tab["p95_reach"] > tab["corpus_p95"]
    print("\n=== per-round deviation, 10-team ADP picks ===")
    print(tab[["round", "mean_reach", "p95_reach", "mx_reach", "mx_bal", "ratio_max",
               "corpus_p95", "over_ceiling"]].round(2).to_string(index=False))

    scored = tab[tab["ratio_max"].notna()]
    bar1 = {"worst_ratio": round(float(scored["ratio_max"].max()), 3),
            "limit": MAX_VS_BALANCED,
            "pass": bool((scored["ratio_max"] <= MAX_VS_BALANCED).all())}
    ceil_rows = tab[tab["corpus_p95"].notna()]
    bar2 = {"rounds_over_ceiling": int(ceil_rows["over_ceiling"].sum()),
            "rounds_scored": int(len(ceil_rows)),
            "pass": bool(not ceil_rows["over_ceiling"].any())}
    print(f"\n=== BAR 1 — max reach <= {MAX_VS_BALANCED}x balanced at EVERY round ===")
    print(f"  worst ratio {bar1['worst_ratio']:.2f} -> {'PASS' if bar1['pass'] else 'FAIL'}")
    print("\n=== BAR 2 — per-round p95 under the realized human p95 ===")
    print(f"  {bar2['rounds_over_ceiling']}/{bar2['rounds_scored']} rounds over -> "
          f"{'PASS' if bar2['pass'] else 'FAIL'}")

    # -- what the budget itself costs, measured separately ---------------------------------------
    # same room, same seed, one seat swapped for its budget-free twin
    room_nb = tuple(replace(p, reach_budget=unbounded_budget()) if p.name == "reacher" else p
                    for p in room)
    sim_nb = mock.batch_drift_panel(board, room_nb, model, season=args.season, seeds=seeds,
                                    n_teams=10, rounds=args.rounds, board_source=src)
    no_budget = reach_ceiling(sim_nb[sim_nb["seat_personality"] == "reacher"])
    cmp_budget = r_reach.merge(no_budget, on="round", suffixes=("_on", "_off"))
    print("\n=== ablation — what the reach budget removes ===")
    print(cmp_budget[["round", "mx_on", "mx_off", "p95_on", "p95_off"]].round(1).to_string(
        index=False))
    budget_moves = bool((cmp_budget["mx_on"] < cmp_budget["mx_off"]).any())
    print(f"  budget binds somewhere: {budget_moves}")

    verdict = {"bar1_max_vs_balanced": bar1["pass"], "bar2_under_corpus_p95": bar2["pass"],
               "direction_moves_signals": bool(any(moved.values())),
               "budget_binds": budget_moves}
    print("\n=== VERDICT ===")
    for k, v in verdict.items():
        print(f"  {k:<28} {'PASS' if v else 'FAIL'}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "generated": pd.Timestamp.now("UTC").isoformat(),
        "season": args.season, "board_source": src,
        "config": {"seeds": args.seeds, "rounds": args.rounds},
        "direction": json.loads(dirtab.to_json(orient="index")),
        "direction_moves": moved,
        "per_round": json.loads(tab.to_json(orient="records")),
        "bar1": bar1, "bar2": bar2,
        "budget_ablation": json.loads(cmp_budget.to_json(orient="records")),
        "verdict": verdict,
    }, indent=2, default=float))
    print(f"\nwrote {args.out}")
    con.close()


if __name__ == "__main__":
    main()
