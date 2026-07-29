"""Interactive mock draft — you at one seat, the fantasy-quant personalities at the other nine.

    uv run python steps/mock_draft.py start --seat 7 [--room a,b,..] [--teams 10] [--seed 7]
                                 # --room defaults to the SHIPPED room (REALISTIC_ROOM, minus one
                                 # `balanced` seat, which is the one you take)
    uv run python steps/mock_draft.py board [--pos RB] [--n 20]
    uv run python steps/mock_draft.py pick "Bijan"
    uv run python steps/mock_draft.py roster [--team 3]
    uv run python steps/mock_draft.py drift          # your draft in the corpus's own units
    uv run python steps/mock_draft.py finish         # autodraft your remaining picks by ADP
    uv run python steps/mock_draft.py summary

Promoted from a session scratchpad, where it was written to let the user draft against the room one
pick at a time — **and it immediately found a defect no automated gate had** (T15: the room's
reaches and falls are impossible; ``findings.md`` §"Live mock draft (2026-07-27)"). That is the
argument for it living in ``steps/`` rather than being rewritten each time: *every subsystem needs
one bar a domain expert could fail by eye, and this is that bar for the draft room.*

Thin over the real engine — there is no modelling here:
  board      ``mock.room_board``      (FFC ADP + 16.13 read-only enrichment)
  opponents  ``personalities``        on the fitted 11.1 β
  mechanics  ``DraftState``/``_apply_pick``, one pick at a time instead of ``run_to_completion``
  drift      ``mock.sim_drift_panel`` — the same frame ``steps/t15_0_baseline.py`` measures

State is pickled between invocations so a draft survives across shell calls (and chat turns); the
opponents' rng lives in ``DraftState``, so the room stays reproducible from ``--seed``.

Note this driver keeps the **nine-opponents-plus-you** shape, which is the real use case. The
fully-simulated ten-personality room used for batch measurement is
:func:`fantasy_quant.draft.mock.full_room` — different question, different harness.
"""

from __future__ import annotations

import argparse
import pickle
from dataclasses import replace
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from fantasy_quant.draft import mock
from fantasy_quant.draft.personalities import (
    DEFAULT_ROOM,
    REALISTIC_ROOM,
    make_room,
    make_room_pick_fn,
    personalities,
)
from fantasy_quant.draft.simulator import (
    DraftState,
    RosterSlots,
    _apply_pick,
    _prepare_board,
    board_player_key,
    pick_by_adp,
)
from fantasy_quant.valuation.value_board import value_board

DB = Path("data/fantasy_quant.duckdb")
STATE = Path("data/interim/mock/draft_state.pkl")
CACHE = Path("analysis/cache")


def _con():
    return duckdb.connect(str(DB), read_only=True)


def build_board(season: int = 2026, teams: int = 10) -> pd.DataFrame:
    """The enriched board plus ``proj_points`` — the one number a human reads first."""
    con = _con()
    board, src = mock.room_board(con, season, teams=teams, cache_dir=CACHE)
    if board.empty:
        raise SystemExit(f"no {season} board at teams={teams}")
    if "proj_points" not in board.columns:
        vb = value_board(con, season, pd.Timestamp.today().date(), n_teams=teams)
        proj = pd.Series(vb["proj_points"].to_numpy(float),
                         index=vb["player_key"].astype(str)).groupby(level=0).first()
        board["proj_points"] = board_player_key(board).astype(str).map(proj).to_numpy()
    con.close()
    print(f"  board: {len(board)} players ({src} ADP + frozen Phase-4/5 context)")
    return board


