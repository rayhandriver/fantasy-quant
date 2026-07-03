"""News / injury / depth-chart ingest — the raw *pipe* for the Phase-12 NLP edge (0.6).

Captures **timestamped raw signal** now so later PIT event-studies are possible — you can't
reconstruct yesterday's news after the fact. No NLP here (that's Phase 12); just land the text
and structured availability data with reliable timestamps. See ``docs/STRATEGY.md`` Part 15.2.
"""
