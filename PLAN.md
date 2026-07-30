# PLAN.md — the HOW (living lab-notebook)

Working notes only: implementation choices, parameter picks, and dead ends **as they arise during a
step**. This file does **not** restate the goal, scope, decisions, or phase plan — those live in
`PROJECT.md` (§1–§5). Keep it terse; newest at the bottom.

## ⭐ T5 PRE-REGISTRATION OF THE FROZEN STACK (2026-07-19, Session D — committed BEFORE the lockbox eval)

**Purpose (TECH-DEBT T5).** The lockbox (2023+2024) is evaluated **exactly once**. PIT-clean ≠
out-of-sample-clean: every phase was selected/tuned on the same ~9 DEV seasons (2014–2022), so the
multiple-testing burden is real. This block **freezes the exact stack and the exact metrics before
the eval** so nothing is chosen post-hoc. **No modeling change after this commit.** Whatever the
lockbox prints is reported as-is with the decision-count caveat below.

**THE FROZEN STACK (component · file · key params):**
- **Value** = consensus→VBD. `projections/consensus.py` (`consensus_projection`: live FantasyPros
  re-scored to full-PPR; historical = Phase-2 baseline **proxy**) → `valuation/value_board.py`
  (draft-time replacement **from projections**; frozen contract) → rookie ridge `projections/rookie.py`
  (4.3) → calibration correction `projections/calibration.py` (4.4, per-pos bias→~0.96).
- **Distributions** = `projections/{quantile,conformal,variance,injury,distribution}.py` (5.1 QuantReg
  median slope ≈1.10 · 5.2 CQR · 5.3 wk_cov+boom/bust · 5.4 logistic-hazard→Beta-Binomial) **+ T3**
  (`injury.cohort_availability_prior` pos×draft-capital tier; `injury.role_retention` washout at
  played<40 %) assembled by `distribution.assemble_distribution` → `player_distributions`; utility CE
  `valuation/utility.py` (5.5, `E[Y]−λ·Var[Y]`, λ default from `DraftConfig.risk_lambda`).
- **Covariance** = `covariance/{estimate,shrinkage,copula}.py` (8.1 relationship-typed pooled ρ · 8.2 EB
  shrink `w=n/(n+κ)` · 8.3 handcuff rotated-Clayton), Σ Higham-repaired.
- **Draft policy** = covariance-aware greedy `draft/optimizer.py` (`personalized_pick_fn`+`RiskModel`;
  9.1/9.4 scarcity+lookahead `scarcity_w=0.5`, `SCARCITY_HORIZON=3`, `DEFAULT_NOISE=5.0`) · archetypes
  incl. **S6 adaptive** `draft/config.py` (`ADAPT_DECAY=0.5`, `ADAPT_SLIDE_WEIGHT=2.0`) · **9.5 win-prob
  objective opt-in** (`winprob_pick_fn`, k=6, sims=200; CE the default). **MCTS (11.2): DROPPED per the
  Session-D research gate `steps/phase11_2_mcts.py` — greedy is the frozen policy.** The determinized-UCT
  MCTS beats the greedy **in-objective** (Δ portfolio CE **+77**, CI[+47,+107], 89 % win-rate over 9
  DEV seat-seasons) but the gain **does not survive to realized OOS points** (Δ realized **+32**,
  CI[−90,+145] ∋ 0, 56 % win-rate) at 8.5 s/pick — the near-perfect-info + can't-out-resolve-consensus
  thesis, measured. Kept in-repo like Phase 7 / props (`analysis/phase11_mcts.json`; findings). CFR stays
  dropped.
- **Season sim** = `simulation/{weekly,season,playoffs,leverage}.py` (top-down weekly disaggregation:
  Phase-5 clouds + Phase-8 Σ via Iman-Conover permutation → Dirichlet(1/CoV²) week shares; `LeagueFormat`
  14-reg / 6-playoff / wks 15–17 / top-2 byes) **+ T4** `weekly.SPREAD_KAPPA={QB 1.4, RB 1.8, WR 1.8,
  TE 1.7}` + 2-season CoV pooling.
- **Opponent model** = `draft/{opponent_model,availability,personalities}.py` (11.1 conditional-logit fit
  on the Sleeper human corpus 2017–20; 11.2 availability oracle; 11.3 personalities).
- **Cost report** = spine S3 `valuation/cost_validation.py` + Phase-6 softness `adp/softness.py`
  (frozen `DURABILITY` +14.6 VOR/SD credit); headline = portfolio CE + risk profile.
- **Config** = `config.py`: DEV 2014–2022 · **LOCKBOX 2023+2024** · CALIBRATION 2025 · full-PPR, 10-team,
  1-QB, 9-starter.

**THE METRICS TO BE REPORTED (on 2023+2024, via `steps/lockbox_eval.py --which lockbox`):**
1. **Season/playoff sim (north-star):** title Brier & playoff Brier vs the 0.09 / 0.24 format baselines,
   reliability, points coverage, sim/realized spread ratio, seed stability, wk-8 leverage direction.
2. **Projection calibration:** overall bias ratio, rank Spearman, MAE.
3. **Distribution 80 %-interval coverage:** unconditional + conditional.
4. **Cost-of-personalization:** per-archetype realized-PAR cost + CI, projected→realized cross-check.
No other metric is added after seeing the result; no threshold is moved.

**2025 FULL-STACK DRESS REHEARSAL (recorded 2026-07-19, `analysis/lockbox_dress_2025.json`).** Board-free
value+risk layers on the 2025 calibration holdout: projection **bias 0.575 · Spearman 0.568 · MAE 78.2**
(n=448); distribution **80 % coverage unconditional 75.5 % · conditional 81.5 %** (n=673). Both well-
calibrated on unseen data → the lockbox is not the assembled system's first contact with a held-out year.
*(2025's draft-backtest parts — season sim, cost report — await a 10-team 2025 ADP board: the only 2025
boards are a 16-team `sleeper_human` and a 32-row `sleeper_mock`; those parts dress-rehearsed on DEV. The
`lockbox_eval` season-sim harness itself is validated to reproduce the frozen `phase10_sim` gate within its
own run-to-run noise — level bias matches exactly; threshold metrics wobble ~±0.002 Brier from BLAS float
ordering, a pre-existing property of the frozen stack.)*

**DEV SELECTION-DECISION COUNT (the multiple-testing caveat).** ≈**35–40** distinct selection/tuning
decisions were made on DEV across 15 phases (ensemble w · EB/shrinkage κ · feature set · rookie ridge ·
per-pos calibration · quantile/CQR/hazard forms · λ default · Phase-6 BH-FDR survivor · copula target ·
`scarcity_w` · win-prob sims · **T4 κ grid** · **T3 tier thresholds** · **S6 ADAPT params** · opponent
features · 13.x hyper-params · Phase-12 status multipliers · Phase-15 κ · the Phase-7 and MCTS keep-or-drop
gates · …). **Read a marginal lockbox number (e.g. title Brier just under 0.09) with that skepticism.**
Mitigant: the reframe deliberately targets **calibration**, not a single OOS edge — a much lower
overfitting surface than point-estimate ADP-beating (which our own Phase-2 backtest showed is unwinnable),
so a *decisive* result (DEV title Brier was 0.088 ≪ 0.09) is robust and a *marginal* one is not over-read.

---

## Current state
- **2026-07-24 — SESSION E (part 2): 16.3's 2026 half SIGNED OFF; 4 decisions locked; 16.3b opened as the
  16.4 blocker. DOCS-ONLY — no code written this part.** The user reviewed the drafted coaching table across
  **three correction rounds** and delivered a final version; I validated it, ran the (now-due) Stage-0 chore,
  and updated every md file so a fresh chat can resume cold. **Nothing committed yet.**
  - **★ FOUR DECISIONS LOCKED (user, 2026-07-24):**
    1. **16.3 sign-off = `confidence=high`.** The 32 signed-off 2026 rows ingest as high-confidence. Three
       aggregates were **never externally verified** and are recorded as such (10 new HCs; McDaniel MIA-HC →
       LAC-OC; 56 % of HCs calling plays) — sign-off was given with those flagged.
    2. **16.4 scope = the FULL historical build** (over: thin-9 / user-fills / skip-16.4). Opens **16.3b** —
       auto-scaffold `head_coach` for all 352 team-seasons 2014–2025 from `pbp`, then research the OC/
       play-caller column for the **23** uncovered 2026 playcallers' prior regimes, user-reviewed. Rationale:
       matches the standing *engine-complete-before-app, no time crunch* rule; the pbp scaffold makes it much
       cheaper than when it was first scoped.
    3. **Schema = drop `change_from_prev`, keep `in_house`** (+ `confidence`). Final contract:
       `season,team,head_coach,offensive_coordinator,play_caller,hc_calls_plays,in_house,confidence,notes`.
       **Consequence to carry into 16.4:** `in_house=0` ⇒ new playcaller regime, but it is **sufficient, not
       necessary** — DEN/PHI/WAS 2026 are `in_house=1` *and* new regimes (internal promotions). With
       `change_from_prev` dropped, **16.4 must handle the internal-promotion cases explicitly.**
    4. **Stage-0 chore = run it** (snapshot + backup). Done — see below.
  - **16.3 (2026 half) ☑ SIGNED OFF.** Artifact preserved verbatim at
    `reference/coaches_2026_signed_off_2026-07-24.csv`. **The merge into `reference/coaches.csv` is still
    OWED** — transform spec lives in `BUILD_PLAN.md` §16.3 (strip whitespace ×5, reorder cols, add
    `confidence=high`, backfill `in_house` on the 16 historical rows, replace the 7 stale 2026 rows).
  - **Validation: all PASS.** 32/32 teams, no empty cells, no person on two teams, `play_caller` ∈ {HC, OC}
    everywhere, `hc_calls_plays` consistent 32/32, **all 11 inter-team move chains cross-reference**.
  - **★ `in_house` semantics reverse-engineered, verified 32/32** = *"the play-caller was already on this
    team's staff the previous season."* **2026 transport-event set = 13 of 32 teams** with a new playcaller.
  - **16.3b OPENED — the hard blocker on 16.4** (the signed-off file is 2026-only; 16.4 needs *past* regimes
    to fingerprint from). Largest remaining item in Session E.
  - **Stage-0 chore run** (had crossed >6 days): FFC 2026 snapshot banked **2026-07-24** — 6 configs, 1,202
    rows, gsis 99.3 %, PIT gate clean, `PASS`; `backup_db.py` mirrored the ADP series + 2025 backfill +
    timestamped `.duckdb` to `/mnt/c/Users/rayha/fantasy-quant-backup/`, checksums verified.
- **2026-07-24 — SESSION E (part 1): T10 + Phase-16 value-side 16.1–16.2 DONE; 16.3/16.5 CSVs DRAFTED
  (awaiting user review); 16.4 gated on that review. NOT committed — left for user.** 316 tests (was 311),
  ruff clean. DEV-only (2014–22); lockbox untouched; walled off from the frozen cost report.
  - **T10 ☑** (`valuation/cost_validation.validate_archetypes`): the `adaptive` archetype no longer crashes
    the sweep — priced **per parent** (`adaptive(zero_rb)`, `adaptive(late_qb)`, `adaptive(elite_te)`,
    `adaptive(hero_rb)`) as distinct subjects (user chose the more-informative option). `spine_4_validate`
    runs green: adaptive≈parent on an ADP board (as S6 predicted); 2 REAL-GAIN reads (elite_te) unchanged.
  - **16.1 ☑ — an honest NULL** (`adp/panel.py` + `steps/phase16_1_situation_alpha.py`). Added two PIT
    situation flags — `team_changed`, `new_starting_qb`. **Neither is a stable ADP bias:** team_changed
    coef −2.5 VOR/SD (p_fdr 0.82, stab 62%), new_starting_qb −0.1 (p_fdr 0.98). The crowd prices offseason
    team/QB changes about right for *value*. **PIT catch (important):** the ADP board's `team` column is
    contaminated with an end-of-season crosswalk (the Sep-1 2022 board lists McCaffrey→SF, Toney→KC,
    Claypool→CHI — all *mid-season trades* not yet made at draft) → team-of-record is derived from `weekly`
    (Week-1 team) instead, verified leak-free. Franchise-alias map collapses relocations (OAK/LV, LA/LAR).
  - **16.2 ☑ — both sources WASH OUT (echoes Phase 12.3)** (`steps/phase16_2_competition.py`). Two
    independent competition-change flags: `competition_change_roster` (weekly usage + `draft_picks`,
    startable-caliber churn, 25%) and `competition_change_depth` (`depth_charts` new-entrant in the top-2,
    72%). The two disagree in **sign** (roster −9.9 VOR/SD, depth +9.8) and **neither survives FDR** (both
    p_fdr 0.087, stab 67%) — a textbook non-signal. Depth used `depth_charts` (2014–24), NOT `depth_charts_ts`
    (2025-only). NB: raw depth-set-diff floods to ~90%; the "new competitor cracked the starting depth"
    definition isolates a real newcomer.
  - **Wall-off intact:** `FEATURES` (the frozen 5-trait softness model) stays **pinned**; the situation
    flags live in `SITUATION_FEATURES`/`PHASE16_FEATURES`, mined only by the Phase-16 steps. Phase-6 drift
    check reproduces frozen `DURABILITY` +14.6 exactly — the cost report is untouched.
  - **16.3 DRAFTED, NOT final** — `reference/coaches.csv` (playcaller history), with a `confidence` column.
    **2026 web data was contradictory** (esp. head-coach assignments) → 2026 coaching rows flagged
    **low/VERIFY**. **USER MUST REVIEW/CORRECT before 16.4 (scheme fingerprint) consumes coaches.csv.**
  - **16.5 ☑ DERIVED (rebuilt 2026-07-25)** — `reference/situation_events_2026.csv` is now **generated** by
    `situation/events.py`, not hand-researched: **138 events over 30 teams**, one row per affected draftable
    player. The 9-row researched version missed 16 of the 23 team changes among draftable players. Human
    input is narrowed to `mechanism`/`notes` (111 rows still unresearched).
  - **Takeaway:** the whole value-side situation track (16.1+16.2) reads as an **honest null** — consensus
    prices offseason situation changes for value; Phase 16's real edge is the *availability* (draft-drift)
    side (16.7–16.12), not value alpha. Reinforces the reframe's "don't fight the sharp market."
