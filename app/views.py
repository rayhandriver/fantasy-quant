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

from app import palette, state
from fantasy_quant.draft import session

#: Column formats for the board. ``None`` = leave as text.
_BOARD_FMT: dict[str, str | None] = {
    "PLAYER": None, "POS": None, "ADP": "%.1f", "PROJ": "%.0f", "MEAN": "%.0f", "AVAIL": "%.1f",
    "BV": "%+.0f", "VBD": "%.0f", "RK": "%.0f", "UPSIDE": "%+.2f", "FLOOR": "%+.2f",
    "TAIL": "%+.2f", "BOOM": "%.2f", "BUST": "%.2f",
    # K2: 14.E's cliff and 14.G's quantile block. COIN and FLAGS are not numbers and are
    # configured separately in `_column_config`.
    "CLIFF": "%.0f", "Q10": "%.0f", "MED": "%.0f", "Q90": "%.0f",
    # UI-2 — both signed, always, because the sign *is* the reading and it is also the channel a
    # colourblind reader keeps when the green/red ink drops out (see `palette.VALUE_GOOD`).
    "Δ": "%+.1f", "BARGAIN": "%+.0f",
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
    # UI-2 step 3 — the scan channel. Narrow on purpose: it is meant to be swept down, not read.
    cfg["RISKS"] = st.column_config.TextColumn("RISKS", width="small",
                                               help=session.stat_help("RISKS"))
    # UI-3 step 1 — your own marks, on every view. Narrow for the same reason as RISKS.
    cfg[session.TAG_COL] = st.column_config.TextColumn(
        session.TAG_COL, width="small", help=session.stat_help(session.TAG_COL))
    # UI-1 step 5 — attached, not projected. A progress column rather than a number because the one
    # thing a drafter does with it under a clock is compare it to the row above.
    cfg[session.REACH_COL] = st.column_config.ProgressColumn(
        session.REACH_COL, format="%.2f", min_value=0.0, max_value=1.0,
        help=session.stat_help(session.REACH_COL))
    return cfg


#: What each mode is *for*, in one clause. The control's help text, and the only place the four are
#: described — a mode explained twice is a mode described differently the first time one is edited.
_MODE_HELP: dict[str, str] = {
    "slim": "the columns you draft on under a clock",
    "ranges": "each player's 10–90 band, and whether he is distinguishable from the man below him",
    "value": "the T27 chain, plus what he costs relative to right now",
    "risk": "shape, tails, and what he would do to the construction of your roster",
}


def mode_control(key: str) -> str:
    """The board's mode picker — UI-2 step 4's four, as a ``segmented_control``.

    ★ **``ADVANCED`` is deliberately not on it.** Fifteen columns is two more than the densest
    product in the market, whose density is the most-criticised thing about it; splitting the view
    and then leaving the undivided one on the control means nobody ever has to learn the split. It
    remains reachable from the CLI and from ``session.project_view``, which is where the two
    committed bar sheets read it.

    ⚠ **The option *values* stay the UPPERCASE labels the radio used, and the lowering happens
    here.** Making them the lowercase mode ids was the obvious build and it broke a contract nobody
    had written down: ``board_mode`` is a **widget key**, so it is session state, and UI-1's bar B3
    reaches the RANGES view by pre-setting it to ``"RANGES"``. Under lowercase ids that assignment
    matched no option, the control silently fell back to the default, and the bar reported that
    **COIN and the censored floor had stopped rendering** — a compression-deleted-an-honesty-surface
    alarm caused entirely by a renamed enum. *A display string that anything else can write is an
    interface; changing it is a breaking change even when nothing imports it.*
    """
    labels = [m.upper() for m in session.APP_VIEW_MODES]
    choice = st.segmented_control(
        "View", labels, default=labels[0], key=key,
        help=" · ".join(f"**{m.upper()}** {h}" for m, h in _MODE_HELP.items()))
    # `segmented_control` returns None when a user deselects the active pill; the board still has
    # to render something, and the thing it renders is the view a drafter is most often in.
    return str(choice or labels[0]).lower()


def board_table(st_obj, team: int | None = None, *, pos: str | None = None, n: int = 40,
                advanced: bool = False, mode: str | None = None, key: str | None = None,
                selectable: bool = False, risk=None, reach: pd.DataFrame | None = None,
                vi: pd.DataFrame | None = None, byes: pd.Series | None = None,
                elevation: float | None = None) -> tuple[pd.DataFrame, int | None]:
    """Render the best-available board; return ``(frame_rendered, selected_board_index)``.

    ``reach`` is :func:`~fantasy_quant.draft.session.reach_risk_view`'s frame. When it is given, the
    board gains a ``P(THERE)`` column through
    :func:`~fantasy_quant.draft.session.attach_reach` — *one derivation, two placements* (UI-1 bar
    B5). Under a clock "will he still be here" is a more decision-relevant column than ``PROJ``, and
    it is the one thing in this app no competitor ships at all.

    ``byes``/``elevation``/``vi`` are what the ``RISKS`` column needs (UI-2 step 3): they are
    properties of the *season* and of the *frozen 8.5 option*, not of the board, so they are handed
    in from a cache rather than opened here. Omit them and the roster-shape glyphs are simply
    absent — which is silence, not a clean bill of health (14.F).

    **Slim by default, one query per rerun** — the frame is
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
    view = session.board_view(st_obj, team=team, pos=pos, n=n, risk=risk, vi=vi, byes=byes,
                              elevation=elevation)
    shown = session.project_view(view, advanced=advanced, mode=mode)
    if reach is not None:
        shown = session.attach_reach(shown, reach)
    # UI-3 step 1 — your marks, on every view, placed by `session` for the same reason `P(THERE)`
    # is: a board the app draws differently from the one the CLI prints is two boards.
    shown = session.attach_tags(shown, st_obj.board, state.tags(), state.queue())
    extra = {"on_select": "rerun", "selection_mode": "single-row"} if selectable else {}
    # ⚠ the Styler wraps `shown`, it does not replace it — row selection still indexes the same
    # frame, so `view.index[rows[0]]` below is untouched. Streamlit honours `background-color` and
    # `color` from a Styler and ignores the rest — exactly the two properties `palette` sets.
    event = st.dataframe(
        palette.style_pos_columns(shown), width="stretch",
        height=min(620, 40 + 35 * min(len(shown), 16)),
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


#: Chrome for the seat strip. Deliberately **rgba greys, not hex** — they composite over whichever
#: theme is active, so the strip does not need a light and a dark variant, and they are not palette
#: colours, so bar B1's "the six hex strings appear exactly once" stays a statement about meaning.
_STRIP_EDGE = "rgba(128,128,128,0.35)"
_STRIP_LIVE = "rgba(128,128,128,0.16)"


def seat_strip_rows(st_obj, meta, sm) -> list[dict]:
    """One dict per seat, in :class:`SeatMap` order — the strip's content, before any styling.

    Split out from the rendering so bar **B4** can assert on the *content*: chip order is seat
    order, exactly one chip is on the clock and it is ``state.team_on_clock()``, and the on-deck
    chip is :func:`~fantasy_quant.draft.session.team_for_pick` at the next pick rather than a
    second piece of snake arithmetic living in a renderer.
    """
    on_clock = None if st_obj.is_done() else st_obj.team_on_clock()
    on_deck = session.team_for_pick(st_obj, st_obj.overall_pick + 1)
    autos = session.auto_teams(meta)
    last: dict[int, dict] = {}
    for p in st_obj.log:
        last[int(p["team"])] = p
    rows = []
    for t in range(st_obj.n_teams):
        p = last.get(t)
        rows.append({
            "team": t + 1, "seat": t, "label": session.seat_label(t, sm),
            "you": t in sm.human_teams, "autopick": t in autos,
            "on_clock": t == on_clock, "on_deck": (t == on_deck and t != on_clock),
            "last_player": (str(p["player_name"]) if p else ""),
            "last_pos": (str(p["pos"]) if p else ""),
            "last_handle": (f"{int(p['round'])}.{int(p['pick_in_round']):02d}" if p else ""),
        })
    return rows


def seat_strip(st_obj, meta, sm) -> list[dict]:
    """S5 — the draft-order strip, pinned at the top of the room.

    ★ **The first place a drafter's eye goes, and we did not have one.** Every mainstream draft
    room (ESPN, Yahoo, Sleeper) puts the order across the top with the team on the clock at the
    left and your team marked; ours had a line of markdown. Convention #4 in the shared design
    grammar, and matching a convention a user already has in their fingers is free.

    Rendered with :func:`st.html` rather than badges because a chip has to carry the **position
    colour** of the seat's last pick, and ``st.badge`` takes seven named colours — mapping six
    positions onto those would be a second palette, which is the defect B1 exists to prevent.
    """
    rows = seat_strip_rows(st_obj, meta, sm)
    cells = []
    for r in rows:
        edge = f"2px solid {_STRIP_EDGE}" if r["on_clock"] else (
            f"1px dashed {_STRIP_EDGE}" if r["on_deck"] else f"1px solid {_STRIP_EDGE}")
        fill = _STRIP_LIVE if r["on_clock"] else "transparent"
        you = ("<span style='font-size:.62rem;letter-spacing:.06em;opacity:.9'> YOU</span>"
               if r["you"] else "")
        auto = ("<span style='font-size:.62rem;opacity:.55'> auto</span>"
                if r["autopick"] else "")
        pick = ""
        if r["last_player"]:
            tint = palette.tint_style(r["last_pos"]) or "background-color: transparent"
            pick = (f"<div style='{tint};border-radius:4px;padding:1px 4px;margin-top:4px;"
                    f"font-size:.68rem;white-space:nowrap;overflow:hidden;"
                    f"text-overflow:ellipsis'>{r['last_handle']} {r['last_player']}</div>")
        cells.append(
            f"<div style='flex:1 1 0;min-width:86px;border:{edge};background:{fill};"
            f"border-radius:6px;padding:5px 7px'>"
            f"<div style='font-size:.78rem;font-weight:700'>T{r['team']}{you}{auto}</div>"
            f"<div style='font-size:.65rem;opacity:.7;white-space:nowrap;overflow:hidden;"
            f"text-overflow:ellipsis'>{r['label']}</div>{pick}</div>")
    arrow = "▸ round runs left to right" if st_obj.round() % 2 else "◂ round runs right to left"
    st.html(f"<div style='display:flex;gap:5px;flex-wrap:nowrap;overflow-x:auto;"
            f"padding-bottom:4px'>{''.join(cells)}</div>"
            f"<div style='font-size:.66rem;opacity:.6;margin-top:2px'>{arrow} · solid = on the "
            f"clock, dashed = on deck</div>")
    return rows


def next_pick_badge(st_obj, team: int) -> dict:
    """"Your next pick **#37** — 12 away", from the optimizer's own snake arithmetic."""
    info = session.next_pick_info(st_obj, team)
    if info["next_pick"] is None:
        st.badge("No further pick for this seat", color="gray")
    else:
        st.badge(f"Your next pick #{info['next_pick']} · {info['picks_away']} away",
                 color="blue", icon=":material/schedule:",
                 help="From `session.next_pick_info`, which wraps the optimizer's own "
                      "`_next_own_pick` — the same call the availability readout sizes its "
                      "simulation window with. One arithmetic, two surfaces.")
    return info


def chain_problem(entry: dict) -> None:
    """Why the T27 chain could not be built for one player — the same sentence on both surfaces.

    It was written out twice, in :func:`why_panel` and in :func:`player_card_body`, which is two
    places for one explanation to drift apart.
    """
    st.warning(entry["reason"])


def no_picks_yet() -> None:
    """The "nothing has happened yet" state, in one place rather than three."""
    st.badge("No picks yet", color="gray")


def no_board_error() -> None:
    """The "there is no board" dead end, in **one** place.

    It was written out three times — two pages and the draft-room setup — which is three chances
    for the sentence to drift and, in a session whose bar counts prose blocks, three blocks saying
    one thing. Deduplicating a message is the same discipline as deduplicating a derivation.
    """
    st.error("The store has no FFC ADP board for any season, so there is nothing to draft from. "
             "Run `uv run python steps/stage0_adp_snapshot.py` to pull one.")


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
        st.badge(f"{len(entries)} matches — be more specific", color="gray")
        return entries
    for e in entries:
        st.markdown(f"**{e['name']}** · {e['pos']} · ADP {e['adp']:.1f}")
        if not e["ok"]:
            chain_problem(e)
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
        no_picks_yet()
        return r
    show = r.rename(columns={"pos": "POS", "player_name": "PLAYER", "adp": "ADP",
                             "proj_points": "PROJ"})
    st.dataframe(palette.style_pos_columns(show, surface="roster_panel"),
                 width="stretch", hide_index=True,
                 column_config={"ADP": st.column_config.NumberColumn("ADP", format="%.1f"),
                                "PROJ": st.column_config.NumberColumn("PROJ", format="%.0f")})
    st.metric("Total consensus projection", f"{session.roster_total(r):,.0f} pts",
              help="The sum of `proj_points` over the whole roster — descriptive, and slot-blind. "
                   "STARTABLE on the post-draft page is the version that knows about lineup slots.")
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
        st.dataframe(palette.style_roster_rail(show), width="stretch", hide_index=True,
                     height=min(560, 40 + 28 * len(show)))
    r = session.roster_view(st_obj, team)
    needs = st_obj.starter_needs(team)
    # ★ The needs line was a sentence; it is the most-glanced fact in the rail and it is a *state*,
    # so it becomes chips — one per unfilled slot, in the position's own colour vocabulary. UI-1's
    # rule: explanations move into tooltips, state-dependent facts become badges.
    open_slots = [(k, v) for k, v in needs.items() if v]
    if open_slots:
        cols = st.columns(min(len(open_slots), 6))
        for c, (pos, n_open) in zip(cols, open_slots, strict=False):
            c.badge(f"{pos} ×{n_open}" if n_open > 1 else pos, color="orange",
                    help=f"{n_open} unfilled starting slot(s) at {pos}.")
    else:
        st.badge("Starters filled", color="green", icon=":material/check:",
                 help="Every dedicated and flex slot has a player in it. Bench picks from here.")
    st.metric("Running projection", f"{session.roster_total(r):,.0f} pts",
              f"{len(r)} of {st_obj.rounds} picks", delta_color="off")
    return r


def room_grid_panel(st_obj, sm, vi: pd.DataFrame | None = None, *,
                    by: str = "pick", surface: str = "room_grid") -> pd.DataFrame:
    """14.L — every drafter's team on one page, teams across the top."""
    grid = session.room_grid(st_obj, sm, by=by, vi=vi)
    # ★ **This is the surface position colour was worth doing for.** A draft board without it cannot
    # show a position run, and a position run is the only reason to look at a draft board mid-draft
    # (UI-PLAN §2, convention 3). The slot index is chipped too where it names a position — FLEX and
    # the bench rows stay uncoloured on purpose, because a flex slot is not a position.
    st.dataframe(palette.style_grid_cells(grid, index=(by == "slot"), surface=surface),
                 width="stretch", height=min(760, 40 + 32 * len(grid)))
    with st.popover("How to read this grid", icon=":material/help:"):
        st.markdown(
            "Every cell is tinted in its player's **position colour**, so a run shows up as a "
            "band of one hue moving across the board.\n\n"
            "**BY PICK** — cells are `round.pick` handles and the snake is in them: R1 runs "
            "1.01 → 1.10 left to right, R2 runs 2.01 → 2.10 right to left. Columns never move, "
            "so a team stays in one place.\n\n"
            "**BY SLOT** — slots are filled by the frozen lineup solver "
            "(`RosterSlots.flex_groups`), the same one the season sim scores every week with, not "
            "a display-layer fill order. Bench rows are best remaining value first; there is no "
            "optimal bench. `FLEX` and the bench rows are uncoloured because a flex slot is not "
            "a position.")
    return grid


def stat_dictionary_panel(columns=None) -> None:
    """14.O — every column, with a worked example. One dictionary, served here and by the CLI."""
    cols = list(columns or [lbl for _, lbl in session.BOARD_VIEW_COLS] + [session.REACH_COL])
    st.markdown("Every number on the board, in the order it appears — what it is, an example off "
                "the live board, and how to read it.")
    for c in cols:
        e = session.STAT_DICT.get(c)
        if not e:
            continue
        with st.expander(f"**{c}** — {e['label']}: {e['one_line']}"):
            st.markdown(f"{e['what_it_means']}\n\n**Example.** {e['worked_example']}\n\n"
                        f"**Reading it.** {e['how_to_read_it']}\n\n"
                        f"*Source: {e['provenance']}*")


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
    with st.popover("STARTABLE vs CAPITAL", icon=":material/help:"):
        st.markdown(
            "**STARTABLE** is the best legal starting lineup's `base_value`. **CAPITAL** is the "
            "slot-blind sum over every roster row, which prices a bench QB2 as though he "
            "started.\n\nThey disagree, and the gap is a real property of the roster rather than a "
            "rounding difference (T28) — on the 2026 walkthrough one QB2 line moved a team from "
            "9th of 10 on one to 3rd on the other. Showing one alone is the defect; showing both "
            "without saying which is which is the same defect with extra steps.\n\n"
            "**TOP-9 PROJ is descriptive only.** Scoring our own seats on our own board wins by "
            "construction; evaluative claims run on realized points.")
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
    # ⚠ T29's ordering is load-bearing and survives the compression: the badge that renders is the
    # *instruction to read the multiple*, and the paragraph explaining why lives one click away.
    st.badge("Read the multiples, not the percentages", color="orange",
             icon=":material/priority_high:")
    with st.popover("Why the ratio and not the percentage", icon=":material/help:"):
        st.markdown(
            "`1.70x` means 1.7 times a fair share of titles — in a ten-team league a fair share "
            "is 10 %.\n\nThe absolute percentages inherit the season sim's documented **−113 "
            "pts/team level bias**; the ratios do not, because that bias moves all ten teams "
            "together and cancels in a ratio. The lockbox certified the *ordering* (title Brier "
            "0.088) and recorded playoff Brier 0.240 as marginal — so the multiple is the number "
            "with evidence behind it and the percentage is the number that looks authoritative.\n\n"
            + " ".join(provenance))


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
    """14.G's honest headline, as **chips** — how much of the order on screen the model resolves.

    ★ This is the S3 item the compression was really for. `COIN` and `censored floor` are two of
    the seven things this app ships that no competitor ships at all, and both of them shipped as a
    five-line grey paragraph under a table — i.e. as an *apology*. A chip carrying a number, with
    the paragraph one click behind it, is read; the paragraph was skipped.

    ⚠ **Neither surface may vanish.** Bar B3 asserts both still render, by driving the app. The
    compression is allowed to move a sentence and is not allowed to lose one.
    """
    if "COIN" not in view.columns or view.empty:
        return
    n_pairs = max(len(view) - 1, 0)
    n_coin = int(pd.Series(view["COIN"]).fillna(False).astype(bool).sum())
    censored = int(view["FLAGS"].astype(str).str.contains("censored floor").sum()) \
        if "FLAGS" in view.columns else 0
    chips = st.columns([1, 1, 2])
    chips[0].badge(f"{n_coin}/{n_pairs} pairs overlap", color="violet", icon=":material/help:",
                   help="Where COIN is ticked, the two players' 10–90 % bands overlap: they are "
                        "not distinguishable by this model, and the row order between them is a "
                        "presentation rather than a finding.")
    # ⌀ — a censored quantity should LOOK different, not be described as different. The glyph is
    # on the chip rather than inside the FLAGS text, because FLAGS is the frozen string bar B4 of
    # the K2 sheet matches on and a display layer must not edit the thing a bar reads.
    if censored:
        chips[1].badge(f"⌀ {censored} censored floors", color="orange",
                       help="A season points total cannot be negative, so these rows' Q10 sits "
                            "exactly on the zero censoring point. Their downside is "
                            "UNRESOLVABLE, not zero (T19) — read the flag, never the 0.")


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
        st.badge(f"⌀ {risk['unknown_byes']} byes unknown", color="orange",
                 help="The store has no schedule table, so byes come from the FantasyPros ECR "
                      "snapshot and about one row in ten has none. These starters are counted as "
                      "unknown and never as week 0 — 14.F's rule, and the same distinction the "
                      "censored floor draws: a missing value is not a zero.")
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
        st.badge("No grade for this seat", color="gray")
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
    # ★ The printed weights stay printed. Being the only tool in the category that shows its own
    # blend is a feature, not a liability — so the disclaimer is compressed to a badge and a
    # popover, never deleted (UI-1 constraint 4, and bar B3 checks it renders).
    weights = tuple(int(w) for w in session.GRADE_WEIGHTS.values())
    st.badge(f"Blend {weights} — nothing validates it", color="orange",
             icon=":material/priority_high:")
    with st.popover("How this grade is built", icon=":material/help:"):
        st.markdown(
            f"**odds** — the T29 title fair-share multiple, which is immune to the sim's "
            f"−113 pts/team level bias where the percentage is not.\n\n"
            f"**starters** — STARTABLE, the best legal lineup's `base_value`.\n\n"
            f"**value** — harvest picks against the corpus reach scale.\n\n"
            f"**construction** — minus your worst bye-week starter count.\n\n"
            f"Each is scored **min–max across the ten teams in this room**, so 50 is the middle of "
            f"*this* room: a C means average here, not average in the abstract.\n\n"
            f"⚠ **The weights {weights} are a presentation choice and nothing validates them.** "
            f"Every input is frozen and separately validated; the act of blending them is house "
            f"style. A reader who can see the four contributions can disagree with the weights — "
            f"a reader shown only `B+` cannot.")


def reach_panel(frame: pd.DataFrame, window: int | None = None) -> None:
    """16.12(c) — ``P(available at your next pick)``, with the un-drifted baseline beside it."""
    if frame.empty:
        st.badge("No further pick for this seat", color="gray")
        return
    show = frame.rename(columns={"player_name": "PLAYER", "pos": "POS", "adp": "ADP",
                                 "p_available": session.REACH_COL,
                                 "p_available_baseline": "BASELINE",
                                 "drift_picks": "DRIFT", "reach_risk": "READ"})
    cols = [c for c in ("PLAYER", "POS", "ADP", session.REACH_COL, "BASELINE", "DRIFT", "READ")
            if c in show.columns]
    st.dataframe(palette.style_pos_columns(show[cols], surface="reach"),
                 width="stretch", hide_index=True,
                 column_config={
                     "ADP": st.column_config.NumberColumn("ADP", format="%.1f"),
                     session.REACH_COL: st.column_config.ProgressColumn(
                         session.REACH_COL, format="%.2f", min_value=0.0, max_value=1.0),
                     "BASELINE": st.column_config.NumberColumn("BASELINE", format="%.2f"),
                     "DRIFT": st.column_config.NumberColumn("DRIFT", format="%+.1f")})
    st.badge(f"{window} opponent picks until your next turn" if window
             else "No further pick for this seat", color="blue", icon=":material/schedule:",
             help="The window comes from the snake itself (`session.next_pick_info`), not from a "
                  "rule of thumb — the same call the seat strip reads.")
    with st.popover("Why two probabilities", icon=":material/help:"):
        st.markdown(
            "**P(THERE)** is the 11.2 survival oracle — a *fitted, Brier-validated* behavioural "
            "opponent model, not the crude ADP+noise placeholder.\n\n"
            "**BASELINE is the same number without the narrative-drift adjustment**, and it ships "
            "beside it because that adjustment **is not backtestable**: FFC publishes one board a "
            "season, so 16.11's momentum could only ever be validated forward. Drift is opt-in and "
            "off by default, which is why the two columns usually agree — and that agreement is a "
            "fact about the default, not evidence about the model.")


#: T38 — the elite-fall dict's keys, in reading order, with the label and unit a human needs.
#: ``share_past_*`` is matched by prefix because
#: :func:`~fantasy_quant.draft.mock.elite_fall_profile`
#: names it after its own threshold (``share_past_10``), and hard-coding the 10 here would be a
#: second definition of the bar's cut.
_ELITE_ROWS: tuple[tuple[str, str, str], ...] = (
    ("n", "Consensus top-12 players drafted", "{:.0f}"),
    ("mean_slot", "Mean landing slot (10-team picks)", "{:.1f}"),
    ("p95_slot", "p95 landing slot", "{:.1f}"),
    ("max_slot", "Furthest any of them fell", "{:.1f}"),
    ("share_past_", "Share that fell past the bar's cut", "{:.1%}"),
)


def elite_fall_table(elite: dict) -> pd.DataFrame:
    """The elite-fall profile as a titled table rather than a JSON dump (T38).

    Pure formatting: every value is :func:`~fantasy_quant.draft.mock.elite_fall_profile`'s own, and
    the only thing added is the label and the unit. The units matter more than they look — the
    slots are **10-team picks**, so a 12-team draft's pick 20 is not silently compared to a
    10-team draft's pick 20, and the readout is worthless without saying so.
    """
    rows = []
    for key, label, fmt in _ELITE_ROWS:
        k = key if key in elite else next((c for c in elite if c.startswith(key)), None)
        if k is None:
            continue
        rows.append({"": label, " ": fmt.format(float(elite[k]))})
    return pd.DataFrame(rows or [{"": "No consensus top-12 player has been drafted yet", " ": ""}])


def positional_strength_panel(tab: pd.DataFrame, team: int) -> pd.DataFrame:
    """A6's positional-strength chart — one seat's starting value per position vs the room median.

    ★ **The form is chosen by the data's job, and the job here is polarity, not identity.** The
    question a report card answers is *which positions did I win and which did I lose*, so the
    measure is a **signed** delta and the chart is a diverging bar around zero. Position identity
    already has a channel — it is the axis label — which is exactly what frees colour to carry the
    sign. Colouring the bars by position instead would spend the strongest channel on the one fact
    the reader can already see, which is the commonest way a dense chart says nothing.
    - ⚠ That is why this chart does **not** inherit ``chartCategoricalColors``, and the exception is
      worth naming because UI-1 set that key *specifically* so future charts would. It was right
      for a categorical chart. This one is diverging, and a diverging scale with six hues at its
      midpoint is not a scale.
    - The pair is :data:`app.palette.VALUE_GOOD`/``VALUE_BAD`` — the same two the board inks ``Δ``
      and ``BARGAIN`` with, so "green means good for you" means one thing across the whole app.
    - **Direction and hue both carry the sign** (a bar left of zero is also red), so nothing is
      lost to a reader who cannot separate the hues, and the table beneath is the third encoding.

    Returns the seat's own rows so a caller — or a bar — can assert on what was drawn.
    """
    mine = tab[tab["team"] == int(team) + 1].copy()
    if mine.empty:
        return mine
    mine["stronger"] = mine["delta"].clip(lower=0.0)
    mine["weaker"] = mine["delta"].clip(upper=0.0)
    st.markdown("**Positional strength** — your starters' `base_value` against the room median")
    st.bar_chart(mine.set_index("pos")[["stronger", "weaker"]], horizontal=True, stack=True,
                 color=[palette.VALUE_GOOD, palette.VALUE_BAD], height=240,
                 x_label="base_value vs the room median", y_label="")
    show = mine[["pos", "value", "room_median", "delta"]].rename(
        columns={"pos": "POS", "value": "YOURS", "room_median": "ROOM MEDIAN", "delta": "Δ"})
    st.dataframe(show, hide_index=True, width="stretch", column_config={
        c: st.column_config.NumberColumn(c, format="%.0f") for c in ("YOURS", "ROOM MEDIAN")}
        | {"Δ": st.column_config.NumberColumn("Δ", format="%+.0f")})
    st.caption("A within-this-draft comparison, so it moves with the room — it answers *did I win "
               "this position in this league*, never *is this a good RB corps*. Starters come from "
               "the one lineup solver, so a deep bench cannot make a position look strong (T28).")
    return mine


def player_card_body(card: dict) -> None:
    """The PLAYER-VIEW deep page for one player — bars, the T27 chain, flags, cliff, reach risk."""
    st.markdown(f"### {card['name']} · {card['pos']} · {card['team']}")
    chips = st.columns([1, 1, 1, 3])
    chips[0].badge(f"ADP {card['adp']:.1f}", color="gray")
    chips[1].badge(f"board #{card['board_index']}", color="gray")
    chips[2].badge("available" if card["available"] else "drafted",
                   color="green" if card["available"] else "red")
    # ★ UI-2 — PLAYER-VIEW bar #5, in the identity strip where §4 puts it. A chip rather than a
    # ninth `metric`, because `card["bars"]` is a shape two committed sheets assert the length of.
    bg = card.get("bargain") or {}
    if bg.get("value") is not None:
        chips[3].badge(f"{bg['value']:+.0f} ranks of value ({bg['rounds']:+.1f} rounds)",
                       color="green" if bg["value"] > 0 else "red", help=bg.get("help"))
    if card["flags"]:
        # An honesty surface: state-dependent, so it becomes a chip rather than a banner — but it
        # keeps its full sentence in the tooltip and it still renders (bar B3).
        st.badge(f"⌀ {card['flags']}", color="orange", icon=":material/priority_high:",
                 help=session.stat_entry("FLAGS")["how_to_read_it"] + " "
                      + session.stat_entry("FLAGS")["what_it_means"])

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

    # UI-3 step 1 — the card is where a preference is most likely to form, so it is where the tag
    # controls go. Above the chain, below the numbers: you decide after reading, not while.
    if card.get("player_key"):
        tag_controls(str(card["player_key"]), where="card")

    if card["chain"]:
        e = card["chain"][0]
        st.markdown("**How his value is built** (T27 — every line is an identity, not a "
                    "re-derivation)")
        if not e["ok"]:
            chain_problem(e)
        else:
            st.dataframe(pd.DataFrame([{"": r["label"],
                                        " ": "" if r["value"] is None else f"{r['value']:,.1f}",
                                        "  ": r["note"]} for r in e["rows"]]),
                         width="stretch", hide_index=True)


def tag_controls(player_key: str, *, where: str) -> None:
    """UI-3 step 1 — set this player's tag, and queue him, from wherever he is on screen.

    ★ **Five buttons: the queue star, and the Cost page's four preference kinds**
    (:data:`~fantasy_quant.draft.session.TAGS`). Clicking the active tag **clears** it: a
    preference you can express and cannot retract is a trap, and the retraction has to be as cheap
    as the assertion or nobody edits a stale board.

    ⚠ **Buttons, not a ``segmented_control``.** The control would need a widget key per player and
    UI-1 has already paid for what happens when widget state and app state both claim to own a
    value (`mode_control`'s docstring). A button is an *event*; the tag lives in one place.
    """
    key = str(player_key)
    cur = state.tags().get(key)
    queued = key in state.queue()
    cols = st.columns(len(session.TAGS) + 1)
    if cols[0].button(f"{session.QUEUE_GLYPH} {'Queued' if queued else 'Queue'}",
                      key=f"q_{where}_{key}", width="stretch",
                      type="primary" if queued else "secondary",
                      help="Ordering, not preference — the queue says *next*, a tag says *how "
                           "much*. Only tags are priced."):
        state.toggle_queue(key)
        st.rerun()
    for col, (name, spec) in zip(cols[1:], session.TAGS.items(), strict=False):
        on = cur == name
        if col.button(f"{spec['glyph']}", key=f"tag_{where}_{name}_{key}", width="stretch",
                      type="primary" if on else "secondary",
                      help=f"**{spec['label']}** — {spec['help']}"
                           + ("\n\nClick again to clear." if on else "")):
            state.set_tag(key, None if on else name)
            st.rerun()


def tag_summary(board: pd.DataFrame, tags: dict[str, str]) -> pd.DataFrame:
    """The tagged players, named — what the Cost page prices, shown before it prices it.

    ⚠ A tag whose player is not on **this** board (a different season, a board that has moved) is
    listed with its key rather than dropped: a preference silently missing from the run it was
    supposed to constrain is the failure mode the whole feature exists to prevent.
    """
    if not tags:
        return pd.DataFrame(columns=["", "PLAYER", "POS", "ADP"])
    keys = board["player_key"].astype(str)
    rows = []
    for k, t in tags.items():
        hit = board[keys == str(k)]
        r = hit.iloc[0] if len(hit) else None
        rows.append({"": session.TAGS[t]["glyph"],
                     "PLAYER": str(r["player_name"]) if r is not None else f"({k} — not on board)",
                     "POS": str(r["pos"]) if r is not None else "—",
                     "ADP": float(r["adp"]) if r is not None else float("nan")})
    frame = pd.DataFrame(rows)
    st.markdown("**What you have tagged**")
    st.dataframe(palette.style_pos_columns(frame, surface="cost"), hide_index=True,
                 width="stretch",
                 column_config={"ADP": st.column_config.NumberColumn("ADP", format="%.1f")})
    return frame


def queue_panel(st_obj, team: int, *, allow_draft: bool) -> tuple[dict | None, str | None]:
    """The draft-room rail's queue, and the button that drafts the top of it.

    Returns ``(resolution, action)`` where ``resolution`` is
    :func:`~fantasy_quant.draft.session.queue_next`'s dict and ``action`` is ``"draft"`` when the
    button was pressed — the *caller* makes the pick, because the confirm bar and the pick path
    belong to the draft room and a rail that could draft on its own would be a second pick path.

    ⚠ **The skipped list renders.** Walking down the queue past a drafted or `🚫`-tagged player is
    the user's chosen behaviour, and a silent skip is how a queue quietly drafts somebody you did
    not mean to take.
    """
    q = state.queue()
    st.markdown(f"**{session.QUEUE_GLYPH} Your queue**")
    if not q:
        # UI-1's rule holds through UI-3: instruction becomes a chip with the sentence in its
        # tooltip, never a paragraph on a rail that is 25% of the screen.
        st.badge("empty", color="gray",
                 help="Queue a player from the board or from his card. The top of the queue is "
                      "one click from a pick — and the confirm bar still stands in front of it.")
        return None, None
    res = session.queue_next(st_obj, int(team), q, state.tags())
    rows = []
    board = st_obj.board
    keys = board["player_key"].astype(str)
    for k in q:
        hit = board[keys == str(k)]
        if hit.empty:
            continue
        r = hit.iloc[0]
        rows.append({"": session.TAGS.get(state.tags().get(str(k), ""), {}).get("glyph", ""),
                     "PLAYER": str(r["player_name"]), "POS": str(r["pos"]),
                     "ADP": float(r["adp"]),
                     "GONE": int(hit.index[0]) not in st_obj.available})
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                     column_config={"ADP": st.column_config.NumberColumn("ADP", format="%.1f"),
                                    "GONE": st.column_config.CheckboxColumn("GONE")})
    for s in res["skipped"]:
        hit = board[keys == str(s["player_key"])]
        who = str(hit.iloc[0]["player_name"]) if len(hit) else s["player_key"]
        # ⚠ Rendered, always. Walking down the queue past somebody is the user's chosen behaviour
        # (2026-08-17) and a silent skip is how a queue drafts a player you did not mean to take.
        st.badge(f"⏭ {who}", color="orange", help=s["why"])
    if res["board_index"] is None:
        st.badge("Nobody in the queue is draftable", color="orange")
        return res, None
    if not allow_draft:
        # ⚠ No button off your own clock. One that silently meant *later* would be a button that
        # lies about when it acts, which is worse than making you wait for your turn.
        st.badge(f"next: {res['player_name']}", color="blue",
                 help="Draftable on your own clock. No button off it — one that silently meant "
                      "*later* would be a button that lies about when it acts.")
        return res, None
    pressed = st.button(f"Draft {res['player_name']}", width="stretch",
                        key=f"queue_draft_{st_obj.overall_pick}",
                        help="Loads the confirm bar — the pick is still yours to confirm.")
    return res, ("draft" if pressed else None)


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
