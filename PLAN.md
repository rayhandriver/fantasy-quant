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
