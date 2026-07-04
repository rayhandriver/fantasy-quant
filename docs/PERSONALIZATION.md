# PERSONALIZATION.md — the design artifact (constraint object · three-signal optimizer · MVP)

The first-class design contract for the **direct-indexing reframe** (2026-07-04). Full rationale:
`docs/REFRAME-2026-07-04.md`; objective & definition-of-done: `docs/STRATEGY.md` Part 0. This file pins
down **the contracts** — the config object every feature reads/writes, and the three optimizer inputs —
so the build does not tangle. *Own the interfaces even while delegating the interiors.*

> **Status:** design-only. No code here yet — packages are created when we reach their phase
> (`CLAUDE.md` §5). This is the schema to build **to**, not a built thing.

---

## 1. The objective (one line)

Produce a **single, fully-optimized personalized team**, and honestly **price what the personalization
cost** versus the consensus-optimal team from your seat. Team strength is a **benchmark we track**, not
the objective; personalization is the objective. (We do *not* ship a worse team — the optimizer still
builds the best roster it can given everything the user wants.)

---

## 2. The three signal layers (never one "ADP" blob)

"Based around ADP" is split into three distinct signals, because ADP is being asked to do jobs that are
not all ADP. Collapsing them produces an incoherent optimizer. **This is a hard contract.**

