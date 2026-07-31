"""14.L — every drafter's team on one page.

Teams across the top, picks or slots down the side. **BY PICK** is the classic draft board; **BY
SLOT** is every roster in starting order, filled by the frozen lineup solver.

★ **K2 moved the analysis off this page.** K1.5 parked the standings, the season odds and the
draft-flow profile here behind a radio, because 14.N did not exist yet and a nested ``st.tabs`` had
T35's defect. 14.N exists now, so those four readouts **moved** rather than being copied: this page
keeps the two things that are about *reading* the draft as it happens (the grid and the log), and
the post-draft page takes everything that is about *judging* it. Two render paths for one table is
how a display drifts away from what it displays.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app import nav, probe, state, views
from fantasy_quant.draft import session

VIEWS = ("Room grid", "Log", "Stat dictionary")


def page_grid() -> None:
    probe.ran("grid")
    st.header("🧑‍🤝‍🧑 The room")
    d = state.draft()
    if d is None:
        st.info("No draft in progress. Start one on the **Draft room** page.")
        st.divider()
        views.stat_dictionary_panel()
        return

    st_obj, meta = d["state"], d["meta"]
    sm = session.seat_map_from(meta)
    done = st_obj.is_done() or not st_obj.available
    st.caption(f"{len(st_obj.log)} picks · {'complete' if done else 'in progress'} · "
               f"pick seed {meta.get('seed')} · seating seed {meta.get('room_seed')}")
    if done and st.button("Go to the post-draft analysis", type="primary"):
        nav.go("post")

    choice = st.radio("View", VIEWS, horizontal=True, label_visibility="collapsed")
    if choice == "Room grid":
        by = st.radio("Layout", ["BY PICK", "BY SLOT"], horizontal=True,
                      help="BY PICK is the draft board. BY SLOT is every team's roster in "
                           "starting order, filled by the frozen lineup solver.")
        views.room_grid_panel(st_obj, sm, d.get("vi"),
                              by="pick" if by == "BY PICK" else "slot")
    elif choice == "Log":
        _log(st_obj, sm)
    else:
        views.stat_dictionary_panel()

    st.caption("Standings, season odds, the draft-flow profile, your grade and your roster-"
               "construction risk all live on the **Post-draft** page (14.N).")


def _log(st_obj, sm) -> None:
    log = pd.DataFrame(st_obj.log)
    if log.empty:
        st.caption("No picks yet.")
        return
    log = log.assign(WHO=[session.seat_label(int(t), sm) for t in log["team"]])
    st.dataframe(log[["round", "pick_in_round", "team", "WHO", "player_name", "pos",
                      "adp"]].iloc[::-1], width="stretch", hide_index=True)
