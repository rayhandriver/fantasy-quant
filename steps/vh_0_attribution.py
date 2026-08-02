"""VH.0 — attribute the value hawk's objected picks, **before** anything is changed.

    uv run python steps/vh_0_attribution.py
    uv run python steps/vh_0_attribution.py --asof 2026-07-24 --label pinned0724

Writes ``analysis/vh_attribution.json``.

★ **This step is written so it can kill the session's own hypothesis, and that is the point.**
Session VH's leading hypothesis is T42's: the value path is **slot-blind** (nothing in
``draft/optimizer.py`` references starters) and ``value_hawk`` is the only seat that *maximizes*
it, so it accumulates capital a human reads as an indefensible roster. Bar **B1** says: confirmed
at **>= 50 %** slot-driven, **dead below 25 %**. Three tickets in a row here — T13, T24, T31 — had
the wrong cause on file, and T24's prescription was built and then rejected.

--------------------------------------------------------------------------------------------------
The instrument
--------------------------------------------------------------------------------------------------
At every one of the seat's turns the **actual** draft state is held fixed and the pick is re-taken
under one-knob ablations of the shipped policy. A pick is attributed to a knob when turning that
knob **changes who is taken**. These are *single-decision* counterfactuals: they do not compound,
because each is evaluated against the real board the shipped seat produced. That is deliberate —
compounding would confound "this knob picked this player" with "this knob picked a different player
four rounds ago".

    board_only      lam=0, scarcity_w=0, no context   the raw `base_value` argmax inside the window
    context_off     context_weights={}                the 16.14R step-3 role/TD-regression terms
    starter_aware   risk.bench_weight=0.0             ★ THE SLOT CHANNEL — value counted only where
                                                        it reaches the best legal starting lineup
    window_tight    value_hawk_budget(0.0 / 0.5)      the reach ceiling: can it pay above the round
    window_open     value_hawk_budget(1.25)           the other side of the same knob

--------------------------------------------------------------------------------------------------
★ PRE-REGISTERED — what counts as an objected pick, fixed before the ablations were run
--------------------------------------------------------------------------------------------------
The user gave a pick-by-pick verdict on a **stale artifact**: ``analysis/mock_16_14R_picks.csv`` was
written 2026-07-28 and predates T22 (07-29), T31 (07-30) and the 08-01 situation-event refresh, so
the roster he judged **cannot be reproduced by the current code on any board vintage** — a pinned
07-24 board reproduces 33/150 picks and the live 08-01 board 10/150. His *player-specific* verdicts
therefore cannot be ablated. His **rules** can, and they are what he actually stated:

  R1  "a value hawk should be looking for actual value picks and late-round QBs tend to be much
      better value" + "Loveland at rd 4 is classic TE premium which value hawk should consider less"
      -> ``premium_early``: a QB or TE taken before round 6.
  R2  "you already have a high quality TE starter you spent on early so it seems like a waste of a
      pick"
      -> ``redundant``: a 2nd QB or 2nd TE while one is already rostered, in a 1-QB / 1-TE league.
  R3  "seems like an overpay", "bad value for the round"
      -> ``reach``: ``adp - overall_pick > 0``, i.e. the seat paid above the board's own price.
  R4  every pick he called **good** (Egbuka, Henderson, Maye, Price) had value *fall* to it.
      -> ``fall``: negative reach. Reported as the control, not as an objection.

``objected`` = ``premium_early or redundant or reach``. The **slot-driven share** = the fraction of
objected picks that ``starter_aware`` changes. R2 and R4 are the two rules with a mechanism attached
in advance; R1 and R3 are the ones the ablation has to arbitrate.

The verdict correlation on the artifact he actually judged is reported alongside, as a **static**
read requiring no replay: his labels against ``reach_picks``.
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
    _local_z,
    make_value_hawk_pick_fn,
    normalized_hype_gains,
    personalities,
    value_hawk_budget,
)
from fantasy_quant.draft.simulator import (
    DraftState,
    RosterSlots,
    _prepare_board,
    run_to_completion,
)

DB = Path("data/fantasy_quant.duckdb")
CACHE = Path("analysis/cache")
OUT = Path("analysis/vh_attribution.json")
SEASON = 2026

#: The user's verdicts on `analysis/mock_16_14R_picks.csv`, transcribed 2026-08-01. Verbatim
#: reasons, one per pick, so the static correlation below is auditable against what he wrote.
USER_VERDICTS: tuple[tuple[str, str, str], ...] = (
    ("Justin Jefferson", "bad", "could've had a higher upside RB or WR in rd 1"),
    ("Zay Flowers", "bad", "much much better rb or wr available in rd 2"),
    ("Josh Allen", "bad", "fine, but late-round QBs tend to be much better value"),
    ("Colston Loveland", "bad", "classic TE premium; value hawk should consider it less"),
    ("Emeka Egbuka", "good", "good"),
    ("Bhayshul Tuten", "bad", "upside but an overpay when other QBs/TEs were the better option"),
    ("TreVeyon Henderson", "good", "good"),
    ("Drake Maye", "good", "a good value pick"),
    ("Kyle Pitts Sr.", "bad", "decent upside but a waste — already spent early on a TE starter"),
    ("Jadarian Price", "good", "good"),
    ("Jayden Reed", "neutral", "good not great evaluation of talent and situation"),
    ("Jonathon Brooks", "neutral", "good not great evaluation of talent and situation"),
    ("Rashid Shaheed", "neutral", "good not great evaluation of talent and situation"),
    ("Brandon Aubrey", "neutral", "good not great evaluation of talent and situation"),
    ("Jacksonville Defense", "neutral", "good not great evaluation of talent and situation"),
)

#: R1's cutoff — "early" rounds, where he says a QB or TE is a value error rather than a preference.
PREMIUM_EARLY_BEFORE_ROUND = 6
#: R2's single-starter positions in this league (10-team, 1-QB, full-PPR).
SINGLE_SLOT = ("QB", "TE")
#: The **contention set** — how many top candidates an argmax is realistically decided between.
#: A term's size has to be judged against the spread *here*, not against the whole 200-row pool.
CONTENDED_K = 10


def _static_verdict_read() -> dict:
    """His labels against ``reach_picks``, on the artifact he judged. No replay, no model."""
    csv = Path("analysis/mock_16_14R_picks.csv")
    if not csv.exists():
        return {"available": False}
    log = pd.read_csv(csv)
    vh = log[log["seat_personality"] == "value_hawk"].sort_values("overall_pick")
    verdict = {n: (v, r) for n, v, r in USER_VERDICTS}
    rows = []
    for _, r in vh.iterrows():
        v, why = verdict.get(str(r["player_name"]), ("unlabelled", ""))
        rows.append({"round": int(r["round"]), "player": str(r["player_name"]),
                     "pos": str(r["pos"]), "adp": float(r["adp"]),
                     "reach_picks": float(r["reach_picks"]), "verdict": v, "reason": why})
    d = pd.DataFrame(rows)
    by = {v: float(d.loc[d["verdict"] == v, "reach_picks"].mean())
          for v in ("bad", "good", "neutral") if (d["verdict"] == v).any()}
    lab = d[d["verdict"].isin(("bad", "good"))]
    sep = None
    if not lab.empty and lab["verdict"].nunique() == 2:
        sep = float(np.corrcoef(lab["reach_picks"], (lab["verdict"] == "bad").astype(float))[0, 1])
    return {"available": True, "picks": rows, "mean_reach_by_verdict": by,
            "corr_reach_vs_bad": sep,
            "n_bad": int((d["verdict"] == "bad").sum()),
            "n_good": int((d["verdict"] == "good").sum())}


def _flags(pos: str, rnd: int, adp: float, overall: int, counts: dict[str, int]) -> dict:
    """The pre-registered rules, applied to one pick. ``counts`` is the roster BEFORE the pick."""
    reach = float(adp) - float(overall)
    redundant = pos in SINGLE_SLOT and counts.get(pos, 0) >= 1
    premium_early = pos in SINGLE_SLOT and rnd < PREMIUM_EARLY_BEFORE_ROUND
    return {"reach_picks": round(reach, 2), "reach": bool(reach > 0),
            "redundant": bool(redundant), "premium_early": bool(premium_early),
            "fall": bool(reach < 0),
            "objected": bool(reach > 0 or redundant or premium_early)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--asof", type=str, default=None,
                    help="pin the FFC board vintage, e.g. 2026-07-24 (default: newest)")
    ap.add_argument("--season", type=int, default=SEASON)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--room-seed", type=int, default=17)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--label", type=str, default="live")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    model = mock.load_opponent_model()
    room = mock.full_room(REALISTIC_ROOM, n_teams=10, seed=args.room_seed)
    vh_seat = [i for i, p in enumerate(room) if p.name == "value_hawk"][0]

    board, src = mock.room_board(con, args.season, cache_dir=CACHE, asof=args.asof)
    vintage = mock.board_vintage(board, src)
    config = DraftConfig()
    vi = optimizer.assemble_value(con, args.season, config)
    attached = optimizer.attach_value(board, vi)
    corr = optimizer.assemble_correlation(con, args.season)
    risk = optimizer.build_risk_model(attached, vi, corr, lam=config.risk_lambda)
    print(f"board {len(board)} rows · vintage {vintage} · value_hawk in seat {vh_seat}")

    # The seat exactly as the shipped room builds it: same normalized hype gain, same n_teams.
    gain = float(normalized_hype_gains(room)[vh_seat])
    vh_p = replace(personalities()["value_hawk"], hype_gain=gain)
    n_room = len(room)

    variants = {
        "shipped": make_value_hawk_pick_fn(vh_p, risk, n_teams=n_room),
        "context_off": make_value_hawk_pick_fn(
            replace(vh_p, context_weights={}), risk, n_teams=n_room),
        "starter_aware": make_value_hawk_pick_fn(
            vh_p, replace(risk, bench_weight=0.0), n_teams=n_room),
        "window_none": make_value_hawk_pick_fn(
            replace(vh_p, reach_budget=value_hawk_budget(0.0)), risk, n_teams=n_room),
        "window_half": make_value_hawk_pick_fn(
            replace(vh_p, reach_budget=value_hawk_budget(0.5)), risk, n_teams=n_room),
        "window_open": make_value_hawk_pick_fn(
            replace(vh_p, reach_budget=value_hawk_budget(1.25)), risk, n_teams=n_room),
        "board_only": make_value_hawk_pick_fn(
            replace(vh_p, context_weights={}),
            replace(risk, lam=0.0, scarcity_w=0.0), n_teams=n_room),
    }

    room_pick = mock.full_room_pick_fn(model, room, risk=risk)
    turns: list[dict] = []

    def instrumented(state, team: int) -> int:
        if team != vh_seat:
            return room_pick(state, team)
        pool = state.draftable_pool(team)
        counts = dict(state.roster_counts(team))
        chosen = {k: int(fn(state, team)) for k, fn in variants.items()}
        idx = int(room_pick(state, team))
        assert idx == chosen["shipped"], "the room's own seat is not the seat we ablated"

        def nm(i: int) -> dict:
            r = state.board.loc[i]
            return {"player": str(r["player_name"]), "pos": str(r["pos"]), "adp": float(r["adp"])}

        # ★ How big is the step-3 context term *in the units it is added to*? The argmax flips
        # above say context changes the pick; this says by how much it could. Reconstructed from
        # the same two lines `make_value_hawk_pick_fn` runs, so it cannot drift from them.
        eff_base = risk.effective_rank(pool, state.roster(team), None)
        eff_base = np.where(np.isnan(eff_base), pool["adp"].to_numpy(float), eff_base)
        delta = np.zeros(len(pool))
        for col, w in (vh_p.context_weights or {}).items():
            if col in pool.columns and w:
                delta = delta - w * n_room * _local_z(
                    pool[col], pool["adp"].to_numpy(float), pool["pos"].to_numpy())
        # ★ and against the **contended** denominator: an argmax is only ever decided among the
        # few candidates at the top, so the pool-wide sd flatters the term. `top` is the
        # contention set — the rows a pick is actually chosen between.
        top = np.argsort(eff_base)[:CONTENDED_K]
        spread_top = float(np.ptp(eff_base[top])) if len(top) > 1 else 0.0
        ctx = {"eff_base_sd": float(np.nanstd(eff_base)),
               "context_delta_sd": float(np.nanstd(delta)),
               "context_delta_absmax": float(np.nanmax(np.abs(delta))),
               "ratio_sd": (float(np.nanstd(delta) / np.nanstd(eff_base))
                            if np.nanstd(eff_base) > 0 else None),
               "contended_spread": spread_top,
               "context_delta_absmax_contended": float(np.nanmax(np.abs(delta[top]))),
               "ratio_contended": (float(np.nanmax(np.abs(delta[top])) / spread_top)
                                   if spread_top > 0 else None)}

        bv = pd.Series({k: risk.bv.get(k, np.nan) for k in pool["player_key"]}).astype(float)
        top_bv = bv.sort_values(ascending=False).head(5)
        key_to_row = dict(zip(pool["player_key"], pool.index, strict=False))
        row = state.board.loc[idx]
        rec = {
            "round": int(state.round()), "overall_pick": int(state.overall_pick),
            "pick": nm(idx), "roster_before": counts,
            "base_value": float(risk.bv.get(str(row["player_key"]), np.nan)),
            "changed_by": sorted(k for k, v in chosen.items()
                                 if k != "shipped" and v != chosen["shipped"]),
            "alternatives": {k: nm(v) for k, v in chosen.items() if k != "shipped"},
            "best_by_adp": nm(int(pool["adp"].idxmin())),
            "context_magnitude": ctx,
            "top5_base_value": [{**nm(key_to_row[k]), "base_value": round(float(v), 1)}
                                for k, v in top_bv.items() if k in key_to_row],
        }
        rec.update(_flags(rec["pick"]["pos"], rec["round"], rec["pick"]["adp"],
                          rec["overall_pick"], counts))
        turns.append(rec)
        return idx

    b = _prepare_board(attached)
    state = DraftState(
        board=b, n_teams=10, rounds=args.rounds, slots=RosterSlots(),
        your_team=0, rng=np.random.default_rng(args.seed), noise=0.0,
        available=set(b.index), rosters=[[] for _ in range(10)],
        human_teams=frozenset(),
    )
    run_to_completion(state, opponent_pick_fn=instrumented)

    # ===== the report =============================================================================
    print(f"\n=== the value hawk's {len(turns)} picks, {vintage} ===")
    hdr = f"{'rd':>3} {'pick':>5}  {'player':<22} {'pos':<4} {'adp':>6} {'reach':>7}  flags"
    print(hdr)
    for t in turns:
        fl = ",".join(k for k in ("reach", "premium_early", "redundant") if t[k]) or "-"
        print(f"{t['round']:>3} {t['overall_pick']:>5}  {t['pick']['player']:<22} "
              f"{t['pick']['pos']:<4} {t['pick']['adp']:>6.1f} {t['reach_picks']:>7.1f}  {fl}")

    objected = [t for t in turns if t["objected"]]
    slot = [t for t in objected if "starter_aware" in t["changed_by"]]
    share = (len(slot) / len(objected)) if objected else 0.0

    counts_by_knob = {k: sum(1 for t in turns if k in t["changed_by"])
                      for k in variants if k != "shipped"}
    obj_by_knob = {k: sum(1 for t in objected if k in t["changed_by"])
                   for k in variants if k != "shipped"}

    print(f"\n=== attribution over {len(objected)} objected picks (of {len(turns)}) ===")
    for k, v in sorted(obj_by_knob.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<14} changes {v:>2}/{len(objected)} objected   "
              f"({counts_by_knob[k]:>2}/{len(turns)} of all picks)")

    verdict = ("CONFIRMED" if share >= 0.50 else "DEAD" if share < 0.25 else "INCONCLUSIVE")
    print(f"\nB1 slot-driven share = {share:.0%}  ->  {verdict}"
          f"   (>=50% confirms, <25% kills the slot hypothesis)")

    def _m(path: str) -> float:
        vals = [t["context_magnitude"][path] for t in turns
                if t["context_magnitude"][path] is not None]
        return float(np.mean(vals)) if vals else float("nan")

    ctx_ratio, ctx_max = _m("ratio_sd"), _m("context_delta_absmax")
    ctx_cont, ctx_spread = _m("ratio_contended"), _m("contended_spread")
    print("\n=== how big is the step-3 context term, in priority-rank units ===")
    print(f"  vs the WHOLE pool:  sd(context)/sd(eff) = {ctx_ratio:.2f}"
          f"   |context|max = {ctx_max:.1f} ranks")
    print(f"  vs the CONTENDED top-{CONTENDED_K}: spread = {ctx_spread:.1f} ranks, "
          f"|context|max = {_m('context_delta_absmax_contended'):.1f} ranks"
          f"  ->  ratio {ctx_cont:.2f}")
    print(f"  (n_teams multiplier = {n_room}; T33 says this should be the LEAGUE size)")

    # ★ The user's own criterion, made numeric: he labelled reaches bad and falls good. So ask
    # each knob what it does to the reach, not merely whether it changes the name.
    reach_by_knob = {}
    shipped_reach = float(np.mean([t["reach_picks"] for t in turns]))
    for k in variants:
        if k == "shipped":
            continue
        r = [t["alternatives"][k]["adp"] - t["overall_pick"] for t in turns]
        reach_by_knob[k] = {"mean_reach": float(np.mean(r)),
                            "delta_vs_shipped": float(np.mean(r) - shipped_reach)}
    print("\n=== what each knob does to the REACH (his stated criterion) ===")
    print(f"  shipped        mean reach {shipped_reach:+6.1f} picks")
    for k, v in sorted(reach_by_knob.items(), key=lambda kv: kv[1]["mean_reach"]):
        print(f"  {k:<14} mean reach {v['mean_reach']:+6.1f} picks   "
              f"({v['delta_vs_shipped']:+.1f} vs shipped)")

    static = _static_verdict_read()
    if static.get("available"):
        print("\n=== his own verdicts vs reach, on the artifact he judged (static) ===")
        for v, m in static["mean_reach_by_verdict"].items():
            print(f"  {v:<8} mean reach {m:+6.1f} picks")
        if static["corr_reach_vs_bad"] is not None:
            print(f"  corr(reach, labelled-bad) = {static['corr_reach_vs_bad']:+.3f} "
                  f"on {static['n_bad']} bad / {static['n_good']} good")

    out = {
        "generated": pd.Timestamp.utcnow().isoformat(),
        "label": args.label,
        "season": args.season,
        "board_vintage": vintage,
        "board_rows": int(len(board)),
        "asof": args.asof,
        "room": [p.name for p in room],
        "value_hawk_seat": vh_seat,
        "config": {"seed": args.seed, "room_seed": args.room_seed, "rounds": args.rounds,
                   "n_teams": 10, "premium_early_before_round": PREMIUM_EARLY_BEFORE_ROUND,
                   "single_slot_positions": list(SINGLE_SLOT)},
        "turns": turns,
        "n_picks": len(turns),
        "n_objected": len(objected),
        "slot_driven_share": share,
        "b1_verdict": verdict,
        "changed_by_knob_all_picks": counts_by_knob,
        "changed_by_knob_objected": obj_by_knob,
        "context_magnitude_mean": {
            "ratio_sd": ctx_ratio, "absmax_ranks": ctx_max,
            "contended_k": CONTENDED_K, "contended_spread": ctx_spread,
            "absmax_ranks_contended": _m("context_delta_absmax_contended"),
            "ratio_contended": ctx_cont, "n_teams_multiplier": n_room},
        "shipped_mean_reach": shipped_reach,
        "reach_by_knob": reach_by_knob,
        "static_verdict_read": static,
        "bars": {"B1": {"pass": verdict != "DEAD", "slot_driven_share": share,
                        "verdict": verdict}},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
