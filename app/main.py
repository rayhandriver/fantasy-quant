"""Fantasy-Quant — the draft-day app (Phase 14.1 / Session K1).

    uv sync --extra ui
    uv run streamlit run app/main.py

Four tabs, in the order a drafter uses them: **Settings** (your league, 17.3) → **Board** (the live
board with the T27 value chain and ``why``) → **Draft room** (any k of n seats against the
calibrated room, 16.15/16.17/14.J) → **Cost** (what your preferences cost against the pure-value
benchmark — the direct-indexing deliverable the 2026-07-04 reframe was built around).

★ **This app derives nothing.** Every number comes from :mod:`fantasy_quant.draft.session`, which
``steps/mock_draft.py`` also reads, so the app and the CLI cannot disagree — there is one
computation and two renderers. That is Session K1's bar B1, satisfied by construction rather than
by testing two implementations against each other and hoping.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app import engine, views
from app.settings_form import lockbox_banner, settings_form, validation_message
from fantasy_quant.draft import session
from fantasy_quant.draft.config import ARCHETYPES, DraftConfig, LeagueSettings
from fantasy_quant.draft.personalities import REALISTIC_ROOM, personalities
from fantasy_quant.draft.simulator import _prepare_board
from fantasy_quant.valuation.cost_report import personalization_cost


@st.cache_resource(show_spinner=False)
def _con():
    return engine.connect()


@st.cache_data(show_spinner=False)
def _seasons() -> list[int]:
    return engine.boarded_seasons(_con())


@st.cache_data(show_spinner="Building the board (consensus → VBD → risk-dialed)…")
def _build(season: int, settings_key: tuple) -> dict:
    """The one cached ``(board, value_index, risk)`` build.

    Keyed on the *settings tuple* rather than the object because a league's shape changes the
    board: ``n_teams`` moves the replacement levels the value index is computed against, so a
    superflex league is a genuinely different board and must not be served from the 1-QB cache.
    """
    return engine.build(_con(), season, LeagueSettings(**dict(settings_key)))


def _settings() -> LeagueSettings:
    return st.session_state.get("settings") or LeagueSettings()


def _settings_key(s: LeagueSettings) -> tuple:
    """A hashable identity for the fields that change the board or the lineup solver."""
    return tuple(sorted({
        "n_teams": s.n_teams, "rounds": s.rounds, "qb": s.qb, "rb": s.rb, "wr": s.wr, "te": s.te,
        "flex": s.flex, "superflex": s.superflex, "k": s.k, "dst": s.dst, "bench": s.bench,
        "scoring_preset": s.scoring_preset, "reg_weeks": s.reg_weeks,
        "playoff_teams": s.playoff_teams, "draft_slot": s.draft_slot,
    }.items()))


# ------------------------------------------------------------------------------------------------
# tabs
# ------------------------------------------------------------------------------------------------
def tab_settings() -> None:
    st.subheader("Your league")
    st.caption("Platform-agnostic — enter what your league actually plays. We do not import from "
               "ESPN, Yahoo or Sleeper; you tell us the rules and every downstream number obeys "
               "them.")
    current = _settings()
    settings, applied = settings_form(current)
    problem = validation_message(settings)
    if problem:
        st.error(f"That league can't be played as configured: {problem}")
        return
    if applied:
        st.session_state["settings"] = settings
        st.session_state.pop("draft", None)     # a format change invalidates a draft in progress
        st.success("Settings applied. The board rebuilds on the Board tab.")
    lockbox_banner(settings)

    with st.expander("What these settings actually change"):
        st.markdown(
            "- **Roster slots** drive the lineup solver *and* the VBD replacement level. A "
            "superflex league moves the QB replacement from QB10 to QB20, which lifts the best QB "
            "from overall rank 15 to 3 on the live board — a real re-ranking, not a caption.\n"
            "- **Scoring** re-scores both the consensus projection and the realized history "
            "through the same `RuleSet`, so the value board is internally consistent.\n"
            "- **Bracket** (teams, regular-season weeks, playoff teams) is what the Phase-10 "
            "season sim plays out for the odds on the Draft tab.\n"
            "- **Non-default formats are supported and correctness-tested** — the multi-flex "
            "solver is checked against an exhaustive brute force — but carry no out-of-sample "
            "claim.")


def tab_board() -> None:
    settings = _settings()
    seasons = _seasons()
    if not seasons:
        st.error("The store has no FFC board for any season.")
        return
    c1, c2, c3 = st.columns([1, 1, 2])
    season = c1.selectbox("Season", seasons, index=0,
                          help="Defaults to the live season — the newest board in the store.")
    pos = c2.multiselect("Position", ["QB", "RB", "WR", "TE", "K", "DST"])
    n = c3.slider("Rows", 10, 200, 40, step=10)

    built = _build(int(season), _settings_key(settings))
    st.caption(f"{len(built['board'])} players · {built['source'].upper()} ADP + frozen "
               f"Phase-4/5 context · {built['n_base_value']} carry base_value · "
               f"λ={built['lam']}")

    # A board with no draft in progress still needs a DraftState to be read through — an empty one
    # is exactly "nothing drafted yet", so the same `board_view` serves both cases.
    draft = st.session_state.get("draft")
    state = draft["state"] if draft else _empty_state(built, settings, int(season))
    views.board_table(state, pos=",".join(pos) if pos else None, n=n)

    st.divider()
    st.markdown("#### Why is this player worth that?")
    st.caption("The arithmetic chain from the consensus projection a human trusts to the "
               "`base_value` every seat optimizes. Each line is read from the frozen contracts — "
               "nothing here is recomputed for display.")
    q = st.text_input("Player", placeholder="e.g. Bijan", label_visibility="collapsed")
    if q.strip():
        # ⚠ `state.board`, not `built["board"]` — the *prepared* board, which is what the CLI
        # passes too. `_prepare_board` is where `player_key`/`player_name`/`pos` come from; the raw
        # frame carries `gsis_id`/`name`/`position` and `explain_chain` raises on it. Caught by
        # bar B5 on the live board, which is the argument for running the bars against the real
        # thing rather than a fixture that happens to have every column.
        views.why_panel(state.board, built["value_index"], q, built["lam"])


def _empty_state(built: dict, settings: LeagueSettings, season: int):
    """A zero-pick :class:`DraftState` so the board tab renders before a draft is started."""
    state, _ = engine.start_draft(built, human_seats=[int(settings.draft_slot) - 1],
                                  settings=settings, season=season)
    return state


def tab_draft() -> None:
    settings = _settings()
    seasons = _seasons()
    if not seasons:
        st.error("The store has no FFC board for any season.")
        return
    draft = st.session_state.get("draft")

    if draft is None:
        _draft_setup(settings, seasons)
        return

    state, meta = draft["state"], draft["meta"]
    sm = session.seat_map_from(meta)
    n_humans = len(sm.human_teams)

    top = st.columns([3, 1, 1])
    if state.is_done() or not state.available:
        top[0].success("**Draft complete.**")
    else:
        team = state.team_on_clock()
        who = session.seat_label(team, sm)
        mine = team in state.human_teams
        top[0].markdown(f"### {'🟢' if mine else '⏳'} On the clock: **{who}** (T{team + 1}) · "
                        f"round {state.round()}, pick {state.pick_in_round()} "
                        f"(#{state.overall_pick} overall)")
    if top[1].button("Export to CLI", help="Write this draft where steps/mock_draft.py reads it"):
        p = engine.export_state(state, meta, draft.get("vi"), draft.get("risk"))
        st.toast(f"Exported to {p}")
    if top[2].button("New draft", type="secondary"):
        st.session_state.pop("draft", None)
        st.rerun()

    # ---- the room, with the per-seat YOU toggle already resolved into the SeatMap (14.J) -------
    with st.expander("The room", expanded=False):
        chips = pd.DataFrame({
            "TEAM": [f"T{t + 1}" for t in range(state.n_teams)],
            "WHO": [session.seat_label(t, sm) for t in range(state.n_teams)],
            "YOU": [t in sm.human_teams for t in range(state.n_teams)],
            "AUTOPICK": [t in session.auto_teams(meta) for t in range(state.n_teams)],
        })
        st.dataframe(chips, width="stretch", hide_index=True)

    if not (state.is_done() or not state.available):
        _draft_clock(state, meta, sm, draft)

    st.divider()
    tabs = st.tabs(["Summary", "Season odds", "Draft flow", "Log"])
    with tabs[0]:
        views.summary_panel(state, sm, draft.get("vi"))
        views.honesty_notes(n_humans)
        for t in sorted(sm.human_teams):
            views.roster_panel(state, t, label=f"Your team — T{t + 1}")
    with tabs[1]:
        _odds(state, meta, sm)
    with tabs[2]:
        _drift(state, meta, sm, n_humans)
    with tabs[3]:
        log = pd.DataFrame(state.log)
        if log.empty:
            st.caption("No picks yet.")
        else:
            log = log.assign(WHO=[session.seat_label(int(t), sm) for t in log["team"]])
            st.dataframe(log[["round", "pick_in_round", "team", "WHO", "player_name", "pos",
                              "adp"]].iloc[::-1], width="stretch", hide_index=True)


def _draft_setup(settings: LeagueSettings, seasons: list[int]) -> None:
    """Start a draft: season, your seats, the room. This is 14.J's per-seat YOU toggle."""
    st.subheader("Start a mock draft")
    lockbox_banner(settings)
    c1, c2 = st.columns(2)
    season = c1.selectbox("Season", seasons, index=0)
    seed = c2.number_input("Seed", 0, 10_000, 7, help="Same seed + same room = the same draft.")

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
            built = _build(int(season), _settings_key(settings))
            state, meta = engine.start_draft(
                built, human_seats=picked, settings=settings, season=int(season), seed=int(seed),
                room_arg=custom if room_choice == "custom" else room_choice,
                auto=[int(a[1:]) - 1 for a in auto])
            made = session.advance(state, meta, built["risk"])
            st.session_state["draft"] = {"state": state, "meta": meta, "vi": built["value_index"],
                                         "risk": built["risk"], "made": made}
            st.rerun()
        except (ValueError, LookupError) as exc:
            st.error(str(exc))


