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

> **★★ Next-session pointer (2026-07-25, ★ SESSION F.5 COMPLETE — corpus expansion. RESUME AT
> SESSION F.6, *then* G.) READ THIS FIRST — it is written to resume cold.**
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