- **2026-07-23 — BACKLOG EXPANDED (10 broad "better for all users" additions) + FULL SESSION RE-ORDER
  (docs-only, no code; makes the md base rock-solid before coding resumes).** After the two Phase-16 scoping
  passes, user asked for more realism/personalization ideas that **broadly help every user regardless of
  background** (explicitly **not** anything keyed to the user's own identity/history — so league-mate models
  and a personal self-model were proposed then **excluded** for now). Ten additions accepted (A–J), with one
  revision:
  - **A** superflex/multi-flex/roster generalization · **B (revised)** a **platform-agnostic manual
    league-settings form** (user is on ESPN/Yahoo, not Sleeper — so NOT auto-import; scoring PPR/half/standard/
    **custom per-stat values** + fully custom roster: add superflex/multi-flex, drop the kicker, change team/
    bench count) · **J** keeper support — **these three = new Phase 17 "League-Format Fidelity."**
  - **C** true FantasyPros **ECR** + **Underdog** ADP → **data step 0.11**, feeds 16.8 (replaces the VBD-ADP
    proxy with the real expert-rank signal + the sharp best-ball divergence source).
  - **D** live-draft **run-detection** (reactive availability mid-draft) → **Phase 16.16** (engine) + surfaced
    in 14.4.
  - **E** tier-cliff board · **F** roster-construction risk readout · **G** uncertainty-aware board · **H**
    playoff-week SOS lens · **I** draft grade/team report → **Phase 14 surfacing (14.E–14.I)** — all read
    already-frozen machinery (positional_cliff/roster_risk/handcuff/distributions/sim/cost_report), near-zero
    modeling risk.
  - **Scope assumptions (stated, user didn't object):** IDP deferred (nflverse IDP data too thin); optional
    platform auto-import is a secondary future convenience, not the primary path; Phase-15.1 dynasty stays
    optional (keeper 17.4 covers the near-term need).
  - **4 structural decisions (user, 2026-07-23):** (1) **new Phase 17 for formats (A+B+J) + distribute the rest**
    (C→0.11 data, D→16.16, E–I→Phase 14); (2) **app strictly last** — all UI/tabs/surfacing consolidate into
    Phase 14 (so 16.6 tab, 16.12 readout, 16.15 selector, 17.3 form all defer to the app block); (3) **same
    ~1.5–2.2k-line one-concept session discipline** with STOP-gates; (4) **dependency-optimal order**.
  - **Frozen-stack posture:** Phase 16 is walled-off (availability model is outside the value lockbox); **Phase
    17 is a config generalization, NOT a modeling change** — the lockbox-validated 10-team full-PPR 1-QB result
    stays valid; non-default formats are supported but **labeled not-lockbox-validated** (the eval was one
    format). Surfacing E–I read frozen outputs (no new modeling).
  - **THE RE-ORDERED SESSION PLAN (full detail in `ROADMAP.md` ★ SESSION PLAN).** Dependency lead is pinned by:
    16.8 reuses 16.1/16.2 situation features; 0.11 feeds 16.8; 16.13→16.14; availability→16.16. →
    **E** Phase-16 value-side 16.1–16.5 (+T10 warm-up; 16.6 tab→app) · **F** data 0.11 + drift 16.7–16.8 ·
    **G** apply drift 16.9–16.12 + 16.16 · **H** personalities 16.13–16.15 · **I** Phase 17 formats 17.1–17.4 ·
    **J** (optional) dynasty 15.1 · **K** Phase 14.1 Streamlit MVP + all surfacing (E/F/G/I + tabs, do not
    bundle) · **L+** Phase 14 go-live tail 14.2–14.7 (incl. 14.H SOS lens, D run-detection alert, deep pages,
    live-draft, widget). **Written into** `PROJECT.md` §5 (Phase 17, 16.16, 0.11, 14.E–14.I), `BUILD_PLAN.md`
    (per-step detail for all), `ROADMAP.md` (phase lines + pipeline step 11 + the ★ SESSION PLAN), `glossary.md`,
    `CLAUDE.md` pointer, and this entry. **Docs-only — no code, awaiting go-ahead; resume at Session E.**
- **2026-07-23 — Phase 16 OPPONENT-PERSONALITY set SCOPED (docs-only; substeps 16.13–16.15, folded into the
  availability track; NOT built).** User loved the AI mock-drafter "personalities" idea and asked for ~5 (upside
  chaser, normal, auto-draft/BPA, safe, …). **Checked first:** `draft/personalities.py` (Phase 11.3) already
  exists with 6 tilts on the fitted behavioral β (`balanced`, `chalk`, `zero_rb`, `reacher`, `homer`,
  `rookie_hawk`) — but they tilt only on **ADP/behavioral** features; the live sim board carries only
  `adp`/`pos`, so **no risk/value personality** (upside=ceiling, safe=floor) can be expressed. Also flagged the
  concept split: these are **opponent personalities**, distinct from `config.py` **archetypes** (the *user's
  own* strategy: `bpa`/`zero_rb`/`hero_rb`/`elite_te`/`late_qb`/`adaptive`).
  - **The 4 decisions (user, 2026-07-23):** (1) **"auto-draft/BPA" = ADP autopilot only** — a deterministic
    lowest-ADP-available seat (Sleeper autopick); **no value-board opponent** (this **cut** the "Value Hawk"
    projection-BPA personality I'd proposed). (2) **Enrich the opponent board with the real frozen Phase-5
    distribution + `value_board` fields** (`boom_prob`/`q90`/`bust_prob`/`q10`/`games_played_mean` + `vbd`/
    `overall_rank`), read-only — highest fidelity. (3) **Home = fold into the Phase 16 availability track**
    (not a standalone phase, not app-only). (4) **Validation = face-validity + unit-tested mechanics** — a
    realism/UX feature, **no corpus Brier gate** (softer than the walk-forward-gated 16.7/16.8 drift work).
  - **The 5 headline personalities (my pick, given the decisions):** **Autopilot** (deterministic ADP
    autopick) · **Balanced** (fitted average human — exists) · **Upside Chaser** (`+boom_prob`/`+q90` + youth,
    punts floor) · **Safe/Floor** (`+q10`/`+games_played_mean`/DURABILITY, `−bust_prob`, veterans) · **Homer/
    Narrative-Chaser** (`+fandom` + hype-board delta). **Chose Homer as the 5th** (replacing the cut Value
    Hawk) because Phase 16 exists to model narrative over-drafting and Homer is the seat that **reaches for
    hyped players** — so it doubles as the channel the 16.9 per-draft narrative shock rides through (unifies
    the personality + drift systems). `zero_rb`/`reacher`/`rookie_hawk` stay as library extras — flag to the
    user in case they'd rather swap Homer for Reacher (pure chaos).
  - **Substeps (detail in `PROJECT.md` §5 / `BUILD_PLAN.md`):** 16.13 opponent-board enrichment
    (`draft/simulator.py`, read-only join off the frozen contracts) · 16.14 the 5 personalities (`Personality`
    gains a `signal_weights` term to tilt on the enriched columns; `draft/personalities.py`) · 16.15 mock-room
    composition (configurable 9-seat mix) + hype-shock coupling (16.9 through Upside/Homer) + Phase-14 app
    selector. **Done-when:** face-validity checks (Upside skews young/high-`q90`, Safe durable/high-`q10`,
    Autopilot pure ADP order, Homer reaches fandom/hype) + mechanics unit tests; whole cluster read-only w.r.t.
    the frozen value stack. **Written into** `PROJECT.md` §5, `BUILD_PLAN.md` (16.13–16.15), `ROADMAP.md`,
    `glossary.md`, `CLAUDE.md` pointer, and this entry. **Docs-only — no code yet, awaiting go-ahead.**
- **2026-07-23 — Phase 16 AVAILABILITY-SIDE track SCOPED (docs-only; substeps 16.7–16.12 folded into Phase
  16, NOT yet built).** User's problem: every year some players are *drafted* above ADP purely on media
  narrative / changed circumstance (this year's example: Ladd McConkey — down 2024, now better playcaller +
  vacated targets + rookie-year pedigree, so mock-drafters reach). The UX failure to fix: a target falls to
  the user at ADP across 10 mock drafts, then gets **sniped early in the real draft** because many humans
  share the read — a bad experience the sim currently manufactures.
  - **Framing.** This is the **availability** signal (does narrative make a player *drafted earlier*?), the
    sibling of the value question Phase 16.1–16.6 already asks (does a changed situation make a player
    *out-earn* ADP?). Same situation-change feature substrate; different target. So the user chose to **fold
    it into Phase 16** as a second track (16.7–16.12) rather than open a new phase.
  - **Key enabling fact (checked in code).** The availability/opponent model (`draft/opponent_model.py`,
    `draft/availability.py`) is documented as **outside the value-stack lockbox** — it predicts draft flow,
    not player value, fits on all seasons 2017–2026, and every number is walk-forward. So extending it does
    **not** spend or contaminate the just-frozen (Session-D) value eval. This is why availability-drift work
    is legitimate post-freeze where a value-side change would not be.
  - **Two hard data constraints (drive the design, can't engineer around):**
    1. **Momentum is forward-only.** ADP *velocity* is the most direct "media already moved the market"
       signal, and Stage-0 has banked a 2026 snapshot **series** since 2026-07-09 → computable live. But FFC
       history is **one ~Sep-1 board per season** (2010–2024) — no historical intra-season ADP series exists,
       so momentum **cannot be backtested**; it's validated **live on 2026 only** (16.11).
    2. **True ECR isn't stored.** `consensus.py` scrapes FantasyPros *projection* pages and keeps points, not
       expert *rank*. The "expert-rank-minus-ADP" gap therefore uses a free proxy computable everywhere incl.
       historically: **our own VBD `value_board.overall_rank` vs ADP** (16.8). A true-ECR scrape is optional
       future work (live-only).
    - What *is* backtestable: the **Sleeper human corpus** (149 human drafts, 2017–2020, real pick slots)
      gives `actual_slot − ADP` as a historical drift target (16.7) — so the correlated shock, VBD-ADP gap,
      and source-divergence pieces get a real walk-forward gate; only momentum + the hype board are live-only.
  - **The four scoping decisions (user, 2026-07-23):** (1) **home** = fold into Phase 16 (not a new phase);
    (2) **validation bar** = walk-forward + an own held-out metric (drift MAE/Spearman, availability Brier) on
    what backtests, momentum live-only on 2026; (3) **hype override** = YES, a curated hand-maintainable
    `reference/hype_board.csv` (Claude-web-research-drafted + user-reviewed, same contract as the 16.3
    playcaller table) for the qualitative residual; (4) **consumption** = BOTH realism (mock opponents draft
    hyped players earlier) AND advice (drift feeds the opt-in Phase-9.4 lookahead — "he won't last, consider
    reaching"), plus an honest `P(available at your pick)` + reach-risk readout in the app.
  - **Substeps (full detail in `PROJECT.md` §5, availability-side track):** 16.7 drift panel/target
    (`adp/drift_panel.py`) · 16.8 drift feature model (`adp/drift_model.py`: VBD-ADP gap + source divergence +
    situation flags, walk-forward) · 16.9 correlated per-draft narrative shock (`draft/simulator.py` +
    `opponent_model.py` — one shared hype draw/draft → reproduces realized draft-slot dispersion) · 16.10
    curated hype board (`adp/hype_board.py` + `reference/hype_board.csv`) · 16.11 live 2026 momentum
    (`adp/momentum.py`, forward-only) · 16.12 consumption = realism + opt-in 9.4 advice + app readout
    (extends `docs/PLAYER-VIEW.md`, walled-off + tagged like the situation bar; drift board on the 16.6 tab).
  - **Guardrails (carried into the build):** walk-forward everywhere it's possible; the frozen value/
    distribution/optimizer/VBD/cost-report stack is **untouched** (drift feeds the opponent model + an opt-in
    lookahead + the app, never the value contracts); momentum + hype board are explicitly labeled live-only /
    curated, not backtested claims. **Written into** `PROJECT.md` §5 (16.7–16.12 + Done-when), `ROADMAP.md`
    (Phase 16 two-track status line + ★ THE PIPELINE step 11), `glossary.md` (new availability-drift section),
    `docs/PLAYER-VIEW.md` (reach-risk readout), and this entry. **Docs-only — no code yet, awaiting go-ahead**
    (STOP-gate discipline).
- **2026-07-23 — PLAYER-VIEW app surface SPECCED (docs-only; `docs/PLAYER-VIEW.md`).** User wants the app
  "as interactive as possible": on a mock-draft/board page, **hover or click a player** to see a simple,
  elegant, detailed overview of impact / injury risk / upside / downside via **quasi-bars** (green large =
  high, yellow mid, red low). Design settled with the user before any code:
  - **Two-tier interaction** (user's own reframe): **hover → 5-bar overview** (bar + number, glanceable),
    **click → per-player deep page** (`/player/<key>`, all 8 bars + one-line why + weekly-distribution band
    + situation context). Resolves "simple **yet** detailed."
  - **8 bars, all reading frozen contracts — no new modeling.** Core 5 on hover: impact (`value_board`
    vbd/pos_rank), upside (`boom_prob`/`q90`), downside (`bust_prob`/`q10`), injury (`games_played_mean`/
    Phase-6 durability), bargain (`overall_rank` vs ADP). Deep-page-only 3: situation-change (Phase 16),
    week-to-week consistency (Phase-5 weekly CoV), opportunity/role (Phase-3 `opportunity.py`).
  - **Decisions (asked + answered 2026-07-23):** (a) extra bars = **all four** offered (situation-change,
    bargain, consistency, opportunity) → the 5/8 hover/page split; (b) **green = good for the drafter
    always** (risk bars inverted); (c) **dual baseline — overall (top) + within-position (below)** on every
    bar (user confirmed "overall + within-position"); (d) target surface = **Next.js frontend primary**
    (Phase 14.3), Streamlit click-to-expand as the reduced fallback; (e) hover detail = **bar + number**,
    the prose "why" lives on the deep page.
  - **Honesty (inherited discipline):** the Phase-16 situation-change bar renders **visually distinct +
    tagged unvalidated**, walled-off from any cost/value number & the optimizer; a **confidence flag** on
    rookie/`no_prior`/`proxy` rows; a limitations footer (the lockbox level-optimism/attrition finding).
  - **Only gating dependency = bar #6 → Phase 16** (Session E). Everything else is already frozen.
    Implementation order unchanged: **Phase 16 → 14.1 backend (per-player bar endpoint) → 14.3 frontend
    (this spec).** Folded into `docs/BUILD_PLAN.md` §14.1/§14.3; glossary + CLAUDE pointer updated.
- **2026-07-19 (post-Session D) — Phase 16 SCOPED (docs-only; not yet built).** User request: dig into
  "changed situations" (trade to a better/worse landing spot, coaching changes, target/carry competition
  changes, workload shifts from a departed teammate) as an avenue they believe ADP under/over-reacts to
  year after year — as a **beta-testing model on a completely separate tab**, not part of "the true
  personalization meat." Research pass before any building:
  - **Checked against what already exists.** Phase 7 (`causal/`, 2026-07-11) already tested something
    adjacent and was **dropped** — but it answered a different question. Phase 7 asked "does modeling
    situation change improve *mean projection accuracy*?" (a blunt team-fixed-effect re-projection) → no,
    wash-to-worse than naive carry-over on 466 movers. The user's question is "does **ADP** systematically
    mis-price these events relative to a fair projection?" — untested. Checked Phase 6.2's actual feature
    set (`adp/regression.py`): `{rookie, experience, adp_stdev, prior_games, prior_ppg}` + position dummies
    only — **nothing about trades/coaching/competition was ever mined.** Real, non-duplicative gap.
  - **Recommended approach:** extend Phase 6's already-validated ADP-alpha mining pipeline
    (`adp/panel.py` → `regression.py` → `scorecard.py`, the same machinery that found DURABILITY
    under-priced, +14.6 VOR/SD, BH-FDR-significant, 100% sign-stable) with new situation-change features,
    rather than rebuilding Phase 7's reprojection machinery. Plus a separate, harder piece: coaching-scheme
    fingerprints (per-playcaller role-share signatures — WR1/2/3 target share, RB carry share, TE
    involvement, PROE — reusing Phase 3.1/3.4 features) with a transport function for playcallers who
    change teams (e.g. McDaniel → Chargers 2026). Checked feasibility: `pbp`/`schedules` already carry
    `home_coach`/`away_coach` (nflverse, 2014+, free) but that's **head coach, not necessarily playcaller**
    — no free structured "who calls plays" table exists anywhere. Flagged as the one real build gap.
  - **Scoping questions asked + answered (2026-07-19):**
    1. **Competition-change signal → dual-sourced.** Phase 12.3 already found depth-chart-derived signals
       (`depth_charts_ts`) don't separate for in-season promo/demo (noisy nflverse ranks) — real risk of
       repeating a known-null result if reused blindly. User chose to build **both** a roster-turnover-
       derived feature (via `draft_picks` + team roster deltas year-over-year) **and** a depth-chart-derived
       one, compared side by side, rather than assume one wins.
    2. **Coaching/playcaller table → Claude drafts via web research, user reviews before use.** No free
       source exists; playcalling duty is often ambiguous (HC vs delegated OC, mid-season firings) — a
       hand-curated table of ~10–15 fantasy-relevant moves/year is the right scope, not a comprehensive
       scrape of all 32 teams' full staff history.
    3. **Scheme-fingerprint/transport validation bar → descriptive-only, clearly labeled.** Sample is thin
       (~20–30 clean "playcaller moved teams, kept playcalling" events in the whole DEV window) — too thin
       for the BH-FDR-gated bar the rest of the mining uses. Ships as an informed hypothesis display (e.g.
       "McDaniel's Dolphins: X% RB1/RB2 split"), not a backtested claim.
    4. **2026 live events → included now, not deferred.** The beta tab should populate this year's actual
       offseason situation-change events (trades, FA signings, coaching hires) so it's immediately useful
       for this year's draft, not just a historical proof of concept.
  - **Written into `PROJECT.md` §5 (new Phase 16, substeps 16.1–16.6) and §3 (4 new settled decisions),
    `ROADMAP.md` (Phase 16 status line + pipeline resequencing — Phase 16 now runs after the lockbox eval,
    before Phase 14, so its tab ships in the app from day one), and `CLAUDE.md`'s next-session pointer
    (Session E = Phase 16, Session F = Phase 14.1).** Docs-only — **no code written yet, awaiting explicit
    go-ahead** (per the STOP-gate discipline — this is a scoping pass, not a build).
  - **Design guardrails carried into the build, when it starts:** DEV-only mining (2014–2022), lockbox
    (2023+2024) untouched; the beta tab is **read-only**, never wired into the optimizer/VBD/cost report —
    it cannot contaminate the just-completed, just-frozen lockbox-validated stack.
- **2026-07-19 (Session D)** — **CLOSEOUT COMPLETE: MCTS research gate DROPPED + T5 pre-registration + the
  one-shot LOCKBOX EVAL. The engine is FINAL; the lockbox is spent.** See §"⭐ T5 PRE-REGISTRATION" above,
  `findings.md` §"Session D" + §"LOCKBOX EVALUATION", `analysis/{phase11_mcts,lockbox_eval,lockbox_dress_2025}.json`.
  311→ (5 new `test_mcts`) tests, ruff clean. **Two local commits** (`7bd6e10` freeze, then the lockbox result);
  **not pushed**. Lockbox now touched — by design, exactly once.
  - **MCTS (11.2) BUILT & DROPPED** (`draft/mcts.py` determinized-UCT; `steps/phase11_2_mcts.py`). Beats the
    greedy **in-objective** (Δ portfolio CE +77, CI[+47,+107], 89 %) but **not on realized OOS points** (Δ +32,
    CI[−90,+145]∋0, 56 %) at 8.5 s/pick → near-perfect-info thesis measured; greedy stays the policy. **Key
    build lesson:** at low iters (15) MCTS *underperforms* the greedy even in-objective (resolution-limited,
    the 9.5 title-objective lesson); needs ~100 iters to reliably beat it on CE.
  - **T5** pre-registration + 2025 dress rehearsal (`steps/lockbox_eval.py --which dress`): projection bias
    0.575 / Spearman 0.568, distribution coverage 75.5 % uncond / 81.5 % cond — well-calibrated on unseen data.
  - **LOCKBOX (2023+2024, as-is):** title Brier **0.088 < 0.09** (champ calibration holds OOS, ≈ DEV),
    conditional coverage **80.1 %**, projection Spearman **0.54**, cheap noise-dominated personalization;
    **known level-optimism / attrition limitation persists** (bias 0.62, uncond 72 %, marginal playoff Brier
    0.240). All hard gates PASS. **Harness fix (not the stack):** the cost-report crashed on S6's `adaptive`
    archetype in `validate_archetypes` (logged **T10**); scoped to the 4 static preference archetypes + computed
    once. **★ Next: Session E = Phase 14.1 Streamlit MVP.**
- **2026-07-13 (Session C)** — **Phase 12 news/NLP + Phase 15 multi-format/auction DONE (all done-bars PASS;
  306 tests, ruff clean; NOT committed — left for user review).** Ran the overdue Stage-0 FFC snapshot chore
  first (banked 2026-07-18 boards). Lockbox untouched; DEV-only (2017–22). Full detail in `findings.md`
  (Session C) + `glossary.md` (Phase 12 / Phase 15). Headlines:
  - **Phase 12 — a qualified KEEP.** `news/{sources,extract,event_study,validate}.py`. Injury designations
    carry a **significant exploitable lag (+5.86 pts/start)** → a news-aware weekly forecast (13.1's reserved
    `news` slot, priced by a DEV-calibrated availability multiplier) **beats injury-blind 13.1 +3.4→4.3
    pts/pw on the designated subset, 6/6 DEV**. Depth-chart changes don't separate → **DROP** that signal.
    LLM edge-only via a **gated `ClaudeClient`** (Haiku 4.5, behind `ANTHROPIC_API_KEY`); the deterministic
    **rules** extractor is the default and the core prices the signal — the reframe guardrail, literalized.
    Free-text RSS is forward-only (can't be backfilled) → the validated signal is the structured injury feed.
  - **Phase 15.** 15.4 auction (`draft/auction.py` — budget-state bidder beats naive 6/6, +66→+128 lineup
    pts; **T9 discharged**, `faab_bid` consumes `endgame_cap`), 15.2 best-ball (`formats/bestball.py` —
    **variance-is-good**, ceiling beats mean 6/6; **weekly** CoV not season sd), 15.3 DFS GPP
    (`formats/dfs.py` — leverage beats chalk 6/6 via duplication/prize-splitting; **MECHANICS only, no free
    DFS salary/ownership feed**). 15.1 dynasty deferred (user scope). **Next: Session D = optional MCTS/RL
    gate → T5 pre-registration → LOCKBOX EVAL → Phase 14 app.**
- **2026-07-12 (Session B, part 3 of 3)** — **Phase 13.5 trades / market-making DONE (DEV done-bar PASS; 276
  tests, ruff clean; NOT committed — left for user review with 13.4).** Greenfield `inseason/trades.py`.
  Lockbox untouched; all tuning on DEV (2017–22). **Session B (13.3+13.4+13.5) complete → S7/Phase 13 done.**
  - **Pure kernels:** `lineup_value` (roster value = its optimal starting-lineup sum only — reuses the 13.2
    greedy `_fill`; the diminishing-returns lesson made positional); `evaluate_trade` (a swap's *change* in
    each side's `lineup_value`; `mutual` iff **both** gain > `ACCEPT_MARGIN=5`); `find_trades` (the market-
    maker — searches every opponent's surplus `_benched` for mutual 1-for-1 / 2-for-1 legal deals, ranks by
    the **worse-off side's** gain `min(mine, theirs)`, tilts to sell-high/buy-low on a `market` gap). 4 pure
    unit tests.
  - **DONE-BAR (PASS):** proposed trades **raise both teams' simulated playoff prob** in the Phase-10 MC sim.
    `n_leagues=40` snake-drafted imbalanced leagues/season, `n_focal=4` maker seats; execute the top proposal
    and re-sim (shared player-weekly cache + fixed schedule → pre/post differ *only* by the two swapped
    rosters, a paired comparison). **6/6 DEV** both maker & partner mean playoff-prob rise (maker season-block
    CI **[+0.014,+0.021]**, partner **[+0.012,+0.021]**, weaker side **[+0.011,+0.019]**). **Random-trade
    control** lifts both sides ~never (~0–10%) → proposed beat random **6/6** (the surplus *signal*, not
    churn). Sell-high tilt modest (`sell_high_rate` ~0.5–0.6).
  - **KEY DESIGN CORRECTION (in-session):** ranking proposals by the **maker's own** gain made the maker
    reliably gain but only cleared a *marginal* partner floor → the worse-off side's sim gain died in MC noise
    (pair_min ~0). Switching `find_trades` to rank by `min(maker, partner)` — the fairest win-win a two-
    signature trade actually needs — makes **both** sides gain robustly. The 13.3/13.4 lesson generalized: the
    objective must reward the *right* thing (mutual benefit) or the maker just skims.
  - **STATS NOTE:** per-season trade counts are small/jittery (n≈14–48; upstream `cached_distribution` board-
    ordering wobbles run-to-run), so the per-season two-CI test is underpowered (2018 partner grazes 0 — an
    honest weak-surplus season, echoing 13.4's 2018 miss). Gate = **season-block bootstrap on each side's
    gain** (the 13.4 device, decisive & rerun-stable) + the 6/6 random control.
  - **DECISION (scope):** value currency = preseason model ros mean (self-consistent with the sim → PIT-
    trivial, fair); in-season this `values` slot is 13.1's re-projected mean (fed in, 13.4→13.1 pattern). Sim
    trades **1-for-1** (count-neutral); **2-for-1** consolidation supported by kernels + unit-tested, not simmed.
  - `steps/phase13_5_trades.py` runner; `analysis/phase13_trades.json`. **Next: Session C = Phase 12 news/NLP
    + Phase 15 multi-format/auction (discharges T9).**
- **2026-07-12 (Session B, part 2 of 3)** — **Phase 13.4 streaming DONE (DEV done-bar PASS; 272 tests, ruff
  clean; NOT committed — left for user review with 13.5).** Greenfield
  `inseason/streaming.py`. Lockbox untouched; all tuning on DEV (2017–22).
  - **`stream_pick`** (pure, position-agnostic): greedy exploit on `matchup_projection = own +
    (opp_allow − league_mean)` (both terms empirical-Bayes shrunk toward the prior season via `_shrink`,
    `PRIOR_GAMES=4`), with a **switch-margin hysteresis** (`SWITCH_MARGIN=1.0`) and an optional UCB explore
    bonus (`UCB_C=0`, off — shrinkage explores softly). 5 pure unit tests (`_shrink`, `matchup_projection`,
    `stream_pick` exploit/hysteresis/UCB).
  - **DECISION (scope):** demonstrate on **DST** — the strongest matchup signal + real weekly scores
    (`dst_weekly_points` + the schedule from `game_lines`). `stream_pick` is position-agnostic; QB/TE
    streaming would feed 13.1 re-projected means in as `proj` (documented extension, not built — the 13.2
    "one passing bar + noted extension" pattern).
  - **DONE-BAR (PASS):** `n_managers=300` each with a random 8-unit slice of the waiver-tier defenses; matchup
    -streaming beats **static-hold** (roster the preseason-best unit, start it every week, eat its bye) **6/6
    DEV**, mean **+1.46 DST pts/wk**, season-block CI **[+0.88,+2.09]**. Signal control: matchup beats
    **random**-streaming **5/6** (the 2018 miss = +0.2; the opponent-offense signal is real but modest).
  - **LESSON APPLIED (from 13.3):** the `switch_margin` hysteresis + the random-streaming control are how 13.4
    keeps the sim from "rewarding churn, not skill" — streaming's raw edge over static-hold is partly just
    roster churn, so `beats_random` isolates that the matchup *signal* itself adds value.
  - `steps/phase13_4_streaming.py` done-bar runner; `analysis/phase13_streaming.json`. **13.5 trades done next
    (part 3 of 3, above).**
- **2026-07-12 (Session B, part 1 of 3)** — **Phase 13.3 waivers/FAAB DONE (DEV done-bar PASS; 267 tests,
  ruff clean; committed.)** Greenfield
  `inseason/waivers.py`. Lockbox untouched; all tuning on DEV (2017–22).
  - **`faab_bid`** (pure): marginal value → `value_scale` willingness-to-pay, **rationed** by the option
    value of budget `1/(1+OPTION_KAPPA·(weeks−1))` (`OPTION_KAPPA=0.15`), then **first-price shaded** to
    `argmax_b (value−b)·P(win|b)` vs a belief `opp_bids` (else flat `SHADE_FRAC=0.9`). 6 pure unit tests.
  - **DECISION (user, upfront):** *pragmatic now, rigor owed.* 13.3's "reuse 11.4" is stale — 11.4/auction
    was deferred to **Phase 15.4** (`draft/auction.py` doesn't exist). So `faab_bid` uses fixed/heuristic
    params, **not** an equilibrium/budget-state DP. Logged as **`docs/TECH-DEBT.md` T9** (fold into 15.4).
  - **DECISION (user, upfront):** *mixed field* — `faab_skill` seats the sharp agent (0) vs a naive
    %-of-budget bidder (1), the rest alternating, so the edge is measured against equally-sharp opponents.
  - **KEY FINDING (in-session):** the first cut banked **every** acquisition's value → the objective rewarded
    raw *volume* and naive aggression won **0/6**. Fix = model **diminishing returns**: score only a team's
    **top-`n_useful`=4** realized pickups and have the sharp agent bid **marginal value over what it already
    holds** (a bench add is worth ~0). That makes budget scarce and flips it to **5/6 PASS** (mean gain +30.0
    value/szn, season-block CI [+21.7,+38.8]; higher value-per-dollar). *Reusable lesson for 13.4/13.5: a
    waiver/streaming/trade sim needs a roster/slot constraint or it rewards churn, not skill.*
  - `steps/phase13_3_waivers.py` done-bar runner; `analysis/phase13_waivers.json`. **Next (pending user go):
    13.4 streaming, then 13.5 trades — straight-through.**
- **2026-07-12** — **SESSION A COMPLETE: S6 + Phase 13.1 + 13.2 (all DEV done-bars PASS; 261 tests, ruff
  clean; NOT yet committed — left for user review).** Resumed the interrupted Session A: the code for all
  three substeps pre-existed (uncommitted WIP) but was never tested, run, or linted. This session verified
  it, added the missing unit tests + done-bar runners, fixed the lint the WIP never got, ran every
  validation, and recorded results. Lockbox (2023+24) untouched; all tuning on DEV (2017–22 validation
  window).
  - **S6 adaptive archetype** — `draft/config.py` `"adaptive"` + `_adaptive_tilt` (melt a *fade* by ADP
    slide: `ADAPT_DECAY`, `ADAPT_SLIDE_WEIGHT`; sliding value melts ~2× a reach; reaches untouched; no
    board context ⇒ reproduces parent). Threaded through `total_tilt_rounds(adp=, overall_pick=)` and
    `_greedy_eff`. **Done-bar** `steps/spine_5_adaptive.py`: `adaptive(zero_rb)` +2.0 / `adaptive(hero_rb)`
    +15.6 team-value in the behavioral (board-breaking) room, ~0 / no-harm in the ADP room. **PASS.**
  - **13.1 weekly re-projection** — `inseason/reproject.py` (scalar Kalman on the per-week level; PIT;
    reserved Phase-12 `news` slot, no-op default). **Done-bar** `steps/phase13_1_reproject.py`: beats the
    static preseason level OOS **6/6** seasons, +0.396 ppg/wk MAE gain, season-block CI [+0.32,+0.48]. **PASS.**
  - **13.2 start/sit** — `inseason/lineup.py`. **DECISION (finding-driven):** the win-probability
    **variance tilt does NOT beat mean-max OOS** even for big underdogs (0/6 seasons; a single legal swap
    barely moves the ~35-pt team sd — consistent with Phase-10.3's whole-team-only leverage). So flipped
    `optimal_lineup` default to `objective="mean"`; the tilt stays **opt-in** `objective="win"`, off by
    default (Phase-7 / props "kept, not default" pattern). The **done-bar that PASSES** is the *co-pilot vs
    set-and-forget*: mean-max on 13.1's **re-projected** means outscores the frozen-preseason lineup on
    realized points **6/6** seasons, +2.08 pts/lineup-week (CI [+1.56,+2.54]). `steps/phase13_2_lineup.py`
    reports both. **PASS** (on the co-pilot bar).
  - New tests `tests/test_inseason.py` (12); S6 tests already in `tests/test_spine.py`. **Next: Session B
    (Phase 13.3–13.5: waivers/FAAB + streaming + trades).**
- **2026-07-11 (h)** — **SESSION SIZING GUIDE added (docs-only).** User asked how S6's size compares to
  past sessions, then how Phase 13/S7 and the rest of the remaining pipeline compare, then for a proposed
  session-bundling plan sized like the Phase-11+7 precedent (~2,000 lines). Sized every remaining item off
  `git diff --stat` on past commits (two clusters: full-phase sessions ≈700–2,000L/10–21 files/5–15 tests
  — Phase 9 728L, Phase 8+6-wiring 1,926L, Phase 5 1,423L, MVP spine 1,496L, Phase 11+7 2,000L, T3+T4 547L
  — vs. single-file deliverables ≈60–150L — 11.3 `personalities.py` 109L, 5.5 `utility.py` 58L). **Key
  finding: Phase 13/S7 is greenfield** (`inseason/` package doesn't exist yet) and its 5 substeps aren't
  uniform — 13.3 (FAAB bandit/auction theory) and 13.5 (trade market-making) are new-domain and heavy
  (~250–400L each) — so it's **full-phase-sized on its own (~1,400–2,100L), unlike S6 or the tech-debt
  items.** Proposed bundling (written into `ROADMAP.md` ★ SESSION SIZING GUIDE + `CLAUDE.md` next-session
  pointer): **Session A** S6+13.1–13.2 → **Session B** 13.3–13.5 → **Session C** Phase 12+Phase 15 (bundled
  like 11+7) → **Session D** optional MCTS/RL gate+T5+LOCKBOX (closeout) → **Session E** Phase 14.1 alone
  (never bundle onto Phase 14) → **Session F+** Phase 14's go-live tail (14.2–14.7, multiple sessions
  expected). Explicitly a **planning aid, not a hard rule** — re-estimate once building starts if actual
  scope diverges. Docs-only, no code changed. **Next session: Session A (S6 + 13.1–13.2).**
- **2026-07-11 (g)** — **PIPELINE REORDER (docs-only) — S6 moved ahead of Phase 13/S7.** A prior-session
  review of ★ THE PIPELINE's locked order (2026-07-09), checked against actual dependencies rather than
  write order, found one change worth making: **S6 — adaptive archetypes** has zero dependency on Phase 13
  or 12 (its done-bar — adaptive beats its static parent when the board diverges from ADP — is detected by
  the Phase-11 availability model and validated in the 11.3 personality-tilted simulator, both already
  built), so it moves from between Phase 13 and Phase 12 to **immediately next**, reusing the still-warm
  opponent-model/optimizer context instead of re-deriving it later. Everything else in the locked order
  checks out on dependency grounds and is unchanged: **Phase 13/S7 before Phase 12** (13.1–13.5 run on
  existing infra, nothing gated on Phase 12 — 13.1 should reserve a generic news-feature slot so Phase 12
  plugs in later without a rebuild), **Phase 12 before Phase 15** (Phase 15's auction support extends the
  Phase-11 opponent model, so it belongs after the draft-engine-consuming phases settle), the **optional
  MCTS/RL research gate last among build steps** (benchmarked against the final greedy/win-prob policy),
  and **T5 → LOCKBOX → Phase 14 as a strict tail** (T3+T4 already ☑ done 2026-07-11; only T5 pre-registration
  remains before the one-shot lockbox). New pipeline order: **S6 → Phase 13/S7 → Phase 12 → Phase 15 →
  optional gate → T5 → LOCKBOX → Phase 14.** Docs-only — no code changed. Updated `ROADMAP.md` (★ THE
  PIPELINE block + Phase 12/13 stage labels + spine S6/S7 line), `CLAUDE.md` (next-session pointer), and
  `docs/BUILD_PLAN.md` (13.1 design note re: the news-feature slot). **Next buildable item: S6.**
- **2026-07-11 (f)** — **PHASE 11 (draft engine core) DONE + PHASE 7 (opportunity-adjusted
  projection) BUILT & DROPPED — one autonomous session.** User authorized a combined
  Phase-11→Phase-7 run **fully autonomously** (STOP gate §3.7 waived for the session), with four
  up-front decisions: **all 149 human drafts** in the fit pool (opponent model predicts *draft
  flow*, not player value → treated as outside the value-stack lockbox; every reported metric is
  still walk-forward), the **as-written** keep-or-drop bar, and the **full 4-substep** Phase 7
  (incl. a fresh rookie transport).
  - **Phase 11.1 — behavioral opponent model (`draft/opponent_model.py`)** ✅ **DONE-when MET.**
    A **conditional (McFadden) logit**: at each pick the manager chooses one of the top-40 available-
    by-ADP skill candidates; utility = β·features, choice prob = softmax over the candidate set;
    fit by MLE (grouped-softmax NLL + L2, vectorized `reduceat`, scipy L-BFGS) on **7,900 real
    human picks / 9 seasons** (FFC as the *external* ADP board — no corpus circularity). Coefs
    tell the behavioral story: **fandom +1.03** (home-team reach — the strongest signal),
    **rookie hype +0.45**, **roster need +0.33**, mild run-chasing +0.07, TE/QB go a touch earlier
    than raw ADP. **Beats the ADP-only baseline** (a logit on ADP alone = "ADP + logistic noise")
    leave-one-season-out: **log-loss 3.613→3.501, gain +0.113 CI[+0.101,+0.124]; Brier gain
    +0.0088 CI[+0.0076,+0.0100]** — CIs exclude 0. *(Two bugs found+fixed mid-build: a scalar-
    reduction in the NLL; and `fav_teams` is stored **comma-separated**, not JSON — the broken
    `json.loads` had silently zeroed fandom, and fixing it ~tripled the log-loss gain.)*
  - **Phase 11.2 — availability distributions + the owed availability Brier (`draft/availability.py`)**
    ✅ **DONE-when MET.** MC-simulates the intervening opponent picks under the fitted model to get
    per-player **survival to your next pick**; scored on real draft windows vs the incumbent
    `survival_prob` (ADP+noise). Compared against the **best-tuned** noise (grid 3–36) to avoid
    strawmanning: **behavioral Brier 0.158 vs best-tuned ADP+noise 0.316** (default-noise-5 is a
    dismal 0.419 — the MVP placeholder is badly overconfident on the contested band), **gain +0.159
    CI[+0.083,+0.264]**. The behavioral availability oracle earns promotion from opt-in to the S4
    default.
  - **Phase 11.3 — realistic mock opponents (`draft/personalities.py`)** ✅ capability delivered.
    A `Personality` = a light tilt on the fitted β (scale/override a coef, temperature, round-
    dependent positional penalty); `make_opponent_pick_fn` plugs into `simulate_draft` via a new
    **backward-compatible `opponent_pick_fn` hook** in the simulator. Behavioral opponents draft a
    realistic first-3-rounds mix (**RB14/WR14**) vs pure ADP+noise's robotic **RB21/WR9**; `zero_rb`
    collapses early RBs to 5 — personalities differentiate as designed. (Tier-B tilts fandom/rookie
    need an enriched board to express; documented.) *MCTS/CFR/auction/self-play remain deliberately
    out of scope — deprioritized/dropped/roadmap per the reframe; Phase 11's verifiable core is
    complete.*
  - **Phase 7 — opportunity-adjusted projection (`causal/`, 4 substeps)** ✅ built, **VERDICT =
    DROP.** 7.1 `decompose.py`: a **two-way fixed-effects (AKM worker/firm) split** of position-and-
    season-relative log-ppg into **skill** (per player, transferable) × **situation** (per team),
    ridge-regularized, movers identify the split — top skill = Kelce/CMC/A.Brown/Kamara (elite,
    team-independent → face-valid). 7.2 `counterfactual.py`: situation swap as an **information-
    preserving delta** on the player's realized prior rate (`log opp = log prior − sit_old +
    sit_new`; non-movers ≡ naive). 7.3 `rookie_transport.py`: draft-capital + landing-spot situation
    + combine → rookie **distribution** (point+interval) — *this one works* (1σ coverage 0.66,
    Spearman +0.53) but duplicates Phase 4.3. 7.4 `validate.py`: strict walk-forward.
    **The gate:** on role-changers (466 movers) the situation swap is a **wash-to-slightly-worse
    than naive** (ppg-MAE 2.972 vs 2.901, gain −0.070 **CI[−0.152,+0.014] includes 0**), and the
    existing **EB-shrunk market baseline actually beats it** on movers (2.821). Overall it's within
    tolerance of market, but it fails the "strictly better on role-changers" half → **DROP** on the
    as-written bar. Also 7.1's estimated skill does **not** travel better than raw prior production
    (Spearman 0.458 vs 0.587). **Honest, thesis-consistent negative result** (the keep-or-drop gate
    doing its job — a team fixed-effect carries no exploitable move signal beyond carrying the rate
    forward; consensus already prices it). Code kept in-repo as a validated-and-dropped experiment
    (like props/CFR).
  - **Integration/discipline:** the behavioral model ships **opt-in** and only *displaces* ADP+noise
    where it won its Brier gate (calibration > edge). Scorecards: `analysis/phase11_opponent_model.json`,
    `analysis/phase7_opportunity.json`. **+15 tests (9 new, all green), 243 total, ruff clean.**
    Runnable: `steps/phase11_opponent_model.py`, `steps/phase7_opportunity.py`.
- **2026-07-11 (e)** — **0.10c: LEAGUE-SEEDING + REAL LIVE CORPUS.** User couldn't find live human mock
  lobbies (too early in season) → chose to **web-search public leagues**. Reframe: live mocks are moot — the
  crawler reads *historical* leagues (all public now, and better: realized outcomes for the Brier). Enhanced
  `crawl_expand` with `league:<id>` seeding + iterative BFS snowball; web-found + validated the **Sleeper
  API-docs public example leagues** (`289646328504385536` 2018-12tm, `206827432160788480` 2017-10tm — real
  human drafts, `picked_by` fully populated → confirmed real-league opponent identity). Live crawl snowballed
  to **149 human + 117 bot drafts (2017–20), 289 manager profiles, `sleeper_human` board ≈2,580 rows, skill
  99.8 %** — **Phase-11 data blocker cleared.** Two live-data bugs fixed: `_upsert` → type-drift-safe full
  rewrite (league_id first seen all-NULL→INT32); reach join → season-aware + dedup (`_attach_reach`). Quality
  filter: derived artifacts use **complete snake/linear only** (44 % of crawled drafts are abandoned); gate =
  **no duplicate pick_no** (incompleteness reported, not failed). **234 tests, ruff clean, all gates PASS.**
  Next modeling step: the actual Phase-11 opponent-model fit + availability Brier on this corpus.
- **2026-07-11 (d)** — **0.10b SLEEPER CORPUS CRAWLER DONE** (same session, on top of 0.10). User data plan:
  gather real-human drafts via **human mock lobbies**, build the corpus infra now. Shipped in `sleeper.py`:
  `crawl_expand` (BFS from seed usernames' histories + **participant expansion** — a human draft's `draft_order`
  seats → crawl their histories, so one human lobby multiplies into its ~10 humans' leagues), `crawl_user_history`,
  `participants_from_draft`, `manager_profiles` → `sleeper_manager_profiles` (behavioral seed), **human/bot ADP
  split** (`sleeper_human` vs `sleeper_mock` — bot ADP never dilutes human ADP), `is_human` tag per draft,
  schema-drift-safe `_upsert`, `load_seeds` + `reference/sleeper_seeds.txt` registry, `crawl_and_ingest`.
  `steps/phase0_10b_crawl.py` done-bar (honest verdict tiers by human-draft count). Verified offline (fake-client
  crawl + participant-expansion tests, manager profiles, board split) + live smoke test. **Data-appetite
  finding:** ~50 real human drafts min / ~100–150 ideal for a Brier-verifiable opponent model; bot mocks add ADP
  only. **232 tests, ruff clean.** Fit still blocked on real-human drafts. See `docs/SLEEPER.md`.
- **2026-07-11 (c)** — **STEP 0.10 SLEEPER INGEST DONE** (pick-by-pick data pipe; `docs/TECH-DEBT.md` T8b
  0.10 ☑, reference `docs/SLEEPER.md`, findings write-up added). User banked **3 mock drafts** (`MadBawa`);
  ingested + verified end-to-end. **Design decisions this session (user):** *stretch* scope (plumbing +
  first behavioral/ADP artifact + sim wiring, not just plumbing); build **corpus-ready** for many mocks +
  real leagues; leave uncommitted. **What shipped:** `data/sources/sleeper.py` (keyless public API;
  `fetch/parse/crosswalk/ingest`, corpus intake by id **or** username/league discovery, `picked_by`
  captured for real-league identity); `sleeper_drafts` + `sleeper_draft_picks` (idempotent upsert by
  `draft_id`); gsis crosswalk **100 % skill / 80 % K / DEF→`dst_team` bridge**; `build_mock_adp` →
  `sleeper_mock` rows in `adp_snapshots` (so `adp_asof(source=...)` + the simulator consume it **unchanged**
  — verified by drafting a 2026 mock); `build_tendencies` POC (`sleeper_tendencies`, per-slot cadence +
  reach); 3 pure gates in `validate.py`; `steps/phase0_10_sleeper_ingest.py` done-bar; `tests/test_sleeper.py`
  (10 tests, offline fixture). **Key finding:** mocks are solo-vs-bots — `picked_by` is set for the human's
  own picks only, so the **behavioral fit** (Phase 11) needs **real human leagues**, not mocks; the ingest is
  built for that. **226 tests, ruff clean.** Next buildable: **Phase 7**; Phase-11 fit waits on real leagues.
- **2026-07-11 (b)** — **T3 + T4 DONE** (pre-lockbox modeling pair; `docs/TECH-DEBT.md` T3/T4 ☑, full write-up
  in `findings.md`). Attribution-first overturned both specs: (T4) the bias is all offense/CoV-path — K/DST
  fallbacks run **+16** (jittering worsens it, left alone) and per-player weekly CoV is already calibrated;
  the cause is the mean-preserving Dirichlet split's light tails understating the lineup **max**. (T3) the
  dominant miss is *barely-plays* (availability), not *plays-worse*. Shipped: **T3-A** cohort availability
  prior (`injury.cohort_availability_prior`, `pos × draft-capital tier`) — the main lever; **T3-B** role-loss
  **washout** mixture (`injury.role_retention`, availability channel, deep-tier only) — reformulated from the
  planned production haircut, which added ~0 coverage; **T4** `weekly.SPREAD_KAPPA` per-position effective-CoV
  inflation (mean-preserving) + 2-season CoV pooling. **κ = {QB 1.4, RB/WR 1.8, TE 1.7}** = the highest κ
  keeping every hard gate passing (κ trades coverage/bias against sim over-dispersion + the dog-leverage gate).
  **Results:** 2025 holdout uncond coverage **44 %→77 %**, cond **76 %→76 %**; Phase-10 points coverage
  **62 %→77.2 %**, bias **−137→−113**, title Brier 0.0881, playoff 0.2342, all gates PASS (1,800 team-seasons);
  216 tests, ruff clean. Residual bias documented (early/COVID + projection-level; probabilities are relative
  so calibrated). Tuned only on DEV; 2025 read once. **Next: T5 pre-registration before the lockbox.**
- **2026-07-11 (a)** — **NEXT-SESSION DECISION + Sleeper account status (see `docs/SLEEPER.md`).** The pipeline's
  strict-next item (step 0.10 Sleeper → Phase 11 opponent model, **T8b**) is **blocked on draft data**: the
  user created a Sleeper account (`MadBawa`, user_id `1381536159267573760`) but it is **brand-new and empty**
  — no leagues, no drafts (verified via the public API; identity resolves, no data behind it). An empty
  account can't be ingested/fit. **Unblock path** (cheapest first): (1) user runs **1–2 mock drafts** →
  a real `draft_id` to build+test the ingest (plumbing only, bot mocks = weak behavioral signal); (2) a real
  human league draft (gold standard, seasonal — Aug–Sep 2026); (3) a corpus of public draft_ids for a scaled
  ADP board. **Recommended next session while Sleeper is empty: T3 + T4** (the pre-lockbox modeling pair —
  downside coverage 44 %→≥70 % + sim level bias −137→~0; autonomous, mandatory before the lockbox, and it
  hardens the exact distributions the Phase-9.5 win-prob objective consumes). Return to Sleeper once draft
  data exists. **Both this session's commits (T7 `ed147bf`, Phase 9 `fd261b4`) are local — not yet pushed.**
- **2026-07-10 (c)** — **PHASE 9 COMPLETE** (9.1 scarcity · 9.4 lookahead · 9.5 win-prob objective) **+ T6**.
  **9.1 scarcity/9.4 lookahead:** `positional_cliff` (value drop to the next same-position tier) × `1 −
  survival_prob` (snake-aware ADP+noise survival to your next pick) → an **urgency** term folded into
  `RiskModel.effective_rank` (`scarcity_w·cliff·(1−survival)`); `scarcity_w=0` reproduces the covariance-only
  greedy exactly (pinned the Phase-8 regression test to `scarcity_w=0`). **T6:** `cached_distribution`
  memoizes the Phase-5 cloud on `(season, ruleset, n_draws, seed)`; `assemble_value` (+ threaded `seed`) and
  `build_weekly_model` both read it — one joint cloud, no silent divergence. **9.5 win-prob (T8a):** opt-in
  `winprob_pick_fn` — portfolio-CE/scarcity prefilter → top-k → finish the draft greedily per candidate →
  Phase-10 **mini-sim** → argmax the routed metric (`make_playoffs`→playoff_prob,
  `championship_or_bust`→title_prob), CRN across candidates; refactored the simulator (`DraftState.clone`
  + `run_to_completion`) to support the rollout. **2022 DEV:** objective swings **8–9 roster slots**,
  title-max **+0.09 title prob** at 250 sims. **Dead end / caveat:** at 60 sims the title objective chases
  noise (under-performs make_playoffs) — title is a ~1-in-10 event → needs ≥~200 sims; default
  `winprob_sims=200`. `steps/phase9_policy.py` + 7 tests; 210 tests pass, ruff clean; cost-report spine
  re-validated with scarcity on. **Next: step 0.10 Sleeper ingest → the behavioral opponent model (T8b).**
- **2026-07-10 (b)** — **T7 done** (opportunistic, while in the data layer): scrape freshness/schema gates in
  `data/validate.py` (`adp_freshness_gate` = the §2 chore as an assertion, `board_size_gate`,
  `match_rate_gate`) wired into `data_health_report`; `cache.archive_text` date-stamps raw FFC/FantasyPros
  payloads under `data/raw/**/payloads/` for last-good diffing; **props/markets layer formally SHELVED**
  (user decision) — not a silent no-op. +10 tests.
- **2026-07-10** — **FULL-CODEBASE AUDIT → remediation register opened (`docs/TECH-DEBT.md`).** Reviewed the
  whole engine in detail (simulation, covariance/distribution/injury core, valuation spine, config); 194
  tests pass, ruff clean, code healthy. Catalogued **8 problems with exact long-run fixes** — the durable
  "what's left to fix" source of truth is now **`docs/TECH-DEBT.md`** (ids T1–T8), sequenced into ROADMAP ★
  THE PIPELINE: **T1** commit the uncommitted Phase-10/Stage-0 work (now) · **T2** back up the irreplaceable
  data — 2026 ADP snapshot series + 2025 backfill live only on the WSL disk, gitignored (now) · **T3**
  under-modeled downside (unconditional coverage 44 % / points 62 %: injury gate `prior_games≥8` excludes
  rookies + **no role/depth-attrition term** → add cohort availability prior + a role-survival haircut
  `Y=H·(G/G_ref)·R`) · **T4** sim level bias −137 pts/team (prior-yr CoV understates weekly spread feeding the
  lineup max; flat K/DST + cloudless fallbacks) — do with T3, **both before the lockbox** · **T5**
  de-risk the one-shot lockbox (pre-register the frozen stack; 2025 full-stack dress rehearsal; track DEV
  decision count) · **T6** consolidate the Monte-Carlo draws (recomputed / silently diverge across optimizer
  & sim once seeds differ) — fold into 9.5 · **T7** scrape freshness/schema guards + settle the props no-op ·
  **T8** make `objective` real (9.5, currently a dead label) + the behavioral opponent model (0.10→Ph11). No
  code changed this session — audit + docs only.
- **2026-07-09 (b)** — **STAGE 0 LIVE + PHASE 10 DONE (all gates PASS).** (a) **Stage 0:** FFC **2026
  snapshot series** banked (1,028 rows, full grid, 99.3 % gsis — the rookie class already resolves;
  `snapshot_adp` = date-keyed raw cache + replay-append on `(config, snapshot_date)`, idempotent +
  self-healing; **weekly chore encoded in CLAUDE.md §2** — Claude cron is session-only, so the standing
  instruction + optional Windows Task Scheduler carry it). **Sleeper probe:** identity SOLVED — Sleeper's
  own gsis field is 31 % sparse but nflverse `player_ids.sleeper_id` → gsis covers **99.0 %** of draftable
  top-300 (cast the DOUBLE, strip padded gsis whitespace); **no public ADP endpoint** (derive from drafts);
  pick-by-pick shape needs a real league → 0.10. (b) **Phase 10** (`simulation/{weekly,season,playoffs,
  leverage}.py`): user decisions — 14-reg/6-team/15–17 format (parameterized), **top-down weekly
  disaggregation** (season draws from the Phase-5 sampler w/ `return_games`, board-wide Phase-8 Σ via an
  Iman-Conover **permutation** so G rides with its draw, Dirichlet(α=1/CoV²) shares, real byes, uniform
  missed-week placement; weeks ≡ season draw ⇒ Phase-5 calibration survives by construction); optimal
  lineups for all teams (vectorized ≡ 1.3 reference); K/DST + cloudless players = prior-season constants.
  **Calibration gate PASS (1,800 team-seasons, 2017–22 × 30 ADP+noise leagues):** title Brier **0.0878 <
  0.090** w/ on-diagonal reliability; playoff **0.2302 < 0.240**; league-spread ratio **1.02**; stability
  0.975/0.949; leverage @ wk8: dog **+0.018** playoff prob at 1.6×, leader **−0.028** (the lever = making
  the cut; title ≈ neutral between equal teams). *Documented:* 62.4 % points coverage (Phase-5 attrition
  propagates) + **−137 pt level bias** (suspects: prior-yr CoV understates realized weekly spread feeding
  the lineup max; replacement-constant fallbacks) — probabilities are relative and calibrate anyway.
  194 tests, ruff clean. **Next: Phase 9 completion (9.1 scarcity · 9.4 lookahead · 9.5 win-prob objective
  on the now-calibrated title/playoff probs).**
- **2026-07-09** — **PHASE 8 DONE + PHASE-6 WIRING DONE + THE PIPELINE LOCKED.** (a) Phase 8 covariance
  (`covariance/{estimate,shrinkage,copula}.py`, `valuation/{roster_risk,handcuff}.py`): relationship-typed
  pooled correlations (QB1-WR1 **+0.37** emp ≈ folk +0.40; RB1-RB2 both-active only −0.05 — backfield
  negativity lives in availability, hence the copula), EB shrink toward structural priors (OOS: halves
  stack-variance error vs independence), rotated-Clayton handcuff tail (0.391 vs 0.393 empirical; Gaussian
  0.346), roster risk + Iman-Conover, handcuff real option (elevation 1.77). **9.1's covariance half pulled
  forward** (user choice): the greedy maximizes marginal portfolio CE, λ=0 reproduces the old greedy exactly;
  cost-report headline = portfolio CE + risk profile; spine re-validated (conclusions unchanged). (b) Phase-6
  softness **wired into the cost report** (user choice: credit + net line, raw headline never moved):
  frozen `adp/softness.py::DURABILITY` (+14.59 VOR/SD, μ=10.57 σ=6.37) → roster exposure gap × coef; drift
  check in `steps/phase6_adp_bias.py`. 175 tests, ruff clean. (c) **PIPELINE DECISION (user, 2026-07-09):
  engine-complete-before-app, no time crunch — the formerly-deferred Phases 12 (news/NLP, edges-only LLM
  guardrail intact) and 15 (multi-format + auction) are IN scope before any app work; Phase 14 comes last
  with everything embedded.** Order (ROADMAP ★ THE PIPELINE): stage-0 passive FFC-2026 snapshots + Sleeper
  probe → Ph10 (+weekly grain) → Ph9 completion → 0.10 Sleeper→S4/Ph11 → Ph7 (keep-or-drop) → Ph13/S7 → S6 →
  Ph12 → Ph15 → optional MCTS/RL gate → **lockbox eval once** → Ph14 app. **Next: stage 0 + Phase 10.1.**
- **2026-07-07** — **PERSONALIZATION SPINE DONE (S1–S3 + S5)** — the direct-indexing MVP, run straight-through
  (gate waived, per the 4→5 cadence). Built/validated on **DEV 2022** (latest non-lockbox season w/ ADP +
  realized); **season is a parameter** (a scraped 2026 board drops in unchanged). **S1** `draft/config.py` —
  `DraftConfig` (the contract we own): league context, one **archetype** (master positional dial), hard
  `never_draft` + `must_draft`(reach budget), soft `tilts` (rounds), `risk_lambda`; validated on construction;
  `benchmark()` strips prefs, `without_constraint`/`constraint_labels` drive LOO. Trimmed to §7 MVP (no fandom/
  correlation/control-tier fields until needed). **S2** `draft/optimizer.py` — constrained greedy over the
  Phase-1.2 simulator (pluggable `your_pick_fn`, no new engine). **`base_value` = risk-adjusted
  value-over-replacement** (Phase-5 CE − positional replacement; VBD scale + λ dial in one); tilts convert
  rounds→priority (`eff = base_rank − n_teams·tilt`); **must-draft = pure availability planning** (take at the
  last responsible pick within budget, using snake geometry + noise margin — never overreach). **S3**
  `valuation/cost_report.py` — personalized vs `benchmark()` over the **same seeds**, differenced into one
  headline (pts + %), attributed per preference by **leave-one-out**, + must-player **secured fraction**;
  relative/directional per §7 (walk-forward realized-PAR = next layer). **S5** risk dial wired in (λ → CE →
  `base_value`). **UI** `app/streamlit_app.py` — Streamlit Autopilot (archetype+seat) + Co-pilot (λ, must/
  never/reach/wait), personalized board **beside** the baseline + cost readout, no LLM. **Bug caught:**
  stateless archetype tilts made `elite_te` draft **two** TEs → made archetypes **roster-state-aware** (`have`
  count) so "grab one anchor" stops after the first (regression-tested). **137 tests (was 120), ruff clean; 3
  spine step scripts green; Streamlit app verified via `AppTest`.** `streamlit` added as a `ui` extra. **Next:
  Phase 8 covariance (portfolio Var under the same λ) · S4 behavioral opponent model · realized-PAR validation
  · scrape 2026 ADP to go live.**
- **2026-07-05** — **PHASE 5 DONE** (distributional layer — the per-player risk dial; full 5.1–5.5 stack,
  season-total grain). **5.1** per-position linear `QuantReg` of realized pts on the calibrated mean, fit on
  the conditional/available DEV cohort (1,074 player-seasons; median slope ≈1.10; band fans with level 3/4
  pos). **5.2** CQR (Romano 2019) per-pos adjustment (QB +18/WR +3/RB +2/TE +0 on [2021,2022]); **2025
  holdout coverage 70%→73%** on the available cohort. **5.3** weekly boom/bust: right-skew confirmed (TE
  +1.60…QB +0.23); **corr(boom,CoV) −0.37** ⇒ boom rate is a level axis, separate from volatility. **5.4**
  logistic **discrete-time availability hazard** (31.6k player-weeks) → **Beta-Binomial games-played**
  (ρ=0.33, keeps the lost-season tail); coefs sane (prior-avail +0.42, RB least available). **Assembler**
  `distribution.py`: `Y=H·(avail_frac/G_ref)` Monte-Carlo cloud (2000 draws) → frozen contract
  `player_key·pos·mean·sd·q10·q50·q90·boom_prob·bust_prob·games_played_mean·ce_value`; **5.5** mean-variance
  CE `E[Y]−λ·Var[Y]` risk dial + `risk_premium`. Wrote `player_distributions` (673 rows, 2025). **2 real bugs
  fixed** (both on 2025/first-season paths 5.1–5.4 never hit): `value_board` crashed on an empty projection
  season (2014 has no proxy → empty arrow-string − float) → guarded to return an empty contract frame; and a
  **units bug** `G/G_ref` (games *count* ÷ *fraction*) inflated means ~17× → fixed to `(G/team_games)/G_ref`
  (regression-tested). Conditional 2025 coverage **76% ≈ 80%**; unconditional full-board **44%** = **role/depth
  attrition** the injury-only model doesn't capture (documented limitation → future work). **Method deviations
  (accepted, no new deps):** statsmodels `QuantReg` not XGBoost (5.1); sklearn logistic hazard not `lifelines`
  (5.4) — future intent to adopt XGBoost-quantile / `lifelines` if the sample justifies it. 120 tests, ruff
  clean; all 5 steps green. **Next: personalization spine — `DraftConfig` + constrained greedy optimizer +
  first cost report → Streamlit MVP** (Phase 8 covariance slots in via the same λ/Var).
- **2026-07-05** — **PHASE 4 DONE** (VALUE signal, reframed = consensus-VBD, not edge-seeking). **4.1**
  two-track consensus (`projections/consensus.py`): live = FantasyPros scrape re-scored to full-PPR via our
  `RuleSet` (528 players, 99% gsis, our-pts↔FP-FPTS corr 1.000; retry-guard beats FP's transient truncated
  pages), historical = Phase-2 baseline **proxy** (no free historical consensus exists); one
  `consensus_projection(season)` dispatches. **4.2** VBD value board (`valuation/value_board.py`): draft-time
  replacement from **projections** (realized doesn't exist for the season being drafted) at QB10/RB24/… ranks
  → QBs drop 6→0 in top-15 vs raw; **frozen contract** `player_key·pos·proj_points·source·vbd·pos_rank·
  overall_rank`. **4.3** rookie ridge (`projections/rookie.py`): closed-form per-position on log(draft_ovr)+
  landing-spot env, walk-forward; OOS Spearman **+0.62**; +76 rookies into the 2021 proxy board. **4.4**
  calibration (`projections/calibration.py`): proxy bias **0.60** played / **0.46** incl-DNP (survivorship
  haircut), reliability bin-corr 0.99, per-pos correction → 0.96; **2025 holdout (once): bias 0.58, Spearman
  +0.57**. Doc numbering reconciled (BUILD_PLAN/PROJECT had stale pre-reframe 4.x). 102 tests, ruff clean.
  **Next: Phase 5 — full distributional layer (user chose 5.1–5.5), wraps the 4.2 contract.**
- **2026-07-05** — **PHASE 3 DONE** (features `X`). 3.1–3.4 realized per-(gsis,season) facts (opportunity/
  efficiency/player/environment); 3.5 `build_exposures(target)` applies the PIT lag (prod←S-1, intrinsic
  as-of, env←S-1 of target team), winsor-z per position, missingness flags. **545×48 matrix**; 100%
  ADP-board cover; lagged WOPR↔next-yr pts +0.46; TD-regression flag −0.50; implied-total↔pts +0.86.
  92 tests, ruff clean. **Next: Phase 4 — consensus-projections ingest + VBD + rookie model** (needs a
  consensus source decision first).
- **2026-07-05** — **0.9 DONE** — 2025 backfilled via nflverse's new `stats_player` release (frozen
  `nfl_data_py` hits the dead old path). weekly→79,250 / seasonal→8,702 (2025 reconstructs PPR to 2.4e-6);
  timestamped `depth_charts_ts` (554k); validator PASS. Lockbox = **2023+2024**; **2025 = calibration
  holdout** (`config.CALIBRATION_SEASONS`; no ADP board → not a draft-backtest season). **Next: Phase 3.**
- **2026-07-04** — **⟳ STRATEGIC REFRAME** (`docs/REFRAME-2026-07-04.md`, `docs/PERSONALIZATION.md`):
  objective → **direct-indexing personalization** (build the team the user wants, price the cost vs
  optimal); team strength = tracked benchmark, "beat ADP" demoted. **Three signal layers:** value =
  consensus-VBD, availability = ADP+behavioral, variance = own distributions. Docs updated (STRATEGY Part
  0, PROJECT, ROADMAP, BUILD_PLAN, CLAUDE, glossary, findings). **Next: the personalization spine on Phases
  0–2** — Phase 3 `X` → consensus ingest+VBD+rookie → trimmed distribution → constraint object + optimizer
  + cost report → Streamlit MVP. **No code changed; Phases 0–2 valid.**
- **2026-07-04** — **PHASE 2 COMPLETE.** 2.1 VBD, 2.2 naive baseline (on par w/ ADP: −59 PAR/season
  CI[−162,+33]), 2.3 props (built+tested; **free-data gap** → no-op), 2.4 ensemble (grid-fit w=0.25 →
  2116 ≥ best component; vs ADP +80 CI[−22,+190] not-sig). Lesson: **don't fight the sharp market.**
  **Next: Phase 3 — feature engineering (exposure matrix X).**
- **2026-07-03** — **PHASE 1 COMPLETE.** Phase **1.5 done** (significance: stationary block-bootstrap CIs;
  ADP-vs-ADP edge 0 not-sig; worst-first −577.6/season CI [−714,−438] sig; block SE 0.239 > iid 0.090).
  Harness scores any rank_fn end-to-end PIT with CIs vs ADP in one call.
- **2026-07-03** — Phase **1.4 done** (PAR metric: replacement levels QB10/RB24/WR24/TE12/K10/DST10,
  2023 roster 1743; PAR ranks elite +818 vs scrub −943; PAR↔exp-wins corr 0.99).
- **2026-07-03** — Phase **1.3 done** (walk-forward harness: rank_fn → K drafts → realized optimal-lineup
  points, strict PIT; ADP baseline pools 2036, worst-first 1458 → harness discriminates; PIT guard trips).
- **2026-07-03** — Phase **1.2 done** (draft simulator: 10×15 snake, ADP+Gaussian-noise opponents,
  pluggable `your_pick_fn`, `DraftState`; ADP-typical roster + reproducible).
- **2026-07-03** — Phase **1.1 done** (scoring engine: full-PPR offense reconstructs nflverse
  `fantasy_points_ppr` across 57.3k player-weeks to 1e-6; K/DST derived from pbp/game_lines; K/DST
  identity bridge). League lineup settled: **9-starter QB/2RB/2WR/TE/FLEX+K+DST**.
- **2026-07-01** — **PHASE 0 COMPLETE.** 0.8 done (9 hard gates PASS, `data_health.json`; gate caught+fixed a
  0.4 homonym-collision bug). 16 tables, PIT panel layer, validator. **Next: Phase 1 — backtest harness.**
- **2026-07-01** — Phase **0.7 done** (weekly+preseason PIT panels, leak-assert, 41-col join).
- **2026-07-01** — Phase **0.6 done** (injuries/depth free 2014+, news_raw RSS pipe, PIT).
- **2026-06-30** — Phase **0.5 done** (game_lines free 2014–25, de-vig + implied totals; props key-gated).
- **2026-06-30** — Phase **0.4 done** (FFC ADP 2010–2024, PIT, gsis-matched; Underdog deferred).
- **2026-06-30** — Phase **0.3 done** (PFR advanced panels via nflverse mirror; reconciles 0.00%).
- **2026-06-30** — Phase **0.2 done** (nflverse → DuckDB, 8 tables, PIT-stamped).
- **2026-06-29** — Environment scaffolded; docs restructured into the granular Phase 0–15 plan (`PROJECT.md`)
  with Vegas markets promoted to a first-class data source.

## Working notes (per step)
**0.2 nflverse:**
- `gsis_id` is the spine. weekly/seasonal expose it as `player_id` (rename); ngs as `player_gsis_id`;
  **snaps has only `pfr_player_id`** → mapped via `player_ids.pfr_id` (pure fn `map_snaps_gsis`, unit-tested).
- Years default `2014..2025`; per-year pulls **skip-on-404** so an unpublished season can't abort the run.
- PBP loaded from a per-season parquet glob with `union_by_name=true` (handles cross-season schema drift);
  small sources written straight from pandas. Raw cache in `data/raw/nflverse/` → `--refresh` to re-pull.
- **Coverage asymmetry to remember:** PBP/snaps/draft/combine reach 2025; weekly/seasonal stop at 2024.
  Fantasy-point history (the backtest target) is therefore **2014–2024**.
- Toolchain note: run tests as `uv run python -m pytest` (the `pytest` console script won't spawn here).

**0.3 PFR:**
- Used the **nflverse PFR mirror** (`import_seasonal_pfr`) over direct PFR scraping — robust/reproducible,
  same data. Tables `pfr_pass`/`pfr_rec`/`pfr_rush` (kept split; `yds` means different things per type).
- **PFR advanced data starts 2018** → those features usable 2018–2024 only.
- Reconciliation (PFR yds == seasonal yds, 0.00%) doubles as a **join-correctness gate** on pfr_id→gsis.
- Unmatched ids (mostly O-linemen) logged to `data/raw/pfr/unmatched_pfr_ids.csv`; hand-fix genuine skill
  misses in `reference/pfr_id_overrides.csv`.

**0.4 ADP:**
- Source = **FFC JSON API** (`/api/v1/adp/{scoring}`); grid {standard,ppr,half-ppr}×{10,12}×2010–2024.
  `meta.end_date` = PIT `snapshot_date` (late-preseason). One snapshot per season-config.
- FFC has no gsis → `match_adp_to_gsis` 4-tier (team+pos+name → pos+name w/ draft-year tie-break → name →
  nickname override). Nickname misses fixed in `reference/adp_name_overrides.csv` (Hollywood→Marquise Brown…).
- **Underdog deferred** (auth-gated; no free history). Schema format-aware (`format='redraft'` for FFC).
- Gotchas: `rows` is a DuckDB reserved word; `.df()` returns DATE as pandas Timestamp.

**0.5 markets:**
- `game_lines` from nflverse `import_schedules` (free, 2014–25). `spread_line` = **home margin** (verified
  KC/DET). `implied_team_total = ((total+spread)/2, (total−spread)/2)`. Closing lines only (no movement).
- `devig` proportional; `fair_two_way` for moneylines (sums to 1, machine-epsilon). `captured_at = gameday`.
- Player props: `parse_props_payload`/`ingest_player_props` built + tested but **key-gated** (`ODDS_API_KEY`);
  no-op without a key. Win totals: `import_win_totals` empty → deferred.

**0.6 news:**
- `injuries` + `depth_charts` free/historical via nflverse, **native gsis** (no name-match). injuries PIT stamp
  = `date_modified`; depth grain = (season, week). `injuries_asof` proven PIT.
- `news_raw` = **forward-capture** RSS (ESPN/CBS/Yahoo); appends + de-dupes by `guid` → accumulates over time
  (schedule a periodic re-pull later). No gsis yet (entity resolution = Phase 12).
- **Inactives deferred** (no free historical importer; derive from snaps==0 or forward-capture).

**0.7 panel:**
- `weekly_panel`/`preseason_panel`; known-at gating: weekly-grain → week's last gameday (from game_lines),
  ADP → snapshot_date, injuries → date_modified. `assert_panel_pit` raises on any future-dated field.
- **FFC ADP is dated ~Sep 1** → preseason draft as-of must be ≥ that (Labor-Day weekend); earlier = empty board.
- `game_lines.gameday` is VARCHAR → cast to DATE for week-end mapping. NGS join = receiving-only for now
  (full multi-type pivot in Phase 3). team abbrevs (weekly.recent_team ↔ schedules) join directly.

**0.8 validate:**
- `validate_panel` raises on dupes / negative counting stats / bad snap% / PIT leak; `data_health_report`
  writes committed `analysis/results/data_health.json`. Only **counting** stats gated ≥0 (yardage can be neg).
- The adp-uniqueness gate **caught a real 0.4 bug**: homonyms (two 2010–11 "Mike Williams"/"Steve Smith" WRs)
  collided onto one gsis → added `dedupe_gsis_within_snapshot` (keep lower-ADP, null+log loser).
- Survivorship check filters to skill positions (K/DST aren't in offensive `weekly`). `rows`/`names` are
  DuckDB reserved words — quote aliases.

**1.1 scoring:**
- `RuleSet` is pydantic; **default `OffenseRules` == nflverse's formula** so `score_offense` validates
  against `fantasy_points_ppr` directly (0 rows over 0.02 tol across 57.3k player-weeks). Half-PPR/TE-prem
  = a config change (`rec=0.5`, etc.).
- Arithmetic in **pure fns** (`score_offense`/`kick_play_points`/`pa_tier_points`/`score_dst`), DB in thin
  wrappers → unit-testable with no DB (like `assert_panel_pit`).
- **K/DST come from `pbp` + `game_lines`, not `weekly`.** Kicker points keyed on `kicker_player_id` (gsis);
  DST keyed on `defteam` abbrev; `td_team == defteam` captures def + return TDs; PA = opponent final score.
  Blocked kicks not derived (approx). FFC ADP K/DST rows have null gsis → `resolve_kicker_gsis` (name→gsis
  via player_ids) + `dst_team_from_adp_name` (city→abbrev, relocations handled) bridge them for the harness.

**1.2 draft sim:**
- Board = **`adp_asof`** (not `preseason_panel`, which drops null-gsis DST via `WHERE gsis_id IS NOT NULL`).
  `_prepare_board` canonicalizes pos (PK→K, DEF→DST), drops non-draftable/null-ADP, sorts by ADP,
  re-indexes; `player_key` = gsis_id else name (DST → name).
- Opponents: `pick_by_adp` = argmin(adp + N(0,noise)) among under-cap positions; default `noise=5.0`
  (ADP points — only reorders nearby players, never lifts a late player to the top). Seeded rng → reproducible.
- **Caps are soft** (fall back to best-available when under-cap positions exhausted → never a short roster).
  Custom `your_pick_fn`s bypass caps (caps are only the opponent-realism knob).
- **FFC undersupplies K/DST** (~5 K / ~6 DST) → only ~3–5 of 10 teams draft each; empty slots = replacement
  later. Perf gotcha: compute roster counts **once per pick**, not per available player (was O(n²), 54s→2s).

**1.3 walk-forward:**
- `rank_fn(board, con, season, as_of) -> Series` on the **ADP/pick scale** (lower=sooner); NaN→ADP
  fallback. Harness sets `board["value"]=rank_fn(...)`; `value_pick_fn` drives your seat; opponents ADP+noise.
- Draft date = FFC **snapshot_date** per season (PIT as-of); `preseason_board` re-asserts no future snapshot.
- Board = `adp_asof` (incl. DST). Realized points: offense+K keyed by **gsis**, DST by **team** (via
  `dst_team_from_adp_name`). **Survivorship guard** = LEFT-JOIN drafted→realized (missing player = 0 pts).
- Season score = Σ optimal-lineup pts over all REG weeks (greedy optimal for a single FLEX). `k_drafts`
  rotate seats. ~0.27s/draft. Note: **you-by-ADP ≈ league avg** — edge vs ADP is 1.5, not here.

**1.4 PAR metric:**
- Replacement rank = league-wide started per position (`n_teams×slot` + FLEX split 2:2:1) →
  QB10/RB24/WR24/TE12/K10/DST10; level = that rank's **realized** season total; FLEX = best flex-eligible
  level. `par = roster_season_points − replacement.roster_total` (2023 total 1743). Adjustable via slots.
- Replacement uses realized totals (OK — PAR is an *evaluation* metric, not a PIT input). Secondary:
  `expected_wins` = all-play (schedule-independent), `final_standings` ranks by it; corr(PAR, exp-wins)=0.99.
  Exposed `roster_weekly_points` in walkforward for the weekly matrix.

**Phase 3 features (X):**
- Each 3.x module = **realized per-(gsis,season) facts**, lag-free + unit-testable; 3.5 assembly applies the
  **PIT lag**. Contract: production←target-1, intrinsic←as-of target, environment←target-1 of the **target
  team** (situation entered; right for movers/rookies). `assert_exposures_pit` enforces prod/env < target.
- Standardize: **winsorized (2/98) cross-sectional z per position**; missing → group-median before z +
  explicit `*_missing`/`no_prior`/`is_rookie` flags (rookies keep intrinsic signal, never silent-0).
- Robustness: clip tiny-sample rate outliers (aDOT/YPC/ypr) to physical bands so z-scoring isn't distorted.
- Gotchas fixed: QB EPA polluted by trick-play throwers → **≥100-dropback gate**; relocated team codes
  (STL/SD/OAK↔LA/LAC/LV) → normalize game_lines side; bogus `draft_year=0` → fall back to first weekly
  season; 0.1% missing birthdates → NaN age imputed in 3.5. `player_ids` has dup gsis (JEF270909 vs
  00-0036322) — weekly-derived modules use the 00-00 gsis, so no pollution.
- `FEATURE_MANIFEST` (43 z + flags) is the column contract Phase 4/5/6/7 select on. Run on `STATS_SEASONS`
  (feature *computation* isn't model selection; the lockbox binds selection in 4/5).

**0.9 2025 backfill / nflverse new-release:**
- nflverse restructured player stats after 2024. Old release `player_stats/player_stats_{yr}.parquet`
  (what frozen `nfl_data_py` hardcodes) has **no 2025** → 404. New release **`stats_player`**:
  `stats_player_week_{yr}` (weekly, REG+POST) + `stats_player_reg_{yr}` (seasonal) — covers 1999–2025.
- Conform renames: `player_id`→`gsis_id`, `passing_interceptions`→`interceptions`, `team`→`recent_team`,
  `sacks_suffered`→`sacks`, `sack_yards_lost`→`sack_yards`; reindex to legacy cols (weekly NA-fills only
  `dakota`; seasonal NA-fills the derived `_sh`/`dom` shares — recompute in Phase 3 from weekly/pbp).
- Append via `db.append_df` (INSERT … BY NAME); `DELETE season=yr` first → idempotent. Writable con.
- **Depth charts 2025 = new timestamped grain** (`dt` ISO8601, no `week`) → separate table `depth_charts_ts`
  (+`source_year`); PIT = latest `dt ≤ as_of` per player. Week-grain `depth_charts` (2014–24) untouched.
- 2025 has **no ADP board** (FFC empty) → `CALIBRATION_SEASONS=(2025,)`, kept out of DEV/LOCKBOX.

**1.5 significance:**
- `block_bootstrap_ci` = **stationary bootstrap** (geometric blocks, expected ≈ n^{1/3}); `expected_block=1`
  = iid → the two are directly comparable. Returns point/CI/SE/`significant` (CI excludes 0).
- `compare_to_baseline` runs a **paired** walk-forward (same seeds → matched opponents/seats) and bootstraps
  the **per-season** PAR-diff series (11 pts). Replacement level cancels → PAR-diff = starter-pts diff.
- Market baseline = same call with a market `rank_fn` (Phase 2.3). Small-`n` reality: 11 seasons, block ≈ 2.

**Phase 2 markets & baselines:**
- Architecture: `projection → vbd → vbd_rank_fn` (a one-line wrap to backtest any projection). Board key =
  gsis (offense/K) else name (DST); uncovered rows → NaN → ADP fallback in `value_pick_fn`.
- **2.2 baseline** = prior-season ppg, EB-shrunk (weeks/(weeks+6)) to positional mean, ×17, light age.
  Multi-position players (RB/FB) collapsed to one row per gsis (dedupe `player_key`, else pandas map dies).
  Naive VBD **overrates QBs** in 1-QB (elite QB VBD ≈ elite RB VBD, but ADP drafts QB rounds later).
- **2.3 props** = **no free preseason market data** (props live-only/paywalled; win totals empty; game_lines
  gameday-dated). `season_props_projection` no-ops → ADP. Math built+tested; a key/paid archive activates it.
- **2.4 ensemble** = `blend_rank_fn` weights component ranks (each NaN→ADP first). `fit_weight` grid-search
  (endpoints w=0 pure-ADP, w=1 pure-baseline → best ≥ both by construction). w=0.25 best in-sample (caveat).

## Open questions (to resolve at the relevant step)
- **⟳ REFRAME decisions (2026-07-04, `docs/REFRAME` §10) — highest priority:**
  - **Consensus-projections source (value signal).** Where do we get consensus projected points (e.g.
    FantasyPros aggregate)? Is it free / scrapeable / **PIT-snapshottable** for backtest seasons? This is
    the new value input (Phase 4 reframed) — confirm before building it.
  - **Human completed-draft data (Sleeper).** The behavioral opponent model + availability (S4) need
    real pick-by-pick drafts, not ADP averages. Confirm Sleeper's API exposes enough before committing;
    else availability falls back to ADP+noise.
  - **Benchmark set for the cost report.** Which to offer: ADP-consensus-optimal / our-projection-optimal
    / expert-consensus-optimal (recommend several — the benchmark is self-referential). *MVP (2026-07-07):
    a single benchmark = the **unconstrained value-optimal team from the same seat & λ**
    (`DraftConfig.benchmark()`), through the identical optimizer; the multi-benchmark set is deferred.*
  - ~~**Lockbox seasons.**~~ RESOLVED (2026-07-04) → **lockbox = 2023 + 2024**; dev on **2014–2022**
    (`config.DEV_SEASONS`/`LOCKBOX_SEASONS`). 2025 excluded (see below).
  - **2025 recovery — ROOT CAUSE FOUND (2026-07-04); planned as step 0.9 before Phase 3.** The 404 was
    **not** "rollup not out yet" — nflverse **restructured stats releases after 2024**; `nfl_data_py` is
    frozen on the *old* `player_stats/player_stats_{yr}.parquet` path (no 2025 file). The data lives in the
    **new `stats_player` release**: `stats_player_week_2025.parquet` (weekly ✅) + `stats_player_reg_2025.parquet`
    (seasonal ✅) — verified, schema-compatible (renames: `passing_interceptions`→`interceptions`,
    `team`→`recent_team`, `player_id`→`gsis_id`). **Plan (0.9):** new-release ingest path → append weekly +
    seasonal 2025 + handle timestamped `depth_charts`; re-validate. **Lockbox stays 2023+2024** (draft
    backtest); recovered 2025 = a **projection-calibration holdout** (no ADP board needed to check
    calibration). **Still blocked:** 2025 ADP (FFC empty for 2025; source via Sleeper/Underdog later →
    then 2025 becomes a full draft-backtest season).
  - **Paid props line.** Under the reframe it's even more optional — decide whether to ever cross it; if
    not, formally drop "beat the betting market" from the goals.
- ~~**0.4 ADP coverage:**~~ RESOLVED — **FFC** goes back to **2010** (free, JSON API; half-ppr only 2018+);
  **Underdog** best-ball requires auth (no free historical) → **deferred**, schema is format-aware for later.
- ~~**0.5 markets:**~~ RESOLVED — **game lines** (spreads/totals/moneylines) are **free & historical** via
  nflverse `import_schedules` (2014+). **Player props are paywalled historically** (the-odds-api live-only;
  key-gated) — the confirmed gap. nflverse `import_win_totals`/`import_sc_lines` are currently empty (deferred).
- **0.5 markets:** which de-vig method (proportional / Shin / power) and which books to aggregate.
- ~~**1.4/2.1 replacement level:**~~ RESOLVED (1.4) — 10-team 9-starter: QB10/RB24/WR24/TE12/K10/DST10
  (`n_teams×slot` + FLEX split 2:2:1). VBD (2.1) reuses `backtest/metrics.replacement_levels`.
- **6.x ADP-alpha:** target definition — finish-rank − ADP-rank vs points − slot-replacement.
- **10.x season-sim:** bye-week, injury (games-missed), and playoff-bracket fidelity.
- ~~**14.2 app:**~~ RESOLVED for the MVP (2026-07-07) — Streamlit **Autopilot** (archetype + seat) +
  **Co-pilot** (risk λ, must/never lists, reach/wait tilts); personalized board shown **beside** the pure-value
  baseline + the cost readout. The fuller **Manual** surface (fandom, correlation appetite, control tiers) is
  deferred to a later app version.

## Dead ends
- _(none yet)_

- **2026-07-25 — 16.3 merge + 16.3b historical playcaller regimes BUILT (Session E, session 3).** New package
  `src/fantasy_quant/situation/` (`coaches.py`), done-bar `steps/phase16_3b_coach_history.py`,
  `analysis/phase16_3b_coach_history.json`, 10 tests (**326 total**, was 316), ruff clean. DEV-only, lockbox
  untouched, walled off from the frozen cost report.
  - **Implementation choices.**
    - **The curated CSV stays the artifact; the scaffold is derived at runtime.** `reference/coaches.csv` is
      hand-editable and human-owned (the user edits it directly after review); the 384-team-season pbp
      head-coach table is recomputed on demand by `head_coach_scaffold()` rather than committed, because it
      is free, exact and regenerable — committing it would duplicate data we can rebuild and invite drift.
    - **The scaffold is wired as an AUDIT, not just a filler.** `audit_against_pbp()` compares every curated
      `head_coach` to pbp and grades the result `MISMATCH` (the person never coached that team that season —
      a hard error, gated in the step) vs `split_season` (they are the season's *other* coach — legitimate,
      and often the right reading, since a mid-season coaching change and a mid-season play-calling change
      tend to be the same event). This is what lets the user's review skip a whole column.
    - **Sentinels instead of empty cells.** `(none)` = the team genuinely carried no OC title (SF under
      Shanahan for most years); `(unknown)` = there was one and it was not verified. The schema gate still
      forbids blanks, and `play_caller ∈ {head_coach, offensive_coordinator}` still holds.
    - **Majority-season inclusion rule.** A team-season enters the table only if the named person called
      plays for the majority of the team's games; sub-majority stints are excluded and documented in an
      adjacent row's `notes`. Prevents 16.4 fingerprinting a scheme on a half-season it did not run.
    - **Move-graph grading.** Sharpened to `HARD:` / `check:` / `note:`, and the contiguity check now flags
      only **one-season** holes — a multi-year absence is an ordinary departure-and-return (McDaniels leaving
      NE and coming back) and flagging it was noise.
  - **Dead end / correction mid-build: `in_house` alone cannot define the transport set.** The flag is
    *sufficient but not necessary* for "new regime", so `new_regimes()` also detects internal promotions
    **structurally** — the table's own previous-season row names a different play-caller. That only works if
    the predecessor season is present, and only 21 of 32 teams had a 2025 row (a byproduct of researching
    regimes, not a plan). Completing 2025 for the other 11 lifted the transport set **13 → 17** and caught
    **MIA** (Slowik was already on Miami's 2025 staff) on top of the DEN/PHI/WAS cases already flagged. The
    11 new rows were taken from ESPN's 32-play-caller survey for 2025, which also independently confirmed
    **all 21** rows already in the table — a free cross-validation of a third of the historical file.
  - **Research corrections worth remembering** (web verification overturned confident drafts): Monken's TB
    2016–18 and CLE 2019 OC stints were **not** play-calling; Schottenheimer did **not** call plays as DAL's
    OC (McCarthy did, 2023–24); Steichen's Chargers years are 2019 (interim from 30 Oct) + 2020; Daboll
    called NYG plays in **2024 only**; Stefanski/CLE **2024** and McCarthy/GB **2015** are real holes, not
    missing rows.
  - **⚠ Data limitation logged:** `pbp`'s coach field is game-level only through **2023**; from **2024** it
    is a season-level *coach of record* (Dennis Allen for all 17 of NO 2024, Daboll for all 17 of NYG 2025,
    both fired in-season). The scaffold's `interim` column is therefore a **lower bound** on mid-season
    changes. Sufficient for the audit; not a source for "who was fired when" in 2024–25.
  - **16.5 re-verified**: 3 real errors in 9 rows (Pittman `UNKNOWN`→traded to PIT; Montgomery
    `free_agent`→**trade**; **Jordan Mason SF→MIN removed — closed 16 Mar 2025, not a 2026 event**), Kyler
    Murray ARI→MIN added, Allgeier left `low`. All edits enumerated in the file header so the diff reviews
    cleanly.
  - **★ Design change mid-session (user, 2026-07-25): the lineage fallback replaces "16.4 says nothing".**
    A first-time play-caller falls back to the regime they came up under, tagged as weaker evidence, instead
    of being left blank. New `reference/coach_lineage.csv` (5 rows) names a **mentor person**, not a scheme,
    so 16.4 resolves through `coaches.csv` and a gate asserts every mentor is itself a play-caller there.
    Required adding **Sean Payton** (NO 2014-21, DEN 2023-24) and **Kliff Kingsbury** (ARI 2019-22, WAS 2024)
    as regimes — +15 rows, **204 total**. `fingerprint_source()` is the one API 16.4 should call; result
    **12 own · 5 lineage · 0 none**. Kept honest by `same_team`: DEN/WAS are same-building promotions where
    lineage and team continuity agree, but **BAL/PHI/SEA disagree** and the step prints an explicit `NB` per
    team so 16.4 reports both priors rather than choosing silently.
  - **Two small API fixes that came out of the tests:** `same_team` is now a pandas **nullable boolean** (it
    was flipping between numpy `bool` and `object` depending on whether any `own`/`none` row put an NA in the
    column — inconsistent scalars for callers), and the lineage loader tolerates an empty frame.
  - **★ Open gate:** the 172 historical rows + the 5 lineage rows are Claude-researched. **16.4 does not run
    until the user signs them off** — same contract as the 2026 half. Review surface is deliberately narrow:
    `offensive_coordinator` / `play_caller` / `hc_calls_plays`, since `head_coach` is machine-audited.

## 2026-07-25 (session 2) — SESSION E CLOSED: review gate + Phase 16.4

**Review gate closed.** The user fact-checked `reference/coaches.csv` and lifted the 26 non-`high` rows →
**204 rows, all `confidence=high`**, signed off end to end. Diff was confidence-only (plus one "- VERIFY"
note removed): no `head_coach`/`offensive_coordinator`/`play_caller`/`hc_calls_plays` value moved, so
16.3b's machine audits (pbp head-coach 0 MISMATCH, move-graph 0 HARD) carry over unchanged.

**Process note worth keeping.** The user reported the edits as saved; disk said otherwise (`git diff` empty,
mtimes unchanged, no edited copy anywhere on the Windows side). This is the **mirror image** of the
2026-07-24 stale-buffer incident — that time the buffer was stale and disk was right; this time the buffer
was right and unsaved. **Check disk before building on a "reviewed" file, in both directions.**

**Decisions taken before building 16.4** (asked up front, per the ask-everything-first instruction):
1. **Season cap — none.** First answered "cap at 2022 (DEV only)", then **reversed**: use all 2014–2025
   seasons on file, lockbox years included. Also **no provenance column** (the seasons-used tag was
   declined). Recorded because it is a deliberate, informed acceptance of lockbox-derived content in a
   descriptive artifact, not an oversight. The DEV cap would have cost CLE/DET/MIA/TB their entire basis
   (all four debuted as play-callers after 2022) — 13 of 17 transport teams would have survived it.
2. **EB shrinkage** toward the league-season baseline, weight estimated from the data.
3. **Partial regimes restricted to the weeks actually called**, transcribed from the rows' own notes;
   unpinnable ones dropped.
4. **Metric set extended** beyond BUILD_PLAN with concentration (HHI), aDOT and pace.
5. **Output at both team and player grain**; role-share deltas **+ implied multiplier**, no points column
   (a points translation would read as an edit to the frozen projections).
6. Commit at the end of the session.

**Built:** `situation/fingerprint.py`, `steps/phase16_4_fingerprint.py`,
`analysis/phase16_4_fingerprint.json`, 15 tests. **359 tests, ruff clean.** Full result in `findings.md`
§16.4; the two things worth carrying forward are the **20.9 % scheme / 79.1 % reversion** split (publishing
the total delta alone would have overstated the phase ~5×) and the **trait-portability ranking**, which is
the one genuinely reusable output of an otherwise-null value-side track.

**Dead end avoided:** the first draft reported `delta_pp` only. Inspecting the numbers showed nearly every
"implied share" sitting at the league mean — i.e. the shrinkage had done its job and the delta was mostly
measuring how far the *incumbent* was from average, not anything about the incoming coach. Decomposing it
was the fix; shipping the total would have been a quietly misleading deliverable.

**Next: Session F** — data 0.11 (ECR + Underdog ADP) + availability drift 16.7–16.8.

---

## 2026-07-25 — Session F: data 0.11 (ECR) + availability drift 16.7–16.8

**Four decisions taken with the user up front**, after a recon pass that changed what was worth building:
1. **0.11 = ECR only, Underdog dropped** — no keyless Underdog endpoint (marketing routes 404; JS app on
   an unpublished API). Deferred rather than half-built or allowed to consume the session.
2. **Include the 2023+2024 lockbox seasons** in the drift panel — the availability track predicts draft
   *flow*, not player value, and is walk-forward-scored, so it neither spends nor contaminates the frozen
   value eval (the position the Phase-16 scoping already took). +12 drafts, ~20 % more panel.
3. **`source_divergence` = held-out-draft split as headline PLUS an ablation without it.** This turned out
   to be the decision that determined the session's conclusion — see below.
4. **Leave the work uncommitted** for user review.

The §3.7 sub-step STOP gate was **waived by the user** for this session ("complete it in its entirety"),
matching the Phase 2–5 precedent.

**Recon that reshaped the plan (all measured, not assumed):**
- **A correction I made mid-session:** I first reported that FantasyPros has no historical ECR archive.
  Wrong — `?year=` serves real history. The first check regex'd `player_name` out of the raw HTML and hit
  a *widget* that renders current-season players on every archived page. Parsing the `ecrData` blob shows
  2020 → McCaffrey/Barkley/Elliott. **Rule: parse the payload, not the page.**
- …but the archive is **kickoff-dated** (every board stamped 9/06–9/11), so it post-dates 37 of the 38
  drafts it would explain. The user's "ECR live-only" call was right for a different reason than I gave.
- **The Sleeper corpus is not a preseason corpus** — draft times run February→November. This forced a
  `PRESEASON_WINDOW` the build plan never had, and it is the largest filter in the funnel.
- **FFC has no 2025 board at all** (live API: `"No ADP data found."`), so the biggest single-season human
  cohort (18 drafts) cannot be measured against an independent board.

**Outcome: an honest null, and the ablation is why.** Headline skill +1.05 % CI[−1.48,+4.96] against a
pre-registered 2 % bar; **ablation without `source_divergence` = −1.75 %**, worse than "everyone drafts at
ADP". The feature was *already* leave-one-draft-out, and it still carried the whole result — same-season
drafts share rooms, drafters and local ADP quirks. **New durable rule (glossary: "the ablation rule"):
for a sibling-derived feature, leave-one-out is not sufficient; report the fit without it.**

**Dead ends / things deliberately not done:**
- No attempt to rescue the null by widening the window to June (it would add ~13 drafts of a genuinely
  different market) or by relaxing the completeness/snake filters. The bar was set first and left alone.
- `days_to_board` was kept as a control rather than used to filter, since the board legitimately
  post-dates most drafts and that gap is a measurement property, not a defect.

**Consequence for Session G:** 16.9 gets no mean drift signal; its dispersion done-bar needs none, and
`aggregate_player_season.sd_drift` is the target. 16.10's curated hype board becomes the primary narrative
channel. See `findings.md` §Session F and the CLAUDE.md ★★ pointer.

## 2026-07-25 (session 4) — Session F.5: corpus expansion

**Why this session existed at all.** The Session F pointer said 16.8 could only be re-asked with a bigger
human corpus. Investigating that turned up the real cause of the small corpus: `analysis/results/sleeper_crawl.json`
recorded `crawled_new: 500` — **exactly `MAX_DRAFTS`**. The crawl had hit its cap, not exhausted the graph.

**Sequencing decision: F.5 before G, not after.** Session G's 16.9 done-bar is a *dispersion* (variance)
match, which needs **sample, not signal**. Fitting it on 34 drafts and then re-fitting after a crawl is
doing the session twice, so the crawl goes first.

**Decisions taken by the user before building (2026-07-25):**
1. **Frontier-only crawl** — walk the managers already in `sleeper_manager_profiles` and stop; no
   second-order snowball into their co-managers. (Snowball is implemented and tested behind `--expand`.)
2. **Ingest and bank non-redraft formats** — dynasty/2QB/superflex/IDP stored, not filtered at ingest, so
   Phase 17 does not have to re-pay the crawl. Downstream consumers filter for themselves.
3. **Archiver off for bulk crawls** — the T7 raw-payload archive would have been ~20k files, which is not
   an audit trail anyone can use. Still on for incremental runs (`--archive-payloads` forces it).
4. **Stop after the 16.7 funnel check** — no re-derivation this session, so every downstream decision is
   made against a *measured* corpus size rather than a projected one.

**Decisions deliberately NOT taken (carried to F.6):** re-asking 16.8 against the pre-registered >2 % bar;
re-fit vs extend for Phase 11.1; re-running the 2025 dress rehearsal (a further read of the calibration
holdout); adopting ECR as the board fallback for 2025.

**T12 closed here, with the decision made explicitly rather than as a drive-by.** The ADP uniqueness gate's
key gains `snapshot_date`. Folded into this session because it multiplies `sleeper_human` rows and would
have made the permanently-red gate redder. Two tests pin **both** directions — a deliberate weekly snapshot
series passes, two rows on the *same* snapshot still fail. Widening a uniqueness key is only safe if you
show it still catches what it was built to catch.

**One unplanned fix, taken because leaving it would have corrupted F.6.** The crawl turned a *passing* gate
red (`ADP top-150 gsis match`, 3.5 % unmatched). Root cause was not the crosswalk but the population:
`_refresh_board` hardcoded `scoring="ppr"`, pooling dynasty/2QB/IDP drafts onto a board labelled PPR
redraft — 82 % contamination at frontier scale. Boards are now redraft-only and split per (season,
scoring). This was in scope as "rebuild the derived artifacts", and shipping a knowingly-wrong ADP board
would have silently poisoned every F.6 conclusion.

**Estimate honesty.** The pre-session estimate was "~1 hr, ~25×". Actual: **70 min, 51.7×** — but only
because a 3-manager smoke test caught that discovery was running at 26 s/manager (a ~4-hour projection)
and prompted the league-cache fix that took it to 4.8 s/manager. The estimate was right by correction, not
by foresight; smoke-test before launching a long unattended run.

## 2026-07-26 — Session F.6: the re-derivation sweep (11.1 · 11.2 · 16.8 · S6 · dress)

Ran everything F.5 deliberately deferred. 411 tests (was 395), ruff clean, gates PASS, committed on
`main` (not pushed). **The sweep's real deliverable was not the refreshed numbers but the discovery
that the behavioral path carried F.5's format-contamination bug**: 11.x read all 7,699 human drafts
against one hardcoded 10-team PPR board; only 1,426 are eligible redraft rooms. The clean re-fit
deleted `rookie` (+0.45→+0.11, dynasty leakage) and `is_QB` (+0.17→−0.03, 2QB leakage) and doubled
`adp_s`. Eligibility + board resolution now live in one shared module (`adp/boards.py`).

Decisions: ECR adopted as the 2025 board fallback **calibrated** (isotonic rank→ADP, depth
truncation); 16.8's pre-registered headline stays FFC-only with ECR as a labelled sensitivity; no
per-manager random effects (mgr_lean ablation = 16 % of gain; only 111 eligible managers with ≥10
drafts); 11.1 fits a sampled 60 drafts/season for memory.

Results: 11.1 +0.1738 log-loss gain (was +0.1126); 11.2 +0.0864 CI[+0.0769,+0.0980] on 36,972
windows (was +0.1587 on 1,501 — the thin result was ~2× optimistic); 16.8 headline +9.25 % with a
**+0.01 %** ablation → the null holds and the leak got *stronger* with scale; S6 adaptive stronger
(+19.4 hero_rb). 2025 dress rehearsal ran its season sim for the first time. New tech debt T13
(distribution not reproducible across processes) and T14 (11.2 bootstrap O(n²)); T11(b) closed.

**Next: Session G — 16.9–16.12 + 16.16 under the null's constraint.**

## 2026-07-26 — Session G (in progress): T14 warm-up + Phase 16.9

**T14 ☑** — `availability_brier` 396.4 s → 12.7 s (31×) on an identical call; ~163 min → ~5.2 min at
full committed scale. **Bit-identical**, verified against the pre-fix implementation kept as a test
oracle. The register's diagnosis was wrong: the bootstrap it blamed runs in **0.79 s (0.008 %)**;
`cProfile` put **99.3 %** in `simulate_survival`, specifically pandas (`cand.iloc[ai]`, per-pick
feature rebuild) over ~13 M calls at scale. Fixed by hoisting one design matrix per seat context
(`OpponentModel.candidate_matrix`, resting on a row-wise-columns invariant that now has its own
test) plus the prescribed `_draft_blocks`. Bit-identity was a **design constraint** — 11.2's
committed `+0.0864` is a reported number — so a 460× algebraic bootstrap was measured and rejected
for consuming the RNG differently.

**16.9 ☑ — the shock is an honest NULL; the real find was a choice-set contract violation.**
New `adp/narrative.py`, `steps/phase16_9_narrative.py`, `analysis/phase16_9_narrative.json`,
`tests/test_narrative.py` (9), band tests in `test_opponent_model.py`. **425 tests, ruff clean.**
- **Premise inverted:** the phase assumed under-dispersion; measured, the simulator **over**-dispersed
  draft slots by **59 %**. 11.1 is fit on the top-40 available by ADP; `make_opponent_pick_fn` and
  `simulate_survival` were both drawing from the whole board. Now share `CHOICE_TOP_K`.
- **The fix alone meets the level done-bar** — pooled `drift_centered_sd` 2.897 → **1.976** vs
  realized 1.816 (**59.5 % → 8.8 %** error) — **and improves the availability Brier**, +0.0644 →
  **+0.0708** on 7,792 windows. Two independent metrics, so not a tuning choice.
- **The shock earns nothing.** Realized depth slope +0.679 · banded +0.077 · +shock +0.057. A **50×**
  sweep of shock size leaves the slope inside its own between-sample noise (+0.249 vs +0.057 at one
  setting) → **unidentified calibration**, reported as a noise draw not a fitted parameter.
  Structural cause: `top_k` is a hard rank filter applied *before* utility.
- **Decisions:** band **ON by default** (it is the contract); shock **default OFF**, kept as the
  expression channel 16.10/16.15 need. Residual shape miss logged as **T15** (an 11.1
  respecification — soft/widening band or log-ADP utility — not attempted inside 16.9).
- **Next: 16.10** (mechanism now, user reviews the board after), then 16.11 → 16.12 → 16.16.

## 2026-07-26 — Session G (2/2, COMPLETE): 16.11 · 16.10 · 16.12 · 16.16

**User pre-authorised 7 decisions up front** (asked before any code, per the standing pattern), then
waived the §3.7 sub-step gate so the four substeps ran straight through with one report at the end:

1. **Hype board authoring = derived-first, then annotate.** The machine ranks *who* (16.8 ablation
   survivors + 16.11 momentum), Claude web-researches only the `note`/`source` per row. Chosen over
   pure web research explicitly because of 16.5's *derived-vs-curated* lesson.
2. **Hype default OFF everywhere, opt-in** — the "kept, not default" pattern.
3. **16.11 velocity on the FFC-only series** (3 snapshots), labelled thin, rather than pooling the
   Sleeper boards for a longer lever arm — pooling different populations is the F.5 failure mode.
4. **Straight through, one report at the end** (§3.7 waived).
5. **16.12(c) engine-side readout only** — no Streamlit UI; the app stays strictly last (Session K).
6. **If 16.16 nulls, ship default OFF and report it** — the 16.9 treatment, not deletion. *(It did.)*
7. **Leave the session uncommitted** for user review.

**Build order deviated from the spec, deliberately:** 16.11 was built **before** 16.10, because
decision (1) makes momentum an *input* to the hype-board nomination.

**Outcomes.** 466 tests (was 425), ruff clean, every done-bar gate PASS.
- **16.11 ☑** forward-only and structurally unbacktestable — labelled in the return value, not just
  the docstring. Centered on the board's own drift; EB-shrunk (44 % of raw spread survives).
- **16.10 ☑** 24 rows / 20 claims, `reviewed=false`, structural review gate. **Elasticity ≈ 0.44
  realized picks per claimed pick.** Four measurement defects found and fixed en route — see
  findings; the durable one is *partial coefficients need their controls*.
- **16.12 ☑** all three consumers + a **proven isolation gate**: `DriftConfig()` is a no-op and a
  `RiskModel` without `hype` is bit-identical to the frozen path, asserted both directions.
- **16.16 ☑ = Phase 16's fourth null.** Detector works (monotone discrimination, +0.109 at threshold
  0.50); reacting to it degrades the availability Brier monotonically. Default OFF, kept as a
  live-draft alert for 14.4.

**Dead ends / corrections worth not repeating.**
- Ranking nominations by raw (signed) score surfaces only risers; the strongest claim on the board is
  a *fader* (Charbonnet, PUP list). Rank by |score|.
- The 16.10 done-bar reported the mechanism **backwards twice** before it was measured correctly:
  once from dropping undrafted players (→ censor at `n_picks+1`) and once from applying all 20 claims
  simultaneously in a zero-sum draft (→ leave-one-in).
- 16.16's first baseline was the whole remaining pool; a board is WR-heavy at every depth, so the
  detector fired on 61 % of windows and anti-discriminated. The baseline must be the **candidate set**.

**New tech debt: T16** (deep curated claims cannot express in a 15-round league; fix properly via
T15's depth-varying candidate set, and surface the limitation meanwhile).

**Next: Session H** — opponent personalities 16.13–16.15 (face-validity + unit tests, no Brier gate).

---

## Session H (2026-07-26) — 16.13 board enrichment + 16.14 the five headline personalities

**Scope: 16.13 + 16.14 only.** 16.15 (mock-room composition, hype coupling, app selector) is
explicitly *not* in this session — stopped at the sub-phase gate for user approval, per §3.7.

**Decisions taken (user, 2026-07-26, asked before building).**
1. **Distribution source = `cached_distribution(con, season, …)`, any season** — not the
   `player_distributions` DuckDB table, which holds **2025 only**. This is the same reader
   `optimizer.assemble_value` uses, works for 2026 and every backtest season, and keeps the join
   PIT via `as_of = draft_date(con, season)`. First call ~12 s per season, memoized after.
2. **Signal scaling = z-score within position**, over the live candidate pool. Makes weights
   readable ("utility per sd"), stops a risk tilt doubling as a positional lean, and — unplanned but
   load-bearing — cancels the uniform multiplicative bias T17 turned out to introduce.
3. **Homer = optional favourite team, defaulting to story-chasing** (hype board + change-of-
   situation), **and must not reach for a crazy target**: with nothing to chase it takes best value.
   Implemented as `max_reach_picks`, a reach ceiling in ADP picks — the fallback falls out of the
   design rather than being special-cased, and is tested as an exact pick-log equality.
4. **Leave the session uncommitted** for user review. (Session G had since been committed through
   `5f6383b`, so the working tree holds Session H alone — 13 files.)

**Deviation from the 16.14 spec, deliberately.** The spec names
`signal_weights={"boom_prob": +, "q90": +}` for the upside chaser and `{"q10": +, …}` for the safe
drafter. Built exactly that way, **the two personalities agree with each other on real data** —
within position `corr(q90, mean) ≈ 0.98` in every season, so both weights are quality tilts. The
shipped build weights `upside`/`floor`, the level-residualized versions, and `enrichment.py` gained
`residual_shape` to derive them. The raw quantiles stay on the board for reporting consumers. Full
measurement in `findings.md`; this is the 16.10 lesson (*a coefficient is not transportable without
its controls*) recurring on a **signal**.

**Also deliberate:** the join helper lives in a new `draft/enrichment.py` rather than in
`simulator.py` as the spec's heading says. `simulator.py` is a Phase-1 leaf with only numpy/pandas
imports and ten modules depend on it; pulling `value_board` + `distribution` + `situation.events`
into it would invert the dependency graph. `simulator.py` got the passthrough half
(`PASSTHROUGH_COLS`, `board_player_key`), which is the part that genuinely belongs there.

**Outcomes.** 496 tests (was 466), ruff clean, both done-bars PASS on the live 2026 board.
- **16.13 ☑** enrichment coverage 81.8 % distribution / 85.8 % value; the entire skill-player gap is
  **one WR** (the rest is 22 DEF + 18 PK, which carry no projection by construction).
- **16.14 ☑** five headliners; all seven live-board face-validity checks pass, `autopilot`
  reproduces `pick_by_adp(noise=0)` **exactly**, and the two risk tilts are opposed rather than
  merely different.
- **Two dead personalities revived**: `homer` (nothing ever passed `fav`) and `rookie_hawk`
  (`_prepare_board` dropped the column) had been literal no-ops since Phase 11.3.

**Dead ends / corrections worth not repeating.**
- **The face-validity bar has to be "they disagree with each other", not "each differs from
  balanced".** The weaker bar passed the broken build.
- **The synthetic fixture was easier than reality** — it drew `q90`/`q10` independently, which made
  residualization look unnecessary. Now generated from a shared level + an opposing shape factor.
- **A single seeded draft cannot read a 1–2-round reach.** The sign flips between seeds; every
  face-validity number pools 8–12 drafts.
- **The reach ceiling had to be measured.** At 10 picks the personalities are real but illegible
  (inside balanced's own noise); at 18 they separate. Shipped 18 / 15 / 24.

**New tech debt: T17** (🟠 the live season has no per-player availability — `availability_projection`
returns 0 rows for an unplayed season, so the Phase-5 `mean` collapses to 37 % of the consensus
projection it is built from). Not a blocker for H or I; **is** a blocker for Phase 14 showing a user
any distribution number. Session H is insulated from it by decision (2).

**Next: 16.15** — mock-room seat composition, routing the 16.9 shock through the `hype_gain` seats,
and the app selector. `hype_gain` and `fav_teams` are already in place for it.

## Session H2 (2026-07-27) — T17 repaired · 16.13 revised · 16.15 the mock room (SESSION H COMPLETE)

**524 tests** (was 496), ruff clean. DEV-only; the spent lockbox untouched; the frozen
value/optimizer/VBD/cost-report stack untouched (16.13 only *reads* it). Session H committed.

**Resumed a session interrupted mid-flight.** The working tree held ~90 minutes of uncommitted,
unvalidated work — T17's fix, a 16.13 revision and 16.15's first cut — with no docs, no unit tests
for 16.15, and a dangling `T18` reference in a code comment pointing at a register entry that did
not exist. All three landed; the audit of what was and was not done is what opened the session.

**Decision taken this session (user, 1 question):** the shared 16.9 shock is applied **outside**
`max_reach_picks` rather than folded into the same clip. Alternatives offered and declined: ship
as-is and document the coupling as a null; or give every seat a ceiling (rejected — it would shrink
total dispersion below 16.9's calibration and requires fitting ceilings for `balanced`/`reacher`).

**Order of work.** audit → measure the coupling → decide → implement + docstrings → harden the
done-bar → unit tests (incl. a regression test verified to fail on the old behaviour) → selector
spec → doc sync → commit.

**What shipped.**
1. **T17 ☑** — `injury.projected_availability_frame` rolls covariates forward for an unplayed
   season, `team_games` from the schedule, `covariate_source` stamped. **2026 level ratio
   0.37 → 0.721** (2025 holdout 0.683). Plus the **level-band guard** (`distribution.level_ratio` /
   `assert_level_band`, band 0.55–0.85) wired into `steps/phase5_5_utility.py` and run on the live
   season as well as the holdout.
2. **16.13 revised** — `residual_shape` gained `durability`; `safe_floor` weights it instead of the
   raw `games_played_mean`. Forced by T17: fixing the data turned that column into a level proxy.
3. **16.15 ☑** — `DEFAULT_ROOM`/`make_room`/`normalized_hype_gains`/`make_room_pick_fn`, the
   hardened done-bar, `docs/PLAYER-VIEW.md` §9, 12 tests.

**Corrections worth not repeating.**
- **My first diagnosis of the clip was overstated and I corrected it mid-session.** "Homer clips
  90 % of candidates, 17 % of the shock survives" was measured on the **test fixture**
  (`β_adp_s = −0.85`). On the live board's fitted β (−1.68) the caps are ~2× larger and homer clips
  **0.0 %**; upside 26 %, safe 33 %. The fix stands on the estimation-conditions argument, not on a
  large current effect — it would start costing after an 11.1 refit that shrank `β_adp_s`.
  *Measure the real board before quoting a fixture's number as the system's behaviour.*
- **A zero vector is not an "off" control.** `argsort` on zeros labels the top-N rows by board
  order — by ADP — which autopick seats take by construction. It produced a large fake effect on
  exactly the seats the control should say nothing about, and it briefly looked like a result.
- **A two-ended bar cannot see the middle of the room.** *Chasers − autopickers* passes on a room
  routing the story backwards, because autopickers get sniped either way.
- **The regression test was verified to fail on the pre-fix code** before being kept. An untested
  regression test is the "inert thing still passes" failure mode wearing a lab coat.
- **The autopilot-in-a-mixed-room test could not be an equality against an all-autopilot draft** —
  the rooms legitimately diverge after round 1 because the other eight seats are different people.
  Restated as the autopicker's own invariant (lowest ADP available at each of its turns).
- **`CHOICE_TOP_K` is a hard ADP-rank filter applied before utility**, so a shock on a player
  outside the top 40 available expresses nothing. Session G's contract lesson, from the other side.

**New tech debt: T18** (🟡 `sleeper_manager_profiles.avg_reach` is scored against a pooled ADP board
across mixed formats → a +91.9-pick mean QB reach; a board mismatch, not a behaviour). Unconsumed
today; fix before a manager-facing readout or an 11.3 refit keys on it. **T17 closed.**

**Next: Session I — Phase 17 League-Format Fidelity 17.1–17.4.** Then J (optional dynasty) → K
(Phase 14.1 MVP + all surfacing, strictly last). Stage-0 FFC chore: last pull 2026-07-24, **due
after 07-30**.

## 2026-07-27 — live mock draft with the user in the room (docs-only; T15 escalated)

**What happened.** The user drafted a full 10-team full-PPR 15-round snake from seat 7 against
`DEFAULT_ROOM` on the live 2026 board, one pick at a time, and gave running notes. **No repo code
was written or changed** — the harness is a throwaway driver over `DraftState` +
`make_room_pick_fn` (scratchpad `mockdraft.py`). Output of the session is a **measurement** and this
doc set. Full writeup: `findings.md` §"Live mock draft (2026-07-27)"; the register entry is
`docs/TECH-DEBT.md` **T15**, escalated 🟡 → 🟠 and re-scoped.

**The user's notes, in the order he gave them (all four are the same defect):**
1. R1 — the room skips players who cannot be skipped; Kenneth Walker III (ADP 22.5) at pick 4 is
   not a thing that happens. **Asked for round-dependent reach weighting: ~5–8 picks early, larger
   only from round 3–4 on.**
2. R2 — 26- and 33-pick reaches "simply do not happen"; a real reach is **≤1 round, 2 at the max**,
   *including* for `reacher`/`homer`/`upside_chaser`. **Asked for a fall cap on the top ~20–25**
   so elite players cannot slide (at most ~1 of them falls).
3. R7 — expected the 7,699-draft Sleeper corpus to have made the seats realistic; asked for a
   **comprehensive account of what makes each personality reach**, and for mitigation options.
4. R11 — reinforced after `balanced` (no tilts at all) reached **42 picks** for Michael Wilson.

**What we measured in response** (`adp/drift_panel.build_drift_panel`, 1,420 human drafts /
197,227 boarded picks / 2017–2025, vs the simulated draft, in 10-team ADP picks):
- Round-1 mean reach **corpus 3.3 / sim 11.4**; p90 **6.6 / 27.7**. Round-15 **27.1 / 15.0**.
  The corpus curve grows monotonically; the sim is flat. **Wrong shape, not wrong scale.**
- Corpus ADP ≤ 12 players: mean slot **8.4**, **p95 = pick 17**, 23.7 % fall past pick 10. The sim
  dropped five top-12 players past that p95 in one draft.
- Per-seat mean drift (picks): `autopilot` **−19.8**, `reacher` **+14.5** (max +52). The two
  autopilot seats finished **1st and 2nd** by top-9 projection — the leaked value is measurable.
- Arithmetic: ADP = **0.0337 utility/pick** vs `is_TE` +0.567 (**17 picks**) and `need` +0.474
  (**14 picks**), softmaxed over a fixed top-40 ⇒ **expected reach 16.8 picks before any tilt**.

**Decisions / positions taken this session:**
- **T15 is a specification error, not a data problem** — record it so nobody proposes "crawl more
  drafts" as the fix. More data estimates a misspecified coefficient more precisely.
- **The fix's functional form is measured**: width ∝ `pick^0.5…0.6`, so **not** log-ADP
  (`pick^1.0`, over-corrects) and not the current linear (`pick^0.0`). Fractional power or
  rank-in-pool, selected by refit log-loss — the corpus curve is the acceptance bar, not the
  estimator.
- **Hard clips (max reach ≈1.5 rounds, top-25 fall cap) are an override, not the fix** — shippable
  for Phase 14 realism but labelled, separable, and never scored as a modelling result, because
  they move 11.2's Brier and 16.9's calibration on contact.
- **Five acceptance bars pre-registered** in T15 (round-1 mean ≈3 / p90 ≈7 · no top-12 past ~pick
  17 · autopickers stop out-valuing the room · 11.1 log-loss and 11.2 Brier hold · 16.9 profile
  re-checked).

**★ DECIDED — session order (user, 2026-07-27).** T15 was queued as opportunistic and is now the
only thing a human noticed in an hour of using the product. Candidates were: **(a)** insert a T15
respecification session before Session I; **(b)** keep Session I (Phase 17 formats) first as
planned; **(c)** ship the labelled hard-clip override now for realism and do the respecification
properly later. **The user chose (a).** Rationale on the record: it is the only user-visible defect
found by real use; 16.12's `P(available at your pick)` is already wrong in a user-facing way; and
Phase 17's new formats would otherwise force validating the room twice. Session I is not gated on
T15 in either direction, so the swap costs nothing.

**The T15 session, in order** (each step's output is the next step's input; step 0 is not optional):

0. **The A/B harness.** Promote the scratchpad `mockdraft.py` (~330 lines, thin over `DraftState` +
   `make_room_pick_fn`) to `steps/`, add a **seeded batch mode** (≥50 drafts) and a helper that
   pushes simulated drafts through `adp/drift_panel.build_drift_panel`, so the corpus-vs-sim table
   is one call. The 2026-07-27 sim column is **one draft** (135 opponent picks) — too noisy to be a
   before/after baseline. Re-measure before touching the model.
1. **Respecify `adp_s` and refit.** Candidates: **(A)** fractional power `adp^p`, `p≈0.45`, exponent
   fit jointly or by grid; **(B)** rank-in-available-pool, scale-free by construction, which also
   answers the fixed `CHOICE_TOP_K=40` spanning ADP 1–45 in round 1 vs 100–200 in round 12. Choose
   by **refit log-loss** — the corpus curve is the acceptance bar, not the estimator. Log-ADP
   (`pick^1.0`) is ruled out by measurement. **A full refit is the point, not a side effect:**
   `is_TE` (+16.8 picks) and `need` (+14.1) only shrink at the top of the board once the ADP term is
   steep there. ⚠ **`adp → adp_s` is constructed in two places** — `build_choice_frame` (fit) and
   `candidate_matrix` (sim) — which must never diverge; extract one shared `adp_feature()` first.
2. **The two judgement-free gates**, added as regression tests: no consensus top-12 player past
   ~pick 17 (≤1 of the top-6 past pick 10), and the `autopilot` seats stop systematically
   out-valuing the room. Bars 1/4/5 of T15 stay as pre-registered.
3. **Re-verify 11.1 log-loss (+0.1738), 11.2 banded Brier (+0.0708) and the 16.9 dispersion profile
   together** — improving one while quietly degrading another is the failure mode. **Re-fit
   `NarrativeShock.intercept`**: it was calibrated under the old dispersion and is not transportable.
4. **Hard clips only if step 1 leaves a gap** — per-seat candidate filter (`ADP > overall_pick +
   1.5 × n_teams` dropped) + top-25 fall cap, shipped labelled, off the estimated path, separable,
   never reported as a modelling result.

## 2026-07-27 (session 2) — personality design review (docs-only; the 16.14R contract)

Follow-on to the live mock. The user reviewed each seat's intended character; **no code written**.
Settled contract → `docs/BUILD_PLAN.md` §**16.14R**; the analysis → `findings.md` §"Personality design
review (2026-07-27)"; T15's acceptance bar #3 rewritten in `docs/TECH-DEBT.md`.

**Settled:**
- **Autopilot: no change.** Its mock win was harvested spill (−19.8 mean drift), not skill. **T15 fixes
  it by fixing everyone else.**
- **★ Width vs direction** is the organizing split for all seats: `width(round) × multiplier` for how
  far, `signal_weights` for which way. Multipliers **autopilot 0 · safe ~0.8 · balanced 1.0 · reacher
  ≤2.0 · value hawk bounded (open)**. This **replaces the absolute `max_reach_picks` ceiling** as the
  primary reach control — T15 showed a single pick-count cap is wrong at one end by construction.
- **Balanced** = corpus width + the 16.8 **ablation survivors** as direction (`rookie`, `adp_stdev`,
  `vbd_gap`, `pos_WR`/`pos_TE`) + the 16.13-enriched board as a **tie-break inside the reach window**.
  Situation/coach = labelled opt-in, **default OFF**.
- **Reacher** ≤2× balanced; **inherits the 16.9 narrative shock + 16.10 hype board** from the retired
  homer.
- **Safe** ~0.8×, durability entering **net of level** (T17 made `games_played_mean` a level proxy).
- **★ Value Hawk replaces Homer** — bounded-window argmax on the value board; reverses the 2026-07-23
  decision that cut it. `fandom` (+35.5 picks, ×2.5 ⇒ 89) becomes fitted-and-unused; **do not delete
  the feature**.

**Two findings, not decisions** (detail in `findings.md`):
- **★ "The level, not the residual."** Situation flags are null for predicting *drift* (16.8, re-asked
  in F.6 at 1,144 drafts: headline +9.25 % but ablation +0.01 %) **and** that is consistent with them
  driving human behaviour — ADP has already absorbed them, so no residual remains to detect. Design
  rule: situation belongs in a seat as what it **agrees with ADP** about, never as a deviation driver.
- **★ `balanced` was never given the holistic behaviour everyone assumed it had** — raw β, every tilt
  off. Explains the 42-pick reach independently of T15's misspecification. Two separate repairs.
- **★ The scoring trap:** value hawk optimizing our board and scored on our board wins by
  construction. Projected-points room rankings are **descriptive**; evaluative claims run on
  **realized** points.

**☐ THREE OPENS — settle before the 16.14R session (not before T15, which is unaffected):**
1. Value hawk's objective — **VBD or portfolio CE?** (recommend **portfolio CE**).
2. Value hawk's reach window (suggest **~1.0–1.25× balanced** — decisive but rare).
3. Whether 16.4/16.5 go onto the 16.13-enriched board now (they are not there today) or stay deferred
   while the situation channel ships default-OFF.

**Order unchanged: T15 respecification → 16.14R personality session → Session I / Phase 17.** T15 is
not blocked by the three opens; 16.14R depends on T15's width function.

## 2026-07-27 (session 3) — T15 step 0 built and closed; step 1 scoped

**Step 0 ☑.** `draft/mock.py` (the harness + the sim→corpus measurement bridge), `steps/mock_draft.py`
(the interactive driver promoted out of the scratchpad — it is how the defect was found, so it lives
in `steps/` now), `steps/t15_0_baseline.py`, `tests/test_mock.py` (16 tests, offline). Baseline frozen
at `analysis/t15_baseline.json`: **900 seeded drafts**, measured by the same functions and on the same
boards as **1,144 realized FFC-boarded human drafts**. **No model was changed.** Numbers and the three
register corrections: `findings.md` §"T15 step 0", `docs/TECH-DEBT.md` T15.

**What changed in the problem statement** (all three from having 900 drafts instead of 1):
- "The simulator is flat" was a one-draft artifact. It rises to round 9, then **turns over**. The
  defect is the **ratio column, 4.24× → 0.57×**, crossing 1.0 at ~round 11.
- **Bar 3 is roughly passing already** on fixed `pool_rank` edges (+20.5 sim vs +17.6 corpus, sd 17.0).
  What fails is the **population**: 54.3 % of human seats sit in the `pool_rank` 2–8 band, the sim puts
  **2.2 %** there and **19.6 %** below 2. **T15's target is the distribution of deviation, not its scale.**
- Bar 2 is worse than the anecdote: **57.9 %** of consensus top-12 past pick 10 vs **18.9 %** realized.

**★ Recorded before step 1 runs, because it decides between the two pre-registered candidates.** For a
candidate set spanning board ranks `r` with ADP `a(r)`, and utility `u = β·f(a)`, the softmax's width
in **rank** is `w_r ∝ 1/(|β|·f'(a)·a'(r))`, so the width in **ADP picks** is `w_a = w_r·a'(r) ∝ 1/f'(a)`
— **the board's local density cancels**. Therefore:
- `f` **linear** ⇒ `w_a` constant in depth. The flat profile is *derived*, not just observed.
- `f = a^p` ⇒ `w_a ∝ a^(1-p)`; the measured `pick^0.5…0.6` ⇒ **p ≈ 0.4–0.5**, which reproduces T15's
  `p≈0.45` from an independent direction.
- `f = log a` ⇒ `w_a ∝ a^1.0` — over-corrects, as already ruled out.
- **rank-in-pool ⇒ `w_r` constant, so `w_a ∝ a'(r)`: pure board density.** Board spacing grows only
  ~2.3× over rounds 1→12 where the corpus grows 5.5×, so **candidate (B) structurally under-corrects**
  — and against today's spec it is nearly a **no-op**, since linear-in-ADP inside a fixed top-K already
  *is* rank-in-pool up to an additive level that cancels in the softmax. This does not override
  "choose by refit log-loss"; it predicts the answer and says the grid should be over the exponent.

**★ Two implementation consequences not previously recorded.** `hype_board.apply_hype` and
`Personality.reach_cap` both convert picks→utility as `−β/_ADP_SCALE`, i.e. they hardcode the
**linear** derivative. Under a power law that conversion is depth-dependent, so the shared extraction
owes a `utility_per_pick(adp)` alongside `adp_feature(adp)`. And the fitted **exponent must be
persisted next to the coefficients** in `analysis/phase11_opponent_model.json`, or `load_opponent_model`
will pair a new β with the old transform — *a coefficient is not transportable without its controls*,
which would be the fourth instance in this project.

**Efficiency note for step 1:** have `build_choice_frame` keep raw `adp` on the frame so an exponent
grid refits from **one** built frame instead of rebuilding the expensive corpus per candidate.

**Environment defect found (pre-existing, unrelated):** `.venv/bin/pytest` carries a shebang pointing
at `/home/rayhan/dev/repo/fantasy-quant/.venv/bin/python` — the path from before the repo moved out of
`~/dev/`. `uv run pytest` fails to spawn; `uv run python -m pytest` works. Fix with `uv sync --reinstall`.

## 2026-07-27 (session 4) — T15 steps 1–4 executed end to end

User instruction: run the remainder of T15 without sub-step gates, after settling four scoping
questions up front. Choices taken (all the wider option): **curvature + a widening candidate band**;
**ship a labelled calibration if the estimate misses the bars**; **pull 16.14R's per-seat width
multiplier forward**; **leave the tree uncommitted**.

**Shipped:** `AdpSpec(power, p=0.15)` + `BandSpec(widening, k0=40, +5/round, cap 160)` +
`WidthCurve(γ=0.8)`, with β refit under all three and the specs persisted beside the coefficients.
Artifacts: `analysis/t15_{respecify,calibrate,width_curve,verify}.json`; the pre-T15 β is preserved
at `analysis/phase11_opponent_model.pre_t15.json`.

**Four things were learned the hard way; each changed the method, not just a number:**
1. **"Gain over the baseline" is not a selection criterion** — inside one band, log-loss picks
   p=0.45 while gain picks p=1.00 (the incumbent). Gain rises when the *baseline* degrades.
   Replaced by `band_coverage`.
2. **`fixed40` was violating the Session-G contract** — it excludes the realized human pick **3.95 %**
   of the time. That, not any fit statistic, is the judgement-free case for widening (and it
   dissolves T16).
3. **A uniform width metric traded away the defect it was built to fix** — it selected a spec that
   failed the elite-fall gate. Objective restricted to rounds 1–6, and **the gates made hard
   constraints rather than terms**.
4. **One knob cannot set both ends** — the exponent that stops elites falling leaves the room
   uniformly too narrow and breaks bar #5. Cause is **pool exhaustion**, which the width derivation
   ignores. Fixed by the round function T15 already owed 16.14R.

**Left open, deliberately:** the seat-faithfulness *population* (median `pool_rank` 10.27 vs a
corpus 7.62; moderate band 14.3 % vs 54.3 %) — not one of T15's five bars, and it trades against the
reach-profile match. Closing it needs per-seat **board perturbation**, i.e. 16.14R's direction half.
Also open: **16.9's `NarrativeShock.intercept` is now formally stale** — it is a size in utility
units calibrated under the old transform. Not re-fit (16.9 measured it as unidentified; a 50× sweep
moved the target less than its own noise), but `assert_transportable` now refuses to apply it across
a spec change.

## 2026-07-27 (session 5) — the 2×5 mock room; 16.14R re-ordered around what it found

User instruction: run a full 15-round mock with **2 seats each of autopilot / value hawk / safe /
reacher / balanced**, interspersed at random, then report picks by round, rosters by position, and an
assessment. No sub-step gates for the run itself. Nothing committed to `analysis/`; the driver and
CSVs live in the session scratchpad, and the method is written up in `findings.md` §"The 2×5 mock
room".

**One thing had to be resolved to run it at all:** `value_hawk` is not in the shipped library (16.14R
is spec-agreed, not built). Rather than block, it was approximated run-locally from existing
machinery — `signal_weights={"vbd": 0.70, "overall_rank": −0.30}`, `temperature 0.85`,
`width_mult 1.15`, `max_reach_picks 14`. **It finished 5.5/10 and the reason is now the argument that
settles 16.14R open decision #1.**

**Then the user reviewed all 150 picks by eye and raised three seat-level objections. All three have a
measured mechanism, and two are defects in things 16.14R was going to build *on top of*.** That is
what re-ordered the session: **repair the signals and the board before re-specifying any personality**,
or each rework tunes around a broken input. The ordered plan of record is
`docs/BUILD_PLAN.md` §"16.14R — THE EXECUTION ORDER" (7 steps, gate after each).

**Decisions taken this session (do not re-litigate):**
1. **`floor` is repaired before any personality consumes it** (T19). It is not a weighting question —
   `q10` is censored at 0 for 42.9 % of offensive rows, so the residualization inverts the signal and
   `corr(floor, adp)` is **positive** for RB/WR. `safe_floor` drafted exactly what the board called
   safest.
2. **The board gains signed situation + committee share + TD-regression before the value hawk is
   built** (16.14R open decision #3, settled). The user's three value-hawk objections are blind
   spots; no objective over today's board avoids those picks.
3. **Value hawk's objective is portfolio CE, not VBD** (open decision #1, settled, and the argument is
   measured not aesthetic): `signal_bonus` z-scores within position and `corr(vbd, adp)` within
   position is −0.86…−0.96, so `pos_z(vbd)` deletes VBD's only non-ADP content.
4. **The reacher gets direction before it gets a budget.** It currently has **no `signal_weights` at
   all** — a hot softmax with zero opinion. The user's budget spec (≤2–3 large reaches in round 5+,
   3–5 medium in round 3+, clamped rounds 1–3) is adopted, with the noted consequence that a budget is
   **stateful per seat** and `make_opponent_pick_fn` is stateless today.
5. **K/DST get a hard roster-legality guarantee** (user instruction, T20): every seat finishes with
   ≥1 K and ≥1 DST whenever `rounds >= slots.starters`. Implemented as a pool restriction — a hard
   filter before utility, the same class as `BandSpec` — **not** as a pick-policy tweak, so every
   policy inherits it and the fitted β's meaning is untouched.
6. **DST goes on the board `include_dst`-flagged, default OFF** — on for the mock path, off for the
   fit path and the drift panel, so no T15 measurement moves.
7. **The default room drops to ≤1 autopilot** (Step 7). It won **48.3 %** of 60 seeded drafts at a
   mean finish of 1.69/10 while representing 0.2 % of real seats.

**Dead end recorded:** the first hypothesis for `safe_floor`'s bad picks was that rookies reach
`pos_z` as NaN and get filled with 0 = "neutral" rather than "unknown". **Wrong** — 0 of 31 rookies on
the 2026 board have a NaN `floor`; Phase 5 covers them. The real cause is censoring, found only by
printing the top-`floor` lists. *Check the ranking a signal actually produces, not just its coverage.*

**Left open, not blocking:** roster **shape** carries no personality signal (every seat hits the 6-WR
`pos_caps` ceiling; 5.82–5.99 across the batch). Deliberately **not** registered as tech debt yet —
it needs a decision on whether shape *should* vary by personality before it can be called a defect.

**T15 remainder, restated so it is not lost:** seat-faithfulness population (Step 7) · per-seat board
perturbation for the late-round 0.61× narrowness (16.14R direction half) · `NarrativeShock.intercept`
formally stale, not re-fit because 16.9 measured it unidentified · **T16 not re-measured** — re-run
the 16.10 done-bar at 15 rounds before marking it ✅ · T18 `avg_reach` still unconsumed.

## 2026-07-27/28 — 16.14R steps 1–7, run straight through

**Instruction:** *"go through the whole 7 step process without stopping until completion"* — the
§3.7 sub-step gate was **waived for this session** (the Session E/F precedent), and eight decisions
were taken up front so the run needed no further input.

**Decisions taken (user, before any code):**

| # | question | decision |
|---|---|---|
| 1 | how to repair `floor` | **build every estimator, pick by the pre-registered bar** |
| 2 | `boom_prob`/`bust_prob` | **new enrichment column, Phase 5 untouched** (they are frozen contract) |
| 3 | who may weight the step-3 context | **any seat may; defaults 0.0 except the value hawk** |
| 4 | the reacher's reach budget | **recompute from `DraftState` each pick** (no new mutable state) |
| 5 | the value hawk's window | **sweep {1.00, 1.15, 1.25} and pick by the bar** |
| 6 | room composition | **corpus-weighted realistic** (1 autopilot, 4 balanced, 5 character seats) |
| 7 | how the session ends | **leave everything uncommitted** for review |
| 8 | deliverables | batch re-measure · T19 before/after · a fresh 15-round mock CSV |

**Two assumptions stated and proceeded under**, both since borne out: `X` in step 4's "disagree on
≥ X % of picks" was **pre-registered at 1/3** before measuring (it came in at 48.7 %), and
`upside_chaser` was checked for the mirror defect in the same pass (it had it — its `boom_prob`
weight was the same stale column).

### Dead ends, kept because each would otherwise be re-proposed

- **Tobit for `floor`.** The censored-normal MLE is the textbook answer to T19 as the ticket framed
  it, it fits cleanly, and it nails the level control exactly (`corr(floor, mean)` = −0.000 by
  construction). It still **fails** — top-10 floor list **100 % ADP > 130**. Kept runnable as
  `method="tobit"`; it is the cleanest demonstration that the defect was never about the likelihood.
- **A neighbourhood rank on the raw quantiles.** Passes T19's bar (`corr(floor, adp)` −0.10…−0.21)
  and restores 16.14's original defect (`corr(upside, floor)` **+0.94 QB**). Kept as `"rank"`… on
  *ratios*; the raw-quantile version is what the oppositions block exists to reject.
- **`rank_delta`, the double rank.** Subtracting the level's own neighbourhood rank from an already
  scale-free ratio **over**-controls: `corr(floor, adp)` +0.29, top-10 90 % deep. Kept named.
- **A pool-relative `level_floor`.** Measured **inert** — inside a 40-player band the worst
  candidate is z ≈ −1.5 whoever he is, so it fires every pick and is a level tilt in disguise. The
  shipped version is board-wide.
- **A rounds-derived corpus reach ceiling.** Recomputing `round` and picks instead of using the
  panel's own gave a round-15 p95 of **8.8** against T15's published p90 of 52.3 — wrong by 6×, and
  it failed the shipped reacher on 11 of 15 rounds before being caught.
- **Choosing the value hawk's window by argmax.** The sweep is inside its own noise (+13.1 CE vs a
  pooled se of 10.7), so the argmax is a noise draw and the **tightest** eligible window ships.

### The one deviation from the plan of record

BUILD_PLAN step 2 asked for "Tobit **or** a rank-based conditional quantile". Neither worked on the
column as specified, and the fix was to change **what is being estimated** (ratios to the projected
level) rather than the estimator. The step is met — `floor` is repaired against its own bar — but by
a route the plan did not name. Written up in `findings.md` because the general form is reusable:
*before choosing an estimator, check the variable is on a scale the estimator can be right about.*

## 2026-07-28 (session 6) — the 2×5 mock re-run; three objections, three tickets, nothing built

**Status: DOCS-ONLY. No code changed.** Rule 7 gate — all three fixes are written up and costed,
none executed, awaiting the user's go-ahead on ordering. Full write-up in `findings.md` §"The 2×5
mock re-run (2026-07-28)"; tickets **T23 / T24 / T25**; durable lessons in `glossary.md`.

**What was run.** The 2×5 room again — 2 seats each of `autopilot` / `balanced` / `safe_floor` /
`reacher` / `value_hawk` — this time with the **shipped** `value_hawk` (16.14R step 6) instead of
the run-local approximation. One showcased 15-round draft (room seed 20260728, draft seed 728) on
the live 2026 FFC board, then **40 seeded drafts with the room reshuffled per seed**. Everything on
the shipped path; DEV-only, nothing written to `analysis/`. Driver `steps/mock_2x5_diag.py`.

**The user reviewed the picks by eye again and raised three objections. All three hold.**

### The three tickets

| | ticket | what it is | cost |
|---|---|---|---|
| 1 | **🔴 T23** | `mandatory_needs` drops TE because TE is in `flex_positions` → **12.2 % of seats finish with no TE**, 46 % of `autopilot` seats. A bug against a stated contract. | ~5 lines |
| 2 | **🟡 T25** | `ReachBudget` is attached to 2 of 10 seat types, so the round ceiling binds `reacher`/`value_hawk` and not `balanced` (4 of 10 seats in `REALISTIC_ROOM`). | small |
| 3 | **🟠 T24** | Width is per-**round** and never per-**player**; the board's `adp_stdev` is unread in the pick path. Consensus #2 lands at a **median pick of 4**. | a full sub-step |

**Recommended order is 1 → 2 → 3.** T23 and T25 are contained and re-measurable in one pass; T24
moves T15 bars 1/2/5 and the seat-faithfulness population and needs its own gated sub-step with a
before/after on the shipped measurement path.

### ★ The two findings worth carrying past this session

1. **An aggregate that pools reaches and falls cannot see a one-sided defect.** Round-1 mean
   |reach| is **2.91 sim vs 2.87 corpus** — the bar passes — while Gibbs (ADP 1.8) lands at a median
   pick of **4** and clears pick 4 **42 %** of the time against a realized **12 %**. A reach and a
   fall have the same absolute value and cancel. T15's *"an aggregate metric cannot see an impossible
   event"* one level down: there it was aggregation over **drafts**, here over **direction**, inside
   a metric that already passes. **Bars over |drift| need a signed companion.**
2. **A bar written from the symptom passes the general defect.** T20's done-bar was *"≥1 K and ≥1
   DST"* — the positions the ticket was about. It passed while the same filter left TE unguarded.
   Sibling of 16.14's *"state your bars as oppositions"*.

### ★ The mechanism T24 proposes, and why it is one object for three problems

A **per-seat private board**, `adp_seat = adp + κ_seat · adp_stdev · ε`, `ε ~ N(0,1)`, drawn once
per seat per draft. Measured basis: **`|drift| ≈ 2 × adp_stdev`** across the corpus, stable through
the usable range; Spearman(`adp_stdev`, |drift|) **0.484** against Spearman(round, |drift|)
**0.535**; and within rounds 1–3 the stdev terciles drift **2.11 / 3.33 / 8.91** — a 4.2× spread the
round curve cannot express. It addresses (a) round-1 tier structure without hard-coding a tier,
(b) **the T15 carry-forward verbatim** (*"needs per-seat board perturbation, not another width
parameter"*) — plausible, untested, (c) the only channel that is live in round 1 for `reacher`.

### Decisions taken this session

- **The `reacher`'s rounds-1–3 quiet is NOT a defect and is not to be "fixed".** It is the user's own
  2026-07-27 spec (`early_rounds=3`, `early_max_picks=8.0`, `large_from_round=5`). The defect is
  that `balanced` has no equivalent constraint. → T25.
- **The per-personality summary reports `pool_rank`, split R1–13 / R14–15** — not a 15-round mean
  reach, which is dominated by late-board ADP noise and by *when* a seat takes K/DST.
- **The corpus far tail is a data question first**, not behaviour to reproduce (p99 = pick 33 for an
  ADP 1–2.5 player; check `days_to_board` and keeper/dynasty leakage before fitting it).

### Dead ends / do not re-propose

- **Do not fix the reacher's early-round quiet with `temperature` or `width_mult`.** Its direction
  channels (`cos`, `rookie`, `upside`, hype) are structurally dead at the top of the board — every
  consensus elite is an established veteran with compressed within-position z-scores — so width with
  nothing steering it is exactly the *"width with no direction"* 16.14R step 5 deleted.
- **Do not narrow round 1 with another global width parameter.** T15 already established one knob
  cannot set both ends; the round-1 problem is *within-round* heterogeneity, which no round-indexed
  curve can express.
- **Do not read a behavioural ordering off one draft** — 30 picks per personality. This recurred
  because the *presentation* was a 15-round per-personality mean-reach table. Report the batch.

## 2026-07-28 (session 7) — T23 + T25 + T24: the room's width was too wide, not the wrong shape

**Status: BUILT.** The three tickets the 2×5 re-run opened, in that entry's own recommended order —
1 → 2 in one pass, then **3 as its own gated sub-step with a before/after on the shipped measurement
path**. Write-up in `findings.md` §"T23 / T25 / T24 (2026-07-28, session 7)"; register entries
`docs/TECH-DEBT.md` T23/T24/T25 all ☑; durable lessons in `glossary.md`.

### What shipped

| | change | where |
|---|---|---|
| T23 | `mandatory_needs` = `base_demand()`; nothing exempt | `draft/simulator.py` |
| T25 | `ROOM_CEILING` — `reach_budget=None` means *inherit*, not *unconstrained*; `unbounded_budget()` for the A/B controls | `draft/personalities.py` |
| T24 | `WidthCurve.base` (width **level** split from **shape**) — **the fix**. Plus the rejected-but-kept private board: `stdev` → `PASSTHROUGH_COLS`, `private_adp()`, κ on the model artifact | `draft/{simulator,personalities,mock}.py` |

New/changed steps: `steps/mock_room_bars.py` (bar sheet + `--kappa`/`--width-base`/`--shuffle-room`),
`steps/mock_t24_sweep.py` (the calibration grid, `--write` ships the choice).

### ★ The T24 verdict — the proposed mechanism is REJECTED and its by-product is the fix

T24 pre-registered a **per-seat private board**, `adp_seat = adp + κ · adp_stdev · ε`, as *one
mechanism for three problems*. Built, calibrated, and measured on the seating-marginalized harness,
it is **monotonically harmful on the objection it was designed to fix**:

| seating-marginalized, 8 seasons, 20 seeds | κ = 0 | κ = 1 | κ = 2 |
|---|---|---|---|
| elite past pick 4, `base` 0.70 | **18.8 %** | 19.7 % | 26.6 % |
| elite past pick 4, `base` 0.50 / γ 1.0 | **11.2 %** | — | 23.4 % |

**Why, in one line: at the top of the board `adp_stdev` is the same size as the gaps it perturbs.**
Bijan 0.7 · Gibbs 0.8 · Chase 1.0 sit 0.2 picks apart, so a draw of ±κ·0.8 does not *create* tier
structure, it **destroys the ordering that was already there** — which is precisely the mechanism
that makes an elite fall. The ticket's premise (*width is flat inside round 1, so make it
per-player*) diagnosed the right symptom and the wrong cause.

**What actually fixes it is the knob added to support it** — separating the width **level** from the
width **shape** (`width(round) = base · round^gamma`). Round 1 was simply too wide:

**Final measurement — the 40-seed seating-marginalized pair** (`analysis/mock_room_bars_
{baseline_shuffled,t24_shuffled}.json`; the 20-seed sweep rows above are superseded):

| | before | after | corpus |
|---|---|---|---|
| `WidthCurve` | `base 1.0 · γ 0.8` | **`base 0.6 · γ 1.0`** | — |
| **elite past pick 4** | 25.8 % **FAIL** | **15.3 % PASS** | 13.1 % |
| bar 2 · p95 / past-10 | 17.0 / 28.8 % | **16.0 / 25.2 %** | ≤ 20 / ≤ 30 % |
| bar 3 harvest | 0.00 sd | 0.00 sd | ≤ 1.0 |
| bar 5 dispersion | −7.1 % | **−11.4 %** | ±20 % |
| bar 1 round-1 mean | 3.33 | **2.64** | 2.87 |
| bar 1 profile distance | 0.107 | **0.089** | — |
| median `pool_rank` | 8.69 | **8.04** | 7.62 |
| moderate share | 33.7 % | **38.2 %** | 54.3 % |

**The cost, stated:** dispersion −7.1 % → **−11.4 %** — narrowing the top takes spread out of the
whole room and only `gamma` gives it back — comfortably inside bar 5. Everything else moves *toward*
the corpus, including bar 1's profile distance (0.107 → **0.089**), which is what separates `base
0.6` from the `0.5` that shipped an hour earlier: 0.5 overshoots to **tighter than real humans**
(11.3 % past-4) and pays 0.154 distance and −17.4 % dispersion for it.

The fixed-seating sheet (`t24`, comparable to `baseline`/`t23`/`t25`) agrees: past-4 **11.3 %**,
bar 2 16.0 / 25.3 %, dispersion −12.2 %, median `pool_rank` 8.15. The 2026 live board reads p95
**16.0** and 24.4 % past pick 10.

### ★ Three things the calibration got wrong before it got it right

1. **Calibrated on a 4-season subsample** (for speed) and shipped `base 0.7 / κ 2.0` on it. The full
   8-season sweep failed that config's landing gate outright (20.4 % vs an 18.1 % ceiling). *Calibrate
   on the same population the acceptance bar is measured on.*
2. **Measured on a fixed seating**, which flattered every number by 5–7 pp — `0.5/1.0/2.0` reads
   16.2 % fixed and **23.4 %** marginalized. See the seating confound below.
3. **Never measured the two knobs separately.** Every sweep row moved `base` *and* κ together, so
   the width narrowing wore the private board's credit for three runs. The isolating row
   (`base 0.7, κ 0`) is what settled it, and it existed only because the verdict looked wrong.

### Decisions taken this session

- **The private board is applied to the *utility* only.** The candidate band is an estimation
  condition β was fit under, and `CORPUS_REACH_P95` is measured in **public** picks — so a seat's
  private opinion must not become a way around either. A test pins it (`test_a_private_board_cannot
  _buy_a_way_past_the_public_reach_ceiling`).
- **κ lives on the model artifact, beside the width curve**, because the two are read together;
  `PRIVATE_KAPPA = 0.0` stays the module default, so a hand-built model is the pre-T24 room exactly.
  The artifact now also carries the **rejection verdict** next to the parameter, so the next person
  to reach for a private board reads the measurement before switching it on.
- **`NarrativeShock.intercept` is NOT re-fit.** Its transportability guard keys on `adp_spec`/`band`,
  neither of which T24 touches; the shock is default-OFF and 16.9 measured its intercept as
  unidentified. Re-fitting an unidentified parameter to chase a width change would be worse than
  leaving it declared stale — the same call T15 step 3 made, for the same reason.
- **T25's done-bar ordering is not claimed** (see `findings.md`): the bar contradicts the ticket's
  own analysis of the reacher's specified quiet opening.

### Dead ends / do not re-propose

- **Do not switch the private board back on** without re-running the seating-marginalized sweep. It
  is not a null, it is **harmful**, monotonically, at every `base` measured. The idea reads well and
  the corpus law behind it (`|drift| ≈ 2 × adp_stdev`) is real — but that law is about *realized*
  drift, which is an outcome of the whole room, and feeding it back as a *per-seat perception* noise
  term is a different thing entirely.
- **Do not push `base` below ~0.5.** `(0.35, 1.1, κ=1)` reaches 9.4 % past pick 4 and **fails bar 5**
  at −20.3 % dispersion. 0.5 is where the two bars meet.
- **Do not read the round-1 half-split off a fixed-seating batch** — see the seating confound above.
  It is also **not resolvable at this sample size** either way: the same room reads 0.54 / 0.82 /
  1.11 / 1.22 across measurement configurations, because a handful of large first-half reaches
  dominate a mean over ~1,600 picks. **Use the landing *share* (n ≈ 640) as the bar and keep the
  rise as a diagnostic** until someone gives it a trimmed or median-based estimator.
- **Do not calibrate on a subsample of the seasons the bar is measured on**, and **do not move two
  knobs together** and attribute the result to the interesting one.

### ★ What to try next on the elite-fall residual (for whoever picks T24 up)

The room now lands at 15.3 % against a realized 13.1 %, so the objection is closed — but the
*mechanism* behind it is worth stating because the next width question will hit it. At the top of
the board the consensus gaps (0.2 picks) are far smaller than any softmax width the fitted β can
express, so the top ~6 players are near-interchangeable to every seat. Narrowing `base` works by
making the whole room follow those gaps more faithfully; the more surgical fix is a **steeper
`AdpSpec.exponent`** (tightening only the top) **with `base`/`gamma` restoring depth width** — the
three-knob version of the trade T15 could not make, because `base` did not exist then. ⚠ Changing
the exponent means **refitting β** (it is an estimation condition), i.e. `steps/t15_1_respecify.py`,
not an artifact edit.

### ⭐ T24 acceptance, pre-registered (written 2026-07-28 **before** reading the shuffled sweep)

The first calibration was run on a **fixed-seating** 4-season subsample and does not survive honest
measurement, so the choice is re-made under a rule stated in advance rather than after the fact.
On the **seating-marginalized** sweep (`--shuffle-room`, 8 seasons), ship the config that:

1. passes the **landing gate** — top-band past-pick-4 ≤ corpus + 5 pp (**the objection itself**);
2. passes **T15 bar 2** (elite p95 ≤ 20 picks, past-pick-10 ≤ 30 %);
3. holds **bar 5** dispersion inside ±20 %;
4. does not raise **`ceiling_saturation`** more than ~5 pp above the κ = 0 room;

and among those, minimizes T15 bar 1's profile distance. **If nothing clears 1–4, ship κ = 0** — the
mechanism stays in the code, default-off, and T24 is written up as a null rather than tuned until a
noisy statistic agrees.

**Why (4) is a gate and not a diagnostic.** `κ_seat = κ · width_mult` gives the `reacher` κ = 4.0,
and mid-board `adp_stdev` is 8–12, so it perceives a deep player anywhere in a ±35-pick window while
`CORPUS_REACH_P95[0]` allows **14.6**. Every pick then maxes out the budget, and the *budget* — not
the belief — selects the player: the room still drafts, still passes a dispersion bar, and has
quietly become *"take the maximum legal reach"*. **A constraint that binds on every pick is no
longer a constraint, it is the policy.** Measured by `ceiling_saturation` in `steps/mock_t24_sweep.py`.

**Bar 4 (11.2 availability Brier) is already answered: +0.088996997698074, CI [+0.0803, +0.0996] —
bit-identical to the committed 16.14R value.** `draft/availability.py` imports nothing from
`personalities`, so neither the private board nor the width curve can reach it; the run confirms the
structural argument instead of resting on it.

**The rule's verdict, applied** (all nine seating-marginalized configs, ranked by the rule):

| base/γ/κ | past-4 | bar 2 past-10 | bar 5 disp | distance | verdict |
|---|---|---|---|---|---|
| **0.6 / 1.0 / 0** | **14.7 %** | 24.4 % | **−11.4 %** | **0.0825** | **← SHIPPED** |
| 0.5 / 1.0 / 0 | 11.3 % | 23.2 % | −17.4 % | 0.1544 | passes, overshoots |
| 0.35 / 1.1 / 1 | 9.4 % | 24.1 % | **−20.3 %** | 0.2152 | fails bar 5 |
| 0.7 / 0.8 / 0 | 18.8 % | 25.6 % | −18.6 % | 0.1426 | fails landing gate |
| 0.7 / 0.8 / 1 | 19.7 % | 26.2 % | −17.5 % | 0.1417 | fails landing gate |
| 0.85 / 0.8 / 1 | 22.8 % | 27.7 % | −11.8 % | 0.0824 | fails landing gate |
| 0.5 / 1.0 / 2 | 23.4 % | 28.1 % | −8.9 % | 0.0665 | fails landing gate |
| 0.7 / 0.8 / 2 | 26.6 % | 29.4 % | −9.9 % | 0.0756 | fails landing gate |
| 1.0 / 0.8 / 0 | 26.6 % | 28.5 % | −7.0 % | 0.1205 | today's room |

Corpus past-4 **13.1 %**, gate ≤ 18.1 %. **Gate (4) never bound** — `ceiling_saturation` measured
**1.5–2.3 % everywhere**, so the saturation story that motivated it was wrong: the reach budget is
not what selects picks at any κ tested. Kept as a standing check; the failure it describes is real
even though it did not occur here.

**★ A fourth method failure, and the same one twice.** `base 0.5` shipped before `0.6` was measured,
exactly as `0.7/κ2` had shipped before the 8-season grid existed. Both times the grid did not
**bracket** the choice — it sampled points and the best one at the edge got shipped. `0.6` beats
`0.5` on every secondary (round-1 mean **2.73** vs 2.51 against a corpus 2.87; dispersion −11.4 % vs
−17.4 %; distance 0.0825 vs 0.1544) while passing the same gates, and it lands *on* the corpus's
past-4 rather than 2 pp tighter than real humans. *Measure the dial before shipping a point on it —
a sweep whose winner sits at the edge of the grid has not finished.*

## 2026-07-29 — the mock-drafter completion audit: T13 + T18 + T22 closed, T26 opened

**Status: BUILT.** A full audit of the mock drafter, then everything it found still open. Write-up
in `findings.md` §"The mock-drafter completion audit (2026-07-29)"; register entries `docs/TECH-DEBT.md`
T13/T18/T22 ☑ and **T26** (new, deliberately not fixed); durable lessons in `glossary.md`.
**597 tests (was 587), ruff clean.** Lockbox, frozen value stack and fitted β untouched.

### What the audit found

The mock-draft arc itself is **complete**: T15 steps 0–4, then 16.14R's seven steps, then
T23/T25/T24 — every one of the five T15 bars plus the landing gate passes on the shipped config, and
the interactive drafter runs a legal 15-round 2026 draft end to end. The register's at-a-glance
table still carried **T15 as open** while its own section was ☑ throughout; that row is corrected.

What was *not* done was everything behind it: three open entries, all of which reach the board a
human drafts from.

| | ticket | what it turned out to be |
|---|---|---|
| 1 | **T22** 🟡 | not latent at all — the interactive drafter **prints** boom/bust, so the 2026 board told the user Bijan Robinson and Puka Nacua *never boom* |
| 2 | **T13** 🟠 | not the coupling — **DuckDB's parallel float aggregation**, which is order-dependent |
| 3 | **T18** 🟡 | not an exaggerated behaviour — a different quantity; fixing the reference **reverses its sign** |

### Decisions taken this session

- **Fix T22 in the enrichment, never in the frozen column.** `boom_prob_live`/`bust_prob_live` from
  season − 1, read-only, `NaN` where unseen; the CLI shows those plus `tail_risk`. `ENRICH_VERSION`
  → `v3-t22-live-vol` so every cached board rebuilds.
- **Delete `avg_reach` rather than repair it.** New columns in stated units (`avg_reach_rounds`,
  `n_reach_picks`) + a ±2-round health gate. A silently redefined column is how the F.5 and T19
  defects both travelled.
- **Do not fix T26 (`pos_share_*` pooled across formats) now.** It refits β, and β's scale is what
  T15's and T24's width calibration was measured against. Measured (0.83 pp mean per-manager QB-share
  difference) so the deferral is informed, and logged against the next 11.1 refit.
- **T13's fix pins reads, not the sampler** — the frozen sampler is untouched and the pinned digest
  equals one of the runs the unpinned code was already producing, so no model number moves.

### Dead ends / do not re-derive

- **The Iman–Conover permutation is not T13's cause.** Nor is row order, `PYTHONHASHSEED`, or BLAS
  threading — all four ruled out by measurement before DuckDB threads fixed it completely. Do not
  re-open the coupling on the strength of the "marginals invariant, assignment moves" fingerprint;
  that fingerprint also describes an input wobbling below the noise floor of the aggregates.
- **`build_tendencies`'s `avg_reach` still inherits the T18 defect** whenever its caller passes a
  board that is not the drafts' own (which `opponent_tendencies` does). It stays the labelled POC it
  always was; `redraft_reach` is the function for any reach that will be read or fitted on.
- **`app/streamlit_app.py`'s season selector is `list(DEV_SEASONS)`**, so the Phase-14 MVP cannot
  select the season anyone is drafting. Noted during the `max(train_seasons)` sweep; it is Phase-14
  work, not a defect in the engine.

### ★ Next

Review + commit sessions 6, 7 and this one (one tree), then **Session I = Phase 17 formats**. The
mock drafter has no open register entry against it. Stage-0 FFC chore last pulled **2026-07-24** —
**due after 07-30**, i.e. next session.

## 2026-07-30 — the all-personality walkthrough → Session H.5 scoped (docs-only, no code)

**Status: DOCS-ONLY.** No `src/` change, no `analysis/` write beyond three CSVs of the walkthrough
itself. The user asked for a full 15-round mock with **all ten seats played by personalities**
(`REALISTIC_ROOM`, `room_seed=17`, draft `seed=0`, live 2026 FFC board snapshotted 2026-07-24, 223
players), a round-by-round walkthrough, team constructions, and an assessment of the mock drafter
**as a shippable product**. Then: write the resulting work into the docs as the direct next steps,
ahead of the existing session order, app still last.

Write-ups: `findings.md` §"The all-personality walkthrough (2026-07-30)"; register entries
`docs/TECH-DEBT.md` **T27/T28/T29/T30** + ordering item 11; the plan of record
`docs/BUILD_PLAN.md` §"Session H.5 — THE MOCK-DRAFTER VALUE SEAM"; `ROADMAP.md` ★ SESSION PLAN
(H.5 inserted ahead of I, "← NOW" moved); `glossary.md`; this entry.

### What the walkthrough established — the simulation is finished

Four things were tried and could not be broken, and each is worth keeping because each was a
*suspicion* first:

- **Positional mix matches reality.** The QB market looked broken by eye (17 QBs for 10 teams; Lamar
  Jackson available at pick 75 projecting 315). It is not: over **333** realized 10-team/15-round
  complete human Sleeper drafts the medians are WR 53 · RB 45 · QB **16** · TE 15 · K 9 · DEF 10,
  against the sim's 55 · 42 · **17** · 16 · 10 · 10. Six positions in line at once.
- **The mechanisms are legible by eye.** `reacher` spent **exactly** its `ReachBudget` — 3 of 3
  swings (>25 picks: Dobbins +37.4 R6, Goff +30.2 R7, Nailor +38.8 R10) and 5 of 5 leans (8–25) —
  with a rounds-1–3 max reach of **−0.1** against its 8-pick clamp. `upside_chaser`, which inherits
  `ROOM_CEILING` (no count tiers, no early clamp), reached **+11.3 in round 2**: the two budget
  mechanisms are separately visible in one draft.
- **Elite fall sits on the shipped distribution.** 3 of 12 consensus top-12 past pick 10 = **25.0 %**
  against the committed 25.2 %; worst fall Jonathan Taylor ADP 7.7 → pick 15.
- **The behavioural fit is not stale.** 70,614 choice groups over **9 seasons**; the human corpus
  spans 2017–2026 with the bulk in 2021–25 (1,079 human drafts in 2025 alone). The "β fit on 2017–20
  applied to a 2026 board" worry is unfounded — checked, not assumed.

Also confirmed internally consistent: title probabilities sum to **1.000**, playoff to **6.000**; all
ten rosters legal; the room's `tail_risk` ordering is monotone across seven seat types
(value_hawk −0.260 · safe_floor −0.090 · chalk −0.078 · balanced −0.010 · autopilot +0.013 ·
reacher +0.052 · upside_chaser **+0.152**).

### What failed — the seam, not the simulator

- **T27 (🟠) — the board a human reads is not the board the seats optimize.** The CLI prints
  `proj_points`; utility and `value_hawk`'s objective run on `base_value = ce_vbd`. **Maye proj 316.5
  → +68.5; Daniels proj 313.4 → −101.6.** Per-position mean haircut 0.28 QB / 0.33 RB / 0.28 WR /
  0.30 TE is Phase 4.4's intended level correction; the **dispersion** (QB 0.15–0.56, sd 0.12) is the
  defect for a reader. Mechanical half: `proj_points` is not in `PASSTHROUGH_COLS`, so
  `_prepare_board` drops it and any new driver silently prints an empty column — **verified by
  writing one and getting `-` for all 150 picks.**
- **T28 (🟠) — `team_value`/`portfolio_value` are slot-blind.** `grep -n "starters"` over
  `draft/optimizer.py` returns nothing. QB2 contributions on this draft: **−101.6** (T1 Caleb
  Williams), **−92.1** (T4 Kyler), −55.6 (T5 Mahomes), **+51.0** (T3 Hurts), +33.1 (T9 Dart); room
  total 1,938, QB2 line **−122**. Spearman vs title over the ten teams: portfolio CE **+0.758** ·
  `team_value` **+0.685** · starting-nine consensus proj **+0.455** · **starting-nine Phase-5 mean
  +0.915**. T4 reacher: **9th of 10 on VBD, 3rd on starting-lineup projection, 9th on title.**
- **T29 (🟡)** bare absolute probabilities from a sim carrying a documented **−113 pts/team** level
  bias and a *marginal* playoff Brier 0.240 (title 0.088, on-diagonal — ordering is fine).
- **T30 (🟡)** `autopilot` at 1 of 10 seats vs **0.2 %** of realized seats (50×), and it is the seat
  that manufactures the spill: mean `pool_rank` **1.77**, median **1.0**, harvest **+11.7 picks**.

### Decisions taken

- **Session H.5 runs NEXT, before Session I / Phase 17.** User instruction: the mock-drafting system
  is adjusted before any other session, and **the app stays strictly last** — every fix lands in the
  engine and the CLI, and Phase 14's board view inherits it for free. E→L ordering otherwise unchanged.
- **All four tickets are display, labelling or composition.** None refits β; none touches the frozen
  value stack; T26 stays deferred to the next 11.1 refit. Every step's hard bar is that
  `analysis/mock_room_bars_verify_20260729.json` reproduces **bit-identically** — *a display change
  that moves a bar is not a display change.*
- **§3.7 gates are NOT waived this session** (contrast 16.14R). Step 2 contains a decision that is the
  user's, and each step is independently shippable.
- **T28 ships a labelled second metric, never an edit to `team_value`.** The cost report's numbers are
  frozen output and the lockbox is spent. **`value_hawk` keeps `objective="portfolio_ce"` for now** —
  changing it refits nothing but *does* change the room's picks, so it moves T15 bars 1/2/5 and needs
  the full T24 treatment (seating-marginalized before/after) as its own sub-step.
- **Bars B1–B6 are pre-registered in `docs/BUILD_PLAN.md` before any of it runs**, including two that
  can fail informatively: **B2** (if the level haircut is *not* explained by `games_played_mean`, that
  is a modelling finding — stop and open a ticket, do not caption it) and **B5** (if starter-aware
  value does not out-rank portfolio CE against title probability over ≥40 drafts × ≥4 seasons, **T28
  closes as a labelling fix only** — the ten-team walkthrough is one draw).

### Dead ends / do not re-derive

- **The QB market is not broken.** 17 QBs for 10 teams is the corpus median (16). Do not "fix" the
  room's QB timing; if anything looks wrong at QB it is T27's level dispersion, not the seats.
- **`steps/mock_draft.py` does not have T27's mechanical half** — `cmd_start` already re-attaches
  `proj_points` after `_prepare_board`, with a comment. The fix is to make the attach unnecessary, not
  to repair the CLI.
- **λ is not "too big".** `base_value` differs from `vbd` through **two** channels — the Phase-5 mean
  (T3 availability) *and* λ·Var — and the variance charge is taken relative to the positional
  replacement's own CE (`ce_replacement(QB)` = 119.4 here). A first pass read the gap as a pure
  variance penalty and it does not reconcile: Josh Allen `vbd` +70.0 → `base_value` +55.2 while
  Daniels +22.6 → −101.6. **Decompose before diagnosing.**
- **`chalk` vs `safe_floor` is not separable in one draft** (mean floor 0.023 vs 0.034; `safe_floor`
  took 3 rookies to `chalk`'s 1, including Hampton at floor −0.35 against its own weights). That is
  consistent with what the code already documents — the durability weight's gap to `balanced` is noise
  around zero, which is why its done-bar A/Bs the weight against *itself-off*. Do not read a seat's
  spec off 13 picks.

### ★ Next

**Session H.5, steps 1→5 in order, gate after each.** Then Session I = Phase 17 formats, J (optional
dynasty), K = Phase 14.1 MVP + surfacing (strictly last, do not bundle), L+ the go-live tail.
**Stage-0 FFC chore: last pulled 2026-07-24 and the board used here is that snapshot — it is at the
6-day mark, so run `steps/stage0_adp_snapshot.py` then `steps/backup_db.py` at the top of H.5.**

---

## 2026-07-30 (session 2) — ★ SESSION H.5 COMPLETE: the mock-drafter value seam (T27 · T28 · T29 · T30)

**Status: BUILT, all five steps, run straight through** — the user waived the §3.7 sub-step gate for
this session ("run through all of them without stopping, no stop gate") after answering four
decisions up front. **612 tests (was 597), ruff clean. UNCOMMITTED** per the user's choice, on top of
the existing uncommitted docs tree. DEV-only; the spent lockbox and the frozen value stack are
untouched.

**The four decisions, and what happened to each.**

| decision | outcome |
|---|---|
| switch `value_hawk` to a starter-aware objective **with the full T24 treatment** | **not shipped** — the treatment ran and B5, the pre-registered bar that authorises the switch, failed first |
| on a pre-registered bar failing: **record, open a ticket, keep going, chase the cause** | exercised twice (B2 → **T31**, B5 → T28 closes as labelling); both causes chased to a mechanism |
| ship a T30 composition change **only if every bar holds or improves** | not shipped — two bars regressed slightly; the argument is written down either way |
| leave the tree uncommitted | done |

**Artifacts.** `analysis/session_h5_seam.json` (the six bars in one place) ·
`analysis/mock_room_bars_{h5_baseline,h5_step1,t30_chalk_swap,t28_benchw0}.json` ·
`analysis/t28_starter_value.{json,csv}` (2,000 team-rows). New steps: `steps/t28_starter_value.py`,
`steps/session_h5_seam.py`. Write-ups: `findings.md` §"Session H.5", `docs/TECH-DEBT.md`
T27/T28/T29/T30 ☑ + **T31**, `glossary.md` (five entries), `ROADMAP.md`, this entry.

### Method notes worth keeping

- **The baseline was banked before anything was touched.** `mock_room_bars.py --label h5_baseline
  --shuffle-room` reproduced `mock_room_bars_verify_20260729.json` **bit-identically on every field**
  before the first edit. Without that, "B3 passes" would only have meant "matches a number from
  another session's code".
- **B6 was diffed against a `git worktree` at the session-start commit**, not argued from the algebra.
  Cheap and available because all `src/` was committed at HEAD (only docs were dirty) — worth
  remembering as a technique: `git worktree add <tmp> HEAD` + symlink `data/` and `analysis/`.
- **The Stage-0 FFC chore was deliberately deferred to the end of the session**, not run first as the
  pointer suggested. Refreshing the 2026 board mid-session would have changed the live-board
  measurements (B1/B2) and the bar sheet's 2026 readout, breaking comparability with the walkthrough
  that opened these tickets. The board is banked at the close instead; nothing about the chore's
  purpose (the boards are unrecoverable later) cares which end of a session it runs at.
- **`bench_weight` and `--room` are both knobs that nest**: `bench_weight=1.0` re-runs the greedy
  pick-for-pick and the default `--room` is `REALISTIC_ROOM`, so an unflagged run is a true baseline.
  T24's lesson about moving two knobs at once is the reason each A/B moved exactly one.

### Dead ends and near-misses

- **The `SIGNAL_COLS` assertion the spec asked for was already false.** `mean` (and `vbd`,
  `overall_rank`) were in `SIGNAL_COLS` before this session, weighted by nothing. Writing the test as
  specified would have failed on arrival. Rather than edit the list (which is also the known-column
  registry that turns a typo into a loud error) the invariant moved to the point of use:
  `personalities.LEVEL_COLS` + a `__post_init__` guard.
- **A `starter_value`-per-candidate pick path was never viable** — ~16M `lineup_points_matrix` calls
  across a batch measurement. The closed-form `starter_marginal` exists for that reason and is
  asserted equal to the solver on 120 random rosters, because a second definition of "starting" is
  the T18 failure mode waiting to happen.
- **The walkthrough's Spearman(starting-nine Phase-5 mean, title) = +0.915 did not replicate** (+0.792
  over 200 drafts, *worse* than portfolio CE). One draw of ten teams. The spec said so in advance and
  was right.

### ★ Next

**Session I = Phase 17 League-Format Fidelity (17.1–17.4)**, unchanged. Open against the mock drafter:
**T31** only, and it is a modelling ticket that needs its own session and its own before/after against
the 2025 dress-rehearsal calibration — it is *not* a Phase-14 blocker for the drafted range, but it is
one for any surface that shows a distribution for a deep player. **T26** still waits on the next 11.1
refit. The T30 composition swap is a live candidate for a deliberate overrule; the flag is recorded.

## 2026-07-30 (session 3) — multi-seat human control scoped: 16.17 + 14.J (docs-only, no code)

**Ask (user):** in the finished mock drafter, "users can control as many of the picks as they'd like —
for example, they can pick personalities for 6/10 to automate most of it, but they control the other
4/10 slots and thus create 4 teams themselves." Asked whether that already exists in the md files, and
to add it to a session if not.

**Answer: it did not exist anywhere — not in BUILD_PLAN, ROADMAP, PROJECT, PLAYER-VIEW §9, or the code.**
Every doc and every call site assumes **exactly one** human seat. Checked, and the gap is structural, not
an oversight of the UI spec:
- `DraftState.your_team` is a single `int`; `run_to_completion` routes on `team == state.your_team`.
- The `team → seat` map is positional arithmetic, `seat = team - 1 if team > state.your_team else team`,
  written out **three times** — `personalities.make_room_pick_fn`, `mock.full_room_pick_fn` (identity
  variant, zero humans), `steps/mock_draft.py::seat_of`/`seat_name`. It is correct only at k = 1.
- `make_room(mix, n_opponents=n_teams - 1)` **raises** on any mix that is not exactly `n_teams - 1` long,
  so even the room-composition call refuses a 6-personality room.
- Consequence: the engine supports two room shapes — 1 human + 9 personalities (interactive) and 0 humans
  + 10 (batch measurement). Every k in between is unreachable.

**Scoped as 16.17 (engine) + 14.J (UI).** Written into `docs/BUILD_PLAN.md` §16.17 / §14.J, `ROADMAP.md`
(phase line + a new **Session I.5**), `PROJECT.md` §5, `docs/PLAYER-VIEW.md` §9.1 (the `n_opponents`
contract was wrong as written) + new §9.5, `glossary.md`, `CLAUDE.md`.

**Design decisions taken while scoping:**
1. **One `SeatMap`, and the three copies of the arithmetic are deleted rather than joined by a fourth.**
   `mock.full_room_pick_fn`'s docstring already conceded the two builders "differ only in the `team ->
   seat` mapping they were split over" — H.5 then found that split had silently made the *interactive*
   room a different room (`value_hawk` running as `balanced`). A second divergence of the same shape is
   what a `human_teams` parameter bolted onto both builders would buy.
2. **`SeatMap` lives in `personalities.py`, not `simulator.py`** — 16.15's layering argument, unchanged:
   the draft engine every earlier phase imports must not learn the personality library.
3. **`your_team` stays and stays primary.** The frozen cost report, the 9.5 win-prob objective,
   `bestball`, `mcts` and every backtest step read it; none of them should learn about a second human.
   `human_teams` defaults to `{your_team}`, so nothing outside the mock drafter changes shape.
4. **The done-bar is bit-identity, not a new metric.** k=1 reproduces the shipped interactive room
   pick-for-pick, k=0 reproduces `full_room_pick_fn` pick-for-pick, and
   `analysis/mock_room_bars_verify_20260729.json` reproduces to the digit. *A plumbing change that moves a
   bar is not a plumbing change* (H.5). Nothing here refits β or touches a frozen contract.
5. **Placed as Session I.5, after Phase 17** — 17.1 generalizes `RosterSlots`/`LeagueFormat` inside the
   same `draft/simulator.py`, and 17.3's settings contract is the natural home for `human_teams`, so
   landing the seat map second avoids a rebase. **Explicitly pullable into Session I as a warm-up** (the
   T10 pattern) if the user wants to draft four teams sooner — it depends on nothing in Phase 17.

**★ Two honesty rules attached to the feature, in the engine substep rather than the app** (16.12's
precedent — the rule belongs where the number is made):
- **k human teams in one draft are ONE observation.** Each human pick removes a player from the other
  human seats' pools, so the teams are mechanically anti-correlated. The cost report is per-seat and
  stays per-seat; no combined record, win-rate or average grade across seats one user drove. Drafting
  four teams and liking all four is one draw, and it will *look* like four.
- **The T15 realism bars describe a fully-simulated room.** Profile distance, dispersion, chalk share and
  the elite-fall landing were all measured with ten modelled seats; a room where four are human is not
  that room. Print the scope; do not re-measure the bars per-mock.

**Not decided (left to the build):** whether `--seats` supersedes `--seat` or wraps it, and whether the
per-seat pick-fn map is exposed on `simulate_draft` as well as `run_to_completion`.

## 2026-07-30 (session 4) — T31: the live-board level correction

**Order for this run (user decisions, 2026-07-30):** T31 → Session I (Phase 17) → hard stop → Session I.5
(16.17). §3.7 gates waived within T31 and Session I; one commit per session, no push.

### ★ The register's filed cause is WRONG — the third prescription in a row that was (T13, T24)

`docs/TECH-DEBT.md` T31 says the break is that "a live season has no realized prior-season basis to
shrink the per-game level toward". **There is no such branch.** `train_seasons` for a 2026 board is
`[s for s in DEV_SEASONS if s < 2026]` = 2014–2022, and for a 2024 board it is
`[s for s in DEV_SEASONS if s < 2024]` = **the same nine seasons**. The fitted QuantReg models are
therefore *identical* between the board that fails and the board that passes. Whatever the defect is, it
is not in the fit.

**Measured cause: linear extrapolation of a per-position QuantReg far below the support of its training
data, exposed by the live board being much deeper than any historical proxy board.**
- The Phase-5 level is `H = b0_τ + b1_τ · calibrated_mean`, fit on the **conditional cohort**
  (`weeks ≥ 0.85 · season_games`) — necessarily starters. Fitted intercepts are large and positive:
  **QB q50 b0 = 169.35**, RB 68.95, WR 43.70, TE 36.24.
- Breakeven, i.e. where the fitted level exceeds the projection it is built from: `proj_points` below
  **272 (QB) / 187 (WR) / 170 (RB) / 150 (TE)**.
- Training support of `calibrated_mean` bottoms out at **QB 34.1 / TE 11.0 / WR 12.0 / RB 4.9**
  (QB 1st pctile 36.2). The **2026 board's median QB `calibrated_mean` is 11.4** — below the *minimum*
  of the training data. **56.4 % of 2026 QBs sit below training support**, against **2.3 % on 2024** and
  **6.7 % on 2022**. Board depth, not season liveness.
- The low end is additionally **selection-biased upward**: a low-projection player who nonetheless played
  85 % of a season is one who won a job, so the cohort's low tail is made of breakouts. This is why
  interpolating the fit to the origin does **not** repair the sign (checked: the origin slope is still
  ~3.4× steeper than `1/correction`), and why the repair has to reach for the consensus level.

**Structural gate = `value_board.source`, already in the frozen contract.** 2022/2023/2024/**2025** are
`proxy`+`rookie`; **2026 is `consensus`** (490/490). So a source-gated fix is bit-identical on every
historical board **including 2025** — the lockbox stays valid and **the calibration holdout stays
unspent**. The read of 2025 the user authorised turns out not to be needed; B5 below verifies 2025 by
hash rather than by reading its calibration.

### ⭐ T31 PRE-REGISTRATION (written before the fix exists; bars are not to be softened)

Population = the 2026 live board. "Drafted range" = `adp ≤ VALUE_SCALE_ADP_MAX`, T27's population.

| bar | property | BEFORE (measured 2026-07-30) | pass |
|---|---|---|---|
| **B1** | whole-board negative-haircut share (`mean > proj_points` is impossible for a level correction) | **38.75 %** (186/480) | **≤ 2.0 %** |
| **B2** | drafted-range `spearman(haircut, games_played_mean)`, all four positions — T27's shipped bar, unchanged | QB −0.902 · **RB −0.288 FAIL** · WR −0.538 · TE −0.838 | **≤ −0.50 all four** |
| **B3** | full-board `spearman` **sign** (off the drafted range the two prices genuinely differ, so no magnitude is demanded — only that it not be positive) | QB **+0.474** · RB **+0.225** · TE **+0.237** · WR −0.011 | **≤ 0 all four** |
| **B4** | the `sd ≈ mean` fingerprint, measured against the projection rather than against our own mean: per-position median `sd / proj_points`, and the whole-board max | median QB **3.57** · RB 0.69 · TE 0.73 · WR 0.58; **max 23.06** | **median ≤ 1.0 all four; max ≤ 3.0** |
| **B5** | historical bit-identity — `assemble_distribution` on **2022 / 2023 / 2024 / 2025** | — | **byte-identical** |
| **B6** | do not touch what the model has a basis for — T17 `LEVEL_BAND` on 2026, and top-60 aggregate mean | ratio **0.7210** ∈ (0.55, 0.85); Σmean **12 176.44** | band holds; **Σ moves < 0.5 %** |

Fail any bar → stop, record, and report rather than retune. (B1's *whole-board* denominator is 480 rows
with both a projection and a cloud; the register's "22.8 %" was over a wider denominator that included
rows with no distribution. Per-position shares are unchanged from the register: QB 59.0 / RB 42.1 /
TE 33.0 / WR 30.8 %.)

### The fix

**`quantile.consensus_level_cap` — outside the support of our own fit, defer to consensus.** For a row on
a live-consensus board whose assembled `mean` exceeds the consensus `proj_points` it was built from,
scale that player's whole draw vector by `proj_points / mean`. Level corrected, uncertainty *shape*
(CoV) preserved, absolute `sd` falls with the level. Applied to `samples` after the draw loop, where it
is **exact**: `Y` is linear in the quantile band, so scaling draws == scaling the band, with none of the
`max(0, q10 − adj)` clamp's non-linearity to reason about. Non-capped rows multiply by exactly `1.0`,
which is exact in floating point — that is what makes B5 hold by construction rather than by tolerance.

**Interpretation to carry:** *outside the support of the quantile fit we add no level information of our
own.* That is the same posture the project already takes on value ("don't fight the sharp market"),
applied one layer down.

### ⭐ T31 RESULT — all six bars pass (2026-07-30)

`analysis/t31_level_cap.json` · `steps/t31_level_cap.py` · `steps/t31_hash_distributions.py` ·
`steps/t31_dump_summary.py`. Full write-up in `findings.md` §"T31"; register row + section in
`docs/TECH-DEBT.md` T31 (☐ → ☑).

| bar | before | after |
|---|---|---|
| B1 negative-haircut share | 38.75 % | **0.00 %** |
| B2 drafted-range rho | RB **−0.288** (QB −0.902 / WR −0.538 / TE −0.838) | RB **−0.666** (QB −0.906 / WR −0.904 / TE −0.889) |
| B3 full-board rho sign | QB **+0.474** / RB +0.225 / TE +0.237 | QB **−0.980** / RB −0.879 / TE −0.949 / WR −0.936 |
| B4 `sd/proj` median QB · max | 3.57 · 23.06 | **0.367** · **0.903** |
| B5 2022/23/24/25 | — | **byte-identical** |
| B6 T17 band · top-60 drift | 0.7210 | 0.7204 · **0.078 %** |

**Implementation as built** (differs from the sketch above in one way that mattered): the target is
`proj_points * avail_p / g_ref`, **not** a bare cap at `proj_points`. The bare cap was built first,
passed B4/B5/B6 and moved B1 to 8.1 %, but parked every capped row at `haircut == 0` — a tie mass with
low projected games and no haircut — and pushed **full-board QB spearman the wrong way, +0.474 →
+0.523**. Cap to the identity the gate measures, not to the boundary.

**Landing gradient** (share of rows whose level moved · median scale among them): ADP 1–24 **0.0 %** ·
25–60 2.9 % (0.988) · 61–120 11.9 % (0.971) · 121–180 51.9 % (0.883) · undrafted 96.5 % (0.443). Board
`sum(mean)` 41 155 → 33 998. A narrow repair, not a replacement — and both would have passed the bars,
so the gradient is reported alongside them.

**Not spent:** the authorised extra read of the 2025 calibration holdout. 2025 is proxy-sourced, so the
source gate leaves it bit-identical and B5 verifies that by hash without reading its calibration.

**Decided in-session, worth not re-litigating:** `LIVE_SOURCES = {"consensus"}` is the gate (a frozen
4.2 contract column, not a new flag or a season comparison) · the scale is applied to `samples`, not to
the quantile band, so the `max(0, q10 − adj)` clamp needs no reasoning about · `games` is deliberately
unscaled (availability was never wrong) · non-live rows multiply by **exactly 1.0** so B5 holds by
construction · `ENRICH_VERSION` → `v4-t31-level-cap`, which forces all nine 16.13 board caches to
rebuild (~35 min, unavoidable — the enrichment reads the cloud).

**Room-bar regression ☑ (added after the bars, 2026-07-30).** `steps/mock_room_bars.py --shuffle-room`
reproduces `analysis/mock_room_bars_verify_20260729.json` with **0 gate-side differences** and all four
bar flags `True`; only `readout_2026` moves (66 fields — the live board, explicitly "never a gate") plus
two `config` keys H.5 added (`bench_weight`, `mix`). Independently corroborated: the v3 and v4 board
caches are **byte-identical for every historical season** and differ only on 2026.
⚠ The first attempt showed **149 gate-side diffs** and looked like a leak — it had defaulted to
`shuffle_room: false` while the verify sheet used `true`. *Check the run's own recorded config before
reading its numbers.* Artifact: `analysis/mock_room_bars_t31_shuffled.json`.

## 2026-07-30 (session 4, cont.) — SESSION I: Phase 17 League-Format Fidelity

Ran straight through from T31 (no stop, per the user's gate choice). Four scope decisions locked up
front; all five done-bar gates PASS (`steps/phase17_formats.py`, `analysis/phase17_formats.json`).
**658 tests (+41, `tests/test_phase17.py`), ruff clean.** Full write-up: `findings.md` §"Session I".

**Decisions as built:**
- **17.1 nested-eligibility flex only.** `RosterSlots.flex_groups()` is the single fill-order rule
  (three solvers previously re-derived it); non-nested sets raise in `assert_nested`, which
  `LeagueSettings` calls. Multi-flex stays vectorized via **the carry** — the first attempt removed
  used rows by value and was wrong, because which row fills a flex differs per sim/week.
- **17.1 replacement:** a superflex admits only QB beyond the base flex, so its slots go to QB —
  **QB10 → QB20**; RB/WR/TE/K/DST unchanged. Live-2026 effect: best QB overall rank **15 → 3**.
- **17.2 presets + bounded knobs** (`SCORING_PRESETS`, `ruleset_from_preset`, `te_rec_bonus`,
  yardage-milestone bonuses). Two self-inflicted bugs found and fixed: pydantic ignored unknown
  fields (→ `_Rules` with `extra="forbid"`), and the `full_ppr` preset returned a different
  `RuleSet.name`, which would have split `cached_distribution`'s cache key.
- **17.3** `LeagueSettings` + `lockbox_validated()`; bracket generalized to **4/6/8** with derived
  byes (a 12-team/8-playoff league was previously unconstructible); **odd `n_teams` refused** with a
  reason at the settings layer.
- **17.4 round-based keepers only.** `apply_keepers` + `DraftState.skipped_picks`. No separate ADP
  adjustment — removing supply *is* the re-inflation; the forfeited pick is the price (147 picks,
  not 150).

**Not decided / deliberately out:** non-nested flex, auction keepers, dynasty (15.1), IDP, Sleeper
settings auto-import. `starter_marginal` routes multi-flex to the exact solver rather than
approximating with its one-flex closed form.

**★ NEXT: hard stop, then Session I.5 = 16.17 the seat map** (per the user's gate: straight through
T31 + Session I, stop before I.5).
