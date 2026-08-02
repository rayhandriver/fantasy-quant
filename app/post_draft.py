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

from app import palette, probe, state, views
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
    chips = st.columns([1, 1, 1, 3])
    chips[0].badge(f"{len(st_obj.log)} picks", color="gray")
    chips[1].badge(f"{n_humans} human seat(s)", color="gray")
    chips[2].badge(f"seeds {meta.get('seed')} / {meta.get('room_seed')}", color="gray",
                   help="Pick seed and seating seed (T34) — lock both on a new draft to replay "
                        "this exact room.")

    # ★ Everything expensive is computed **once, here**, and handed to the tabs. `st.tabs` executes
    # every tab body on every rerun (T35), which is why K1.5 pulled the room page's nested tabs
    # out — the cost that made it a 🟠 there was that a *timer-driven* rerun multiplied it. 14.N has
    # no timer, and these four readouts were all computed unconditionally on one page before this
    # session, so the tabs cost nothing new. The rule that keeps it true: nothing below re-derives.
    odds = _odds(d, st_obj, meta, sm) if done else None
    frames = session.drift_frames(st_obj, meta, sm)
    summary = session.summary_table(st_obj, sm, vi)
    grade = _grade(st_obj, meta, sm, vi, odds)
    strength = session.positional_strength(st_obj, sm, vi)

    _hero(sm, summary, odds, grade, frames, n_humans)

    tabs = st.tabs(["Your team" + ("s" if n_humans > 1 else ""), "Standings", "Season odds",
                    "Every team", "How the room drafted"])
    with tabs[0]:
        _your_teams(st_obj, meta, sm, vi, n_humans, grade=grade, frames=frames,
                    strength=strength)
    with tabs[1]:
        _standings(st_obj, sm, vi, n_humans)
    with tabs[2]:
        _season_odds(odds, sm)
    with tabs[3]:
        _room_rosters(st_obj, sm, vi)
    with tabs[4]:
        _draft_flow(frames, n_humans)


# ------------------------------------------------------------------------------------------------
# the hero row — a report card leads with a verdict, not with a table
# ------------------------------------------------------------------------------------------------
def _hero(sm, summary: pd.DataFrame, odds, grade, frames: dict, n_humans: int) -> None:
    """**Grade letter · title fair-share multiple · STARTABLE rank**, then best and worst pick.

    ⚠ **T29 governs the order and it is not a style choice.** The absolute title percentage is the
    weakest number in the stack wearing the most authoritative costume: the season sim carries a
    documented **−113 pts/team** level bias and a *marginal* playoff Brier of 0.240. A ratio to the
    uniform share moves all ten teams together and survives that bias; a percentage does not. So the
    multiple is the big number and the percentage is the small print under it — *no hero-number
    redesign may promote the absolute probability above the fair share.*

    ⚠ **16.17: one block per human seat, never a blend.** k human teams in one draft are ONE
    observation, so there is deliberately nowhere here to put a combined grade.
    """
    if not sm.human_teams:
        return                      # the "no human seat" line lives in the Your-team tab, once

    # An ordinal over a column that already exists. Sorting is formatting; the model quantity is
    # `startable`, which `session.summary_table` computed, and this does not change it.
    ranks = (summary.set_index("team")["startable"].rank(ascending=False, method="min")
             if "startable" in summary.columns else None)

    for seat in sorted(sm.human_teams):
        team_no = seat + 1
        with st.container(border=True):
            st.markdown(f"### T{team_no} · {session.seat_label(seat, sm)}")
            c = st.columns(4)
            row = grade[grade["team"] == team_no] if grade is not None else None
            if row is not None and len(row):
                r = row.iloc[0]
                c[0].metric("Draft grade", str(r["letter"]), f"{r['total']:.0f} / 100",
                            delta_color="off",
                            help="Weighted composite, curved across the ten teams in this room. "
                                 "The weights are printed on the Your-team tab.")
            else:
                c[0].metric("Draft grade", "—", "needs the season sim", delta_color="off")

            if odds is not None:
                o = odds[odds["team"] == team_no]
                if len(o):
                    c[1].metric("Title fair share", f"{float(o.iloc[0]['title_fair']):.2f}×",
                                f"{float(o.iloc[0]['title']):.1%} absolute", delta_color="off",
                                help="1.00× is a fair share of titles. Read the multiple — the "
                                     "percentage inherits the sim's −113 pts/team level bias and "
                                     "the ratio does not.")
                    c[2].metric("Playoff fair share",
                                f"{float(o.iloc[0]['playoff_fair']):.2f}×",
                                f"{float(o.iloc[0]['playoff']):.1%} absolute", delta_color="off")
            else:
                c[1].metric("Title fair share", "—", "needs the season sim", delta_color="off")

            if ranks is not None and team_no in ranks.index:
                c[3].metric("STARTABLE rank", f"{int(ranks.loc[team_no])} of {len(summary)}",
                            help="Rank on the best legal starting lineup's base_value — the "
                                 "slot-aware number, not the slot-blind CAPITAL sum (T28).")
            _headline_picks(frames, seat)

    if n_humans > 1:
        views.honesty_notes(n_humans)


