"""Personalization spine · step 2 — the constrained greedy optimizer, on real 2022 data.

    uv run python steps/spine_2_optimizer.py

Done when: from a PIT ADP board + the risk-adjusted value signal, the optimizer builds a
personalized roster that (a) honors a refusal, (b) secures a must-draft within its reach budget,
and (c) bends to the archetype — while the benchmark (same seat, same λ) drafts pure value via the
identical machinery. Season 2022 (latest DEV season; lockbox 2023/24 untouched); season is a
parameter, so a scraped 2026 board drops straight in.
"""

from __future__ import annotations

from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.data import db
from fantasy_quant.draft.config import DraftConfig, LeagueSetup
from fantasy_quant.draft.optimizer import assemble_value, optimize_draft

SEASON = 2022


def _roster(state, vi):
    mine = state.pick_log().query("is_you").copy()
    bv = vi.dropna(subset=["base_value"]).drop_duplicates("player_key").set_index("player_key")
    mine["base_value"] = mine["player_key"].map(bv["base_value"])
    return mine[["round", "player_name", "pos", "adp", "base_value"]].reset_index(drop=True)


def main() -> None:
    assert SEASON in DEV_SEASONS, "stay out of the lockbox / holdout during development"
    con = db.connect(read_only=True)
    base = DraftConfig(league=LeagueSetup(draft_slot=5))
    print(f"assembling the value signal for {SEASON} (consensus→VBD, risk-dialed by λ) …")
    vi = assemble_value(con, SEASON, base)
    valued = vi.dropna(subset=["base_value"]).sort_values("base_value", ascending=False)
    print(f"  {len(vi)} players, {len(valued)} valued (base_value = "
          f"risk-adjusted value-over-replacement).")

    # pick real constraints off the board: refuse the #3 value, insist on #25, tilt #40.
    keys = valued["player_key"].tolist()
    never, must, tilt = keys[2], keys[24], keys[39]

    cfg = DraftConfig(league=LeagueSetup(draft_slot=5), archetype="zero_rb",
                      must_draft=[(must, 2.0)], never_draft={never}, tilts={tilt: 2.0})

    pers = optimize_draft(con, SEASON, cfg, value_index=vi, seed=7)
    bench = optimize_draft(con, SEASON, cfg.benchmark(), value_index=vi, seed=7)
    pr, br = _roster(pers, vi), _roster(bench, vi)

    print(f"\nBENCHMARK roster (unconstrained value, seat 5):\n{br.to_string(index=False)}")
    print(f"\nPERSONALIZED roster (zero_rb + 1 must + 1 never + 1 tilt):\n"
          f"{pr.to_string(index=False)}")

    secured = set(pers.pick_log().query("is_you")["player_key"])
    assert never not in secured, "hard refusal was violated"
    assert must in secured, "must-draft was not secured within its reach budget"
    # zero-RB should carry fewer early RBs than the benchmark.
    early_rb_pers = pr[(pr["round"] <= 5) & (pr["pos"] == "RB")].shape[0]
    early_rb_bench = br[(br["round"] <= 5) & (br["pos"] == "RB")].shape[0]
    print(f"\n  refusal honored: {never} absent ✓ | must-draft {must} secured ✓")
    print(f"  early-round (≤5) RBs — benchmark {early_rb_bench}, zero_rb {early_rb_pers}")
    assert early_rb_pers <= early_rb_bench, "zero_rb should not add early RBs vs benchmark"
    print("\nSpine step 2 (constrained optimizer) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
