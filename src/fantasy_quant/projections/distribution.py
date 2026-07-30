"""Phase 5 assembler — the per-player season distribution + the frozen output contract.

This is where the four factors compose into the object the personalization optimizer, the
copula/roster layer (Phase 8) and the season sim (Phase 10) all consume — a **Monte-Carlo sample
cloud per player**, plus summary columns for display and the risk dial:

    player_key · pos · mean · sd · q10 · q50 · q90 · boom_prob · bust_prob ·
    games_played_mean · ce_value

The sample model (documented, deliberately simple, no double-counting):

    Y = H · (G / G_ref) · R      H = if-healthy points,  G = games played,  R = role survival

* **H** is drawn from the conformal-calibrated conditional quantiles (5.1 fanned by level, 5.2
  widened to real 80% coverage). Its asymmetry *is* the boom skew — realized fantasy points are
  right-skewed, so the empirical quantiles already carry it (no separate skew injection needed).
* **G** ~ Beta-Binomial availability (5.4), normalized by ``G_ref`` = the conditional cohort's own
  mean games, so a typical-availability draw returns ≈ H (the injury downside lives entirely in the
  multiplier, never double-counted inside H's spread — the 4.4 conditional/unconditional
  discipline, now sampled). **T3-A:** rookies/backups (no prior-season hazard) draw ``G`` from a
  ``(pos × draft-capital)`` cohort prior — a lower mean and fatter lost-season tail than the league
  median the old single fallback used.
* **R** (T3-B) ~ a Bernoulli role-survival haircut (``R ≤ 1``): with a per-(pos, projected-role)
  probability a healthy player loses his role and keeps only a downside fraction of H. It widens the
  **left tail / games≈0 region** — the dominant *unconditional* (draft-day) coverage miss: a
  projected body who washes out. Applied to established, deep-projected players only (the cohort
  prior already owns the rookie/backup downside), so injury and role loss never double-count.

Samples are the substrate; ``mean/sd/quantiles`` are percentiles of the cloud.
``boom_prob``/``bust_prob`` are the 5.3 *weekly* volatility signal (a different, complementary
axis, carried through for the dial).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.backtest.scoring import RuleSet
from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.data import db
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
                         rng: np.random.Generator, n: int, return_games: bool = False,
                         p_crater: float = 0.0, crater_avail: float = 0.35,
                         keep_frac: float = 1.0):
    """``n`` season-point draws for one player: healthy H (from quantiles) × normalized
    availability × role-survival haircut.

    ``G_ref`` is the conditional cohort's mean availability *fraction* (~0.93), so the availability
    multiplier must be a fraction too: we divide the sampled games *count* by the player's team
    games to a fraction before normalizing. A typical-availability draw (fraction ≈ G_ref) returns
    ≈ H; the injury downside lives entirely here, never double-counted inside H's spread.

    **T3-B role-survival mixture**: with probability ``p_crater`` the player's season "goes bad"
    (benched/buried/hurt) — his games are drawn from a low ``crater_avail`` instead of his normal
    availability and he keeps only ``keep_frac`` of per-game production. This bad branch *replaces*
    the normal branch (not additive), so it fattens the **left tail / games≈0 region** — the
    dominant unconditional miss — without lowering the healthy upper tail (``q90``); injury is never
    double-counted. ``p_crater = 0`` ⇒ the pre-T3 behavior. The per-draw ``g`` returned reflects the
    crater, so the weekly-grain layer spreads a bad season over correspondingly few weeks.

    ``return_games=True`` additionally returns the per-draw games count ``g`` (same rng stream —
    the draws are identical either way).
    """
    tg = int(round(team_games))
    h = sample_from_quantiles(taus, qvals, rng.uniform(0.0, 1.0, n))
    g = injury.sample_games(avail_p, tg, rho, rng, n)
    r = 1.0
    if p_crater > 0.0:
        crater = rng.random(n) < p_crater
        g_lost = injury.sample_games(crater_avail, tg, min(rho * 1.5, 0.5), rng, n)
        g = np.where(crater, g_lost, g)
        r = np.where(crater, keep_frac, 1.0)
    avail_frac = g / max(tg, 1)
    y = np.clip(h * (avail_frac / max(g_ref, 1e-6)) * r, 0.0, None)
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

    ★ **Every read below runs under** :func:`~fantasy_quant.data.db.deterministic_reads` **(T13).**
    DuckDB's parallel float aggregation is order-dependent, so without the pin the training frames
    — and therefore the fitted quantile/hazard coefficients, and therefore every per-player draw —
    differ in the last bits from process to process. Same seed now means the same cloud tomorrow,
    which is what lets an app publish a player's q10 and a mock board be rebuilt from a seed. The
    *model* is unchanged: this picks one of the runs the old code was already alternating between
    (dress-rehearsal coverage 75.5 ↔ 76.5 %), it does not re-specify anything.
    """
    ruleset = ruleset or RuleSet()
    if train_seasons is None:
        train_seasons = [s for s in DEV_SEASONS if s < season] or list(DEV_SEASONS)
    taus = quantile.QUANTILE_TAUS
    with db.deterministic_reads(con):
        correction = quantile.dev_correction(con, ruleset)

        qdf = quantile.quantile_projection(con, season, ruleset, taus, train_seasons, correction)
        adj = _conformal_adjustment(con, train_seasons, ruleset, correction, taus)
        g_ref = conditional_avail_ref(con, train_seasons)
        avail = injury.availability_projection(con, season, train_seasons)
        # ⚠ T22: `max(train_seasons)` is the newest DEV season, which for any live board is 2022.
        # The frozen contract keeps this column as it is; `draft/enrichment.live_volatility` is the
        # honest read for a board a human looks at.
        vol = variance.weekly_volatility(con, [max(train_seasons)], ruleset)
        # The three T3 lookups are read here rather than at their point of use for one reason: they
        # are DuckDB aggregates, so they belong inside the determinism pin with every other read.
        cohort = injury.cohort_availability_prior(con, train_seasons)
        tiers = injury.player_tiers(con, [season])[["player_key", "capital_tier"]]
        retention = injury.role_retention(con, train_seasons)

    qcols = [f"q{int(t * 100)}" for t in taus]
    df = qdf.merge(avail[["player_key", "avail_p", "team_games", "rho"]],
                   on="player_key", how="left")
    df = df.merge(vol[["player_key", "boom_prob", "bust_prob"]], on="player_key", how="left")
    df = df.dropna(subset=qcols).reset_index(drop=True)

    # T3-A: players without a hazard row are the rookie/backup COHORT — route them to the cohort
    # availability prior (keyed on pos × draft-capital tier) instead of one shared median. Their
    # downside lives in a low avail_p + fat rho; established contributors keep the hazard estimate.
    is_cohort = df["avail_p"].isna().to_numpy()
    df = df.merge(tiers, on="player_key", how="left")
    df["capital_tier"] = df["capital_tier"].fillna("lo")
    for i in np.flatnonzero(is_cohort):
        ap, rh = injury.lookup_cohort(cohort, df.at[i, "pos"], df.at[i, "capital_tier"])
        df.at[i, "avail_p"], df.at[i, "rho"] = ap, rh
    df["team_games"] = df["team_games"].fillna(quantile.season_games(season))
    df["rho"] = df["rho"].fillna(df["rho"].median() if df["rho"].notna().any() else 0.15)
    df[["boom_prob", "bust_prob"]] = df[["boom_prob", "bust_prob"]].fillna(0.0)

    # T3-B: the role-loss washout mixture, applied to ESTABLISHED players projected in a **deep**
    # role only (cohort players' downside is already in their low availability; elite/starter
    # washouts are injury, already in the hazard G — restricting to deep is the pure role-loss
    # channel and keeps injury from being double-counted). Projected role tier comes from the
    # calibrated projection rank within position vs the startable (replacement) rank.
    from fantasy_quant.backtest.metrics import replacement_ranks
    from fantasy_quant.draft.simulator import RosterSlots
    startable = replacement_ranks(RosterSlots(), n_teams=10)
    df["proj_rank"] = df.groupby("pos")["calibrated_mean"].rank(ascending=False, method="first")
    p_crater = np.zeros(len(df))
    crater_avail = np.full(len(df), 0.35)
    keep_frac = np.ones(len(df))
    for i in range(len(df)):
        if is_cohort[i]:
            continue
        tier = injury.role_tier(df.at[i, "proj_rank"], startable.get(df.at[i, "pos"], 24))
        if tier != "deep":
            continue
        p_crater[i], crater_avail[i], keep_frac[i] = injury.lookup_role(
            retention, df.at[i, "pos"], tier)

    rng = np.random.default_rng(seed)
    samples = np.empty((len(df), n_draws))
    games = np.empty((len(df), n_draws)) if return_games else None
    for i, row in df.iterrows():
        qv = np.sort(row[qcols].to_numpy(float))
        qv[0] = max(0.0, qv[0] - adj.get(row["pos"], 0.0))          # conformal-widen the band
        qv[-1] = qv[-1] + adj.get(row["pos"], 0.0)
        drawn = sample_player_season(taus, qv, row["avail_p"], row["team_games"],
                                     row["rho"], g_ref, rng, n_draws,
                                     return_games=return_games,
                                     p_crater=float(p_crater[i]),
                                     crater_avail=float(crater_avail[i]),
                                     keep_frac=float(keep_frac[i]))
        if return_games:
            samples[i], games[i] = drawn
        else:
            samples[i] = drawn

    # T31 — the consensus level cap, applied to the DRAWS rather than to the quantile band. `Y` is
    # linear in the band, so scaling every draw is exactly equivalent to scaling the band, and it
    # sidesteps the `max(0, q10 - adj)` clamp's non-linearity entirely. `games` is deliberately
    # untouched: availability was never the thing that was wrong. Non-live rows scale by exactly
    # 1.0, so every historical board — including the unspent 2025 holdout — is bit-identical.
    lvl_scale = quantile.consensus_level_cap(samples.mean(axis=1), df["proj_points"], df["source"],
                                             df["avail_p"], g_ref)
    samples *= lvl_scale[:, None]

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


