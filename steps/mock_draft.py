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
from dataclasses import replace
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from fantasy_quant.draft import mock, optimizer
from fantasy_quant.draft.config import DraftConfig
from fantasy_quant.draft.personalities import (
    DEFAULT_ROOM,
    HUMAN,
    REALISTIC_ROOM,
    SeatMap,
    personalities,
)
from fantasy_quant.draft.simulator import (
    DraftState,
    RosterSlots,
    _apply_pick,
    _prepare_board,
    pick_by_adp,
    run_to_completion,
)

DB = Path("data/fantasy_quant.duckdb")
STATE = Path("data/interim/mock/draft_state.pkl")
CACHE = Path("analysis/cache")


def _con():
    return duckdb.connect(str(DB), read_only=True)


def build_board(season: int = 2026, teams: int = 10) -> tuple[pd.DataFrame, pd.DataFrame, object]:
    """``(board, value_index, risk)`` — the board a human reads **and** the value every seat
    optimizes, built from one call so they cannot disagree about which season they describe.

    ★ **T27 — this used to return the board alone, and that was the ticket.** ``proj_points`` (the
    consensus number printed at every turn) rode in on a hand-rolled re-attach, ``base_value`` (the
    risk-adjusted VOR that actually drives utility, the value hawk's objective and every seat's
    priority rank) was never attached at all, and with no ``risk`` model the room's ``value_hawk``
    seat silently fell back to the behavioral softmax — i.e. the *interactive* mock ran a different
    room from every batch measurement in the repo. All three are the same defect: the display path
    and the decision path were built separately.
    """
    con = _con()
    board, src = mock.room_board(con, season, teams=teams, cache_dir=CACHE)
    if board.empty:
        raise SystemExit(f"no {season} board at teams={teams}")
    config = DraftConfig()
    vi = optimizer.assemble_value(con, season, config)
    board = optimizer.attach_value(board, vi)
    risk = optimizer.build_risk_model(board, vi, optimizer.assemble_correlation(con, season),
                                      lam=config.risk_lambda)
    con.close()
    have = int(board["base_value"].notna().sum())
    print(f"  board: {len(board)} players ({src} ADP + frozen Phase-4/5 context) · "
          f"{have} carry base_value · λ={config.risk_lambda}")
    return board, vi, risk


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


#: The nine opponents a human faces, from the ten-seat shipped room. One ``balanced`` seat is the
#: one dropped, because **you** are taking a seat and ``balanced`` is the modal manager — removing
#: any character seat instead would change the composition 16.14R step 7 validated.
#:
#: ★ **16.17 generalizes the same rule to k seats:** :func:`realistic_mix` drops **one ``balanced``
#: per human seat**, for exactly the argument above, and refuses once there are no ``balanced``
#: seats left to give up rather than silently deleting a character seat and quietly changing the
#: composition step 7 validated.
REALISTIC_NINE: tuple[str, ...] = tuple(
    [n for i, n in enumerate(REALISTIC_ROOM) if not (n == "balanced" and i == REALISTIC_ROOM.index(
        "balanced"))])


def realistic_mix(n_humans: int, n_teams: int = 10) -> tuple[str, ...]:
    """The shipped room with ``n_humans`` seats taken out of it — one ``balanced`` per human."""
    names = list(REALISTIC_ROOM)
    if n_teams != len(REALISTIC_ROOM):
        raise SystemExit(f"--room realistic is the {len(REALISTIC_ROOM)}-seat shipped room; "
                         f"pass an explicit --room for a {n_teams}-team draft")
    if n_humans >= n_teams:               # k = n: you drive the whole table, there is no room
        return ()
    for _ in range(n_humans):
        if "balanced" not in names:
            raise SystemExit(
                f"the shipped room has only {REALISTIC_ROOM.count('balanced')} `balanced` seats to "
                f"give up; for {n_humans} human seats pass an explicit --room of "
                f"{n_teams - n_humans} names")
        names.remove("balanced")
    return tuple(names)


def room_mix(arg: str | None, n_humans: int = 1, n_teams: int = 10) -> tuple[str, ...]:
    """``--room`` -> the modelled-seat mix. Default is the **shipped** room, not the pre-16.14R
    one; it must be exactly ``n_teams - n_humans`` long, which :meth:`SeatMap.of` re-checks."""
    if arg in (None, "", "realistic"):
        return realistic_mix(n_humans, n_teams)
    if arg == "default":
        return tuple(DEFAULT_ROOM)
    return tuple(x.strip() for x in arg.split(","))