# ---------------------------------------------------------------------------------- state io
def save(st: DraftState, meta: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_bytes(pickle.dumps({"state": st, "meta": meta}))


def load() -> tuple[DraftState, dict]:
    if not STATE.exists():
        raise SystemExit("no draft in progress — run `start` first")
    d = pickle.loads(STATE.read_bytes())
    return d["state"], d["meta"]


#: The nine opponents a human faces, from the ten-seat shipped room. One ``balanced`` seat is the
#: one dropped, because **you** are taking a seat and ``balanced`` is the modal manager — removing
#: any character seat instead would change the composition 16.14R step 7 validated.
REALISTIC_NINE: tuple[str, ...] = tuple(
    [n for i, n in enumerate(REALISTIC_ROOM) if not (n == "balanced" and i == REALISTIC_ROOM.index(
        "balanced"))])


def room_mix(arg: str | None) -> tuple[str, ...]:
    """``--room`` -> a nine-name mix. Default is the **shipped** room, not the pre-16.14R one."""
    if arg in (None, "", "realistic"):
        return REALISTIC_NINE
    if arg == "default":
        return tuple(DEFAULT_ROOM)
    return tuple(x.strip() for x in arg.split(","))


def room_from(meta: dict):
    lib = personalities()
    return tuple(replace(lib[n], fav_teams=tuple(meta.get("fav", ())))
                 if (meta.get("fav") and n == "homer") else lib[n]
                 for n in meta["room"])


def seat_of(team: int, your_team: int) -> int:
    return team - 1 if team > your_team else team


def seat_name(team: int, meta: dict) -> str:
    return "YOU" if team == meta["your_team"] else meta["room"][seat_of(team, meta["your_team"])]


# ---------------------------------------------------------------------------------- display
def fmt_pick(r: dict, meta: dict) -> str:
    return (f"  {r['round']:>2}.{r['pick_in_round']:02d}  {'T' + str(r['team'] + 1):<4}"
            f"{seat_name(r['team'], meta):<15}{r['player_name'][:23]:<24}{r['pos']:<4}"
            f"(ADP {r['adp']:.1f})")


def show_available(st: DraftState, n: int = 18, pos: str | None = None) -> None:
    pool = st.draftable_pool(st.your_team)
    if pos:
        pool = pool[pool["pos"].isin([p.strip().upper() for p in pos.split(",")])]
    # BOOM/BUST are the **live** pair (T22): the frozen Phase-5 columns are
    # `weekly_volatility(max(train_seasons))`, which on a live board is 2022, and a player who was
    # not in the league that season reads 0.00 — i.e. *never busts*. `boom_prob_live`/
    # `bust_prob_live` are the same rates on season − 1, and a player we have never seen play
    # prints "-" rather than a fabricated zero. TAIL is `tail_risk`, the relative q90−q10 spread —
    # the column 16.14R shipped as the honest boom-or-bust read.
    print(f"  {'#':<5}{'PLAYER':<24}{'POS':<5}{'ADP':>6}{'PROJ':>7}{'VBD':>7}{'RK':>5}"
          f"{'UPSIDE':>8}{'FLOOR':>7}{'TAIL':>7}{'BOOM':>6}{'BUST':>6}")
    for idx, r in pool.head(n).iterrows():
        def g(c, fmt=".2f", row=r):
            v = row.get(c, np.nan)
            return format(v, fmt) if pd.notna(v) else "-"
        print(f"  {idx:<5}{r['player_name'][:23]:<24}{r['pos']:<5}{r['adp']:>6.1f}"
              f"{g('proj_points', '.0f'):>7}{g('vbd', '.0f'):>7}{g('overall_rank', '.0f'):>5}"
              f"{g('upside', '+.2f'):>8}{g('floor', '+.2f'):>7}{g('tail_risk', '+.2f'):>7}"
              f"{g('boom_prob_live', '.2f'):>6}{g('bust_prob_live', '.2f'):>6}")


def show_roster(st: DraftState, team: int) -> None:
    r = st.roster(team)
    if r.empty:
        print("  (empty)")
        return
    order = {"QB": 0, "RB": 1, "WR": 2, "TE": 3, "K": 4, "DST": 5}
    r = r.assign(_o=r["pos"].map(order)).sort_values(["_o", "adp"])
    tot = 0.0
    for _, p in r.iterrows():
        pp = p.get("proj_points", np.nan)
        tot += float(pp) if pd.notna(pp) else 0.0
        shown = f"{pp:.0f}" if pd.notna(pp) else "-"
        print(f"  {p['pos']:<4}{p['player_name'][:24]:<26}ADP {p['adp']:>6.1f}"
              f"  proj {shown:>4}")
    print(f"  {'':<4}{'TOTAL (consensus proj pts)':<26}{'':>10}  {tot:>9.0f}")


def advance(st: DraftState, meta: dict) -> list[dict]:
    """Run opponent picks until it is your turn (or the draft ends)."""
    opp = make_room_pick_fn(mock.load_opponent_model(), room_from(meta))
    made: list[dict] = []
    while not st.is_done() and st.available:
        team = st.team_on_clock()
        if team == st.your_team:
            break
        _apply_pick(st, team, int(opp(st, team)))
        made.append(st.log[-1])
    return made


def report_turn(st: DraftState, meta: dict, made: list[dict], n: int = 18,
                pos: str | None = None) -> None:
    if made:
        print(f"\n--- {len(made)} picks since your last turn ---")
        for r in made:
            print(fmt_pick(r, meta))
    if st.is_done() or not st.available:
        print("\n=== DRAFT COMPLETE ===")
        summary(st, meta)
        return
    print(f"\n=== ON THE CLOCK: YOU — round {st.round()}, pick {st.pick_in_round()} "
          f"(#{st.overall_pick} overall) ===")
    print("\n  YOUR ROSTER")
    show_roster(st, st.your_team)
    needs = st.starter_needs(st.your_team)
    print("  starter needs: " + ", ".join(f"{k} {v}" for k, v in needs.items() if v))
    print("\n  BEST AVAILABLE")
    show_available(st, n=n, pos=pos)


def summary(st: DraftState, meta: dict) -> None:
    print("\n=== FINAL ROSTERS ===")
    rows = []
    for t in range(st.n_teams):
        pp = pd.to_numeric(st.roster(t).get("proj_points"), errors="coerce").fillna(0.0)
        rows.append({"team": t + 1, "who": seat_name(t, meta), "proj": float(pp.sum()),
                     "starters": float(pp.nlargest(9).sum())})
    tab = pd.DataFrame(rows).sort_values("starters", ascending=False)
    print(f"  {'RANK':<6}{'TEAM':<6}{'PERSONALITY':<16}{'TOP-9 PROJ':>12}{'FULL ROSTER':>13}")
    for i, (_, r) in enumerate(tab.iterrows(), 1):
        star = "  <-- you" if r["who"] == "YOU" else ""
        print(f"  {i:<6}{'T' + str(int(r['team'])):<6}{r['who']:<16}"
              f"{r['starters']:>12.0f}{r['proj']:>13.0f}{star}")
    print("\n  (Top-9 proj = the 9 best consensus projections on the roster — a rough")
    print("   team-strength readout, not the Phase-10 season sim. Projected-points rankings")
    print("   are DESCRIPTIVE:")
    print("   scoring our own seats on our own board wins by construction — see findings.md.)")
    print("\n  YOUR TEAM")
    show_roster(st, st.your_team)


# ---------------------------------------------------------------------------------- commands
def cmd_start(a) -> None:
    board = build_board(season=a.season, teams=a.teams)
    b = _prepare_board(board)
    # proj_points is display-only (not a simulator PASSTHROUGH col), so re-attach it by key
    proj = pd.Series(board["proj_points"].to_numpy(float),
                     index=board_player_key(board).astype(str)).groupby(level=0).first()
    b["proj_points"] = b["player_key"].astype(str).map(proj).to_numpy()
    mix = room_mix(a.room)
    fav = tuple(x.strip().upper() for x in (a.fav or "").split(",") if x.strip())
    resolved = [p.name for p in make_room(mix, n_opponents=a.teams - 1, seed=a.room_seed,
                                          fav_teams=fav)]
    meta = {"your_team": a.seat - 1, "room": resolved, "teams": a.teams, "rounds": a.rounds,
            "fav": list(fav), "seed": a.seed, "season": a.season}
    st = DraftState(board=b, n_teams=a.teams, rounds=a.rounds, slots=RosterSlots(),
                    your_team=a.seat - 1, rng=np.random.default_rng(a.seed), noise=5.0,
                    available=set(b.index), rosters=[[] for _ in range(a.teams)])
    print(f"=== MOCK DRAFT — {a.teams}-team full-PPR snake, {a.rounds} rounds, "
          f"you pick {a.seat} ===")
    print("  the room:")
    for i, n in enumerate(resolved):
        print(f"    T{(i + 1 if i >= meta['your_team'] else i) + 1:<3} {n}")
    made = advance(st, meta)
    save(st, meta)
    report_turn(st, meta, made, n=a.n, pos=a.pos)


def cmd_pick(a) -> None:
    st, meta = load()
    pool = st.draftable_pool(st.your_team)
    q = a.query.strip()
    if q.isdigit() and int(q) in pool.index:
        idx = int(q)
    else:
        hit = pool[pool["player_name"].str.lower().str.contains(q.lower(), regex=False)]
        if hit.empty:
            print(f"no available player matching {q!r}")
            return
        if len(hit) > 1:
            print(f"{len(hit)} matches — be more specific or use the # column:")
            for i, r in hit.head(10).iterrows():
                print(f"  {i:<5}{r['player_name']:<24}{r['pos']:<4}ADP {r['adp']:.1f}")
            return
        idx = int(hit.index[0])
    row = st.board.loc[idx]
    _apply_pick(st, st.your_team, idx)
    print(f"\n>>> YOU pick {row['player_name']} ({row['pos']}, ADP {row['adp']:.1f}) "
          f"at #{st.overall_pick - 1}")
    made = advance(st, meta)
    save(st, meta)
    report_turn(st, meta, made, n=a.n, pos=a.pos)


def cmd_board(a) -> None:
    st, _ = load()
    show_available(st, n=a.n, pos=a.pos)


def cmd_roster(a) -> None:
    st, meta = load()
    t = (a.team - 1) if a.team else st.your_team
    print(f"\n=== T{t + 1} — {seat_name(t, meta)} ===")
    show_roster(st, t)


def cmd_finish(a) -> None:
    st, meta = load()
    opp = make_room_pick_fn(mock.load_opponent_model(), room_from(meta))
    while not st.is_done() and st.available:
        team = st.team_on_clock()
        idx = pick_by_adp(st, team, noise=0.0) if team == st.your_team else int(opp(st, team))
        _apply_pick(st, team, idx)
    save(st, meta)
    summary(st, meta)


def cmd_summary(a) -> None:
    summary(*load())


def cmd_log(a) -> None:
    st, meta = load()
    for r in st.log[-a.n:]:
        print(fmt_pick(r, meta))


def cmd_drift(a) -> None:
    """This draft in the corpus's own units — the eyeball bar, quantified."""
    st, meta = load()
    room = room_from(meta)
    # seat i of the room is the i-th team excluding yours; the panel wants one label per team
    by_team = [None if t == meta["your_team"] else room[seat_of(t, meta["your_team"])]
               for t in range(st.n_teams)]
    labels = ["YOU" if p is None else p.name for p in by_team]
    panel = mock.sim_drift_panel(st, season=meta.get("season", 2026), draft_id="interactive",
                                 board_teams=meta["teams"], seed=meta["seed"])
    panel["seat_personality"] = panel["draft_slot"].map(lambda s: labels[s - 1])
    print("\n=== REACH PROFILE — 10-team ADP picks (compare to analysis/t15_baseline.json) ===")
    print(mock.reach_profile(panel).round(2).to_string(index=False))
    print("\n=== ELITE FALL (consensus top-12) ===")
    print("  " + str(mock.elite_fall_profile(panel)))
    print("\n=== PER SEAT ===")
    print(mock.seat_table(panel).round(2).to_string(index=False))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start")
    s.add_argument("--seat", type=int, default=4)
    s.add_argument("--teams", type=int, default=10)
    s.add_argument("--rounds", type=int, default=15)
    s.add_argument("--season", type=int, default=2026)
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--room-seed", type=int, default=None)
    s.add_argument("--room", default="realistic",
                   help="'realistic' (the shipped room, default) | 'default' (pre-16.14R) | "
                        "a comma-separated list of nine personality names")
    s.add_argument("--fav", default="")
    s.add_argument("--n", type=int, default=18)
    s.add_argument("--pos", default=None)
    s.set_defaults(fn=cmd_start)

    p = sub.add_parser("pick")
    p.add_argument("query")
    p.add_argument("--n", type=int, default=18)
    p.add_argument("--pos", default=None)
    p.set_defaults(fn=cmd_pick)

    b = sub.add_parser("board")
    b.add_argument("--n", type=int, default=18)
    b.add_argument("--pos", default=None)
    b.set_defaults(fn=cmd_board)

    r = sub.add_parser("roster")
    r.add_argument("--team", type=int, default=None)
    r.set_defaults(fn=cmd_roster)

    sub.add_parser("finish").set_defaults(fn=cmd_finish)
    sub.add_parser("summary").set_defaults(fn=cmd_summary)
    sub.add_parser("drift").set_defaults(fn=cmd_drift)

    lg = sub.add_parser("log")
    lg.add_argument("--n", type=int, default=20)
    lg.set_defaults(fn=cmd_log)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
