"""Renderers. Every number here arrives from :mod:`fantasy_quant.draft.session` already computed.

The rule this module is written to: **a renderer formats, it does not derive.** If a function here
does arithmetic on a model quantity, that arithmetic has escaped the one place it belongs and the
app has started to drift away from the CLI it is supposed to mirror. Formatting a float, choosing a
column order and deciding that a NaN prints as ``-`` are formatting; subtracting two model outputs
is not.

The one place that rule is load-bearing rather than tidy is :func:`why_panel`, whose entire purpose
is that the chain shown is the chain the frozen stack computed (T27).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from fantasy_quant.draft import session

#: Column formats for the board. ``None`` = leave as text.
_BOARD_FMT: dict[str, str | None] = {
    "PLAYER": None, "POS": None, "ADP": "%.1f", "PROJ": "%.0f", "MEAN": "%.0f", "AVAIL": "%.1f",
    "BV": "%+.0f", "VBD": "%.0f", "RK": "%.0f", "UPSIDE": "%+.2f", "FLOOR": "%+.2f",
    "TAIL": "%+.2f", "BOOM": "%.2f", "BUST": "%.2f",
    # K2: 14.E's cliff and 14.G's quantile block. COIN and FLAGS are not numbers and are
    # configured separately in `_column_config`.
    "CLIFF": "%.0f", "Q10": "%.0f", "MED": "%.0f", "Q90": "%.0f",
}

def _column_config() -> dict:
    """Number formats + the 14.O tooltip for every board column.

    The help text is :data:`~fantasy_quant.draft.session.STAT_DICT`'s, not a local copy. The local
    copy (``_BOARD_HELP``) is **deleted**: it was terse, app-only, and the moment a column's
    meaning moved — as ``BOOM``/``BUST``'s did under T22 — there were two places to update and one
    of them would have been missed. One dictionary, every surface.
    """
    cfg: dict = {c: st.column_config.NumberColumn(c, format=f, help=session.stat_help(c))
                 for c, f in _BOARD_FMT.items() if f is not None}
    cfg["COIN"] = st.column_config.CheckboxColumn("COIN", help=session.stat_help("COIN"))
    cfg["FLAGS"] = st.column_config.TextColumn("FLAGS", help=session.stat_help("FLAGS"))
    return cfg


def board_table(st_obj, team: int | None = None, *, pos: str | None = None, n: int = 40,
                advanced: bool = False, mode: str | None = None, key: str | None = None,
                selectable: bool = False, risk=None) -> tuple[pd.DataFrame, int | None]:
    """Render the best-available board; return ``(frame_rendered, selected_board_index)``.

    **Slim by default, advanced on a toggle, one query** — the frame is
    :func:`~fantasy_quant.draft.session.board_view` and the two views are
    :func:`~fantasy_quant.draft.session.project_view` applied to it, so they cannot show different
    rows in a different order (bar B2). Building a second, narrower query for the slim view is the
    obvious shortcut and it is the one that ends with two boards disagreeing about who is
    available.

    ⚠ **T22 — an unseen player's BOOM/BUST renders blank, never ``0.00``.** The frozen Phase-5 pair
    is measured at ``max(train_seasons)``; on a live board that is 2022, so a player who was not in
    the league that season reads 0.00, which a human correctly parses as *never busts*. The live
    pair leaves him NaN, and NaN must survive all the way to the screen — a ``fillna(0)`` anywhere
    in this file would silently restore the exact defect the column was rebuilt to fix.
    """
    view = session.board_view(st_obj, team=team, pos=pos, n=n, risk=risk)
    shown = session.project_view(view, advanced=advanced, mode=mode)
    extra = {"on_select": "rerun", "selection_mode": "single-row"} if selectable else {}
    event = st.dataframe(
        shown, width="stretch", height=min(620, 40 + 35 * min(len(shown), 16)),
        column_config=_column_config(), key=key, **extra,
    )
    picked = None
    if selectable:
        rows = list(getattr(getattr(event, "selection", None), "rows", []) or [])
        if rows and rows[0] < len(view):
            # the frame's index IS the board index — the `#` a CLI user types and the label
            # `_apply_pick` wants. Never re-derive it from the row position of a filtered view.
            picked = int(view.index[rows[0]])
    return view, picked


def why_panel(board: pd.DataFrame, vi: pd.DataFrame, query: str, lam: float) -> list[dict]:
    """The PROJ → BASE_VALUE arithmetic chain for one player (T27), rendered.

    ★ **Every line is an identity read from the frozen contracts, not a re-derivation.** ``λ·Var``
    is ``mean − ce_value`` and the positional replacement is ``ce_value − ce_vbd``, both computed in
    :func:`~fantasy_quant.draft.session.explain_chain`. That is what makes this an audit trail
    rather than a caption: a display layer that recomputed the chain could disagree with the stack
    it claims to explain, and nobody would be able to tell which one was wrong.
    """
    entries = session.explain_chain(board, vi, query, lam)
    if not entries:
        st.info(f"No player on the board matching “{query}”.")
        return entries
    if len(entries) > 6:
        st.info(f"{len(entries)} matches — be more specific.")
        return entries
    for e in entries:
        st.markdown(f"**{e['name']}** · {e['pos']} · ADP {e['adp']:.1f}")
        if not e["ok"]:
            st.warning(e["reason"])
            continue
        rows = [{"": r["label"],
                 " ": "" if r["value"] is None else f"{r['value']:,.1f}",
                 "  ": r["note"]} for r in e["rows"]]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    return entries


def roster_panel(st_obj, team: int, label: str = "") -> pd.DataFrame:
    """One seat's roster plus its consensus-projection total."""
    r = session.roster_view(st_obj, team)
    if label:
        st.markdown(f"**{label}**")
    if r.empty:
        st.caption("(empty)")
        return r
    show = r.rename(columns={"pos": "POS", "player_name": "PLAYER", "adp": "ADP",
                             "proj_points": "PROJ"})
    st.dataframe(show, width="stretch", hide_index=True,
                 column_config={"ADP": st.column_config.NumberColumn("ADP", format="%.1f"),
                                "PROJ": st.column_config.NumberColumn("PROJ", format="%.0f")})
    st.caption(f"Total consensus projection: **{session.roster_total(r):,.0f}** pts")
    return r


