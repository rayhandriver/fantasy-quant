"""Data-source ingest modules — one file per upstream source.

Each module pulls a raw source, normalizes player identity onto ``gsis_id``, and writes
PIT-stamped tables into the DuckDB store. See ``docs/BUILD_PLAN.md`` Phase 0.
"""
