"""Phase 2.2 — the naive opportunity×efficiency baseline projection (the dumb model to beat).

Deliberately simple and PIT: project a player's season fantasy points from **prior-season production
per game**, shrunk toward the positional mean (more history → less shrink, an empirical-Bayes
flavor), stretched over a full season and nudged by a light age penalty. No ML, no current-season
peeking (only season ``S-1`` is used). Returning players get a projection; rookies / no-history
players are left out (NaN) so the VBD ``rank_fn`` falls back to their ADP — a naive last-year-stats
model can't forecast rookies, and pretending otherwise would flatter it. This is the honest bar the
real models (Phase 4) must clear.
"""

from __future__ import annotations

import pandas as pd

from fantasy_quant.backtest import scoring
from fantasy_quant.backtest.scoring import RuleSet

_OFF = {"QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "FB": "RB", "HB": "RB"}
GAMES = 17           # a full modern regular season
SHRINK_K = 6.0       # games of prior data at which the player weight = mean weight (0.5)


def _shrink_ppg(ppg: float, weeks: float, pos_mean: float) -> float:
    """Empirical-Bayes shrink of a player's prior points-per-game toward the positional mean;
    weight = weeks / (weeks + K), so a 4-game sample leans on the mean, a full season barely."""
    w = weeks / (weeks + SHRINK_K)
    return w * ppg + (1 - w) * pos_mean


def _age_factor(pos: str, age: float | None) -> float:
    """A light, documented age nudge (the full delta-method age curve is Phase 4.2)."""
    if age is None or pd.isna(age):
        return 1.0
    if pos == "RB":
        return 0.85 if age >= 30 else (0.95 if age >= 28 else 1.0)
    if pos in ("WR", "TE"):
        return 0.90 if age >= 32 else 1.0
    if pos == "QB":
        return 0.90 if age >= 38 else 1.0
    return 1.0


def _ages(con, as_of) -> pd.Series:
    ids = con.execute(
        "SELECT gsis_id, MAX(birthdate) AS birthdate FROM player_ids "
        "WHERE gsis_id IS NOT NULL GROUP BY gsis_id"
    ).df()
    bd = pd.to_datetime(ids["birthdate"], errors="coerce")
    ids["age"] = (pd.Timestamp(as_of) - bd).dt.days / 365.25
    return ids.set_index("gsis_id")["age"]


def _project(tot: pd.DataFrame, ages: pd.Series, aged: bool) -> pd.DataFrame:
    """Shared projection for a (gsis, pos, points, weeks) frame -> (player_key, pos, proj)."""
    tot = tot[tot["weeks"] > 0].copy()
    tot["ppg"] = tot["points"] / tot["weeks"]
    regulars = tot[tot["weeks"] >= 8]
    means = regulars.groupby("pos")["ppg"].mean()
    default_mean = tot["ppg"].mean()
    tot["age"] = tot["gsis_id"].map(ages) if aged else None
    proj = []
    for r in tot.itertuples(index=False):
        shrunk = _shrink_ppg(r.ppg, r.weeks, means.get(r.pos, default_mean))
        factor = _age_factor(r.pos, getattr(r, "age", None)) if aged else 1.0
        proj.append(shrunk * GAMES * factor)
    tot["proj_points"] = proj
    return tot[["gsis_id", "pos", "proj_points"]].rename(columns={"gsis_id": "player_key"})


def baseline_projection(con, season: int, as_of=None,
                        ruleset: RuleSet | None = None) -> pd.DataFrame:
    """Naive prior-season projection for the draftable universe (offense + K), keyed by gsis.

    PIT: uses only season ``S-1`` realized production and player ages as-of the draft date.
    """
    season = int(season)
    prior = season - 1
    as_of = as_of or f"{season}-09-01"
    ages = _ages(con, as_of)

    off = scoring.season_points(con, prior, ruleset)          # gsis, position, points, weeks
    off["pos"] = off["position"].map(_OFF)
    off = off.dropna(subset=["pos"])
    # collapse multi-position players (e.g. RB listed FB some weeks) to one row per gsis
    off = (off.sort_values("points", ascending=False)
              .groupby("gsis_id", as_index=False)
              .agg(pos=("pos", "first"), points=("points", "sum"), weeks=("weeks", "max")))
    frames = [_project(off, ages, aged=True)]

    kw = scoring.kicker_weekly_points(con, prior, ruleset)
    if not kw.empty:
        ks = (kw.groupby("gsis_id")
                .agg(points=("points", "sum"), weeks=("week", "nunique")).reset_index())
        ks["pos"] = "K"
        frames.append(_project(ks[["gsis_id", "pos", "points", "weeks"]], ages, aged=False))

    return pd.concat(frames, ignore_index=True)
