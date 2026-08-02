"""The draft-session surface, as data — the one place the CLI and the app both read.

★ **Why this module exists (Session K1).** ``steps/mock_draft.py`` grew into a complete
human-in-the-loop draft driver: the board with the T27 value chain, the ``why`` arithmetic, the room
over 16.17's :class:`~fantasy_quant.draft.personalities.SeatMap`, the T28 dual-labelled summary, the
T29 fair-share odds. All of it was *printed* — the derived frames existed only as f-strings inside
``print`` calls. A Streamlit app needs the same numbers as objects, and there are exactly two ways
to get them:

1. re-derive them in the app, or
2. compute them **once**, here, and let both surfaces render them.

This repo has already paid for (1) three times, under three names. ``mock.py``'s own docstring
states the rule — *if the two sides of a comparison are computed by different code, the comparison
measures the code* — and T18 (``avg_reach``), F.5 (the hardcoded ``scoring``) and T27 (the display
path and the decision path built separately, so the interactive room was never the shipped room)
are the same defect at three altitudes. **So the app does not "agree with" the CLI; there is one
computation and two renderers.** Session K1's bar B1 is thereby satisfied by construction, and its
test asserts the construction rather than a coincidence of formatting.

Everything here is **pure in the sense that matters**: no printing, no ``SystemExit``, no Streamlit.
Errors are raised as ordinary exceptions (:class:`LookupError`, :class:`ValueError`) for the caller
to render however its medium renders errors. The one impure edge is :func:`build_board`, which reads
the store — it takes an open connection rather than opening one, so a UI can cache it.

⚠ **This module holds no modelling.** Every number it returns is read from a frozen contract or
computed by the engine; the only thing added is arrangement. A function here that *computes* a
quantity rather than reading one is a bug — see :func:`explain_chain`, whose entire design is that
``lambda*Var`` is printed as ``mean - ce_value`` rather than recomputed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

import numpy as np
import pandas as pd

from fantasy_quant.draft import mock, optimizer
from fantasy_quant.draft.config import DraftConfig
from fantasy_quant.draft.personalities import (
    DEFAULT_ROOM,
    HUMAN,
    REALISTIC_ROOM,
    SeatMap,
    personalities,
)
from fantasy_quant.draft.simulator import (
    DraftState,
    _apply_pick,
    pick_by_adp,
)

#: The board columns a human reads, in the order the arithmetic runs (T27). ``PROJ`` is the
#: consensus projection, ``MEAN`` the Phase-5 season mean, ``AVAIL`` the games-played read that
#: explains the gap between them, and ``BV`` the ``base_value`` every seat actually optimizes.
#: Keeping the order here rather than in a format string is what lets the app render the same
#: columns without re-deciding what they are.
BOARD_VIEW_COLS: tuple[tuple[str, str], ...] = (
    ("player_name", "PLAYER"), ("pos", "POS"), ("adp", "ADP"),
    ("proj_points", "PROJ"), ("mean", "MEAN"), ("games_played_mean", "AVAIL"),
    ("base_value", "BV"), ("vbd", "VBD"), ("overall_rank", "RK"),
    ("upside", "UPSIDE"), ("floor", "FLOOR"), ("tail_risk", "TAIL"),
    # ⚠ the **live** boom/bust pair (T22). The frozen Phase-5 columns are measured at
    # `max(train_seasons)` = 2022, so on a live board a player who was not in the league that
    # season reads 0.00 — which renders as *never busts*. These are the same rates on season − 1,
    # and an unseen player stays NaN so the renderer can print "-" instead of a fabricated zero.
    ("boom_prob_live", "BOOM"), ("bust_prob_live", "BUST"),
    # 14.E — the 9.1 scarcity cliff, read from the *decision* path rather than re-derived for
    # display (see :func:`cliff_series`). It is last because it is the only column here that
    # depends on the rest of the pool rather than on the player.
    ("cliff", "CLIFF"),
)

#: Board columns that exist on the frame for :data:`RANGE_VIEW_COLS` to project but are not part of
#: the advanced view — the raw Phase-5 quantiles and the two flags derived from them. Kept separate
#: so the advanced view stays exactly :data:`BOARD_VIEW_COLS` and each mode is a *named subset* of
#: one frame rather than three frames that have to be kept agreeing.
_RANGE_EXTRA_COLS: tuple[tuple[str, str], ...] = (
    ("q10", "Q10"), ("q50", "MED"), ("q90", "Q90"),
)

#: The columns a human actually drafts on under a clock, plus the ``#`` pick handle carried by the
#: index. **Slim is a projection of :func:`board_view`, never a second query** — one derivation, two
#: column subsets, which is why :data:`BOARD_VIEW_COLS` and this tuple cannot describe different
#: rows. (K1.5 step 2. The advanced view is simply :data:`BOARD_VIEW_COLS` in full.)
#:
#: ★ **UI-2 adds ``Δ`` and keeps ``PROJ``.** The session was authorised to trade ``PROJ`` away
#: for ``TIER`` — the two questions under a clock being *"is he in the same tier as the man below
#: him"* and *"is the draft past his price"*. ``TIER`` did not survive its own measurement (see
#: :func:`tier_series`), so the trade had nothing to trade for and ``PROJ`` stays. ``Δ`` ships:
#: it is the half of the pair that measured out.
SLIM_VIEW_COLS: tuple[str, ...] = ("PLAYER", "POS", "ADP", "PROJ", "Δ")

#: **14.G — the board as ranges rather than false-precise ranks.** The same frame again, projected
#: onto the distribution's own quantiles: ``Q10``/``MED``/``Q90`` are the frozen Phase-5 season
#: quantiles in points, ``COIN`` marks a player whose 80 % interval overlaps the player ranked
#: directly below him, and ``FLAGS`` carries the PLAYER-VIEW confidence markers.
#:
#: ⚠ **``Q10`` is left-censored and the renderer must say so.** A season-points quantile cannot go
#: below zero, so ``enrichment.CENSOR_AT`` piles up **36 % of the 2026 board** on exactly 0.0 —
#: those rows do not have a floor of zero, they have *no resolvable floor*, which is T19's finding
#: one display layer up. :func:`range_flags` emits ``censored floor`` for them and
#: :data:`STAT_DICT` says it in the tooltip; printing a bare ``0`` would be the T22 defect
#: (*blank is not zero*) wearing the other sign.
RANGE_VIEW_COLS: tuple[str, ...] = ("PLAYER", "POS", "ADP", "PROJ", "Q10", "MED", "Q90",
                                    "COIN", "FLAGS")

#: **UI-2 step 4 — ``ADVANCED``'s fifteen columns, split in two.** Fifteen is two more than Draft
#: Sharks' full rankings table, whose density is the single most-criticised property in its own
#: category reviews (`docs/UI-PLAN.md` §1.2). The split is not a deletion: both halves are
#: projections of the same one :func:`board_view` frame, so bar B4's *one query, N projections*
#: property is preserved exactly as it was when there were three.
#:
#: ``VALUE`` is the T27 chain plus the two "relative to *now*" columns UI-2 adds; ``RISK`` is the
#: shape/uncertainty block plus the tier and the two flag columns. ``CLIFF`` sits in ``VALUE``
#: because a positional cliff is a statement about *value* falling away, not about a player's own
#: variance — the one placement UI-PLAN's sketch of this split did not name.
VALUE_VIEW_COLS: tuple[str, ...] = ("PLAYER", "POS", "ADP", "PROJ", "MEAN", "AVAIL", "BV", "VBD",
                                    "RK", "Δ", "BARGAIN", "CLIFF")
RISK_VIEW_COLS: tuple[str, ...] = ("PLAYER", "POS", "UPSIDE", "FLOOR", "TAIL", "BOOM", "BUST",
                                   "RISKS", "FLAGS")

#: The board projections, in the order the mode control offers them.
#:
#: ⚠ **``advanced`` stays**, and is deliberately no longer on the app's control. K1.5's and K2's
#: committed sheets both difference against ``project_view(view, advanced=True)`` returning exactly
#: :data:`BOARD_VIEW_COLS`; deleting the mode would force an edit to two committed bar sheets to
#: keep them passing, and *a bar sheet that has to be edited to keep passing is not a bar sheet.*
VIEW_MODES: tuple[str, ...] = ("slim", "ranges", "value", "risk", "advanced")

#: The four modes a **human** is offered (UI-2 step 4). ``advanced`` is reachable from the CLI and
#: from :func:`project_view`, and is not on the app's segmented control: the whole point of the
#: split is that nobody reads fifteen columns, and leaving the fifteen on the control means they
#: stay read.
APP_VIEW_MODES: tuple[str, ...] = ("slim", "ranges", "value", "risk")

#: **The one column that is attached rather than projected** (UI-1 step 5 / bar B5).
#: ``P(THERE)`` is :func:`reach_risk_view`'s ``p_available`` placed beside the board instead of in a
#: panel of its own. It is *not* in :data:`BOARD_VIEW_COLS`, and that is deliberate: the readout
#: costs ~20 ms of survival simulation and depends on the seat's *next* pick, so making it part of
#: ``board_view`` would charge every caller — the CLI, every bar sheet, nine seasons of cached
#: measurement — for a number most of them never look at. :func:`attach_reach` is therefore a
#: **placement**, not a derivation: it moves an existing frame's column onto an existing frame's
#: rows and computes nothing.
REACH_COL: str = "P(THERE)"

#: **UI-2 step 3 — the construction glyphs, and the one place they are spelled.** Each is a fact
#: about the pair *(your roster, this player)* that :func:`roster_construction_risk` already
#: computed and, until now, only rendered **after** the draft — when none of it can be acted on.
#:
#: ⚠ **The ``FLAGS`` string was not extended to carry these**, exactly as UI-1 refused to put ``⌀``
#: on it: K2's bar B4 matches on ``FLAGS``' text, and a display layer must not edit the thing a bar
#: reads. ``RISKS`` is a second, separate column — the *scan* channel, where ``FLAGS`` is the *read*
#: channel. ``⌀`` and ``◔`` appear in both by design; a glyph you can sweep a column for and a
#: sentence you can read are different jobs.
CONSTRUCTION_GLYPHS: dict[str, str] = {
    "bye": "⚑",          # his bye week already holds ≥1 of your starters
    "stack": "⛓",        # same NFL team as ≥1 of your starters
    "handcuff": "🛡",     # he is the backup to a lead RB you already hold
    "censored": "⌀",     # q10 sits on the censoring point — no resolvable floor (T19)
    "thin": "◔",         # no Phase-5 distribution, or never seen play (T22)
}

#: The three columns UI-2 derives onto the board. Named here so the CLI, the app and the bar sheet
#: all agree on what "the new columns" means without any of them listing the strings again.
UI2_COLS: tuple[str, ...] = ("Δ", "BARGAIN", "RISKS")


#: **14.O — one stat dictionary, served to every surface.** Board tooltips, the room grid, the
#: post-draft page and the CLI's ``stats`` command all read this; ``views._BOARD_HELP`` (a terse,
#: app-only copy) is deleted rather than kept in sync, because two help texts for one column are
#: two chances to describe it differently.
#:
#: ★ **Every entry carries a worked example off the live board**, which is what the request was
#: actually about: a column is not explained by a definition a drafter has to translate. The
#: numbers below are the 2026 FFC board (07-30 snapshot) and are asserted to be *real* nowhere —
#: they are illustrative text, and the test that guards this dictionary checks **coverage**
#: (``BOARD_VIEW_COLS`` ⊆ ``STAT_DICT``), not equality with today's board.
#:
#: ⚠ **Two entries carry their known limitation in the tooltip, not in a doc** — ``BOOM``/``BUST``
#: (T22: blank means *never seen play*, not *never busts*) and ``MEAN``/``AVAIL`` (T31: the level
#: correction was extrapolating below its own support for deep players until it was capped). A
#: limitation a user has to find in `findings.md` is a limitation nobody reads.
STAT_DICT: dict[str, dict[str, str]] = {
    "PLAYER": {
        "label": "Player",
        "one_line": "The player, as the ADP board names him.",
        "what_it_means": "Names come from the FFC board and are crosswalked to nflverse gsis ids; "
                         "team defenses key on their name because they carry no gsis.",
        "worked_example": "“James Cook III” is one player, not three.",
        "how_to_read_it": "Type any part of it into the pick box — matching is case-insensitive "
                          "and substring-based.",
        "provenance": "adp_snapshots (FFC) → simulator.board_player_key",
    },
    "POS": {
        "label": "Position",
        "one_line": "Canonical position: QB, RB, WR, TE, K or DST.",
        "what_it_means": "Every source position is mapped to these six; anything that maps to "
                         "none of them is not draftable and never reaches the board.",
        "worked_example": "A player listed 'FB' on one feed and 'RB' on another is RB here, once.",
        "how_to_read_it": "It drives the roster caps, the starter slots and the replacement level "
                          "your value is measured against.",
        "provenance": "simulator.canon_pos",
    },
    "ADP": {
        "label": "Average draft position",
        "one_line": "Where this player actually goes, in leagues shaped like yours.",
        "what_it_means": "The FFC consensus ADP for your team count and scoring, from the most "
                         "recent snapshot in the store. It is the availability signal — what the "
                         "room will do — and it is deliberately NOT the value signal.",
        "worked_example": "Jahmyr Gibbs 1.7 means he is typically gone by the second pick.",
        "how_to_read_it": "Compare it to RK. A player whose RK is far better than his ADP is the "
                          "board saying you can wait; the reverse is the board saying he is "
                          "priced past his value.",
        "provenance": "adp_snapshots, source 'ffc' (Stage-0 chore keeps it fresh)",
    },
    "PROJ": {
        "label": "Consensus projection",
        "one_line": "Season points the consensus expects, re-scored to your league's rules.",
        "what_it_means": "The number a human trusts, and the start of the value chain. Scraped "
                         "from FantasyPros and re-scored through our own RuleSet, so a half-PPR "
                         "or TE-premium league moves it rather than being labelled onto it.",
        "worked_example": "Gibbs 372 · Jayden Daniels 313 — both full seasons, as projected.",
        "how_to_read_it": "It is a healthy-season number. The gap between PROJ and MEAN is the "
                          "availability haircut, and it is often large.",
        "provenance": "projections/consensus.py → backtest/scoring.RuleSet",
    },
    "MEAN": {
        "label": "Season mean",
        "one_line": "PROJ × projected availability — the level the engine actually believes.",
        "what_it_means": "The Phase-5 distribution's mean. It prices the games a player is "
                         "expected to miss, which the consensus projection does not.",
        "worked_example": "Drake Maye 316 PROJ → 261 MEAN (14.4 games). Daniels 313 PROJ → 137 "
                          "MEAN (7.7 games). Three points apart on the projection, 124 apart here.",
        "how_to_read_it": "⚠ Known limitation (T31): for players the consensus prices as backups, "
                          "this correction was extrapolating below the data it was fitted on and "
                          "is now capped. Deep-board MEANs are the least trustworthy numbers on "
                          "this screen.",
        "provenance": "projections/distribution.py (Phase 5), level-capped by quantile.py (T31)",
    },
    "AVAIL": {
        "label": "Projected games played",
        "one_line": "Games of 17 — the column that explains the PROJ → MEAN gap.",
        "what_it_means": "A discrete-time hazard model plus a cohort prior for players with too "
                         "little history, and a role-washout term for established players the "
                         "board projects deep (T3).",
        "worked_example": "Maye 14.4 vs Daniels 7.7 is the whole of their 124-point MEAN gap.",
        "how_to_read_it": "Anything under ~12 is the model saying it expects real missed time, "
                          "not a rounding of 17.",
        "provenance": "projections/injury.py (Phase 5.4 + T3)",
    },
    "BV": {
        "label": "base_value",
        "one_line": "(MEAN − λ·Var) − positional replacement. What every seat optimizes.",
        "what_it_means": "The end of the value chain: risk-adjust the mean by your λ dial, then "
                         "subtract what a waiver claim at that position would have given you. It "
                         "is the only column any drafting policy in this engine reads.",
        "worked_example": "Maye +68.5, Daniels −101.6 — three ADP rounds apart and 170 points "
                          "apart in what they are worth to a roster.",
        "how_to_read_it": "Negative is not a typo: it means a freely available player at that "
                          "position projects better. Use `why` to see the arithmetic.",
        "provenance": "valuation/value_board.py + utility.py (Phase 4/5.5)",
    },
    "VBD": {
        "label": "Frozen Phase-4 VBD",
        "one_line": "Value over replacement before the risk dial — kept for reference.",
        "what_it_means": "The pre-Phase-5 value board: projection minus replacement, no "
                         "distribution and no λ. Shown because it is the number the lockbox "
                         "evaluation was run against.",
        "worked_example": "Gibbs 170.6 VBD against 91.4 BV — the risk dial and the availability "
                          "haircut are the difference.",
        "how_to_read_it": "If VBD and BV disagree sharply, the disagreement is about health and "
                          "variance, not about talent.",
        "provenance": "valuation/value_board.py (frozen contract)",
    },
    "RK": {
        "label": "Overall value rank",
        "one_line": "This player's rank on the value board, 1 = best.",
        "what_it_means": "The board sorted by value rather than by what the room will do. It is "
                         "computed against YOUR roster slots, so it moves with your settings.",
        "worked_example": "In a superflex league the best QB moves from overall rank 15 to 3, "
                          "because the QB replacement level shifts from QB10 to QB20.",
        "how_to_read_it": "RK vs ADP is the whole draft-day decision: value against availability.",
        "provenance": "valuation/value_board.py, recomputed per LeagueSettings",
    },
    "UPSIDE": {
        "label": "Relative ceiling",
        "one_line": "More ceiling than a player projected this high usually has.",
        "what_it_means": "q90 ÷ MEAN, then the projected level regressed out within position by "
                         "rank. The residual is the point: raw q90 correlates 0.98+ with the mean, "
                         "so an uncorrected 'upside' column is a quality tilt in disguise (16.14).",
        "worked_example": "Jayden Daniels +0.46 — his ceiling is unusually high *for his level*, "
                          "which is a different claim from being good.",
        "how_to_read_it": "Centred on 0, roughly −0.5 … +0.5. Positive = more headroom than his "
                          "peers; it says nothing about whether he is a better player.",
        "provenance": "draft/enrichment.py residual_shape (16.13)",
    },
    "FLOOR": {
        "label": "Relative floor",
        "one_line": "More floor than a player projected this high usually has.",
        "what_it_means": "q10 ÷ MEAN, level-residualized within position by **rank** rather than "
                         "by OLS — 42.9 % of the 2026 board has q10 exactly 0, and a line fitted "
                         "through that floor rewarded replacement-level players (T19).",
        "worked_example": "Jaxon Smith-Njigba +0.48 floor against Drake London −0.20.",
        "how_to_read_it": "Centred on 0. It is the mirror of UPSIDE by construction "
                          "(corr ≈ −0.71), so a player rarely has both.",
        "provenance": "draft/enrichment.py residual_shape (16.13, T19 rank method)",
    },
    "TAIL": {
        "label": "Boom-or-bust spread",
        "one_line": "(q90 − q10) ÷ MEAN, level-controlled — total relative spread.",
        "what_it_means": "The honest variance read, and the column that replaces the broken "
                         "boom/bust pair for anyone who wants one number.",
        "worked_example": "Daniels +0.46 (wide) against Jaxon Smith-Njigba −0.48 (tight).",
        "how_to_read_it": "High = the outcome is genuinely uncertain, in both directions. Whether "
                          "you want that depends on your format: managed lineups punish it, "
                          "best-ball rewards it.",
        "provenance": "draft/enrichment.py residual_shape (16.13)",
    },
    "BOOM": {
        "label": "Live boom rate",
        "one_line": "Share of last season's weeks above 1.5× his own average.",
        "what_it_means": "Measured on season − 1, refreshed every year (T22). The frozen Phase-5 "
                         "boom column is stuck at 2022 and reads 0.000 for anyone who was not in "
                         "the league that year, which is why this one exists.",
        "worked_example": "Christian McCaffrey 0.71 · Justin Jefferson 0.06 — same tier, opposite "
                          "week-to-week shapes.",
        "how_to_read_it": "⚠ **Blank means never seen play, not never booms.** Rookies are blank "
                          "and must stay blank; 27 % of the 2026 board has no reading at all.",
        "provenance": "draft/enrichment.py live_volatility (T22)",
    },
    "BUST": {
        "label": "Live bust rate",
        "one_line": "Share of last season's weeks under half his own average.",
        "what_it_means": "The mirror of BOOM, on the same season − 1 window and with the same "
                          "blank-is-not-zero rule.",
        "worked_example": "Jaylen Waddle 0.19 — about one week in five came in under half his own "
                          "average.",
        "how_to_read_it": "⚠ **Blank means never seen play, not never busts.** Fixing that "
                          "misreading took the exact-zero share from 56 % to 8 % (T22).",
        "provenance": "draft/enrichment.py live_volatility (T22)",
    },
    "CLIFF": {
        "label": "Tier cliff",
        "one_line": "How far the board falls at this player's position just below him.",
        "what_it_means": "His base_value minus the value of the 3rd-next-best available player at "
                         "the same position, floored at zero. A steep cliff means the tier does "
                         "not refill: taking him is the difference between a starter and a "
                         "replacement. A flat one means waiting costs you almost nothing.",
        "worked_example": "RB 41 with two RBs above the same cliff = the third RB off this tier "
                          "is 41 points of base_value worse than the second, so the drop happens "
                          "inside the next two picks at that position.",
        "how_to_read_it": "Read it beside ADP, not instead of it — a big cliff on a player nobody "
                          "else is taking for two rounds is not urgent. That pairing is exactly "
                          "what the drafting policy does (9.1 cliff × 9.4 survival).",
        "provenance": "draft/optimizer.py positional_cliff (9.1) — the same call the greedy makes",
    },
    "Q10": {
        "label": "Downside (10th percentile)",
        "one_line": "One season in ten finishes at or below this.",
        "what_it_means": "The frozen Phase-5 season-points 10th percentile, in points — the bad "
                         "tail of the same distribution MEAN is the average of.",
        "worked_example": "Jahmyr Gibbs 129 against a mean of 265: a bad Gibbs season is still "
                          "half a good one.",
        "how_to_read_it": "⚠ **A season total cannot be negative, so this column is censored at "
                          "zero and about a third of the board sits exactly on it.** Those rows "
                          "are flagged `censored floor`: they do not have a floor of zero, they "
                          "have no resolvable floor (T19).",
        "provenance": "player_distributions.q10 (Phase 5), via draft/enrichment.py",
    },
    "MED": {
        "label": "Median (50th percentile)",
        "one_line": "The middle season — half above, half below.",
        "what_it_means": "The frozen Phase-5 q50. It sits below MEAN for most players because "
                         "season totals are right-skewed: a healthy career year pulls the average "
                         "up further than a lost season pulls it down.",
        "worked_example": "Puka Nacua: median 273 against a mean of 264 — one of the rows where "
                          "the ordering reverses, which is the availability tail doing the work.",
        "how_to_read_it": "Compare it to MEAN to see which way a player's season is skewed.",
        "provenance": "player_distributions.q50 (Phase 5), via draft/enrichment.py",
    },
    "Q90": {
        "label": "Upside (90th percentile)",
        "one_line": "One season in ten finishes at or above this.",
        "what_it_means": "The frozen Phase-5 season-points 90th percentile, in points.",
        "worked_example": "Bijan Robinson 413 — a top-of-the-range Bijan season is 150 points "
                          "clear of his own mean.",
        "how_to_read_it": "The gap Q90 − Q10 is the width of the whole claim. A wide band on a "
                          "high mean is a swing; a wide band on a low mean is a lottery ticket.",
        "provenance": "player_distributions.q90 (Phase 5), via draft/enrichment.py",
    },
    "COIN": {
        "label": "Coin flip with the next player",
        "one_line": "True when this player's 10–90 band overlaps the player ranked below him.",
        "what_it_means": "Two adjacent rows whose 80 % intervals overlap are not distinguishable "
                         "by this model. The board still has to print them in *some* order, and "
                         "this column is the board admitting that the order is not evidence.",
        "worked_example": "On the 2026 board **146 of the 147 adjacent pairs whose bands can both "
                          "be read overlap** — the ordering is a presentation almost everywhere, "
                          "not a finding.",
        "how_to_read_it": "Where it is true, break the tie on something the model does not price: "
                          "your own read, roster fit, or the construction risks in RISKS. ⚠ Read "
                          "the denominator: this column is also False when a band is *missing*, "
                          "which is 52 of the top 200's 199 pairs. The often-quoted '146 of 199' "
                          "therefore sums *distinguishable* and *unknown* into one number — of the "
                          "pairs we can evaluate at all, 99.3 % overlap (UI-2).",
        "provenance": "derived in session.range_flags from the frozen q10/q90 pair",
    },
    "FLAGS": {
        "label": "Confidence flags",
        "one_line": "Why a row's numbers deserve less weight than they look like they deserve.",
        "what_it_means": "`no distribution` — no Phase-5 cloud at all, so this player drafts on "
                         "ADP fallback and no seat's value objective can see him. `censored "
                         "floor` — Q10 is on the zero censoring point. `rookie` — no NFL prior, so "
                         "his projection is the 4.3 ridge landing-spot model rather than a "
                         "measured history.",
        "worked_example": "A rookie WR with `rookie, censored floor` has both a modelled level and "
                          "an unresolvable downside — two independent reasons his band is softer "
                          "than a veteran's of the same width.",
        "how_to_read_it": "Flags never change a number; they tell you how hard to lean on one.",
        "provenance": "session.range_flags over the board's rookie / q10 / mean columns",
    },
    # ---- UI-2's three ----------------------------------------------------------------------
    "Δ": {
        "label": "ADP countdown",
        "one_line": "His ADP minus the pick the draft is on right now.",
        "what_it_means": "Value relative to *now*, which is the thing every product in the "
                         "category shows and we showed relative to nothing. Positive means the "
                         "board has not reached his price yet — he is falling toward you; negative "
                         "means the draft is already past it and taking him is a reach of that "
                         "many picks.",
        "worked_example": "At pick 9, a player with ADP 11.4 reads `+2.4` — the room would "
                          "typically take him two picks from now. Same player at pick 15 reads "
                          "`−3.6`.",
        "how_to_read_it": "Read it against P(THERE), not instead of it: Δ is where the *market* "
                          "is, P(THERE) is what the fitted room will actually do before your turn "
                          "comes round. A big positive Δ on a player with a low P(THERE) is "
                          "precisely the trap — cheap by the market, gone by your pick.",
        "provenance": "session.board_view — adp − DraftState.overall_pick, the engine's own "
                      "pick counter",
    },
    "BARGAIN": {
        "label": "Value vs draft cost",
        "one_line": "How many ranks of value you get over what the market charges.",
        "what_it_means": "His rank on the ADP board minus his rank on our value board, over the "
                         "whole board rather than the shrinking pool — so it is a **static** "
                         "property of the player, not something that moves as the draft empties. "
                         "PLAYER-VIEW's bar #5, specced since the card was written and never put "
                         "on a board until now.",
        "worked_example": "A player the market takes 50th and our board ranks 20th reads `+30` — "
                          "thirty ranks of value, about three rounds in a ten-team league.",
        "how_to_read_it": "Positive is good, always (PLAYER-VIEW's grammar rule: green = good for "
                          "the drafter). ⚠ It is the *value board's* opinion of him, so it "
                          "inherits everything the value board inherits — read it beside FLAGS, "
                          "and treat a large bargain on a row flagged `no distribution` or "
                          "`rookie` as a question rather than an answer.",
        "provenance": "session.board_view — adp rank − value_board.overall_rank, both over the "
                      "full board",
    },
    "RISKS": {
        "label": "Construction risks",
        "one_line": "What this player would do to the shape of YOUR roster, at pick time.",
        "what_it_means": "`⚑` his bye week already holds at least one of your starters · `⛓` he "
                         "plays for the same NFL team as one of your starters, which the "
                         "covariance prices as correlated risk · `🛡` he is the handcuff to a lead "
                         "RB you already hold · `⌀` his floor is censored, i.e. unresolvable "
                         "rather than zero · `◔` we have no prior on him at all. The first three "
                         "are the post-draft roster-construction readout, evaluated on your "
                         "roster **plus him** — the same function, moved to the moment it can "
                         "still be acted on.",
        "worked_example": "`⚑⛓` on a WR means taking him gives you a second starter on his bye "
                          "week and a second starter on his NFL team — two independent reasons a "
                          "roster that wins every player comparison can still be badly built.",
        "how_to_read_it": "None of these is a veto and none of them is priced against the others: "
                          "there is no evidence for a rate of exchange between 'two starters idle "
                          "in week 11' and 'two starters on one offense', so they are reported "
                          "separately and unweighted. ⚠ A blank `⚑` where a bye is simply unknown "
                          "is an unknown, never a clean bill — unknown byes stay unknown (14.F).",
        "provenance": "session.construction_flags → session.roster_construction_risk on "
                      "(roster + this player)",
    },
    # UI-1 step 5 — the attached column. It is documented here rather than in `app/` for the same
    # reason every other column is: one dictionary, every surface, and a column the CLI cannot
    # explain is a column with no behaviour behind it.
    "P(THERE)": {
        "label": "Probability he is still there at your next pick",
        "one_line": "How likely this player survives the picks between now and your next turn.",
        "what_it_means": "The 11.2 survival oracle — a fitted, Brier-validated behavioural "
                         "opponent model — simulated forward over exactly the opponents who pick "
                         "before you do, not an ADP rule of thumb. The window comes from the "
                         "snake itself (`session.next_pick_info`), so it shrinks as your turn "
                         "approaches and is 0 when you have no further pick.",
        "worked_example": "A 0.62 on a player 8 picks before your next turn means he survives "
                          "that gap in about 5 of 8 simulated rooms — so taking someone else "
                          "now and him later works more often than not, but not reliably.",
        "how_to_read_it": "Read it against the cliff, not on its own: a 0.9 on a player whose "
                          "position has four more of roughly his value is not a reason to reach, "
                          "and a 0.35 on the last man above a cliff is. The panel beneath the "
                          "board shows the same number with its **un-drifted baseline** beside "
                          "it, because the narrative-drift adjustment is not backtestable.",
        "provenance": "session.reach_risk_view → draft.drift.availability_readout (Phase 11.2)",
    },
}


def stat_entry(column: str) -> dict[str, str]:
    """One :data:`STAT_DICT` entry, or a :class:`LookupError` naming the column."""
    try:
        return STAT_DICT[str(column).upper()]
    except KeyError:
        raise LookupError(f"no stat-dictionary entry for {column!r}") from None


def stat_help(column: str) -> str:
    """The tooltip string a table column shows — one line, then how to read it."""
    e = STAT_DICT.get(str(column).upper())
    if not e:
        return ""
    return f"**{e['label']}** — {e['one_line']}\n\n{e['how_to_read_it']}"


def assert_stat_dict_covers_board() -> None:
    """Every rendered board column has a dictionary entry. A new column without documentation is
    a test failure, which is the only way a dictionary stays complete (14.O's done-bar).

    ★ **K2 widened this from the advanced view to every view.** 14.G added a third projection, and
    a column documented only in the mode nobody opens is the defect 14.O exists to prevent — the
    dictionary is complete when the *screens* are covered, not when one tuple is.
    """
    # ⚠ :data:`REACH_COL` is in here even though it is *attached* rather than projected. It renders
    # on the slim board and in the CLI's, so a reader meets it exactly the way they meet `PROJ`;
    # "documented unless it is bolted on" would be a rule about our plumbing, not about them.
    rendered = ({lbl for _, lbl in BOARD_VIEW_COLS} | set(RANGE_VIEW_COLS) | set(SLIM_VIEW_COLS)
                | set(VALUE_VIEW_COLS) | set(RISK_VIEW_COLS) | {REACH_COL})
    missing = sorted(c for c in rendered if c not in STAT_DICT)
    if missing:
        raise AssertionError(f"rendered board columns with no STAT_DICT entry: {missing}")


def project_view(view: pd.DataFrame, advanced: bool = False,
                 mode: str | None = None) -> pd.DataFrame:
    """The rendered column subset of a :func:`board_view` frame — slim, ranges or advanced.

    Takes the *frame*, not the state, precisely so a caller cannot accidentally re-query for one of
    the views: all three are this function applied to one object, so "the board modes show the same
    rows in the same order" is true by construction rather than by test (K1.5 bar B2, K2 bar B4).

    ``advanced=`` is K1.5's two-state control and still means what it meant; ``mode=`` supersedes it
    when given. The older flag is kept rather than migrated because ``steps/session_k1_5_app.py``
    differences against it, and a committed bar sheet that has to be edited to keep passing is not
    a bar sheet.
    """
    mode = str(mode) if mode else ("advanced" if advanced else "slim")
    if mode not in VIEW_MODES:
        raise ValueError(f"project_view takes mode in {VIEW_MODES}, got {mode!r}")
    cols = {
        "advanced": [lbl for _, lbl in BOARD_VIEW_COLS],
        "ranges": list(RANGE_VIEW_COLS),
        "value": list(VALUE_VIEW_COLS),
        "risk": list(RISK_VIEW_COLS),
        "slim": list(SLIM_VIEW_COLS),
    }[mode]
    return view[[c for c in cols if c in view.columns]]


def attach_reach(view: pd.DataFrame, reach: pd.DataFrame | None) -> pd.DataFrame:
    """Place :func:`reach_risk_view`'s ``p_available`` onto a rendered board as :data:`REACH_COL`.

    ★ **A placement, not a derivation** — and the distinction is the whole reason this lives here
    rather than in ``app/``. Nothing is computed: the probability was produced by the validated
    11.2 oracle in :func:`reach_risk_view`, and this aligns it to the board's own index. Doing the
    same join inside a renderer would give the app a number the CLI could not print, which is the
    T18 / F.5 / T27 family this repo has already paid for three times.

    Rows the reach frame does not cover (it reads the top ``n`` of the pool, the board may show
    more) come back **NaN and stay NaN**. That is T22's rule again: a player nobody simulated is
    not a player with a 0 % chance of surviving.
    """
    out = view.copy()
    if reach is None or len(reach) == 0 or "board_index" not in getattr(reach, "columns", []):
        out[REACH_COL] = np.nan
        return out
    p = pd.Series(pd.to_numeric(reach["p_available"], errors="coerce").to_numpy(float),
                  index=pd.Index(reach["board_index"].astype(int)))
    out[REACH_COL] = p.reindex(out.index).to_numpy(float)
    return out


def team_for_pick(st: DraftState, overall_pick: int) -> int | None:
    """Which seat is on the clock at ``overall_pick`` — the snake, for a pick that is not *now*.

    :meth:`DraftState.team_on_clock` answers the same question for the *current* pick and is the
    only place the geometry lived; a strip that shows who is **on deck** needs it one pick ahead.

    ⚠ **This is a second copy of a formula, and it is allowed only because it is checked.** The
    K1.5 seat-map defect was positional ``team → seat`` arithmetic written out four times and
    correct in three of them, and the fix that stuck was not "write it once" but "write it once and
    *assert exhaustively* that the deleted copies agreed with it". So this function is differenced
    against ``team_on_clock`` over **every pick of a full draft** by both a unit test and UI-1's bar
    B4. Copy it a third time and that guarantee stops meaning anything.
    """
    n, last = int(st.n_teams), int(st.n_teams) * int(st.rounds)
    p = int(overall_pick)
    if p < 1 or p > last:
        return None
    rnd0, idx = (p - 1) // n, (p - 1) % n
    return idx if rnd0 % 2 == 0 else n - 1 - idx


def next_pick_info(st: DraftState, team: int | None = None) -> dict:
    """``{next_pick, picks_away, on_the_clock}`` for one seat — **the one snake arithmetic.**

    ★ Both surfaces that need it read this: the draft room's seat strip (*"your next pick #37, 12
    away"*) and :func:`reach_risk_view`'s simulation window. Before UI-1 the window was derived in
    ``reach_risk_view`` and the strip did not exist; adding a second copy for the strip is exactly
    how the K1.5 seat-map defect happened, where positional ``team → seat`` arithmetic was written
    out four times and was correct in three of them.

    ⚠ ``optimizer._next_own_pick`` answers *which* pick is next; a reader needs *how many
    opponents pick first*, and the two differ by whether the seat is on the clock right now. That
    subtraction is the thing being centralised — it is one line and it is one line people get
    wrong.
    """
    from fantasy_quant.draft.optimizer import _next_own_pick

    seat = st.your_team if team is None else int(team)
    last = st.n_teams * st.rounds
    nxt = _next_own_pick(st.overall_pick, seat, st.n_teams, last)
    mine = st.team_on_clock() == seat
    away = 0 if nxt is None else max(
        0, int(nxt) - int(st.overall_pick) - (1 if mine else 0))
    return {"next_pick": (None if nxt is None else int(nxt)), "picks_away": int(away),
            "on_the_clock": bool(mine)}


# ------------------------------------------------------------------------------------------------
# the board a human reads and the value every seat optimizes — built together, once
# ------------------------------------------------------------------------------------------------
def build_board(con, season: int = 2026, teams: int = 10, config: DraftConfig | None = None,
                *, cache_dir=None) -> dict:
    """``{board, value_index, risk, source, n_base_value, lam}`` from **one** pass over the store.

    ★ **T27 — the board and the value index must be built together or not at all.** This used to
    return the board alone: ``proj_points`` rode in on a hand-rolled re-attach, ``base_value`` was
    never attached, and with no ``risk`` model the room's ``value_hawk`` seat silently fell back to
    the behavioral softmax — so the *interactive* mock ran a different room from every batch
    measurement in the repo. All three were one defect, and the fix is structural: one call returns
    the display frame and the decision frame, so they cannot describe different seasons.

    Takes an open ``con`` rather than opening one, so a UI can hold the connection in a resource
    cache and a step can pass its read-only handle. Raises :class:`LookupError` for an empty board —
    a caller decides whether that is a crash or a message.
    """
    config = config or DraftConfig()
    board, src = mock.room_board(con, int(season), teams=int(teams), cache_dir=cache_dir)
    if board.empty:
        raise LookupError(f"no {season} board at teams={teams}")
    vi = optimizer.assemble_value(con, int(season), config)
    board = optimizer.attach_value(board, vi)
    risk = optimizer.build_risk_model(board, vi, optimizer.assemble_correlation(con, int(season)),
                                      lam=config.risk_lambda)
    return {"board": board, "value_index": vi, "risk": risk, "source": str(src),
            "n_base_value": int(board["base_value"].notna().sum()),
            "lam": float(config.risk_lambda)}


# ------------------------------------------------------------------------------------------------
# the room: which seat is whom
# ------------------------------------------------------------------------------------------------
#: The shipped ten-seat room with one ``balanced`` removed — the nine opponents a single human
#: faces. ``balanced`` is the seat given up because it is the modal fitted manager; dropping a
#: *character* seat instead would quietly change the composition 16.14R step 7 validated.
REALISTIC_NINE: tuple[str, ...] = tuple(
    n for i, n in enumerate(REALISTIC_ROOM)
    if not (n == "balanced" and i == REALISTIC_ROOM.index("balanced")))


def realistic_mix(n_humans: int, n_teams: int = 10) -> tuple[str, ...]:
    """The shipped room with ``n_humans`` seats taken out of it — one ``balanced`` per human seat.

    Refuses rather than silently deleting a character seat once the ``balanced`` seats run out, for
    the reason above: the composition is a validated object, not a convenience.
    """
    names = list(REALISTIC_ROOM)
    if n_teams != len(REALISTIC_ROOM):
        raise ValueError(f"the shipped room is {len(REALISTIC_ROOM)} seats; pass an explicit room "
                         f"for a {n_teams}-team draft")
    if n_humans >= n_teams:                   # k = n: you drive the whole table, there is no room
        return ()
    for _ in range(n_humans):
        if "balanced" not in names:
            raise ValueError(
                f"the shipped room has only {REALISTIC_ROOM.count('balanced')} `balanced` seats to "
                f"give up; for {n_humans} human seats pass an explicit room of "
                f"{n_teams - n_humans} names")
        names.remove("balanced")
    return tuple(names)


def room_mix(arg: str | None, n_humans: int = 1, n_teams: int = 10) -> tuple[str, ...]:
    """A room spec -> the modelled-seat mix. Default is the **shipped** room, not the pre-16.14R
    one; it must be exactly ``n_teams - n_humans`` long, which :meth:`SeatMap.of` re-checks."""
    if arg in (None, "", "realistic"):
        return realistic_mix(n_humans, n_teams)
    if arg == "default":
        return tuple(DEFAULT_ROOM)
    return tuple(x.strip() for x in str(arg).split(","))


def room_from(meta: dict):
    """The draft's :class:`~fantasy_quant.draft.personalities.Personality` objects, from ``meta``.

    ``meta`` stores personality *names*, never objects, so a state file stays readable across a code
    change to :class:`Personality`. ``fav`` is re-applied to ``homer`` here for the same reason.
    """
    lib = personalities()
    return tuple(replace(lib[n], fav_teams=tuple(meta.get("fav", ())))
                 if (meta.get("fav") and n == "homer") else lib[n]
                 for n in meta["room"])


def seat_map_from(meta: dict) -> SeatMap:
    """Rebuild the draft's :class:`SeatMap` — 16.17's single ``team -> seat`` mapping.

    ``meta["human_teams"]`` is 16.17's; a draft started before it falls back to ``{your_team}``,
    which is what that draft was.
    """
    humans = meta.get("human_teams", [meta["your_team"]])
    return SeatMap.of(meta["teams"], human_teams=humans, room=room_from(meta))


def seat_label(team: int, sm: SeatMap) -> str:
    """``YOU (T3)`` for a human seat in a multi-seat draft, ``YOU`` when you drive only one."""
    if sm.seats[team] != HUMAN:
        return sm.seats[team].name
    return "YOU" if len(sm.human_teams) == 1 else f"YOU (T{team + 1})"


def seat_labels(sm: SeatMap, n_teams: int) -> list[str]:
    """One label per team — what a room readout and the drift panel both index by."""
    return [seat_label(t, sm) for t in range(n_teams)]


def auto_teams(meta: dict) -> frozenset[int]:
    """Human seats handed to the ADP autopicker — still *yours*, just not typed by hand."""
    return frozenset(int(t) for t in meta.get("auto", ()))


def room_pick_fn(meta: dict, risk=None):
    """The room's ``(state, team) -> board_index`` function for this draft.

    Built once and passed around because :func:`~fantasy_quant.draft.mock.load_opponent_model`
    re-reads the fitted-β artifact from disk on every call, and the pick clock (14.M) would
    otherwise do that once per tick.
    """
    return seat_map_from(meta).pick_fn(mock.load_opponent_model(), risk=risk)


def advance_one(st: DraftState, meta: dict, risk=None, opp=None) -> dict | None:
    """Make **exactly one** modelled (or autopicked) pick; ``None`` if it is your turn or the
    draft is over.

    ★ **This is the clock's step, and :func:`advance` is the loop over it** (14.M). Written this
    way round rather than as a second, clock-shaped copy of the same loop: bar B3 says a clocked
    draft must produce the identical ``state.log`` to an un-clocked run of the same seed, and two
    loops that agree today are two loops that can disagree tomorrow — the T18/F.5/T27 rule, one
    more altitude down. Because both paths consume ``DraftState.rng`` through the same call in the
    same order, the clock changes *when* picks happen and cannot change *which*.
    """
    if st.is_done() or not st.available:
        return None
    team = st.team_on_clock()
    if team in st.human_teams and team not in auto_teams(meta):
        return None
    opp = opp if opp is not None else room_pick_fn(meta, risk)
    idx = pick_by_adp(st, team, noise=0.0) if team in auto_teams(meta) else int(opp(st, team))
    _apply_pick(st, team, idx)
    return st.log[-1]


def advance(st: DraftState, meta: dict, risk=None) -> list[dict]:
    """Run modelled (and autopicked) picks until a seat **you** drive is on the clock.

    ``risk`` is what routes the room's ``value_hawk`` seat to the Phase-9 greedy instead of the
    behavioral softmax (T27); omitting it raises rather than silently seating a second ``balanced``.

    ★ **16.17 — the stop condition is membership, not equality.** It was ``team == st.your_team``,
    which is why a second human seat would have been drafted *for* you by the room.
    """
    opp = room_pick_fn(meta, risk)
    made: list[dict] = []
    while (entry := advance_one(st, meta, risk, opp)) is not None:
        made.append(entry)
    return made


def resolve_pick(st: DraftState, team: int, query: str) -> int | list[dict]:
    """A typed query -> a board index, or the ambiguous matches for the caller to disambiguate.

    Returns an ``int`` when the query resolves, or a list of ``{index, player_name, pos, adp}``
    when it matches several rows (empty list = no match). Shared so the CLI's "be more specific"
    and the app's picker offer the *same* candidate set from the same pool.
    """
    pool = st.draftable_pool(team)
    q = str(query).strip()
    if q.isdigit() and int(q) in pool.index:
        return int(q)
    hit = pool[pool["player_name"].str.lower().str.contains(q.lower(), regex=False)]
    if len(hit) == 1:
        return int(hit.index[0])
    return [{"index": int(i), "player_name": str(r["player_name"]), "pos": str(r["pos"]),
             "adp": float(r["adp"])} for i, r in hit.head(25).iterrows()]


# ------------------------------------------------------------------------------------------------
# the derived frames — what a renderer renders
# ------------------------------------------------------------------------------------------------
def cliff_series(st: DraftState, team: int | None = None, *, risk=None) -> pd.Series:
    """The 9.1 positional cliff for every player in one seat's pool — ``board index -> points``.

    ★ **Read from the decision path, not re-derived for display (14.E).** The greedy computes this
    inside :meth:`~fantasy_quant.draft.optimizer.RiskModel.effective_rank` as
    ``positional_cliff(pool.player_key, pool.pos, risk.bv)``; this calls the same function on the
    same pool with the same ``bv`` map, so the number on the board is the number the room is
    drafting on. Passing ``risk`` is what makes that literally true — without it the pool's own
    ``base_value`` column is used, which is where ``risk.bv`` came from, and the fallback exists
    only so a board with no risk model still renders.

    ⚠ **Computed over the seat's whole available pool**, before any position filter or row cap. A
    cliff is a statement about what is left at a position; measuring it inside a 25-row window
    would make "the tier runs out" mean "the tier runs out *on this screen*".
    """
    pool = st.draftable_pool(st.your_team if team is None else int(team))
    if pool.empty:
        return pd.Series(dtype=float)
    if risk is not None and getattr(risk, "bv", None) is not None:
        bv = risk.bv
    else:
        bv = dict(zip(pool["player_key"].astype(str),
                      pd.to_numeric(pool["base_value"], errors="coerce"), strict=False))
    vals = optimizer.positional_cliff(pool["player_key"], pool["pos"], bv)
    return pd.Series(vals, index=pool.index, name="cliff")


def cliff_table(st: DraftState, team: int | None = None, *, risk=None,
                scan: int = 12) -> pd.DataFrame:
    """Each position's **next** cliff — ``pos · n_before · drop · at_player · at_index``.

    The board strip 14.E asks for ("after these 3 RBs, a big VBD drop"), as data. Within each
    position, the cliff is scanned over the top ``scan`` available players and the largest one wins;
    ``n_before`` counts the players at or above it, which is the number a drafter actually acts on —
    *how many are left before the drop*.

    ``scan`` bounds the search rather than the cliff: a position's steepest fall is usually near the
    bottom of the board, where every remaining player is replacement level and the drop is an
    artifact of the tail. Looking only at the part of the board being drafted from is the difference
    between a live readout and a curiosity.
    """
    seat = st.your_team if team is None else int(team)
    pool = st.draftable_pool(seat)
    cliffs = cliff_series(st, seat, risk=risk)
    rows = []
    for p, grp in pool.groupby("pos", sort=False):
        head = grp.head(int(scan))
        c = cliffs.reindex(head.index)
        if c.notna().sum() == 0 or float(c.max()) <= 0.0:
            continue
        at = c.idxmax()
        rows.append({"pos": str(p),
                     "n_before": int(list(head.index).index(at)) + 1,
                     "drop": float(c.loc[at]),
                     "at_player": str(head.loc[at, "player_name"]),
                     "at_index": int(at),
                     "n_available": int(len(grp))})
    if not rows:
        return pd.DataFrame(columns=["pos", "n_before", "drop", "at_player", "at_index",
                                     "n_available"])
    return pd.DataFrame(rows).sort_values("drop", ascending=False).reset_index(drop=True)


def range_flags(pool: pd.DataFrame) -> pd.Series:
    """The PLAYER-VIEW confidence markers for a pool, as one comma-joined string per row (14.G).

    Three, in the order they matter: **no distribution** (no Phase-5 cloud — this player drafts on
    ADP fallback and no value objective can see him), **censored floor** (``q10`` sits on
    :data:`~fantasy_quant.draft.enrichment.CENSOR_AT`, so the downside is unresolvable rather than
    zero — T19), and **rookie** (the projection is 4.3's landing-spot ridge, not a measured
    history). A row with nothing to disclose gets an empty string, never a placeholder: a flag
    column that is never blank stops being read.
    """
    from fantasy_quant.draft.enrichment import CENSOR_AT

    idx = pool.index
    mean = pd.to_numeric(pool.get("mean", pd.Series(np.nan, index=idx)), errors="coerce")
    q10 = pd.to_numeric(pool.get("q10", pd.Series(np.nan, index=idx)), errors="coerce")
    rook = pd.to_numeric(pool.get("rookie", pd.Series(0.0, index=idx)), errors="coerce").fillna(0.0)
    out = []
    for i in idx:
        f = []
        if pd.isna(mean.loc[i]):
            f.append("no distribution")
        elif pd.notna(q10.loc[i]) and float(q10.loc[i]) <= CENSOR_AT:
            f.append("censored floor")
        if float(rook.loc[i]) > 0:
            f.append("rookie")
        out.append(", ".join(f))
    return pd.Series(out, index=idx, name="flags")


def coin_flags(q10, q90) -> np.ndarray:
    """``True`` where a row's 80 % interval overlaps the row **directly below it** (14.G).

    Parameter-free on purpose. "These two are a coin flip" is a claim about resolution, and the
    only resolution statement the frozen contract actually supports is whether the two intervals
    intersect — anything narrower (a gap threshold, a probability of one outscoring the other)
    would be a number this session invented and nothing validates.

    The last row compares with nothing and is ``False``; so is any row whose band is missing, since
    "we cannot tell" and "they are indistinguishable" are different answers.

    ⚠⚠ **That last sentence is right and the number this column is quoted by is not.** ``False``
    means *both* "distinguishable" and "no band to compare", and every published statement of this
    column — K2's bar B4, UI-PLAN §3.3, the ``COIN`` dictionary entry — reports the single figure
    *146 of 199 adjacent pairs overlap*, which a reader takes as "27 % are resolvable". On the live
    2026 board the decomposition is **147 pairs with both bands present, 146 of them overlapping,
    exactly 1 genuine break, and 52 pairs where a band is absent.** The honest statement is *of the
    adjacent pairs we can evaluate at all, 99.3 % overlap*. Found in UI-2 while trying to build
    tiers on top of this column, and it is why that feature is a null — see :func:`tier_series`.
    """
    lo = pd.to_numeric(pd.Series(q10), errors="coerce").to_numpy(float)
    hi = pd.to_numeric(pd.Series(q90), errors="coerce").to_numpy(float)
    out = np.zeros(len(lo), bool)
    if len(lo) < 2:
        return out
    a = (lo[:-1] <= hi[1:]) & (lo[1:] <= hi[:-1])
    out[:-1] = np.where(np.isfinite(lo[:-1]) & np.isfinite(hi[:-1])
                        & np.isfinite(lo[1:]) & np.isfinite(hi[1:]), a, False)
    return out


def _tiers_from_bands(q10, q90) -> np.ndarray:
    """1-indexed tier ids down **one ordered sequence**; ``NaN`` where the band is missing.

    ★ **This is :func:`coin_flags`, accumulated.** A tier ends where and only where two adjacent
    10–90 bands stop overlapping, so the rule that draws the tiers and the rule that already
    published *146 of 199 adjacent pairs overlap* are the same code rather than two descriptions of
    one idea. That is the whole differentiated claim: a tier here is a statement of statistical
    indistinguishability on **our own distributions**, which is Boris Chen's thesis executed on
    something better than expert ranks — and it is the one item in the UI plan no competitor can
    copy without building a distribution stack first.

    ⚠ **A missing band is skipped, not treated as a break.** A player with no Phase-5 cloud does not
    end a tier and does not start one; he simply has no tier, and the chain closes over him. Reading
    "we cannot tell" as "these are different" would manufacture a boundary out of missing data,
    which is T22's rule (*blank is not zero*) wearing a third face — and it is the same distinction
    :func:`coin_flags` makes when it returns ``False`` for an absent band rather than ``True``.
    """
    lo = pd.to_numeric(pd.Series(q10), errors="coerce").to_numpy(float)
    hi = pd.to_numeric(pd.Series(q90), errors="coerce").to_numpy(float)
    ids = np.full(len(lo), np.nan)
    ok = np.isfinite(lo) & np.isfinite(hi)
    if not ok.any():
        return ids
    overlap = coin_flags(lo[ok], hi[ok])            # overlap[i] = row i overlaps row i + 1
    breaks = (~overlap[:-1]).astype(int) if len(overlap) > 1 else np.zeros(0, int)
    ids[ok] = 1 + np.cumsum(np.concatenate([[0], breaks]))
    return ids


def _tiers_from_gaps(values) -> np.ndarray:
    """1-indexed tier ids down one ordered sequence, cut where the drop exceeds the median drop.

    `docs/BUILD_PLAN.md` §UI-2 step 1's option **(a)**, verbatim: *"a tier ends where ``base_value``
    falls by more than the pool's local median gap."* The threshold is the sequence's own median
    adjacent drop, so there is no constant to tune and none to go stale — a position whose board is
    flat gets a small threshold and one with real steps gets a large one, which is the behaviour the
    word "local" is doing in that sentence.

    ⚠ **This is the cut the plan called the cheap one, and it is the one that ships**, because the
    differentiated one does not cut this board at all — see :func:`tier_series`. Rows with no value
    are skipped rather than treated as breaks, exactly as a missing band is in
    :func:`_tiers_from_bands`.
    """
    v = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(float)
    ids = np.full(len(v), np.nan)
    ok = np.isfinite(v)
    if not ok.any():
        return ids
    x = v[ok]
    if len(x) < 2:
        ids[ok] = 1.0
        return ids
    drops = -np.diff(x)                      # board order is value-descending, so drops are ≥ 0
    thresh = float(np.median(drops))
    ids[ok] = 1 + np.cumsum(np.concatenate([[0], (drops > thresh).astype(int)]))
    return ids


def tier_series(st: DraftState, team: int | None = None, *, method: str = "gap",
                within_position: bool = True) -> pd.Series:
    """Within-position tier ids for one seat's pool — ``board index -> "RB2"`` (UI-2 step 1).

    ★★ **``method="overlap"`` is a NULL on this board, and that is this session's finding.**
    `docs/UI-PLAN.md` §S2 and `docs/BUILD_PLAN.md` §UI-2 both specify the overlap cut — *a tier ends
    where adjacent 10–90 bands stop overlapping* — and both call it the one differentiated item in
    the plan, *"the single item no competitor could copy without building our distribution stack
    first."* Measured on the live 2026 board it does not cut anything, at any scope:

    ====================================  ==============================================
    within RB / WR / QB / TE              **1 tier each** — 62, 83, 29, 24 players
    whole board order                     **2 tiers** over 244 available
    adjacent pairs with **both** bands    **147**; of those, **146 overlap**
    adjacent pairs that genuinely break   **1**
    ====================================  ==============================================

    Two mechanisms, and the second is worth more than the column:

    1. **Scale.** The median RB 80 % band is **228 points** wide against a median adjacent-player
       gap of **16.3 points** — **14×**. A pairwise-overlap rule cannot cut a sequence whose
       neighbours sit at a fourteenth of their own interval width. Overlap is near-universal *by
       construction*, not as a finding about football.
    2. **A category error in the premise.** UI-PLAN calls this *"precisely Boris Chen's thesis
       executed on our own distributions rather than on expert ranks."* It is not. Chen clusters
       **expert rank dispersion** — how much rankers *disagree about where a player belongs* — and
       we hold a **predictive interval for a season total**. Disagreement is narrow; outcome
       uncertainty is enormous. Two different quantities wearing one name, which is T24's lesson
       (*a relationship measured on one object is not a specification for another*) arriving on a
       visualisation instead of on a draft room.

    ⚠ **And the published figure hides its own denominator.** *146 of 199 adjacent pairs overlap*
    has been quoted all session — in K2's bar B4, in UI-PLAN §3.3, in this module's ``COIN``
    entry — and reads as *"73 % overlap, so 27 % are resolvable."* **52 of those 53 non-overlaps
    are pairs where a band is missing.** :func:`coin_flags` returns ``False`` both for *these two
    are distinguishable* and for *we cannot tell*, and its own docstring says those are different
    answers — but the headline sums them. The honest statement is **"of the adjacent pairs we can
    evaluate at all, 99.3 % overlap."*

    ★ **So ``method="gap"`` ships** — `BUILD_PLAN`'s own option (a), the cut it called the cheap
    one. The overlap path is kept runnable, not deleted, so the null stays checkable rather than
    becoming a sentence in a write-up.

    ⚠ **Computed over the seat's whole available pool, before any position filter or row cap** —
    14.E's rule for the cliff, verbatim. A tier is a fact about the pool, so cutting it inside a
    25-row window would make "the tier runs out" mean "the tier runs out *on this screen*". Bar B1
    asserts the ids do not move under truncation or filtering, which is what that scope buys.
    """
    seat = st.your_team if team is None else int(team)
    pool = st.draftable_pool(seat)
    out = pd.Series([pd.NA] * len(pool), index=pool.index, dtype=object)
    if pool.empty:
        return out
    if method not in ("gap", "overlap"):
        raise ValueError(f"tier_series takes method in ('gap', 'overlap'), got {method!r}")

    def ids_for(frame) -> np.ndarray:
        if method == "overlap":
            q10 = frame["q10"] if "q10" in frame.columns else pd.Series(np.nan, index=frame.index)
            q90 = frame["q90"] if "q90" in frame.columns else pd.Series(np.nan, index=frame.index)
            return _tiers_from_bands(q10, q90)
        bv = (frame["base_value"] if "base_value" in frame.columns
              else pd.Series(np.nan, index=frame.index))
        return _tiers_from_gaps(bv)

    if within_position:
        for p, grp in pool.groupby("pos", sort=False):
            out.loc[grp.index] = [f"{p}{int(k)}" if np.isfinite(k) else pd.NA for k in ids_for(grp)]
        return out
    out.loc[pool.index] = [f"T{int(k)}" if np.isfinite(k) else pd.NA for k in ids_for(pool)]
    return out


def tier_number(label: object) -> int | None:
    """``"RB2"`` -> ``2``; anything with no tier -> ``None``. The renderer's shading reads this."""
    s = str(label)
    digits = s[len(s.rstrip("0123456789")):]
    return int(digits) if digits else None


def _shares_row(frame: pd.DataFrame, key: str, value, *, starts: bool = True,
                starters_col: bool = False) -> bool:
    """Does ``value``'s row in a :func:`roster_construction_risk` sub-frame hold company?

    The one predicate behind ``⚑`` and ``⛓``: find the candidate's own row in the hypothetical
    readout and ask whether it counts **more than him**. Returns ``False`` for a value the readout
    has no row for, which is 14.F's rule — *an unknown bye stays unknown*, and silence is not a
    clean bill of health.
    """
    if not starts or value is None or (not isinstance(value, str) and pd.isna(value)):
        return False
    if frame is None or len(frame) == 0 or key not in frame.columns:
        return False
    col = frame[key]
    hit = frame[col.astype(str) == str(int(value) if not isinstance(value, str) else value)]
    if hit.empty:
        return False
    if int(hit.iloc[0]["n"]) < 2:
        return False
    return bool(not starters_col or int(hit.iloc[0].get("n_starters", 0)) >= 1)


def construction_flags(st: DraftState, team: int, index=None, *, vi: pd.DataFrame | None = None,
                       byes: pd.Series | None = None, elevation: float | None = None,
                       flags: pd.Series | None = None) -> pd.Series:
    """The A5 glyph string per candidate — *what would this player do to your roster* (UI-2 step 3).

    ★ **The live glyph IS the post-draft readout, evaluated one pick early.**
    :func:`roster_construction_risk` already priced bye clustering, NFL-team concentration and
    handcuff gaps, and rendered them only **after** the draft, when none of it can be acted on. Each
    of the three construction glyphs here is read off **that same function, evaluated on your roster
    plus this candidate** — nothing is recomputed and no second rule is written:

    ==========  ==========================================================================
    ``⚑``       he starts, and **his** bye-week row in the hypothetical holds ≥ 2 starters
    ``⛓``       **his** NFL-team row holds ≥ 2 of your players, ≥ 1 of them a starter
    ``🛡``       ``n_handcuff_gaps`` goes **down** — he closes insurance you do not own
    ==========  ==========================================================================

    ⚠ **Each reads *his own row* in the hypothetical readout, not a movement in its maximum.** The
    first build tested ``max_bye_starters`` going up, which is a different and much narrower claim:
    it fires only when the candidate joins the *already-largest* cluster, so a player who would put
    a second starter on a clean bye week showed nothing. Measured on the live board, ``⚑`` fired
    **zero** times in 40 rows — and the bar's control caught it, which is what the control is for.
    The documented meaning (*"his bye week already holds one of your starters"*) is also the
    decision-relevant one, so the code moved to the documentation rather than the other way round.

    Writing a cheaper look-alike rule here (compare his bye against a list of your starters' byes,
    say) is the T18 / F.5 / T27 family: two descriptions of one quantity, correct on the day and
    divergent by the second edit. The two that are *not* roster-dependent — ``⌀`` and ``◔`` — are
    likewise read straight off :func:`range_flags` rather than re-testing ``q10`` here, so ``RISKS``
    is a strict glyph encoding of facts that already have exactly one home.

    ⚠ **Scoped to the rows handed in, and that is not the cliff/tier error.** A tier is a fact about
    the *pool*, so scoping it to the screen would change its meaning; a construction flag is a fact
    about the *pair* (your roster, this player), so evaluating it for the rows on screen is the
    whole of it. What it costs is one lineup solve per row, which is why the scope matters at all.

    ⚠ **An unknown bye stays unknown** (14.F). ``byes=None`` — or a player the bye table does not
    cover — yields no ``⚑``, and that is *silence*, never a clean bill of health.
    """
    seat = int(team)
    idx = pd.Index(st.draftable_pool(seat).index if index is None else index)
    out = pd.Series([""] * len(idx), index=idx, dtype=object)
    if len(idx) == 0:
        return out
    board, roster, g = st.board, st.roster(seat), CONSTRUCTION_GLYPHS
    flags = range_flags(board.loc[[i for i in idx if i in board.index]]) if flags is None else flags

    base = roster_construction_risk(st, seat, vi=vi, byes=byes, elevation=elevation)
    can_shape = not roster.empty            # nothing to cluster with, nothing to concentrate on

    for i in idx:
        if i not in board.index:
            continue
        row, marks = board.loc[i], []
        if can_shape:
            hypo = roster_construction_risk(
                st, seat, vi=vi, byes=byes, elevation=elevation,
                roster=pd.concat([roster, board.loc[[i]]], ignore_index=True))
            if _shares_row(hypo["byes"], "week",
                           (byes.get(str(row.get("player_key"))) if byes is not None else None),
                           starts=str(row.get("player_name")) in set(hypo["starters"])):
                marks.append(g["bye"])
            if _shares_row(hypo["concentration"], "nfl_team", row.get("team"), starters_col=True):
                marks.append(g["stack"])
            if hypo["n_handcuff_gaps"] < base["n_handcuff_gaps"]:
                marks.append(g["handcuff"])
        f = str(flags.get(i, ""))
        if "no distribution" in f:
            marks.append(g["thin"])
        elif "censored floor" in f:
            marks.append(g["censored"])
        out.loc[i] = "".join(marks)
    return out


def board_view(st: DraftState, team: int | None = None, *, pos: str | None = None,
               n: int | None = None, risk=None, vi: pd.DataFrame | None = None,
               byes: pd.Series | None = None, elevation: float | None = None) -> pd.DataFrame:
    """The best-available board for one seat: every rendered column, index = the pick handle.

    The index is preserved deliberately — it is the ``#`` a CLI user types and the row key an app
    selects on, and it is the board index :func:`~fantasy_quant.draft.simulator._apply_pick` wants.
    A missing column is created as all-NaN rather than dropped, so the frame's shape does not depend
    on how richly a particular board happened to enrich.

    ★ **One frame, three projections** (:func:`project_view`). The frame carries the union of what
    the slim, ranges and advanced views show; the mode chooses columns and never re-queries. K2
    added ``CLIFF`` (14.E) and the ``Q10/MED/Q90/COIN/FLAGS`` block (14.G) to it rather than adding
    a second query for each, because two queries are two chances to disagree about who is available.

    ⚠ **``COIN`` is a property of the order on screen, so it is computed after the filter.** Filter
    to RB and it tells you which RBs are indistinguishable *from each other*, which is the question
    a drafter filtering to RB is asking.
    """
    seat = st.your_team if team is None else int(team)
    cliffs = cliff_series(st, seat, risk=risk)
    pool = st.draftable_pool(seat)
    if pos:
        wanted = [p.strip().upper() for p in str(pos).split(",") if p.strip()]
        pool = pool[pool["pos"].isin(wanted)]
    if n is not None:
        pool = pool.head(int(n))
    out = pd.DataFrame(index=pool.index)
    for col, label in BOARD_VIEW_COLS:
        if col == "cliff":
            out[label] = cliffs.reindex(pool.index)
        else:
            out[label] = pool[col] if col in pool.columns else np.nan
    for col, label in _RANGE_EXTRA_COLS:
        out[label] = pool[col] if col in pool.columns else np.nan
    out["COIN"] = coin_flags(out["Q10"], out["Q90"])
    out["FLAGS"] = range_flags(pool)
    # ---- UI-2's four ---------------------------------------------------------------------------
    # ⚠ appended **after** the fifteen, and none of them read by the existing three projections, so
    # `project_view(advanced=True)` returns exactly what it returned before this session. That is
    # not tidiness: two committed bar sheets difference against that frame column-for-column.
    # `Δ` is the engine's own pick counter, subtracted — never a second counter kept in a renderer.
    out["Δ"] = pd.to_numeric(out["ADP"], errors="coerce") - float(st.overall_pick)
    out["BARGAIN"] = _bargain(st).reindex(pool.index)
    out["RISKS"] = construction_flags(st, seat, pool.index, vi=vi, byes=byes, elevation=elevation,
                                      flags=out["FLAGS"])
    return out


def _bargain(st: DraftState) -> pd.Series:
    """``adp rank − overall_rank`` over the **whole board** — PLAYER-VIEW bar #5, as a column.

    ★ **Static by construction, and that is the claim.** Both ranks are taken over every boarded
    player rather than over the shrinking available pool, so a player's bargain does not improve
    merely because better players were drafted. PLAYER-VIEW calls bar #5 *"a static value gap"*; a
    pool-relative version would be a different quantity wearing its name.

    ⚠ **The sign is the opposite of the expression `docs/BUILD_PLAN.md` writes**, and this is the
    one place UI-2 deviates from its own pre-registration. The plan says
    ``overall_rank − adp_rank``;
    under that sign a player the market takes 50th and our board ranks 20th scores **−30**, i.e. the
    bargain column is most negative for the best bargains. That contradicts PLAYER-VIEW §5's
    governing rule — *green = good for the drafter, always* — and its own worked example, *"+1.5
    rounds of value"*. The plan never states a polarity in words, only the expression, so this ships
    the polarity the words require and records the discrepancy rather than quietly picking one.
    """
    board = st.board
    if "overall_rank" not in board.columns:
        return pd.Series(np.nan, index=board.index, dtype=float)
    adp_rank = pd.to_numeric(board["adp"], errors="coerce").rank(method="min")
    val_rank = pd.to_numeric(board["overall_rank"], errors="coerce")
    return (adp_rank - val_rank).astype(float)


def roster_view(st: DraftState, team: int) -> pd.DataFrame:
    """One seat's roster in lineup order, with ``proj_points`` — the frame both surfaces total."""
    r = st.roster(int(team))
    if r.empty:
        return pd.DataFrame(columns=["pos", "player_name", "adp", "proj_points"])
    order = {"QB": 0, "RB": 1, "WR": 2, "TE": 3, "K": 4, "DST": 5}
    r = r.assign(_o=r["pos"].map(order)).sort_values(["_o", "adp"])
    out = r[["pos", "player_name", "adp"]].copy()
    out["proj_points"] = (pd.to_numeric(r["proj_points"], errors="coerce")
                          if "proj_points" in r.columns else np.nan)
    return out.reset_index(drop=True)


def roster_total(roster: pd.DataFrame) -> float:
    """The consensus-projection total of a :func:`roster_view` frame (NaN counts as 0, as shown)."""
    if roster.empty or "proj_points" not in roster.columns:
        return 0.0
    return float(pd.to_numeric(roster["proj_points"], errors="coerce").fillna(0.0).sum())


def _slot_scores(roster: pd.DataFrame, vi: pd.DataFrame | None) -> np.ndarray:
    """The per-player number the slot grid fills on — ``base_value``, exactly as
    :func:`~fantasy_quant.draft.optimizer.starter_value` reads it (unvalued rows count 0.0)."""
    if vi is not None and not vi.empty and "player_key" in vi.columns:
        from fantasy_quant.draft.optimizer import _bv_map
        return roster["player_key"].map(_bv_map(vi)).fillna(0.0).to_numpy(float)
    col = roster["base_value"] if "base_value" in roster.columns else pd.Series(
        np.nan, index=roster.index)
    return pd.to_numeric(col, errors="coerce").fillna(0.0).to_numpy(float)


def slot_plan(st: DraftState) -> list[str]:
    """The league's starting-slot labels in fill order — ``QB · RB1 · … · FLEX · K · DST``."""
    from fantasy_quant.inseason.lineup import _slot_plan

    return [label for label, _ in _slot_plan(st.slots)]


def lineup_choice(st: DraftState, roster: pd.DataFrame,
                  vi: pd.DataFrame | None = None) -> tuple[dict, np.ndarray]:
    """``(slot label -> roster row position, the base_value vector)`` from the **frozen** solver.

    ★ **The single fill-order read, shared by every K1.5/K2 surface that needs one** — the 14.L slot
    grid, the roster rail, and 14.F's bye/concentration analysis all call this rather than each
    asking :func:`~fantasy_quant.inseason.lineup.optimal_lineup` themselves. 17.1's rule is that
    :meth:`RosterSlots.flex_groups` is the *single* fill-order rule after three solvers had each
    re-derived it once; three display surfaces re-deriving it would be the same mistake at a lower
    altitude, and the display copy is the one nobody would think to test.

    A degenerate one-draw "week": ``optimal_lineup`` reduces to its greedy mean-max fill, which is
    the frozen ``flex_groups`` order. Nothing here chooses a lineup; it reads one.
    """
    from fantasy_quant.inseason.lineup import optimal_lineup

    scores = _slot_scores(roster, vi)
    choice = optimal_lineup(scores[:, None], roster["pos"].tolist(), st.slots)
    return dict(choice.slots), scores


def room_grid(st: DraftState, sm: SeatMap, *, by: str = "pick",
              vi: pd.DataFrame | None = None) -> pd.DataFrame:
    """Every drafter's team on one frame — teams across the top (14.L).

    ``by="pick"`` is the classic draft board: one row per round, one column per seat in table
    order, each cell the pick that seat made in that round. The **snake is visible in the cell
    handles** — round 1 runs ``1.01`` at T1 to ``1.10`` at T10 and round 2 runs ``2.01`` at T10
    back to ``2.10`` at T1, so a row read left to right shows the direction reverse without the
    columns having to move (moving them would make the same team appear in two places).

    ``by="slot"`` is the roster grid: one row per starting slot, then the bench. ★ **The slot
    assignment is the frozen solver's, not a fill order re-derived for display** —
    :func:`~fantasy_quant.inseason.lineup.optimal_lineup` on the same ``base_value`` vector
    :func:`~fantasy_quant.draft.optimizer.starter_value` scores, which reaches the fill order
    through :meth:`RosterSlots.flex_groups`. 17.1's rule is that ``flex_groups`` is the *single*
    fill-order rule, after three solvers had each re-derived it once; a fourth copy living in a
    display layer would be the same mistake wearing a different hat, and it would be the copy
    nobody thought to test. Bar B4 closes the loop by asserting the assigned starters' values sum
    to ``starter_value`` — one grid, checked against the headline number it illustrates.

    The **bench** rows are display arrangement rather than a rule: whoever the solver did not
    start, best value first. There is no "optimal bench".
    """
    labels = seat_labels(sm, st.n_teams)
    cols = [f"T{t + 1} · {labels[t]}" for t in range(st.n_teams)]
    if by == "pick":
        grid = pd.DataFrame("", index=[f"R{r}" for r in range(1, st.rounds + 1)], columns=cols)
        for p in st.log:
            grid.iat[int(p["round"]) - 1, int(p["team"])] = (
                f"{int(p['round'])}.{int(p['pick_in_round']):02d}  {p['player_name']} "
                f"({p['pos']})")
        return grid
    if by != "slot":
        raise ValueError(f"room_grid takes by='pick' or by='slot', got {by!r}")

    plan = slot_plan(st)
    rows = plan + [f"BN{i + 1}" for i in range(max(0, st.rounds - len(plan)))]
    grid = pd.DataFrame("", index=rows, columns=cols)
    for t in range(st.n_teams):
        roster = st.roster(t)
        if roster.empty:
            continue
        slots, scores = lineup_choice(st, roster, vi)
        started = set()
        for label, i in slots.items():
            if i is None or label not in grid.index:
                continue
            started.add(int(i))
            r = roster.iloc[int(i)]
            grid.at[label, cols[t]] = f"{r['player_name']} ({r['pos']})"
        bench = sorted((i for i in range(len(roster)) if i not in started),
                       key=lambda i: -scores[i])
        for k, i in enumerate(bench):
            if k < len(rows) - len(plan):
                r = roster.iloc[int(i)]
                grid.at[f"BN{k + 1}", cols[t]] = f"{r['player_name']} ({r['pos']})"
    return grid


# ------------------------------------------------------------------------------------------------
# 14.F — roster-construction risk: the three ways a good roster is badly built
# ------------------------------------------------------------------------------------------------
#: Cache for the pooled Phase-8.5 backfield elevation ratio, which is a property of the DEV panel
#: and not of any draft — recomputing it per page render would read nine seasons per rerun.
_ELEVATION: dict[str, float] = {}


def elevation_ratio(con) -> float:
    """The pooled DEV multiplier a backup's ppg gets when his starter is out (Phase 8.5).

    Read from the *same* call ``steps/phase8_covariance.py`` makes — ``elevation_stats`` over
    ``copula.handcuff_pairs`` on the DEV weekly panel — so the option premium the app quotes is the
    one the 8.5 done-bar asserted, not a constant retyped into a display layer.
    """
    if "ratio" not in _ELEVATION:
        from fantasy_quant.config import DEV_SEASONS
        from fantasy_quant.covariance import copula
        from fantasy_quant.covariance.estimate import weekly_offense_panel
        from fantasy_quant.valuation.handcuff import elevation_stats

        _ELEVATION["ratio"] = float(
            elevation_stats(copula.handcuff_pairs(weekly_offense_panel(con, DEV_SEASONS)))["ratio"])
    return _ELEVATION["ratio"]


def bye_weeks(con, season: int) -> pd.Series:
    """``player_key -> bye week`` for a season, from the FantasyPros ECR snapshots (0.11).

    ⚠ **The store has no schedule table, so this is the only bye source in the repo** and it is
    incomplete — roughly nine in ten 2026 board rows carry one. A player whose bye is unknown must
    stay unknown all the way to the screen: an ``fillna(0)`` here would put him in a "week 0" bucket
    that reads as *no bye*, which is the T22 defect (blank is not zero) in a new column.

    Keys the same way :func:`~fantasy_quant.draft.simulator.board_player_key` does — ``gsis_id``,
    so team defenses (which carry none) simply have no bye here rather than a wrong one.
    """
    df = con.execute(
        "SELECT gsis_id, MAX(bye) AS bye FROM ecr_snapshots "
        "WHERE season = ? AND bye IS NOT NULL AND gsis_id IS NOT NULL GROUP BY gsis_id",
        [int(season)]).df()
    if df.empty:
        return pd.Series(dtype=float)
    return pd.Series(pd.to_numeric(df["bye"], errors="coerce").to_numpy(float),
                     index=df["gsis_id"].astype(str), name="bye")


def roster_construction_risk(st: DraftState, team: int, *, vi: pd.DataFrame | None = None,
                             byes: pd.Series | None = None, elevation: float | None = None,
                             roster: pd.DataFrame | None = None) -> dict:
    """The three construction risks for one seat — bye clustering, concentration, handcuff gaps.

    A roster can win every player-level comparison and still be badly built, and all three of these
    are invisible in ``STARTABLE``/``CAPITAL`` because both are sums over players. They are reported
    **separately and unweighted**: there is no evidence for a rate of exchange between "four
    starters idle in week 11" and "three of your players share a bye", and inventing one would bury
    the only part of this readout a drafter can act on.

    Returns ``{team, starters, byes, max_bye_starters, unknown_byes, concentration,
    max_team_players, handcuffs, n_handcuff_gaps, elevation_ratio}``.

    ⚠ **Bye clustering is measured over your STARTERS, not your roster** — a bench player's bye
    costs nothing, and counting him would make a deep roster look fragile for being deep. Starters
    come from :func:`lineup_choice`, the frozen solver, so this readout and the 14.L grid can never
    disagree about who starts.

    ★ **``roster=`` is UI-2's whole step 3, and it adds no arithmetic.** Passing a roster evaluates
    this same readout on a *hypothetical* one — your fifteen plus a candidate — which is how
    :func:`construction_flags` puts the post-draft warning on the board at the moment it can still
    be acted on. The default path (``roster=None``) is byte-for-byte what it was, which is what
    keeps K2's 14.F bar and this session's B0 unmoved.
    """
    seat = int(team)
    roster = st.roster(seat) if roster is None else roster
    out: dict = {"team": seat, "starters": [], "byes": pd.DataFrame(columns=["week", "n", "who"]),
                 "max_bye_starters": 0, "unknown_byes": 0,
                 "concentration": pd.DataFrame(columns=["nfl_team", "n", "n_starters", "who"]),
                 "max_team_players": 0,
                 "handcuffs": pd.DataFrame(columns=["starter", "nfl_team", "backup", "held",
                                                    "option_premium"]),
                 "n_handcuff_gaps": 0, "elevation_ratio": elevation}
    if roster.empty:
        return out

    slots, _ = lineup_choice(st, roster, vi)
    starter_rows = sorted({int(i) for lbl, i in slots.items() if i is not None})
    starters = roster.iloc[starter_rows] if starter_rows else roster.iloc[[]]
    out["starters"] = [str(n) for n in starters["player_name"]]

    # --- bye clustering, over the starters ------------------------------------------------------
    if byes is not None and len(byes):
        wk = starters["player_key"].astype(str).map(byes)
        known = wk.notna()
        out["unknown_byes"] = int((~known).sum())
        if known.any():
            grp = (pd.DataFrame({"week": wk[known].astype(int),
                                 "who": starters.loc[known.to_numpy(), "player_name"].astype(str)})
                   .groupby("week"))
            out["byes"] = (pd.DataFrame({"n": grp.size(), "who": grp["who"].apply(", ".join)})
                           .reset_index().sort_values(["n", "week"], ascending=[False, True])
                           .reset_index(drop=True))
            out["max_bye_starters"] = int(out["byes"]["n"].max())

    # --- NFL-team concentration, over the whole roster ------------------------------------------
    if "team" in roster.columns:
        tm = roster["team"].astype("string")
        start_keys = set(starters["player_key"].astype(str))
        rows = []
        for t, grp in roster.assign(_t=tm).groupby("_t", dropna=True, sort=False):
            rows.append({"nfl_team": str(t), "n": int(len(grp)),
                         "n_starters": int(sum(str(k) in start_keys
                                               for k in grp["player_key"])),
                         "who": ", ".join(str(n) for n in grp["player_name"])})
        if rows:
            out["concentration"] = (pd.DataFrame(rows)
                                    .sort_values(["n", "nfl_team"], ascending=[False, True])
                                    .reset_index(drop=True))
            out["max_team_players"] = int(out["concentration"]["n"].max())

    # --- handcuff gaps, priced with the frozen 8.5 option -----------------------------------------
    out.update(_handcuff_gaps(st, roster, elevation))
    return out


def _handcuff_gaps(st: DraftState, roster: pd.DataFrame, elevation: float | None) -> dict:
    """Which of your lead RBs you do **not** hold the backup for, and what that option is worth.

    ★ **Restricted to RB, deliberately.** The 8.5 elevation ratio is estimated on backfields
    (``copula.handcuff_pairs``), so quoting an option premium for a WR2 would apply a measured
    number to a population it was not measured on — the T24 failure (*a relationship measured on
    one object is not a specification for another*) in its cheapest form. The other positions get
    no row rather than a made-up one.

    ⚠ **Only your seat's *lead* backs generate a row.** Board order within an NFL backfield is the
    consensus's own depth read, so the handcuff of the RB1 is the RB2 — and if you hold the RB2 you
    do not have a gap, you *are* the handcuff. The first run of this function reported "Tyjae
    Spears → backup Tony Pollard", which is the depth chart upside down: taking "the next RB on the
    same team" without first checking which of them is the starter prices insurance on the wrong
    life.
    """
    cols = ["starter", "nfl_team", "backup", "held", "option_premium"]
    if roster.empty or "team" not in roster.columns:
        return {"handcuffs": pd.DataFrame(columns=cols), "n_handcuff_gaps": 0}
    board = st.board
    held = set(str(k) for k in roster["player_key"])
    rows = []
    for _, r in roster[roster["pos"] == "RB"].iterrows():
        nfl = r.get("team")
        if not isinstance(nfl, str) or not nfl:
            continue
        mates = board[(board["team"] == nfl) & (board["pos"] == "RB")]
        if len(mates) < 2 or str(mates.iloc[0]["player_key"]) != str(r["player_key"]):
            continue                      # not this backfield's lead back — no insurance to price
        backup = mates.iloc[1]
        gp = pd.to_numeric(pd.Series([r.get("games_played_mean")]), errors="coerce").iloc[0]
        p_out = float(np.clip(1.0 - (gp / 17.0), 0.0, 1.0)) if pd.notna(gp) else np.nan
        b_mean = pd.to_numeric(pd.Series([backup.get("mean")]), errors="coerce").iloc[0]
        prem = np.nan
        if elevation is not None and pd.notna(p_out) and pd.notna(b_mean):
            from fantasy_quant.valuation.handcuff import handcuff_value
            prem = float(handcuff_value(p_out, float(b_mean) / 17.0,
                                        float(elevation)).option_premium)
        rows.append({"starter": str(r["player_name"]), "nfl_team": nfl,
                     "backup": str(backup["player_name"]),
                     "held": str(backup["player_key"]) in held,
                     "option_premium": prem})
    frame = pd.DataFrame(rows, columns=cols)
    if not frame.empty:
        frame = frame.sort_values(["held", "option_premium"], ascending=[True, False],
                                  na_position="last").reset_index(drop=True)
    return {"handcuffs": frame, "n_handcuff_gaps": int((~frame["held"]).sum()) if len(frame) else 0}


def explain_chain(board: pd.DataFrame, vi: pd.DataFrame, query: str,
                  lam: float) -> list[dict]:
    """``why "<player>"`` as data — one entry per matched player, each with its arithmetic chain.

    ★ **Every line is an identity, never a re-derivation.** ``lambda*Var`` is reported as
    ``mean - ce_value`` and the positional replacement as ``ce_value - ce_vbd``, so what is shown is
    what the frozen Phase-4/5 stack actually computed. A display layer that recomputes the chain can
    drift away from the stack it claims to explain, and then the audit trail is the thing being
    audited. That property is the whole command; it is why this returns the *differences* of stored
    quantities rather than applying λ to a variance itself.

    Each entry is ``{name, pos, adp, ok, rows: [{label, value, note}], reason}``. ``ok=False`` marks
    a player with no Phase-5 distribution — he drafts on ADP fallback and no seat's value objective
    can see him, which is a fact worth rendering rather than an empty panel.
    """
    q = str(query).strip().lower()
    hit = board[board["player_name"].str.lower().str.contains(q, regex=False)]
    if hit.empty:
        return []
    idx = vi.drop_duplicates("player_key").set_index(vi["player_key"].astype(str))
    out: list[dict] = []
    for _, r in hit.iterrows():
        entry = {"name": str(r["player_name"]), "pos": str(r["pos"]), "adp": float(r["adp"]),
                 "ok": False, "rows": [], "reason": ""}
        key = str(r["player_key"])
        v = idx.loc[key] if key in idx.index else None
        if v is None or pd.isna(v.get("mean")):
            entry["reason"] = ("no Phase-5 distribution — this player drafts on ADP fallback "
                               "(base_value is NaN, so no seat's value objective can see him).")
            out.append(entry)
            continue
        proj, mean = float(v["proj_points"]), float(v["mean"])
        ce, ce_vbd = float(v["ce_value"]), float(v["ce_vbd"])
        gp = r.get("games_played_mean", np.nan)
        lam_var, repl = mean - ce, ce - ce_vbd
        pos = str(r["pos"])
        avail = f"games_played_mean {gp:.1f} of 17" if pd.notna(gp) else "(no availability read)"
        haircut = f"haircut {1 - mean / proj:+.1%}" if proj else "(no consensus projection)"
        entry["ok"] = True
        entry["rows"] = [
            {"label": "consensus projection (PROJ)", "value": proj,
             "note": "full-PPR, re-scored by our RuleSet"},
            {"label": "x projected availability", "value": None, "note": avail},
            {"label": "= Phase-5 season mean (MEAN)", "value": mean, "note": haircut},
            {"label": "  sd", "value": float(v["sd"]), "note": ""},
            {"label": f"- lambda*Var   (lambda = {lam:.3g})", "value": -lam_var, "note": ""},
            {"label": "= certainty equivalent (ce_value)", "value": ce,
             "note": "the risk dial's output"},
            {"label": f"- replacement CE at {pos}", "value": -repl,
             "note": f"the {pos} a waiver claim gets you"},
            {"label": "= BASE_VALUE — what seats optimize", "value": ce_vbd, "note": ""},
            {"label": "(frozen Phase-4 VBD, for reference)", "value": float(v["vbd"]), "note": ""},
        ]
        out.append(entry)
    return out


def summary_table(st: DraftState, sm: SeatMap, vi: pd.DataFrame | None = None) -> pd.DataFrame:
    """Final rosters, ranked — ``team · who · human · proj · starters`` (+ the T28 pair).

    ★ **T28 — every team-level number appears twice, labelled.** ``startable`` is
    :func:`~fantasy_quant.draft.optimizer.starter_value` (the best legal starting lineup's
    ``base_value``); ``capital`` is ``team_value``, the slot-blind sum over all fifteen rows that
    prices a bench QB2 as though he starts. On the 2026 walkthrough those disagreed by −122 points
    on one QB2 line, which is how a team sits 9th of 10 on one and 3rd on the other. Neither is
    deleted and neither is silently renamed — ``team_value`` is what the frozen cost report
    differences, so it stays exactly what it was.

    ⚠ **No combined row for multiple human seats, by construction.** k human teams in one draft are
    ONE observation: your picks deplete each other's pools, so the seats' outcomes are mechanically
    anti-correlated. The frame carries a ``human`` flag and nowhere to put an average.
    """
    rows = []
    for t in range(st.n_teams):
        roster = st.roster(t)
        pp = pd.to_numeric(roster.get("proj_points"), errors="coerce").fillna(0.0)
        row = {"team": t + 1, "who": seat_label(t, sm), "human": t in sm.human_teams,
               "proj": float(pp.sum()), "starters": float(pp.nlargest(9).sum())}
        if vi is not None:
            row["startable"] = optimizer.starter_value(roster, vi, st.slots)
            row["capital"] = optimizer.team_value(roster, vi)
        rows.append(row)
    tab = pd.DataFrame(rows).sort_values("starters", ascending=False).reset_index(drop=True)
    tab.insert(0, "rank", np.arange(1, len(tab) + 1))
    return tab


def positional_strength(st: DraftState, sm: SeatMap,
                        vi: pd.DataFrame | None = None) -> pd.DataFrame:
    """Each team's **starting** value by position, against the room median — A6's chart, as data.

    ``team · pos · value · room_median · delta``, one row per (team, position). This is the piece
    deferred out of UI-1 by name: every other part of A6 was a rearrangement of frames that already
    existed, and this needed a genuinely new derivation, which is UI-2's character rather than a
    formatting session's.

    ★ **Starters only, through :func:`lineup_choice`.** A positional-strength readout summed over
    the whole roster would tell a drafter his RB room is strong because he carries five of them,
    which is the exact defect T28 named at the team level: ``capital`` is slot-blind and
    ``startable`` is not. The single starters read is 17.1's ``flex_groups`` rule one altitude down
    — a fourth display-layer fill order would be the copy nobody thinks to test.

    ⚠ **The median is over the room, so it moves with the room.** It is a *within-this-draft*
    comparison and carries no out-of-sample claim; the number it answers is "did I win this
    position in this league", not "is this a good RB corps".
    """
    order = [p for p in ("QB", "RB", "WR", "TE", "K", "DST")]
    rows = []
    for t in range(st.n_teams):
        roster = st.roster(t)
        slots, _ = lineup_choice(st, roster, vi)
        starter_rows = sorted({int(i) for _lbl, i in slots.items() if i is not None})
        starters = roster.iloc[starter_rows] if starter_rows else roster.iloc[[]]
        bv = pd.to_numeric(starters.get("base_value"), errors="coerce") if len(starters) \
            else pd.Series(dtype=float)
        by_pos = (pd.Series(bv.to_numpy(float), index=starters["pos"].astype(str).to_numpy())
                  .groupby(level=0).sum() if len(starters) else pd.Series(dtype=float))
        for p in order:
            rows.append({"team": t + 1, "who": seat_label(t, sm), "human": t in sm.human_teams,
                         "pos": p, "value": float(by_pos.get(p, 0.0))})
    tab = pd.DataFrame(rows)
    med = tab.groupby("pos")["value"].median()
    tab["room_median"] = tab["pos"].map(med).astype(float)
    tab["delta"] = tab["value"] - tab["room_median"]
    return tab


def odds_table(con, st: DraftState, meta: dict, sm: SeatMap, *,
               sims: int = 400, seed: int = 0) -> tuple[pd.DataFrame, list[str]]:
    """Playoff/title odds for the finished league — ``(table, provenance_lines)``.

    ★ **Led by the fair-share multiple (T29).** A bare "17.0 % to win the league" is the weakest
    number in the stack wearing the most authoritative costume: the lockbox certified the *ordering*
    (title Brier 0.088, reliability on-diagonal) but recorded playoff Brier 0.240 as marginal, over
    a sim with a documented −113 pts/team level bias. A ratio to the uniform is immune to that bias
    because it moves all ten teams together, so ``1.70x`` is a claim the evidence supports and
    ``17.0 %`` is not. Both are returned; a renderer must lead with the multiple.
    """
    from fantasy_quant.simulation.season import (
        LeagueFormat,
        assert_probability_sums,
        fair_share,
        league_probabilities,
        playoff_fair_share,
        provenance_lines,
    )
    from fantasy_quant.simulation.weekly import build_weekly_model

    fmt = meta.get("league_format") or LeagueFormat(n_teams=st.n_teams)
    ruleset = meta.get("ruleset") or DraftConfig().league.ruleset
    wm = build_weekly_model(con, int(meta.get("season", 2026)), ruleset, seed=seed)
    rosters = [st.roster(t) for t in range(st.n_teams)]
    pp, tp = league_probabilities(rosters, wm, fmt, st.slots, np.random.default_rng(seed),
                                  sims=int(sims))
    assert_probability_sums(pp, tp, fmt)                      # a structural identity, not a check
    pf, tf = playoff_fair_share(pp, fmt), fair_share(tp, fmt.n_teams)
    order = np.argsort(-tf)
    tab = pd.DataFrame({
        "team": [t + 1 for t in order],
        "who": [seat_label(int(t), sm) for t in order],
        "human": [int(t) in sm.human_teams for t in order],
        "playoff": [float(pp[t]) for t in order],
        "playoff_fair": [float(pf[t]) for t in order],
        "title": [float(tp[t]) for t in order],
        "title_fair": [float(tf[t]) for t in order],
    })
    return tab, list(provenance_lines(int(sims), fmt))


def drift_frames(st: DraftState, meta: dict, sm: SeatMap) -> dict:
    """This draft in the realized corpus's own units — ``{profile, elite, seats, n_humans}``.

    The panel is :func:`~fantasy_quant.draft.mock.sim_drift_panel`, the exact frame
    ``steps/t15_0_baseline.py`` measures, so a human draft and a batch measurement are computed by
    the same functions on the same board.

    ⚠ **Scope, which a renderer must state (16.17 honesty rule 2):** the committed T15 realism bars
    — profile distance, dispersion, chalk share, elite-fall landing — were measured on a **fully
    simulated** ten-seat room. These numbers describe *this* draft and are not a re-measurement of
    those bars; ``n_humans`` is returned so the caller can say so with the right number in it.
    """
    labels = seat_labels(sm, st.n_teams)
    panel = mock.sim_drift_panel(st, season=int(meta.get("season", 2026)), draft_id="interactive",
                                 board_teams=meta["teams"], seed=meta["seed"])
    panel["seat_personality"] = panel["draft_slot"].map(lambda s: labels[s - 1])
    return {"profile": mock.reach_profile(panel), "elite": mock.elite_fall_profile(panel),
            "seats": mock.seat_table(panel), "n_humans": len(sm.human_teams), "panel": panel}


def pick_drift_table(frames: dict, team: int | None = None) -> pd.DataFrame:
    """Every pick as a reach or a steal — ``pick · round · who · player · pos · adp · reach_picks``.

    ★ **Read off the drift panel, not recomputed as ``adp − overall_pick``.** The panel already
    centres each draft on its own median slope and expresses drift in 10-team ADP picks, which is
    the unit every T15/T18 bar is stated in. A page that subtracted two raw numbers instead would
    produce a *third* definition of "reach" in a repo that has already had two (T18's ``avg_reach``
    disagreed with itself by a sign), and it would disagree with the profile printed beside it.

    ``reach_picks`` keeps the panel's sign: **positive = the seat reached**, negative = the player
    fell to them. Sorted most-reached first, so the two ends of the frame are "biggest reach" and
    "best value".
    """
    panel = frames.get("panel")
    cols = ["pick_no", "round", "who", "player", "pos", "adp", "reach_picks"]
    if panel is None or panel.empty:
        return pd.DataFrame(columns=cols)
    p = panel if team is None else panel[panel["draft_slot"].astype(int) == int(team) + 1]
    if p.empty:
        return pd.DataFrame(columns=cols)
    out = pd.DataFrame({
        "pick_no": p["pick_no"].astype(int), "round": p["round"].astype(int),
        "who": p["seat_personality"].astype(str), "player": p["name"].astype(str),
        "pos": p["pos"].astype(str), "adp": pd.to_numeric(p["adp"], errors="coerce"),
        # `mock._picks` is private and called anyway: its docstring says it is "the only place
        # TEAMS_REF is applied", so multiplying by TEAMS_REF here would create the second place.
        "reach_picks": mock._picks(p["drift"]).astype(float),
    })
    return out.sort_values("reach_picks", ascending=False).reset_index(drop=True)


# ------------------------------------------------------------------------------------------------
# 14.I — the draft grade
# ------------------------------------------------------------------------------------------------
#: **The weights, and they are a presentation choice with nothing validating them.**
#:
#: ★ Every *input* below is read from frozen, separately-validated machinery; the act of combining
#: them into one number is not. No backtest in this repo scores a weighted blend of odds, starter
#: strength, draft-value capture and bye clustering against anything, so these four numbers are a
#: house style, chosen by the user (2026-07-31) to lead with the component the season sim actually
#: certified. They are declared here, printed beside every grade, and named in the tooltip for
#: exactly that reason: an invented constant that is visible is a design decision, and the same
#: constant buried inside a scoring function is a claim.
#:
#: The lockbox certified the *ordering* of title odds (Brier 0.088) — hence 50 on the component
#: with evidence behind it. ``construction`` is the smallest because it is the noisiest: it is one
#: count (see :func:`grade_components`), not a model output.
GRADE_WEIGHTS: dict[str, float] = {
    "odds": 50.0, "starters": 20.0, "value": 15.0, "construction": 15.0,
}

#: ``(floor, letter)`` from the top down, **anchored to this scale rather than to a school
#: gradebook**: :func:`apply_grade` scores each component min–max across the ten teams, so a
#: middling roster lands near **50 by construction** and the bands put ``C`` there.
#:
#: ★ This was a real defect caught by the first run rather than a taste question. On plain US bands
#: (90/80/70/60) the median team in a ten-team room graded **D+**, and six of ten graded D or F —
#: the app telling an average drafter he had drafted badly, because the letters assumed 50 % was a
#: fail when on a curve 50 is the middle. *A scale and its labels have to be anchored to the same
#: thing.* An ``F`` here means "last in this room", never "bad in the abstract".
GRADE_BANDS: tuple[tuple[float, str], ...] = (
    (92.0, "A+"), (85.0, "A"), (80.0, "A−"), (74.0, "B+"), (68.0, "B"), (62.0, "B−"),
    (56.0, "C+"), (50.0, "C"), (44.0, "C−"), (38.0, "D+"), (32.0, "D"), (26.0, "D−"),
)


def grade_letter(total: float) -> str:
    """The letter for a 0–100 score. Below the last band is an ``F``."""
    if not np.isfinite(total):
        return "—"
    for floor, letter in GRADE_BANDS:
        if float(total) >= floor:
            return letter
    return "F"


def grade_components(st: DraftState, meta: dict, sm: SeatMap, *, odds: pd.DataFrame,
                     vi: pd.DataFrame | None = None, byes: pd.Series | None = None,
                     elevation: float | None = None) -> pd.DataFrame:
    """The four **raw** component values for every team — measurement, before any curve.

    One row per seat: ``team · who · human`` plus

    * ``odds`` — the T29 title **fair-share multiple**, not the percentage. Immune to the sim's
      documented −113 pts/team level bias, which the percentage is not.
    * ``starters`` — ``STARTABLE`` from :func:`summary_table`, i.e. the best legal starting lineup's
      ``base_value`` (T28's startable half, never the slot-blind capital).
    * ``value`` — ``harvest_picks`` from the drift panel: picks of surplus against the corpus's own
      reach scale, positive when the seat let value come to it.
    * ``construction`` — **minus** the largest number of the seat's starters sharing one bye week,
      from :func:`roster_construction_risk`. Negated so that, like the other three, more is better.

    ⚠ **``construction`` is deliberately one count and not a blend of 14.F's three risks.** Team
    concentration and handcuff gaps are reported on the page and stay out of the arithmetic:
    combining three unvalidated risks into an unvalidated sub-score and feeding it to an unvalidated
    weighting would put two invented layers under one number. One count is legible and it is
    checkable against the bye table printed beside it.
    """
    summary = summary_table(st, sm, vi).set_index("team")
    seats = drift_frames(st, meta, sm)["seats"]
    harvest = {}
    if not seats.empty and "draft_slot" in seats.columns:
        harvest = {int(s): float(h) for s, h in zip(seats["draft_slot"],
                                                    seats.get("harvest_picks", np.nan),
                                                    strict=False)}
    tf = {int(t): float(v) for t, v in zip(odds["team"], odds["title_fair"], strict=False)}
    rows = []
    for t in range(st.n_teams):
        risk = roster_construction_risk(st, t, vi=vi, byes=byes, elevation=elevation)
        rows.append({
            "team": t + 1, "who": seat_label(t, sm), "human": t in sm.human_teams,
            "odds": tf.get(t + 1, np.nan),
            "starters": (float(summary.loc[t + 1, "startable"])
                         if "startable" in summary else np.nan),
            "value": harvest.get(t + 1, np.nan),
            "construction": -float(risk["max_bye_starters"]),
            "max_bye_starters": int(risk["max_bye_starters"]),
            "max_team_players": int(risk["max_team_players"]),
            "n_handcuff_gaps": int(risk["n_handcuff_gaps"]),
        })
    return pd.DataFrame(rows)


def apply_grade(components: pd.DataFrame) -> pd.DataFrame:
    """Score :func:`grade_components` on the room and add ``total`` + ``letter``.

    ★ **One scoring rule for all four components: min–max across the ten teams.** Chosen because it
    is the only convention that needs no per-component constant — a curve on the room, which is
    what "grade the roster **vs the room**" means. A component the room does not separate on (every
    team equal, or the column missing) scores **0.5 for everyone**, so a dimension carrying no
    information cannot decide a grade.

    ``total = Σ wᵢ·scoreᵢ`` with :data:`GRADE_WEIGHTS` summing to 100, and every ``points_*`` term
    is returned beside it — bar B5 is that the total reproduces from the printed parts, which is the
    only thing that keeps an invented weighting honest.
    """
    out = components.copy()
    total = np.zeros(len(out))
    for comp, w in GRADE_WEIGHTS.items():
        raw = pd.to_numeric(out.get(comp, pd.Series(np.nan, index=out.index)), errors="coerce")
        lo, hi = raw.min(), raw.max()
        if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
            score = pd.Series(0.5, index=out.index)
        else:
            score = ((raw - lo) / (hi - lo)).fillna(0.5)
        out[f"score_{comp}"] = score.to_numpy(float)
        out[f"points_{comp}"] = (score * w).to_numpy(float)
        total = total + out[f"points_{comp}"].to_numpy(float)
    out["total"] = total
    out["letter"] = [grade_letter(v) for v in total]
    return out.sort_values("total", ascending=False).reset_index(drop=True)


def draft_grade(st: DraftState, meta: dict, sm: SeatMap, *, odds: pd.DataFrame,
                vi: pd.DataFrame | None = None, byes: pd.Series | None = None,
                elevation: float | None = None) -> pd.DataFrame:
    """:func:`grade_components` scored by :func:`apply_grade` — a row per seat, graded on the room.

    ⚠ **There is no combined grade across your seats and there is nowhere to put one.** k human
    teams in one draft are ONE observation (16.17): your picks depleted each other's pools, so their
    grades are mechanically anti-correlated and averaging them would report the depletion as skill.
    The frame carries a ``human`` flag and k rows.
    """
    return apply_grade(grade_components(st, meta, sm, odds=odds, vi=vi, byes=byes,
                                        elevation=elevation))


# ------------------------------------------------------------------------------------------------
# 16.12(c) — the availability / reach-risk readout, rendered at last
# ------------------------------------------------------------------------------------------------
def reach_risk_view(st: DraftState, meta: dict, team: int | None = None, *, n: int = 25,
                    model=None, n_sims: int = 200, seed: int = 0) -> pd.DataFrame:
    """``P(this player is still there at your next pick)`` for the top of one seat's board.

    ★ **The engine side of this shipped in Session G and has had no surface until now** — 16.12(c)
    was built ``engine-side only`` because the app came strictly last. It is
    :func:`~fantasy_quant.draft.drift.availability_readout` over 11.2's validated survival oracle,
    with the pick window taken from :func:`~fantasy_quant.draft.optimizer._next_own_pick` rather
    than counted here: the snake arithmetic already exists and a display layer re-deriving it is how
    the K1.5 seat-map defect happened.

    Returns the board rows with ``p_available``, ``p_available_baseline``, ``drift_picks`` and the
    three-bucket ``reach_risk`` label. **Both probabilities are kept**: the drift adjustment is not
    backtestable (16.11's forward-only constraint), so the honest presentation of it is the pair.
    """
    seat = st.your_team if team is None else int(team)
    pool = st.draftable_pool(seat).head(int(n))
    # ``board_index`` is first because it is what makes this frame joinable back onto the board
    # (:func:`attach_reach`); the readout itself never looks at it.
    cols = ["board_index", "player_key", "player_name", "pos", "adp", "drift_picks", "p_available",
            "p_available_baseline", "p_available_delta", "reach_risk"]
    if pool.empty:
        return pd.DataFrame(columns=cols)

    from fantasy_quant.draft import drift

    # ⚠ `optimizer._next_own_pick` answers *which* pick is next; the readout needs *how many
    # opponents pick first*, and the two differ by whether the seat is on the clock right now. That
    # one-line difference now lives in :func:`next_pick_info` and is read, not repeated — the seat
    # strip needs the same fact and a second copy is how the K1.5 seat-map defect happened.
    nxt_info = next_pick_info(st, seat)
    nxt, window = nxt_info["next_pick"], nxt_info["picks_away"]
    model = model if model is not None else mock.load_opponent_model()
    out = drift.availability_readout(pool.reset_index(drop=True), model, window_picks=window,
                                     season=int(meta.get("season", 2026)),
                                     n_teams=int(st.n_teams), pick0=int(st.overall_pick),
                                     n_sims=int(n_sims), seed=int(seed))
    out.insert(1, "player_name", pool["player_name"].to_numpy())
    out["board_index"] = pool.index.to_numpy()
    out.attrs["window_picks"] = window
    out.attrs["next_pick"] = nxt
    return out[[c for c in cols if c in out.columns]]


# ------------------------------------------------------------------------------------------------
# the player card (PLAYER-VIEW §3/§4) — one player, everything the frozen stack knows
# ------------------------------------------------------------------------------------------------
def player_card(st: DraftState, board_index: int, *, vi: pd.DataFrame | None = None,
                lam: float = 0.0, risk=None, reach: pd.DataFrame | None = None) -> dict:
    """Everything the frozen stack holds about one player, arranged — the PLAYER-VIEW deep page.

    ``{name, pos, team, adp, available, bars, chain, flags, cliff, reach}``. ``bars`` is the eight
    PLAYER-VIEW readouts as ``{label, value, fmt, help}`` rows; ``chain`` is
    :func:`explain_chain`'s T27 arithmetic for this player, unchanged.

    ⚠ **Nothing here is computed for the card.** Every value is a lookup into a frame that already
    existed — which is the difference between a deep page and a second model. The one arrangement
    choice is which eight bars, and that is `docs/PLAYER-VIEW.md`'s list, not this function's.
    """
    row = st.board.loc[int(board_index)]
    key = str(row["player_key"])
    card: dict = {
        "board_index": int(board_index), "name": str(row["player_name"]),
        "pos": str(row["pos"]), "team": (str(row["team"]) if pd.notna(row.get("team")) else "—"),
        "adp": float(row["adp"]), "available": int(board_index) in st.available,
        "flags": str(range_flags(st.board.loc[[int(board_index)]]).iloc[0]),
        "chain": [], "reach": None,
    }
    def _num(col):
        v = row.get(col)
        v = pd.to_numeric(pd.Series([v]), errors="coerce").iloc[0]
        return float(v) if pd.notna(v) else None

    card["bars"] = [
        {"label": "PROJ", "value": _num("proj_points"), "fmt": "%.0f"},
        {"label": "MEAN", "value": _num("mean"), "fmt": "%.0f"},
        {"label": "AVAIL", "value": _num("games_played_mean"), "fmt": "%.1f"},
        {"label": "Q10", "value": _num("q10"), "fmt": "%.0f"},
        {"label": "MED", "value": _num("q50"), "fmt": "%.0f"},
        {"label": "Q90", "value": _num("q90"), "fmt": "%.0f"},
        {"label": "BOOM", "value": _num("boom_prob_live"), "fmt": "%.2f"},
        {"label": "BUST", "value": _num("bust_prob_live"), "fmt": "%.2f"},
    ]
    for b in card["bars"]:
        b["help"] = stat_help(b["label"])

    cliffs = cliff_series(st, risk=risk)
    if int(board_index) in cliffs.index:
        card["cliff"] = float(cliffs.loc[int(board_index)])
    else:
        card["cliff"] = None

    # ★ UI-2 — PLAYER-VIEW bar #5, as a **field rather than a ninth bar**. The eight ``bars`` are a
    # frozen shape two committed sheets and a unit test assert the length of, and growing it to make
    # room for a number would mean editing a bar sheet to keep it passing. The card renders this
    # beside the identity strip; bar B2 asserts it is the *same* number the board's `BARGAIN` column
    # shows, for every player on the live board — one derivation, two surfaces.
    bg = _bargain(st)
    v = float(bg.loc[int(board_index)]) if int(board_index) in bg.index else np.nan
    card["bargain"] = {"value": (None if pd.isna(v) else v),
                       "rounds": (None if pd.isna(v) else v / float(st.n_teams)),
                       "help": stat_help("BARGAIN")}

    if vi is not None and not vi.empty:
        hit = [e for e in explain_chain(st.board.loc[[int(board_index)]], vi,
                                        str(row["player_name"]), lam)]
        card["chain"] = hit[:1]
    if reach is not None and not reach.empty and "player_key" in reach.columns:
        m = reach[reach["player_key"].astype(str) == key]
        if len(m):
            card["reach"] = m.iloc[0].to_dict()
    return card


def parse_seats(raw: str | Sequence[int]) -> list[int]:
    """``"3,7"`` (1-indexed) -> ``[2, 6]``. The **first** listed seat is the primary one.

    Primary matters: ``DraftState.your_team`` is what the frozen cost report, the 9.5 objective,
    best-ball and MCTS all read, and none of them should learn that a second human exists.
    """
    if not isinstance(raw, str):
        seats = [int(x) - 1 for x in raw]
    else:
        try:
            seats = [int(x.strip()) - 1 for x in raw.split(",") if x.strip()]
        except ValueError:
            raise ValueError(f"seats wants comma-separated seat numbers, got {raw!r}") from None
    if len(set(seats)) != len(seats):
        raise ValueError(f"seats has a repeat: {raw!r}")
    if any(s < 0 for s in seats):
        raise ValueError(f"seats are 1-indexed: {raw!r}")
    return seats