| Signal | Question it answers | Source | Notes |
|---|---|---|---|
| **Value** | What makes one team better than another? | **Consensus projections → VBD** | *Not* ADP (that's draft *order*, not points). Lean on consensus (e.g. FantasyPros aggregate) for the mean; always convert to **value-over-replacement** (raw order overrates QBs in 1-QB — our Phase-2 finding). This is the big simplification: drop most of the "build a better projection" burden. |
| **Availability** | Who is gettable at each pick? | **ADP + behavioral opponent model** | Drives "who survives to my next pick" and the whole draft-flow plan (availability forecasts + realistic mock). Was always ADP; stays ADP (+ behavior). |
| **Variance / risk** | Floor vs ceiling? | **Our own distributional layer** | Consensus and ADP are point estimates — they cannot hand you distributions. The per-round risk dial needs a per-player variance/distribution we build ourselves (a **trimmed Phase 5**). Required only if risk features are in scope. |

**Optimizer objective:** maximize **consensus-VBD value** subject to the user's constraints + archetype,
**planning around ADP-driven availability**, with the **risk dial** modulating the value/variance
tradeoff. Personalization cost is priced against the **consensus-VBD-optimal** team.

Two things to keep straight so the build does not tangle: **value is consensus *projections*, not ADP
*order*** (correlated, not the same object), and **the risk dial needs a variance model we build.**

---

## 3. The constraint / config object (the schema to pin down)

One object under the hood; every feature **reads from it**, all three doors (§4) **write to it**. The
optimizer always receives a **complete** object — nothing is ever unset (§5 precedence chain fills gaps).
Indicative shape (design intent, not final types):

```
DraftConfig
  # --- league context (READ, don't ask — auto-sets replacement levels, positional priority, QB weight)
  league:
    scoring: RuleSet            # full custom scoring ingestion (PPR/TE-premium/…)
    roster_slots: {...}         # incl. SUPERFLEX / 2QB (changes everything), FLEX, K, DST
    n_teams, draft_slot
    format: snake | linear | third_round_reversal | auction
    auction_budget?, keeper_holds?
    playoff_weeks: [15,16,17]   # target-date analog

  # --- archetype (a MASTER dial: one choice cascades ~20 knobs; blend two with a weight)
  archetype: zero_rb | hero_rb | hero_wr | robust_rb | elite_te | late_qb | konami | bpa | adaptive
  archetype_blend?: (name, weight)
  adaptive: bool                # abandon the plan when the board breaks

  # --- player/roster preferences (the "custom index")
  must_draft:  [(player, reach_budget_rounds)]
  never_draft: [player]
  tilts:       {player|group: over_under_weight_in_rounds}     # e.g. +0.5 rd, −1 rd
  fandom: {love_teams, hate_teams}          # refuse a rival's players
  character_excludes: [player]              # the ESG analog
  injury_averse: 0..1                       # down-weight high re-injury-hazard (concentrated-position analog)
  rookie_veteran_tilt: -1..1
  handcuff_own_rbs: bool

  # --- risk (drives value↔variance tradeoff; needs the variance signal)
  risk_global: floor .. ceiling             # casual/"don't embarrass me" ↔ money/"win it all"
  risk_per_round: [floor..ceiling]
  correlation_appetite: decorrelated .. stacked
  objective: make_playoffs | championship_or_bust    # mean vs tail

  # --- meta
  benchmark_set: [adp_consensus_optimal, our_projection_optimal, expert_consensus_optimal]
  control_tier: autopilot | copilot | manual
  explanation_depth: pick | reasoning | full_math
```

Rules: every field resolves to a concrete value via §5; the optimizer never sees a null. Hard constraints
(`never_draft`, roster legality) are inviolable; soft tilts bend value by a bounded number of rounds.

---

## 4. One config, three doors

Same object, three depths of access — one app, not three:

- **Autopilot** — two decisions (archetype + league), then go.
- **Co-pilot** — 5–7 high-impact dials exposed.
- **Manual** — the full surface, every slider.

---

## 5. Precedence chain (never a blank form)

Every configurable resolves so nothing is unset; the optimizer always gets a complete config:

```
explicit user setting  >  inferred from league settings  >  implied by chosen archetype  >  population prior
```

Supporting rules: (1) **Read the league, do not ask** — scoring/slots/superflex/size/slot are synced or
pasted once and set replacement levels + positional priority + QB weighting. (2) **The archetype is a
master dial** — one choice pre-fills ~20 knobs; opening any knob reveals the editable preset. (3)
**Surface the default with a one-line why, always overridable** — *"Set to Ceiling because you flagged a
money league. Change it?"* Never blank, never silent.

---

## 6. The signature seven (the spine to build)

1. Preference-spec layer (this constraint object + UI).
2. Constrained optimizer (maximize consensus-VBD value s.t. hard excludes + soft tilts + archetype +
   risk dial; plan around ADP availability).
3. Cost-of-personalization report (tracking-error decomposition vs the benchmark team).
4. Behavioral opponent model → availability forecasts + realistic mock.
5. Per-round / global risk dial (powered by the trimmed variance layer).
6. Adaptive archetypes (presets that abandon the plan when the board breaks).
7. In-season weekly-edge harvester (the tax-loss-harvesting analog).

Full feature catalog: `docs/REFRAME-2026-07-04.md` §7.

---

## 7. Near-term MVP scope (needs none of Phases 11–15, no in-app AI)

- Reuse Phases 0–2 as-is (data, harness, baselines, projection → VBD → `rank_fn`).
- Wire the **three signal layers** as separate optimizer inputs:
  - **Value:** ingest **consensus projections** → **VBD**. No own edge-seeking model. Thin rookie-value fill.
  - **Availability:** ADP (existing ADP+noise simulator first; upgrade to the behavioral model once real
    completed-draft data is confirmed — open decision, `PLAN.md`).
  - **Variance:** a minimal own per-player distribution (trimmed Phase 5), enough to drive the risk dial.
- The **constraint object** (§3) + a **constrained greedy optimizer** maximizing consensus-VBD value s.t.
  hard excludes, soft tilts, archetype priors, per-round risk; planning around ADP availability.
- A first-pass **cost-of-personalization** number vs the **consensus-VBD-optimal** team (relative /
  directional first — lead with "this choice vs that," stay humble on absolute title-equity deltas).
- A **Streamlit / Gradio** UI exposing Autopilot + Co-pilot (archetype, league sync, a handful of dials,
  must/never lists) with defaulted sliders and the one-line why.

**MVP done:** you can sit down for a real draft this season, express your preferences, and get
personalized pick recs with an honest, relative cost readout — from a Python UI, **no LLM in the loop**.

---

## 8. Guardrails

- **AI on the edges, deterministic core** — no LLM computes a number that must be correct (all in-app AI
  is deferred post-MVP; `docs/REFRAME-2026-07-04.md` §9).
- **Streamlit/Gradio first, not FastAPI+Next.js** — validate the idea before a production frontend.
- **Own the contracts** (this object + the projection output shape); delegate the interiors.
- **Always show the personalized board next to the pure baseline** — treat large divergences as
  hypotheses, not preferences to bake in.
- **Calibration > edge** — a miscalibrated projection is a visibly wrong number the user sees.
