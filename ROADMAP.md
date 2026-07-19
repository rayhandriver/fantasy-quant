# ROADMAP.md — status tracker

Status only — definitions/target files in `PROJECT.md` §5; full per-step detail in `docs/BUILD_PLAN.md`.
Legend: ☐ todo · ◐ in progress · ☑ done · ✗ dropped · ◔ deprioritized · ⟳ reframed.

> **⟳ STRATEGIC REFRAME (2026-07-04).** Objective pivots from *beat ADP* → **direct-indexing
> personalization** (`docs/REFRAME-2026-07-04.md`, `docs/PERSONALIZATION.md`). Phases 0–2 stay done &
> valid. Below: promotions (5, 8, 10 → core/earlier), reframes (4, 6, 7, 11), **CFR dropped**, **MCTS
> deprioritized**, **NLP + all in-app AI deferred**, and a new **Personalization spine** (bottom).

- ☑ **Setup** — env scaffold (uv + Python 3.12, repo, docs, git). *2026-06-29.*

**Phase 0 — Data foundation** ✅ **COMPLETE** — ☑ 0.2 nflverse *(8 tables, weekly↔snaps 0.24% unmatched)* · ☑ 0.3 PFR *(advanced 2018+, reconciles 0.00%)* · ☑ 0.4 ADP *(FFC 2010–2024; top-150 gsis-matched; PIT ✓; homonym-dedup; Underdog deferred)* · ☑ **0.5 Vegas markets** *(game_lines 2014–25 free; de-vig + implied totals ✓; props key-gated)* · ☑ 0.6 news ingest *(injuries/depth 2014+ native-gsis; news_raw RSS pipe; PIT ✓)* · ☑ 0.7 PIT panel *(weekly+preseason grains; leak-assert ✓; 41-col join)* · ☑ 0.8 validation *(9 hard gates PASS; data_health.json; caught+fixed a 0.4 homonym bug)*
**0.9 — 2025 backfill + nflverse new-release migration** ✅ **DONE** *(2026-07-05)* — ☑ new-release ingest (`stats_player` release; renamed cols conformed) → **weekly 79,250 (2025 REG 18,539+POST 882) / seasonal 8,702**; 2025 reconstructs `fantasy_points_ppr` to 2.4e-6 · ☑ timestamped `depth_charts_ts` (554k rows, dt Aug-25→Mar-26; week-grain table untouched) · ☑ 0.8 validator PASS on extended store. *Root cause: nflverse restructured stats releases post-2024; frozen `nfl_data_py` hits the dead old path. 2025 = **calibration holdout** (`config.CALIBRATION_SEASONS`); draft-backtest lockbox stays 2023+2024 (`DEV_SEASONS`=2014–22); 2025 ADP → Sleeper later.*
**Phase 1 — Backtest harness** ✅ **COMPLETE** — ☑ **1.1 scoring** *(full-PPR reconstructs nflverse across 57.3k pw @1e-6; K/DST from pbp/game_lines; 9-starter QB/2RB/2WR/TE/FLEX+K+DST; K/DST identity bridge)* · ☑ **1.2 draft sim** *(10×15 snake, ADP+noise opponents, pluggable your_pick_fn, DraftState; ADP-typical + reproducible; adp_asof board)* · ☑ **1.3 walk-forward** *(rank_fn→K drafts→realized optimal-lineup pts, strict PIT; ADP pools 2036 vs worst-first 1458; survivorship LEFT-JOIN; PIT guard trips)* · ☑ **1.4 PAR metric** *(replacement QB10/RB24/WR24/TE12/K10/DST10; PAR ranks elite +818 vs scrub −943; PAR↔exp-wins 0.99)* · ☑ **1.5 significance** *(stationary block-bootstrap CIs; ADP-vs-ADP edge 0 not-sig; worst-first −578/season CI [−714,−438] sig; compare_to_baseline)*
**Phase 2 — Markets & baselines** ✅ **COMPLETE** — ☑ **2.1 VBD** *(value transform; monotonic; reuses 1.4 replacement)* · ☑ **2.2 baseline proj** *(prior-yr ppg, EB-shrunk, aged; on par w/ ADP: −59/season CI[−162,+33])* · ⏸️ **2.3 props-implied** *(math built+tested; free-data gap → **SHELVED 2026-07-10 (T7)**: markets layer formally deferred per "don't fight the sharp market" — reactivates only if a props source is wired)* · ☑ **2.4 ensemble-with-market** *(blend baseline+ADP; grid-fit w=0.25 → 2116 ≥ best component; vs ADP +80 CI[−22,+190] not-sig)*
**Phase 3 — Features (X)** ✅ **COMPLETE** *(2026-07-05; the engine)* — ☑ **3.1 opportunity** *(share/WOPR/aDOT/RZ; Hill/Jacobs top)* · ☑ **3.2 efficiency** *(rates + TD-regression flag corr −0.50 next-yr; QB EPA gated)* · ☑ **3.3 player** *(age as-of, draft capital, combine; rookies flagged)* · ☑ **3.4 environment** *(pass rate/pace/implied-total corr +0.86; 32 tm/szn)* · ☑ **3.5 exposures** *(build_exposures: 545×48, winsor-z per pos, PIT-guarded; 100% ADP-board cover; lagged WOPR↔pts +0.46; 2025 holdout builds)*
**Phase 4 — Mean VALUE** *(⟳ consensus-VBD, not edge-seeking)* ✅ **COMPLETE** *(2026-07-05)* — ☑ **4.1 consensus ingest** *(two-track: live FantasyPros scrape re-scored to full-PPR — 528 players, 99% gsis, corr 1.000 vs FP; historical baseline **proxy**; PIT + dispatch)* · ☑ **4.2 VBD value board** *(draft-time replacement from projections; QBs 6→0 in top-15 vs raw; frozen contract player_key·pos·proj_points·source·vbd·pos_rank·overall_rank)* · ☑ **4.3 rookie model** *(per-position ridge on draft capital + landing spot; OOS Spearman +0.62; +76 rookies into proxy board)* · ☑ **4.4 calibration** *(proxy bias 0.60 played / 0.46 incl-DNP; reliability bin-corr 0.99; correction→0.96; **2025 holdout bias 0.58, Spearman +0.57**)* · GBT/age-curve/hier-Bayes/props-shrink **demoted to optional**
**Phase 5 — Distributions** *(⟳ PROMOTED to core — the risk dial; the one value-side thing we build ourselves)* ✅ **COMPLETE** *(2026-07-05; season-total grain)* — ☑ **5.1 quantile** *(per-pos linear QuantReg on the calibrated mean; median slope ≈1.10; band fans with level 3/4 pos)* · ☑ **5.2 conformal** *(CQR; 2025 holdout coverage 70%→73% on the available cohort)* · ☑ **5.3 variance** *(weekly boom/bust + CoV; right-skew confirmed; corr(boom,CoV) −0.37 ⇒ separate axis)* · ☑ **5.4 injury survival** *(logistic discrete-time hazard → Beta-Binomial games-played, ρ=0.33; RB least available)* · ☑ **5.5 utility** *(mean-variance CE = E[Y]−λ·Var[Y] risk dial; assembler writes frozen `player_distributions`)* — **conditional 2025 coverage 76% ≈ 80% target**; unconditional 44% = role/depth attrition (documented limitation). *Deviations (no new deps): statsmodels QuantReg not XGBoost; sklearn hazard not lifelines — future intent to adopt those if the sample justifies. Weekly-grain distribution = future work (folds into Phase-10 sim).*
**Phase 6 — Personalization intelligence** *(⟳ from ADP-bias mining: where ADP is soft = how cheaply to indulge a preference)* ✅ **COMPLETE** *(2026-07-08; **wired into the cost report 2026-07-09** — `adp/softness.py` frozen DURABILITY signal → per-roster exposure gap × coef = softness credit + net-effective-cost lines under the untouched raw headline; drift-checked by `steps/phase6_adp_bias.py`)* — ☑ **6.1 ADP-alpha panel** *(1504 drafted offense × 9 DEV szn; target = VOR-alpha = realized VOR − **LOSO isotonic** ADP-implied VOR, leak-free; per-pos mean α≈0; breakouts McCaffrey/Kamara/Kupp top)* · ☑ **6.2 regression** *(alpha ~ PIT traits; **season-block-bootstrap** CIs; R²=0.017 — ADP prices ~everything)* · ☑ **6.3 softness scorecard** *(BH-FDR + sign-stability ≥60%; **one bias survives: prior-yr games/durability UNDER-priced +14.6 VOR/SD, p_fdr=0.001, 100% stable → cheap to prefer**; efficiency over-priced but ruled out p_fdr=0.06; rookie/experience/dispersion ruled out)*
**Phase 7 — Opportunity-adjusted projection** *(⟳ from "causal" — a feature, not causal inference)* — ✗ **BUILT & DROPPED (2026-07-11)**: all 4 substeps built + validated OOS on DEV; keep-or-drop gate (as-written bar) = **DROP**. ☑ **7.1 skill÷opportunity decompose** *(two-way FE / AKM split; skill face-valid — Kelce/CMC/Kamara top — but does NOT travel better than raw prior rate across moves: Spearman 0.458<0.587)* · ☑ **7.2 situation-multiplier re-projection** *(info-preserving delta on prior rate; on 466 movers a **wash-to-worse than naive** MAE 2.972 vs 2.901, gain −0.070 CI[−0.152,+0.014]∋0; EB-shrunk market beats it 2.821)* · ☑ **7.3 rookie transport** *(draft-capital+landing+combine → distribution; 1σ coverage 0.66, Spearman +0.53 — **works but duplicates 4.3**)* · ☑ **7.4 validate** *(strict walk-forward + verdict)*. **DROP rationale:** team fixed-effect carries no exploitable move-signal beyond carrying the rate forward — consensus already prices it (thesis-consistent). Code kept in-repo (`causal/`) like props/CFR.
**Phase 8 — Covariance & rosters** *(⟳ PROMOTED/earlier — tracking error is a covariance quantity; correlation appetite = a user dial)* ✅ **COMPLETE** *(2026-07-09)* — ☑ **8.1 estimate** *(relationship-typed pooled correlations; QB1-WR1 **+0.37** emp ≈ the +0.40 folk prior, 287 pairs; RB1-RB2 both-active only −0.05 — backfield negativity lives in availability; Σ hard gate + Higham repair; 142-player board Σ PASS, cond 9.1)* · ☑ **8.2 shrinkage** *(EB shrink toward structural priors, w=n/(n+κ); OOS walk-forward: shrunk ρ **halves** stack-variance error vs independence, MAE 21.7 vs 45.8, 217 pairs)* · ☑ **8.3 copula** *(targeted to handcuffs per 2026-07-09 decision; rotated Clayton on zero-filled RB1/RB2: τ=−0.14, λ_L=0.13; real-tail check 0.393 emp vs 0.391 Clayton vs 0.346 Gaussian)* · ☑ **8.4 roster risk** *(portfolio μ/σ/floor/ceiling + Iman-Conover on the Phase-5 clouds; stack-vs-hedge done-bar holds on the 2022 board)* · ☑ **8.5 handcuff option** *(contingent claim on 5.4 availability; elevation ratio 1.77 from 506 starter-out weeks; premium monotone in fragility)*
**Phase 9 — Valuation & draft policy** *(⟳ + constrained optimizer + cost report)* ✅ **COMPLETE** *(2026-07-10)* — ☑ **9.1 conditional-VBD** *(covariance half pulled forward 2026-07-09; **scarcity half done 2026-07-10**: a positional value-cliff `positional_cliff` gated by 9.4 availability → an urgency term in `RiskModel.effective_rank`, `scarcity_w=0` reproduces the covariance-only greedy)* · ☑ **9.2 constrained optimizer** *(= spine S2)* · ☑ **9.3 cost-of-personalization report** *(= spine S3; headline **portfolio CE** + risk profile)* · ☑ **9.4 lookahead** *(`survival_prob`: snake-aware ADP+noise survival to your next pick; scarce **and** vanishing = draft now; regression-tested to flip a pick)* · ☑ **9.5 win-prob objective** *(opt-in `winprob_pick_fn`: portfolio-CE prefilter → top-k greedy-completion rollout → Phase-10 mini-sim; **makes `DraftConfig.objective` real** — `make_playoffs`→playoff_prob, `championship_or_bust`→title_prob, T8a; 2022 DEV: objective swings 8–9 roster slots, title-max +0.09 title prob at 250 sims; title is resolution-limited → needs ≥~200 sims)*
**Phase 10 — Season/playoff sim** *(⟳ PROMOTED/earlier — the tracked benchmark + tail objective)* ✅ **COMPLETE** *(2026-07-09; `simulation/` package + weekly grain — the Phase-5 deferral folded in)* — ☑ **10.1 season engine** *(top-down weekly disaggregation: Phase-5 clouds + Phase-8 Σ via Iman-Conover permutation → Dirichlet(1/CoV²) week shares, real byes, uniform missed-game placement; `LeagueFormat` 14-reg/6-team/15–17 w/ top-2 byes; vectorized optimal lineups ≡ 1.3 reference; **sim-sd/realized league sd = 1.02**)* · ☑ **10.2 playoffs** *(reseeded bracket → title/playoff probs; **calibration gate on 1,800 DEV team-seasons: title Brier 0.0878 < 0.090, playoff 0.2302 < 0.240, reliability on-diagonal; stability 0.975/0.949**)* · ☑ **10.3 leverage** *(mean-preserving spread from any mid-season state: trailing +0.018 playoff prob at 1.6×, leader −0.028 — variance is about making the cut; `leverage_advice` verdict for Phase 13)* — *documented: 62.4% points coverage (Phase-5 attrition gap propagates) + −137 pt level bias; probabilities calibrate regardless*
**Phase 11 — Draft engine** *(⟳ opponent model = core & Brier-verifiable)* — **☑ step 0.10 Sleeper ingest + 0.10b corpus crawler DONE (2026-07-11)**: the pick-by-pick data pipe (`data/sources/sleeper.py`; `sleeper_drafts`/`sleeper_draft_picks`; gsis crosswalk 100% skill; POC `sleeper_tendencies`) **+ the corpus crawler** (`steps/phase0_10b_crawl.py`: seed registry incl. `league:<id>`, iterative BFS snowball via co-managers, **human/bot ADP split** `sleeper_human` vs `sleeper_mock`, complete-draft quality filter, `sleeper_manager_profiles` behavioral seed) **+ a real live corpus** (149 human + 117 bot drafts 2017–20, 289 manager profiles, crawled from the Sleeper docs' public example leagues). · ☑ **11.1 behavioral opponent model** *(2026-07-11 — conditional/McFadden logit on 7.9k real human picks/9 szn; **beats ADP-only** walk-forward: log-loss +0.113 CI[+0.101,+0.124], Brier +0.0088 CI[+0.0076,+0.0100]; interpretable coefs — **fandom +1.03** strongest, rookie +0.45, need +0.33; `draft/opponent_model.py`)* · ☑ **11.2 per-pick availability distributions** *(2026-07-11 — MC survival under the model; **availability Brier 0.158 vs best-tuned ADP+noise 0.316**, gain +0.159 CI[+0.083,+0.264] — the owed S4 metric; promotes to the S4 default; `draft/availability.py`)* · ☑ **11.3 realistic mock** *(2026-07-11 — `Personality` tilts + `opponent_pick_fn` sim hook; behavioral RB14/WR14 vs ADP+noise RB21/WR9; `draft/personalities.py`)* · ✗ CFR *(dropped — snake draft ≈ perfect-info)* · ✗ **11.2 MCTS — BUILT & DROPPED (2026-07-19, Session D research gate)**: a determinized-UCT (`draft/mcts.py`) that searches on top of the greedy beats it **in-objective** (Δ portfolio CE +77, CI[+47,+107], 89 % over 9 DEV seat-seasons) but the gain **does not survive to realized OOS points** (Δ +32, CI[−90,+145]∋0, 56 %) at 8.5 s/pick → the greedy already banks the realizable value; near-perfect-info thesis measured. Kept in-repo like Phase 7 (`steps/phase11_2_mcts.py`, `analysis/phase11_mcts.json`) · ☐ auctions (later, done in 15.4) · ◔ **self-play RL (roadmap — a fortiori: a heavier bet on the objective whose OOS edge just failed to resolve)**
**Phase 12 — NLP/news** *(⟳ stage 7; LLM on the edges only)* ✅ **COMPLETE** *(2026-07-13, Session C — a
qualified KEEP: the injury signal pays, the depth-chart signal doesn't)* — ☑ **12.1 sources** *(`news/sources.py`:
the PIT, deduped news stream — 18k injury_status + 16k depth_change events 2016–22, native-gsis, + forward-only
RSS headlines; PIT-guarded)* · ☑ **12.2 extract** *(`news/extract.py`: deterministic offline **rules** extractor
(the default, runs in tests) + a **gated `ClaudeClient`** LLM seam (Haiku 4.5, behind ANTHROPIC_API_KEY — never
in the core) + the deterministic `structured_injury_signal` — the validated path; the guardrail literalized:
the LLM only extracts, the core prices)* · ☑ **12.3 event-study** *(`news/event_study.py`: **injury exploitable
lag = +5.86 pts/start, sig** (Out +8.4 / Questionable +3.9, both CI-clear); **depth-chart change does NOT
separate** promo−demo −0.10 → **DROP** the depth signal, noisy nflverse ranks — the gate doing its job)* · ☑
**12.4 validate** *(`news/validate.py`: prices status→availability multiplier (Out≈0, Q≈0.56, DEV-calibrated),
fills 13.1's reserved `news` slot; the news-aware weekly forecast **beats the injury-blind 13.1 on the
designated subset +3.4→4.3 pts/player-week, 6/6 DEV, season-block CI [+3.4,+4.0]** (diluted leaguewide +0.5).
Injury = KEEP; depth = drop — unlike Phase 7/props, the gate says a qualified yes)*
**Phase 13 — In-season co-pilot** *(the tax-loss-harvesting analog; pipeline stage 6 — reordered after S6
2026-07-11)* — ☑ **13.1 re-project** *(2026-07-12 — scalar **Kalman** on each player's per-week level;
PIT; **reserved Phase-12 `news` slot**, no-op default; **beats static preseason OOS 6/6 DEV seasons,
+0.396 ppg/wk MAE gain CI[+0.32,+0.48]**; `inseason/reproject.py`)* · ☑ **13.2 start/sit** *(2026-07-12 —
**co-pilot done-bar PASS**: mean-max on 13.1's re-projected means beats set-and-forget on realized points
6/6 DEV, **+2.08 pts/lineup-week** CI[+1.56,+2.54]. **FINDING**: the win-prob **variance tilt** does NOT
beat mean-max even for big underdogs (0/6; single-swap barely moves team sd — cf. Phase-10.3 whole-team-only
leverage) → `optimal_lineup` default = `objective="mean"`, tilt kept opt-in `objective="win"` off by
default; `inseason/lineup.py`)* · ☑ **13.3 waivers/FAAB** *(2026-07-12 — `faab_bid` = marginal value +
budget option-value + first-price shading; **mixed-field** sim, **beats naive %-of-budget 5/6 DEV**, mean
+30.0 value/szn CI[+21.7,+38.8]; key finding: model **diminishing returns** (top-`n_useful` scoring) or
volume wins. **Pragmatic** — rigorous auction theory owed to Phase 15.4 / TECH-DEBT **T9**; `inseason/waivers.py`)*
· ☑ 13.4 streaming *(2026-07-12 — a **matchup-streaming** contextual bandit over the waiver pool:
`stream_pick` on `matchup_projection = own + (opp_allow − league_mean)`, empirical-Bayes shrunk, with a
switch-margin hysteresis; demonstrated on **DST** — **beats static-hold 6/6 DEV**, +1.46 pts/wk CI[+0.88,+2.09],
and beats random-streaming 5/6 so the matchup signal itself pays; `stream_pick` position-agnostic (QB/TE feed
13.1 means); `inseason/streaming.py`)* · ☑ 13.5 trades *(2026-07-12 — **market-making**: `find_trades` searches
every opponent's surplus for mutual 1-for-1/2-for-1 deals that arbitrage complementary positional surpluses,
ranked by the worse-off side's gain (`min(mine, theirs)`) with a sell-high/buy-low tilt; `lineup_value` +
`evaluate_trade` price a swap by each side's optimal-starting-lineup change (the diminishing-returns lesson).
Done-bar: proposed trades **raise both teams' simulated playoff prob** in the Phase-10 sim — **6/6 DEV** both
sides (maker +0.014→+0.021, partner +0.012→+0.021 win%; season-block CIs>0), vs a random-trade control that
lifts both ~never; `inseason/trades.py`)* — **Phase 13 / S7 COMPLETE ← Session B done**
**Phase 14 — App** *(⟳ 2026-07-09: **LAST** — built only after the full engine incl. Phases 12/15 and the lockbox eval; ships with every factor embedded)* ☐ 14.1 **Streamlit MVP hardening** (autopilot+co-pilot, constraint-object UI, league sync, cost+risk+softness readouts, sim views, in-season dashboard, news feed, format toggles) · ☐ 14.2 personalization tiers · ☐ 14.3 explain · ☐ 14.4 backend/Next.js/live-draft/widget *(the go-live tail)*
**Phase 15 — Multi-format** *(⟳ stage 8; + auction draft support)* ✅ **CORE COMPLETE** *(2026-07-13, Session C
— 15.2/15.3/15.4 built; 15.1 dynasty stays roadmap per user scope)* — ◔ **15.1 dynasty** *(deferred — user
scoped Session C to auction+best-ball+DFS)* · ☑ **15.2 best-ball** *(`formats/bestball.py`: **variance is GOOD
in best-ball** — the mirror of the 13.2 managed-lineup finding; a ceiling-aware drafter (rank `mean·(1+κ·wk_cov)`,
**weekly** CoV not season sd) beats mean-only **6/6 DEV, +37→+104 pts/season, CI [+55,+93]**; reuses the draft
sim + WeeklyModel + lineup_points_matrix)* · ☑ **15.3 DFS GPP** *(`formats/dfs.py`: salary-cap optimizer +
modeled ownership + leverage + prize-splitting field sim; **leverage beats chalk 6/6 DEV** (chalk is duplicated
→ splits its prize ~0; the contrarian keeps it) — **MECHANICS, not Brier-validated: no free DK/FD salary/
ownership feed** (the props gap), salaries synthesised + ownership modeled)* · ☑ **15.4 auction** *(`draft/
auction.py`: auction values + the exact `endgame_cap` $1-endgame continuation + winner's-curse `auction_bid` +
`nominate`; a budget-state bidder beats naive budget-splitting **6/6 DEV, +66→+128 lineup pts, CI [+78,+108]**;
**discharges TECH-DEBT T9** — `faab_bid` now consumes `endgame_cap`)*

**★ Personalization spine** *(the reframe's new MVP-critical track — cross-phase; spec in `docs/PERSONALIZATION.md`)*
✅ **S1** preference-spec layer (`DraftConfig` + Streamlit Autopilot/Co-pilot UI) · ✅ **S2** constrained greedy optimizer (max risk-adjusted-VBD/CE s.t. constraints/archetype, plan around ADP availability; **covariance-aware since 2026-07-09** — marginal portfolio CE per pick) · ✅ **S3** cost-of-personalization report (vs the value-optimal team, + per-constraint leave-one-out; headline = **portfolio CE** + risk profile + Phase-6 softness credit) — **+ realized-PAR validation** *(2026-07-08, re-run 2026-07-09 under the covariance-aware greedy: archetype sweep on 2017–22; projected cost tiny & realized cost noise-dominated; late_qb a real ~65 pt/szn gain, elite_te marginally so; projected↔realized Spearman ≈ 0 ⇒ projected cost is a draft-day aid, not a season forecast; availability Brier deferred — needs real pick logs)* · ✅ **S4** behavioral opponent model → availability forecasts *(2026-07-11 — fit + availability Brier both beat ADP+noise; the availability oracle promotes from opt-in to the S4 default)* · ✅ **S5** per-round risk dial (Phase-5 λ/CE, wired into S2) · ✅ **S6** adaptive archetypes *(2026-07-12 — a fade-melt wrapper on a static parent, keyed to how far a candidate has slid off ADP; **does no harm on an ADP board, banks team-value when the board breaks** — the realistic Phase-11 behavioral room: adaptive(zero_rb) +2.0, adaptive(hero_rb) +15.6; `draft/config.py` + `steps/spine_5_adaptive.py`)* · ✅ **S7** in-season weekly-edge harvester *(= Phase 13, **COMPLETE 2026-07-12**; 13.1 re-project + 13.2 start/sit, then Session B: **13.3 waivers + 13.4 streaming + 13.5 trades** all DONE — every done-bar PASS on DEV)*

**★ THE PIPELINE (locked 2026-07-09 — engine-complete-before-app; no time crunch).** Every underlying
function — **including the formerly-deferred Phases 12 & 15** — is built and validated before any app work;
Phase 14 comes last and ships with everything embedded. Done so far: Phases 0–6, 8; spine S1–S3+S5;
Phase-6→cost-report wiring (all ✅ above). Remaining, in order:
**Stage 0** ✅ **LIVE** *(2026-07-09)* — FFC **2026 snapshot series** banked from 2026-07-09 (1,028 rows,
full grid, 99.3 % gsis; `steps/stage0_adp_snapshot.py`, idempotent + self-healing; **standing weekly chore
in CLAUDE.md §2** until the season starts) + **Sleeper probe** done (identity solved: crosswalk
`sleeper_id→gsis` = 99.0 % of draftables; no public ADP endpoint; pick-by-pick shape needs a real league →
0.10) →
**1) Phase 10** ✅ **DONE** *(2026-07-09 — weekly grain folded in; done-when MET: calibrated championship
probs on DEV, title Brier 0.0878 < 0.090 with on-diagonal reliability)* →
**Stage H — housekeeping** ✅ **DONE** *(2026-07-10)* — ☑ **T1** committed the Phase-10 + Stage-0 work ·
☑ **T2** backed up the irreplaceable data off the WSL disk (`steps/backup_db.py`, checksum-verified;
6 × 2026 ADP snapshots + 2025 backfill + timestamped `.duckdb` at `/mnt/c/.../fantasy-quant-backup/`) ·
☑ **T7** scrape freshness/schema gates + raw-payload archival + props formally shelved.
*(`docs/TECH-DEBT.md`.)* →
**2) Phase 9 completion** ✅ **DONE** *(2026-07-10 — 9.1 scarcity half · 9.4 lookahead · 9.5 win-prob
objective; `make_playoffs` vs `championship_or_bust` now change the draft, consuming the calibrated
Phase-10 probs; folded in **T8a** `objective` made real + **T6** one shared Monte-Carlo draw cloud
before the sim feeds the draft. `steps/phase9_policy.py`, +7 tests.)* →
**3) step 0.10 Sleeper ingest ✅ DONE (2026-07-11)** — the pick-by-pick data pipe is built, verified on 3
real mock drafts, corpus-ready + league-aware (`docs/SLEEPER.md`; `steps/phase0_10_sleeper_ingest.py`).
**S4/Phase 11 (behavioral opponent model + availability Brier, T8b) ✅ DONE (2026-07-11)** — data blocker
cleared by the 0.10c corpus; the conditional-logit fit **beats ADP-only** (log-loss +0.113 CI[+0.101,
+0.124]) and the **availability Brier beats best-tuned ADP+noise** (0.158 vs 0.316, +0.159 CI[+0.083,
+0.264]) → the behavioral availability oracle promotes to the S4 default. 11.1/11.2/11.3 done; MCTS/CFR/
auction stay out (deprioritized/dropped/roadmap). →
**4) Phase 7 ✗ BUILT & DROPPED (2026-07-11)** opportunity-adjusted projection — all 4 substeps built +
validated OOS; keep-or-drop (as-written bar) = **DROP** (situation swap is a wash-to-worse than naive on
role-changers; consensus already prices moves). Rookie transport works but duplicates 4.3. →
**5) S6** adaptive archetypes ✅ **DONE (2026-07-12)** — the fade-melt wrapper does no harm on an ADP board
and banks team-value when the board breaks (adaptive(zero_rb) +2.0, adaptive(hero_rb) +15.6 in the
Phase-11 behavioral room). →
**6) Phase 13/S7** in-season co-pilot — **☑ 13.1 re-project + ☑ 13.2 start/sit DONE (2026-07-12, Session
A):** weekly Kalman re-projection beats static preseason 6/6 DEV (+0.396 ppg/wk); the co-pilot (mean-max on
re-projected means) beats set-and-forget +2.08 pts/lineup-week; **the win-prob variance tilt was tried and
does not pay at the lineup grain (kept opt-in, off by default — the Phase-7/props pattern)**; 13.1 reserved
the Phase-12 news slot. **☑ 13.3 waivers/FAAB DONE (2026-07-12, Session B):** `faab_bid` (marginal value +
budget option-value + first-price shading) beats naive %-of-budget 5/6 DEV in a mixed-field sim; the key
finding was that the sim needs **diminishing returns** (top-`n_useful` scoring) or it rewards volume; shipped
**pragmatic**, with rigorous auction theory owed to Phase 15.4 (TECH-DEBT **T9**). **☑ 13.4 streaming DONE
(2026-07-12, Session B):** a matchup-streaming contextual bandit (`stream_pick` on `own + opp-generosity`,
empirical-Bayes shrunk, switch-margin hysteresis) beats static-hold 6/6 DEV on DST (+1.46 pts/wk) and beats a
random-streaming control 5/6 (the switch cost + random control are the 13.3 anti-churn lesson applied). **☑
13.5 trades DONE (2026-07-12, Session B):** the market-maker `find_trades` searches every opponent's surplus
for mutual 1-for-1/2-for-1 deals that arbitrage complementary positional surpluses (`lineup_value` +
`evaluate_trade` price a swap by each side's optimal-starting-lineup change — the diminishing-returns lesson),
ranked by the *worse-off side's* gain with a sell-high/buy-low tilt; proposed trades **raise both teams'
simulated playoff prob 6/6 DEV** (maker +0.014→+0.021, partner +0.012→+0.021 win%) vs a random-trade control
that lifts both ~never — the key correction was ranking by `min(maker, partner)`, not the maker's own gain, so
the objective rewards *mutual* benefit. **Phase 13 / S7 COMPLETE — Session B done.** →
**7+8) Phase 12 + Phase 15 ✅ DONE (2026-07-13, Session C).** Phase 12 news/NLP = a **qualified KEEP** (injury
exploitable lag +5.86 pts/start sig → the news-aware weekly forecast beats injury-blind 13.1 +3.4→4.3 pts/pw
on the designated subset 6/6 DEV; depth-chart signal DROPPED, no separation; LLM edge-only via a gated
`ClaudeClient`, core stays deterministic). Phase 15 = 15.2 best-ball (variance-is-good, ceiling beats mean 6/6),
15.3 DFS GPP (leverage beats chalk 6/6 — **mechanics only**, no free salary/ownership feed), 15.4 auction
(budget-state bidder beats naive 6/6, **T9 discharged**). 15.1 dynasty stays roadmap. **← NOW: Session D =
optional MCTS/RL research gate + T5 pre-registration + LOCKBOX EVAL.** →
**7) Phase 12** news/NLP ✅ **DONE (2026-07-13, Session C)** — the gate said a **qualified yes**: the injury
signal is a real, significant KEEP (exploitable lag +5.86 pts/start → news-aware 13.1 forecast beats
injury-blind +3.4→4.3 pts/pw on the designated subset 6/6 DEV), the depth-chart signal a DROP (no
separation). LLM edge-only via a gated `ClaudeClient`; the deterministic core prices the signal (the
guardrail, literalized). → **8) Phase 15** multi-format + auction ✅ **DONE (2026-07-13, Session C)** — 15.2
best-ball (variance-is-good, 6/6), 15.3 DFS GPP (leverage>chalk 6/6, mechanics only — no free salary/
ownership feed), 15.4 auction (budget-state bidder>naive 6/6, **T9 discharged**). 15.1 dynasty stays roadmap
(user-scoped). →
**9) optional research gate ✅ DONE (2026-07-19, Session D)** — **MCTS BUILT & DROPPED** (user chose to
build the benchmark, not defer): a determinized-UCT beats the greedy in-objective (Δ CE +77 sig) but not
on realized OOS points (Δ +32, CI∋0) at 8.5 s/pick → greedy stays the policy; self-play RL stays roadmap;
CFR stays dropped. The gate is spent — **no MCTS/RL in the frozen stack.** →
**➤ PRE-LOCKBOX HARDENING (`docs/TECH-DEBT.md`):** ☑ **T3** coverage fix (→ uncond 44 %→77 %) · ☑ **T4** sim
level bias (−137→−113) · ☑ **T5** *(2026-07-19, Session D)* — the frozen stack + metrics + the ≈35–40
DEV-decision count pre-registered in `PLAN.md` and committed (`7bd6e10`) **before** the eval; 2025 dress
rehearsal recorded. →
**10) LOCKBOX EVAL — spent EXACTLY ONCE ✅ DONE (2026-07-19, Session D)** — `steps/lockbox_eval.py`,
`analysis/lockbox_eval.json`, `findings.md` §"LOCKBOX EVALUATION"; reported **as-is**. **Result: the
reframe's honest-value claims GENERALISE OOS** — title Brier **0.088 < 0.09** (championship calibration
holds, ≈ DEV), conditional distribution coverage **80.1 %**, projection rank Spearman **0.54**, cheap
noise-dominated personalization cost; **known level-optimism / unconditional-attrition limitation persists**
(projection bias 0.62, uncond coverage 72 %, a *marginal* playoff Brier 0.240). All hard gates PASS. **The
stack is frozen — nothing modeling-side changes on the basis of this result.** →
**11) ← NOW: Phase 14** the app with every factor embedded (Session E = 14.1 Streamlit MVP; F+ = the 14.4
go-live tail). *(Built last by design — it surfaces every factor the now-final engine produces.)*
Net change from the prior sequencing (2026-07-11 review): only S6's position moved (from between Phase
13/12 to immediately next). Everything else — Phase 13 before 12, 12 before 15, the optional gate last
among builds, T5 → lockbox → app as a strict tail — checks out on actual dependencies, not just write order.

