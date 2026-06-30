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
- **Vegas markets (first-class):** player props, game totals, spreads, season win totals — free odds API
  (the-odds-api.com free tier) or book scraping; store **de-vig'd** fair lines. *Caveat:* live odds are free,
  but **historical prop lines for backtesting may be the one paid gap** — confirm free coverage before relying
  on props in the walk-forward (see `PLAN.md` open questions).
- **News/injury/depth-chart** text (beat writers, official injury reports, inactives) for the Phase-12 NLP pipeline.

Keep a **point-in-time** discipline: snapshot ADP/odds at fixed dates with timestamps; never let
end-of-season outcomes (or a later odds move) leak into an as-of feature.
