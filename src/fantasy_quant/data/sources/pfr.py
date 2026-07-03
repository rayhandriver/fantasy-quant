"""Phase 0.3 — Pro-Football-Reference advanced season panels.

**Source choice (documented deviation):** we pull PFR's advanced season tables through
``nfl_data_py.import_seasonal_pfr`` — which mirrors PFR via the nflverse-data releases — rather
than scraping pro-football-reference.com directly. It's the *same PFR data*, but reproducible,
cached, and respectful of PFR's aggressive rate-limiting / bot-protection. (The raw httpx+bs4
scraping stack is reserved for 0.4 ADP, where direct scraping is genuinely required.)

These advanced metrics are **not** in the base nflverse weekly/seasonal tables — they're the
extra features 0.3 is meant to add:
  - **rec:**  YBC (yards before catch), YAC, ADOT, broken tackles, drops, drop%
  - **rush:** YBC, YAC/att, broken tackles
  - **pass:** pressures / blitzes / hurries, on-target%, play-action, RPO, scrambles

Identity: every PFR row carries ``pfr_id`` -> mapped to ``gsis_id`` via the ``player_ids``
crosswalk (the same pattern snaps used in 0.2). Tables: ``pfr_pass`` / ``pfr_rec`` / ``pfr_rush``
(kept separate rather than one ``pfr_seasonal`` — their schemas don't overlap cleanly and ``yds``
means different things per type).
"""

from __future__ import annotations

import logging

import nfl_data_py as nfl
import pandas as pd

from fantasy_quant.config import PROJECT_ROOT, RAW_DIR
from fantasy_quant.data import cache, db

log = logging.getLogger(__name__)

DEFAULT_YEARS: list[int] = list(range(2014, 2026))
PFR_RAW = RAW_DIR / "pfr"
OVERRIDES_CSV = PROJECT_ROOT / "reference" / "pfr_id_overrides.csv"
STAT_TYPES = ("pass", "rec", "rush")


def _pull_seasonal(stat_type: str, years) -> pd.DataFrame:
    """Pull one PFR advanced table per year, skipping (logging) years that fail."""
    frames = []
    for y in years:
        try:
            frames.append(nfl.import_seasonal_pfr(stat_type, [y]))
        except Exception as e:  # noqa: BLE001
            log.warning("skip pfr %s year %d: %s", stat_type, y, e)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _load_overrides() -> pd.DataFrame:
    """Manual pfr_id -> gsis_id fixes (committed at ``reference/pfr_id_overrides.csv``)."""
    if OVERRIDES_CSV.exists():
        ov = pd.read_csv(OVERRIDES_CSV, dtype=str)
        if {"pfr_id", "gsis_id"}.issubset(ov.columns):
            return ov.dropna(subset=["pfr_id", "gsis_id"]).drop_duplicates("pfr_id")
    return pd.DataFrame(columns=["pfr_id", "gsis_id"])


def map_pfr_ids(df: pd.DataFrame, ids: pd.DataFrame,
                overrides: pd.DataFrame | None = None) -> pd.DataFrame:
    """Attach ``gsis_id`` via the ``player_ids.pfr_id`` crosswalk, then apply manual overrides."""
    xwalk = (
        ids.dropna(subset=["pfr_id", "gsis_id"])
        .drop_duplicates("pfr_id")[["pfr_id", "gsis_id"]]
    )
    out = df.merge(xwalk, on="pfr_id", how="left")
    if overrides is not None and len(overrides):
        fill = out["pfr_id"].map(overrides.set_index("pfr_id")["gsis_id"])
        out["gsis_id"] = out["gsis_id"].fillna(fill)
    return out


def ingest_pfr_seasonal(con, years=DEFAULT_YEARS, refresh: bool = False) -> dict:
    """Ingest the three PFR advanced season tables, gsis-mapped, logging unmatched ids."""
    ids = con.execute("SELECT pfr_id, gsis_id FROM player_ids").df()
    overrides = _load_overrides()
    counts: dict[str, int] = {}
    unmatched = []
    for st in STAT_TYPES:
        df = cache.load_or_pull(
            PFR_RAW / f"seasonal_{st}.parquet",
            lambda st=st: _pull_seasonal(st, years),
            refresh=refresh,
        )
        if df.empty:
            log.warning("pfr %s returned no rows", st)
            continue
        df = map_pfr_ids(df, ids, overrides)
        miss = df[df["gsis_id"].isna()][["pfr_id", "player", "season"]].drop_duplicates()
        if len(miss):
            unmatched.append(miss.assign(stat_type=st))
        counts[f"pfr_{st}"] = db.write_df(con, f"pfr_{st}", df)
    if unmatched:
        out = PFR_RAW / "unmatched_pfr_ids.csv"
        pd.concat(unmatched, ignore_index=True).to_csv(out, index=False)
        log.info("logged unmatched pfr_ids -> %s", out)
    return counts


def match_rate(con) -> dict:
    """Fraction of PFR rows that resolved to a ``gsis_id`` (per table)."""
    res = {}
    for st in STAT_TYPES:
        table = f"pfr_{st}"
        if not db.table_exists(con, table):
            continue
        total, matched = con.execute(
            f'SELECT COUNT(*), COUNT(gsis_id) FROM "{table}"'
        ).fetchone()
        res[table] = {
            "rows": int(total),
            "matched": int(matched),
            "unmatched_rate": (total - matched) / total if total else float("nan"),
        }
    return res


def reconcile(con) -> dict:
    """Cross-check PFR yards vs nflverse ``seasonal`` (REG) for matched players — validates the
    pfr_id->gsis mapping (mismatched ids would blow up the % diff)."""
    res = {}
    for st, seas_col in [("rec", "receiving_yards"), ("rush", "rushing_yards")]:
        df = con.execute(
            f"""
            WITH p AS (
                SELECT gsis_id, season, SUM(yds) AS pfr_yds
                FROM pfr_{st} WHERE gsis_id IS NOT NULL GROUP BY 1, 2
            ),
            s AS (
                SELECT gsis_id, season, SUM({seas_col}) AS nfl_yds
                FROM seasonal WHERE season_type = 'REG' GROUP BY 1, 2
            )
            SELECT p.pfr_yds, s.nfl_yds
            FROM p JOIN s USING (gsis_id, season)
            WHERE s.nfl_yds > 50
            """
        ).df()
        if df.empty:
            res[st] = {"matched": 0}
            continue
        abs_pct = (df["pfr_yds"] - df["nfl_yds"]).abs() / df["nfl_yds"]
        res[st] = {
            "matched": int(len(df)),
            "median_abs_pct": float(abs_pct.median()),
            "p90_abs_pct": float(abs_pct.quantile(0.9)),
        }
    return res
