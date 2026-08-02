# UI-PLAN.md — the competitive UI/UX deep dive, and the evidence behind Sessions UI-1 … UI-4

*Research session, 2026-07-31 / 2026-08-01. **Docs only** — no `src/` change, no `app/` change, no
test-count change. Written against the Session-K2 app (`app/`, 1,903 lines, six pages, Streamlit 1.59).
Companion to `docs/PLAYER-VIEW.md` (which specs the player card) — this doc covers **everything else on
the screen**, and where the two disagree, PLAYER-VIEW.md wins on the card and this doc wins on the board.*

> **★ Where the build spec lives.** This document is the **evidence and the argument** — eleven products
> surveyed, our app audited page by page, the recommendation register (§4), and fourteen explicit
> non-recommendations (§5). The **plan of record** — four sessions, their steps, their pre-registered
> bars and their ⚠ do-nots — is `docs/BUILD_PLAN.md` §"Sessions UI-1 … UI-4", written 2026-08-01 from
> this. Read that to build; read this to know why. The two defects the audit found are registered as
> **T37** (the reach-risk expander) and **T38** (the `st.json` dump) and are UI-1's step 0.

> **The one-sentence finding.** Our app is not missing analysis — it has **more** decision-relevant
> content than any product surveyed. It is missing an **information architecture**: everything renders at
> one altitude, in undifferentiated tables, with the epistemics carried in prose. Every competitor encodes
> meaning in *visual* channels — colour, tier bands, icons, position on screen — and keeps prose one click
> away. That single difference is the entire usability gap.

---

## 0. What was surveyed, and how

Eleven products, plus the design literature. Where a page was a JS app that could not be read directly,
the source was the vendor's own feature documentation, support articles and third-party reviews.

| Product | What it is | What was read |
|---|---|---|
| **FantasyPros Draft Wizard** | The market leader; 6-tool suite | Draft Assistant, Mock Draft Simulator, Cheat Sheet Creator, Pick Predictor, Draft Intel, Draft Analyzer docs + blog walkthroughs |
| **Draft Sharks Draft War Room** | The most analytically dense paid tool | "Inside the War Room", the 17-indicator list, the live PPR rankings table, the cheat-sheet KB |
| **PFF Mock Draft Simulator** | 2026 rebuild; the most-improved product this year | Their own "every new feature" release post |
| **4for4 Draft Hero** | The best-documented *layout* of any tool | The official Draft Hero walkthrough (panel by panel) |
| **RotoWire Draft Assistant** | Single-screen live assistant | Product page |
| **Sleeper** | Best-in-class league host / mobile | Support centre, queue-vs-watchlist docs, third-party tier tooling |
| **ESPN / Yahoo draft rooms** | The baseline every user already knows | Official queue/draft-room support articles |
| **Underdog Fantasy** | The most *polished* draft flow in the industry | Reviews; consistently praised for fewest-taps drafting |
| **Ultimate Draft Kit (Fantasy Footballers)** | Tier-first mobile draft kit | App-store listings + their own review |
| **Footballguys Draft Dominator** | The old-guard power tool | Reviews (notable for its criticism) |
| **Boris Chen tiers / KeepTradeCut / FantasyCalc** | The visualisation reference points | Method pages + calculator UIs |

Plus: dashboard-design literature on data density, colour semantics and progressive disclosure, and the
Streamlit 1.59 API surface (theming, `column_config`, Styler, `pills`, `segmented_control`, `badge`,
`popover`, `fragment`) to keep every recommendation implementable *today* without a new dependency.

---

## 1. The landscape, product by product

### 1.1 FantasyPros Draft Wizard — the one to beat on *workflow*

Six tools that hand off to each other, and the hand-offs are the product:

- **Cheat Sheet Creator.** Drag-and-drop reordering of a 100-expert consensus; **tiers inserted by
  hovering between two rows and clicking "Insert Tier"**, then draggable as units; three default tags
  (🎯 Target / 💤 Sleeper / 🚫 Avoid) plus user-defined tags that **persist across every cheat sheet**;
  expert notes pre-populated with a "My Notes" field beside them; printer-friendly export and Excel
  download; cloud-synced across mobile and desktop.
- **Mock Draft Simulator.** Settings panel (league sync, roster config, positional-value weighting,
  "Draft Against" bot-logic control); the cheat sheet is a **tab inside the draft screen**, not a separate
  page; **Pick Predictor** as its own tab; a draft log you can **edit opponents' picks in** and restart
  from any point; post-draft Draft Analyzer report card.
- **Pick Predictor.** The single most-copied idea in the category: **"% odds this player is still there at
  your next pick"**, toggleable to 1 / 2 / 3 rounds out, computed by simulating over the cheat-sheet
  database and accounting for what's gone and what opponents still need.
- **Draft Intel.** Syncs **five years** of your league's real draft history and reports per-manager
  tendencies — how long each manager waits on QB, how RB-heavy they are early, whether they take a backup
  TE — each insight expandable to the actual picks behind it, and each **toggleable on/off per team** so
  your mock room drafts like your real room.
