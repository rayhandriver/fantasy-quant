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
}

_BOARD_HELP = {
    "PROJ": "Consensus projection, re-scored to your league's rules. The number a human trusts.",
    "MEAN": "Phase-5 season mean = PROJ x projected availability. The level correction.",
    "AVAIL": "Projected games played, of 17 — the column that explains the PROJ→MEAN gap.",
    "BV": "base_value: (MEAN − λ·Var) − positional replacement. What each seat optimizes.",
    "UPSIDE": "Relative q90 headroom.", "FLOOR": "Relative q10 floor.",
    "TAIL": "Relative q90−q10 spread — the honest boom-or-bust read.",
    "BOOM": "Live boom rate, measured on last season. Blank = never seen play.",
    "BUST": "Live bust rate, measured on last season. Blank = never seen play.",
}


def board_table(st_obj, team: int | None = None, *, pos: str | None = None,
                n: int = 40) -> pd.DataFrame:
    """Render the best-available board and return the frame that was rendered.

    ⚠ **T22 — an unseen player's BOOM/BUST renders blank, never ``0.00``.** The frozen Phase-5 pair
    is measured at ``max(train_seasons)``; on a live board that is 2022, so a player who was not in
    the league that season reads 0.00, which a human correctly parses as *never busts*. The live
    pair leaves him NaN, and NaN must survive all the way to the screen — a ``fillna(0)`` anywhere
    in this file would silently restore the exact defect the column was rebuilt to fix.
    """
    view = session.board_view(st_obj, team=team, pos=pos, n=n)
    st.dataframe(
        view, width="stretch", height=min(620, 40 + 35 * min(len(view), 16)),
        column_config={
            c: st.column_config.NumberColumn(c, format=f, help=_BOARD_HELP.get(c))
            for c, f in _BOARD_FMT.items() if f is not None},
    )
    return view


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