def room_from(meta: dict):
    lib = personalities()
    return tuple(replace(lib[n], fav_teams=tuple(meta.get("fav", ())))
                 if (meta.get("fav") and n == "homer") else lib[n]
                 for n in meta["room"])


def seat_map_from(meta: dict) -> SeatMap:
    """Rebuild the draft's :class:`SeatMap` from the pickled ``meta``.

    ``meta["human_teams"]`` is 16.17's; a draft started before it falls back to ``{your_team}``,
    which is what that draft was. Rebuilding rather than pickling the map itself keeps the state
    file readable across a code change to :class:`Personality` — the same reason ``meta`` stores
    personality *names* and not objects.
    """
    humans = meta.get("human_teams", [meta["your_team"]])
    return SeatMap.of(meta["teams"], human_teams=humans, room=room_from(meta))


def seat_label(team: int, sm: SeatMap) -> str:
    """``YOU (T3)`` for a human seat in a multi-seat draft, ``YOU`` when you drive only one."""
    if sm.seats[team] != HUMAN:
        return sm.seats[team].name
    return "YOU" if len(sm.human_teams) == 1 else f"YOU (T{team + 1})"


# ---------------------------------------------------------------------------------- display
def fmt_pick(r: dict, sm: SeatMap) -> str:
    return (f"  {r['round']:>2}.{r['pick_in_round']:02d}  {'T' + str(r['team'] + 1):<4}"
            f"{seat_label(r['team'], sm):<15}{r['player_name'][:23]:<24}{r['pos']:<4}"
            f"(ADP {r['adp']:.1f})")


def show_available(st: DraftState, n: int = 18, pos: str | None = None,
                   team: int | None = None) -> None:
    pool = st.draftable_pool(st.your_team if team is None else team)
    if pos:
        pool = pool[pool["pos"].isin([p.strip().upper() for p in pos.split(",")])]
    # BOOM/BUST are the **live** pair (T22): the frozen Phase-5 columns are
    # `weekly_volatility(max(train_seasons))`, which on a live board is 2022, and a player who was
    # not in the league that season reads 0.00 — i.e. *never busts*. `boom_prob_live`/
    # `bust_prob_live` are the same rates on season − 1, and a player we have never seen play
    # prints "-" rather than a fabricated zero. TAIL is `tail_risk`, the relative q90−q10 spread —
    # the column 16.14R shipped as the honest boom-or-bust read.
    # ★ T27 — the value chain first, in the order the arithmetic runs:
    #   PROJ   consensus projection, re-scored full-PPR. The number a human trusts.
    #   MEAN   the Phase-5 season mean = PROJ x projected availability. The level correction.
    #   AVAIL  games_played_mean — **the column that explains the gap between the first two.**
    #   BV     base_value = ce_vbd = (MEAN - lambda*Var) - positional replacement. What every
    #          seat's utility, the value hawk's objective and the priority rank actually run on.
    # Before this, the board printed PROJ and the room optimized BV, and on the 2026 board those
    # disagree by up to 179 points (Drake Maye +68.5 vs Jayden Daniels -101.6, 3 points apart on
    # screen). `why "<player>"` prints the whole chain for one player.
    print(f"  {'#':<5}{'PLAYER':<22}{'POS':<4}{'ADP':>6}{'PROJ':>6}{'MEAN':>6}{'AVAIL':>6}"
          f"{'BV':>7}{'VBD':>6}{'RK':>5}{'UPSIDE':>7}{'FLOOR':>7}{'TAIL':>7}{'BOOM':>6}{'BUST':>6}")
    for idx, r in pool.head(n).iterrows():
        def g(c, fmt=".2f", row=r):
            v = row.get(c, np.nan)
            return format(v, fmt) if pd.notna(v) else "-"
        print(f"  {idx:<5}{r['player_name'][:21]:<22}{r['pos']:<4}{r['adp']:>6.1f}"
              f"{g('proj_points', '.0f'):>6}{g('mean', '.0f'):>6}{g('games_played_mean', '.1f'):>6}"
              f"{g('base_value', '+.0f'):>7}{g('vbd', '.0f'):>6}{g('overall_rank', '.0f'):>5}"
              f"{g('upside', '+.2f'):>7}{g('floor', '+.2f'):>7}{g('tail_risk', '+.2f'):>7}"
              f"{g('boom_prob_live', '.2f'):>6}{g('bust_prob_live', '.2f'):>6}")


