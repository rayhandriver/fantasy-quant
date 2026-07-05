"""Phase 3.5 — the standardized, point-in-time exposure matrix ``X`` (the engine's output).

Assembles the four factor families (3.1–3.4) into **one design matrix to project a target season**,
with the **PIT lag applied here** (the whole reason the modules stay lag-free):

  - **production** (opportunity 3.1 + efficiency 3.2) ← season **target-1** (what he just did);
  - **intrinsic** (player 3.3) ← as-of **target** (age/experience move; draft/athletic static);
  - **environment** (3.4) ← season **target-1** of the player's **target team** (the situation
    they enter — correct for movers *and* rookies: a rookie's landing-spot prior-year offense).

Then **winsorized cross-sectional z-scores per position**, explicit missingness (rookies get
a ``no_prior`` flag + imputation, never a silent 0), and a documented manifest. This matrix is what
Phase 4 (rookie model, calibration), Phase 5 (variance), Phase 6 (ADP softness) and Phase 7
(opportunity-adjusted) all read. ``assert_exposures_pit`` guarantees no feature used data ≥ target.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.features import efficiency, environment, opportunity, player

SKILL = ("QB", "RB", "WR", "TE")

# binary flags are passed through as 0/1 (not z-scored); everything else is a continuous exposure.
_FLAG_COLS = ["is_rookie", "is_undrafted"]
_CONT_COLS = (
    [c for c in opportunity.FEATURE_COLS]
    + [c for c in efficiency.FEATURE_COLS]
    + [c for c in player.FEATURE_COLS if c not in _FLAG_COLS]
    + [c for c in environment.FEATURE_COLS]
)
# missingness indicators surfaced to the model (informative, not silently imputed away).
_MISSING_FLAGS = ["no_prior", "age_missing", "athletic_missing"]
_ATHLETIC = ["forty", "vertical", "broad_jump", "cone", "shuttle", "bench"]
IDENTITY = ["gsis_id", "season", "position", "team", "prior_team"]

# the full feature manifest downstream models select on.
FEATURE_MANIFEST = [f"{c}_z" for c in _CONT_COLS] + _FLAG_COLS + _MISSING_FLAGS


# --------------------------------------------------------------------------------------------
# standardization (pure, unit-tested)
# --------------------------------------------------------------------------------------------
def standardize_within_position(df: pd.DataFrame, cols, winsor=(0.02, 0.98)) -> pd.DataFrame:
    """Winsorized cross-sectional z-score of ``cols`` within each ``position`` group. Missing values
    are imputed to the group median **before** z (so z is on a complete column) and a global
    fallback covers a group that is entirely missing. Adds ``{col}_z``; leaves raw cols intact."""
    out = df.copy()
    lo, hi = winsor
    for c in cols:
        z = pd.Series(0.0, index=out.index)
        for _, idx in out.groupby("position").groups.items():
            s = pd.to_numeric(out.loc[idx, c], errors="coerce")
            med = s.median()
            s = s.fillna(med if pd.notna(med) else 0.0)
            if pd.notna(med):
                s = s.clip(lower=s.quantile(lo), upper=s.quantile(hi))
            sd = s.std(ddof=0)
            z.loc[idx] = (s - s.mean()) / sd if sd > 1e-9 else 0.0
        out[f"{c}_z"] = z.fillna(0.0)
    return out


# --------------------------------------------------------------------------------------------
# the PIT guard
# --------------------------------------------------------------------------------------------
def assert_exposures_pit(prod_season: int, env_season: int, target_season: int) -> bool:
    """No production/environment feature may use data from on/after the target season."""
    assert prod_season < target_season, f"production {prod_season} not < target {target_season}"
    assert env_season < target_season, f"environment {env_season} not < target {target_season}"
    return True


# --------------------------------------------------------------------------------------------
# assembly
# --------------------------------------------------------------------------------------------
def _universe(con, target_season: int) -> pd.DataFrame:
    """Skill players active in ``target_season`` + their primary team/position (rows to project)."""
    return con.execute(
        """
        SELECT gsis_id, season, ARG_MAX(recent_team, g) AS team, ARG_MAX(position, g) AS position
        FROM (SELECT gsis_id, season, recent_team, position, COUNT(*) AS g FROM weekly
              WHERE season_type='REG' AND position IN ('QB','RB','WR','TE') AND gsis_id IS NOT NULL
                    AND season = ?
              GROUP BY gsis_id, season, recent_team, position)
        GROUP BY gsis_id, season
        """,
        [int(target_season)],
    ).df()


def build_exposures(con, target_season: int, winsor=(0.02, 0.98)) -> pd.DataFrame:
    """Assemble the PIT exposure matrix to project ``target_season``. Returns identity columns +
    the standardized :data:`FEATURE_MANIFEST` (one finite row per skill player) + raw ``age``."""
    target_season = int(target_season)
    prior = target_season - 1
    assert_exposures_pit(prior, prior, target_season)

    uni = _universe(con, target_season)                          # gsis, season, team, position
    # select only what X needs from each family (avoids raw-counting column collisions on merge).
    opp = opportunity.opportunity_features(con, [prior])[
        ["gsis_id", "team", *opportunity.FEATURE_COLS]].rename(columns={"team": "prior_team"})
    eff = efficiency.efficiency_features(con, [prior])[["gsis_id", *efficiency.FEATURE_COLS]]
    plr = player.player_features(con, [target_season])[["gsis_id", *player.FEATURE_COLS]]
    env = environment.environment_features(con, [prior])[["team", *environment.FEATURE_COLS]]

    prod = opp.merge(eff, on="gsis_id", how="outer")             # prior-season production, by gsis
    df = uni.merge(prod, on="gsis_id", how="left")
    df["no_prior"] = df[opportunity.FEATURE_COLS[0]].isna().astype(int)  # no prior production
    df = df.merge(plr, on="gsis_id", how="left")
    # environment of the team the player is ENTERING (target-season team), valued at prior season.
    df = df.merge(env, on="team", how="left")

    df["changed_team"] = ((df["prior_team"].notna()) & (df["prior_team"] != df["team"])).astype(int)
    df["age_missing"] = df["age"].isna().astype(int)
    df["athletic_missing"] = df[_ATHLETIC].isna().all(axis=1).astype(int)
    for c in _FLAG_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    df = standardize_within_position(df, _CONT_COLS, winsor=winsor)

    cols = IDENTITY + ["age", "changed_team"] + FEATURE_MANIFEST
    out = df[cols].copy()
    feat = out[FEATURE_MANIFEST].to_numpy(dtype=float)
    assert np.isfinite(feat).all(), "non-finite value in exposure matrix"
    assert not out.duplicated("gsis_id").any(), "duplicate gsis in exposure matrix"
    return out.reset_index(drop=True)
