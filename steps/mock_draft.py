"""Interactive mock draft — you at **any number of seats**, personalities at the rest.

    uv run python steps/mock_draft.py start --seat 7 [--room a,b,..] [--teams 10] [--seed 7]
                                 # --room defaults to the SHIPPED room (REALISTIC_ROOM, minus one
                                 # `balanced` seat per human seat, which is the one you take)
    uv run python steps/mock_draft.py start --seats 3,7 --auto 7
                                 # 16.17: drive two teams; hand seat 7 to the ADP autopicker
    uv run python steps/mock_draft.py board [--pos RB] [--n 20]
    uv run python steps/mock_draft.py pick "Bijan" [--team 3]
    uv run python steps/mock_draft.py why "Maye"      # PROJ -> BASE_VALUE, the whole chain
    uv run python steps/mock_draft.py roster [--team 3]
    uv run python steps/mock_draft.py drift          # your draft in the corpus's own units
    uv run python steps/mock_draft.py finish         # autodraft every remaining human pick by ADP
    uv run python steps/mock_draft.py summary [--odds]   # --odds -> Phase-10 season odds
    uv run python steps/mock_draft.py stats [BUST]   # 14.O: what a column means, with examples

Promoted from a session scratchpad, where it was written to let the user draft against the room one
pick at a time — **and it immediately found a defect no automated gate had** (T15: the room's
reaches and falls are impossible; ``findings.md`` §"Live mock draft (2026-07-27)"). That is the
argument for it living in ``steps/`` rather than being rewritten each time: *every subsystem needs
one bar a domain expert could fail by eye, and this is that bar for the draft room.*

Thin over the real engine — there is no modelling here:
  board      ``mock.room_board``      (FFC ADP + 16.13 read-only enrichment)
  opponents  ``personalities``        on the fitted 11.1 β
  seats      ``personalities.SeatMap`` — the one ``team -> seat`` mapping (16.17)
  mechanics  ``DraftState``/``_apply_pick``, one pick at a time instead of ``run_to_completion``
  drift      ``mock.sim_drift_panel`` — the same frame ``steps/t15_0_baseline.py`` measures

★ **Session K1 — this file is now a RENDERER.** Every derived frame it prints comes from
:mod:`fantasy_quant.draft.session`, which the Streamlit app reads too. The functions here decide
column widths and where the arrows point; they do not decide what a number is. That is deliberate
and it is the T18/F.5/T27 rule applied before the fact: two surfaces computing the same quantity is
how the two drift apart, so *there is one computation and two renderers*. If you are about to
compute something in this file, it belongs in ``session.py``.

State is pickled between invocations so a draft survives across shell calls (and chat turns); the
opponents' rng lives in ``DraftState``, so the room stays reproducible from ``--seed``.

★ **16.17 — ``--seats`` drives k of the n teams.** This driver used to hardwire the
**nine-opponents-plus-you** shape because the engine had no other: the human seat was a single int
and ``team -> seat`` was positional arithmetic correct only at k=1. Any k now works, including k=0
(a fully simulated room, the batch harness's shape, which is
:func:`fantasy_quant.draft.mock.full_room`) and k=n.

⚠ **Two honesty rules the readouts state, and this docstring restates because they are easy to
lose:** (1) **k teams in one draft are ONE observation** — every pick you make removes a player
from your other seats' pools, so their outcomes are mechanically anti-correlated; ``summary``
prints them per seat and never averages them or reports a combined record. (2) **The T15 realism
bars describe a fully-simulated room** — profile distance, dispersion and the elite-fall landing
were measured with ten *modelled* seats, so ``drift`` labels its scope rather than re-measuring
them for a room you are sitting in.
"""

from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from fantasy_quant.draft import mock, session
from fantasy_quant.draft.config import DraftConfig
from fantasy_quant.draft.personalities import SeatMap
from fantasy_quant.draft.session import (
    REALISTIC_NINE,
    advance,
    auto_teams,
    realistic_mix,
    room_from,
    room_mix,
    seat_label,
    seat_map_from,
)
from fantasy_quant.draft.simulator import (
    DraftState,
    RosterSlots,
    _apply_pick,
    _prepare_board,
    pick_by_adp,
    run_to_completion,
)

