# PLAYER-VIEW.md — the interactive player card + deep page (app spec)

*Focused spec for the app's most-interactive surface: a **hover overview card** on any player, and a
**click-through per-player deep page**. Both render the model's already-frozen per-player outputs as
simple, elegant "quasi-bar" meters. Design-only doc — no code yet. Owned by the human (a UI contract),
like `PERSONALIZATION.md` and `SLEEPER.md`. Decisions recorded in `PLAN.md` (2026-07-23 entry).*

> **Guardrail inheritance.** This surface is presentation only. It never computes a number that must be
> correct — it *reads* frozen contracts (`value_board`, `player_distributions`, Phase-6 durability,
> Phase-3 opportunity, Phase-16 situation-change). No LLM in any path that produces a bar value (an LLM
> may only phrase the one-line "why" on the deep page — the Phase-14.5 / 12-guardrail pattern). The
> Phase-16 bar is walled-off and explicitly unvalidated (see §6).

---

## 1. The interaction — two tiers

Every player on a board (draft board, mock-draft page, roster table) is both **hoverable** and
**clickable**:

- **Hover → overview card** — a small, glanceable card: **5 bars**, each a bar + a number. Answers
  *"should I even consider him right now?"* in under a second. Deliberately **not** exhaustive.
- **Click → deep page** — a dedicated route (`/player/<key>`), *much* more in-depth: **all 8 bars** with
  numbers **and** a one-line plain-English why, plus deeper breakdowns (weekly distribution, situation
  context, opportunity components, ADP/value history, honest limitations).

This split resolves the "simple **yet** detailed" tension: the hover is simple; the page is detailed.

---

## 2. The eight bars → frozen-contract mapping

Nothing here requires new modeling — every bar reads an existing frozen output.

| # | Bar | Backing contract / field | Hover | Page |
|---|-----|--------------------------|:----:|:----:|
| 1 | **Impact / value** | `value_board`: `vbd`, `pos_rank`, `overall_rank` | ✅ | ✅ |
| 2 | **Upside / ceiling** | `player_distributions`: `boom_prob`, `q90` (vs `mean`) | ✅ | ✅ |
| 3 | **Downside / floor** | `player_distributions`: `bust_prob`, `q10` (vs `mean`) | ✅ | ✅ |
| 4 | **Injury / availability** | `games_played_mean`, `avail_p`, `team_games`; Phase-6 `DURABILITY` | ✅ | ✅ |
| 5 | **Draft-cost value (bargain)** | `value_board` `overall_rank` − ADP-board rank | ✅ | ✅ |
| 6 | **Situation-change upside** | Phase 16 (`team_changed`, `new_starting_qb`, competition, scheme) | — | ✅* |
| 7 | **Week-to-week consistency** | Phase-5 weekly CoV (`sd`/`mean`; `boom_prob`/`bust_prob` are the weekly signal) | — | ✅ |
| 8 | **Opportunity / role security** | Phase-3 `features/opportunity.py` (target share, WOPR, aDOT, RZ, snap/touch role) | — | ✅ |

\* Bar 6 renders **visually distinct** and never feeds a cost/value number (§6).

