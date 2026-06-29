# PLAN.md — the HOW (living workspace)

My working notebook: design choices, parameter picks, open questions, dead ends. `PROJECT.md` is the
fixed WHAT; this is mine to manage. Newest notes at the bottom of each section.

## Current state
- **2026-06-29 — Environment scaffolded.** Repo created at `~/dev/repo/fantasy-quant`; uv + pinned Python
  3.12; core stack defined in `pyproject.toml`; doc set + `docs/STRATEGY.md` in place; local git. **No
  modeling code yet.** Next: Phase 0.

## Decisions log
- Product = shareable league app; metric = layered (PAR → season/playoff sim); data = free/scraped.
  (See `PROJECT.md` §3.)
- Tooling = uv + Python 3.12 (not system 3.14) for ML-wheel compatibility. src layout → editable install,
  no `sys.path` bootstrap.
- ADP-bias mining promoted to an early, self-contained workstream (reuses intern factor-return regression).

## Open questions
- Which ADP source(s) to scrape first and how far back is reconstructable PIT? (FFCalculator historical +
  Underdog early best-ball are the free starting pair.)
- Exact "ADP alpha" target definition (finish-rank − ADP-rank vs points − slot-replacement) — decide in the
  ADP workstream.
- Replacement-level definition per position for VBD in a 10-team PPR league.
- How many personalization levers to expose in the v1 app.
- Season-sim fidelity: how to model bye weeks, injuries (games-missed distribution), and the playoff bracket.

## Notes / dead ends
- _(none yet)_
