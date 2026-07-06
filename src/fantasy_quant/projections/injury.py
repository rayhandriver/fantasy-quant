"""Phase 5.4 — availability: a discrete-time weekly hazard → games-played distribution.

The 4.4 calibration found the mean's biggest *level* miss isn't mis-ranking — it's **games-played
attrition**: projected players who lose chunks of the season to injury. Phase 5.1–5.3 model the
*if-healthy* season; this module models the **other factor** — how many games a player actually
plays — so the assembler can multiply the two and reproduce the honest, unconditional (draft-day)
distribution without double-counting the injury downside inside the healthy spread.

We fit a **discrete-time availability hazard**: on the player-week grid (one row per player per
team game week), a logistic regression of ``P(available that week)`` on age, position, prior-season
availability, and week — the discrete-time-survival formulation (a logit on person-period rows *is*
the hazard model, and it is the right tool for a 17-week horizon, vs. a continuous-time Cox). We
model **week-level availability** (players return from injury), not an absorbing first-injury
survival, because season-long games-played — not time-to-first-injury — is what the draft dial
needs.

Games-played is then a **Beta-Binomial** over the team's games: mean from the fitted availability,
with an empirically-estimated over-dispersion ``ρ`` so the distribution keeps the fat *lost-season*
tail (injuries are lumpy — a torn ACL zeroes the rest of the year — which a plain Binomial would
miss). PIT: fit on strictly-prior DEV seasons. Documented limitation: the grid conditions on ≥1
appearance, so a player who misses an *entire* season pre-Week-1 is under-counted (the 4.4
unconditional haircut partly covers it).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.features import player as player_features_mod

SKILL = ("QB", "RB", "WR", "TE")
_CONT = ["age", "prior_avail", "week_norm"]
_POS_DUMMIES = ["is_RB", "is_WR", "is_TE"]        # QB is the reference level
FEATURES = _CONT + _POS_DUMMIES


def _season_games(season: int) -> int:
    return 16 if int(season) < 2021 else 17


# --------------------------------------------------------------------------------------------
# the player-week availability grid
# --------------------------------------------------------------------------------------------
def _played(con, seasons) -> pd.DataFrame:
    ss = ",".join(str(int(s)) for s in seasons)
    return con.execute(
        f"""
        SELECT season, gsis_id, week, recent_team AS team, position
        FROM weekly
        WHERE season IN ({ss}) AND season_type='REG'
          AND position IN ('QB','RB','WR','TE') AND gsis_id IS NOT NULL
        """
    ).df()


def _team_weeks(con, seasons) -> pd.DataFrame:
    ss = ",".join(str(int(s)) for s in seasons)
    return con.execute(
        f"""SELECT DISTINCT season, recent_team AS team, week FROM weekly
            WHERE season IN ({ss}) AND season_type='REG'"""
    ).df()


def games_played(con, seasons) -> pd.DataFrame:
    """Per (season, player) primary team, position, games played and team games. One
    row/player-season."""
    played = _played(con, seasons)
    if played.empty:
        return pd.DataFrame(columns=["season", "player_key", "pos", "team", "games", "team_games"])
    # primary team & position by appearances
    prim = (played.groupby(["season", "gsis_id", "team", "position"]).size()
            .reset_index(name="g").sort_values("g")
            .groupby(["season", "gsis_id"]).tail(1)[["season", "gsis_id", "team", "position"]])
    gp = (played.groupby(["season", "gsis_id"])["week"].nunique().reset_index(name="games"))
    tw = _team_weeks(con, seasons).groupby(["season", "team"])["week"].nunique().reset_index(
        name="team_games")
    out = prim.merge(gp, on=["season", "gsis_id"]).merge(tw, on=["season", "team"], how="left")
    out = out.rename(columns={"gsis_id": "player_key", "position": "pos"})
    out["team_games"] = out["team_games"].fillna(out["season"].map(_season_games))
    return out


def availability_frame(con, seasons, min_prior_games: int = 8) -> pd.DataFrame:
    """The person-period grid: one row per player per team game week with ``available`` +
    covariates.

    ``available=1`` if the player recorded stats that week, else 0 (injury/inactive). Covariates:
    ``age`` (as-of season), position dummies, ``prior_avail`` (prior-season games/team-games),
    ``week_norm`` (week/season_games). PIT-safe: covariates predate outcomes.

    The universe is **established contributors** (prior-season games ≥ ``min_prior_games``): the
    availability multiplier applies to *projected starters*, so we model *their* injury attrition —
    not the roster-depth churn of 3rd-string players who never play (that would read as 20%
    "availability" and swamp the real injury signal). Rookies/backups fall to the
    median-availability fallback in the assembler.
    """
    played = _played(con, seasons)
    if played.empty:
        return pd.DataFrame(columns=["season", "player_key", "pos", "available", *FEATURES])
    prim = (played.groupby(["season", "gsis_id", "team", "position"]).size()
            .reset_index(name="g").sort_values("g")
            .groupby(["season", "gsis_id"]).tail(1)[["season", "gsis_id", "team", "position"]])
    played_set = set(zip(played["season"], played["gsis_id"], played["week"], strict=False))

    tw = _team_weeks(con, seasons)
    grid = prim.merge(tw, on=["season", "team"], how="left")   # player × their team's game weeks
    grid["available"] = [
        float((s, g, w) in played_set)
        for s, g, w in zip(grid["season"], grid["gsis_id"], grid["week"], strict=False)]

    # prior-season availability (durability persistence) + established-contributor gate
    prior = games_played(con, [s - 1 for s in seasons])
    prior["prior_avail"] = (prior["games"] / prior["team_games"]).clip(0, 1)
    prior["season"] = prior["season"] + 1          # value it in the following season
    prior = prior.rename(columns={"player_key": "gsis_id", "games": "prior_games"})
    grid = grid.merge(prior[["season", "gsis_id", "prior_avail", "prior_games"]],
                      on=["season", "gsis_id"], how="inner")       # drop non-contributors / rookies
    grid = grid[grid["prior_games"] >= min_prior_games]

    # age (as-of season) from player features
    ages = []
    for s in seasons:
        pf = player_features_mod.player_features(con, [int(s)])[["gsis_id", "age"]].copy()
        pf["season"] = int(s)
        ages.append(pf)
    age = pd.concat(ages, ignore_index=True)
    grid = grid.merge(age, on=["season", "gsis_id"], how="left")
    grid["age"] = grid["age"].fillna(grid["age"].median())

    grid["week_norm"] = grid["week"] / grid["season"].map(_season_games)
    for pos in ("RB", "WR", "TE"):
        grid[f"is_{pos}"] = (grid["position"] == pos).astype(float)
    return grid.rename(columns={"gsis_id": "player_key", "position": "pos"})[
        ["season", "player_key", "pos", "team", "week", "available", *FEATURES]]


# --------------------------------------------------------------------------------------------
# the hazard model + dispersion (pure-ish)
# --------------------------------------------------------------------------------------------
def fit_availability(frame: pd.DataFrame, features=FEATURES) -> dict:
    """Logistic availability hazard on the person-period grid. Returns a scaler + model +
    features."""
    x = frame[features].to_numpy(float)
    y = frame["available"].to_numpy(float)
    scaler = StandardScaler().fit(x)
    model = LogisticRegression(C=1.0, max_iter=1000).fit(scaler.transform(x), y)
    return {"scaler": scaler, "model": model, "features": list(features)}


def predict_availability(fit: dict, frame: pd.DataFrame) -> np.ndarray:
    x = fit["scaler"].transform(frame[fit["features"]].to_numpy(float))
    return fit["model"].predict_proba(x)[:, 1]


def estimate_dispersion(games: np.ndarray, team_games: np.ndarray, p: np.ndarray) -> float:
    """Method-of-moments Beta-Binomial over-dispersion ``ρ`` from realized games vs predicted avail.

    Standardized residual ``r=(a−p)/√(p(1−p)/G)`` has ``E[r²]≈1+(G−1)ρ`` under Beta-Binomial, so
    ``ρ≈(mean r²−1)/(mean G−1)``. Clipped to ``[0, 0.5]``. Captures the lumpy lost-season tail.
    """
    g, G, p = (np.asarray(v, float) for v in (games, team_games, p))
    a = g / G
    var = np.clip(p * (1 - p) / G, 1e-9, None)
    r2 = ((a - p) ** 2 / var)
    rho = (np.nanmean(r2) - 1.0) / max(np.nanmean(G) - 1.0, 1.0)
    return float(np.clip(rho, 0.0, 0.5))


def sample_games(p: float, team_games: int, rho: float, rng: np.random.Generator,
                 n: int) -> np.ndarray:
    """Draw ``n`` games-played counts ~ Beta-Binomial(team_games, p, ρ). ρ=0 ⇒ plain Binomial."""
    p = float(np.clip(p, 1e-3, 1 - 1e-3))
    if rho <= 1e-6:
        return rng.binomial(team_games, p, size=n)
    conc = 1.0 / rho - 1.0
    pp = rng.beta(p * conc, (1 - p) * conc, size=n)
    return rng.binomial(team_games, pp)


# --------------------------------------------------------------------------------------------
# the PIT projection
# --------------------------------------------------------------------------------------------
def availability_projection(con, season: int, train_seasons=None) -> pd.DataFrame:
    """Per-player availability for ``season``: ``[player_key, pos, avail_p, games_played_mean,
    team_games, rho]``. Fits the hazard on strictly-prior DEV seasons; ``rho`` is shared (attached
    to every row for the sampler)."""
    if train_seasons is None:
        train_seasons = [s for s in DEV_SEASONS if s < season] or list(DEV_SEASONS)
    train = availability_frame(con, train_seasons)
    fit = fit_availability(train)

    # dispersion from realized games vs. per-player mean availability on the training seasons
    gp = games_played(con, train_seasons)
    per_player = (train.assign(p=predict_availability(fit, train))
                  .groupby(["season", "player_key"])["p"].mean().reset_index())
    gpm = gp.merge(per_player, on=["season", "player_key"], how="inner")
    rho = estimate_dispersion(gpm["games"].to_numpy(), gpm["team_games"].to_numpy(),
                              gpm["p"].to_numpy()) if len(gpm) else 0.15

    # target-season players: predict availability at each player's covariates (mean over the season)
    tgt = availability_frame(con, [season])
    if tgt.empty:
        return pd.DataFrame(columns=["player_key", "pos", "avail_p", "games_played_mean",
                                     "team_games", "rho"])
    tgt = tgt.assign(p=predict_availability(fit, tgt))
    out = (tgt.groupby(["player_key", "pos"]).agg(
        avail_p=("p", "mean"), team_games=("week", "nunique")).reset_index())
    out["games_played_mean"] = out["avail_p"] * out["team_games"]
    out["rho"] = rho
    return out