__all__ = ["REALISTIC_NINE", "advance", "auto_teams", "realistic_mix", "room_from", "room_mix",
           "seat_label", "seat_map_from"]

DB = Path("data/fantasy_quant.duckdb")
STATE = Path("data/interim/mock/draft_state.pkl")
CACHE = Path("analysis/cache")


def _con():
    return duckdb.connect(str(DB), read_only=True)


def build_board(season: int = 2026, teams: int = 10) -> tuple[pd.DataFrame, pd.DataFrame, object]:
    """``(board, value_index, risk)`` — :func:`session.build_board`, opened and announced.

    The build itself moved to ``session.py`` (Session K1) so the app gets the *same* board, value
    index and risk model rather than an independently-assembled lookalike. What stays here is the
    connection and the one printed line.
    """
    con = _con()
    try:
        built = session.build_board(season=season, teams=teams, con=con, cache_dir=CACHE)
    except LookupError as exc:
        raise SystemExit(str(exc)) from None
    finally:
        con.close()
    print(f"  board: {len(built['board'])} players ({built['source']} ADP + frozen Phase-4/5 "
          f"context) · {built['n_base_value']} carry base_value · λ={built['lam']}")
    return built["board"], built["value_index"], built["risk"]


# ---------------------------------------------------------------------------------- state io
def save(st: DraftState, meta: dict, vi: pd.DataFrame | None = None, risk=None) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_bytes(pickle.dumps({"state": st, "meta": meta, "vi": vi, "risk": risk}))


def load() -> tuple[DraftState, dict, pd.DataFrame | None, object]:
    """``(state, meta, value_index, risk)``. The value index and risk model are pickled with the
    draft rather than rebuilt per invocation: rebuilding costs a ``value_board`` + a Phase-5 cloud
    (~10 s) on **every** ``pick``, and — worse — a rebuild that silently disagreed with the board
    the draft started on would reintroduce exactly the two-scales defect T27 closes."""
    if not STATE.exists():
        raise SystemExit("no draft in progress — run `start` first")
    d = pickle.loads(STATE.read_bytes())
    return d["state"], d["meta"], d.get("vi"), d.get("risk")


# ---------------------------------------------------------------------------------- display
# `REALISTIC_NINE`, `realistic_mix`, `room_mix`, `room_from`, `seat_map_from`, `seat_label`,
# `auto_teams` and `advance` moved to `draft/session.py` in Session K1 and are re-exported above:
# the app drives the same room through the same SeatMap, and a second copy of the room-composition
# rule is precisely how the shipped mix and the interactive mix would come apart (T27, one level
# up).
# The only adaptation is at the boundary — `session` raises `ValueError`, this CLI exits.
def fmt_pick(r: dict, sm: SeatMap) -> str:
    return (f"  {r['round']:>2}.{r['pick_in_round']:02d}  {'T' + str(r['team'] + 1):<4}"
            f"{seat_label(r['team'], sm):<15}{r['player_name'][:23]:<24}{r['pos']:<4}"
            f"(ADP {r['adp']:.1f})")


def show_available(st: DraftState, n: int = 18, pos: str | None = None,
                   team: int | None = None) -> None:
    """The best-available table. Columns and their meaning: :data:`session.BOARD_VIEW_COLS`.

    ★ T27 — the value chain reads left to right in the order the arithmetic runs: ``PROJ`` the
    consensus projection a human trusts, ``MEAN`` the Phase-5 season mean (PROJ x availability),
    ``AVAIL`` the games-played read that explains the gap, ``BV`` the ``base_value`` every seat's
    utility actually runs on. On the 2026 board PROJ and BV disagree by up to 179 points (Drake
    Maye +68.5 vs Jayden Daniels −101.6, three points apart on screen); ``why`` prints the chain.

    ⚠ T22 — ``BOOM``/``BUST`` are the **live** pair, and a player we have never seen play prints
    ``-`` rather than a fabricated ``0.00`` (which reads as *never busts*).
    """
    view = session.board_view(st, team=team, pos=pos, n=n)
    fmt = {"ADP": ">6.1f", "PROJ": ">6.0f", "MEAN": ">6.0f", "AVAIL": ">6.1f", "BV": ">+7.0f",
           "VBD": ">6.0f", "RK": ">5.0f", "UPSIDE": ">+7.2f", "FLOOR": ">+7.2f",
           "TAIL": ">+7.2f", "BOOM": ">6.2f", "BUST": ">6.2f"}
    print(f"  {'#':<5}{'PLAYER':<22}{'POS':<4}{'ADP':>6}{'PROJ':>6}{'MEAN':>6}{'AVAIL':>6}"
          f"{'BV':>7}{'VBD':>6}{'RK':>5}{'UPSIDE':>7}{'FLOOR':>7}{'TAIL':>7}{'BOOM':>6}{'BUST':>6}")
    for idx, r in view.iterrows():
        cells = "".join(
            format(r[c], f) if pd.notna(r[c]) else format("-", f">{f.split('.')[0][1:]}")
            for c, f in fmt.items())
        print(f"  {idx:<5}{str(r['PLAYER'])[:21]:<22}{str(r['POS']):<4}{cells}")