def _draft_clock(state, meta, sm, draft) -> None:
    """The pick control for whichever of your seats is on the clock."""
    team = state.team_on_clock()
    if team not in state.human_teams:
        st.info("The room is picking — press **Advance** to run it to your next turn.")
        if st.button("Advance", type="primary"):
            session.advance(state, meta, draft.get("risk"))
            st.rerun()
        return

    left, right = st.columns([2, 1])
    with left:
        views.roster_panel(state, team, label=f"Your roster — T{team + 1}")
        needs = state.starter_needs(team)
        short = ", ".join(f"{k} {v}" for k, v in needs.items() if v)
        st.caption(f"Starter needs: **{short or 'none — starters filled'}**")
    with right:
        st.markdown("**Make a pick**")
        q = st.text_input("Player", key=f"pick_q_{state.overall_pick}",
                          placeholder="name or board #")
        c1, c2 = st.columns(2)
        if c1.button("Pick", type="primary", disabled=not q.strip()):
            found = session.resolve_pick(state, team, q)
            if isinstance(found, list):
                if not found:
                    st.error(f"No available player matching “{q}”.")
                else:
                    st.warning(f"{len(found)} matches — use the board # column:")
                    st.dataframe(pd.DataFrame(found), width="stretch", hide_index=True)
            else:
                engine.make_pick(state, meta, team, found, draft.get("risk"))
                st.rerun()
        if c2.button("Autopick"):
            engine.autopick(state, meta, team, draft.get("risk"))
            st.rerun()

    st.markdown("**Best available**")
    pos = st.multiselect("Position", ["QB", "RB", "WR", "TE", "K", "DST"],
                         key=f"pos_{state.overall_pick}")
    views.board_table(state, team=team, pos=",".join(pos) if pos else None, n=25)