def explain(board: pd.DataFrame, vi: pd.DataFrame, query: str, lam: float) -> None:
    """``why "<player>"`` — the arithmetic chain from the number a human trusts to the number the
    engine uses (T27 step 1c, the session's real product deliverable).

    Every line is an identity, not a re-derivation: ``lambda*Var`` is printed as ``mean - ce_value``
    and the positional replacement as ``ce_value - ce_vbd``, so what is shown is what the frozen
    Phase-4/5 stack actually computed rather than a display-layer reimplementation of it that could
    drift away from it. That is the whole point of the command — an auditable path, not a caption.
    """
    q = query.strip().lower()
    hit = board[board["player_name"].str.lower().str.contains(q, regex=False)]
    if hit.empty:
        print(f"no player on the board matching {query!r}")
        return
    if len(hit) > 6:
        print(f"{len(hit)} matches — be more specific")
        return
    idx = vi.drop_duplicates("player_key").set_index(vi["player_key"].astype(str))
    for _, r in hit.iterrows():
        v = idx.loc[str(r["player_key"])] if str(r["player_key"]) in idx.index else None
        print(f"\n=== {r['player_name']} ({r['pos']}, ADP {r['adp']:.1f}) ===")
        if v is None or pd.isna(v.get("mean")):
            print("  no Phase-5 distribution — this player drafts on ADP fallback "
                  "(base_value is NaN, so no seat's value objective can see him).")
            continue
        proj, mean = float(v["proj_points"]), float(v["mean"])
        ce, ce_vbd = float(v["ce_value"]), float(v["ce_vbd"])
        gp = r.get("games_played_mean", np.nan)
        lam_var, repl = mean - ce, ce - ce_vbd
        w, pos = 36, str(r["pos"])
        avail = f"games_played_mean {gp:.1f} of 17" if pd.notna(gp) else "(no availability read)"
        haircut = f"haircut {1 - mean / proj:+.1%}" if proj else "(no consensus projection)"

        def row(label: str, value: float | None, note: str = "", width: int = w) -> None:
            shown = "" if value is None else format(value, ">10.1f")
            print(f"  {label:<{width}}{shown:>10}   {note}".rstrip())

        row("consensus projection (PROJ)", proj, "full-PPR, re-scored by our RuleSet")
        row("x projected availability", None, avail)
        row("= Phase-5 season mean (MEAN)", mean, haircut)
        row("  sd", float(v["sd"]))
        row(f"- lambda*Var   (lambda = {lam:.3g})", -lam_var)
        row("= certainty equivalent (ce_value)", ce, "the risk dial's output")
        row(f"- replacement CE at {pos}", -repl, f"the {pos} a waiver claim gets you")
        row("= BASE_VALUE — what seats optimize", ce_vbd)
        row("(frozen Phase-4 VBD, for reference)", float(v["vbd"]))


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


def auto_teams(meta: dict) -> frozenset[int]:
    """Human seats the caller handed to the ADP autopicker (``--auto``) — still *yours*, just not
    typed by hand. The same seam 9.5's rollout uses on your own seat internally."""
    return frozenset(int(t) for t in meta.get("auto", ()))


