"""Step 0.10b — Sleeper corpus crawler (grow the draft corpus toward the Phase-11 opponent model).

    uv run python steps/phase0_10b_crawl.py --mode frontier --max-seconds 5400
    uv run python steps/phase0_10b_crawl.py --mode seeds          # legacy seed-file snowball

**Two modes.**

``frontier`` (default) walks the history of every manager already observed in the corpus
(``sleeper_manager_profiles``) and stops there — no second-order snowball into *their*
co-managers. This is the mode that actually grows the corpus: the seed file holds a handful of
ids, while the profiles table holds hundreds of managers who were never fed back in as seeds, so
every previous run re-walked the same tiny neighbourhood.

``seeds`` is the original ``reference/sleeper_seeds.txt`` snowball, kept for topping up from a
specific league/username.

**Resumable.** Progress lives in ``sleeper_crawl_users`` (whose history is walked) and
``sleeper_crawl_queue`` (discovered draft_ids, retired ``done``/``dead``). Interrupt it and re-run;
it picks up where it stopped and never re-spends calls on ids that 404'd.

Data-appetite reminder (see docs/SLEEPER.md): **bot mocks add ADP only**; the opponent model needs
**real human drafts** (human mock lobbies + crawled histories).

Privacy: crawling brings other managers' public handles + picks into the store (already public via
the API, but other people's league data). The crawl is rate-limited to ``sleeper.CRAWL_RATE``
calls/sec, deliberately under Sleeper's documented ~1000/min.

Formats: **nothing is filtered at ingest** — dynasty / 2QB / superflex / IDP drafts are banked
alongside redraft. Downstream consumers do their own filtering (the drift panel keeps redraft
only); Phase 17 (league-format fidelity) is the consumer that will want the rest.
"""

from __future__ import annotations

import argparse
import json

from fantasy_quant.config import PROJECT_ROOT
from fantasy_quant.data import db
from fantasy_quant.data.sources import sleeper

OUT = PROJECT_ROOT / "analysis" / "results" / "sleeper_crawl.json"
MAX_DRAFTS = 500          # `seeds` mode only — the frontier mode runs to exhaustion or the clock


def _corpus(con) -> dict:
    n_h, n_b = con.execute(
        "SELECT COUNT(*) FILTER (WHERE is_human), COUNT(*) FILTER (WHERE NOT is_human) "
        "FROM sleeper_drafts").fetchone()
    n_p = con.execute("SELECT COUNT(*) FROM sleeper_draft_picks").fetchone()[0]
    n_m = db.row_count(con, "sleeper_manager_profiles") \
        if db.table_exists(con, "sleeper_manager_profiles") else 0
    return {"human_drafts": int(n_h), "bot_drafts": int(n_b), "picks": int(n_p),
            "managers": int(n_m)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Grow the Sleeper draft corpus.")
    ap.add_argument("--mode", choices=("frontier", "seeds"), default="frontier")
    ap.add_argument("--max-seconds", type=float, default=None,
                    help="wall-clock budget; the crawl stops cleanly and stays resumable")
    ap.add_argument("--max-users", type=int, default=None,
                    help="frontier mode: cap how many managers to walk this run")
    ap.add_argument("--expand", action="store_true",
                    help="frontier mode: also snowball into newly found co-managers")
    ap.add_argument("--archive-payloads", action="store_true",
                    help="keep the T7 raw-payload archive on (off by default for bulk crawls)")
    ap.add_argument("--batch", type=int, default=400, help="drafts ingested per committed batch")
    args = ap.parse_args()

    con = db.connect()
    try:
        before = _corpus(con)
        print(f"=== 0.10b crawl [{args.mode}] — before: {before} ===")

        if args.mode == "frontier":
            frontier = sleeper.seed_users_from_profiles(con)
            walked = sleeper.crawled_users(con)
            print(f"  frontier: {len(frontier)} known managers, "
                  f"{len(frontier) - len(walked & set(frontier))} not yet walked")
            result = sleeper.crawl_frontier(
                con, user_ids=frontier, max_users=args.max_users,
                max_seconds=args.max_seconds, expand_participants=args.expand,
                batch=args.batch, archive_payloads=args.archive_payloads)
        else:
            seeds = sleeper.load_seeds()
            print(f"  seeds: {len(seeds['usernames'])} usernames, "
                  f"{len(seeds['league_ids'])} leagues, {len(seeds['draft_ids'])} draft_ids")
            result = sleeper.crawl_and_ingest(
                con, seed_usernames=seeds["usernames"], seed_draft_ids=seeds["draft_ids"],
                seed_league_ids=seeds["league_ids"], max_drafts=MAX_DRAFTS,
                expand_participants=True)

        # the crawl only fills the raw tables; the derived artifacts are rebuilt here
        boards = sleeper.refresh_adp_boards(con)
        prof = sleeper.build_and_store_profiles(con)
        tend = sleeper.opponent_tendencies(con)
        after = _corpus(con)

        print(f"\n  crawl           : {result}")
        print(f"  corpus          : {before} -> {after}")
        print(f"  ADP boards      : {boards}")
        print(f"  manager profiles: {len(prof)}   tendencies: {len(tend)}")

        report = {"mode": args.mode, "result": result, "before": before, "after": after,
                  "boards": boards, "manager_profiles": int(len(prof)),
                  "tendencies": int(len(tend))}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2, default=str))
        # Honest verdict: a Brier-verifiable opponent model wants ≳50 human drafts.
        n_h = after["human_drafts"]
        tier = ("PLUMBING (need real human drafts)" if n_h == 0
                else "SEEDED" if n_h < 50 else "CORPUS READY")
        print(f"\n=== phase0_10b_crawl: {tier} — {n_h} human drafts "
              f"(wrote {OUT.relative_to(PROJECT_ROOT)}) ===")
    finally:
        con.close()


if __name__ == "__main__":
    main()
