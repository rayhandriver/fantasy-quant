"""Phase 7.1 — skill ÷ opportunity decomposition.

Production = a **player-intrinsic latent** (skill, which travels with the player) × a
**team-conferred situation multiplier** (opportunity, which stays with the team). We estimate both
with a **two-way fixed-effects** model — the labor-economics AKM worker/firm decomposition, here
players/teams — on position-and-season-relative log points-per-game. Player *movers* are what
separate the two effects (a player seen in two situations pins down which part is his), exactly as
job-changers identify worker vs firm effects in AKM. The high-dimensional dummy system is **ridge-
regularized** for stability (weak identification for non-movers); the split is therefore a
*regularized* estimate, not a causal effect — used as a projection feature, validated OOS (7.4).

Not causal: ridge shrinkage + the AKM limited-mobility bias mean the absolute player/team split is
only as good as the mover graph. We use it for *prediction of movers* (does skill travel?), where
it is testable, and never assert an identified counterfactual.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import sparse

from fantasy_quant.backtest import scoring

_OFF = {"QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "FB": "RB", "HB": "RB"}
SKILL_POS = ("QB", "RB", "WR", "TE")
MIN_WEEKS = 4          # a player-season needs at least this many games to enter the fit
GAMES = 17


# =============================================================================================
# the player-season production panel
# =============================================================================================
def _modal_team(con, seasons) -> pd.DataFrame:
    """Each player-season's modal (most-frequent) team from weekly ``recent_team``."""
    s = ",".join(str(int(x)) for x in seasons)
    wk = con.execute(
        f"SELECT gsis_id, season, recent_team AS team, COUNT(*) AS n "
        f"FROM weekly WHERE season IN ({s}) AND recent_team IS NOT NULL "
        f"GROUP BY 1,2,3"
    ).df()
    wk = wk.sort_values("n", ascending=False).groupby(["gsis_id", "season"], as_index=False).first()
    return wk[["gsis_id", "season", "team"]]


def player_season_panel(con, seasons) -> pd.DataFrame:
    """Build the (gsis, season, pos, team, points, weeks, ppg) panel for skill positions."""
    frames = []
    for s in seasons:
        sp = scoring.season_points(con, int(s))
        sp["season"] = int(s)
        frames.append(sp)
    panel = pd.concat(frames, ignore_index=True)
    panel["pos"] = panel["position"].map(_OFF)
    panel = panel.dropna(subset=["pos"])
    panel = panel[panel["pos"].isin(SKILL_POS)]
    # collapse multi-position weeks to one row per player-season
    panel = (panel.sort_values("points", ascending=False)
                  .groupby(["gsis_id", "season"], as_index=False)
                  .agg(pos=("pos", "first"), points=("points", "sum"), weeks=("weeks", "max")))
    teams = _modal_team(con, seasons)
    panel = panel.merge(teams, on=["gsis_id", "season"], how="left")
    panel = panel[panel["weeks"] >= MIN_WEEKS].copy()
    panel["ppg"] = panel["points"] / panel["weeks"]
    panel = panel[panel["ppg"] > 0]
    panel["team"] = panel["team"].fillna("UNK")
    return panel.reset_index(drop=True)


# =============================================================================================
# two-way fixed-effects decomposition
# =============================================================================================
@dataclass
class TwoWayDecomposition:
    """Fitted skill (per player) + situation (per team) log-multipliers on position/season-relative
    log-ppg. ``predict_logppg`` reassembles a projection for any player×team×season."""
    alpha: float = 10.0
    skill_: dict = field(default_factory=dict)          # gsis -> log skill effect
    situation_: dict = field(default_factory=dict)      # team -> log situation effect
    pos_season_base_: dict = field(default_factory=dict)  # (pos, season) -> mean log-ppg
    pos_base_: dict = field(default_factory=dict)        # pos -> mean log-ppg (season fallback)
    meta: dict = field(default_factory=dict)

    def fit(self, panel: pd.DataFrame) -> TwoWayDecomposition:
        df = panel.copy()
        df["logppg"] = np.log(df["ppg"])
        base = df.groupby(["pos", "season"])["logppg"].mean()
        self.pos_season_base_ = {k: float(v) for k, v in base.items()}
        self.pos_base_ = {k: float(v) for k, v in df.groupby("pos")["logppg"].mean().items()}
        base_lvl = df.set_index(["pos", "season"]).index.map(self.pos_season_base_.get)
        df["z"] = df["logppg"] - np.asarray(base_lvl, float)

        players = df["gsis_id"].astype("category")
        teams = df["team"].astype("category")
        pc, tc = players.cat.categories, teams.cat.categories
        n, npl, ntm = len(df), len(pc), len(tc)
        # design: [player one-hot | team one-hot], ridge (no intercept — z is already centered)
        rows = np.arange(n)
        Xp = sparse.csr_matrix((np.ones(n), (rows, players.cat.codes)), shape=(n, npl))
        Xt = sparse.csr_matrix((np.ones(n), (rows, teams.cat.codes)), shape=(n, ntm))
        X = sparse.hstack([Xp, Xt]).tocsr()
        w = np.sqrt(df["weeks"].to_numpy(float))
        Xw = X.multiply(w[:, None]).tocsr()
        yw = df["z"].to_numpy(float) * w

        # ridge normal equations: (XᵀX + αI) b = Xᵀy  (sparse, symmetric PD)
        A = (Xw.T @ Xw).toarray()
        A[np.diag_indices_from(A)] += self.alpha
        b = Xw.T @ yw
        coef = np.linalg.solve(A, b)
        self.skill_ = {g: float(c) for g, c in zip(pc, coef[:npl], strict=False)}
        self.situation_ = {t: float(c) for t, c in zip(tc, coef[npl:], strict=False)}
        self.meta = {"n_obs": n, "n_players": npl, "n_teams": ntm, "alpha": self.alpha}
        return self

    # -- accessors ----------------------------------------------------------------------------
    def skill(self, gsis: str) -> float:
        return self.skill_.get(gsis, 0.0)

    def situation(self, team: str) -> float:
        return self.situation_.get(team, 0.0)

    def predict_logppg(self, gsis: str, team: str, pos: str, season: int,
                       skill_override: float | None = None) -> float:
        base = self.pos_season_base_.get((pos, season))
        if base is None:
            base = self.pos_base_.get(pos, 0.0)
        sk = skill_override if skill_override is not None else self.skill(gsis)
        return base + sk + self.situation(team)

    def predict_points(self, gsis: str, team: str, pos: str, season: int,
                       games: int = GAMES, skill_override: float | None = None) -> float:
        return float(np.exp(self.predict_logppg(gsis, team, pos, season, skill_override)) * games)


def decompose(panel: pd.DataFrame, alpha: float = 10.0) -> TwoWayDecomposition:
    """Convenience: fit and return a :class:`TwoWayDecomposition` on a player-season panel."""
    return TwoWayDecomposition(alpha=alpha).fit(panel)