def _odds(state, meta, sm) -> None:
    if not state.is_done():
        st.caption("Season odds are available once the draft is complete.")
        return
    sims = st.slider("Simulations", 100, 2000, 400, step=100,
                     help="The sim is not interactive-speed; it runs on demand, never per rerun.")
    if st.button("Run the season sim"):
        with st.spinner(f"Simulating {sims} seasons…"):
            tab, prov = session.odds_table(_con(), state, meta, sm, sims=int(sims))
        st.session_state["odds"] = (tab, prov)
    if "odds" in st.session_state:
        tab, prov = st.session_state["odds"]
        views.odds_panel(tab, prov)
        if len(sm.human_teams) > 1:
            st.warning("Your seats' probabilities are **not** independent and do not add up to "
                       "your chance of winning — the sim runs one league in which they play each "
                       "other.")


def _drift(state, meta, sm, n_humans: int) -> None:
    if not state.log:
        st.caption("No picks yet.")
        return
    d = session.drift_frames(state, meta, sm)
    st.markdown("**Reach profile** — 10-team ADP picks")
    st.dataframe(d["profile"].round(2), width="stretch", hide_index=True)
    st.markdown("**Elite fall** (consensus top-12)")
    st.json(d["elite"])
    st.markdown("**Per seat**")
    st.dataframe(d["seats"].round(2), width="stretch", hide_index=True)
    views.honesty_notes(n_humans, drift=True)


