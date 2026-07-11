# SLEEPER.md — Sleeper integration reference (step 0.10 → Phase 11 / T8b)

The single place to look for everything Sleeper: the account, the public API, the identity crosswalk,
and — most importantly — **what still has to happen before a Sleeper session is worth running**. Opened
2026-07-11. See also `findings.md` (the 2026-07-09 probe + this 2026-07-11 account check),
`docs/TECH-DEBT.md` **T8b**, and `ROADMAP.md` ★ THE PIPELINE stage 3.

## Why Sleeper is in the plan
Two payoffs, both needing **real pick-by-pick draft data**:
1. **The behavioral opponent model (T8b / Phase 11).** The reframe's availability signal is "ADP + a
   *behavioral* model," not ADP+noise. Fitting it — and reporting the **availability Brier** owed from
   spine-4 (does it beat ADP+noise on real picks?) — requires observed human drafts.
2. **A 2025/2026 ADP board derived at scale.** Sleeper has **no public ADP endpoint**; ADP has to be
   *aggregated from many drafts*. A 2025 board would upgrade 2025 from a projection-calibration holdout to
   a **full draft-backtest season**.

## The account (as of 2026-07-11)
- **username:** `MadBawa` (canonical lowercase `madbawa`)
- **user_id:** `1381536159267573760`  ·  `is_bot: false`, created 2026-07-11
- **STATUS: 3 mock drafts banked & ingested (2026-07-11).** The account still shows **no leagues** and the
  mock drafts do **not** surface on `GET /user/<id>/drafts/nfl/2026` (mocks aren't attached to the user
  endpoint — the field-verified reality that step 0.10 was designed around). They are reached **by
  `draft_id`** (from the draft-board URL) instead. The three seed ids live in
  `steps/phase0_10_sleeper_ingest.py::SEED_DRAFT_IDS`.

## ✅ Step 0.10 — ingest DONE (2026-07-11); pick shape confirmed
Ran the ingest end-to-end on the 3 mocks (`steps/phase0_10_sleeper_ingest.py`, all gates PASS):
- **Format (all 3):** `complete` `snake`, **10-team × 15-round PPR**, season 2026, 150 picks each (**450**).
  Roster is QB1/RB2/WR2/TE1/**FLEX2**/K1/DEF1 = 10 starters (wider FLEX than the canonical 9-starter
  `RosterSlots`; irrelevant to pick-sequence ingest, recorded on `sleeper_drafts`).
- **Pick shape:** each pick carries `pick_no`, `round`, `draft_slot`, `player_id` (= sleeper_id), rich
  `metadata` (name/pos/team/years_exp), `is_keeper`. **`picked_by` is populated for the *human's own*
  picks only** (45 rows = 15 × 3, all `is_human_slot`); the 405 bot picks have `picked_by = null` and
  `roster_id = null`. `draft_order` = a single entry (the user) → `human_slot` (3 / 6 / 8 across the mocks).
  ⇒ **bots have no persistent identity; a mock keys behavioral stats by `draft_slot`, a real league by
  `picked_by`.**
- **Identity crosswalk (measured on the 450 picks):** QB/RB/WR/TE **100%**, K **80%**, team DEF **0%**
  (their id is the team abbr → bridged to a `dst_team` key, no gsis — matches the `_NON_GSIS_POS`
  convention). Unmatched *skill* players are logged, not dropped.
- **Deliverables:** `sleeper_drafts` + `sleeper_draft_picks` tables (idempotent upsert by `draft_id`); the
  derived `sleeper_mock` ADP board written into `adp_snapshots` (so `adp_asof(source="sleeper_mock")` and
  the draft simulator consume it **unchanged** — verified by drafting a 2026 mock against it); a POC
  `sleeper_tendencies` artifact (per-slot positional cadence + reach-vs-ADP). Module:
  `src/fantasy_quant/data/sources/sleeper.py`; tests `tests/test_sleeper.py` (offline, fixture-backed).
