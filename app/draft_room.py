"""The draft room — a page, not a tab (14.K), with a board you can pick from and a clock.

Session K1 put the room in the third of four tabs, made you retype a name you could already see,
showed twelve columns when four would do, drafted the whole room instantly, and — because
``app/engine.start_draft`` carried the CLI's measurement defaults — dealt the **same draft every
time** (T34). This module is that list, answered.

★ **It still derives nothing.** Every frame is :mod:`fantasy_quant.draft.session`'s; what lives
here is which button is next to which table, and when the clock ticks.
"""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from app import engine, nav, probe, state, views
from app.settings_form import lockbox_banner
from fantasy_quant.draft import session
from fantasy_quant.draft.personalities import REALISTIC_ROOM, personalities

#: Measured on the live 2026 board, 2026-07-31: 135 modelled picks over a full 10-team draft, worst
#: **single** pick 10 ms, ``value_hawk`` (the Phase-9 greedy seat, and the one 14.M expected to be
#: slow) 5.5 ms mean / 9.4 ms worst — i.e. the room is ~100× faster than the fastest clock a human
#: would set, and the spec's worry that the room could not meet its own interval does not survive
#: contact with a measurement. The floor stays as a floor rather than being deleted: it is what
#: keeps the *next* slow seat from silently overrunning, and :func:`_overrun_notice` reports actual
#: tick cost so the constant cannot quietly go stale.
MIN_CLOCK_SECONDS = 1
CLOCK_DEFAULT = 5


def page_draft() -> None:
    probe.ran("draft")
    settings = state.settings()
    seasons = state.seasons()
    if not seasons:
        st.error("The store has no FFC board for any season.")
        return
    d = state.draft()
    if d is None:
        _setup(settings, seasons)
        return
    _room(d)


# ------------------------------------------------------------------------------------------------
# starting a draft
# ------------------------------------------------------------------------------------------------
def _setup(settings, seasons: list[int]) -> None:
    st.header("🎯 Start a mock draft")
    lockbox_banner(settings)
    c1, c2 = st.columns(2)
    season = c1.selectbox("Season", seasons, index=0)

    # ★ T34 — the human-facing default is a NEW draft. `seed=None` tells `engine.start_draft` to
    # draw both the pick seed and the seating seed from OS entropy; locking is the opt-in.
    mode = c2.radio("Draft variation", ["Randomize (a new draft every time)", "Lock to a seed"],
                    horizontal=False,
                    help="Randomize draws a fresh pick seed AND a fresh seating order. Both are "
                         "shown once the draft starts, so any draft can be replayed exactly.")
    locked = mode.startswith("Lock")
    seed = room_seed = None
    if locked:
        s1, s2 = st.columns(2)
        seed = int(s1.number_input("Pick seed", 0, 1_000_000, 7))
        room_seed = int(s2.number_input("Seating seed", 0, 1_000_000, 1))

    n_teams = int(settings.n_teams)
    st.markdown("**Which seats do you drive?** (16.17 — any k of n)")
    cols = st.columns(min(n_teams, 10))
    default = int(settings.draft_slot)
    picked = [t for t in range(n_teams)
              if cols[t % len(cols)].checkbox(f"T{t + 1}", value=(t + 1 == default),
                                              key=f"seat{t}")]
    auto = st.multiselect("Hand any of your seats to the ADP autopicker",
                          [f"T{t + 1}" for t in picked])

    room_choice = st.selectbox(
        "The room", ["realistic", "default", "custom"],
        help="'realistic' is the shipped, calibrated ten-seat room minus one `balanced` seat per "
             "seat you take.")
    custom = ""
    if room_choice == "custom":
        custom = st.text_input(
            "Personalities, comma-separated",
            value=",".join(REALISTIC_ROOM[:max(0, n_teams - len(picked))]),
            help=f"Exactly {n_teams - len(picked)} names from: "
                 f"{', '.join(sorted(personalities()))}")

    if len(picked) > 1:
        st.warning(f"**{len(picked)} seats in one draft are ONE observation, not {len(picked)}** — "
                   f"your picks deplete each other's pools.")

    if st.button("Start draft", type="primary"):
        try:
            built = state.built_for(settings, int(season))
            st_obj, meta = engine.start_draft(
                built, human_seats=picked, settings=settings, season=int(season),
                seed=seed, room_seed=room_seed,
                room_arg=custom if room_choice == "custom" else room_choice,
                auto=[int(a[1:]) - 1 for a in auto])
            session.advance(st_obj, meta, built["risk"])
            state.put_draft(st_obj, meta, built["value_index"], built["risk"])
            st.rerun()
        except (ValueError, LookupError) as exc:
            st.error(str(exc))


