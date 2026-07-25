"""Phase 16.3 / 16.3b — the playcaller/coaching reference table.

`reference/coaches.csv` is the one piece of this project with **no free source**: who actually
*calls the offensive plays* is not in any feed we ingest. It is therefore a small, versioned,
**human-approved** table — Claude drafts it via research, the user reviews and corrects it, and only
then may 16.4 fingerprint a scheme from it.

**What is free, and what is not (found 2026-07-24).** `pbp.home_coach` / `pbp.away_coach` yields an
exact, PIT **head coach** per team-season for every team-season 2014-2025 — see
:func:`head_coach_scaffold`. That is *insufficient* on its own (a head coach is the playcaller only
about half the time) but it is a genuine free scaffold, and more usefully it **audits** the curated
table: any curated `head_coach` that disagrees with pbp is a research error, caught with no external
lookup (:func:`audit_against_pbp`). The research burden is thereby reduced to the
`offensive_coordinator` / `play_caller` columns.

**Frozen schema** (user decision 2026-07-24 — `change_from_prev` is dropped in favour of
`in_house`)::

    season, team, head_coach, offensive_coordinator, play_caller, hc_calls_plays, in_house,
    confidence, notes

`in_house` — "the season's play-caller was already on this team's staff the previous season."
`in_house=0` therefore implies a **new playcaller regime** (a 16.4 transport event), but it is
*sufficient, not necessary*: an internal promotion (DEN 2026 — Payton hands the offense to Davis
Webb, already the QB coach) is `in_house=1` and still a new regime. 16.4 must handle those
explicitly; :func:`playcaller_regimes` finds them structurally, by detecting a change of
`play_caller` from the team's previous season rather than trusting the flag.

The table is deliberately **not** a complete staff history. It carries the team-seasons whose
play-caller we need to fingerprint — the prior regimes of incoming playcallers, plus the legacy
DEV-window rows — and the current-season targets.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from fantasy_quant.adp.panel import _canon_team

REFERENCE = Path(__file__).resolve().parents[3] / "reference"
COACHES_CSV = REFERENCE / "coaches.csv"
LINEAGE_CSV = REFERENCE / "coach_lineage.csv"
SIGNED_OFF_2026 = REFERENCE / "coaches_2026_signed_off_2026-07-24.csv"

#: The frozen column order. Anything else in the file is a schema drift and fails the gate.
SCHEMA: tuple[str, ...] = ("season", "team", "head_coach", "offensive_coordinator", "play_caller",
                           "hc_calls_plays", "in_house", "confidence", "notes")

#: Free-text columns that get whitespace-stripped on ingest (the signed-off file has trailing
#: spaces on 5 name fields — BAL x2, LV, PHI x2).
_NAME_COLS: tuple[str, ...] = ("team", "head_coach", "offensive_coordinator", "play_caller")

_CONFIDENCE = ("high", "med", "low")

#: Seasons `pbp` can audit. 2026 has not been played, so 2026 rows are unauditable by construction.
PBP_SEASONS: tuple[int, ...] = tuple(range(2014, 2026))


# ------------------------------------------------------------------------------------------------
# the free scaffold — head coach per team-season, straight out of play-by-play
# ------------------------------------------------------------------------------------------------
def head_coach_scaffold(con, seasons: tuple[int, ...] | None = None) -> pd.DataFrame:
    """Exact head coach per team-season from `pbp`, as ``season · team · head_coach · games ·
    interim``.

    A team-season with a mid-season firing shows **two** coaches in pbp; we take the one who
    coached the most games as `head_coach` and name the other(s) in `interim` (most games first),
    which is the honest reading for a scheme fingerprint — the regime is the one that ran most of
    the season.

    **Known limitation (found 2026-07-25).** The split is only visible for **2014-2023**: 19 of
    those team-seasons carry two coaches. From **2024 onward the field is a season-level coach of
    record**, not the game-day coach — Dennis Allen appears for all 17 of NO 2024 and Brian Daboll
    for all 17 of NYG 2025 despite both being fired in-season. So `interim` is a *lower bound* on
    mid-season changes, and the identity of the season-opening head coach is what this really
    gives us for recent seasons. That is still exactly what the audit needs (is this row about the
    right franchise-season?), but it must not be read as "no coach was fired in 2024-25".

    PIT-trivial: a head coach's identity on game day is known on game day.
    """
    seasons = tuple(seasons) if seasons is not None else PBP_SEASONS
    placeholders = ",".join("?" * len(seasons))
    sides = con.execute(f"""
        SELECT season, team, coach, COUNT(DISTINCT game_id) AS games FROM (
            SELECT DISTINCT season, game_id, home_team AS team, home_coach AS coach
              FROM pbp WHERE home_coach IS NOT NULL AND season IN ({placeholders})
            UNION ALL
            SELECT DISTINCT season, game_id, away_team AS team, away_coach AS coach
              FROM pbp WHERE away_coach IS NOT NULL AND season IN ({placeholders})
        ) GROUP BY 1, 2, 3
    """, [*seasons, *seasons]).df()

    sides["team"] = _canon_team(sides["team"])
    sides["coach"] = sides["coach"].astype("string").str.strip()
    sides = sides.sort_values(["season", "team", "games"], ascending=[True, True, False])

    out = (sides.groupby(["season", "team"], as_index=False)
                .agg(head_coach=("coach", "first"),
                     games=("games", "sum"),
                     interim=("coach", lambda s: " / ".join(list(s)[1:]))))
    return out.reset_index(drop=True)


# ------------------------------------------------------------------------------------------------
# the curated table — read, normalize, gate
# ------------------------------------------------------------------------------------------------
def load_coaches(path: Path | str = COACHES_CSV) -> pd.DataFrame:
    """Read the curated table, applying the frozen ingest transform (strip whitespace on every name
    field, canonical franchise codes, typed flags). `#` header comments are skipped."""
    df = pd.read_csv(path, comment="#")
    for col in _NAME_COLS:
        df[col] = df[col].astype("string").str.strip()
    df["team"] = _canon_team(df["team"])
    df["notes"] = df["notes"].astype("string").fillna("")
    df["confidence"] = df["confidence"].astype("string").str.strip()
    for col in ("season", "hc_calls_plays", "in_house"):
        df[col] = df[col].astype(int)
    return df[list(SCHEMA)].sort_values(["season", "team"]).reset_index(drop=True)


def assert_coaches_schema(df: pd.DataFrame) -> None:
    """Structural gate — the shape a 16.4 consumer is entitled to assume."""
    assert tuple(df.columns) == SCHEMA, f"schema drift: {tuple(df.columns)}"
    assert not df.duplicated(["season", "team"]).any(), "duplicate (season, team) rows"
    for col in _NAME_COLS + ("confidence",):
        blank = df[col].isna() | (df[col].astype(str).str.len() == 0)
        assert not blank.any(), f"empty {col} in rows {df.index[blank].tolist()}"
    assert df["confidence"].isin(_CONFIDENCE).all(), f"bad confidence: {set(df['confidence'])}"
    assert df["hc_calls_plays"].isin((0, 1)).all(), "hc_calls_plays must be 0/1"
    assert df["in_house"].isin((0, 1)).all(), "in_house must be 0/1"

    # the play-caller is one of the two named coaches, and the flag agrees with who it is
    is_hc = df["play_caller"] == df["head_coach"]
    is_oc = df["play_caller"] == df["offensive_coordinator"]
    bad = ~(is_hc | is_oc)
    assert not bad.any(), f"play_caller is neither HC nor OC:\n{df[bad][list(SCHEMA[:5])]}"
    mismatch = df["hc_calls_plays"].astype(bool) != is_hc
    assert not mismatch.any(), f"hc_calls_plays disagrees with play_caller:\n{df[mismatch]}"


def audit_against_pbp(df: pd.DataFrame, scaffold: pd.DataFrame) -> pd.DataFrame:
    """Cross-check every curated `head_coach` against the free pbp scaffold.

    Returns the rows that do **not** match the scaffold's primary head coach, with a `verdict`:

    * `MISMATCH` — the named head coach did not coach that team that season at all. A hard error:
      a wrong head coach almost always means the whole row is about the wrong regime.
    * `split_season` — the named head coach *is* one of the season's two coaches, just not the one
      who coached the most games. Legitimate, and often the correct reading for a play-calling
      row, since a mid-season coaching change and a mid-season play-calling change tend to be the
      same event. Informational.

    An empty frame means every auditable row's head coach is exactly the scaffold's — the cheapest
    possible verification of a researched row. Rows outside :data:`PBP_SEASONS` (i.e. 2026) are
    skipped: the season has not been played.
    """
    auditable = df[df["season"].isin(PBP_SEASONS)]
    merged = auditable.merge(scaffold, on=["season", "team"], how="left",
                             suffixes=("", "_pbp"))
    merged = merged.rename(columns={"head_coach_pbp": "pbp_head_coach", "interim": "pbp_interim"})
    agrees = merged["head_coach"] == merged["pbp_head_coach"]
    on_staff = [hc in str(i).split(" / ")
                for hc, i in zip(merged["head_coach"], merged["pbp_interim"], strict=True)]
    merged["verdict"] = ["split_season" if ok else "MISMATCH" for ok in on_staff]
    cols = ["season", "team", "head_coach", "pbp_head_coach", "pbp_interim", "verdict"]
    return merged.loc[~agrees, cols].reset_index(drop=True)


# ------------------------------------------------------------------------------------------------
# the move-graph cross-reference — the method that found every error in the 2026 half
# ------------------------------------------------------------------------------------------------
def move_graph_check(df: pd.DataFrame) -> list[str]:
    """Internal-consistency findings, with **zero external lookups**.

    Three checks, each of which caught real errors in the signed-off 2026 draft:

    1. **No person holds two jobs in one season** (the same name as play-caller on two teams).
    2. **`in_house` agrees with the table's own history.** `in_house=0` while the same person
       called plays for the same team last season is a contradiction — a **HARD** finding. The
       mirror case (`in_house=1` with a different prior play-caller) is *not* an error: it is the
       **internal promotion** the frozen semantics allow (McCarthy taking the calls back at DAL in
       2023 after four years as its head coach), so it is reported as informational.
    3. **A play-caller's per-team spells have no one-season holes** — a single missing year
       between two present ones is either a missing row or a season the person deliberately did
       not call plays. Both happen (Stefanski handed Cleveland's calls to Ken Dorsey for most of
       2024), so a hole demands an explanation in `notes` rather than being an error on its own.
       Multi-year absences are ordinary departures-and-returns (McDaniels leaving New England and
       coming back) and are not flagged.

    Findings are prefixed `HARD:` (a contradiction to fix), `check:` (must be explained in
    `notes`) or `note:` (expected, explainable). Returns a list of human-readable findings;
    deliberately *reports*, never raises — the user is the judge.
    """
    findings: list[str] = []

    for season, grp in df.groupby("season"):
        dupes = grp["play_caller"].value_counts()
        for name, n in dupes[dupes > 1].items():
            teams = sorted(grp.loc[grp["play_caller"] == name, "team"])
            findings.append(f"HARD: {season}: {name} calls plays for {n} teams "
                            f"({', '.join(teams)})")

    by_team = {(r.season, r.team): r.play_caller for r in df.itertuples()}
    for r in df.itertuples():
        prev = by_team.get((r.season - 1, r.team))
        if prev is None:
            continue
        if r.in_house == 0 and prev == r.play_caller:
            findings.append(f"HARD: {r.season} {r.team}: in_house=0 but {prev} also called plays "
                            f"in {r.season - 1}")
        if r.in_house == 1 and prev != r.play_caller:
            findings.append(f"note: {r.season} {r.team}: internal promotion — {r.play_caller} was "
                            f"already on staff but {prev} called plays in {r.season - 1}")

    for (name, team), grp in df.groupby(["play_caller", "team"]):
        yrs = set(grp["season"])
        for y in range(min(yrs) + 1, max(yrs)):
            if y not in yrs and {y - 1, y + 1} <= yrs:
                findings.append(f"check: {name} @ {team}: one-season hole at {y} inside the "
                                f"{min(yrs)}-{max(yrs)} spell — confirm it is a deliberate "
                                f"exclusion, not a missing row")

    return findings


# ------------------------------------------------------------------------------------------------
# regimes — what 16.4 actually consumes
# ------------------------------------------------------------------------------------------------
def playcaller_regimes(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse the table into **regimes**: one row per contiguous `(play_caller, team)` spell, as
    ``play_caller · team · first_season · last_season · n_seasons · seasons``.

    This is the unit 16.4 fingerprints — a scheme belongs to a spell, not to a season. Contiguity is
    computed from the seasons actually present, so a genuine return to a former team (Josh McDaniels
    at NE, twice) yields two regimes rather than one impossible fourteen-year block.
    """
    rows = []
    for (name, team), grp in df.sort_values("season").groupby(["play_caller", "team"]):
        seasons = sorted(grp["season"])
        spell = [seasons[0]]
        for s in seasons[1:]:
            if s == spell[-1] + 1:
                spell.append(s)
            else:
                rows.append((name, team, spell))
                spell = [s]
        rows.append((name, team, spell))

    out = pd.DataFrame([{"play_caller": n, "team": t, "first_season": sp[0], "last_season": sp[-1],
                         "n_seasons": len(sp), "seasons": ",".join(str(s) for s in sp)}
                        for n, t, sp in rows])
    return out.sort_values(["play_caller", "first_season"]).reset_index(drop=True)