- **Still open (needs real-league data): the Phase-11 behavioral opponent-model fit + the availability
  Brier.** 3 solo-vs-bots mocks are weak signal with no opponent identity — plumbing + POC only. The
  ingest is corpus-ready (`ingest_drafts` takes a list of ids **or** discovers a username/league) for when
  real drafts land. See TECH-DEBT **T8b**.

## The public API (read-only, no auth)
Sleeper's v1 API is fully public — **no password, API key, or OAuth**; everything is keyed off public IDs.
The traversal we use:
```
GET https://api.sleeper.app/v1/user/<username>              -> user object (user_id, display_name)
GET https://api.sleeper.app/v1/user/<user_id>/leagues/nfl/<yr>   -> that user's leagues (league_id[])
GET https://api.sleeper.app/v1/user/<user_id>/drafts/nfl/<yr>    -> that user's drafts (draft_id[])
GET https://api.sleeper.app/v1/league/<league_id>/drafts         -> a league's draft(s)
GET https://api.sleeper.app/v1/draft/<draft_id>                  -> draft metadata (type snake/auction, slots)
GET https://api.sleeper.app/v1/draft/<draft_id>/picks            -> THE pick-by-pick list (the payload 0.10 needs)
GET https://api.sleeper.app/v1/players/nfl                       -> full player dump (sleeper_id -> metadata; crosswalk)
```
`/draft/<id>/picks` is the documented pick-by-pick endpoint; **confirming its exact shape against a real
draft is the whole job of step 0.10** (the probe couldn't verify it without a real draft).

## Identity crosswalk (solved — 2026-07-09 probe)
`sleeper_id → gsis` via nflverse `player_ids.sleeper_id` covers **99.0 %** of the draftable top-300.
Gotchas: Sleeper's *own* `gsis_id` field is ~31 % sparse (don't rely on it); `sleeper_id` is stored as a
**DOUBLE** (cast it); nflverse `gsis` is sometimes **whitespace-padded** (strip it). Full detail in
`findings.md` (2026-07-09).

## What's needed to unblock — tiered, cheapest first
1. **1–2 mock drafts (~15 min each).** Sleeper app → Draft Center → Mock Draft (solo vs. bots, or a public
   mock lobby). A completed mock yields a real `draft_id` + picks. **Enough to confirm the JSON shape and
   build + test the ingest** — the plumbing half of 0.10. After finishing, either it shows under
   `/user/<id>/drafts/nfl/<yr>` or grab the draft URL (the `draft_id` is in it) and hand it over. *Caveat:*
   bot-heavy mocks are **weak behavioral signal** — good for plumbing, not for a real opponent model.
2. **A real human league draft** — the gold standard for the behavioral model, but **seasonal**: 2026
   redrafts go **Aug–Sep 2026**, and it needs 9 other managers.
3. **A corpus of public draft_ids** — required to *derive an ADP board at scale* and fit a well-powered
   model. Not something one account provides; needs many drafts (public leagues / mock lobbies / friends'
   league IDs).

## ✅ Corpus crawler — 0.10b (2026-07-11) + a real live corpus
Built on top of 0.10 so the corpus scales without hand-collecting ids (`steps/phase0_10b_crawl.py`;
`sleeper.crawl_and_ingest`). Verified offline (fake-client tests) **and run live** — see the corpus below.
- **Seed registry** `reference/sleeper_seeds.txt` — one token/line (`#` comments): `league:<id>` = a
  league_id (from a public league URL), `draft:<id>` (or a bare number) = a draft_id, anything else = a
  **username**. Grow the corpus = add a line, re-run the step.
- **Crawl** `crawl_expand`: **iterative BFS snowball**. Seed from usernames (walk `user→leagues→drafts`
  across seasons `2018–2026`), league_ids (→ their drafts + members), and draft_ids; then **participant
  expansion** — every *human* (multi-manager) draft found queues its `draft_order` managers, whose histories
  are crawled in turn, so **one league fans out through co-managers** until no new users or `max_drafts`.
  Rate-limited, dedups against the store.
