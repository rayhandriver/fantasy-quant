"""T24's calibration sweep — pick ``(WidthCurve.base, κ)`` against the corpus, not by eye.

    uv run python steps/mock_t24_sweep.py --seeds 12 --seasons 2019 2022 2024

Runs the shipped room over a grid of (narrowing, private-board scale) and prints the four numbers
that decide the trade, so the full bar sheet (``steps/mock_room_bars.py``) is run **once** on a
config that was chosen rather than guessed. Writes ``analysis/mock_t24_sweep.json``.

★ **The verdict this harness produced (2026-07-28), so nobody re-runs it hoping for the old story.**
The grid was built to calibrate a **reallocation** — narrow the flat softmax (``base``) and hand the
deviation back per player through ``κ·adp_stdev``. The measurement says the second half of that is
**wrong**: κ is *monotonically harmful* on the elite-fall objection (18.8 / 19.7 / 26.6 % past pick
4 at κ = 0/1/2, seating-marginalized), because at the top of the board ``adp_stdev`` (0.7–2.5) is
the same size as the ADP gaps it perturbs (~0.2 picks) — the draw destroys ordering rather than
creating tier structure. **Shipped: ``base 0.6 · γ 1.0 · κ 0``.** Round 1 was simply too wide.

⚠ **Run this with ``--shuffle-room``.** A fixed seating flatters every landing number by 5–7 pp and
no number of extra seeds fixes it — the seating error is a *bias* until the seating is redrawn.
⚠ **Bracket the dial.** Two configs shipped off this grid before it contained their neighbours; the
row that decided the ticket (``base 0.7, κ 0``) and the row that ships (``0.6``) were both added
after a result looked wrong.

The scored columns:

  ``past4``    share of the ADP 0–2.5 band landing past pick 4. **The objection, quantified**
               (corpus 13.1 %, gate ≤ corpus + 5 pp). The mean cannot see it: reaches and falls
               cancel inside |drift|.
  ``r1``       round-1 mean |drift| in picks — T15 bar 1's level (corpus 2.87).
  ``rise``     round-1 second-half mean ÷ first-half. The corpus **rises** (1.22); a flat sim is
               the shape half of the defect.
  ``disp``     bar 5, mean within-draft sd of centered drift vs the corpus (±20 %).
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
from fantasy_quant.draft import mock, optimizer
from fantasy_quant.draft.config import DraftConfig
from fantasy_quant.draft.personalities import (
    CORPUS_REACH_P95,
    PRIVATE_CLIP,
    REALISTIC_ROOM,
)

DB = Path("data/fantasy_quant.duckdb")
CACHE = Path("analysis/cache")
OUT = Path("analysis/mock_t24_sweep.json")
#: The shipped model artifact — `--write` merges the chosen (base, gamma, κ) into it, the same way
#: `steps/t15_4_width_curve.py` ships its own joint choice. The room reads it through
#: `mock.load_opponent_model`, so nothing downstream has a second copy to fall out of step with.
SHIPPED = Path("analysis/phase11_opponent_model.json")

#: The grid, as ``(base, gamma, kappa)``. The first row is the **shipped** room (``base=1``,
#: the fitted ``gamma=0.8``, no private board), so every other row is a before/after against a
#: number this same code produced on this same subsample.
#:
#: ``gamma`` is in the grid because ``base`` narrows *every* round: if the private board cannot give
#: back the late-round spread it removes, the honest repair is to steepen the depth curve rather
#: than to accept a uniformly tighter room (T15 bar 5). ``base·15^gamma`` is the round-15 width, so
#: ``(0.5, 1.0)`` ends up within 15 % of the shipped curve's late end while halving round 1.
GRID: tuple[tuple[float, float, float], ...] = (
    (1.00, 0.80, 0.0),
    (0.70, 0.80, 1.0),
    (0.70, 0.80, 2.0),
    (0.50, 0.80, 2.0),
    (0.50, 1.00, 2.0),
    (0.50, 1.00, 3.0),
    (0.35, 1.00, 3.0),
)


def ceiling_saturation(sim: pd.DataFrame, *, tol: float = 0.9) -> float:
    """Share of simulated picks sitting at (≥ ``tol`` ×) the room's per-round reach ceiling.

    ★ **The diagnostic that catches a private board which has stopped being an opinion.** κ scales a
    perturbation in ADP picks, and by mid-board ``adp_stdev`` is 8–12, so a seat with
    ``κ_seat = κ · width_mult`` of 4 perceives a deep player anywhere in a ±35-pick window — far
    wider than ``CORPUS_REACH_P95[0] = 14.6``. Every such seat then wants the deepest player its
    budget allows, at every pick, and the budget (not the belief) is what picks the player. The room
    still drafts, still passes a dispersion bar, and has silently become *"take the maximum legal
    reach"*. **A constraint that binds every time is no longer a constraint; it is the policy.**
    """
    r = sim["drift"].to_numpy(float) * mock.TEAMS_REF          # rounds -> 10-team picks, reach > 0
    rnd = sim["round"].to_numpy(int).clip(1, len(CORPUS_REACH_P95))
    ceil = np.asarray(CORPUS_REACH_P95, float)[rnd - 1]
    return float((r >= tol * ceil).mean())


def score(sim: pd.DataFrame, corpus: pd.DataFrame) -> dict:
    land = mock.landing_profile(sim)
    top = land.iloc[0]
    gl = mock.gate_elite_landing(sim, corpus)
    r1 = mock.compare_profiles(sim, corpus)
    r1row = r1[r1["round"] == 1].iloc[0]
    split = mock.round1_split(sim)
    rise = float(split.iloc[1]["mean_abs"] / split.iloc[0]["mean_abs"])
    sd_sim = float(sim.groupby("draft_id")["drift_centered"].std().mean())
    sd_cor = float(corpus.groupby("draft_id")["drift_centered"].std().mean())
    g2 = mock.gate_elite_fall(sim)
    return {"past4": float(top["past_4"]), "past6": float(top["past_6"]),
            "median_slot": float(top["median_slot"]), "landing_pass": bool(gl["pass"]),
            "r1_mean": float(r1row["sim_mean"]), "r1_rise": rise,
            "disp_error": (sd_sim - sd_cor) / sd_cor,
            "elite_p95": float(g2["p95_slot"]), "elite_past10": float(g2["share_past_10"]),
            "elite_pass": bool(g2["pass"]), "profile_distance": mock.profile_distance(sim, corpus),
            "ceiling_saturation": ceiling_saturation(sim)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=12)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--room-seed", type=int, default=17)
    ap.add_argument("--seasons", type=int, nargs="*", default=[2019, 2022, 2024])
    ap.add_argument("--grid", type=float, nargs="*", default=None,
                    help="flat (base, gamma, kappa) triples overriding GRID")
    ap.add_argument("--write", type=float, nargs=3, default=None,
                    metavar=("BASE", "GAMMA", "KAPPA"),
                    help="ship this config into analysis/phase11_opponent_model.json")
    ap.add_argument("--shuffle-room", action="store_true",
                    help="re-seat the room every seed (the seating confound; see mock_room_bars)")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    grid = (tuple(zip(args.grid[::3], args.grid[1::3], args.grid[2::3], strict=True))
            if args.grid else GRID)

    con = duckdb.connect(str(DB), read_only=True)
    model = mock.load_opponent_model()
    room = mock.full_room(REALISTIC_ROOM, n_teams=10, seed=args.room_seed)
    seasons = tuple(args.seasons)

    corpus = build_drift_panel(con)
    ffc = corpus[corpus["board_source"] == boards.FFC]
    corpus_matched = ffc[ffc["season"].isin(seasons)]
    cl = mock.landing_profile(corpus_matched).iloc[0]
    csplit = mock.round1_split(corpus_matched)
    print(f"corpus ({len(corpus_matched):,} picks): top-band past-4 {cl['past_4']:.1%} · "
          f"median slot {cl['median_slot']:.2f} · round-1 rise "
          f"{csplit.iloc[1]['mean_abs'] / csplit.iloc[0]['mean_abs']:.2f}")

    # boards/value/risk are the expensive part and do not depend on the grid — build once.
    prepared = {}
    for season in seasons:
        board, src = mock.room_board(con, season, cache_dir=CACHE)
        if board.empty:
            print(f"  {season}: no board, skipped")
            continue
        config = DraftConfig()
        vi = optimizer.assemble_value(con, season, config)
        attached = optimizer.attach_value(board, vi)
        risk = optimizer.build_risk_model(attached, vi, optimizer.assemble_correlation(con, season),
                                          lam=config.risk_lambda)
        prepared[season] = (attached, src, risk)

    rows = []
    for base, gamma, kappa in grid:
        m = mock.load_opponent_model()
        m.width_curve = replace(model.width_curve, base=float(base), gamma=float(gamma))
        frames = []
        for season, (attached, src, risk) in prepared.items():
            seatings = ([mock.full_room(REALISTIC_ROOM, n_teams=10, seed=args.room_seed + 1000 * s)
                         for s in range(args.seeds)] if args.shuffle_room
                        else [room] * args.seeds)
            frames += [mock.batch_drift_panel(
                attached, seatings[s], m, season=season, seeds=[s], n_teams=10,
                rounds=args.rounds, board_source=src, risk=risk, kappa=float(kappa))
                for s in range(args.seeds)]
        sim = pd.concat(frames, ignore_index=True)
        s = score(sim, corpus_matched)
        s |= {"base": float(base), "gamma": float(gamma), "kappa": float(kappa)}
        rows.append(s)
        print(f"  base {base:<5} gamma {gamma:<4} kappa {kappa:<4} | past4 {s['past4']:6.1%} "
              f"(gate {'PASS' if s['landing_pass'] else 'FAIL'}) · r1 {s['r1_mean']:5.2f} · "
              f"rise {s['r1_rise']:4.2f} · disp {s['disp_error']:+6.1%} · "
              f"elite p95 {s['elite_p95']:4.1f} past10 {s['elite_past10']:5.1%} "
              f"{'PASS' if s['elite_pass'] else 'FAIL'} · "
              f"at-ceiling {s['ceiling_saturation']:5.1%}", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "generated": pd.Timestamp.now("UTC").isoformat(),
        "config": {"seeds": args.seeds, "rounds": args.rounds, "seasons": list(seasons),
                   "room_seed": args.room_seed, "room": [p.name for p in room],
                   "shuffle_room": bool(args.shuffle_room)},
        "corpus": {"past_4": float(cl["past_4"]), "past_6": float(cl["past_6"]),
                   "median_slot": float(cl["median_slot"]),
                   "r1_rise": float(csplit.iloc[1]["mean_abs"] / csplit.iloc[0]["mean_abs"])},
        "grid": rows,
    }, indent=2, default=float))
    if args.write:
        base, gamma, kappa = (float(x) for x in args.write)
        art = json.loads(SHIPPED.read_text())
        art["width_curve"] = replace(model.width_curve, base=base, gamma=gamma).to_dict()
        art["private_board"] = {
            "kappa": kappa, "clip": PRIVATE_CLIP,
            "source": "steps/mock_t24_sweep.py --write (T24, 2026-07-28)",
            "why": "width per player, not per round: the corpus says |drift| ~ 2 x adp_stdev, and "
                   "a round-indexed curve is structurally blind to a 4.2x spread inside rounds 1-3",
        }
        SHIPPED.write_text(json.dumps(art, indent=2, default=float))
        print(f"\nshipped base={base} gamma={gamma} kappa={kappa} -> {SHIPPED}")

    print(f"\nwrote {args.out}")
    con.close()


if __name__ == "__main__":
    main()
