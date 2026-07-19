"""Phase 12.3 — event study (how much a news event moves the thing it predicts, and the lag).

The reframe's freshest-information thesis: a structured injury/depth signal is only worth building
if it
**predicts a production change the stale market hasn't priced yet**. This module measures exactly
that, on
the two historical PIT feeds (12.1), so 12.4 can decide keep-or-drop with numbers instead of hope.

What "the market" is here. The reframe **shelved props** and there is no in-season ADP re-draft, so
we have no tradeable line that moves on news. The honest market proxy is the manager's own
**set-and-forget lineup**: an injury report is filed Wed–Sat, before Sunday's games, yet a preseason
projection (or a last-week lineup) hasn't reacted. The *exploitable lag* is the fantasy points that
stale lineup loses by starting a player the report already flagged — a quantity we can measure
against realized points, and the exact edge 13.1/13.2 could harvest.

Two studies:

* :func:`injury_impact` — per report status (Out/Doubtful/Questionable/Probable): the play rate,
the mean
  points that week, the player's own clean-week baseline, and the **expected points lost** by
  starting him
  anyway. This is the documented impact/lag per news type.
* :func:`depth_impact` — a depth-chart promotion/demotion at week ``t`` vs the player's own points
in the
  weeks before and after: does a role change predict a production change (and in the right
  direction)?

Both are PIT: an event at week ``t`` is known before week-``t`` games, and every "after" window
reads only
weeks ``> t``. CIs are clustered by player (one player contributes many correlated events).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.backtest.scoring import RuleSet, weekly_points
from fantasy_quant.news import sources

OFFENSE = ("QB", "RB", "WR", "TE")


def _offense_points(con, seasons, ruleset: RuleSet | None = None) -> pd.DataFrame:
    """Realized offense player-week points (``player_key`` = gsis), pooled over ``seasons``."""
    frames = []
    for s in seasons:
        wp = weekly_points(con, s, ruleset)
        wp = wp[wp["position"].isin(OFFENSE) & wp["gsis_id"].notna()].copy()
        wp["player_key"] = wp["gsis_id"].astype(str)
        wp["season"] = int(s)
        frames.append(wp[["player_key", "season", "week", "position", "points"]])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["player_key", "season", "week", "position", "points"])


def _cluster_ci(values: np.ndarray, cluster: np.ndarray, n_boot: int = 2000, seed: int = 0,
                alpha: float = 0.05) -> tuple[float, float]:
    """Percentile CI of the mean, resampling whole ``cluster``s (players) — the honest error bar
    when a
    player contributes many correlated events."""
    values = np.asarray(values, float)
    cluster = np.asarray(cluster)
    if len(values) == 0:
        return (float("nan"), float("nan"))
    order = np.argsort(cluster, kind="stable")
    values, cluster = values[order], cluster[order]
    _, starts = np.unique(cluster, return_index=True)
    groups = np.split(values, starts[1:])
    rng = np.random.default_rng(seed)
    n = len(groups)
    means = np.array([np.concatenate([groups[i] for i in rng.integers(0, n, n)]).mean()
                      for _ in range(n_boot)])
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


# ------------------------------------------------------------------------------------------------
# study 1 — injury-report impact + exploitable lag
# ------------------------------------------------------------------------------------------------
def injury_impact(con, seasons, ruleset: RuleSet | None = None, *, n_boot: int = 2000,
                  seed: int = 0) -> dict:
    """Per-status impact of an injury designation, and the exploitable lag.

    For each ``(player, season, week)`` injury designation we look up whether the player recorded
    points that week (``played``) and how many (missing ⇒ did not play, 0 points). The player's
    **clean-week baseline** is his mean points over that season's weeks with *no* designation — his
    normal level. The **expected loss** of starting him under a given status is
    ``baseline − points_that_week``. Returns a per-status table and an overall exploitable-loss CI
    clustered by player.
    """
    inj = sources.injury_events(con, seasons)
    pts = _offense_points(con, seasons, ruleset)
    if inj.empty or pts.empty:
        return {"seasons": list(map(int, seasons)), "n_events": 0, "per_status": {}}

    inj = inj[inj["pos"].isin(OFFENSE)].copy()
    key = ["player_key", "season", "week"]
    # attach realized points to each designation (LEFT: an Out player has no played row ⇒ 0).
    ev = inj[[*key, "status"]].merge(pts[[*key, "points"]], on=key, how="left")
    ev["played"] = ev["points"].notna().astype(float)
    ev["points"] = ev["points"].fillna(0.0)

    # clean-week baseline per (player, season): mean points over weeks with NO designation.
    designated = set(map(tuple, inj[key].to_numpy()))
    pts["_desig"] = [tuple(r) in designated for r in pts[key].to_numpy()]
    clean = pts[~pts["_desig"]]
    baseline = (clean.groupby(["player_key", "season"])["points"].mean()
                .rename("baseline").reset_index())
    ev = ev.merge(baseline, on=["player_key", "season"], how="left")
    ev = ev.dropna(subset=["baseline"])
    ev["loss"] = ev["baseline"] - ev["points"]

    per_status = {}
    for status, g in ev.groupby("status"):
        lo, hi = _cluster_ci(g["loss"].to_numpy(), g["player_key"].to_numpy(), n_boot, seed)
        per_status[str(status)] = {
            "n": int(len(g)),
            "play_rate": float(g["played"].mean()),
            "mean_points": float(g["points"].mean()),
            "baseline_points": float(g["baseline"].mean()),
            "expected_loss": float(g["loss"].mean()),
            "expected_loss_ci": (lo, hi),
        }
    # overall exploitable lag = mean loss across designations that carry real threat
    # (Out/Doubtful/Q).
    threat = ev[ev["status"].isin(["Out", "Doubtful", "Questionable"])]
    olo, ohi = _cluster_ci(threat["loss"].to_numpy(), threat["player_key"].to_numpy(), n_boot, seed)
    return {
        "seasons": list(map(int, seasons)), "n_events": int(len(ev)),
        "per_status": per_status,
        "exploitable_loss": float(threat["loss"].mean()) if len(threat) else float("nan"),
        "exploitable_loss_ci": (olo, ohi),
        "exploitable_significant": bool(olo > 0.0),
    }


# ------------------------------------------------------------------------------------------------
# study 2 — depth-chart change impact
# ------------------------------------------------------------------------------------------------
def depth_impact(con, seasons, ruleset: RuleSet | None = None, *, window: int = 3,
                 n_boot: int = 2000, seed: int = 0) -> dict:
    """Does a depth-chart change at week ``t`` predict a production change (right direction)?

    For each promotion/demotion event, compare the player's mean points over the ``window`` weeks
    *after*
    ``t`` to the ``window`` weeks *before* — ``after − before``. A promotion should raise it, a
    demotion
    lower it. Returns each direction's mean before→after change with a player-clustered CI, and
    whether
    ``(promotion − demotion)`` separates (the sign test the signal must pass to be real).
    """
    dep = sources.depth_events(con, seasons)
    pts = _offense_points(con, seasons, ruleset)
    if dep.empty or pts.empty:
        return {"seasons": list(map(int, seasons)), "n_events": 0}

    dep = dep[dep["pos"].isin(OFFENSE)].copy()
    # per (player, season) week→points lookup for the before/after windows.
    pk = {(r.player_key, int(r.season), int(r.week)): float(r.points)
          for r in pts.itertuples(index=False)}

    def _win_mean(player, season, lo, hi):
        vals = [pk.get((player, season, w), 0.0) for w in range(lo, hi)]
        return float(np.mean(vals)) if vals else 0.0

    rows = []
    for e in dep.itertuples(index=False):
        t = int(e.week)
        before = _win_mean(e.player_key, int(e.season), t - window, t)
        after = _win_mean(e.player_key, int(e.season), t + 1, t + 1 + window)
        rows.append((e.player_key, e.status, after - before))
    df = pd.DataFrame(rows, columns=["player_key", "status", "change"])

    out = {"seasons": list(map(int, seasons)), "n_events": int(len(df)), "window": int(window)}
    for status in ("promotion", "demotion"):
        g = df[df["status"] == status]
        lo, hi = _cluster_ci(g["change"].to_numpy(), g["player_key"].to_numpy(), n_boot, seed)
        out[status] = {"n": int(len(g)), "change_ci": (lo, hi),
                       "mean_change": float(g["change"].mean()) if len(g) else 0.0}
    prom = out.get("promotion", {}).get("mean_change", 0.0)
    demo = out.get("demotion", {}).get("mean_change", 0.0)
    out["separation"] = float(prom - demo)  # > 0 ⇒ role change predicts production (right sign)
    out["directional"] = bool(prom > demo)
    return out
