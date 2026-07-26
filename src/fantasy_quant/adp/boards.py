"""Board resolution — the single answer to *"which consensus board does this draft belong to?"*.

Every consumer of the Sleeper corpus (16.7's drift panel, 11.1's choice frame, 11.2's availability
windows) needs a reference board, and each one used to answer that question for itself. Two facts,
both learned the expensive way, say it must be answered in one place:

1. **A board is keyed by (season, scoring, teams) — never by season alone.** Session F.5's
   format-contamination bug was a hardcoded ``scoring="ppr"`` that pooled dynasty, 2QB and IDP
   rooms onto one board labelled PPR redraft; it was harmless at 149 drafts and 82 % wrong at
   7,699. The same latent bug lived on in the behavioral path (:mod:`draft.opponent_model`,
   :mod:`draft.availability`), which read *all* human drafts against a single 10-team PPR board
   until Session F.6. A board key is a fact about the draft, not a default argument.

2. **FFC publishes no 2025 board at all** (verified live: "No ADP data found."), which strands the
   single largest human cohort in the corpus. FantasyPros ECR covers 2017–2026, so it is the
   fallback — but it is a *different measurement*, and this module never lets that go unlabelled:
   every resolution returns its ``source``, and callers propagate it as ``board_source`` so a
   pooled fit can segment on it.

**What the ECR fallback actually substitutes.** ECR is an expert *ranking*, ADP is realized draft
behaviour. Rank and ADP share units loosely — both order the board in pick space, so ``adp_rounds
= adp / teams`` stays interpretable — but ADP compresses at the top (the consensus 1.01 goes at
1.6, not 1.0) and carries real draft-room noise, while ECR does not. Likewise ``stdev``: FFC's is
dispersion in *picks*, ECR's is disagreement in *expert rank*. They play the same role ("where the
crowd disagrees with itself") in different units. Hence the rule: **never pool ECR-boarded seasons
into a headline that was pre-registered on FFC boards** — report them as a labelled sensitivity.

The 2023-PPR trap is handled here too: that snapshot is stamped ``as_of`` 2024-02-12 with
``is_preseason=False`` (FantasyPros re-touched the page after the Super Bowl). Only preseason
snapshots are eligible as a board, so a post-season re-touch can never masquerade as a draft-day
consensus.
"""

from __future__ import annotations

import pandas as pd

#: Sleeper ``scoring`` values that are genuinely redraft formats with a consensus-board analog,
#: mapped to the board vocabulary. ``dynasty_*``/``2qb``/``idp`` are a different market.
SCORING_MAP: dict[str, str] = {"ppr": "ppr", "half_ppr": "half-ppr", "std": "standard"}

#: FFC publishes 10- and 12-team boards only; a draft reads whichever is closer in size.
FFC_TEAM_SIZES: tuple[int, ...] = (10, 12)

FFC = "ffc"
ECR = "ecr"

#: Columns every resolved board carries, whatever its source.
BOARD_COLS = ["gsis_id", "name", "position", "team", "adp", "stdev", "pos_rank", "snapshot_date"]


def nearest_board_size(teams: int) -> int:
    """The published board size a league of ``teams`` should read (FFC has 10 and 12 only)."""
    return min(FFC_TEAM_SIZES, key=lambda t: abs(t - int(teams)))


def _ffc_board(con, season: int, scoring: str, teams: int) -> pd.DataFrame:
    return con.execute(
        """
        SELECT gsis_id, name, position, team, adp, stdev, pos_rank, snapshot_date
        FROM adp_snapshots
        WHERE season = ? AND source = 'ffc' AND scoring = ? AND teams = ?
          AND gsis_id IS NOT NULL
        QUALIFY snapshot_date = MAX(snapshot_date) OVER ()
        """,
        [int(season), scoring, int(teams)],
    ).df()


