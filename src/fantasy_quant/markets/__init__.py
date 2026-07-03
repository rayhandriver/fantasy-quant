"""Vegas betting markets — the *sharper* market than ADP (Phase 0.5+).

Game lines (spreads/totals → implied team totals) come free & historical from nflverse
schedules; player props are live-only via the-odds-api (historical props are the paid gap).
De-vig utilities turn raw book odds into fair probabilities/means used as features, projection
anchors, and calibration targets. See ``docs/STRATEGY.md`` Part 15.2 and glossary "Betting-market".
"""
