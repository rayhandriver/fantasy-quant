# Fantasy Football Quant Model & App — Feasibility, Parallels, and Build Plan

## Context

You spent this internship at **Alphathena building a production-grade equity risk model**: a
fundamental factor covariance cache (`Σ = X F Xᵀ + D`) that replicates and is horse-raced against
the firm's PCA covariance, feeding a tracking-error/min-variance optimizer for **direct indexing +
tax-loss harvesting**. You now want to build a **personalized, quant-inspired fantasy football draft
model** and wrap it in a **shareable web app your league can use**, reusing the same machinery and
discipline. This document answers: *what carries over, what doesn't, is it worth it (for learning
**and** for a real edge), and how would you build it.*

It is grounded in three sources I read in full:
- `~/Downloads/fantasy_football_model_reference.md` — your prior planning conversation (the modeling stack, build order, tech).
- `intern-repo/` — `PROJECT.md`, `PLAN.md`, `CLAUDE.md`, `glossary.md`, `findings.md`, the `statistics/` pipeline, and the `steps/` walk-forward race.
- **alphathena.com** — the product/business (direct indexing, TLH, optimization, personalization-at-scale, Open-API B2B).

**Your stated steer (2026-06-29):** product target = *shareable app for my league*; backtest metric =
*layer both* (points-above-replacement first, then season+playoff simulation as north star); data =
*free / self-scraped*, pay only if it becomes a real product.

---

## Part 1 — What you actually built at Alphathena (so the parallels are concrete)

| Piece | What it is | The transferable skill |
|---|---|---|
| **Factor covariance** `Σ = X F Xᵀ + D` | Low-rank (shared factors) + diagonal (idiosyncratic) decomposition of co-movement | Decomposing any cross-section into *systematic exposure* + *private noise* |
| **Exposures `X`** (9 style ranks + sector dummies, z-scored, PIT) | Each name's "fingerprint" across value/momentum/quality/size/beta/vol/… | Feature engineering: standardized, point-in-time exposure matrices |
| **Cross-sectional regression** (daily WLS, returns on `X`) | Backs out *factor returns* (what each factor "paid") + *specific returns* (residual) | The exact engine that separates signal-from-factors vs idiosyncratic alpha |
| **EWMA + half-lives** (vol 84, corr 252) | Recency-weighted estimates that track the current regime | Time-weighting noisy series without overfitting the present |
| **Shrinkage** (QIS / Ledoit-Wolf / OAS / WeSpeR) + **Marchenko-Pastur** | Pull noisy sample covariance toward a stable target; clip eigenvalues below the noise floor | Regularization under small `n` — the core defense against overfitting |
| **Walk-forward horse-race** (`min_variance_backtest`, monthly 2018→2025, strict `as_of` PIT) | Out-of-sample, point-in-time evaluation; **never rank on in-sample fit** | The single most valuable habit you learned — and the rarest in fantasy tools |
| **Bias statistic** (realized ÷ predicted ≈ 1) | Calibration check on risk forecasts | Are your *intervals* honest, not just your point estimates |
| **Hard gate** (`_validate_cov_hard_gate`: PSD, symmetric, finite, sane bounds) | A contract every output must pass | Defensive validation as a first-class artifact |
| **The verdict** | **PCA beat your fundamental factor model OOS** (GMV vol 17.93% vs 17.07%; tracking TE 1.80% vs 1.74%, both CIs exclude 0); factor's *only* edge was lower turnover | **The humility lesson**: a sophisticated, "smarter" model can lose to a simple baseline out-of-sample. This is the most important thing you learned and it applies directly below. |

You also internalized the three biases that destroy backtests — **look-ahead**, **survivorship**, and
**in-sample selection** — and the "reuse before you write / the boring parts are the edge" ethos.
**All of this transfers almost verbatim.**

## Part 2 — What Alphathena's business is (the product parallel, not just the math)