- **Draft Assistant.** Live sync crosses off taken players; suggestions consider your cheat sheet, team
  needs and positional scarcity; a **streamlined compact view** that parks in a screen corner beside the
  real draft site.
- **Draft Analyzer.** Grade, projected standings, positional strengths/weaknesses, best/worst picks.

**What to steal:** the tag system, tiers-in-the-board, Pick Predictor's framing, and the compact view.
**What not to:** drag-to-reorder rankings (see §5).

### 1.2 Draft Sharks Draft War Room — the most analytically dense, and the cautionary tale

Their live rankings table ships these columns, in this order:

> `RK · Player · Games · ADP · Bye · SOS · Injury Risk · Floor Proj · Consensus Proj · DS Proj · Ceiling Proj · 3D Value · Tier`

Design features worth naming:

- **Tier as a grey full-width section header** dividing player groups — not a column, a *break in the
  table*. This is the category's dominant tier idiom.
- **Quick-Check Icons** beside the player name: injury status, sleeper, breakout, handcuff.
- **An ADP countdown** — not raw ADP, but *how many picks away from his ADP your draft currently is*.
- **Bye-week conflict alerts fired at pick time**, against players you already hold at that position.
- **Colour-coded valuation** — green undervalued, red overvalued — on ADP.
- **Top-5 recommendations highlighted when it is your turn**, updating live.
- **3D Projections**: floor / consensus (38 sources) / ceiling shown together, feeding one **3D Value**.
- 17 named live indicators (scoring, positional value, 3D projections, value-vs-baseline, your needs,
  opponents' needs, evolving scarcity, injury risk, breakout likelihood, correlated ADP, bye conflicts,
  flex options, bench depth, trust factor, personal projection adjustments, positional tiers, SOS).

**The cautionary half — and it is the most important single sentence in this whole survey.** Their own
category review lists as a *weakness*: *"the extensive amount of features and data might be
overwhelming."* Footballguys draws the same criticism ("information overload for casual users"). **The
most analytically rich tools in this market are penalised for it.** We have more indicators than Draft
Sharks. The correct response is not to add; it is to *rank and hide*.

### 1.3 PFF Mock Draft Simulator — the best 2026 feature set

- **Big Board Builder** — build and save a custom board *before* drafting, then import it into mocks.
- **Undo last pick** — reverse one selection and re-decide without restarting. Reportedly the
  most-requested mock feature for years.
- **Multiplayer rooms** — private rooms by invite code.
- **Live leaderboards** — community ADP across all mocks run on the platform, filterable by timeframe.
- **My Mock Drafts hub** — every completed mock, searchable, filterable, **sortable by draft grade**.
- Randomness sliders, positional-value weighting, speed/turbo settings, post-draft grade breakdown.

**What to steal:** undo, and the mock-history hub. Both turn a one-shot toy into a practice loop.

### 1.4 4for4 Draft Hero — the best-documented *layout*

The only product with a publicly specified panel arrangement, and it is worth reproducing:

```
┌─ summary grid: first two rounds, condensed ─────────────────────────────┐
├──────────────┬──────────────────────────────────┬──────────────────────┤
│ LEFT RAIL    │  CENTRE: recommendations          │  RIGHT: draft status │
│  Draft Board │   "Top 5 Recommended" button →    │   every pick from    │
│  Rankings    │   5 best available w/ ADP, proj   │   the last round,    │
│  Site ADP    │   pts, ARV                        │   all teams visible  │
│  Fantasy     │   "Top Recommended" w/ dropdown   │                      │
│    Rosters   │   filters: ADP / targets /        │                      │
│  NFL Rosters │   avoids / watchlist              │                      │
│  Draft Plan  │                                   │                      │
└──────────────┴───────────────────────────────────┴──────────────────────┘
```

- Left rail is **tabbed**, so one region serves six jobs without navigation.
- **Fantasy Rosters** tab: every league roster, **position-colour-coded**, starters in the upper half and
  bench below — i.e. the roster view is *slot-aware*, not a list.
- **NFL Rosters** tab: all 32 depth charts, players highlighting in position colour once drafted.
- **Draft Plan** (paid): round-by-round position targets, with your picks filling in beneath.
- Position colour is used **consistently across all six tabs** — starters, bench, drafted, recommended.

**What to steal:** the three-region layout, the tabbed rail, and colour consistency across every surface.

### 1.5 RotoWire — the "everything in one screen" thesis

Projections, rankings, cheat sheets and auction values in a single interface that updates live; player
notes and a queue; colour-coded by position; explicitly sold on *"identify positional tier drop-offs and
predict positional runs."* No download, works on any device. Nothing novel — but note that **tier
drop-offs and position runs are the marketed benefit**, not a feature buried on page four.

### 1.6 Sleeper — the mobile/aesthetic benchmark

- **Queue vs Watch List are two distinct objects** and the distinction is documented: the queue is an
  ordered auto-draft list, the watch list is passive interest.
- Draft board is **fully editable, castable to a TV**, ships in **light and dark themes**.
- Draft-board view is explicitly sold as *"extra context on opponent moves so you can adapt to position
  runs and team needs."*