def explain(board: pd.DataFrame, vi: pd.DataFrame, query: str, lam: float) -> None:
    """``why "<player>"`` — the arithmetic chain from the number a human trusts to the number the
    engine uses (T27 step 1c, the session's real product deliverable).

    Every line is an identity, not a re-derivation: ``lambda*Var`` is printed as ``mean - ce_value``
    and the positional replacement as ``ce_value - ce_vbd``, so what is shown is what the frozen
    Phase-4/5 stack actually computed rather than a display-layer reimplementation of it that could
    drift away from it. That is the whole point of the command — an auditable path, not a caption.
    """
    entries = session.explain_chain(board, vi, query, lam)
    if not entries:
        print(f"no player on the board matching {query!r}")
        return
    if len(entries) > 6:
        print(f"{len(entries)} matches — be more specific")
        return
    for e in entries:
        print(f"\n=== {e['name']} ({e['pos']}, ADP {e['adp']:.1f}) ===")
        if not e["ok"]:
            print(f"  {e['reason']}")
            continue
        for r in e["rows"]:
            shown = "" if r["value"] is None else format(r["value"], ">10.1f")
            print(f"  {r['label']:<36}{shown:>10}   {r['note']}".rstrip())


def show_roster(st: DraftState, team: int) -> None:
    r = session.roster_view(st, team)
    if r.empty:
        print("  (empty)")
        return
    for _, p in r.iterrows():
        pp = p["proj_points"]
        shown = f"{pp:.0f}" if pd.notna(pp) else "-"
        print(f"  {p['pos']:<4}{str(p['player_name'])[:24]:<26}ADP {p['adp']:>6.1f}"
              f"  proj {shown:>4}")
    print(f"  {'':<4}{'TOTAL (consensus proj pts)':<26}{'':>10}  {session.roster_total(r):>9.0f}")


def report_turn(st: DraftState, meta: dict, made: list[dict], n: int = 18,
                pos: str | None = None, vi: pd.DataFrame | None = None) -> None:
    sm = seat_map_from(meta)
    if made:
        print(f"\n--- {len(made)} picks since your last turn ---")
        for r in made:
            print(fmt_pick(r, sm))
    if st.is_done() or not st.available:
        print("\n=== DRAFT COMPLETE ===")
        summary(st, meta, vi)
        return
    team = st.team_on_clock()
    print(f"\n=== ON THE CLOCK: {seat_label(team, sm)} — T{team + 1}, round {st.round()}, "
          f"pick {st.pick_in_round()} (#{st.overall_pick} overall) ===")
    if len(sm.human_teams) > 1:
        others = ", ".join(f"T{t + 1}" for t in sorted(sm.human_teams - {team}))
        print(f"  (you also drive {others} — `pick` applies to the seat on the clock; "
              f"`--team` overrides, `roster --team` / `board --team` read another seat)")
    print(f"\n  ROSTER — T{team + 1}")
    show_roster(st, team)
    needs = st.starter_needs(team)
    print("  starter needs: " + ", ".join(f"{k} {v}" for k, v in needs.items() if v))
    print("\n  BEST AVAILABLE")
    show_available(st, n=n, pos=pos, team=team)


