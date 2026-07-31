"""Fantasy-Quant — the draft-day app (Phase 14.1 / Sessions K1 + K1.5).

    uv sync --extra ui
    uv run streamlit run app/main.py

★ **This file is a router.** In K1 it was the app: four ``st.tabs``, four bodies, all executed on
every rerun — which is T35, and which is why a keystroke in the draft room also rebuilt the cost
page's whole-board option list. 14.K replaces them with ``st.navigation`` / ``st.Page``: real
pages, real URLs, **one body per rerun**, and a draft room that is a *place* you are in rather than
a tab you are on.

Pages, in the order a drafter uses them: **Settings** (your league, 17.3) → **Board** (the live
board with the T27 value chain and ``why``) → **Draft room** (any k of n seats against the
calibrated room, 16.15/16.17/14.J, on a clock) → **Room** (14.L's grids, the standings, the odds)
→ **Cost** (what your preferences cost against the pure-value benchmark — the direct-indexing
deliverable the 2026-07-04 reframe was built around).

★ **The app still derives nothing.** Every number comes from :mod:`fantasy_quant.draft.session`,
which ``steps/mock_draft.py`` also reads, so the app and the CLI cannot disagree — there is one
computation and two renderers. That is Session K1's bar B1, satisfied by construction rather than
by testing two implementations against each other and hoping.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ⚠ **This must run before `from app import ...`, and it is not boilerplate.**
# `streamlit run app/main.py` executes this file with **`app/` on `sys.path`, not the repo root**,
# so the `app` *package* is not importable from inside its own entry point. (`python -m streamlit`
# happens to work, because `-m` puts the cwd on the path — which is exactly how this shipped
# broken: the done-bar launched it that way while the README told a human to use the console
# script. *A guard that does not run on the path a human uses is not a guard* — T27's rule, and
# this session's own finding, arriving one level up.) Bootstrapping here makes every invocation
# work: the console script, `python -m streamlit`, `AppTest`, and any working directory.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st  # noqa: E402

from app import nav  # noqa: E402
from app.draft_room import page_draft  # noqa: E402
from app.post_draft import page_post  # noqa: E402
from app.room_grid import page_grid  # noqa: E402
from app.screens import page_board, page_cost, page_settings  # noqa: E402

#: name -> (body, title, icon, url_path). The registry :mod:`app.nav` hands back to any page that
#: needs to navigate — the draft room sends you into itself when a draft starts and to the room
#: grid on the final pick.
PAGE_SPECS: dict[str, tuple] = {
    "settings": (page_settings, "Settings", "⚙️", "settings"),
    "board": (page_board, "Board", "📋", "board"),
    "draft": (page_draft, "Draft room", "🎯", "draft"),
    "grid": (page_grid, "The room", "🧑‍🤝‍🧑", "room"),
    "post": (page_post, "Post-draft", "🏁", "post-draft"),
    "cost": (page_cost, "Cost", "💸", "cost"),
}


def build_pages() -> dict[str, object]:
    pages = {}
    for i, name in enumerate(nav.ORDER):
        body, title, icon, url = PAGE_SPECS[name]
        pages[name] = st.Page(body, title=title, icon=icon, url_path=url, default=(i == 0))
    return pages


def main() -> None:
    st.set_page_config(page_title="Fantasy-Quant · Draft", page_icon="🏈", layout="wide")
    pages = build_pages()
    nav.register(pages)
    st.sidebar.title("🏈 Fantasy-Quant")
    st.sidebar.caption("Value = consensus → VBD, risk-dialed · availability = ADP + a fitted "
                       "behavioral opponent model · variance = our own distributions.")
    st.navigation(list(pages.values())).run()


# ⚠ guarded, and the guard matters more than it looks: `tests/test_app.py` imports this module to
# assert the app and the CLI resolve to the same `session` functions (bar B1), and an unguarded
# call would run the whole app — router, DuckDB connection and all — at import time.
if __name__ == "__main__":
    main()
