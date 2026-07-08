"""Personalization spine · step 4 — realized-PAR validation of the cost number, on real data.

    uv run python steps/spine_4_validate.py

Done when: each archetype is drafted against its unconstrained ``bpa`` benchmark over matched
seeded opponents across the DEV validation window (2017–2022), scored on **realized** optimal-lineup
season points, and its realized-PAR cost put on a block-bootstrap 95% CI — then cross-checked
against the projected cost the report prints. The honest expectation (and finding) is that on ~6
seasons the realized cost of a soft draft archetype is **swamped by seasonal noise**: the CIs cover
zero. That *is* the result — it says the actionable number is the projected draft-day cost, and that
no archetype demonstrably throws away real points. Availability (a draft-day Brier) is **not**
validated here: it needs real pick-by-pick draft logs the historical FFC aggregates don't contain.

Runs on ``VALIDATION_SEASONS`` (DEV, with ≥3 training seasons of history); lockbox untouched.
"""

from __future__ import annotations

from fantasy_quant.config import LOCKBOX_SEASONS
from fantasy_quant.data import db
from fantasy_quant.valuation.cost_validation import VALIDATION_SEASONS, validate_archetypes


def main() -> None:
    assert not (set(VALIDATION_SEASONS) & set(LOCKBOX_SEASONS)), "lockbox must stay untouched"
    con = db.connect(read_only=True)

    res = validate_archetypes(con, seasons=VALIDATION_SEASONS, k_drafts=10, n_boot=10000)
    print(res.render())

    print("\nPer-season realized vs projected cost (zero_rb):")
    zero = next(v for v in res.per_archetype if v.subject == "zero_rb")
    print(zero.per_season.round(1).to_string(index=False))

    # sanity gates — structural, not "the cost is significant" (on ~6 seasons it won't be).
    assert res.per_archetype, "no archetypes validated"
    assert all(v.n_seasons >= 5 for v in res.per_archetype), "validation window collapsed"
    assert all(abs(v.realized_cost) < 1e4 and v.ci.lo <= v.ci.hi for v in res.per_archetype)
    assert res.cross.n >= 15, "too few subject-seasons for a cross-check"

    real = [v.subject for v in res.per_archetype
            if v.verdict.startswith(("REAL COST", "REAL GAIN"))]
    verdict = (f"{len(real)} archetype(s) show a realized effect distinguishable from 0: {real}"
               if real else
               "no archetype's realized cost is distinguishable from 0 — projected cost is the "
               "actionable number; personalization does not measurably throw away real points.")
    print(f"\n  Reading: {verdict}")
    print("\nSpine step 4 (realized-PAR validation) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
