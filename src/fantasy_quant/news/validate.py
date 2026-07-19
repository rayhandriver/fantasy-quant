"""Phase 12.4 — signal validation (the keep-or-drop gate: does the news signal improve decisions
OOS?).

The project's pattern is a gate that is allowed to say *no* (props shelved, Phase 7 dropped). Here
it says
a qualified *yes for injuries, no for depth charts*, and this module is where the yes is earned: a
news
signal is kept only if it **lowers out-of-sample forecast error where it applies**, on a strict
walk-forward.

The mechanism is the reserved Phase-12 slot in 13.1. :func:`reproject_week` already accepts a
``news``
mapping (a per-player, per-week level shift) that has defaulted to a no-op since it was built.
Phase 12
fills it: at decision week ``t`` (PIT — injury reports are filed before week-``t`` games), we price
each
active injury designation into a level shift and hand it to the re-projector, so the start/sit
optimizer
(13.2) benches a player the report has flagged. The **extraction** (status → severity) is 12.2's
job; the
**pricing** (status → a points multiplier) is the deterministic core's, calibrated here on DEV — the
guardrail exactly (the LLM never computes the number that must be correct).

Done-when (keep bar): the news-aware weekly forecast beats the injury-blind 13.1 forecast on
realized
points **on the designated subset** (where the signal applies), with a player-clustered CI
excluding 0.
We also report the (diluted) leaguewide effect honestly. Depth-change events failed the 12.3
direction
test, so only the injury signal is wired.
"""

from __future__ import annotations

import numpy as np

from fantasy_quant.backtest.scoring import RuleSet
from fantasy_quant.inseason.reproject import (
    PRIOR_WEEKS,
    preseason_prior,
    realized_weekly,
    reproject_week,
)
from fantasy_quant.news import event_study, sources
from fantasy_quant.simulation.weekly import build_weekly_model

# a fallback used only when a status is absent from the DEV-derived table (kept for robustness).
DEFAULT_MULTIPLIER = {"Out": 0.0, "Injured Reserve": 0.0, "IR": 0.0,
                      "Doubtful": 0.02, "Questionable": 0.56, "Probable": 0.95}
# regular-season decision weeks the gate forecasts (module-level so it isn't a call in a default).
GATE_SPLITS = tuple(range(2, 15))


def injury_multipliers(con, seasons, ruleset: RuleSet | None = None) -> dict[str, float]:
    """Per-status availability multiplier ``E[points | status] / baseline``, calibrated on
    ``seasons``.

    Derived from the 12.3 :func:`event_study.injury_impact` table (mean points that week ÷ the
    player's
    clean-week baseline), clipped to [0, 1]. An ``Out`` comes out ≈ 0 (a stale lineup should zero
    him),
    a ``Questionable`` ≈ 0.55. PIT when ``seasons`` are strictly prior to the forecast season.
    """
    imp = event_study.injury_impact(con, seasons, ruleset, n_boot=1)  # CI unused here → cheap
    mult = dict(DEFAULT_MULTIPLIER)
    for status, d in imp.get("per_status", {}).items():
        base = d["baseline_points"]
        if base > 1e-6:
            mult[status] = float(np.clip(d["mean_points"] / base, 0.0, 1.0))
    return mult


def news_level_shift(levels: dict[str, float], designations: dict[str, str],
                     multipliers: dict[str, float]) -> dict[str, float]:
    """The 13.1 ``news``-slot filler: a per-player level shift for one week.

    ``levels`` is ``player_key -> current forecast level`` (from 13.1, injury-blind for this week);
    ``designations`` is ``player_key -> report_status`` in force this week; ``multipliers`` is
    :func:`injury_multipliers`. The shift is ``level·(mult − 1)`` so
    ``level + shift = level·mult`` — i.e. an ``Out`` player is knocked toward 0. Pure; only
    designated players get a (non-zero) entry."""
    shift = {}
    for pk, status in designations.items():
        m = multipliers.get(status, 1.0)
        if m < 1.0:
            shift[pk] = levels.get(pk, 0.0) * (m - 1.0)
    return shift


