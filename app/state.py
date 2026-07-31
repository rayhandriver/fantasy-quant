"""Session state and the cached engine calls — the seam every page reads, so no page owns it.

Session K1 put these in ``app/main.py`` because ``main.py`` *was* the app. 14.K makes ``main.py`` a
router, so the shared accessors move here rather than being imported *from* the entry point: a page
importing the router that imports the page is a cycle, and the way that usually gets "fixed" is by
re-deriving the board in the second place. The K1 rule is unchanged and this module is how it stays
cheap to obey — **renderers format, they do not derive**, and everything derived arrives from
:mod:`fantasy_quant.draft.session` through here.
"""

from __future__ import annotations

import streamlit as st

from app import engine
from fantasy_quant.draft.config import LeagueSettings

#: The seed pair the Board page's zero-pick state is built with. It is **not** a draft anyone
#: plays: `board_view` reads no RNG, so any constant does, and a constant is what keeps the page
#: from drawing fresh entropy (T34) on every rerun for a state that exists only to be read.
PREVIEW_SEEDS = (0, 0)


@st.cache_resource(show_spinner=False)
def con():
    return engine.connect()


@st.cache_data(show_spinner=False)
def seasons() -> list[int]:
    return engine.boarded_seasons(con())


@st.cache_data(show_spinner="Building the board (consensus → VBD → risk-dialed)…")
def build(season: int, settings_key: tuple) -> dict:
    """The one cached ``(board, value_index, risk)`` build.

    Keyed on the *settings tuple* rather than the object because a league's shape changes the
    board: ``n_teams`` moves the replacement levels the value index is computed against, so a
    superflex league is a genuinely different board and must not be served from the 1-QB cache.
    """
    return engine.build(con(), season, LeagueSettings(**dict(settings_key)))


def settings() -> LeagueSettings:
    return st.session_state.get("settings") or LeagueSettings()


def settings_key(s: LeagueSettings) -> tuple:
    """A hashable identity for the fields that change the board or the lineup solver."""
    return tuple(sorted({
        "n_teams": s.n_teams, "rounds": s.rounds, "qb": s.qb, "rb": s.rb, "wr": s.wr, "te": s.te,
        "flex": s.flex, "superflex": s.superflex, "k": s.k, "dst": s.dst, "bench": s.bench,
        "scoring_preset": s.scoring_preset, "reg_weeks": s.reg_weeks,
        "playoff_teams": s.playoff_teams, "draft_slot": s.draft_slot,
    }.items()))


def built_for(s: LeagueSettings, season: int) -> dict:
    return build(int(season), settings_key(s))


# ------------------------------------------------------------------------------------------------
# the draft in progress
# ------------------------------------------------------------------------------------------------
def draft() -> dict | None:
    return st.session_state.get("draft")


def put_draft(state, meta, vi=None, risk=None) -> None:
    st.session_state["draft"] = {"state": state, "meta": meta, "vi": vi, "risk": risk}


def clear_draft() -> None:
    """Drop the draft **and everything derived from it**.

    The per-draft caches are listed here rather than being left to expire on their own because
    every one of them would otherwise survive into the next draft: the room's pick function is
    built from the old seat map, and a pending pick is a board index into a board that no longer
    has that player available. T34 made this reachable — before it, the next draft was the same
    draft, so a stale room function was indistinguishable from a correct one.
    """
    for k in ("draft", "odds", "_arrived_post_draft", "_room_fn", "pending_pick",
              "clock_worst_s"):
        st.session_state.pop(k, None)
