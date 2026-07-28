"""16.14R step 4 — ``safe_floor`` reworked to **lowest downside**, not *highest floor*.

    uv run python steps/phase16_14r_4_safe_floor.py
    uv run python steps/phase16_14r_4_safe_floor.py --seeds 20 --season 2026

Done when, **stated as an opposition** (the 16.14 rule — "each differs from balanced" passes the
broken build):

1. ``safe_floor`` and ``reacher`` disagree on **>= DISAGREE_MIN** of their picks, and
2. ``safe_floor``'s drafted pool shows **lower spread** than ``balanced`` — not merely higher floor.

★ **Bar 2 is the one that matters, and it is the one the seat previously failed.** "Higher floor"
was satisfiable by the broken T19 column, and satisfied by it: the mock's ``safe_floor`` read +0.198
floor against ``balanced`` while drafting boom-or-bust players, because the *column* was inverted.
A spread bar cannot be satisfied that way — it asks whether the outcomes this manager bought are
actually narrower, which is what a risk-averse manager is *for*.

★ **``X`` is pre-registered here rather than read off the run**, per the T15 discipline: a
"disagree on >= X %" bar chosen after seeing the number measures nothing. ``DISAGREE_MIN`` is set
from the structure of the problem, not from a pilot — see its docstring.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from fantasy_quant.draft import mock
from fantasy_quant.draft.personalities import make_opponent_pick_fn, personalities, pos_z
from fantasy_quant.draft.simulator import _prepare_board, board_player_key, simulate_draft

DB = Path("data/fantasy_quant.duckdb")
OUT = Path("analysis/phase16_14r_safe_floor.json")
CACHE = Path("analysis/cache")

#: Pre-registered disagreement floor for bar 1.
#:
#: Both seats draft from the same board under the same fitted beta, and both are bounded reachers —
#: so a large shared component is *expected*, not a defect: at any pick, the best-available player
#: is often the right answer for everyone. The bar has to be clear of that shared floor without
#: demanding two managers who never agree. Two ADP-faithful seats with different tastes overlap on
#: roughly the top of the pool at each pick; requiring a **third** of picks to differ says the
#: tastes are doing real work while leaving room for the board to dominate the rest.
DISAGREE_MIN: float = 1 / 3

#: Signals reported for the drafted pool. ``tail_risk`` is the headline (bar 2).
COLS: tuple[str, ...] = ("floor", "tail_risk", "upside", "durability", "mean", "rookie")


def _drafted_z(board: pd.DataFrame, pers, *, seeds, rounds: int, model) -> pd.DataFrame:
    """Within-position z of every reported signal, over the pool this personality drafted."""
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
    return pd.DataFrame(rows)


def _picks(board, pers, *, seed, rounds, model) -> list[str]:
    st = simulate_draft(board, n_teams=10, rounds=rounds, seed=seed,
                        opponent_pick_fn=make_opponent_pick_fn(model, pers))
    return list(st.pick_log().query("not is_you")["player_key"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--seeds", type=int, default=16)
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    model = mock.load_opponent_model()
    board, src = mock.room_board(con, args.season, cache_dir=CACHE)
    seeds = range(args.seeds)
    pers = personalities()
    print(f"{args.season} board {len(board)} rows ({src}); "
          f"{args.seeds} seeds x {args.rounds} rounds")

    # -- bar 2: is the pool this manager bought actually narrower? --------------------------------
    pools = {n: _drafted_z(board, pers[n], seeds=seeds, rounds=args.rounds, model=model)
             for n in ("safe_floor", "balanced", "reacher", "upside_chaser")}
    tab = pd.DataFrame({n: p.mean() for n, p in pools.items()}).T
    print("\n=== drafted pool, mean within-position z ===")
    print(tab.round(3).to_string())

    safe, bal = pools["safe_floor"], pools["balanced"]
    d_spread = float(safe["tail_risk"].mean() - bal["tail_risk"].mean())
    # paired over seeds: the same board and the same shared board dynamics, so the seed pairing
    # removes most of the between-draft noise the 16.14 face-validity numbers had to pool away.
    paired = safe["tail_risk"] - bal["tail_risk"]
    se = float(paired.std(ddof=1) / np.sqrt(len(paired)))
    ci = (round(float(paired.mean() - 1.96 * se), 4), round(float(paired.mean() + 1.96 * se), 4))
    bar2 = {"delta_tail_risk_vs_balanced": round(d_spread, 4), "ci": ci,
            "delta_floor_vs_balanced": round(float(safe["floor"].mean() - bal["floor"].mean()), 4),
            "delta_mean_vs_balanced": round(float(safe["mean"].mean() - bal["mean"].mean()), 4),
            "delta_rookie_vs_balanced": round(
                float(safe["rookie"].mean() - bal["rookie"].mean()), 4),
            "pass": bool(d_spread < 0 and ci[1] < 0)}
    print("\n=== BAR 2 — lower spread than balanced (not merely higher floor) ===")
    print(f"  tail_risk delta {d_spread:+.4f} CI[{ci[0]:+.4f},{ci[1]:+.4f}] -> "
          f"{'PASS' if bar2['pass'] else 'FAIL'}")
    print(f"  (floor delta {bar2['delta_floor_vs_balanced']:+.4f}, "
          f"level delta {bar2['delta_mean_vs_balanced']:+.4f}, "
          f"rookie delta {bar2['delta_rookie_vs_balanced']:+.4f})")

    # -- bar 1: the two opposed seats must actually disagree --------------------------------------
    shares = []
    for s in seeds:
        a = _picks(board, pers["safe_floor"], seed=s, rounds=args.rounds, model=model)
        b = _picks(board, pers["reacher"], seed=s, rounds=args.rounds, model=model)
        shares.append(1.0 - len(set(a) & set(b)) / max(len(set(a) | set(b)), 1))
    disagree = float(np.mean(shares))
    bar1 = {"disagreement": round(disagree, 4), "min": DISAGREE_MIN,
            "pass": bool(disagree >= DISAGREE_MIN)}
    print("\n=== BAR 1 — safe_floor vs reacher disagreement ===")
    print(f"  {disagree:.1%} of the drafted pool differs (bar {DISAGREE_MIN:.1%}) -> "
          f"{'PASS' if bar1['pass'] else 'FAIL'}")

    # -- every knob must MOVE something (the "an inert thing still passes" rule) ------------------
    print("\n=== ablation — each knob against itself off ===")
    b = _prepare_board(board)
    lz = pos_z(b["mean"], b["pos"].to_numpy())
    idxmap = {k: i for i, k in enumerate(b["player_key"])}
    below = float((lz < (pers["safe_floor"].level_floor or -np.inf)).mean())

    # ⚠ the threshold is the SHIPPED one in both arms. Reading it off each variant makes the
    # ablation measure -inf when the guard is off and report a spurious 0.0 % — a control has to
    # be scored on the treatment's own yardstick, not on its own.
    thr = float(pers["safe_floor"].level_floor)

    def sub_floor_rate(p) -> float:
        hits = tot = 0
        for s in seeds:
            st = simulate_draft(board, n_teams=10, rounds=15, seed=s,
                                opponent_pick_fn=make_opponent_pick_fn(model, p))
            for k in st.pick_log().query("not is_you")["player_key"]:
                i = idxmap.get(k)
                if i is not None:
                    tot += 1
                    hits += lz[i] < thr
        return hits / max(tot, 1)

    base = pers["safe_floor"]
    ablation = {"board_share_below_floor": round(below, 4)}
    rk_on = _drafted_z(board, base, seeds=seeds, rounds=args.rounds, model=model)["rookie"].mean()
    rk_off = _drafted_z(board, replace(base, override={}), seeds=seeds, rounds=args.rounds,
                        model=model)["rookie"].mean()
    ablation["rookie_z_with_override"] = round(float(rk_on), 4)
    ablation["rookie_z_without"] = round(float(rk_off), 4)
    ablation["rookie_override_moves"] = bool(rk_on < rk_off)
    lf_on = sub_floor_rate(base)
    lf_off = sub_floor_rate(replace(base, level_floor=None))
    ablation["sub_floor_pick_rate_with_guard"] = round(lf_on, 4)
    ablation["sub_floor_pick_rate_without"] = round(lf_off, 4)
    ablation["level_floor_binds"] = bool(lf_on < lf_off)
    print(f"  rookie override : z {rk_off:+.4f} -> {rk_on:+.4f}  "
          f"{'moves' if ablation['rookie_override_moves'] else 'INERT'}")
    print(f"  level floor     : sub-floor picks {lf_off:.1%} -> {lf_on:.1%} "
          f"({below:.0%} of the board sits below it)  "
          f"{'binds' if ablation['level_floor_binds'] else 'INERT'}")
    print("  ^ the level floor is a RAIL, not a force: the ADP term already declines most of\n"
          "    these players, so it is the tail it catches that justifies it, not the average.")

    # -- what it actually drafts, for eyes ---------------------------------------------------------
    st = simulate_draft(board, n_teams=10, rounds=args.rounds, seed=0,
                        opponent_pick_fn=make_opponent_pick_fn(model, pers["safe_floor"]))
    log = st.pick_log().query("not is_you").head(14)
    print("\n=== a safe_floor room's first picks (seed 0) ===")
    print(log[["round", "player_name", "pos", "adp"]].round(1).to_string(index=False))

    verdict = {"bar1_disagreement": bar1["pass"], "bar2_lower_spread": bar2["pass"],
               "every_knob_moves_something": bool(ablation["rookie_override_moves"]
                                                  and ablation["level_floor_binds"])}
    print("\n=== VERDICT ===")
    for k, v in verdict.items():
        print(f"  {k:<24} {'PASS' if v else 'FAIL'}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "generated": pd.Timestamp.now("UTC").isoformat(),
        "season": args.season, "board_source": src,
        "config": {"seeds": args.seeds, "rounds": args.rounds},
        "drafted_pool_z": json.loads(tab.to_json(orient="index")),
        "bar1_disagreement": bar1, "bar2_spread": bar2, "ablation": ablation,
        "weights": personalities()["safe_floor"].signal_weights,
        "verdict": verdict,
    }, indent=2, default=float))
    print(f"\nwrote {args.out}")
    con.close()


if __name__ == "__main__":
    main()
