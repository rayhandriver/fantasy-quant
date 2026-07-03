"""Phase 0.5 — Vegas markets ingest, run + verify.

    uv run python steps/phase0_5_markets.py            # use raw cache if present
    uv run python steps/phase0_5_markets.py --refresh  # re-pull nflverse schedules

Done when: de-vig'd two-way markets sum to ~1.0, implied team totals are sane (~17–30), and
``odds_asof`` is PIT (BUILD_PLAN.md 0.5). Player props skip cleanly without ODDS_API_KEY.
"""

from __future__ import annotations

import argparse
import logging

from fantasy_quant.data import db
from fantasy_quant.markets import odds_ingest as oi


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="ignore raw caches; re-pull")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    con = db.connect()
    n = oi.ingest_game_lines(con, refresh=args.refresh)
    cov = con.execute("SELECT MIN(season), MAX(season) FROM game_lines").fetchone()
    print(f"\n=== game_lines rows: {n:,}  seasons: {cov[0]}–{cov[1]} ===")

    print("\n=== done-criterion #1: de-vig'd moneylines sum to 1.0 ===")
    dev = con.execute(
        "SELECT MAX(ABS(home_fair_winprob + away_fair_winprob - 1.0)) "
        "FROM game_lines WHERE home_fair_winprob IS NOT NULL"
    ).fetchone()[0]
    print(f"  max |home_wp + away_wp - 1| = {dev:.2e}  -> {'PASS' if dev < 1e-9 else 'REVIEW'}")

    print("\n=== done-criterion #2: implied team totals are sane ===")
    s = oi.implied_total_sanity(con)
    ok2 = 18 <= s["median"] <= 26 and s["frac_in_10_40"] > 0.98
    print(f"  min={s['min']:.1f} median={s['median']:.1f} max={s['max']:.1f} "
          f"frac_in[10,40]={s['frac_in_10_40']:.3f}  -> {'PASS' if ok2 else 'REVIEW'}")

    print("\n=== done-criterion #3: odds_asof PIT (season 2020) ===")
    first_gd = con.execute(
        "SELECT MIN(captured_at) FROM game_lines WHERE season=2020").fetchone()[0]
    import datetime as dt
    n_before = len(oi.odds_asof(con, first_gd - dt.timedelta(days=1), season=2020))
    n_after = len(oi.odds_asof(con, dt.date(2021, 3, 1), season=2020))
    print(f"  first 2020 gameday={first_gd}")
    print(f"  as_of day-before: {n_before} rows (expect 0)   as_of post-season: {n_after} rows")
    ok3 = n_before == 0 and n_after > 200
    print(f"  -> {'PASS' if ok3 else 'REVIEW'}")

    print("\n=== player props ===")
    np_ = oi.ingest_player_props(con)
    print(f"  props rows written: {np_}  (0 + warning expected without ODDS_API_KEY)")
    con.close()


if __name__ == "__main__":
    main()