- **Direct indexing**: own the *individual constituents* of an index instead of the fund, so you can
  **personalize** (ESG/values exclusions, factor tilts, security selection) and **harvest tax losses**
  while **tracking the benchmark** (minimizing tracking error via the optimizer your `Σ` feeds).
- **Value proposition**: *personalization at scale* + a quantified edge ("**1–2% annual tax alpha**" vs a
  plain ETF, backtested). Delivered as **B2B SaaS via an Open API** to RIAs/TAMPs/advisors; the advisor
  configures preferences, the software automates optimize→rebalance→harvest.
- **Moat**: not one clever trick — it's the *whole pipeline done cleanly* (data, optimizer, tax logic,
  custodian integration) plus credible backtested numbers and personalization breadth.

This business shape is the template for your app (Part 6).

---

## Part 3 — The parallels (the heart of it)

### 3a. The math/modeling parallel — uncannily tight

| Alphathena risk model | Fantasy model analog |
|---|---|
| Universe ≈ 7,000 stocks × 2,360 days | ≈ 250–300 fantasy-relevant players/yr × ~15 usable seasons (**~3,750 player-seasons** — *much* smaller; see drawbacks) |
| `Σ` = stock-stock covariance | **Player-week covariance**: QB–WR1 stack ≈ +0.4, RB1–RB2 same team ≈ −0.3, RB–handcuff ≈ −0.5…−0.8 |
| `Σ = X F Xᵀ + D` (factor + idiosyncratic) | **Projection** = exposure to systematic factors (opportunity, age, environment) + **player-specific alpha** + week noise. Same Fama-French shape. |
| Style factors (value, momentum, quality…) | **Fantasy factors**: target share, air yards, snap share, age curve, O-line, QB quality, pace, implied team total (full taxonomy in Part 4) |
| Cross-sectional regression → factor returns | Regress weekly points on player exposures → "how much did target share pay this week" |
| Specific risk `D` (EWMA, HL 84) | **Week-to-week variance** — boom/bust is literally high realized vol; **GARCH-like clustering** is real (your reference doc nails this) |
| Shrinkage / hierarchical priors | **Bayesian shrinkage** of thin-sample players (rookies, injury-returns, new systems) toward **archetype priors** — your strongest small-sample tool |
| Marchenko-Pastur noise floor | "How many factors are *real*?" With 3,750 rows, **deep nets overfit instantly**; stay in regularized-linear / GBT / hierarchical-Bayes territory |
| PCA vs fundamental horse-race | **Statistical (data-discovered) vs hand-specified (opportunity/age) projections** — race them the same way |
| Walk-forward, strict `as_of` PIT | **Backtest draft strategies on 2015–2024 preseason data**, no leakage — *the* differentiator vs every free tool |
| Bias statistic ≈ 1 | **Calibration**: do your 90th-percentile weeks actually happen 10% of the time? |
| Tracking error `(w−w_tgt)ᵀ Σ (w−w_tgt)` | **Roster variance / correlation**: build a lineup with a chosen floor/ceiling; stacks raise ceiling, anti-correlation raises floor |
| min-var / SPY-tracking optimization | **VBD / lineup optimization** as constrained optimization; "track the optimal board" with personal tilts |
| Survivorship (`Active=True` only) | Survivorship in fantasy panels (players who stayed relevant); injured-out seasons |
| **PCA beat factor OOS** | **Expect your clever model to struggle to beat ADP + a simple projection baseline.** Bar = beat both in backtest *before* trusting it. |

### 3b. The product/business parallel — also tight

