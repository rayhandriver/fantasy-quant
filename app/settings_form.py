"""The 17.3 league-settings form — platform-agnostic, and the thing that un-orphans Phase 17.

Before Session K1, :class:`~fantasy_quant.draft.config.LeagueSettings` was imported by nothing
outside its own gate ``steps/phase17_formats.py``: the whole format-fidelity track was
correctness-tested and wired to no surface a user touches. This module is the binding.

Two rules the UI half owns, both of them honesty rather than features:

★ **``lockbox_validated()`` is rendered, always.** The lockbox was spent once, on a 10-team
full-PPR 1-QB league. Superflex, TE-premium, custom brackets and keepers are supported and
unit-tested for *correctness* and carry **no** out-of-sample claim. A user in a non-default league
must be told that in the interface, not in a docstring.

⚠ **Changing the scoring preset requires explicit confirmation** (bar B6). ``RuleSet`` is
serialized into :func:`~fantasy_quant.projections.distribution.cached_distribution`'s cache key, so
a cosmetic scoring change splits the cache and forces a silent nine-season rebuild — ~6 minutes per
season. A dropdown must not be able to trigger that by being brushed with a mouse.
"""

from __future__ import annotations

import streamlit as st

from fantasy_quant.backtest.scoring import SCORING_PRESETS
from fantasy_quant.draft.config import LeagueSettings

#: Presets a user picks by name. Anything beyond these is an override, and an override is what
#: makes a league unvalidated — so the two are separate controls rather than one free-text box.
PRESET_LABELS: dict[str, str] = {
    "full_ppr": "Full PPR (1.0 per reception)",
    "half_ppr": "Half PPR (0.5 per reception)",
    "standard": "Standard (no PPR)",
    "te_premium": "TE premium (+0.5 per TE reception)",
}


def settings_form(default: LeagueSettings | None = None) -> tuple[LeagueSettings, bool]:
    """Render the form. Returns ``(settings, applied)`` — ``applied`` is the submit press.

    The default is the lockbox case, which is both the most common league and the only one any
    out-of-sample number describes.
    """
    d = default or LeagueSettings()
    with st.form("league_settings"):
        st.markdown("#### League shape")
        c1, c2, c3 = st.columns(3)
        n_teams = c1.number_input("Teams", 4, 20, int(d.n_teams), step=2)
        draft_slot = c2.number_input("Your draft slot", 1, int(n_teams),
                                     min(int(d.draft_slot), int(n_teams)))
        rounds = c3.number_input("Rounds", 5, 30, int(d.rounds))

        st.markdown("#### Starting lineup")
        c = st.columns(5)
        qb = c[0].number_input("QB", 0, 3, int(d.qb))
        rb = c[1].number_input("RB", 0, 5, int(d.rb))
        wr = c[2].number_input("WR", 0, 6, int(d.wr))
        te = c[3].number_input("TE", 0, 3, int(d.te))
        flex = c[4].number_input("FLEX", 0, 4, int(d.flex))
        c = st.columns(4)
        superflex = c[0].number_input("SUPERFLEX / OP", 0, 2, int(d.superflex),
                                      help="A flex that may also take a QB. Lifts QB value sharply "
                                           "— the replacement level moves QB10 → QB20.")
        k = c[1].number_input("K", 0, 2, int(d.k))
        dst = c[2].number_input("DST", 0, 2, int(d.dst))
        bench = c[3].number_input("Bench", 0, 15, int(d.bench))

        st.markdown("#### Scoring")
        preset = st.selectbox("Preset", list(SCORING_PRESETS),
                              index=list(SCORING_PRESETS).index(d.scoring_preset),
                              format_func=lambda p: PRESET_LABELS.get(p, p))
        changed = preset != d.scoring_preset
        confirm = st.checkbox(
            "I understand changing the scoring rebuilds the projection cache (slow, one-time)",
            value=False, disabled=not changed,
            help="RuleSet is part of the distribution cache key, so a scoring change invalidates "
                 "every cached season — roughly 6 minutes per season, once.")

        st.markdown("#### Season & bracket")
        c1, c2 = st.columns(2)
        reg_weeks = c1.number_input("Regular-season weeks", 10, 17, int(d.reg_weeks))
        playoff_teams = c2.selectbox("Playoff teams", [4, 6, 8],
                                     index=[4, 6, 8].index(int(d.playoff_teams))
                                     if int(d.playoff_teams) in (4, 6, 8) else 1)
        applied = st.form_submit_button("Apply settings", type="primary")

    # B6 — a scoring change that is not confirmed does not take effect, and says so.
    if applied and changed and not confirm:
        st.warning("Scoring change not applied — tick the confirmation box. Every other setting "
                   "was applied.")
        preset = d.scoring_preset

    settings = LeagueSettings(
        n_teams=int(n_teams), draft_slot=int(draft_slot), rounds=int(rounds),
        qb=int(qb), rb=int(rb), wr=int(wr), te=int(te), flex=int(flex), superflex=int(superflex),
        k=int(k), dst=int(dst), bench=int(bench), scoring_preset=str(preset),
        reg_weeks=int(reg_weeks), playoff_teams=int(playoff_teams))
    return settings, bool(applied)


