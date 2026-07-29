"""Phase 16.13 — the read-only risk/value enrichment of the mock-draft board.

A live :class:`~fantasy_quant.draft.simulator.DraftState` board carries only ``adp``/``pos``. That
is enough to build the *behavioral* opponents of 11.1/11.3 (chalk, zero-RB, a reacher), but it
cannot express the two opponents a real league is full of — the manager who chases ceiling and the
manager who wants a floor — because the board has no ceiling or floor on it. This module attaches
what those personalities need to see:

    boom_prob · q90 · bust_prob · q10 · games_played_mean · mean
                                                             (Phase 5, frozen distribution)
    boom_prob_live · bust_prob_live                          (the same rates measured on the
                                                              season before the board — T22)
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
from fantasy_quant.draft.simulator import board_player_key, canon_pos
from fantasy_quant.projections import distribution, variance
from fantasy_quant.situation import events
from fantasy_quant.valuation.value_board import value_board

#: Frozen Phase-5 distribution columns the enrichment lifts onto the board. ``mean`` rides along as
#: the **level control** the shape signals below are computed against — it is not itself a risk
#: signal. ``q50`` likewise: it is the denominator of :data:`tail_risk`'s relative spread, never a
#: weightable signal of its own.
DIST_COLS: tuple[str, ...] = ("boom_prob", "q90", "bust_prob", "q10", "q50",
                              "games_played_mean", "mean")

#: **T22 — the boom/bust pair, re-measured on the season the board is actually drafted after.**
#: The frozen ``boom_prob``/``bust_prob`` above are ``weekly_volatility(max(train_seasons))``, and
#: ``train_seasons`` for a live season is ``DEV_SEASONS``, which ends at **2022** — so a 2026 board
#: carries the 2022 rates and a player absent in 2022 carries a ``fillna(0.0)`` that reads as
#: *never busts*. These two columns answer the same question against ``season − 1``. Same read-only
#: contract as everything else here: nothing is fitted, the frozen column is left exactly as it is,
#: and a player with no prior season stays **NaN** — the honest value for "we have not seen him
#: play", and the one thing the frozen column gets wrong by construction.
LIVE_VOL_COLS: tuple[str, ...] = ("boom_prob_live", "bust_prob_live")

#: Seasons of lag between the board and the realized weekly season the live rates are measured on
#: that still count as "prior season". One, and the guard is the point: T17 and T22 are the same
#: failure — a live season silently reading a covariate from four years ago — so this module states
#: the recency it needs rather than trusting a default to be current.
VOL_MAX_LAG: int = 1

#: Derived *shape* columns: ``q90``/``q10``/``games_played_mean``/relative downside spread with the
#: projected level controlled for, within position. See :func:`residual_shape` — these, not the raw
#: columns, are what a ceiling-, floor- or durability-seeking personality must tilt on.
SHAPE_COLS: tuple[str, ...] = ("upside", "floor", "durability", "tail_risk")

#: How the level is controlled for in :func:`residual_shape`, applied to the **ratios** built by
#: :func:`shape_inputs`. **T19 replaced the default with** ``rank``, selected against a
#: pre-registered bar by ``steps/phase16_14r_2_floor.py`` — not by argument.
#:
#: ``linear``     the 16.14 original — OLS within position, ``y − (a + b·level)``. On the ratios it
#:                is no longer *inverted* (worst ``corr(floor, adp)`` +0.179 → **+0.069**), but its
#:                top-10 floor list is still **70 % ADP > 130** and its ``corr(upside, floor)``
#:                collapses to −0.11: the residual of a ratio still puts its extremes at the thin
#:                end of the board. Fails bar 2.
#: ``tobit``      censored-normal MLE + the *generalized* residual, so a player at the censoring
#:                point scores the inverse-Mills value (negative, "at least this bad") instead of a
#:                large positive one. It nails the level control exactly (``corr(floor, mean)`` =
#:                −0.000 by construction) and still fails bar 2 at **100 %** deep — the cleanest
#:                demonstration that the defect was never really about the likelihood.
#: ``rank``       the percentile of ``y`` among the player's nearest neighbours in board order,
#:                centred at 0. Distribution-free, and a rank cannot be inverted by censoring —
#:                tied zeros tie at the bottom of their own neighbourhood. **Selected**: the only
#:                method passing both halves of the T19 bar *and* keeping 16.14's opposition
#:                (``corr(upside, floor)`` −0.49).
#: ``rank_delta`` ``rank`` **minus the level's own rank in the same neighbourhood** — the rank
#:                analogue of residualizing, i.e. a second level control on top of the ratio. It
#:                **over**-controls: ``corr(floor, adp)`` swings back to **+0.29** and the top-10
#:                is 90 % deep, because subtracting the level rank from an already scale-free ratio
#:                hands the biggest values to low-projection players. Kept as a named dead end.
SHAPE_METHODS: tuple[str, ...] = ("linear", "tobit", "rank", "rank_delta")

#: Neighbours either side of a player, in board order within position, for ``method="rank"`` —
#: an **upper bound**, capped at :data:`RANK_WINDOW_FRAC` of the position group.
#:
#: ⚠ The cap is not a detail. At a flat 25 the window is wider than the whole QB (27) and TE (23)
#: group on a 2026 board, so the "local" rank degenerates into a **global** one and the level
#: control silently switches off — measured as ``corr(tail_risk, adp)`` +0.45 QB / +0.78 TE while
#: RB/WR, whose groups are big enough, sat at +0.38/+0.13. A neighbourhood has to be a *fraction*
#: of its group, never an absolute count, or the estimator means something different per position.
RANK_WINDOW: int = 25

#: Fraction of a position group either side of a player that counts as his neighbourhood.
RANK_WINDOW_FRAC: float = 0.25

#: Left-censoring point of ``q10``. A season-points quantile cannot go below zero, and 42.9 % of
#: the 2026 offensive board sits exactly on it.
CENSOR_AT: float = 0.0

#: Projected-level floor below which a ratio to the level is meaningless (points/season). Guards
#: :func:`shape_inputs` against dividing by a near-zero projection.
MIN_LEVEL: float = 1.0

#: Cache-busting tag for anything that memoizes an **enriched** board — bump it whenever what this
#: module produces changes, in columns or in meaning.
#:
#: ⚠ It exists because the alternative bit us mid-session: ``mock.room_board``'s parquet cache is
#: keyed on ``(season, scoring, teams)``, so after T19 changed what ``floor`` *means* every
#: downstream step would have silently read boards built by the previous definition. That is the
#: repo's most-repeated failure mode (F.5's hardcoded label, T13's cross-process cloud, the stale
#: editor buffer) in its cheapest form. A version in the key turns a silent wrong answer into a
#: cache miss.
ENRICH_VERSION: str = "v3-t22-live-vol"

#: Frozen Phase-4 value-board columns the enrichment lifts onto the board. ``overall_rank`` is a
#: rank — **lower is better** — so a personality that wants good players weights it *negative*.
VALUE_COLS: tuple[str, ...] = ("vbd", "overall_rank")

#: 16.14R step 3 — **structural context a value objective cannot see**, all three derived (see
#: :func:`role_shares` / :func:`td_regression`), all three shipping **default-OFF**: no seat weights
#: them unless it says so, per the "level, not the residual" rule. They exist because the value
#: hawk's bad picks in the 2x5 mock were *blind spots*, not mis-weights — no objective over a board
#: without these columns can avoid them.
#:
#: ⚠ **Two of the three are partly a level restatement, and a consumer must control for that.**
#: Measured against ``vbd`` within position on the 2026 board: ``role_share`` **+0.88 RB / +0.67
#: WR** (a bell-cow is both valuable and uncontested — they are the same fact seen twice) and
#: ``td_regression`` **+0.63 RB / +0.47 QB** (better players score more touchdowns, so scoring more
#: than expected correlates with being good). Only ``role_delta`` is close to orthogonal
#: (−0.06…+0.31). This is the same level-vs-shape trap the rest of this module documents, arriving
#: for the fifth time; ``signal_bonus``'s within-position z-score does **not** remove it. A seat
#: weighting these owes the level control at the point of use — see 16.14R step 6, which applies
#: them as neighbourhood-local penalties inside its objective rather than as flat tilts.
CONTEXT_COLS: tuple[str, ...] = ("role_share", "role_delta", "td_regression")

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


def _tobit_residual(y, x, pos, *, left: float = CENSOR_AT) -> np.ndarray:
    """``y`` with ``x`` regressed out inside each position, **accounting for left-censoring**.

    Fits ``y* = a + b·x + ε``, ``ε ~ N(0, σ)``, observed ``y = max(y*, left)`` by MLE, and returns
    the **generalized residual** — ``y − (a + b·x)`` where uncensored, and
    ``E[y* − (a + b·x) | y* ≤ left] = −σ·φ(z)/Φ(z)`` where censored. That second branch is the
    whole point: an OLS fit through a floored variable predicts a *negative* ``y*`` for
    replacement-level players, so every one of them sitting on the floor scores a large **positive**
    residual and the signal inverts. Under the censored likelihood they instead score the
    inverse-Mills value, which is negative and more negative the further below the floor the fit
    thinks they truly are.

    Falls back to the plain OLS residual when a group is too small to fit or nothing is censored
    (where the two estimators coincide anyway).
    """
    from scipy.optimize import minimize
    from scipy.stats import norm

    y = pd.to_numeric(pd.Series(y), errors="coerce").to_numpy(float)
    x = pd.to_numeric(pd.Series(x), errors="coerce").to_numpy(float)
    p = np.asarray(pos)
    out = np.full(len(y), np.nan)
    for g in np.unique(p):
        ok = (p == g) & np.isfinite(y) & np.isfinite(x)
        if int(ok.sum()) < MIN_FIT_ROWS:
            continue
        yy, xx = y[ok], x[ok]
        a = np.column_stack([np.ones(len(xx)), xx])
        obs = yy > left
        if obs.sum() < MIN_FIT_ROWS or obs.all():        # nothing censored -> OLS is the MLE
            beta, *_ = np.linalg.lstsq(a, yy, rcond=None)
            out[ok] = yy - a @ beta
            continue
        b0, *_ = np.linalg.lstsq(a[obs], yy[obs], rcond=None)
        s0 = max(float(np.std(yy[obs] - a[obs] @ b0)), 1e-6)

        def nll(th, a=a, yy=yy, obs=obs):
            s = float(np.exp(th[2]))
            mu = a @ th[:2]
            uncens = norm.logpdf(yy, mu, s)
            cens = norm.logcdf((left - mu) / s)
            return -float(np.where(obs, uncens, cens).sum())

        res = minimize(nll, np.r_[b0, np.log(s0)], method="Nelder-Mead",
                       options={"maxiter": 4000, "xatol": 1e-6, "fatol": 1e-6})
        beta, sigma = res.x[:2], float(np.exp(res.x[2]))
        mu = a @ beta
        z = (left - mu) / sigma
        mills = -sigma * np.exp(norm.logpdf(z) - np.maximum(norm.logcdf(z), -700.0))
        out[ok] = np.where(obs, yy - mu, mills)
    return out


def _neighbourhood_rank(y, key, pos, *, window: int = RANK_WINDOW, level=None) -> np.ndarray:
    """``y``'s percentile among its nearest neighbours in ``key`` order, within position, minus 0.5.

    The distribution-free level control. ``key`` is the board axis (ADP): players sitting near each
    other on the board are of comparable consensus quality, so ranking inside that window asks
    "safer than the players going around him?" and answers it without a functional form. Ties —
    which is what a censored variable is made of — share a mid-rank, so a floored ``q10`` can never
    out-score an unfloored one.

    ★ **Whether ``level`` belongs here depends entirely on what ``y`` is, and getting that wrong
    is how T19 took three attempts.** An ADP neighbourhood controls for what the *board* thinks,
    not for what *our projection* thinks. Run on **raw** quantiles that difference matters: a
    player we like more than the board does carries a higher ``q10`` *and* a higher ``q90`` than
    his ADP neighbours, both shape signals rank him up, and ``corr(upside, floor)`` came out
    **+0.94 QB / +0.41 RB** — the two personalities agreeing again, 16.14's defect restored, while
    passing T19's one-sided bar. Passing ``level`` (the ``rank_delta`` method) fixes that by
    subtracting the level's own neighbourhood rank.

    But once ``y`` is a **ratio to the level** (:func:`shape_inputs`), the level is already
    divided out and ``level`` here becomes a *second* control that over-shoots — ``corr(floor,
    adp)`` +0.29, top-10 90 % deep. So the shipped configuration is ratios **without** it, and
    ``rank_delta`` survives as a documented dead end.
    """
    y = pd.to_numeric(pd.Series(y), errors="coerce").to_numpy(float)
    key = pd.to_numeric(pd.Series(key), errors="coerce").to_numpy(float)
    lv = (None if level is None
          else pd.to_numeric(pd.Series(level), errors="coerce").to_numpy(float))
    p = np.asarray(pos)
    out = np.full(len(y), np.nan)
    for g in np.unique(p):
        finite = (p == g) & np.isfinite(y) & np.isfinite(key)
        if lv is not None:
            finite &= np.isfinite(lv)
        idx = np.flatnonzero(finite)
        if len(idx) < MIN_FIT_ROWS:
            continue
        order = idx[np.argsort(key[idx], kind="stable")]
        yy = y[order]
        ll = None if lv is None else lv[order]
        n = len(order)
        w = max(MIN_FIT_ROWS, min(int(window), int(n * RANK_WINDOW_FRAC)))
        for i in range(n):
            lo, hi = max(0, i - w), min(n, i + w + 1)
            nb = yy[lo:hi]
            r = float(np.mean(nb < yy[i]) + 0.5 * np.mean(nb == yy[i])) - 0.5
            if ll is not None:
                nl = ll[lo:hi]
                r -= float(np.mean(nl < ll[i]) + 0.5 * np.mean(nl == ll[i])) - 0.5
            out[order[i]] = r
    return out


def _shape(y, *, level, neighbour_key, pos, method: str) -> np.ndarray:
    """One shape column under the chosen level control (see :data:`SHAPE_METHODS`)."""
    if method == "linear":
        return _residualize(y, level, pos)
    if method == "tobit":
        return _tobit_residual(y, level, pos)
    if method == "rank":
        return _neighbourhood_rank(y, neighbour_key, pos)
    if method == "rank_delta":
        return _neighbourhood_rank(y, neighbour_key, pos, level=level)
    raise ValueError(f"unknown shape method {method!r} — known: {list(SHAPE_METHODS)}")


def shape_inputs(board: pd.DataFrame, *, level: str = "mean") -> dict[str, pd.Series]:
    """The **scale-free** quantities the shape signals are built from, before any level control.

    ★★ **This is T19's actual resolution, and it took three failed estimators to find.** The defect
    was framed as "OLS is the wrong likelihood for a censored variable", so the first two attempts
    changed the *estimator*: a censoring-aware Tobit, then a distribution-free neighbourhood rank.
    Both failed, in opposite directions and for the same underlying reason — **the problem is the
    scale, not the fit.** Residualizing a raw ``q10`` that piles up at zero has no well-behaved
    answer for the pile-up: a linear fit hands it a large *positive* residual (T19's inversion), a
    rank hands it a mid-rank that then inherits the sign of whatever the level control subtracts.
    No amount of better fitting repairs a variable whose floor is a boundary of its own support.

    Ratios do repair it. ``q10 / mean`` is the fraction of a player's projected level that survives
    to his 10th percentile — bounded, scale-free, and a censored player sits at the **bottom** of
    it, which is the honest reading: a 10th percentile of zero *is* the worst possible floor, not a
    missing observation. The level control then only has to remove what the ratio leaves.

    Three signals, one construction:

    * ``floor``      ``q10 / mean``          — how much of the projection survives the bad tail
    * ``upside``     ``q90 / mean``          — how much of it the good tail adds
    * ``tail_risk``  ``(q90 − q10) / mean``  — total relative spread, i.e. **boom-or-bust**; this
      is the column 16.14R step 4 asks for by name, and the one the user's objection ("a lot of
      these guys are relatively boom-or-bust") is actually about.

    ★ **``tail_risk`` is also the replacement for ``bust_prob``, which cannot be repaired from
    here.** ``boom_prob``/``bust_prob`` are the *prior season's* realized weekly rates, where
    "prior" means ``max(train_seasons)`` — and ``train_seasons`` for a live season is
    ``DEV_SEASONS``, which ends at **2022**. So the 2026 board's boom/bust columns are the **2022**
    season's rates (verified: a 100 % exact match on the 39 % that join) and **292 of the 306 zeros
    are ``fillna(0.0)``** — a player who was not in the league in 2022 is recorded as *never
    busting*. That is not an inert column, it is a fabricated safety claim, and it is worst exactly
    for the rookies a floor-seeking manager should most distrust. Frozen Phase-5 contract, so it is
    left alone and logged (**T22**) rather than edited.

    ``durability`` is not a ratio: ``games_played_mean`` is already on a natural bounded scale
    (games), so it passes through and is level-controlled as T17 left it.
    """
    lvl = pd.to_numeric(board.get(level), errors="coerce")
    denom = lvl.where(lvl > MIN_LEVEL)
    q10 = pd.to_numeric(board.get("q10"), errors="coerce")
    q90 = pd.to_numeric(board.get("q90"), errors="coerce")
    return {
        "floor": q10 / denom,
        "upside": q90 / denom,
        "tail_risk": (q90 - q10) / denom,
        "durability": pd.to_numeric(board.get("games_played_mean"), errors="coerce"),
    }


def residual_shape(board: pd.DataFrame, *, level: str = "mean",
                   method: str = "rank") -> pd.DataFrame:
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
    genuinely opposed.

    ★ **``durability`` is the same correction applied a third time, and T17 is why it exists.**
    While the live board was broken, ``games_played_mean`` held four cohort constants and was
    ``corr = +0.00`` with the level — inert, and documented as such. Repairing T17 turned it into a
    real per-player forecast and, in doing so, into a **level** column: ``corr(games_played_mean,
    mean)`` within position is **+0.90 / +0.47 / +0.51 / +0.46** (QB/RB/TE/WR, 2026). So a raw
    durability weight became a quality tilt the moment the data got better — the failure mode
    arriving through an *upstream fix* rather than through new code. ``durability`` is the
    level-residualized column, and it is what ``safe_floor`` weights.

    (The same repair is visible in the shape pair itself: ``corr(upside, floor)`` on 2026 was
    **−0.20** while T17 was live — the flattened games-played draw collapsing the cloud — and is
    **−0.71** once availability is rolled forward properly, back in family with 2022/2025.)

    Same family as the 16.10 finding carried forward in ``CLAUDE.md``: *a coefficient is not
    transportable without its controls.* Here it is a **signal**, not a coefficient, and the missing
    control is the projected level — but the failure mode is identical, and it presented the same
    way: as a plausible-looking result rather than as an error.

    ★★ **T19 — and this one was self-inflicted: the fix above created the next defect.** Removing
    the level by OLS is only valid if the variable being residualized is uncensored. ``q10`` is
    **exactly 0 for 42.9 % of the 2026 offensive board** (5.7 % inside ADP 50, 59.0 % past ADP 100)
    — a 10th percentile cannot be negative. A line fitted through that floor predicts a negative
    ``q10`` for replacement-level players, so everyone sitting *on* the floor scored a large
    positive residual and ``corr(floor, adp)`` came out **+0.179 RB / +0.124 WR**: the safety
    signal preferred *deeper* players, and ``safe_floor`` dutifully drafted them (Jonah Coleman,
    ADP 171; Jaydon Blue, ADP 140). Removing the level from a censored variable does not leave
    something orthogonal to quality — it leaves something anti-correlated with it.
    **A residualization is a modelling assumption about the tail.**

    ``method`` therefore selects the level control (:data:`SHAPE_METHODS`); the default is
    ``"rank"``, chosen by the pre-registered T19 bar (``corr(shape, adp) <= 0`` within **every**
    position, and a top-10 list that is not just deep players) rather than by preference. ``linear``
    is kept because it is what 16.14 shipped and the before/after has to stay runnable.
    """
    pos_col = "pos" if "pos" in board.columns else "position"
    if level not in board.columns or pos_col not in board.columns:
        return pd.DataFrame(index=board.index)
    pos = board[pos_col].to_numpy()
    # the neighbourhood axis for `rank`: the board's own level ordering, falling back to the
    # projected level when a caller hands us a frame with no ADP (the offline enrichment tests).
    nb_key = board["adp"] if "adp" in board.columns else board[level]
    raw = shape_inputs(board, level=level)
    return pd.DataFrame(
        {c: _shape(raw[c], level=board[level], neighbour_key=nb_key, pos=pos, method=method)
         for c in SHAPE_COLS},
        index=board.index)


def weekly_seasons(con) -> list[int]:
    """Regular seasons that have realized player-weeks in ``weekly``, ascending.

    Read from the table rather than from :data:`~fantasy_quant.config.DEV_SEASONS` on purpose:
    the whole of T22 is a constant that fell four years behind the data, so the one thing this
    must not do is ask a constant what the newest season is.
    """
    df = con.execute(
        "SELECT DISTINCT season FROM weekly WHERE season_type = 'REG' ORDER BY season").df()
    return [int(s) for s in df["season"].dropna()]


def volatility_source(con, season: int, *, max_lag: int = VOL_MAX_LAG) -> int:
    """The realized season the live boom/bust rates for a ``season`` board are measured on.

    The most recent season **strictly before** ``season`` that actually has weekly rows, asserted
    to be within ``max_lag`` of it. A live 2026 board resolves to 2025; a 2022 backtest board to
    2021; and a board for a season we have no prior data for raises rather than quietly reaching
    back to whatever the newest training season happens to be — which is T22's exact failure.

    Two different failures, two different exceptions, because callers should treat them
    differently: **no prior season at all** (:class:`LookupError`) is a legitimate absence — the
    first season in the store — and :func:`enrich_board` responds by not creating the columns, per
    this module's "a column whose source is absent is not created" contract. **A prior season that
    is too old** (:class:`ValueError`) is the T22 defect itself and must stop the run.
    """
    have = [s for s in weekly_seasons(con) if s < int(season)]
    if not have:
        raise LookupError(f"volatility_source: no realized weekly season before {season}")
    src = max(have)
    lag = int(season) - src
    if lag > int(max_lag):
        raise ValueError(
            f"volatility_source: newest realized season before {season} is {src} — a lag of {lag} "
            f"seasons exceeds max_lag={max_lag}. Boom/bust measured that far back is the T22 "
            f"defect, not a fallback; ingest the missing season or pass a wider max_lag knowingly.")
    return src


def live_volatility(con, season: int, *, ruleset: RuleSet | None = None,
                    max_lag: int = VOL_MAX_LAG) -> pd.DataFrame:
    """``boom_prob_live`` / ``bust_prob_live`` for a ``season`` board — T22's read.

    Same estimator as the frozen column (:func:`~fantasy_quant.projections.variance.
    weekly_volatility`, the per-player share of weeks over the boom line and under the bust line);
    the only thing that changes is *which* season it is measured on. Returns one row per player
    who actually played in that season — players it does not cover arrive as ``NaN`` at the join,
    never 0. Raises exactly as :func:`volatility_source` does.
    """
    src = volatility_source(con, season, max_lag=max_lag)
    vol = variance.weekly_volatility(con, [src], ruleset or RuleSet())
    if vol.empty:
        return pd.DataFrame(columns=["player_key", *LIVE_VOL_COLS])
    out = vol[["player_key", "boom_prob", "bust_prob"]].rename(
        columns={"boom_prob": "boom_prob_live", "bust_prob": "bust_prob_live"})
    out.attrs["source_season"] = src
    return out


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


# ==================================================================================================
# 16.14R step 3 — the three things a value objective is blind to
# ==================================================================================================
def _team_of_record(con, season: int, board: pd.DataFrame) -> pd.Series:
    """``player_key -> canonical team``, PIT, for :func:`role_shares`.

    ★ **Which source is safe depends on the direction of time, and this is the one place both
    answers are needed.** ``adp_snapshots.team`` is contaminated with an end-of-season crosswalk
    (16.1's catch: the Sep-1 2022 board lists McCaffrey on SF, a mid-season trade not yet made at
    draft time), so a *historical* board's team must come from ``weekly`` Week 1 —
    :func:`~fantasy_quant.adp.panel._early_season_team`, reused rather than re-derived. But a
    snapshot of a season **not yet played** cannot encode a trade not yet made, so for the live
    season the board's own column is both correct and the only one that exists.
    """
    from fantasy_quant.adp.panel import _canon_team, _early_season_team

    key = board_player_key(board).astype(str)
    played = _early_season_team(con, int(season))
    if not played.empty:
        mapped = key.map(played.set_index(played["gsis_id"].astype(str))["team"])
        if mapped.notna().mean() > 0.5:                  # the season really has been played
            return mapped
    if "team" not in board.columns:
        return pd.Series(index=board.index, dtype=object)
    return pd.Series(_canon_team(board["team"]).to_numpy(), index=board.index)


def role_shares(con, season: int, board: pd.DataFrame, *, level: str = "mean") -> pd.DataFrame:
    """``role_share`` and the **signed** ``role_delta`` — the committee/depth structure behind a
    projection, and whether it just got better or worse.

    ★ **Both are DERIVED, not curated** — the "derived-vs-curated" rule: hand-curate only what has
    no free source. 16.14R step 3 asks for committee share (Dylan Sampson behind Judkins) and a
    *signed* situation change (``cos`` scores how loud the story is, never whether it is good news
    — Rachaad White reads 1.0 and DK Metcalf 0.6). The obvious sources are a depth-chart feed and a
    research table; neither is needed, because two tables already ingested answer it:

    * ``role_share`` = this player's projected level as a fraction of **his own team's projected
      level at his position** on the same board. A bell-cow approaches 1.0; one half of a committee
      sits near 0.5. This is precisely the structure a value objective cannot see: ``vbd`` prices
      *how much*, never *how contested*.
    * ``role_delta`` = ``role_share`` minus the share he **actually realized** last season, on
      realized points. Positive = his role grew. That is a signed situation change with no
      annotation anywhere in it — and it prices a move by what the move does to his role, which is
      the thing a fantasy manager is trying to ask when he asks about a trade.

    ⚠ ``role_delta`` is a *transition*, so it needs both endpoints: a rookie has no prior share and
    lands as NaN, not 0. Absence here means "unknown", never "unchanged".
    """
    key = board_player_key(board).astype(str)
    pos = board["pos"] if "pos" in board.columns else board["position"].map(canon_pos)
    team = _team_of_record(con, season, board)
    lvl = pd.to_numeric(board.get(level), errors="coerce")

    cur = pd.DataFrame({"key": key, "pos": pos, "team": team, "lvl": lvl})
    tot = cur.groupby(["team", "pos"], dropna=True)["lvl"].transform("sum")
    share = (cur["lvl"] / tot.where(tot > 0)).rename("role_share")

    prior = con.execute(
        "SELECT gsis_id, recent_team AS team, position AS pos, SUM(fantasy_points_ppr) AS pts "
        "FROM weekly WHERE season = ? AND gsis_id IS NOT NULL AND recent_team IS NOT NULL "
        "GROUP BY gsis_id, recent_team, position", [int(season) - 1]).df()
    if prior.empty:
        return pd.DataFrame({"role_share": share,
                             "role_delta": pd.Series(np.nan, index=board.index)})
    from fantasy_quant.adp.panel import _canon_team

    prior["team"] = _canon_team(prior["team"])
    prior["pts"] = prior["pts"].clip(lower=0)
    ptot = prior.groupby(["team", "pos"])["pts"].transform("sum")
    prior["prev_share"] = prior["pts"] / ptot.where(ptot > 0)
    # a mid-season trade leaves two rows for one player; keep the team he scored most of his
    # points for, which is the share that describes the role he actually held.
    prev = prior.sort_values("pts", ascending=False).drop_duplicates("gsis_id")
    prev_share = pd.Series(prev["prev_share"].to_numpy(),
                           index=prev["gsis_id"].astype(str).to_numpy())
    delta = (share - key.map(prev_share)).rename("role_delta")
    return pd.DataFrame({"role_share": share, "role_delta": delta})


def td_regression(con, season: int, board: pd.DataFrame) -> pd.Series:
    """Prior-season **touchdowns over expectation, per game** — positive = due to regress *down*.

    The third blind spot (James Cook). Read straight off the Phase-3 efficiency features rather
    than rebuilt: ``td_regression_flag`` is ``td_oe / games``, clipped, where expected TDs come
    from red-zone opportunity. Phase 3.2 measured its next-year correlation at **−0.50**, which is
    what makes it a *risk* column rather than a value one — and why it ships default-OFF and
    labelled, like every other Phase-16 context channel.

    Absent for anyone with no prior season (a rookie has no TD luck to regress), which is an
    honest NaN rather than a 0.
    """
    from fantasy_quant.features.efficiency import efficiency_features

    try:
        eff = efficiency_features(con, [int(season) - 1])
    except Exception:                                    # a season with no usable weekly frame
        return pd.Series(np.nan, index=board.index)
    if eff.empty or "td_regression_flag" not in eff.columns:
        return pd.Series(np.nan, index=board.index)
    idx = eff.drop_duplicates("gsis_id").set_index(eff["gsis_id"].astype(str).loc[
        eff.drop_duplicates("gsis_id").index])
    return pd.to_numeric(board_player_key(board).astype(str).map(idx["td_regression_flag"]),
                         errors="coerce")


def attach_enrichment(board: pd.DataFrame, *, dist: pd.DataFrame | None = None,
                      value: pd.DataFrame | None = None, rookie: set[str] | None = None,
                      situation: pd.Series | None = None, context: pd.DataFrame | None = None,
                      live_vol: pd.DataFrame | None = None,
                      shape_method: str = "rank") -> pd.DataFrame:
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

    for src, cols in ((dist, DIST_COLS), (value, VALUE_COLS), (live_vol, LIVE_VOL_COLS)):
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

    shape = residual_shape(out, method=shape_method)
    for c in SHAPE_COLS:
        if c in shape.columns:
            out[c] = shape[c]

    if context is not None:
        for c in CONTEXT_COLS:
            if c in context.columns:
                out[c] = pd.to_numeric(context[c], errors="coerce").astype(float)
    return out


def enrich_board(con, season: int, board: pd.DataFrame, *, as_of=None,
                 ruleset: RuleSet | None = None, seed: int = 0, slots=None, n_teams: int = 10,
                 situation: bool = True, context: bool = True, live_vol: bool = True,
                 shape_method: str = "rank") -> pd.DataFrame:
    """A raw ADP board + the frozen risk/value context, ready for :func:`simulate_draft`.

    ``seed`` selects the shared Phase-5 draw cloud (T6) — pass the same seed the rest of a run uses
    and the ceiling an opponent chases is the ceiling everything else scored. The distribution is
    memoized per process, so the first call costs ~12 s for a fresh season and later ones are free.

    ``live_vol`` attaches :data:`LIVE_VOL_COLS` — the boom/bust pair re-measured on ``season − 1``
    (T22). On by default: the frozen pair is four seasons stale on any live board, and this is the
    board a human reads.

    ⚠ **T13 (fixed 2026-07-29):** the Phase-5 cloud used to move between processes, so the tests
    here assert on the **shape** of what a personality drafts (skew, group means) rather than on a
    named player. That discipline is worth keeping — but the underlying draw is now reproducible
    across processes (:func:`~fantasy_quant.data.db.deterministic_reads`), so a board built from the
    same ``(season, ruleset, seed)`` is the same board tomorrow.
    """
    ruleset = ruleset or RuleSet()
    if as_of is None:
        as_of = draft_date(con, season)
    dist = distribution.cached_distribution(con, season, ruleset=ruleset, seed=seed)[0]
    vb = value_board(con, season, as_of, ruleset=ruleset, slots=slots, n_teams=n_teams)
    # the step-3 context needs a `mean` to take shares of, so it is computed on the board *after*
    # the distribution join rather than from the raw frame.
    vol = None
    if live_vol:
        try:
            vol = live_volatility(con, season, ruleset=ruleset)
        except LookupError:
            # the earliest season in the store has no prior season to measure against; per this
            # module's contract that means *no column*, not a fabricated one. A source that exists
            # but is too old still raises — that is T22 itself.
            vol = None
    with_level = attach_enrichment(board, dist=dist, value=vb,
                                   rookie=rookie_flags(con, season),
                                   situation=situation_scores(con, season) if situation else None,
                                   live_vol=vol, shape_method=shape_method)
    if not context:
        return with_level
    ctx = role_shares(con, season, with_level)
    ctx["td_regression"] = td_regression(con, season, with_level)
    for c in CONTEXT_COLS:
        with_level[c] = pd.to_numeric(ctx[c], errors="coerce").astype(float)
    return with_level


def enrichment_coverage(board: pd.DataFrame) -> dict:
    """Per-column fill rate on an enriched board — the 16.13 done-bar, reported not assumed.

    Coverage is never expected to be 100 %: team defenses carry no projection at all and rookies
    without a prior season are exactly the population Phase 5 is thinnest on. The number is here so
    a drop is *visible* rather than silently becoming a pool of NaN a personality treats as neutral.
    """
    n = len(board)
    out = {"n_rows": int(n)}
    for c in (*DIST_COLS, *SHAPE_COLS, *VALUE_COLS, *CONTEXT_COLS, *LIVE_VOL_COLS,
              "rookie", "cos"):
        if c in board.columns:
            filled = int(pd.to_numeric(board[c], errors="coerce").notna().sum())
            out[c] = round(filled / n, 4) if n else 0.0
    return out