def new_regimes(df: pd.DataFrame, season: int) -> pd.DataFrame:
    """The team-seasons in `season` whose play-caller is new to that team — the **16.4 transport
    set**.

    Uses `in_house=0` as the primary trigger (the frozen flag's meaning) and adds the
    internal-promotion cases structurally: `in_house=1` but the table's own previous-season row for
    that team names a different play-caller. Carries a `trigger` column saying which fired.
    """
    prev = {r.team: r.play_caller for r in df[df["season"] == season - 1].itertuples()}
    cur = df[df["season"] == season].copy()
    changed = cur["team"].map(prev).notna() & (cur["team"].map(prev) != cur["play_caller"])
    cur["trigger"] = pd.Series("", index=cur.index, dtype="string")
    cur.loc[cur["in_house"] == 0, "trigger"] = "external"
    cur.loc[(cur["in_house"] == 1) & changed, "trigger"] = "internal_promotion"
    return cur[cur["trigger"] != ""].reset_index(drop=True)


#: Lineage columns (`reference/coach_lineage.csv`).
LINEAGE_SCHEMA: tuple[str, ...] = ("play_caller", "season", "team", "mentor", "learned_at",
                                   "learned_seasons", "role", "confidence", "notes")


def load_lineage(path: Path | str = LINEAGE_CSV) -> pd.DataFrame:
    """The **fallback prior for a first-time play-caller** (user direction, 2026-07-25).

    A play-caller with no regime of their own is not a blank. They came up inside somebody's
    system, and the honest prior is broad continuity with that system — Declan Doyle held the OC
    title in Chicago while Ben Johnson called the plays, so the 2026 Ravens should look more like
    the 2025 Bears than like nothing at all.

    The table names a **mentor**, not a scheme: 16.4 looks the mentor up in `coaches.csv` and
    fingerprints *their* regimes, which is why every mentor here is itself a play-caller in that
    file. `learned_at`/`learned_seasons` record where the apprenticeship happened and are context —
    the mentor's fingerprint may draw on more seasons than those.
    """
    df = pd.read_csv(path, comment="#")
    for col in ("play_caller", "team", "mentor", "learned_at", "confidence"):
        df[col] = df[col].astype("string").str.strip()
    df["team"] = _canon_team(df["team"])
    df["season"] = df["season"].astype(int)
    df["notes"] = df["notes"].astype("string").fillna("")
    return df[list(LINEAGE_SCHEMA)].reset_index(drop=True)


