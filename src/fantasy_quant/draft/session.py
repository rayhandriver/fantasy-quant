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
)

#: The four columns a human actually drafts on, plus the ``#`` pick handle carried by the index.
#: **Slim is a projection of :func:`board_view`, never a second query** — one derivation, two
#: column subsets, which is why :data:`BOARD_VIEW_COLS` and this tuple cannot describe different
#: rows. (K1.5 step 2. The advanced view is simply :data:`BOARD_VIEW_COLS` in full.)
SLIM_VIEW_COLS: tuple[str, ...] = ("PLAYER", "POS", "ADP", "PROJ")


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
    a test failure, which is the only way a dictionary stays complete (14.O's done-bar)."""
    missing = [lbl for _, lbl in BOARD_VIEW_COLS if lbl not in STAT_DICT]
    if missing:
        raise AssertionError(f"BOARD_VIEW_COLS with no STAT_DICT entry: {missing}")


def project_view(view: pd.DataFrame, advanced: bool = False) -> pd.DataFrame:
    """The rendered column subset of a :func:`board_view` frame.

    Takes the *frame*, not the state, precisely so a caller cannot accidentally re-query for the
    slim view: both views are this function applied to one object, so "the slim board and the
    advanced board show the same rows in the same order" is true by construction rather than by
    test (bar B2).
    """
    if advanced:
        return view
    return view[[c for c in SLIM_VIEW_COLS if c in view.columns]]


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
def board_view(st: DraftState, team: int | None = None, *, pos: str | None = None,
               n: int | None = None) -> pd.DataFrame:
    """The best-available board for one seat: :data:`BOARD_VIEW_COLS`, index = the pick handle.

    The index is preserved deliberately — it is the ``#`` a CLI user types and the row key an app
    selects on, and it is the board index :func:`~fantasy_quant.draft.simulator._apply_pick` wants.
    A missing column is created as all-NaN rather than dropped, so the frame's shape does not depend
    on how richly a particular board happened to enrich.
    """
    pool = st.draftable_pool(st.your_team if team is None else int(team))
    if pos:
        wanted = [p.strip().upper() for p in str(pos).split(",") if p.strip()]
        pool = pool[pool["pos"].isin(wanted)]
    if n is not None:
        pool = pool.head(int(n))
    out = pd.DataFrame(index=pool.index)
    for col, label in BOARD_VIEW_COLS:
        out[label] = pool[col] if col in pool.columns else np.nan
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

    from fantasy_quant.inseason.lineup import _slot_plan, optimal_lineup

    plan = [label for label, _ in _slot_plan(st.slots)]
    rows = plan + [f"BN{i + 1}" for i in range(max(0, st.rounds - len(plan)))]
    grid = pd.DataFrame("", index=rows, columns=cols)
    for t in range(st.n_teams):
        roster = st.roster(t)
        if roster.empty:
            continue
        scores = _slot_scores(roster, vi)
        # a degenerate one-draw "week": `optimal_lineup` reduces to its greedy mean-max fill, which
        # is the frozen `flex_groups` order. Nothing here chooses a lineup; it reads one.
        choice = optimal_lineup(scores[:, None], roster["pos"].tolist(), st.slots)
        started = set()
        for label, i in choice.slots.items():
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
            "seats": mock.seat_table(panel), "n_humans": len(sm.human_teams)}


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
