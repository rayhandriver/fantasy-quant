"""14.L — every drafter's team on one page, and where a finished draft lands.

Teams across the top, picks or slots down the side. This is also the new home of the readouts that
were tabs *inside* the K1 draft tab (summary, season odds, draft flow, log): a nested ``st.tabs``
has T35's defect too — every body runs on every rerun, and the draft-flow body calls
``sim_drift_panel``. They sit behind a **radio** here, which renders one.

⚠ The full post-draft analysis page is **14.N (Session K2)**; this is its precursor, and the
readouts move there when it exists rather than being duplicated into it.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app import probe, state, views
from fantasy_quant.draft import session

VIEWS = ("Room grid", "Standings", "Season odds", "Draft flow", "Log", "Stat dictionary")


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
    n_humans = len(sm.human_teams)
    done = st_obj.is_done() or not st_obj.available
    st.caption(f"{len(st_obj.log)} picks · {'complete' if done else 'in progress'} · "
               f"pick seed {meta.get('seed')} · seating seed {meta.get('room_seed')}")

    choice = st.radio("View", VIEWS, horizontal=True, label_visibility="collapsed")
    if choice == "Room grid":
        by = st.radio("Layout", ["BY PICK", "BY SLOT"], horizontal=True,
                      help="BY PICK is the draft board. BY SLOT is every team's roster in "
                           "starting order, filled by the frozen lineup solver.")
        views.room_grid_panel(st_obj, sm, d.get("vi"),
                              by="pick" if by == "BY PICK" else "slot")
    elif choice == "Standings":
        views.summary_panel(st_obj, sm, d.get("vi"))
        views.honesty_notes(n_humans)
    elif choice == "Season odds":
        _odds(st_obj, meta, sm)
    elif choice == "Draft flow":
        _drift(st_obj, meta, sm, n_humans)
    elif choice == "Log":
        _log(st_obj, sm)
    else:
        views.stat_dictionary_panel()


def _odds(st_obj, meta, sm) -> None:
    if not st_obj.is_done():
        st.caption("Season odds are available once the draft is complete.")
        return
    sims = st.slider("Simulations", 100, 2000, 400, step=100,
                     help="The sim is not interactive-speed; it runs on demand, never per rerun.")
    if st.button("Run the season sim"):
        with st.spinner(f"Simulating {sims} seasons…"):
            tab, prov = session.odds_table(state.con(), st_obj, meta, sm, sims=int(sims))
        st.session_state["odds"] = (tab, prov)
    if "odds" in st.session_state:
        tab, prov = st.session_state["odds"]
        views.odds_panel(tab, prov)
        if len(sm.human_teams) > 1:
            st.warning("Your seats' probabilities are **not** independent and do not add up to "
                       "your chance of winning — the sim runs one league in which they play each "
                       "other.")


def _drift(st_obj, meta, sm, n_humans: int) -> None:
    if not st_obj.log:
        st.caption("No picks yet.")
        return
    d = session.drift_frames(st_obj, meta, sm)
    st.markdown("**Reach profile** — 10-team ADP picks")
    st.dataframe(d["profile"].round(2), width="stretch", hide_index=True)
    st.markdown("**Elite fall** (consensus top-12)")
    st.json(d["elite"])
    st.markdown("**Per seat**")
    st.dataframe(d["seats"].round(2), width="stretch", hide_index=True)
    views.honesty_notes(n_humans, drift=True)


def _log(st_obj, sm) -> None:
    log = pd.DataFrame(st_obj.log)
    if log.empty:
        st.caption("No picks yet.")
        return
    log = log.assign(WHO=[session.seat_label(int(t), sm) for t in log["team"]])
    st.dataframe(log[["round", "pick_in_round", "team", "WHO", "player_name", "pos",
                      "adp"]].iloc[::-1], width="stretch", hide_index=True)
