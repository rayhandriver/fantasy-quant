# data/

Local data store — **gitignored** (artifacts are large and regenerable via the pipeline). Layout:

| Dir / file | Contents |
|---|---|
| `raw/` | Untouched pulls/scrapes (nfl_data_py play-by-play, PFR season tables, FFCalculator/Underdog ADP snapshots). Immutable once written. |
| `interim/` | Cleaned, joined, partially processed intermediates. |
| `processed/` | Model-ready, point-in-time panels. |
| `fantasy_quant.duckdb` | The DuckDB point-in-time store (set via `DUCKDB_PATH`). |

**Sources (free):** `nfl_data_py` (play-by-play, snaps, targets, weekly fantasy points), Pro-Football-
Reference (season panels), scraped Fantasy Football Calculator (historical ADP) and Underdog (early
best-ball ADP). Keep a **point-in-time** discipline: snapshot ADP at fixed pre-season dates; never let
end-of-season outcomes leak into an as-of feature.
