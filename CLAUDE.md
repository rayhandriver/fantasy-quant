# CLAUDE.md — working guide for the fantasy-quant repo

Instructions for anyone (including Claude) working in this repo. Mirrors the discipline that made the
Alphathena `intern-repo` work. **Read `docs/STRATEGY.md` (esp. its Part 0 reframe), `PROJECT.md`, and
`docs/PERSONALIZATION.md` before writing code.**

> **⟳ REFRAME (2026-07-04).** Objective is now **direct-indexing personalization**, not beating ADP:
> `docs/REFRAME-2026-07-04.md`. Value = **consensus projections → VBD**; availability = **ADP + a
> behavioral model**; variance = **our own distributions** (never one "ADP" input). **No LLM in the core.**

## 1. What this is
A quant-inspired fantasy football **personalization engine**: build each user a fully-optimized team from
their own constraints and **honestly price the cost** of each preference vs the consensus-optimal team
(the direct-indexing reframe). The honest value is **personalization + cost transparency + calibrated
projections + correlation-aware construction** — **not** out-forecasting consensus (which our own Phase-2
backtest shows is unwinnable on ~10 seasons). Team strength is a **tracked benchmark**, not the objective.

## 2. Environment & how to run
- **Package/Python manager: `uv`** with a **pinned Python 3.12** (`.python-version`). We deliberately do
  **not** use the machine's system Python 3.14 — some ML wheels (XGBoost/LightGBM/PyMC) lag on brand-new
  Python. uv downloads and manages the 3.12 toolchain itself.
- Create/refresh the env: `uv sync` (core) · `uv sync --extra data` (NFL sources) · `uv sync --extra bayes`
  (PyMC, when Phase 4 needs hierarchical priors).
- Run anything with **`uv run`** (e.g. `uv run python steps/<script>.py`, `uv run pytest`, `uv run ruff check`).
  No manual `source .venv/bin/activate` needed.