# ------------------------------------------------------------------------------------------------
# the keep-or-drop gate: news-aware weekly forecast vs the injury-blind 13.1 forecast
# ------------------------------------------------------------------------------------------------
def _cluster_ci(diff: np.ndarray, cluster: np.ndarray, n_boot: int, seed: int,
                alpha: float = 0.05) -> tuple[float, float]:
    if len(diff) == 0:
        return (float("nan"), float("nan"))
    order = np.argsort(cluster, kind="stable")
    diff, cluster = diff[order], cluster[order]
    _, starts = np.unique(cluster, return_index=True)
    groups = np.split(diff, starts[1:])
    rng = np.random.default_rng(seed)
    n = len(groups)
    means = np.array([np.concatenate([groups[i] for i in rng.integers(0, n, n)]).mean()
                      for _ in range(n_boot)])
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def news_forecast_gain(con, season: int, *, splits=GATE_SPLITS, reg_weeks: int = 14,
                       ruleset: RuleSet | None = None, train_seasons=None,
                       prior_weeks: float = PRIOR_WEEKS, n_draws: int = 600, n_boot: int = 2000,
                       seed: int = 0) -> dict:
    """Walk-forward keep-or-drop gate for the injury signal, for one ``season``.

    At each week ``t`` we build the 13.1 re-projected level through week ``t−1`` (injury-blind for
    week
    ``t``), then form two one-week forecasts for week ``t``: the **baseline** (that level) and the
    **news-aware** (level × the week-``t`` injury multiplier, via :func:`news_level_shift`). Both
    are
    scored on realized week-``t`` points (MAE). The scoring universe per week is players who
    **played**
    that week **or carried a designation** — the set where a start/sit call is real (byes
    excluded). We
    report the error gain overall and on the **designated subset** (where the signal applies), each
    with
    a player-clustered CI. PIT throughout: injury reports for week ``t`` are known before week-``t``
    games; the re-projection reads only weeks ``≤ t−1``; multipliers train on strictly-prior
    seasons.
    """
    from fantasy_quant.config import DEV_SEASONS
    if train_seasons is None:
        train_seasons = [s for s in DEV_SEASONS if s != season] or list(DEV_SEASONS)
    mult = injury_multipliers(con, train_seasons, ruleset)

    model = build_weekly_model(con, season, ruleset, n_draws=n_draws, seed=seed)
    prior = preseason_prior(model, prior_weeks=prior_weeks)
    m0 = dict(zip(prior["player_key"], prior["m0"], strict=False))
    board = set(prior["player_key"])
    realized = realized_weekly(con, season, ruleset)
    realized = realized[realized["player_key"].isin(board)]
    rp = {(r.player_key, int(r.week)): float(r.points) for r in realized.itertuples(index=False)}

    inj = sources.injury_events(con, [season])
    # designations in force per (player, week): player_key -> status, per week.
    desig_by_week: dict[int, dict[str, str]] = {}
    for e in inj.itertuples(index=False):
        if e.player_key in board:
            desig_by_week.setdefault(int(e.week), {})[e.player_key] = str(e.status)

    base_err, news_err, who, is_desig = [], [], [], []
    for t in splits:
        if t < 1 or t > reg_weeks:
            continue
        levels = reproject_week(prior, realized, t - 1).week_mean()
        desig = desig_by_week.get(t, {})
        shift = news_level_shift(levels, desig, mult)
        # universe: players who played week t, plus any designated player (who may have scored 0).
        played = {pk for (pk, w) in rp if w == t}
        universe = (played | set(desig)) & board
        for pk in universe:
            base_fc = levels.get(pk, m0.get(pk, 0.0))
            news_fc = max(0.0, base_fc + shift.get(pk, 0.0))
            y = rp.get((pk, t), 0.0)
            base_err.append(abs(base_fc - y))
            news_err.append(abs(news_fc - y))
            who.append(pk)
            is_desig.append(pk in desig)

    base_err = np.asarray(base_err)
    news_err = np.asarray(news_err)
    who = np.asarray(who)
    is_desig = np.asarray(is_desig, bool)
    diff = base_err - news_err                         # + = news forecast has the lower error
    lo, hi = _cluster_ci(diff, who, n_boot, seed)
    dlo, dhi = _cluster_ci(diff[is_desig], who[is_desig], n_boot, seed)
    return {
        "season": int(season), "n_player_weeks": int(len(diff)),
        "n_designated": int(is_desig.sum()),
        "base_mae": float(base_err.mean()) if len(base_err) else float("nan"),
        "news_mae": float(news_err.mean()) if len(news_err) else float("nan"),
        "mae_gain": float(diff.mean()) if len(diff) else float("nan"),
        "mae_gain_ci": (lo, hi),
        "designated_base_mae": float(base_err[is_desig].mean()) if is_desig.any() else float("nan"),
        "designated_news_mae": float(news_err[is_desig].mean()) if is_desig.any() else float("nan"),
        "designated_gain": float(diff[is_desig].mean()) if is_desig.any() else float("nan"),
        "designated_gain_ci": (dlo, dhi),
        "multipliers": mult,
        "beats_on_designated": bool(dlo > 0.0),
    }
