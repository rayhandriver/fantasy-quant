"""Phase 5.3 — weekly boom/bust variance (the week-to-week volatility layer).

The season-total spread (5.1/5.2) answers "how uncertain is his year?" This module answers a
*different* question the risk dial and the start/sit story both need: **how volatile is he week to
week?** Two RBs can share a season projection yet feel completely different — a steady 14-a-week
grinder vs. a 4-or-28 boom/bust back. That volatility is a real, forecastable player trait
(usage-driven: TD-dependence, target concentration, committee risk).

We compute, from realized weekly points, each player's **weekly mean / sd /
coefficient-of-variation** and his **boom rate** (share of weeks clearing a position "great game"
line) and **bust rate** (share of weeks below a "dud" line). These are surfaced directly in the
distribution contract (a consistency signal), and the mean boom/bust *skew* informs the shape of
the season sampler (5.x). We also cross-check the season spread: under week independence
``sd_season ≈ sd_week·√games`` — the gap measures hot/cold streakiness. PIT: computed on realized
weeks of strictly-prior seasons for a forward projection.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.backtest.scoring import RuleSet, weekly_points

# position-relative weekly PPR thresholds: a "boom" (league-winning week) vs a "bust"
# (unstartable dud).
BOOM_LINE = {"QB": 25.0, "RB": 20.0, "WR": 20.0, "TE": 15.0}
BUST_LINE = {"QB": 12.0, "RB": 6.0, "WR": 6.0, "TE": 4.0}
SKILL = ("QB", "RB", "WR", "TE")


def boom_bust_rates(weekly: pd.DataFrame, boom=BOOM_LINE, bust=BUST_LINE) -> pd.DataFrame:
    """Per-player weekly volatility stats from a player-week frame (``pos``/``position``,
    ``points``).

    Returns one row per ``player_key`` with weeks, weekly mean/sd/cov and boom/bust rates. Pure
    over the passed frame (the unit-test target); ``boom``/``bust`` are per-position thresholds.
    """
    w = weekly.copy()
    posc = "pos" if "pos" in w.columns else "position"
    w["_boom"] = w.apply(lambda r: float(r["points"] >= boom.get(r[posc], 1e9)), axis=1)
    w["_bust"] = w.apply(lambda r: float(r["points"] <= bust.get(r[posc], -1e9)), axis=1)
    g = w.groupby("player_key")
    out = g.agg(pos=(posc, "first"), weeks=("points", "size"),
                wk_mean=("points", "mean"), wk_sd=("points", lambda s: float(s.std(ddof=0))),
                boom_prob=("_boom", "mean"), bust_prob=("_bust", "mean")).reset_index()
    out["wk_cov"] = np.where(out["wk_mean"] > 1e-6, out["wk_sd"] / out["wk_mean"], np.nan)
    return out


def weekly_volatility(con, seasons, ruleset: RuleSet | None = None) -> pd.DataFrame:
    """Boom/bust + weekly moments pooled over ``seasons`` (per player_key = gsis_id)."""
    ruleset = ruleset or RuleSet()
    frames = []
    for s in seasons:
        wk = weekly_points(con, s, ruleset)
        wk = wk[wk["position"].isin(SKILL) & wk["gsis_id"].notna()].copy()
        wk["player_key"] = wk["gsis_id"]
        frames.append(wk[["player_key", "position", "points"]])
    allwk = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["player_key", "position", "points"])
    return boom_bust_rates(allwk)


def position_skew(con, seasons, ruleset: RuleSet | None = None, min_weeks: int = 6) -> dict:
    """Per-position skew of weekly points (fantasy scoring is right-skewed — the boom tail). Feeds
    the sampler's tail shape. Players with ``< min_weeks`` are excluded (noisy)."""
    ruleset = ruleset or RuleSet()
    frames = []
    for s in seasons:
        wk = weekly_points(con, s, ruleset)
        wk = wk[wk["position"].isin(SKILL) & wk["gsis_id"].notna()]
        frames.append(wk[["position", "points"]])
    allwk = pd.concat(frames, ignore_index=True)
    skew = {}
    for pos, g in allwk.groupby("position"):
        if len(g) >= min_weeks:
            skew[pos] = float(pd.Series(g["points"]).skew())
    return skew