# ------------------------------------------------------------------------------------------------
# the room
# ------------------------------------------------------------------------------------------------
def _room(d: dict) -> None:
    st_obj, meta = d["state"], d["meta"]
    sm = session.seat_map_from(meta)
    done = st_obj.is_done() or not st_obj.available

    if done and not st.session_state.get("_arrived_post_draft"):
        # the last pick sends you where a finished draft is read (14.L). Once — after that the
        # room stays reachable, because leaving a completed draft on screen is also a valid thing
        # to want.
        st.session_state["_arrived_post_draft"] = True
        nav.go("grid")

    top = st.columns([3, 1, 1])
    if done:
        top[0].success("**Draft complete.** The room grid has every team.")
    else:
        team = st_obj.team_on_clock()
        who = session.seat_label(team, sm)
        mine = team in st_obj.human_teams
        top[0].markdown(f"### {'🟢' if mine else '⏳'} On the clock: **{who}** (T{team + 1}) · "
                        f"round {st_obj.round()}, pick {st_obj.pick_in_round()} "
                        f"(#{st_obj.overall_pick} overall)")
    if top[1].button("Export to CLI", help="Write this draft where steps/mock_draft.py reads it"):
        p = engine.export_state(st_obj, meta, d.get("vi"), d.get("risk"))
        st.toast(f"Exported to {p}")
    if top[2].button("New draft", type="secondary"):
        state.clear_draft()
        st.rerun()

    # T34 — a randomized draft is only honest if it is also replayable, so the draw is shown.
    st.caption(f"Pick seed **{meta.get('seed')}** · seating seed **{meta.get('room_seed')}** — "
               f"lock these two on a new draft to replay this exact room.")

    with st.expander("The room", expanded=False):
        chips = pd.DataFrame({
            "TEAM": [f"T{t + 1}" for t in range(st_obj.n_teams)],
            "WHO": [session.seat_label(t, sm) for t in range(st_obj.n_teams)],
            "YOU": [t in sm.human_teams for t in range(st_obj.n_teams)],
            "AUTOPICK": [t in session.auto_teams(meta) for t in range(st_obj.n_teams)],
        })
        st.dataframe(chips, width="stretch", hide_index=True)

    if done:
        return

    board_col, rail_col = st.columns([3, 1], gap="medium")
    with rail_col:
        seat = _rail_seat(st_obj, sm)
        views.roster_rail(st_obj, seat, sm, d.get("vi"))
    with board_col:
        _clock_and_board(d, sm)


def _rail_seat(st_obj, sm) -> int:
    """Which of your seats the rail shows. 16.17: one at a time, never a combined view."""
    yours = sorted(st_obj.human_teams)
    if not yours:
        return 0
    if len(yours) == 1:
        return yours[0]
    on_clock = st_obj.team_on_clock()
    labels = [f"T{t + 1}" for t in yours]
    idx = yours.index(on_clock) if on_clock in yours else 0
    choice = st.selectbox("Seat", labels, index=idx, key="rail_seat")
    return yours[labels.index(choice)]


