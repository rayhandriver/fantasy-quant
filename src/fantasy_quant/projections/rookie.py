"""Phase 4.3 — the rookie value model (draft capital + landing spot → projected rookie points).

Rookies are the one place the consensus/baseline mean goes blind: a first-year player has **no prior
production**, so the Phase-2 baseline leaves him NaN and the historical proxy value board simply
misses him. But a rookie is not information-free — he has **draft capital** (where the NFL invested)
and a **landing spot** (the offense he walks into). This module projects a rookie's season points
from those, so the value board (4.2) can fill rookies with a real number instead of dropping them to
ADP.

Model: a small **per-position ridge** (closed-form, dependency-free — respects the ~hundreds-of-
rookies sample and the no-deep-nets rule) on ``log(draft_ovr)`` + landing-spot environment (implied
team total, target competition, pass rate). Fit **walk-forward** on rookies from strictly-prior
seasons; predict the target season's rookies. PIT: draft capital is known pre-draft and landing spot
is valued at the **prior** season, so nothing dated ≥ the target leaks in.

Live caveat: a season's rookies must be in the ``player_ids`` crosswalk (draft data) with a known
target-season team; for the *upcoming* draft that lands late (documented) — there the live
FantasyPros board already carries rookie projections. The model's role is the historical/backtest
fill + a validated standalone rookie signal.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.backtest import scoring
from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.features import environment, player

ROOKIE_FEATURES = ["log_draft_ovr", "implied_team_total", "tgt_hhi", "pass_rate"]
_OFF = {"QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE"}
# league-typical fallbacks so a season whose prior-year env is unavailable (e.g. 2014 needs 2013,
# which predates the store) never yields NaN features that would poison the fit.
_ENV_DEFAULTS = {"implied_team_total": 22.0, "tgt_hhi": 0.17, "pass_rate": 0.58}


# --------------------------------------------------------------------------------------------
# feature assembly
# --------------------------------------------------------------------------------------------
def _primary_team(con, season: int) -> pd.DataFrame:
    """Each player's primary REG team in ``season`` (the landing spot), one row per gsis."""
    return con.execute(
        """
        SELECT gsis_id, ARG_MAX(recent_team, g) AS team FROM (
            SELECT gsis_id, recent_team, COUNT(*) g FROM weekly
            WHERE season = ? AND season_type='REG' AND gsis_id IS NOT NULL
              AND position IN ('QB','RB','WR','TE')
            GROUP BY gsis_id, recent_team)
        GROUP BY gsis_id
        """,
        [int(season)],
    ).df()


def rookie_frame(con, season: int, with_target: bool = False) -> pd.DataFrame:
    """Feature frame for ``season``'s rookies: draft capital + landing-spot env (valued at ``S-1``).

    ``with_target=True`` attaches realized rookie-season points (for training only). PIT-safe: all
    features predate the season; the target is used solely on strictly-prior seasons.
    """
    season = int(season)
    plr = player.player_features(con, [season])
    rk = plr[plr["is_rookie"] == 1][["gsis_id", "position", "draft_ovr", "bmi"]].copy()
    if rk.empty:
        return rk.assign(**{f: [] for f in ROOKIE_FEATURES}, pos=[], player_key=[])

    team = _primary_team(con, season)
    env = environment.environment_features(con, [season - 1])[
        ["team", "implied_team_total", "tgt_hhi", "pass_rate"]]
    df = rk.merge(team, on="gsis_id", how="left").merge(env, on="team", how="left")

    df["log_draft_ovr"] = np.log(pd.to_numeric(df["draft_ovr"], errors="coerce").clip(lower=1))
    # a rookie with no landing-spot env (team not found) gets league-median context, not a drop;
    # a whole-season gap (prior year predates the store) falls back to the league-typical constant.
    for c in ("implied_team_total", "tgt_hhi", "pass_rate"):
        s = pd.to_numeric(df[c], errors="coerce")
        df[c] = s.fillna(s.median()).fillna(_ENV_DEFAULTS[c])
    df["pos"] = df["position"].map(_OFF)
    df["player_key"] = df["gsis_id"]
    df = df.dropna(subset=["pos"])

    if with_target:
        pts = scoring.season_points(con, season)[["gsis_id", "points"]]
        df = df.merge(pts, on="gsis_id", how="left")
        df["points"] = df["points"].fillna(0.0)  # drafted-but-DNP rookie realized ~0
    return df.reset_index(drop=True)


# --------------------------------------------------------------------------------------------
# per-position ridge (closed-form, pure — the unit-test target)
# --------------------------------------------------------------------------------------------
def fit_ridge(x: np.ndarray, y: np.ndarray, lam: float = 10.0) -> dict:
    """Closed-form ridge on standardized features. Returns the params needed to predict:
    feature mean/std, weights, and the intercept (mean of ``y``). Pure/deterministic."""
    mu, sd = x.mean(axis=0), x.std(axis=0)
    sd = np.where(sd < 1e-9, 1.0, sd)
    z = (x - mu) / sd
    b = float(y.mean())
    w = np.linalg.solve(z.T @ z + lam * np.eye(z.shape[1]), z.T @ (y - b))
    return {"mu": mu, "sd": sd, "w": w, "b": b}


def predict_ridge(model: dict, x: np.ndarray) -> np.ndarray:
    z = (x - model["mu"]) / model["sd"]
    return model["b"] + z @ model["w"]


def fit_rookie_models(train: pd.DataFrame, features=ROOKIE_FEATURES, lam: float = 10.0) -> dict:
    """One ridge per position over the pooled training rookies (needs ``points`` target)."""
    models = {}
    for pos, g in train.groupby("pos"):
        if len(g) >= 8:  # need a few rookies to fit anything honest
            models[pos] = fit_ridge(g[features].to_numpy(float), g["points"].to_numpy(float), lam)
    return models


# --------------------------------------------------------------------------------------------
# the PIT projection
# --------------------------------------------------------------------------------------------
def rookie_projection(con, season: int, as_of=None, train_seasons=None,
                      lam: float = 10.0) -> pd.DataFrame:
    """Project ``season``'s rookies as ``[player_key, pos, proj_points]`` (draft-time VBD shape).

    Fits per-position ridge on rookies from ``train_seasons`` (default: DEV seasons strictly before
    ``season``) and predicts this class. Points are floored at 0. Empty if no rookies / no fittable
    history (caller falls back to ADP).
    """
    season = int(season)
    if train_seasons is None:
        train_seasons = [s for s in DEV_SEASONS if s < season]
    train = pd.concat([rookie_frame(con, s, with_target=True) for s in train_seasons],
                      ignore_index=True) if train_seasons else pd.DataFrame()
    train = train.dropna(subset=[*ROOKIE_FEATURES, "points"]) if not train.empty else train
    if train.empty:
        return pd.DataFrame(columns=["player_key", "pos", "proj_points"])
    models = fit_rookie_models(train, lam=lam)

    cur = rookie_frame(con, season, with_target=False)
    if cur.empty:
        return pd.DataFrame(columns=["player_key", "pos", "proj_points"])
    out = []
    for pos, g in cur.groupby("pos"):
        if pos not in models:
            continue
        pred = predict_ridge(models[pos], g[ROOKIE_FEATURES].to_numpy(float)).clip(min=0.0)
        out.append(pd.DataFrame({"player_key": g["player_key"].to_numpy(), "pos": pos,
                                 "proj_points": pred}))
    if not out:
        return pd.DataFrame(columns=["player_key", "pos", "proj_points"])
    return pd.concat(out, ignore_index=True)