def advance(st: DraftState, meta: dict, risk=None) -> list[dict]:
    """Run modelled (and ``--auto``) picks until a seat **you** drive is on the clock.

    ``risk`` is what routes the room's ``value_hawk`` seat to the Phase-9 greedy instead of the
    behavioral softmax (T27). Omitting it now **raises** rather than silently seating a second
    ``balanced`` — see :func:`~fantasy_quant.draft.personalities.assert_room_objectives`.

    ★ **16.17 — the stop condition is membership, not equality.** It was ``team == st.your_team``,
    which is why a second human seat would have been drafted *for* you by the room.
    """
    sm = seat_map_from(meta)
    opp = sm.pick_fn(mock.load_opponent_model(), risk=risk)
    auto = auto_teams(meta)
    made: list[dict] = []
    while not st.is_done() and st.available:
        team = st.team_on_clock()
        if team in st.human_teams and team not in auto:
            break
        idx = pick_by_adp(st, team, noise=0.0) if team in auto else int(opp(st, team))
        _apply_pick(st, team, idx)
        made.append(st.log[-1])
    return made


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
    slots = st.slots
    rows = []
    for t in range(st.n_teams):
        roster = st.roster(t)
        pp = pd.to_numeric(roster.get("proj_points"), errors="coerce").fillna(0.0)
        row = {"team": t + 1, "who": seat_label(t, sm), "human": t in sm.human_teams,
               "proj": float(pp.sum()), "starters": float(pp.nlargest(9).sum())}
        if vi is not None:
            row["startable"] = optimizer.starter_value(roster, vi, slots)
            row["capital"] = optimizer.team_value(roster, vi)
        rows.append(row)
    tab = pd.DataFrame(rows).sort_values("starters", ascending=False)
    has_bv = "startable" in tab.columns
    head = f"  {'RANK':<6}{'TEAM':<6}{'PERSONALITY':<16}{'TOP-9 PROJ':>12}{'FULL ROSTER':>13}"
    print(head + (f"{'STARTABLE':>11}{'CAPITAL':>10}" if has_bv else ""))
    for i, (_, r) in enumerate(tab.iterrows(), 1):
        star = "  <-- you" if r["human"] else ""
        extra = f"{r['startable']:>11.0f}{r['capital']:>10.0f}" if has_bv else ""
        print(f"  {i:<6}{'T' + str(int(r['team'])):<6}{r['who']:<16}"
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
    from fantasy_quant.simulation.season import (
        LeagueFormat,
        assert_probability_sums,
        fair_share,
        league_probabilities,
        playoff_fair_share,
        provenance_lines,
    )
    from fantasy_quant.simulation.weekly import build_weekly_model

    con = _con()
    fmt = LeagueFormat(n_teams=st.n_teams)
    wm = build_weekly_model(con, meta.get("season", 2026), DraftConfig().league.ruleset, seed=0)
    con.close()
    rosters = [st.roster(t) for t in range(st.n_teams)]
    pp, tp = league_probabilities(rosters, wm, fmt, st.slots, np.random.default_rng(0), sims=sims)
    assert_probability_sums(pp, tp, fmt)                      # 3c — a structural identity
    pf, tf = playoff_fair_share(pp, fmt), fair_share(tp, fmt.n_teams)

    sm = seat_map_from(meta)
    print("\n=== SEASON ODDS (Phase-10 sim) ===")
    print("\n".join(provenance_lines(sims, fmt)))
    order = np.argsort(-tf)
    print(f"\n  {'TEAM':<6}{'PERSONALITY':<16}{'PLAYOFF':>9}{'vs FAIR':>9}"
          f"{'TITLE':>9}{'vs FAIR':>9}")
    for t in order:
        star = "  <-- you" if t in sm.human_teams else ""
        print(f"  {'T' + str(t + 1):<6}{seat_label(t, sm):<16}{pp[t]:>8.1%}{pf[t]:>8.2f}x"
              f"{tp[t]:>9.1%}{tf[t]:>8.2f}x{star}")
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
        seats = [int(x.strip()) - 1 for x in str(raw).split(",") if x.strip()]
    except ValueError:
        raise SystemExit(f"--seats wants comma-separated seat numbers, got {raw!r}") from None
    if not seats:
        raise SystemExit("--seats needs at least one seat (or use --seats '' for a 0-human room)")
    if len(set(seats)) != len(seats):
        raise SystemExit(f"--seats has a repeat: {raw!r}")
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
    meta = {"your_team": primary, "human_teams": seats, "auto": auto,
            "room": [p.name for p in sm.room()], "teams": a.teams, "rounds": a.rounds,
            "fav": list(fav), "seed": a.seed, "season": a.season}
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
    pool = st.draftable_pool(team)
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


def cmd_log(a) -> None:
    st, meta, _, _ = load()
    sm = seat_map_from(meta)
    for r in st.log[-a.n:]:
        print(fmt_pick(r, sm))


def cmd_drift(a) -> None:
    """This draft in the corpus's own units — the eyeball bar, quantified."""
    st, meta, _, _ = load()
    # 16.17: the panel wants one label per team, and `SeatMap` is where that mapping lives now.
    sm = seat_map_from(meta)
    labels = [seat_label(t, sm) for t in range(st.n_teams)]
    panel = mock.sim_drift_panel(st, season=meta.get("season", 2026), draft_id="interactive",
                                 board_teams=meta["teams"], seed=meta["seed"])
    panel["seat_personality"] = panel["draft_slot"].map(lambda s: labels[s - 1])
    print("\n=== REACH PROFILE — 10-team ADP picks (compare to analysis/t15_baseline.json) ===")
    print(mock.reach_profile(panel).round(2).to_string(index=False))
    print("\n=== ELITE FALL (consensus top-12) ===")
    print("  " + str(mock.elite_fall_profile(panel)))
    print("\n=== PER SEAT ===")
    print(mock.seat_table(panel).round(2).to_string(index=False))
    # 16.17 honesty rule 2 — state the bars' scope rather than re-measuring them here.
    n_h = len(sm.human_teams)
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

    lg = sub.add_parser("log")
    lg.add_argument("--n", type=int, default=20)
    lg.set_defaults(fn=cmd_log)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
