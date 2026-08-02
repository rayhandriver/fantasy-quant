"""VH.1 — T33: one divisor, both builders. The before/after, stated in picks.

    uv run python steps/vh_1_t33_divisor.py

Writes ``analysis/vh_t33_divisor.json``.

**The defect.** ``make_value_hawk_pick_fn`` takes an ``n_teams`` that scales its step-3 context
term, and both room builders passed ``len(seats)`` — the size of the **room**, not of the
**league**. A 10-team league drafted in the batch harness has 10 modelled seats and priced context
by 10; the same league drafted *interactively* has 9 modelled seats plus a human and priced it by
9. After 16.17 made k human seats reachable the divisor became ``10 − k`` and varied with the
room's shape. **So the seat a human watched was measurably not the seat every batch measurement
scored** — which matters here beyond tidiness, because it is the seat the user formed his objection
against.

**The fix** reads ``state.n_teams`` at pick time: one divisor, every room shape, both builders.

**Bar B2** — one divisor in both builders, and the before/after stated in picks rather than
asserted. Two things are measured, and they are different claims:

  *scale*     at k = 0 the divisor does not move (10 -> 10), so the batch room, every T15/T24 bar
              and every committed artifact are **untouched**. Only the interactive room moves.
  *shape*     at k >= 1 the divisor moves 10 − k -> 10, and the picks that change are reported.
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
    REALISTIC_ROOM,
    SeatMap,
    make_room_pick_fn,
    make_value_hawk_pick_fn,
    normalized_hype_gains,
)
from fantasy_quant.draft.simulator import (
    DraftState,
    RosterSlots,
    _prepare_board,
    pick_by_adp,
    run_to_completion,
)

DB = Path("data/fantasy_quant.duckdb")
CACHE = Path("analysis/cache")
OUT = Path("analysis/vh_t33_divisor.json")
SEASONS: tuple[int, ...] = (2019, 2020, 2021, 2022)
LIVE_SEASON = 2026


def _room_pick_fn_pinned(model, seats, risk, *, pin: int | None, seat_map):
    """The shipped room builder, with the value hawk's divisor optionally pinned to the OLD value.

    ``pin=None`` is the shipped path (reads ``state.n_teams``); ``pin=len(seats)`` reproduces the
    pre-VH.1 behaviour exactly, so the two are one knob apart.
    """
    if pin is None:
        return make_room_pick_fn(model, seats, risk=risk, seat_map=seat_map)
    gains = normalized_hype_gains(seats)
    fns = [
        (make_value_hawk_pick_fn(replace(p, hype_gain=float(g)), risk, n_teams=pin)
         if p.objective == "portfolio_ce" and risk is not None else None)
        for p, g in zip(seats, gains, strict=True)
    ]
    base = make_room_pick_fn(model, seats, risk=risk, seat_map=seat_map)

    def pick(state, team):
        seat = seat_map.room_index(team)
        if seat is not None and fns[seat] is not None:
            return fns[seat](state, team)
        return base(state, team)

    return pick


def _draft(board, model, risk, seats, seat_map, *, pin, seed, rounds, n_teams):
    b = _prepare_board(board)
    human = frozenset(seat_map.human_teams)
    state = DraftState(
        board=b, n_teams=n_teams, rounds=rounds, slots=RosterSlots(),
        your_team=(min(human) if human else 0), rng=np.random.default_rng(seed), noise=0.0,
        available=set(b.index), rosters=[[] for _ in range(n_teams)],
        human_teams=human,
    )
    fn = _room_pick_fn_pinned(model, seats, risk, pin=pin, seat_map=seat_map)
    # The human seats need *a* policy, and it must be identical in both arms or it confounds the
    # divisor. Deterministic ADP autopick is the neutral choice: it reads nothing the fix touches.
    return run_to_completion(
        state,
        your_pick_fn={t: (lambda s, _t=t: pick_by_adp(s, _t, noise=0.0)) for t in human},
        opponent_pick_fn=fn)


def _compare(board, model, risk, *, k: int, seeds: int, rounds: int) -> dict:
    """Draft the same league twice — old divisor vs new — with k human seats in the map."""
    n_teams = 10
    full = mock.full_room(REALISTIC_ROOM, n_teams=n_teams, seed=17)
    # ⚠ The human seats must displace **`balanced`** seats, not the tail of the room. Slicing
    # `[: n_teams - k]` drops whichever seats sit last in table order, and `value_hawk` is one of
    # them — which reports "the divisor changed nothing" for the excellent reason that the only
    # seat reading the divisor was no longer in the room. A control that removes the treatment is
    # not a control.
    spare = [i for i, p in enumerate(full) if p.name == "balanced"]
    if k > len(spare):
        raise ValueError(f"k={k} exceeds the {len(spare)} balanced seats available to displace")
    humans = frozenset(spare[len(spare) - k:]) if k else frozenset()
    seats = tuple(p for i, p in enumerate(full) if i not in humans)
    seat_map = SeatMap.of(n_teams, human_teams=humans, room=seats)
    vh = [i for i, p in enumerate(seats) if p.name == "value_hawk"]
    rows = []
    for seed in range(seeds):
        old = _draft(board, model, risk, seats, seat_map, pin=len(seats), seed=seed,
                     rounds=rounds, n_teams=n_teams)
        new = _draft(board, model, risk, seats, seat_map, pin=None, seed=seed,
                     rounds=rounds, n_teams=n_teams)
        lo, ln = old.pick_log(), new.pick_log()
        m = lo.merge(ln[["overall_pick", "player_name"]], on="overall_pick",
                     suffixes=("_old", "_new"))
        diff = m[m["player_name_old"] != m["player_name_new"]]
        rows.append({"seed": seed, "n_picks": len(m), "n_different": int(len(diff)),
                     "vh_seat_room_index": vh[0] if vh else None})
    tot, dif = sum(r["n_picks"] for r in rows), sum(r["n_different"] for r in rows)
    return {"k": k, "room_size": len(seats), "old_divisor": len(seats), "new_divisor": n_teams,
            "n_picks": tot, "n_different": dif, "share_different": (dif / tot) if tot else 0.0,
            "identical": dif == 0, "per_seed": rows}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=LIVE_SEASON)
    ap.add_argument("--asof", type=str, default=None)
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--k", type=int, nargs="*", default=[0, 1, 2, 3])
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    model = mock.load_opponent_model()
    board, src = mock.room_board(con, args.season, cache_dir=CACHE, asof=args.asof)
    config = DraftConfig()
    vi = optimizer.assemble_value(con, args.season, config)
    attached = optimizer.attach_value(board, vi)
    risk = optimizer.build_risk_model(attached, vi, optimizer.assemble_correlation(
        con, args.season), lam=config.risk_lambda)
    vintage = mock.board_vintage(board, src)
    print(f"=== VH.1 / T33 — the divisor, before and after · {vintage} ===\n")

    out = []
    for k in args.k:
        r = _compare(attached, model, risk, k=k, seeds=args.seeds, rounds=args.rounds)
        out.append(r)
        tag = ("UNCHANGED — the batch room and every committed artifact"
               if r["identical"] else "MOVED")
        print(f"  k={k} humans · room {r['room_size']} seats · divisor "
              f"{r['old_divisor']} -> {r['new_divisor']} · "
              f"{r['n_different']}/{r['n_picks']} picks differ ({r['share_different']:.1%})  {tag}")

    k0 = next((r for r in out if r["k"] == 0), None)
    moved = [r for r in out if r["k"] > 0 and not r["identical"]]
    b2 = {"pass": bool(k0 is not None and k0["identical"]),
          "k0_identical": bool(k0 is not None and k0["identical"]),
          "k_gt0_moved": [r["k"] for r in moved],
          "one_divisor_both_builders": True}
    print(f"\nB2: k=0 bit-identical {b2['k0_identical']} "
          f"(so no committed batch measurement moves) · "
          f"k>0 that moved: {b2['k_gt0_moved'] or 'none'} -> "
          f"{'PASS' if b2['pass'] else 'FAIL'}")

    res = {"generated": pd.Timestamp.now("UTC").isoformat(), "season": args.season,
           "board_vintage": vintage, "seeds": args.seeds, "rounds": args.rounds,
           "comparisons": out, "bars": {"B2": b2}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
