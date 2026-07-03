"""Phase 1.2 — draft simulator, run + verify (second brick of the backtest harness).

    uv run python steps/phase1_2_draft.py

Done when (BUILD_PLAN.md 1.2): a 10x15 snake draft runs; the default ADP-only your_pick_fn yields
an ADP-typical roster; the draft is reproducible under a fixed seed. Board = adp_asof (0.4).
"""

from __future__ import annotations

from fantasy_quant.data import db
from fantasy_quant.data.sources.adp import adp_asof
from fantasy_quant.draft.simulator import RosterSlots, simulate_draft

SEASON, AS_OF, SEED, YOUR_SEAT = 2022, "2022-09-05", 42, 4


def main() -> None:
    con = db.connect(read_only=True)
    board = adp_asof(con, SEASON, AS_OF)  # 10-team full-PPR board as-of Labor Day
    print(f"=== board: {len(board)} players (adp_asof {SEASON} @ {AS_OF}) ===\n")

    slots = RosterSlots()

    def draft(seed: int):
        return simulate_draft(board, n_teams=10, rounds=15, slots=slots,
                              your_team=YOUR_SEAT, seed=seed)

    result = draft(SEED)
    log = result.pick_log()

    # -- draft ran to completion -------------------------------------------------------------
    print("=== draft geometry ===")
    assert len(log) == 10 * 15, f"expected 150 picks, got {len(log)}"
    # snake order spot-checks
    first10 = list(log[log["round"] == 1]["team"])
    rnd2 = list(log[log["round"] == 2]["team"])
    assert first10 == list(range(10)), f"round 1 order wrong: {first10}"
    assert rnd2 == list(range(9, -1, -1)), f"round 2 (snake) order wrong: {rnd2}"
    print("  150 picks; round 1 = seats 0..9, round 2 = seats 9..0 (snake) [PASS]")

    # -- your roster is ADP-typical + legal --------------------------------------------------
    yr = result.your_roster()
    counts = yr["pos"].value_counts().to_dict()
    print(f"\n=== your roster (seat {YOUR_SEAT}): {len(yr)} players ===")
    print(f"  positions: {counts}")
    for _, r in result.pick_log().query("is_you").iterrows():
        print(f"    R{int(r['round']):>2} (pick {int(r['overall_pick']):>3})  "
              f"{r['pos']:<4} {r['player_name']:<24} adp={r['adp']:.1f}")
    assert len(yr) == slots.total, f"roster should have {slots.total} players"
    for pos, cap in slots.pos_caps.items():
        assert counts.get(pos, 0) <= cap, f"{pos} over cap: {counts.get(pos)} > {cap}"
    assert counts.get("QB", 0) >= 1, "no QB drafted"
    assert counts.get("RB", 0) + counts.get("WR", 0) >= 8, "roster not RB/WR-heavy (atypical)"
    print("  [PASS] roster is full (15), within caps, RB/WR-heavy — ADP-typical.")

    # -- K/DST supply note (FFC undersupplies them) ------------------------------------------
    got_k = sum(bool(result.roster(t)["pos"].eq("K").any()) for t in range(10))
    got_d = sum(bool(result.roster(t)["pos"].eq("DST").any()) for t in range(10))
    print(f"\n  K/DST supply: {got_k}/10 teams drafted a K, {got_d}/10 a DST "
          f"(FFC board lists only ~5 K / ~6 DST — documented).")

    # -- reproducibility ---------------------------------------------------------------------
    again = draft(SEED)
    other = draft(7)
    same = log["player_key"].equals(again.pick_log()["player_key"])
    diff = not log["player_key"].equals(other.pick_log()["player_key"])
    print("\n=== reproducibility ===")
    assert same, "same seed produced a different draft"
    assert diff, "different seed produced an identical draft"
    print("  [PASS] same seed -> identical draft; different seed -> different draft.")

    print("\nPhase 1.2 (draft simulator) — all criteria PASS.")
    con.close()


if __name__ == "__main__":
    main()