def validation_message(settings: LeagueSettings) -> str | None:
    """``None`` when the league is playable, else the reason it is not — rendered, never swallowed.

    Phase 17 is deliberately strict here: the alternative is a league that configures cleanly and
    then produces a silently wrong board, which is the failure this whole track exists to avoid.
    """
    try:
        settings.validate()
        settings.roster_slots()
    except (ValueError, AssertionError) as exc:
        return str(exc)
    return None


def lockbox_banner(settings: LeagueSettings) -> None:
    """The honesty surface, as a **badge with the paragraph one click behind it** (UI-1 S3).

    **Not a feature flag** — both branches describe supported leagues. The distinction it draws is
    about evidence, not capability: one configuration has an out-of-sample result behind it and
    every other one has correctness tests and nothing more.

    ★ **Compressed, not deleted, and that is the whole discipline of UI-1 step 3.** It was a
    four-line coloured block at the top of three pages, which is the shape an eye learns to skip.
    A green or amber chip with the same sentences in a popover is *more* likely to be read, and bar
    B3 asserts that **both branches still render** by driving the app rather than by reading the
    diff — because the failure mode of a compression pass is a surface that quietly stops
    appearing, and that failure looks exactly like success in a diff.
    """
    validated = settings.lockbox_validated()
    c1, c2 = st.columns([1, 3])
    if validated:
        c1.badge("LOCKBOX-VALIDATED", color="green", icon=":material/verified:")
    else:
        c1.badge("NOT LOCKBOX-VALIDATED", color="orange", icon=":material/priority_high:")
    with c2.popover("What that means", icon=":material/help:"):
        if validated:
            st.markdown(
                "**This is the exact format the held-out evaluation was spent on** — 2023 + 2024, "
                "once, and once only: title Brier **0.088**, conditional distribution coverage "
                "**80.1 %**, projection Spearman **0.54**.\n\nThose numbers describe *this* "
                "configuration: 10 teams, full PPR, one QB. They are the only out-of-sample claim "
                "this project has, and it cannot be re-spent.")
        else:
            st.markdown(
                "**Supported, and correctness-tested — but carrying no out-of-sample claim.**\n\n"
                "The lineup solver for your slots is checked against an exhaustive brute force and "
                "the VBD replacement levels are recomputed for your format (a superflex league "
                "moves QB replacement from QB10 to QB20, which lifts the best QB from overall rank "
                "15 to 3). The board is right.\n\nWhat does not transfer is the *calibration*: the "
                "held-out evaluation was spent once, on a 10-team full-PPR 1-QB league. Title "
                "Brier 0.088 is evidence about that league and not about yours.")
