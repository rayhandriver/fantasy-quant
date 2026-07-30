"""Phase 16.17 done-bar — the seat map: **multi-seat human control**.

    uv run python steps/phase16_17_seat_map.py [--seasons 2022 2024 2026] [--seeds 6]

Writes ``analysis/phase16_17_seat_map.json``.

**What this substep changed, and what it deliberately did not.** "Which seat is the human" was a
single int (``DraftState.your_team``) and the ``team -> seat`` mapping was positional arithmetic —
``seat = team - 1 if team > your_team else team`` — written out in four places. That arithmetic is
correct for **exactly one** human seat, so the engine supported exactly two room shapes (1 human +
9 personalities, or 0 humans + 10) and every k in between was unreachable. 16.17 replaces all four
copies with one :class:`~fantasy_quant.draft.personalities.SeatMap`, adds
``DraftState.human_teams`` and per-seat pick functions, and **refits nothing**: no fitted β, no
frozen contract, no lockbox.

★ **Because it changes no model, the hard bar is BIT-IDENTITY** — the H.5 rule, *a plumbing change
that moves a bar is not a plumbing change*. Bars 1 and 2 below run the **deleted** arithmetic
(re-implemented verbatim in this file as ``_legacy_*``) against the shipped code over real boards
and require the pick logs to match pick for pick.

⚠ **And bar 3 is the control on the control.** T31 shipped a before/after that ran post-fix code
twice and produced identical hashes — *indistinguishable from "nothing moved"*. So before bars 1
and 2 are believed, the same comparison is run against a **deliberately mis-seated** legacy room
and must report a difference. *Assert the control can produce a known difference before trusting
it to show none.*

The third bar the substep owes — the room bar sheet reproduced to the digit — is a separate, slower
run, so it is *checked* here (``--verify-bars``) rather than re-measured. Produce it with
``steps/mock_room_bars.py --shuffle-room``: that is the flag the committed sheet was generated
with, and without it 149 gate-side fields differ and it looks like a regression that is not one.

⚠ **And pass ``--control-bars`` too, because the committed reference is no longer clean.**
``analysis/mock_room_bars_verify_20260729.json`` was produced against the **2026-07-24** FFC board;
the Stage-0 chore has since banked a 07-30 board and T31 bumped ``ENRICH_VERSION``, rebuilding all
nine 16.13 caches against it. So its ``readout_2026`` block legitimately moved — 79 of 628 fields,
every one of them in the live-board readout or in ``config`` provenance, and **0 of the 412 gate
fields**, which run on 2017–2024. The comparison that actually isolates this substep is against a
sheet produced by the *pre-16.17* code on **today's** board (a ``git worktree`` at the pre-change
commit + ``PYTHONPATH=<wt>/src``): that one is bit-identical on **all 628 fields**.
*A committed artifact is a control only while nothing else it depends on has moved.*
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
    make_opponent_pick_fn,
    make_room,
    make_room_pick_fn,
    make_value_hawk_pick_fn,
    normalized_hype_gains,
)
from fantasy_quant.draft.simulator import (
    RosterSlots,
    pick_by_adp,
    simulate_draft,
)

DB = Path("data/fantasy_quant.duckdb")
CACHE = Path("analysis/cache")
OUT = Path("analysis/phase16_17_seat_map.json")

#: One DEV season, one lockbox-era season and the live board — the mapping is board-independent, so
#: this is breadth against a coincidence rather than a statistical sample.
SEASONS: tuple[int, ...] = (2022, 2024, 2026)

#: The k values the new capability is exercised at: none, the old shape, several, all-but-one, all.
K_VALUES: tuple[int, ...] = (0, 1, 4, 9, 10)

#: The shipped room minus one ``balanced`` — the nine seats a human has actually faced since
#: 16.14R (``steps/mock_draft.py::REALISTIC_NINE``, restated rather than imported so this done-bar
#: does not depend on a driver).
SHIPPED_NINE: tuple[str, ...] = tuple(
    n for i, n in enumerate(REALISTIC_ROOM)
    if not (n == "balanced" and i == REALISTIC_ROOM.index("balanced")))


# ==================================================================================================
# the deleted arithmetic, re-implemented verbatim — the control for bars 1 and 2
# ==================================================================================================
def _legacy_fns(model, room, *, hype=None, normalize_hype=True, risk=None, **kw):
    """The per-seat function list both deleted builders shared, unchanged."""
    seats = tuple(room)
    gains = (normalized_hype_gains(seats) if normalize_hype
             else np.array([p.hype_gain for p in seats], float))
    return [
        (make_value_hawk_pick_fn(replace(p, hype_gain=float(g)), risk, n_teams=len(seats))
         if p.objective == "portfolio_ce" and risk is not None
         else make_opponent_pick_fn(model, replace(p, hype_gain=float(g)), hype=hype, **kw))
        for p, g in zip(seats, gains, strict=True)
    ]


def _legacy_room_pick_fn(model, room, *, offset: int = 0, **kw):
    """``personalities.make_room_pick_fn`` as it stood before 16.17 (k=1 only).

    ``offset`` is bar 3's poison: it rotates the ``team -> seat`` mapping so the control is known
    to differ. It is not a variant anything ever shipped.
    """
    fns = _legacy_fns(model, room, **kw)

    def pick(state, team) -> int:
        seat = team - 1 if team > state.your_team else team
        seat = (seat + offset) % len(fns)
        if not 0 <= seat < len(fns):
            raise ValueError(f"team {team} maps to seat {seat}")
        return fns[seat](state, team)

    return pick


def _legacy_full_room_pick_fn(model, room, **kw):
    """``mock.full_room_pick_fn`` as it stood before 16.17 (k=0 only): the identity mapping."""
    fns = _legacy_fns(model, room, **kw)

    def pick(state, team) -> int:
        if not 0 <= team < len(fns):
            raise ValueError(f"team {team} has no seat in a {len(fns)}-seat room")
        return fns[team](state, team)

    return pick


# ==================================================================================================
# helpers
# ==================================================================================================
def _picks(state) -> list[tuple]:
    """The pick log reduced to what a bit-identity claim is actually about."""
    return [(int(r["overall_pick"]), int(r["team"]), str(r["player_key"])) for r in state.log]


def _board_and_risk(con, season: int):
    board, src = mock.room_board(con, season, cache_dir=CACHE)
    if board.empty:
        return None, None, None
    config = DraftConfig()
    vi = optimizer.assemble_value(con, season, config)
    attached = optimizer.attach_value(board, vi)
    risk = optimizer.build_risk_model(attached, vi, optimizer.assemble_correlation(con, season),
                                      lam=config.risk_lambda, slots=config.league.slots)
    return attached, risk, src


def _run_k1(board, model, room, risk, *, seat: int, seed: int, rounds: int, legacy_offset=None):
    """One 10-team draft, nine personalities + you on the ADP autopicker at ``seat``.

    ``legacy_offset=None`` runs the shipped :func:`make_room_pick_fn`; an int runs the deleted
    arithmetic with that rotation (0 = the true legacy mapping, bar 3 uses 1).
    """
    opp = (make_room_pick_fn(model, room, risk=risk) if legacy_offset is None
           else _legacy_room_pick_fn(model, room, offset=legacy_offset, risk=risk))
    return simulate_draft(board, n_teams=10, rounds=rounds, seed=seed, your_team=seat,
                          slots=RosterSlots(), opponent_pick_fn=opp,
                          your_pick_fn=lambda st: pick_by_adp(st, st.your_team, noise=0.0))


def _run_k0(board, model, room, risk, *, seed: int, rounds: int, legacy: bool):
    """One 10-team draft with a personality in every seat."""
    if legacy:
        pick = _legacy_full_room_pick_fn(model, room, risk=risk)
        return simulate_draft(board, n_teams=10, rounds=rounds, seed=seed, your_team=0, noise=0.0,
                              slots=RosterSlots(), opponent_pick_fn=pick,
                              your_pick_fn=lambda st: pick(st, st.your_team))
    return mock.simulate_room_draft(board, room, model, n_teams=10, rounds=rounds, seed=seed,
                                    risk=risk)


def _legality_log(state, *, season: int, draft_id: str) -> pd.DataFrame:
    """One draft's pick log in the frame :func:`mock.roster_legality` reads."""
    log = state.pick_log()
    return log.assign(season=int(season), draft_id=str(draft_id),
                      seat_personality=log["seat_role"] if "seat_role" in log.columns else pd.NA)


