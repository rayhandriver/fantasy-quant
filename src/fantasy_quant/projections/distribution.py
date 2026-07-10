"""Phase 5 assembler — the per-player season distribution + the frozen output contract.

This is where the four factors compose into the object the personalization optimizer, the
copula/roster layer (Phase 8) and the season sim (Phase 10) all consume — a **Monte-Carlo sample
cloud per player**, plus summary columns for display and the risk dial:

    player_key · pos · mean · sd · q10 · q50 · q90 · boom_prob · bust_prob ·
    games_played_mean · ce_value

The sample model (documented, deliberately simple, no double-counting):

    Y = H · (G / G_ref)          H = if-healthy season points,  G = games played

* **H** is drawn from the conformal-calibrated conditional quantiles (5.1 fanned by level, 5.2
  widened to real 80% coverage). Its asymmetry *is* the boom skew — realized fantasy points are
  right-skewed, so the empirical quantiles already carry it (no separate skew injection needed).
* **G** ~ Beta-Binomial availability (5.4), normalized by ``G_ref`` = the conditional cohort's own
  mean games, so a typical-availability draw returns ≈ H (the injury downside lives entirely in the
  multiplier, never double-counted inside H's spread — the 4.4 conditional/unconditional
  discipline, now sampled).

Samples are the substrate; ``mean/sd/quantiles`` are percentiles of the cloud.
``boom_prob``/``bust_prob`` are the 5.3 *weekly* volatility signal (a different, complementary
axis, carried through for the dial).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.backtest.scoring import RuleSet
from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.projections import conformal, injury, quantile, variance

DIST_CONTRACT = ["player_key", "pos", "mean", "sd", "q10", "q50", "q90",
                 "boom_prob", "bust_prob", "games_played_mean", "ce_value"]
N_DRAWS = 2000


# --------------------------------------------------------------------------------------------
# pure samplers (unit-test targets)
# --------------------------------------------------------------------------------------------
def sample_from_quantiles(taus, qvals, u) -> np.ndarray:
    """Inverse-CDF sample from a monotone quantile grid, with linear tail extrapolation (≥0).

    ``taus`` ascending in (0,1), ``qvals`` the matching ascending values, ``u`` uniforms in (0,1).
    Tails beyond the outer τ are linearly extrapolated using the end slopes (floored at 0).
    """
    taus = np.asarray(taus, float)
    qvals = np.asarray(qvals, float)
    lo_slope = (qvals[1] - qvals[0]) / (taus[1] - taus[0])
    hi_slope = (qvals[-1] - qvals[-2]) / (taus[-1] - taus[-2])
    t0, t1 = max(1e-3, 2 * taus[0] - taus[1]), min(1 - 1e-3, 2 * taus[-1] - taus[-2])
    taus_e = np.concatenate([[t0], taus, [t1]])
    vals_e = np.concatenate([[max(0.0, qvals[0] + lo_slope * (t0 - taus[0]))],
                             qvals, [qvals[-1] + hi_slope * (t1 - taus[-1])]])
    return np.clip(np.interp(np.asarray(u, float), taus_e, vals_e), 0.0, None)


def sample_player_season(taus, qvals, avail_p, team_games, rho, g_ref,
                         rng: np.random.Generator, n: int, return_games: bool = False):
    """``n`` season-point draws for one player: healthy H (from quantiles) × normalized
    availability.

    ``G_ref`` is the conditional cohort's mean availability *fraction* (~0.93), so the availability
    multiplier must be a fraction too: we divide the sampled games *count* by the player's team
    games to a fraction before normalizing. A typical-availability draw (fraction ≈ G_ref) returns
    ≈ H; the injury downside lives entirely here, never double-counted inside H's spread.

    ``return_games=True`` additionally returns the per-draw games count ``g`` (same rng stream —
    the draws are identical either way). The Phase-10 weekly-grain layer needs each draw's own
    ``g`` so a low season total caused by missed games is spread over correspondingly few weeks.
    """
    tg = int(round(team_games))
    h = sample_from_quantiles(taus, qvals, rng.uniform(0.0, 1.0, n))
    g = injury.sample_games(avail_p, tg, rho, rng, n)
    avail_frac = g / max(tg, 1)
    y = np.clip(h * (avail_frac / max(g_ref, 1e-6)), 0.0, None)
    return (y, g) if return_games else y


# --------------------------------------------------------------------------------------------
# conformal calibration of the conditional band (fit on a held-out prior season)
# --------------------------------------------------------------------------------------------
def _conformal_adjustment(con, train_seasons, ruleset, correction, taus) -> dict:
    """Per-position CQR ``d`` widening the [q10,q90] band to real 80% coverage, from the latest
    training season held out as the conformal calibration split."""
    train_seasons = sorted(train_seasons)
    if len(train_seasons) < 3:
        return {}
    cal_seasons, fit_seasons = train_seasons[-2:], train_seasons[:-2]
    models = quantile.fit_quantile_models(
        quantile.conditional_training_frame(con, fit_seasons, ruleset, correction), taus)
    cal = quantile.conditional_training_frame(con, cal_seasons, ruleset, correction)
    lo, hi = [], []
    for pos, idx in cal.groupby("pos").groups.items():
        q = quantile.predict_quantiles(
            models, pos, cal.loc[idx, "calibrated_mean"].to_numpy(), taus)
        lo.append(pd.Series(q[:, 0], index=idx))
        hi.append(pd.Series(q[:, -1], index=idx))
    cal = cal.assign(_lo=pd.concat(lo) if lo else np.nan, _hi=pd.concat(hi) if hi else np.nan)
    cal = cal.dropna(subset=["_lo", "_hi"])
    return conformal.fit_cqr(cal, "_lo", "_hi")


def conditional_avail_ref(con, seasons, floor: float = 0.85) -> float:
    """G_ref as a *fraction*: the conditional (available) cohort's mean games-played fraction
    (~0.93)."""
    gp = injury.games_played(con, seasons)
    frac = (gp["games"] / gp["team_games"]).clip(0, 1)
    cohort = frac[frac >= floor]
    return float(cohort.mean()) if len(cohort) else 0.93


# --------------------------------------------------------------------------------------------
# the assembler
# --------------------------------------------------------------------------------------------
def assemble_distribution(con, season: int, ruleset: RuleSet | None = None, n_draws: int = N_DRAWS,
                          train_seasons=None, seed: int = 0, return_games: bool = False):
    """Build the season distribution for every player on ``season``'s board.

    Returns ``(summary_df, samples)`` where ``summary_df`` has the contract columns (minus
    ``ce_value``, added by :mod:`fantasy_quant.valuation.utility`) and ``samples`` is an
    ``(n_players, n_draws)`` array aligned to ``summary_df`` rows. With ``return_games=True``
    returns ``(summary_df, samples, games)`` — the per-draw games-played counts aligned to
    ``samples`` (identical draws; the Phase-10 weekly layer consumes ``games``).
    """
    ruleset = ruleset or RuleSet()
    if train_seasons is None:
        train_seasons = [s for s in DEV_SEASONS if s < season] or list(DEV_SEASONS)
    taus = quantile.QUANTILE_TAUS
    correction = quantile.dev_correction(con, ruleset)

    qdf = quantile.quantile_projection(con, season, ruleset, taus, train_seasons, correction)
    adj = _conformal_adjustment(con, train_seasons, ruleset, correction, taus)
    g_ref = conditional_avail_ref(con, train_seasons)
    avail = injury.availability_projection(con, season, train_seasons)
    vol = variance.weekly_volatility(con, [max(train_seasons)], ruleset)  # prior-season boom/bust

    qcols = [f"q{int(t * 100)}" for t in taus]
    df = qdf.merge(avail[["player_key", "avail_p", "team_games", "rho"]],
                   on="player_key", how="left")
    df = df.merge(vol[["player_key", "boom_prob", "bust_prob"]], on="player_key", how="left")
    df = df.dropna(subset=qcols).reset_index(drop=True)

    # sensible fallbacks for players missing an availability/volatility row (e.g. rookies).
    med_p = float(df["avail_p"].median()) if df["avail_p"].notna().any() else 0.85
    df["avail_p"] = df["avail_p"].fillna(med_p)
    df["team_games"] = df["team_games"].fillna(quantile.season_games(season))
    df["rho"] = df["rho"].fillna(df["rho"].median() if df["rho"].notna().any() else 0.15)
    df[["boom_prob", "bust_prob"]] = df[["boom_prob", "bust_prob"]].fillna(0.0)

    rng = np.random.default_rng(seed)
    samples = np.empty((len(df), n_draws))
    games = np.empty((len(df), n_draws)) if return_games else None
    for i, row in df.iterrows():
        qv = np.sort(row[qcols].to_numpy(float))
        qv[0] = max(0.0, qv[0] - adj.get(row["pos"], 0.0))          # conformal-widen the band
        qv[-1] = qv[-1] + adj.get(row["pos"], 0.0)
        drawn = sample_player_season(taus, qv, row["avail_p"], row["team_games"],
                                     row["rho"], g_ref, rng, n_draws,
                                     return_games=return_games)
        if return_games:
            samples[i], games[i] = drawn
        else:
            samples[i] = drawn

    pcts = np.percentile(samples, [10, 50, 90], axis=1)
    out = pd.DataFrame({
        "player_key": df["player_key"], "pos": df["pos"],
        "mean": samples.mean(axis=1), "sd": samples.std(axis=1),
        "q10": pcts[0], "q50": pcts[1], "q90": pcts[2],
        "boom_prob": df["boom_prob"], "bust_prob": df["bust_prob"],
        "games_played_mean": df["avail_p"] * df["team_games"],
    })
    return (out, samples, games) if return_games else (out, samples)


# --------------------------------------------------------------------------------------------
# T6 — one shared draw cloud per (season, ruleset, n_draws, seed)
# --------------------------------------------------------------------------------------------
_DIST_CACHE: dict[tuple, tuple] = {}


def cached_distribution(con, season: int, ruleset: RuleSet | None = None, n_draws: int = N_DRAWS,
                        seed: int = 0) -> tuple:
    """Memoized :func:`assemble_distribution` — the **single source of the draw cloud** both the
    draft optimizer (``optimizer.assemble_value``) and the season sim
    (``weekly.build_weekly_model``) both read, so they can never silently diverge (T6).

    Always computed ``return_games=True`` and cached as ``(summary, samples, games)`` keyed on
    ``(season, ruleset_json, n_draws, seed)`` — mirroring ``_CORR_CACHE``. ``samples`` is
    bit-identical whether or not ``games`` is captured (same rng stream — see
    :func:`sample_player_season`), so the games-free consumer slices ``[:2]`` off the *same* cloud.
    Thread one explicit ``seed`` from a run's entry point and the draft and sim reference the same
    joint draws.
    """
    rs = ruleset or RuleSet()
    key = (int(season), rs.model_dump_json(), int(n_draws), int(seed))
    if key not in _DIST_CACHE:
        _DIST_CACHE[key] = assemble_distribution(con, season, rs, n_draws=n_draws, seed=seed,
                                                 return_games=True)
    return _DIST_CACHE[key]
