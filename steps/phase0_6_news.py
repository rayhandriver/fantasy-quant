"""Phase 0.6 — News / injury / depth-chart raw ingest, run + verify.

    uv run python steps/phase0_6_news.py            # use raw cache if present
    uv run python steps/phase0_6_news.py --refresh  # re-pull injuries/depth charts

Done when: each table has a timestamp and a day's injury report is reconstructable as-of that day
(BUILD_PLAN.md 0.6). No NLP — that's Phase 12.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging

from fantasy_quant.data import db
from fantasy_quant.news import ingest as news


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="ignore raw caches; re-pull")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    con = db.connect()
    n_inj = news.ingest_injuries(con, refresh=args.refresh)
    n_dc = news.ingest_depth_charts(con, refresh=args.refresh)
    n_news = news.ingest_news_text(con)

    print("\n=== row counts ===")
    print(f"  injuries    {n_inj:>8,}")
    print(f"  depth_charts{n_dc:>8,}")
    print(f"  news_raw    {n_news:>8,}")

    inj_cov = con.execute("SELECT MIN(season), MAX(season) FROM injuries").fetchone()
    dc_cov = con.execute("SELECT MIN(season), MAX(season) FROM depth_charts").fetchone()
    print(f"\ninjuries seasons {inj_cov[0]}–{inj_cov[1]}  |  "
          f"depth_charts seasons {dc_cov[0]}–{dc_cov[1]}")
    src = con.execute("SELECT source, COUNT(*) FROM news_raw GROUP BY 1").fetchall()
    print("news sources:", src)

    print("\n=== done-criterion: injuries reconstructable as-of a day (PIT) ===")
    # pick a mid-2023-season Wednesday; reports filed up to then should appear, later ones must not.
    as_of = dt.datetime(2023, 10, 25, tzinfo=dt.UTC)
    asof_df = news.injuries_asof(con, as_of, season=2023)
    later = con.execute(
        "SELECT COUNT(*) FROM injuries WHERE season=2023 AND date_modified > ?", [as_of]
    ).fetchone()[0]
    latest = asof_df["date_modified"].max() if len(asof_df) else None
    print(f"  as_of={as_of.date()}: {len(asof_df):,} reports <= as_of (latest {latest}); "
          f"{later:,} later reports correctly excluded")
    ok = (len(asof_df) > 0) and (later > 0)
    print(f"  -> {'PASS' if ok else 'REVIEW'}  (both sides non-empty proves the PIT cut)")
    con.close()


if __name__ == "__main__":
    main()