# ==================================================================================================
# the bars
# ==================================================================================================
def bar_bit_identity(con, model, seasons, seeds: int, rounds: int) -> dict:
    """Bars 1–3: k=1 and k=0 reproduce the deleted arithmetic pick for pick, and the comparison
    that says so is shown to be capable of saying otherwise."""
    rows, diffs, poison_diffs = [], 0, 0
    for season in seasons:
        board, risk, _ = _board_and_risk(con, season)
        if board is None:
            print(f"  {season}: no board, skipped")
            continue
        # the two nine-seat rooms a human has ever faced: the pre-16.14R default and the shipped
        # room minus one `balanced` (steps/mock_draft.py's REALISTIC_NINE), plus the ten-seat
        # batch room. Different mixes so the mapping is not tested against one arrangement.
        nine = make_room(None)                                          # DEFAULT_ROOM, 9 seats
        shipped_nine = make_room(SHIPPED_NINE)
        ten = mock.full_room(REALISTIC_ROOM, n_teams=10, seed=17)
        for seed in range(seeds):
            seat = seed % 10
            for label, room in (("default9", nine), ("shipped9", shipped_nine)):
                new = _picks(_run_k1(board, model, room, risk, seat=seat, seed=seed,
                                     rounds=rounds))
                old = _picks(_run_k1(board, model, room, risk, seat=seat, seed=seed, rounds=rounds,
                                     legacy_offset=0))
                bad = new != old
                diffs += bad
                # bar 3 — the poisoned control, run on the same pair of code paths
                poison = _picks(_run_k1(board, model, room, risk, seat=seat, seed=seed,
                                        rounds=rounds, legacy_offset=1))
                poison_diffs += (poison != new)
                rows.append({"season": season, "k": 1, "room": label, "seat": seat, "seed": seed,
                             "identical": not bad, "poison_differs": poison != new})
            new0 = _picks(_run_k0(board, model, ten, risk, seed=seed, rounds=rounds, legacy=False))
            old0 = _picks(_run_k0(board, model, ten, risk, seed=seed, rounds=rounds, legacy=True))
            diffs += (new0 != old0)
            rows.append({"season": season, "k": 0, "room": "shipped10", "seat": None, "seed": seed,
                         "identical": new0 == old0, "poison_differs": None})
        print(f"  {season}: {seeds} seeds x (2 k=1 rooms + 1 k=0 room) compared", flush=True)
    tab = pd.DataFrame(rows)
    k1 = tab[tab["k"] == 1]
    return {
        "n_comparisons": int(len(tab)),
        "n_identical": int(tab["identical"].sum()),
        "n_different": int(diffs),
        "k1_identical": bool(k1["identical"].all()),
        "k0_identical": bool(tab[tab["k"] == 0]["identical"].all()),
        # bar 3: the control must be able to fail
        "poison_n": int(len(k1)),
        "poison_n_differ": int(poison_diffs),
        "poison_always_differs": bool(k1["poison_differs"].all()),
        "pass": bool(tab["identical"].all() and k1["poison_differs"].all()),
    }


