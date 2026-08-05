"""Phase 0.13.1 — the **defensive play-caller regime table** (T48).

DATA-1 banked 478,989 participation plays carrying ``defense_personnel``,
``number_of_pass_rushers``, ``defense_man_zone_type`` and ``defense_coverage_type``, and none of
it can be assigned to a coordinator, a tenure or a person: ``reference/coaches.csv`` is offense-only
by construction. So :mod:`fantasy_quant.situation.fingerprint`'s entire apparatus — within-season
z-scoring, empirical-Bayes shrinkage by regime length, PARTIAL-season week-pinning — has no
defensive counterpart to run on, and every defensive question in the store is person-anonymous.

★ **Only the subject is new; the method is the offensive table's, deliberately.** ``coaches.csv``
took three correction rounds before sign-off and its disciplines are all here unchanged:
majority-of-games inclusion, PARTIAL seasons pinned or dropped rather than averaged, ``head_coach``
auto-filled from ``pbp`` (exact and PIT) so human effort lands only on the coordinator columns,
``in_house`` meaning *this season's caller was already on staff last season*, explicit ``(none)``
/``(unknown)`` sentinels, a per-row ``confidence``, and a **user sign-off gate** before 0.13.8
consumes any of it.

★ **Four of the offensive module's functions are side-agnostic and are reused verbatim** —
:func:`~fantasy_quant.situation.coaches.head_coach_scaffold`, ``audit_against_pbp``,
``move_graph_check`` and ``playcaller_regimes``/``new_regimes`` touch only
``season``/``team``/``play_caller``/``in_house``/``head_coach``, which both schemas share. Copying
them would have meant maintaining the move-graph logic twice, and that logic is what found every
error in the offensive table's 2026 half.

⚠ **``base_front`` and ``coverage_identity`` are deliberately NOT columns here.** They are
derivable from 0.13.2's snap shares, and the 16.5 derived-vs-curated rule says a question a feed
can answer gets no human maintainer. **The CSV carries only what no feed knows: who called it.**
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from fantasy_quant.adp.panel import _canon_team
from fantasy_quant.situation.coaches import (
    PBP_SEASONS,
    audit_against_pbp,
    head_coach_scaffold,
    move_graph_check,
    new_regimes,
    playcaller_regimes,
)

__all__ = [
    "SCHEMA", "LINEAGE_SCHEMA", "DEFENSE_COACHES_CSV", "DEFENSE_LINEAGE_CSV", "PBP_SEASONS",
    "load_defense_coaches", "assert_defense_schema", "load_defense_lineage",
    "assert_lineage_schema", "coverage",
    # reused unchanged from the offensive module — see the module docstring
    "head_coach_scaffold", "audit_against_pbp", "move_graph_check",
    "playcaller_regimes", "new_regimes",
]

REFERENCE = Path(__file__).resolve().parents[3] / "reference"
DEFENSE_COACHES_CSV = REFERENCE / "defense_coaches.csv"
DEFENSE_LINEAGE_CSV = REFERENCE / "defense_lineage.csv"

#: The frozen column order. Mirrors ``coaches.SCHEMA`` with the two offensive fields swapped.
SCHEMA: tuple[str, ...] = ("season", "team", "head_coach", "defensive_coordinator", "play_caller",
                           "hc_calls_defense", "in_house", "confidence", "notes")

LINEAGE_SCHEMA: tuple[str, ...] = ("play_caller", "season", "team", "mentor", "learned_at",
                                   "learned_seasons", "role", "confidence", "notes")

_NAME_COLS: tuple[str, ...] = ("team", "head_coach", "defensive_coordinator", "play_caller")
_CONFIDENCE = ("high", "med", "low")

#: Explicit sentinels — the difference between "there was no such job" and "we did not verify it".
NO_COORDINATOR = "(none)"
UNKNOWN = "(unknown)"


def load_defense_coaches(path: Path | str = DEFENSE_COACHES_CSV) -> pd.DataFrame:
    """Read the curated defensive table, applying the frozen ingest transform."""
    df = pd.read_csv(path, comment="#")
    for col in _NAME_COLS:
        df[col] = df[col].astype("string").str.strip()
    df["team"] = _canon_team(df["team"])
    df["notes"] = df["notes"].astype("string").fillna("")
    df["confidence"] = df["confidence"].astype("string").str.strip()
    for col in ("season", "hc_calls_defense", "in_house"):
        df[col] = df[col].astype(int)
    return df[list(SCHEMA)].sort_values(["season", "team"]).reset_index(drop=True)


def assert_defense_schema(df: pd.DataFrame) -> None:
    """Structural gate — the shape a 0.13.8 consumer is entitled to assume.

    The last two checks are the ones that matter: a ``play_caller`` who is neither the head coach
    nor the named coordinator means the row does not identify anybody, and an ``hc_calls_defense``
    flag that disagrees with who the play-caller actually is makes the flag worse than absent,
    because a consumer will believe it.
    """
    assert tuple(df.columns) == SCHEMA, f"schema drift: {tuple(df.columns)}"
    assert not df.duplicated(["season", "team"]).any(), "duplicate (season, team) rows"
    for col in _NAME_COLS + ("confidence",):
        blank = df[col].isna() | (df[col].astype(str).str.len() == 0)
        assert not blank.any(), f"empty {col} in rows {df.index[blank].tolist()}"
    assert df["confidence"].isin(_CONFIDENCE).all(), f"bad confidence: {set(df['confidence'])}"
    assert df["hc_calls_defense"].isin((0, 1)).all(), "hc_calls_defense must be 0/1"
    assert df["in_house"].isin((0, 1)).all(), "in_house must be 0/1"

    known = df["play_caller"] != UNKNOWN
    is_hc = df["play_caller"] == df["head_coach"]
    is_dc = df["play_caller"] == df["defensive_coordinator"]
    # ★ A TITLE-LESS play-caller is legal exactly where the coordinator column carries the (none)
    # sentinel. NE 2018 is the case that found this: New England carried no defensive coordinator
    # after Patricia left, and Brian Flores called the defense as linebackers coach. Demanding
    # play_caller ∈ {head_coach, coordinator} there forces a choice between fabricating a title and
    # losing a real regime — and the regime is the thing 0.13.8 exists to fingerprint. Where a
    # coordinator DOES exist the original rule stands: a third name identifies nobody.
    titleless = df["defensive_coordinator"] == NO_COORDINATOR
    bad = known & ~(is_hc | is_dc | titleless)
    assert not bad.any(), f"play_caller is neither HC nor DC:\n{df[bad][list(SCHEMA[:5])]}"
    mismatch = known & (df["hc_calls_defense"].astype(bool) != is_hc)
    assert not mismatch.any(), f"hc_calls_defense disagrees with play_caller:\n{df[mismatch]}"


def load_defense_lineage(path: Path | str = DEFENSE_LINEAGE_CSV) -> pd.DataFrame:
    """The mentor fallback for a **first-time** defensive play-caller.

    Same contract as the offensive lineage file: 0.13.8 resolves own regimes → else the mentor's
    regimes → else **nothing**. Scoped (user decision, 2026-08-03) to the 2026 first-timers only —
    the branches nobody will ever resolve against are not worth researching.
    """
    df = pd.read_csv(path, comment="#")
    for col in ("play_caller", "team", "mentor", "learned_at", "role", "confidence"):
        df[col] = df[col].astype("string").str.strip()
    df["team"] = _canon_team(df["team"])
    df["notes"] = df["notes"].astype("string").fillna("")
    df["season"] = df["season"].astype(int)
    return df[list(LINEAGE_SCHEMA)].reset_index(drop=True)


def assert_lineage_schema(df: pd.DataFrame, coaches: pd.DataFrame | None = None) -> None:
    """Structural gate. If ``coaches`` is given, every mentor must itself be a play-caller in it —
    otherwise the fallback lands on nothing, which is the one thing it exists to prevent."""
    assert tuple(df.columns) == LINEAGE_SCHEMA, f"schema drift: {tuple(df.columns)}"
    assert not df.duplicated(["play_caller", "season", "team"]).any(), "duplicate lineage rows"
    assert df["confidence"].isin(_CONFIDENCE).all(), f"bad confidence: {set(df['confidence'])}"
    if coaches is not None:
        callers = set(coaches["play_caller"])
        orphans = sorted(set(df["mentor"]) - callers)
        assert not orphans, f"mentors with no regime to fingerprint: {orphans}"


def coverage(df: pd.DataFrame, season: int) -> pd.DataFrame:
    """Per team in ``season``: does this play-caller have prior history to fingerprint?

    ★ The done-bar is *"the table is right and the first-timers are labelled"*, **not** "everyone
    has history". The offensive build found five genuinely first-time play-callers and the correct
    behaviour was for 16.4 to stay silent on them rather than invent a prior.
    """
    prior = (df[df["season"] < season]
             .groupby("play_caller")
             .agg(prior_seasons=("season", "nunique"),
                  prior_teams=("team", lambda s: ",".join(sorted(set(s)))))
             .reset_index())
    cur = df[df["season"] == season][["season", "team", "play_caller", "confidence"]]
    out = cur.merge(prior, on="play_caller", how="left")
    out["prior_seasons"] = out["prior_seasons"].fillna(0).astype(int)
    out["prior_teams"] = out["prior_teams"].fillna("")
    out["first_time"] = out["prior_seasons"] == 0
    return out.sort_values(["first_time", "team"]).reset_index(drop=True)
