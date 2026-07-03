# data/

Local data store — **gitignored** (artifacts are large and regenerable via the pipeline). Layout:

| Dir / file | Contents |
|---|---|
| `raw/` | Untouched pulls/scrapes (nfl_data_py play-by-play, PFR season tables, FFCalculator/Underdog ADP snapshots). Immutable once written. |
| `interim/` | Cleaned, joined, partially processed intermediates. |
| `processed/` | Model-ready, point-in-time panels. |
| `fantasy_quant.duckdb` | The DuckDB point-in-time store (set via `DUCKDB_PATH`). |

**Sources (free):**
- `nfl_data_py` (play-by-play, snaps, targets, weekly fantasy points) and Pro-Football-Reference (season panels).
- Scraped **ADP** — Fantasy Football Calculator (historical) and Underdog (early best-ball).
- **Vegas markets (first-class):** *(0.5 done)* **game lines** (spreads/totals/moneylines → implied team
  totals) are **free & historical** via nflverse `import_schedules` (2014+) → `game_lines`, stored de-vig'd.
  **Player props** are **live-only** via the-odds-api (`ODDS_API_KEY`) — **historical prop lines are the
  confirmed paid gap**; `props` is only built when a key is set. Season win totals deferred
  (`import_win_totals` empty upstream).
- **News/injury/depth-chart** text (beat writers, official injury reports, inactives) for the Phase-12 NLP pipeline.

Keep a **point-in-time** discipline: snapshot ADP/odds at fixed dates with timestamps; never let
end-of-season outcomes (or a later odds move) leak into an as-of feature.