def bar_capability(con, model, season: int, seeds: int, rounds: int) -> dict:
    """Bar 4: every k runs to completion with every seat legal, and a mix of the wrong length is
    refused **at construction** rather than at some pick that happens to map past the end.

    ⚠ **Legality is measured with T23's own ``supply`` argument, and gated on the AVOIDABLE
    share.** The naive version was written first and reported 90 illegal seats on 2022 — a board
    that carries **5** kickers and **6** defenses for a ten-seat room, so half those seats cannot
    finish with a kicker and no pick policy can conjure one. ``mock.roster_legality`` already knows
    this and says so in its own docstring: *a bar that cannot be passed teaches a team to ignore
    it.* The claim 16.17 is accountable for is that **multi-seat rooms are no less legal than the
    fully-simulated one on the same board**, which is what ``share_avoidable`` measures.
    """
    board, risk, _ = _board_and_risk(con, season)
    if board is None:
        return {"pass": False, "reason": f"no {season} board"}
    supply = {int(season): mock.board_supply(board)}
    rows, logs = [], []
    for k in K_VALUES:
        humans = tuple(range(k))
        mix = tuple(REALISTIC_ROOM)[:10 - k]
        sm = SeatMap.of(10, human_teams=humans, mix=mix, seed=17)
        assert sm.human_teams == frozenset(humans)
        assert len(sm.room()) == 10 - k
        for seed in range(seeds):
            opp = sm.pick_fn(model, risk=risk)      # None at k = n_teams
            st = simulate_draft(
                board, n_teams=10, rounds=rounds, seed=seed, slots=RosterSlots(),
                your_team=(humans[0] if humans else 0), human_teams=frozenset(humans),
                seat_roles=sm.roles(), opponent_pick_fn=opp,
                your_pick_fn={t: (lambda s, _t=t: pick_by_adp(s, _t, noise=0.0))
                              for t in humans} or None)
            logs.append(_legality_log(st, season=season, draft_id=f"k{k}_s{seed}"))
            rows.append({"k": k, "seed": seed, "n_picks": len(st.log),
                         "complete": st.is_done(),
                         "seat_role_logged": all("seat_role" in r for r in st.log)})
        # the length check is now stated once, at construction, for every k
        try:
            SeatMap.of(10, human_teams=humans, mix=mix + ("balanced",))
            refused = False
        except ValueError:
            refused = True
        rows[-1]["bad_mix_refused"] = refused
    tab = pd.DataFrame(rows)
    log = pd.concat(logs, ignore_index=True)
    legality = mock.roster_legality(log, supply=supply, n_teams=10)
    per_k = {}
    for k in K_VALUES:
        sub = log[log["draft_id"].str.startswith(f"k{k}_")]
        per_k[int(k)] = mock.roster_legality(sub, supply=supply, n_teams=10)["share_avoidable"]
    avoidable_ok = all(v <= 0.005 for v in per_k.values())
    return {
        "k_values": list(K_VALUES),
        "n_drafts": int(len(tab)),
        "all_complete": bool(tab["complete"].all()),
        "all_150_picks": bool((tab["n_picks"] == 10 * rounds).all()),
        "seat_role_logged": bool(tab["seat_role_logged"].all()),
        "bad_mix_refused": bool(tab["bad_mix_refused"].dropna().all()),
        "legality": {k: v for k, v in legality.items() if k != "by_personality"},
        "share_avoidable_by_k": {str(k): float(v) for k, v in per_k.items()},
        "avoidable_ok": bool(avoidable_ok),
        "pass": bool(tab["complete"].all() and (tab["n_picks"] == 10 * rounds).all()
                     and tab["seat_role_logged"].all() and avoidable_ok
                     and tab["bad_mix_refused"].dropna().all()),
    }