def summary(st: DraftState, meta: dict, vi: pd.DataFrame | None = None) -> None:
    """The post-draft readout.

    ★ **T28 2b — every team-level number appears twice, labelled.** ``STARTABLE`` is
    :func:`~fantasy_quant.draft.optimizer.starter_value` (the best legal starting lineup's
    ``base_value``); ``CAPITAL`` is ``team_value``, the slot-blind sum over all fifteen rows that
    prices a bench QB2 as though he starts. On the 2026 walkthrough those two disagreed by −122
    points on the QB2 line alone, which is how a team could sit 9th of 10 on one and 3rd on the
    other. Neither is deleted and neither is silently renamed: ``team_value`` is what the frozen
    cost report differences, so it stays exactly what it was.

    ★ **16.17 — one block per human seat, never a combined line.** With k seats you get k blocks
    and no average, because **k human teams in one draft are ONE observation**: your picks deplete
    each other's pools, so the seats' outcomes are mechanically anti-correlated and four teams
    going 4-for-4 on a strategy is a single draw. That is the honesty rule the substep owns, and it
    is enforced here by simply not having a place to put a combined number.
    """
    sm = seat_map_from(meta)
    print("\n=== FINAL ROSTERS ===")
    tab = session.summary_table(st, sm, vi)
    has_bv = "startable" in tab.columns
    head = f"  {'RANK':<6}{'TEAM':<6}{'PERSONALITY':<16}{'TOP-9 PROJ':>12}{'FULL ROSTER':>13}"
    print(head + (f"{'STARTABLE':>11}{'CAPITAL':>10}" if has_bv else ""))
    for _, r in tab.iterrows():
        star = "  <-- you" if r["human"] else ""
        extra = f"{r['startable']:>11.0f}{r['capital']:>10.0f}" if has_bv else ""
        print(f"  {int(r['rank']):<6}{'T' + str(int(r['team'])):<6}{r['who']:<16}"
              f"{r['starters']:>12.0f}{r['proj']:>13.0f}{extra}{star}")
    print("\n  (Top-9 proj = the 9 best consensus projections on the roster — a rough")
    print("   team-strength readout, not the Phase-10 season sim. Projected-points rankings")
    print("   are DESCRIPTIVE:")
    print("   scoring our own seats on our own board wins by construction — see findings.md.)")
    if has_bv:
        print("  (STARTABLE = best legal starting lineup's base_value; CAPITAL = the slot-blind")
        print("   sum over all 15 rows, which prices a bench QB2 as if he started. T28.)")
    for t in sorted(sm.human_teams):
        print(f"\n  YOUR TEAM — T{t + 1}")
        show_roster(st, t)
    if len(sm.human_teams) > 1:
        print(f"\n  (These {len(sm.human_teams)} teams are ONE observation, not "
              f"{len(sm.human_teams)}: every pick you made removed a player from your other")
        print("   seats' pools, so their outcomes are mechanically anti-correlated. Read them")
        print("   side by side; do NOT average them or count a record across them. 16.17.)")


def league_odds(st: DraftState, meta: dict, sims: int = 400) -> None:
    """Playoff/title odds for the finished league, **led by the fair-share multiple** (T29).

    A bare "17.0 % to win the league" is the weakest number in the stack wearing the most
    authoritative costume: the lockbox certified the *ordering* (title Brier 0.088, reliability
    on-diagonal) but recorded playoff Brier 0.240 as marginal, over a sim with a documented
    −113 pts/team level bias. A ratio to the uniform is immune to that bias because it moves all
    ten teams together, so ``1.70x`` is a claim the evidence supports and ``17.0 %`` is not.
    """
    sm = seat_map_from(meta)
    con = _con()
    try:
        tab, prov = session.odds_table(con, st, meta, sm, sims=sims)
    finally:
        con.close()
    print("\n=== SEASON ODDS (Phase-10 sim) ===")
    print("\n".join(prov))
    print(f"\n  {'TEAM':<6}{'PERSONALITY':<16}{'PLAYOFF':>9}{'vs FAIR':>9}"
          f"{'TITLE':>9}{'vs FAIR':>9}")
    for _, r in tab.iterrows():
        star = "  <-- you" if r["human"] else ""
        print(f"  {'T' + str(int(r['team'])):<6}{r['who']:<16}{r['playoff']:>8.1%}"
              f"{r['playoff_fair']:>8.2f}x{r['title']:>9.1%}{r['title_fair']:>8.2f}x{star}")
    if len(sm.human_teams) > 1:
        print("\n  (Your seats' probabilities are NOT independent and do not add up to your")
        print("   chance of winning the league — the sim runs one league in which they play each")
        print("   other. 16.17.)")


