"""Phase 16.13 — the read-only risk/value enrichment of the mock-draft board.

A live :class:`~fantasy_quant.draft.simulator.DraftState` board carries only ``adp``/``pos``. That
is enough to build the *behavioral* opponents of 11.1/11.3 (chalk, zero-RB, a reacher), but it
cannot express the two opponents a real league is full of — the manager who chases ceiling and the
manager who wants a floor — because the board has no ceiling or floor on it. This module attaches
what those personalities need to see:

    boom_prob · q90 · bust_prob · q10 · games_played_mean · mean
                                                             (Phase 5, frozen distribution)
    upside · floor                                           (those quantiles, level-controlled —
                                                              see :func:`residual_shape`)
    vbd · overall_rank                                       (Phase 4, frozen value board)
    rookie                                                   (Sleeper ``years_exp == 0``)
    cos                                                      (Phase 16.5 change-of-situation)

**Read-only, and that is the whole design constraint.** Every column is *read* out of an existing
frozen contract — :func:`~fantasy_quant.projections.distribution.cached_distribution` and
:func:`~fantasy_quant.valuation.value_board.value_board`, the same two readers
``optimizer.assemble_value`` uses — and nothing here is fitted, tuned, or written back. There is no
modelling change in this module; if a number here is wrong it is wrong upstream. The columns are
optional throughout: :data:`~fantasy_quant.draft.simulator.PASSTHROUGH_COLS` carries whatever is
present, ADP-only callers are unaffected, and a player the Phase-5 board misses (a rookie with no
prior, a team defense) arrives as ``NaN`` for the consumer's own fallback to handle.

**PIT.** ``as_of`` defaults to :func:`~fantasy_quant.backtest.walkforward.draft_date` for the
season, and the value board filters at the read — so enriching a 2022 board for a backtest sees
2022 draft-day projections, never the season that followed.

**★ ``cos`` is a behavioral prior, not a value claim.** Phase 16.1 (situation alpha) and 16.2
(competition) are honest nulls: a changed situation does **not** predict outperformance in our
backtest, and nothing in the frozen value stack prices it. What 16.5's event board *does* describe
is what the draft room *talks about* — the traded receiver, the rookie, the new play-caller — which
is exactly the pull a narrative-chasing opponent is meant to model. It is used here only to shape
an *opponent's* reach, and :data:`COS_WEIGHTS` is a stated, uncalibrated preference ordering, not a
fitted coefficient. Do not let it leak into the value stack.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.backtest.scoring import RuleSet
from fantasy_quant.backtest.walkforward import draft_date
from fantasy_quant.draft.simulator import board_player_key
from fantasy_quant.projections import distribution
from fantasy_quant.situation import events
from fantasy_quant.valuation.value_board import value_board

#: Frozen Phase-5 distribution columns the enrichment lifts onto the board. ``mean`` rides along as
#: the **level control** the shape signals below are computed against — it is not itself a risk
#: signal.
DIST_COLS: tuple[str, ...] = ("boom_prob", "q90", "bust_prob", "q10", "games_played_mean", "mean")

#: Derived *shape* columns: ``q90``/``q10`` with the projected level regressed out, within position.
#: See :func:`residual_shape` — these, not the raw quantiles, are what a ceiling- or floor-seeking
#: personality must tilt on.
SHAPE_COLS: tuple[str, ...] = ("upside", "floor")

#: Frozen Phase-4 value-board columns the enrichment lifts onto the board. ``overall_rank`` is a
#: rank — **lower is better** — so a personality that wants good players weights it *negative*.
VALUE_COLS: tuple[str, ...] = ("vbd", "overall_rank")

#: How loudly each 16.5 event type reads as "this player's situation changed", in [0, 1]. A stated
#: preference ordering for opponent behaviour (see the module note) — not a fitted coefficient, and
#: deliberately coarse so nobody mistakes it for one.
COS_WEIGHTS: dict[str, float] = {
    "team_change": 1.0,      # he is somewhere new — the loudest offseason story there is
    "new_to_league": 0.9,    # rookie (or a returning ghost): unbounded imagination, no film
    "room_change": 0.6,      # he stayed, the depth chart around him did not
    "context_only": 0.4,     # same room, new play-caller or new quarterback
}

#: Minimum rows a position group needs before a within-group regression is worth running.
MIN_FIT_ROWS: int = 5


def _residualize(y, x, pos) -> np.ndarray:
    """``y`` with ``x`` regressed out inside each position group (NaN where either is missing)."""
    y = pd.to_numeric(pd.Series(y), errors="coerce").to_numpy(float)
    x = pd.to_numeric(pd.Series(x), errors="coerce").to_numpy(float)
    p = np.asarray(pos)
    out = np.full(len(y), np.nan)
    for g in np.unique(p):
        ok = (p == g) & np.isfinite(y) & np.isfinite(x)
        if int(ok.sum()) < MIN_FIT_ROWS:
            continue
        a = np.column_stack([np.ones(int(ok.sum())), x[ok]])
        beta, *_ = np.linalg.lstsq(a, y[ok], rcond=None)
        out[ok] = y[ok] - a @ beta
    return out


def residual_shape(board: pd.DataFrame, *, level: str = "mean") -> pd.DataFrame:
    """``upside`` / ``floor`` — the ceiling and the floor a player carries **beyond his level**.

    ★ **This is the correction that makes 16.14 mean anything, and it is the Session-G lesson
    again.** The obvious build — an "upside chaser" who weights ``q90`` and a "safe" drafter who
    weights ``q10`` — does not produce two opposed managers. Measured within position on the frozen
    board, ``corr(q90, mean) = 0.98–0.999`` in *every* season checked (2022, 2025, 2026) and
    ``corr(q90, q10) = +0.62 … +0.74``. A raw ``q90`` weight is therefore not a *ceiling* tilt at
    all — it is a **quality** tilt wearing a ceiling's clothes, and so is a raw ``q10`` weight. Both
    personalities just drafted good players from opposite-sounding rationales, and the
    face-validity check caught them agreeing.

    Regressing the level out inside each position leaves the partial signal that was wanted all
    along — "more ceiling than a player projected this high usually has". It works: ``corr`` with
    ``mean`` is 0 by construction, and ``corr(upside, floor)`` is **−0.86** (2022/2025), i.e.
    genuinely opposed. On 2026 it is only −0.20, which is T17 showing through — the live season's
    games-played draw collapses to four cohort values and flattens the cloud's shape.

    Same family as the 16.10 finding carried forward in ``CLAUDE.md``: *a coefficient is not
    transportable without its controls.* Here it is a **signal**, not a coefficient, and the missing
    control is the projected level — but the failure mode is identical, and it presented the same
    way: as a plausible-looking result rather than as an error.
    """
    pos_col = "pos" if "pos" in board.columns else "position"
    if level not in board.columns or pos_col not in board.columns:
        return pd.DataFrame(index=board.index)
    pos = board[pos_col].to_numpy()
    return pd.DataFrame({
        "upside": _residualize(board.get("q90"), board[level], pos),
        "floor": _residualize(board.get("q10"), board[level], pos),
    }, index=board.index)


def rookie_flags(con, season: int) -> set[str]:
    """gsis ids Sleeper lists at ``years_exp == 0`` for ``season``.

    The same read 11.1's choice frame and 11.2's availability replay use, so the ``rookie`` column a
    simulated board carries means exactly what the fitted ``rookie`` coefficient was estimated on.
    """
    df = con.execute(
        "SELECT DISTINCT gsis_id FROM sleeper_draft_picks "
        "WHERE season = ? AND gsis_id IS NOT NULL AND years_exp = 0", [season]).df()
    return set(df["gsis_id"].astype(str)) if not df.empty else set()


def situation_scores(con, season: int, *, max_adp: float = events.MAX_ADP) -> pd.Series:
    """``gsis_id -> cos`` in [0, 1], from 16.5's derived event board via :data:`COS_WEIGHTS`.

    16.5 ships its event board on a name/team schema (the CSV a human annotates), so the gsis is
    recovered by joining back onto :func:`~fantasy_quant.situation.events.board`, which is the exact
    frame ``build_event_board`` was derived from — the join is total by construction and asserted
    here rather than assumed. Players with no event are simply absent (the caller fills 0).
    """
    ev = events.build_event_board(con, season, max_adp)
    if ev.empty:
        return pd.Series(dtype=float)
    keys = events.board(con, season, max_adp)[["gsis_id", "player", "position", "team"]]
    m = ev.merge(keys, on=["player", "position", "team"], how="left")
    missing = int(m["gsis_id"].isna().sum())
    if missing:
        raise ValueError(f"{missing} of {len(m)} 16.5 events did not rejoin their board gsis — "
                         f"the event board and its source board have drifted apart")
    m = m.drop_duplicates("gsis_id")
    return pd.Series(m["event_type"].map(COS_WEIGHTS).fillna(0.0).to_numpy(float),
                     index=m["gsis_id"].astype(str), name="cos")


def attach_enrichment(board: pd.DataFrame, *, dist: pd.DataFrame | None = None,
                      value: pd.DataFrame | None = None, rookie: set[str] | None = None,
                      situation: pd.Series | None = None) -> pd.DataFrame:
    """Attach the 16.13 columns to a raw ADP board, keyed by :func:`board_player_key`.

    The pure join half of :func:`enrich_board` — every input is already-loaded, so this is what the
    offline tests exercise. Returns a copy; the inputs are never mutated. A column whose source
    frame is ``None`` is not created at all, so a partial enrichment stays honest about what it
    knows rather than filling zeros.

    ``rookie`` and ``situation`` are the two exceptions and deliberately so: both are
    *absence-means-no* signals (not on the rookie list ⇒ not a rookie; no 16.5 event ⇒ nothing
    changed), so a missing key is a real 0, not an unknown.
    """
    out = board.copy()
    key = board_player_key(out).astype(str)

    for src, cols in ((dist, DIST_COLS), (value, VALUE_COLS)):
        if src is None or src.empty:
            continue
        idx = src.drop_duplicates("player_key").set_index(src["player_key"].astype(str))
        for c in cols:
            if c in idx.columns:
                out[c] = pd.to_numeric(key.map(idx[c]), errors="coerce").astype(float)

    if rookie is not None:
        out["rookie"] = key.isin(rookie).astype(float)
    if situation is not None:
        out["cos"] = (key.map(situation) if len(situation) else 0.0)
        out["cos"] = pd.to_numeric(out["cos"], errors="coerce").fillna(0.0).astype(float)

    shape = residual_shape(out)
    for c in SHAPE_COLS:
        if c in shape.columns:
            out[c] = shape[c]
    return out


def enrich_board(con, season: int, board: pd.DataFrame, *, as_of=None,
                 ruleset: RuleSet | None = None, seed: int = 0, slots=None, n_teams: int = 10,
                 situation: bool = True) -> pd.DataFrame:
    """A raw ADP board + the frozen risk/value context, ready for :func:`simulate_draft`.

    ``seed`` selects the shared Phase-5 draw cloud (T6) — pass the same seed the rest of a run uses
    and the ceiling an opponent chases is the ceiling everything else scored. The distribution is
    memoized per process, so the first call costs ~12 s for a fresh season and later ones are free.

    ⚠ **T13:** the Phase-5 cloud is not yet reproducible *across processes* — per-player ``q10``/
    ``q90`` move between runs. Assert on the **shape** of what a personality drafts (skew, group
    means), never on a named player, or the test is flaky by construction.
    """
    ruleset = ruleset or RuleSet()
    if as_of is None:
        as_of = draft_date(con, season)
    dist = distribution.cached_distribution(con, season, ruleset=ruleset, seed=seed)[0]
    vb = value_board(con, season, as_of, ruleset=ruleset, slots=slots, n_teams=n_teams)
    return attach_enrichment(
        board,
        dist=dist,
        value=vb,
        rookie=rookie_flags(con, season),
        situation=situation_scores(con, season) if situation else None,
    )


def enrichment_coverage(board: pd.DataFrame) -> dict:
    """Per-column fill rate on an enriched board — the 16.13 done-bar, reported not assumed.

    Coverage is never expected to be 100 %: team defenses carry no projection at all and rookies
    without a prior season are exactly the population Phase 5 is thinnest on. The number is here so
    a drop is *visible* rather than silently becoming a pool of NaN a personality treats as neutral.
    """
    n = len(board)
    out = {"n_rows": int(n)}
    for c in (*DIST_COLS, *SHAPE_COLS, *VALUE_COLS, "rookie", "cos"):
        if c in board.columns:
            filled = int(pd.to_numeric(board[c], errors="coerce").notna().sum())
            out[c] = round(filled / n, 4) if n else 0.0
    return out