**★ SESSION SIZING GUIDE (2026-07-11 — a planning aid, not a hard rule; re-estimate if actual scope
diverges once building starts).** Sized from `git diff --stat` on past commits, which cluster into two
bands: **full-phase sessions** ≈ 700–2,000 lines / 10–21 files / 5–15 new tests (Phase 9: 728L·13f·+7t;
Phase 8+6-wiring: 1,926L·18f; Phase 5: 1,423L·19f; MVP spine S1–S3: 1,496L·17f; **Phase 11+7 (2 phases
bundled): 2,000L·21f·+15t**; T3+T4: 547L·11f·+6t) and **single-file/single-concept deliverables** ≈
60–150 lines (11.3 `personalities.py`: 109L; 5.5 `utility.py`: 58L — S6 is this size, not full-phase size).
Phase 13/S7 is greenfield (no `inseason/` package exists yet) and its 5 substeps aren't uniform — 13.3
(FAAB bandit + auction theory) and 13.5 (trade market-making) are new-domain and heavy (~250–400L each),
13.1 (state-space re-projection) is medium (~150–300L), 13.2/13.4 are light wiring onto existing infra
(~100–200L each) — **estimated ~1,400–2,100L all-in, i.e. full-phase-sized on its own**, unlike every other
remaining item. Proposed bundling to land future sessions in the ~1,500–2,200-line target band, mirroring
how 11+7 combined a spine-completion phase with a 4-substep exploratory phase:
- **Session A:** S6 + Phase 13.1–13.2 (re-project + start/sit). S6 alone (~150L) is sub-session-sized;
  13.1/13.2 lean on existing Phase-5/9.4/10.x infra → **~400–600L combined**, likely light enough to pull
  13.3 in too if there's room.