def roster_rail(st_obj, team: int, sm=None, vi: pd.DataFrame | None = None) -> pd.DataFrame:
    """The persistent rail beside the board: your roster in slot order, open slots shown as open.

    ★ **An empty slot is a row, not an absence.** The K1 roster panel listed what you had, which
    answers "who did I draft" and not "what do I still need" — and on draft day the second question
    is the one with a clock on it. Rows come from the frozen ``flex_groups`` slot plan via
    :func:`~fantasy_quant.draft.session.room_grid`, so the rail and the room grid cannot disagree
    about which of your players is starting.

    ⚠ 16.17: with more than one human seat this renders **one seat at a time**, selected by the
    caller. There is deliberately nowhere to put a combined total — k teams in one draft are one
    observation.
    """
    grid = session.room_grid(st_obj, sm, by="slot", vi=vi) if sm is not None else None
    label = session.seat_label(team, sm) if sm is not None else f"T{team + 1}"
    st.markdown(f"**Your roster — T{team + 1} · {label}**")
    if grid is not None:
        col = grid.columns[team]
        show = pd.DataFrame({"SLOT": grid.index, "PLAYER": grid[col].to_numpy()})
        show["PLAYER"] = show["PLAYER"].replace("", "—")
        st.dataframe(show, width="stretch", hide_index=True, height=min(560, 40 + 28 * len(show)))
    r = session.roster_view(st_obj, team)
    needs = st_obj.starter_needs(team)
    short = ", ".join(f"{k} {v}" for k, v in needs.items() if v)
    st.caption(f"Starter needs: **{short or 'none — starters filled'}**")
    st.caption(f"Running consensus projection: **{session.roster_total(r):,.0f}** pts "
               f"· {len(r)} of {st_obj.rounds} picks made")
    return r


