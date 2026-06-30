# PLAN.md — the HOW (living lab-notebook)

Working notes only: implementation choices, parameter picks, and dead ends **as they arise during a
step**. This file does **not** restate the goal, scope, decisions, or phase plan — those live in
`PROJECT.md` (§1–§5). Keep it terse; newest at the bottom.

## Current state
- **2026-06-29** — Environment scaffolded; docs restructured into the granular Phase 0–15 plan (`PROJECT.md`)
  with Vegas markets promoted to a first-class data source. **No modeling code yet.** Next: Phase 0.2.

## Working notes (per step)
_(empty — populated as each step in `PROJECT.md` §5 is implemented: what was decided, what was tried,
what to reuse. Canonical decisions go in `PROJECT.md` §3, not here.)_

## Open questions (to resolve at the relevant step)
- **0.4/0.5 data:** how far back are FFCalculator/Underdog ADP and historical **prop lines** reconstructable
  PIT? (Historical odds is the likely-paid gap — confirm free coverage before relying on it for backtests.)
- **0.5 markets:** which de-vig method (proportional / Shin / power) and which books to aggregate.
- **2.1 VBD:** replacement-level definition per position for 10-team PPR.
- **6.x ADP-alpha:** target definition — finish-rank − ADP-rank vs points − slot-replacement.
- **10.x season-sim:** bye-week, injury (games-missed), and playoff-bracket fidelity.
- **14.2 app:** how many personalization levers to expose in v1.

## Dead ends
- _(none yet)_