**Deep-page reach-risk / draft-market-drift readout** *(added 2026-07-23; fed by Phase 16.7–16.12, the
availability-side track).** Distinct from bar 5 (bargain = a static value gap, "how much *value* he is at his
ADP") and bar 6 (situation-change *upside* = a value signal): this readout answers **"will he even be there
when I pick, and is he going earlier than his ADP says?"** — the availability signal. It shows an honest
**`P(available at your pick)`** (from the 11.2 availability oracle, drift-adjusted) plus a **reach-risk flag**
when the drift signals point early ("trending up / sharp-market ADP ~1 round ahead of public — consider
reaching"). Directly defuses the user's "fell to me in 10 mock drafts, then got sniped in the real one" bad
experience by replacing a yes/no fall with a probability. Inputs = 16.8 drift model (VBD-ADP gap + source
divergence + situation flags), 16.11 live 2026 momentum (labeled live-only), and the 16.10 curated hype
board. Like bar 6 it is **walled-off** from the frozen cost/value/optimizer stack and its momentum/hype
components are **tagged as live/curated, not backtested claims**. Deep-page only (needs a draft slot to
condition on); a compact "P(here at your pick)" chip may also appear on the hover card during a live mock.

**Number shown per bar** (the "detailed" half of the hover, per Q4 = bar + number):

1. Impact → positional rank, e.g. **"WR7"** (from `pos_rank`).
2. Upside → **boom-week %**, e.g. **"34% boom weeks"** (`boom_prob`), or `q90` points.
3. Downside → **floor points** `q10`, e.g. **"floor 118 pts"** (bar inverted — big green = high floor).
4. Injury → **expected games**, e.g. **"15.2 of 17"** (`games_played_mean`).
5. Bargain → **value vs cost**, e.g. **"+1.5 rounds of value"** (`overall_rank` vs ADP).

---

## 3. The hover overview card (5 bars)

- Header: name · team · position · ADP.
- Five bars (#1–#5), each **bar + number**, no prose (prose lives on the page).
- Footer: a single **"Open full profile →"** affordance (the click target).
- The three deep-page-only bars (#6–#8) are the "why/context" signals — deliberately withheld from the
  glance so the hover stays a *draft-now* decision, not a scouting report.

## 4. The player deep page (all 8 bars)

Reached by clicking a player anywhere. Contents, top to bottom:

1. **Identity strip** — name/team/pos/age/ADP/`overall_rank` + the **confidence indicator** (§6).
2. **All 8 bars**, each: bar + number + **one-line plain-English why**
   (e.g. *"Upside — 34% boom weeks · top-15% at WR — new OC projects a higher target share."*).
3. **Weekly distribution** — the Phase-5 cloud drawn as a floor→ceiling band (`q10`/`q50`/`q90`) so the
   upside/downside/consistency bars have a picture behind them.
4. **Situation context** (§6) — the Phase-16 flags for this player, framed as hypotheses.
5. **Opportunity breakdown** — the Phase-3 components behind bar #8.
6. **Honest limitations footer** — a short, standing note that levels are ~optimistic and unconditional
   attrition is under-modeled (the lockbox finding), so the page never presents false crispness.

---

## 5. Visual grammar (the rules every bar obeys)

- **Green = good for the drafter, always.** Bars for *risk* traits (injury, downside) are **inverted** so
  a durable, high-floor player shows a **big green** bar, not a big red "risk" bar. One consistent reading
  everywhere: **more green = more you want him.** Length tracks the same scale as color (bigger = better).
- **Three tiers** — green (top) / yellow (middle) / red (bottom), a quasi-bar the user reads at a glance.
- **Dual baseline on every bar** (Q2 decision): each bar carries **two** references —
  - **Primary / top: overall** — percentile vs the entire draftable pool.
  - **Secondary / below: within-position** — percentile vs same-position peers (e.g. "top-15% at WR"),
    rendered as a tick/marker + label beneath the primary fill.
  - *Why both:* overall alone makes a whole position look uniformly weak/strong on some traits; positional
    alone hides that an elite-for-his-position TE is still a modest overall pick. The pair keeps a
    cross-position draft-slot comparison honest **and** gives the "great for a TE" read.
- **Draft-cost is its own bar (#5), not the baseline.** ("Good for where he's picked" lives in the bargain
  meter; the other bars grade the *trait*, not the price — the two are kept separate on purpose.)

---

## 6. Honesty rules (non-negotiable — inherited from the engine's discipline)

- **Situation-change bar (#6) is walled-off and unvalidated.** Phase 16 ships *descriptive-only, no
  backtested-edge claim* (thin sample, no FDR gate on the transport piece). On the page this bar renders
  **visually distinct** (hatched / outlined, tagged *"directional context — not a calibrated
  projection"*) and **never** feeds any cost/value/impact number or the optimizer. It is scouting color,
  not a recommendation. Whichever of Phase 16.1/16.2's signals *did* survive their BH-FDR gate may show
  their CI + sign-stability, same presentation as the DURABILITY credit — but still off the hover.
- **Confidence indicator.** Rookies, `no_prior`/missingness-flagged players, and `source = proxy`/`rookie`
  rows (vs `consensus`) have genuinely softer estimates. A small marker on the card/page flags "thin data
  — read the bars as wide," so a shaky estimate is never presented with false crispness.
- **Bars are relative, not promises.** The lockbox showed the stack is well-calibrated in **rank** and
  championship probability, but ~optimistic in **level** with under-modeled unconditional attrition. The
  page's limitations footer says so plainly.

---

## 7. Target surface

- **Primary: the Next.js + TypeScript frontend (Phase 14.3 / go-live tail).** True hover tooltips on
  arbitrary marks, per-player routes, and the elegant styling this design wants are real-frontend
  capabilities. This spec is written against that frontend, fed by the Phase-14.1 FastAPI backend
  (`app/backend/`) serving the frozen contracts.
- **Streamlit fallback (Phase-14.1 MVP).** Streamlit can't do true per-mark hover; the reduced version is
  **click-to-expand** cards (`st.expander` / a selected-player panel) on the existing board/roster tables
  — same bars, same numbers, no hover. Acceptable as an interim; not the target look.

---

## 8. Data readiness

| Bar | Data status |
|-----|-------------|
| #1 Impact, #2 Upside, #3 Downside, #4 Injury, #7 Consistency | ✅ **built & frozen** (Phases 4/5/6) |
| #5 Bargain | ✅ built (`value_board` + ADP board) |
| #8 Opportunity | ✅ built (Phase-3 `features/opportunity.py`) |
| #6 Situation-change | ⏳ **needs Phase 16** (value-side 16.1–16.6) — the one *bar* gating dependency |
| Reach-risk / drift readout | ✅ **engine-side built** 2026-07-26 (16.12 `draft/drift.py::availability_readout`) — UI still owed by Phase 14 |

**The new-signal dependencies both point at Phase 16.** Building Phase 16 next double-serves: the value-side
(16.1/16.2 mined signals + 16.4 fingerprints + 16.6 tab) lights up the Beta-Lab tab *and* supplies the deep
page's situation-change **bar #6**; the availability-side (16.7–16.12) supplies the **reach-risk /
draft-market-drift readout** + the honest `P(available at your pick)`. Everything else the cards need already
exists behind frozen contracts.

> **Update 2026-07-26 (Session G complete).** The availability-side readout now **exists engine-side**:
> `draft/drift.py::availability_readout` returns `p_available`, `p_available_baseline`, `drift_picks`,
> a three-bucket `reach_risk` label (`likely gone` / `coin flip` / `likely available`) and a
> `drift_material` flag. Three rules the UI must honour, because they are the honest part:
> 1. **Always render the pair**, never the drift-adjusted probability alone — the adjustment rests on
>    a curated board and a forward-only momentum series, and Phase 16 returned four honest nulls.
> 2. **Never show `pick_delta` as a predicted change in draft slot.** Measured elasticity is ≈0.44
>    realized picks per claimed pick; it is a nudge, not a repricing.
> 3. **Deep claims may be inert in a 15-round league** (→ T16). Mark them rather than showing a
>    reach-risk that cannot move.
>
> The drift channels are **opt-in and default OFF**, and the shipped `reference/hype_board.csv` is
> `reviewed=false` — so by default this readout shows the plain 11.2 availability oracle.

Implementation order (unchanged from ROADMAP): **Phase 16 → Phase 14.1 backend → Phase 14.3 frontend
(this spec)**. The FastAPI backend (14.1) exposes a per-player endpoint returning the 8 bar values +
percentiles (overall & positional) + the confidence flag; the frontend renders them per this doc.

## 9. Deferred / open

- Exact tier cutoffs (green/yellow/red percentile bands) — set at build time; likely tertiles, tunable.
- Whether the deep page shows player-vs-player **comps** — nice-to-have, later.
- Mobile/compact hover behavior (tap-to-preview before full navigate) — frontend detail, later.