# ---------------------------------------------------------------------------------- commands
def human_seats(a) -> list[int]:
    """``--seats 3,7`` (1-indexed, 16.17) or the single ``--seat``, as 0-indexed teams.

    The **first listed** seat is the primary one — ``DraftState.your_team`` — because that is the
    seat the frozen cost report, the 9.5 objective, best-ball and MCTS all read, and none of them
    should learn that a second human exists.
    """
    raw = a.seats if getattr(a, "seats", None) else str(a.seat)
    try:
        seats = session.parse_seats(str(raw))
    except ValueError as exc:
        raise SystemExit(str(exc).replace("seats wants", "--seats wants")) from None
    if not seats:
        raise SystemExit("--seats needs at least one seat (or use --seats '' for a 0-human room)")
    return seats


def cmd_start(a) -> None:
    board, vi, risk = build_board(season=a.season, teams=a.teams)
    # T27 1a: `proj_points` and `base_value` are `simulator.PASSTHROUGH_COLS` now, so they ride
    # through `_prepare_board` with everything else. The hand-rolled re-attach that used to sit
    # here is deleted rather than duplicated — it was the visible half of the two-scales defect.
    b = _prepare_board(board)
    seats = [] if a.seats == "" else human_seats(a)
    fav = tuple(x.strip().upper() for x in (a.fav or "").split(",") if x.strip())
    mix = room_mix(a.room, n_humans=len(seats), n_teams=a.teams)
    # 16.17: `SeatMap.of` is the only length check — `n_teams - k`, not `n_teams - 1`.
    sm = SeatMap.of(a.teams, human_teams=seats, mix=mix, seed=a.room_seed, fav_teams=fav)
    auto = sorted({int(x.strip()) - 1 for x in (a.auto or "").split(",") if x.strip()})
    if set(auto) - set(seats):
        raise SystemExit(f"--auto {sorted(t + 1 for t in set(auto) - set(seats))} are not your "
                         f"seats; --auto hands one of YOUR seats to the ADP autopicker")
    primary = seats[0] if seats else 0
    # ⚠ T34 — the CLI's defaults do NOT move. `--seed 7` and `--room-seed` unset are what T24's
    # sweep, 16.17's 1,014-triple mapping check and every committed bar sheet are differenced
    # against; the entropy default belongs to the app (`app/engine.draw_seeds`) and stops there.
    # `room_seed` is recorded in `meta` on both surfaces so an exported draft carries the same keys
    # either way — a key on one side and not the other is how a resumed draft changes rooms.
    meta = {"your_team": primary, "human_teams": seats, "auto": auto,
            "room": [p.name for p in sm.room()], "teams": a.teams, "rounds": a.rounds,
            "fav": list(fav), "seed": a.seed, "room_seed": a.room_seed, "season": a.season}
    st = DraftState(board=b, n_teams=a.teams, rounds=a.rounds, slots=RosterSlots(),
                    your_team=primary, rng=np.random.default_rng(a.seed), noise=5.0,
                    available=set(b.index), rosters=[[] for _ in range(a.teams)],
                    human_teams=frozenset(seats), seat_roles=sm.roles())
    yours = ", ".join(str(t + 1) for t in seats) or "none (fully simulated room)"
    print(f"=== MOCK DRAFT — {a.teams}-team full-PPR snake, {a.rounds} rounds, "
          f"you pick {yours} ===")
    print("  the room:")
    for t in range(a.teams):
        tag = "  [autopick]" if t in auto else ""
        print(f"    T{t + 1:<3} {seat_label(t, sm)}{tag}")
    if len(seats) > 1:
        print(f"\n  ⚠ {len(seats)} seats in one draft are ONE observation, not {len(seats)} — "
              f"your picks deplete\n    each other's pools. Read the teams side by side; never "
              f"average them (16.17).")
    made = advance(st, meta, risk)
    save(st, meta, vi, risk)
    report_turn(st, meta, made, n=a.n, pos=a.pos, vi=vi)