def tab_cost() -> None:
    """The direct-indexing deliverable: your team beside the pure-value benchmark, priced."""
    settings = _settings()
    seasons = _seasons()
    st.subheader("What does wanting your team cost?")
    st.caption("Build the team you want; see the honest price against the value-optimal team from "
               "the same seat, at the same risk dial. This is the whole point of the project — the "
               "benchmark is a *tracked* number, not the objective.")
    lockbox_banner(settings)

    c1, c2, c3 = st.columns(3)
    season = c1.selectbox("Season", seasons, index=0, key="cost_season")
    archetype = c2.selectbox("Archetype", ARCHETYPES, format_func=lambda a: a.replace("_", "-"))
    lam = c3.slider("Risk dial λ", 0.0, 0.03, DraftConfig().risk_lambda, 0.005,
                    help="0 = risk-neutral (chase upside). Higher favours safe floors.")

    built = _build(int(season), _settings_key(settings))
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
        rep = personalization_cost(_con(), int(season), cfg,
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
    left.dataframe(rep.personalized_roster, hide_index=True, width="stretch")
    right.markdown("**Benchmark (pure value)**")
    right.dataframe(rep.benchmark_roster, hide_index=True, width="stretch")

    if not rep.per_constraint.empty:
        st.markdown("**What each preference cost**")
        show = rep.per_constraint.assign(
            cost=lambda d: d["cost_points"].round(1),
            share=lambda d: (d["cost_pct"] * 100).round(1))
        st.dataframe(show[["name", "cost", "share"]].rename(
            columns={"name": "preference", "cost": "cost (pts)",
                     "share": "cost (% of benchmark)"}), hide_index=True, width="stretch")
        st.caption("Leave-one-out. Positive = the preference cost you value; negative = it "
                   "happened to help. A projected draft-day gap, not a realized-season claim — "
                   "and on ~10 seasons these costs are noise-dominated, which the lockbox "
                   "confirmed (every archetype-cost CI contained zero).")


def main() -> None:
    st.set_page_config(page_title="Fantasy-Quant · Draft", page_icon="🏈", layout="wide")
    st.title("🏈 Fantasy-Quant")
    st.caption("A quant draft engine for the league you actually play in. Value = consensus → VBD, "
               "risk-dialed · availability = ADP + a fitted behavioral opponent model · variance = "
               "our own distributions.")
    tabs = st.tabs(["⚙️ Settings", "📋 Board", "🎯 Draft room", "💸 Cost"])
    with tabs[0]:
        tab_settings()
    with tabs[1]:
        tab_board()
    with tabs[2]:
        tab_draft()
    with tabs[3]:
        tab_cost()


if __name__ == "__main__":
    main()