| Alphathena | Your fantasy app |
|---|---|
| Direct indexing: track an index, personalized | Draft helper: track the "optimal board," personalized to user |
| Personalization levers (ESG, tilts, selection) | **Archetype prefs, per-factor over/under-weights, draft style, anchor picks** (your reference doc's whole v1 vision) |
| Tax-loss-harvesting "**tax alpha** 1–2%" | Your **edge claim**: "drafting with this beat ADP by *X* in backtest" — the credibility hook |
| Tracking-error optimizer | Conditional-VBD / draft optimizer |
| Household-level coordination, wash-sale rules | League/roster rules, bye-week & positional constraints |
| **Open API, custodian integration** | **League-platform integration** (Sleeper easiest → ESPN/Yahoo) for live-draft sync |
| Advisor configures, software automates | User configures preferences, model recommends the pick |
| "**Personalization at scale**" moat | Same moat: deep customization + transparency + backtest credibility vs paywalled, generic FantasyPros |

**Bottom line on parallels:** this is not a loose metaphor. Your internship was *a risk model + a
tracking-error optimizer + a walk-forward backtest*, and a serious fantasy draft model is *a player
risk/covariance model + a roster optimizer + a walk-forward backtest*. The **business** you supported
(personalization-at-scale, backtested-alpha, API-delivered) is the **same business** you'd build for
fantasy. You have already done the hard version of ~70% of this.

---

## Part 4 — Every factor that can / should be included

Organized by role in `points = Σ(exposureᵢ · factorᵢ) + player_alpha + noise`. **Bold = highest signal.**
Tag: **[X]** systematic exposure, **[D]** drives idiosyncratic variance, **[M]** market/draft-context.

**A. Opportunity / volume — the dominant predictors [X]**
- **Target share**, **snap share / route participation**, **carry/touch share**
- **Air yards, aDOT, WOPR** (weighted opportunity), **red-zone targets/carries, goal-line carries** (TD opportunity)
- Slot vs perimeter; pass-game vs run-game script dependence; **vacated targets/touches** (departures)

**B. Efficiency — partially skill, partially mean-reverting [X]**
- **YPRR** (sticky for WRs), yards/touch, yards-after-contact, contested-catch rate, catch rate
- **TD rate & TD-regression flags** (high/low TD luck), QB EPA/play, completion %, aDOT; YPC (noisy — regresses hard)

**C. Player-intrinsic [X]**
- **Age / position-specific age curve** (RB cliff ~28–30, WR peak 25–27, TE late, QB long plateau) — use the **delta method**
- **Draft capital / prospect pedigree**, athletic profile (combine, **breakout age, college dominator**)
- **Injury history / durability** (actuarial) **[D]**, experience / breakout-year flags (e.g. WR year-3), playstyle archetype

**D. Team / environment — systematic, shared across teammates [X]**
- **O-line quality** (run/pass-block win rates), **QB quality** (for pass-catchers), **implied team total / Vegas win total**
- **Scheme & play-caller** (pass rate over expected / PROE), **pace / neutral plays-per-game**, coaching/OC changes
- Teammate competition (target/backfield committee), strength-of-schedule funnel (noisy — discount it)

**E. Role / depth-chart [X][M]**
- **Depth-chart rank & job security**, **within-team role rank** (your *team-leader* WR1>WR2 factor)
- **Handcuff / contingent value** (a real option — Part 5), committee ambiguity (touch-allocation uncertainty)

**F. Risk / distribution [D]**
- **Week-to-week variance**, **floor (P10) & ceiling (P90)**, consistency (% startable weeks)
- **Correlation to teammates** (stacks) **& to game environment**, **injury-games-missed distribution**, archetype hit/bust rate

**G. Market / draft-context [M]**
- **ADP + source bias** (best-ball vs redraft vs dynasty), ADP trend/volatility, **positional scarcity / VBD baseline**
- **Tier breaks / comparative dropoff** (your factor), **bye-week distribution**, positional-run dynamics, **opponent tendencies in your league** (for the draft engine)

**H. Macro / contextual [X][M]**
- Scoring settings (PPR/TE-premium — *changes everything*), rule changes, contract-year/holdout/suspension risk, weather (in-season > draft)

> Your four stated factors map cleanly: **ADP-adjustments → [M]**, **comparative dropoff → [M]/VBD**,
> **consistency-vs-volatility → [D]** (a utility function over the distribution), **team-leader → [E]**.

---

## Part 5 — Where the analogy holds vs breaks (drawbacks & differences)

**Holds cleanly** (build on these): factor decomposition; volatility/GARCH modeling; covariance &
correlation for roster construction; **Ledoit-Wolf/QIS shrinkage** of the player covariance; Bayesian
hierarchical shrinkage for thin samples; **walk-forward, PIT-correct backtesting**; the handcuff as a
**real option** (`Value = P(injury)·E[replacement] + (1−P)·E[standalone]`); VBD as a **conditional
expectation** over who's available at your next pick (option-pricing flavor).

**Breaks down** (respect these — they're the hard part):
1. **No continuous price discovery.** ADP updates in *weeks*, not ticks; it's rough consensus, not an
   equilibrium price. No order book. Less to anchor on than equities.
2. **You compete for *inventory*, not return.** Two drafters can't own the same player → this is **game
   theory** (auction/draft), not pure forecasting. The draft engine (MCTS/CFR) is genuinely poker-shaped.
3. **The market is *inefficient*.** Good for alpha (unlike EMH-equities) — but it means your edge is real
   *and* that ADP is a weak teacher.
4. **Brutal sample size.** ~3,750 player-seasons total vs your ~16M stock-days. **This is the biggest
   constraint.** It rules out deep nets and *demands* the regularization you already know (shrinkage,
   hierarchical priors, GBTs with heavy CV). Your intern instinct — "regularized linear/tree, not neural"
   — is exactly right here.
5. **Non-stationarity.** Rule changes, scheme evolution, a player changing teams — features drift faster
   than equity factors. Age curves and archetype priors are your stabilizers.
6. **The negative-result lesson is *more* likely here.** With this little data, a hand-built factor model
   will frequently fail to beat (a) ADP and (b) a simple projection baseline OOS — just as your
   fundamental cov lost to PCA. **Plan for that outcome; it's information, not failure.**

---

## Part 6 — Verdict: is it worthwhile? Can it give an edge? Can it be an app?

**For learning — unambiguously yes (highest-value possible).** It re-exercises *every* skill from your
internship (factor models, covariance, shrinkage, walk-forward + PIT, calibration, the optimizer seam,
the discipline) on a domain you care about, and adds two you didn't touch: **distributional/quantile
projections** and **game-theoretic sequential decisions (MCTS/CFR)**. It is the ideal capstone.

**For a real edge — yes, but bounded, and concentrated in specific places.** Be honest about *where*
the edge lives:
- **Strongest edge — draft-day decisions, not season-long point prediction.** You will *not* dramatically
  out-predict consensus on raw points (too little data, sharp public market). You *can* beat the field on
  **(a) conditional VBD** (value of a pick = points now − expected best-available at your next pick),
  **(b) roster correlation/variance construction** (stacks for ceiling, anti-correlation for floor — pure
  portfolio theory, almost no casual drafter does this), and **(c) exploiting your specific league's**
  ADP mispricings and opponents' tendencies.
- **Realistic magnitude:** a modest but real shift — more in **playoff/championship probability** (via
  better roster construction and variance management) than in expected raw points. Not a money printer.
- **The true moat is the boring part** (your reference doc and your internship both say this): cleaner
  data, PIT-honest backtesting, and a model you've *proven* beats ADP before you trust it. Most public
  tools fail exactly here. That discipline **is** your edge.

**As an app for your league — yes, very feasible, and the personalization is a genuine differentiator.**
FantasyPros et al. are paywalled and generic; a transparent, deeply customizable, backtest-credible tool
for your league is a real product. The binding constraints (per your reference doc): the **data-freshness
pipeline** through preseason and the **live-draft data integration** (Sleeper API is the low-friction
start). For a friends' league these are very tractable; as a paid product they're the main work.

**Recommendation:** build it. Target the **shareable league app** as the product, but **model-core-first**
inside it — a credible model with an honest backtest is what makes the app worth using and is also the
part that compounds your career skills. Defer MCTS/CFR and any paid data until the core + app prove out.

---

## Part 7 — The build plan (model-core-first, app as the v1 product)

Mirrors your intern repo's discipline: **reuse-before-write, PIT everywhere, walk-forward never in-sample,
a hard gate on every output, and a `findings.md`/`glossary.md` log as you go.** Each phase has a "Done when."

### Phase 0 — Data pipeline + backtest harness (do this first; it's 60% of the value)
- **Ingest (free):** `nfl-data-py` (play-by-play, snaps, targets, weekly fantasy points), Pro-Football-Reference
  (season panels), **scrape Fantasy Football Calculator** (historical ADP snapshots) and **Underdog** (early best-ball ADP). Store **point-in-time** in **DuckDB**.
- **Backtest harness (the analog of `min_variance_backtest`):** a function that takes a *ranking method*,
  runs it on 2015–2024 preseason states, simulates drafts vs ADP-following opponents, and scores the
  resulting rosters against *actual* season outcomes — **strict `as_of`, no look-ahead, survivorship
  documented**. This is your `as_of`-enforced walk-forward, ported.
- **Done when:** you can score *any* ranking method end-to-end on historical drafts with one call, PIT-clean.

### Phase 1 — Baseline projections + the metric (layer both, per your choice)
- Implement a **documented public baseline first** (e.g. simple opportunity × efficiency) and a **VBD /
  points-above-replacement** scorer — the simpler headline metric. **Beat the baseline before getting fancy.**
- **Done when:** PAR-ranked drafts backtest cleanly and you can compare any method to baseline + to ADP.

### Phase 2 — Factor projections + distributions (your `X F Xᵀ + D`, ported)
- Component models per position (**GBT: XGBoost/LightGBM**) from the Part-4 factors; **age curves via the
  delta method**; **hierarchical-Bayes priors** for rookies/thin samples.
- **Distributions, not points:** **quantile regression** (P10/P50/P90) — this powers the consistency-vs-
  volatility *utility function* and floor/ceiling. **Calibrate with a bias-statistic analog.**
- **Done when:** per-player predictive distributions are calibrated and beat the Phase-1 baseline OOS.

### Phase 3 — Covariance + roster construction (the most direct reuse of your internship)
- **Player-week covariance** with **structured correlations** (stacks +, RB1/RB2 −, handcuff −) and
  **Ledoit-Wolf/QIS shrinkage** — *literally your intern estimators*. Optional **copulas** (Clayton/Gumbel)
  for handcuff tail-dependence.
- **Conditional-VBD** (value vs expected best-available at next pick) and roster floor/ceiling via
  `(w)ᵀ Σ (w)` — your tracking-error machinery, repurposed.
- **Done when:** rosters built with correlation awareness beat naive-BPA rosters in backtest.

### Phase 4 — North-star metric: season + playoff simulation
- Monte-Carlo the **full season + playoff bracket** from the predictive distributions + covariance; score a
  draft by **championship/playoff probability** (the layered-on north star). Add the **handcuff real-option**
  valuation and injury-games-missed distributions.
- **Done when:** title-probability ranking is stable and (ideally) beats both ADP and PAR-only drafting OOS.

### Phase 5 — The app (shareable for your league) — the v1 product
- **Backend FastAPI + DuckDB/Postgres; frontend Next.js + TypeScript.** Auth for your league-mates.
- **Pre-draft personalization layer** (the core differentiator): per-user **archetype prefs, per-factor
  over/under-weights, draft style, anchor picks** → each user gets a *personalized board* from the same model.
- **Live-draft companion:** manual pick entry first; then **Sleeper API** sync (Redis + WebSockets for live
  state). Recommend the next pick from current state via a **greedy conditional-VBD policy**.
- **Guardrail (from your reference doc):** always show the personalized board *next to* the pure-projection
  baseline, and flag large divergences as *hypotheses to test*, not biases to bake in.
- **Done when:** your league can run a live draft through it end-to-end with personalized recommendations.

### Phase 6 — (Stretch / only if it goes real-product) the chess/poker engine + paid data
- **MCTS draft engine** (AlphaGo-style: top-K branching, cheap rollouts, opponent models from prior league
  drafts) → **CFR** (poker AI; the true imperfect-information match). **Paid data (PlayerProfiler/FantasyPros)**
  only here. Everything before this must be solid first.

**Tech stack (free-first):** Python (`polars`/`pandas`, `scikit-learn`, `XGBoost`/`LightGBM`, `PyMC`/`numpyro`,
`statsmodels`), **DuckDB**, `nfl-data-py`, scrapers for FFCalculator/Underdog ADP; app = FastAPI + Next.js +
Redis + WebSockets. (R `nflfastR`/`brms` optional where better.) W&B free tier for experiment tracking.

---

## Part 8 — Key risks & pitfalls (pre-mortem)

1. **Overfitting to ~3,750 rows.** Mitigate: shrinkage, hierarchical priors, GBTs with nested CV, *few*
   factors. Use Marchenko-Pastur thinking to resist phantom factors.
2. **Backtest self-deception** (look-ahead, survivorship, in-sample selection). Mitigate: the `as_of` harness
   in Phase 0 — built *before* any modeling, exactly as your internship insisted.
3. **Baking in your own biases** via personalization. Mitigate: the baseline-vs-personalized guardrail.
4. **Data-freshness decay** through preseason (injuries/trades move ADP for months). Mitigate: scheduled
   re-pulls, probabilistic trade pricing, multi-source ADP (don't trust one).
5. **Live-draft integration is the hardest plumbing**, not the model. Mitigate: manual entry v1, Sleeper next.
6. **Expecting to beat consensus on raw points.** Reframe: the edge is draft decisions + roster construction +
   your league, not season-long clairvoyance. (The PCA-beat-factor lesson, again.)

## Part 9 — How you'll verify it works (end-to-end)

- **Harness self-test:** feed it a *known* method (pure ADP) → it should reproduce roughly average finishes;
  feed it perfect hindsight → it should win every time. (Sanity bounds, like your hard gate.)
- **Beat-the-baseline gate:** every modeling phase must **beat the prior phase AND ADP** on the walk-forward,
  with **block-bootstrap CIs** on the metric difference (your Phase-5.3 technique, ported) — not a single season.
- **Calibration:** P10/P50/P90 coverage matches realized frequencies (bias-statistic analog ≈ 1).
- **App acceptance:** run a **mock draft** (and then a real league draft) through the live companion; confirm
  personalized boards differ sensibly per user-config and the next-pick rec is conditional-VBD-correct.
- **Honest-verdict deliverable:** a short scorecard (method vs ADP vs baseline, CIs, stress seasons) — the
  fantasy analog of your intern write-up. If the model *doesn't* beat ADP, that's a publishable finding too.

## Part 10 — Open decisions before/while building

- League format to optimize first (stated baseline: **10-team full-PPR, 1-QB redraft**) — confirm before backtest scoring.
- Personalization granularity for v1 app (how many user-tunable levers to expose at launch).
- Which ADP sources to scrape first (FFCalculator historical + Underdog early best-ball are the free starting pair).
- When (if ever) to cross the paid-data / real-product line.

---

### One-paragraph answer to your core question
Yes — this is worth building, for learning *and* for a real (if modest) edge. The overlap with your
Alphathena work is near-total: you'd be reusing the same factor-model, covariance, shrinkage, and
*especially* the walk-forward/PIT backtesting discipline, plus the same personalization-at-scale product
shape. The honest edge is concentrated in **draft-day decisions and correlation-aware roster construction**,
not in out-predicting consensus on raw points — and your hardest constraint is the tiny sample, which is
exactly why the regularization habits you already have matter. Expect, and welcome, the possibility that a
simple baseline beats your clever model (it happened with PCA vs your factor cov) — proving that *honestly*
is the whole game. Build the model core first, wrap it in the league app, defer MCTS/CFR and paid data.

---

## Part 11 — Deeper: why "you won't beat ADP on raw projection," and the reframe (added 2026-06-29)

**Mechanism (why your factor model lost to PCA, and why it repeats here):**
- **Bias–variance under tiny `n`.** A more complex/structured model lowers *bias* but raises *estimation
  variance*. With ~3,750 player-seasons (vs your 16M stock-days), variance dominates — the extra structure
  adds estimation error faster than it removes bias, so it loses out-of-sample. PCA's top components are an
  *implicit regularizer*; your fundamental model's added structure was unforced error. **Same trap here.**
- **ADP is a strong ensemble baseline.** Consensus ADP aggregates thousands of sharp opinions — it's the
  *market price*, a wisdom-of-crowds estimator. Beating an ensemble on *average across all players* is as
  hard as beating the market; it's the wrong fight.
- **The footnote that is actually the strategy:** your "losing" factor model *still won on lower turnover* —
  a **secondary axis**. The entire plan below is: **stop competing on the headline forecasting axis you'll
  lose, and compete on the secondary axes you can win** — roster *structure*, *schedule*, *variance*, and
  *specific, persistent ADP biases*. You don't need to beat ADP on every player; you need to beat it on a
  *subset*, and to convert equal-or-slightly-worse projections into better *outcomes* via construction.

## Part 12 — Structural alpha: the tax-loss-harvesting parallel (the core reframe)

TLH produces ~1–2%/yr **orthogonal to whether you picked good stocks** — it's a *mechanical, low-variance,
compounding* edge that doesn't require beating the market, only managing a controllable drag while keeping
tracking error in check. **Fantasy has a direct analog: edges orthogonal to whether your projections beat
ADP.** These are more reliable than out-forecasting and are where the realistic, repeatable edge lives:

| Tax-loss harvesting (Alphathena) | Fantasy "structural alpha" |
|---|---|
| Harvest losses to offset gains; keep tracking error bounded | **Bench as a portfolio of real options** — handcuffs/contingent claims priced on injury optionality, not on out-projecting |
| Deterministic, compounding, low-variance | **Bye-week & schedule construction** — *guarantee* you never field a hole; deterministic, free |
| Wash-sale-compliant swap = same exposure, better tax | **Zero-cost swaps** — two picks with ~equal projection but better roster *structure* (correlation/floor/ceiling): take the structural one |
| Manage drag, not returns | **Variance management** — build the roster whose week distribution maximizes *win probability* given your scoring & seed needs (your `(w)ᵀΣ(w)` machinery) |
| Household-level coordination | **Draft-slot-aware strategy** — snake-turn dynamics; back-to-back picks at the turn enable tier-stacking |
| Ongoing rebalancing captures recurring value | **In-season streaming & waiver/FAAB** — the recurring "harvest" the static draft can't capture (QB/TE/DST streaming, vacated-opportunity pickups) |
| Backtested "1–2% tax alpha" headline | **Playoff-week (15–17) schedule optimization** — deterministic future-matchup info, ignored by most drafters |

**This is the headline edge claim of the product**, and it's backtestable with the Phase-0 harness:
*"even holding projections equal to ADP, structure/schedule/variance optimization improved expected finish /
title odds by X%."* That number is your "tax alpha" — and unlike forecasting, it's a *controllable* edge.

## Part 13 — ADP bias mining: exploiting an under-scrutinized market (a concrete early workstream)

**The key asymmetry vs your internship:** equity anomalies get *arbitraged away once published* (factor
returns decay post-publication; capital floods in). **ADP has no such correction** — it's recreational, low-
stakes, re-set every year with fresh narratives, and *nobody audits last year's ADP*. So biases that would
vanish in equities **persist** here. This is the one place the inefficiency works *for* you.

**Method (this is literally your intern cross-sectional factor-return regression, repurposed):**
1. Build a PIT panel: `(player, season)` → **pre-season ADP snapshot** (fixed date, no leakage) + **end-of-
   season finish** (points / positional rank).
2. Define **"ADP alpha"** = realized value − value expected at that draft slot (e.g. finish-rank minus
   ADP-rank, or points minus slot-replacement).
3. **Regress ADP alpha on features known *before* the season**: age, position, prior-year **TD rate**
   (regression flag), **rookie flag**, prior-year games-missed, **change-of-team / new-OC flag**, prior-year
   target/touch share, draft capital, ADP *source* (best-ball vs redraft), camp-narrative flags.
4. Features with **stable, significant coefficients across seasons** (walk-forward + block-bootstrap CIs,
   **never in-sample**) = exploitable biases. The dependent variable is just "beating ADP" instead of "stock
   return" — *identical machinery to `steps/phase2_factor_returns.py`.*

**Well-documented candidate biases to test first** (treat as hypotheses, *measure them yourself*):
- **TD-rate regression** — unsustainable prior-year TD luck → systematically *over*drafted; low-TD-luck → under.
- **Recency / anchoring on last year's points** (which are TD-inflated) → late-season heroes overdrafted.
- **Age-cliff underweighting** — RBs ~28–30 overdrafted relative to the cliff.
- **Vacated-opportunity underreaction** — beneficiaries of a departed teammate's targets/touches slow to be priced.
- **Coaching/scheme-change underreaction** — new OC / PROE shifts priced late.
- **Best-ball vs redraft divergence** — best-ball overpays for ceiling/variance; redraft for floor — a systematic, tradeable gap.
- **Rookie / draft-capital hype** — NFL draft capital overweighted regardless of landing spot/opportunity.
- **Positional dead zones** (QB/TE) and **SOS overweighting** early-season.

**Honesty caveats:** the *sharp* community already partially prices TD-regression/age/vacated-opportunity —
but your **casual league opponents do not**, and your edge is (a) measuring these precisely & PIT-correctly,
(b) *combining* them, (c) correcting for multiple-testing, and (d) re-checking decay (best-ball reshaped the
market). Backtest before believing.

## Part 14 — The draft-day "ambient widget": delivery form factors & feasibility

Goal: something that, on draft day, knows who's been picked and tells you what to do, from your pre-set
personalizations. **API-first beats screen-watching wherever possible.**

| Form factor | How it knows the picks | Feasibility | Notes |
|---|---|---|---|
| **Sleeper API sync (recommended core)** | Poll the public **draft API** — get picks directly, cleanly | **High** | No screen-reading at all. Most robust. Build this first. |
| **Browser extension (desktop web drafts)** | Read the **DOM** of the ESPN/Yahoo/Sleeper draft page directly | **High** | Far more reliable than OCR — the "watch the screen" vision, done right, for laptop drafters. |
| **Android floating bubble** | **`SYSTEM_ALERT_WINDOW`** ("draw over other apps") + **MediaProjection** screen capture → OCR (ML Kit/Tesseract) → fuzzy-match names → update state | **Medium** | This is the literal "widget in the corner" — Android *allows* overlays + screen capture (like chat-heads / live-caption apps). Fragile to per-platform UI changes; OCR name ambiguity (J. Jefferson). |
| **iOS** | **No draw-over-other-apps for third-party apps.** ReplayKit can capture screen (with permission) but not as a floating overlay over another app; PiP is video-only | **Low for the overlay dream** | Realistic iOS: **Live Activity / Dynamic Island** *displays* the rec, with **API sync or manual/share-sheet entry** feeding state. The corner-widget-reading-another-app is essentially not permitted. |
| **Second-screen companion (most robust universally)** | Draft on laptop, app on phone, **API or manual** sync | **High** | Cleanest UX; sidesteps all overlay/OCR limits. |
| **Manual entry (universal backstop)** | You tap who's gone | **Trivial** | Always works; the v1 and the fallback for hostile platforms. |

**Recommended path:** **manual-entry + Sleeper-API v1** → **browser extension** (desktop) and **Android
bubble + MediaProjection OCR** as the "ambient widget" once the engine is trusted → iOS via Live Activities +
API/manual. The recommendation policy is pre-loaded (personalizations set before draft day), so live it's just
*state-update → greedy conditional-VBD eval → display* — must return in well under your ~30–90s pick clock.
