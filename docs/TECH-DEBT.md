# TECH-DEBT.md — known problems & the exact plan to fix each (the remediation register)

The durable, dated register of every known problem in the engine and **exactly what to do about it in
the long run**. Opened after a full-codebase audit (2026-07-10). One entry per problem, stable id
`T1…T8`, newest facts appended in place. This is the "what do we still have to fix" source of truth;
`ROADMAP.md ★ THE PIPELINE` sequences these against the phase build, `PLAN.md` logs the work as it's done.

**Severity:** 🔴 loss/operational (fix now) · 🟠 validity (fix before the lockbox eval) · 🟡 quality (opportunistic).
**Status:** ☐ open · ◐ in progress · ☑ done · ✗ won't-fix.

At a glance:

| id | 🔺 | problem | when | status |
|----|----|---------|------|--------|
| **T1** | 🔴 | Phase 10 + Stage 0 work uncommitted | now | ☑ |
| **T2** | 🔴 | Irreplaceable data (2026 ADP series, 2025 backfill) has no backup | now | ☑ |
| **T3** | 🟠 | Downside under-modeled — unconditional coverage 44 % / points coverage 62 % | before lockbox | ☐ |
| **T4** | 🟠 | Season-sim level bias −137 pts/team/season | before lockbox (with T3) | ☐ |
| **T5** | 🟠 | Lockbox is a one-shot; researcher-degrees-of-freedom accumulating on DEV | pre-register right before lockbox | ☐ |
| **T6** | 🟡 | Monte-Carlo draws recomputed / silently diverge across consumers | with Phase 9.5 | ☐ |
| **T7** | 🟡 | External scrapes (FantasyPros/FFC) fail silently; props layer a no-op | opportunistic | ☐ |
| **T8** | 🟡 | `objective` is a dead label; opponent model still ADP+noise | 9.5 now / opponent model at 0.10 | ☐ |

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
**Status ☐ · the top modeling debt; do before the lockbox (pair with T4).**

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

---

## 🟠 T4 — Fix the season-sim level bias (−137 pts/team/season)
**Status ☐ · do with T3 (~1 session).**

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

---

## 🟠 T5 — De-risk the one-shot lockbox
**Status ☐ · execute right before the lockbox eval (~1 hr of discipline).**

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

---

## 🟡 T6 — Consolidate the Monte-Carlo draws
**Status ☐ · fold into Phase 9.5 (~1–2 hr).**

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

---

## 🟡 T7 — Harden the external-scrape dependencies
**Status ☐ · opportunistic (~2 hr guards; 5-min props decision).**

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

---

## 🟡 T8 — Make `objective` real (Phase 9.5) + the behavioral opponent model (0.10 → Phase 11)
**Status ☐ · 9.5 is the immediate build; opponent model blocked on a real Sleeper league.**

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

**Fix — 8b (step 0.10 → Phase 11, blocked on a real league).**
- 0.10: point the ingest at the user's own Sleeper league (free) to confirm the pick-by-pick draft JSON
  shape, build the `sleeper_id → gsis` crosswalk ingest (99 % coverage already proven), derive per-slot ADP +
  reach behavior.
- Phase 11: fit the behavioral opponent model; **report the availability Brier** owed from spine-4 (the open
  S4 item), verifying it beats ADP+noise on real picks. 2025 becomes a full backtest season once its board lands.

**Done-when.** 8a: switching `objective` measurably changes the drafted roster on DEV, consuming calibrated
probs. 8b: opponent model beats ADP+noise on a real-pick availability Brier.

---

## Ordering (see `ROADMAP.md ★ THE PIPELINE` for the full sequence)
1. ~~**Now:** T1 (commit), T2 (backup).~~ ☑ both done (2026-07-10).
2. **Next build:** T8a (Phase 9.5 — roadmap's "← NOW") with T6 (MC consolidation) folded in.
3. **Before the lockbox:** T3 + T4 together (coverage + level bias), then T5 (pre-register).
4. **Opportunistic:** T7 (scrape guards) whenever data is touched; T8b when a real Sleeper league is available.