def bar_mapping_identity() -> dict:
    """Bar 5, free and exhaustive: :meth:`SeatMap.room_index` reproduces the deleted positional
    formula for **every** ``(n_teams, your_team, team)`` a single-human draft can have.

    A property check rather than a sample, because that is what the claim is: the general mapping
    *contains* the special case. Bars 1–3 then show the containment survives contact with the
    behaviour built on top of it.
    """
    lib_room = make_room()
    bad = []
    for n_teams in range(2, 15):
        room = (lib_room * 3)[:n_teams - 1]
        for your_team in range(n_teams):
            sm = SeatMap.of(n_teams, human_teams=(your_team,), room=room)
            for team in range(n_teams):
                got = sm.room_index(team)
                want = None if team == your_team else (team - 1 if team > your_team else team)
                if got != want:
                    bad.append((n_teams, your_team, team, got, want))
    return {"n_checked": sum(n * n for n in range(2, 15)), "n_mismatch": len(bad),
            "examples": bad[:5], "pass": not bad}


def _flat(d, prefix=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out |= _flat(v, f"{prefix}{k}.")
    elif isinstance(d, list):
        for i, v in enumerate(d):
            out |= _flat(v, f"{prefix}{i}.")
    else:
        out[prefix.rstrip(".")] = d
    return out


#: Sections of the bar sheet that are **not** gates, split out because they legitimately move
#: without any code change. ``readout_2026`` is the live board, which the sheet's own header calls
#: "an eyeball readout, never a gate" and which the Stage-0 chore refreshes;
#: ``config``/``generated``/``label`` are provenance about the run.
NON_GATE_SECTIONS: tuple[str, ...] = ("readout_2026", "config", "generated", "label")


def _diff(a: dict, b: dict) -> dict:
    return {k: [a.get(k), b.get(k)] for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)}