def fingerprint_source(df: pd.DataFrame, season: int,
                       lineage: pd.DataFrame | None = None) -> pd.DataFrame:
    """**What 16.4 should fingerprint each `season` team on, and how strong the evidence is.**

    Resolution order, most direct first:

    * `own` — the play-caller has prior regimes of their own. Fingerprint those.
    * `lineage` — a first-time play-caller: fall back to their **mentor's** regimes, tagged as
      weaker evidence. `same_team` marks the cases where the mentor's regime is on the team the
      play-caller is now taking over (DEN 2026 Payton→Webb, WAS 2026 Kingsbury→Blough), so lineage
      and team continuity agree — the strongest form of the fallback. Where they disagree (PHI
      2026: Mannion comes from Green Bay, but Philadelphia's 2025 caller was Patullo) 16.4 should
      report both rather than choose silently, which is what `prev_play_caller` is for.
    * `none` — no own regime and no lineage row. 16.4 must stay silent rather than invent a prior.

    Columns: `team · play_caller · source · fingerprint_on · prior_seasons · same_team ·
    prev_play_caller · is_new_regime`. Returns every team in `season`, continuity included, so a
    caller can join it straight onto the transport set.
    """
    lineage = load_lineage() if lineage is None else lineage
    cov = coverage(df, season).set_index(["play_caller", "team"])
    lin = lineage[lineage["season"] == season]
    mentors = {(r.play_caller, r.team): r for r in lin.itertuples()}
    prev = {r.team: r.play_caller for r in df[df["season"] == season - 1].itertuples()}
    new = set(new_regimes(df, season)["team"])
    hist = df[df["season"] < season]

    rows = []
    for r in df[df["season"] == season].sort_values("team").itertuples():
        own = int(cov.loc[(r.play_caller, r.team), "prior_seasons"])
        m = mentors.get((r.play_caller, r.team))
        if own:
            source, on, n, same = "own", r.play_caller, own, pd.NA
        elif m is not None:
            source, on = "lineage", m.mentor
            n = int((hist["play_caller"] == m.mentor).sum())
            same = bool(m.learned_at == r.team)   # a plain bool, not numpy's
        else:
            source, on, n, same = "none", pd.NA, 0, pd.NA
        rows.append({"team": r.team, "play_caller": r.play_caller, "source": source,
                     "fingerprint_on": on, "prior_seasons": n, "same_team": same,
                     "prev_play_caller": prev.get(r.team, pd.NA),
                     "is_new_regime": r.team in new})
    out = pd.DataFrame(rows)
    # nullable boolean, always — otherwise the dtype flips between numpy bool and object
    # depending on whether any `own`/`none` row put an NA in the column.
    out["same_team"] = out["same_team"].astype("boolean")
    return out


def coverage(df: pd.DataFrame, season: int) -> pd.DataFrame:
    """For each play-caller in `season`, how much **prior** history the table gives 16.4 to
    fingerprint them with: ``play_caller · team · prior_seasons · prior_regimes · prior_detail``.

    `prior_seasons == 0` is the 16.3b blocker in one number — a play-caller with no past regime
    cannot be transported, only observed.
    """
    hist = df[df["season"] < season]
    rows = []
    for r in df[df["season"] == season].sort_values("team").itertuples():
        past = hist[hist["play_caller"] == r.play_caller]
        spells = playcaller_regimes(past) if len(past) else pd.DataFrame()
        detail = ("; ".join(f"{s.team} {s.first_season}"
                            + (f"-{s.last_season}" if s.n_seasons > 1 else "")
                            for s in spells.itertuples()) if len(spells) else "")
        rows.append({"play_caller": r.play_caller, "team": r.team, "prior_seasons": len(past),
                     "prior_regimes": len(spells), "prior_detail": detail})
    return pd.DataFrame(rows)