def room_grid_panel(st_obj, sm, vi: pd.DataFrame | None = None, *,
                    by: str = "pick") -> pd.DataFrame:
    """14.L — every drafter's team on one page, teams across the top."""
    grid = session.room_grid(st_obj, sm, by=by, vi=vi)
    st.dataframe(grid, width="stretch", height=min(760, 40 + 32 * len(grid)))
    if by == "pick":
        st.caption("Each cell is that seat's pick in that round, handled `round.pick`. The snake "
                   "is in the handles: round 1 runs 1.01 → 1.10 left to right, round 2 runs "
                   "2.01 → 2.10 right to left. Columns never move, so a team stays in one place.")
    else:
        st.caption("Slots are filled by the frozen lineup solver (`RosterSlots.flex_groups`), the "
                   "same one the season sim scores every week with — not a display-layer fill "
                   "order. Bench rows are best remaining value first; there is no optimal bench.")
    return grid


def stat_dictionary_panel(columns=None) -> None:
    """14.O — every column, with a worked example. One dictionary, served here and by the CLI."""
    cols = list(columns or [lbl for _, lbl in session.BOARD_VIEW_COLS])
    st.caption("Every number on the board, in the order it appears — what it is, an example off "
               "the live board, and how to read it.")
    for c in cols:
        e = session.STAT_DICT.get(c)
        if not e:
            continue
        with st.expander(f"**{c}** — {e['label']}: {e['one_line']}"):
            st.markdown(f"{e['what_it_means']}\n\n**Example.** {e['worked_example']}\n\n"
                        f"**Reading it.** {e['how_to_read_it']}")
            st.caption(f"Source: {e['provenance']}")


def summary_panel(st_obj, sm, vi: pd.DataFrame | None) -> pd.DataFrame:
    """Final standings with **both** team-level numbers, labelled (T28).

    ``STARTABLE`` is the best legal starting lineup's ``base_value``; ``CAPITAL`` is the slot-blind
    sum over every roster row, which prices a bench QB2 as though he started. On the 2026
    walkthrough those disagreed by −122 points on one QB2 line — enough to put a team 9th of 10 on
    one and 3rd on the other. Showing one alone is the defect; showing both without saying which
    is which is the same defect with extra steps.
    """
    tab = session.summary_table(st_obj, sm, vi)
    show = tab.rename(columns={"rank": "RANK", "team": "TEAM", "who": "WHO",
                               "starters": "TOP-9 PROJ", "proj": "FULL ROSTER",
                               "startable": "STARTABLE", "capital": "CAPITAL"})
    show["TEAM"] = "T" + show["TEAM"].astype(str)
    cols = [c for c in ("RANK", "TEAM", "WHO", "TOP-9 PROJ", "FULL ROSTER", "STARTABLE", "CAPITAL")
            if c in show.columns]
    st.dataframe(show[cols], width="stretch", hide_index=True,
                 column_config={c: st.column_config.NumberColumn(c, format="%.0f")
                                for c in cols if c not in ("TEAM", "WHO", "RANK")})
    st.caption(
        "**STARTABLE** = the best legal starting lineup's base_value. **CAPITAL** = the slot-blind "
        "sum over all roster rows, which prices a bench QB2 as if he started. They disagree, and "
        "the gap is a real property of the roster, not a rounding difference (T28). "
        "Top-9 PROJ is descriptive only — scoring our own seats on our own board wins by "
        "construction.")
    return tab


def odds_panel(tab: pd.DataFrame, provenance: list[str]) -> None:
    """Season odds **led by the fair-share multiple** (T29).

    A bare "17.0 % to win the league" is the weakest number in the stack wearing the most
    authoritative costume: the lockbox certified the *ordering* (title Brier 0.088) but recorded
    playoff Brier 0.240 as marginal, over a sim carrying a documented −113 pts/team level bias. A
    ratio to the uniform share moves all ten teams together, so it survives that bias while the
    absolute percentage does not. Hence: multiple first and large, percentage second and small.
    """
    show = pd.DataFrame({
        "TEAM": "T" + tab["team"].astype(str),
        "WHO": tab["who"],
        "PLAYOFF": tab["playoff_fair"].map(lambda v: f"{v:.2f}x"),
        "(abs)": tab["playoff"].map(lambda v: f"{v:.1%}"),
        "TITLE": tab["title_fair"].map(lambda v: f"{v:.2f}x"),
        "(abs) ": tab["title"].map(lambda v: f"{v:.1%}"),
    })
    st.dataframe(show, width="stretch", hide_index=True)
    st.caption(
        "**Read the multiples, not the percentages.** `1.70x` = 1.7 times a fair share of titles. "
        "The absolute percentages inherit the sim's documented −113 pts/team level bias; the "
        "ratios do not, because the bias moves every team together. " + " ".join(provenance))