def ecr_to_adp_calibration(con, scoring: str) -> tuple[object, int] | None:
    """Learn the ECR-rank → FFC-ADP map from the seasons that have **both**, plus a board depth.

    Substituting raw ECR rank for ADP is not unit-safe, and the size of the error is not a
    rounding detail — measured on 2024 PPR, ECR rank 396 is FFC ADP 193.5, roughly 2× compression,
    and the ECR board is 544–724 deep against FFC's ~200. Used raw, a fringe player ranked 400
    lands 40 "rounds" late on a 10-team board and shows up as a monstrous reach; the first F.6
    panel run duly reported Efton Chism at +17.5 rounds, every top-10 "reach" a 2025 name, and a
    2025 drift sd of 2.67 against ~1.75 everywhere else. That is a measurement artifact, not
    narrative drift.

    So the fallback is **calibrated, not raw**: an isotonic (monotone) fit of rank → ADP pooled
    over the overlapping seasons, and a **truncation depth** = the median FFC board size. Beyond
    that depth FFC simply does not board a player, and neither do we — an unboarded player is
    absent from the panel rather than assigned an extrapolated ADP.

    Returns ``None`` when no season carries both sources, in which case the caller keeps raw rank
    and the row is still labelled ``ecr`` for the reader to judge.
    """
    pairs = con.execute(
        """
        SELECT e.season, CAST(e.ecr AS DOUBLE) AS rank, a.adp
        FROM ecr_snapshots e
        JOIN adp_snapshots a
          ON a.gsis_id = e.gsis_id AND a.season = e.season
        WHERE e.scoring = ? AND e.is_preseason AND a.source = 'ffc' AND a.scoring = ?
          AND a.teams = 10 AND e.gsis_id IS NOT NULL AND a.adp IS NOT NULL
        """,
        [scoring, scoring],
    ).df()
    if len(pairs) < 50:
        return None
    depths = con.execute(
        """
        SELECT season, COUNT(*) AS n FROM adp_snapshots
        WHERE source = 'ffc' AND scoring = ? AND teams = 10 AND gsis_id IS NOT NULL
        GROUP BY season
        """,
        [scoring],
    ).df()
    if depths.empty:
        return None
    from sklearn.isotonic import IsotonicRegression

    iso = IsotonicRegression(increasing=True, out_of_bounds="clip")
    iso.fit(pairs["rank"].to_numpy(), pairs["adp"].to_numpy())
    return iso, int(depths["n"].median())


def _ecr_board(con, season: int, scoring: str) -> pd.DataFrame:
    """ECR shaped into a board. ``adp`` = calibrated pick scale, ``stdev`` = expert disagreement.

    Only ``is_preseason`` snapshots qualify — see the 2023-PPR trap in the module docstring — and
    the rank is put on an ADP scale by :func:`ecr_to_adp_calibration` before it is called a board.
    """
    if not con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name='ecr_snapshots'"
    ).fetchone()[0]:
        return pd.DataFrame(columns=BOARD_COLS)
    board = con.execute(
        """
        SELECT gsis_id, name, position, team,
               CAST(ecr AS DOUBLE) AS adp, ecr_std AS stdev, pos_rank,
               CAST(as_of AS DATE) AS snapshot_date
        FROM ecr_snapshots
        WHERE season = ? AND scoring = ? AND is_preseason AND gsis_id IS NOT NULL
        QUALIFY as_of = MAX(as_of) OVER ()
        """,
        [int(season), scoring],
    ).df()
    if board.empty:
        return board
    calib = ecr_to_adp_calibration(con, scoring)
    if calib is None:                       # no overlapping season: raw rank, still labelled 'ecr'
        return board
    iso, depth = calib
    board = board[board["adp"] <= depth].copy()      # FFC's natural truncation, reproduced
    board["adp"] = iso.predict(board["adp"].to_numpy())
    return board


def resolve_board(con, season: int, scoring: str, teams: int,
                  *, allow_ecr: bool = True) -> tuple[pd.DataFrame, str]:
    """The board for one ``(season, scoring, teams)`` cell, plus the source that answered.

    Tries FFC first (the market-realized ADP every earlier phase was built on) and falls back to
    ECR only when FFC published nothing for that season. Returns ``(board, source)`` where
    ``source`` is :data:`FFC`, :data:`ECR`, or ``""`` when neither has it — an empty board is a
    normal, reportable outcome, not an error.
    """
    ffc = _ffc_board(con, season, scoring, teams)
    if not ffc.empty:
        return ffc, FFC
    if not allow_ecr:
        return ffc, ""
    ecr = _ecr_board(con, season, scoring)
    return (ecr, ECR) if not ecr.empty else (ecr, "")


def resolve_boards(con, keys, *, allow_ecr: bool = True) -> dict[tuple, tuple[pd.DataFrame, str]]:
    """:func:`resolve_board` over many ``(season, scoring, teams)`` keys, read once each."""
    out: dict[tuple, tuple[pd.DataFrame, str]] = {}
    for season, scoring, teams in {(int(s), str(sc), int(t)) for s, sc, t in keys}:
        out[(season, scoring, teams)] = resolve_board(
            con, season, scoring, teams, allow_ecr=allow_ecr)
    return out
