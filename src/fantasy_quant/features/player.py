"""Phase 3.3 — player-intrinsic features (age, draft capital, experience, athletic profile).

One row per **(gsis_id, season)** for skill players: the *who* of a player, mostly season-invariant
(draft capital, combine athleticism) plus the two that move each year (**age as-of the draft** and
**experience**). These are the rookie-projection inputs the reframe calls for (a rookie has no prior
production but *does* have draft capital + athletic + landing spot), so they must not punt to ADP.

Sources: ``player_ids`` (birthdate, draft slot, height/weight), ``combine`` (forty/vertical/…, via
``pfr_id``), ``weekly`` (the skill-player universe + entry season). **College production
(dominator / breakout age) is deferred** (user decision 2026-07-04) — add a CFBref ingest later.

PIT: age is computed as-of **Sep 1 of the season** (≈ draft time), never end-of-season, and only for
seasons on/after the player's entry — no future birthdays.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

UNDRAFTED_OVR = 262  # one past the last pick of a 7-round draft — the "draft capital" of an UDFA
UNDRAFTED_ROUND = 8

FEATURE_COLS = [
    "age", "experience", "is_rookie", "draft_ovr", "draft_round", "is_undrafted",
    "bmi", "forty", "vertical", "broad_jump", "cone", "shuttle", "bench",
]
_ATHLETIC = ["forty", "vertical", "broad_jump", "cone", "shuttle", "bench"]


def player_features(con, seasons=None) -> pd.DataFrame:
    """Realized per-(gsis_id, season) player-intrinsic features for skill players (FEATURE_COLS)."""
    where_season = ""
    if seasons is not None:
        yrs = ", ".join(str(int(s)) for s in seasons)
        where_season = f"AND w.season IN ({yrs})"

    sql = f"""
    WITH uni AS (  -- the skill-player universe + primary position, one row per (gsis, season)
        SELECT gsis_id, season,
               ARG_MAX(position, g) AS position
        FROM (SELECT gsis_id, season, position, COUNT(*) AS g FROM weekly w
              WHERE season_type='REG' AND position IN ('QB','RB','WR','TE') AND gsis_id IS NOT NULL
                    {where_season}
              GROUP BY gsis_id, season, position)
        GROUP BY gsis_id, season
    ),
    entry AS (SELECT gsis_id, MIN(season) AS first_season FROM weekly
              WHERE position IN ('QB','RB','WR','TE') AND gsis_id IS NOT NULL GROUP BY gsis_id),
    ids AS (
        SELECT gsis_id, MAX(birthdate) AS birthdate, MAX(draft_year) AS draft_year,
               MAX(draft_round) AS draft_round, MAX(draft_ovr) AS draft_ovr,
               MAX(TRY_CAST(height AS DOUBLE)) AS height, MAX(TRY_CAST(weight AS DOUBLE)) AS weight,
               MAX(pfr_id) AS pfr_id
        FROM player_ids WHERE gsis_id IS NOT NULL GROUP BY gsis_id
    ),
    comb AS (  -- combine athletic profile, mapped to gsis via pfr_id
        SELECT p.gsis_id,
               MAX(c.forty) AS forty, MAX(c.vertical) AS vertical, MAX(c.broad_jump) AS broad_jump,
               MAX(c.cone) AS cone, MAX(c.shuttle) AS shuttle, MAX(c.bench) AS bench
        FROM combine c JOIN (SELECT DISTINCT gsis_id, pfr_id FROM player_ids
                             WHERE gsis_id IS NOT NULL AND pfr_id IS NOT NULL) p
                        ON p.pfr_id=c.pfr_id
        GROUP BY p.gsis_id
    )
    SELECT u.gsis_id, u.season, u.position,
           i.birthdate, i.draft_year, i.draft_round, i.draft_ovr, i.height, i.weight,
           e.first_season,
           c.forty, c.vertical, c.broad_jump, c.cone, c.shuttle, c.bench
    FROM uni u
    LEFT JOIN ids i ON i.gsis_id=u.gsis_id
    LEFT JOIN entry e ON e.gsis_id=u.gsis_id
    LEFT JOIN comb c ON c.gsis_id=u.gsis_id
    """
    return _finalize(con.execute(sql).df())


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Age as-of Sep-1 + experience + draft-capital sentinels + BMI; assert age plausible/finite."""
    asof = pd.to_datetime(df["season"].astype(int).astype(str) + "-09-01")
    bd = pd.to_datetime(df["birthdate"], errors="coerce")
    df["age"] = ((asof - bd).dt.days / 365.25).round(2)

    # draft_year is sometimes 0/bogus in the crosswalk -> treat <1990 as missing, fall back to the
    # player's first observed season (they're always in weekly, so first_season is populated).
    dy = pd.to_numeric(df["draft_year"], errors="coerce").where(lambda s: s >= 1990)
    fs = pd.to_numeric(df["first_season"], errors="coerce")
    entry = dy.fillna(fs)
    df["experience"] = (df["season"] - entry).clip(lower=0, upper=30).fillna(0)
    df["is_rookie"] = (df["season"] <= entry.fillna(df["season"])).astype(int)

    df["is_undrafted"] = df["draft_ovr"].isna().astype(int)
    df["draft_ovr"] = pd.to_numeric(df["draft_ovr"], errors="coerce").fillna(UNDRAFTED_OVR)
    df["draft_round"] = pd.to_numeric(df["draft_round"], errors="coerce").fillna(UNDRAFTED_ROUND)

    ht = pd.to_numeric(df["height"], errors="coerce")
    wt = pd.to_numeric(df["weight"], errors="coerce")
    df["bmi"] = (wt / (ht ** 2) * 703).replace([np.inf, -np.inf], np.nan)

    # age/athletic/bmi may be genuinely missing (no birthdate for ~0.1% fringe players; no combine)
    # -> leave NaN here; 3.5 adds missing-flags and imputes. Where age IS present it must be sane.
    present = df["age"].notna()
    assert df.loc[present, "age"].between(18, 50).all(), \
        f"age out of [18,50]: {df.loc[present, 'age'].min()}..{df.loc[present, 'age'].max()}"
    # experience/draft-capital have no-NaN sentinels -> always finite.
    always = ["experience", "is_rookie", "draft_ovr", "draft_round", "is_undrafted"]
    assert np.isfinite(df[always].to_numpy(dtype=float)).all(), "non-finite intrinsic feature"
    keep = ["gsis_id", "season", "position", *FEATURE_COLS]
    return df[keep].copy()
