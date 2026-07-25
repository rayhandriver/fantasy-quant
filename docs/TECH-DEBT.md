# TECH-DEBT.md — known problems & the exact plan to fix each (the remediation register)

The durable, dated register of every known problem in the engine and **exactly what to do about it in
the long run**. Opened after a full-codebase audit (2026-07-10). One entry per problem, stable id
`T1…T9`, newest facts appended in place. This is the "what do we still have to fix" source of truth;
`ROADMAP.md ★ THE PIPELINE` sequences these against the phase build, `PLAN.md` logs the work as it's done.

**Severity:** 🔴 loss/operational (fix now) · 🟠 validity (fix before the lockbox eval) · 🟡 quality (opportunistic).
**Status:** ☐ open · ◐ in progress · ☑ done · ✗ won't-fix.

At a glance:

| id | 🔺 | problem | when | status |
|----|----|---------|------|--------|
| **T1** | 🔴 | Phase 10 + Stage 0 work uncommitted | now | ☑ |
| **T2** | 🔴 | Irreplaceable data (2026 ADP series, 2025 backfill) has no backup | now | ☑ |
| **T3** | 🟠 | Downside under-modeled — unconditional coverage 44 % / points coverage 62 % | before lockbox | ☑ |
| **T4** | 🟠 | Season-sim level bias −137 pts/team/season | before lockbox (with T3) | ☑ |
| **T5** | 🟠 | Lockbox is a one-shot; researcher-degrees-of-freedom accumulating on DEV | pre-register right before lockbox | ☑ |
| **T6** | 🟡 | Monte-Carlo draws recomputed / silently diverge across consumers | with Phase 9.5 | ☑ |
| **T7** | 🟡 | External scrapes (FantasyPros/FFC) fail silently; props layer a no-op | opportunistic | ☑ |
| **T8** | 🟡 | `objective` a dead label (**8a ☑**); opponent model still ADP+noise (**8b: ingest+crawler+real corpus ☑, fit ☑**) | 9.5 done / fit done | ◐→☑ |
| **T9** | 🟡 | Phase 13.3 FAAB bidder is the **pragmatic** heuristic; rigorous auction theory deferred | Phase 15.4 (auction support) | ☑ |
| **T10** | ✅ | `validate_archetypes`/`spine_4_validate` sweep S6's `adaptive` archetype → crash (needs `adaptive_parent`) | opportunistic (post-lockbox) | ☑ 2026-07-24 |

---

## 🔴 T1 — Commit the Phase 10 + Stage 0 session
**Status ☐ · do now (minutes).**

**Symptom.** `git status` shows 16 changed/untracked files — the entire `simulation/` package (Phase 10),
both `steps/stage0_*.py`, `tests/test_phase10.py`, `tests/test_stage0.py`, the `distribution.py`/`adp.py`
edits, the doc updates, and `analysis/results/sleeper_probe.json` — all uncommitted. A full session's output
exists only in the working tree. 194 tests pass, ruff clean; there is no reason to hold it.

**Fix.**
1. Inspect `analysis/results/sleeper_probe.json` (`git diff --cached` it) — confirm no private
   username/league identifiers before it goes in git.
2. `git add` the simulation package, both stage-0 scripts, the two test files, the `distribution.py` +
   `adp.py` edits, `steps/README.md`, the doc set, and the probe json; commit
   (`"Phase 10 (season/playoff sim + leverage) + Stage 0 (2026 ADP snapshots, Sleeper probe)"`); push.