def verify_bars(new: Path, ref: Path, control: Path | None = None) -> dict:
    """Bar 6: the room bar sheet reproduces **to the digit**, field by field.

    ★ **Two comparisons, because the reference is not a clean control.** The 07-29 sheet was
    produced against the **2026-07-24** FFC board; since then the Stage-0 chore banked a 07-30 board
    and T31 bumped ``ENRICH_VERSION``, rebuilding all nine 16.13 caches — so ``readout_2026`` moved
    for reasons that have nothing to do with this substep, and ``config`` gained two provenance
    fields (``mix``, ``bench_weight``) that did not exist on 07-29. Comparing against it alone would
    make a plumbing change look like it moved something.

    So:

    * **against the 07-29 reference** the hard claim is restricted to the **gate** sections — the
      matched-season T15 bars, landing, legality, faithfulness, personality buckets — which are
      board-vintage-independent because they run on 2017–2024;
    * **against a ``control`` sheet** produced by the *pre-16.17* code on **today's** board, the
      claim is total: **every field**, readout included. That is the comparison that actually
      isolates this substep, and it is the one to trust.

    ⚠ Produce the control from a ``git worktree`` at the pre-change commit **with
    ``PYTHONPATH=<worktree>/src``** — ``uv run --project <main>`` resolves the *editable* install to
    the main tree's ``src``, which is how T31's before/after ran post-fix code twice and reported
    identical hashes. Assert the control imports the old module (it must NOT have ``SeatMap``)
    before believing it.
    """
    if not new.exists():
        return {"pass": None, "reason": f"{new} not produced yet — run steps/mock_room_bars.py "
                                        f"--label <x> --shuffle-room"}
    b = _flat(json.loads(new.read_text()))
    a = _flat(json.loads(ref.read_text()))
    gate = {k for k in set(a) | set(b) if k.split(".")[0] not in NON_GATE_SECTIONS}
    d_ref = _diff(a, b)
    d_gate = {k: v for k, v in d_ref.items() if k in gate}
    out = {"reference": str(ref), "candidate": str(new),
           "n_gate_fields": len(gate), "n_fields": len(set(a) | set(b)),
           "vs_reference_gate_different": len(d_gate),
           "vs_reference_all_different": len(d_ref),
           "gate_differences": dict(list(d_gate.items())[:20]),
           "non_gate_differences": dict(list({k: v for k, v in d_ref.items()
                                              if k not in gate}.items())[:8]),
           "gate_identical": not d_gate}
    if control is not None and control.exists():
        c = _flat(json.loads(control.read_text()))
        d_ctl = {k: v for k, v in _diff(c, b).items()
                 if k.split(".")[0] not in ("generated", "label")}
        out |= {"control": str(control), "vs_control_different": len(d_ctl),
                "control_differences": dict(list(d_ctl.items())[:20]),
                "control_identical": not d_ctl}
    elif control is not None:
        out |= {"control": str(control), "control_identical": None,
                "reason": f"{control} not produced yet"}
    hard = [out["gate_identical"]] + ([out["control_identical"]]
                                      if out.get("control_identical") is not None else [])
    out["pass"] = bool(all(hard))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seasons", type=int, nargs="*", default=None)
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--verify-bars", type=Path, default=None,
                    help="a mock_room_bars sheet produced with --shuffle-room, to diff against "
                         "analysis/mock_room_bars_verify_20260729.json")
    ap.add_argument("--control-bars", type=Path, default=None,
                    help="the same sheet produced by the PRE-16.17 code on today's board (a git "
                         "worktree + PYTHONPATH=<wt>/src) — the comparison that isolates 16.17")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    seasons = tuple(args.seasons) if args.seasons else SEASONS

    con = duckdb.connect(str(DB), read_only=True)
    model = mock.load_opponent_model()

    print("=== 16.17 — THE SEAT MAP ===")
    print("\n[5] the mapping contains the deleted formula (exhaustive)")
    b5 = bar_mapping_identity()
    print(f"  {b5['n_checked']} (n_teams, your_team, team) triples · "
          f"{b5['n_mismatch']} mismatches -> {'PASS' if b5['pass'] else 'FAIL'}")

    print(f"\n[1-3] bit-identity vs the deleted arithmetic · seasons {seasons}")
    b13 = bar_bit_identity(con, model, seasons, args.seeds, args.rounds)
    print(f"  {b13['n_comparisons']} draft pairs · {b13['n_different']} differ  "
          f"(k=1 {'OK' if b13['k1_identical'] else 'FAIL'} · "
          f"k=0 {'OK' if b13['k0_identical'] else 'FAIL'})")
    print(f"  control-can-fail: {b13['poison_n_differ']}/{b13['poison_n']} poisoned runs differ "
          f"-> {'PASS' if b13['poison_always_differs'] else 'FAIL — the control proves nothing'}")

    print(f"\n[4] the new capability · k in {list(K_VALUES)} on {seasons[-1]}")
    b4 = bar_capability(con, model, seasons[-1], max(2, args.seeds // 2), args.rounds)
    print(f"  {b4.get('n_drafts')} drafts · all complete {b4.get('all_complete')} · "
          f"wrong-length mix refused {b4.get('bad_mix_refused')}")
    if "legality" in b4:
        print(f"  legality: raw illegal {b4['legality']['share_illegal']:.1%} "
              f"(board supply), AVOIDABLE {b4['legality']['share_avoidable']:.2%} · per k "
              + " ".join(f"k{k}={v:.2%}" for k, v in b4["share_avoidable_by_k"].items()))
    print(f"  -> {'PASS' if b4['pass'] else 'FAIL'}")

    b6 = (verify_bars(args.verify_bars, Path("analysis/mock_room_bars_verify_20260729.json"),
                      args.control_bars)
          if args.verify_bars else
          {"pass": None, "reason": "not requested (pass --verify-bars <sheet>)"})
    if b6["pass"] is not None:
        print("\n[6] the room bar sheet")
        print(f"  vs the 07-29 reference: {b6['vs_reference_gate_different']}/"
              f"{b6['n_gate_fields']} GATE fields differ "
              f"({b6['vs_reference_all_different']}/{b6['n_fields']} incl. the live-board readout "
              f"+ config provenance, which move with the board vintage, not with the code)")
        for k, (x, y) in list(b6["gate_differences"].items())[:10]:
            print(f"      GATE {k}: {x} -> {y}")
        if b6.get("control_identical") is None:
            print("  ⚠ no pre-16.17 control sheet — the reference alone cannot isolate this "
                  "substep from the board refresh")
        else:
            print(f"  vs the PRE-16.17 control on today's board: "
                  f"{b6['vs_control_different']}/{b6['n_fields']} fields differ "
                  f"-> {'BIT-IDENTICAL' if b6['control_identical'] else 'MOVED'}")
            for k, (x, y) in list(b6["control_differences"].items())[:10]:
                print(f"      {k}: {x} -> {y}")
        print(f"  -> {'PASS' if b6['pass'] else 'FAIL'}")
    else:
        print(f"\n[6] the room bar sheet: {b6['reason']}")

    con.close()
    hard = [b5["pass"], b13["pass"], b4["pass"]] + ([b6["pass"]] if b6["pass"] is not None else [])
    result = {"seasons": list(seasons), "seeds": args.seeds, "rounds": args.rounds,
              "bar1_3_bit_identity": b13, "bar4_capability": b4, "bar5_mapping": b5,
              "bar6_room_bar_sheet": b6, "pass": bool(all(hard))}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, default=str))
    print(f"\n  -> {args.out}   OVERALL {'PASS' if result['pass'] else 'FAIL'}")


if __name__ == "__main__":
    main()