- The project installs **editable** (src layout), so `import fantasy_quant` works with no `sys.path` hack
  (an improvement over the intern-repo's bootstrap). Put reusable logic in `src/fantasy_quant/`, runnable
  phase scripts in `steps/`.
- Jupyter kernel: **"Python (fantasy-quant)"** (registered via ipykernel). Notebooks live in `notebooks/`.
- **Standing chore (Stage 0, from 2026-07-09 until the 2026 season starts):** the FFC 2026 ADP board is
  unrecoverable later, so keep the snapshot series fresh — if the latest 2026 snapshot in `adp_snapshots`
  is > 6 days old, run `uv run python steps/stage0_adp_snapshot.py` (idempotent, ~10 s). Any session
  working in this repo should check/refresh this. **After refreshing, back up the crown jewels off the WSL
  disk** (they're gitignored, single-copy): run `uv run python steps/backup_db.py` — it copies the 2026 ADP
  snapshots + 2025 backfill + a timestamped `.duckdb` to `/mnt/c/Users/rayha/fantasy-quant-backup/` and
  md5-verifies each. See `docs/TECH-DEBT.md` **T2** (done 2026-07-10).

## 3. The discipline (non-negotiable — ported from the intern project)
1. **Point-in-time (PIT) everywhere.** When building any as-of feature/projection/ranking, **no data
   dated after the as-of** may touch it. Enforce it structurally (filter at the read), not after the fact.
   This is the single easiest way to fool yourself.
2. **Walk-forward, never in-sample.** Rank methods on **realized out-of-sample** outcomes (backtest over
   past seasons), not on in-sample fit. Report effect size **+ bootstrap CIs**, not a single season.
3. **Calibration > edge (⟳ reframed 2026-07-04).** The bar is **well-calibrated**, not ADP-beating:
   value projections pass reliability/coverage checks; availability beats ADP+noise on **Brier** over real
   picks; the cost report leads with robust **relative** numbers. *(Old rule — "beat ADP + the betting
   market" — is retired: our own Phase-2 backtest shows an 80-PAR edge is unresolvable on ~10 seasons, so
   we stop fighting that fight. "Beat ADP" is an optional curiosity.)* Value = **consensus projections →
   VBD**; don't rebuild a beat-the-market projection.
4. **Reuse before you write.** Search `src/fantasy_quant/` first; don't rebuild a primitive.
5. **Guard every output.** Projections/rankings pass sanity gates (no impossible values, plausible ranges,
   calibrated intervals) — the analog of the intern repo's covariance hard gate.
6. **Document as you go.** Decisions + dead ends → `PLAN.md`; what each step produced/taught → `findings.md`;
   new terms → `glossary.md` (keep it current — see the memory note on glossary maintenance).
7. **Sub-phase gate — STOP between every sub-step.** After finishing each numbered sub-step (0.2, 0.3, …,
   1.1, …) deliver a short overview of what was accomplished and **explicitly ask the user for permission
   before starting the next sub-step.** Never chain sub-steps without that approval. This applies across the
   **entire** project, every phase. (User instruction, 2026-06-30.)

> **Known problems & their exact fixes live in `docs/TECH-DEBT.md` (register T1–T9, opened 2026-07-10).**
> **T3 (coverage) + T4 (sim level bias) are ☑ done (2026-07-11).** Remaining hard gate before the lockbox
> eval: **T5** pre-registration (freeze the stack — incl. the T3/T4 params — and report metrics once).

> **★★★ Next-session pointer (2026-07-30, session 4 — T31 ☑ + SESSION I ☑. READ THIS FIRST.)**
>
> **State: 658 tests, ruff clean. Two commits this session, both LOCAL (not pushed).** T31 is
> `496836f`; Session I sits on top. The spent lockbox and the frozen value stack are untouched: T31
> changed only live-consensus boards (2022/23/24/**25** byte-identical) and Phase 17 is a config
> generalization whose default path is asserted unmoved (gate G3).
>
> **★ SESSION I ☑ — Phase 17 League-Format Fidelity (17.1–17.4).** All five gates PASS
> (`steps/phase17_formats.py`, `analysis/phase17_formats.json`); +41 tests in `tests/test_phase17.py`.
> Write-up: `findings.md` §"Session I", `PLAN.md` §2026-07-30 (session 4, cont.), `glossary.md`.
>
> | | |
> |---|---|
> | **17.1** | `RosterSlots.flex_groups()` is now the **single** fill-order rule — three solvers had each re-derived it. Multi-flex/superflex stays vectorized via **the carry** (sort a group's pool, take its top *n*, pass the unused tail to the next wider group). **Non-nested eligibility is REFUSED** (`assert_nested`), not approximated. |
> | **17.1 replacement** | **The superflex replacement level was quietly wrong**: the old proportional rule gave QB **1/6** of the slot. A superflex admits only QB beyond the base flex → **QB10 → QB20**; nothing else moves. Live 2026: best QB overall rank **15 → 3**. |
> | **17.2** | `SCORING_PRESETS` + `ruleset_from_preset` + `te_rec_bonus` + yardage-milestone bonuses. |
> | **17.3** | `LeagueSettings` (platform-agnostic; **not** Sleeper auto-import) + `lockbox_validated()`. Bracket now **4/6/8 with derived byes** — a 12-team/8-playoff league was previously unconstructible. Odd `n_teams` refused with a reason. |
> | **17.4** | Round-based keepers. `apply_keepers` + `DraftState.skipped_picks`: 147 picks, not 150. |
>
> **⚠ Do not re-derive / do not "fix":**
> - **Never add a third lineup solver, and never check one against another.** Both consume
>   `flex_groups()`, so agreement between them tests the plumbing. The gate is an **exhaustive brute
>   force** (worst abs error 0.0). *Two greedies that share a bug agree perfectly.*
> - **Keepers have no "ADP adjustment" and must not gain one** — ADP is a rank on the remaining
>   board, so removing the kept player *is* the re-inflation; a separate shift double-counts.
> - `ruleset_from_preset("full_ppr")` returns `RuleSet()` **itself**, name included, because
>   `RuleSet` is serialized into `cached_distribution`'s cache key — a cosmetic name difference
>   would split the cache and force a silent nine-season rebuild.
> - `OffenseRules` and friends are `extra="forbid"` (`_Rules`). That is the whole argument for a
>   bounded field set over an open `{stat: value}` map; the first implementation lacked it and
>   silently accepted `rec_typo=1.0`.
> - `starter_marginal` **routes multi-flex to the exact solver** rather than approximating with its
>   one-flex closed form. Leave it routing.
> - **`lockbox_validated()` is an honesty method, not a feature flag.** Non-default formats are
>   supported and correctness-tested and carry **no** out-of-sample claim. Phase 14 must render that.
>
> **★ NEXT: Session I.5 = 16.17 the seat map** (multi-seat human control), the scoping for which is
> immediately below and unchanged. Its hard done-bar is **bit-identity** at k=1 and k=0 plus
> `analysis/mock_room_bars_verify_20260729.json` to the digit — note that sheet must be reproduced
> with **`--shuffle-room`**, which is how it was generated; without the flag it differs on 149
> gate-side fields and looks like a regression that is not one.
>
> _(T31's entry, still the authority on the level cap, follows.)_
>
> **★★★ Next-session pointer (2026-07-30, session 4 — T31 ☑ DONE. READ THIS FIRST.)**
>
> **Running order agreed with the user for this stretch: T31 → Session I (Phase 17) → hard stop →
> Session I.5 (16.17).** §3.7 gates waived *within* T31 and Session I; one commit per session, **not
> pushed**. Ten scope decisions were taken up front and are recorded in `PLAN.md` §2026-07-30
> (session 4) — 17.1 **nested-eligibility flex only** (non-nested refused at `LeagueSettings`),
> bracket **4/6/8 with derived byes** and **odd `n_teams` rejected**, 17.2 **presets + a bounded knob
> set** (not an open stat map), 17.4 **round-based keepers only**.
>
> **T31 ☑ — and the register's filed cause was WRONG, the third in a row after T13 and T24.** There
> is no live-vs-historical branch in the level fit: `train_seasons` is 2014–2022 for a **2024** board
> *and* a 2026 one, so the QuantReg models are **identical** and the defect was entirely in the
> **board**. Measured cause = **linear extrapolation far below the support of the fit** (median 2026
> QB `calibrated_mean` **11.4** vs a training *minimum* of 34.1; **56.4 %** of 2026 QBs below support
> against **2.3 %** on 2024), with the low end *additionally* selection-biased upward because the fit
> trains on `weeks >= 0.85*season`. Fixed by `quantile.consensus_level_cap` + four lines in
> `distribution.assemble_distribution`, gated on **`value_board.source`** (already a frozen 4.2
> contract column). **All six pre-registered bars PASS**: negative-haircut share **38.75 % → 0.00 %**,
> drafted-range rho **RB −0.288 → −0.666**, full-board **QB +0.474 → −0.980**, max `sd/proj`
> **23.06 → 0.90**, 2022/23/24/**25 bit-identical**, T17 band held (top-60 moved 0.078 %).
>
> **⚠ Do not re-derive / do not "fix":** the target is `proj_points * avail_p / g_ref`, **not** a bare
> cap at `proj_points` — the bare cap was built first, moved B1 to 8.1 % and pushed **full-board QB
> spearman the wrong way (+0.474 → +0.523)** by parking every capped row at `haircut == 0`. *Cap to
> the identity, not to the boundary.* · The scale is applied to `samples`, not to the quantile band ·
> `games` is deliberately unscaled · non-live rows multiply by **exactly 1.0**, which is what makes
> the bit-identity bar hold by construction · **the 2025 calibration holdout was authorised for one
> more read and then NOT spent** — the source gate leaves it bit-identical, verified by hash.
>
> **⚠ Method warning that outlives the ticket — a control that cannot fail.** The B5 before/after ran
> **post-fix code twice**: `uv run --project <main>` from a `git worktree` resolves the **editable**
> install to the *main* tree's `src`, and on the retry a persistent `cd` sent the working-tree run
> into the worktree. Both produced *identical hashes* — indistinguishable from "nothing moved".
> Use `PYTHONPATH=<worktree>/src`, and **assert the control can produce a known difference before
> trusting it to show none**. See `steps/t31_level_cap.py`'s docstring.
>
> **`ENRICH_VERSION` → `v4-t31-level-cap`**, so all nine 16.13 board caches rebuild (~35 min).
> Artifacts: `analysis/t31_level_cap.json`, `analysis/t31_hashes_{before,after}.json`. New steps:
> `t31_level_cap.py`, `t31_hash_distributions.py`, `t31_dump_summary.py`. Write-ups: `findings.md`
> §"T31", `docs/TECH-DEBT.md` T31 (☑), `PLAN.md`, `glossary.md`.
>
> **★ NEXT: Session I = Phase 17 formats**, then a hard stop, then Session I.5 = 16.17.

> **★ Scoped 2026-07-30 (session 3, docs-only — no code, nothing run): 16.17 multi-seat human control.**
> User asked for the finished mock drafter to let a user **drive as many seats as they like** (e.g. 6
> personalities + 4 teams drafted by hand). **It was in none of the md files, and the gap is structural:**
> `DraftState.your_team` is a single int and the `team → seat` map is positional arithmetic repeated in
> three places (`personalities.make_room_pick_fn`, `mock.full_room_pick_fn`, `steps/mock_draft.py::seat_of`),
> correct only at k=1 — so the engine supports exactly two room shapes, 1-human and 0-human. Scoped as
> **16.17** (engine: a `SeatMap` + `DraftState.human_teams` + per-seat pick fns + `--seats` CLI;
> **done-bar = bit-identity** at k=1 and k=0 plus the 07-29 bar sheet to the digit) and **14.J** (UI: a
> YOU toggle per seat chip, clock routing, per-seat 14.I grade). Slotted as **Session I.5**, after Phase
> 17, **pullable into Session I as a warm-up** — it depends on nothing in Phase 17 and refits nothing.
> Spec: `docs/BUILD_PLAN.md` §16.17/§14.J · `docs/PLAYER-VIEW.md` §9.5 (and §9.1's `n_opponents`
> contract, which was wrong as written) · `ROADMAP.md` ★ SESSION PLAN · `PROJECT.md` §5 · `PLAN.md`
> §2026-07-30 (session 3) · `glossary.md`. **Two honesty rules travel with it:** k human teams in one
> draft are **one** observation (their picks deplete each other's pools — never aggregate a record
> across them), and the T15 realism bars describe a **fully-simulated** room.

> **★★★ Next-session pointer (2026-07-30, session 2 — SESSION H.5 COMPLETE. T27/T28/T29/T30 all ☑,
> **T31 opened**. 612 tests, ruff clean, UNCOMMITTED. READ THIS FIRST.)**
>
> **State:** **612 tests** (was 597), ruff clean. The spent lockbox, the frozen value stack and the
> fitted β are untouched — nothing here refits anything, and both bit-identity bars hold: the room bar
> sheet reproduces `analysis/mock_room_bars_verify_20260729.json` on **every field**, and the frozen
> cost report was diffed against a **`git worktree` at the session-start commit**. Artifacts:
> `analysis/session_h5_seam.json` (the six bars), `analysis/t28_starter_value.{json,csv}`,
> `analysis/mock_room_bars_{h5_baseline,h5_step1,t30_chalk_swap,t28_benchw0}.json`. New steps:
> `steps/t28_starter_value.py`, `steps/session_h5_seam.py`. Write-ups: `findings.md` §"Session H.5",
> `docs/TECH-DEBT.md` (T27–T30 ☑ + **T31**), `PLAN.md` §2026-07-30 (session 2), `glossary.md`, `ROADMAP.md`.
>
> **The shape of the session: the two hard bars held and both falsifiable bars failed.**
>
> | | outcome |
> |---|---|
> | **T27** ☑ | The value chain is on the board (`PROJ · MEAN · AVAIL · BV`) and `mock_draft.py why "<player>"` prints it — Maye +68.5 vs Daniels −101.6 explained by **14.4 games against 7.7**. ⚠ **It also uncovered that the *interactive* room was never the shipped room**: `personalities.make_room_pick_fn` had no `risk` parameter, so `value_hawk` ran the Phase-9 greedy in every batch measurement and the plain behavioural softmax in every *human* mock. `assert_room_objectives` moved down into `personalities.py` so both builders share it. |
> | **T28** ☑ | **Closed as a LABELLING FIX, as pre-registered.** `starter_value` ships beside `team_value`, both printed. **B5 failed**: −0.0230, CI[−0.0407, −0.0055] over 200 seated-reshuffled drafts. The slot-blind sum is the *better* predictor of title probability because the sim draws injuries — **bench value alone scores +0.711, positive in 100 % of drafts**, and the blend sweep peaks at w=0.90 against the shipped w=1.0. `value_hawk` keeps `objective="portfolio_ce"`. |
> | **T29** ☑ | `PROB_PROVENANCE` + `fair_share`/`playoff_fair_share` + `assert_probability_sums`; every driver leads with the multiple (0.170 → **1.70×**). New surface: `mock_draft.py summary --odds`. |
> | **T30** ☑ | **Argued and deliberately NOT changed.** The `chalk` swap closes **79 %** of the chalk-share gap (11.0 → 2.4 % vs a realized 0.2 %) and regresses two reach bars slightly; the rule ("every bar holds or improves") was fixed first, so it does not ship. **The closest call in the session** — reversal is one `--room` flag and the evidence is written down. |
> | **T31** 🟠 NEW | T27's gate B2 fired: on a **live** board the level correction inverts for players consensus projects as backups — **22.8 % of the 2026 value index has `mean` ABOVE `proj_points`** (0.4 % on 2024). Cause: **consensus prices ROLE, our correction prices AVAILABILITY**; they agree for starters and diverge for backups, and a live season has no prior year to shrink the per-game level toward. The gate ships **red** rather than softened. |
>
> **⚠ Do not re-derive / do not "fix":** `value_hawk`'s objective is **settled by measurement** — do not
> switch it to starter-aware without re-running `steps/t28_starter_value.py` and beating B5 · the
> `bench_weight` knob is in `RiskModel`, default **1.0**, and 1.0 re-runs the greedy pick-for-pick
> (`test_phase9`) · `mean`/`vbd`/`overall_rank` stay in `SIGNAL_COLS` (it is also the typo registry) but
> `personalities.LEVEL_COLS` + `Personality.__post_init__` now make weighting one raise · the T30 swap
> is a *composition* question, never delete the `autopilot` personality (it is the deterministic control
> several tests depend on).
>
> **★ NEXT: review + commit (this session sits on top of the still-uncommitted docs tree), then
> Session I = Phase 17 formats.** Against the mock drafter only **T31** is open, and it needs its own
> session with a before/after against the 2025 dress-rehearsal calibration. **T26** still waits on the
> next 11.1 refit. Stage-0 FFC chore was run at the **close** of this session (deliberately not the
> start — a mid-session board refresh would have broken the live-board measurements).
>
> _(Prior pointer — the H.5 scoping session, still the authority on why these four tickets exist.)_
>
> **★★★ (2026-07-30 — SESSION H.5 SCOPED, docs-only; T27/T28/T29/T30 opened.)**
>
> **State:** **docs-only, no `src/` change, no test-count change (597, ruff clean).** The lockbox, the
> frozen value stack and the fitted β are untouched. New artifacts: the walkthrough itself at
> `analysis/mock_walkthrough_20260729_{picks,teams,seats}.csv` (untracked). Write-ups: `findings.md`
> §"The all-personality walkthrough (2026-07-30)", `docs/TECH-DEBT.md` **T27–T30** + ordering item 11,
> **`docs/BUILD_PLAN.md` §"Session H.5 — THE MOCK-DRAFTER VALUE SEAM" (the plan of record)**,
> `ROADMAP.md` ★ SESSION PLAN, `PLAN.md` §2026-07-30, `glossary.md`.
>
> **What happened.** The user asked for a full 15-round mock with **all ten seats played by
> personalities** (`REALISTIC_ROOM`, `room_seed=17`, `seed=0`, live 2026 board) and then for an
> assessment of the mock drafter **as a shippable product**. The room *simulation* passed every bar it
> was asked — see below — and the failures are all in the **seam between a correct engine and a human
> reading it**. User instruction: **fix the mock-drafting system before any other session; the app
> stays strictly last.** So Session H.5 is inserted ahead of Session I; E→L order is otherwise unchanged.
>
> | | ticket | the number that opened it |
> |---|---|---|
> | **T27** 🟠 | the board a human reads ≠ the board the seats optimize | CLI prints `proj_points`; seats optimize `base_value`. **Drake Maye proj 316.5 → +68.5, Jayden Daniels proj 313.4 → −101.6** — 3 points apart on screen, 170 apart in the number that decides every pick |
> | **T28** 🟠 | `team_value`/`portfolio_value` are **slot-blind** | no slot logic in the value path at all; the walkthrough's QB2 line nets **−122** of a 1,938 room total, and **T4 is 9th of 10 on VBD, 3rd on starting-lineup projection**. Spearman vs title: portfolio CE **+0.758** vs starting-nine Phase-5 mean **+0.915** |
> | **T29** 🟡 | bare absolute probabilities | printed from a sim with a documented **−113 pts/team** level bias and a *marginal* playoff Brier 0.240 (title 0.088 is fine) |
> | **T30** 🟡 | `autopilot` is 1 of 10 seats vs **0.2 %** of real seats | and it is the seat that manufactures the spill: mean `pool_rank` **1.77**, median **1.0**, harvest **+11.7 picks** |
>
> **★★ THE FINDING TO CARRY FORWARD — T22's lesson one level up, on the first number a human reads.**
> T22 sat on file as "latent, no personality weights it" while `steps/mock_draft.py` was *printing* it.
> `proj_points` is the identical defect on a much bigger number. *A column's consumers are not only the
> models that weight it.* Its mechanical half bit immediately: `proj_points` is **not** in
> `simulator.PASSTHROUGH_COLS`, so `_prepare_board` drops it and a **fresh driver written this session
> printed `-` for all 150 picks**. `mock_draft.cmd_start` already re-attaches it by hand — the fix is to
> make the attach unnecessary, not to repair the CLI.
>
> **★ Two more, each one line.** **(1) Decompose before diagnosing** — `base_value` differs from `vbd`
> through *two* channels (the T3 availability haircut inside the Phase-5 mean, then λ·Var, then
> subtracting the replacement's own CE, 119.4 for QB here). The one-channel reading "λ is too big" fits
> neither end: Allen +70.0 → +55.2 while Daniels +22.6 → −101.6. **(2) The level is intended, the
> dispersion is the defect** — the mean haircut (0.28 QB / 0.33 RB / 0.28 WR / 0.30 TE) *is* Phase 4.4's
> calibrated level correction; the spread around it (QB 0.15–0.56) with nothing on screen explaining it
> is what makes the board unreadable.
>
> **★ What the walkthrough CLEARED, and do not re-open** — four suspicions that died on contact with
> the corpus, each in one query: **the QB market is fine** (17 QBs for 10 teams against a realized
> **median of 16** over 333 matched 10-team/15-round human drafts; the full mix matches at the median on
> all six positions) · **the fit is not stale** (70,614 groups over **9 seasons**, bulk 2021–25, not a
> 2017–20 extrapolation) · **elite fall is on distribution** (25.0 % past pick 10 vs a committed 25.2 %)
> · **the reach budget works exactly as specified** (`reacher` spent 3 of 3 swings and 5 of 5 leans with
> a rounds-1–3 max reach of **−0.1**; `upside_chaser`, which has no early clamp, reached +11.3 in round
> 2). *An audit's value is in what it clears.*
>
> **⚠ Constraints on H.5, all pre-registered in `BUILD_PLAN.md` before anything runs:** every step's
> hard bar is that `analysis/mock_room_bars_verify_20260729.json` reproduces **bit-identically** — *a
> display change that moves a bar is not a display change* · **nothing refits β** and **nothing touches
> the frozen value stack**; T26 stays deferred to the next 11.1 refit · **T28 ships a labelled second
> metric, never an edit to `team_value`** (the cost report is frozen output, the lockbox is spent) ·
> **§3.7 gates are NOT waived** (contrast 16.14R) — step 2 contains a decision that is the user's:
> whether `value_hawk` keeps `objective="portfolio_ce"`, which changes the room's picks and therefore
> needs the full T24 seating-marginalized treatment as its own sub-step · **B2 and B5 can fail
> informatively** — if the level haircut is not explained by `games_played_mean` that is a *modelling*
> finding (stop, open a ticket, do not caption it), and if starter-aware value does not out-rank
> portfolio CE against title probability over ≥40 drafts × ≥4 seasons then **T28 closes as a labelling
> fix only**.
>
> **★ NEXT: Session H.5, steps 1→5, gate after each** (`docs/BUILD_PLAN.md` §"Session H.5"). Then
> Session I = Phase 17 formats → J (optional dynasty) → **K = Phase 14.1 MVP + surfacing, strictly
> last**. **Stage-0 FFC chore: the board used here is the 2026-07-24 snapshot and is now at the 6-day
> mark — run `steps/stage0_adp_snapshot.py` then `steps/backup_db.py` at the top of H.5.** Also still
> owed: review + commit sessions 6, 7 and 2026-07-29 (one tree) plus these docs.
>
> _(Prior pointer — the 2026-07-29 completion audit, still the authority on T13/T18/T22.)_
>
> **★★★ (2026-07-29 — THE MOCK DRAFTER IS COMPLETE. T13 + T18 + T22 ☑,
> T26 opened. NOT COMMITTED — sessions 6, 7 and this one are one tree.)**
>
> **State:** **597 tests** (was 587), ruff clean. The lockbox, the frozen value stack and the fitted
> β are untouched — nothing here refits anything. New artifacts:
> `analysis/mock_room_bars_verify_20260729.json` (the shipped room re-measured) and
> `analysis/t13_reproducibility.json`. New step `steps/t13_reproducibility.py`. Write-ups:
> `findings.md` §"The mock-drafter completion audit (2026-07-29)", `docs/TECH-DEBT.md`
> T13/T18/T22 ☑ + **T26**, `PLAN.md` §2026-07-29, `glossary.md`.
>
> **The mock-draft arc was already done** — T15 steps 0–4, 16.14R's seven steps, T23/T25/T24 — and
> re-measuring it confirmed that: all five T15 bars, the landing gate and the legality report come
> back **unchanged to the digit** (distance 0.0894, round-1 2.64, elite past-10 25.24 %, dispersion
> −11.4 %, top-band past-pick-4 15.3 % vs a realized 13.1 %). ⚠ The register's at-a-glance table had
> been carrying **T15 as open** while its own section was ☑ since 07-27; that row is corrected. What
> was genuinely unfinished were the three entries *behind* the room, each of which reaches the board
> a human drafts from:
>
> | | was on file as | what it actually was |
> |---|---|---|
> | **T22** | "latent — no personality weights it" | **already on screen**: `steps/mock_draft.py` prints BOOM/BUST, so the live 2026 board told the user Bijan Robinson and Puka Nacua *never boom* (0.000 — neither played in 2022, where `max(train_seasons)` lands). Fixed read-only in the enrichment: `boom_prob_live`/`bust_prob_live` from season − 1, `NaN` where unseen, `volatility_source` asserting ≤ 1 season of lag. Exact-zero `bust_prob` **56.0 % → 8.2 %**; **corr(frozen, live) = 0.026** |
> | **T13** | "prime suspect: the Iman–Conover coupling" | **DuckDB's parallel float aggregation.** Row order, `PYTHONHASHSEED` and BLAS threads were all ruled out first; pinning DuckDB to one thread makes the cloud **bit-identical** across processes. `db.deterministic_reads`; cost **negative** (10.2 s → 9.1 s) |
> | **T18** | "+91.9-pick mean QB reach — a board mismatch" | correct, and worse than stated: fixing the reference **reverses the sign** (QBs go −0.58 rounds *later*). Column deleted, not repaired: `avg_reach_rounds` + `n_reach_picks` from `redraft_reach`, mean \|reach\| **35.8 picks → 0.776 rounds**, ±2-round health gate |
>
> **★★ The three carry-forward lessons** (all in `glossary.md`): **(1) a column's consumers are not
> only the models that weight it** — T22 was audited by grepping `signal_weights` and the display
> layer was never looked at. **(2) The noisy stage is not always the stochastic one** — every T13
> hypothesis on file involved randomness; the cause was arithmetic in a database, and the
> prescription on file (*thread a seed through the coupling*) would have been built, tested, and
> would not have worked. **(3) When the sign flips, it was never a behaviour** — T18's magnitude
> falling was suggestive; its *direction reversing* is what proved the old number was a different
> quantity wearing a behaviour's name.
>
> **⚠ Do not re-derive / do not "fix":** the coupling is **not** T13's cause, whatever the
> "marginals invariant, assignment moves" fingerprint suggests · **T26** (`pos_share_*` pooled across
> formats, read by `mgr_lean`) is **measured and deliberately deferred** — fixing it refits β and
> moves every T15/T24 width bar for a 0.83 pp feature shift; do it with the next 11.1 refit ·
> `build_tendencies`'s `avg_reach` keeps the T18 defect by design (labelled POC; use `redraft_reach`)
> · `app/streamlit_app.py`'s season selector is DEV-only — Phase-14 work, noted not fixed.
>
> **★ NEXT: review + commit (sessions 6 + 7 + this one, one tree), then Session I = Phase 17
> formats.** No register entry is open against the mock drafter. **Stage-0 FFC chore: last pulled
> 2026-07-24, DUE after 07-30** — run `steps/stage0_adp_snapshot.py` then `steps/backup_db.py`.
>
> _(Prior pointer — session 7, T23/T25/T24 as they were built.)_
>
> **★★★ (2026-07-28 session 7 — T23 + T25 + T24 all ☑ BUILT. The mock room is
> fixed; T24's own prescription was rejected on the way.)**
>
> **State:** 596 tests (was 577), ruff clean, **UNCOMMITTED** together with sessions 6's docs. DEV-only;
> the spent lockbox and the frozen value stack are untouched (`draft/availability.py` imports nothing
> from `personalities`, so the 11.2 Brier is **bit-identical**: +0.0890, CI [+0.0803, +0.0996]).
> Artifacts: `analysis/mock_room_bars_{baseline,t23,t25,t24,baseline_shuffled,t24_shuffled}.json`
> (+ the rejected `t24_kappa2{,_shuffled}`) and `analysis/mock_t24_sweep{,_rep,_full,_shuffled,
> _shuffled2,_shuffled3}.json`. Write-ups: `findings.md` §"T23 / T25 / T24 (2026-07-28, session 7)",
> `docs/TECH-DEBT.md` T23/T24/T25 (all ☑), `PLAN.md` §2026-07-28 (session 7), `glossary.md`.
>
> | | result |
> |---|---|
> | **T23** | `mandatory_needs` = `base_demand()`. Seats unable to fill a dedicated slot **23.2 % → 12.3 %**; the *avoidable* half **12.08 % → 0.03 %**. No T15 bar moved (verified). |
> | **T25** | `ROOM_CEILING` — `reach_budget=None` now means *inherit*. `balanced` R1–3 `pool_rank` 6.36 → 5.98; median `pool_rank` 9.31 → **8.85** (corpus 7.62); moderate share 28.8 → **32.7 %**. |
> | **T24** | Elite (ADP ≤ 2.5) past pick 4 **25.8 % → 15.3 %** (realized 13.1 %); bar 2 p95/past-10 17.0/28.8 % → **16.0/25.2 %**; bar 1 distance 0.107 → **0.089**; median `pool_rank` 8.69 → **8.04** (corpus 7.62); moderate share 33.7 → **38.2 %**. Cost: bar 5 dispersion −7.1 → **−11.4 %**. All five T15 bars + the new landing gate PASS. |
>
> **★★ THE FINDING — T24's prescription was built and REJECTED; the fix was the knob added to
> support it.** The per-seat `adp_stdev`-scaled **private board** is *monotonically harmful* on the
> objection it was designed for (18.8 / 19.7 / **26.6 %** at κ = 0/1/2). **At the top of the board
> `adp_stdev` (0.7–2.5) is the same size as the gaps it perturbs (~0.2 picks), so the draw destroys
> the ordering that was already there** — which is exactly how an elite falls. The corpus law behind
> the idea (`|drift| ≈ 2 × adp_stdev`) is about **realized** drift, an outcome of ten seats
> interacting; re-injecting it as a **per-seat perception** is a different object. *A relationship
> measured on outcomes is not a specification for the mechanism that produced them.* Kept in code,
> **default-off**, verdict written onto `analysis/phase11_opponent_model.json` next to κ. **What
> worked: `WidthCurve` gained `base`**, splitting the width *level* from the *shape*
> (`width = base·round^gamma`); `base 1.0·γ0.8 → 0.6·γ1.0` halves round 1 while keeping 86 % of the
> round-15 width. **Round 1 was simply too wide — the ticket had the right symptom and the wrong cause.**
>
> **★ Three method failures, in the order they were caught — each by the next measurement:**
> (1) **calibrated on a 4-season subsample** and shipped off it; the 8-season sweep failed that config
> (20.4 % vs an 18.1 % ceiling). (2) **Measured on one fixed seating**, which flatters by 5–7 pp
> (`0.5/1.0/2.0`: 16.2 % fixed vs **23.4 %** marginalized) — and ⚠ **more seeds do not fix it**, the
> seating error is a *bias* until the seating is redrawn (`--shuffle-room`). (3) **Moved two knobs
> together**, so the narrowing wore the private board's credit for three runs; the isolating row
> (`base 0.7, κ 0`) was in no grid and is what decided the ticket.
>
> **⚠ Do not re-derive:** the private board is **not a null, it is harmful** — do not switch κ on
> without re-running the seating-marginalized sweep · `ceiling_saturation` was a **wrong** hypothesis
> (1.5–2.3 % at every κ; the diagnostic is kept as a standing check) · the **round-1 half-split is
> unresolvable** at this n (0.54 / 0.82 / 1.11 / 1.22 for the same room) — use the landing **share**
> (n ≈ 640) as the bar, the rise as a diagnostic · `base` below 0.5 fails bar 5 (`0.35/1.1`: 9.4 %
> past-4 but **−20.3 %** dispersion) · **`base 0.5` was shipped and then withdrawn** — it passes the
> same gates but overshoots to *tighter than real humans* (11.3 % past-4) at 0.154 distance and
> −17.4 % dispersion; the un-sampled midpoint 0.6 beats it on every secondary. **A sweep whose winner
> sits at the edge of the grid has not finished.** The residual cost at 0.6 is dispersion −7.1 % →
> **−11.4 %** — that is the trade, do not tune it away without re-measuring.
>
> **★ NEXT: review + commit (sessions 6 + 7 in one tree), then Session I = Phase 17 formats.** The
> residual elite-fall gap (15.3 % vs 13.1 %) is closed; if it is ever reopened, the surgical fix is a
> steeper `AdpSpec.exponent` with `base`/`gamma` restoring depth width — which **refits β**
> (`steps/t15_1_respecify.py`), not an artifact edit. Stage-0 FFC chore last pulled **2026-07-24**
> (verified in-DB), next due after 07-30.
>
> _(Prior pointer — session 6, the three objections as they were opened.)_
>
> **★★★ (2026-07-28 session 6 — the 2×5 mock re-run. T23/T24/T25 opened,
> NOTHING BUILT, at the rule-7 gate.)**
>
> **State:** **docs-only, no `src/` change.** One new read-only driver, `steps/mock_2x5_diag.py`
> (ruff clean, untracked); five docs edited. **16.14R and everything before it is committed at
> `7c13402`** — the prior pointer's "NOT COMMITTED" was stale, the tree was clean on arrival.
> Writeups: `findings.md` §"The 2×5 mock re-run (2026-07-28)", `docs/TECH-DEBT.md` **T23/T24/T25**,
> `PLAN.md` §2026-07-28 (session 6), `glossary.md`. DEV-only; nothing written to `analysis/`.
>
> **What happened.** The 2×5 room re-run with the *shipped* `value_hawk` — one showcased draft (room
> seed 20260728, draft seed 728) plus **40 seeded drafts, room reshuffled per seed**. The user read
> the picks by eye and raised **three** objections. All three hold.
>
> | | ticket | what it is | cost |
> |---|---|---|---|
> | 1 | **🔴 T23** | `mandatory_needs` drops TE because TE ∈ `flex_positions` → **12.2 % of seats finish with no TE** (46 % of `autopilot`). Bug against a stated contract. | ~5 lines |
> | 2 | **🟡 T25** | `ReachBudget` is on 2 of 10 seat types, so the round ceiling binds `reacher`/`value_hawk` and **not `balanced`** (4 of 10 seats in `REALISTIC_ROOM`). | small |
> | 3 | **🟠 T24** | Width is per-**round**, never per-**player**; the board's `adp_stdev` is **unread in the pick path**. Consensus #2 lands at a **median pick of 4**. | a full sub-step |
>
> **★ RESUME HERE: the user was asked to choose 1→2 first, or straight at 3. No answer yet.** T23 and
> T25 are contained and re-measurable in one pass; T24 moves T15 bars 1/2/5 and the seat-faithfulness
> population, so it needs its own gated sub-step with a before/after on the shipped measurement path.
>
> **★★ THE FINDING TO CARRY FORWARD — an aggregate that pools reaches and falls cannot see a
> one-sided defect.** Round-1 mean |reach| is **2.91 sim vs 2.87 corpus** — the bar **passes** —
> while Gibbs (ADP 1.8) lands at a **median pick of 4** and clears pick 4 **42 %** of the time against
> a realized **12 %**. A reach and a fall have the same absolute value and cancel inside the mean.
> This is T15's *"an aggregate metric cannot see an impossible event"* one level down: there the
> aggregation was over **drafts**, here it is over **direction**, inside a metric that already passes.
> **Bars over |drift| need a signed companion — here, a landing-spot distribution for the consensus
> top tier.**
>
> **★ The mechanism T24 proposes, and why it is ONE object for THREE open problems.** A **per-seat
> private board**, `adp_seat = adp + κ_seat · adp_stdev · ε`, drawn once per seat per draft. Measured
> basis, on 1,144 corpus drafts: **|drift| ≈ 2 × adp_stdev** (stable through the usable range; the
> decay above stdev 12 is pool exhaustion, T15's own finding arriving independently);
> Spearman(`adp_stdev`, |drift|) **0.484** vs Spearman(round, |drift|) **0.535**; and **within rounds
> 1–3 the stdev terciles drift 2.11 / 3.33 / 8.91** — a 4.2× spread no round-indexed curve can
> express. It buys (a) round-1 tier structure without hard-coding a tier, (b) **the T15 carry-forward
> verbatim** — *"needs per-seat board perturbation, not another width parameter"* (plausible,
> **untested**), (c) the only direction channel that is **live in round 1** for `reacher`.
> ⚠ **`adp_stdev` is on the board and nothing in `draft/` reads it** — `stdev` appears only at
> `mock.py:301`, copied onto the *output* panel. 16.8 already measured it as a drift driver
> (+0.35/SD). *The finding existed in this repo and was never fed back into the room.*
>
> **★ Second lesson — a bar written from the symptom passes the general defect.** T20's done-bar was
> *"60/60 seats finish with ≥1 K and ≥1 DST"*, the two positions the ticket was about. It passed while
> the same deadline filter left **TE** unguarded. State a guarantee's bar against the whole contract.
>
> **⚠ Do not re-derive these dead ends:** the `reacher`'s rounds-1–3 quiet is **the user's own
> 2026-07-27 spec** (`early_rounds=3`, `early_max_picks=8.0`, `large_from_round=5`) and is **not** to
> be "fixed" — the defect is that `balanced` has no equivalent constraint (T25) · do **not** raise the
> reacher's `temperature`/`width_mult` early (its `cos`/`rookie`/`upside`/hype channels are
> structurally dead at the top of the board — that is the *"width with no direction"* 16.14R step 5
> deleted) · do **not** narrow round 1 with another global width parameter (one knob cannot set both
> ends; the round-1 problem is *within-round* heterogeneity) · do **not** read a behavioural ordering
> off one draft — over 40 drafts `reacher` **does** out-reach `balanced` (`pool_rank` 13.40 vs 11.74);
> the inversion is real only in **R1–3** · the corpus far tail (p99 = pick 33 for an ADP 1–2.5 player)
> is a **data question first** — check `days_to_board` and keeper/dynasty leakage before fitting it.
>
> **★ Reporting rule adopted:** the per-personality summary leads with **`pool_rank`, split R1–13 /
> R14–15**, not a 15-round mean reach — which is dominated by late-board ADP noise (Tyler Allgeier at
> ADP 167 taken at pick 119 scores **+48** and means nothing) and by *when* a seat takes K/DST.
> **Mis-reporting it this way is what produced objection 3 in the first place.**
>
> _(Prior pointer — 16.14R's own closeout, still the authority on the seven steps and the T15 bars.)_
>
> **★★★ (2026-07-28 — ★ 16.14R COMPLETE, all seven steps. T19/T20/T21 ☑,
> T22 opened. NOT COMMITTED.)**
>
> **State:** **569 tests** (was 549), ruff clean, **UNCOMMITTED** together with the prior docs-only
> sessions. New steps `steps/phase16_14r_{2..7}_*.py` + `phase16_14r_signal_report.py`; artifacts
> `analysis/phase16_14r_{floor,context,safe_floor,reacher,value_hawk,room,signal_report,brier}.json`
> + **`analysis/mock_16_14R_picks.csv`** (a full 15-round mock, for your eye) +
> `analysis/t19_signals.csv`. DEV-only; the spent lockbox and the frozen value stack are untouched.
>
> **What ran.** The seven-step execution order, straight through under a **waived §3.7 gate** (your
> instruction), with eight decisions taken up front (`PLAN.md` §2026-07-27/28). Step 1 roster
> legality + K/DST · 2 the `floor` repair · 3 the three blind spots · 4 `safe_floor` · 5 `reacher` ·
> 6 `value_hawk` · 7 composition + re-measure.
>
> | bar | T15 shipped | 16.14R | |
> |---|---|---|---|
> | 1 profile distance · round-1 | 0.2220 · 4.36 | **0.1156 · 3.70** | PASS |
> | 2 elite p95 · past pick 10 | 17.0 · 28.5 % | 19.0 · **30.07 %** | **marginal FAIL** |
> | 3 worst harvest excess | +0.21 sd | **+0.06 sd** | PASS |
> | 4 11.2 Brier | +0.0890 | **+0.0890** | PASS, unchanged |
> | 5 dispersion error | +17.0 % | **+5.6 %** | PASS |
> | seat faithfulness | 10.40 · 13.5 % · 19.6 % | **9.38 · 27.8 % · 10.6 %** | corpus 7.62 · 54.3 % · 0.2 % |
>
> **★ Bar 2 is a marginal miss and is deliberately NOT tuned into a pass.** 30.07 % vs a 30.0 %
> ceiling on n = 5,700, binomial se 0.61 pp ⇒ **+0.12 se**, i.e. indistinguishable; the p95 half
> passes (19.0 ≤ 20.0) and the **2026 live board passes outright at 26.3 %**. The direction is a
> real trade, **measured** (same code, 2021–24, 40 seeds, only the mix differing): the T15 room
> scores 28.72 % and the shipped room 29.47 %, so composition costs **+0.75 pp** while profile
> distance falls 0.118 → **0.093**, dispersion +10.4 % → **+6.5 %** and chalk 19.9 % → **10.7 %**.
> That difference is itself +0.51 se, so the attribution gives the *direction and the trade*, not a
> magnitude. **Decide explicitly whether to accept it or re-add a chalkier seat — do not reweight a
> personality until the number crosses.**
>
> **★★ THE FINDING TO CARRY FORWARD — the problem was the SCALE, not the fit.** T19 framed itself as
> *"OLS is the wrong likelihood for a censored variable"*, and **both** repairs that framing admits
> failed: a censored-normal Tobit left a **100 %**-deep top-10 floor list, and a distribution-free
> neighbourhood rank flipped `corr(upside, floor)` to **+0.94 QB** — 16.14's original defect,
> restored, while passing T19's one-sided bar cleanly. A variable that piles up on a boundary of its
> own support has no well-behaved residual however it is fitted. Rebuilding the signals as **ratios
> to the projected level** (`shape_inputs`) puts a censored player at the *bottom* of a bounded
> quantity, which is the honest reading, and only then does an estimator pass. *Before choosing an
> estimator, check the variable is on a scale the estimator can be right about.*
>
> **★ Three more, each one line:**
> 1. **A one-sided bar is passed by the same defect in the other direction.** Selection now requires
>    T19's bar **and** 16.14's oppositions. That check is the only thing that rejected `rank` on raw
>    quantiles.
> 2. **`boom_prob`/`bust_prob` are four seasons stale on any live board (T22, new 🟡)** — they read
>    `max(train_seasons)` and `train_seasons` for a live season is `DEV_SEASONS`, ending **2022**.
>    **292 of 306 zeros are `fillna(0.0)`**, i.e. a player absent in 2022 reads as *never busts*: a
>    fabricated safety claim, worst for exactly the rookies a floor-seeker should distrust. Frozen
>    contract → logged, not edited; both seats now weight `tail_risk`. Same `max(train_seasons)`
>    idiom as T17 — **a sweep for the pattern is probably worth more than either fix.**
> 3. **`floor` is not what fixed the objected picks — `tail_risk` is.** Zay Flowers went *up* the
>    floor percentile (0.76 → 0.85). The objection was about **width**, and width is not floor:
>    Johnston 0.85 / Blue 0.84 / Metcalf 0.76 on `tail_risk`. T19 repaired the input to "highest
>    floor"; step 4 changed the objective to "lowest downside". Both were needed.
>
> **⚠ Do not re-derive these dead ends** (all kept runnable, `PLAN.md` has the list): Tobit ·
> neighbourhood rank on raw quantiles · `rank_delta` · a **pool-relative** `level_floor` (measured
> inert — inside a 40-player band the worst candidate is z ≈ −1.5 whoever he is) · a rounds-derived
> corpus reach ceiling (wrong by **6×**; the panel carries its own `round`, and `reach_profile`
> pools |drift| so its round-15 p90 is mostly players *falling*) · picking the value-hawk window by
> argmax (the sweep is inside its own noise, **+13.1 CE vs a pooled se of 10.7** → the tightest
> window ships).
>
> **★ NEXT:** review + commit (7 steps' worth, one working tree). Then **Session I = Phase 17
> League-Format Fidelity 17.1–17.4**, then J (optional dynasty) → **K = Phase 14.1 MVP + surfacing,
> strictly last**. Stage-0 FFC chore: last pull **2026-07-24**, next due after 07-30.
>
> _(Prior pointer — the 2×5 mock that opened 16.14R, still the authority on why the order changed.)_
>
> **★★ (2026-07-27 session 5 — 16.14R RE-ORDERED, `docs/BUILD_PLAN.md` §"16.14R — THE EXECUTION ORDER".)**
>
> **State:** no code changed this session. Docs only: `docs/BUILD_PLAN.md` §16.14R execution order
> (the 7-step plan of record), `docs/TECH-DEBT.md` **T19/T20/T21**, `findings.md` §"The 2×5 mock
> room", `PLAN.md` §2026-07-27 (session 5), `glossary.md`. T15 remains COMPLETE (steps 0–4 ☑, five
> bars PASS). The mock itself was a DEV run — driver + CSVs in the session scratchpad, nothing
> written to `analysis/`.
>
> **What happened.** A full 15-round mock with **2 seats each of autopilot / value_hawk / safe_floor /
> reacher / balanced**, plus 60 seeded drafts of the same mix. The T15 fix holds on the live board
> (round-1 reach **12.31 → 4.58** picks, elite-fall p95 **30.0 → 17.0** vs a corpus 17.5, profile
> distance r1–6 **0.713 → 0.244**). Then **the user reviewed all 150 picks by eye and raised three
> seat-level objections — and two of them are defects in the *signals* 16.14R was going to build on
> top of.** Hence the re-order.
>
> **★★ THE FINDING TO CARRY FORWARD — the fix for a level-vs-shape defect created the next one.**
> `safe_floor` drafts boom-or-bust players because **`q10` is censored at exactly 0 for 42.9 % of
> offensive board rows** (59.0 % past ADP 100). `residual_shape` regresses it on `mean`, so the
> largest positive residuals go to players just above the censoring point and
> **`corr(floor, adp)` = +0.179 RB / +0.124 WR** — the *safety* signal prefers *deeper* players. The
> board's safest RBs are Jonah Coleman (ADP 171) and Jaydon Blue (ADP 140). **The seat drafted exactly
> what the board told it was safest.** Fourth member of the family (`q90`/`q10` 16.14 ·
> `games_played_mean` T17 · `vbd` · **`floor`**) and the first **self-inflicted** one: 16.14
> residualized to remove a level proxy and produced a *depth* proxy, because removing the level from a
> censored variable leaves something anti-correlated with quality rather than orthogonal to it.
> *A residualization is a modelling assumption about the tail.* **T19.**
>
> **★ Three more things, each a one-line diagnosis:**
> 1. **The `reacher` has width with no direction — literally.** It is
>    `Personality("reacher", temperature=2.2, width_mult=WIDTH_REACHER)`, **no `signal_weights` at
>    all**. Mean `pool_rank` 20.5 vs a corpus p90 of 13.1. Give it direction (rookies · 16.10 hype ·
>    the 16.9 shock, all already assigned to it) **before** applying the user's reach budget — a
>    budget over directed reaching is a different object from a budget over noise.
> 2. **The value hawk's bad picks are blind spots, not mis-weights.** Signed situation, committee
>    share and TD-regression are **not on the 16.13 board** (`cos` exists but is **unsigned** —
>    Rachaad White 1.0, DK Metcalf 0.6). No objective over today's board avoids those picks ⇒ board
>    scope moves first (open decision #3, settled). Separately: `pos_z(vbd)` deletes VBD's only
>    non-ADP content (`corr(vbd, adp)` within position −0.86…−0.96), so a `signal_weights` value hawk
>    **cannot** work ⇒ objective is **portfolio CE** (open decision #1, settled, measured).
> 3. **K/DST — a filter, not a data gap.** `adp_snapshots` has the defenses (60 `DEF` rows, 2026 FFC
>    PPR 10-team); `_ffc_board`'s `gsis_id IS NOT NULL` drops them because they key on
>    `ffc_player_id`, and `board_player_key`/`canon_pos`/`DRAFTABLE` already support DST. **T20.**
>    Found alongside it: **K is in the sim's candidate band but not the fit's** (`skill_only=True`) —
>    Session-G choice-set violation, second home. **T21**, must land with T20.
>
> **★ NEXT = 16.14R Step 1** (roster legality + the K/DST guarantee — user instruction: ≥1 K and ≥1
> DST per seat whenever `rounds >= slots.starters`). Then Step 2 **repair `floor` before any
> personality consumes it**, Step 3 board scope, Step 4 safe_floor, Step 5 reacher, Step 6 value hawk,
> Step 7 composition + re-measure. **Gate after each** (rule 7). Full text: `docs/BUILD_PLAN.md`.
>
> **⚠ Do not re-derive these:** `autopilot` won **48.3 %** of 60 drafts at mean finish 1.69/10 ⇒ the
> default room drops to ≤1 autopilot (Step 7). Composition **alone** moved T15's open faithfulness gap
> from median `pool_rank` 10.40 → **8.59** (corpus 7.62) with no model change. The late-round 0.61×
> narrowness is **unchanged and expected** — it needs per-seat board perturbation, not another width
> parameter. Dead end: rookies do **not** reach `pos_z` as NaN (0 of 31 on the 2026 board) — that was
> the first, wrong, hypothesis for T19.
>
> _(Prior pointer — T15's own closeout, still the authority on the T15 bars.)_
>
> **★★ (2026-07-27, ★ T15 COMPLETE — steps 0–4 ☑, all five bars PASS. NEXT was 16.14R.)**
>
> **State:** **549 tests**, ruff clean, **UNCOMMITTED** (user's choice) together with the three prior
> docs-only sessions. New: `draft/mock.py`, `steps/t15_{0,1,2,3,4}_*.py`, `steps/mock_draft.py`,
> `tests/test_mock.py`. Artifacts `analysis/t15_{baseline,respecify,calibrate,width_curve,verify}.json`;
> **pre-T15 β preserved at `analysis/phase11_opponent_model.pre_t15.json`** so before/after stays
> runnable. DEV-only; the spent lockbox and the frozen value stack are untouched.
>
> **★ SHIPPED:** `AdpSpec(power, p=0.15)` · `BandSpec(widening, k0=40, +5/round, cap 160)` ·
> `WidthCurve(γ=0.8)` · per-seat `Personality.width_mult`. **All three specs travel with β** in
> `analysis/phase11_opponent_model.json` and are read back with it.
>
> | bar | pre-T15 | shipped | corpus |
> |---|---|---|---|
> | #1 profile distance · round-1 mean | 0.388 · 12.15 | **0.222 · 4.36** | 0 · 2.87 |
> | #2 elite p95 · past pick 10 | 30.0 · 57.9 % | **17.0 · 28.5 %** | 17.5 · 18.9 % |
> | #3 worst harvest excess | — | **+0.21 sd** | tol 1.0 |
> | #4 11.2 Brier gain | +0.0708 | **+0.0890** | — |
> | #5 dispersion error | +8.8 % | **+17.0 %** | tol ±20 % |
>
> **⚠ Two things did NOT improve, and the verdict hides them:** dispersion error grew +8.8 % →
> +17.0 % (passes tolerance, but Session G had it better), and **11.1's log-loss gain is not
> comparable across this change** (+0.1715 at the shipped band vs a committed +0.1738 on `fixed40` —
> different candidate sets, and this session's own finding is that log-loss is not comparable across
> bands). Only the 11.2 Brier supports a clean before/after.
>
> **★★ THE FINDINGS TO CARRY FORWARD — four method errors, each of which would have shipped a
> plausible wrong answer:**
> 1. **"Gain over the baseline" is not a selection criterion.** Inside one band, log-loss picks
>    p=0.45 while gain picks **p=1.00 — the incumbent spec T15 exists to replace.** Gain rises when
>    the *baseline* degrades. Twin of F.6's ablation rule. Replaced by **`band_coverage`**.
> 2. **The shipped `fixed40` band was violating the Session-G contract, unmeasured** — it excludes
>    the realized human pick **3.95 %** of the time. That, not a fit statistic, is the judgement-free
>    case for widening.
> 3. **A uniform width metric traded away the defect it was built to fix**, selecting a spec that
>    failed the elite-fall gate. Objective restricted to rounds 1–6 and **gates promoted from terms
>    to hard constraints** — *a gate a metric can out-vote is not a gate.* Related: **a scalar gate
>    over a curve** reported PASS while the curve went 0.388 → 0.791.
> 4. **One knob cannot set both ends.** The `w_a ∝ a^(1-p)` derivation ignores **pool exhaustion**
>    (~30 boarded players remain by round 15): predicted late growth 18×, measured 1.8×. Fixed with
>    the round function T15 already owed 16.14R.
>
> **☐ OPEN, handed to 16.14R with numbers attached:** the **seat-faithfulness population** — median
> `pool_rank` **10.40 vs a corpus 7.62**, moderate band **13.5 % vs 54.3 %**, chalk **19.6 % vs
> 0.2 %**. It trades against the reach profile (γ=0 gives 65.9 % moderate but fails dispersion), was
> never one of T15's five bars, and needs **per-seat board perturbation** (16.14R's *direction* half)
> plus a **room-composition** decision on the two `autopilot` seats (16.15). **☐ Also:** 16.9's
> `NarrativeShock.intercept` is formally **stale** — `assert_transportable` now refuses it across a
> spec change; not re-fit, because 16.9 measured it as unidentified. **◐ T16** is very likely
> dissolved by the widening band but is **not re-measured** — re-run the 16.10 done-bar at 15 rounds
> before marking it ✅.
>
> _(Prior pointer — step 0, superseded above.)_ Baseline **frozen** at `analysis/t15_baseline.json`
> — 900 seeded drafts vs 1,144 realized FFC-boarded human drafts, one measurement code path over
> both. Writeups: `findings.md` §"T15 step 0", `PLAN.md` §2026-07-27 (session 3),
> `docs/TECH-DEBT.md` T15 §"Step 0 done".
>
> **★ Three corrections the 900-draft baseline makes to the text below — the older numbers came off
> ONE draft, so prefer these:** (1) **"the sim is flat" is wrong** — Spearman +0.646 (corpus +1.000),
> it rises to round 9 then **turns over**; state the defect as the **ratio column, 4.24× at round 1 →
> 0.57× at round 15**. (2) **Bars 1–2 tighten on the FFC-only corpus**: round-1 mean **2.87** / p90
> **5.23**; and bar 2 is worse than the anecdote — **57.9 %** of consensus top-12 fall past pick 10 vs
> **18.9 %** realized (p95 **30.0 vs 17.5**). (3) **Bar 3 already roughly passes** on *fixed*
> `pool_rank` edges (+20.5 sim vs +17.6 corpus, sd 17.0); its **quantile** form is an artifact
> (compares `pool_rank` 1.28 to 4.28) and must not be used.
>
> **★★ THE FINDING TO CARRY FORWARD — the room has no moderate drafters.** 54.3 % of real seats sit at
> `pool_rank` 2–8; the sim puts **2.2 %** there and **19.6 %** below 2. The room is **bimodal**, so
> **T15's target is the distribution of deviation, not its scale** — a uniform shrink moves the
> extremists and leaves the middle empty. Two corollaries: `autopilot` at 2-of-10 seats over-represents
> a behaviour that is **0.2 %** of real seats (**a 16.15 composition question**, and it does *not*
> reopen 16.14R's "autopilot: no change", which was about its win); and simulated within-bin harvest sd
> is **2.1–3.7** picks vs the corpus's **8.7–17.0**, so the seats are too homogeneous even where the
> means match.
>
> **★ STEP 1, and the arithmetic that decides it (derived in `PLAN.md` session 3).** With utility
> `u = β·f(a)`, width in ADP picks is `w_a ∝ 1/f'(a)` — **board density cancels**. So linear ⇒ flat
> (the defect, derived); `a^p` ⇒ `w_a ∝ a^(1-p)`, and the measured `pick^0.5…0.6` gives **p ≈ 0.4–0.5**;
> `log a` ⇒ over-corrects. **Rank-in-pool ⇒ `w_a ∝ board density`, which grows ~2.3× where the corpus
> grows 5.5× — it structurally under-corrects and is nearly a no-op** (linear-in-ADP inside a fixed
> top-K already *is* rank-in-pool up to a level that cancels in the softmax). Still choose by refit
> log-loss, but grid the **exponent**. ⚠ Two things the plan did not record: `apply_hype` and
> `Personality.reach_cap` hardcode the **linear** derivative `−β/_ADP_SCALE`, so the extraction owes a
> `utility_per_pick(adp)` next to `adp_feature(adp)`; and **persist the fitted exponent alongside the
> coefficients** in `analysis/phase11_opponent_model.json` or `load_opponent_model` pairs a new β with
> the old transform. Keep raw `adp` on the choice frame so an exponent grid refits from one built frame.
>
> **⚠ Environment:** `.venv/bin/pytest` has a stale shebang from the pre-move path — use
> `uv run python -m pytest`, or repair with `uv sync --reinstall`.
>
> _(Prior pointer — the live mock that opened this session; its one-draft numbers are superseded above.)_
>
> **What happened.** The user drafted a full 10-team mock from seat 7 against `DEFAULT_ROOM`, live,
> one pick at a time. He raised **one** issue, four times, unprompted: the room's reaches and falls
> are impossible. He is right, and it is measured — `findings.md` §"Live mock draft (2026-07-27)",
> register entry `docs/TECH-DEBT.md` **T15**.
>
> **The number to carry:** round-1 mean reach is **11.4 ADP picks simulated vs 3.3 realized**
> (p90 **27.7 vs 6.6**) over 1,420 human drafts / 197,227 boarded picks; by round 15 it inverts
> (**15.0 vs 27.1**). The corpus curve grows monotonically, the sim is flat — **a shape error, not
> a scale error**, so do not "just make it chalkier". Elite falls mirror it: corpus ADP ≤ 12 has
> **p95 = pick 17**; the sim dropped five top-12 players past that in one draft. And the spill is
> harvested — `autopilot` mean drift **−19.8 picks**, both autopilot seats finished **1st and 2nd**.
>
> **★ Why it survived every gate: an aggregate metric cannot see an impossible event.** 11.1
> log-loss +0.174, 11.2 Brier +0.086 and 16.9's dispersion match are all still true. They score
> *better than a baseline*, never *possible*. **Every subsystem needs one bar a domain expert could
> fail by eye, run in front of one before it ships.**
>
> **★ It is a specification error, so more data cannot fix it** — ADP is worth **0.0337 utility per
> pick** while `is_TE` is +0.567 (**17 picks**) and `need` +0.474 (**14 picks**), softmaxed over a
> fixed top-40 ⇒ **expected reach 16.8 picks before any personality tilt**. `adp_s` is linear in raw
> ADP pooled over all rounds; one coefficient cannot be sharp at the top and diffuse at depth.
> F.5's 52× corpus expansion estimated the wrong coefficient more precisely. **Measured fix family:
> width ∝ `pick^0.5…0.6`, i.e. a fractional power or rank-in-pool — NOT log-ADP (`pick^1.0`),
> which over-corrects; T15's earlier log suggestion is superseded.** Five acceptance bars are
> pre-registered in T15.
>
> **⚠ `Personality.max_reach_picks` is not a total-reach cap** and was misread as one: it clips a
> seat's *own opinion* only. The draft's 42-pick reach came from **`balanced`** — every tilt off.
>
> **★ DECIDED 2026-07-27 (user): (a) — the T15 respecification session goes NEXT, before Session I.**
> Phase 17 / Session I slides one session; nothing in it depends on T15 or vice versa. Rejected: (b)
> keep Session I first, (c) ship the hard-clip override now. **The clip is a step-4 fallback only** —
> shipped only if the refit leaves a gap, and then labelled/separable (see T15). Ordered plan:
> **0** promote `mockdraft.py` to `steps/` + seeded batch mode + a sim→`build_drift_panel` helper (the
> A/B harness — build it before anything else; the single-draft evidence is noisy) · **1** respecify
> `adp_s` (fractional power `adp^~0.45` **or** rank-in-pool; choose by **refit log-loss**, not by
> curve-fitting the corpus table) and **refit** — the point is that `is_TE`/`need` shrink in
> pick-units at the top of the board. ⚠ `adp → adp_s` is built in **two** places that must not
> diverge (`opponent_model.py` `build_choice_frame` fit path + `candidate_matrix` sim path) → extract
> one shared `adp_feature()` · **2** add the two judgement-free gates (no top-12 past ~pick 17; the
> `autopilot` seats stop out-valuing the room) · **3** re-verify 11.1 / 11.2 / 16.9 **together**, and
> **re-fit `NarrativeShock.intercept`** (not transportable) · **4** clip only if still needed. See
> `PLAN.md` 2026-07-27.
>
> **★ THEN (2026-07-27 session 2, docs-only): the 16.14R personality contract is SPEC-AGREED** —
> `docs/BUILD_PLAN.md` §16.14R, `PLAN.md` §2026-07-27 (session 2), `findings.md` §"Personality design
> review". It is the session **after** T15 (it needs T15's round-varying width function). Headlines:
> **width vs direction** replaces the absolute `max_reach_picks` ceiling (autopilot 0 · safe ~0.8 ·
> balanced 1.0 · reacher ≤2.0) · **autopilot unchanged** (its win was harvested spill, so T15 fixes it
> by fixing everyone else — **T15 bar #3 was rewritten to measure surplus, not standings**) ·
> **balanced was never given its holistic tilts** (raw β, every tilt off — that is the 42-pick reach) ·
> **Value Hawk replaces Homer** (reverses 2026-07-23; `fandom` becomes fitted-and-unused, do not delete)
> · reacher inherits the 16.9 shock + 16.10 hype. **★ "The level, not the residual"**: situation flags
> are null for *drift* and that is consistent with them driving human behaviour — ADP already absorbed
> them — so situation ships opt-in/default-OFF and never as a deviation driver. **⚠ Scoring trap:** the
> value hawk optimizing our board and scored on our board wins by construction; projected-points
> rankings are **descriptive**, evaluative claims run on **realized** points. **☐ 3 opens before 16.14R
> only** (value hawk objective VBD-vs-**CE**, its reach window, whether 16.4/16.5 join the 16.13 board)
> — **none of them block T15.**
>
> **Reusable artifact:** the interactive human-vs-personalities driver lives in the session
> scratchpad (`mockdraft.py`, ~330 lines, thin over `DraftState` + `make_room_pick_fn`). **Promote
> it to `steps/` if we want repeatable human mocks** — it is how this defect was found, and it is
> the natural before/after harness for the T15 fix (re-measure over ≥50 seeded drafts).
>
> _(Prior pointer — history.)_ **★★ (2026-07-27, ★ SESSION H COMPLETE — 16.13 ☑ · 16.14 ☑ · 16.15 ☑ ·
> T17 ☑. NEXT = Session I, Phase 17 formats.)**
>
> **State:** **524 tests** (was 496), ruff clean, every done-bar gate PASS on the live 2026 board.
> `steps/phase16_15_mock_room.py` → `analysis/phase16_15_mock_room.json`; the T17 guard lives in
> `steps/phase5_5_utility.py`. **Committed** — Session H is one commit on top of `5f6383b`
> (Session G). DEV-only; the spent lockbox untouched; the frozen value/distribution/optimizer/VBD/
> cost-report stack untouched (16.13 only *reads* it). Stage-0 FFC chore: last pull 2026-07-24,
> **next due after 07-30** (`steps/stage0_adp_snapshot.py`).
>
> **★★ THE FINDING TO CARRY FORWARD — an upstream fix can break a downstream signal by making it
> better.** T17 turned `games_played_mean` from four cohort constants into a real forecast, and in
> the same move into a **level** column (`corr` with `mean` within position: +0.00 before, then
> +0.46…+0.90). `safe_floor`'s durability weight silently became a quality tilt — no code change, a
> green suite, and a plausible-looking personality. Third instance of the *level vs shape* lesson,
> first to arrive through **data** rather than code, fixed the same way (`residual_shape` gained
> `durability`). **A regression test pins a signal's behaviour, not its meaning:** nothing in the
> suite could have caught this. What catches it is re-measuring a signal's correlation with the
> level after **any** change to the data it is built from — the F.5 "re-audit after a step change in
> input volume" rule, generalized from volume to quality.
>
> **★ 16.15 = Phase 16's FIFTH null, and it is 16.9's null.** At the shipped shock (1.48 ADP picks)
> the room does nothing: largest per-seat move **0.036**, routing-vs-gain **+0.07**. The same shock
> ×10 gives **+0.91** (sweep ×1→×40: +0.07 · +0.53 · +0.84 · +0.91 · +0.95). So the coupling is
> **built correctly and waiting on a signal worth routing**. The done-bar **gates the mechanism** at
> `AMP_GATE` and **reports** the shipped size — turning the shock up to pass would tune a calibrated
> parameter to a face-validity check. (Same shape as 16.16: the detector works, reacting does not.)
>
> **★ The reach ceiling bounds a seat's OWN OPINION, not the room's story.** `max_reach_picks` caps
> `signal_weights` + fandom excess; the shared 16.9 draw is applied outside the clip, because 16.9
> fitted it **uncapped and uniform**. Folded in, a seat whose signals saturate its ceiling cannot
> express the story at all — and nothing fails, since a personality that ignores the shock still
> drafts legally. **Two bar-design lessons came out of finding it:** (1) a **two-ended** bar
> (*chasers − autopickers*) passes on a room routing the story backwards, because autopickers get
> sniped either way — state the bar across **every** seat; (2) a **zero vector is not an off
> control** — `argsort` on zeros labels the top-N by board order, i.e. by ADP, which autopick seats
> take by construction, manufacturing a large fake effect on exactly the seats it should be silent
> about. Close the channel, keep the same labels.
>
> **⚠ Correction recorded, because the number is quotable and was wrong:** "homer clips 90 % of
> candidates" was measured on the **test fixture** (`β_adp_s = −0.85`). On the live board's fitted β
> (−1.68) homer clips **0.0 %** (upside 26 %, safe 33 %). The fix stands on the estimation-conditions
> argument, not on a large current effect. *Measure the real board before quoting a fixture number
> as the system's behaviour.*
>
> **★ NEXT: Session I — Phase 17 League-Format Fidelity 17.1–17.4** (roster/lineup generalization
> incl. superflex + format-aware VBD replacement, custom scoring, the generic settings contract,
> keeper). A full-phase item, ~1,000–1,800 lines. Then J (optional dynasty 15.1) → **K = Phase 14.1
> MVP + all surfacing, strictly last, do not bundle.** `docs/TECH-DEBT.md`: **T17 ☑**, new **T18**
> (🟡 `avg_reach` is a pooled-board mismatch, unconsumed today); T13/T15 still open.
>
> _(Prior pointer — history.)_ **★★ (2026-07-26, ◐ SESSION H PART 1/2 — 16.13 ☑ · 16.14 ☑.)**
>
> **State:** **496 tests** (was 466), ruff clean, every done-bar gate PASS.
> `steps/phase16_13_personalities.py` → `analysis/phase16_13_personalities.json`. **UNCOMMITTED**
> (13 files), your choice — Session G is fully committed through `5f6383b`, so the working tree holds
> Session H alone. DEV-only; the frozen value/distribution/optimizer/VBD/cost-report stack is untouched
> (16.13 only *reads* it). Stage-0 FFC chore: last pull 2026-07-24, **next due after 07-30**.
>
> **★★ THE FINDING TO CARRY FORWARD — a signal is not a *shape* signal without its level control.**
> 16.14's spec says the upside chaser weights `q90` and the safe drafter weights `q10`. Built exactly
> that way, **they agree with each other**: on the real board `safe_floor` drafted a *higher* mean
> `q90` than `upside_chaser`. Measured within position, `corr(q90, mean)` = **+0.984 / +0.985 /
> +0.999** (2022 / 2025 / 2026) and `corr(q90, q10)` = +0.62…+0.74. The quantiles are almost entirely
> **level** — "is this player good" — so both weights are quality tilts wearing risk-tilt clothes.
> The fix is `enrichment.residual_shape`: regress the level out inside each position, giving
> `upside`/`floor`, orthogonal to level by construction and `corr = −0.86` with each other.
> **This is the 16.10 finding again** (*a coefficient is not transportable without its controls*) —
> same failure mode, one level down, on a **signal** instead of a coefficient, and it presented the
> same way: as a plausible modelling result rather than as an error. It was caught only because the
> face-validity bar was stated as *the two must disagree with each other* rather than *each must
> differ from balanced*; the weaker bar passes the broken build. **State your bars as oppositions.**
>
> **★ The other lesson: an inert thing still passes.** `homer` had been scaling a `fandom`
> coefficient whose feature was identically 0 (nothing in the mock path ever passed `fav`) and
> `rookie_hawk` scaled a column `_prepare_board` discarded. Both were **literal no-ops from Phase
> 11.3 through a full phase and a green suite**, because a personality that does nothing still
> completes a legal draft. Assert that a tilt *moves* something, not merely that it runs.
>
> **★ Effect sizes here are small and that is honest.** ±0.05 z on a pooled drafted pool; a manager
> who reaches 1–2 rounds cannot move 90 picks much. One seeded draft cannot even resolve the *sign* —
> every face-validity number pools 8–12 drafts. The reach ceilings (18 / 15 / 24 picks) were
> **measured**: at 10 the personalities sit inside `balanced`'s own noise.
>
> **★ New tech debt: T17 (🟠) — the live season has no per-player availability.**
> `availability_projection(con, 2026)` returns **0 rows** (a future season has no played weeks to
> predict on), so every player falls to the T3-A cohort prior: **4 distinct `games_played_mean`
> values across 480 players** and the Phase-5 `mean` collapses to **37 % of the consensus projection
> it is built from** (2025: 75 %). Session H is insulated because every signal is standardized
> *within position*, so a uniform multiplier cancels — but this **blocks Phase 14** showing a user
> any distribution number for the season they are drafting. Fix + guard in `docs/TECH-DEBT.md`.
>
> **★ NEXT: 16.15** — mock-room seat composition (a default realistic mix over the 9 opponents,
> user-overridable), routing the 16.9 narrative shock through the seats that would chase it, and the
> app selector spec. The plumbing is already in: `Personality.hype_gain` is the per-seat multiplier
> on the shared shock and `fav_teams` makes a homer's team configurable. Then Session I (Phase 17
> formats) → K (Phase 14 app, last).
>
> _(Prior pointer — history.)_ **★★ (2026-07-26, ★ SESSION G COMPLETE — T14 ☑ · 16.9 ☑ · 16.11 ☑
> · 16.10 ☑ · 16.12 ☑ · 16.16 ☑.)**
>
> **State:** **466 tests** (was 425), ruff clean, every done-bar gate PASS. **UNCOMMITTED** — left on
> a clean-diff basis for your review (your choice this session). DEV-only; the spent lockbox is
> untouched; the frozen value/distribution/optimizer/VBD/cost-report stack is **provably** untouched
> (see the isolation gate below). Stage-0 FFC chore: last pull 2026-07-24, **next due after 07-30**.
>
> **★★ THE FINDING TO CARRY FORWARD — a coefficient is not transportable without its controls.**
> 16.10 ranks nominations using the three weights that survived 16.8's ablation. Those are *partial*
> coefficients, fit with `adp_rounds` and position dummies in the model. Used unconditionally they
> ranked players by **board depth** (ADP standard deviation grows mechanically with ADP: 0.7 picks at
> the top of the 2026 board, 33 near the bottom) and then, once depth was controlled, by **position**
> (our value board likes every TE more than ADP does). Two plausible-looking, wrong candidate lists.
> A third defect hid in the *units* — the weights are in rounds, velocity is rounds/week, so momentum
> was nearly inert until multiplied by a horizon. **This is the F.5/F.6/16.9 family again: every one
> presented as a modelling result rather than as an error.** When reusing a fitted coefficient
> anywhere new, reproduce its controls and check its units before reading the output.
>
> **★ Phase 16's availability track is DONE and it is four honest nulls** (16.8 drift model, 16.9
> narrative shock, 16.16 run reaction — plus the value side's 16.1/16.2 and 16.4's deflationary
> 20.9 %). Everything that ships is either a **contract fix** that improved a validated metric (16.9's
> choice-set band) or an explicitly **curated, opt-in, default-OFF** channel. Phase 16 found no edge;
> it found four ways the apparent edges were measurement artifacts.
>
> **★ 16.16 = the detector works, reacting to it does not.** Run intensity measured against the **live
> candidate set** (top-40 by ADP, *not* the whole remaining pool — that version fired on 61 % of
> windows and anti-discriminated) gives monotone discrimination, **+0.109** at threshold 0.50 across
> 7,957 replayed windows. But paired availability Brier on 4,300 run-opened windows degrades
> monotonically in the bump size: **0.2121 → 0.2123 → 0.2128 → 0.2186**. Likely double-counting
> (11.1 already carries `pos_run3`); confirming it needs an 11.1 refit, cf. T15. **Default OFF**,
> detector kept as a live-draft alert for 14.4.
>
> **★ What you owe the hype board.** `reference/hype_board.csv` ships **24 rows / 20 directional
> claims, all `reviewed=false` — therefore inert.** Nothing consumes it until you set `reviewed=true`
> per row. Your review surface is `pick_delta` / `note` / `confidence`; the rows themselves are
> derived and regenerate safely (`steps/phase16_10_hype_board.py --write` merges your edits forward).
> Four rows are deliberate **non-claims** (`pick_delta=0`, e.g. Brian Robinson Jr., whose board-topping
> ADP disagreement is *handcuff contingency*, not hype) — kept visible so you can see where the
> derivation fired and the research found nothing.
>
> **★ New tech debt: T16** (🟡 a deep curated claim cannot express in a standard **15-round** league —
> a +12-pick claim on a board-rank-171 player gave a *bit-identical* 30-draft result and needed ~5×
> the offset to move; the 16.10 done-bar therefore runs at 18 rounds. Recommendation: surface the
> limitation now, and let **T15**'s depth-varying candidate set dissolve it properly. Do not hack the
> offset scale alone.) **T14 ☑, T15 still open.**
>
> **★ NEXT: Session H — opponent personalities 16.13–16.15.** 16.13 board enrichment (attach the frozen
> Phase-5 distribution + `value_board` fields read-only), 16.14 the five headline personalities
> (`signal_weights`), 16.15 mock-room composition + hype coupling. Validation = face-validity + unit
> tests, **no Brier gate** (decided 2026-07-23). Then I (Phase 17 formats) → K (Phase 14 app, last).
>
> _(Prior pointer — history.)_ **★★ (2026-07-26, ★ SESSION G part 1/2 — T14 ☑ + 16.9 ☑.)**
>
> **State:** **425 tests** (was 411), ruff clean. Committed on `main`. DEV-only; the spent lockbox is
> untouched; the frozen value/distribution/optimizer/VBD/cost-report stack is not touched by any of
> this. Stage-0 FFC chore: last pull 2026-07-24, **next due after 07-30**.
>
> **★★ THE FINDING TO CARRY FORWARD — the choice-set contract.** 11.1 is a conditional logit fit on
> `build_choice_frame(top_k=40)` = the top-40 available by ADP. **Both** consumers of that fitted β
> were simulating against the *whole board*: `personalities.make_opponent_pick_fn` and
> `availability.simulate_survival`. A conditional logit's coefficients only mean anything relative to
> the candidate set they were estimated on. This inflated simulated draft-slot dispersion **59 %**.
> Both now read `opponent_model.CHOICE_TOP_K` and a test fails if fit and simulation drift apart.
> **This is the fourth member of the F.5/F.6 family** (hardcoded `scoring="ppr"` → contaminated
> behavioural corpus → modal board size → candidate set): *every one was a fit/use mismatch that
> presented as a modelling result.* When a fitted model gets a new caller, check the caller
> reproduces estimation-time conditions before trusting the output.
>
> **★ 16.9 = an honest NULL (Phase 16's third).** The premise inverted: the phase assumed
> independent per-seat sampling **under**-disperses; measured, the simulator **over**-dispersed.
> After the contract fix — level error **59.5 % → 8.8 %** (pooled sd 2.897 → 1.976 vs realized
> 1.816) and availability Brier **+0.0644 → +0.0708** on 7,792 windows, so *two independent metrics
> improved and it is not a tuning choice*. The shock itself does nothing: realized depth slope
> **+0.679**, banded **+0.077**, +shock **+0.057**; swept over a **50× size range** the slope stays
> inside its own between-sample noise (two runs at one setting: +0.249 / +0.057) → the calibration is
> **unidentified**, and its "best intercept" is a noise draw, reported as such rather than as a fit.
> **Structural reason it cannot work:** `top_k` is a hard rank filter applied *before* utility, so no
> additive shock pulls a player into the candidate set. **Shipped: band ON by default; shock built,
> wired, tested, default OFF** — kept because 16.10/16.15 need an expression channel for a curated
> narrative, and that channel is now correct.
>
> **★ New tech debt: T15** (🟡 simulated dispersion is flat in board depth — `adp_s` is linear in raw
> ADP, so dispersion is uniform *in rank*; real drafting is sharp at the top and diffuse at depth.
> Fix is an **11.1 respecification** — soft/widening band or log-ADP/rank utility — and must be
> re-verified against 11.1 log-loss, 11.2 Brier **and** the 16.9 profile *together*. Do it before
> Phase 14 surfaces `P(available)` to a user; do not block Session H on it.) **T14 ☑** — see its
> register entry for the "a complexity class is not a profile" lesson.
>
> **★ NEXT: 16.10** — the curated hype board. User decision already taken: **build the mechanism now
> (loader + schema + tests + a Claude-drafted 2026 board stamped `reviewed=false`, apply path refuses
> unreviewed rows), user reviews the CSV afterwards** — do NOT stall the session on review. Then
> 16.11 momentum (live-2026-only, forward-only label) → 16.12 consumption → 16.16 run detection.
> Then Session H (personalities 16.13–16.15) → I (Phase 17 formats) → K (Phase 14 app, last).
>
> _(Prior pointer — history.)_ **★★ (2026-07-26, ★ SESSION F.6 COMPLETE — the re-derivation sweep.)**
>
> **State:** **411 tests** (was 395), ruff clean, all data-health gates PASS. Committed on `main`,
> **not pushed**. Stage-0 FFC chore: next due after 07-30. DEV-only; the spent lockbox is untouched.
>
> **★★ THE FINDING TO CARRY FORWARD — a contaminated corpus invents effects.** F.5 fixed format
> contamination on the ADP board path but the **behavioral** path had the identical bug:
> `build_choice_frame`/`availability_brier` read all 7,699 human drafts (74 % dynasty/2QB/IDP/
> auction/abandoned) against one hardcoded 10-team PPR board. Of those, **1,426 are eligible**.
> Re-fitting on the clean corpus deleted two "behavioral findings": `rookie` +0.45→**+0.11** (that
> was dynasty rooms) and `is_QB` +0.17→**−0.03** (2QB rooms), while `adp_s` doubled
> −0.85→**−1.68**. *Noise shows up in a CI; contamination shows up as a plausible result.*
> Eligibility now lives in one place — `adp/boards.py` + `drift_panel.eligible_drafts` — and
> `tests/test_boards.py` fails on the old rule (verified by reverting, not by inspection).
>
> **★ Results after the sweep.** 11.1: **+0.1738** log-loss gain CI[+0.1693,+0.1781] on 70,614
> groups (was +0.1126 / 7,900) — beats ADP. 11.2: gain **+0.0864** CI[+0.0769,+0.0980] on 36,972
> windows over 252 drafts — still beats best-tuned ADP+noise, but **half** the +0.1587 that 21
> drafts implied (`n_drafts: 21` was a *default argument*, not a corpus limit). S6 adaptive
> re-validated and stronger: adaptive(hero_rb) **+19.4 CI[+4.5,+32.9]**.
>
> **★ 16.8: the leak got stronger with more data.** Headline **+9.25 %** CI[+3.29,+13.91] (bar is
> 2 %) — and the mandatory ablation without `source_divergence` is **+0.01 %** CI[−1.98,+1.84].
> With more sibling drafts the leave-one-draft-out board estimates each room's own consensus
> better, so the leak-prone feature predicts better. **Scale does not launder a leak — a rising
> headline is what a leak looks like from outside.** Verdict stands: no per-player drift forecast
> for 16.9; it shapes its shock from the ablation survivors (`rookie`, `adp_stdev`, `vbd_gap`,
> `pos_WR`, `pos_TE`).
>
> **★ Decisions taken this session (do not re-litigate):** ECR adopted as the 2025 board fallback
> but **calibrated** (isotonic rank→ADP + truncation at FFC's median depth 182 — raw rank produced
> +17.5-round fake reaches and a 2025 sd of 2.67 vs 1.82 after); the pre-registered 16.8 headline
> stays **FFC-only** with ECR as a labelled sensitivity; **no per-manager random effects**
> (ablating `mgr_lean` costs 16 % of the gain, and the eligible corpus has only 111 managers with
> ≥10 drafts — the "1,330 with 10+" figure counted all formats); 11.1 fits a **sampled 60
> drafts/season** because the full frame is ~8M rows and this box has ~3 GB.
>
> **★ New tech debt: T13** (🟠 the Phase-5 cloud is **not reproducible across processes** — dress
> coverage wobbles 75.5↔76.5 %, so Session D's 75.5 % and today's 76.5 % are *the same number*;
> frozen layer, fix at Phase 14) and **T14** (🟡 11.2's bootstrap is O(n_boot × n_drafts ×
> n_windows), ~45 min at 252 drafts). **T11(b) closed.**
>
> **★ The 2025 dress rehearsal ran its season sim for the first time** (Session D could not): 300
> team-seasons, playoff Brier 0.2325 < 0.240, title Brier 0.0905 vs 0.090 (marginal miss), points
> coverage 0.88. Cause of the old skip: `sleeper_human` boards are labelled with the **modal**
> league size (12 from 2019 on) while every consumer asks for `teams=10` — the hardcoded-label
> family, third instance. Fixed at harness level; frozen readers untouched.
>
> **★ NEXT: Session G** — apply the drift, 16.9–16.12 + 16.16, under the null's constraint
> (dispersion match, no mean signal). Then H (personalities) → I (Phase 17 formats) → K (Phase 14
> app, last). Re-running 11.2 at scale first? Fix T14 or it costs ~45 min of bootstrap.
>
> _(Prior pointer — history.)_ **★★ (2026-07-25, ★ SESSION F.5 COMPLETE — corpus expansion.)**
>
> **State:** **395 tests** (was 382), ruff clean, **all data-health gates PASS for the first time**
> (T12 closed). DB backed up 2026-07-25 (357 MB, checksums verified). Stage-0 FFC chore: current,
> next due after 07-30. Session F.5 is **left uncommitted for your review**, same as prior sessions.
>
> **★ What happened: the Sleeper corpus grew ~52× and the 16.7 drift panel grew 33.6×.**
>
> | | Before | After |
> |---|---|---|
> | Human drafts | 149 | **7,699** |
> | Picks | 17,082 | **1,207,687** |
> | Manager profiles | 289 | **24,696** |
> | **16.7 panel drafts** | **34** | **1,144** |
> | `drift_centered_sd` (16.9's target) | 1.5375 | **1.8161** |
>
> The old crawl was **un-reseeded, not exhausted** — three mechanical defects (frontier never fed back
> in from `sleeper_manager_profiles`; participant expansion dead-ended because it keyed on "is this
> draft new" while the caller pre-seeds the whole store; budget counted *discovered* not *ingested* ids,
> burning 263/500 on dead ids). All fixed, all regression-tested. `steps/phase0_10b_crawl.py --mode
> frontier` is resumable via `sleeper_crawl_users`/`_leagues`/`_queue`. Full detail: `findings.md`
> §"Session F.5", `docs/SLEEPER.md`.
>
> **★★ THE FINDING TO CARRY FORWARD — format contamination.** `_refresh_board` hardcoded
> `scoring="ppr"`, so every complete human snake draft landed on one board labelled PPR redraft. At 149
> drafts that was harmless; at 7,399 it was **82 % wrong** (only 1,312 are PPR redraft; 2,547 are
> dynasty_2qb, 952 2qb, 861 dynasty, 610 IDP). It surfaced as an *unrelated-looking* gate failure — `ADP
> top-150 gsis match` red at 3.5 % unmatched, because IDP rooms pushed DB/DL/LB onto an offensive-redraft
> board. Boards are now **redraft-only, split per (season, scoring)**, in FFC's vocabulary; unmatched
> fell to 0.61 %. **A hardcoded label is a bug that scales with your corpus — re-audit derived artifacts
> after any step change in input volume, not just after code changes.**
>
> **★ NEXT: Session F.6 — the re-derivation sweep**, in this order, and note each item's *decision*
> status because F.5 deliberately took none of them:
> 1. **Phase 11.2 availability Brier (T8b)** — the thinnest result in the repo (`n_drafts: 21`). The
>    binding constraint was repeated managers; there are now **12,578 with ≥2 drafts, 1,330 with 10+**.
>    Largest proportional firming available; do this first.
> 2. **Phase 11.1 opponent model** — 7,900 choice groups → ~200k. **Decide explicitly: re-fit, or
>    *extend*** (per-manager random effects are only now viable). A re-fit is mechanical; an extension is
>    a modelling session. Recommendation was: re-fit first, look, then decide.
> 3. **16.8 drift model** — CI shrinks ~5.8× (√(1144/34)). **The pre-registered >2 % skill bar stands
>    unmoved** and the `source_divergence` **ablation remains mandatory** (see the Session F ablation
>    rule below — it is the single most important carry-forward in this file). Honest expectation: the CI
>    clears zero, the point estimate stays under 2 %, i.e. real but too small to use.
> 4. **Phase 11.3 personalities** + **S6 adaptive** (`spine_5_adaptive.py`) — both ride the fitted β and
>    the behavioural room, so both move once (1)–(2) land.
> 5. **Open decisions not taken in F.5:** (a) adopt **ECR as the board fallback** to recover 2025 (278
>    eligible drafts, no FFC board; ECR covers 2017–2026 — mind the 2023 PPR `is_preseason=False` trap);
>    (b) whether to **re-run the 2025 dress rehearsal**, which is a further read of the 2025 calibration
>    holdout.
>
> **★ Banked for Phase 17 (Session I):** ingest filters nothing, so **5,693 complete human non-redraft
> drafts** (dynasty_2qb 2,607 · 2qb 1,021 · dynasty 861 · idp 610 · …) are already in the store. Phase 17
> would otherwise have re-paid the 70-minute crawl.
>
> **★ The lockbox is safe — verified three ways, do not re-litigate.** `lockbox_eval.py --which lockbox`
> routes to `source="ffc"`/`_board_ffc`; its seats use `_noisy_adp_pick` (ADP+noise, not the behavioural
> model); `cost_validation.py` likewise. Only `--which dress` (2025) reads `sleeper_human`. Growing the
> corpus **cannot** contaminate the spent 2023+2024 lockbox or the frozen value stack. Phase 9.1's
> scarcity is also Sleeper-independent (`survival_prob` lives in `draft/optimizer.py`).
>
> _(Prior pointer — history, and still the authority on the ablation rule.)_ **★★ (2026-07-25, ★ SESSION F
> COMPLETE — data 0.11 + availability drift 16.7–16.8.)**
>
> **State (as of Session F, superseded above):** 382 tests, ruff clean. Session F was committed at
> `6a047a7`. Stage-0 FFC chore: done 2026-07-24, **next due after 07-30**.
> New files: `data/sources/ecr.py`, `adp/drift_panel.py`, `adp/drift_model.py`, three `steps/`, two
> `tests/`, `tests/fixtures/ecr/`, three `analysis/*.json`; one edit to `adp/regression.py` (a
> backward-compatible `target`/`continuous` kwarg — the frozen softness path is untouched and its
> tests pass).
>
> **★ THE VERDICT: the availability side is an honest null too.** 16.8 = **DOES NOT PREDICT** against a
> bar fixed before the result was read (skill > 2 %, CI clear of 0): headline **+1.05 % CI[−1.48,+4.96]**.
>
> **★★ The single most important thing to carry forward — the ablation rule.** The headline's entire
> apparent skill came from `source_divergence`, a feature derived from the target's own sibling drafts.
> It was **already** computed leave-one-draft-out; the ablation that drops it scores **−1.75 %**, i.e.
> *worse than assuming everyone drafts at ADP*. **Leave-one-out is NOT sufficient for a sibling-derived
> feature** — drafts from the same season still share rooms, drafters and local ADP quirks. Always report
> the fit without it. Without that ablation (added on your instruction) this would have been written up
> as a weak positive.
>
> **What this means for Session G, concretely:** **16.9 must NOT be handed a quantitative drift
> prediction to amplify.** Its done-bar is a *dispersion* (variance) match, which needs no mean signal —
> `drift_panel.aggregate_player_season` already emits `sd_drift` for exactly that. Shape the shared
> per-draft shock with the things that **did** survive the ablation, as descriptive room behaviour rather
> than a per-player forecast: **`rookie` +0.73 rounds** (rooms reach for rookies by three-quarters of a
> round), **`adp_stdev` +0.35/SD** (where the crowd disagrees with itself, someone jumps), `vbd_gap`
> +0.18/SD, `pos_WR` +0.47. And **16.10's curated hype board is now the primary narrative channel** — its
> "curated, not a backtested claim" label is load-bearing, not a caveat.
>
> **Situation flags are null on the availability side too** (`team_changed`, `new_starting_qb`, both
> competition flags — insignificant, sign-unstable), exactly as in 16.1/16.2. Measured twice now from two
> independent directions: **situation change is a smaller lever than the narrative around it.**
>
> **★ 16.7's three deviations from BUILD_PLAN, each forced by a measurement — do not "fix" them back:**
> 1. **`PRESEASON_WINDOW` (Aug 1 – Sep 15)**, which the plan lacked. The Sleeper corpus contains drafts
>    from **February to November**; an offseason dynasty startup or a November in-season draft measured
>    against a September board is a different market, not drift. Biggest single filter: 117 → 42 drafts.
> 2. **Units are rounds** (`pick_no / teams`), so 6/8/14/16-team rooms join the 10/12-team FFC board.
> 3. **Sign flipped**: `drift > 0` = drafted **EARLIER** (matching `sleeper.build_tendencies`' `reach`),
>    and **`drift_centered`** — drift minus its own draft's mean — is the headline target, removing each
>    room's level offset. Never model raw `drift`.
>
> Panel: **34 drafts / 4,495 picks / 436 players / 2017–2024**. 2025 drops entirely because **FFC
> publishes no 2025 board** (confirmed against the live API). It is thin, and the one thing that would let
> 16.8 be re-asked is a bigger human corpus: add seeds to `reference/sleeper_seeds.txt` → run
> `steps/phase0_10b_crawl.py`.
>
> **★ 0.11 — I was wrong first, then measured it.** The FantasyPros ECR `?year=` archive **is** genuinely
> historical (2020 → McCaffrey/Barkley/Elliott). An initial check said otherwise because it regex'd a
> *different* embedded block out of the page — a widget that renders current-season players on every
> archived page. **Always parse the `ecrData` blob**, never loose `player_name` matches.
> **But the archive is kickoff-dated**: every board is a single end-of-preseason snapshot stamped
> 9/06–9/11, *after* the drafts it would explain — **1 of 38** corpus drafts post-dates its own stamp. So
> BUILD_PLAN's "does true-ECR beat the VBD proxy on drift MAE" is **unanswerable**, 16.8 keeps the proxy,
> and `ecr_asof` enforces this **structurally** (a draft-day as-of returns an **empty frame**, not a
> future board). The general lesson: *an archive existing is not the same as an archive being
> point-in-time — read the vendor's own timestamp before treating history as backtestable.*
> ECR is banked anyway (17,264 rows, 2017–2026 × 3 scorings, 99.2 % gsis) because it is free, deletable
> by the vendor, PIT-clean for **season-outcome** work, and **covers 2025 where FFC has nothing**.
> **⚠ 2023 PPR is flagged `is_preseason=False`** — `as_of = 2024-02-12`, re-touched after the Super Bowl,
> so it saw the season it should precede. Exclude it from any draft-season expert baseline.
> **Underdog is deferred, not attempted** (your decision): no keyless endpoint — marketing routes 404,
> board is a JS app on an unpublished API.
>
> **★ NEXT: Session G — apply the drift, 16.9–16.12 + 16.16**, under the constraint above. Then Session H
> (personalities 16.13–16.15) → I (Phase 17 formats) → K (Phase 14 app, strictly last).
>
> _(Prior pointer — history.)_ **★ (2026-07-25, SESSION E COMPLETE — the Phase-16 value-side track.)**
>
> **What closed this session:** the **user review gate** — `reference/coaches.csv` is **204 rows, all
> `confidence=high`**, fact-checked and signed off end to end (the edits were confidence-only, so 16.3b's
> machine audits stand) — and **16.4**, the last unbuilt substep.
>
> **16.4 (`situation/fingerprint.py`, `steps/phase16_4_fingerprint.py`) — descriptive only, as scoped.**
> 14 metrics per team-season, **z-scored within season** so league drift never reads as personality, pooled
> per play-caller and **EB-shrunk** by regime length (`k = σ²/τ²`). 41 play-callers / 64 spells / 169
> regime-seasons; all **17** transport teams resolve (12 own · 5 lineage · 0 silent); BAL/PHI/SEA report
> **both** priors (mentor lineage vs. outgoing caller). Decisions locked with the user: **no season cap**
> (2014–2025, lockbox years included, no provenance column — an initial DEV-cap answer was reversed),
> partial regimes cut to the weeks actually called, metrics extended with HHI/aDOT/pace, output at team and
> player grain, deltas + implied multiplier and **no points column**.
>
> **★ Two results worth carrying into any later phase that touches this:**
> 1. **The transport effect is small and mostly isn't the coach.** Only **20.9 %** of implied role-share
>    movement is the incoming play-caller; **79.1 %** is the incumbent slot regressing toward the league
>    mean, which any hire would produce. Every player row carries `reversion_pp` + `scheme_pp` — **never
>    surface `delta_pp` alone**, it overstates the phase ~5×.
> 2. **Trait portability is the real deliverable.** What a coach carries between jobs: `rz_pass_rate`
>    (k=1.7), `team_adot`/`plays_pg` (1.8), **`carry_hhi` (2.0)**. What he does **not**:
>    **`wr1_tgt_share` (k=17.9)** — the alpha receiver's target share is a **roster** fact. If a later phase
>    wants a "this coach will feed X" claim, the concentration and tempo traits support it; WR1 share doesn't.
>
> **★ Repo-wide lesson from a real bug here — `LA` vs `LAR`.** `pbp`/`weekly` write the Rams as `LA`,
> `reference/coaches.csv` as `LAR`, and 16.4's first run **silently deleted Sean McVay's entire nine-season
> tenure**, reporting it as an ordinary empty result. **A missing entity and a failed join look identical.**
> Route every cross-source team comparison through `adp.panel._canon_team`, and make "dropped with no stated
> reason" an assertion (`fingerprint.assert_regime_coverage`), not an empty row.
>
> **★ NEXT: Session F — data 0.11 (ECR + Underdog ADP ingest) + availability drift 16.7–16.8**
> (`adp/drift_panel.py` on the Sleeper human corpus, `adp/drift_model.py` consuming 16.1/16.2 features +
> the new ECR; walk-forward drift MAE/Spearman). **16.6 Beta Lab tab stays deferred to the Phase-14 app
> block.** Value-side reads as an honest null → Phase 16's edge is the availability side. Run the Stage-0
> chore first if the latest 2026 FFC snapshot is >6 days old.
>
> _(Prior pointer — history.)_ **★ (2026-07-25, SESSION E mid-flight — the review gate that is now closed.)**
> `reference/coaches.csv` was **204 rows**: the 32
> signed-off 2026 rows plus **172 Claude-researched historical rows (2014–2025)**. The historical half has
> **not** been reviewed, and **16.4 must not consume it until the user signs it off** — the same contract as
> the 2026 half. **The review surface is deliberately narrow: `offensive_coordinator`, `play_caller` and
> `hc_calls_plays` only.** `head_coach` is machine-audited against `pbp` (172 rows, **0 MISMATCH**) so it does
> not need human eyes. Sort by `confidence` — **25 `med` + 1 `low`** rows are where the doubt is concentrated;
> the 178 `high` rows were web-verified this session. Also awaiting review: **`reference/coach_lineage.csv`**
> (5 rows, new — see below).
>
> **★ 16.5 is now DERIVED, not researched (2026-07-25) — `reference/situation_events_2026.csv` is a
> GENERATED file: do not hand-edit rows.** Re-run `uv run python steps/phase16_5_situation_events.py
> --write`; research goes in that step's `ANNOTATIONS` block and is merged onto the derived rows. The
> hand-built 9-row version **missed 16 of the 23 team changes among draftable players** (incl. A.J. Brown
> PHI→NE at ADP 13.6) and had no row for the two highest-ADP players in the league. It is now **138 events
> over 30 teams**, dual-sourced (2026 `adp_snapshots` × `consensus_projections`, 0 disagreements) against
> 2025 `weekly`. **Its review surface is only `mechanism`/`confidence`/`notes` — 111 rows are still
> `mechanism=unknown`** (i.e. trade-vs-FA unresearched); every other column is machine-checked.
>
> **★ THEN, IN ORDER:** (1) build **16.4** on the reviewed table — scheme fingerprint + transport,
> `situation/fingerprint.py`, **descriptive-only, no FDR gate**; (2) **commit Session E**; (3) **Session F**
> (data 0.11 + drift 16.7–16.8). **16.6 tab stays deferred to the Phase-14 app block.**
>
> **★ What 16.4 is entitled to assume (consume via the API, do not re-derive):**
> - **The transport set is 17 teams, not the 13 the old pointer said** — `situation.coaches.new_regimes(df,
>   2026)` returns 13 `external` + **4 `internal_promotion`** (DEN, MIA, PHI, WAS). Deriving it from
>   `in_house==0` alone silently drops the promotions.
> - **★ Ask `coaches.fingerprint_source(df, 2026)` what to fingerprint each team on — do not work this out
>   from `coverage()` alone.** It returns `own` / `lineage` / `none` per team. Currently **12 own · 5 lineage
>   · 0 none**, i.e. **all 17 transport teams are covered**.
> - **The lineage fallback (user direction, 2026-07-25) replaced the earlier "say nothing" plan.** BAL, DEN,
>   PHI, SEA and WAS have genuinely FIRST-TIME play-callers (Doyle, Webb, Mannion, Fleury, Blough), but a
>   first-timer is not a blank — they came up inside somebody's system, so fall back to **that mentor's**
>   regimes and tag the evidence as weaker. `reference/coach_lineage.csv` names the mentor; every mentor is
>   itself a play-caller in `coaches.csv` (a gate asserts it), so the fallback always lands on a real
>   fingerprint. Doyle→Ben Johnson (CHI 2025), Webb→Sean Payton, Mannion→Matt LaFleur (GB), Fleury→Kyle
>   Shanahan (SF), Blough→Kliff Kingsbury. **Sean Payton (NO 2014–21, DEN 2023–25) and Kliff Kingsbury (ARI
>   2019–22, WAS 2024–25) were added to `coaches.csv` purely to make their mentees fingerprint-able.**
> - **Where lineage and team continuity disagree, 16.4 owes BOTH readings** — `same_team` marks the cases
>   where they coincide (DEN, WAS: same-team promotions, the strongest form). They **disagree at BAL**
>   (lineage Ben Johnson vs 2025 Monken), **PHI** (Matt LaFleur vs Patullo) and **SEA** (Shanahan vs Kubiak);
>   `prev_play_caller` carries the continuity side. Report both, do not pick silently.
> - **Regime grain:** `coaches.playcaller_regimes()` — a contiguous `(play_caller, team)` spell, with returns
>   split into separate spells. 70 regimes / 43 play-callers / 172 team-seasons; median 4 prior seasons for a
>   2026 play-caller (was ~1).
> - **Most prior regimes sit in 2023–2025** (Petzing/ARI, Monken/BAL, Slowik/HOU, Caley/HOU, Kubiak/SEA …),
>   i.e. **lockbox + calibration seasons**. The *names* are not outcome data, but 16.4's fingerprints are
>   built from realized role-shares — **decide explicitly how to treat 2023–24 before computing them**, and
>   note that the lockbox was already spent once in Session D and the value stack is frozen.
>
> **★ Decisions locked (do not re-litigate):** 16.3 signs off at **`confidence=high`** (2026-07-24) · 16.4
> gets the **full historical build** · schema **drops `change_from_prev`, keeps `in_house`** · research scope
> = **targeted** (the 23 uncovered play-callers' prior regimes, not a full staff history) · verification =
> **web-verify + move-graph** (2026-07-25).
>
> **★ Carry-forward caveats:**
> - **Three aggregates in the 2026 table were never externally verified** and the user signed off knowing it:
>   **10 new head coaches**, **McDaniel leaving the MIA HC job to be LAC's OC**, **56 % of HCs calling plays**
>   (18/32). Internal consistency ≠ factual accuracy — label 16.4 output accordingly.
> - **`pbp`'s coach field is game-level only through 2023.** From **2024** it is a season-level *coach of
>   record* (Dennis Allen shows for all 17 of NO 2024, Daboll for all 17 of NYG 2025, both fired in-season),
>   so `head_coach_scaffold()`'s `interim` column is a **lower bound** on mid-season changes. Fine for the
>   audit; not a source for "who was fired when" in 2024–25.
>
> **Useful method (reused, worked twice):** the **move-graph cross-reference** — each "X departs" must match
> an "X arrives", nobody holds two jobs in a season, a continuity flag must agree with the table's own
> history, and a spell must have no one-season holes. Zero external lookups. `coaches.move_graph_check()`
> grades findings `HARD:` / `check:` / `note:`; the merged table returns **12 findings, 0 HARD**.
>
> **Stage-0 chore: DONE 2026-07-24** (FFC 2026 snapshot banked, 6 configs, 1,202 rows, gsis 99.3 %, PASS;
> `backup_db.py` verified). Next due after **2026-07-30**.
>
> _(Prior pointer — history.)_ **★ Next-session pointer (2026-07-24, SESSION E IN PROGRESS — value-side situation track is an honest
> NULL; at the 16.3 review gate).** Completed T10 + Phase-16 value-side 16.1–16.2; drafted the 16.3/16.5
> CSVs; **16.4 is gated on the user reviewing `reference/coaches.csv`.** **NOT committed — left for user.**
> 316 tests (was 311), ruff clean; DEV-only, lockbox untouched, walled off from the frozen cost report.
> - **T10 ☑** — `validate_archetypes` prices the S6 `adaptive` archetype **per parent** (`adaptive(zero_rb)`
>   …); `steps/spine_4_validate.py` green.
> - **16.1 ☑ (NULL)** — `team_changed` (−2.5 VOR/SD, p_fdr 0.82) + `new_starting_qb` (−0.1, p_fdr 0.98) both
>   ruled out. **PIT catch:** the `adp_snapshots.team` column leaks an end-of-season crosswalk (Sep-1 2022
>   board lists mid-season trades McCaffrey→SF etc.) → team-of-record derived from `weekly` Week-1 instead.
> - **16.2 ☑ (BOTH WASH OUT)** — `competition_change_roster` (−9.9) and `competition_change_depth` (+9.8)
>   flip sign, neither survives FDR (p_fdr 0.087) → echoes Phase 12.3. Depth uses `depth_charts` (2014–24),
>   not `depth_charts_ts` (2025-only).
> - **Wall-off:** `FEATURES` pinned (5-trait softness model); situation flags in `SITUATION_FEATURES` /
>   `PHASE16_FEATURES`, mined only by `steps/phase16_1_*` / `phase16_2_*`. Phase-6 drift check reproduces
>   frozen `DURABILITY` +14.6 — cost report untouched.
> - **16.3/16.5 DRAFTED, awaiting review:** `reference/coaches.csv` + `reference/situation_events_2026.csv`,
>   both with a `confidence` column. **2026 web data was contradictory (esp. head coaches) — those rows are
>   flagged low/VERIFY.** **★ RESUME: user reviews/corrects `reference/coaches.csv` → then build 16.4 (scheme
>   fingerprint, `situation/fingerprint.py`, descriptive-only) → 16.6 tab defers to Phase 14.** Then Session F
>   (data 0.11 + drift 16.7–16.8). Value-side null means Phase 16's edge is the availability side.
>
> _(Prior pointer — history.)_ **★ Next-session pointer (2026-07-19, SESSION D COMPLETE — the engine is FINAL and the lockbox is spent).**
> Session D closed the pre-app pipeline: **(1) the optional MCTS research gate — BUILT & DROPPED** (user chose
> to build the benchmark; a determinized-UCT beats the greedy in-objective Δ CE +77 but not on realized OOS
> points Δ +32 CI∋0 at 8.5 s/pick → greedy stays the policy; CFR/self-play-RL stay out; `draft/mcts.py`,
> `steps/phase11_2_mcts.py`); **(2) T5 pre-registration** of the exact frozen stack + metrics + the ≈35–40
> DEV-decision count (`PLAN.md` §"⭐ T5 PRE-REGISTRATION"), committed **before** the eval; **(3) the LOCKBOX
> EVAL — spent EXACTLY ONCE** on 2023+2024 (`steps/lockbox_eval.py`, `analysis/lockbox_eval.json`,
> `findings.md` §"LOCKBOX EVALUATION"). **Result, as-is: the honest-value claims GENERALISE OOS** — title
> Brier **0.088 < 0.09** (championship calibration holds ≈ DEV), conditional coverage **80.1 %**, projection
> Spearman **0.54**, cheap personalization; **known level-optimism / unconditional-attrition limitation
> persists** (bias 0.62, uncond 72 %, marginal playoff Brier 0.240). **The modeling stack is FROZEN — nothing
> changes model-side on the basis of this result.** **★ WHAT'S NEXT (revised 2026-07-19): Session E = Phase
> 16 — Situation-Change Beta Lab** (new, non-core research track, user request — mine whether ADP misprices
> "changed situation" events: team change, QB change, teammate competition change, coaching/scheme change;
> ship as a walled-off, read-only tab, never wired into the frozen optimizer/VBD/cost-report). **Scoped, not
> yet built** — 4 scoping questions answered 2026-07-19 (`PLAN.md`): competition-change is **dual-sourced**
> (roster-turnover-derived + depth-chart-derived, compared, since the depth-chart source already failed once
> in Phase 12.3); the coaching/playcaller history table is **Claude-drafted via web research, user-reviewed
> before use** (no free source exists); the scheme-fingerprint/transport piece ships **descriptive-only,
> explicitly unvalidated** (thin sample, no FDR gate); **this year's (2026) real situation-change events are
> populated now**, not deferred. Substeps 16.1–16.6 in `PROJECT.md` §5 / `ROADMAP.md`. **★ EXPANDED
> 2026-07-23 — Phase 16 now has a second, AVAILABILITY-SIDE track (substeps 16.7–16.12):** where 16.1–16.6
> ask "does a changed situation make a player *out-earn* ADP?", 16.7–16.12 ask the sibling "does narrative/
> situation make a player *drafted earlier* than ADP (draft-slot **drift**)?" — the fix for the user's UX
> failure (a target falls in 10 mock drafts, then gets sniped in the real draft). It **extends the
> availability/opponent model** (`draft/opponent_model.py`, `draft/availability.py`, `draft/simulator.py`),
> which is **already OUTSIDE the value lockbox** (predicts draft flow, walk-forward-scored) — so it doesn't
> spend/contaminate the frozen value eval. 4 decisions (user 2026-07-23): fold into Phase 16 · walk-forward +
> own held-out metric (momentum live-only on 2026 — no historical intra-season ADP series) · a curated
> `reference/hype_board.csv` override · BOTH realism (mocks) + advice (9.4 lookahead) + honest `P(available)`.
> Substeps: 16.7 drift panel (`adp/drift_panel.py`) · 16.8 drift model (`adp/drift_model.py`) · 16.9
> correlated per-draft narrative shock · 16.10 hype board (`adp/hype_board.py`) · 16.11 live momentum
> (`adp/momentum.py`) · 16.12 consumption. **★ ALSO ADDED 2026-07-23 — opponent-personality set (16.13–16.15),
> folded into the same availability track:** heterogeneous mock-draft opponents extending the existing
> `draft/personalities.py` (Phase 11.3, which already has 6 ADP/behavioral tilts but none on risk/value). The
> **5 headliners**: Autopilot (deterministic ADP autopick), Balanced, Upside Chaser (boom/q90), Safe/Floor
> (q10/durability), Homer/Narrative-Chaser (fandom + hype board — the seat the 16.9 shock rides). Decisions
> (user 2026-07-23): BPA = **ADP autopilot only** (no value-board opponent) · **enrich the sim board with the
> real frozen Phase-5 dist + value_board fields** (read-only) · validation = **face-validity + unit-tested
> mechanics** (no Brier gate). 16.13 board enrichment · 16.14 the personalities · 16.15 mock-room composition
> + hype coupling + app selector. Full scope: `PLAN.md` 2026-07-23 (personalities) + `PROJECT.md` §5 /
> `BUILD_PLAN.md`. Still awaiting
> go-ahead to build.
> **★★ BACKLOG EXPANDED + FULL SESSION RE-ORDER (2026-07-23) — the current source of truth for what's next.**
> User added 10 broadly-useful "better for all users" items (explicitly NOT anything personal to the user —
> league-mate/self models were excluded). **New Phase 17 — League-Format Fidelity** (superflex/multi-flex/
> custom-scoring/**platform-agnostic manual settings form**/keeper — correct advice for ANY league; a config
> generalization, NOT a modeling change; non-default formats labeled not-lockbox-validated). **New data 0.11**
> (ECR + Underdog ADP → feeds 16.8). **New 16.16** (live run-detection). **New Phase-14 surfacing 14.E–14.I**
> (tier-cliff / roster-risk / uncertainty / playoff-SOS / draft-grade — all read frozen machinery). Decisions
> (user 2026-07-23): new Phase 17 + distribute the rest · **app strictly last** (all UI/tabs/surfacing → Phase
> 14) · same ~1.5–2.2k one-concept sessions · **dependency-optimal order**. **★ THE SESSION PLAN (full detail
> in `ROADMAP.md` ★ SESSION PLAN): E** Phase-16 value-side 16.1–16.5 (+T10 warm-up; 16.6 tab→app) — **RESUME
> HERE** · **F** data 0.11 + drift 16.7–16.8 · **G** apply drift 16.9–16.12 + 16.16 · **H** personalities
> 16.13–16.15 · **I** Phase 17 formats 17.1–17.4 · **J** (optional) dynasty 15.1 · **K** Phase 14.1 MVP + all
> surfacing (do not bundle) · **L+** Phase 14 go-live tail. Lead pinned by: 16.8 reuses 16.1/16.2 features;
> 0.11 feeds 16.8. Scoping in `PLAN.md` (2026-07-23 backlog-expansion entry) + `PROJECT.md` §5 + `BUILD_PLAN.md`.
> **Prior pointer (Session E = Phase 16) still valid — value-side is the lead; the plan just now spells out E→L+.**
> **App-UI spec added 2026-07-23:
> `docs/PLAYER-VIEW.md`** — the interactive player card (hover → 5-bar overview) + per-player deep page
> (click → all 8 bars); quasi-bars over frozen contracts, green=good, dual-baseline (overall + within-pos),
> the Phase-16 situation bar walled-off + tagged unvalidated. Its **one gating dependency is bar #6 →
> Phase 16** (a further reason 16 goes next); it lands in the Next.js frontend at **14.3**, fed by a
> per-player endpoint at **14.1**. See `PLAN.md` 2026-07-23. Two commits landed locally
> (`7bd6e10` freeze, then the lockbox-result commit) — **not pushed** (user's review-then-push habit).
> Opportunistic tech-debt left: **T10** (the S6 `adaptive` archetype crashes
> `spine_4_validate`/`validate_archetypes` — worked around in the lockbox harness; fix before re-running the
> DEV cost-report — now folded into Session E as a warm-up). Run the Stage-0 FFC snapshot chore if >6 days
> stale (§2). **Resume: Session E = Phase 16 value-side 16.1–16.5 + T10 (awaiting user go-ahead to start
> coding). Full E→L+ ordering in `ROADMAP.md` ★ SESSION PLAN.**
>
> _(Prior pointer — history.)_ **★ Next-session pointer (2026-07-13, SESSION C COMPLETE — not yet committed, left for user review).**
> **Session C = Phase 12 news/NLP + Phase 15 multi-format/auction — all done-bars PASS, ruff clean, 306
> tests (was 276; +19 `test_news`, +11 `test_phase15`).** Ran the overdue Stage-0 FFC snapshot chore first.
> **Phase 12 = a qualified KEEP:** the injury signal is real (exploitable lag +5.86 pts/start sig → the
> news-aware weekly forecast beats injury-blind 13.1 **+3.4→4.3 pts/pw on the designated subset, 6/6 DEV**),
> the depth-chart signal a DROP (no separation). LLM edge-only via a **gated `ClaudeClient`** (Haiku 4.5,
> behind `ANTHROPIC_API_KEY`); the deterministic **rules** extractor is the default and the core prices the
> signal — the guardrail literalized. `news/{sources,extract,event_study,validate}.py`; `steps/phase12_*`.
> **Phase 15:** 15.4 auction (`draft/auction.py` — budget-state bidder beats naive 6/6; **T9 discharged**,
> `faab_bid` consumes `endgame_cap`), 15.2 best-ball (`formats/bestball.py` — **variance-is-good**, ceiling
> beats mean 6/6; **weekly** CoV not season sd), 15.3 DFS GPP (`formats/dfs.py` — leverage beats chalk 6/6
> via duplication/prize-splitting, **MECHANICS only — no free DFS salary/ownership feed**). 15.1 dynasty
> deferred (user scope). **What's next: Session D = optional MCTS/RL research gate (explicit decision) → T5
> pre-registration (the only open pre-lockbox tech-debt) → the single LOCKBOX EVAL on 2023+2024 → then Phase
> 14 the app.** Analysis JSON: `analysis/phase12_*`, `analysis/phase15_*`. **Resume: commit Session C.**
>
> _(Prior pointers, kept as history.)_ **SESSION A ☑ COMPLETE** (S6 + 13.1 + 13.2,
> committed `87e6bae`). **SESSION B ☑ COMPLETE — 13.3 + 13.4 + 13.5 all DONE → Phase 13 / S7 COMPLETE.**
> **276 tests, ruff clean; 13.3 committed; 13.4 + 13.5 NOT yet committed — left for user review.** Lockbox
> (2023+24) untouched;
> DEV-only (2017–22 validation window). Session-A recap (S6 fade-melt archetype; 13.1 Kalman re-projection;
> 13.2 co-pilot start/sit + the variance-tilt "kept-not-default" finding):
> - **S6 adaptive archetypes** (`draft/config.py` `"adaptive"` + `_adaptive_tilt`; `steps/spine_5_adaptive.py`)
>   — a wrapper that **melts a static parent's *fade* by how far a candidate has slid off ADP** (`ADAPT_DECAY`,
>   `ADAPT_SLIDE_WEIGHT`; sliding value melts ~2× a reach; reaches untouched; no board context ⇒ = parent).
>   **Does no harm on an ADP board, banks team-value when the board breaks** (adaptive(zero_rb) +2.0,
>   adaptive(hero_rb) +15.6 in the realistic Phase-11 behavioral room).
> - **13.1 weekly re-projection** (`inseason/reproject.py`; `steps/phase13_1_reproject.py`) — a scalar
>   **Kalman** on each player's per-week level; **PIT**; a **reserved Phase-12 `news` slot** (no-op default,
>   so Phase-12 plugs in without a rebuild). **Beats static preseason OOS 6/6 seasons, +0.396 ppg/wk (CI
>   [+0.32,+0.48]).**
> - **13.2 start/sit** (`inseason/lineup.py`; `steps/phase13_2_lineup.py`) — **co-pilot done-bar PASS**:
>   mean-max on 13.1's re-projected means beats set-and-forget on realized points 6/6, **+2.08 pts/lineup-week**
>   (CI[+1.56,+2.54]). **FINDING:** the win-prob **variance tilt does NOT beat mean-max even for big underdogs**
>   (0/6; a single legal swap barely moves the ~35-pt team sd — cf. Phase-10.3 whole-team-only leverage), so
>   `optimal_lineup` default is now `objective="mean"`; the tilt is kept **opt-in** `objective="win"`, off by
>   default (the Phase-7 / props "kept, not the default" pattern).
> - **13.3 waivers/FAAB ☑** (`inseason/waivers.py`; `steps/phase13_3_waivers.py`) — pure `faab_bid` =
>   **marginal value** (rest-of-season over replacement, from 13.1) → `value_scale` willingness-to-pay,
>   **rationed** by the option value of budget `1/(1+κ·(weeks−1))`, **first-price shaded** vs a belief about
>   the field. **Beats naive %-of-budget 5/6 DEV** in a **mixed-field** sim (mean +30.0 value/szn, CI
>   [+21.7,+38.8]). **KEY FINDING:** the sim needs **diminishing returns** — score only a team's **top-4**
>   pickups + bid marginal-over-roster — or it rewards *volume* and naive aggression wins (0/6 → 5/6).
>   **DECISIONS (user, upfront):** *pragmatic now* (11.4/auction was deferred to 15.4, `draft/auction.py`
>   doesn't exist → rigor owed as **TECH-DEBT T9**); *mixed field* (sharp vs naive + alternating).
> - **13.4 streaming ☑** (`inseason/streaming.py`; `steps/phase13_4_streaming.py`) — pure, position-agnostic
>   `stream_pick`: a **contextual bandit** over the waiver pool = greedy exploit on `matchup_projection = own +
>   (opp_allow − league_mean)` (both empirical-Bayes shrunk toward the prior season, `PRIOR_GAMES=4`), with a
>   **switch-margin hysteresis** (`SWITCH_MARGIN=1.0`; UCB explore off by default). **Demonstrated on DST**:
>   matchup-streaming beats **static-hold 6/6 DEV, +1.46 pts/wk (CI[+0.88,+2.09])**, and beats a
>   **random-streaming** control 5/6 — so the *matchup signal*, not just the churn, pays (the 13.3 anti-churn
>   lesson: switch cost + random control). **Scope:** DST demo; `stream_pick` position-agnostic (QB/TE feed
>   13.1 means as `proj`) — documented extension, not built.
> - **13.5 trades ☑** (`inseason/trades.py`; `steps/phase13_5_trades.py`) — the **market-maker**. Three pure
>   kernels: `lineup_value` (a roster's value = its optimal starting-lineup sum only — reuses the 13.2 `_fill`;
>   the diminishing-returns lesson made positional), `evaluate_trade` (a swap's *change* in each side's
>   `lineup_value`; `mutual` iff both gain > `ACCEPT_MARGIN=5`), `find_trades` (searches every opponent's
>   surplus `_benched` for mutual **1-for-1 / 2-for-1** legal deals arbitraging complementary positional
>   surpluses, ranked by the **worse-off side's** gain `min(mine, theirs)`, with a sell-high/buy-low `market`
>   tilt). Done-bar via the **Phase-10 MC season sim**: proposed trades **raise both teams' playoff prob 6/6
>   DEV** (maker season-block CI **[+0.014,+0.021]**, partner **[+0.012,+0.021]**) vs a **random-trade** control
>   that lifts both ~never. **KEY CORRECTION:** ranking by the *maker's own* gain only cleared a marginal
>   partner floor (worse side died in MC noise) → rank by `min(maker, partner)` so the objective rewards
>   *mutual* benefit. **Scope:** value = preseason model ros mean (self-consistent → PIT-trivial); in-season
>   this `values` slot is 13.1's re-projected mean. Sim trades 1-for-1; 2-for-1 kernel-supported + unit-tested.
> **What's next (THE PIPELINE):** **Sessions A/B/C done → Phases 12, 13/S7, 15 (core) COMPLETE; T9 ☑.**
> Next = **Session D = optional MCTS/RL research gate (explicit decision) + T5 pre-registration + the single
> LOCKBOX EVAL on 2023+2024**, then **Session E = Phase 14.1** (Streamlit MVP) and **F+ = the go-live tail**.
> **T5** pre-registration (freeze the stack; T3/T4/T9 already ☑) is the **only open pre-lockbox item**, and
> must run strictly last among build steps. Corpus can be grown anytime via `reference/sleeper_seeds.txt` +
> `steps/phase0_10b_crawl.py`; `docs/SLEEPER.md`. **Resume here: commit Session C, then Session D.** (Full
> session-sizing guide in `ROADMAP.md`.)

## 4. Watch out for
- **Look-ahead via "current" snapshots.** End-of-season stats, final ADP, injury outcomes — never let them
  leak into a historical as-of step.
- **Survivorship** — panels of "players who stayed relevant" flatter results. Document it as a limitation.
- **Overfitting the tiny sample** (~3,750 player-seasons). Stay in regularized-linear / GBT / hierarchical-
  Bayes territory; **no deep nets**. Correct for multiple testing when mining ADP biases.
- **Personalization baking in bias.** Always show personalized boards next to the pure-projection baseline;
  treat large divergences as hypotheses to test, not preferences to lock in.
- **PIT-clean ≠ out-of-sample-clean (the lockbox rule, ⟳ 2026-07-04).** PIT stops temporal leakage, not
  overfitting from repeatedly selecting on the same ~10 seasons. **Lockbox = 2023 + 2024** (frozen; set
  2026-07-04): never touch it during development / feature+model selection; evaluate the final chosen
  stack there **exactly once**. All development runs on **`config.DEV_SEASONS` = 2014–2022**; only the
  final eval reads `config.LOCKBOX_SEASONS`. (**2025** is out of the *draft-backtest* lockbox because there
  is **no 2025 ADP board** — FFC empty; source via Sleeper later. Its realized weekly/seasonal *are*
  recoverable via the new nflverse `stats_player` release — **step 0.9** — so once ingested, 2025 serves as
  a **projection-calibration holdout** and upgrades to a full backtest season when ADP lands. `findings.md` 2026-07-04.)
- **No LLM in the core (⟳ 2026-07-04; timing amended 2026-07-09).** The deterministic core never depends
  on an LLM. Phase 12 (news/NLP) is now **in the pre-app pipeline** (ROADMAP ★ THE PIPELINE, stage 7 — no
  longer "post-MVP"), but the guardrail is unchanged: AI lives **on the edges** (fuzzy input → validated
  object, or numbers → narrative) — it never computes a number that must be correct.
- **Own the contracts.** The human owns the data contracts between components (the `DraftConfig` constraint
  object, the projection output shape); delegate the interiors. Contracts drift silently if the AI owns them.

## 5. Structure map (one focused file per aspect — the AlphaThena methodology)
Each step in `PROJECT.md` §5 lands in its **own module** (mirroring the intern repo's separate files for
wash-sales / rebalancing / construction). Packages beyond the current eight are **created as we reach their
phase** — do not pre-create empty trees.

| Concern | Package | Status |
|---|---|---|
| Data ingest (nflverse/PFR/ADP) + DuckDB panel + validation | `src/fantasy_quant/data/` | exists |
| **Vegas markets** (odds ingest, de-vig, props projection) | `src/fantasy_quant/markets/` | exists |
| **News/NLP** ingest + LLM extraction + event studies | `src/fantasy_quant/news/` | exists |
| Feature/exposure engineering (`X`) | `src/fantasy_quant/features/` | exists |
| Projections (baseline, GBT, age curves, hier-Bayes, quantile, conformal, injury) | `src/fantasy_quant/projections/` | exists |
| **Causal** player-in-system (decompose, counterfactual, transport) | `src/fantasy_quant/causal/` | planned |
| Player-week covariance + shrinkage + copulas | `src/fantasy_quant/covariance/` | exists |
| Valuation (VBD, conditional-VBD, structural-alpha, utility, objective, handcuff) | `src/fantasy_quant/valuation/` | exists |
| Draft (simulator, greedy policy, opponent model, MCTS, CFR, auction) | `src/fantasy_quant/draft/` | exists |
| Season/playoff **simulation** + leverage | `src/fantasy_quant/simulation/` | exists |
| **In-season** co-pilot (re-project, lineup, waivers, streaming, trades) | `src/fantasy_quant/inseason/` | exists |
| PIT walk-forward **backtest** harness + metrics + significance | `src/fantasy_quant/backtest/` | exists |
| **ADP-bias mining** | `src/fantasy_quant/adp/` | exists |
| The **app** (FastAPI backend, Next.js frontend, widget) | `src/fantasy_quant/app/` (+ `app/frontend`) | planned |
| Multi-format (dynasty/best-ball/DFS) + auction | `src/fantasy_quant/formats/`, `draft/auction.py` | exists (best-ball/DFS/auction; dynasty roadmap) |
| Phased runnable scripts (one per step) | `steps/` | exists |
| Results / scorecards | `analysis/` | exists |

## 6. Do not
- Do **not** install into system Python or the intern-repo venv. Use this project's `uv`/`.venv` only.
- Do **not** evaluate a method on in-sample fit or a single season.
- Do **not** commit data artifacts (gitignored) or secrets (`.env`).