def cmd_pick(a) -> None:
    st, meta, vi, risk = load()
    team = st.team_on_clock() if a.team is None else a.team - 1
    if team not in st.human_teams:
        raise SystemExit(f"T{team + 1} is not one of your seats "
                         f"({', '.join('T' + str(t + 1) for t in sorted(st.human_teams))})")
    if team != st.team_on_clock():
        raise SystemExit(f"T{team + 1} is not on the clock — T{st.team_on_clock() + 1} is")
    q = a.query.strip()
    found = session.resolve_pick(st, team, q)
    if isinstance(found, list):
        if not found:
            print(f"no available player matching {q!r}")
            return
        print(f"{len(found)} matches — be more specific or use the # column:")
        for m in found[:10]:
            print(f"  {m['index']:<5}{m['player_name']:<24}{m['pos']:<4}ADP {m['adp']:.1f}")
        return
    idx = found
    row = st.board.loc[idx]
    _apply_pick(st, team, idx)
    print(f"\n>>> T{team + 1} picks {row['player_name']} ({row['pos']}, "
          f"ADP {row['adp']:.1f}) at #{st.overall_pick - 1}")
    made = advance(st, meta, risk)
    save(st, meta, vi, risk)
    report_turn(st, meta, made, n=a.n, pos=a.pos, vi=vi)


def _seat_arg(st: DraftState, team: int | None) -> int:
    """``--team`` -> a 0-indexed seat; default is the seat on the clock when it is one of yours,
    else the primary seat (16.17: with k seats "your board" is ambiguous without one)."""
    if team is not None:
        return team - 1
    on_clock = st.team_on_clock()
    return on_clock if on_clock in st.human_teams else st.your_team


def cmd_board(a) -> None:
    st, _, _, _ = load()
    show_available(st, n=a.n, pos=a.pos, team=_seat_arg(st, a.team))


def cmd_roster(a) -> None:
    st, meta, _, _ = load()
    t = _seat_arg(st, a.team)
    print(f"\n=== T{t + 1} — {seat_label(t, seat_map_from(meta))} ===")
    show_roster(st, t)


def cmd_finish(a) -> None:
    """Autodraft **every** remaining human seat by ADP, then run the room out."""
    st, meta, vi, risk = load()
    sm = seat_map_from(meta)
    opp = sm.pick_fn(mock.load_opponent_model(), risk=risk)
    run_to_completion(
        st,
        your_pick_fn={t: (lambda s, _t=t: pick_by_adp(s, _t, noise=0.0)) for t in st.human_teams},
        opponent_pick_fn=opp)
    save(st, meta, vi, risk)
    summary(st, meta, vi)


def cmd_summary(a) -> None:
    st, meta, vi, _ = load()
    summary(st, meta, vi)
    if a.odds and st.is_done():
        league_odds(st, meta, sims=a.sims)


def cmd_why(a) -> None:
    """T27 1c — the arithmetic chain for one player, from PROJ to BASE_VALUE."""
    st, meta, vi, _ = load()
    if vi is None:
        raise SystemExit("this draft was started before T27 — run `start` again to get `why`")
    explain(st.board, vi, a.query, lam=DraftConfig().risk_lambda)


def cmd_stats(a) -> None:
    """14.O — the stat dictionary, in the terminal. Same entries the app's tooltips show.

    One dictionary, every surface: a column explained two ways is a column explained differently
    the first time one of the two is edited.
    """
    cols = [a.column.upper()] if a.column else [lbl for _, lbl in session.BOARD_VIEW_COLS]
    for c in cols:
        try:
            e = session.stat_entry(c)
        except LookupError as exc:
            raise SystemExit(str(exc)) from None
        print(f"\n=== {c} — {e['label']} ===")
        print(f"  {e['one_line']}")
        print(f"\n  {e['what_it_means']}")
        print(f"\n  EXAMPLE   {e['worked_example']}")
        print(f"  READING   {e['how_to_read_it']}")
        print(f"  SOURCE    {e['provenance']}")


