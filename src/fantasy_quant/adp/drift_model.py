"""Phase 16.8 — does draft-slot **drift** predict? (the survive-or-drop verdict)

Fits ``drift_centered ~ features`` on the Phase-16.7 panel and scores it **walk-forward**
(leave-one-season-out), against the only baseline that matters: ``drift = 0``, i.e. "everyone goes
at ADP". Same discipline as Phase 6.2 — season-block bootstrap CIs, sign stability, and a metric
fixed before the result is seen. A feature survives or is dropped; no threshold moves post-hoc.

**Features, and why each is or is not point-in-time:**

* ``vbd_gap`` — our own value board's ``overall_rank`` minus the board's ADP rank, in rounds. The
  proxy for "the experts rank him higher than the market drafts him". BUILD_PLAN wanted *true* ECR
  here; Phase 0.11 banked the ECR archive and then proved it unusable for this — every archived
  board is stamped at kickoff, after 37 of 38 drafts in the corpus — so the proxy stands and the
  reason is now measured rather than assumed.
* ``source_divergence`` — the public FFC board minus the sharper Sleeper-room board, in rounds,
  computed **leave-one-draft-out** (:func:`~fantasy_quant.adp.drift_panel.heldout_sleeper_board`).
  The stored ``sleeper_human`` ADP is the mean pick over these very drafts, so the naive version of
  this feature is the target's own negative; the held-out form is the honest one. Because even the
  held-out form is built from the target's siblings, the headline fit is reported **with an
  ablation that drops it entirely** — if the verdict only survives with it, the verdict is the
  leak.
* the 16.1/16.2 **situation flags** — ``team_changed``, ``new_starting_qb``, and the two
  competition-change flags, reused verbatim from ``adp/panel.py`` (all derived from ``weekly`` /
  ``draft_picks``, genuinely PIT at draft day).
* controls — ``adp_rounds`` (a player 12 rounds deep simply has more room to move than a first-
  rounder: without this the model would "discover" depth), ``adp_stdev`` (the crowd's own
  disagreement), ``days_to_board`` (the board post-dates most drafts, so some measured drift is
  market movement, not behaviour), ``rookie``, and position dummies.

**Expect a null.** The panel is 34 drafts over 8 seasons, several of them a single draft deep. The
project's stated bar is calibration and honesty, not a forced edge — 16.1/16.2 came back null on
the value side and were reported as such.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from fantasy_quant.adp.drift_panel import heldout_sleeper_board
from fantasy_quant.adp.panel import (
    OFFENSE,
    _canon_pos,
    _canon_team,
    _competition_flags,
    _early_season_team,
    _new_starting_qb_map,
    _prev_primary_team,
)
from fantasy_quant.adp.regression import fit_alpha_regression, prepare

TARGET = "drift_centered"

#: every feature the model may see (the ablation drops ``source_divergence`` from this list).
DRIFT_FEATURES: tuple[str, ...] = (
    "vbd_gap", "source_divergence",
    "team_changed", "new_starting_qb", "competition_change_roster", "competition_change_depth",
    "rookie", "adp_rounds", "adp_stdev", "days_to_board",
)
#: the honest fallback set — everything the target's own siblings did not help build.
ABLATION_FEATURES: tuple[str, ...] = tuple(f for f in DRIFT_FEATURES if f != "source_divergence")

_CONTINUOUS: tuple[str, ...] = ("vbd_gap", "source_divergence", "adp_rounds", "adp_stdev",
                                "days_to_board")


# ------------------------------------------------------------------------------------------------
# feature assembly
# ------------------------------------------------------------------------------------------------
def _vbd_gap(con, season: int, board_teams: int, value_board_fn) -> pd.DataFrame:
    """Per player: our value board's overall rank minus the ADP board's rank, **in rounds**.

    Positive = we rank him better than the market drafts him (a value the room is leaving late).
    Returns an empty frame when the season has no projection board (e.g. the proxy's first year).
    """
    vb = value_board_fn(con, int(season))
    if vb is None or vb.empty:
        return pd.DataFrame(columns=["gsis_id", "vbd_gap"])
    vb = vb.rename(columns={"player_key": "gsis_id"})
    vb = vb[["gsis_id", "overall_rank"]].dropna(subset=["gsis_id"])
    vb["vbd_rounds"] = pd.to_numeric(vb["overall_rank"], errors="coerce") / float(board_teams)
    return vb[["gsis_id", "vbd_rounds"]]


def _situation_flags(con, season: int) -> pd.DataFrame:
    """The 16.1/16.2 flags for every offensive player with a Week-1 team in ``season``.

    Rebuilt here (rather than joined off the 16.1 alpha panel) because that panel is restricted to
    the FFC board's top-180 and to ``DEV_SEASONS``; the drift panel spans a different universe.
    The *definitions* are the imported ones, so the two phases cannot drift apart.
    """
    team = _early_season_team(con, season)
    if team.empty:
        return pd.DataFrame(columns=["gsis_id", "team_changed", "new_starting_qb",
                                     "competition_change_roster", "competition_change_depth"])
    pos = con.execute(
        "SELECT gsis_id, position FROM weekly WHERE season = ? AND gsis_id IS NOT NULL",
        [int(season)]).df()
    pos["pos"] = _canon_pos(pos["position"])
    pos = pos.dropna(subset=["pos"]).groupby("gsis_id")["pos"].agg(
        lambda s: s.mode().iat[0]).reset_index()

    df = team.merge(pos, on="gsis_id", how="inner")
    df = df[df["pos"].isin(OFFENSE)].reset_index(drop=True)
    prev = _prev_primary_team(con, season)
    df = df.merge(prev, on="gsis_id", how="left")
    df["team"] = _canon_team(df["team"])

    nsq = _new_starting_qb_map(con, season)
    changed = (df["team_prev"].notna() & df["team"].notna() & (df["team_prev"] != df["team"]))
    comp_roster, comp_depth = _competition_flags(con, season, df)
    return pd.DataFrame({
        "gsis_id": df["gsis_id"],
        "team_changed": changed.astype("boolean").fillna(False).astype(int),
        "new_starting_qb": df["team"].map(nsq).fillna(0).astype(int),
        "competition_change_roster": comp_roster,
        "competition_change_depth": comp_depth,
    })


def build_features(con, panel: pd.DataFrame, value_board_fn,
                   rookie_years: pd.DataFrame | None = None) -> pd.DataFrame:
    """Attach every :data:`DRIFT_FEATURES` column to the 16.7 panel (one row per boarded pick)."""
    if panel.empty:
        return panel.assign(**{f: [] for f in DRIFT_FEATURES})
    out = panel.copy()

    # --- leave-one-draft-out sharp board -> source divergence (rounds; +ve = public is later) ----
    heldout = heldout_sleeper_board(out)
    out["source_divergence"] = out["adp_rounds"] - heldout

    # --- per-season joins -----------------------------------------------------------------------
    # `vbd_rounds` is a rank divided by a league size, so it is keyed by (season, board_teams) —
    # NOT by season alone. That distinction was invisible while each season's handful of drafts
    # happened to share one board size; on the Session-F.5 corpus a single season carries both
    # 10- and 12-team rooms, and joining on season alone would price roughly half the rows against
    # the wrong board. Grouping on both is a correctness fix, not a tuning choice.
    gaps, flags = [], []
    for (season, bteams), _g in out.groupby(["season", "board_teams"]):
        vb = _vbd_gap(con, int(season), int(bteams), value_board_fn)
        if not vb.empty:
            gaps.append(vb.assign(season=int(season), board_teams=int(bteams)))
    for season, _g in out.groupby("season"):
        sf = _situation_flags(con, int(season))
        if not sf.empty:
            flags.append(sf.assign(season=int(season)))
    vbd = pd.concat(gaps, ignore_index=True) if gaps else pd.DataFrame(
        columns=["gsis_id", "vbd_rounds", "season", "board_teams"])
    sit = pd.concat(flags, ignore_index=True) if flags else pd.DataFrame(
        columns=["gsis_id", "season", *DRIFT_FEATURES[2:6]])

    out = out.merge(vbd, on=["gsis_id", "season", "board_teams"], how="left")
    out["vbd_gap"] = out["adp_rounds"] - out["vbd_rounds"]
    out = out.merge(sit, on=["gsis_id", "season"], how="left")
    for f in ("team_changed", "new_starting_qb", "competition_change_roster",
              "competition_change_depth"):
        out[f] = out[f].fillna(0).astype(int)

    # --- rookie flag (draft_year == season) -----------------------------------------------------
    if rookie_years is None:
        rookie_years = con.execute(
            "SELECT gsis_id, draft_year FROM player_ids WHERE gsis_id IS NOT NULL").df()
    ry = rookie_years.drop_duplicates("gsis_id")
    out = out.merge(ry, on="gsis_id", how="left")
    out["rookie"] = (pd.to_numeric(out["draft_year"], errors="coerce")
                     == out["season"]).fillna(False).astype(int)

    out["adp_stdev"] = pd.to_numeric(out["adp_stdev"], errors="coerce")
    out["adp_stdev"] = out["adp_stdev"].fillna(out["adp_stdev"].median())
    return out


# ------------------------------------------------------------------------------------------------
# walk-forward scoring
# ------------------------------------------------------------------------------------------------
@dataclass
class DriftVerdict:
    """Leave-one-season-out drift predictability vs the ``drift = 0`` baseline.

    ``mae``/``mae_baseline`` are in **rounds**. ``skill`` is the fraction of baseline MAE removed
    (>0 = better than assuming everyone goes at ADP). ``spearman`` is the rank correlation between
    predicted and realized drift, pooled over held-out seasons.
    """
    features: list[str]
    mae: float
    mae_baseline: float
    skill: float
    spearman: float
    spearman_p: float
    n: int
    n_seasons: int
    per_season: pd.DataFrame = field(default_factory=pd.DataFrame)
    skill_ci: tuple[float, float] = (float("nan"), float("nan"))

    def render(self) -> str:
        lo, hi = self.skill_ci
        return (f"  features      : {len(self.features)} ({', '.join(self.features)})\n"
                f"  n rows        : {self.n:,} over {self.n_seasons} held-out seasons\n"
                f"  MAE (model)   : {self.mae:.4f} rounds\n"
                f"  MAE (drift=0) : {self.mae_baseline:.4f} rounds\n"
                f"  skill         : {self.skill:+.2%}  CI[{lo:+.2%}, {hi:+.2%}]\n"
                f"  Spearman      : {self.spearman:+.4f}  (p={self.spearman_p:.3g})")


def _design(panel: pd.DataFrame, features: Sequence[str]) -> tuple[pd.DataFrame, list[str]]:
    return prepare(panel, features, continuous=_CONTINUOUS)


def walk_forward_drift(panel: pd.DataFrame, features: Sequence[str] = DRIFT_FEATURES,
                       target: str = TARGET, n_boot: int = 2000,
                       seed: int = 0) -> DriftVerdict:
    """Leave-one-season-out fit → predict → score against ``drift = 0``.

    Rows with any missing design cell are dropped (a single-draft season has no held-out sharp
    board, so it contributes nothing when ``source_divergence`` is in the feature set — which is
    exactly why the ablation exists).
    """
    aug, cols = _design(panel, features)
    use = aug[[target, "season", *cols]].dropna().copy()
    if use.empty:
        return DriftVerdict(list(features), float("nan"), float("nan"), float("nan"),
                            float("nan"), float("nan"), 0, 0)

    seasons = sorted(use["season"].unique())
    preds, truth, keys, rows = [], [], [], []
    for s in seasons:
        train, test = use[use["season"] != s], use[use["season"] == s]
        if len(train) < 50 or test.empty:
            continue
        X = np.column_stack([np.ones(len(train)), train[cols].to_numpy(float)])
        beta, *_ = np.linalg.lstsq(X, train[target].to_numpy(float), rcond=None)
        Xt = np.column_stack([np.ones(len(test)), test[cols].to_numpy(float)])
        yhat = Xt @ beta
        y = test[target].to_numpy(float)
        preds.append(yhat)
        truth.append(y)
        keys.append(np.full(len(y), s))
        rows.append({"season": int(s), "n": int(len(y)),
                     "mae": float(np.abs(y - yhat).mean()),
                     "mae_baseline": float(np.abs(y).mean())})
    if not preds:
        return DriftVerdict(list(features), float("nan"), float("nan"), float("nan"),
                            float("nan"), float("nan"), 0, 0)

    yhat = np.concatenate(preds)
    y = np.concatenate(truth)
    ssn = np.concatenate(keys)
    mae, mae0 = float(np.abs(y - yhat).mean()), float(np.abs(y).mean())
    rho, p = stats.spearmanr(yhat, y)

    # season-block bootstrap on the skill statistic (the ~8-season effective sample, not ~4.5k rows)
    rng = np.random.default_rng(seed)
    uniq = np.unique(ssn)
    boot = np.empty(n_boot)
    for b in range(n_boot):
        draw = rng.choice(uniq, size=len(uniq), replace=True)
        m = np.concatenate([np.flatnonzero(ssn == s) for s in draw])
        num, den = np.abs(y[m] - yhat[m]).mean(), np.abs(y[m]).mean()
        boot[b] = 1.0 - num / den if den > 0 else np.nan
    lo, hi = np.nanquantile(boot, [0.025, 0.975])

    return DriftVerdict(
        features=list(features), mae=mae, mae_baseline=mae0,
        skill=1.0 - mae / mae0 if mae0 > 0 else float("nan"),
        spearman=float(rho), spearman_p=float(p), n=int(len(y)), n_seasons=int(len(uniq)),
        per_season=pd.DataFrame(rows), skill_ci=(float(lo), float(hi)),
    )


def fit_drift(panel: pd.DataFrame, features: Sequence[str] = DRIFT_FEATURES,
              target: str = TARGET, n_boot: int = 2000, seed: int = 0):
    """Pooled coefficient fit with season-block-bootstrap CIs (the *which feature* view).

    Reuses the Phase-6.2 harness verbatim so the two phases report coefficients on one scale:
    each continuous coefficient reads as "rounds of drift per 1 SD of the trait".
    """
    return fit_alpha_regression(panel, features, n_boot=n_boot, seed=seed,
                                target=target, continuous=_CONTINUOUS)


def predict_drift(panel: pd.DataFrame, beta: np.ndarray,
                  features: Sequence[str] = DRIFT_FEATURES) -> pd.Series:
    """Apply a fitted coefficient vector to a panel, returning predicted drift in rounds."""
    aug, cols = _design(panel, features)
    X = np.column_stack([np.ones(len(aug)), aug[cols].to_numpy(float)])
    return pd.Series(X @ beta, index=aug.index, name="pred_drift")


def sign_stability(panel: pd.DataFrame, features: Sequence[str] = DRIFT_FEATURES,
                   target: str = TARGET) -> pd.DataFrame:
    """Per feature: the share of leave-one-season-out refits whose coefficient keeps the pooled
    sign. The Phase-6.3 stability guard — a feature that flips sign season to season is noise."""
    aug, cols = _design(panel, features)
    use = aug[[target, "season", *cols]].dropna()
    seasons = sorted(use["season"].unique())
    full = np.linalg.lstsq(
        np.column_stack([np.ones(len(use)), use[cols].to_numpy(float)]),
        use[target].to_numpy(float), rcond=None)[0]
    signs = []
    for s in seasons:
        tr = use[use["season"] != s]
        if len(tr) < 50:
            continue
        b = np.linalg.lstsq(np.column_stack([np.ones(len(tr)), tr[cols].to_numpy(float)]),
                            tr[target].to_numpy(float), rcond=None)[0]
        signs.append(np.sign(b) == np.sign(full))
    if not signs:
        return pd.DataFrame({"term": ["intercept", *cols], "coef": full, "stability": np.nan})
    return pd.DataFrame({"term": ["intercept", *cols], "coef": full,
                         "stability": np.vstack(signs).mean(axis=0)})
