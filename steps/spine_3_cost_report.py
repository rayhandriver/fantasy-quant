"""Personalization spine · step 3 — the cost-of-personalization report, on real 2022 data.

    uv run python steps/spine_3_cost_report.py

Done when: the personalized roster and its unconstrained benchmark are drafted through the same
optimizer over the same seeds, their total risk-adjusted value differenced into one honest cost,
and that cost attributed per preference by leave-one-out — "what did refusing him, insisting on
her, or going zero-RB actually cost?". Relative/directional per §7 — a projected draft-day gap,
not a realized-season claim (the walk-forward realized-PAR validation is the next layer).
"""

from __future__ import annotations

from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.data import db
from fantasy_quant.draft.config import DraftConfig, LeagueSetup
from fantasy_quant.draft.optimizer import assemble_value
from fantasy_quant.valuation.cost_report import personalization_cost

SEASON = 2022


def main() -> None:
    assert SEASON in DEV_SEASONS, "stay out of the lockbox / holdout during development"
    con = db.connect(read_only=True)
    base = DraftConfig(league=LeagueSetup(draft_slot=5))
    vi = assemble_value(con, SEASON, base)
    valued = vi.dropna(subset=["base_value"]).sort_values("base_value", ascending=False)
    keys = valued["player_key"].tolist()
    never, must, tilt = keys[2], keys[24], keys[39]

    cfg = DraftConfig(league=LeagueSetup(draft_slot=5), archetype="zero_rb",
                      must_draft=[(must, 2.0)], never_draft={never}, tilts={tilt: 2.0})

    rep = personalization_cost(con, SEASON, cfg, value_index=vi, k_drafts=6)
    print(rep.render())

    print("\nYOUR team (representative draft):")
    print(rep.personalized_roster.to_string(index=False))

    # sanity gates: cost is a modest, non-absurd share; attribution has a row per active preference.
    assert -0.25 <= rep.cost_pct <= 0.60, f"cost {rep.cost_pct:.0%} implausible"
    assert len(rep.per_constraint) == len(cfg.constraint_labels())
    # leave-one-out sum should track the headline (interactions make it approximate, not exact).
    loo_sum = rep.per_constraint["cost_points"].sum()
    print(f"\n  headline cost {rep.cost_points:+.1f} pts vs leave-one-out sum {loo_sum:+.1f} pts "
          f"(differ by interactions between preferences).")
    print("\nSpine step 3 (cost report) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
