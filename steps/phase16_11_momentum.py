"""Phase 16.11 done-bar — live 2026 ADP momentum.

The bar here is deliberately **not** a walk-forward gate, because no walk-forward test is
constructible: FFC publishes one board per season historically and the ECR archive is
kickoff-dated (0.11), so a within-season ADP series exists for 2026 and for no other year. The bar
is the 16.4-style descriptive-honesty one:

1. velocity computes on the banked 2026 series, for every FFC scoring/size config;
2. the output states its own provenance and thinness (``backtestable: False``, ``n_snapshots``,
   per-player standard errors, how much survives shrinkage);
3. the movers read like a hype list a human would recognise, and the mechanical confounds are
   handled — board-wide drift centered out, kickers filtered from the readout.

Run:  uv run python steps/phase16_11_momentum.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

from fantasy_quant.adp.momentum import FORWARD_ONLY, adp_velocity, momentum_summary, movers

DB = Path("data/fantasy_quant.duckdb")
OUT = Path("analysis/phase16_11_momentum.json")

SCORINGS = ("ppr", "half-ppr", "standard")
TEAM_SIZES = (10, 12)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--k", type=int, default=15)
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    out: dict = {"season": args.season, "forward_only": FORWARD_ONLY, "configs": {}}

    for scoring in SCORINGS:
        for teams in TEAM_SIZES:
            vel = adp_velocity(con, args.season, scoring=scoring, teams=teams)
            key = f"{scoring}_{teams}"
            summ = momentum_summary(vel)
            out["configs"][key] = summ
            if vel.empty:
                print(f"{key:>16}: no series")
                continue
            print(f"{key:>16}: {summ['n_players']:>3} players, "
                  f"{summ['n_snapshots_max']} snapshots over {summ['span_days']:.0f}d, "
                  f"velocity sd {summ['velocity_sd']:.2f} -> "
                  f"shrunk {summ['velocity_shrunk_sd']:.2f} "
                  f"({summ['shrinkage_retained']:.0%} retained)")

    # the headline config is the league baseline: 10-team full PPR
    vel = adp_velocity(con, args.season, scoring="ppr", teams=10)
    mv = movers(vel, k=args.k)
    cols = ["name", "position", "n_snapshots", "adp_first", "adp_last", "adp_now",
            "velocity", "velocity_shrunk", "se"]
    out["headline"] = {
        "config": "ppr_10",
        "summary": momentum_summary(vel),
        "risers": mv["risers"][cols].to_dict("records"),
        "fallers": mv["fallers"][cols].to_dict("records"),
    }

    print(f"\nRISERS (drafted EARLIER over time — the hype direction), {args.season} PPR 10-team:")
    print(mv["risers"][cols].to_string(index=False))
    print("\nFALLERS:")
    print(mv["fallers"][cols].to_string(index=False))

    # --- the honesty gates -----------------------------------------------------------------
    summ = out["headline"]["summary"]
    gates = {
        "series_computes": bool(summ["n_players"] > 0),
        "multi_snapshot": bool(summ["n_snapshots_max"] >= 2),
        "labeled_forward_only": summ["backtestable"] is False,
        # centering is meant to leave the median player at zero movement; if it does not, the
        # board-wide component was not actually removed.
        "board_drift_centered": bool(abs(summ["velocity_median"]) < 1e-9),
        "movers_are_skill_only": bool(
            set(r["position"] for r in out["headline"]["risers"]) <= {"QB", "RB", "WR", "TE"}),
    }
    out["gates"] = gates
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nwrote {OUT}")
    print(f"\n  board-wide drift removed: {summ['board_median_slope_per_week']:+.3f} picks/wk "
          f"(the pool deepens through the preseason — that part is not a player's own movement)")
    print(f"  shrinkage retained {summ['shrinkage_retained']:.0%} of the raw spread "
          f"({summ['n_snapshots_max']} snapshots ⇒ 1 residual df per player)")
    for k, v in gates.items():
        print(f"  {k:>24}: {'PASS' if v else 'FAIL'}")
    print(f"\n  ⚠ {FORWARD_ONLY}")


if __name__ == "__main__":
    main()