# ------------------------------------------------------------------------------------------------
# K2 — the surfacing panels
# ------------------------------------------------------------------------------------------------
def cliff_strip(st_obj, team: int, risk=None) -> pd.DataFrame:
    """14.E — each position's next tier cliff, above the board it describes.

    ⚠ **Rendered as a strip rather than as a rule drawn between two table rows.** The board is an
    ``st.dataframe`` because that is what gives row selection, and a dataframe cannot carry a
    separator row that is not also a player. Faking one (a blank row, a divider glyph in PLAYER)
    would put a non-player in a frame whose index *is* the board index — the one column
    ``_apply_pick`` consumes. So the cliff is stated above the board and marked in the ``CLIFF``
    column beside each player, and the table stays a table.
    """
    tab = session.cliff_table(st_obj, team, risk=risk)
    if tab.empty:
        return tab
    cols = st.columns(len(tab))
    for c, (_, r) in zip(cols, tab.iterrows(), strict=False):
        c.metric(f"{r['pos']} cliff", f"−{r['drop']:.0f}",
                 f"{int(r['n_before'])} left", delta_color="off",
                 help=f"The board falls {r['drop']:.0f} points of base_value at "
                      f"{r['at_player']} — {int(r['n_before'])} {r['pos']}(s) at or above it, "
                      f"{int(r['n_available'])} available in all. Read it against ADP: a steep "
                      f"cliff nobody else is near is not urgent.")
    return tab


def range_note(view: pd.DataFrame) -> None:
    """14.G's honest headline: how much of the order on screen the model can actually resolve."""
    if "COIN" not in view.columns or view.empty:
        return
    n_pairs = max(len(view) - 1, 0)
    n_coin = int(pd.Series(view["COIN"]).fillna(False).astype(bool).sum())
    censored = int(view["FLAGS"].astype(str).str.contains("censored floor").sum()) \
        if "FLAGS" in view.columns else 0
    st.caption(
        f"**{n_coin} of {n_pairs} adjacent pairs on this screen overlap at 10–90 %** — where COIN "
        f"is ticked the two players are not distinguishable by this model and the row order is a "
        f"presentation, not a finding. {censored} row(s) show `censored floor`: a season total "
        f"cannot be negative, so their Q10 sits on the zero censoring point and their downside is "
        f"**unresolvable, not zero** (T19).")


def construction_panel(risk: dict) -> None:
    """14.F — bye clustering, NFL-team concentration and handcuff gaps, reported separately.

    ⚠ **No composite.** There is no evidence for a rate of exchange between "four starters idle in
    week 11" and "you hold three Eagles", so the three are shown side by side and only the bye
    count feeds the 14.I grade (where it is named as one count, not a blend).
    """
    c1, c2, c3 = st.columns(3)
    c1.metric("Starters sharing a bye", risk["max_bye_starters"],
              help="The largest number of your starters idle in any single week.")
    c2.metric("Most from one NFL team", risk["max_team_players"],
              help="Same-team players move together — that is the Phase-8 covariance the "
                   "optimizer already charges you for, shown as a count.")
    c3.metric("Handcuff gaps", risk["n_handcuff_gaps"],
              help="Lead backs you hold whose backup you do not. RB only: the elevation ratio "
                   "that prices the option is measured on backfields.")

    byes = risk["byes"]
    if len(byes):
        show = byes.rename(columns={"week": "WEEK", "n": "STARTERS", "who": "WHO"})
        st.dataframe(show, width="stretch", hide_index=True)
    if risk["unknown_byes"]:
        st.caption(f"⚠ {risk['unknown_byes']} of your starters have **no bye week on file** — the "
                   f"store has no schedule table, so byes come from the FantasyPros ECR snapshot "
                   f"and about one row in ten has none. They are counted as unknown, never as "
                   f"week 0.")
    conc = risk["concentration"]
    if len(conc):
        top = conc[conc["n"] > 1]
        if len(top):
            st.markdown("**Team concentration**")
            st.dataframe(top.rename(columns={"nfl_team": "TEAM", "n": "N",
                                             "n_starters": "STARTING", "who": "WHO"}),
                         width="stretch", hide_index=True)
    hc = risk["handcuffs"]
    if len(hc):
        st.markdown("**Handcuffs**")
        show = hc.rename(columns={"starter": "YOUR RB", "nfl_team": "TEAM", "backup": "HANDCUFF",
                                  "held": "HELD", "option_premium": "OPTION"})
        st.dataframe(show, width="stretch", hide_index=True,
                     column_config={"OPTION": st.column_config.NumberColumn(
                         "OPTION", format="%.0f",
                         help="The insurance half of the backup's value: his season points with "
                              "the starter healthy vs. folding in the starter's own measured "
                              "absence risk, at the pooled Phase-8.5 elevation ratio.")})


