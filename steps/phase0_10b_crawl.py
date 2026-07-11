"""Step 0.10b — Sleeper corpus crawler (grow the draft corpus toward the Phase-11 opponent model).

    uv run python steps/phase0_10b_crawl.py

Reads the seed registry (`reference/sleeper_seeds.txt`: usernames + draft_ids), crawls a corpus by
walking each user's league/draft history and expanding through the *human* participants of any
multi-manager draft it finds, ingests whatever is new, and rebuilds both ADP boards
(`sleeper_human` + `sleeper_mock`) plus the per-manager behavioral profiles.

Data-appetite reminder (see docs/SLEEPER.md): **bot mocks add ADP only**; the opponent model needs
**real human drafts** (human mock lobbies + crawled histories) — target ~50, ideal ~100–150.

Privacy: crawling brings other managers' public handles + picks into the store (already public via
the API, but other people's league data). `max_drafts` caps a run; the crawl is rate-limited.
"""

from __future__ import annotations

import json

from fantasy_quant.config import PROJECT_ROOT
from fantasy_quant.data import db
from fantasy_quant.data.sources import sleeper

OUT = PROJECT_ROOT / "analysis" / "results" / "sleeper_crawl.json"
MAX_DRAFTS = 500


def main() -> None:
    seeds = sleeper.load_seeds()
    print(f"=== 0.10b crawl — seeds: {len(seeds['usernames'])} usernames, "
          f"{len(seeds['league_ids'])} leagues, {len(seeds['draft_ids'])} draft_ids ===")
    con = db.connect()
    try:
        result = sleeper.crawl_and_ingest(
            con, seed_usernames=seeds["usernames"], seed_draft_ids=seeds["draft_ids"],
            seed_league_ids=seeds["league_ids"], max_drafts=MAX_DRAFTS, expand_participants=True)

        n_h, n_b = con.execute(
            "SELECT COUNT(*) FILTER (WHERE is_human), COUNT(*) FILTER (WHERE NOT is_human) "
            "FROM sleeper_drafts").fetchone()
        print(f"  crawled new     : {result['crawled_new']}  "
              f"ingested: {result['ingested']['n_drafts']}")
        print(f"  corpus drafts   : {n_h} human + {n_b} bot = {n_h + n_b}")
        print(f"  ADP boards      : {result['boards']}")
        print(f"  manager profiles: {result['manager_profiles']}")

        if result["manager_profiles"]:
            prof = con.execute(
                "SELECT manager, n_drafts, n_picks, avg_reach, pos_share_RB, pos_share_WR, "
                "fav_teams FROM sleeper_manager_profiles ORDER BY n_picks DESC LIMIT 10").df()
            print("\n  top managers by picks observed:")
            print(prof.to_string(index=False))

        report = {"seeds": seeds, "result": result,
                  "corpus": {"human_drafts": int(n_h), "bot_drafts": int(n_b)}}
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2, default=str))
        # Honest verdict: a Brier-verifiable opponent model wants ≳50 human drafts.
        tier = ("PLUMBING (need real human drafts)" if n_h == 0
                else "SEEDED" if n_h < 50 else "CORPUS READY")
        print(f"\n=== phase0_10b_crawl: {tier} — {n_h} human drafts "
              f"(wrote {OUT.relative_to(PROJECT_ROOT)}) ===")
    finally:
        con.close()


if __name__ == "__main__":
    main()