- Fantasy-relevant live scoring rather than generic box scores.
- **Its documented weakness is the queue's poverty:** one tap at a time, no tiers, no notes, no CSV import
  of any kind. A whole third-party product ("Sleeper Tiers") exists to work around it.

**Read that weakness carefully — it is our opportunity.** The best-designed platform in the category has
*no* tier support and *no* import. A tool that gets tiers and tagging right is filling a real hole.

### 1.7 ESPN / Yahoo — the conventions your users already have in their fingers

- **A draft-order strip across the top**: the team on the clock at the left, on-deck to its right, your
  team highlighted (ESPN uses a yellow square).
- Player pool sortable by position, NFL team, projected stats, bye week, with a search box.
- **Queue by drag-and-drop**, or right-click → "Add to Top of List" (ESPN); **star to queue** (Yahoo).
- Tabs to view every other team's roster mid-draft.
- A visible pick clock (Yahoo default 60s) and an on-the-clock message.

These are the conventions any user of ours already knows. **Deviating from them costs us; matching them
is free familiarity.**

### 1.8 Underdog — the polish benchmark

Consistently praised as the most polished in the category: *"lighter, cleaner slate, building a lineup
takes fewer taps."* Their best-ball draft flow is called out specifically for **clean queueing**,
**auto-pick fallback**, and a **usable post-draft roster view**. There is no feature here to copy — the
lesson is that *fewer taps per decision* is itself a competitive advantage, and it is measurable.

### 1.9 Ultimate Draft Kit — tiers as the entire product

Rankings separated into per-position tiers so you can see **which position to draft or avoid** at a
glance; tap a player for a full report (three rankers' ranks, projections, prior-year stats, video
breakdown, notes); **customisable, printable cheat sheets with expandable/collapsible detail** and custom
markers. Their marketing line is that tier-based drafting is *the* effective way to use a draft tool.

### 1.10 Footballguys Draft Dominator — what happens without an information architecture

Deep customisation, complex-league support, an extensive knowledge base — and reviews that say
**"information overload for casual users"** and note reliability problems at peak. Feature-complete and
unpleasant. This is the failure mode nearest to where we currently sit.

### 1.11 The visualisation references

- **Boris Chen's tier charts** (NYT / borischen.co): expert consensus ranks passed through a **Gaussian
  mixture model** to find natural tiers, then drawn as a one-dimensional plot with tier bands. The whole
  product is *one chart*, and it is the most-cited fantasy visualisation there is. The lesson: **a tier
  is a statistical claim about indistinguishability, and drawing it beats ranking.** This is exactly what
  our `COIN` column already computes and buries.
- **KeepTradeCut** trade calculator: per-asset trend sparklines, average age, average rank, **value
  dispersion**, stacked bars, and suggested add-ons to balance a deal. Dense, but every element answers
  one question. Worth studying as "how to show a distribution of value without a table."

---

## 2. The shared design grammar — fourteen conventions every product obeys

This is the distilled answer to "what do they all do that we don't."

1. **Position is a colour, everywhere, always.** One hue per position, identical on the board, the
   rosters, the draft grid, the log and the recommendation panel. It is the primary scanning channel.
   (Common convention: QB gold/yellow, RB red, WR blue, TE orange, K purple, DST green.)
2. **Tiers are drawn, not stated.** Either a grey full-width break row (Draft Sharks) or a banded column
   (UDK). A tier break is the single most decision-relevant fact on a draft board.
3. **The board is a *board*, not a table.** Teams across the top, rounds down, snake direction indicated,
   your column marked, every cell in position colour.
4. **A draft-order strip lives at the top of the screen at all times.** On the clock · on deck · your next
   pick.
5. **Three regions: rail / board / status.** Roster and needs on one side, the pool in the middle, the
   room on the other side. Nothing important requires navigation during a pick.
6. **Recommendations are a distinct, highlighted object** — "Top 5 Recommended", surfaced *when it's your
   turn*, not a sort order on a table.
7. **Value is relative to *now*, not absolute.** ADP countdown, value-vs-baseline, green/red bargain
   colouring. Raw ADP alone is never the whole story a tool tells.
8. **Icons carry status; prose carries explanation.** A row gets glyphs (injury, sleeper, breakout,
   handcuff, bye conflict); the sentence explaining the glyph is in a tooltip.
9. **Every player is clickable to a profile, and the board stays visible.**
10. **Ranges are shown as ranges.** Floor / projection / ceiling as three columns or one band — not a
    single number.
11. **Targets and avoids are first-class, persistent objects** (tags, queue, watch list, flags), created
    on the board and consumed everywhere else.
12. **Post-draft is a report card, not a data dump.** A grade, a projected finish, strengths/weaknesses,
    best and worst picks.
13. **Progressive disclosure is the default.** A compact view for the clock; an advanced view on request.
    FantasyPros literally ships a "streamlined view" for the corner of your screen.
14. **Light and dark themes, and a deliberate visual identity.** Nobody ships framework defaults.

---

## 3. Where fantasy-quant stands — the honest audit

### 3.1 The measurement

Counted across `app/` (1,903 lines):