def cmd_log(a) -> None:
    st, meta, _, _ = load()
    sm = seat_map_from(meta)
    for r in st.log[-a.n:]:
        print(fmt_pick(r, sm))


def cmd_drift(a) -> None:
    """This draft in the corpus's own units — the eyeball bar, quantified."""
    st, meta, _, _ = load()
    # 16.17: the panel wants one label per team, and `SeatMap` is where that mapping lives now.
    d = session.drift_frames(st, meta, seat_map_from(meta))
    print("\n=== REACH PROFILE — 10-team ADP picks (compare to analysis/t15_baseline.json) ===")
    print(d["profile"].round(2).to_string(index=False))
    print("\n=== ELITE FALL (consensus top-12) ===")
    print("  " + str(d["elite"]))
    print("\n=== PER SEAT ===")
    print(d["seats"].round(2).to_string(index=False))
    # 16.17 honesty rule 2 — state the bars' scope rather than re-measuring them here.
    n_h = d["n_humans"]
    print("\n  (SCOPE: the committed T15 realism bars — profile distance, dispersion, chalk")
    print("   share, elite-fall landing — were measured on a **fully simulated** ten-seat room.")
    print(f"   This draft has {n_h} human seat(s), so these numbers describe THIS draft and are")
    print("   not a re-measurement of those bars. Use steps/mock_room_bars.py for those.)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start")
    s.add_argument("--seat", type=int, default=4, help="the single seat you drive (1-indexed)")
    s.add_argument("--seats", default=None,
                   help="16.17: several seats, e.g. '3,7'. The first is the primary one "
                        "(DraftState.your_team). '' is a fully simulated room. Overrides --seat")
    s.add_argument("--auto", default="",
                   help="16.17: seats of YOURS the ADP autopicker drives, e.g. '7'")
    s.add_argument("--teams", type=int, default=10)
    s.add_argument("--rounds", type=int, default=15)
    s.add_argument("--season", type=int, default=2026)
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--room-seed", type=int, default=None)
    s.add_argument("--room", default="realistic",
                   help="'realistic' (the shipped room minus one `balanced` per human seat, "
                        "default) | 'default' (pre-16.14R) | a comma-separated list of exactly "
                        "n_teams - (your seats) personality names")
    s.add_argument("--fav", default="")
    s.add_argument("--n", type=int, default=18)
    s.add_argument("--pos", default=None)
    s.set_defaults(fn=cmd_start)

    p = sub.add_parser("pick")
    p.add_argument("query")
    p.add_argument("--team", type=int, default=None,
                   help="which of your seats (1-indexed); default = the one on the clock")
    p.add_argument("--n", type=int, default=18)
    p.add_argument("--pos", default=None)
    p.set_defaults(fn=cmd_pick)

    b = sub.add_parser("board")
    b.add_argument("--team", type=int, default=None)
    b.add_argument("--n", type=int, default=18)
    b.add_argument("--pos", default=None)
    b.set_defaults(fn=cmd_board)

    r = sub.add_parser("roster")
    r.add_argument("--team", type=int, default=None)
    r.set_defaults(fn=cmd_roster)

    w = sub.add_parser("why", help="the PROJ -> BASE_VALUE arithmetic chain for one player")
    w.add_argument("query")
    w.set_defaults(fn=cmd_why)

    sub.add_parser("finish").set_defaults(fn=cmd_finish)

    sm = sub.add_parser("summary")
    sm.add_argument("--odds", action="store_true",
                    help="also run the Phase-10 season sim (fair-share multiples, T29)")
    sm.add_argument("--sims", type=int, default=400)
    sm.set_defaults(fn=cmd_summary)
    sub.add_parser("drift").set_defaults(fn=cmd_drift)

    stt = sub.add_parser("stats", help="14.O: what every board column means, with examples")
    stt.add_argument("column", nargs="?", default=None, help="one column, e.g. BUST")
    stt.set_defaults(fn=cmd_stats)

    lg = sub.add_parser("log")
    lg.add_argument("--n", type=int, default=20)
    lg.set_defaults(fn=cmd_log)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
