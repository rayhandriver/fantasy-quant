"""Suite-wide pytest configuration.

``needs_db`` marks a test that reads the project's DuckDB store (``data/fantasy_quant.duckdb``,
~765 MB, gitignored, rebuilt by ``steps/``). Without the store such a test is skipped rather than
failed, so the suite runs anywhere; CI deselects them outright with ``-m "not needs_db"``.
"""

from __future__ import annotations

import pytest

from fantasy_quant.config import DUCKDB_PATH


def pytest_collection_modifyitems(config, items):
    if DUCKDB_PATH.exists():
        return
    skip = pytest.mark.skip(reason=f"project store not present ({DUCKDB_PATH.name})")
    for item in items:
        if "needs_db" in item.keywords:
            item.add_marker(skip)
