"""Step 0.10 — Sleeper draft ingest (the done-bar).

    uv run python steps/phase0_10_sleeper_ingest.py

Ingests the seed mock drafts (ids below — the corpus grows by adding ids here or discovering a
username/league in `sleeper.ingest_drafts`), then:
  1. writes `sleeper_drafts` + `sleeper_draft_picks` (idempotent),
  2. rebuilds the `sleeper_mock` ADP board into `adp_snapshots` (so `adp_asof`/the sim use it),
  3. computes the POC opponent-tendencies artifact,
  4. drafts a 2026 mock with the real simulator against the Sleeper-derived board (the sim wiring),
  5. runs the 0.10 validation gates and writes `analysis/results/sleeper_ingest.json`.

Scope (honest): this is the ingest PLUMBING + a proof-of-concept board/tendencies on bot mocks.
The Phase-11 behavioral opponent model and the availability Brier need real-league pick logs
(persistent `picked_by`), not solo-vs-bots mocks. See docs/SLEEPER.md.
"""

from __future__ import annotations

import json

import pandas as pd

from fantasy_quant.config import PROJECT_ROOT
from fantasy_quant.data import db
from fantasy_quant.data.sources import adp as adp_src
from fantasy_quant.data.sources import sleeper
from fantasy_quant.data.validate import _sleeper_gates
from fantasy_quant.draft.simulator import simulate_draft

# Seed corpus — MadBawa's mock drafts (2026). Add ids / a username to grow the corpus.
SEED_DRAFT_IDS = [
    "1381689410868760576",
    "1381687658979291136",
    "1381667884610109440",
]
OUT = PROJECT_ROOT / "analysis" / "results" / "sleeper_ingest.json"


def main() -> None:
    con = db.connect()
    try:
        summary = sleeper.ingest_drafts(con, SEED_DRAFT_IDS)
        print("=== 0.10 Sleeper ingest ===")
        print(f"  drafts ingested : {summary['n_drafts']}  picks: {summary['n_picks']}  "
              f"missing: {summary['missing']}")
        print(f"  skill gsis match: {summary['skill_match_rate']:.1%}")
        print(f"  by position     : {summary['coverage_by_position']}")

        # per-draft format readout
        drafts = con.execute(
            "SELECT draft_id, source, draft_type, teams, rounds, scoring, status, human_slot "
            "FROM sleeper_drafts ORDER BY draft_id").df()
        print("\n  drafts:")
        for r in drafts.itertuples():
            print(f"    {r.draft_id}  {r.source:6} {r.draft_type} {r.teams}tm x{r.rounds} "
                  f"{r.scoring}  status={r.status}  human_slot={r.human_slot}")

        board = sleeper.refresh_mock_adp(con, season=2026)
        print(f"\n  mock ADP board  : {len(board)} players "
              f"(source={sleeper.MOCK_SOURCE}, {int(board['total_drafts'].iloc[0])} drafts)")
        top = board.sort_values("adp").head(15)[["name", "position", "adp", "times_drafted",
                                                 "high", "low"]]
        print(top.to_string(index=False))

        tend = sleeper.opponent_tendencies(con, season=2026)
        print(f"\n  tendencies rows : {len(tend)}  (key_type="
              f"{tend['key_type'].iloc[0] if len(tend) else 'n/a'})")

        # --- sim wiring: draft a 2026 mock against the Sleeper-derived board -----------------
        as_of = pd.to_datetime(board["snapshot_date"].iloc[0]).date()
        sim_board = adp_src.adp_asof(con, 2026, as_of, source=sleeper.MOCK_SOURCE,
                                     scoring="ppr", teams=10)
        st = simulate_draft(sim_board, n_teams=10, rounds=15, your_team=0, seed=0)
        your = st.your_roster()[["player_name", "pos", "adp"]]
        print(f"\n  sim draft (vs sleeper_mock board, seed=0): your team, {len(your)} picks")
        print(your.to_string(index=False))

        gates = _sleeper_gates(con)
        all_pass = all(g["passed"] for g in gates)
        print("\n  gates:")
        for g in gates:
            print(f"    [{'PASS' if g['passed'] else 'FAIL'}] {g['gate']}")

        report = {
            "ingest": summary,
            "mock_adp_players": int(len(board)),
            "tendencies_rows": int(len(tend)),
            "sim_your_picks": int(len(your)),
            "gates": gates,
            "all_gates_passed": all_pass,
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2, default=str))
        verdict = "PASS" if all_pass and summary["n_drafts"] == len(SEED_DRAFT_IDS) else "REVIEW"
        print(f"\n=== phase0_10_sleeper_ingest: {verdict} "
              f"(wrote {OUT.relative_to(PROJECT_ROOT)}) ===")
    finally:
        con.close()


if __name__ == "__main__":
    main()