def grade_panel(grade: pd.DataFrame, team: int) -> None:
    """14.I — one seat's grade, with the arithmetic that produced it and the weights named.

    ★ **The weighting is printed, not hidden.** Every input is frozen and separately validated; the
    act of blending them is a presentation choice this session made and nothing validates. A reader
    who can see the four contributions can disagree with the weights; a reader shown only ``B+``
    cannot.
    """
    row = grade[grade["team"] == team + 1]
    if row.empty:
        st.info("No grade for this seat.")
        return
    r = row.iloc[0]
    left, right = st.columns([1, 3])
    left.metric(f"{r['who']} (T{int(r['team'])})", str(r["letter"]), f"{r['total']:.0f} / 100",
                delta_color="off")
    parts = pd.DataFrame([{
        "COMPONENT": name,
        "WEIGHT": f"{w:.0f}",
        "RAW": r[name],
        "SCORE": r[f"score_{name}"],
        "POINTS": r[f"points_{name}"],
    } for name, w in session.GRADE_WEIGHTS.items()])
    right.dataframe(parts, width="stretch", hide_index=True, column_config={
        "RAW": st.column_config.NumberColumn("RAW", format="%.2f"),
        "SCORE": st.column_config.NumberColumn("SCORE", format="%.2f"),
        "POINTS": st.column_config.NumberColumn("POINTS", format="%.1f")})
    st.caption(
        f"**odds** = the T29 title fair-share multiple (immune to the sim's −113 pts/team level "
        f"bias, which the percentage is not) · **starters** = STARTABLE, the best legal lineup's "
        f"base_value · **value** = harvest picks against the corpus reach scale · "
        f"**construction** = minus your worst bye-week starter count. Each is scored **min–max "
        f"across the ten teams in this room**, so 50 is the middle of *this* room and a C means "
        f"average here, not average in the abstract. "
        f"⚠ **The weights {tuple(int(w) for w in session.GRADE_WEIGHTS.values())} are a "
        f"presentation choice and nothing validates them** — the inputs are frozen, the blend is "
        f"house style.")


def reach_panel(frame: pd.DataFrame, window: int | None = None) -> None:
    """16.12(c) — ``P(available at your next pick)``, with the un-drifted baseline beside it."""
    if frame.empty:
        st.caption("No availability readout — the draft has no further pick for this seat.")
        return
    show = frame.rename(columns={"player_name": "PLAYER", "pos": "POS", "adp": "ADP",
                                 "p_available": "P(THERE)", "p_available_baseline": "BASELINE",
                                 "drift_picks": "DRIFT", "reach_risk": "READ"})
    cols = [c for c in ("PLAYER", "POS", "ADP", "P(THERE)", "BASELINE", "DRIFT", "READ")
            if c in show.columns]
    st.dataframe(show[cols], width="stretch", hide_index=True, column_config={
        "ADP": st.column_config.NumberColumn("ADP", format="%.1f"),
        "P(THERE)": st.column_config.ProgressColumn("P(THERE)", format="%.2f",
                                                    min_value=0.0, max_value=1.0),
        "BASELINE": st.column_config.NumberColumn("BASELINE", format="%.2f"),
        "DRIFT": st.column_config.NumberColumn("DRIFT", format="%+.1f")})
    st.caption(
        f"P(still there when you pick again{f', {window} opponent picks away' if window else ''}) "
        f"from the **validated** 11.2 survival oracle, not the crude ADP+noise placeholder. "
        f"**BASELINE is the same number without the narrative-drift adjustment, and it is shown "
        f"because the adjustment is not backtestable** — FFC gives one board a season, so 16.11's "
        f"momentum could only ever be validated forward. Drift is opt-in and off by default, which "
        f"is why the two columns usually agree.")


