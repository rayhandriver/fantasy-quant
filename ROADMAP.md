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
**Phase 14 — App** *(⟳ 2026-07-09: **LAST** — built only after the full engine incl. Phases 12/15 and the lockbox eval; ships with every factor embedded)* ◐ 14.1 **Streamlit MVP** *(**K1 ☑ 2026-07-30** — four tabs on the live board: Settings · Board+`why` · Draft room (any k of n) · Cost)* · ☐ 14.2 personalization tiers · ☐ 14.3 explain · ☐ 14.4 backend/Next.js/live-draft/widget *(the go-live tail)*
— **surfacing + UX substeps:** ☑ 14.E tier-cliff · ☑ 14.F roster risk · ☑ 14.G uncertainty board · ☐ 14.H playoff SOS *(specced for the 14.3 frontend, not the Streamlit MVP)* · ☑ 14.I draft grade · ☑ 14.J multi-seat control · **☑ 14.K multipage shell** · **☑ 14.L room grid (every team, by pick or by slot)** · **☑ 14.M pick clock** · **☑ 14.N post-draft analysis page** · **☑ 14.O stat dictionary/tooltips** *(K–O added 2026-07-30 s4 from the user's first real use of the app; E/F/G/I/N built 2026-07-31 in Session K2)*
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

**Phase 16 — Situation-Change Beta Lab** *(new 2026-07-19; non-core research track, scoped not yet built —
sequenced after the lockbox eval, before Phase 14 per user decision. **Two tracks: value-side 16.1–16.6 +
availability-side 16.7–16.12, added 2026-07-23.**)*
**Value-side (does situation change make a player out-*earn* ADP?):** ☐ **16.1** team-change +
new-starting-QB ADP-alpha extension (Phase 6.1/6.2 panel+regression) · ☐ **16.2** competition-change signal,
**dual-sourced** (roster-turnover-derived vs depth-chart-derived, compared — the latter mirrors Phase
12.3's already-null signal) · ☑ **16.3** playcaller/coaching history table (2026 half signed off, merged
onto the frozen schema) · ☑ **16.3b** historical playcaller regimes (204-row table + a 5-row lineage
fallback, pbp head-coach audit, **★ user review gate open**) · ☐ **16.4** scheme fingerprint + transport (descriptive-only, no
statistical gate — thin sample; **17-team transport set, all 17 covered: 12 own + 5 lineage**) · ☑ **16.5** 2026 live
situation-change event board (**rebuilt as DERIVED 2026-07-25 — 138 events over 30 teams**, dual-sourced;
the hand-built 9-row version missed 16 of 23 team changes; `mechanism` unresearched on 111) · ☐ **16.6** Beta Lab
Streamlit tab (`app/streamlit_app.py`, read-only, no optimizer/VBD/cost-report coupling).
**Availability-side (does narrative/situation make a player *drafted earlier* than ADP? — folds in the
"McConkey falls in mocks then gets sniped" fix; extends the opponent/availability model, which is already
OUTSIDE the value lockbox):** ☐ **16.7** draft-slot-drift panel & target (`drift = actual_slot − ADP` on the
Sleeper human corpus 2017–20; `adp/drift_panel.py`) · ☐ **16.8** drift feature model (VBD-ADP gap + source
divergence + situation flags; walk-forward, own held-out drift MAE/Spearman; `adp/drift_model.py`) · ☐
**16.9** correlated per-draft narrative shock (one shared hype draw per sim draft → hyped players go early
consistently; reproduces realized draft-slot dispersion; `draft/simulator.py`+`opponent_model.py`) · ☐
**16.10** curated hype-board override (`reference/hype_board.csv`, web-research-drafted + user-reviewed;
`adp/hype_board.py`) · ☐ **16.11** live 2026 momentum/ADP-velocity (`adp/momentum.py`; **forward-only — NOT
backtestable**, validated live on 2026) · ☐ **16.12** consumption = realism (mocks) + opt-in advice (9.4
lookahead) + app readout (`P(available)` + reach-risk in `docs/PLAYER-VIEW.md`). **Validation bar (user
2026-07-23): walk-forward + own held-out metric.**
**Opponent-personality set (16.13–16.15; added 2026-07-23 — heterogeneous mock-draft opponents; extends the
existing `draft/personalities.py`, Phase 11.3):** ☑ **16.13** opponent-board enrichment (attach frozen
read-only Phase-5 dist + `value_board` fields to the sim board; `draft/simulator.py`) · ☑ **16.14** the 5
headline personalities — **Autopilot** (deterministic ADP autopick), **Balanced**, **Upside Chaser** (boom/
`upside`), **Safe/Floor** (`floor`/`durability`), **Homer/Narrative-Chaser** (fandom + hype board;
`draft/personalities.py`) — note the shipped weights are the **level-residualized** columns, not the raw
quantiles · ☑ **16.15** mock-room composition + hype-shock coupling + app selector (all ☑ 2026-07-27; see
the Session-H entry below for the two nulls and the ceiling-scope fix). Decisions (user 2026-07-23): BPA =
**ADP autopilot only** · enrich with **real frozen fields** · validation = **face-validity + unit-tested
mechanics** (no Brier gate). · ☐ **16.17** **the seat map — multi-seat human control** (added 2026-07-30,
user request): the user must be able to run **as many seats as they like** (e.g. 6 personalities + 4 teams
drafted by hand). 16.15 shipped the opponent half; the human half is stuck at k=1 because "which seat is
the human" is a single int (`DraftState.your_team`) and the `team → seat` map is positional arithmetic
written out three times. Fix = one `SeatMap` (each of `n_teams` entries is `HUMAN` or a `Personality`) +
`DraftState.human_teams` + per-seat pick functions + a multi-seat CLI. **Hard bar = bit-identity**
(k=1 reproduces the shipped interactive room, k=0 reproduces `full_room_pick_fn`, the 07-29 bar sheet
reproduces to the digit). Touches no fitted parameter and no frozen contract. UI half = **14.J**.
**Live reactivity + data (added 2026-07-23):** ☐ **0.11** ECR + Underdog ADP ingest (true expert-rank + sharp
best-ball board; feeds 16.8; `data/sources/`) · ☐ **16.16** live-draft run-detection (mid-draft positional-run
reactive availability; face-validity replay; `draft/opponent_model.py` → surfaced in 14.4). Scoping questions
answered 2026-07-19 (value) + 2026-07-23 (availability + personalities + formats) (see `PLAN.md`); **not yet
coded — awaiting go-ahead.**

**Phase 17 — League-Format Fidelity & Custom Settings** *(new 2026-07-23; broad all-users **correctness** track
— make the engine give correct advice for ANY league, not just 10-team full-PPR 1-QB; NOT a modeling change to
the frozen stack — a config generalization, non-default formats labeled not-lockbox-validated)* ☐ **17.1**
roster + lineup generalization (superflex/multi-flex/OP/no-K; remove the `season.py` single-FLEX
`NotImplementedError`; format-aware VBD replacement — superflex lifts QBs; `draft/simulator.py`,
`simulation/season.py`) · ☐ **17.2** custom scoring generalization (`RuleSet` arbitrary per-stat values +
presets; `backtest/scoring.py`) · ☐ **17.3** generic **platform-agnostic** league-settings input contract
(`LeagueSettings` builder — presets or full custom; the Phase-14 form binds to it; `draft/config.py`) · ☐
**17.4** keeper support (remove kept players + re-inflate effective ADP; `draft/simulator.py`, `adp/`).
**17.1–17.4 ☑ COMPLETE 2026-07-30 (Session I).** Decisions (user 2026-07-23): platform-agnostic manual form
(not Sleeper auto-import) · IDP deferred (data gap) · optional platform auto-import is a secondary future
convenience.
**★ LEAGUE IMPORT ADDED 2026-07-30 s4 (user request — "import personal leagues straight from
ESPN/Yahoo/Sleeper for max efficiency"), which narrowly reverses the 07-23 "not auto-import" decision:**
the manual form stays and stays primary; import is an **alternative constructor for `LeagueSettings`**
(`import_league(platform, ident, creds)`), so nothing downstream changes and every imported field lands in
the 17.3 form for the user to **confirm** before a board is built from it. ☐ **17.5** the contract +
**Sleeper** *(free, keyless, client already built, offline fixture — its value is the contract, not the
platform)* · ☐ **17.6** **ESPN** *(undocumented JSON API; public leagues keyless, private ones need pasted
`espn_s2`+`SWID` cookies — ships labelled fragile, caches last-good, never logs the cookies; **the one the
user actually needs**)* · ☐ **17.7** **Yahoo — deferred to 14.4**: OAuth2 needs a registered app and a
hosted redirect the Streamlit MVP does not have. Spec: `docs/BUILD_PLAN.md` §"Phase 17 — league import";
session slot = **Session K3**.

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
**11) ← NOW: the remaining engine work, then the app last.** Scope **expanded 2026-07-23** — the post-lockbox
backlog is now: **Phase 16** (three tracks: value-side 16.1–16.6, availability-side 16.7–16.12, opponent
personalities 16.13–16.15, + 0.11 data + 16.16 live reactivity), **Phase 17** (League-Format Fidelity —
superflex/custom-settings/keeper correctness for any league), and **Phase 14** (the app + all decision-support
surfacing E–I, built strictly last). Sequencing decisions (user 2026-07-23): **dependency-optimal order**, **app
strictly last**, **same ~1.5–2.2k-line one-concept sessions**. The one cross-track dependency that pins the
lead: **16.8's drift model reuses 16.1/16.2's situation-change features**, and **0.11 (ECR/Underdog) feeds
16.8** — so value-side → data+drift → apply-drift → personalities → formats → app. **Full session breakdown in
the ★ SESSION PLAN below.** All of Phase 16/17 ships walled-off from the frozen optimizer/VBD/cost-report stack;
Phase 17 is a config generalization (non-default formats labeled not-lockbox-validated), not a modeling change.
Scoped in `PLAN.md` (2026-07-19 + the three 2026-07-23 entries); **awaiting go-ahead to build.**
Net change from the prior sequencing: Phase 16 grew from one track to three + data/live; Phase 17 (formats) is
new and slots after Phase 16, before the app; all UI/surfacing consolidated into Phase 14 (app strictly last).
Everything else checks out on actual dependencies, not just write order.

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
- **Sessions A–D ☑ DONE** (S6+13.1–13.2 · 13.3–13.5 · Phase 12+15 · MCTS gate+T5+LOCKBOX). *(kept for the
  record; sizing held.)*

**(2026-07-26: Session F.6 ☑ — the re-derivation sweep. 11.1/11.2/S6 re-fit on the *eligible*
redraft corpus after the behavioral path was found to carry F.5's contamination bug; 16.8 re-asked
and the null HELD (headline +9.25 %, ablation +0.01 %). **Session G ☑ COMPLETE 2026-07-26** — 16.9 + 16.11 + 16.10 + 16.12 + 16.16; the availability track ends with **four** honest nulls, and everything it ships is opt-in and default OFF. **Session H ☑ COMPLETE 2026-07-27** — 16.13 + 16.14 + 16.15 + T17; the personality set ships as a *realism* feature (face validity + mechanics, no Brier gate) and the hype coupling is Phase 16's **fifth** null. **Session H.5 ☑ COMPLETE 2026-07-30** — the mock-drafter value seam (T27–T30): T27/T29 shipped, T28 closed as a labelling fix when its pre-registered bar failed, T30 argued and deliberately not changed; B2's failure opened **T31**. **T31 ☑ COMPLETE 2026-07-30** (its own session, per the user's ordering decision) — the live-board level correction. **The register's filed cause was wrong, the third in a row after T13/T24:** there is no live-vs-historical branch in the level fit (`train_seasons` is 2014–2022 for a **2024** board *and* a 2026 one, so the models are identical); the defect was **board depth** — a linear `QuantReg` extrapolated far below its own support, on a live consensus board that runs hundreds of players deeper than any proxy board. `quantile.consensus_level_cap`, gated on `value_board.source`. **All six pre-registered bars PASS** (negative-haircut share 38.75 % → **0.00 %**; drafted-range rho RB −0.288 → **−0.666**; full-board QB +0.474 → **−0.980**; 2022/23/24/**25 bit-identical**, so the spent lockbox stands and the **calibration holdout was never read**). Top-24 ADP untouched; the effect ramps to 96.5 % of undrafted rows. **Session I ☑ COMPLETE 2026-07-30** — Phase 17 League-Format Fidelity 17.1–17.4, all five gates PASS, **658 tests (+41), ruff clean**. One shared fill rule (`RosterSlots.flex_groups()`) replaced three independently-derived copies; multi-flex/superflex solver checked against an **exhaustive brute force** (worst error 0.0), not against the repo's other greedy. **Headline: the superflex replacement level was quietly wrong** — the old proportional rule gave QB 1/6 of the slot; a superflex admits only QB beyond the base flex, so **QB10 → QB20**, and on the live 2026 board the best QB moves from overall rank **15 → 3**. Bracket generalized to 4/6/8 with derived byes (a 12-team/8-playoff league was previously unconstructible); odd `n_teams` refused with a reason; keepers re-inflate ADP by **removing supply**, and the forfeited pick is the price. **The default 10-team full-PPR path did not move** (G3), and `LeagueSettings.lockbox_validated()` is the programmatic "this claim does not transfer" for everything else. **Session I.5 ☑ COMPLETE 2026-07-30** — 16.17 the seat map: one `SeatMap` replaced **four** copies of the one-human `team → seat` arithmetic, `DraftState.human_teams` + per-seat pick functions make **any k of n** seats human-driven, and `steps/mock_draft.py --seats 3,7` drives them. **668 tests (+10), ruff clean; the done-bar was bit-identity and it held everywhere** — 1,014 exhaustive mapping triples, 54 draft pairs against the deleted arithmetic re-implemented verbatim, and the room bar sheet bit-identical to a **pre-16.17 control run on today's board** (the committed 07-29 sheet is not a clean reference: the Stage-0 chore + T31's `ENRICH_VERSION` bump refreshed the live board, so its `readout_2026` block moved for reasons unrelated to this substep). Nothing refits; the honesty rules ship with the readouts (*k human teams in one draft are ONE observation*; *the T15 bars describe a fully-simulated room*). Opened **T33**. **← NOW: Session J (optional dynasty) → K (Phase 14 app, strictly last).**)**

**★ SESSION PLAN (re-ordered 2026-07-23 — the full remaining backlog, dependency-optimal, app strictly last,
same ~1.5–2.2k-line one-concept discipline).** Covers everything not done: Phase 16 (3 tracks) + 0.11 + 16.16,
Phase 17, Phase 14, T10, and the deferred 15.1 dynasty. The lead is pinned by real dependencies
(16.1/16.2 features → 16.8; 0.11 → 16.8; 16.13 → 16.14; availability → 16.16). Each session: STOP-gates between
substeps, Stage-0 FFC snapshot chore first if stale, then a hard stop + report + questions.
- **Session E — Phase 16 value-side (16.1–16.5) + T10 warm-up.** ◐ **IN PROGRESS (docs current as of
  2026-07-25, session 3):** **T10 ☑** (adaptive priced per-parent, `spine_4_validate` green), **16.1 ☑**
  (team/QB change — honest NULL; PIT team-of-record from `weekly`, the ADP-board `team` col leaks),
  **16.2 ☑** (competition dual-sourced — both sources wash out, opposite signs, echoes Phase 12.3),
  **16.3 ☑ DONE** (2026 half signed off at `confidence=high` after 3 user correction rounds; **merged onto
  the frozen schema 2026-07-25**, `in_house` backfilled, stale 2026 rows replaced; signed-off original
  retained verbatim), **16.3b ☑ BUILT** (`situation/coaches.py` + `steps/phase16_3b_coach_history.py`;
  **204 rows** = 172 historical 2014–2025 + 32 for 2026; head-coach column auto-audited against `pbp` —
  **0 MISMATCH of 172**; move-graph 13 findings / **0 HARD**; coverage **9/32 → 27/32** play-callers with a
  median 4 prior seasons; **transport set corrected 13 → 17** = 13 external + 4 internal promotions
  (DEN/MIA/PHI/WAS)) **+ the LINEAGE FALLBACK** (user direction 2026-07-25 — a first-time play-caller falls
  back to the regime they came up under, `reference/coach_lineage.csv`; Payton + Kingsbury added as mentor
  regimes) → **all 17 transport teams covered: 12 own · 5 lineage · 0 none**. **16.5 ☑ REBUILT AS DERIVED
  2026-07-25** — the user asked why the board had only 9 rows and was right: hand-research had missed 16 of
  the 23 team changes among draftable players (incl. A.J. Brown PHI→NE at ADP 13.6) and had no row for the
  two highest-ADP players in the league. New `situation/events.py` generates it from 2026 `adp_snapshots` ×
  `consensus_projections` (0 team disagreements) against 2025 `weekly` → **138 events over 30 teams**;
  research narrowed to `mechanism`/`notes` and merged in. **16.4 still to build. 16.6 tab → deferred to the
  Phase-14 app block.** ruff clean, DEV-only, lockbox untouched, walled off from the frozen cost
  report. **Value-side reads as an honest null → Phase 16's edge is the availability side (16.7–16.12).**
  326 → 331 → 344 → **359 tests**.
  **★ REVIEW GATE CLOSED 2026-07-25** — the user fact-checked the historical rows and lifted all 26
  non-`high` ones; `reference/coaches.csv` is **204 rows, all `confidence=high`**, signed off end to end.
  The edits were confidence-only (no `head_coach`/OC/`play_caller`/`hc_calls_plays` value moved), so
  16.3b's machine audits stand.
  **16.4 ☑ DONE 2026-07-25 (descriptive only)** — `situation/fingerprint.py` + `steps/phase16_4_fingerprint.py`.
  14 metrics z-scored within season, EB-shrunk by regime length; **41 play-callers / 64 spells / 169
  regime-seasons**; all **17** transport teams resolve (12 own · 5 lineage · 0 silent), BAL/PHI/SEA report
  **both** priors. **★ Headline is deflationary: only 20.9 % of implied role movement is the incoming
  coach**, 79.1 % is regression to the league mean — so every player row splits into `reversion_pp` +
  `scheme_pp`. **★ Best by-product: measured trait portability** — `rz_pass_rate`/`team_adot`/`plays_pg`/
  `carry_hhi` travel with a coach (k≈1.7–2.0); **`wr1_tgt_share` does not (k=17.9)**, i.e. the alpha WR's
  target share is a roster fact. Guard added (`assert_regime_coverage`) after an `LA`-vs-`LAR` join failure
  silently deleted Sean McVay's whole Rams tenure on the first run.
  **★ SESSION E COMPLETE.** (data 0.11 + drift 16.7–16.8 = Session F, now also complete — see below).
  16.6 tab stays deferred to the Phase-14 app block. (Session G — apply the drift, 16.9–16.12 + 16.16
  — is now also **☑ COMPLETE 2026-07-26**; see its entry below.)
- **Session F — data 0.11 + availability drift 16.7–16.8. ☑ COMPLETE 2026-07-25.** 382 tests (+23), ruff
  clean; uncommitted for user review. **The availability track returns an honest null too — 16.8's verdict
  is DOES NOT PREDICT** (headline skill +1.05 % CI[−1.48,+4.96] vs a pre-set 2 % bar; **ablation without
  the sibling-derived feature: −1.75 %, worse than "everyone drafts at ADP"**).
  - **0.11 ◐** — **ECR ☑** (`data/sources/ecr.py`; 17,264 rows, 2017–2026 × 3 scorings, 99.2 % gsis, incl.
    **2025 where FFC has no board**), **Underdog deferred** (no keyless endpoint). **★ The archive is real
    but kickoff-dated** — every board stamped 9/06–9/11, after 37 of 38 corpus drafts — so BUILD_PLAN's
    "does true-ECR beat the VBD proxy" is unanswerable; `ecr_asof` returns **empty** for a draft-day as-of.
    ECR is a live-season/season-outcome input, not a draft-day feature. 2023 PPR flagged `is_preseason=False`
    (`as_of` 2024-02-12, re-touched post-Super-Bowl).
  - **16.7 ☑** (`adp/drift_panel.py`) — **34 drafts / 4,495 picks / 436 players / 2017–2024**. Three forced
    deviations from spec: a **`PRESEASON_WINDOW`** the plan lacked (the corpus runs **Feb–Nov**; biggest
    filter, 117→42 drafts), **rounds units** so any league size joins the 10/12-team board, and a **flipped
    sign** (`drift > 0` = drafted EARLIER) plus **`drift_centered`** as the headline target. TE +0.46 rounds
    (reached), QB −0.20 (slides).
  - **16.8 ☑** (`adp/drift_model.py`) — **★ the ablation is the finding**: a leave-one-out feature still
    shares season, room and drafters with its target, so leave-one-out is **not sufficient** — report the
    fit without it. **Situation flags null on the availability side too**, mirroring 16.1/16.2. What
    survives, and what 16.9 must shape its shock with (descriptive, not a per-player forecast):
    **`rookie` +0.73 rounds**, **`adp_stdev` +0.35/SD**, `vbd_gap` +0.18/SD, `pos_WR` +0.47.
  - **→ Consequence for Session G:** 16.9 gets **no quantitative drift prediction to amplify** — its
    dispersion (variance) done-bar needs no mean signal, and **16.10's curated hype board is now the
    primary narrative channel**, its "curated, not backtested" label load-bearing rather than a caveat.
- **Session F.5 — corpus expansion. ☑ COMPLETE 2026-07-25.** 395 tests (+13), ruff clean, **all data-health
  gates PASS for the first time** (T12 closed). Inserted ahead of G because G's 16.9 done-bar is a
  *dispersion* target, which needs **sample, not signal** — fitting it on 34 drafts and re-fitting after a
  crawl would be doing the session twice. Fixed three mechanical crawler defects (frontier never reseeded
  from `sleeper_manager_profiles`; participant expansion dead-ended on re-runs; budget counted *discovered*
  not *ingested* ids), added resumable crawl state + a run-scoped league cache (**5.4× discovery speedup**)
  + token-bucket pacing. Corpus **149 → 7,699 human drafts / 17k → 1.21M picks / 289 → 24,696 managers** in
  70 min; **16.7 panel 34 → 1,144 drafts** (33.6×), `drift_centered_sd` 1.5375 → **1.8161**.
  - **★★ Format contamination found and fixed:** `_refresh_board` hardcoded `scoring="ppr"`, making the
    `sleeper_human` board **82 % non-redraft** at scale (2,547 dynasty_2qb / 952 2qb / 861 dynasty / 610 IDP
    vs 1,312 actual PPR redraft). Now redraft-only, split per (season, scoring). Surfaced as an
    unrelated-looking join-rate gate failure (3.52 % → 0.61 % unmatched). *A hardcoded label is a bug that
    scales with your corpus.*
  - **Banked for Phase 17:** 5,693 complete human non-redraft drafts already in the store.
  - **Deliberately took no modelling decisions** — 16.8, Phase 11, personalities, S6, the dress rehearsal
    and the ECR fallback all deferred to F.6 so they could be judged against measured corpus size.
- **Session F.6 — the re-derivation sweep.** In dependency order: **11.2 availability Brier (T8b)** first
  (thinnest result in the repo at `n_drafts: 21`; now 12,578 managers with ≥2 drafts, 1,330 with 10+) →
  **11.1 opponent model** (7,900 → ~200k choice groups; *decide explicitly* re-fit vs extend with
  per-manager random effects) → **16.8** against a ~5.8× tighter CI with the **>2 % bar unmoved and the
  `source_divergence` ablation mandatory** → **11.3 personalities** + **S6 adaptive** (both ride the fitted
  β). Open decisions: ECR board fallback (recovers 2025's 278 eligible drafts), and whether to re-run the
  2025 dress rehearsal (a further read of the calibration holdout).
- **Session G — apply the drift 16.9–16.12 + 16.16.** ☑ **COMPLETE (2026-07-26).** **T14 ☑** (the
  warm-up: 11.2 396 s → 12.7 s, bit-identical — and its **diagnosis was wrong**, the bootstrap was 0.79 s
  while 99.3 % sat in pandas inside `simulate_survival`). **16.9 ☑ BUILT — an honest NULL, and the third
  in Phase 16.** The premise inverted under measurement: the simulator **over**-dispersed draft slots by
  59 %, because 11.1's top-40-fit β was being applied to the whole board in both `make_opponent_pick_fn`
  and `simulate_survival` — a **choice-set contract violation**, now fixed and shared via `CHOICE_TOP_K`.
  That fix alone met the level done-bar (**59.5 % → 8.8 %** error) and *improved* the availability Brier
  (**+0.0644 → +0.0708**). The shock itself moves nothing: realized depth slope +0.679, banded +0.077,
  +shock +0.057, and a 50× size sweep stays inside the metric's own noise → **default OFF, kept as the
  expression channel for 16.10/16.15**. Residual shape miss → **T15**.
  **Part 2/2 (same day): 16.11 + 16.10 + 16.12 + 16.16 — 466 tests (was 425), ruff clean, every
  done-bar gate PASS.** Built in **dependency order**: 16.11 before 16.10, since derived-first
  nomination makes momentum an input to the hype board.
  - **16.11 momentum ☑** (`adp/momentum.py`) — 192 players over 3 FFC snapshots / 15 days; centered on
    the board's own drift, EB-shrunk (44 % of the raw spread survives, 2-snapshot players → exactly 0);
    **forward-only and structurally unbacktestable**, labelled so in its own return value.
  - **16.10 hype board ☑** — 24 rows / 20 directional claims, written `reviewed=false`; the **review
    gate is structural** (`load_hype_board` drops unreviewed rows, independent of the on/off switch).
    Method = **derived rows, curated claims**; 16/24 rows machine-nominated. **Elasticity ≈ 0.44
    realized picks per claimed pick** — a nudge, not a repricing. Four measurement defects found and
    fixed en route (partial coefficients used without their controls; a `log(adp)` curvature leak;
    momentum in incommensurate units; a signed composite ranked one-sided) → **T16** (a deep claim
    cannot express in a 15-round league).
  - **16.12 consumption ☑** (`draft/drift.py`) — realism + opt-in advice + **engine-side** readout (UI
    stays in Phase 14 per "app strictly last"). **Isolation proven:** `DriftConfig()` is a no-op and a
    `RiskModel` without `hype` is **bit-identical** to the frozen path — asserted both ways so the
    guarantee cannot pass vacuously.
  - **16.16 run detection ☑ = Phase 16's FOURTH NULL.** The detector works (discrimination monotone in
    the threshold, **+0.109** at 0.50 over 7,957 replayed windows) but *reacting* to it degrades the
    availability Brier monotonically (0.2121 → 0.2186). **Ships default OFF**; kept as a live-draft
    alert for 14.4.
- **Session H ☑ COMPLETE 2026-07-27 — opponent personalities 16.13–16.15.** **16.13 ☑ · 16.14 ☑
  (2026-07-26) · 16.15 ☑ · T17 ☑ (2026-07-27).** 524 tests, ruff clean, all done-bars PASS.
  - **16.13 board enrichment ☑** (`draft/enrichment.py`, `draft/simulator.py`). Read-only join off
    `cached_distribution` + `value_board` — **not** the `player_distributions` table, which holds 2025
    only. Live-2026 coverage **81.8 % dist / 85.8 % value**; the entire skill-player gap is one WR.
    Also revived `homer` and `rookie_hawk`, **literal no-ops since Phase 11.3** (nothing ever passed
    `fav`; `_prepare_board` dropped `rookie`).
  - **16.14 the five headliners ☑** (`draft/personalities.py`) — `autopilot · balanced · upside_chaser
    · safe_floor · homer`, via `signal_weights` + a `max_reach_picks` reach ceiling + `hype_gain`.
    **All 7 live-board face-validity checks PASS**; `autopilot` reproduces `pick_by_adp(noise=0)`
    exactly. **496 tests** (was 466), ruff clean.
  - **★★ The spec as written builds two personalities that AGREE.** Within position
    `corr(q90, mean) = +0.98…+0.999` in every season — the raw quantiles are a **level** signal, so
    an upside chaser weighting `q90` and a safe drafter weighting `q10` both just draft good players.
    Shipped build weights the level-residualized `upside`/`floor` (`corr = −0.86`). *The 16.10 lesson
    recurring on a signal rather than a coefficient.*
  - **New tech debt T17** (🟠): `availability_projection` returns 0 rows for an unplayed season, so
    the live Phase-5 `mean` is **37 %** of the consensus projection it is built from. Blocker for
    Phase 14 surfacing, not for H or I.
  - **16.15 the mock room ☑** (`draft/personalities.py`: `DEFAULT_ROOM`/`make_room`/
    `normalized_hype_gains`/`make_room_pick_fn`; selector spec `docs/PLAYER-VIEW.md` §9). Default mix
    hand-set, **corpus-checked** on 3,309 eligible-redraft managers (1.7 % RB-light ⇒ no `zero_rb`
    seat); per-seat gains **normalized to room-mean 1** so composition redistributes 16.9's shock
    instead of rescaling it.
  - **★ 16.15's headline is Phase 16's FIFTH null, and it is 16.9's null.** At the shipped 1.48-pick
    shock the largest per-seat move is **0.036** and routing-vs-gain is **+0.07**; the same shock ×10
    gives **+0.91** (sweep ×1→×40: +0.07 · +0.53 · +0.84 · +0.91 · +0.95). The coupling is built
    correctly and waiting on a signal worth routing, so the done-bar **gates the mechanism**
    (`AMP_GATE`) and **reports the shipped size**. Turning the shock up to pass would tune a
    calibrated parameter to a face-validity check.
  - **★ The reach ceiling now bounds a seat's own opinion, not the shared story** — folded into one
    clip, a seat whose signals saturate its ceiling cannot express the shock, and nothing fails.
    Found only because the bar was restated across **all nine seats**: *chasers − autopickers* passes
    on a room routing the story backwards, since autopickers get sniped either way.
  - **T17 ☑** — `injury.projected_availability_frame` rolls covariates forward for an unplayed season
    (2026 level ratio **0.37 → 0.721**), plus a **level-band guard** in `steps/phase5_5_utility.py`
    that runs on the live season too. Knock-on: the repair turned `games_played_mean` into a *level*
    proxy, so 16.13 gained a residualized `durability` column and `safe_floor` weights that. **New
    T18** (🟡): `avg_reach` in the manager profiles is a pooled-board mismatch (+91.9-pick mean QB
    reach), unconsumed today.
- **Mock-drafter completion audit (2026-07-29) ☑ — the arc is closed and re-measured.** T15 steps
  0–4 · 16.14R · T23/T25/T24 were already done (the register's index row for T15 was stale, now
  corrected); the shipped room re-measures **unchanged to the digit** on all five bars plus the
  landing and legality gates (`analysis/mock_room_bars_verify_20260729.json`). The three entries
  *behind* it are now ☑: **T22** (boom/bust were four seasons stale **and being printed to the
  human** → `boom_prob_live`/`bust_prob_live` in the 16.13 enrichment, exact-zero bust 56 % → 8 %),
  **T13** (cross-process reproducibility — the cause was **DuckDB's parallel float aggregation**,
  not the Iman–Conover coupling → `db.deterministic_reads`, bit-identical over three processes),
  **T18** (per-manager reach against each draft's **own** board — 35.8 picks → 0.776 rounds, and the
  QB sign reverses). **New T26** (🟡): `pos_share_*` is pooled across formats while the fit is
  redraft-only and `mgr_lean` reads it — measured (0.83 pp) and deferred to the next 11.1 refit,
  because fixing it refits β and moves every T15/T24 width bar.
- **★ Session H.5 — the mock-drafter value seam (T27 · T28 · T29 · T30). ☑ COMPLETE 2026-07-30.**
  **Result: the two hard bars held and both falsifiable bars failed.** T27 ☑ shipped (the value chain is on
  the board; `why <player>` prints it; and wiring it in found that the *interactive* room had been running
  `value_hawk` as `balanced` all along, because `make_room_pick_fn` had no `risk` parameter and so
  `assert_room_objectives` never ran on the human path). **T28 ☑ closed as a LABELLING FIX** — `starter_value`
  ships beside `team_value` and every surface prints both, but **B5 failed** (−0.0230, CI[−0.0407,−0.0055]
  over 200 seated-reshuffled drafts): the slot-blind sum predicts title probability *better*, because the sim
  draws injuries and bench value alone scores **+0.711**, so `value_hawk` keeps `objective=portfolio_ce`.
  **T29 ☑** provenance + fair-share multiples everywhere. **T30 ☑ argued and NOT changed** — the `chalk` swap
  closes 79 % of the chalk-share gap but regresses two reach bars, and the rule was fixed first.
  **B2 failed at RB → new 🟠 T31** (on a live board the level correction inverts for players consensus
  projects as backups: 22.8 % of the 2026 value index has `mean` **above** `proj_points`). 612 tests
  (was 597), ruff clean, bar sheet + frozen cost report both bit-identical.
  _(original scoping, for the record:)_ The room *simulation* is finished and re-verified; what is not finished is the
  **seam between a correct engine and a human reading it**, and the first fully-simulated ten-personality
  walkthrough found all of it there. **The simulation passed everything it was asked** — positional mix matches
  333 realized 10-team/15-round human drafts at the median (WR 53/55 · RB 45/42 · QB 16/17 · TE 15/16 · K 9/10 ·
  DEF 10/10), `reacher` spent *exactly* its budget (3 of 3 swings, 5 of 5 leans, round-1–3 max reach **−0.1**),
  elite fall landed on the shipped distribution (**25.0 %** past pick 10 vs a committed 25.2 %), and the fit is
  9 seasons / 70,614 groups, not a stale 2017–20 extrapolation. The four tickets:
  - **T27 🟠 — the board a human reads is not the board the seats optimize.** The CLI prints
    `proj_points`; utility and `value_hawk`'s objective run on `base_value` = Phase-5 CE − replacement CE.
    **Drake Maye proj 316.5 → +68.5, Jayden Daniels proj 313.4 → −101.6**: 3 points apart on screen, 170 apart
    in the number that decides every pick. The mean haircut (0.28 QB/0.33 RB/0.28 WR/0.30 TE) is the *intended*
    level correction; the **dispersion** (QB 0.15–0.56) is what makes the board unreadable. Fix = show both
    scales + `games_played_mean`, a **`why <player>`** command printing the whole arithmetic chain, and a
    health gate asserting the haircut is *explained* by projected availability. **T22's lesson one level up —
    a column's consumers are not only the models that weight it, and this is the first number a human reads.**
  - **T28 🟠 — `team_value`/`portfolio_value` are slot-blind.** No slot logic exists in the value path, so a
    bench QB2 is priced at full weight: the walkthrough's QB2 line nets **−122** of a 1,938 room total and
    **T4 is 9th of 10 on VBD, 3rd on starting-lineup projection**. Spearman vs title: portfolio CE **+0.758**,
    starting-nine Phase-5 mean **+0.915**. `value_hawk` *optimizes* it, so it steers picks too. Fix = a
    **labelled second metric** beside the frozen one, never an edit; the value-hawk-objective question is
    explicitly the user's and gets its own sub-step.
  - **T29 🟡 — bare absolute probabilities** from a sim with a documented **−113 pts/team** level bias and a
    *marginal* playoff Brier 0.240. Fix = provenance + lead with **fair-share multiple**.
  - **T30 🟡 — `autopilot` is 1 of 10 seats against 0.2 % of real seats** (50×) and is the seat that
    manufactures the spill. 16.14R halved it on this argument and stopped. Fix = a cheap
    seating-marginalized A/B against a near-autopilot seat, then **write the paragraph either way**.
  - **None of it refits β; none of it touches the frozen value stack.** Every step's hard bar is that
    `analysis/mock_room_bars_verify_20260729.json` reproduces **bit-identically** — *a display change that
    moves a bar is not a display change.* **~350–600L / 8–12 files / ~10–15 tests.** Steps + pre-registered
    bars B1–B6: `docs/BUILD_PLAN.md` §"Session H.5". **§3.7 gates NOT waived** — step 2 contains a user decision.
- **Session I — Phase 17 League-Format Fidelity 17.1–17.4.** 17.1 roster+lineup generalization (superflex/
  multi-flex; the `season.py` solver + format-aware VBD replacement — the meaty bit), 17.2 custom scoring, 17.3
  generic settings contract (engine/parser; form UI → 14), 17.4 keeper. **~full-phase (1,000–1,800L).**
- **★ Session I.5 ☑ COMPLETE 2026-07-30 — the seat map: multi-seat human control (16.17).** *(inserted
  2026-07-30, user request — "users can control as many of the picks as they'd like: pick personalities for
  6/10 and draft the other 4 teams themselves".)* One `SeatMap` replaced **four** copies of the one-human
  `team → seat` arithmetic (three named in the spec + a fourth in `steps/phase16_15_mock_room.py`);
  `DraftState.human_teams` + `seat_roles`; per-seat pick functions (`human_pick_fns`); `--seats 3,7` and
  `--auto <seat>` in `steps/mock_draft.py`. **668 tests (+10), ruff clean.** Every k ∈ {0,1,4,9,10} runs to a
  complete, legal draft. **The done-bar was bit-identity and it held on every comparison:** the mapping
  contains the deleted formula exhaustively (1,014 triples, 0 mismatches); 54 draft pairs against the deleted
  arithmetic re-implemented verbatim, 0 different; and the room bar sheet is **bit-identical to a pre-16.17
  control run on today's board**. ★ Two method notes worth keeping: (1) the *poisoned control* — before
  believing "0 differ", the same comparison was run against a deliberately rotated legacy mapping and had to
  report a difference (36/36 did), because T31 had shipped a before/after that ran post-fix code twice; (2)
  the committed 07-29 sheet is **not** a clean reference — the Stage-0 chore and T31's `ENRICH_VERSION` bump
  refreshed the live board, so its `readout_2026` block legitimately moved. Hence the control run. Opened
  **T33** (the value hawk's `n_teams` is the *room* size, so it is 9 interactively and 10 in batch — preserved
  verbatim because bit-identity is the bar, and now varying with k). Done-bar: `steps/phase16_17_seat_map.py`
  → `analysis/phase16_17_seat_map.json`. UI half still ships in Session K as **14.J**.
- **Session J — (optional) Phase 15.1 dynasty.** Multi-year asset pricing; deferred/optional per user scope —
  a short session or skipped. Keeper (17.4) already covers the nearer-term need.
- **Session K — Phase 14.1 the Streamlit MVP (do NOT bundle — the largest phase). SPLIT IN TWO 2026-07-30**,
  by the draft calendar rather than by module: Session K was scoped as "multiple-session-sized on its own",
  and the 2026 draft is ~4–6 weeks out, so the half a drafter actually needs ships first. Full spec + the
  six pre-registered bars: `docs/BUILD_PLAN.md` §"Session K1". **Premise: the app is a UI over
  `steps/mock_draft.py`, which is already a complete human-in-the-loop driver on the live board** — so K1
  is a port of a working surface, not new modelling, and its hard bar is that **the app and the CLI agree
  to the digit** from the same seed.
  - **Session K1 — the draft-day half. ✅ DONE 2026-07-30.** T32 ☑ (the board-vintage cache key) → the
    app on the **live** season → the board + the `why` value chain → the room with 14.J's per-seat YOU
    toggle over the 16.17 `SeatMap` → the 17.3 settings form (`LeagueSettings` is no longer orphaned) +
    the cost tab; `src/fantasy_quant/app/` deleted. **All six pre-registered bars PASS** plus two
    live-run checks (`analysis/session_k1_app.json`); **691 tests**, ruff clean. The port's shape is
    the result worth carrying: every derived frame moved into `draft/session.py` and **both**
    `steps/mock_draft.py` and the new top-level `app/` render it, so B1 (app == CLI) holds by
    construction — the CLI's output is byte-identical across seven commands before and after.
  - **★ Session K1.5 ☑ COMPLETE 2026-07-31 — the draft room a human can use.** All six steps built,
    **all eight bars PASS** (`analysis/session_k1_5_app.json`: B0 20/20 distinct openings · B1 one page
    body per rerun · B2 slim ≡ advanced · B3 clocked ≡ stepped over 150 picks · B4 slot grid == the
    frozen startable lineup, gap 0.0 · B5 14 documented columns · **FLOW** a draft started and a pick
    made by clicking · **K1** Session K1's sheet re-run passing). **T34 ☑ · T35 ☑ · 14.K/14.L/14.M/14.O
    ☑.** 702 tests (was 691), ruff clean; nothing refits, no frozen contract moved, the lockbox not
    re-read. **Two findings:** the 14.M latency worry did not survive its own measurement (worst modelled
    pick **10 ms**, not seconds — the 8.5 s/pick number was Session D's dropped MCTS *search*), and
    driving the widgets found a defect six bars missed → the new `bar_flow` (*an import bar and a use bar
    are different claims*). Scoped 2026-07-30 s4 as:
  - *(original scope, kept for the record)* **INSERTED ahead of K2**, from the
    user's notes after driving the K1 app for the first time. Everything in it sits between the drafter
    and the board on draft day; K2's surfacing does not, so this goes first. Full spec + six
    pre-registered bars: `docs/BUILD_PLAN.md` §"Session K1.5". **Step 0 = T34**, the one real bug —
    `app/engine.start_draft` defaults `seed=7` **and** `room_seed=None`, freezing both sources of
    variation, so **every mock is the same mock** (reproduced exactly: seat 6 always opens Gibbs · Chase ·
    Taylor · McCaffrey · Cook; `seed=8` opens Gibbs · Nacua · Jeanty · Bijan · Chase). The app default
    becomes entropy with a **lock-the-seed** option; **`steps/` keeps `--seed 7`** because every committed
    bar sheet is differenced against it — *a measurement default and a human default are different
    objects.* Then **14.K** pages-not-tabs (**T35**: `st.tabs` runs every tab body on every rerun — the
    hard blocker on the clock) · a **slim board** (`# · PLAYER · POS · ADP · PROJ`) with an **advanced
    view**, **pick buttons in the row** and **search results under the box** · **14.M** the pick clock
    (n seconds per modelled pick) · **14.L** the room grid (every team across the top, by pick or by
    slot) · the **roster rail** beside the board · **14.O** stat tooltips with worked examples.
  - **★ Session K2 ☑ COMPLETE 2026-07-31 — surfacing + the post-draft page.** All eight pre-registered
    bars PASS (`analysis/session_k2_app.json`, runner `steps/session_k2_app.py`); **726 tests (+24),
    ruff clean**; nothing refits and **B0 re-runs both committed sheets**. Shipped: **14.N** the
    post-draft page (`app/post_draft.py` — reachable throughout, live mid-draft, auto-runs 400 sims
    once on arrival at a finished draft; it **absorbed** the room page's standings/odds/draft-flow
    readouts rather than copying them) · **14.E** the tier-cliff strip + `CLIFF` column, read from the
    greedy's own `positional_cliff(pool, risk.bv)` · **14.G** a third board projection (`RANGES`:
    `Q10/MED/Q90/COIN/FLAGS`) whose honest headline is that **146 of 199 adjacent pairs overlap** and
    **70 of 200 rows sit on the `q10` censoring point**, flagged `censored floor` rather than printed
    as a floor of zero · **14.F** bye clustering (over *starters*, unknown byes stay unknown — the
    store has no schedule table) / NFL-team concentration / handcuff gaps priced with the frozen 8.5
    elevation ratio · **14.I** the draft grade, 0–100 → letter on a **user-chosen** 50/20/15/15
    weighting that is printed beside every grade because nothing validates it, once **per human seat**
    and never blended · **16.12** the reach-risk readout, which had no surface since Session G, with
    its un-drifted baseline beside it · the `PLAYER-VIEW.md` card as an `st.dialog`. The CLI moved
    with it (`board --view {slim,ranges,advanced}`). **16.6 the Beta Lab tab was skipped by user
    decision** (the value-side track is an honest null) and stays ☐. **14.H** stays ☐ — it is specced
    for the 14.3 frontend, not the Streamlit MVP. Outcome + the three defects the measurements caught:
    `docs/BUILD_PLAN.md` §"Session K2", `findings.md`, `PLAN.md` 2026-07-31 (session 2).
  - **Session K3 — league import (17.5 Sleeper · 17.6 ESPN; 17.7 Yahoo deferred to 14.4).** One function
    and two adapters: `import_league(...) -> LeagueSettings`, filling the 17.3 form for the user to
    confirm. Spec: `docs/BUILD_PLAN.md` §"Session K3" + §"Phase 17 — league import".
  - **★ Sessions UI-1 … UI-4 — the front end** *(scoped 2026-08-01 from a competitive deep dive across
    **eleven** products — FantasyPros Draft Wizard · Draft Sharks War Room · PFF · 4for4 Draft Hero ·
    RotoWire · Sleeper · ESPN · Yahoo · Underdog · UDK · Footballguys, plus Boris Chen and KeepTradeCut.
    Evidence + fourteen non-recommendations: `docs/UI-PLAN.md`. Build spec + per-session bars:
    `docs/BUILD_PLAN.md` §"Sessions UI-1 … UI-4").* **The finding is not the expected one: we are not
    missing analysis, we are missing an information architecture.** `app/` renders **68 prose blocks
    against 9 visual elements, 0 uses of colour to encode anything, 0 tier breaks drawn** — and
    `ADVANCED` is 15 columns, **two more than Draft Sharks' full rankings table**, whose density is that
    product's most-criticised property. The work is ranking, encoding and hiding; it is not adding.
    Seven things we ship have **no competitor equivalent** (validated `P(available)` with an un-drifted
    baseline · `COIN` · `censored floor` · the T27 chain · lockbox provenance · the printed 14.I weights ·
    the cost report) and every one currently reads as an apology.
    - **☑ UI-1 "it looks like a product" — COMPLETE 2026-08-01.** All eight bars PASS
      (`steps/session_ui_1.py` → `analysis/session_ui_1.json`); **737 tests** (was 726), ruff clean.
      Shipped: S4 a dark `.streamlit/config.toml` · S1 position colour on all five surfaces from one
      `app/palette.py` constant — **Okabe-Ito, the user's call over the market convention, because
      QB-gold / RB-red / TE-orange is three positions a deuteranope reads as one** · S3 prose
      **68 → 23** by relocation into `st.badge` chips, `help=` tooltips and `st.popover`s, with **B3
      asserting all seven honesty surfaces still render by driving the app** · S5 the draft-order seat
      strip (`st.html`, position-coloured last pick, your seats marked, snake arrow, *your next pick
      #N, k away*) · S6 **T37 ☑** the reach risk out of the expander and permanently in the right rail,
      plus `P(THERE)` on the **slim** board and in the CLI's · A6 **T38 ☑** 14.N as a report card
      (hero row **grade · title fair-share multiple · STARTABLE rank**, biggest-reach / best-value pair,
      the rest behind `st.tabs`). **One authorised deviation from "nothing enters `session.py`"** (user
      decision): `attach_reach` / `next_pick_info` / `team_for_pick` are **placements**, not
      derivations — B0 re-ran the K2 sheet unchanged. **Deferred to UI-2:** the positional-strength
      chart (needs a genuinely new derivation) and the hatched `censored floor` **bar** (UI-3's A3 is
      where bars get drawn; UI-1 ships the `⌀` chip + tooltip instead).
    - **☑ UI-2 "the board answers the question" — COMPLETE 2026-08-01**, four of five steps shipped and
      **step 1 measured as a NULL**. Shipped: A4 `Δ` (ADP countdown) + `BARGAIN` · A5 the 14.F
      construction flags surfaced **at pick time** as `RISKS` (`⚑⛓🛡⌀◔`), each glyph a delta of
      `roster_construction_risk` on (roster + him) · the 15-column `ADVANCED` split into `VALUE`(12) /
      `RISK`(9) · **A6's positional-strength chart**, the piece UI-1 deferred by name. All eight bars
      PASS (`steps/session_ui_2.py`), 749 tests, and B0 holds the fifteen existing columns
      **bit-identical**.
      **★ S2 did NOT ship — the tier cut by *band overlap* is a null (T39).** It was scoped as *"the one
      item here no competitor could copy without our distribution stack"*; measured, it cuts **1 tier per
      position** and **2 over the whole board**, because the median RB 80 % band is **228 pts** against a
      median adjacent gap of **16.3** (**14×**) and because the Boris Chen analogy is a category error
      (he clusters expert rank **dispersion**; we hold a **predictive interval**). ⚠ It also corrected a
      number quoted throughout these docs: `COIN`'s **146 of 199** conflates *distinguishable* with
      *unknown* — **147** pairs have both bands, **146** overlap, **1** is a genuine break and **52** are
      missing bands, so the honest figure is **99.3 % of evaluable pairs overlap**.
    - **☐ UI-3 "preferences are first-class"** — A1 the queue/tag system (🎯 must · 🚫 never · ↑ reach ·
      ↓ wait) **unified with the Cost page, replacing its four multiselects**, so a preference formed
      while drafting can be priced — the direct-indexing workflow the current UI makes impossible · A2 the
      selected-player strip (PLAYER-VIEW §3's hover card, inline, board stays visible) · A3 **actually
      draw the §5 bars** (today's `st.metric` has no bar and no baseline — the largest spec-vs-shipped gap
      in the repo) · A7 two taps to a pick, not three.
    - **☐ UI-4 polish tail** — league presets *(after K3 — same 17.3 form)* · room-grid colour · density ·
      CSV export · merge the `why` box into the dialog · land on Board · C2 a mock history that **replays
      exactly** (T34's stamped seeds make it near-free; PFF's hub cannot) · C3 a room scouting report from
      `drift_frames["seats"]` — **realism, never prediction** (PLAYER-VIEW §9.3) · C4 light/dark.
    - **Recommended order: UI-1 → K3 → UI-2 → UI-3 → UI-4.** *(UI-1 ☑ and UI-2 ☑ are both done as of
      2026-08-01; K3 is next.)* UI-1 is pure formatting with zero engine
      risk; the only real coupling is that UI-4's presets sit above the form K3's importer fills.
    - **Deferred out of all four, deliberately:** **C1 undo** (`DraftState` is append-only and consumes an
      RNG, so honest undo is a seeded replay and must preserve K1.5's clocked-≡-stepped identity — engine
      work with its own sheet) · **the 14.3 Next.js frontend** (get Streamlit to "a friend can use it
      unaided" first) · `streamlit-aggrid` · headshots/logos · mobile-in-Streamlit · LLM board narrative ·
      drag-to-reorder rankings · multiplayer rooms — twelve more with reasons at `docs/UI-PLAN.md` §5.
- **✅ Session VH — the value-hawk repair** *(DONE 2026-08-01; scoped same day. Spec
  `docs/BUILD_PLAN.md` §"Sessions VH · MM-1 · MM-2"; **T33 ☑**, **T43 opened**, T42 answered)*.
  **All four bars reported; the session's own leading hypothesis was demoted by its first substep.**
  The user supplied a verdict on **all 15** picks, which beat the spec's "name the ones you object
  to" because it came with a control group. **VH.0:** the judged artifact is **unreproducible**
  (10/150 picks on the live board, 33/150 pinned — it predates T22/T31/the 08-01 refresh) → added
  `resolve_board(..., asof=)`; his labels track **reach** at `corr = +0.767` (bad picks +5.5, good
  picks −10.6); **B1 = 38 %/29 % slot-driven → INCONCLUSIVE**, and **T42's flagship pick (the TE2)
  is changed by no ablation at all because TE is flex-eligible** — the slot channel owns QB2, not
  TE2. **VH.1:** T33 fixed by reading `state.n_teams`; **k=0 bit-identical, k=1 moved 20.7 % of
  picks** — the room a human drafts against was never the room that was measured. **VH.2:** the
  interventional A/B (200 seat-shuffled drafts × 4 DEV seasons) found **realized points and the
  sim's title probability disagree in sign** — `starter_aware` is **+50 realized** and **−0.295
  title ×** with every shape measure improving, so B3 blocks it on the metric we least trust
  (reported as a **finding about the sim**, not acted on); **`blend_50` passes B3** (+0.144 title,
  +0.026 playoff, +19.9 starter value, nothing degraded). **VH.3:** the window is **still
  unresolved** on outcome (non-monotone, ±25 against se 9–13) and monotone/clean on reach (0.70 →
  3.77) — but the realism sheet decides it: **w=0.5 costs +0.0360 profile distance (0.0894 →
  0.1254), 7× T30's unshipped change and worse than 16.14R's own 0.1156 → free on outcome,
  EXPENSIVE on realism, keep 1.0.** **★★ And corpus round-1 reach is 2.868 against the shipped
  seat's 2.6405 — the seat already reaches LESS than a real human, so *the seat is realistic, it
  just is not a value hawk*: one seat is doing two jobs and only one of them has a corpus.**
  **B0: 628 leaves, zero gate values moved, all 8 pass flags hold.** 763 tests, ruff clean.
- *(superseded scope line, kept for the record)* **Session VH** *(scoped 2026-08-01 s5, from a user report; spec
  `docs/BUILD_PLAN.md` §"Sessions VH · MM-1 · MM-2", register **T42** + **T33**)*. The user reported the
  seat "consistently makes picks that are characteristically uncalled for" **and** finishes weak — asked to
  separate them, he said **both, and they feel related**, which is the answer that diagnoses it. **The value
  path is slot-blind and `value_hawk` is the only seat that *maximizes* it**: `capital − startable` is
  **+152** for this seat and negative for every other, and the shipped mock has it taking a **QB2 in round 8
  and a TE2 in round 9** in a 10-team 1-QB league with its first RB in round 6. **★ T28 could not have
  settled this** — its bar asked which roster-value definition best *correlates* with title probability and
  used the answer to decide what the seat should *maximize*; **a relationship measured on outcomes is not a
  specification for the mechanism that produced them** (T24's lesson, one level up). Substeps: **VH.0**
  attribute the objected picks (**and it can kill its own hypothesis** — confirmed at ≥50 % slot-driven,
  abandoned below 25 %) · **VH.1** T33 (`n_teams` is the room size, so the interactive seat is not the
  measured seat) · **VH.2** the interventional A/B, ≥200 seating-marginalized drafts × ≥4 DEV seasons,
  **reporting outcome and roster shape separately** · **VH.3** the window sweep that never resolved. ⚠ The
  seat is **repaired, not replaced** — it is 1 of 10 in `REALISTIC_ROOM` and every T15/T24 bar was measured
  with it there. ~half a session.
- **☐ Sessions MM-1 · MM-2 — the fitted manager model (16.18)** *(scoped 2026-08-01 s5)*. The user's own
  proposal: a personality **modelled on himself**. Ships as `FittedManager`, loading a **profile file** — a
  general mechanism with the user as subject #1, which **preserves** the 2026-07-23 "nothing personal to the
  user" decision rather than overriding it. **★ The scoping finding: "mimic me" is two objects** — *beliefs*
  (disagreement with consensus about players → a board, ~50 rows) and *policy* (the tradeoff rule → fitted
  from ~300 **designed** pairwise comparisons, 45–60 min). Learning both at once from mock drafts is what
  made it look like it needed "many many drafts". A comparison and a real 40-way pick are the **same
  conditional-logit likelihood**, so elicited and realized data pool; the fit is a **shrunk deviation** from
  the corpus β (16.4's EB machinery). **★ The bar is held-out pick prediction against the corpus-fit
  `balanced`** — withheld comparisons *and* real mock picks never used in fitting — pre-registered before
  the fit is read, because the optimizer and the grader are the same human. **A faithful replica is a
  realism deliverable, not an edge one**; the spent lockbox already called personalization noise-dominated
  on realized points. MM-1 ≈ full session + his hour; MM-2 ≈ half to full.
- **Session L+ — Phase 14 go-live tail (14.2–14.7).** Personalization tiers, explain, FastAPI backend, Next.js
  frontend (PLAYER-VIEW deep pages + 14.H playoff-SOS lens), Sleeper live-draft sync (+ 16.16 run-detection
  alert, item D), widget, mock-draft sim. **Expect multiple sessions**, each ≥ a single past phase.

Working rules throughout: DEV-only (lockbox 2023+24 untouched — Phase 16/17 are walled-off/config-only), STOP
gates between sub-steps, findings/glossary/PLAN/ROADMAP/BUILD_PLAN per step.
**Known-problem register (the exact fix per item): `docs/TECH-DEBT.md` (T1–T10).**

**Open decisions (reframe §10 — tracked in `PLAN.md`):** real completed-draft data (Sleeper) for the
behavioral model; a **consensus-projections source** (FantasyPros aggregate — free/PIT?); the benchmark
set. **Resolved:** lockbox = **2023 + 2024** (dev on 2014–2022; `config.DEV_SEASONS`). 2025 excluded (no
weekly rollup / ADP board yet — see `findings.md`).

**Phase-2 finding (still true — now a feature, not a failure):** consensus ADP is a strong baseline the
naive model can't *significantly* beat — so we **stop trying**, lean on consensus for value, and compete on
personalization + honest cost transparency instead.
