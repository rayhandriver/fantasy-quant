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
- **STATUS: EMPTY** — `GET /user/madbawa/leagues/nfl/2026` → `null`, `GET /user/madbawa/drafts/nfl/2026`
  → `null`. Brand-new account, **no leagues, no drafts**. Identity resolves fine; there is simply no draft
  data behind it yet. **An empty account does not unblock the Sleeper session** (nothing to ingest/fit).

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

## Current recommendation (2026-07-11)
Because the account is empty, **do not spend the next session on Sleeper** — it stalls on missing data or
produces throwaway plumbing. Recommended autonomous next session: **T3 + T4** (the pre-lockbox modeling
pair; see TECH-DEBT) — no external dependency, and it hardens the exact distributions the Phase-9.5
win-prob objective consumes. **Return to Sleeper once real draft data exists**: either the user runs a
batch of mock drafts (plumbing now) or the real 2026 draft season arrives (Aug–Sep, gold-standard signal).

If prioritizing Sleeper anyway: the user runs **1–2 mock drafts and hands over the draft URL(s)**; then a
session can build + verify the ingest against real payloads, with the behavioral-model fit following once
there are enough drafts.

## Privacy note
Pulling a league surfaces the *other* managers' public Sleeper handles and picks. That's already public via
the API, but it is other people's league data entering our store — worth a heads-up before ingesting a
shared league.