def player_card_body(card: dict) -> None:
    """The PLAYER-VIEW deep page for one player — bars, the T27 chain, flags, cliff, reach risk."""
    st.markdown(f"### {card['name']} · {card['pos']} · {card['team']}")
    st.caption(f"ADP {card['adp']:.1f} · board #{card['board_index']} · "
               f"{'available' if card['available'] else 'already drafted'}")
    if card["flags"]:
        st.warning(f"**Confidence flags: {card['flags']}.** "
                   f"{session.stat_entry('FLAGS')['how_to_read_it']}")

    bars = [b for b in card["bars"] if b["value"] is not None]
    for chunk in (bars[:4], bars[4:]):
        if not chunk:
            continue
        cols = st.columns(len(chunk))
        for c, b in zip(cols, chunk, strict=False):
            c.metric(b["label"], f"{b['value']:{b['fmt'][1:]}}", help=b["help"])

    line = []
    if card.get("cliff") is not None:
        line.append(f"**Tier cliff** {card['cliff']:.0f} pts")
    if card.get("reach"):
        rr = card["reach"]
        line.append(f"**P(there at your next pick)** {float(rr['p_available']):.0%} "
                    f"— _{rr['reach_risk']}_")
    if line:
        st.markdown(" · ".join(line))

    if card["chain"]:
        e = card["chain"][0]
        st.markdown("**How his value is built** (T27 — every line is an identity, not a "
                    "re-derivation)")
        if not e["ok"]:
            st.warning(e["reason"])
        else:
            st.dataframe(pd.DataFrame([{"": r["label"],
                                        " ": "" if r["value"] is None else f"{r['value']:,.1f}",
                                        "  ": r["note"]} for r in e["rows"]]),
                         width="stretch", hide_index=True)


@st.dialog("Player", width="large")
def player_dialog(card: dict) -> None:
    """The deep page as a modal, opened from a board row.

    ⚠ **A modal, not a hover.** `docs/PLAYER-VIEW.md` §3 specs a hover overview card and §4 a deep
    page; Streamlit has no hover event, so one surface serves both roles rather than the hover half
    being faked with a tooltip that cannot hold eight bars and an arithmetic chain. The column
    tooltips (14.O) already carry the per-number explanation a hover would have.
    """
    player_card_body(card)


def honesty_notes(n_humans: int, *, drift: bool = False) -> None:
    """The two 16.17 honesty rules, rendered rather than merely true.

    (1) k human teams in one draft are **one** observation — your picks deplete each other's pools,
    so the seats' outcomes are mechanically anti-correlated. (2) The T15 realism bars describe a
    *fully simulated* room. Both are stated with the actual k in them, because a note that does not
    know how many seats you drive is a note nobody reads.
    """
    if n_humans > 1:
        st.warning(
            f"**These {n_humans} teams are ONE observation, not {n_humans}.** Every pick you made "
            f"removed a player from your other seats' pools, so their outcomes are mechanically "
            f"anti-correlated. Read them side by side; never average them or count a record "
            f"across them.")
    if drift:
        st.info(
            f"**Scope:** the committed T15 realism bars — profile distance, dispersion, chalk "
            f"share, elite-fall landing — were measured on a **fully simulated** ten-seat room. "
            f"This draft has {n_humans} human seat(s), so these numbers describe *this draft* and "
            f"are not a re-measurement of those bars.")
