"""14.N — the post-draft page: where a finished draft goes.

*"After the draft is done, I want to be in a finalized analysis page where I can see all opposing
teams and all post-draft analytics."* This is that page, and it is the **destination the draft room
navigates to on the last pick**.

★ **It absorbs the readouts K1.5 parked on the room page rather than duplicating them.** Standings,
season odds and the draft-flow profile lived behind a radio on the room grid because there was
nowhere else for them yet; the room page keeps the two things that are about *reading the draft*
(the grid and the log) and this page takes the four that are about *judging it*. Two render paths
for one table is how the K1 board and the CLI board drifted apart, one altitude down.

★ **Reachable throughout, not gated on completion.** The literal reading of the spec — move the
readouts here and gate the page on a finished draft — would delete the running standings a drafter
looks at mid-draft. So the page renders live state with a banner while picks remain, and everything
that costs a simulation waits until the draft is done, which is also the only point at which those
numbers mean anything.

⚠ **Both 16.17 honesty rules render here or the page is wrong**: k human seats get k blocks with
nowhere to put a combined number, and your own seats' odds are not independent because they play
each other.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app import probe, state, views
from fantasy_quant.draft import session

#: Simulations run on arrival at a completed draft. 200 is the resolution floor 9.5 measured for a
#: title-probability comparison (below it the objective chases noise); 400 buys headroom for a
#: number that carries a letter grade, at a cost a human waits through once per draft.
ARRIVAL_SIMS = 400


def page_post() -> None:
    probe.ran("post")
    st.header("🏁 Post-draft analysis")
    d = state.draft()
    if d is None:
        st.info("No draft to analyse. Start one on the **Draft room** page.")
        return

    st_obj, meta = d["state"], d["meta"]
    sm = session.seat_map_from(meta)
    vi = d.get("vi")
    done = st_obj.is_done() or not st_obj.available
    n_humans = len(sm.human_teams)

    if not done:
        st.warning(f"**Draft in progress** — {len(st_obj.log)} of "
                   f"{st_obj.n_teams * st_obj.rounds} picks made. Rosters and the reach profile "
                   f"are live below; the season simulation waits for the final pick, because a "
                   f"half-drafted league has no season to simulate.")
    st.caption(f"{len(st_obj.log)} picks · pick seed {meta.get('seed')} · "
               f"seating seed {meta.get('room_seed')} · {n_humans} human seat(s)")

    odds = _odds(d, st_obj, meta, sm) if done else None

    _standings(st_obj, sm, vi, n_humans)
    if odds is not None:
        _season_odds(odds, sm)
    _your_teams(d, st_obj, meta, sm, vi, odds, n_humans)
    _room_rosters(st_obj, sm, vi)
    _draft_flow(st_obj, meta, sm, n_humans)


# ------------------------------------------------------------------------------------------------
# the season simulation — run once on arrival, keyed on the draft it describes
# ------------------------------------------------------------------------------------------------
def _odds_key(st_obj, meta) -> tuple:
    """What makes two calls the *same* simulation: this draft, at this many picks.

    Keyed on the log length as well as the seeds because a draft is only finished once — but the
    same seeds with a different number of picks is a different league, and serving the cached
    answer for it would be T32 (a cache key that omits the thing that changed) in miniature.
    """
    return (meta.get("seed"), meta.get("room_seed"), len(st_obj.log), ARRIVAL_SIMS)


def _odds(d: dict, st_obj, meta, sm):
    key = _odds_key(st_obj, meta)
    cached = st.session_state.get("odds")
    if cached and cached[0] == key:
        tab, prov = cached[1], cached[2]
    else:
        with st.spinner(f"Simulating {ARRIVAL_SIMS} seasons of this league…"):
            tab, prov = session.odds_table(state.con(), st_obj, meta, sm, sims=ARRIVAL_SIMS)
        st.session_state["odds"] = (key, tab, prov)
    st.session_state["odds_prov"] = prov
    return tab


# ------------------------------------------------------------------------------------------------
# the panels
# ------------------------------------------------------------------------------------------------
def _standings(st_obj, sm, vi, n_humans: int) -> None:
    st.subheader("Standings")
    views.summary_panel(st_obj, sm, vi)
    views.honesty_notes(n_humans)


def _season_odds(odds: pd.DataFrame, sm) -> None:
    st.subheader("Season odds")
    views.odds_panel(odds, st.session_state.get("odds_prov", []))
    if len(sm.human_teams) > 1:
        st.warning("Your seats' probabilities are **not** independent and do not add up to your "
                   "chance of winning — the sim runs one league in which they play each other.")


def _your_teams(d: dict, st_obj, meta, sm, vi, odds, n_humans: int) -> None:
    """14.I + 14.F, **once per human seat**, with nowhere to put a combined number."""
    if not sm.human_teams:
        st.subheader("Your team")
        st.caption("This draft has no human seat — every team was drafted by the room.")
        return

    st.subheader("Your team" + ("s" if n_humans > 1 else ""))
    if n_humans > 1:
        views.honesty_notes(n_humans)

    con = state.con()
    byes = _byes(int(meta.get("season", 2026)))
    grade = None
    if odds is not None:
        with st.spinner("Grading…"):
            grade = session.draft_grade(st_obj, meta, sm, odds=odds, vi=vi, byes=byes,
                                        elevation=session.elevation_ratio(con))
    frames = session.drift_frames(st_obj, meta, sm)

    for seat in sorted(sm.human_teams):
        with st.container(border=True):
            st.markdown(f"#### T{seat + 1} · {session.seat_label(seat, sm)}")
            if grade is not None:
                views.grade_panel(grade, seat)
            else:
                st.caption("The grade needs the season simulation, which waits for the final pick.")
            st.markdown("**Roster construction risk**")
            views.construction_panel(session.roster_construction_risk(
                st_obj, seat, vi=vi, byes=byes, elevation=session.elevation_ratio(con)))
            _reaches(frames, seat)


@st.cache_data(show_spinner=False)
def _byes(season: int) -> pd.Series:
    """Cached because it is a property of the season, not of the draft."""
    return session.bye_weeks(state.con(), int(season))


def _reaches(frames: dict, seat: int) -> None:
    picks = session.pick_drift_table(frames, seat)
    if picks.empty:
        return
    st.markdown("**Biggest reach & best value**")
    show = picks.rename(columns={"pick_no": "PICK", "round": "RD", "player": "PLAYER",
                                 "pos": "POS", "adp": "ADP", "reach_picks": "REACH"})
    ends = pd.concat([show.head(3), show.tail(3)]).drop_duplicates(subset=["PICK"])
    st.dataframe(ends[["PICK", "RD", "PLAYER", "POS", "ADP", "REACH"]], width="stretch",
                 hide_index=True, column_config={
                     "ADP": st.column_config.NumberColumn("ADP", format="%.1f"),
                     "REACH": st.column_config.NumberColumn(
                         "REACH", format="%+.1f",
                         help="10-team ADP picks, the unit every T15 bar is stated in. Positive = "
                              "you reached; negative = he fell to you.")})


def _room_rosters(st_obj, sm, vi) -> None:
    st.subheader("Every team")
    views.room_grid_panel(st_obj, sm, vi, by="slot")


def _draft_flow(st_obj, meta, sm, n_humans: int) -> None:
    st.subheader("How the room drafted")
    if not st_obj.log:
        st.caption("No picks yet.")
        return
    frames = session.drift_frames(st_obj, meta, sm)
    st.markdown("**Reach profile** — 10-team ADP picks, by round")
    st.dataframe(frames["profile"].round(2), width="stretch", hide_index=True)
    c1, c2 = st.columns([1, 2])
    c1.markdown("**Elite fall** (consensus top-12)")
    c1.json(frames["elite"])
    c2.markdown("**Per seat**")
    c2.dataframe(frames["seats"].round(2), width="stretch", hide_index=True)
    views.honesty_notes(n_humans, drift=True)
