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

#: The four columns a human actually drafts on, plus the ``#`` pick handle carried by the index.
#: **Slim is a projection of :func:`board_view`, never a second query** — one derivation, two
#: column subsets, which is why :data:`BOARD_VIEW_COLS` and this tuple cannot describe different
#: rows. (K1.5 step 2. The advanced view is simply :data:`BOARD_VIEW_COLS` in full.)
SLIM_VIEW_COLS: tuple[str, ...] = ("PLAYER", "POS", "ADP", "PROJ")

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

#: The three board projections, in the order the mode control offers them.
VIEW_MODES: tuple[str, ...] = ("slim", "ranges", "advanced")


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
        "worked_example": "On the 2026 board almost every adjacent pair inside the first four "
                          "rounds overlaps — the ranking there is a presentation, not a finding.",
        "how_to_read_it": "Where it is true, break the tie on something the model does not price: "
                          "your own read, roster fit, or the bye-week and concentration risks on "
                          "the post-draft page.",
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
    rendered = {lbl for _, lbl in BOARD_VIEW_COLS} | set(RANGE_VIEW_COLS) | set(SLIM_VIEW_COLS)
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
    if mode == "advanced":
        cols = [lbl for _, lbl in BOARD_VIEW_COLS]
    elif mode == "ranges":
        cols = list(RANGE_VIEW_COLS)
    else:
        cols = list(SLIM_VIEW_COLS)
    return view[[c for c in cols if c in view.columns]]


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


def board_view(st: DraftState, team: int | None = None, *, pos: str | None = None,
               n: int | None = None, risk=None) -> pd.DataFrame:
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
    return out


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
                             byes: pd.Series | None = None,
                             elevation: float | None = None) -> dict:
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
    """
    seat = int(team)
    roster = st.roster(seat)
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
    cols = ["player_key", "player_name", "pos", "adp", "drift_picks", "p_available",
            "p_available_baseline", "p_available_delta", "reach_risk"]
    if pool.empty:
        return pd.DataFrame(columns=cols)

    from fantasy_quant.draft import drift
    from fantasy_quant.draft.optimizer import _next_own_pick

    last = st.n_teams * st.rounds
    nxt = _next_own_pick(st.overall_pick, seat, st.n_teams, last)
    # ⚠ `_next_own_pick` answers *which* pick is next; the readout needs *how many opponents pick
    # first*, and the two differ by whether the seat is on the clock right now. The optimizer's
    # `window_end = nxt - 1` is a pick-number threshold on the ADP scale, a different
    # parameterisation of the same fact — so the count is derived here rather than copied from
    # there and quietly reinterpreted.
    if nxt is None:
        window = 0
    elif st.team_on_clock() == seat:
        window = max(0, int(nxt) - int(st.overall_pick) - 1)
    else:
        window = max(0, int(nxt) - int(st.overall_pick))
    model = model if model is not None else mock.load_opponent_model()
    out = drift.availability_readout(pool.reset_index(drop=True), model, window_picks=window,
                                     season=int(meta.get("season", 2026)),
                                     n_teams=int(st.n_teams), pick0=int(st.overall_pick),
                                     n_sims=int(n_sims), seed=int(seed))
    out.insert(1, "player_name", pool["player_name"].to_numpy())
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
