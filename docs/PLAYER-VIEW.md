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
| Mock-room opponent selector | ✅ **engine-side built** 2026-07-27 (16.15 `draft/personalities.py::make_room`) — UI owed by Phase 14; spec in §9 |
| Multi-seat human control (drive k of n seats) | ◐ **engine ☑ 2026-07-30** (16.17: `SeatMap` + `DraftState.human_teams` + per-seat pick fns; `steps/mock_draft.py --seats 3,7` drives it today), **UI ☐ = 14.J**; spec in §9.5 |

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

## 9. The mock-room opponent selector (16.15)

*The "who am I drafting against" control on the mock-draft view. Not a player card — it lives on the
draft screen — but it is specced here because it is the last piece of app surface Phase 16 owes, and
because its honesty rules are the same family as §6.*

### 9.1 The contract

The UI needs **two inputs and one call**. Everything else is defaulted engine-side:

```python
n_opponents = n_teams - len(human_teams)                                 # = n_teams - 1 by default
room = make_room(mix, n_opponents=n_opponents, seed=..., fav_teams=...)   # draft/personalities.py
opponent_pick_fn = make_room_pick_fn(model, room, hype=...)               # -> simulate_draft
```

- **`mix`** — a tuple of personality names, exactly as long as there are **non-human** seats. Omit it
  for `DEFAULT_ROOM`. `make_room` raises on a wrong-length mix and on an unknown name (a typo must not
  degrade to `balanced`), so the UI can surface both as form errors rather than validating them itself.
- **`n_opponents`** — derived, never a separate control: `n_teams − (number of seats the user is
  driving)`. It is `n_teams - 1` only in the default one-human case; see §9.5, and 16.17 for the
  engine contract that makes any k legal.
- **`seed`** — shuffles seats so a personality is not confounded with a draft slot. `None` keeps the
  listed order, which is what a "name my room" power-user flow wants.
- **`fav_teams`** — attaches to the `homer` seat only; expose it as a team picker that appears when a
  homer is in the room, and hide it otherwise.

`available_personalities` in `analysis/phase16_15_mock_room.json` is the list to populate the
dropdown from — read it, don't hardcode it, so a personality added later shows up for free.

### 9.2 What to show for each seat

| Personality | One-line label for the UI |
|---|---|
| `autopilot` | Follows ADP exactly. No opinions, no reaches. |
| `balanced` | The average manager the behavioural model was fit on. |
| `upside_chaser` | Buys ceiling and story; tolerates the bust risk. |
| `safe_floor` | Buys floor and availability; avoids the bust tail. |
| `homer` | Chases the narrative — and his own team, if you name one. |
| `chalk` · `zero_rb` · `reacher` · `rookie_hawk` | Phase-11.3 library extras, available as overrides. |

**Default room** (9 seats): 2 × autopilot, 3 × balanced, and one each of upside_chaser, safe_floor,
homer, reacher. Show it as the pre-filled state, editable per seat.

**No `zero_rb` seat by default, and say why if asked:** across 3,309 eligible-redraft managers in the
Sleeper corpus only **1.7 %** draft RB-light. A strategy roughly 1 manager in 60 runs does not belong
in a typical room; it stays one override away.

### 9.3 Honesty rules (same standing as §6)

1. **Do not present the room as predictive.** The personality set is validated by *face validity and
   mechanics tests only* — no Brier gate, by decision (2026-07-23). 11.1 already owns "predicts the
   average manager"; deviating from it is the entire point of a personality, so a personality cannot
   be scored on that metric. Frame the control as **realism**, never as "this is how your league
   drafts".
2. **Never label the hype channel a prediction.** At the shipped 16.9 shock size, seat composition
   changes a seat's share of hyped players by ≤0.04 with a rank correlation of +0.07 to seat gain —
   a null (16.15). The routing mechanism is proven at larger shock sizes; the *shipped* signal is not
   big enough to move a room. If the UI ever visualizes "who chased the story", it is illustrating a
   mechanism, not reporting a measurement.
3. **Composition redistributes the story, it does not amplify it.** Per-seat `hype_gain` is
   normalized to room-mean 1, so a room full of chasers does not secretly rescale a parameter 16.9
   fitted against realized draft-slot dispersion. Any UI that lets a user "turn up the hype" is
   changing a calibrated quantity and must say so.
4. **A seat's reach ceiling bounds its own opinion, not the room's story.** If the UI shows a
   "max reach" per personality, label it accordingly — a loud enough shared story can carry a seat
   past it, by design.

### 9.4 Target surface

Same split as §7: **click-to-select seat chips** in the Streamlit MVP (14.1) — a `st.selectbox` per
seat over the personality list, plus a "shuffle seats" toggle bound to `seed` — and a proper
drag-to-assign room editor in the Next.js frontend (14.3). The engine call is identical either way.

### 9.5 Driving more than one seat (16.17 / 14.J)

*Added 2026-07-30 on user request: "users can control as many of the picks as they'd like — pick
personalities for 6/10 to automate most of it, and control the other 4/10 slots themselves."*

The selector above assigns a personality to every seat **that isn't yours**, and §9.1 assumed exactly
one of those. The generalization is one extra state per chip:

**Each of the `n_teams` seats is either `YOU` or a personality.** The chip row gains a YOU toggle; the
mix control resizes itself to `n_teams − k` where `k` is the number of YOU seats. `k = 1` is the
default and looks exactly like today; `k = 0` is a fully-simulated room to watch; `k = 4` is four teams
drafted by hand against six bots; `k = n` is a manual draft board with no engine opponents at all.

```python
seats = SeatMap.of(n_teams, human_teams={2, 6}, mix=(...))    # draft/personalities.py (16.17)
opponent_pick_fn = seats.pick_fn(model, hype=..., risk=...)   # -> simulate_draft; None at k = n
state = DraftState(..., your_team=2, human_teams=frozenset({2, 6}), seat_roles=seats.roles())
```

The engine call is the same for every `k`, which is the point of 16.17 — the UI never computes a
seat index itself. **Built 2026-07-30** and shipping exactly as sketched here; `your_team` stays the
**primary** seat (the frozen cost report, the 9.5 objective, best-ball and MCTS all read it and none
of them learn a second human exists), and `run_to_completion` takes a `dict[team, pick_fn]` so each
of your seats can be driven differently — which is also the `--auto <seat>` seam item 2 asks for.

**What the draft view must do differently at `k > 1`:**
1. **Say whose turn it is.** The clock banner names the seat (`T3 — YOU`), and the board, roster and
   starter-needs panels follow that seat rather than a fixed "your team".
2. **Offer autopick per human seat.** A user driving four teams will want to coast one of them; that
   is the same `--auto` seam the engine exposes, not a UI hack.
3. **Report each of your teams separately.** The 14.I draft grade and the cost report are per-seat.

**Two honesty rules, both inherited from 16.17 and both required to render:**
- **Your k teams are one draft, not k trials.** Each pick you make removes a player from your other
  seats' pools, so the teams are mechanically anti-correlated. Never show a combined record,
  win-rate or average grade across seats a single user drove — it reads as replication and is not.
- **The room-realism claims in §9.3 describe a fully-simulated room.** Profile distance, dispersion
  and chalk share were measured with ten *modelled* seats. A room where four seats are human is not
  the room those numbers describe; label the copy accordingly rather than restating the bars.

---

## 10. The stat dictionary (14.O) — one source of truth for what a column *means*

*(added 2026-07-30 session 8, user request: "the stats in each column of the draft board are just numbers
to those who don't know what they are, so hovering over the 'upside' or 'bust' box of the column should
show an overhead explaining the stat with examples". Build spec: `docs/BUILD_PLAN.md` §14.O.)*

The eight bars in §2 already map to frozen contracts. What has never existed is the **prose** — and it is
currently duplicated and thin: `app/views.py::_BOARD_HELP` holds one terse line per column, the CLI holds
none, `glossary.md` holds the long form, and the PLAYER-VIEW cards would have needed a third copy.

**The contract.** One table, `draft/session.py::STAT_DICT`, **data not Streamlit**, keyed by the column id:

| field | what it holds |
|---|---|
| `label` | the column header (`UPSIDE`) |
| `one_line` | the tooltip's first line — what it is, in a sentence |
| `what_it_means` | two or three sentences a first-time drafter can act on |
| `worked_example` | **a real player off the live board**, with the number and its reading |
| `how_to_read_it` | the direction (higher = ?) and the scale (z-score? probability? points?) |
| `provenance` | which frozen contract it comes from, and any limitation that changes the reading |

Served to **every** surface: the board column tooltips (slim and advanced), the 14.L room grid, these
cards, the 14.N post-draft page, and the CLI's `--help`. **A column in `BOARD_VIEW_COLS` without an entry
fails a test** — that assertion is what keeps the dictionary from rotting the first time a column is added.

**Two entries must carry their limitation in the tooltip itself, not in a doc nobody opens:**
- **`BOOM`/`BUST`** — these are the **live** pair (season − 1) and **blank means "we have never seen him
  play", not "he never busts"**. That exact misreading is what T22 exists to prevent: the frozen column
  read `fillna(0.0)` at `max(train_seasons)` = 2022, so the live board told the user that Bijan Robinson
  and Puka Nacua never boom. A tooltip that omits this re-creates the defect in prose.
- **`MEAN`/`AVAIL`** — the PROJ→MEAN gap is the *intended* availability haircut, and on a live board it is
  additionally capped by T31's `consensus_level_cap` for deep players. The honest one-liner is *"we expect
  him to play 14.4 games, not 17"* — which is what made Maye +68.5 vs Daniels −101.6 legible in the first
  place (T27).

**Style rule inherited from §5 and §6:** the tooltip explains the number, it never *argues* for a player.
Where a stat is descriptive-only or unvalidated (the Phase-16 situation bar, playoff SOS), the tooltip says
so in the same breath as the definition — not in a footnote.

---

## 11. Deferred / open

- Exact tier cutoffs (green/yellow/red percentile bands) — set at build time; likely tertiles, tunable.
- Whether the deep page shows player-vs-player **comps** — nice-to-have, later.
- Mobile/compact hover behavior (tap-to-preview before full navigate) — frontend detail, later.