- **Session B:** Phase 13.3–13.5 (waivers/FAAB, streaming, trades) — the two heavy new-domain substeps
  plus streaming → **~600–1,000L**, a full session on its own.
- **Session C:** Phase 12 + Phase 15 (news/NLP + multi-format/auction) — two medium 4-substep phases
  (~700–1,200L each) bundled the same way 11+7 was → **~1,400–2,300L**.
- **Session D:** optional MCTS/RL gate + T5 pre-registration + LOCKBOX EVAL — three small, sequential,
  gated items → **~350–850L**, a closeout bundle like the T1/T2/T7 housekeeping session.
- **Session E:** Phase 14.1 (Streamlit MVP hardening) **alone** — do not bundle anything onto Phase 14;
  it's the largest remaining phase by scope.
- **Session F+:** Phase 14's go-live tail (14.2–14.7: personalization tiers, explain, FastAPI backend,
  Next.js frontend, live-draft sync, widget, mock-draft sim) — expect **multiple sessions**, each
  comparable to or larger than any single phase built so far.

Working rules throughout: DEV-only, STOP gates between sub-steps, findings/glossary/PLAN/ROADMAP per step.
**Known-problem register (the exact fix per item): `docs/TECH-DEBT.md` (T1–T8).**

**Open decisions (reframe §10 — tracked in `PLAN.md`):** real completed-draft data (Sleeper) for the
behavioral model; a **consensus-projections source** (FantasyPros aggregate — free/PIT?); the benchmark
set. **Resolved:** lockbox = **2023 + 2024** (dev on 2014–2022; `config.DEV_SEASONS`). 2025 excluded (no
weekly rollup / ADP board yet — see `findings.md`).

**Phase-2 finding (still true — now a feature, not a failure):** consensus ADP is a strong baseline the
naive model can't *significantly* beat — so we **stop trying**, lean on consensus for value, and compete on
personalization + honest cost transparency instead.
