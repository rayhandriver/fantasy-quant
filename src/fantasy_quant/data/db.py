"""DuckDB helpers — the point-in-time store.

Thin wrappers so every source writes tables the same way: a single connection per process,
``CREATE OR REPLACE`` writes, and a ``pulled_at`` stamp on every row (the PIT discipline starts
here — see CLAUDE.md §3.1). Big sources (PBP) are loaded straight from a parquet glob with
``union_by_name`` so per-season schema drift doesn't break the load.
"""

from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

from fantasy_quant.config import DUCKDB_PATH


def utc_now() -> dt.datetime:
    """Timezone-aware UTC timestamp used for ``pulled_at`` stamps."""
    return dt.datetime.now(dt.UTC)


def connect(path=None, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open (creating parent dirs) the DuckDB store. Defaults to ``config.DUCKDB_PATH``."""
    from pathlib import Path

    p = Path(path or DUCKDB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(p), read_only=read_only)


def write_df(con: duckdb.DuckDBPyConnection, table: str, df: pd.DataFrame,
             pulled_at: dt.datetime | None = None) -> int:
    """Replace ``table`` with ``df``, stamping every row with ``pulled_at`` (defaults to now).

    Returns the resulting row count.
    """
    df = df.copy()
    df["pulled_at"] = pulled_at or utc_now()
    con.register("_write_df", df)
    con.execute(f'CREATE OR REPLACE TABLE "{table}" AS SELECT * FROM _write_df')
    con.unregister("_write_df")
    return row_count(con, table)


def write_parquet_glob(con: duckdb.DuckDBPyConnection, table: str, glob: str,
                       pulled_at: dt.datetime | None = None) -> int:
    """Build ``table`` from a parquet glob via ``read_parquet(..., union_by_name=true)``.

    Used for large, per-season-partitioned sources (PBP) whose column sets drift across years.
    The glob is a path we construct ourselves (no untrusted input), so it's inlined.
    """
    pa = pulled_at or utc_now()
    con.execute(
        f'CREATE OR REPLACE TABLE "{table}" AS '
        f"SELECT *, TIMESTAMP '{pa:%Y-%m-%d %H:%M:%S}' AS pulled_at "
        f"FROM read_parquet('{glob}', union_by_name=true)"
    )
    return row_count(con, table)


def append_df(con: duckdb.DuckDBPyConnection, table: str, df: pd.DataFrame,
              pulled_at: dt.datetime | None = None) -> int:
    """Append ``df`` to an existing ``table`` (matched **by column name**, unmatched table columns
    NULL-filled), stamping every appended row with ``pulled_at``. Used to add a newly-available
    season to a table without rebuilding it. Returns the resulting row count.
    """
    df = df.copy()
    df["pulled_at"] = pulled_at or utc_now()
    con.register("_append_df", df)
    con.execute(f'INSERT INTO "{table}" BY NAME SELECT * FROM _append_df')
    con.unregister("_append_df")
    return row_count(con, table)


def row_count(con: duckdb.DuckDBPyConnection, table: str) -> int:
    return con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def list_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    return [r[0] for r in con.execute("SHOW TABLES").fetchall()]


def table_exists(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    return table in list_tables(con)
