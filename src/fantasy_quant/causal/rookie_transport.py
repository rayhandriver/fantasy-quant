"""Phase 7.3 — college→NFL transport for rookies.

A rookie has no NFL skill effect to carry, so we *transport* a projection from the pre-NFL signal
— **draft capital** (where the league valued him), **landing spot** (the 7.1 team situation
multiplier), position, and **combine athleticism** — onto the NFL rate scale. This extends the
Phase-4.3 rookie point-model in two Phase-7-native ways: it uses the decomposition's situation
multiplier as the landing-spot feature, and it returns a **distribution** (point + interval), not
just a point, so the risk layer can price rookie uncertainty.

Honest limitation (documented, not hidden): the fit is **conditional on playing** ≥ a few games —
drafted skill players who never see the field are out of sample — so this projects *given a role*,
and draft capital is leaned on to carry bust risk. Calibrated vs realized on held-out classes (7.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from fantasy_quant.causal.decompose import GAMES, SKILL_POS, TwoWayDecomposition

_POS = ("QB", "RB", "WR", "TE")


def build_rookie_panel(con, dec: TwoWayDecomposition, panel: pd.DataFrame,
                       seasons) -> pd.DataFrame:
    """Rookie-season rows with transport features + realized rate. A rookie = a drafted skill player
    whose draft year is in ``seasons`` and who has a same-year panel row (played ≥ MIN_WEEKS)."""
    s = ",".join(str(int(x)) for x in seasons)
    dp = con.execute(
        f"SELECT gsis_id, season AS draft_year, round AS draft_round, pick AS draft_ovr, "
        f"team AS draft_team, position, college, pfr_player_id, cfb_player_id "
        f"FROM draft_picks WHERE season IN ({s}) AND gsis_id IS NOT NULL"
    ).df()
    dp["pos"] = dp["position"].where(dp["position"].isin(SKILL_POS))
    dp = dp.dropna(subset=["pos", "draft_ovr"])
    # combine athleticism (forty) joined via pfr/cfb ids
    comb = con.execute(
        "SELECT pfr_id, cfb_id, forty FROM combine WHERE forty IS NOT NULL"
    ).df()
    dp = dp.merge(comb[["pfr_id", "forty"]].rename(columns={"pfr_id": "pfr_player_id"}),
                  on="pfr_player_id", how="left")
    # realized rookie-season rate
    real = panel[["gsis_id", "season", "ppg", "weeks", "team"]].rename(
        columns={"season": "draft_year", "team": "played_team"})
    dp = dp.merge(real, on=["gsis_id", "draft_year"], how="inner")
    dp["situation"] = dp["draft_team"].map(dec.situation_).fillna(0.0)
    dp["log_ovr"] = np.log(dp["draft_ovr"].astype(float))
    dp["forty"] = dp["forty"].fillna(dp["forty"].mean())
    return dp.reset_index(drop=True)


@dataclass
class RookieTransport:
    """Ridge transport of pre-NFL signal → rookie log-ppg, with a per-position residual-sd band."""
    alpha: float = 5.0
    coef_: np.ndarray | None = None
    cols_: list[str] = field(default_factory=list)
    resid_sd_: dict = field(default_factory=dict)
    mean_: np.ndarray | None = None
    meta: dict = field(default_factory=dict)

    def _design(self, df: pd.DataFrame) -> np.ndarray:
        X = {
            "log_ovr": df["log_ovr"].to_numpy(float),
            "situation": df["situation"].to_numpy(float),
            "forty": df["forty"].to_numpy(float),
            "is_RB": (df["pos"] == "RB").astype(float).to_numpy(),
            "is_WR": (df["pos"] == "WR").astype(float).to_numpy(),
            "is_TE": (df["pos"] == "TE").astype(float).to_numpy(),
            "is_QB": (df["pos"] == "QB").astype(float).to_numpy(),
        }
        self.cols_ = list(X)
        return np.column_stack([X[c] for c in self.cols_])

    def fit(self, rookie_panel: pd.DataFrame) -> RookieTransport:
        df = rookie_panel[rookie_panel["ppg"] > 0].copy()
        X = self._design(df)
        y = np.log(df["ppg"].to_numpy(float))
        self.mean_ = X.mean(0)
        Xc = X - self.mean_
        w = np.sqrt(df["weeks"].to_numpy(float))
        Xw = Xc * w[:, None]
        yw = (y - y.mean()) * w
        A = Xw.T @ Xw + self.alpha * np.eye(Xc.shape[1])
        self.coef_ = np.linalg.solve(A, Xw.T @ yw)
        self._intercept = float(y.mean())
        pred = Xc @ self.coef_ + self._intercept
        df = df.assign(_resid=y - pred)
        self.resid_sd_ = {
            p: float(g["_resid"].std(ddof=1)) if len(g) > 3 else float(df["_resid"].std())
            for p, g in df.groupby("pos")}
        self._global_sd = float(df["_resid"].std())
        self.meta = {"n": len(df), "alpha": self.alpha,
                     "coef": dict(zip(self.cols_, self.coef_.tolist(), strict=False))}
        return self

    def project(self, rookie_panel: pd.DataFrame, *, games: int = GAMES,
                z: float = 1.0) -> pd.DataFrame:
        """Point + [lo, hi] rate/points band for each rookie row (z = band half-width in σ)."""
        X = self._design(rookie_panel)
        logppg = (X - self.mean_) @ self.coef_ + self._intercept
        sd = rookie_panel["pos"].map(lambda p: self.resid_sd_.get(p, self._global_sd)).to_numpy()
        out = rookie_panel[["gsis_id", "pos", "draft_year", "draft_ovr"]].copy()
        out["proj_ppg"] = np.exp(logppg)
        out["ppg_lo"] = np.exp(logppg - z * sd)
        out["ppg_hi"] = np.exp(logppg + z * sd)
        out["proj_points"] = out["proj_ppg"] * games
        return out
