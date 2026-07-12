"""Phase 13.1 — weekly re-projection (the value signal, refreshed as results land).

Preseason we calibrated each player's *season* distribution (Phase 5) and split it into weeks
(Phase 10). In-season we get new evidence every Sunday: a scalar **Kalman filter** on each player's
per-week scoring *level* folds those results into the preseason prior. The prior is worth
``prior_weeks`` pseudo-observations at the preseason level ``m0`` (per-active-week mean); each
played week ``y`` nudges the level toward what we've actually seen, weighted by the week-to-week
noise ``r`` (from his own 5.3 weekly CoV). ``process_var`` > 0 makes the level a slow random walk
so recent form outweighs a hot September — set it 0 to just "shrink preseason toward realized".

PIT / walk-forward: a re-projection *at* week ``t`` reads only weeks ``≤ t`` (strictly the past),
so the held-out weeks ``> t`` it is scored on never leak in. The preseason prior itself is PIT
(trained strictly before the season, via ``simulation.weekly.build_weekly_model``).

News slot (reserved, 2026-07-11 design note): :func:`reproject_week` accepts a ``news`` mapping —
a per-player, per-week level shift (points/week) a future Phase-12 news/NLP feature will fill (a
beat-writer snap-count note, a coordinator change). It is wired through the input contract now and
defaults to a no-op, so Phase 12 plugs in later without touching this signature.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from fantasy_quant.backtest.scoring import RuleSet, weekly_points
from fantasy_quant.simulation.weekly import OFFENSE, WeeklyModel, build_weekly_model

PRIOR_WEEKS = 5.0        # preseason prior strength, in equivalent weeks of observation (DEV-tuned)


@dataclass(frozen=True)
class RestOfSeason:
    """The re-projected rest-of-season weekly forecast after folding in weeks ``≤ through_week``.

    ``forecast`` columns: ``player_key · pos · team · n_played · level · level_sd · mean_week ·
    sd_week`` — ``level`` is the filtered per-week scoring mean (± ``level_sd`` parameter
    uncertainty), ``mean_week``/``sd_week`` the predictive per-week points (level + week-to-week
    noise) the start/sit optimizer (13.2) consumes."""
    forecast: pd.DataFrame
    through_week: int

    def week_mean(self) -> dict[str, float]:
        """``player_key -> predictive per-week points`` (the rest-of-season projection)."""
        return dict(zip(self.forecast["player_key"], self.forecast["mean_week"], strict=False))


def preseason_prior(model: WeeklyModel, *, prior_weeks: float = PRIOR_WEEKS,
                    n_weeks: int | None = None) -> pd.DataFrame:
    """Each offense player's Kalman initial state from the preseason :class:`WeeklyModel`.

    ``m0`` = season mean ÷ scheduled active (non-bye) weeks = the preseason per-week level; ``r`` =
    ``(wk_cov·m0)²`` the week-to-week observation variance (his own 5.3 volatility); ``p0`` = ``r /
    prior_weeks`` the prior variance on the level (a stronger ``prior_weeks`` trusts preseason more,
    updating slower). K/DST and cloudless players are excluded — re-projection speaks to modeled
    offense only."""
    n_weeks = int(n_weeks or model.n_weeks)
    s = model.summary
    s = s[s["pos"].isin(OFFENSE)].copy()
    has_bye = s["team"].map(lambda t: pd.notna(t) and str(t) in model.byes)
    active = (n_weeks - has_bye.astype(int)).clip(lower=1).to_numpy(float)
    m0 = np.clip(s["mean"].to_numpy(float) / active, 0.0, None)
    r = np.clip((s["wk_cov"].to_numpy(float) * m0) ** 2, 1e-6, None)
    p0 = r / max(float(prior_weeks), 1e-6)
    return pd.DataFrame({
        "player_key": s["player_key"].to_numpy(), "pos": s["pos"].to_numpy(),
        "team": s["team"].to_numpy(), "m0": m0, "r": r, "p0": p0,
        "active_weeks": active.astype(int),
    })


def reproject_week(prior: pd.DataFrame, realized: pd.DataFrame, through_week: int, *,
                   process_var: float = 0.0,
                   news: Mapping[str, float] | None = None) -> RestOfSeason:
    """Kalman-filter each player's per-week level from weeks ``≤ through_week`` of ``realized``.

    ``prior`` is :func:`preseason_prior`; ``realized`` is long ``player_key · week · points`` (only
    weeks a player actually recorded count as evidence — byes/DNPs are simply absent). ``news`` (the
    reserved Phase-12 slot) is an optional ``player_key -> level shift`` added to the projected
    mean; it defaults to a no-op.
    """
    news = news or {}
    obs = realized[realized["week"] <= int(through_week)]
    played = {pk: g.sort_values("week")["points"].to_numpy(float)
              for pk, g in obs.groupby("player_key")}

    keys, pos, team, npl, lvl, lvl_sd, mwk, swk = [], [], [], [], [], [], [], []
    for row in prior.itertuples(index=False):
        m, p, r = float(row.m0), float(row.p0), float(row.r)
        ys = played.get(row.player_key, ())
        for y in ys:                                  # scalar Kalman: predict (drift) then update
            p += process_var
            k = p / (p + r)
            m += k * (float(y) - m)
            p = (1.0 - k) * p
        m_adj = max(0.0, m + float(news.get(row.player_key, 0.0)))
        keys.append(row.player_key)
        pos.append(row.pos)
        team.append(row.team)
        npl.append(len(ys))
        lvl.append(m)
        lvl_sd.append(np.sqrt(p))
        mwk.append(m_adj)
        swk.append(np.sqrt(p + r))
    fc = pd.DataFrame({"player_key": keys, "pos": pos, "team": team, "n_played": npl,
                       "level": lvl, "level_sd": lvl_sd, "mean_week": mwk, "sd_week": swk})
    return RestOfSeason(forecast=fc, through_week=int(through_week))


# ------------------------------------------------------------------------------------------------
# the done-bar: re-projection beats the static preseason forecast out-of-sample (walk-forward)
# ------------------------------------------------------------------------------------------------
def realized_weekly(con, season: int, ruleset: RuleSet | None = None) -> pd.DataFrame:
    """Realized offense player-week points for ``season`` (``player_key · pos · week · points``),
    keyed by ``gsis_id`` to match the preseason prior."""
    wp = weekly_points(con, season, ruleset)
    wp = wp[wp["position"].isin(OFFENSE) & wp["gsis_id"].notna()]
    return pd.DataFrame({"player_key": wp["gsis_id"].astype(str), "pos": wp["position"],
                         "week": wp["week"].astype(int), "points": wp["points"].astype(float)})


def _cluster_bootstrap_ci(diff: np.ndarray, cluster: np.ndarray, n_boot: int = 2000,
                          seed: int = 0, alpha: float = 0.05) -> tuple[float, float]:
    """Percentile CI of the mean of ``diff`` resampling whole ``cluster``s (players) with
    replacement — the honest error bar when a player contributes many correlated player-weeks."""
    order = np.argsort(cluster, kind="stable")
    diff, cluster = diff[order], cluster[order]
    _, starts = np.unique(cluster, return_index=True)
    groups = np.split(diff, starts[1:])
    rng = np.random.default_rng(seed)
    n = len(groups)
    means = np.empty(n_boot)
    for b in range(n_boot):
        pick = rng.integers(0, n, n)
        means[b] = np.concatenate([groups[i] for i in pick]).mean()
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def reprojection_skill(con, season: int, *, splits=(4, 6, 8, 10), reg_weeks: int = 14,
                       ruleset: RuleSet | None = None, prior_weeks: float = PRIOR_WEEKS,
                       process_var: float = 0.0, n_draws: int = 800, n_boot: int = 2000,
                       seed: int = 0) -> dict:
    """Walk-forward skill of re-projection vs the static preseason level, for one ``season``.

    At each split week ``t`` we re-project from weeks ``≤ t`` and score the per-week forecast on the
    *future* played weeks ``t < w ≤ reg_weeks`` (MAE, points/week). The static baseline is the
    frozen preseason level ``m0``. Done-when: re-projection's MAE is lower and the per-player-
    clustered gain CI excludes 0. Offense only, PIT throughout.
    """
    model = build_weekly_model(con, season, ruleset, n_draws=n_draws, seed=seed)
    prior = preseason_prior(model, prior_weeks=prior_weeks)
    m0 = dict(zip(prior["player_key"], prior["m0"], strict=False))
    realized = realized_weekly(con, season, ruleset)
    realized = realized[realized["player_key"].isin(set(prior["player_key"]))]

    static_err, reproj_err, who = [], [], []
    for t in splits:
        rp = reproject_week(prior, realized, t, process_var=process_var).week_mean()
        fut = realized[(realized["week"] > t) & (realized["week"] <= reg_weeks)]
        for pk, y in zip(fut["player_key"], fut["points"], strict=False):
            base = m0.get(pk, 0.0)
            static_err.append(abs(base - y))
            reproj_err.append(abs(rp.get(pk, base) - y))
            who.append(pk)

    static_err = np.asarray(static_err)
    reproj_err = np.asarray(reproj_err)
    diff = static_err - reproj_err                       # + = re-projection has the lower error
    lo, hi = _cluster_bootstrap_ci(diff, np.asarray(who), n_boot=n_boot, seed=seed)
    return {
        "season": int(season), "n_player_weeks": int(len(diff)),
        "n_players": int(len(set(who))),
        "static_mae": float(static_err.mean()), "reproj_mae": float(reproj_err.mean()),
        "mae_gain": float(diff.mean()), "mae_gain_ci": (lo, hi),
        "beats_static": bool(lo > 0.0),
    }