# --------------------------------------------------------------------------------------------
# T17 — the level guard: does the assembled mean still resemble the projection it is built from?
# --------------------------------------------------------------------------------------------
#: Admissible ``sum(mean) / sum(proj_points)`` over the top of the board. The distribution is the
#: projection times an availability fraction, so this ratio *should* sit meaningfully below 1 — it
#: is the games-played haircut, and 2019–2025 measure it at a very tight **0.638–0.683**. The band
#: is deliberately much wider than that spread because it is a **structural** guard, not a
#: calibration target: below the floor the availability multiplier is eating almost half the
#: projection (T17's live-2026 board scored **0.37** — every player on the cohort prior), above the
#: ceiling availability is barely being applied at all (an inert hazard). Both are the kind of
#: break that should stop a run, and neither is reachable by ordinary year-to-year drift.
LEVEL_BAND: tuple[float, float] = (0.55, 0.85)
LEVEL_TOP_N = 60


def level_ratio(dist: pd.DataFrame, proj: pd.DataFrame, top_n: int = LEVEL_TOP_N) -> float:
    """``sum(mean) / sum(proj_points)`` over the ``top_n`` players by projection.

    Restricted to the top of the board on purpose: that is the part a user actually reads, and it
    is the part where both frames agree on who exists, so the ratio measures the availability
    haircut rather than a difference in universe.
    """
    m = dist.merge(proj[["player_key", "proj_points"]], on="player_key", how="inner")
    if m.empty:
        raise ValueError("level_ratio: distribution and projection share no players")
    top = m.sort_values("proj_points", ascending=False).head(int(top_n))
    denom = float(top["proj_points"].sum())
    if denom <= 0:
        raise ValueError("level_ratio: projection sums to zero over the top of the board")
    return float(top["mean"].sum()) / denom


def assert_level_band(dist: pd.DataFrame, proj: pd.DataFrame, season: int,
                      band: tuple[float, float] = LEVEL_BAND,
                      top_n: int = LEVEL_TOP_N) -> float:
    """Assert :func:`level_ratio` sits inside ``band``; return it. The check that would have caught
    T17 the day the 2026 board landed."""
    r = level_ratio(dist, proj, top_n)
    lo, hi = band
    assert lo <= r <= hi, (
        f"{season}: distribution/projection level ratio {r:.3f} outside [{lo}, {hi}] over the "
        f"top {top_n}. Below the floor usually means availability collapsed to the cohort prior "
        f"(cf. docs/TECH-DEBT.md T17); above the ceiling means the hazard is not being applied.")
    return r