def _clock_and_board(d: dict, sm) -> None:
    st_obj, meta = d["state"], d["meta"]
    team = st_obj.team_on_clock()
    yours = team in st_obj.human_teams and team not in session.auto_teams(meta)

    # ⚠ **No `session_state.setdefault` on a widget key.** Writing `st.session_state["clock_secs"]`
    # before the slider that owns that key is Streamlit's documented anti-pattern: the widget's
    # `value=` and the pre-set state then both claim to be the source of truth, and Streamlit warns
    # and keeps one of them. The key alone already persists the choice across reruns. (Found by
    # driving the app under AppTest, not by any bar — the K1 lesson, one session later.)
    c1, c2 = st.columns([2, 3])
    secs = c1.slider("Seconds per modelled pick", 0, 30, CLOCK_DEFAULT, key="clock_secs",
                     help="0 = the room waits for you and picks all at once on Advance.")
    effective = _effective_interval(secs)
    if 0 < secs < MIN_CLOCK_SECONDS:
        c2.warning(f"A {secs}s clock is below the measured floor — running at "
                   f"{effective}s so the interval is one the room can actually meet.")
    else:
        c2.caption("**Your seat has no clock.** The room drafts on the timer; when it reaches one "
                   "of your seats it waits as long as you like. (Your choice, K1.5 step 3.)")

    if not yours:
        if secs > 0:
            _run_clock(d, effective)
        else:
            st.info("The room is picking — press **Advance** to run it to your next turn.")
            if st.button("Advance", type="primary"):
                session.advance(st_obj, meta, d.get("risk"))
                st.rerun()
        return

    _pick_controls(d, team)


def _effective_interval(secs: int) -> int:
    return max(int(secs), MIN_CLOCK_SECONDS) if secs > 0 else 0


def _run_clock(d: dict, interval: int) -> None:
    """14.M — one modelled pick per tick, in a fragment so a tick reruns *this*, not the page.

    ★ **The clock changes when picks happen, never which picks happen** (bar B3). It calls
    :func:`~fantasy_quant.draft.session.advance_one`, of which ``advance`` is the loop, so both
    paths consume ``DraftState.rng`` through the same call in the same order and a clocked draft
    and a stepped draft are the same draft at different speeds.

    The fragment is why 14.K had to come first: under ``st.tabs`` every tick would have re-run all
    four tab bodies, including the cost page's whole-board option build (T35).
    """
    @st.fragment(run_every=interval)
    def tick() -> None:
        cur = state.draft()
        if cur is None:
            return
        s, m = cur["state"], cur["meta"]
        if s.is_done() or not s.available:
            st.rerun(scope="app")
        on = s.team_on_clock()
        if on in s.human_teams and on not in session.auto_teams(m):
            st.rerun(scope="app")            # your turn — repaint the page, rail and board included
        t0 = time.perf_counter()
        entry = session.advance_one(s, m, cur.get("risk"), _room_fn(cur))
        took = time.perf_counter() - t0
        if entry is not None:
            st.session_state["clock_worst_s"] = max(
                float(st.session_state.get("clock_worst_s", 0.0)), took)
        _recent_picks(s, m)
        _overrun_notice(interval)

    st.caption(f"⏱ The room is drafting — one pick every {interval}s.")
    tick()


def _room_fn(d: dict):
    """The room's pick function, built once per draft rather than once per tick."""
    key = "_room_fn"
    if key not in st.session_state:
        st.session_state[key] = session.room_pick_fn(d["meta"], d.get("risk"))
    return st.session_state[key]


def _recent_picks(st_obj, meta) -> None:
    sm = session.seat_map_from(meta)
    log = st_obj.log[-8:]
    if not log:
        st.caption("No picks yet.")
        return
    frame = pd.DataFrame([{
        "PICK": f"{p['round']}.{p['pick_in_round']:02d}",
        "TEAM": f"T{p['team'] + 1}",
        "WHO": session.seat_label(int(p["team"]), sm),
        "PLAYER": p["player_name"], "POS": p["pos"], "ADP": p["adp"],
    } for p in reversed(log)])
    st.dataframe(frame, width="stretch", hide_index=True,
                 column_config={"ADP": st.column_config.NumberColumn("ADP", format="%.1f")})


def _overrun_notice(interval: int) -> None:
    """Report the clock's actual cost. A timer that silently overruns is the same class of defect
    as a bar that cannot fail, so the measured worst tick is shown rather than assumed."""
    worst = float(st.session_state.get("clock_worst_s", 0.0))
    if worst > interval:
        st.warning(f"The room's slowest pick this draft took {worst:.1f}s against a {interval}s "
                   f"clock — picks are landing late. Raise the interval.")
    elif worst:
        st.caption(f"Slowest pick so far: {worst * 1000:.0f} ms.")


