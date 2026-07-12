"""Phase 7.2 — re-projection on a situation change.

Given the 7.1 decomposition, projecting a player who changes teams is a **situation swap**: keep
his skill effect, replace the old team's situation multiplier with the new team's. That is the
honest, testable content of the old "counterfactual" — not an identified causal effect, but the
prediction *"his rate should move toward what this player's talent produces in that offense."* The
bar (7.4) is that this beats **naive carry-over** (last season's rate, which bakes in the old
situation) on **held-out moves**.

We also expose a light **comparable-mover** blend (a synthetic-control flavor): shrink the FE
re-projection toward the average realized rate-change of historical movers with a similar
situation delta, which stabilizes the estimate when a player's mover graph is thin.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.causal.decompose import GAMES, TwoWayDecomposition


def reproject_on_move(dec: TwoWayDecomposition, gsis: str, pos: str, new_team: str,
                      season: int, *, games: int = GAMES) -> float:
    """Re-project a single player onto ``new_team`` by swapping the situation multiplier."""
    return dec.predict_points(gsis, new_team, pos, season, games=games)


def project_season(dec: TwoWayDecomposition, panel: pd.DataFrame, season: int) -> pd.DataFrame:
    """Project every player active in ``season`` who has a **prior-season** rate (returning
    players), using the decomposition fit on history. Returns per-player rate forecasts:

      * ``opp_rate``  — prior rate with the situation multiplier swapped (Phase-7 re-projection).
      * ``naive_rate``— prior-season ppg carried over (the must-beat baseline).
      * ``is_mover``  — the season-team differs from the prior-season team (a role-changer).

    plus the realized ``ppg`` (target) for scoring. PIT: only the season-team assignment (known at
    draft) and pre-season history enter the forecasts.
    """
    cur = panel[panel["season"] == season][["gsis_id", "pos", "team", "ppg", "weeks"]]
    prior = (panel[panel["season"] == season - 1][["gsis_id", "team", "ppg"]]
             .rename(columns={"team": "prior_team", "ppg": "prior_ppg"}))
    df = cur.merge(prior, on="gsis_id", how="inner")     # returning players only
    if df.empty:
        return df.assign(opp_rate=[], naive_rate=[], is_mover=[])

    # Situation SWAP as a delta on the player's realized prior rate (information-preserving):
    #   log(opp_rate) = log(prior_ppg) − situation[old_team] + situation[new_team]
    # Non-movers get a zero delta ⇒ opp_rate ≡ naive_rate (Phase 7 only moves role-changers).
    sit = dec.situation_
    old = df["prior_team"].map(sit).fillna(0.0).to_numpy()
    new = df["team"].map(sit).fillna(0.0).to_numpy()
    df["naive_rate"] = df["prior_ppg"]
    df["opp_rate"] = df["prior_ppg"].to_numpy() * np.exp(new - old)
    df["is_mover"] = (df["team"] != df["prior_team"]).astype(int)
    df["season"] = season
    return df
