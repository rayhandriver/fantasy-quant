"""Phase 16.11 — live ADP momentum (velocity) on the 2026 snapshot series.

**What this is.** Stage 0 has been banking the FreeFantasyCalculator 2026 board on a rolling
schedule since 2026-07-09 precisely because those boards are unrecoverable later. That series is
the only place in this repo where a player's consensus draft cost is observed **more than once
within a season**, so it is the only place ADP *velocity* — "the room is moving toward him" — can
be computed at all.

**What this is NOT: a backtestable claim.** FFC publishes one board per season historically (dated
around Sep 1), and the FantasyPros ECR archive turned out to be kickoff-dated (0.11), so no
historical intra-season ADP series exists anywhere we can reach. Velocity therefore cannot be
walk-forward scored the way 16.7/16.8 scored drift, and nothing here is allowed to claim it
predicts anything. The bar is the 16.4-style **descriptive-honesty** one: compute it correctly,
label its provenance, expose how thin it is, and let a human read it. :data:`FORWARD_ONLY` and the
``n_snapshots``/``se`` columns exist so that label travels with the data instead of living in a
docstring nobody reads.

**Sign convention** matches :mod:`fantasy_quant.adp.drift_panel` and everything downstream of it:
``velocity > 0`` means the player is being drafted **EARLIER** over time (his ADP number is
falling), i.e. the hype direction. Getting this backwards is silent and expensive, so the raw
falling-ADP slope is negated once, here, and never again.

**Two corrections applied, both mechanical rather than behavioural:**

1. *Centering.* ADP is a rank-like quantity over a pool that grows as the preseason proceeds
   (2026 PPR: 201 → 216 → 225 boarded players between 07-09 and 07-24), so the whole board drifts
   slightly later together. Velocity is reported net of the board's own median slope — the same
   move ``drift_centered`` makes in 16.7, for the same reason.
2. *Shrinkage.* A slope fit on three snapshots has one residual degree of freedom. Raw slopes at
   that sample size are mostly noise, so :func:`adp_velocity` also returns an empirical-Bayes
   shrunk slope (toward zero, by the ratio of the cross-player signal variance to each player's own
   standard error). Read ``velocity_shrunk``; ``velocity`` is kept for diagnosis.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

#: Velocity is computed on a live, forward-only series and is **not** walk-forward validated.
#: Anything that consumes it must surface this, not bury it.
FORWARD_ONLY = (
    "live 2026 series only — no historical intra-season ADP exists (FFC publishes one board per "
    "season; the FantasyPros ECR archive is kickoff-dated), so velocity is not backtestable"
)

#: Half-life (days) for the recency-weighted current ADP. ~1 snapshot cadence: the latest board
#: dominates, but a one-off outlier board cannot single-handedly define a player's cost.
RECENCY_HALFLIFE_DAYS = 10.0

#: Minimum snapshots before a slope is reported at all. Two points give a slope with zero residual
#: df — reported, but with an infinite-variance standard error, so shrinkage crushes it toward 0.
MIN_SNAPSHOTS = 2

VELOCITY_COLS = [
    "season", "gsis_id", "name", "position", "team", "n_snapshots", "first_date", "last_date",
    "span_days", "adp_first", "adp_last", "adp_now", "stdev_now", "velocity", "velocity_shrunk",
    "se", "board_median_slope",
]


def _series(con, season: int, source: str, scoring: str, teams: int) -> pd.DataFrame:
    """The full snapshot series (every date, not just the latest — which is what
    :func:`fantasy_quant.adp.boards._ffc_board` deliberately returns)."""
    return con.execute(
        """
        SELECT snapshot_date, gsis_id, name, position, team, adp, stdev
        FROM adp_snapshots
        WHERE season = ? AND source = ? AND scoring = ? AND teams = ?
          AND gsis_id IS NOT NULL AND adp IS NOT NULL
        ORDER BY gsis_id, snapshot_date
        """,
        [int(season), str(source), str(scoring), int(teams)],
    ).df()


def _slope_and_se(days: np.ndarray, adp: np.ndarray) -> tuple[float, float]:
    """OLS slope of ADP on days, and its standard error.

    Returns ``(nan, inf)`` when the design is degenerate (one distinct date) and ``(slope, inf)``
    when there are exactly two points — a real slope with no residual df, so the caller's shrinkage
    is what stops it being read as a measurement.
    """
    n = len(days)
    x = days - days.mean()
    sxx = float((x * x).sum())
    if n < 2 or sxx <= 0:
        return float("nan"), float("inf")
    slope = float((x * (adp - adp.mean())).sum() / sxx)
    if n < 3:
        return slope, float("inf")
    resid = adp - (adp.mean() + slope * x)
    sigma2 = float((resid * resid).sum()) / (n - 2)
    return slope, float(np.sqrt(max(sigma2, 0.0) / sxx))


def adp_velocity(con, season: int, *, source: str = "ffc", scoring: str = "ppr",
                 teams: int = 10, min_snapshots: int = MIN_SNAPSHOTS,
                 halflife_days: float = RECENCY_HALFLIFE_DAYS) -> pd.DataFrame:
    """Per-player ADP velocity over the banked snapshot series, in **picks per week**.

    ``velocity > 0`` = being drafted earlier over time (the hype direction; his ADP number falls).
    One row per player with at least ``min_snapshots`` observations; players who joined the board
    late simply have a smaller ``n_snapshots``, which is reported rather than imputed.

    The FFC-only default is deliberate. The 2026 series also holds ``sleeper_human`` and
    ``sleeper_mock`` boards, but those are a different population sampled on different dates, and
    pooling them would turn a composition change into an apparent slope — the F.5 hardcoded-label
    failure mode. Pass ``source`` explicitly to look at one of the others on its own.
    """
    raw = _series(con, season, source, scoring, teams)
    if raw.empty:
        return pd.DataFrame(columns=VELOCITY_COLS)

    raw["snapshot_date"] = pd.to_datetime(raw["snapshot_date"])
    t0 = raw["snapshot_date"].min()
    raw["days"] = (raw["snapshot_date"] - t0).dt.days.astype(float)

    rows = []
    for gsis, g in raw.groupby("gsis_id", sort=False):
        g = g.sort_values("days")
        if len(g) < min_snapshots:
            continue
        days = g["days"].to_numpy(float)
        adp = g["adp"].to_numpy(float)
        slope, se = _slope_and_se(days, adp)
        w = np.exp(-np.log(2.0) * (days.max() - days) / max(halflife_days, 1e-6))
        last = g.iloc[-1]
        rows.append({
            "season": int(season), "gsis_id": gsis, "name": last["name"],
            "position": last["position"], "team": last["team"],
            "n_snapshots": int(len(g)),
            "first_date": g["snapshot_date"].iloc[0].date(),
            "last_date": g["snapshot_date"].iloc[-1].date(),
            "span_days": float(days.max() - days.min()),
            "adp_first": float(adp[0]), "adp_last": float(adp[-1]),
            "adp_now": float((w * adp).sum() / w.sum()),
            "stdev_now": float(last["stdev"]) if pd.notna(last["stdev"]) else float("nan"),
            "_slope_per_day": slope, "_se_per_day": se,
        })
    if not rows:
        return pd.DataFrame(columns=VELOCITY_COLS)
    out = pd.DataFrame(rows)

    # --- centering: strip the board-wide drift, keep the relative movement ----------------------
    # The pool deepens through the preseason, so every ADP creeps later together. That common
    # component is a property of the board, not of any player.
    med = float(np.nanmedian(out["_slope_per_day"]))
    rel_day = out["_slope_per_day"] - med

    # --- to picks/week, and flip the sign so positive = drafted EARLIER = hyped ------------------
    out["velocity"] = -rel_day * 7.0
    out["se"] = out["_se_per_day"] * 7.0
    out["board_median_slope"] = -med * 7.0

    # --- empirical-Bayes shrinkage toward zero ---------------------------------------------------
    # tau2 = the cross-player variance of the true slope, backed out as (observed spread - mean
    # sampling noise) and floored at 0: if the observed spread is no wider than the noise, there is
    # no signal to keep and every velocity shrinks to 0. Two-snapshot players have se=inf and so
    # shrink to exactly 0 by construction.
    v = out["velocity"].to_numpy(float)
    se2 = np.square(out["se"].to_numpy(float))
    finite = np.isfinite(se2)
    mean_noise = float(np.mean(se2[finite])) if finite.any() else 0.0
    tau2 = max(float(np.nanvar(v)) - mean_noise, 0.0)
    with np.errstate(invalid="ignore"):
        shrink = (np.where(np.isfinite(se2), tau2 / (tau2 + se2), 0.0)
                  if tau2 > 0 else np.zeros(len(v)))
    out["velocity_shrunk"] = v * shrink

    return out[VELOCITY_COLS].sort_values("velocity_shrunk", ascending=False).reset_index(drop=True)


def momentum_summary(vel: pd.DataFrame) -> dict:
    """A compact, honest description of what the series can and cannot support.

    Leads with ``backtestable: False`` and the snapshot count, because those two facts govern how
    every other number here may be read.
    """
    if vel.empty:
        return {"backtestable": False, "forward_only": FORWARD_ONLY, "n_players": 0,
                "n_snapshots_max": 0}
    return {
        "backtestable": False,
        "forward_only": FORWARD_ONLY,
        "n_players": int(len(vel)),
        "n_snapshots_max": int(vel["n_snapshots"].max()),
        "n_players_full_series": int((vel["n_snapshots"] == vel["n_snapshots"].max()).sum()),
        "span_days": float(vel["span_days"].max()),
        "first_date": str(vel["first_date"].min()),
        "last_date": str(vel["last_date"].max()),
        "board_median_slope_per_week": float(vel["board_median_slope"].iloc[0]),
        # 0 by construction once the board-wide slope is removed — kept as a checkable invariant
        # rather than a claim in a docstring.
        "velocity_median": float(vel["velocity"].median()),
        "velocity_sd": float(vel["velocity"].std(ddof=0)),
        "velocity_shrunk_sd": float(vel["velocity_shrunk"].std(ddof=0)),
        # how much of the raw spread survived shrinkage — the single most informative number about
        # whether three snapshots carry any signal at all
        "shrinkage_retained": (float(vel["velocity_shrunk"].std(ddof=0) /
                                     vel["velocity"].std(ddof=0))
                               if float(vel["velocity"].std(ddof=0)) > 0 else 0.0),
    }


def movers(vel: pd.DataFrame, *, k: int = 15, skill_only: bool = True) -> dict[str, pd.DataFrame]:
    """The ``k`` biggest risers and fallers, skill positions only by default.

    Kickers dominate a raw sort — their ADP is nearly arbitrary and swings by 15+ picks between
    boards — so a hype readout that does not filter them is reporting noise with names on it.
    """
    v = vel
    if skill_only:
        v = v[v["position"].isin(("QB", "RB", "WR", "TE"))]
    return {"risers": v.nlargest(k, "velocity_shrunk"),
            "fallers": v.nsmallest(k, "velocity_shrunk")}