# ------------------------------------------------------------------------------------------------
# making a pick — three ways in, one board
# ------------------------------------------------------------------------------------------------
def _pick_controls(d: dict, team: int) -> None:
    st_obj = d["state"]
    st.markdown("#### Your pick")

    # --- search that behaves like search: matches render UNDER the box, clickable, ADP-ranked ---
    q = st.text_input("Search the board", key=f"pick_q_{st_obj.overall_pick}",
                      placeholder="name or board #",
                      help="Type a name. Matches appear below — Enter never drafts anyone.")
    if q.strip():
        found = session.resolve_pick(st_obj, team, q)
        if isinstance(found, int):
            _confirm_bar(d, team, found, why="matched your search")
        elif not found:
            st.error(f"No available player matching “{q}”.")
        else:
            # ⚠ deliberately two-step. `st.text_input` fires on Enter and Streamlit has no keypress
            # hook, so "Enter drafts the top hit" would let a stray Enter cost a round.
            st.caption(f"{len(found)} matches — click one to load it into the confirm bar.")
            for m in found[:10]:
                if st.button(f"{m['player_name']} · {m['pos']} · ADP {m['adp']:.1f}",
                             key=f"hit_{st_obj.overall_pick}_{m['index']}", width="stretch"):
                    st.session_state["pending_pick"] = int(m["index"])
                    st.rerun()

    pending = st.session_state.get("pending_pick")
    if pending is not None and pending in st_obj.available:
        _confirm_bar(d, team, int(pending), why="selected")

    st.markdown("**Best available**")
    c1, c2, c3 = st.columns([2, 1, 1])
    pos = c1.multiselect("Position", ["QB", "RB", "WR", "TE", "K", "DST"],
                         key=f"pos_{st_obj.overall_pick}")
    n = c2.slider("Rows", 10, 100, 25, step=5, key=f"n_{st_obj.overall_pick}")
    advanced = c3.toggle("Advanced", value=False, key=f"adv_{st_obj.overall_pick}",
                         help="The full value/risk chain instead of the four drafting columns.")

    view, selected = views.board_table(
        st_obj, team=team, pos=",".join(pos) if pos else None, n=n, advanced=advanced,
        key=f"board_{st_obj.overall_pick}", selectable=True)
    if selected is not None:
        st.session_state["pending_pick"] = int(selected)
        _confirm_bar(d, team, int(selected), why="selected on the board")

    # a literal button per row is fine for the top handful and gets slow past that (14.K spec), so
    # the quick row covers the picks a drafter actually makes at a glance and the table covers all.
    st.caption("Quick pick — the top of the board you are looking at:")
    quick = view.head(6)
    if len(quick):
        cols = st.columns(len(quick))
        for col, (idx, row) in zip(cols, quick.iterrows(), strict=False):
            if col.button(f"{row['PLAYER']}\n\n{row['POS']} · ADP {row['ADP']:.0f}",
                          key=f"quick_{st_obj.overall_pick}_{idx}", width="stretch"):
                _apply(d, team, int(idx))

    if st.button("Autopick this seat", key=f"auto_{st_obj.overall_pick}"):
        engine.autopick(st_obj, d["meta"], team, d.get("risk"))
        st.session_state.pop("pending_pick", None)
        st.rerun()


def _confirm_bar(d: dict, team: int, board_index: int, *, why: str) -> None:
    """Never a one-click irreversible pick without the name in front of the user — a mis-click
    costs a round, and a round is the most expensive unit in this app."""
    row = d["state"].board.loc[board_index]
    c1, c2 = st.columns([3, 1])
    c1.info(f"**{row['player_name']}** · {row['pos']} · ADP {float(row['adp']):.1f} "
            f"(#{board_index}) — {why}.")
    if c2.button("Draft him", type="primary", key=f"confirm_{d['state'].overall_pick}"):
        _apply(d, team, board_index)


def _apply(d: dict, team: int, board_index: int) -> None:
    engine.make_pick(d["state"], d["meta"], team, int(board_index), d.get("risk"))
    st.session_state.pop("pending_pick", None)
    st.rerun()
