"""DuckDB helpers — the point-in-time store.

Thin wrappers so every source writes tables the same way: a single connection per process,
``CREATE OR REPLACE`` writes, and a ``pulled_at`` stamp on every row (the PIT discipline starts
here — see CLAUDE.md §3.1). Big sources (PBP) are loaded straight from a parquet glob with
``union_by_name`` so per-season schema drift doesn't break the load.
"""

from __future__ import annotations

import contextlib
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


@contextlib.contextmanager
def deterministic_reads(con: duckdb.DuckDBPyConnection):
    """Run a block of reads with DuckDB pinned to one thread, restoring the setting afterwards.

    ★ **This is T13's fix, and the register's stated cause was wrong.** The symptom was that the
    Phase-5 cloud was not reproducible across processes: same seed, fresh interpreter, per-player
    ``q10``/``q90`` moved (dress-rehearsal coverage alternating 75.5 ↔ 76.5 %). The suspect on file
    was the Iman–Conover permutation in the Phase-8 coupling. It is not:

    * the row order is **identical** across processes (the sampler's rng stream therefore lines up
      player-for-player), and the marginals barely move — so nothing is being shuffled;
    * pinning ``PYTHONHASHSEED`` changes nothing (no set/dict ordering leaks into a result);
    * pinning the BLAS thread count changes nothing (the fits are not the source);
    * pinning **DuckDB** to one thread makes ``quantile_projection`` and ``availability_projection``
      bit-identical across processes, and with them the whole cloud.

    The cause is float aggregation inside DuckDB: a parallel ``SUM``/``AVG`` adds its partitions in
    whatever order the threads finish, and floating-point addition is not associative. The training
    frames therefore differ in the last bits between runs, the quantile and hazard fits differ in
    the last bits of their coefficients, and the sampler turns that into a *visibly* different
    per-player draw. **A reproducibility bug does not have to live in the random number generator.**

    Cost, measured on the 2025/2026 clouds: none — 10.2 s → 9.1 s, because these queries are small
    enough that thread coordination costs more than it buys. That is why this wraps the assembler
    wholesale rather than hunting the one offending aggregate.

    A connection that cannot report its own thread count (a stub in an offline test) is yielded
    untouched: this is a determinism *guarantee* where DuckDB is real, never a hard dependency on
    it being real.
    """
    try:
        prev = int(con.execute("SELECT current_setting('threads')").fetchone()[0])
    except Exception:                                   # not a real DuckDB connection
        yield con
        return
    con.execute("SET threads TO 1")
    try:
        yield con
    finally:
        con.execute(f"SET threads TO {prev}")


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