3. Keep the `.duckdb`/parquet artifacts out (already gitignored — verify they're not staged).

**Done-when.** `git status` clean; `origin/main` has the Phase 10 + Stage 0 commit.

---

## 🔴 T2 — Back up the irreplaceable data
**Status ☑ done (2026-07-10) — layers 1 & 2 shipped; layer 3 (git-LFS) left as an optional stretch.**

**Done (2026-07-10).** Added `steps/backup_db.py` (idempotent, checksum-verifying) and ran it: the 6 live
2026 FFC snapshot parquets + the 3 2025 `stats_player` backfill parquets + a date-stamped full `.duckdb`
dump (295 MB) now live off the WSL disk at `/mnt/c/Users/rayha/fantasy-quant-backup/`, all md5-verified
byte-identical to source. Wired into the weekly Stage-0 chore (CLAUDE.md §2). **Remaining optional:** layer
3 — put `data/raw/adp/snapshots/` under git-LFS for automatic versioned history (removes the manual step).

<details><summary>Original plan (kept for the record)</summary>

**Symptom.** `data/fantasy_quant.duckdb` (309 MB) and `data/raw/adp/snapshots/*.parquet` (6 banked) are
gitignored and live only on this WSL ext4 disk. Two assets in them are **not reproducible**: the **live
2026 FFC ADP snapshot series** (Stage 0's whole point — "unrecoverable later") and the **2025 nflverse
`stats_player` backfill** (the old frozen `nfl_data_py` path is dead — a 404). A disk/WSL loss wipes exactly
what we spent sessions to capture.

**Fix (layered — cheap first).**
1. **Immediate off-disk copy of the crown jewels** (tiny): copy `data/raw/adp/snapshots/*.parquet` to the
   Windows side, e.g. `/mnt/c/Users/rayha/fantasy-quant-backup/adp-snapshots/`. These are the
   replay-idempotent source of truth — the ingest self-heals from them.
2. **Periodic full-DB dump.** Add `steps/backup_db.py` (or a make target) copying the `.duckdb` to a
   timestamped file on `/mnt/c/...` or a cloud-synced folder. Hang it off the existing weekly Stage-0 chore
   (after each snapshot pull, dump the DB).
3. **Structural (recommended).** Put **just** `data/raw/adp/snapshots/` under **git-LFS** (or a private
   second repo) — a few KB per snapshot, fully versioned, no 309 MB bloat. Turns "back up sometime" into
   automatic history and removes the manual step.

**Done-when.** The 2026 snapshot parquets + a recent `.duckdb` exist off the WSL disk; the weekly chore
refreshes the backup; (stretch) snapshots are version-controlled.

</details>

---

## 🟠 T3 — Fix the under-modeled downside (unconditional coverage 44 %, points coverage 62 %)
**Status ☑ done (2026-07-11).** **2025 holdout (read once): unconditional coverage 44 % → 77 %,
conditional 76 % → 76 % (held); Phase-10 team-points coverage 62 % → 77 %.** DEV: uncond 39 % → 70 %,
cond 79 % → 75 %. 2025 is the calibration holdout (not the lockbox) — tuned only on DEV, read once.

**What shipped, and how it diverged from this plan.** Attribution first (`findings.md` 2026-07-11): 31 % of
board players realize below their own q10 and **~95 % of those barely played** (realized ≈ 0), so the
dominant unconditional miss is **availability / roster-security** (a projected body who never plays), not
the "plays-but-produces-less" case Root-cause-B's production haircut targeted.
- **A — cohort availability prior** (`injury.cohort_availability_prior`) — the **main lever** (uncond
  39 %→63 % alone). Routes the sub-`prior_games≥8` cohort to a `(pos × draft-capital tier)` prior for both
  `avail_p` and `rho` (hi-capital rookie RB plays 0.67 of games vs lo-capital 0.42; fat `rho` 0.37+ vs the
  0.15 shared fallback). Wired into `distribution.assemble_distribution` (replaces the median fallback).
- **B — role-loss WASHOUT mixture** (`injury.role_retention` + `distribution.sample_player_season`), the
  reformulation. The planned production haircut `Y=H·(G/G_ref)·R` added ~0 coverage and dropped conditional
  to ~72 %; role loss instead acts through the **availability channel** — a tier-specific washout rate
  `p_crater` (played < 40 % of games) draws games from a low `crater_avail` (≈0.15) *replacing* the hazard
  branch (injury never double-counted), applied to **established, deep-projected** players only (elite/starter
  washouts are injury, already in `G`). `covariance/estimate.role_ranks` reuse was **not** needed — role
  tiers key on projection rank vs the startable/replacement rank (`injury.role_tier`), simpler and PIT.
- Guard held: conditional coverage stayed in band (76 % holdout / 75 % DEV) and title Brier is unbroken.
- New unit tests in `tests/test_phase5.py` (capital/role tiers, backoff, washout left-tail widening);
  `steps/phase5_4_injury.py` extended with the T3 done-bar (cohort + washout assertions).

<details><summary>Original plan (kept for the record — Root-cause-B was overturned by the DEV diagnosis)</summary>

**Symptom.** Phase 5 unconditional 80 %-interval coverage = **44 %** (target 80 %); Phase 10 team-points
coverage = **62.4 %**. Distributions are too narrow on the draft-day (unconditional) axis; rank calibration
is fine (Spearman ≈ 0.57, title Brier 0.088) — it's the **level and left tail** that leak. Two independent
root causes.

**Root cause A — the availability universe excludes the volatile players.**
`injury.availability_frame` (`src/fantasy_quant/projections/injury.py:87`, gate `prior_games ≥ 8`) drops
rookies, second-year players, and anyone without a full prior season to a single median-availability
fallback; `availability_projection` (`injury.py:213`) then attaches **one shared `rho`** to every row. The
highest-attrition-variance cohort is modeled with the least specificity.

**Root cause B — role/depth attrition isn't modeled at all.** A projected WR2 benched to WR4 by October has
full "availability" (he plays) but craters — nothing captures this. It is the dominant *unconditional* miss.
The sample model is `Y = H·(G/G_ref)` (`distribution.py`) — injury only, no role term.

**Fix.**
1. **Cohort availability prior (A).** In `availability_frame`, route the `< min_prior_games` rows to a
   separate estimator keyed on `(pos, draft_capital/age)` instead of dropping them; draw both the fallback
   `avail_p` **and its dispersion `rho`** from that cohort (rookie RBs have fatter lost-season tails than the
   league median). Keep the established-contributor hazard as-is.
2. **Role-survival haircut (B) — the higher-value half.** Add `injury.role_retention(con, season)` →
   per-player `P(keeps ≥ projected role)` + a downside points-fraction if not, estimated on DEV seasons from
   realized role-rank transitions. **Reuse `covariance/estimate.py:role_ranks` (`:72`)** — do not rebuild
   role logic. Fold a third factor into `distribution.sample_player_season`:
   `Y = H·(G/G_ref)·R`, `R` a Bernoulli mixture (in-role → 1; lost-role → cohort downside fraction). This
   widens the **left tail specifically**, where the coverage leaks.

**Done-when.** Re-run the Phase-5 conformal coverage check and the Phase-10 gate: unconditional coverage
44 % → **≥ 70 %**, points coverage 62 % → **≥ 75 %**, **without** breaking conditional 76 % or title Brier
0.088. Guard against over-widening — if conditional coverage overshoots 80 %, back the haircut off.

**Effort.** A real 1–2 session phase. Highest-value modeling fix; strengthens every downstream probability
before the freeze.

</details>

---

## 🟠 T4 — Fix the season-sim level bias (−137 pts/team/season)
**Status ☑ done (2026-07-11) — with T3.** Phase-10 team-points coverage **62 % → 77.2 %**, mean bias
**−137 → −113 pts/team/season**; title Brier **0.0881** (< 0.09), playoff **0.2342** (< 0.24), stability
0.979/0.949, **all hard gates PASS** (1,800 DEV team-seasons). `steps/phase10_sim.py` unchanged as the gate.

**What shipped, and how it diverged from this plan.** Attribution (`findings.md` 2026-07-11) overturned both
candidates: (1) the bias is entirely in the **offense** path (−140); K/DST fallbacks run **+16** — jittering
them would *worsen* the bias, so they're left alone; (2) per-player weekly CoV is **already well-calibrated**
from the prior season (RB 0.67 model vs 0.63 realized) — pooling doesn't move the bias. The real cause is
**structural**: the mean-preserving Dirichlet week-split has tails too light to reproduce the weekly
optimal-lineup **max** (a tail statistic), because a mean-preserving split caps weekly upside at the season
total. Fix = `weekly.SPREAD_KAPPA`, a per-position **effective-CoV inflation** (mean-preserving, so season
totals / Phase-5 / T3 calibration are untouched) that restores the max, plus pooling `wk_cov` over the prior
**two** seasons. QB is a single mean-preserving lineup slot (barely responds) → smallest inflation.
**κ is a genuine trade-off** (higher → more coverage/less bias but sim over-dispersion + a broken dog-leverage
gate); locked at `{QB 1.4, RB/WR 1.8, TE 1.7}` = the highest κ that keeps **every** hard gate passing.
**Residual bias (documented):** ~−113 remains, concentrated in the early/COVID seasons (2017/18/20 start
~−220 at κ=1.0) and partly a **projection-level** shortfall κ can't fix; the deliverable probabilities are
relative so they stay calibrated. Fully closing it needs a non-mean-preserving weekly-upside term (breaks the
Phase-5 sum invariant, gated behind explicit approval) or better early-season projections — future work.

<details><summary>Original plan (kept for the record — both root-cause candidates were wrong)</summary>

**Symptom.** Phase-10 predicted optimal-lineup totals run ~**137 pts/team/season low** (~−8/wk). The
championship-prob deliverable is *relative within a league* so it calibrates anyway — but any absolute-points
consumer, and the variance machinery that feeds on spread (`valuation/utility.py` CE, `simulation/leverage.py`
mean-preserving spreads), inherit the understatement. Season totals are preserved; the **weekly
disaggregation** that feeds the lineup max is the suspect.

**Root cause (two candidates — attribute before fixing).**
1. **Stale/understated weekly CoV.** `build_weekly_model` (`src/fantasy_quant/simulation/weekly.py:203`)
   pulls `variance.weekly_volatility(con, [season-1], …)` — a **single** prior season of `wk_cov`
   (`variance.py:47`), noisy and biased low for players whose usage grew; the Dirichlet `α = 1/CoV²`
   (`weekly.py:92`) then makes weeks too flat, so the lineup max (which rewards spikes) comes out low.
2. **Flat constant fallbacks.** `replacement_weekly` + `kdst_weekly_baseline` (`weekly.py:120–140`) assign a
   *constant* weekly score — zero week-to-week variance, so those slots never spike and drag the team max down.

**Fix.**
1. **Attribute first.** Instrument `steps/phase10_sim.py` to print predicted-vs-realized mean lineup points
   **decomposed by roster slot** — this says whether the CoV path or the fallback path owns the −8/wk.
2. **CoV path:** pool `wk_cov` over **2–3 prior seasons** (widen the `[season-1]` window) and/or shrink each
   player's CoV toward his position median rather than filling missing with the flat `DEFAULT_COV = 0.9`.
3. **Fallback path:** give the K/DST + cloudless-offense fallbacks a modest lognormal jitter (position-typical
   CoV) instead of a hard constant.

**Done-when.** Level bias shrinks toward 0 **while** title Brier stays < 0.090 and the reliability diagonal
holds. (Widening spread also lifts T3 coverage — that's why they're done together.)

</details>

---

## 🟠 T5 — De-risk the one-shot lockbox
**Status ☑ (2026-07-19, Session D). Pre-registration committed BEFORE the eval (`7bd6e10`); lockbox
evaluated EXACTLY ONCE and reported as-is.** Pre-registration in `PLAN.md` §"⭐ T5 PRE-REGISTRATION": the
exact frozen stack + the exact metrics + the 2025 dress rehearsal + the ≈35–40 DEV-decision count. **2025
dress rehearsal** (`analysis/lockbox_dress_2025.json`): projection bias 0.575 / Spearman 0.568, coverage
75.5 % uncond / 81.5 % cond. **Lockbox result** (`steps/lockbox_eval.py --which lockbox`,
`analysis/lockbox_eval.json`, `findings.md` §"LOCKBOX EVALUATION"): **title Brier 0.088 < 0.09 (holds OOS,
≈ DEV) · conditional coverage 80.1 % · projection Spearman 0.54 · cheap personalization**; known
level-optimism / unconditional-attrition limitation persists (bias 0.62, uncond coverage 72 %, a marginal
playoff Brier 0.240). **No modeling change after this — the stack is frozen.**

<details><summary>Original plan (kept for the record)</summary>

**Symptom.** By design everything is developed on DEV 2014–2022 and 2023+2024 is evaluated **exactly once**
at the end (`config.LOCKBOX_SEASONS`, CLAUDE.md §4). Every phase has been selected/tuned on the same ~9 DEV
seasons — the multiple-testing burden is real and growing, and the whole external-validity claim rests on a
single eval with no retry. PIT-clean ≠ out-of-sample-clean.

**Fix (reduce what we implicitly fit before spending the one shot — you can't add trials, so freeze late).**
1. **Pre-register** in `PLAN.md`, dated and committed, immediately before the eval: the exact frozen stack
   (projection, λ default, archetypes, the T3 coverage fix) **and** the exact metrics to be reported. No
   post-hoc "one more tweak" after this.
2. **Use 2025 as the full-stack dress rehearsal.** It's already the calibration holdout
   (`config.CALIBRATION_SEASONS`); run the *assembled* system against it (not just projections) so the
   lockbox isn't the system's first contact with unseen data. Once a 2025 ADP board lands (Sleeper, step
   0.10) it upgrades to a full backtest season and this gets much stronger.
3. **Track a running count** in `findings.md` of selection decisions made on DEV, so a marginal lockbox
   result is read with the right skepticism (1.5σ after 40 decisions ≠ after 5).

**Done-when.** A committed, dated pre-registration exists; 2025 dress-rehearsal numbers are recorded; the
lockbox is evaluated once and reported as-is with the decision-count caveat.

</details>

---

## 🟡 T6 — Consolidate the Monte-Carlo draws
**Status ☑ done (2026-07-10, with Phase 9.5).**

**Done (2026-07-10).** Added `distribution.cached_distribution(con, season, ruleset, n_draws, seed)`
— memoized on `(season, ruleset_json, n_draws, seed)` (the `_CORR_CACHE` pattern), always computed
`return_games=True` and served as `(summary, samples, games)`; `samples` is bit-identical whether or
not `games` is captured (same rng stream), so the games-free consumer slices `[:2]` off the *same*
cloud. Both consumers now read it: `optimizer.assemble_value` (with a new threaded `seed`) and
`weekly.build_weekly_model`. `optimize_draft(winprob=True)` builds the sim's `WeeklyModel` on the
**same seed** as the value index, so the draft and sim reference one joint cloud. `test_phase9`
asserts the memoization (one underlying call per `(season, seed)`; a distinct seed recomputes).

<details><summary>Original plan (kept for the record)</summary>

**Symptom.** `distribution.assemble_distribution` (`N_DRAWS = 2000`, `seed = 0` default) is called
independently by `optimizer.assemble_value` (`src/fantasy_quant/draft/optimizer.py:100`) and
`build_weekly_model` (`src/fantasy_quant/simulation/weekly.py:195`). Today they share a base draw **only by
the coincidence of the default seed** — the moment any caller passes a non-zero seed (or parallelizes), the
value the greedy drafts against and the value the sim scores **silently diverge**, and the same 2000-draw
cloud is recomputed several times.

**Fix.**
1. Add `distribution.cached_distribution(con, season, ruleset, n_draws, seed)`, memoized on
   `(season, ruleset_json, n_draws, seed)` — mirror the existing `_CORR_CACHE` pattern
   (`optimizer.py:184`) — returning `(summary, samples, games)`; point both consumers at it.
2. Thread **one explicit seed** from the top-level entry points (cost report, `phase10_sim`) so a run is
   fully reproducible and the draft and sim reference the *same* joint draws.

**Done-when.** 194 tests still pass; a new test asserts the two consumers get identical `samples` for the
same `(season, seed)`. Do this **before** Phase 9.5 wires the sim into the draft objective (T8) — that's when
the divergence would start biasing results.

</details>

---

## 🟡 T7 — Harden the external-scrape dependencies
**Status ☑ done (2026-07-10) — all three parts shipped.**

**Done (2026-07-10).**
1. **Freshness/schema guards** (`data/validate.py`): pure, injectable gates `adp_freshness_gate`
   (live-season FFC snapshot ≤ 6 days old — the CLAUDE.md §2 chore as an assertion), `board_size_gate`
   (FantasyPros board row-count band 400–700), `match_rate_gate` (gsis-match ≥ 95 %), wired into
   `data_health_report` via `_scrape_gates`; guards fire only when the relevant live board is present
   (historical-only stores stay green). 7 new pure unit tests in `tests/test_validate.py`.
2. **Raw-payload archival** (`data/cache.py::archive_text`): each FFC (`_pull_ffc`) and FantasyPros
   (`_pull_fp`) pull date-stamps its raw JSON/HTML under `data/raw/**/payloads/` (gitignored) so a
   broken scrape can be diffed against last-good shape; best-effort (never sinks a pull). 3 new tests
   in `tests/test_cache.py`.
3. **Props decision — SHELVED** (user, 2026-07-10): the markets/props layer is **formally deferred**
   (not a silent no-op), consistent with the reframe's "don't fight the sharp market"; the de-vig math
   stays built + tested for a future `ODDS_API_KEY`. Marked in `markets/props_projection.py`,
   `ROADMAP.md` Phase 2.3 (⏸️).

<details><summary>Original plan (kept for the record)</summary>

**Symptom.** FantasyPros (value) and FFC (ADP) scrapes are the spine and rot silently when site markup
changes; `markets/props_projection.py` is a **no-op** (no free props data), so the "markets" signal layer is
effectively absent though half-wired.

**Fix.**
1. **Freshness/schema guards** in `data/validate.py` (where `data_health.json` already lives), as
   test-visible assertions, not prose: latest 2026 ADP snapshot ≤ 6 days old (promote the CLAUDE.md §2 chore
   to an assertion), FantasyPros board row-count in a sane band, gsis-match rate ≥ 95 %. Fail loudly instead
   of ingesting garbage.
2. **Persist the raw payload** on each pull (HTML/JSON alongside the cached parquet) so a broken scrape can be
   diffed against last-good shape.
3. **Props decision.** Per the reframe finding ("don't fight the sharp market"), **formally shelve** the
   markets layer in ROADMAP (a 5-min doc edit) rather than invest — or wire one free odds source if ever
   wanted. Either way, remove the ambiguous no-op limbo.

**Done-when.** A markup change trips a red test; raw payloads are archived; the props layer's status is an
explicit decision, not a silent no-op.

</details>

---

## 🟡 T8 — Make `objective` real (Phase 9.5) + the behavioral opponent model (0.10 → Phase 11)
**Status ◐ · 8a ☑ done (2026-07-10); 8b: step-0.10 ingest ☑ done (2026-07-11), the behavioral fit still
open (needs a real-league pick log — bot mocks carry no persistent opponent identity).**

**Done — 8b step 0.10 (2026-07-11).** The pick-by-pick **data pipe** is built + verified on 3 real mock
drafts (`src/fantasy_quant/data/sources/sleeper.py`, `steps/phase0_10_sleeper_ingest.py`, `tests/test_sleeper.py`;
`docs/SLEEPER.md`). Keyless public API; `sleeper_drafts` + `sleeper_draft_picks` (idempotent by `draft_id`);
gsis crosswalk **100 % skill / 80 % K / DEF bridged**; derived `sleeper_mock` ADP board written into
`adp_snapshots` (so `adp_asof(source="sleeper_mock")` + the simulator consume it unchanged — verified by
drafting a 2026 mock); POC `sleeper_tendencies` (per-slot cadence + reach). Corpus-ready (`ingest_drafts`
takes a list of ids **or** discovers a username/league). **What 0.10 confirmed that changes the fit:**
mocks are **solo-vs-bots** — `picked_by` is set for the *human's own* picks only, so there is **no
persistent opponent identity**; the behavioral fit + availability Brier need **real human leagues** (which
populate `picked_by`), not mocks.

**Done — 8a (2026-07-10).** `DraftConfig.objective` is now consumed. `winprob_pick_fn` (opt-in via
`optimize_draft(winprob=True)`) prefilters to the top-k portfolio-CE/scarcity candidates, finishes the
draft greedily for each, scores the league with a Phase-10 mini-sim, and takes the candidate that
maximizes the routed metric — `make_playoffs`→`playoff_prob`, `championship_or_bust`→`title_prob`.
Common random numbers across candidates make the comparison pure roster signal. 2022 DEV: the two
objectives draft **8–9 different roster slots** and the title-max board carries **+0.09 title prob** over
the playoff-max board on an independent eval (at 250 sims/pick). **Honest caveat:** `title_prob` is a
~1-in-10 event, so `championship_or_bust` needs ≥~200 sims or it chases sim noise (at 60 sims it
under-performed); `make_playoffs` resolves at far fewer. Portfolio CE stays the fast default.
`steps/phase9_policy.py` is the done-bar; **8b** (behavioral opponent model) remains below.

**Symptom.** `DraftConfig.objective` (`src/fantasy_quant/draft/config.py:141`, comment "MVP: label") is
validated and passed around but **nothing consumes it** — the optimizer maximizes portfolio CE, not win
probability, so `make_playoffs` vs `championship_or_bust` draft identically. Separately, opponents are still
**ADP + Gaussian noise** (`draft/simulator.py`); the reframe's *behavioral* opponent model (a hard contract)
isn't built.

**Fix — 8a (Phase 9.5, now).** Wire the greedy to the Phase-10 probabilities (findings already notes "9.5
consumes `title_probability`/`playoff_prob` directly"):
- Replace/augment the per-pick score with the **marginal championship/playoff probability** from a mini-sim
  (`LeagueSim.title_prob` / `.playoff_prob`, `simulation/season.py:114`).
- Route `objective`: `make_playoffs` → maximize `playoff_prob`; `championship_or_bust` → maximize
  `title_prob` (rewards ceiling/variance → genuinely different boards — the point).
- Keep portfolio CE as the fast default; gate the win-prob objective behind the `objective` field / a Phase-9.4
  lookahead budget (a mini-sim per candidate is expensive).

**Fix — 8b (step 0.10 ☑ → Phase 11 fit ☐). Full reference: `docs/SLEEPER.md`.**
- 0.10 ☑ (2026-07-11): ingest built + verified — pick-by-pick JSON shape confirmed, `sleeper_id → gsis`
  crosswalk ingested (100 % skill), per-slot/reach behavior + `sleeper_mock` ADP board derived. See the
  "Done — 8b step 0.10" note above.
- Phase 11 ☑ (2026-07-11 — fit on the real corpus): the behavioral opponent model (conditional/McFadden
  logit) **beats ADP-only** walk-forward (log-loss +0.113 CI[+0.101,+0.124]) and the **availability Brier**
  owed from spine-4 **beats best-tuned ADP+noise** (0.158 vs 0.316, +0.159 CI[+0.083,+0.264]) → the S4
  availability oracle promotes from opt-in to the default. `draft/opponent_model.py`, `draft/availability.py`,
  `draft/personalities.py`; `steps/phase11_opponent_model.py`. (2025→2026 still becomes a full backtest
  season once a real *2026* ADP board lands.)

**Blocker → CLEARED for a first fit (2026-07-11).** The crawler (0.10b/0.10c) + a live crawl from the
Sleeper docs' **public example leagues** built a real corpus — **149 human + 117 bot drafts (2017–2020),
289 manager profiles**, `sleeper_human` ADP board, skill match 99.8 %. Real-league drafts were confirmed to
carry full per-manager `picked_by`. So the *data* no longer blocks the fit — a first behavioral opponent
model + availability Brier can run on real human picks (older seasons, but with realized outcomes). What
would strengthen it: **more/newer seeds** (broader connected components; the current corpus is one co-manager
component off 2 seeds) — add `league:<id>`/usernames to `reference/sleeper_seeds.txt` and re-run
`steps/phase0_10b_crawl.py`.

**Done-when.** 8a: switching `objective` measurably changes the drafted roster on DEV, consuming calibrated
probs. 8b: ☑ ingest + crawler verified on real drafts; a real corpus exists; **☑ the opponent model beats
ADP+noise on a real-pick availability Brier** (done 2026-07-11 — behavioral 0.158 vs best-tuned ADP+noise
0.316, +0.159 CI[+0.083,+0.264]). **T8b CLOSED.**

---

## 🟡 T9 — Phase 13.3 FAAB bidder is pragmatic; rigorous auction theory owed
**Status ☑ done (2026-07-13, Session C — Phase 15.4).** `draft/auction.py` now exists (auction values,
the exact `endgame_cap` budget-state continuation, winner's-curse-shaded `auction_bid`, `nominate`), and
its own done-bar PASSES 6/6 DEV seasons (a budget-state bidder beats naive budget-splitting by +66→+128
realized starting-lineup pts, season-block CI [+78, +108]). **`inseason/waivers.faab_bid` consumes it**:
pass `slots_remaining` and it caps the willingness-to-pay by `auction.endgame_cap` instead of the
closed-form ration (the rigorous continuation value the pragmatic bidder lacked); `faab_skill(use_auction=
True)` exercises the path. The FAAB *value* done-bar is unchanged under the upgrade — winner-selection is
scale-invariant among symmetric bidders, so the continuation form changes prices (budget efficiency), not
who wins, and the sim passes identically (no regression). The closed-form ration stays the default so the
committed 13.3 result is untouched. **Done-when met:** `draft/auction.py` exists, `faab_bid` consumes
auction values + a DP continuation cap, the FAAB sim still passes. **T9 CLOSED.**

<details><summary>Original entry (kept for the record)</summary>
**Opened 2026-07-12 (Session B, 13.3).**

**Symptom / decision.** 13.3's spec (`docs/BUILD_PLAN.md`) said "reuse 11.4", but **11.4 (auction-draft
support) was deferred out of Phase 11 into Phase 15.4** and `draft/auction.py` does not exist. Per the user
decision (2026-07-12), 13.3 shipped the **pragmatic** FAAB bidder (`inseason/waivers.py::faab_bid`) — enough
to clear the done-bar — and the **rigorous** version is explicitly owed here.

**What's pragmatic (and its limitation).** `faab_bid` combines three forces with **fixed/heuristic**
parameters, not an equilibrium: (1) marginal value → willingness-to-pay via a linear `value_scale`; (2) the
option value of budget as a closed-form ration `1/(1+κ·(weeks−1))` (a monotone hoard-early curve, **not** a
budget-state dynamic program); (3) first-price shading against a **fixed belief** `opp_bids` (a static
naive-field sample, **not** a fitted/equilibrium opponent-bid distribution). Also: the sim's smart agent bids
marginal-value-over-its-own-roster, but against a **synthetic** field (no real FAAB transaction data exists —
the Sleeper corpus is draft picks only), so the done-bar is a relative sim result, not a Brier-verified fit.

**The exact fix (at Phase 15.4).** Build `draft/auction.py` with a real auction-value engine (budget-state
DP or an equilibrium bid-shading model calibrated to an opponent-bid distribution), then have 13.3 reuse it:
replace the `value_scale` map with auction values, the closed-form ration with the DP's continuation value,
and the fixed `opp_bids` with the fitted field. If/when real FAAB transaction logs are ever sourced (Sleeper
transactions endpoint), fit and Brier-score the opponent-bid model like the draft opponent model (11.1/11.2).

**Done-when.** `draft/auction.py` exists and `faab_bid` consumes auction values + a fitted/DP continuation
value; the FAAB sim still passes its done-bar under the upgraded machinery.

</details>

---

## ✅ T10 — the archetype sweep crashes on S6's `adaptive` — **DONE 2026-07-24 (Session E)**
**Status ☑ · fixed per parent.** `validate_archetypes` now expands `adaptive` into one distinct subject
per static parent — `adaptive(zero_rb)`, `adaptive(late_qb)`, `adaptive(elite_te)`, `adaptive(hero_rb)` —
so the sweep prices each variant against its parent (the more-informative option) instead of skipping it.
`steps/spine_4_validate.py` runs green; the frozen stack is untouched (harness/utility fix only). On an
ADP board adaptive reproduces its parent (as S6 predicted); the 2 REAL-GAIN reads (elite_te) are unchanged.
_Original diagnosis below (kept for the record)._

**Status ☐ · opportunistic (found during the lockbox eval; worked around there).**

**Symptom.** `valuation/cost_validation.validate_archetypes` defaults its sweep to `[a for a in ARCHETYPES
if a != "bpa"]` — which now includes **`adaptive`** (added by S6 in Session A). `replace(bench,
archetype="adaptive")` raises: the `adaptive` archetype requires an `adaptive_parent`. So the archetype
cost-report done-bar `steps/spine_4_validate.py` (and any default call) crashes post-S6 — a latent
regression the DEV done-bar hasn't re-run since 2026-07-09 (pre-S6). The lockbox eval hit it and worked
around it at the harness level (`steps/lockbox_eval.py::cost_report_par` passes an explicit
`archetypes=list(ADAPTIVE_PARENTS)`), so the frozen stack was untouched.

**Fix (opportunistic, post-lockbox — a harness/utility fix, not the modeling stack).** Either exclude
`adaptive` from `validate_archetypes`' default names, or price it against each of its parents (sweep
`adaptive(zero_rb)`, `adaptive(hero_rb)`, … as distinct subjects — the more informative option). Update
`spine_4_validate.py` to match.

**Done-when.** `steps/spine_4_validate.py` runs green again; the sweep either skips `adaptive` or prices it
per parent.

---

## Ordering (see `ROADMAP.md ★ THE PIPELINE` for the full sequence)
1. ~~**Now:** T1 (commit), T2 (backup).~~ ☑ both done (2026-07-10).
2. ~~**Opportunistic:** T7 (scrape guards + raw-payload archival + props shelved).~~ ☑ done (2026-07-10).
3. ~~**Phase 9 completion:** T8a (win-prob objective) with T6 (MC consolidation) folded in.~~ ☑ done (2026-07-10).
4. ~~**Before the lockbox:** T3 + T4 together (coverage + level bias).~~ ☑ done (2026-07-11).
5. ~~**Next build:** step 0.10 Sleeper ingest (the pick-by-pick data pipe).~~ ☑ done (2026-07-11).
6. ~~**Next build:** Phase 7 (opportunity-adjusted projection, keep-or-drop).~~ ✗ **built & DROPPED**
   (2026-07-11 — situation swap is a wash-to-worse than naive on role-changers; consensus already prices it).
7. ~~**When real leagues exist:** S4/Phase 11 (T8b behavioral opponent model + availability Brier).~~
   ☑ **done (2026-07-11)** — corpus cleared the blocker; fit + availability Brier both beat ADP+noise.
8. ~~**Next buildable pipeline item:** S6 → Phase 13/S7 → Phase 12 → Phase 15.~~ ☑ **all done**
   (Session A 2026-07-12: S6+13.1+13.2; Session B 2026-07-12: 13.3+13.4+13.5; **Session C 2026-07-13:
   Phase 12 news/NLP + Phase 15.2/15.3/15.4**).
9. ~~**At Phase 15.4 (auction support):** T9.~~ ☑ **done (2026-07-13, Session C)** — `draft/auction.py`
   built; `faab_bid` consumes `endgame_cap`; auction done-bar 6/6 DEV.
10. **Right before the lockbox:** T5 (pre-register the frozen stack, incl. the T3/T4 params) — **the only
    open pre-lockbox tech-debt item.** (Optional MCTS/RL research gate sits just before it.)