def _headline_picks(frames: dict, seat: int) -> None:
    """The one pair a report card owes: **biggest reach** and **best value**.

    ``pick_drift_table`` is sorted most-reached first, so the two ends of the frame *are* the pair.
    It was already computed and rendered as a six-row table under a heading nobody reads.
    """
    picks = session.pick_drift_table(frames, seat)
    if picks.empty:
        return
    worst, best = picks.iloc[0], picks.iloc[-1]
    c1, c2 = st.columns(2)
    c1.metric(f"Biggest reach · {worst['player']}", f"{float(worst['reach_picks']):+.1f} picks",
              f"{worst['pos']} · ADP {float(worst['adp']):.1f} · taken {int(worst['pick_no'])}",
              delta_color="off",
              help="10-team ADP picks, the unit every T15 bar is stated in. Positive = you took "
                   "him earlier than the room would have.")
    c2.metric(f"Best value · {best['player']}", f"{float(best['reach_picks']):+.1f} picks",
              f"{best['pos']} · ADP {float(best['adp']):.1f} · taken {int(best['pick_no'])}",
              delta_color="off", help="Negative = he fell to you.")


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
    views.summary_panel(st_obj, sm, vi)
    views.honesty_notes(n_humans)


def _season_odds(odds, sm) -> None:
    if odds is None:
        st.info("The season simulation waits for the final pick — a half-drafted league has no "
                "season to simulate.")
        return
    views.odds_panel(odds, st.session_state.get("odds_prov", []))
    if len(sm.human_teams) > 1:
        st.warning("Your seats' probabilities are **not** independent and do not add up to your "
                   "chance of winning — the sim runs one league in which they play each other.")


def _grade(st_obj, meta, sm, vi, odds):
    """14.I, computed once for the whole page. ``None`` until the draft is finished."""
    if odds is None or not sm.human_teams:
        return None
    con = state.con()
    with st.spinner("Grading…"):
        return session.draft_grade(st_obj, meta, sm, odds=odds, vi=vi,
                                   byes=_byes(int(meta.get("season", 2026))),
                                   elevation=session.elevation_ratio(con))


def _your_teams(st_obj, meta, sm, vi, n_humans: int, *, grade, frames, strength) -> None:
    """14.I + 14.F, **once per human seat**, with nowhere to put a combined number."""
    if not sm.human_teams:
        st.info("This draft has no human seat — every team was drafted by the room.")
        return

    if n_humans > 1:
        views.honesty_notes(n_humans)

    con = state.con()
    byes = _byes(int(meta.get("season", 2026)))
    for seat in sorted(sm.human_teams):
        with st.container(border=True):
            st.markdown(f"#### T{seat + 1} · {session.seat_label(seat, sm)}")
            if grade is not None:
                views.grade_panel(grade, seat)
            # ★ A6's positional-strength chart — deferred out of UI-1 by name because it needed a
            # genuinely new derivation (per-position starting value per team), which is UI-2's
            # character rather than a formatting session's.
            views.positional_strength_panel(strength, seat)
            st.markdown("**Roster construction risk**")
            views.construction_panel(session.roster_construction_risk(
                st_obj, seat, vi=vi, byes=byes, elevation=session.elevation_ratio(con)))
            _reaches(frames, seat)


def _byes(season: int) -> pd.Series:
    """UI-2 — moved to :func:`app.state.byes`, because the board needs the same table at pick time.
    Kept as a one-line forwarder so this page's four call sites read the way they did."""
    return state.byes(int(season))


def _reaches(frames: dict, seat: int) -> None:
    picks = session.pick_drift_table(frames, seat)
    if picks.empty:
        return
    st.markdown("**Every reach and every steal, both ends**")
    show = picks.rename(columns={"pick_no": "PICK", "round": "RD", "player": "PLAYER",
                                 "pos": "POS", "adp": "ADP", "reach_picks": "REACH"})
    ends = pd.concat([show.head(3), show.tail(3)]).drop_duplicates(subset=["PICK"])
    st.dataframe(palette.style_pos_columns(
        ends[["PICK", "RD", "PLAYER", "POS", "ADP", "REACH"]], surface="reaches"),
                 width="stretch", hide_index=True, column_config={
                     "ADP": st.column_config.NumberColumn("ADP", format="%.1f"),
                     "REACH": st.column_config.NumberColumn(
                         "REACH", format="%+.1f",
                         help="10-team ADP picks, the unit every T15 bar is stated in. Positive = "
                              "you reached; negative = he fell to you.")})


def _room_rosters(st_obj, sm, vi) -> None:
    views.room_grid_panel(st_obj, sm, vi, by="slot", surface="post_draft_rosters")


def _draft_flow(frames: dict, n_humans: int) -> None:
    if frames["panel"].empty:
        views.no_picks_yet()
        return
    st.markdown("**Reach profile** — 10-team ADP picks, by round")
    st.dataframe(frames["profile"].round(2), width="stretch", hide_index=True)
    c1, c2 = st.columns([1, 2])
    c1.markdown("**Elite fall** (consensus top-12)")
    # T38 — this was `c1.json(frames["elite"])`: a pretty-printed debug dump on the page whose
    # whole job is to be a report card. It survived because K2 *moved* the readouts here from the
    # room page rather than rewriting them, which is the cheapest way for a defect to change
    # address without being looked at.
    c1.dataframe(views.elite_fall_table(frames["elite"]), width="stretch", hide_index=True)
    c2.markdown("**Per seat**")
    c2.dataframe(frames["seats"].round(2), width="stretch", hide_index=True)
    views.honesty_notes(n_humans, drift=True)