| Element | Count |
|---|---|
| `st.dataframe` | 22 |
| `st.caption` | 37 |
| `st.warning` / `info` / `error` / `success` | 31 |
| `st.markdown` prose blocks | 28 |
| `st.metric` (the only visual encoding present) | 9 |
| Colour used to encode anything | **0** |
| Icons used to encode status | **0** |
| Tier breaks drawn on the board | **0** |

**Sixty-eight blocks of prose to nine visual elements.** That ratio *is* the problem. Every competitor
inverts it.

### 3.2 Page by page

**Settings.** A 15-field form with no presets, opening the app. Every competitor opens on a board and
imports a league. The lockbox banner is right and important, but it is a paragraph where it should be a
badge with a popover.

**Board.** Three filters, a mode radio, a metric strip, one 4-to-15-column dataframe, then a *separate*
text box that re-searches the same board to print the `why` chain. Problems:
- No colour, no tiers, no icons, no bargain-vs-now column.
- `ADVANCED` is **15 columns** — two more than Draft Sharks' full rankings table, which is their
  most-criticised property.
- The `why` search box duplicates the board's own row-selection → player dialog. Two paths to one fact.
- The cliff strip states a point drop but not **how many picks until the cliff binds**, which is the
  actionable half.

**Draft room.** The best page in the app, and still: the on-the-clock line is markdown, not a seat strip;
the room composition is inside a collapsed expander; picking a player is a three-step flow (type → click a
match button → click "Draft him"); the quick-pick row is six buttons that duplicate the top of the table;
and **`_reach_risk` — the single best asset in the app — renders inside `st.expander(..., expanded=False)`
directly beneath a docstring that says "a readout you have to ask for is a readout nobody asks for."**
The docstring is correct and the code contradicts it.

**The room (grid).** A radio over three views; the grid is an uncoloured dataframe. A draft board without
position colour cannot show a position run, which is the *only* reason to look at a draft board mid-draft.

**Post-draft.** Five dataframes, a metric block, and **`c1.json(frames["elite"])` — a raw JSON dump in a
shipped user interface.** The grade panel shows a letter and a components table; PLAYER-VIEW.md §5 specs
bars with dual baselines and none are drawn.

**Cost.** The most novel thing we have and the worst-presented. Four `st.multiselect`s over a
~200-entry option list, rebuilt every rerun, with no way to carry a preference over from the board where
you formed it. Then a button, a spinner, three metrics and two side-by-side tables.

### 3.3 What we have that nobody else does — and are hiding

This matters as much as the deficits, because it defines what the redesign should *promote*:

| Ours | Nearest competitor | Where it currently lives |
|---|---|---|
| `P(available at your next pick)` **with an un-drifted baseline**, from a validated survival model | FantasyPros Pick Predictor (no baseline, no validation claim) | a collapsed expander |
| `COIN` — *146 of 199 adjacent board pairs overlap at 10–90 %* | nobody. Boris Chen's tiers are the closest idea | a checkbox column in a non-default view |
| `censored floor` — "no resolvable floor" vs "a floor of zero" | nobody | a text flag |
| The T27 value chain `PROJ → MEAN → AVAIL → BV` as an auditable identity | nobody | a text box on the Board page |
| Lockbox provenance (this format has an out-of-sample number; yours doesn't) | nobody | a paragraph |
| Personalization **cost** vs a pure-value benchmark | nobody | the Cost page |
| A fitted, calibrated opponent room (10 personality seats) | FantasyPros Draft Intel (real league history) | a selectbox |
| Printed grade weights with "nothing validates this blend" | nobody — everyone hides the formula | a caption |

**The strategic read: our differentiation is epistemic — honesty and auditability. The redesign's job is
to make that feel like a feature rather than a disclaimer.** Concretely, that means a *visual language for
confidence*, not more sentences about it.

---

## 4. Recommendations

Ordered by (usability gained) ÷ (effort), with the repo's own constraints attached.

> **The constraint that governs every item below.** `draft/session.py` is the one derivation site;
> `app/` only formats (Session K1's rule, and the reason bar B1 holds by construction). Several
> recommendations below add a **column** — `TIER`, `VALUE`, `BARGAIN`, richer `FLAGS`. Every one of those
> is arithmetic on frozen contracts and therefore lands in `session.board_view`, **never** in `app/`.
> Items that are pure formatting are marked ⬤; items that need a new `session.py` function are marked ◆.

### S — do these first

**S1 ⬤ Position colour, everywhere.**
One palette, applied to the `POS` cell on the board, the room grid cells, the log, the roster rail and the
post-draft rosters. `st.dataframe` accepts a `pandas.Styler` and Streamlit supports custom cell colours
through it. Suggested (matching the market convention so it reads correctly to anyone who has drafted
before): QB `#D9A441`, RB `#C0504D`, WR `#4472C4`, TE `#E8833A`, K `#8064A2`, DST `#4F8A5B`. Dark-theme
variants at ~35 % opacity as cell backgrounds with full-strength text.
*Effort: ~40 lines in `app/views.py` + a palette constant. Impact: the largest single readability gain
available, and it makes position runs visible in the grid for the first time.*

**S2 ◆ Tiers on the board.**
Add a `TIER` column — a within-position tier index derived from the machinery `cliff_series` already uses
— and render it as (a) a banded colour column and (b) row shading that alternates by tier. Two honest
options for how tiers are cut, and the second is the one that fits this repo:
- **(a) gap-based** — a tier ends where `base_value` falls by more than the pool's local median gap;
  cheap, and it is essentially what `positional_cliff` already computes.
- **(b) overlap-based — the one to build.** ⚠⚠ **BUILT AND MEASURED A NULL, 2026-08-01 (T39).**
  On the live board it cuts **1 tier per position** and **2 over the whole board**: the median RB 80 %
  band is 228 pts against a median adjacent gap of 16.3 (**14×**), so every adjacent pair overlaps by
  construction. And the analogy below is a **category error** — Chen clusters expert rank *dispersion*,
  we hold a *predictive interval*. The paragraph that follows is left as written because it is the
  argument that was made; it is wrong, and T39 records why. A tier ends where the 10–90 bands *stop* overlapping. That
  makes the tier a statement of **statistical indistinguishability**, which is what `COIN` already
  measures, and it turns our best honesty column into the most useful navigation aid on the board. It is
  also, precisely, Boris Chen's thesis executed on our own distributions rather than on expert ranks.
  **This would be a genuinely differentiated feature, not a catch-up one.**

⚠ The existing note in `cliff_strip` is right that a dataframe cannot carry a separator row, because the
frame's index *is* the board index that `_apply_pick` consumes. So: column + shading, never a fake row.

**S3 ⬤ Cut prose ~70 % by relocating it, and give confidence a visual language.**
The rule: *any explanation longer than one line moves into a `help=` tooltip, an `st.popover` or an
`st.expander`; only state-dependent facts stay inline, and they become `st.badge` chips.*

**This does not weaken the honesty discipline and must not be allowed to.** The repo's rule is that
honesty surfaces must *render*. A badge that says `⚠ not lockbox-validated` with a popover carrying the
current paragraph renders, is more likely to be read than a four-line block the eye skips, and is
strictly better than the status quo. Concretely:
- Lockbox banner → a header badge, green `LOCKBOX-VALIDATED` or amber `NOT VALIDATED`, popover for the
  detail. (Both branches still render, as `settings_form.lockbox_banner` requires.)
- `range_note`'s COIN sentence → a chip `146/199 pairs overlap` + popover.
- `censored floor` → a **half-filled / hatched** floor bar on the card and a `⌀` glyph in `FLAGS`, with
  the "unresolvable, not zero" sentence in the tooltip. This is the visual language item: *a censored
  quantity should look different, not be described as different.*
- `honesty_notes` (k seats are one observation) → keep as a banner. It is state-dependent and
  consequential; it earns its space.
- The grade-weights disclaimer → keep, but as one line + popover. Do not delete it; being the only tool
  in the category that prints its own blend weights is a feature.

**S4 ⬤ A theme.** Project-local `.streamlit/config.toml`. Streamlit 1.59 exposes `theme.base`,
`primaryColor`, `backgroundColor`, `secondaryBackgroundColor`, `textColor`, `borderColor`,
`dataframeHeaderBackgroundColor`, `dataframeBorderColor`, `baseRadius`, `buttonRadius`,
`showWidgetBorder`, `chartCategoricalColors`, and a separate `[theme.sidebar]` block. ~25 lines to stop
looking like a framework default. Set `chartCategoricalColors` to the position palette so any future chart
inherits it.

**S5 ⬤ A draft-order seat strip, pinned to the top of the draft room.**
Replace the markdown on-the-clock line with a horizontal strip of `n_teams` chips: team label, seat
personality, position-coloured last pick, **your seats outlined**, the team on the clock filled, on-deck
outlined, and a `→` / `←` snake-direction arrow. Add "your next pick: **#37** (12 picks away)". Every
mainstream draft room has this; it is the first thing a drafter's eye goes to. `st.columns(n_teams)` with
`st.container(border=True)` and `st.badge` gets there with no HTML.

**S6 ⬤ Un-hide the reach risk.** Move `session.reach_risk_view` out of the collapsed expander and into the
right rail, permanently, beneath the roster. It is ~20 ms, it is our best asset, and the module's own
docstring already argues for exactly this. Add `P(THERE)` as a column on the **slim** board — it is more
decision-relevant under a clock than `PROJ`.

### A — do these second

**A1 ◆ A queue / tag system, unified with the Cost page.**
The largest missing *feature*, universal across the category, and it solves our worst form at the same
time. Design:
- Four tags, matching the Cost page's existing four preference kinds so nothing new is invented:
  🎯 **must** · 🚫 **never** · ↑ **reach** · ↓ **wait**. Plus an untagged ⭐ **queue** for ordering.
- Set from the board (a `CheckboxColumn`-style tag cell, or buttons in the selected-player strip).
- Persisted in `st.session_state` keyed by `player_key`, surviving page navigation.
- Rendered as a `★`/tag column on every board view and as a **Queue panel** in the draft-room rail with a
  "draft top of queue" button.
- **The Cost page reads the tags instead of its four multiselects.** That deletes ~15 lines of
  option-list building, removes the T35-adjacent rebuild cost, and — the real win — lets a user form a
  preference *while drafting* and then price it, which is the actual workflow the direct-indexing thesis
  describes and which the current UI makes impossible.

**A2 ◆ A selected-player strip, inline above the board.**
`PLAYER-VIEW.md` §11 records that Streamlit has no hover, so one modal serves both the hover card and the
deep page. That is a real cost — the modal covers the board you are picking from. The honest resolution:
keep `st.dialog` as the deep page, and add a **compact strip** that renders inline when a row is selected —
name · pos · tier · ADP · the five §3 hover bars · `P(there)` · **Draft him**. That is PLAYER-VIEW §3's
hover card, rendered as a strip rather than a hover, and it keeps the board on screen (convention #9).

**A3 ⬤ Draw the bars.**
`views.grade_panel` and `player_card_body` currently render `st.metric` — a number with no bar and no
baseline. PLAYER-VIEW §5 specs a quasi-bar with **green = good always** (risk traits inverted), a
three-tier colour band, and a **dual baseline** (overall percentile as the fill, within-position
percentile as a tick beneath). `st.html` renders this in ~20 lines of inline SVG/CSS per bar and needs no
component. This is the largest gap between the written spec and what shipped.

**A4 ◆ Value relative to *now*.** Two columns, both arithmetic on existing frozen fields:
- `Δ` = `adp − current_overall_pick` — Draft Sharks' ADP countdown. Positive = he is falling to you.
- `BARGAIN` = `overall_rank − adp_rank` — PLAYER-VIEW bar #5, specced and never put on the board.
Colour both green/red. This is convention #7, and it is the thing a drafter actually asks.

**A5 ◆ Live construction flags on the board.**
`session.roster_construction_risk` already computes bye clustering, NFL-team concentration and handcuff
gaps — and only renders them **after** the draft, when they can no longer be acted on. Surface them as
row glyphs at pick time:
`⚑` bye collides with N of your starters · `⛓` same NFL team as k of your starters · `🛡` handcuff for an
RB you hold · `⌀` censored floor · `◔` thin data / no prior.
Draft Sharks fires bye-conflict alerts at pick time and it is one of their best-reviewed touches. **Ours
would be the only one that also prices team concentration, because the covariance is already in the
optimizer.** ⚠ These are per-seat and pool-dependent, so the derivation belongs in `session.py` beside
`board_view`, not in a renderer.

**A6 ⬤ Post-draft as a report card.**
Delete the `st.json` dump. Lead with a hero row — **grade letter · title fair-share multiple · STARTABLE
rank** — then a positional-strength bar chart of your team vs the room median, then push standings / odds
/ every-team / draft-flow behind `st.tabs`. Keep every honesty note; move the long ones into popovers.
Add "best pick / worst pick" as a headline pair (we already compute `pick_drift_table`; it is currently a
six-row table under a heading nobody reads).

**A7 ⬤ Fewer taps to a pick.** Current: type → click a match → click "Draft him". Proposal: a single
searchable `st.selectbox` over available players (Streamlit selectboxes filter as you type) that loads
the confirm bar directly — two steps. Keep the explicit confirm; the comment defending it is right, a
mis-click costs a round. Delete the six-button quick-pick row: it duplicates the top of the table and the
selected-player strip (A2) replaces it.

### B — worth doing, lower leverage

- **B1 ⬤ Split `ADVANCED` in two.** 15 columns is past the point where anyone reads them. Offer
  `VALUE` (`PROJ · MEAN · AVAIL · BV · VBD · RK`) and `RISK` (`UPSIDE · FLOOR · TAIL · BOOM · BUST`) as
  separate modes via `st.segmented_control`. Each stays a projection of the one `board_view` frame, so
  bar B2's "one query, N projections" property is preserved.
- **B2 ⬤ League presets on Settings.** Buttons for "10-team PPR (lockbox)", "12-team half-PPR",
  "12-team superflex", "TE-premium" above the form. Cheap, and it makes the lockbox case a one-click
  default. (Real league import is Session K3 and is the proper fix.)
- **B3 ⬤ Room grid polish.** Position-coloured cells, your column highlighted, pick handles in-cell,
  snake arrows on the row labels.
- **B4 ⬤ Density control.** `st.dataframe(row_height=...)` — a compact/comfortable toggle.
- **B5 ⬤ Export.** `st.download_button` for the board as CSV and the roster as text. FantasyPros'
  print/export is among its most-used features and this is three lines.
- **B6 ⬤ Merge the `why` search into the player dialog.** One path to one fact; delete the second box.
- **B7 ⬤ First-run state.** Land on Board, not Settings. Settings becomes a badge in the header that
  opens the form.

### C — later, or engine work

- **C1 ◆ Undo last pick.** PFF's headline 2026 addition. Our `DraftState` is append-only and consumes an
  RNG, so honest undo = replay from the log with the same seeds, not a pop. **Engine work, and it must
  preserve the clocked-≡-stepped identity (bar B3).** Flag it, don't hack it.
- **C2 ⬤ Mock-draft history hub.** We already stamp `seed` + `room_seed` on every draft, so a saved list
  that replays exactly is nearly free — and it is strictly better than PFF's hub, which cannot replay.
- **C3 ◆ A "scouting report" on the room.** Our analog of Draft Intel, and we have the better version:
  `drift_frames["seats"]` already measures each seat's realised behaviour. Show per-seat tendencies
  before the draft ("T4 · reacher — takes his guy ~2 rounds early; T7 · safe_floor — never a rookie in
  rounds 1–3"). ⚠ PLAYER-VIEW §9.3 rule 1 applies: frame it as **realism, never as prediction**.
- **C4 ⬤ Light/dark toggle.** Streamlit gives it free once `[theme]` and `[theme.sidebar]` are set.

---

## 5. What I do **not** recommend

Deliberate omissions, each with its reason. Several of these are things every competitor has.

1. **Do not add `streamlit-aggrid`.** It is the obvious answer to "our tables are weak" and it is the
   wrong one here: it is a JS component with its own selection model, it would break the
   `on_select="rerun"` / board-index contract `_apply_pick` depends on, it adds a dependency the repo's
   test discipline would then have to cover, and Streamlit 1.59's `column_config` + Styler covers ~90 %
   of what we would use it for. Revisit only if we ever need frozen columns *and* row grouping at once.
2. **Do not start the Next.js frontend (14.3) yet.** It is the right eventual home for true hover cards
   and per-player routes. But the Streamlit app is roughly four focused sessions from being genuinely
   good, and starting the rewrite now restarts the UI learning at zero and abandons the surface that is
   actually finding defects (three real bugs were found by booting this app). Get Streamlit to
   "a friend can use it unaided," *then* port the settled design.
3. **Do not add player headshots or team logos.** Universal in the category, and an asset-licensing and
   pipeline problem for zero decision value. **Team colour on the row gets ~80 % of the recognition
   benefit for zero assets** — do that instead.
4. **Do not chase mobile in Streamlit.** A 15-column dataframe in `layout="wide"` is not going to work on
   a phone, and the workarounds are worse than the problem. Say plainly in the README that the Streamlit
   MVP is desktop; mobile is a 14.3 concern.
5. **Do not add LLM-generated player narrative to the board.** It violates the repo's own core guardrail
   (`CLAUDE.md` §4: no LLM in the core, AI on the edges only), and every competitor's version of it is
   filler that erodes trust in the numbers beside it.
6. **Do not copy Draft Sharks' 17-indicator density.** It is their single most-criticised property, and
   we already carry more indicators than they do. The fix is ranking and hiding, not adding.
7. **Do not delete the honesty surfaces while compressing them.** Compress and relocate — never remove.
   The lockbox banner, COIN, `censored floor`, the k-seats rule and the printed grade weights are the
   product's differentiator. Every one must still *render* after S3, in a form the eye actually lands on.
   A compression that makes one of them disappear has failed, not succeeded.
8. **Do not put any of the new derivations in `app/`.** `TIER`, `Δ`, `BARGAIN`, the construction flags and
   the seat-tendency report are all new *numbers*. They go in `session.py` or they will drift from the
   CLI, which is exactly the T18 / F.5 / T27 family this repo has already paid for three times.
9. **Do not build a second board frame for the queue or tier view.** Every view stays a projection of one
   `board_view` call (bar B2). A queue view is a filter on the same frame.
10. **Do not add drag-to-reorder custom rankings** (FantasyPros' Cheat Sheet Creator). Streamlit cannot do
    it well, *and* it fights the thesis: our board is model-derived, and a hand reorder would silently
    replace the value model with an opinion while every downstream number kept claiming to be calibrated.
    **The tags (A1) are the honest subset of that feature** — they express preference *and get priced* by
    the Cost page, which is strictly more useful than reordering a list.
11. **Do not add keyboard shortcuts.** Streamlit has no keypress hook without a custom component, and a
    half-working hotkey during a live pick is worse than none.
12. **Do not fake hover tooltips.** The 14.O column `help=` text is the honest version and it already
    exists on every column. Leave it.
13. **Do not build multiplayer draft rooms** (PFF 2026). Large surface, no analytical value, and it is a
    hosting problem before it is a UI one.
14. **Do not show absolute season probabilities more prominently than the fair-share multiples.** T29's
    ordering is correct and the temptation, when making a page prettier, is to put "17 % to win the
    league" in a big number. The sim carries a documented −113 pts/team level bias; the ratio survives it
    and the percentage does not. **Any hero-number redesign must lead with the multiple.**

---

## 6. Build order

> **★ This section became the spec at `docs/BUILD_PLAN.md` §"Sessions UI-1 … UI-4" on 2026-08-01.** That
> is the plan of record: per-step file targets, per-session pre-registered bars, per-session ⚠ do-nots,
> and the decisions that must be asked before a straight run is authorised. What follows is the summary
> it was written from. **Recommended order: UI-1 → K3 → UI-2 → UI-3 → UI-4** — UI-1 is pure formatting
> with zero engine risk and the largest impact per hour here, K3 makes the app *correct* for the user's
> actual league and should not queue behind three UI sessions, and the only real coupling is that UI-4's
> league presets sit above the same 17.3 form K3's importer fills.

Four sessions, each independently shippable, each gated per `CLAUDE.md` rule 7.

| Session | Contents | Character |
|---|---|---|
| **✅ UI-1 — "it looks like a product"** *(done 2026-08-01)* | S4 theme · S1 position colour · S3 prose compression + confidence chips · S5 seat strip · S6 un-hide reach risk (T37) · A6 kill the JSON dump (T38) | **Pure formatting**, with one authorised exception — `P(THERE)` is an existing number in a new *placement*, so `session.attach_reach`/`next_pick_info`/`team_for_pick` landed in `session.py` (user decision). Prose **68 → 23**; palette = **Okabe-Ito**, not the market convention; all eight bars PASS and **B0 classifies every one of the 23 changed leaves** in the nested sheets. Deferred to UI-2/UI-3: the positional-strength chart and the hatched `censored floor` **bar**. |
| **UI-2 — "the board answers the question"** | S2 tiers (overlap-based) · A4 `Δ` + `BARGAIN` · A5 construction flags · B1 split ADVANCED | **First `session.py` work.** New columns must appear in `STAT_DICT` (a column in `BOARD_VIEW_COLS` without an entry fails a test) and in the CLI board, or the two renderers have diverged. |
| **UI-3 — "preferences are first-class"** | A1 queue/tags + Cost-page rewire · A2 selected-player strip · A3 draw the bars · A7 fewer taps | The session that changes the *workflow*, and the one that makes the direct-indexing thesis actually reachable from the draft room. |
| **UI-4 — polish tail** | B2–B7 · C2 mock history · C3 room scouting report | Cheap items, batchable, no ordering constraints. |

**Carried through all four:**
- `steps/session_ui_N.py` + `analysis/session_ui_N.json`, in the house style, with the K2 sheet nested
  inside every one of them.
- A **`bar_flow`** run per session — drive the app under `AppTest` the way a human drives it (click Start
  draft, click a player). K1.5's lesson stands: an import bar and a use bar are different claims.
- `glossary.md` gains the new terms it earns (`tier band`, `queue`, `tag`, `seat strip`, `bargain`,
  `ADP countdown`) — per the standing glossary rule, not as an afterthought.

---

## 7. Acceptance bars (pre-registered, house style)

*These are the **claims**. `docs/BUILD_PLAN.md` §"Sessions UI-1 … UI-4" distributes them into per-session
sheets (`steps/session_ui_N.py` → `analysis/session_ui_N.json`), each carrying **B0** — the K2 sheet
re-run in full, K1.5 and K1 nested inside it — and a **`bar_flow`** at k ∈ {0, 1, 4}. Session mapping:
B0 all four · B1 → UI-1 · B2 → UI-2 · B3 → UI-1 (paired with the prose-compression bar, so a compression
that deletes an honesty surface fails) · B4 → UI-2 · B5 → UI-3 · B6 → UI-3 · FLOW all four.*

| bar | claim |
|---|---|
| **B0** | The K2 bar sheet re-runs passing in full at the end of every UI session — K1.5 and K1 nested inside it. Not one number moves. |
| **B1** | Every position on the live board renders in its palette colour on the board, the grid, the log, the rail and the post-draft rosters — **one palette constant, five surfaces, zero second copies.** |
| **B2** | ~~Tier boundaries on the live 2026 board are reproducible from `COIN` alone…~~ **RETIRED 2026-08-01 (T39).** The rule reproduces `COIN` exactly and cuts nothing; and the 146/199 anchor itself conflates *distinguishable* with *unknown* — 147 pairs have both bands, 146 overlap, **1** is a genuine break, **52** are missing bands. |
| **B3** | Prose blocks in `app/` fall from 68 to ≤ 25, **and** every one of the seven named honesty surfaces still renders — asserted by driving the app, not by reading the diff. |
| **B4** | Every new board column has a `STAT_DICT` entry with a worked example, and appears in the CLI board. The app and the CLI show the same columns with the same numbers. |
| **B5** | A tag set on the Board page is readable by the Cost page without re-entry, and `personalization_cost` receives exactly the `DraftConfig` the old four multiselects would have produced — differenced against a recorded run. |
| **B6** | Time-to-pick, measured under `AppTest`: from "your turn" to a completed pick in **≤ 2 interactions** for a queued player and **≤ 3** for an arbitrary search. (Currently 3 and 3.) |
| **FLOW** | All six pages render, zero exceptions, at k ∈ {0, 1, 4}, on a draft started and advanced **by clicking**. |

---

## 8. The three sentences to remember

1. **We are not behind on analysis; we are behind on encoding.** Everything the competitors show, we
   compute — and several things they don't. It is all in tables and paragraphs.
2. **The most data-rich tools in this market are penalised for being data-rich.** Draft Sharks and
   Footballguys are both criticised for overload while carrying fewer indicators than we do. Ranking and
   hiding is the work; adding is not.
3. **Our honesty machinery is the product, and it currently reads as apology.** `COIN`, `censored floor`,
   the un-drifted baseline and the printed grade weights are things no competitor offers. Given a visual
   language — a tier band, a hatched bar, a paired probability, a badge — they become the reason to use
   this tool instead of FantasyPros.
