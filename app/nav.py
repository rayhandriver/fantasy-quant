"""The page registry — one place that knows what the pages are called and how to get to one.

``st.switch_page`` wants the :class:`st.Page` object, which only the router builds. Rather than
have every page import the router (a cycle, and the usual "fix" for a cycle is a second copy of
whatever was needed), the router *registers* its pages here on every rerun — it runs top to bottom
before any page body does — and pages navigate by name.
"""

from __future__ import annotations

import streamlit as st

#: name -> ``st.Page``. Repopulated by the router on every rerun; never written by a page.
PAGES: dict[str, object] = {}

#: Registration order == the order the sidebar lists them, which is the order a drafter uses them.
#: ``post`` (14.N) sits after the room because that is where the last pick sends you.
ORDER: tuple[str, ...] = ("settings", "board", "draft", "grid", "post", "cost")


def register(pages: dict[str, object]) -> None:
    PAGES.clear()
    PAGES.update(pages)


def go(name: str) -> None:
    """Navigate to a registered page. A no-op if the router has not registered one by that name,
    so an offline test that calls a page body directly does not have to fake the router."""
    page = PAGES.get(name)
    if page is not None:
        st.switch_page(page)
