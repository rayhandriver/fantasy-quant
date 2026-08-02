"""The pages that are not the draft room: **Settings**, **Board**, **Cost**.

Moved out of ``app/main.py`` by 14.K with their behaviour unchanged — ``st.tabs`` executed all
four bodies on every rerun (T35), ``st.navigation`` executes one, and that is the whole difference
at this altitude. What each page *does* is Session K1's and is not re-litigated here.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app import palette, probe, state, views
from app.settings_form import lockbox_banner, settings_form, validation_message
from fantasy_quant.draft import session
from fantasy_quant.draft.config import ARCHETYPES, DraftConfig
from fantasy_quant.draft.simulator import _prepare_board
from fantasy_quant.valuation.cost_report import personalization_cost


def page_settings() -> None:
    probe.ran("settings")
    st.header("⚙️ Your league")
    current = state.settings()
    lockbox_banner(current)
    settings, applied = settings_form(current)
    problem = validation_message(settings)
    if problem:
        st.error(f"That league can't be played as configured: {problem}")
        return
    if applied:
        st.session_state["settings"] = settings
        state.clear_draft()                     # a format change invalidates a draft in progress
        # A confirmation is a transient event, not a fact about the page — so it is a toast, which
        # is what Streamlit has for exactly this and which does not leave a block of prose behind.
        st.toast("Settings applied. The board rebuilds on the Board page.", icon="✅")

    with st.expander("What these settings actually change"):
        st.markdown(
            "**Platform-agnostic.** Enter what your league actually plays — we do not import from "
            "ESPN, Yahoo or Sleeper; you tell us the rules and every downstream number obeys "
            "them.\n\n"
            "- **Roster slots** drive the lineup solver *and* the VBD replacement level. A "
            "superflex league moves the QB replacement from QB10 to QB20, which lifts the best QB "
            "from overall rank 15 to 3 on the live board — a real re-ranking, not a caption.\n"
            "- **Scoring** re-scores both the consensus projection and the realized history "
            "through the same `RuleSet`, so the value board is internally consistent.\n"
            "- **Bracket** (teams, regular-season weeks, playoff teams) is what the Phase-10 "
            "season sim plays out for the odds on the Draft page.\n"
            "- **Non-default formats are supported and correctness-tested** — the multi-flex "
            "solver is checked against an exhaustive brute force — but carry no out-of-sample "
            "claim.")


def page_board() -> None:
    probe.ran("board")
    settings = state.settings()
    seasons = state.seasons()
    st.header("📋 The board")
    if not seasons:
        views.no_board_error()
        return
    c1, c2, c3 = st.columns([1, 1, 2])
    season = c1.selectbox("Season", seasons, index=0,
                          help="Defaults to the live season — the newest board in the store.")
    pos = c2.multiselect("Position", ["QB", "RB", "WR", "TE", "K", "DST"])
    n = c3.slider("Rows", 10, 200, 40, step=10)

    built = state.built_for(settings, int(season))
    # Provenance as chips rather than a sentence: it is four independent state facts, and a reader
    # scanning for "which ADP source is this" should not have to parse a clause to find it.
    b = st.columns([1, 1, 1, 3])
    b[0].badge(f"{len(built['board'])} players", color="gray")
    b[1].badge(f"{built['source'].upper()} ADP", color="blue",
               help="The availability signal — where players actually go in leagues shaped like "
                    "yours. Deliberately NOT the value signal.")
    b[2].badge(f"λ={built['lam']}", color="gray",
               help=f"The risk dial in the mean-variance objective. {built['n_base_value']} of "
                    f"these players carry a `base_value`; the rest draft on ADP fallback.")

    # A board with no draft in progress still needs a DraftState to be read through — an empty one
    # is exactly "nothing drafted yet", so the same `board_view` serves both cases.
    draft = state.draft()
    st_obj = draft["state"] if draft else _preview_state(built, settings, int(season))
    mode = views.mode_control("board_mode")
    views.cliff_strip(st_obj, st_obj.your_team, built["risk"])
    view, selected = views.board_table(st_obj, pos=",".join(pos) if pos else None, n=n,
                                       mode=mode, risk=built["risk"],
                                       key="board_page_table", selectable=True,
                                       vi=built["value_index"], byes=state.byes(int(season)),
                                       elevation=state.elevation())
    if mode == "ranges":
        views.range_note(view)
    if selected is not None:
        views.player_dialog(session.player_card(st_obj, int(selected),
                                                vi=built["value_index"], lam=built["lam"],
                                                risk=built["risk"]))

    st.divider()
    st.markdown("#### Why is this player worth that?")
    q = st.text_input(
        "Player", placeholder="e.g. Bijan", label_visibility="collapsed",
        help="The T27 arithmetic chain, from the consensus projection a human trusts to the "
             "`base_value` every seat optimizes. Each line is an identity read from the frozen "
             "contracts — nothing here is recomputed for display, which is what makes it an audit "
             "trail rather than a caption.")
    if q.strip():
        # ⚠ `st_obj.board`, not `built["board"]` — the *prepared* board, which is what the CLI
        # passes too. `_prepare_board` is where `player_key`/`player_name`/`pos` come from; the raw
        # frame carries `gsis_id`/`name`/`position` and `explain_chain` raises on it. Caught by
        # bar B5 on the live board, which is the argument for running the bars against the real
        # thing rather than a fixture that happens to have every column.
        views.why_panel(st_obj.board, built["value_index"], q, built["lam"])


def _preview_state(built: dict, settings, season: int):
    """A zero-pick :class:`DraftState` so the board renders before a draft is started.

    Seeded from a constant (T34): this state is read, never played, and drawing fresh entropy for
    it on every rerun would rebuild a seat map nobody looks at.
    """
    from app import engine

    seed, room_seed = state.PREVIEW_SEEDS
    st_obj, _ = engine.start_draft(built, human_seats=[int(settings.draft_slot) - 1],
                                   settings=settings, season=season, seed=seed,
                                   room_seed=room_seed)
    return st_obj


def page_cost() -> None:
    """The direct-indexing deliverable: your team beside the pure-value benchmark, priced."""
    probe.ran("cost")
    settings = state.settings()
    seasons = state.seasons()
    st.header("💸 What does wanting your team cost?")
    with st.popover("What this page is", icon=":material/help:"):
        st.markdown(
            "Build the team you *want*; see the honest price against the value-optimal team from "
            "the same seat, at the same risk dial.\n\n"
            "This is the whole point of the project — the 2026-07-04 reframe's *direct indexing* "
            "thesis. The benchmark is a **tracked** number, not the objective: we are not claiming "
            "your preferences are wrong, we are pricing them.")
    lockbox_banner(settings)
    if not seasons:
        views.no_board_error()
        return

    c1, c2, c3 = st.columns(3)
    season = c1.selectbox("Season", seasons, index=0, key="cost_season")
    archetype = c2.selectbox("Archetype", ARCHETYPES, format_func=lambda a: a.replace("_", "-"))
    lam = c3.slider("Risk dial λ", 0.0, 0.03, DraftConfig().risk_lambda, 0.005,
                    help="0 = risk-neutral (chase upside). Higher favours safe floors.")

    built = state.built_for(settings, int(season))
    # the **prepared** board, for the same reason the `why` panel needs it: `player_key` is what
    # `DraftConfig`'s must/never/tilt sets are keyed on, and the raw frame carries `gsis_id`.
    # Both instances of this were found by booting the app, not by the test suite (bar B5 and the
    # AppTest run) — *a column set is part of a function's contract even when nothing declares it.*
    board = _prepare_board(built["board"])
    labels = (board.assign(_a=pd.to_numeric(board["adp"], errors="coerce"))
              .dropna(subset=["_a"]).sort_values("_a"))
    opts = {f"{r['player_name']} — {r['pos']} (ADP {r['_a']:.0f})": str(r["player_key"])
            for _, r in labels.iterrows()}
    names = list(opts)
    must = st.multiselect("Must draft (secure within a ~2-round reach)", names)
    never = st.multiselect("Never draft (hard refusal)", names)
    reach = st.multiselect("Reach ~1 round early on", names)
    wait = st.multiselect("Willing to wait ~1 round on", names)

    if not st.button("Price it", type="primary"):
        st.info("Pick an archetype and any preferences, then **Price it**. The report runs paired "
                "drafts and a leave-one-out redraft per preference, so it is not instant.")
        return

    tilts = {opts[x]: 1.5 for x in reach} | {opts[x]: -1.5 for x in wait}
    try:
        cfg = DraftConfig(league=settings.league_setup(), archetype=archetype, risk_lambda=lam,
                          must_draft=[(opts[x], 2.0) for x in must],
                          never_draft={opts[x] for x in never}, tilts=tilts)
    except ValueError as exc:
        st.error(f"That combination doesn't work: {exc}")
        return

    with st.spinner("Drafting your team and its benchmark…"):
        rep = personalization_cost(state.con(), int(season), cfg,
                                   value_index=built["value_index"], k_drafts=4)

    m1, m2, m3 = st.columns(3)
    m1.metric("Benchmark value", f"{rep.benchmark_value:,.0f}",
              help="Unconstrained, same seat and same λ")
    m2.metric("Your team value", f"{rep.personalized_value:,.0f}")
    m3.metric("Cost of your preferences", f"{rep.cost_points:,.1f} pts", f"{rep.cost_pct:+.1%}",
              delta_color="inverse")

    for r in rep.secured.itertuples(index=False):
        if r.secured_frac < 1.0:
            st.warning(f"**{r.name}** was secured in only {r.secured_frac:.0%} of mock drafts — "
                       f"his ADP is too early to reach reliably within your budget.")

    left, right = st.columns(2)
    left.markdown("**Your team**")
    left.dataframe(palette.style_pos_columns(rep.personalized_roster, surface="cost"),
                   hide_index=True, width="stretch")
    right.markdown("**Benchmark (pure value)**")
    right.dataframe(palette.style_pos_columns(rep.benchmark_roster, surface="cost"),
                    hide_index=True, width="stretch")

    if not rep.per_constraint.empty:
        st.markdown("**What each preference cost**")
        show = rep.per_constraint.assign(
            cost=lambda d: d["cost_points"].round(1),
            share=lambda d: (d["cost_pct"] * 100).round(1))
        st.dataframe(show[["name", "cost", "share"]].rename(
            columns={"name": "preference", "cost": "cost (pts)",
                     "share": "cost (% of benchmark)"}), hide_index=True, width="stretch")
        with st.popover("How to read these costs", icon=":material/help:"):
            st.markdown(
                "**Leave-one-out.** Positive = the preference cost you value; negative = it "
                "happened to help.\n\n"
                "It is a **projected draft-day gap, not a realized-season claim** — and on ~10 "
                "seasons these costs are noise-dominated, which the lockbox confirmed directly: "
                "every archetype-cost confidence interval contained zero. Read the ordering and "
                "the sign; do not read the third significant figure.")
