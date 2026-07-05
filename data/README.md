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
  - **⚠ nflverse restructured player stats after 2024.** `nfl_data_py` is frozen on the dead
    `player_stats` path (404 for 2025+), so **weekly/seasonal for 2025+ are read directly from the new
    `stats_player` release** (`stats_player_week_{yr}` / `stats_player_reg_{yr}`) and conformed to the
    legacy schema — see `data/sources/nflverse.py::backfill_stats_new_release` (step 0.9).
  - **Depth charts changed grain in 2025:** no more `week` — each update is appended with an ISO8601
    `dt` timestamp. Week-grain 2014–24 lives in `depth_charts`; timestamped 2025+ in **`depth_charts_ts`**.
  - **2025 = a projection-calibration holdout** (realized outcomes present; no 2025 ADP board yet, so it
    is *not* in the draft-backtest lockbox — `config.CALIBRATION_SEASONS`).
- Scraped **ADP** — Fantasy Football Calculator (historical) and Underdog (early best-ball).
- **Vegas markets (first-class):** *(0.5 done)* **game lines** (spreads/totals/moneylines → implied team
  totals) are **free & historical** via nflverse `import_schedules` (2014+) → `game_lines`, stored de-vig'd.
  **Player props** are **live-only** via the-odds-api (`ODDS_API_KEY`) — **historical prop lines are the
  confirmed paid gap**; `props` is only built when a key is set. Season win totals deferred
  (`import_win_totals` empty upstream).
- **News/injury/depth-chart** text (beat writers, official injury reports, inactives) for the Phase-12 NLP pipeline.

Keep a **point-in-time** discipline: snapshot ADP/odds at fixed dates with timestamps; never let
end-of-season outcomes (or a later odds move) leak into an as-of feature.