- **Human vs bot separation:** each draft tagged `is_human` (≥2 distinct `picked_by`). Real drafts build a
  **`sleeper_human`** ADP board; bots a **`sleeper_mock`** board (bot ADP never dilutes human ADP).
- **Quality filter:** a crawled corpus is full of **abandoned drafts** (people quit mid-draft) + auctions;
  derived artifacts (ADP boards, manager profiles) use **complete snake/linear drafts only**. Raw
  `sleeper_draft_picks` keeps everything. The integrity gate checks **no duplicate `pick_no`** (a real
  corruption check) — incompleteness is *reported, not failed*.
- **Behavioral seed:** `sleeper_manager_profiles` — per real manager (across all their drafts): draft count,
  per-position pick share, mean reach-vs-ADP, top NFL teams (crude fandom). The Phase-11 opponent-model input.

### Live corpus (2026-07-11) — seeded from the Sleeper docs' public example leagues
Web-searched + validated two **public** real human leagues (the official API docs' examples, `picked_by`
fully populated — this also **confirmed real-league drafts carry full opponent identity**, unlike mocks):
`league:289646328504385536` ("Sleeper Friends League", 2018 12-team) and `league:206827432160788480`
("Men Of Steel", 2017 10-team). The snowball reached a **connected component of ~266 drafts** before
exhausting: **149 human + 117 bot drafts**, seasons 2017–2020, **289 manager profiles**, `sleeper_human`
board ≈2,580 rows (per season), skill gsis-match **99.8 %**. All gates PASS. **This clears the Phase-11
*data* blocker** — a first opponent-model fit + availability Brier can now run on real human picks (older
seasons w/ realized outcomes). More/newer seeds broaden it; the fit itself is the next modeling step.

## How much data (what each source buys)
| Source | Behavioral signal? | Good | Ideal | Powers |
|---|---|---|---|---|
| Solo-vs-bot mocks | ❌ (bots) | ~10 | ~20 | `sleeper_mock` ADP only (FFC already covers production ADP) |
| **Human mock-lobby** drafts | ✅ ~10 humans each | ~20 | ~40 | behavioral model + `sleeper_human` ADP |
| Crawled public user histories | ✅ | ~50 | ~100–150 | the Brier-verifiable opponent fit |
| Your own redraft leagues | ✅ (1 draft each) | 1–3 | — | your draft day + validation |

Board mean-ADP error ≈ σ_pick/√N (mid-round σ≈15 → N=20 ⇒ ±3–4 picks). A Brier-verifiable opponent model
needs **~50 real human drafts minimum, ~100–150 ideal** — best gotten from **human mock lobbies +
participant-expansion crawling**, not from personally joining many leagues. (User plan 2026-07-11: gather via
**human mock lobbies**; crawler built now to expand from them.)

## Current recommendation (updated 2026-07-11, post-0.10)
The plumbing is built and verified; the ingest is corpus-ready. To make the derived board + opponent model
**non-trivial** (the user intends both):
1. **Batch of mocks** → grow `SEED_DRAFT_IDS` (or discover from a username). More mocks tighten the
   `sleeper_mock` ADP board; still weak behavioral signal (bots).
2. **Real human leagues** (the user plans to join several) → these populate `picked_by` = persistent
   manager identity across drafts. **This is what unlocks the Phase-11 behavioral opponent model + the
   availability Brier.** Ingest via `ingest_drafts(con, username=...)` (or league ids); a real 2026 board
   also upgrades 2025→2026 to a full draft-backtest season.

**Privacy:** ingesting a real shared league brings other managers' public handles + picks into the store
(already public via the API, but other people's data) — fine to proceed, noted for awareness.

## Privacy note
Pulling a league surfaces the *other* managers' public Sleeper handles and picks. That's already public via
the API, but it is other people's league data entering our store — worth a heads-up before ingesting a
shared league.
