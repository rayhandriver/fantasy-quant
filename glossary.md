# Glossary — fantasy-quant

Living reference for the fantasy + quant terms in this project. Updated as we complete steps (keep it
current — there is a standing memory note about glossary maintenance). New terms fold into the right
section, not just appended.

> **Last updated:** 2026-08-17 — **Session UI-3 terms** (bottom section: tag · queue · the
> workflow the old UI made impossible · the skip is rendered · `never` is inviolable · a
> recorded baseline for a deleted path · **step 2/A2:** the strip · one selection, one
> `pending_pick` · **the two positional ranks** · T39's slot · **step 3/A3:** quasi-bar ·
> polarity resolved before the renderer · the dual baseline · no reading, no bar ·
> **drawing a number asks what its maximum is** · the third tier, measured) and **bar-sheet comparator terms** (T41/T40/T55:
> board vintage stamp · gate leaf vs readout leaf · the pinned control · the room is an input ·
> constructed vs sampled control · an inert guard). _Previously:_ 2026-07-30 — **seat-map terms**
> (16.17 **BUILT**, 14.J still
> planned: seat map · k-of-n control · the positional-mapping smell · one draft is one observation ·
> bars have a scope, not just a value · **the poisoned control** · **a stale reference is not a
> control**). _Previously:_ 2026-07-27 — **the 2×5 mock-room terms** (bottom section: the 2×5 room · censored
> signal · the level-vs-shape family's fourth and first self-inflicted instance · inert weight · width
> without direction · reach budget · blind spot vs mis-weight · unsigned situation score · mandatory
> needs / roster-completion rule · a filter not a data gap · the choice-set contract's second home ·
> composition is not a model change). _Previously:_ 2026-07-26 — **Session G (2/2) terms** (curated-not-backtested · the review gate ·
> derived rows / curated claims · partial-coefficient reuse · nesting the functional form · two-sided
> nomination · velocity / ADP momentum · forward-only · commensurate units · elasticity · below the
> simulator’s resolution · censoring not dropping · crowding-out · run intensity · sweeping a free
> parameter). _Previously:_ **16.3b playcaller-regime terms** (play-caller vs HC vs OC · playcaller
> regime · head-coach scaffold + its 2024 limitation · `in_house` · move-graph cross-reference ·
> first-time play-caller · majority-season inclusion rule · **lineage fallback / mentor regime** ·
> `same_team` · fingerprint source) **+ 16.5 derived-event-board terms** (**derived-vs-curated**, the
> method split between the two reference tables · event type · room churn · `(unsettled)` quarterback),
> folded into the Phase-16 section.
> *(Prior: 2026-07-23 — **Phase-17 / 0.11 / Phase-14-surfacing terms** (bottom section, planned):
> League-Format Fidelity, superflex/OP, multi-flex, `LeagueSettings` contract, keeper effective-ADP inflation,
> ECR, Underdog ADP, run detection, decision-support surfacing (tier-cliff / roster-risk / uncertainty /
> playoff-SOS / draft-grade). *(Earlier same day: **Phase-16 opponent personalities** (planned 16.13–16.15):
> opponent personality vs archetype, the 5 headliners (Autopilot / Balanced / Upside Chaser / Safe-Floor /
> Homer-Narrative-Chaser), opponent-board enrichment, `signal_weights`, face-validity bar, mock-room
> composition. *(Same day earlier: **Phase-16 availability-drift terms** (planned 16.7–16.12):
> draft-slot drift, availability drift vs value alpha, ADP velocity/momentum (forward-only), source
> divergence, VBD-ADP gap (ECR proxy), correlated per-draft narrative shock, hype board, drift MAE. *(Same
> day: **player-view / app-card terms**: player card (hover
> overview) / player deep page (click-through), quasi-bar meter, green=good convention, dual-baseline bar,
> bargain bar, walled-off situation-change bar, confidence indicator.)* *(Prior: 2026-07-19 — **Session D terms**:
> MCTS / determinized-UCT (PIMC /
> SO-ISMCTS) / UCB1, the in-objective-vs-OOS-gain lesson, research gate, T5 pre-registration, dress
> rehearsal, lockbox eval.)* *(Prior: 2026-07-12 — **Session A terms**: adaptive archetype (implemented — fade-melt / slide /
> `adaptive_parent`), Phase-13 in-season section (weekly Kalman re-projection, `m0`/`p0`/`r`/`prior_weeks`,
> `process_var`, reserved news slot, set-and-forget vs co-pilot, mean-max lineup, lineup-grain variance tilt
> finding).)* *(Prior: 2026-07-11 (e) — **crawler league-seeding + real corpus terms**: iterative BFS snowball /
> `league:<id>` seeding, complete-draft quality filter, type-drift-safe upsert.)* *(Prior: 2026-07-11 (d) —
> Sleeper corpus-crawler terms: corpus crawler / participant expansion, `is_human` + human-vs-bot ADP,
> `sleeper_manager_profiles`, data appetite.)* *(Prior: 2026-07-11 (c) — step
> 0.10 Sleeper ingest terms: Sleeper draft ingest, `draft_id` vs the user endpoint, `picked_by`/`draft_slot`
> opponent identity, `human_slot`, `sleeper_mock` ADP board, `sleeper_tendencies` POC, DEF→`dst_team` bridge.)*
> *(Prior: 2026-07-11 — T3/T4 implemented: role-loss
> washout mixture — reformulated from the planned production haircut; cohort availability prior; weekly-spread
> correction κ; residual level bias.)*
> *(Prior: 2026-07-10 — audit / remediation terms: remediation register, role-survival haircut, cohort
> availability prior.)*
>
> **Prior update:** 2026-07-07 — added personalization-spine implementation terms (`base_value` =
> risk-adjusted value-over-replacement, reach budget / secured fraction, leave-one-out attribution).
> *(Prior: 2026-07-05 Phase-4 value terms — consensus two-track, VBD value board contract, draft-time
> replacement, rookie model, bias ratio / correction / survivorship haircut; 2026-07-05 Phase-3 feature
> terms — exposure matrix, TD-regression, winsor-z.)**

## Direct-indexing / personalization terms (reframe 2026-07-04)
- **Direct indexing (for fantasy)** — don't try to *beat* the benchmark (the optimal team); **track** it
  within a tolerance budget while layering on **personalization** and the in-season "tax-loss-harvesting"
  analog. Personalization is the objective; team strength is a tracked benchmark.
- **Tracking error (fantasy)** — the projected-value / championship-equity **gap vs the optimal team** from
  your seat; the quantity the cost report decomposes. (Equity analog: drift from the index.)
- **Cost-of-personalization report** — the signature metric: *"locking X and refusing Y cost ~N PAR and
  ~M% title probability vs the optimal build, per decision."* Prices indulgence honestly; lead with
  **relative/directional** cost.
- **Three signal layers** — the hard contract splitting "ADP" into **value** (consensus projections → VBD,
  *not* ADP order), **availability** (ADP + behavioral opponent model), and **variance** (our own
  distributions). The optimizer maximizes consensus-VBD value, plans around availability, dials variance.
- **Consensus-VBD value** — the value signal: external **consensus projected points** (e.g. FantasyPros
  aggregate) converted to **value-over-replacement**; the "best team" and cost numbers are computed from it.
- **Constraint / config object (`DraftConfig`)** — the single "custom index": league context, archetype,
  must/never lists + reach budgets, tilts (in rounds), risk dials, fandom/character/injury/rookie prefs.
  Every feature reads it; the three doors write it; the optimizer always gets a **complete** one.
- **Precedence chain** — how every configurable resolves so nothing is unset: *explicit user setting >
  inferred from league > implied by archetype > population prior.*
- **Three doors** — one config at three depths: **Autopilot** (2 choices), **Co-pilot** (5–7 dials),
  **Manual** (every slider).
- **Constrained draft optimizer** — maximize consensus-VBD value s.t. hard excludes + soft tilts +
  archetype + risk dial, planning around ADP availability (the AlphaThena tracking-error optimizer analog).
  *MVP built 2026-07-07 as a constrained greedy over the Phase-1.2 simulator (`draft/optimizer.py`).*
- **Risk-adjusted value-over-replacement (`base_value`)** — the concrete quantity the MVP optimizer drafts
  and the cost report sums: the Phase-5 **certainty equivalent** (mean − λ·Var) minus its own positional
  replacement level. VBD's cross-position comparability **and** the λ risk dial in one number; a player with
  no distribution falls back to plain Phase-4 VBD, a team defense to ADP.
- **Reach budget** — per must-draft player, how many *rounds early* you'll reach to secure him. The optimizer
  waits until the last responsible pick within budget — where ADP says he won't survive to your next turn
  (snake geometry + a noise margin) — so value is never wasted overreaching. **Secured fraction** = the share
  of mock drafts a must-player was actually landed (the reach-budget honesty readout).
- **Leave-one-out (LOO) attribution** — how the cost report splits the headline gap across preferences: drop
  exactly one constraint, redraft on the **same seeds**, and the value it recovers = that preference's cost.
  Sums to the headline only approximately (preferences interact) — reported honestly.
- **Behavioral opponent model** — replaces "ADP + Gaussian noise": models real drafter biases (positional
  runs, favorite reaches, hometown/name-brand bias, rookie hype, K/DST panic). Powers **availability
  distributions** (who's likely at each pick); **Brier-scorable** against real completed drafts.
- **Adaptive archetype** (implemented, spine step 6, 2026-07-12) — a preset (Zero RB, Hero RB, …) that
  **abandons the plan when the board breaks** (elite RBs slide → drop Zero RB). Concretely it is a
  *wrapper* on an `adaptive_parent` (`draft/config.py`: archetype `"adaptive"` + `_adaptive_tilt`) that
  **melts a *fade*** — a negative tilt like Zero-RB's early-RB fade — in proportion to how far a candidate
  has diverged from his ADP. **Slide** `= (overall_pick − adp)/n_teams` (+ = fell to us, − = a reach); the
  fade decays by `ADAPT_DECAY·max(|slide|, ADAPT_SLIDE_WEIGHT·max(0,slide))`, so value *actively sliding to
  us* melts the fade ~2× faster than a reach. A fade only melts toward 0 (never flips to a reach); a
  *reaching* archetype (positive tilt, e.g. `elite_te`) is untouched. With no board context it reproduces
  its parent exactly (the leave-one-out / benchmark path). **Validated:** does no harm on an ADP board and
  banks team-value when the board breaks (the realistic Phase-11 behavioral room) — see findings 2026-07-12.
- **Risk dial** — the floor↔ceiling (and correlation-appetite) control, powered by our per-player
  distributions; sets the value/variance tradeoff and the make-playoffs vs championship-or-bust objective.
- **Lockbox** — recent season(s) frozen and untouched during development; the final chosen stack is
  evaluated there **exactly once** (defends against in-sample model selection; PIT ≠ out-of-sample).
- **Calibration > edge** — the reframed bar: projections must be well-calibrated (reliability, coverage),
  not ADP-beating; a miscalibrated number is now visibly wrong to the user.
- **AI on the edges, deterministic core** — LLMs only turn fuzzy input → validated object or numbers →
  narrative; they never compute a number that must be correct. (All in-app AI deferred post-MVP.)

## Fantasy / draft terms
- **ADP (Average Draft Position)** — consensus draft cost of a player; the "market price." Sources differ
  (best-ball vs redraft vs dynasty) with systematic biases.
- **VBD (Value-Based Drafting)** — value = a player's projected points minus a positional **replacement
  level** (e.g. RB24 in a 10-team league). Turns cross-position points into draftable value.
- **Conditional-VBD** — value of a pick = points now − **expected best-available at your next pick**
  (expectation over the random draft order between your picks). The option-pricing flavor of VBD.
- **Points-above-replacement (PAR)** — the simpler headline backtest metric: expected starting-lineup
  points above replacement.
- **Replacement level** — the baseline a position is measured against (the last reliably-started
  player). Resolved for the 10-team 9-starter league (1.4): league-wide started = `n_teams × slot` with
  the FLEX split RB/WR/TE ∝ 2:2:1 → replacement ranks QB10 / RB24 / WR24 / TE12 / K10 / DST10.
- **Draft-time (projection) replacement** — for a *forward* value board, the replacement level is the
  **projected** points at each replacement rank, **not** realized (the season being drafted has no realized
  yet). Using realized by mistake zeros out VBD. (Phase 1.4's realized replacement is for backtest scoring.)
- **Consensus projection (two-track)** — Phase 4's value mean. *Live:* scrape the free **FantasyPros**
  consensus board, re-score its projected stats to **full-PPR with our own `RuleSet`** (same scale as the
  repo, not FantasyPros' scoring). *Historical:* the Phase-2 baseline as a documented **proxy** (no free
  historical/PIT consensus exists). One `consensus_projection(season)` dispatches; both yield
  `player_key·pos·proj_points`.
- **VBD value board (the contract)** — consensus mean → draft-time VBD → within-position + overall ranks,
  frozen as `player_key·pos·proj_points·source·vbd·pos_rank·overall_rank`. The single value object the
  optimizer maximizes and the Phase-5 distribution layer wraps.
- **Rookie value model** — a rookie has no prior production but has **draft capital + landing spot**; a
  per-position **ridge** on `log(draft_ovr)` + landing-spot environment fills rookies the mean misses
  (instead of punting to ADP). Draft capital is the dominant signal (earlier picks score more).
- **All-play / expected wins** — a schedule-independent record: each week you "win" the fraction of the
  league you outscore (ties half). Removes head-to-head schedule luck; the cheap proxy for finish until
  the Phase-10 season/playoff simulation.
- **Tier / comparative dropoff** — the gap to the next player at a position; steep dropoffs justify reaching.
- **Handcuff** — a backup (usually RB) whose value is contingent on the starter's injury — a **real option**.
- **Stack** — correlated teammates (e.g. QB + WR1) drafted together to raise roster ceiling.
- **RuleSet / scoring engine** — the configurable league ruleset (per-stat weights) that turns raw
  counting stats into fantasy points; the backtest scores every method on the *same* ruleset (1.1).
  Baseline: full-PPR, 4-pt pass TD, −2 INT/fumble, 9-starter QB/2RB/2WR/TE/FLEX+K+DST.
- **Points-allowed tiers (DST)** — the team-defense scoring band by points surrendered (shutout=10 …
  35+=−4); combined with sack/INT/fumble-recovery/TD/safety event points for a defense's weekly total.
- **Kicker distance scoring** — FG points by make distance (0–39=3 / 40–49=4 / 50+=5) + PATs; derived
  from play-by-play FG/XP events since kickers aren't in the offensive `weekly` table.
- **Snake draft** — draft order reverses each round (seats 1→N, then N→1), so pick value is roughly
  symmetric across seats; the simulator's `DraftState` tracks the serpentine order.
- **ADP-following opponent (baseline)** — opponents draft the lowest-ADP available player + Gaussian
  noise, respecting soft per-position roster caps; the simplest realistic draft-room model (richer
  Bayesian board inference is Phase 11.1).
- **Roster caps (soft)** — per-position ceilings that steer opponents off over-drafting a position
  while an under-cap alternative exists, but yield to best-available when supply is exhausted.
- **`rank_fn` (pluggable ranking method)** — the one-argument plug the walk-forward scores: given the
  PIT board (+ as-of context) it returns a draft-priority per player on the ADP scale (lower = sooner).
  Baseline = ADP; every later projection/valuation method is just a different `rank_fn`.
- **Optimal weekly lineup** — the max-scoring legal starting lineup from a roster's realized weekly
  points (fill each slot with its top scorers, FLEX with the best leftover RB/WR/TE); summed over the
  season it's the roster's realized value. Greedy is optimal for a single FLEX.
- **Survivorship guard** — score drafted rosters by LEFT-JOIN to realized points so a drafted-but-DNP
  bust counts as 0, never silently dropped (dropping flatters the backtest).
- **Structural alpha** — edge from roster/schedule/variance construction, *orthogonal to projection
  accuracy* — the tax-loss-harvesting analog. See `docs/STRATEGY.md` Part 12.
- **ADP alpha / ADP-residual** — how much a player out/under-performed their draft cost; the dependent
  variable in ADP-bias mining (Part 13).

## Feature / factor terms
- **Target share, snap share, route participation, carry/touch share** — opportunity/volume factors (the
  dominant predictors).
- **Air yards / aDOT / WOPR** — depth and weighted-opportunity measures.
- **YPRR (yards per route run)** — efficiency, relatively sticky for WRs.
- **YBC / YAC (yards before / after catch)** — splits receiving (and rushing) yardage into scheme/QB-driven
  (before) vs player-created (after); PFR advanced (0.3), available 2018+.
- **Broken tackles / drops / drop%** — player-created-value and reliability signals (PFR advanced, 2018+).
- **Pressure / blitz / hurry rate, on-target %** — QB-context advanced stats (PFR `pfr_pass`, 2018+).
- **TD-rate regression** — unsustainable TD luck mean-reverts; a key ADP bias.
- **Age curve (delta method)** — position-specific aging estimated from year-over-year deltas (Tango),
  robust to the selection bias of cross-sectional polynomial fits.
- **Exposure matrix `X`** — players × factors, standardized (z-scored), point-in-time — the fantasy analog
  of the intern repo's style-exposure matrix. Built by `features/exposures.py::build_exposures(target)`:
  production lagged to target-1, intrinsic as-of target, environment from the target-team's prior year.
- **TD-regression flag** — realized TDs minus **red-zone-opportunity-expected** TDs; positive = TD luck
  that mean-reverts (validated: corr −0.50 with next-year TD/game change). A key ADP-bias input (Phase 6).
- **Winsorized cross-sectional z (per position)** — clip a factor to its 2nd/98th percentile within a
  position, then z-score across that position's players in the as-of cross-section; the exposure-matrix
  standardization recipe (missing → group median before z, plus an explicit missing-indicator column).
- **`no_prior` / rookie intrinsic signal** — a player with no prior-season production (rookie / return) is
  flagged, not silently zeroed; their draft-capital + athletic + landing-spot exposures still carry signal
  (the reframe's "rookies must not punt to ADP").

## Modeling / quant terms (carried from the intern project)
- **Factor + idiosyncratic decomposition** — outcome = systematic factor exposure + player-specific alpha
  + noise (the `Σ = X F Xᵀ + D` shape).
- **Player-week covariance** — how players' weekly scores co-move (stacks +, RB1/RB2 −, handcuff −); drives
  roster floor/ceiling.
- **Shrinkage (Ledoit-Wolf / QIS)** — pull noisy sample covariance toward a stable target.
- **Hierarchical / Bayesian shrinkage** — pool thin-sample players (rookies, injury-returns) toward
  archetype priors.
- **Quantile projection** — model P10/P50/P90 directly (not just the mean) to get floor/ceiling.
- **Calibration / bias statistic** — realized ÷ predicted ≈ 1; do P90 weeks actually happen 10% of the time.
- **Bias ratio** — Σrealized / Σpredicted per position; <1 = optimistic. The value signal's headline
  calibration number (the reframe's real done-criterion — *calibration > edge*).
- **Correction factor** — deflate/inflate a miscalibrated projection by its bias (`corrected = pred·bias`)
  so Σreal/Σcorrected → 1: a documented miscalibration *corrected*, not just noted.
- **Reliability table** — bin players by predicted points; realized should climb monotonically across bins
  (rank fidelity) even if the level is off (which the correction factor fixes).
- **Conditional vs unconditional calibration (survivorship haircut)** — bias among players who *played*
  vs including projected-but-DNP as 0. The gap (~0.60 → ~0.46 for our proxy) is the injury/washout discount
  a draft board must respect; it's mostly games-played attrition, not mis-ranking.
- **Quadratic / expected-utility roster scoring** — concave utility for starters (floor), convex for late
  dart-throws (ceiling) — makes "consistency vs volatility" concrete.

### Phase 5 — distribution / risk-dial terms (2026-07-05)
- **Quantile regression** — fit a line per quantile τ (the pinball/quantile loss) to get P10/P50/P90 directly;
  our 5.1 is a per-position linear `QuantReg` of realized points on the calibrated mean, so the outer τ lines
  **fan out with level** (heteroscedastic spread — bigger projections have wider absolute outcomes).
- **Quantile crossing** — fitted quantiles that cross (P90 < P50 somewhere); repaired by sorting the τ values.
- **Conformalized quantile regression (CQR)** — a distribution-free correction (Romano 2019) that widens/shrinks
  an estimated interval by the empirical (1−α) quantile of the conformity score `E = max(q_lo−y, y−q_hi)` on a
  held-out calibration set, giving **≈(1−α) marginal coverage** even if the quantile model is off.
- **Empirical coverage** — the fraction of realized outcomes that actually land inside the stated interval;
  the calibration check for an "80% interval" (should be ≈80%).
- **If-healthy (conditional) distribution** — the season-points spread for players who play a near-full slate
  (weeks ≥ 0.85·season); injury attrition is modeled **separately** (5.4) and multiplied in, so downside isn't
  double-counted (mirrors conditional-vs-unconditional calibration).
- **Boom / bust rate** — share of a player's weeks clearing a position "great game" line (boom) or below a "dud"
  line (bust). A **consistency** signal; `corr(boom, CoV) ≈ −0.37` ⇒ boom rate tracks scoring *level*, a
  **separate axis** from volatility.
- **Coefficient of variation (CoV)** — weekly sd ÷ weekly mean; a scale-free volatility read (steady grinder vs
  boom/bust dart).
- **Discrete-time (survival) hazard** — a logistic regression on person-period (player-week) rows *is* a
  survival model; the right tool for a fixed 17-week horizon (vs. continuous-time Cox). Our 5.4 availability model.
- **Beta-Binomial games-played** — games played ~ Binomial(team_games, p) with an over-dispersion ρ (Beta-mixed
  success prob) so the count keeps a fat **lost-season tail** (injuries are lumpy — an ACL zeroes the year).
- **Availability multiplier / G_ref** — season points = if-healthy H × (a player's availability fraction ÷ the
  cohort's mean availability fraction G_ref ≈ 0.93); a typical-availability draw returns ≈ H.
- **Certainty equivalent (CE) / risk dial** — mean-variance `CE(λ) = E[Y] − λ·Var[Y]`; the single number the
  optimizer maximizes. **λ is the user-facing risk dial** (λ=0 risk-neutral; larger λ docks volatility). Slots
  into Phase-8 covariance unchanged (Var → portfolio tracking-error variance, same λ prices tracking error).
- **Risk premium** — `λ·Var`, the honest per-player **cost of uncertainty in points** (the reframe's promise).
- **CVaR (conditional value-at-risk)** — mean of the worst α-tail of the sample cloud; a downside-floor read for
  the narrative (not the ranking objective).
- **Role / depth attrition** — a projected player who never earns a snap (cut, buried on the depth chart) —
  realized ≈ 0. Distinct from **injury** attrition; the 5.4 availability model doesn't capture it, so the
  *unconditional* full-board interval under-covers (a documented Phase-5 limitation → future work).

## Betting-market terms (a sharper market than ADP — first-class data source)
- **Player prop** — a sportsbook line on a player stat (e.g. receiving yards O/U 62.5, anytime-TD). A sharp,
  real-money estimate of expectation — used as a feature, a projection anchor, and a calibration target.
- **Vig / juice** — the book's margin baked into the odds; must be removed before a line implies a fair probability.
- **De-vig** — strip the vig to recover fair implied probabilities/means (proportional, Shin, or power methods).
- **Implied team total** — points a team is expected to score (from the game total + spread); a top-tier
  opportunity proxy and a `features/environment.py` input.
- **Closing-line value (CLV)** — did your pre-season/pre-game read beat the market's closing number? A clean edge metric.
- **Win total / season prop** — season-long market on team wins or a player's season stat; a pre-season projection anchor.
- **Props-implied projection** — repackage a player's de-vig'd **season** prop lines (rec/rush/pass yds,
  receptions, TDs) into projected fantasy points via the league ruleset — the market's own forecast in
  our currency (2.3). Blocked on free data: historical preseason props are the paid gap.
- **Preseason market-data gap** — the confirmed free-data hole: player props are live-only (paywalled),
  win totals empty, and game lines are gameday-dated — so there is **no free pre-draft market signal**.

## Advanced / beyond-Alphathena terms
- **Ensemble-with-market** — blend your model with ADP + props + expert consensus via learned weights;
  shrink toward the market by confidence (don't fight it without a reason).
- **Conformal prediction** — distribution-free, *calibrated* prediction intervals; complements quantile regression.
- **Skill ÷ opportunity decomposition** — split production into a transferable player-intrinsic latent ×
  a team-conferred situation multiplier — the tractable core of causal "player-in-system".
- **Win-probability objective / leverage** — optimize P(playoffs/title), not variance; *raise* roster
  correlation & variance when behind (chase ceiling), *lower* it when ahead (protect floor).
- **CVaR / tail objective** — optimize a downside quantile instead of symmetric variance.
- **Bandit (explore/exploit)** — framework for in-season streaming / waiver decisions under uncertainty.
- **Opponent model** — a live Bayesian posterior over each league-mate's board, updated as picks reveal;
  enables *exploitative* (not Nash) draft play.

## Data-source / identity terms
- **nflverse / nfl_data_py** — the free, community NFL data ecosystem (play-by-play, weekly/seasonal stats,
  snaps, NGS, IDs, draft, combine). Our primary source (Phase 0.2).
- **`gsis_id`** — the NFL's official player ID and our **universal join key**; every source is normalized
  onto it (weekly/seasonal call it `player_id`, NGS `player_gsis_id`, snaps only carry `pfr_player_id` →
  mapped via the `player_ids` crosswalk).
- **`player_ids` (crosswalk)** — the Rosetta-Stone table mapping a player across ID systems (`gsis_id`,
  `pfr_id`, `sleeper_id`, `espn_id`, …); how sources that don't expose `gsis_id` get joined.
- **PBP (play-by-play)** — one row per play with rich context (air yards, EPA, personnel); the richest raw
  source, feeds opportunity/efficiency features.
- **Snap counts** — per-game offensive/defensive/ST snaps & share; the backbone opportunity measure.
- **NGS (Next Gen Stats)** — tracking-derived aggregates (separation, cushion, air yards, YAC over expected);
  the free aggregated tier (granular tracking data is paid).
- **`pulled_at`** — the ingest timestamp stamped on every store row; the foundation of PIT discipline.

## Discipline terms
- **Point-in-time (PIT)** — no post-as-of data may touch an as-of estimate.
- **Walk-forward / horse-race** — out-of-sample evaluation rolling through past seasons; the only honest test.
- **Look-ahead bias / survivorship bias** — the two classic backtest-inflators to design out.
- **Block bootstrap** — resample blocks of the realized-difference series for CIs that respect autocorrelation.
- **Stationary bootstrap (Politis–Romano)** — a block bootstrap with random geometric block lengths
  (expected ≈ n^{1/3}); `block=1` degrades to the iid bootstrap, so the two are directly comparable.
- **Effect size + 95% CI** — report the size of an edge and its uncertainty, not a single-season number;
  an edge is "real" only when its CI excludes 0 (the ship/no-ship gate vs ADP **and** the market).
- **Paired comparison** — score two methods in the *same* seeded draft contexts so the difference
  isolates the method (not draft-slot or opponent luck); the replacement level cancels in the difference.
- **Realized-PAR validation (spine step 4)** — does the *projected* personalization cost show up in
  *realized* points? Draft each archetype vs its benchmark on matched seeds, score realized optimal-lineup
  season points, block-bootstrap the per-season cost. Finding: on ~6 seasons it's noise-dominated (projected
  cost is a draft-day aid, not a season forecast).

## Phase 6 — ADP-bias mining terms
- **ADP-alpha** — how much a player's realized value beat (+) or missed (−) what their draft slot implied;
  the fantasy analog of a **factor return**. Our target is **value-over-replacement alpha** = realized VOR −
  ADP-implied VOR.
- **ADP-implied baseline (LOSO isotonic)** — the expected VOR at a given ADP positional rank, from a
  monotone (non-increasing) **isotonic** fit trained **leave-one-season-out** — never on the season it
  scores, so no outcome leaks into a player's own baseline.
- **ADP softness** — where ADP is systematically mispriced; the reframe reads a **positive** stable alpha for
  a trait as **under-drafted** (cheap/free to indulge a preference toward) and **negative** as over-drafted
  (costly to chase).
- **Durability under-pricing** — the one bias that survives FDR + stability: players who played more games
  *last* season beat their ADP (+14.6 VOR/SD, p_fdr≈0.001) — the crowd under-values availability.
- **Benjamini-Hochberg FDR** — controls the false-discovery rate when testing several traits at once; a raw
  5 % p-value is too generous across a family, so we FDR-adjust before calling a bias real.
- **Sign stability (walk-forward)** — the fraction of seasons a coefficient keeps its pooled sign; a bias
  that flips across seasons is not actionable regardless of its pooled p-value.

## Phase 8 — covariance & roster-construction terms (2026-07-09)
- **Relationship-typed correlation** — instead of a hopeless 500×500 sample covariance from 17 weeks, pool
  the weekly-point correlation of every same-team pair of one *kind* (QB1-WR1, RB1-RB2, WR1-WR2, …) across
  all training seasons; hundreds of pairs estimate one number. Cross-team pairs are 0.
- **Structural prior / EB shrinkage** — each pooled correlation is shrunk toward a documented folk prior
  (QB1-WR1 +0.40, RB1-RB2 −0.30) with weight `n_pairs/(n_pairs+κ)` — the Ledoit-Wolf bias-variance idea
  adapted to typed blocks. Data-rich relationships go empirical; rare ones lean on the prior.
- **Covariance hard gate** — no consumer ever sees a Σ that isn't finite, symmetric and PSD (the intern
  covariance gate, ported); assembly slippage is repaired by a diagonal-preserving eigenvalue clip
  (Higham-style — a player's own Phase-5 variance is never distorted).
- **Portfolio CE** — the roster-level certainty equivalent: `Σ base_value − 2λ·Σ_{i<j same team} ρσσ`.
  `base_value` already charges each player's own λ·Var; the cross-term charges (stacks) or credits (hedges)
  co-movement. The covariance-aware greedy's objective and the cost report's yardstick.
- **Marginal covariance penalty** — what adding player *j* to roster *R* costs beyond his own variance:
  `2λ·σ_j·Σ_{i∈R, same team} ρ_ij σ_i`. Mapped through the static value→rank curve so it moves a candidate a
  calibrated number of *picks* down the board.
- **Stack / hedge** — same-team pair with materially positive ρ (QB + his pass-catcher: higher ceiling,
  lower floor) / negative ρ (RB1 + RB2: higher floor). The risk profile names them per roster.
- **Iman–Conover** — impose a target rank correlation on independent Monte-Carlo marginals by re-ordering
  draws; every Phase-5 marginal (skew, conformal width, injury tail) is preserved exactly.
- **Clayton copula (rotated)** — a dependence structure whose mass concentrates in one tail,
  `λ_L = 2^(−1/θ)`; rotated 90° it expresses the handcuff direction (starter LOW ↔ backup HIGH), which a
  single Pearson ρ cannot. Fit from pooled Kendall τ on zero-filled backfield weeks.
- **Kendall τ** — rank-based dependence used to fit the copula (`θ = 2τ/(1−τ)` for Clayton); robust to the
  zero-inflated weekly point distributions.
- **Handcuff option premium** — the part of a backup's value that exists only because his starter might miss
  time: `G·p_out·ppg_standalone·(elevation_ratio − 1)`; priced with the 5.4 availability hazard.
- **Elevation ratio** — pooled multiplier on a backup's scoring when the starter sits (DEV estimate: 1.77,
  from 506 real starter-out weeks).

## Phase 6 wiring terms (2026-07-09)
- **Softness credit** — (your roster's durability exposure − the benchmark's) × the frozen scorecard
  coefficient, in VOR points; positive means your preferences tilted toward the under-priced trait and the
  raw projected cost overstates the real cost. Reported with the coefficient's CI.
- **Durability exposure** — a roster's summed z-score of prior-season games over its offensive players,
  standardized by the frozen DEV-panel μ/σ (the regression's own scale — never recomputed on a new season).
- **Net effective cost** — raw projected cost − softness credit; a separate, labeled line (*historical-bias
  estimate, not a projection*) under the untouched headline. Decision 2026-07-09: credit + net line, never a
  silently-moved headline.
- **Frozen signal + drift check** — the scorecard survivor is embedded as a constant with provenance
  (`adp/softness.py::DURABILITY`); the Phase-6 step script recomputes the scorecard and fails loudly if the
  frozen numbers drift > 5 % — computed-not-hardcoded, enforced.

## Stage 0 + Phase 10 — snapshot series & season-sim terms (2026-07-09)
- **Snapshot series** — the live season's ADP banked repeatedly over the preseason (vs 0.4's single
  late-preseason snapshot per historical year); each pull appends only new
  `(season, config, snapshot_date)` keys, so it's idempotent, and replays its own raw parquet cache, so a
  table rebuild can't lose it. `adp_asof` needs no change — it already takes the latest snapshot ≤ as-of.
- **Sleeper identity join** — Sleeper's own `gsis_id` field is sparse (~31% of draftables), but nflverse
  `player_ids` carries a native `sleeper_id` column: `sleeper player_id → player_ids.sleeper_id → gsis_id`
  covers **99.0%** of the draftable top-300 (probe 2026-07-09; mind the DOUBLE dtype and padded whitespace).
- **Top-down weekly disaggregation** — the Phase-10 weekly grain: draw **season totals** from the Phase-5
  clouds (Phase-8 Σ imposed board-wide via Iman–Conover), then split each draw across the player's active
  weeks; weeks sum exactly to the season draw, so all season-grain calibration survives by construction.
- **Dirichlet week shares** — active-week proportions drawn Dirichlet with concentration `α = 1/CoV²` from
  the player's own 5.3 weekly volatility: a boom/bust player's weeks fan out, a grinder's stay flat.
- **Correlation permutation** — Iman–Conover expressed as an index array instead of reordered values, so a
  companion array (each draw's games-played `G`) is permuted identically and every season draw keeps its
  own injury story for week placement.
- **LeagueFormat** — the league structure object (2026-07-09 decision: 10 teams, weeks 1–14 regular season,
  6-team playoff weeks 15–17, top-2 byes, reseeded semis, points-for tiebreak); the sim treats it as a
  parameter, so other formats drop in.
- **Exchangeable-league calibration** — the Phase-10 done-bar: draft many ADP+noise leagues on DEV seasons,
  predict each team's playoff/title probability preseason, then replay the same rosters and schedule on
  realized weekly points; calibration = Brier vs the format base rates (0.6/0.1) + reliability bins.
- **Variance leverage** — the 10.3 lever: a mean-preserving spread on a team's remaining weekly scores;
  trailing teams gain playoff probability from added variance (they need tails), leaders lose it (they need
  to protect the cut) — the DFS-GPP logic applied season-long.

## Audit / remediation terms (2026-07-10)
- **Remediation register** — `docs/TECH-DEBT.md`: the dated, stable-id (`T1–T8`) list of every known problem
  in the engine with the *exact* long-run fix, severity, and when-to-do; the "what's left to fix" source of
  truth, sequenced against the build in ROADMAP ★ THE PIPELINE.
- **Role-loss washout mixture (T3-B, done 2026-07-11)** — `injury.role_retention` +
  `distribution.sample_player_season`. The *implemented* T3-B, reformulated after the DEV diagnosis that the
  dominant unconditional miss is a projected body who **barely plays** (benched/buried/hurt), not one who
  plays but produces less. So role loss acts through the **availability channel**: a two-component season
  mixture where, with a tier-specific **washout** probability `p_crater` (played < 40 % of games), the games
  are drawn from a low `crater_avail` (≈0.15) *replacing* the normal hazard branch (not additive → injury not
  double-counted), and per-game production keeps only `keep_frac`. Applied to **established, deep-projected**
  players only (elite/starter washouts are injury, already in `G`). Fattens the games≈0 left tail without
  lowering the healthy `q90`. Supersedes the originally-planned production haircut `R`, which added ~0 coverage
  and hurt the conditional band. (Role tiers still keyed on `role_tier` vs the startable/replacement rank.)
- **Cohort availability prior (T3-A, done 2026-07-11)** — `injury.cohort_availability_prior`: instead of
  dropping sub-threshold players (`prior_games < 8`) to one league-median availability, give rookies/backups
  an availability mean **and dispersion `rho`** drawn from their `(pos × draft-capital tier)` cohort (hi = pick
  ≤ 100 overall), with `(pos,*)`→`(*,*)` backoff. Recovers the real split the median erased (hi-capital rookie
  RB plays 0.67 of games vs lo-capital 0.42, fatter `rho`). The **main** T3 lever: DEV unconditional coverage
  39 %→63 % on its own.
- **Weekly-spread correction κ (T4, done 2026-07-11)** — `weekly.SPREAD_KAPPA`, a per-position multiplier on
  the effective weekly CoV. The Phase-10 level bias is *not* stale CoV (per-player CoV is well-calibrated) nor
  the flat K/DST fallbacks (those run +16, slightly high) — it is **structural**: the mean-preserving Dirichlet
  week-split has tails too light to reproduce the weekly optimal-lineup **max** (a tail statistic), because a
  mean-preserving split caps weekly upside at the season total. κ inflates the effective CoV (mean-preserving,
  so season totals and Phase-5/T3 calibration are untouched) to restore the max. QB is a single mean-preserving
  slot so it barely responds → smallest inflation. Chosen on the DEV gate as the **highest κ that keeps every
  hard gate (Brier, stability, both leverage) passing** — a genuine trade-off (higher κ → more coverage/less
  bias but over-dispersion + broken dog-leverage).
- **Level bias (sim) — residual (T4)** — after κ, a residual level bias remains, concentrated in the
  early/COVID DEV seasons (2017/18/20 start ~−220/team at κ=1.0) and partly a **projection-level** shortfall κ
  cannot fix (κ is mean-preserving). Championship probabilities are relative within a league so they calibrate
  regardless; absolute-points and variance consumers inherit the residual. Fully closing it needs a
  non-mean-preserving weekly-upside term (breaks the Phase-5 sum invariant) or better early-season projections.
- **Scrape freshness/schema gates (T7)** — test-visible hard gates in `data/validate.py` that fail loudly
  when an external scrape rots: `adp_freshness_gate` (live-season FFC snapshot ≤ 6 days old — the CLAUDE.md
  §2 Stage-0 chore as an assertion), `board_size_gate` (FantasyPros board row-count band), `match_rate_gate`
  (gsis-match ≥ 95 %). Pure/injectable; fire only when the relevant live board is present.
- **Raw-payload archival (T7)** — `cache.archive_text` date-stamps each FFC/FantasyPros pull's raw JSON/HTML
  under `data/raw/**/payloads/` (gitignored, one file/day), so a broken scrape can be diffed against
  last-good shape. Best-effort: never sinks a pull.
- **Positional cliff (9.1 scarcity)** — `optimizer.positional_cliff`: for each player, the value drop to
  the `horizon`-th next-best available same-position player in the current pool. A steep cliff = a scarce
  tier that won't refill → addressing it is urgent; a flat tier ≈ 0 → safe to wait. Pure pool structure.
- **Survival probability / lookahead (9.4)** — `optimizer.survival_prob`: P(a player is still available at
  your next pick) = `Φ((adp − window_end)/noise)`, `window_end` = the last opponent pick before your next
  snake turn. Combined with the cliff as an **urgency** term `scarcity_w·cliff·(1−survival)` — scarce **and**
  vanishing = draft now. `scarcity_w=0` reproduces the covariance-only greedy.
- **Win-prob objective (9.5)** — the opt-in `winprob_pick_fn`: portfolio-CE/scarcity prefilter → top-k →
  finish the draft greedily per candidate → Phase-10 mini-sim → take the candidate that maximizes the
  routed metric. Makes `DraftConfig.objective` real: `make_playoffs`→`playoff_prob`,
  `championship_or_bust`→`title_prob`. Title is resolution-limited (needs ≥~200 sims/pick).
- **cached_distribution (T6)** — the memoized Phase-5 draw cloud both the draft value (`assemble_value`) and
  the season sim (`build_weekly_model`) read, keyed on `(season, ruleset, n_draws, seed)`, so they reference
  one joint set of draws instead of diverging by an accidental seed mismatch.
- **Sleeper integration (0.10 / T8b)** — the free public read-only Sleeper API is the source for the
  behavioral opponent model + a scaled ADP board. Everything is keyed off public IDs (username→user_id→
  leagues→drafts→picks; no auth). Identity via nflverse `player_ids.sleeper_id`→gsis (100 % of the drafted
  skill cohort). Full reference: **`docs/SLEEPER.md`**.

## Step 0.10 — Sleeper draft ingest terms (2026-07-11)
- **Sleeper draft ingest** — `data/sources/sleeper.py`: fetch draft metadata + pick-by-pick, gsis-join, and
  upsert `sleeper_drafts` + `sleeper_draft_picks` (idempotent by `draft_id`). Corpus intake takes an explicit
  list of `draft_id`s **or** discovers drafts from a `username`/`user_id` (real leagues); pure `parse_*`/
  `crosswalk`/`build_*` helpers + thin DB wrappers, so the parser is unit-tested offline against a fixture.
- **`draft_id` vs the user endpoint** — a Sleeper **mock** draft is reached only by its `draft_id` (in the
  board URL); it does **not** appear on `GET /user/<id>/drafts/...`. Real leagues *do* surface via that walk.
- **`picked_by` / `draft_slot` (opponent identity)** — a real league stamps each pick with `picked_by` (the
  manager's user_id — a **persistent identity** across drafts, the behavioral signal). A **solo-vs-bots mock**
  stamps `picked_by` for the **human's own picks only**; the 9 bots are null. So behavioral stats key by
  `picked_by` when ≥2 distinct managers exist (a real league), else by `draft_slot` (all a mock exposes).
- **`human_slot`** — from `draft_order` (user_id→seat); in a mock the single entry is the user, so `human_slot`
  tags which seat (and which picks, `is_human_slot`) were the human's.
- **`sleeper_mock` ADP board** — `build_mock_adp` aggregates pick numbers across the corpus into the exact
  **`adp_snapshots` contract** (`source="sleeper_mock"`: `adp`=mean pick, `stdev`, `high`=earliest, `low`=
  latest, `times_drafted`, `pos_rank`), so `adp_asof(source="sleeper_mock")` **and the draft simulator consume
  it with no code change** — the clean wiring point for drafting a live season against real draft behavior.
- **`sleeper_tendencies` (POC behavioral artifact)** — `build_tendencies`: per-drafter (slot or manager)
  positional cadence (`n_picked`, `avg_round`) + **reach** (`board ADP − pick_no`; +ve = drafted earlier than
  value). On a bot-mock corpus the ADP reference is that same corpus, so it's a plumbing proof-of-concept, the
  seed of the Phase-11 fit — which needs real-league `picked_by`, not mocks.
- **DEF→`dst_team` bridge** — a team defense's Sleeper `player_id` is the team abbr (no gsis); the crosswalk
  routes it to a `dst_team` key instead (matching the `_NON_GSIS_POS` D/ST convention), so DEF still boards.
- **Corpus crawler (0.10b/0.10c)** — `crawl_expand`: grow the draft corpus by **iterative BFS snowball**.
  Seed from usernames (walk their full `user→leagues→drafts` history), **`league:<id>`** (→ its drafts +
  members), and draft_ids; then **participant expansion** — every *human* draft found queues its `draft_order`
  managers, whose histories are crawled in turn, so one league fans out through co-managers until no new users
  or `max_drafts`. Rate-limited, dedups against the store. Seeds live in `reference/sleeper_seeds.txt`
  (`league:`/`draft:` prefixes). *A crawl reads **historical** leagues — all public in the API year-round —
  so it needs no live/in-season drafting; historical leagues also have realized outcomes (better for the Brier).*
- **Complete-draft quality filter** — a crawled corpus is ~44 % **abandoned drafts** (people quit mid-draft)
  plus auctions/linear. `sleeper_draft_picks` keeps everything (raw), but derived artifacts (ADP boards,
  manager profiles) use **complete snake/linear drafts only** (`_QUALITY_FILTER`). The integrity gate checks
  **no duplicate `pick_no`** per draft (a real corruption check); incompleteness is *reported, not failed*.
- **Type-drift-safe upsert** — `_upsert` does a full atomic rewrite (keep non-replaced rows, re-write union),
  so the heterogeneous corpus reconciles both schema drift and **column-type drift** (e.g. `league_id` first
  seen all-NULL → inferred INT, later a real string) — the append path would `ConversionException`.
- **`is_human` / human vs bot ADP** — a draft is `is_human` when ≥2 distinct `picked_by` (a real lobby/league)
  vs 1 (a solo-vs-bots mock). Human drafts build the **`sleeper_human`** ADP board, bots the **`sleeper_mock`**
  board — kept separate so Sleeper's *algorithmic* bot ADP never dilutes the *behavioral* human ADP the
  opponent model wants.
- **`sleeper_manager_profiles`** — the Phase-11 behavioral seed: per real manager across all their crawled
  drafts, per-position pick share + mean reach-vs-ADP + top NFL teams (crude fandom). Empty until real-human
  drafts are ingested; the input the opponent-model fit consumes.
- **Data appetite (Sleeper)** — board mean-ADP error ≈ σ_pick/√N (mid-round σ≈15 → N=20 ⇒ ±3–4 picks); a
  **Brier-verifiable opponent model needs ~50 real human drafts min, ~100–150 ideal**. Bot mocks add ADP only
  (cap ~10–20; FFC covers production ADP). Cheapest real-signal source = human mock lobbies + participant crawl.

### Phase 11 — behavioral opponent model
- **Behavioral opponent model** (`draft/opponent_model.py`) — the reframe's upgrade of "ADP + Gaussian
  noise": a model of *who each manager actually picks*, fit on real drafts and **Brier/log-loss-scored** on
  held-out picks. Keeps ADP as the dominant term, learns the human deviations (fandom, rookie hype, roster
  need, positional runs).
- **Conditional (McFadden) logit / discrete-choice model** — the estimator: at a pick, the manager chooses
  **one** player from the set on the board; utility of each candidate = β·features, and P(pick=p) =
  **softmax over the available candidate set** (not an independent per-player probability). Fit by MLE of the
  grouped-softmax negative log-likelihood; the gradient is `Xᵀ(softmax − chosen)`.
- **Candidate set** — per pick, the **top-K available-by-ADP** skill players (K=40; the realized pick is in-
  set ~100 %). Conditioning both models on the same set makes "behavioral vs ADP-only" a fair comparison;
  it also means absolute log-loss is high (≈ ln K) because the exact pick among K similar players is high-
  entropy — the **gain over ADP** (a proper-scoring rule) is the deliverable, not top-1 accuracy.
- **Tier-A / Tier-B features** — Tier-A (`adp`, position dummies, positional-run) are computable from any
  live `DraftState` board, so the fitted β also drives availability sim + mock opponents; Tier-B (`mgr_lean`,
  `rookie`, `fandom`, `need`) need manager/player metadata and are set to **0** (the exact "no info"
  marginalization, utility being linear) when unknown live.
- **Fandom (home-team reach)** — a manager drafting a player on one of their favorite NFL teams; empirically
  the **strongest** behavioral coefficient (+1.03). Note: `sleeper_manager_profiles.fav_teams` is stored
  **comma-separated** (`"CLE,MIA,DET"`), not JSON — parse with `.split(",")`.
- **Availability Brier** — the S4-owed metric: for each real draft window, predict P(each contested player
  still available at your next pick) and Brier-score vs realized. Behavioral **0.158** vs best-tuned ADP+noise
  **0.316** (default noise-5 is 0.419 — worse than a base-rate constant). Computed by MC-simulating the
  intervening opponent picks under the model (`draft/availability.py`).
- **Personality (mock opponent)** (`draft/personalities.py`) — a named tilt on the fitted β (scale/override a
  coefficient, softmax temperature, a round-dependent positional penalty) → a heterogeneous opponent
  (`chalk`, `zero_rb`, `reacher`, `homer`, …) pluggable into `simulate_draft` via the new `opponent_pick_fn`
  hook. Makes practice drafts feel like a real room.

### Phase 7 — opportunity-adjusted projection (dropped)
- **Skill ÷ opportunity decomposition** (`causal/decompose.py`) — production = a player-intrinsic **skill**
  effect (transferable) × a team-conferred **situation multiplier** (opportunity). Estimated as a **two-way
  fixed-effects (AKM) model** — the labor-economics worker/firm decomposition, here players/teams — on
  position-and-season-relative log-ppg; **movers identify the split** (a player seen in two situations pins
  down which part is his). Ridge-regularized ⇒ a *regularized estimate*, **not** an identified causal effect.
- **Situation swap (re-projection)** — projecting a mover by keeping his realized rate and swapping the team
  situation: `log opp_rate = log prior_rate − situation[old_team] + situation[new_team]` (non-movers get a
  zero delta ⇒ ≡ naive carry-over). The information-preserving form; the from-scratch reconstruction is worse.
- **Keep-or-drop gate** — Phase 7's exit criterion: keep iff **≥ consensus proxy overall AND strictly better
  on role-changers**, else drop. **Result: DROP** — the situation swap is a wash-to-worse than naive on movers
  (the team fixed-effect adds no exploitable move-signal; consensus already prices it).

## Phase 13 — in-season co-pilot terms (2026-07-12)
The draft is ~1 of 17+ decisions; the in-season engine re-estimates the same three signals weekly.
- **Weekly re-projection** (`inseason/reproject.py`, 13.1) — a **scalar Kalman filter** on each player's
  per-week scoring **level**. The preseason season-projection ÷ active weeks is the prior level `m0`, worth
  `PRIOR_WEEKS` **pseudo-observations**; each played week `y` updates `m ← m + k·(y − m)` with Kalman gain
  `k = p/(p+r)`, `r` the player's own 5.3 weekly observation variance. Output = a **rest-of-season** per-week
  mean/sd (`RestOfSeason`). Beats the frozen preseason level OOS (MAE, 6/6 DEV seasons).
- **`m0` / `p0` / `r` / `prior_weeks`** — Kalman initial state: `m0` the preseason per-active-week level,
  `r = (wk_cov·m0)²` the week-to-week noise, `p0 = r/prior_weeks` the prior variance on the level (a stronger
  `prior_weeks` trusts preseason more and updates slower).
- **`process_var`** — a random-walk term added to the level variance each week; `>0` lets **recent form
  outweigh** a hot September, `=0` is a pure "shrink preseason toward realized" update (the default).
- **News slot** (reserved) — a per-player level-shift argument on `reproject_week`, wired through the input
  contract now and a **no-op by default**, so a future **Phase-12** news/NLP feature plugs in without a
  rebuild (the 2026-07-11 build-before-Phase-12 design note).
- **Set-and-forget vs the co-pilot** — the two weekly lineups compared in 13.2: *set-and-forget* ranks the
  mean-max lineup by the **frozen preseason** level; the *co-pilot* ranks it by 13.1's **re-projected** mean.
  The co-pilot's edge (**+2.1 pts/lineup-week** OOS) is the whole 13.2 win — better means, ordinary lineup.
- **Mean-max lineup** — start the highest-**projected** legal lineup (dedicated slots first, FLEX takes the
  best leftover). The validated **default** start/sit (`optimal_lineup(objective="mean")`).
- **Win-probability / variance tilt (lineup grain)** — the opt-in `objective="win"`: score each player by
  `mean + lever·sd`, `lever` **+** as underdog (add variance, take a tail shot) and **−** when favored (cut
  it), size set by the H2H edge (`tanh`, `LEV_GAMMA/LEV_SCALE`), kept only under a do-no-harm guard. **Finding
  (2026-07-12): it does not beat mean-max OOS even for big underdogs** — a single legal swap barely moves the
  ~35-pt team sd (cf. Phase-10.3, where leverage only bit at *whole-team* 1.6× spread changes). Retained
  opt-in, **off by default** (the Phase-7 / props "kept, not the default" pattern).
- **FAAB / `faab_bid`** (13.3, `inseason/waivers.py`) — Free-Agent Acquisition Budget: a fixed season-long
  wallet spent in weekly sealed **first-price** auctions for waiver-wire pickups. `faab_bid` sets one bid from
  three forces — **marginal value** (rest-of-season points over replacement, from 13.1) → `value_scale` →
  willingness-to-pay; the **option value of budget**; **first-price shading**. The *pragmatic* bidder
  (`docs/TECH-DEBT.md` **T9**: rigorous auction theory owed to Phase 15.4). Beats naive %-of-budget 5/6 DEV.
- **Option value of budget / rationing** — a spent dollar can't win a *better* later pickup, so bids are
  shaded down early and freed at season's end. Encoded as `ration = 1/(1+OPTION_KAPPA·(weeks_remaining−1))`
  (→ 1 in the final week). The intertemporal-budget half of `faab_bid`.
- **First-price shading** — in a pay-what-you-bid auction you never bid your full value; you bid the
  surplus-maximiser `argmax_b (value−b)·P(win|b)` against a belief `opp_bids` about the field (else a flat
  `SHADE_FRAC`). The competitive half of `faab_bid`.
- **`n_useful` / diminishing returns (waivers)** — the FAAB sim scores only a team's **top-`n_useful`=4**
  realized pickups (limited startable slots; a 13th add rides the bench at ~0) and the sharp agent bids
  **marginal value over what it already holds**. Without this the objective rewards raw *volume* and naive
  aggression wins — the load-bearing modeling choice that makes budget scarce (finding 2026-07-12).
- **Mixed field (sim opponents)** — the 13.3 done-bar's opponent set: the sharp agent (seat 0) vs a naive
  bidder (seat 1) with the remaining seats alternating sharp/naive, so the edge is measured against
  *equally-sharp* opponents, not only fish (user decision 2026-07-12). No real FAAB transaction data exists
  (Sleeper corpus = draft picks only), so the field is synthetic — a relative sim result, not a Brier fit.
- **Streaming / `stream_pick`** (13.4, `inseason/streaming.py`) — not rostering one unit at a matchup-driven
  position (classically **DST**, a bye-week QB/TE) all year, but each week picking up whichever
  freely-available unit has the best matchup. A **contextual bandit** over the waiver pool: `stream_pick`
  starts the projected-best available streamer, keeping the currently-held one unless a challenger clears the
  `switch_margin`. Beats static-hold **6/6 DEV** on DST (+1.46 pts/wk).
- **`matchup_projection`** — a streamer's projected points = `own + (opp_allow − league_mean)`: the unit's own
  scoring level plus how much more (or fewer) points this week's **opponent offense** concedes to defenses
  than a league-average offense. Both terms are season-to-date rates **empirical-Bayes shrunk** (`_shrink`,
  `PRIOR_GAMES=4`) toward the prior season — the shrinkage is the soft **explore** (don't chase thin samples);
  the argmax is the **exploit**.
- **Static-hold vs matchup-streaming** — the 13.4 done-bar's two strategies: *static-hold* rosters the
  preseason-best waiver unit and starts it every week (eating its bye at 0); *matchup-streaming* starts each
  week's projected-best available unit. A third **random-streaming** control (a random available unit each
  week) isolates that the matchup *signal*, not just the churn, adds value (matchup beats random 5/6 DEV).
- **Switch margin / streaming hysteresis** — the transaction-cost knob (`SWITCH_MARGIN=1.0` pts): keep the
  held streamer unless a challenger's projection beats it by the margin. The 13.3 anti-churn lesson applied to
  13.4 — without it, the sim just rewards volume of waiver moves, not matchup skill.
- **Trade / market-making** (13.5, `inseason/trades.py`) — the one *cooperative* in-season move: both GMs
  must agree, so a completed trade helps **both** rosters. Possible because a team scores its optimal starting
  lineup, so a player's worth is his *marginal* starting-lineup value (a benched surplus is worth ~0). Trades
  arbitrage **complementary surpluses** — each side ships from a position it is deep and fills a hole.
- **`lineup_value` / `evaluate_trade`** — `lineup_value` = a roster's value counting only its optimal starting
  lineup (reuses the 13.2 greedy fill — the diminishing-returns lesson made positional). `evaluate_trade`
  prices a swap as the *change* in each side's `lineup_value`; `mutual` iff **both** gain more than
  `ACCEPT_MARGIN` (the anti-churn hysteresis).
- **`find_trades` / balanced ranking** — the market-maker: searches every opponent's surplus for mutual
  1-for-1 (and 2-for-1 consolidation) deals, keeping only ones that leave both rosters legal. Default
  `rank="balanced"` ranks by the **worse-off side's** gain `min(mine, theirs)` — the fairest win-win a
  two-signature trade needs (vs `rank="mine"`, a self-interested skim that only clears a marginal partner
  floor). The 13.3/13.4 anti-churn lesson: the objective must reward *mutual* benefit or the maker just skims.
- **Buy-low / sell-high (`edge`)** — when a **market perception** diverges from model value, `find_trades`
  tilts toward shipping players the market over-rates (sell high) and acquiring ones it under-rates (buy low);
  `edge` = the captured gap. A tiebreak on top of mutual benefit, not a substitute for it.
- **13.5 done-bar** — proposed trades **raise both teams' simulated playoff probability** in the Phase-10 MC
  season sim (not just the additive proxy). **6/6 DEV** seasons both sides' mean win% rises (maker +0.014→
  +0.021, partner +0.012→+0.021 playoff prob; season-block CIs > 0), vs a **random-trade control** that lifts
  both sides ~never — so it is the surplus *signal*, not roster churn. Value currency = preseason model ros
  mean (in-season this slot is 13.1's re-projected mean).

## Phase 12 — news / NLP (2026-07-13)

- **Exploitable lag** — the fantasy points a stale set-and-forget lineup loses by starting a player a
  structured news event has already flagged, measured against realized points (`news/event_study.py`).
  The "market" proxy the reframe leaves us (props shelved, no in-season ADP re-draft). **Injury lag =
  +5.86 pts/start, sig** (Out +8.4, Questionable +3.9); **depth-chart change does not separate** (DROP).
- **Availability multiplier** — the deterministic price of an injury status = `E[pts|status] / clean-week
  baseline`, calibrated on DEV (Out≈0, Doubtful≈0.01, Questionable≈0.56; `news/validate.injury_multipliers`).
  Fills 13.1's reserved `news` slot as a per-week level shift `level·(mult−1)`. The **core prices**, the
  **LLM only extracts** — the reframe guardrail literalized.
- **Extraction seam / gated `ClaudeClient`** — `news/extract.py` splits extraction (fuzzy text → a
  structured `ExtractedSignal`) from pricing (core). Default = an **offline rules extractor** (runs in
  tests, no network); the LLM path is a `ClaudeClient` (Haiku 4.5) gated behind `ANTHROPIC_API_KEY` +
  the `anthropic` SDK, invoked only when a caller passes it in → the core stays LLM-free. `structured_
  injury_signal` is the deterministic, validatable historical path (the injury feed already IS structured).
- **News keep-or-drop gate (12.4)** — walk-forward: does a news-aware weekly forecast beat the injury-blind
  13.1 forecast on realized points? **On the designated subset (where it applies): +3.4→4.3 pts/pw, 6/6
  DEV.** A qualified KEEP (injury) + a DROP (depth) — the gate saying a *conditional* yes.

## Phase 15 — multi-format + auction (2026-07-13)

- **Auction value** — VOR expressed in dollars: every rosterable player costs ≥ `$min_bid`, the surplus
  budget (total wallets − $1/slot) split ∝ VOR, so studs soak the money and the last slots go for $1
  (`draft/auction.auction_values`). Replaces 13.3's fixed points→$ `value_scale`.
- **$1 endgame / `endgame_cap`** — the exact budget-state (stochastic-knapsack) continuation constraint:
  never bid so much you can't still fill every *other* remaining slot at $1 → `budget − $1·(slots−1)`.
  The rigorous continuation value the pragmatic FAAB bidder lacked; **T9 discharged** — `faab_bid` now
  consumes it (`slots_remaining`).
- **Winner's-curse-aware bidding** — you only win when everyone else drops (evidence your estimate was
  high); shade the max bid toward the field. In an English (pay-second-price) auction the load-bearing
  skill is bidding *marginal* value (value to your own roster — a 4th RB is worth $1 to a full backfield)
  under the endgame cap; `draft/auction.auction_bid`. **Budget-state bidder beats naive budget-splitting
  6/6 DEV, +66→+128 lineup pts.**
- **Variance is good in best-ball** — best-ball auto-keeps each week's boom and discards duds, so the
  weekly total is **convex** in a player's spread — the exact **mirror of the 13.2 managed-lineup finding**
  (variance hurt there, forced to start). A ceiling-aware drafter (`mean·(1+κ·wk_cov)`, κ=0.1, **weekly**
  CoV not season sd — season sd carries injury downside and lost) beats mean-only 6/6 DEV, +37→+104 pts/szn.
- **Leverage vs chalk (DFS GPP)** — in a top-heavy field you win by being *different and right*: the field
  duplicates chalk (projection-max) so it splits its prize; a contrarian **leverage** lineup (`proj·(1−λ·
  own)`, fading high-owned studs) is unique and keeps it. The mechanic is **prize-splitting among duplicate
  lineups**. **MECHANICS only** — no free DK/FD salary or ownership feed (the props gap), so salaries are
  synthesised (monotone in weekly projection) and ownership modeled (projection-driven); not Brier-validated.

## Session D — MCTS research gate + lockbox terms (2026-07-19)
- **MCTS (Monte-Carlo Tree Search)** — a search that estimates each move's value by many random
  playouts, growing a tree biased toward promising branches. Here (`draft/mcts.py`) it searches snake-
  draft states: actions = the **top-K greedy candidates**, rollouts = the greedy policy, leaf value = the
  roster's **portfolio CE** — so it searches *on top of* the greedy it is benchmarked against.
- **Determinized UCT / PIMC (perfect-information Monte-Carlo) / SO-ISMCTS** — the technique for an
  imperfect-information game (you don't know opponents' boards): each search iteration **determinizes** the
  chance (samples one ADP+noise room), turning the draft deterministic for that iteration; candidates an
  opponent happens to take simply don't appear that iteration (availability handling). Averaged over
  iterations it approximates searching the real stochastic game.
- **UCB1 selection** — the tree's explore/exploit rule: pick the child maximising
  `mean_value + c·√(ln N_parent / n_child)`. Leaf values here are on the VBD-points scale, so the
  exploitation term is **min-max-normalised** over the values seen in the search to make `c` meaningful.
- **In-objective vs out-of-sample gain (the MCTS gate lesson)** — a search can beat the greedy on **the
  objective it optimises** (MCTS: Δ portfolio CE **+77**, sig) yet **not** on **realized OOS outcomes**
  (Δ realized **+32**, CI∋0). When the objective's link to reality is noisy (a near-perfect-info snake
  draft + a model edge unresolvable on ~10 seasons), harder optimisation buys no realized edge → **DROP**.
  The same shape as the 9.5 title-objective resolution limit, made a keep-or-drop verdict.
- **Research gate** — an *explicit-decision* build step (MCTS / self-play RL, before the lockbox): build
  the benchmark, measure it against the incumbent policy, keep-or-drop. CFR stays dropped (a snake draft is
  ≈ perfect-information — a category error for regret minimisation).
- **T5 pre-registration** — freezing the *exact* stack + the *exact* metrics in a dated, committed block
  **before** the one-shot lockbox eval, so nothing is chosen post-hoc; plus a **running count of DEV
  selection decisions** (≈35–40) so a marginal held-out number is read with the right multiple-testing
  skepticism. PIT-clean ≠ out-of-sample-clean.
- **Dress rehearsal** — running the *assembled* system against the **2025 calibration holdout** before the
  lockbox, so the lockbox isn't the system's first contact with unseen data. Board-free here (2025 has no
  10-team ADP board): projection calibration + distribution coverage.
- **Lockbox eval** — the single, irreversible evaluation of the frozen stack on the held-out seasons
  (**2023+2024**), reported **as-is** (`steps/lockbox_eval.py`, `analysis/lockbox_eval.json`). Spending it
  twice destroys the external-validity claim it certifies.

## Player-view / app-card terms (2026-07-23, spec `docs/PLAYER-VIEW.md`)
- **Player card (hover overview)** — the glanceable card shown when a user *hovers* a player on a board:
  **5 quasi-bars** (impact, upside, downside, injury, bargain), each a **bar + a number**, no prose. The
  *draft-now* read, deliberately not exhaustive.
- **Player deep page (click-through)** — the dedicated per-player route (`/player/<key>`) opened on
  *click*: **all 8 bars** with numbers **and** a one-line plain-English "why," plus a weekly-distribution
  band, situation context, opportunity breakdown, and a limitations footer. The scouting-report tier. The
  hover→page split is the "simple **yet** detailed" resolution.
- **Quasi-bar / meter** — a three-tier (green/yellow/red) bar rendering one per-player trait read off a
  frozen contract; length and color track the same scale. Not a chart axis — a glance meter.
- **green = good (bar convention)** — green/large **always** means "good for the drafter." Risk traits
  (injury, downside) are **inverted** so a durable, high-floor player shows a big green bar, not a big red
  "risk" bar. One consistent reading everywhere: more green = more you want him.
- **Dual-baseline bar** — every bar carries **two** percentile references: **overall** (vs the whole
  draftable pool) as the primary/top fill, and **within-position** (vs same-position peers, "top-15% at
  WR") as the secondary marker/label below. Overall keeps cross-position slot comparisons honest;
  positional gives the "great for a TE" read. (User decision 2026-07-23.)
- **Bargain bar** — the draft-cost value meter: `value_board.overall_rank` vs the ADP-board rank ("+1.5
  rounds of value"). Draft-cost is its **own bar**, kept separate from the trait bars (which grade the
  trait, not the price).
- **Situation-change bar (walled-off)** — the deep-page-only bar fed by Phase 16 (team/QB/competition/
  scheme change). Renders **visually distinct + tagged "directional context — not a calibrated
  projection,"** never feeds a cost/value/impact number or the optimizer. Scouting color, not a rec — the
  UI literalization of Phase 16's unvalidated, read-only status.
- **Confidence indicator** — a card/page marker on rookie / `no_prior` / `source=proxy|rookie` players,
  whose estimates are genuinely softer ("thin data — read the bars as wide"), so a shaky estimate is never
  shown with false crispness. The UI analog of the engine's calibration discipline.

## Phase 16 value-side — the coaching/scheme table (2026-07-24, 16.3/16.3b/16.4)
- **Playcaller regime** — a `(team, season, play_caller)` tuple: *who actually called the offensive plays*
  for that team that year. The atomic unit of `reference/coaches.csv` and the thing 16.4 fingerprints. Not
  the same as head coach — **`pbp.home_coach`/`away_coach` gives head coach only**, which is why this table
  has to be curated by hand (though pbp is a valid free **scaffold** for the `head_coach` column across all
  352 team-seasons 2014–2025).
- **`in_house` (the frozen flag, semantics verified 32/32 on 2026-07-24)** — *"the season's play-caller was
  already on this team's staff the previous season."* Replaced the earlier `change_from_prev` (user decision
  2026-07-24, which **dropped** that column). **`in_house=0` ⇒ a new playcaller regime ⇒ a 16.4 transport
  event** (13 of 32 teams in 2026). **Caveat that matters:** it is **sufficient but not necessary** — an
  *internal promotion* is `in_house=1` yet still a new regime (DEN 2026: Payton hands the offense to Davis
  Webb, already the QB coach; PHI and WAS are the same shape). With `change_from_prev` gone, 16.4 must
  handle those explicitly rather than keying purely on `in_house=0`.
- **Scheme fingerprint (16.4, BUILT 2026-07-25)** — a play-caller's 14-metric signature: team tendencies
  (`pass_rate`, `early_down_pass_rate`, `plays_pg`, `rz_pass_rate`, `team_adot`) plus the role-share split
  (WR1/2/3 and TE1 target share, RB target share, RB1/RB2 carry share) plus **concentration** (`tgt_hhi`,
  `carry_hhi`). Every metric is **z-scored within season** before aggregation — league drift in pass rate
  and pace must never read as a coach's personality — then **EB-shrunk** by regime length. 41 play-callers
  / 64 spells over 169 regime-seasons.
- **Trait stability / the EB constant `k` (16.4)** — `k = σ²/τ²` (within-coach season noise ÷ between-coach
  spread), estimated by method of moments; a regime of `n` seasons keeps weight `n/(n+k)`. **`k` is itself
  the finding** — it measures how much of a trait a coach *carries between jobs*. Most portable:
  `rz_pass_rate` (1.7), `team_adot` (1.8), `plays_pg` (1.8), **`carry_hhi` (2.0)**. Least portable:
  **`wr1_tgt_share` (17.9)** — the alpha receiver's target share is a **roster fact, not a scheme fact**.
- **Transport (16.4)** — reweighting a new team's *current* personnel by an *incoming* playcaller's
  historical fingerprint. Structurally adjacent to 7.3's rookie transport but a distinct hypothesis:
  scheme-specific, not a blunt team fixed-effect. **Ships descriptive-only, explicitly unvalidated** — no
  FDR gate, no edge claim; the done-bar is "computes correctly and is honestly labeled."
- **★ Reversion vs. scheme split (16.4)** — the honesty decomposition on every player row:
  `delta_pp = reversion_pp + scheme_pp`, where `reversion_pp = league_mean − team_prev` (what *any* hire
  would produce as the incumbent slot regresses) and `scheme_pp = z × sd` (**the only part the fingerprint
  actually claims**). Measured 2026: scheme is just **20.9 %** of the movement, reversion **79.1 %** (mean
  |1.53| pp vs |5.77| pp). Reporting the total alone would overstate the phase ~5×. Generalizable pattern:
  when a "predicted change" is mostly regression to a mean, say which part is which.
- **Partial-regime window (`PARTIAL_WEEKS` / `UNRESOLVED_PARTIAL`, 16.4)** — six seasons where the listed
  play-caller only called part of the year are cut to **the weeks he actually called** (specs resolve
  against weeks the team *played*, so a bye never shifts a boundary); three more are flagged but too vague
  to pin and are **dropped rather than guessed**. Averaging two coaches' games into one fingerprint is the
  easiest way to make the module lie.
- **★ Silent-join failure (the LA/LAR lesson, 2026-07-25)** — `pbp`/`weekly` write the Rams as `LA`,
  `reference/coaches.csv` as `LAR`, so 16.4's first run **deleted Sean McVay's entire nine-season tenure**
  and reported it as an ordinary empty result. **A missing coach and a failed join look identical.** Two
  durable rules: route every cross-source team comparison through `adp.panel._canon_team`, and make
  "dropped with no stated reason" an **assertion failure** (`fingerprint.assert_regime_coverage`) rather
  than an empty row.
- **Move-graph cross-reference** — the review technique that caught every error in the drafted 2026 coaching
  table **without a single external lookup**: each "X departs" claim in one row must be matched by an "X
  arrives" claim in another, and the flags must agree with the prose. Found 4 hard contradictions, 3
  incoherent notes and 2 cycle-stale rows. **Reuse for 16.3b and any future curated reference table.**
- **Signed-off-with-flags** — the honest sign-off pattern used for 16.3: the table is accepted at
  `confidence=high` *and* the specific claims that were **never externally verified** are recorded alongside
  it (for 2026: the 10-new-HC count, McDaniel MIA-HC→LAC-OC, the 56 % HC-playcaller rate). Internal
  consistency ≠ factual accuracy; writing down the boundary of what was checked is part of the artifact.

## Phase 16 availability-drift terms (2026-07-23, planned 16.7–16.12, spec `PROJECT.md` §5)
- **Availability drift (draft-slot drift)** — how much *earlier or later* a player is actually **drafted**
  than his consensus ADP, `drift = actual_draft_slot − preseason_ADP` (negative = drafted earlier / reached
  for). The **availability**-signal phenomenon: media narrative / changed circumstance (the McConkey case)
  makes drafters reach, so the player is gone before his ADP says he should be. **Distinct from value alpha**
  (Phase 6 / 16.1–16.6), which asks whether he *out-earns* his ADP in realized points. A player can drift
  early (hyped) without any real value alpha, and vice-versa.
- **Value alpha vs availability drift** — the two sibling mispricings this project separates. *Value alpha* =
  realized VOR − ADP-implied VOR (is the price wrong about how *good* he is?). *Availability drift* = draft
  slot − ADP (is the price wrong about how *early he goes*?). Phase 16 now mines both: 16.1–16.6 value,
  16.7–16.12 availability.
- **ADP velocity / momentum** — the slope of a player's ADP across a within-season snapshot **series** (rising
  = the market is moving him up, i.e. narrative already being priced by other drafters). The most direct
  "media already moved it" signal. **Forward-only:** only the Stage-0 2026 series is a true time series;
  historical FFC is one ~Sep-1 board/season, so momentum is **not backtestable** and is validated live on
  2026 (16.11).
- **Source divergence** — the gap between a *public* ADP board (FFC) and a *sharper* one (`sleeper_human`).
  A player much earlier on the sharp board is a **leading indicator** the public will over-draft him as it
  catches up. A market-derived, backtestable narrative proxy (16.8).
- **VBD-ADP gap (ECR proxy)** — `value_board.overall_rank` minus the ADP-board rank: "our projections rank
  him well ahead of where he's drafted." A free stand-in for the classic **expert-rank-minus-ADP** value gap,
  since we store projections (points), **not** FantasyPros' expert *rank* (ECR). Computable historically →
  the backbone drift feature (16.8). *(A true-ECR scrape is optional future work, live-only.)*
- **Correlated per-draft narrative shock** — the simulator fix for the user's key insight: sampling each AI
  opponent **independently** understates clustering, so a hyped player *always* falls to you. Instead draw
  **one shared hype shock per simulated draft**, applied to every opponent, so a hyped player goes early
  **consistently within that draft** — reproducing the realized cross-draft **dispersion** of a player's
  slot (some drafts he's gone early, some he lasts), i.e. the "sniped by a like-minded drafter" outcome (16.9).
- **Hype board** — a small, hand-maintainable override table (`reference/hype_board.csv`: `player_key ·
  pick_delta · note · source`), Claude-web-research-drafted + **user-reviewed before use** (same contract as
  the 16.3 playcaller table), capturing the **qualitative** narrative residual pure market signals miss.
  Applied as a bias on opponent utility / survival on top of the quantitative drift signals; live-season,
  curated, explicitly **not** a backtested claim (16.10).
- **Drift MAE / drift Spearman** — the own held-out metric for the availability-drift model: mean-absolute
  error (and rank correlation) of predicted vs realized `drift` on the Sleeper human corpus, walk-forward,
  vs a naive `drift = 0` baseline. The "does it actually predict who gets over-drafted?" gate (16.8), the
  availability analog of Phase-6's VOR-alpha scorecard.
- **P(available at your pick) / reach-risk readout** — the honest app surfacing (16.12): instead of a
  yes/no "he falls to you," report the **probability** the player survives to your next pick (from the 11.2
  availability oracle, drift-adjusted), plus a reach-risk flag ("going ~1 round early in sharp drafts —
  consider reaching"). Sets expectations with a number, directly defusing the "fell in 10 mocks then got
  sniped" bad experience.

## Phase 16 — opponent personalities (2026-07-23, planned 16.13–16.15, spec `PROJECT.md` §5 / `BUILD_PLAN.md`)
- **Opponent personality** — a named, interpretable **tilt on the fitted behavioral opponent model** used to
  make a mock-draft room *heterogeneous* (`draft/personalities.py`, Phase 11.3). **Distinct from an
  archetype** (`config.py`): an archetype is the *user's own* draft strategy; a personality is *another seat*
  in the room. Existing six (`balanced`, `chalk`, `zero_rb`, `reacher`, `homer`, `rookie_hawk`) tilt only on
  ADP/behavioral features; 16.13–16.15 add **risk/value** personalities.
- **The 5 headline personalities (16.14)** — the curated set surfaced in the app: **Autopilot** (deterministic
  lowest-ADP-available — the literal Sleeper autopick, "BPA every time" in the *ADP* sense), **Balanced** (the
  fitted average human), **Upside Chaser** (ceiling — tilts to `boom_prob`/`q90` + youth, punts floor), **Safe
  / Floor** (floor/durability — tilts to `q10`/`games_played_mean`/DURABILITY, low `bust_prob`, veterans), and
  **Homer / Narrative-Chaser** (favorite-team `fandom` + hyped names off the 16.10 hype board — the seat the
  16.9 narrative shock rides through). *(Value-BPA was considered and cut — user chose "ADP autopilot only,"
  no value-board opponent.)*
- **Opponent-board enrichment (16.13)** — attaching the frozen, **read-only** Phase-5 distribution
  (`boom_prob`/`q90`/`bust_prob`/`q10`/`games_played_mean`) + `value_board` (`vbd`/`overall_rank`) fields to
  the sim board, so risk/value personalities have signal to tilt on (the live board otherwise carries only
  `adp`/`pos`). No modeling change.
- **`signal_weights` (personality term)** — the new `Personality` field that lets a personality add a linear
  bonus/penalty on the *enriched* columns (e.g. Upside Chaser `+boom_prob`, Safe `+q10 −bust_prob`), beyond
  the existing β-scale/override/temperature/early-pos-penalty tilts.
- **Face-validity bar (personalities)** — the validation the user chose for 16.14: verify each personality
  drafts *sensibly* (Upside skews young/high-`q90`, Safe durable/high-`q10`, Autopilot pure ADP order, Homer
  reaches for `fandom`/hype) + unit-test the tilt mechanics — **no corpus Brier gate** (a realism/UX feature,
  unlike the walk-forward-gated 16.7/16.8 drift model).
- **Mock-room composition (16.15)** — the configurable assignment of the 9 opponent seats to personalities (a
  default realistic mix, user-overridable), plus the coupling that routes the 16.9 per-draft narrative shock
  through the Upside/Homer seats, plus the Phase-14 app selector.

## Phase 17 / 0.11 / Phase-14 surfacing terms (2026-07-23, planned — spec `PROJECT.md` §5 / `BUILD_PLAN.md`)
- **League-Format Fidelity (Phase 17)** — making the engine give **correct** advice for *any* league, not just
  the vanilla 10-team full-PPR 1-QB it hard-codes today. A **config generalization, not a modeling change** —
  the lockbox-validated default stays valid; non-default formats are supported but **labeled
  not-lockbox-validated** (the eval was one format). Broadly helps *every* non-vanilla user.
- **Superflex / OP slot** — a lineup slot that can start a QB *in addition to* the dedicated QB slot (OP =
  "offensive player," QB-eligible). It roughly **doubles QB demand** and lifts QBs into the early rounds —
  which today's fixed `RosterSlots.qb=1` / single-FLEX solver gets **silently wrong** (17.1 fixes it).
- **Multi-flex** — more than one FLEX slot (e.g. 2 FLEX, or a superflex + FLEX). `simulation/season.py`
  currently raises `NotImplementedError` for `flex>1`; 17.1 generalizes the vectorized optimal-lineup solver.
- **`LeagueSettings` contract (17.3)** — the **platform-agnostic** object a user's league maps onto (built from
  a manual form — presets *or* full custom: scoring values, roster positions, superflex, no-kicker, team/bench
  count), which the engine turns into `RuleSet` + `RosterSlots` + `LeagueFormat`. Deliberately **not** tied to
  Sleeper/ESPN/Yahoo (users hand-enter); optional platform auto-import is a secondary future convenience.
- **Keeper (effective-ADP inflation) (17.4)** — a keeper league **removes kept players from the pool** and
  **re-inflates everyone else's effective ADP** (the board shifts up); a keeper's cost = the forfeited pick.
  The nearer-term subset of the deferred Phase-15.1 dynasty.
- **ECR (expert consensus rank)** — FantasyPros' expert *ranking* (distinct from the projection *points* pages
  `consensus.py` already scrapes). The *true* expert-rank-minus-ADP signal that 16.8 currently proxies with the
  VBD-ADP gap; ingested by **0.11**, live-only.
- **Underdog ADP** — the sharp best-ball market's ADP (deferred back in Phase 0.4). The cleanest
  `source_divergence` input for 16.8 and the realistic board for best-ball (15.2); ingested by **0.11**.
- **Run detection (16.16)** — mid-draft, spotting a **positional run** (elevated recent pick-rate for a
  position vs its ADP-implied rate) and reactively updating the room's availability forecast live ("RBs are
  flying — your window is closing faster than ADP says"). Extends the 11.1/11.2 opponent model; face-validity in
  replay.
- **Decision-support surfacing (14.E–14.I)** — five broadly-useful app readouts that **read already-frozen
  machinery** (near-zero modeling risk): **tier-cliff board** (positional value cliffs, from 9.1
  `positional_cliff`), **roster-construction risk readout** (bye clustering / team concentration / handcuff
  gaps, from `roster_risk.py` + 8.5), **uncertainty-aware board** (q10..q90 ranges not false-precise ranks,
  from Phase-5), **playoff-week SOS lens** (weeks-15–17 matchup difficulty, keyed to `LeagueFormat`), **draft
  grade / team report** (post-mock grade vs the room, from the Phase-10 sim + cost report). All land in the
  Phase-14 app (app strictly last).

- **Situation-change features (Phase 16.1–16.2, value side, 2026-07-24)** — four PIT 0/1 flags added to
  the ADP-alpha panel to test whether the crowd misprices a *changed situation*. `team_changed` (on a
  different franchise than last year), `new_starting_qb` (team enters the season with a different Week-1
  starter than last year's attempts leader), `competition_change_roster` and `competition_change_depth` (a
  startable-caliber same-position teammate arrived/left — dual-sourced from weekly usage+`draft_picks` vs
  the `depth_charts` starting-depth). **All mined honestly; all washed out** (team/QB null; the two
  competition sources flip sign and fail FDR — echoing Phase 12.3). Live in `SITUATION_FEATURES` /
  `PHASE16_FEATURES`, **walled off** from the pinned frozen `FEATURES` (the cost-report DURABILITY model).
- **Board-team leak (2026-07-24)** — the `adp_snapshots.team` column is an end-of-season crosswalk, NOT a
  draft-day roster: historical boards list a player's *eventual* team (mid-season trades included). Never
  use it for a PIT feature; derive team-of-record from `weekly` (Week-1 team). Discovered building 16.1.
- **`SITUATION_FEATURES` / `PHASE16_FEATURES`** — the Phase-16 value-side feature sets. `FEATURES` (the
  frozen 5-trait softness model) is **pinned** so adding situation features never perturbs the cost-report
  DURABILITY credit; `PHASE16_FEATURES = FEATURES + SITUATION_FEATURES` is what the walled-off Phase-16
  steps mine. Reminder: enlarging the default `FEATURES` would also break `test_adp_bias` and the drift check.
- **`MATERIAL_RANK` / `DEPTH_TOP` (16.2 knobs)** — "material competitor" = a prior-season leaguewide finish
  inside a per-position rank (QB18/RB30/WR36/TE15); `DEPTH_TOP=2` = the starter-level depth slots. A looser
  bar floods the competition-change features to ~90 % (deep-bench churn hits every room yearly).
- **`reference/coaches.csv` (16.3)** — a Claude-drafted, **user-reviewed** table of playcaller/coaching
  history, feeding the 16.4 scheme fingerprint. Carries a `confidence` column; 16.4 must not consume it
  until the user signs off. As of 2026-07-25 it is **204 rows** on the frozen schema — 172 historical
  (2014–2025, Claude-researched + web-verified, review owed) + the 32 signed-off 2026 rows. This is the
  project's one genuinely un-derivable input, which is *why* it is hand-curated — contrast
  `situation_events_2026.csv` below.
- **`reference/situation_events_2026.csv` (16.5)** — the current-season situation-change event board
  feeding the 16.6 Beta Lab tab: **one row per affected draftable player**, **generated** by
  `situation/events.py` (never hand-edited). 138 events over 30 teams as of 2026-07-25. It was originally
  hand-researched at 9 rows and **missed 16 of the 23 team changes among draftable players**, which is the
  case for deriving anything that *can* be derived: the 2026 ADP board, the 2026 consensus projections and
  2025 `weekly` pin down who plays where, so research narrows to the `mechanism` column (trade vs free
  agency vs draft) that no feed carries.
- **Derived-vs-curated (the 16.3/16.5 split)** — the two reference tables look alike and are built by
  opposite methods on purpose. Hand-curate only what has **no free source** (who calls plays); derive
  everything a feed can already answer, and spend the human budget on the residue. The test is not "is this
  hard to look up" but "does any table we already ingest contain it".
- **Event type (16.5)** — which kind of situation change a player is on the board for, strongest first:
  `team_change` (on a new team) · `new_to_league` (no prior-season snaps — rookie or missed year) ·
  `room_change` (stayed put, but a same-position draftable player arrived or left) · `context_only` (only
  the play-caller and/or the quarterback changed around him).
- **Room churn (16.5)** — the arrivals into and departures from a player's `(team, position)` room among
  draftable players. Departures include prior-season producers (≥100 carries+targets+attempts) who left the
  draftable pool entirely: a retirement or an unsigned veteran vacates opportunity exactly like a trade
  does, and the incumbent who inherits it is the actual fantasy event.
- **`(unsettled)` quarterback (16.5)** — a team with **no** QB anywhere on the season's ADP board. Counted
  as a QB change rather than skipped, because an undraftable quarterback room is the *least* settled kind,
  not missing data (2026: ARI, ATL, CLE, NYJ, PIT).
- **Play-caller (vs head coach vs offensive coordinator)** — the person who actually calls the offensive
  plays. It is the unit Phase 16.4 fingerprints, and it is **neither** of the two title columns reliably: a
  head coach calls plays only about half the time, and an OC can hold the title for years without ever
  calling a play (Todd Monken at TB 2016–18 and CLE 2019; Brian Schottenheimer at DAL 2023–24). This is why
  the table has no free source.
- **Playcaller regime** — a contiguous `(play_caller, team)` spell, the grain 16.4 fingerprints a scheme on.
  Computed by `situation/coaches.py::playcaller_regimes`, which splits a return to a former team into two
  spells (Josh McDaniels at NE 2014–21 and again 2025) rather than one impossible block.
- **Head-coach scaffold (16.3b)** — an exact head coach per team-season for all **384** team-seasons
  2014–2025, derived free and PIT from `pbp.home_coach`/`away_coach`. Two uses: it removes the head-coach
  column from the research burden, and — the bigger one — it **audits** every researched row, since a wrong
  head coach almost always means the row is about the wrong regime. **Limitation:** the field is game-level
  only through **2023**; from 2024 it is a season-level *coach of record* (Daboll shows for all 17 of NYG
  2025 despite an in-season firing), so its `interim` column is a lower bound on mid-season changes.
- **`in_house` (16.3 frozen flag)** — "this season's play-caller was already on this team's staff the
  previous season." `in_house=0` ⇒ a new playcaller regime ⇒ a **16.4 transport event** — but **sufficient,
  not necessary**: an *internal promotion* (DEN 2026, Payton handing the offense to QB coach Davis Webb) is
  `in_house=1` and still a new regime. Hence `new_regimes()` pairs the flag with a **structural** check
  against the table's own previous-season row, which is what lifted the 2026 transport set from 13 to **17**.
- **Move-graph cross-reference** — the internal-consistency method for a curated table, run with **zero
  external lookups**: every "X departs" must match an "X arrives"; nobody holds two jobs in one season; a
  continuity flag must agree with the table's own history; a spell must have no one-season holes. Findings
  are graded `HARD:` (a self-contradiction — fix it), `check:` (must be explained in `notes`) or `note:`
  (expected, e.g. an internal promotion). It found every error in the 2026 draft table and, on the merged
  table, produced 12 findings with 0 HARD.
- **First-time play-caller** — a 2026 play-caller with **no prior play-calling regime anywhere** (2026: Declan
  Doyle/BAL, Davis Webb/DEN, Sean Mannion/PHI, Brian Fleury/SEA, David Blough/WAS). Not a research gap —
  research cannot manufacture a past — so they are handled by the **lineage fallback** below.
- **Lineage fallback / mentor regime (16.3b, user direction 2026-07-25)** — a first-time play-caller is not a
  blank. They came up inside somebody's system, so the honest prior is broad continuity with **that mentor's**
  regime, tagged as weaker evidence: Declan Doyle held the OC title in Chicago while Ben Johnson called the
  plays, so the 2026 Ravens should resemble the 2025 Bears more than they resemble nothing. Lives in
  `reference/coach_lineage.csv`, which names a *person*, not a scheme — 16.4 looks the mentor up in
  `coaches.csv` and fingerprints their regimes, and a gate asserts every mentor is itself a play-caller there.
- **`same_team` (lineage strength)** — whether the mentor's regime is on the team the mentee is now taking
  over. `True` (DEN 2026 Payton→Webb, WAS 2026 Kingsbury→Blough) means lineage and **team continuity** agree —
  the strongest form of the fallback. `False` (BAL, PHI, SEA 2026) means they point at different schemes, and
  16.4 owes the user **both** readings rather than picking silently; `prev_play_caller` carries the continuity
  side.
- **Fingerprint source (`coaches.fingerprint_source`)** — the resolved answer to "what does 16.4 fingerprint
  this team on?": `own` (the play-caller's own prior regimes) → `lineage` (their mentor's) → `none` (stay
  silent). For 2026: **12 own · 5 lineage · 0 none** across the 17 transport teams.
- **Majority-season inclusion rule (16.3b)** — a team-season enters `coaches.csv` only if the named person
  called plays for the **majority** of the team's games; sub-majority stints (McDaniels LV 2023, Kubiak DEN
  2022, Brady BUF 2023, Schottenheimer JAX 2021) are excluded and documented in an adjacent row's `notes`,
  so 16.4 never fingerprints a scheme on a half-season it did not run.

## Session F — availability drift + ECR (2026-07-25)

- **Draft-slot drift (16.7)** — how far a player was actually drafted from the consensus board, in
  **rounds**. **`drift > 0` = taken EARLIER than ADP** (a reach; the hype direction), mirroring the
  existing `reach` in `sleeper.build_tendencies`. This is the *availability* twin of ADP-alpha: alpha asks
  whether a player **out-earns** his slot, drift asks whether he **goes before** it. NB the sign is the
  negative of the `actual_slot − ADP` written in BUILD_PLAN §16.7 — flipped on purpose so that "positive =
  hyped" holds all the way through 16.8–16.12.
- **`drift_centered`** — drift minus its own draft's mean drift, and the **headline target**. Every room
  has a level offset that is nothing to do with any player (a 14-round draft against a ~200-deep board;
  K/DST picks the offense-only panel never sees). Centering isolates the real question: did he go early
  *relative to how this room drafted overall*. Never model raw `drift`.
- **Rounds normalization** — `slot_rounds = pick_no / teams`, `adp_rounds = adp / board_teams`. A pick
  number means different things in an 8- and a 16-team league, and FFC only publishes 10/12-team boards;
  expressing both sides as "rounds deep" is what lets the whole human corpus join one board.
- **`PRESEASON_WINDOW` (Aug 1 – Sep 15)** — the filter that makes drift mean anything. The crawled Sleeper
  corpus contains drafts from **February to November**; an offseason dynasty startup or an in-season draft
  compared to a September board measures a different market, not narrative drift. It is the single largest
  cut in the funnel (117 human complete drafts → 42) and was **absent from the original build plan**.
- **Held-out-draft `source_divergence` (16.8)** — public FFC board minus the sharper Sleeper-room board,
  where the Sleeper side is recomputed from every draft **except the row's own**. The stored
  `sleeper_human` ADP is literally the mean pick over the drafts being explained, so the naive feature is
  the target's own negative and would self-predict spectacularly. **Even held out it did not survive** —
  see the next entry.
- **★ The ablation rule (the durable lesson of Session F)** — when a feature is derived from the target's
  own siblings, computing it leave-one-out is **not sufficient**; report the fit *without it* as well. Here
  the headline was a weak positive (+1.05 % skill) and the ablation was **negative** (−1.75 %, worse than
  assuming everyone drafts at ADP), which converted an apparent finding into a null. Generalizes: a
  leave-one-out feature still shares the season, the room and the drafters with its target. **If a result
  only survives with the sibling-derived feature, the result is the leak.**
- **Skill (drift metric)** — fraction of the `drift = 0` baseline MAE removed by the model, where
  "drift = 0" means "everyone goes at ADP". Deliberately *not* an R² against a fitted intercept, which
  would flatter the model.
- **Rank-without-level** — Spearman +0.21 alongside ≈0 MAE skill: the model orders **who** gets reached
  better than chance while being unable to say **by how much**. Same shape as the Phase-4.4 projection
  finding (calibrated in rank, optimistic in level). A rank signal is not a usable per-player forecast.
- **ECR (Expert Consensus Rank, 0.11)** — FantasyPros' consensus **rank** board (`ecr_snapshots`), distinct
  from the *projection* pages `projections/consensus.py` already scrapes. Carries the experts' spread
  (`ecr_std`, min/max over 90–243 experts) and tier, which points-only projections cannot express.
- **★ Kickoff-dated archive (the ECR PIT trap)** — the `?year=` archive is real, but each season's board is
  a **single end-of-preseason snapshot** stamped 9/06–9/11, *after* the drafts it would explain (**1 of 38**
  corpus drafts post-dates its own stamp). So ECR cannot be a draft-day feature, and `ecr_asof` enforces
  that by returning an **empty frame** for an earlier as-of rather than a future-dated board. The general
  form: *an archive existing is not the same as an archive being point-in-time* — always read the
  vendor's own timestamp before treating history as backtestable.
- **`is_preseason` (ECR)** — per-board flag, false when the stamp falls after its own season's kickoff.
  The live 2023 PPR board carries `as_of = 2024-02-12`, re-touched after the Super Bowl: it has seen the
  season it is supposed to precede. Flagged rather than dropped, and excluded from any draft-season baseline.
- **Frontier crawl (0.10b, `--mode frontier`)** — walk the histories of the managers *already observed in
  the corpus* (`sleeper_manager_profiles`) and stop, as opposed to the BFS **snowball** that also expands
  into each newly-found co-manager. The frontier is the set the previous crawl discovered but never fed
  back in as seeds — which is why a crawl that looked exhausted at 266 drafts was merely un-reseeded.
- **★ Discovered ≠ ingested (the dead-id lesson)** — a crawl budget must be spent in the unit you actually
  want. `MAX_DRAFTS=500` counted *discovered* ids; **263 of them were 404/empty**, so over half the budget
  bought nothing and every re-run would re-buy the same nothing. Count ingests, and **persist the dead ids**
  so failure is remembered. The general form: *if a budget is denominated in attempts rather than successes,
  the failure rate silently becomes the budget.*
- **★ Shared-league fan-in (the crawl's dominant cost)** — a manager frontier is *built out of shared
  leagues*, so expanding `league → drafts` once per member re-requests the same league once per co-manager.
  A run-scoped `seen_leagues` cache took discovery from **26 s → 4.8 s per manager (5.4×)**. The general
  form: *when a graph is crawled from its nodes but its cost lives on its edges, dedupe the edges* — the
  more connected the corpus, the bigger the win, and connectivity is exactly what makes the corpus useful.
- **Resumable crawl state** — `sleeper_crawl_users` / `sleeper_crawl_leagues` / `sleeper_crawl_queue`
  (`todo`/`done`/`dead`), plus per-batch ingest commits. A multi-hour network walk *will* be interrupted;
  without persisted progress it restarts from zero, which is the practical reason a crawl never gets extended.
- **Token-bucket pacing vs a flat nap** — a fixed `sleep(0.05)` between calls does **not** cap throughput at
  20/s: it *adds* to response latency, and measured **29 calls/s**, above Sleeper's documented ~1000/min. A
  bucket makes a slow response pay for its own latency, so the stated ceiling is the real one.
- **★ Format contamination (the ADP board defect the crawl exposed)** — `_refresh_board` hardcoded
  `scoring="ppr"`, so every complete human snake draft landed on one board labelled PPR redraft. At 149
  drafts that was near-harmless; at frontier scale it was **82 % wrong** — of 7,399 complete human
  drafts only 1,312 are PPR redraft, against 2,547 dynasty_2qb, 952 2qb, 861 dynasty and 610 IDP. The
  board is now **redraft-only, split per (season, scoring)**, labelled in FFC's vocabulary so
  `adp_asof` reads both interchangeably. **The general form: a hardcoded label is a bug that scales with
  your corpus.** It was invisible while the sample was small and homogeneous, and the *same* code became
  a serious defect the moment the sample got big and mixed — so re-audit derived artifacts after any
  step change in input volume, not just after code changes.
- **The unmatched-rate canary** — the defect surfaced as an unrelated-looking gate failure: `ADP top-150
  gsis match` went red at **3.5 %** unmatched, because IDP rooms had pushed DB/DL/LB rows onto a board
  that is supposed to be offensive redraft. Removing the contamination took it to **0.61 %**. A join-rate
  gate on a *derived* artifact is a cheap detector for "the wrong rows are in here" — the crosswalk was
  never broken, the population was.


## Session F.6 terms (2026-07-26)

**eligible draft** — the corpus filter every Sleeper consumer must apply before learning anything
about redraft behaviour: `is_human` · `status='complete'` · `draft_type='snake'` · a redraft
`scoring` with a board analog · inside the Aug 1–Sep 15 preseason window. 1,426 of 7,699 human
drafts qualify. Implemented once in `adp/drift_panel.eligible_drafts`; consumed by 16.7, 11.1 and
11.2. Anything outside it is a *different market*, not noisy redraft.

**board key** — a consensus board is identified by **(season, scoring, teams)**, never by season
alone. Asking for a board without all three is the single most repeated bug in this repo: F.5
(hardcoded `scoring="ppr"`), F.6 (hardcoded 10-team PPR board in the behavioral path), and F.6
again (`teams=10` against `sleeper_human` boards labelled with the *modal* league size). See
`adp/boards.py`.

**calibrated fallback** — a substitute data source is not a drop-in until its units are shown to
match the original. ECR ranks 544+ players where FFC boards ~200 and compresses ADP ~2×; used raw
it manufactured +17.5-round "reaches". The fallback maps rank→ADP isotonically on overlapping
seasons and truncates at the original's depth. *Check the distribution of the substitute against
the thing it substitutes for, before trusting a single row.*

**scale does not launder a leak** — the sharpened form of the ablation rule. A leak-prone feature
derived from the target's siblings gets *better* as the corpus grows, so a rising headline is
exactly what a leak looks like from the outside. 16.8's headline went +1.05 % → +9.25 % while its
ablation went −1.75 % → +0.01 %. Only the ablation distinguishes the two.

**contamination invents effects** — the F.6 headline lesson. A wrong-population corpus does not
merely widen confidence intervals; it produces coefficients that tell a coherent, plausible story
(*"managers reach for rookies and QBs"*) which is really a description of which leagues leaked in.
Noise is visible in a CI; contamination is not.

**the sample you did not choose** — `n_drafts: 21`, the thinnest number in the repo and cited for
two sessions as a corpus limit, was the default argument `max_drafts_per_season=3`. When a headline
rests on a sample size nobody deliberately picked, treat it as an upper bound on the effect.

**a complexity class is not a profile** — T14 was opened by *reading* code: a `flatnonzero` scan
inside a 400-replicate loop, correctly derived as O(n_boot × n_drafts × n_windows), asserted to
dominate a 100-minute run. Measured, it took **0.79 s — 0.008 %**; 99.3 % was pandas row-slicing in
`simulate_survival`, an O(1)-per-call operation made 13 M times. Sound asymptotics, wrong by four
orders of magnitude, because the constant factor lived elsewhere. *A performance ticket written
without a profile is a hypothesis. Profile first; suspect pandas in any loop that mixes it with
numpy.*

**the choice-set contract** — a conditional logit's β means nothing except *relative to the
candidate set it was estimated on*. 11.1 is fit on the top-40 available by ADP; both the mock
simulator and the availability sim were applying that β to the whole board, inflating simulated
draft-slot dispersion by 59 %. Fit and simulation now share one constant (`CHOICE_TOP_K`) with a
test that fails if they drift apart. *Whenever a fitted model is used somewhere new, the first
question is whether the new caller reproduces the estimation-time conditions — not whether the
output looks reasonable.* Fourth member of the F.5/F.6 family (hardcoded label, contaminated
corpus, modal-size board, and now candidate set): **every one was a fit/use mismatch that looked
like a modelling result.**

**right-shaped vs right-sized** — the pre-fix simulator reproduced the realized *shape* of
dispersion-by-depth (+0.48 vs +0.68) far better than the fixed one (+0.08), while being 59 % too
dispersed overall. It got the shape by accident, from an unbounded candidate set letting deep
players go anywhere. *When a defective version scores better on one axis, check whether it is right
for a reason or right by coincidence before treating the fix as a regression.*

**an unidentified calibration** — 16.9's shock size was swept over a 50× range and the target
metric never moved beyond its own between-sample noise (two runs at the same setting: +0.249 and
+0.057). The grid still has an argmin, and reporting it as "the calibrated value" would have
dressed a noise draw as a fitted parameter. *Before quoting an optimum, check that the objective
varies more across the parameter than it does across reruns at a fixed parameter.*

## Session G (2/2) terms — hype board, momentum, drift consumption, run detection (2026-07-26)

**curated-not-backtested** — the explicit label every 16.10/16.11 output carries. Phase 16's
availability track produced three nulls and one unbacktestable series, so the hype board's
`pick_delta` and the momentum velocity are *claims*, not measurements. They are opt-in, default
OFF, and every function that surfaces one (`DriftConfig.describe`, `momentum_summary`,
`availability_readout`) states the caveat in its own return value rather than in a docstring.
Contrast a **frozen contract** (Phase 4/5), which is validated and may be relied on silently.

**the review gate** — `reviewed` on `reference/hype_board.csv`, enforced *structurally*:
`load_hype_board` drops unreviewed rows by default, so a Claude-drafted board is inert until a
human signs it. Independent of the on/off switch — `DriftConfig(hype=True)` against an unsigned
board still contributes exactly zero. Same contract as `reference/coaches.csv` (16.3).

**derived rows / curated claims** — how 16.5's *derived-vs-curated* rule applies when the answer is
genuinely not in any feed. The **row set** is derived (`nominate` ranks the live board), the
**annotation** is curated (`pick_delta`/`note`/`source`). The machine picks *who*, the human writes
*why and how much*. Regeneration merges forward so a signed row survives a re-run.

**partial-coefficient reuse** — reusing a fitted model's coefficients as a ranking requires
reproducing its *controls*. 16.8's surviving weights (`rookie` +0.73, `adp_stdev` +0.35/SD,
`vbd_gap` +0.18/SD) were estimated with `adp_rounds` and position dummies in the model, so they
mean "holding depth and position fixed". Scored unconditionally they rank players by **depth** (ADP
standard deviation grows mechanically with ADP: ~0.7 picks at the top of the 2026 board, ~33 near
the bottom) and by **position** (our value board likes every TE more than ADP does) — the first two
runs of `nominate` returned an ADP-120-to-175 list, then a TE-flooded one. `_z_resid` residualizes
each carrier on `log(adp)` **and** `adp` **and** position dummies first. *A coefficient is only
transportable together with the things it was conditioned on.*

**nesting the functional form** — the depth control carries both `log(adp)` and `adp` rather than
betting on one. With `log` alone, a carrier that happens to grow *linearly* in ADP leaks its
curvature into the residual: the very top of the board (Bijan Robinson, Jahmyr Gibbs, Ja'Marr
Chase) surfaced as "unusually disputed" purely from misfit, and dropped out once `adp` was added.
*The 1.01 debate is real; the derivation was not detecting it.*

**two-sided nomination** — the composite is signed (positive = the room reaches for him), so
ranking by raw score surfaces only risers. A **fader** is exactly as worth researching — the
strongest claim on the 2026 board is Zach Charbonnet at −10 picks (PUP list, out a minimum four
games) — so `nominate` ranks by |score| and preserves direction in the column.

**velocity / ADP momentum** — slope of a player's ADP across the Stage-0 within-season snapshot
series, in picks per week, **sign-flipped** so `velocity > 0` = drafted earlier = the hype
direction (matching 16.7's `drift` end to end). Two mechanical corrections: **centered** on the
board's own median slope (the pool deepens through a preseason, so every ADP creeps later together)
and **EB-shrunk** toward zero by each player's standard error (three snapshots ⇒ one residual
degree of freedom; 44 % of the raw spread survives). Two-snapshot players have infinite standard
error and shrink to exactly zero.

**forward-only** — a signal computable now but never backtestable, *structurally* rather than for
want of effort. No historical intra-season ADP series exists anywhere reachable: FFC publishes one
board per season and 0.11 established the FantasyPros ECR archive is kickoff-dated. Judged on the
16.4 **descriptive-honesty** bar (compute correctly, label provenance, expose thinness), never a
walk-forward gate.

**commensurate units** — combining a fitted coefficient with an unfitted signal requires putting
them on one scale first. 16.8's weights are in *rounds of drift*; velocity is *rounds per week*.
Entered directly, momentum was nearly inert and dropped the loudest live mover (Daniel Jones, +5.3
picks/wk, a locked-in starter on a new $88M deal) out of the top 45 entirely. Multiplying by a
data-derived horizon (weeks to the nominal Sep-1 draft) makes it rounds — and it is **capped**,
because linearly extrapolating a three-point slope five weeks forward is not a credible forecast.

**elasticity (of a curated claim)** — realized picks of movement per claimed pick, measured at
**≪ 1**. ADP is only one term in the fitted utility and `top_k` is a hard rank filter applied
before it, so a hype row is a *nudge*, not a repricing. Never surface `pick_delta` to a user as a
predicted change in draft slot.

**below the simulator's resolution** — a claim can be structurally unmeasurable rather than merely
noisy. At the league-standard 15 rounds (150 picks against a 201-deep board), a +12-pick claim on a
board-rank-171 player produced a **bit-identical** 30-draft result and only moved when the offset
was raised ~5×; at 18 rounds the same claim resolves. *Check that the measurement design can
contain the effect before concluding the effect is absent.*

**censoring, not dropping** — when a player is undrafted he must still contribute a value, or the
statistic is conditioned on the very thing being changed. Averaging only the slots a player *was*
taken at reported that hyping Cam Ward pushed him **later**; in fact it made him get drafted at all,
in rooms where he had gone untaken, and each new appearance near the final pick dragged the
conditional mean backwards. Score undrafted as `n_picks + 1` and report `draft_rate` alongside —
for a deep player the channel legitimately expresses as *more often drafted* before *drafted
earlier*.

**crowding-out** — a draft has a fixed number of picks, so hype is zero-sum: applying twenty claims
at once makes the hyped players compete with each other and the small claims lose to the large ones
(a +4 row got drafted *less* often while +12 and +8 rows rose). Correct behaviour, and the reason
the per-claim done-bar runs **leave-one-in** against a shared baseline.

**run intensity** (16.16) — a position's share of the last `RUN_WINDOW` picks minus its share of
the **live candidate set** (top-`CHOICE_TOP_K` available by ADP). Scale-free, computable mid-draft,
no corpus refit. The baseline choice is the whole measurement: scored against the entire remaining
pool — which is WR-heavy at every depth — the detector fired on **61 %** of real windows and the
flagged position was taken *slightly less* often over the next five picks (0.268 vs 0.278). Against
the candidate set, discrimination is monotone in the threshold, reaching **+0.109** (0.382 vs
0.274) at intensity 0.50. *The same choice-set discipline as the fitted β, applied to a rate.*

**sweeping a free parameter** — a detector's firing threshold is a knob, and picking one silently
is how a detector gets tuned until it looks like it works. 16.16 reports the whole
threshold/fire-rate/discrimination curve and selects an operating point from it, so a reader can
see that discrimination rises monotonically rather than at one chosen point.

**opponent personality vs archetype** (16.13–16.15) — two different things that both describe "a
way of drafting". A **personality** is an *opponent*: a tilt on the fitted 11.1 β that makes one of
the nine other seats behave like a recognizable manager. An **archetype** (`draft/config.py`) is
*your own* strategy, a constraint set the optimizer drafts under. They never mix — one is realism,
the other is personalization.

**signal weights** (16.14) — a personality's linear bonus on the enriched board columns, in units
of **utility per within-position standard deviation of the live candidate pool**. Standardizing
first is what makes `+0.45` mean the same thing for `boom_prob` ∈ [0,1] and `q90` ∈ [100, 300], and
standardizing *within position* is what stops a risk tilt from silently becoming a positional lean
(QBs carry the fattest raw `q90`; that is the scoring system, not an opinion about ceiling).

**reach ceiling** (`max_reach_picks`, 16.14) — a cap on how far a personality may reach for a
player it likes, stated **in ADP picks** and converted to utility through the model's own `β_adp_s`
(the same conversion `apply_hype` uses). It bounds only the *discretionary, player-specific* tilt —
hype, signal weights, a homer's fandom excess — and deliberately not β reshaping or
`early_pos_penalty`, because "I never take RBs early" is a **strategy**, not a reach for a name.
Two properties fall out for free: nothing on the board that fits a personality's taste ⇒ the bonus
is ≈0 and it quietly takes best value; and a curated claim can never drag a player further than a
human would have claimed.

**level vs shape** (16.13, `enrichment.residual_shape`) — the distinction that decides whether a
risk signal means anything. Within position, `q90` is **~0.98 collinear with the projected mean**
in every season checked (2022, 2025, 2026) and `corr(q90, q10) = +0.62…+0.74`: the quantiles are
mostly *level*, i.e. "is this player good". So an "upside chaser" weighting `q90` and a "safe"
drafter weighting `q10` both just draft good players and **agree**. Regressing the level out inside
each position leaves the **shape** — `upside` / `floor`, "more ceiling (floor) than a player
projected this high usually carries" — which are orthogonal to level by construction and correlate
**−0.86** with each other. *Same family as the 16.10 lesson: a signal is not a shape signal without
its control, and it fails by looking plausible.*

**change of situation** (`cos`, 16.13) — a coarse [0,1] score over 16.5's derived event board
(`team_change` 1.0 · `new_to_league` 0.9 · `room_change` 0.6 · `context_only` 0.4). Strictly a
**behavioral** prior — what a draft room *talks about* — never a value claim: 16.1 and 16.2 both
found situation change does not predict outperformance. It exists so a narrative-chasing opponent
has something to chase, and it must not leak into the value stack.

**inert personality** — the failure mode a personality set fails by. `homer` shipped in Phase 11.3
scaling a `fandom` coefficient whose feature was **identically zero** (nothing in the mock path
ever passed `fav`), and `rookie_hawk` scaled a `rookie` column `_prepare_board` dropped. Both were
literal no-ops for a whole phase and no test noticed, because a personality that does nothing still
completes a legal draft. The lesson: assert a tilt **moves** something, not merely that it runs.

## Session H2 terms — the mock room, and T17's knock-on (2026-07-27)

**rolled-forward availability** (T17, `injury.projected_availability_frame`) — the fix for a season
that has not been played: predict each player's hazard at his **most recent completed season's**
covariates, with `team_games` from the schedule rather than `week.nunique()` of a season with no
weeks, and stamp `covariate_source` (`observed` | `rolled_forward`) on the result so the
substitution is visible in the output rather than inferred. Took the live 2026 level ratio from
**0.37 → 0.721** (2025 holdout: 0.683). The rolled-forward path sits slightly *above* the observed
range on purpose — a draft-day forecast cannot condition on a player appearing — so a live number is
mildly optimistic, which is unconditionality rather than a defect.

**level-band guard** (`distribution.level_ratio` / `assert_level_band`) — asserts the distribution's
mean stays within a stated band (0.55–0.85) of the consensus projection it is built from, on the top
N by projection. Runs on the holdout **and on the live unplayed season, which is the one that
breaks**. The generalizable form: *assert the relationship between a derived quantity and its input,
not merely that the derivation ran* — T17 threw no exception, returned no empty frame and failed no
test; it just quietly halved a board.

## Live-mock-draft terms (2026-07-27) — reach width and the human-in-the-room bar

**reach width** — the dispersion of `drift` (`adp_rounds − slot_rounds`, positive = drafted early)
that a draft room generates, measured **by round**. The realized human corpus grows monotonically
from **3.3 picks in round 1 to 27.1 in round 15** (p90 6.6 → 51.7); the simulator is **flat at
~10–21 picks with no trend**. The distinction that matters: this is a **shape** error, not a scale
error — the room is ~3.5× too wide early *and* ~1.8× too narrow late, so any global "make it
chalkier" fix trades one end for the other. See `docs/TECH-DEBT.md` T15.

**the width exponent** — the measured law behind reach width: mean|reach| ∝ `pick^0.5…0.6`. Useful
because it *rules out* the two obvious specifications by inspection: the current linear ADP term
implies `pick^0.0` and a log-ADP term implies `pick^1.0`. A fitted fractional power (`adp^~0.45` in
utility) or a rank-in-pool transform sits in between. **The corpus curve is the acceptance bar, not
the estimator** — choose the form by refit log-loss, never by curve-fitting to the target.

**value leakage to the autopickers** — the objective symptom of an over-wide room, and the
regression test that needs no human judgement: when the opinionated seats reach, the ADP-following
seats harvest what they spill. Measured 2026-07-27 at `autopilot` mean drift **−19.8 picks** with
both autopilot seats finishing **1st and 2nd** on top-9 projection. **A room in which drafting pure
chalk wins is a room that is wrong**, independent of whether any individual pick "looks" plausible.

**the human-in-the-room bar** — the class of defect an aggregate gate structurally cannot catch.
11.1 log-loss (+0.174), 11.2 Brier (+0.086) and 16.9's dispersion match were all green while the
room drafted a 42-pick reach and left three consensus top-6 players on the board at pick 14: those
metrics score *better than a baseline*, never *possible*. Rule: **every subsystem needs at least
one bar a domain expert could fail by eye, run in front of one before it ships.** Sibling of the
16.14 lesson (*state your bars as oppositions*) and of *an inert thing still passes*.

**specification error vs contamination** (the F.5/F.6 family, completed) — F.6: a contaminated
corpus **invents** effects that a CI cannot see. 2026-07-27: a misspecified functional form
**hides** a defect in plain sight while every aggregate stays green, and **more data makes it
worse, not better** — a 52× corpus expansion (F.5) estimated the wrong coefficient more precisely.
Diagnostic question when a fitted model behaves absurdly in a region: *can this specification
represent the behaviour I want, anywhere in its parameter space?*

**a fix that breaks a signal by improving it** (T17 → 16.13) — repairing the availability data
turned `games_played_mean` from four cohort constants (`corr` with the level **+0.00**, documented
as inert) into a real forecast **and thereby into a level proxy** (+0.46…+0.90 within position). So
`safe_floor`'s durability weight became a quality tilt with no code change and a green suite. Third
instance of *level vs shape*, first to arrive through data rather than code. Rule: **re-measure a
signal's correlation with the level after any change to the data it is built from** — the F.5
"re-audit after a step change in input volume" rule, generalized from volume to quality.

**own opinion vs shared story** (16.15) — the scope of `max_reach_picks`. The reach ceiling bounds
what a seat decides **for itself** (`signal_weights`, a homer's fandom excess); the shared 16.9
narrative draw is applied *outside* it, because it is the room's story and carries its own fitted
scale. Folded into the same clip, a seat whose signals already saturate its ceiling cannot express
the story at all — and nothing fails, since a personality that ignores the shock still drafts
legally. Justified on the estimation conditions, not on the current magnitude: **16.9 fitted the
shock uncapped and uniform**, so clipping it uses a fitted parameter outside where it was estimated.
(Measured scope: on the fixture's smaller β the clip bit hard — homer 90 % of candidates; on the
live board's fitted β it bites 0 % for homer, 26–33 % for upside/safe. The fold-in would start
costing after any 11.1 refit that shrank `β_adp_s`.)

**a two-ended bar** (16.15) — a face-validity check stated as the gap between the *extremes* of a
population, which cannot see the middle of it going backwards. *Chasers − autopickers* passes on a
room that routes the story to the wrong seats, because the autopickers' share of hyped players falls
when the channel opens regardless of **who** is chasing (they get sniped). Replaced by a rank
correlation across every seat. The companion clause to 16.14's *state your bars as oppositions*.

**the control must be the same measurement** (16.15) — closing a channel by passing a **zero
vector** is not a control: `argsort` on zeros labels the top-N rows by board order, i.e. by ADP,
which autopick seats take by construction, so the "off" arm measures a different quantity and
manufactures a large fake effect on exactly the seats it should say nothing about. Close the channel
(`hype=None`) and keep the **same labels**.

**mechanism gate vs shipped-size report** (16.15, `AMP_GATE`) — when a substep's plumbing is sound
but the signal it carries is a known null, gate the **mechanism** at an amplification big enough to
resolve it and **report** the shipped-size result separately. 16.15's routing is +0.07 at the
calibrated 1.48-pick shock and +0.91 at ×10; sweeping ×1→×40 gives +0.07 · +0.53 · +0.84 · +0.91 ·
+0.95. The alternative — turning the shock up so the substep looks better — would tune a calibrated
parameter to a face-validity check. Same move as Phase 9.5's `winprob_sims ≥ 200`, same shape as
16.16's *the detector works, reacting to it does not*.

**hand-set mix, corpus-checked** (16.15, `DEFAULT_ROOM`) — a manager's **tendency** is observable in
the draft corpus; his **personality** is a latent label nothing in the data assigns. So the default
room is hand-set and the corpus is used to *check* it rather than supply it: 3,309 eligible-redraft
managers give median QB share 12.6 %, RB share 31 %, and only **1.7 % RB-light** — which is why no
`zero_rb` seat is in a default room. The check computes position share **from picks alone, with no
ADP reference**, because the stored `avg_reach` is a pooled-board mismatch (**T18**).

## Personality-design terms (2026-07-27) — width vs direction

**width vs direction** (16.14R, the personality contract) — the decomposition every seat is built
from: **width** = `width(round) × personality_multiplier`, *how far* a seat deviates from ADP;
**direction** = `signal_weights`, *which way*. T15 forced the split — realized reach width grows 3.3
→ 27.1 picks across the draft, so a single absolute `max_reach_picks` ceiling is wrong at one end by
construction. **The multiplier replaces the ceiling as the primary reach control** (autopilot 0 ·
safe ~0.8 · balanced 1.0 · reacher ≤2.0). See `docs/BUILD_PLAN.md` §16.14R.

**the level, not the residual** — why a signal can be real *and* measure as null: a drift/deviation
model sees only what ADP has **not** already absorbed. Situation and coaching changes are priced into
ADP, so a human drafting on them drafts **at** ADP and leaves no residual — hence 16.8's null
(measured twice, 34 and 1,144 drafts) is fully consistent with situation driving human behaviour.
Rule: **before calling a signal inert, check whether your target already contains it.** A
residual-target null is much weaker evidence than a level-target null, and both print "not
significant". Sibling of *the ablation rule*: there more data strengthened a leak, here the wrong
target hides a real effect inside the baseline.

**the anchor assumption** — `balanced` was specified as "the fitted average human" and was exactly
that: raw β, no `signal_weights`, no `fav_teams`, no cap. It made the mock's 42-pick reach. **A seat
whose spec is "the anchor" quietly acquires whatever qualities people assume anchors have** —
holistic, sensible, high-quality — none of which were ever built. Keep the two repairs distinct: T15
fixes how far it deviates, 16.14R fixes which way.

**scoring the argmax** (the value-hawk trap) — a seat that optimizes our value board, evaluated on
our value board, wins by construction and carries no information. The lockbox already found
personalization noise-dominated on realized points. So room rankings on **projected** points are
**descriptive**; any **evaluative** claim must run on **realized** points in a backtest season.
Family: *an inert thing still passes*, and 16.14's two personalities that agreed with each other.

**harvested spill** (retires T15 bar #3's standings half) — an ADP-following seat finishing first is
**not** evidence it drafts well; "don't fight the sharp market" (Phase 2) predicts it should do fine.
The defect is the **surplus**: autopilot's −19.8 mean drift, i.e. players taken ~20 picks below ADP
because the room spilled them. **Measure surplus, not standings** — the rewritten bar is that an
ADP-follower harvests what the corpus's most ADP-faithful managers harvest.

**`pool_rank`** (T15 step 0) — how many better-ADP players a seat passed over on a pick; 1 = took the
best available. The measure of **faithfulness**, and it exists because |drift| cannot be one: a chalk
seat in a room of reachers records a huge |drift| *precisely because* it stayed faithful and harvested
the fall. `pool_rank` separates *what the seat did* from *what was done to it*, and computes
identically on a simulated and a realized draft. Corpus median **7.62**; simulated `autopilot` **1.28**.

**the harvest curve** (T15 bar #3, fixed-edge form) — harvest in 10-team picks against `pool_rank`, on
**absolute** bin edges rather than per-population quantiles. Quantile-matching compares "the most
faithful quintile" of a robot room (`pool_rank` 1.28) with that of a human corpus (4.28), i.e. two
different behaviours, and reports the difference as an effect (+20.4 vs +8.5, an artifact). On fixed
edges the simulated harvest is *right* (+20.5 vs +17.6 at [1,2), corpus sd 17.0). Rule: **when two
populations have different distributions of the conditioning variable, condition on its value, never
on its quantile.**

**the missing middle** (T15 step 0, the finding) — the simulated room is **bimodal**: 19.6 % of seats
are chalk (`pool_rank` < 2) and the rest sit past 11, while **54.3 %** of real seats fall in the 2–8
band the sim leaves at **2.2 %**. So T15's target is the **distribution** of deviation, not its scale —
a uniform shrink moves the extremists and leaves the middle empty. Corollary: `autopilot` is ~100×
over-represented relative to the 0.2 % of human seats that draft that faithfully (a 16.15 composition
question, not a model one).

**the ratio column** (T15 bar #1's honest scalar) — sim ÷ corpus mean|drift| by round: **4.24 at round
1 → 0.57 at round 15**, crossing 1.0 near round 11. Supersedes "the simulator is flat", which was read
off one draft; at 800 drafts the sim curve does rise (Spearman +0.646 vs the corpus's +1.000) and then
**turns over** after round 9. A scale fix moves the whole column and makes the right-hand end worse.

**`AdpSpec` / `BandSpec`** (T15 step 1) — the two objects that own how ADP enters the opponent
model: the **transform** (`adp_s = (adp/50)^p`) and the **candidate set** (top-k, optionally widening
with depth). They exist because `adp_s = adp/50` had **four** independent copies — the fit
(`build_choice_frame`), the simulator (`candidate_matrix`), and two places that *inverted* it to turn
picks into utility (`apply_hype`, `Personality.reach_cap`) — none of which could see the others. Both
specs are **persisted next to β** and read back with it: they are estimation conditions, not
settings, and a β paired with the wrong one produces a plausible, wrong room.

**the width law** — `w_a ∝ 1/f'(a)`: with utility `u = β·f(adp)`, the softmax's deviation width **in
ADP picks** depends only on the transform's derivative, because the board's local density cancels
between rank-width and pick-width. Consequences: linear `f` ⇒ width flat in depth (**the T15 defect,
derived rather than observed** — no amount of extra corpus can move it); `f = (a/s)^p` ⇒ width
`∝ a^(1-p)`, so the corpus's measured `pick^0.5…0.6` implies **p ≈ 0.4–0.5**; `f = log a` ⇒ width
`∝ a^1.0`, over-correcting. **Rank-in-pool** ⇒ width `∝` board density, which grows ~2.3× where the
corpus grows 5.5× — it under-corrects, and against a fixed top-k it is nearly a no-op, since
linear-in-ADP inside a fixed set already *is* rank-in-pool up to a level that cancels in the softmax.

**★ gain is not a selection criterion** (T15 step 1, measured) — *a difference-of-two-models metric
can be improved by damaging the weaker model.* Inside one fixed band, held-out log-loss is minimized
at exponent **0.45** while gain over the ADP-only baseline is maximized at **1.00**, the incumbent
spec T15 exists to replace: a linear ADP term cripples an ADP-only model more than one that also has
position dummies and `need` to lean on, so the *gap* is widest where the absolute fit is worst.
Selecting on gain would have chosen the widest band and the flattest ADP term — the defect itself —
while printing a rising headline. Twin of the F.6 **ablation rule**: there a leak made a headline
rise with more data, here a bad specification makes one rise by hurting its own baseline. **Rank
specifications only against a fixed comparator.**

**band coverage** (`opponent_model.band_coverage`) — the judgement-free replacement: *how often does
the candidate set fail to contain the pick a human actually made?* A property of the set, not of a
likelihood's normalization, so it is comparable across bands and has no degree of freedom to game.
It restates the Session-G choice-set contract as a measurable quantity. Selection rule: the
**narrowest** band inside a stated 1 % miss tolerance, then the exponent by log-loss **within** it —
sequential, because the log-loss-optimal exponent moves with the band (0.45 at fixed-40, 0.75 at
widen+5/10) and no criterion is comparable across bands.

**`width_mult`** (16.14R's width half, pulled into T15) — a seat's deviation width as a multiple of
the fitted average manager's, implemented as `β_adp_s / width_mult` because width `∝ 1/|β_adp_s|`.
Depth-correct by construction once the ADP term carries curvature, which is why it **replaces the
absolute `max_reach_picks` ceiling** as the primary reach control: T15 showed a single pick-count cap
is wrong at one end by construction. `max_reach_picks` survives, still bounding a seat's own
*opinion* — a different quantity. Shipped: autopilot 0 · chalk 0.55 · safe 0.8 · balanced 1.0 ·
homer 1.2 · upside 1.35 · reacher 2.0.

**an optimum at the grid's edge is a statement about your budget** (T15) — a 4-draft/season smoke run
put the log-loss minimum at the bottom of the exponent grid, reading as "the choice data want
log-ADP". At 20 drafts/season the minimum is **interior at 0.45**. The cheap run's version was the
more quotable one, and it was wrong.

**`WidthCurve` / the depth-width law** (T15 step 4) — the room's deviation width as a function of
**round**, `round^γ`, applied to `β_adp_s` and composing with each seat's `width_mult`. Together they
are 16.14R's **`width(round) × multiplier`** contract, with T15 owning the round function. It exists
because a single ADP exponent could not set both ends: the exponent flat enough to stop elites
falling (p=0.15) left the room uniformly too narrow and broke the 16.9 dispersion match (+8.8 % →
**−53.6 %**). **Two requirements, two parameters — an identification fix, not a richer model.**

**pool exhaustion** (why the width law over-promises at depth) — `w_a ∝ a^(1-p)` assumes an
unbounded local candidate pool. By round 15 roughly **thirty** boarded players remain, so a seat
cannot deviate 27 picks from a board with less than 27 picks of depth beneath it. Predicted late
growth at p=0.15 was ~18×; measured **1.8×**. So **curvature buys far less late width than the
algebra promises while costing full price at the top** — the reason the exponent alone is not an
identified fix, and a standing caution that a derivation's boundary assumptions are where it breaks.

**a scalar gate over a curve** (T15 step 3, a caution) — bar #1 was implemented as a round-1-only
pass criterion and duly reported **PASS** on a configuration whose full-profile distance had gone
**0.388 → 0.791**, i.e. worse than before the fix. Summarizing a curve by one of its points hides
movement everywhere else. Report the curve next to the gate.

**the joint re-verify** — running 11.1, 11.2 and 16.9 in **one** script rather than three sessions,
because T15's own register warned that "a change which improves one and quietly degrades another is
the failure mode". It duly caught exactly that: the step-2 spec improved the elite-fall gate and
11.2's Brier (+0.0708 → +0.0890) while breaking bar #5. **Each metric checked by the person who
cares about it is the same thing as no check.**

## The 2×5 mock-room terms (2026-07-27, session 5 — signal repair before personality repair)

**the 2×5 room** — a fully-simulated 10-seat mock with **two seats each** of autopilot / value hawk /
safe floor / reacher / balanced, seats shuffled so a personality is never confounded with a draft
slot. Distinct from `DEFAULT_ROOM` (nine opponents built to sit *opposite* a human) and from
`DEFAULT_FULL_ROOM` (ten seats, the T15 measurement composition). Run at 60 seeds because *one draft
is ten picks per round*.

**censored signal** (T19, the session's headline) — a variable with a hard floor or ceiling that a
large share of the population sits exactly on. `q10` is **exactly 0 for 42.9 %** of offensive board
rows. **Regressing a censored variable on a level control and calling the residual a shape signal
inverts it**: the linear fit predicts a negative value for replacement-level players, so the ones just
above the censoring point earn the largest positive residuals. Measured effect —
`corr(floor, adp)` = **+0.179 RB / +0.124 WR**, i.e. the "safety" signal prefers *deeper* players.
The general caution: **check the ranking a signal produces, not just its coverage** — coverage was
100 % and the ranking was upside down.

**the level-vs-shape family, fourth instance — and the first self-inflicted one.** `q90`/`q10`
(16.14) → `games_played_mean` (T17) → `vbd` (this session) → **`floor` (T19)**. T19 is different in
kind: it was **created by the fix for 16.14**. Residualizing removed the level and left something
*anti*-correlated with quality in the tail rather than orthogonal to it. *A residualization is not
free — it is a modelling assumption about the tail.*

**inert weight** — a `signal_weights` entry on a column that cannot fire for most of the board.
`boom_prob` is exactly 0 for **64.7 %** of offensive rows and `bust_prob` for **56.0 %**, so
`safe_floor` spends 0.35 of a 1.10 budget on nothing. Fourth instance of *an inert thing still
passes*. **Assert that a tilt moves something, on the real board, not the fixture.**

**width without direction** — the `reacher`'s actual state: `temperature=2.2` and a wide
`width_mult`, with **no `signal_weights` at all**. It reaches, and what it reaches for is noise. The
user's phrase *"nonsensical and have no basis"* is literal, not rhetorical. **Direction is repaired
before width is budgeted**, because a budget over directed reaching is a different object from a
budget over noise.

**reach budget** (user spec, 2026-07-27) — bounding a seat by the **count** of deviations in each size
class per draft rather than by a per-pick ceiling: ≤2–3 large (>25 picks) in round 5+, 3–5 medium
(8–15 picks) in round 3+, clamped near `balanced` in rounds 1–3. Consequence to scope before
building: a budget is **stateful per seat**, and `make_opponent_pick_fn` is a stateless softmax today.

**blind spot vs mis-weight** (the value-hawk distinction) — a seat making bad picks because its
weights are wrong is a *tuning* problem; a seat making bad picks because the board does not carry the
information is a *scope* problem, and no objective function fixes it. The user's three value-hawk
objections (signed situation, committee share, TD-regression) are all the second kind. **Diagnose
which one you have before re-specifying a personality.**

**unsigned situation score** — `cos` measures *how loud a story is*, never whether it is good or bad
(`COS_WEIGHTS`: team_change 1.0, new_to_league 0.9, room_change 0.6, context_only 0.4). Rachaad White
reads 1.0 and DK Metcalf 0.6 — one is opportunity, one is competition, and the column cannot tell
them apart. Splitting it into magnitude + direction is 16.14R Step 3.

**mandatory needs / roster-completion rule** (T20) — unfilled **non-flexable** starter demand
(`base_demand()` minus `flex_positions` ⇒ QB/K/DST). When a team's remaining picks equal its unfilled
mandatory slots, the pool is restricted to those positions. Deliberately a **hard filter applied
before utility** — the same class of object as `BandSpec` — so every pick policy inherits it and the
fitted β's meaning is untouched. Gated on `rounds >= slots.starters`.

**a filter, not a data gap** — team defenses were absent from every board not because the data was
missing but because `_ffc_board` requires `gsis_id IS NOT NULL` and defenses key on `ffc_player_id`.
The data was present and complete the whole time (60 `DEF` rows for 2026 FFC PPR 10-team).
**Before sourcing new data, check whether the pipeline is discarding what you already have.**

**the choice-set contract, second home** (T21) — `build_choice_frame(skill_only=True)` fits on
QB/RB/WR/TE while the simulator bands the whole board, so the fitted β nominates kickers it never saw.
Same failure as Session G's `top_k` mismatch, and it survived for the T15 reason: **an aggregate
metric cannot see an occasional impossible event.**

**composition is not a model change** — swapping `homer` + `upside_chaser` for `value_hawk` + a second
`safe_floor` moved T15's open faithfulness gap from median `pool_rank` 10.40 → **8.59** (corpus 7.62)
and the moderate band 13.5 % → **24.3 %** with no code change at all. *Check what seating alone buys
before spending a session on the model.*

## 16.14R execution terms (2026-07-27/28) — the signal repair, and what it taught

**shape input (`shape_inputs`)** — the *scale-free ratio* a shape signal is built from before any
level control: `floor = q10/mean`, `upside = q90/mean`, `tail_risk = (q90−q10)/mean`. T19's actual
resolution. **The point is the scale, not the estimator**: a censored `q10` has no well-behaved
*residual* under any likelihood, but it has a perfectly well-behaved *ratio* — it sits at the
bottom, which is the honest reading of a 10th percentile of zero. Contrast **level-vs-shape**, whose
fifth and sixth instances this session produced.

**`tail_risk`** — relative outcome spread `(q90−q10)/mean`, level-controlled. The column that
actually prices **boom-or-bust**, and the replacement for `bust_prob` (see *stale-by-construction*).
Weighted **negative** by `safe_floor` and **positive** by `upside_chaser` and `reacher`: width is a
cost to one manager and the whole point to another (the 15.2 best-ball finding from the other side).

**stale-by-construction (T22)** — a column that is not wrong so much as *four years old*, because
its upstream reads `max(train_seasons)` and `train_seasons` for a live season is `DEV_SEASONS`.
`boom_prob`/`bust_prob` on the 2026 board are the **2022** rates with **292 of 306 zeros
manufactured by `fillna(0.0)`**. Distinct from *inert*: an inert column says nothing, a
stale-by-construction one says something confident and false — here, that a player absent in 2022
*never busts*. Check what season a column is actually from before weighting it.

**the one-sided-bar trap** — a bar written to catch a defect in one direction is passed by the same
defect in the other. T19's bar (`corr(floor, adp) <= 0`) is cleanly passed by an estimator that
over-corrects into a pure quality tilt, which is 16.14's original defect wearing a PASS. Fixed by
always running the **oppositions** (`corr(upside, floor)` strongly negative, `corr(floor, mean)`
near zero) alongside. Sibling of *state your bars as oppositions* and of *the ablation rule*.

**neighbourhood-local z** — standardizing a board column against a player's **ADP neighbours**
rather than his whole position, so a signal that is partly a level restatement is not paid for
twice. Used for the step-3 context columns (`corr(role_share, vbd)` +0.88 RB) and, as
`_neighbourhood_rank`, for the shape signals themselves. ⚠ **The window must be a fraction of the
group, never a count**: a flat 25 was wider than the whole QB group, so the level control silently
switched off for QB/TE only.

**deadline filter** — a hard constraint that fires only when a seat's remaining picks equal its
unfilled non-flexable slots (`DraftState.mandatory_needs`, T20). Guarantees a legal roster without
becoming a preference: K/DST land in rounds 14–15 exactly as in a real league. Same class of object
as `BandSpec` and the reach budget — *applied before utility*, so it never changes what a fitted β
means. Corollary for tests: *"a K/DST was drafted early" and "a K/DST was forced early" are
different events, and only the second is a bug.*

**reach budget (`ReachBudget`)** — how *often* a seat may reach (count tiers by round), as opposed
to `width_mult`, which is how *widely* it reaches on every pick. Stateful per seat but **re-derived
from the draft log each pick**, so a `DraftState.clone` used by a 9.5 rollout cannot silently
diverge from its parent.

**`CORPUS_REACH_P95`** — frozen per-round 95th percentile of realized human *reaching*, in 10-team
ADP picks, over 1,144 FFC-boarded corpus drafts. **A count budget bounds how often, never how far**,
so this is part of the *mechanism*, not only the measurement. ⚠ **Reach side only**:
`mock.reach_profile` pools |drift|, and its round-15 p90 of 52 picks is mostly elite players
*falling* — a ceiling on how far a manager may **jump** cannot be read off a number that is mostly
about players **sliding**.

**resolution-limited sweep** — a parameter sweep whose spread is inside its own noise. 16.14R step
6's window sweep separates 1.00× from 1.25× by **+13.1 CE against a pooled se of 10.7**, so the
argmax is a noise draw. Rule adopted: *an unresolved choice does not buy itself a wider licence* —
default to the tighter constraint and say the sweep failed to resolve. Sibling of T15's
resolution-limited title objective and of 9.5's 60-sim finding.

**signed companion (to an absolute-value bar)** — a second measurement that preserves direction,
required wherever a bar is stated over |drift| or |reach|. Round-1 mean |reach| reads **2.91 sim vs
2.87 corpus** — a clean pass — while the consensus #2 lands at a **median pick of 4** and clears
pick 4 42 % of the time against a realized 12 %, because *a reach and a fall have the same absolute
value and cancel inside the mean*. The companion here is a **landing-spot distribution for the
consensus top tier**. T15's *"an aggregate metric cannot see an impossible event"* one level down:
there the aggregation was over **drafts**, here it is over **direction**, inside a metric that
already passes. (T24, 2026-07-28.)

**consensus dispersion as a width scale (`adp_stdev`)** — the per-player standard deviation the ADP
board already carries (Bijan 0.7 · Gibbs 0.8 · Lamb 2.1 · a round-11 flier ~11), as opposed to
`WidthCurve`, which indexes width by **round** and therefore gives every round-1 pick the same
width. Measured on 1,144 corpus drafts: **|drift| ≈ 2 × adp_stdev**, stable through the usable range
(the decay above stdev 12 is **pool exhaustion**, T15's own finding arriving independently);
Spearman with |drift| **0.484** against **0.535** for round. Decisive property: it separates *inside*
a round — within rounds 1–3 the stdev terciles drift **2.11 / 3.33 / 8.91**, a 4.2× spread no
round-indexed curve can express. ⚠ **That measurement is sound and the mechanism built on it still
failed** — see *private board* below: the same column that separates drift terciles at *board scale*
is, at the *top* of the board, the same size as the gaps it would perturb. `stdev` joined
`simulator.PASSTHROUGH_COLS` in T24 and the pick path can now read it (κ = 0 by default). Until then
**nothing in `draft/` read it** — it appeared only in `mock.py`, copied onto the *output* panel for
reporting, while 16.8 had already scored it as a drift driver (+0.35/SD). *The finding existed in
the repo for a phase and a half and was never fed back into the room; a column that never reaches
the pick path is a measurement nobody can act on.*

**private board (per-seat board perturbation)** — each seat drafting off its own draw
`adp_seat = adp + κ_seat · adp_stdev · ε`, rather than all ten seats reading one board and deviating
from it by noise. The object T15 handed forward (*"the late-round narrowness needs per-seat board
perturbation, not another width parameter"*) and 16.14R deferred. **T24 built it and REJECTED it
(2026-07-28): measured monotonically HARMFUL** on the objection it was designed for — seating-
marginalized elite-past-pick-4 runs **18.8 / 19.7 / 26.6 %** at κ = 0 / 1 / 2. **★ The reason
generalizes: at the top of the board `adp_stdev` (0.7–2.5) is the same size as the ADP gaps it
perturbs (~0.2 picks), so the draw does not *create* tier structure, it destroys the ordering that
was already there** — the exact mechanism that makes an elite fall. The corpus law behind the idea
(`|drift| ≈ 2 × adp_stdev`) is real but describes **realized drift**, an outcome of ten seats
interacting; re-injecting it as **per-seat perception** is a different object. *A relationship
measured on outcomes is not a specification for the mechanism that produced them.* Implementation
kept, **default-off** (`κ = 0`), verdict recorded on the model artifact beside the parameter; drawn
once per seat per draft, `κ_seat = κ · width_mult`, applied to the **utility** only (the band is an
estimation condition and the reach ceiling is stated in *public* picks). Distinguish from
`width_mult` (how widely a seat strays from a *shared* board) and `ReachBudget` (how often).

**a knob that sets the level and a knob that sets the shape (`WidthCurve.base` vs `gamma`)** — T15
established that one parameter cannot set both ends of the depth profile; T24 needed the same split
one level down. `width(round) = base · round^gamma`: `base` is how wide round 1 is, `gamma` how fast
width grows with depth. They were one number while depth was the only lever. **This — not the
private board it was added to support — is what closed T24**: `base 1.0·γ0.8 → 0.6·γ1.0` takes
consensus elites past pick 4 from **25.8 % → 15.3 %** (realized 13.1 %) and bar 2 p95/past-10 from
17.0 / 28.8 % → **16.0 / 25.2 %**, while γ keeps **90 %** of the old round-15 width. Cost, stated:
room dispersion −7.1 % → **−11.4 %** (bar 5 allows ±20 %), because narrowing the top takes spread out
of everywhere and only `gamma` gives any back; every other headline, profile distance included
(0.107 → 0.089), moves toward the corpus. **The ticket diagnosed the right symptom and the wrong cause — round 1 was
simply too wide, not the wrong shape.** (2026-07-28.)

**a relationship measured on outcomes is not a specification for the mechanism** — the corpus's
`|drift| ≈ 2 × adp_stdev` is a fact about *realized* draft slots, which ten interacting seats
produce jointly. T24 fed it back as each seat's *private perception* noise and made the thing it was
built to fix **worse at every setting**. Before turning a measured regularity into a model
component, ask which level it lives at: an equilibrium outcome, or an individual's belief. Sibling
of *"the level, not the residual"* (16.8) and of *"the problem was the SCALE, not the fit"* (T19).
(T24, 2026-07-28.)

**moving two knobs together credits the interesting one** — every T24 sweep row changed
`WidthCurve.base` **and** κ, so the width narrowing wore the private board's credit for three runs
and a wrong config shipped on it. The row that settled the ticket (`base 0.7, κ 0`) was never in any
grid; it existed only because the verdict looked wrong. *If two changes ship together, the one you
were excited about gets the credit — put the isolating row in the grid from the start.*
(T24, 2026-07-28.)

**seating confound (fixed-room batch)** — a batch of simulated drafts that holds **one** seat→slot
arrangement across every seed measures *where the reachy seats happen to sit* as if it were a
property of the model. Found while calibrating T24: with the same code, the round-1 half-split
"rises" 1.26 at room seed 17 and **falls to 0.82** at room seed 18, and the top-band past-pick-4
share reads 23.8 % vs 17.1 %. The human corpus averages over 1,144 independently-seated drafts, so
the sim has to marginalize seating too or the two sides are not the same statistic —
`steps/mock_room_bars.py --shuffle-room` re-seats every seed. Same family as *derived-vs-curated*
and the F.5 hardcoded label: **the comparison measures whatever the two sides do not share.**
(T24, 2026-07-28.)

**a bar written from the symptom passes the general defect** — T20's done-bar was *"60/60 seats
finish with ≥1 K and ≥1 DST"*, the two positions the ticket was written about. It passed while the
same deadline filter left **TE** unguarded, so 12.2 % of seats finished with no legal lineup. State
a guarantee's bar against the **whole contract** ("no unfillable starting slot"), not against the
instances that motivated the ticket. Sibling of 16.14's *"state your bars as oppositions"* and of
T15's scalar-gate-over-a-curve. (T23, 2026-07-28.)

**`pool_rank` over mean reach (reporting rule)** — the per-personality summary leads with
`pool_rank`, split **R1–13 / R14–15**. A 15-round mean reach is dominated by late-board ADP noise
(Tyler Allgeier at ADP 167 taken at pick 119 scores **+48** and means nothing — nobody else was
taking him at 119 either) and by *when* a seat takes K/DST. Reporting it that way is what produced
the 2026-07-28 "the reacher reaches less than balanced" objection, which the batch then contradicted
(reacher 13.40 vs balanced 11.74) while revealing a **real** depth-localized inversion in R1–3.

**a sweep whose winner sits at the edge of the grid has not finished** — T24 shipped a config twice
before the grid bracketed it: `base 0.7 · κ 2` (chosen on a 4-season subsample, then failed by the
8-season one) and `base 0.5 · κ 0` (chosen because 0.5 and 0.7 were the only points measured). The
un-sampled midpoint **0.6** passes the same gates while sitting closer to the corpus on *every*
secondary — round-1 mean 2.73 vs 2.51 against a realized 2.87, dispersion −11.4 % vs −17.4 %,
profile distance 0.0825 vs 0.1544. **A grid samples points; a dial needs bracketing.** If the best
row is at an end of the range, the range was the answer's constraint, not the data.
(T24, 2026-07-28.)

**`db.deterministic_reads`** (T13's fix, 2026-07-29) — a context manager that pins DuckDB to one
thread for a block of reads and restores the previous setting. Exists because a parallel `SUM`/`AVG`
adds its partitions in whatever order the threads finish and floating-point addition is not
associative, so the Phase-5 assembler's training frames differed in their last bits from process to
process, the fits' coefficients differed at ~1e-11, and the sampler turned that into visibly
different per-player draws. Wraps the assembler's reads wholesale rather than hunting the offending
aggregate because the measured cost is **negative** (10.2 s → 9.1 s).

**the noisy stage is not always the stochastic one** (T13, 2026-07-29) — every hypothesis on file
for the non-reproducible cloud involved randomness (an Iman–Conover permutation, a seed, an rng);
the cause was float arithmetic inside the database, and the sampler was innocent throughout. The
register's fingerprint — *marginals invariant, per-player assignment moves* — reads as a reshuffle
and reads equally well as **an input wobbling below the noise floor of every aggregate you were
watching**. Corollary, and the reason this cost a diagnosis rather than a fix: the prescription on
file (*thread a seed through the coupling*) would have been built, tested, and would not have worked.

**a column's consumers are not only the models that weight it** (T22, 2026-07-29) — `boom_prob` /
`bust_prob` were logged as latent because no personality's `signal_weights` names them. The
interactive drafter **printed** them, so the live 2026 board told a human that Bijan Robinson and
Puka Nacua never boom (exactly 0.000 — neither played in 2022, where `max(train_seasons)` lands).
On a human-in-the-loop tool the display layer is the consumer that can be wrong at the user
directly. Sibling of *state your bars as oppositions*: an audit that looks only where the model
reads finds only what the model reads.

**`boom_prob_live` / `bust_prob_live` · `volatility_source`** (T22, 2026-07-29) — the boom/bust pair
re-measured on **season − 1** inside the 16.13 enrichment, read-only, leaving the frozen Phase-5
column untouched. `volatility_source` picks that season **from the `weekly` table, never from a
constant** — the defect being repaired *was* a constant that fell four years behind the data — and
asserts the lag is ≤ 1 season. Unseen players stay `NaN`: on the frozen column they were
`fillna(0.0)`, which does not read as "unknown", it reads as *never busts*, and it was worst exactly
for the rookies a floor-seeking manager should most distrust.

**`avg_reach_rounds` / `redraft_reach`** (T18's fix, 2026-07-29) — per-manager mean drift in
**rounds**, every pick scored against **its own draft's board** over the redraft-eligible corpus,
replacing a pooled-board `avg_reach` that reported a **+91.9-pick** mean QB reach. Deleted rather
than repaired in place, in stated units, because a silently redefined column is how F.5's hardcoded
`scoring="ppr"` and T19's changed `floor` both travelled.

**when the sign flips, it was never a behaviour** (T18, 2026-07-29) — the test that settled the
ticket was not that the magnitude fell (35.8 picks → 0.78 rounds) but that the **direction
reversed**: scored against their own boards, quarterbacks go *later* than consensus (−0.58 rounds),
not ninety picks earlier. A statistic that changes sign when you fix its reference was never a noisy
estimate of the thing it is named after — it was a different quantity wearing that name. Cheap
diagnostic wherever a derived per-entity number looks merely *large*: fix the reference and see
whether it shrinks or turns around.

## The value-seam terms (2026-07-30) — Session H.5, T27–T30

**the value seam (T27)** — the join between the number a human reads off the board (`proj_points`,
consensus, re-scored full-PPR) and the number every seat actually optimizes (`base_value` = `ce_vbd`
= Phase-5 CE − positional replacement CE). They are built from **different means** and disagree by up
to **170 points** on the live 2026 board — Drake Maye proj 316.5 → **+68.5**, Jayden Daniels proj
313.4 → **−101.6**, three points apart on screen. Not a bug in either quantity; a **missing bridge**
between two correct ones. The product fix is auditability (`why <player>`, printing the whole chain),
not a model change.

**the level is intended, the dispersion is the defect** — the companion rule for reading a haircut.
The mean gap between consensus and the Phase-5 mean (**0.28 QB · 0.33 RB · 0.28 WR · 0.30 TE**) is
Phase 4.4's measured level optimism working exactly as designed, and "fixing" it would un-do a
calibrated correction. What makes a board unreadable is the **spread** around it (QB 0.15–0.56,
sd 0.12) with nothing on screen explaining who got cut. *Judge a systematic correction by its
variance across comparable players, not by its mean.*

**decompose before diagnosing** (2026-07-30) — `base_value` differs from `vbd` through **two**
channels (the T3 availability haircut inside the Phase-5 mean, then λ·Var, then a subtraction of the
*replacement's own* CE). A single-channel reading — "the variance charge is too big" — fits neither
end of the board: Josh Allen `vbd` +70.0 → `base_value` +55.2 (a 15-point gap) while Daniels +22.6 →
−101.6 (124 points). The arithmetic only closes with all three terms. *Before naming a cause for a
gap between two quantities, write out every term that separates them.*

**slot-blind value (T28)** — `team_value` = `Σ base_value` over all fifteen roster rows, with no
starter/slot logic anywhere in the value path, so a second QB on a 1-QB roster is priced at full
weight in both directions (−101.6 for a bench Caleb Williams, +51.0 for a Hurts taken second). Room
total 1,938; the QB2 line alone nets **−122**. Measured cost: Spearman vs title probability is
**+0.685** for `team_value` and **+0.758** for portfolio CE, against **+0.915** for the starting
nine's Phase-5 mean. *A sum over a roster is not a forecast of a lineup.* The metric is correct as
what it was built to be — "value over replacement, independent players" — and acquired a second,
wrong meaning by being the only team-level number anyone printed.

**fair-share multiple (T29)** — title probability expressed as `title_prob · n_teams`, so a 10-team
league's uniform is 1.00× and 0.170 reads **1.70×**. A ratio to the uniform is immune to the season
sim's documented **−113 pts/team** level bias, which the raw percentage is not. The general form:
*when a model's ordering is calibrated and its level is not, publish the ratio, not the level.*

**a composition question is not a defect (T30)** — `autopilot` sits in 1 of 10 seats against **0.2 %**
of realized seats, and it is the seat that manufactures the spill the room harvests (mean `pool_rank`
**1.77**, median **1.0**, harvest **+11.7 picks**). Every bar passes, so nothing is broken; what is
missing is the **written argument** for the ratio. Booked as a ticket anyway, because an unstated
modelling choice that survives every gate is exactly the kind of thing that is later mistaken for a
measured result. *A null on a composition A/B is a decision, and decisions get written down.*

**a display change that moves a bar is not a display change** — the hard bar carried by every step of
Session H.5: `analysis/mock_room_bars_verify_20260729.json` must reproduce **bit-identically**. The
cheap guard that keeps a "cosmetic" session from quietly becoming a modelling session.

**check the suspicion before you write the ticket** (2026-07-30) — four defects that looked real by
eye and died on contact with the corpus: the QB market (17 QBs for 10 teams is the realized **median
of 16**, over 333 matched drafts), a stale behavioural fit (the corpus is 9 seasons, bulk 2021–25),
elite fall (25.0 % vs a committed 25.2 %), and the reach budget (the reacher spent exactly 3 of 3
swings and 5 of 5 leans, with a rounds-1–3 max reach of −0.1). Each one took a single query, and each
would have produced a plausible, wrong ticket. The four that *did* survive are the register's
T27–T30. *An audit's value is in what it clears, not only in what it opens.*

**a guard that does not run on the path a human uses is not a guard** (2026-07-30, T27) — the
`value_hawk` seat ran the Phase-9 greedy in every batch measurement in the repo and the plain
behavioural softmax in every *human* mock, for as long as both existed. `assert_room_objectives` was
written to catch exactly that and could not, because it lived in `draft/mock.py`'s room builder while
`steps/mock_draft.py` used `personalities.make_room_pick_fn`, which had no `risk` parameter to guard.
The guard moved down the import graph so both builders share it. Generalizes **T22's** lesson (*a
column's consumers are not only the models that weight it*) from columns to assertions: when two code
paths do the same job, the assertion belongs to the one *underneath* both, not to whichever one it was
written in.

**the predictor and the display are different claims** (2026-07-30, T28) — `team_value` sums
`base_value` over all fifteen roster rows, so it prices a bench QB2 as if he started. That is a real
reporting defect: the gap `capital − startable` is negative for every seat except `value_hawk`
(+152.0), which is the only seat that *maximizes* the sum and therefore the only one that hoards
startable-elsewhere value on its own bench. But scored against the Phase-10 title probability over 200
seated-reshuffled drafts, the slot-blind sum is the **better** predictor (+0.8382 vs starter-aware
+0.7971, CI on the difference clear of zero) — because the sim draws injuries, so bench value alone
predicts title probability at **+0.711, positive in 100 % of drafts**. *A number can be misleading to
read and still be the most informative thing you have.* Fix the display; do not assume the objective
was wrong too. (Cf. **the scoring trap**, which is the converse error.)

**a pre-registered bar earns its keep on the day it fails by a little** (2026-07-30, T27→T31) — B2
(`spearman(haircut, games_played_mean) ≤ −0.50` per position) was written into the plan before the
number was known, with an explicit instruction not to soften it. It came back passing at QB/WR/TE and
failing at **RB −0.288** on one board out of three — precisely the result that is effortless to round
off as "basically fine" if the threshold is chosen after looking. Chasing it instead found **T31**, a
real live-season defect worth 22.8 % of the value index. The corollary is the one that costs
something: the gate ships **red**, because a threshold moved to make a report green is not a
threshold. (Distinguish **T12**, red for *no* reason — that kind is worth silencing.)

**role is not availability** (2026-07-30, T31) — the consensus projection and our Phase-5 level
correction both discount a player, for different reasons: consensus prices **role** (a backup is
projected low because he sits behind someone), our correction prices **availability** (an injury /
games-played haircut). For a player consensus expects to start the two coincide, which is why
`haircut ~ games_played_mean` holds at −0.6 to −0.9 on every historical board. For a projected backup
they diverge, and on a **live** season — where there is no realized prior year to shrink the per-game
level toward — the divergence inverts: 22.8 % of the 2026 value index has `mean` **above**
`proj_points`. *Before treating two discounts as the same quantity, check they are discounting the
same thing.*

**the rule decides the borderline case, not the other way round** (2026-07-30, T30) — the T30
composition A/B was agreed in advance to ship "only if every bar holds or improves". It came back
closing **79 %** of the chalk-share gap and **63 %** of the moderate-share gap while regressing two
reach bars by 2.3 % relative and 0.97 pp. Under a rule chosen *after* seeing that, it ships; under the
rule chosen before, it does not. Both readings are defensible, which is the whole argument for fixing
the rule first — otherwise the threshold is just a description of the result.

## Seat-map terms (2026-07-30) — multi-seat human control (16.17 **built**, 14.J planned)

**seat map** (16.17, `draft/personalities.SeatMap`) — the object that says, for each of the `n_teams` seats, whether it is driven by a
**human** or by a named **opponent personality**. It replaces the thing the engine used instead: a
single `DraftState.your_team` int plus the positional arithmetic `seat = team - 1 if team >
your_team else team`, which is only correct when exactly one seat is human. With a seat map, "I take
4 of the 10 teams and give the other 6 personalities" is one construction argument rather than an
unrepresentable state.

**k-of-n control** — the capability the seat map buys: any `k ∈ 0…n` of the seats in a mock may be
human. `k = 1` is the interactive mock; `k = 0` is the fully-simulated room the T15/T24 bars are
measured on; `k = n` is a manual draft board with no engine opponents. Before 16.17 the engine
supported **only** k=1 and k=0, in two separate builders.

**the positional-mapping smell** — a `team → seat` index computed by *skipping* one distinguished
team. It encodes "there is exactly one of these" into arithmetic, where a type would have said so out
loud, and it duplicates: the same three-line skip existed in `make_room_pick_fn`,
`full_room_pick_fn` and the CLI. The tell is that the two builders' docstring already described them
as differing "only in the `team -> seat` mapping" — the difference *was* the design, and H.5 found it
had already cost something (the interactive room ran `value_hawk` as `balanced` for as long as the two
builders existed). Sibling of *a guard that does not run on the path a human uses is not a guard*.
**Built 2026-07-30, and there were four copies, not three** — the fourth was in
`steps/phase16_15_mock_room.py`'s hype-routing measurement, which a scoping pass that grepped the
`draft/` package and the CLI did not reach. *A duplicated formula spreads to the places that measure
it, not only to the places that use it.*

**one draft is one observation** (16.17 honesty rule) — a user who drafts four teams in the same mock
has not run four trials. Every pick made on one of those seats removes a player from the other three
pools, so the rosters are mechanically anti-correlated by construction; a strategy that "went 4-for-4"
went 1-for-1. Consequence for the app: the cost report and draft grade stay **per-seat**, and no
surface may average or aggregate a record across seats one user drove. *Correlated draws presented as
a sample is the same error as reading one draw of ten teams as a Spearman* (H.5's B5).

**bars have a scope, not just a value** (16.17 honesty rule) — the T15 room-realism bars (profile
distance, dispersion, chalk share, elite-fall landing) were all measured on ten **modelled** seats. A
room where four seats are human is not the population they describe, so the honest UI move is to
label the scope rather than silently re-report the number or re-measure it per-mock on n=1.

**the poisoned control** (16.17) — before believing a before/after that reports *no difference*, run
the same comparison against a version deliberately broken in a known way and check that it *does*
report one. 16.17's bit-identity bars re-implement the deleted `team → seat` arithmetic and compare
it to the shipped code; bar 3 rotates that legacy mapping by one seat and requires all 36 runs to
differ. The lesson is T31's, paid for the hard way: its B5 before/after ran post-fix code twice (a
`git worktree` under `uv run --project <main>` resolves the *editable* install back to the main
tree's `src`) and produced identical hashes, which is **indistinguishable from "nothing moved"**.
*A control that cannot fail is not evidence.* The cheap positive check for a worktree control is to
assert the old module lacks the new symbol before trusting any number from it.

**a stale reference is not a control** (16.17) — a committed artifact is a valid before/after
reference only for as long as nothing *else* it depends on has moved. 16.17's spec named
`analysis/mock_room_bars_verify_20260729.json` as its bit-identity bar; by 07-30 that sheet differed
on 77 of 626 fields, all of them in the **2026 live-board readout** (the Stage-0 chore banked a new
FFC board and T31's `ENRICH_VERSION` bump rebuilt the caches against it) or in two `config`
provenance fields added after it was written. None of it was 16.17. The fix is not an argument, it
is a **control run**: the same harness, pre-change code, *today's* data. In a repo with a standing
weekly data chore, expect this — and note the matched-season **gate** fields, which run on
2017–2024, were identical throughout, which is why partitioning a bar sheet into gates and readouts
is worth doing before you need it.

**out-of-support extrapolation** (T31) — the measured cause of the live-board level inversion. The
Phase-5 level is a per-position linear `QuantReg` on `calibrated_mean`, fit on the *conditional*
(available) cohort, i.e. starters; its intercepts are large and positive (QB q50 `b0`=169.35). A live
consensus board runs hundreds of players deeper than any historical proxy board — median 2026 QB
`calibrated_mean` **11.4** against a training **minimum** of 34.1 — so the fitted line is evaluated a
long way below its own support and returns a starter's level for a projected backup. **Board depth,
not season liveness:** `train_seasons` is the same nine seasons for a 2024 board and a 2026 one, so
the models are identical and only the population differs.

**selection-biased low tail** (T31) — the reason "just don't extrapolate" was not enough. The level
fit trains on `weeks >= 0.85*season_games`, so a *low-projection* player who is in the training data
is one who **won a job**. The fit's low end is made of breakouts, which is why interpolating it to the
origin still leaves the violation's sign intact and the repair has to reach for the consensus level.

**cap to the identity, not to the boundary** (T31) — a repair that restores the *sign* of a violated
property can still fail the property. Capping a too-high level at `proj_points` moved the negative-
haircut share 38.75 % → 8.1 % but parked every capped row at `haircut == 0`, a **tie mass** of players
with low projected games and no haircut at all, and full-board QB spearman went the *wrong* way
(+0.474 → +0.523). The bar was never "haircut >= 0"; it was "haircut **is** the availability discount"
(`proj * avail_p / g_ref`). T19's lesson on a repair rather than a signal: *a one-sided fix is passed
by the same defect pointing the other way.*

**a ticket's cause line is a hypothesis** (T13 · T24 · T31) — three filed prescriptions in a row were
wrong, one of them built and rejected. A register entry's cause is written the moment the symptom is
found, which is the moment you know least about it, so re-derive it before building on it. Cheapest
first move: *when a defect is claimed to be about A versus B, check whether A and B actually differ in
the code* — one line ruled out T31's filed cause before anything was written.

**a control that cannot fail** (T31 method warning) — a before/after harness that silently runs the
same code twice returns "bit-identical", which is indistinguishable from the answer you wanted. It
happened twice in one session: `uv run --project <main>` from a `git worktree` resolves the *editable*
install to the main tree's `src`, and a persistent `cd` in a chained command later sent the working-
tree run into the worktree. **Assert the control produces a known difference before trusting it to
show none** — and carry that discriminator (`live_board_changed`) in the artifact, not in memory.

**the bars constrain, the gradient identifies** (T31) — a narrow repair and a wholesale replacement of
the Phase-5 level would both have passed all six pre-registered bars. What distinguishes them is where
the change lands: 0.0 % of top-24-ADP rows moved, ramping to 96.5 % of undrafted ones. Report the
distribution of the change, not just the metrics it satisfied.

**flex group** (17.1) — `(count, eligible_positions)`, the unit `RosterSlots.flex_groups()` returns,
ordered **most-restrictive-first**. Every lineup solver in the repo (`lineup_points_matrix`,
`optimal_lineup_points`, `inseason.lineup._slot_plan`) consumes it instead of reading
`flex`/`flex_positions`, so the fill order is defined once. A **superflex** is simply a second group
whose eligibility adds QB.

**nested eligibility** (17.1) — the condition that makes greedy lineup-filling optimal: each flex
group's positions contain the previous group's. Then a player the narrow slot can use is also usable
by the wide one, so committing the narrow slot first never strands a better assignment. Non-nested
sets (a WR/TE flex beside an RB/WR flex) break the argument and need a per-cell assignment that does
not vectorize — so they are **refused at construction** (`assert_nested`) rather than mis-solved.
*Supporting a format you would answer wrongly is worse than not supporting it.*

**the carry** (17.1) — how multi-flex stays vectorized. Which roster row fills a flex differs per sim
and per week, so used players cannot be removed by identity (the first implementation tried to match
them by value and was wrong). Instead: sort a group's pool descending, take its top `n`, and carry
the **unused tail** forward to the next wider group. Under nested eligibility that carry is exactly
what is still available to the wider slot, per cell, with no loop over cells.

**two greedies that share a bug agree perfectly** (17.1) — why Phase 17's solver gate is an
exhaustive brute force rather than the repo's other lineup solver. Once both consume `flex_groups()`,
agreement between them tests the plumbing, not the answer. Check a generalized optimizer against an
optimum, not against its sibling.

**the marginal position of a wider slot** (17.1) — a superflex admits exactly one position the base
flex did not, so its replacement-level effect falls entirely on QB: **QB10 → QB20** in a 10-team
league, the last starter becoming the last *second* starter. The old proportional-to-demand rule gave
QB 1/6 of the slot and priced a superflex league almost as a 1-QB one. On the live 2026 board the fix
moves the best QB from overall rank 15 to **rank 3**.

**a field that is "only a label" is not, once something keys on it** (17.2) — `ruleset_from_preset
("full_ppr")` first returned identical scoring under a different `RuleSet.name`. `RuleSet` is
serialized into `cached_distribution`'s cache key, so that cosmetic difference would have split the
cache and forced a silent nine-season rebuild. The preset returns `RuleSet()` itself.

**extra="forbid"** (17.2) — the reason a *bounded* scoring field set beats an open `{stat: value}`
map: a misspelled setting must raise at construction rather than score 0.0 all season. Worth noting
that the first implementation had the defect it was designed to prevent — pydantic ignores unknown
fields by default, so `OffenseRules(rec_typo=1.0)` was accepted until `_Rules` was added.

**lockbox_validated()** (17.3) — the programmatic form of "this claim does not transfer". True for
exactly one configuration: the 10-team full-PPR 1-QB league the lockbox was spent on. Every other
format is supported and correctness-tested but carries **no out-of-sample claim**, and Phase 14 is
expected to render that rather than let a user assume the calibration carries over.

**removing supply IS the ADP adjustment** (17.4) — keepers re-inflate everyone's effective ADP
because ADP is a *rank on the remaining board*, so dropping the kept player from the pool is the
whole adjustment. Adding a separate "keeper ADP shift" on top would double-count it. The other half
is the price: the owning team forfeits that round's pick (`skipped_picks`), so keeping three studs
means drafting three fewer times — 147 picks instead of 150.

## Session K1 — the app (2026-07-30)

**one computation, two renderers** — the shape a UI port should take. When a second surface needs
the same numbers as an existing one, do not re-derive them there and then test the two against each
other; move the derivation into one module and make **both** surfaces render it. Testing two
implementations proves they agree *on the case tested*; sharing one proves they cannot disagree.
`draft/session.py` is that module for the draft surface; `steps/mock_draft.py` and `app/` are its
renderers. Generalizes T18/F.5/T27, which are the same defect at three altitudes, and it is
`draft/mock.py`'s own rule turned into a layout: *if the two sides of a comparison are computed by
different code, the comparison measures the code.*

**a renderer formats, it does not derive** — the working test for whether code belongs in a
surface or in the shared core. Formatting a float, choosing a column order, deciding a NaN prints
as `-`: formatting. Subtracting two model outputs: derivation, and it has escaped.

**the fixture was too rich to fail** — why 17 passing unit tests missed two `KeyError`s that a
single real click would have raised. The test board was hand-built carrying every column any
consumer wanted, so a function being handed the *wrong frame* (raw board vs `_prepare_board`'s)
still found what it needed. **A column set is part of a function's contract even when nothing
declares it, and a fixture that satisfies every consumer at once cannot detect that one of them is
being handed the wrong one.** The corollary is a build rule: a UI's done-bar must include *running
it* — here `AppTest` and a real headless server were the only things that caught the second bug.
Sits directly below T22's "a column's consumers are not only the models that weight it".

**board vintage** (T32) — *which snapshot* a resolved board came from: `source` + its single
`snapshot_date`. Sufficient as an identity because `_ffc_board` closes with `QUALIFY snapshot_date
= MAX(snapshot_date) OVER ()`, so a board never mixes vintages. Belongs in any cache key derived
from a board, because `ENRICH_VERSION` covers the enrichment but **not its input** — which is how a
mandated freshness chore could run weekly and invalidate nothing.

**a coincidence that makes a bar pass is not a fix** — T32's gate already read 244/244 before the
key was changed, because an unrelated `ENRICH_VERSION` bump had rebuilt the cache after the last
Stage-0 pull. The defect was real and the pass was accidental. Distinguishing them needs a
**control**: revert the change, re-run the tests, confirm they fail for the stated reason. Same
discipline as 16.17's "the control can fail" bar and H.5's pre-change baseline.

**`lockbox_validated()` is an honesty method, not a feature flag** *(Phase 17, rendered in K1)* —
both branches describe **supported, correctness-tested** leagues. What differs is the *evidence*: one
configuration has a held-out result behind it and every other one has unit tests and no
out-of-sample claim. A UI must render the distinction rather than let a user assume the calibration
travels.

**a bar's name is a claim** — `bar_server` was called "a real headless server boots and serves the
page" and was read as "the app works". It proved the process starts and binds; Streamlit does not
execute the script until a websocket session opens, so an HTTP GET could not see a broken import.
An over-broad name is worse than a missing bar, because a missing bar is visibly missing. State
what a check does **not** cover in the check itself.

**when a control does not fail, suspect the instrument** — reverting the `sys.path` fix left the
server bar still passing, which looked like evidence the fix was unnecessary. It was evidence the
bar was blind. A control that fails to fail is a measurement result about the *measurement*.

**run it the way the docs say** — for anything with an entry point, one bar must launch it exactly
as the README instructs, from outside the repo, with `PYTHONPATH` scrubbed. Import resolution is
configuration, not code: it is invisible to every test that has already configured itself
correctly (pytest's `pythonpath`, an in-process `sys.path.insert`, a `-m` invocation that adds the
cwd). Session K1 shipped a `ModuleNotFoundError` past 18 unit tests, an `AppTest` and a live server
boot for exactly this reason.

**a measurement default and a human default are different objects** *(T34, 2026-07-30)* — fixed seeds
are correct for `steps/`, where every committed artifact is differenced against `--seed 7`, and wrong
for a drafter, whose whole use case is drafting one slot twenty times to see twenty rooms. The K1 app
inherited the CLI's `seed=7` (and `room_seed=None`, which keeps the personalities in their listed
chairs) because the CLI's was the only default that existed, so **every mock draft was the same mock
draft** — reproduced exactly: seat 6 opened Gibbs · Chase · Taylor · McCaffrey · Cook every time.
The fix is two defaults, not one behaviour: entropy in the app with a **lock-the-seed** replay
option, `--seed 7` untouched in `steps/`. Cf. **the seating error is a bias** (T24): the app had also
been showing one fixed seating, which is exactly the thing T24 found flatters by 5–7 pp.

**a hidden tab is still an executed tab** *(T35, 2026-07-30)* — `st.tabs` renders **every** tab's body
on every rerun and hides the inactive ones in the browser. Four tabs meant one keystroke in the draft
room also re-ran the cost tab's whole-board build. It reads as a performance nit until a feature needs
timer-driven reruns (the 14.M pick clock), at which point it is a structural blocker. Related: *the
ergonomic request and the performance defect had the same fix* — the user asked for real pages on
usability grounds and that is also T35's remedy.

**the clock must not lie** *(14.M, 2026-07-30)* — a mock-draft timer that offers "5 seconds per pick"
while the `value_hawk` seat's Phase-9 greedy takes longer is presenting a promise it cannot keep.
Measure worst-case per-seat latency on the live board **before** offering an interval, and refuse or
warn below it. Same family as *a bar's name is a claim*: a UI control is a claim about the system.

**slim vs advanced is a projection, not a second frame** *(14.K/K1.5, 2026-07-30)* — two audiences want
different column counts off the *same* query. The temptation is a second derived frame; the rule is one
derivation site (`session.board_view`) and two column subsets chosen in the renderer. A second
derivation of a shipped frame is how T18, F.5 and T27 each happened.

**import is an alternative constructor, not an integration** *(17.5–17.7, 2026-07-30)* — a league
importer's whole job is `import_league(platform, ident, creds) -> LeagueSettings`. Because Phase 17
already parameterized the board, replacement levels, lineup solver, sim bracket and cost report on that
object, a correct import changes zero lines downstream. Two contracts travel with it: the imported
settings **land in the form for the user to confirm** (a wrong scoring rule does not fail loudly — it
silently re-ranks every player), and anything the platform did not say is left at the engine default
and **labelled inferred**, never guessed.

**the platform you can test is not the platform you need** *(Session K3, 2026-07-30)* — Sleeper is
free, keyless, already-clienting and has an offline fixture; ESPN is undocumented and needs the user's
cookies; Yahoo needs OAuth2 and a hosted redirect. The user plays on ESPN/Yahoo. Build Sleeper first
anyway — for the **contract**, tested against something we own — and say in the report that its
user-facing value is the contract, not the platform. Overselling the cheap one is how a session
delivers nothing.

**a measurement default and a human default are different objects** *(T34, Session K1.5, 2026-07-31)* —
`seed=7` is *correct* for `steps/`, where every committed bar sheet is differenced against it, and
*wrong* for a drafter whose whole use case is drafting one slot twenty times to see twenty rooms. The
K1 port carried the CLI's into the app because the CLI's was the only one that existed, and the result
was a mock drafter that dealt the same draft every time. The fix is two defaults, not one behaviour —
entropy on the app's side of the seam, `--seed 7` untouched on the other — plus the drawn values
recorded in `meta` so *randomized* does not cost *replayable*.

**count the calls, don't time them** *(T35 / bar B1, 2026-07-31)* — the claim "`st.tabs` executes every
tab body on every rerun" is about **how many times a function runs**, so the instrument is a counter
(`app/probe.py`), not a stopwatch. A timing bar would have passed on any day the expensive page was
cheap, and would have said nothing about the case that mattered: a clock ticking every second. Related:
the probe ships in the app rather than being patched in by the test, because *a probe that only exists
under the test measures the test.*

**an import bar and a use bar are different claims** *(bar_flow, 2026-07-31)* — Session K1 shipped a
broken app with nine PASSes and answered it with `bar_imports`, which proves the entry point *imports*.
It does not prove the app *works*. Driving the actual widgets — start a draft with the button, pick a
player with the button, then check the state those buttons were supposed to change — found a
`session_state.setdefault` on a widget key that six pre-registered bars had missed. Any session that
adds UI owes the second bar.

**a constant justified by a measurement needs something that notices when the measurement goes stale**
*(14.M, 2026-07-31)* — the clock floor was set from a real measurement (worst modelled pick 10 ms, i.e.
the pre-registered latency worry did not survive contact with data) and **kept anyway**, paired with a
live overrun notice. A measurement retires today's risk, not the mechanism; the floor is what stops the
*next* slow seat landing picks late in silence.

**a limitation belongs in the tooltip, not in the doc** *(14.O, 2026-07-31)* — `BOOM`/`BUST` carry T22's
*blank means never seen play, not never busts* and `MEAN` carries T31's level cap **in the text a
drafter hovers**, because a caveat a user has to find in `findings.md` is a caveat nobody reads. Its
sibling rule: one dictionary serves every surface and the local copy is *deleted*, since a column's
meaning does move (T22 is the proof) and two help texts are two chances to describe it differently.

**a scale and its labels have to be anchored to the same thing** *(14.I, 2026-07-31)* — the draft grade
scores four components min–max across the ten teams, so a middling roster lands near **50 by
construction**. On plain US bands (90/80/70/60) that is a **D+**, and six of ten teams in an ordinary
room graded D or F: the app calling an average draft a failure, because the letters assumed 50 % was a
fail while the scale's own midpoint was 50. The scoring was never wrong. `GRADE_BANDS` now put `C` at
50. Caught only because the first run printed all ten letters instead of one — *a curve is only legible
next to the population it was drawn on.*

**an invented constant that is visible is a design decision; the same constant buried in a function is
a claim** *(14.I, 2026-07-31)* — the grade's 50/20/15/15 weighting is a presentation choice with nothing
validating it, chosen by the user. Every *input* is frozen and separately validated; the *blend* is not.
That is allowed for exactly as long as a reader can re-add it by hand, so the weights are one named
constant summing to 100, each component's raw value / score / points print beside the letter, and a bar
asserts the total reproduces from the printed parts. Cf. **derived-vs-curated**: the test is not whether
a number is invented but whether the reader can see that it was.

**zero is not a floor** *(14.G, 2026-07-31)* — T22's rule with the opposite sign. A season-points
quantile cannot go below zero, so `enrichment.CENSOR_AT` piles ~36 % of the live board on `q10 = 0.0`.
Printing that as a floor tells a drafter *his downside is zero* when what we have is *no resolvable
downside* — T19's censoring finding arriving in the display layer, where a human actually reads it. The
row reads `censored floor` instead. Sibling: **blank means never seen play, not never busts**.

**a fact about the pool, not about the screen** *(14.E, 2026-07-31)* — the tier cliff is computed over a
seat's whole available pool *before* any position filter or row cap, and a bar asserts it does not move
when the board is truncated to 8 rows. A cliff measured inside the visible window would mean "the tier
runs out on this screen", which is a statement about scrolling.

**a test that cannot fail is the same defect as a bar that cannot fail** *(14.F, 2026-07-31)* — the first
handcuff test drove a full draft on the synthetic board and asserted a property of every row returned.
The board seated no lead back, so it asserted over an **empty frame** and passed while proving nothing.
Rewritten against a four-row stub with a known answer. The live-board coverage stayed, in bar B3, where
the frame is non-empty.

**a bar failing for the wrong reason is a bar nobody trusts the next time it fails** *(B1, 2026-07-31)* —
B1's first run reported the two 16.17 honesty rules missing from a page that renders them: the check
scraped `at.markdown`/`at.caption`, and both are `st.warning`/`st.info`. The page was right and the
instrument was wrong. A false negative costs more than a missing bar, because it teaches you to
discount the next real one.

**deriving the header turned a latent crash into an immediate one** *(14.G/CLI, 2026-07-31)* — the
terminal board's column header was a hand-written literal beside a dict of format strings. Deriving it
from that dict immediately raised *Sign not allowed in string format specifier* — a crash the pre-K2
code would also have hit, on the first NaN in the signed `BV` column, and had simply never met. Two
descriptions of one thing hide each other's bugs until you make one of them read the other.

**moved, not copied** *(14.N, 2026-07-31)* — K1.5 parked the standings, season odds and draft-flow
readouts on the room page because 14.N did not exist yet. K2 **moved** them and the room page kept only
the grid and the log. Two render paths for one table is how the K1 board and the CLI board drifted
apart; the fix is that there is one place, not two that agree today.

**a censored quantity should look different, not be described as different** *(UI-PLAN / UI-1 S3,
2026-08-01)* — 14.G established that ~36 % of the live board sits on the `q10` censoring point and prints
`censored floor` instead of a floor of zero. That is a *sentence*, and a sentence competes with every
other sentence on the page. The display rule one level up: give the epistemics their own visual channel —
a **hatched or half-filled bar** for a censored floor, a `⌀` glyph in `FLAGS`, the explanation in the
tooltip. Generalises to the whole honesty layer (lockbox → badge, `COIN` → chip, grade weights → one line
+ popover). Sibling of **a limitation belongs in the tooltip, not in the doc**, and its converse: the
tooltip is where the *words* go, but the *fact* still needs something on screen the eye lands on.

**compress and relocate, never delete** *(UI-1 S3, 2026-08-01)* — the app carries 68 prose blocks against
9 visual elements and the plan cuts that to ≤ 25. The repo's honesty discipline is not that a caveat is
*true*, it is that the surface **renders**; a badge with a popover renders and is more likely to be read
than a four-line block the eye skips. So the compression bar is **paired** with a render bar over all
seven named honesty surfaces, asserted by driving the app rather than by reading the diff. *A compression
that makes an honesty surface disappear has failed, not succeeded.*

**density is not depth** *(UI-PLAN, 2026-08-01)* — our `ADVANCED` board is **15 columns, two more than
Draft Sharks' full rankings table**, and Draft Sharks' density is the most-criticised property in its own
category reviews, with Footballguys drawing the same complaint. **The two most analytically rich products
in the market are penalised for being analytically rich.** The corollary for any surfacing session: the
work is ranking, encoding and hiding. Adding a column is the easy move and almost never the right one.

**a tier is a claim of statistical indistinguishability** *(UI-2 S2, 2026-08-01)* — the whole category
draws tiers by *value gaps*. Cutting them instead where adjacent **10–90 bands stop overlapping** makes
the tier say something falsifiable: these players are not distinguishable by our own distributions. That
is what `session.coin_flags` already measures (146 of 199 adjacent pairs overlap) and then buries behind
a checkbox — so the change promotes the most-buried honesty column to the board's primary navigation aid.
Boris Chen's thesis executed on our distributions instead of on expert ranks, and the one item in the UI
plan that cannot be copied without a distribution stack. Inherits 14.E's rule: **a fact about the pool,
not about the screen** — tier ids are computed before any filter or row cap.

**a preference that cannot be priced is just a note** *(UI-3 A1, 2026-08-01)* — the reason the plan takes
**tags** (🎯 must · 🚫 never · ↑ reach · ↓ wait, the Cost page's own four kinds) and refuses
drag-to-reorder custom rankings, which every competitor ships. A hand reorder silently replaces the value
model with an opinion while every downstream number keeps claiming to be calibrated. A tag expresses the
same preference **and flows into `personalization_cost`**, so the app can answer what it cost. The
direct-indexing thesis needs the second half; the pretty feature only has the first.

**the docstring and the code disagreed, and the docstring was right** *(T37, 2026-08-01)* —
`draft_room._reach_risk` argues in its own opening line that *"a readout you have to ask for is a readout
nobody asks for"* and then renders inside `st.expander(expanded=False)`. Found by reading the module, not
by any bar, because nothing tests where a widget sits. Sibling of **a test that cannot fail is the same
defect as a bar that cannot fail**: a comment asserting a property is not the property, and the cheapest
place for the two to drift is anything the bars cannot see.

## Session UI-1 terms (2026-08-01) — encoding, and the instruments that measure it

**information architecture (the UI-PLAN finding).** The thing the app was missing, as opposed to
analysis, which it has more of than any product surveyed. Concretely: everything rendered at one
altitude, in undifferentiated tables, with the epistemics carried in prose — **68 prose blocks against
9 visual elements, 0 uses of colour to encode anything.** Every competitor inverts that ratio, and the
two closest to our density (Draft Sharks, Footballguys) are *penalised for it* in their own category
reviews. **The work is ranking, encoding and hiding; it is not adding.**

**position colour (S1).** One hue per position, identical on the board, the room grid, the log, the
roster rail and the post-draft rosters — the primary scanning channel, and the first convention every
surveyed product obeys. It is what makes a **position run** visible in the 14.L grid, which is the only
reason to look at a draft board mid-draft. One constant, `app/palette.POSITION_COLORS`; bar B1 asserts
the six hex strings appear **once** in `app/`.

**Okabe-Ito over the market convention.** The user's palette decision, with its trade named: the market
convention (QB gold · RB red · WR blue · TE orange) buys familiarity and puts **three positions in one
hue family for a deuteranope**. Okabe-Ito is the standard qualitative set built to survive the three
common colour-vision deficiencies. *A scanning channel that does not reach a twelfth of your readers is
worth less than the familiarity it buys.*

**chip vs tint.** The two treatments one palette supports, and both are theme-independent by
construction. A **chip** is a solid hue with auto-contrast lettering, used where a cell *is* a position —
opaque, so its contrast cannot depend on the background. A **tint** is `rgba` at low alpha with **no
text colour set**, used where a cell merely *mentions* one — the browser composites it over whichever
theme is live. *A colour that only works in one theme is a colour that breaks the day someone presses
the toggle.*

**auto-contrast ink.** Choosing a chip's lettering by comparing both candidate contrasts rather than by
a luminance threshold. Written that way because a threshold got it wrong: `#E69F00` has luminance 0.410
and the break-even is **0.179**, so a 0.42 cut lettered QB in white at 2.3 : 1. *A constant chosen by
eye is a constant nobody re-derives when the palette changes.*

**seat strip (S5).** The draft-order strip pinned at the top of the room: one chip per seat in `SeatMap`
order, the team on the clock filled, on deck dashed, your seats marked, the last pick in **position
colour**, a snake-direction arrow, and *your next pick #N, k away*. Convention #4 of the shared design
grammar and the first place a drafter's eye goes. It replaced a line of markdown **and** the collapsed
"The room" expander — the room's composition had been one click away on the page whose subject is the
room.

**attached column.** A column placed onto a rendered board rather than projected out of `board_view` —
`P(THERE)` is the only one. It is a **placement, not a derivation**: `session.attach_reach` moves an
existing frame's column onto an existing frame's rows and computes nothing. It stays out of
`BOARD_VIEW_COLS` because the readout costs a survival simulation per row and every other caller — the
CLI, nine seasons of cached measurement, every bar sheet — would otherwise pay for it. It is still in
`STAT_DICT` and still in the CLI, because *"documented unless it is bolted on"* would be a rule about
our plumbing rather than about the reader.

**the prose census.** The instrument that produced the 68 and the 23: `st.caption` plus the four alert
primitives, counted over `app/*.py` (37 + 31 = 68, matching UI-PLAN §3.1). It **ships inside
`steps/session_ui_1.py`** and reads the "before" from `git show HEAD:`, so both numbers come off one
ruler. `st.badge`, `st.popover` and `help=` are deliberately **not** counted — they are where the text
went, and that is the rule: *an explanation longer than one line moves; a state-dependent fact becomes
a chip.*

**compress and relocate, never delete.** The discipline that governs S3, and the reason B2 ships
**paired** with B3. A compression pass fails *silently* — a surface that stops rendering looks exactly
like a surface that got tidier, and both look like a smaller diff — so the render bar drives the app and
reads what came out, rather than reading the diff.

**★★ a grep cannot tell doing from describing.** Three instruments in one session counted a *mention* as
an *occurrence*: the palette census read hexes out of the docstring explaining them, the `st.json` census
read the comment recording what T38 replaced, and both looked like a failing app. In a repo whose
comments deliberately quote the code they replaced, **a text scan over source is not a measurement of
behaviour** — state the claim about the artifact it is about (a string literal the code evaluates, an
AST `Call`, a rendered element), not about the bytes that mention it. Sibling of *a column's consumers
are not only the models that weight it* (T22) and *a test that cannot fail is the same defect as a bar
that cannot fail* (K2).

**a surface with no rows is not a surface that failed to colour.** Why B1 first reported four of five
surfaces styled. At k = 1 the human seat drafts first, so a mid-draft fixture has an **empty log**, and
an empty log renders "No picks yet" rather than a table. The fixture could not exhibit the thing being
measured. Companion to K2's *a curve is only legible next to the population it was drawn on*.

**partial artifact.** A one-bar run must not be able to overwrite a full sheet. `--only` writes
`analysis/session_ui_1.partial.json`; the house pattern did not, and this session lost a committed
eight-bar K2 sheet to a thirty-second `--only b6` before restoring it from git. *A partial measurement
should not be able to look like a full one.*

**a docstring is not a guard (T37).** The reach readout shipped inside a collapsed expander directly
beneath its own docstring arguing that it must not be, through a whole session in which every bar
passed. Where prose and code disagree, the code is what the user gets — so the fix ships with a bar
(*zero expanders on the draft page*), not with a stronger comment.

**named allowance (B0's second half).** The rule that turns *"the committed sheets still pass"* into
*"and here is exactly what moved and why"*. Every leaf that differs from `git show HEAD:` must match a
category the bar declares in advance — a rendered-element count, a T34 entropy draw, a wall-clock
timing, the one new stat-dictionary entry — and **an unclassified move fails the bar**. Passing and
unchanged are different claims, and a display session that only checks the first has checked the weaker
one. ⚠ It caught `worst_seat` on its first run: **the argmax of a noisy vector is noisier than the
vector**, and a categorical label is the last place anyone looks for a timing artifact.

## Session UI-2 terms (2026-08-01) — value relative to now, construction at pick time, and a null

**`Δ` (ADP countdown).** `adp − DraftState.overall_pick` — where the draft is *right now* against what
the market charges for a player. Positive = the board has not reached his price yet and he is falling
toward you; negative = the draft is past it and taking him is a reach of that many picks. Draft Sharks'
best-reviewed single column, and convention #7 of the shared design grammar: **value is relative to now,
not absolute.** ⚠ Read it against `P(THERE)`, never instead of it — `Δ` is where the *market* is,
`P(THERE)` is what the *fitted room* will actually do before your turn. A big positive `Δ` on a low
`P(THERE)` is the trap: cheap by the market, gone by your pick.

**`BARGAIN`.** `adp rank − overall_rank`, both taken over the **whole board** rather than the shrinking
pool, so it is a **static** property of the player — PLAYER-VIEW bar #5, specced since the card was
written and on a board for the first time. Positive means value the market has not charged for.
⚠ **Its sign is the negation of the expression `BUILD_PLAN` writes.** The plan says
`overall_rank − adp_rank`, under which the best bargains score most *negative*, contradicting
PLAYER-VIEW §5's *green = good for the drafter, always* and its own worked example *"+1.5 rounds of
value"*. No document states a polarity in words, so the words won and the discrepancy is recorded.

**construction flag (`RISKS`).** `⚑` his bye already holds one of your starters · `⛓` he shares an NFL
team with one · `🛡` he closes a handcuff gap · `⌀` censored floor · `◔` no prior at all. The first three
are **deltas of `roster_construction_risk`'s own scalars** between your roster and your roster **plus
him** — the post-draft readout, evaluated at the moment it can still be acted on, rather than a cheaper
look-alike rule. The last two are a strict glyph encoding of `FLAGS`. *One lineup solve per row* is what
it costs, and why it is scoped to the rendered rows.

**scan channel vs read channel.** Why `RISKS` is a second column instead of an edit to `FLAGS`. A glyph
run you sweep a column for and a sentence you read are different jobs, and `FLAGS`' *text* is matched by
K2's bar B4 — **a display layer must not edit the thing a bar reads** (UI-1's rule, carried forward).

**the split (`VALUE` / `RISK`).** `ADVANCED`'s fifteen columns — two more than the densest product in
the market, whose density is the most-criticised thing about it — projected into twelve and nine. Both
stay projections of **one** `board_view` frame, so *one query, N projections* survives the split.
⚠ `advanced` stays in `session.py` and comes **off** the app's control: leaving the undivided view on
the control means nobody ever has to learn the split, and deleting the mode would force an edit to two
committed bar sheets.

**a string anything else can write is an interface.** Why the mode control's option *values* stayed the
uppercase labels the radio used. `board_mode` is a widget key, hence session state; UI-1's bar B3 reaches
the RANGES view by pre-setting it. Lowercasing the values matched no option, the control fell back to its
default, and B3 reported that **two honesty surfaces had stopped rendering** — a deletion alarm caused
entirely by a renamed enum. *Changing a display string is a breaking change even when nothing imports
it.*

**the tier null (T39).** The UI plan's one differentiated feature — *a tier ends where adjacent 10–90
bands stop overlapping* — cuts **1 tier per position** and **2 over the whole board**. Two causes:
**scale**, the median RB band is **228 pts** against a median adjacent gap of **16.3** (**14×**), so
overlap is universal by construction; and a **category error**, because Boris Chen clusters expert rank
*dispersion* (disagreement about placement) while we hold a *predictive interval* (uncertainty about
outcome). T24's lesson on a visualisation: *a relationship measured on one object is not a specification
for another.* Nothing shipped; the rule stays runnable and unwired.

**a threshold at the median is not a cut.** Why the gap-based tier is not a fallback for the overlap one.
*"A tier ends where value falls by more than the pool's local median gap"* fires on **half of all pairs
by definition**, returning ~n/2 tiers whatever the data says. The drop distribution is heavy-tailed, not
bimodal, so how many tiers exist is entirely a function of where the threshold is put — and no
threshold-free answer is available from arithmetic on frozen contracts.

**`False` for two different reasons.** `coin_flags` returns `False` both for *distinguishable* and for
*no band to compare*, and says so in its own docstring — while every published statement of it reports
the single figure **146 of 199 adjacent pairs overlap**, which reads as *27 % are resolvable*. The
decomposition: **147** pairs have both bands, **146** overlap, **1** is a genuine break, **52** are
missing bands. The honest figure is **99.3 % of evaluable pairs overlap**. *An instrument that returns
one value for two states will mislead whoever reads it, including the person who wrote it* — the first
probe in this session made the same error in the other direction.

**redundant colour vs replacement colour.** Why `Δ`/`BARGAIN` may be green/red when the *position*
palette may not. UI-1 rejected the market convention because six positions were carried by hue **alone**,
so a deuteranope lost the encoding outright. Here both columns render an explicit sign, so the hue
duplicates a channel that is already there. **Colour that duplicates an available channel is a
convenience; colour that replaces one is a barrier.**

**measure the colour, do not choose it.** The first `Δ`/`BARGAIN` pair was picked by eye and failed
twice: contrast **2.63** on the app's own dark background (a *mark* needs 3.0) and both poles under 4.5
as **text** on both themes at once — no mid-tone clears AA against near-black and white simultaneously,
which is UI-PLAN §S1's tint trap again. The shipped pair was found by search: worst-case **3.39** across
both surfaces and white, normal-vision ΔE **27.0**, and deuteranopia **21.1** / protanopia **8.1** /
tritanopia **24.9**, surviving because it differs in **lightness** as much as in hue.

**a diverging chart does not inherit the categorical palette.** UI-1 set `chartCategoricalColors` to the
position palette *so that any future chart would inherit it*, and A6's positional-strength chart is the
first chart and deliberately does not. Its job is **polarity** (above or below the room median), position
identity is already carried by the axis label, and a diverging scale with six hues at its midpoint is not
a scale. *The form is chosen by the data's job, and the job decides what colour is free to encode.*

**input vintage (of a control).** *Which version of its data* a bar sheet was measured against. A control
that records only its outputs can tell you a number moved but not **whether its inputs moved**, so a
scheduled data refresh and a genuine regression produce the identical alarm. Introduced 2026-08-01 when
the mandated Stage-0 pull took UI-1's and UI-2's B0 from `all_pass: True` with zero unclassified leaves to
122 and 23 unclassified — with every nested sheet still passing its own bars. It is the **cache-key
lesson (T32) applied to a control**: there the enriched-board cache omitted `board_vintage` and served a
stale board under a fresh name; here the sheet omits it and reports a fresh board as a fault. The fix in
both places is the same — put the vintage in the key, and *classify* the moves it explains rather than
excusing them. See **T41**. *An instrument that does not record what it was pointed at cannot tell you
that the world moved.*

**a control on n = 1.** A guard written to stop a check passing vacuously, which is itself satisfied by a
single observation — so it reports a defect that does not exist as soon as that one case disappears.
UI-2's B3 requires every construction glyph to fire at least once; `handcuff` fired **exactly once** on
the 07-30 board and **zero** times on 08-01, failing the bar while every correctness claim in it
(`mismatched: []`, `FLAGS` byte-identical, unknown byes preserved) still held. The mirror of K2's *a test
that cannot fail is the same defect as a bar that cannot fail*: that one produced a false **pass**, this
one a false **failure**, and both come from letting a sampled fixture decide whether the interesting case
is present. Fix by **constructing** the case, never by loosening the control. See **T40**.

---

## Manager-model terms (2026-08-01, session 5 — planned; spec `docs/BUILD_PLAN.md` §"Sessions VH · MM-1 · MM-2")

**slot-blind objective.** A roster-value quantity that sums over every rostered player without asking which
of them *start*. `team_value`/`portfolio_value` are slot-blind by construction — nothing in
`draft/optimizer.py` references starters. T28 measured this as a **reporting** defect and it is, for nine
of ten seats; for `value_hawk` it is a **behaviour**, because that is the only seat that *maximizes* the
quantity. **T42.**

**capital vs startable.** The two readings of a drafted roster: `team_value` (all 15 players) against
`starter_value` (the lineup that can actually be fielded). Shipped side by side and labelled
`CAPITAL`/`STARTABLE` since T28. The gap is negative for every seat except `value_hawk`, where it is
**+152** — the signature of a seat accumulating value it cannot start.

**★ the predictor/objective gap.** *A quantity that best **predicts** an outcome across agents is not
thereby the quantity an agent should **maximize**.* T28 ranked three roster-value definitions by their
Spearman against title probability and used the ranking to choose an objective; that is a correlational
answer to an interventional question. **This is T24's lesson one level up** — *a relationship measured
on outcomes is not a specification for the mechanism that produced them* — and the third time this repo has
met that shape. The corresponding experiment is always: **run the mechanism both ways and measure what it
builds**, not which summary correlates best.

**★ beliefs vs policy (the manager-model split).** The two independently-learnable halves of "draft like
this person": **beliefs** = where they disagree with consensus about *players* (a **board**); **policy** =
how they trade value / risk / need / scarcity *given* a board (a **decision rule**). A mock draft observes
both at once and identifies neither cheaply, which is why "learn my style" reads as expensive. It is the
reframe's **value-vs-availability** line one level down, and each half has its own instrument.

**choice-set-size invariance.** A pairwise comparison and a real 40-way draft pick are the **same
conditional-logit likelihood** with different choice-set sizes, so elicited comparisons and realized picks
**pool into one fit**. The practical consequence: choosing to elicit does not close the door on revealed
preference later, and no data is stranded.

**★ the informative region.** In a draft, most picks are obvious, and an obvious pick carries almost no
information about the *tradeoff* coefficients — it identifies the level, which ADP already gives you. The
observations that identify a policy are the ones where the drafter is **torn**. They are rare and unplanned
in a real draft and are the *only* thing a designed pair asks about. Hence: **you can design for the
informative region; you cannot sample your way into it** — which is why ~300 designed comparisons beat
20 mock drafts despite a 40-way choice carrying more raw information than a binary one.

**disagreement-only elicitation.** Asking a human only where they **differ** from a reference, because for
everything else the reference already encodes their view. Turns "annotate 250 players" into "annotate ~50",
and is the belief-side instrument. ⚠ Carries an **anchoring** cost — showing the reference value first
compresses stated disagreement — so a **blind subset** ships as its control.

**shrunk deviation (a manager profile).** Fitting a person as a **deviation from the corpus β**, EB-shrunk
by evidence count (`k = σ²/τ²` — 16.4's coach-fingerprint machinery pointed at a manager). At n ≈ 300 over
~15 features a fresh fit is mostly noise while a well-estimated prior already exists, so the honest
deliverable is *per-coefficient shrinkage weights* naming which dimensions are actually the person's.

**`FittedManager`.** A personality whose coefficients load from a **profile file** rather than being
written in code — the design that makes a self-model a **general mechanism with subject #1**, preserving
the 2026-07-23 "nothing personal to the user" decision instead of overriding it. Nothing in the code knows
whose profile it is.

**★ the grader-is-the-subject trap.** The **scoring trap** sharpened. `value_hawk` optimizing our board and
being scored on our board wins by construction; a model fit on a person's stated preferences and scored by
*that person* is worse, because the optimizer and the grader are the same human and no amount of care in
the fit can detect it. The only escape is **held-out prediction** decided before the fit is read.

**held-out pick prediction (the manager-model bar).** Beat the corpus-fit `balanced` on top-1 accuracy and
log-loss, CI clear of zero, against **two** withheld sets: elicited comparisons excluded from the fit, and
**real mock picks never used in fitting**. The second set is what makes the bar about a person rather than
about a questionnaire.

**stated vs revealed preference.** What someone says in a calm elicitation session need not be what they do
on a clock. Measured as the accuracy gap between the two held-out sets above; a large gap is a **finding
about preference instability**, reported rather than patched.

**a faithful replica is not a stronger drafter.** A seat that predicts a human's picks well is a **realism**
deliverable, not an edge one — the spent lockbox already recorded personalization as noise-dominated on
realized points. Ranking on our own board stays **descriptive**; evaluative claims run on realized points.

## Session VH — the value-hawk repair *(2026-08-01)*

**board-vintage pin (`resolve_board(..., asof=)`).** "The newest FFC board **as of** this date"
rather than "the newest board". `asof=None` leaves the SQL identical, and T32's cache key already
carries `board_vintage`, so a pinned board and a live one cannot collide. Exists because the
standing Stage-0 chore banks a new 2026 board every few days and each one is a *different* board —
after the `ffc-20260801` pull the shipped 15-round mock reproduced **10 of 150** picks. The rule it
serves: **you cannot attribute a decision to a mechanism if you cannot reproduce the decision.**

**★ the contended set (the denominator problem).** The handful of candidates an argmax is actually
decided between — in a draft, roughly the top 10 of a 200-row pool. **A term's size must be judged
against the spread *here*, not against the pool.** The value hawk's step-3 context term measures
`sd(context)/sd(eff)` = **0.08** against the whole pool (negligible) and **0.29–0.34** against the
contended top-10 (decisive), while changing 6 of 15 picks. *A term calibrated against the wrong
dispersion looks small right up until it decides the pick* — which is how this one survived 16.14R,
T24, T27, T28 and 16.17 unexamined. See **T43**.

**stale derived artifact.** A committed file that no longer describes the thing it is named after,
with nothing dating it against the code that produced it. `analysis/mock_16_14R_picks.csv` (07-28)
predates T22, T31 and the 08-01 situation refresh, so the roster a human formed an objection
against was unreproducible on **any** board vintage. Worse than having no artifact, because it is
what a human reads. **T41** is this defect for bar sheets; the CSV is the same defect one surface
along.

**★ a control must differ on exactly one axis.** When VH.1 changed the value hawk's divisor, the
frozen pre-16.17 control in `steps/phase16_17_seat_map.py` had to change with it — left verbatim it
would have reported a **T33** difference as a 16.17 **mapping** difference and failed bars 1–3 for
something they were never built to test. The corollary: a control that removes the treatment is not
a control (VH.1's first harness sliced the room to make room for human seats and sliced off
`value_hawk`, then reported that the divisor changed nothing).

**a bug off the measured path.** T33 was live from 16.14R step 6 through 16.17 and **749 tests
passed over it**, because every harness that exercised the value hawk ran at k=0 — where the room
size and the league size coincide. The class: *a defect that is invisible at the configuration you
measure needs a test at the configuration you ship.*

**chaotic amplification (why a share is not a dose).** T33's picks-changed share is 20.7 % at k=1,
**10.2 %** at k=2 and 57.4 % at k=3 — not monotone in the divisor gap, because one changed pick
cascades through every later pick. Read such a number as *"this moved the draft"*, never as a
dose-response curve.

**★ the reach criterion (what the user's objection actually was).** Across the 15 picks he judged,
his labels track one mechanical quantity: mean reach **+5.5** picks on the six he called bad,
**−10.6** on the four he called good, `corr(reach, labelled-bad) = +0.767`. **He objects to
reaching and approves of waiting** — a single criterion, not a bundle of taste, and the reason the
reach **window** rather than the objective is the substantive knob in this session.

**flex-eligibility defeats "redundant".** A second TE in this league is a legal **flex starter**, so
a slot-aware objective has no complaint about one — which is why `starter_aware` does not move the
Kyle Pitts pick that **T42** was opened on. The slot channel owns **QB2** (QB is not flex-eligible)
and not TE2; the ticket's headline evidence pooled the two.

**an echoed flag is not an applied flag.** A run artifact that records `vh_window: 0.5` in its
config block proves the *argument was parsed*, not that it reached the model. VH's `--vh-window`
recorded itself correctly for a whole run in which it changed nothing, because `--shuffle-room`
rebuilt the room per seed and discarded the override. The check that works is the boring one: **the
treatment arm and the control arm must not produce identical numbers.** Third instance of the
doing-vs-describing family, after T22 (the display layer is a consumer) and UI-1 (a grep counts
mentions).

**★ one seat, two jobs (the value-hawk frame).** `value_hawk` is asked simultaneously to be a
**plausible tenth of a calibrated room** and to be **the sharp value-seeker in it**. Only the first
has a corpus to price it against — the T15 realism bars — so every measurement the repo can run
scores the seat on the job the user is *not* complaining about. Measured: corpus round-1 mean reach
**2.868** vs the shipped seat's **2.6405**, i.e. **the seat already reaches slightly less than a
real human drafter**, and tightening its window further costs **+0.0360 profile distance**. So the
objection is not "this seat is unrealistic" but "this seat is not what its name promises" — a
**design** question about which job the seat has, resolvable only by adding a seat beside it and
re-measuring the mix (T30-shaped), never by turning the window down.

**free on outcome, expensive on realism.** A knob can be unresolvable on the metric you evaluate
with and still be firmly decided by a *different* bar. VH.3's window moves realized points ±25
against an se of 9–13 (unresolved) while moving profile distance +0.0360 (decisive). *Price a knob
on every bar it touches before calling it free.*

---

### Data ingest & provenance *(added 2026-08-02, Session DATA-1 scoping)*

**wrapper ceiling.** `nfl_data_py` is a *wrapper* over `nflverse-data` GitHub release assets, so its
function list bounds what we can see, not what exists. Everything it does not expose is **invisible**
rather than unavailable — and an absence nobody can see never gets prioritised. Phase 0.9 met a symptom
("frozen wrapper hits the dead old path") and filed it as a one-off; it was the general case, and it cost
us `pbp_participation` (ten seasons, play grain). The fix is to read release assets directly and keep the
wrapper beside it. **T46.** See [[upstream floor]], [[release-asset loader]].

**release-asset loader.** `data/sources/nflverse_release.py` (0.12.1) — `list_releases` /
`release_assets` / `read_release` over
`releases/download/<tag>/<asset>.parquet`. Its bar is a **control, not a smoke test**: reproduce an
already-ingested table bit-identically *and* assert the control can fail on a wrong asset. T31's rule
verbatim — *assert the control can produce a known difference before trusting it to show none.*

**upstream floor.** The earliest season a source exists at all, as opposed to the earliest season we have
ingested. participation 2016 · NGS 2016 · PFR 2018 · FTN 2022. **The register's most useful column**,
because it is what separates *a gap a session can close* from *a fact about the world*, and without it
the same question gets re-investigated every time someone notices a short panel. Asserted, not
documented: a request below a floor **raises and names the floor** (the `ecr_asof` pattern).

**a source is not ingested until the question that motivated it returns an answer.** DATA-1's bar B4
requires the four questions that prompted the session (box counts faced per RB-week; man/zone share faced
per WR-week; TE/WR snap share *within* 11/12/13 personnel; neutral-script seconds per play per team-week)
to each return a result from one query. Row counts and gates prove a table landed; they do not prove it
answers anything. Cf. [[a test that cannot fail]].

**PIT class.** A declared property of every ingested table — `preseason` (available before a draft) ·
`in_season_weekly` (available only after week *w* is played) · `retrospective` (never a feature).
Participation and FTN are `in_season_weekly`: native and safe for the Phase-13 co-pilot and for variance
work, and usable in a **draft** feature *only* through `features/exposures.py`'s season-*t−1* lag. The
class is read by `assert_panel_pit`/`assert_exposures_pit` rather than trusted to the caller, because PIT
discipline enforced at the read is the one thing that has never failed here.

**ingest all seasons, analyse DEV only.** Loading lockbox-season data does **not** spend the lockbox;
building a feature on it does. The wall belongs at the modelling step, where Phase 16 already put it —
restricting the *ingest* buys no protection and guarantees a re-download later.

**a table nobody reads and a table that does not exist are indistinguishable from the outside.** Why
`ngs` sat ingested-and-unread for eleven months (**T45**) and why the 0.12.2 inventory carries a
**consumers** column. [[a column's consumers are not only the models that weight it]] one level up: T22's
audit looked at the wrong consumer, this one had no artifact that would have shown there were none.

**state a fill rate against its denominator.** Participation's `route`/coverage columns read ~0.38 of all
rows for 2016–2022, which is the **pass-play share**, not 62 % missing. The unconditional rate and the
conditional rate are different claims about the same column, and only one of them is about data quality.
The corollary is the fill-rate **gate**: `ngs_air_yards` went to 0.00 in 2023 with no announcement and no
downstream error — *silent vendor degradation is indistinguishable from a quiet column until something
asserts the rate.*

**one DEV season is not a development set.** `DEV_SEASONS` is 2014–2022, so a source with a 2022 floor
(FTN) contributes exactly one. Twice now this repo has measured what n≈1 produces — T24 calibrated on a
four-season subsample and failed the full sweep; T40's control passed on a single observation. Such a
source ships `backtestable: false` as an **assertion**, because *a docstring is not a guard*.

**point the micro-detail at the week.** Seven alpha hunts aimed at season-level draft decisions (16.1,
16.2, 16.8, 16.9, 16.16, the value-side track, Phase 2) returned seven nulls; the two aimed at weekly
decisions (12.3/12.4, 13.1/13.2) both paid. The **season is the unit of independence** and DEV holds
nine of them, while a weekly effect has n ≈ players × weeks ≈ 10⁵ — the same arithmetic that demoted
"beat ADP". Corollary: aim at the **second moment and availability**, where our own calibration is
documented as weak and consensus publishes nothing at all.

---

### Data ingest & provenance, part 2 *(added 2026-08-03, Session DATA-1 as run)*

**two tables sharing a name.** A single table holding two different grains, distinguished only by
*which columns happen to be null*. Found in `depth_charts`: 401,774 weekly rows (2014–2024, keyed
`season`/`week`) plus 554,215 rows of the 2025 timestamped snapshot series appended with a NULL
`season` — so `group by season` silently dropped **58 %** of it and reported the data as ending in
2024. *A table that answers a different question depending on which rows you land on is not a table
with a missing season.* Diagnostic: a table whose declared grain needs a caveat about nulls.
The fix is to make the grain a **column**, never an inference. See [[declared grain]].

**declared grain / `key_unique`.** Every source states its row key **and whether that key is
actually unique**. Five of 0.12.6's thirteen declarations were false on the first run. *A declared
grain that does not hold is worse than no declared grain* — it invites a downstream join that
silently fans out. Where a source genuinely has no row key (`contracts` emits byte-identical
duplicates; `trades` is one row per **asset moved**, not per trade), that is recorded as a fact
about the source rather than papered over with a synthetic id. The bar checks the declaration in
**both** directions.

**a join rate needs its denominator.** The sibling of the fill-rate denominator rule, one level
up, and it produced a false B3 failure before it was noticed. Participation's raw join to `pbp` is
0.983–0.986 for 2016–2022 and exactly 1.000 from 2023 — which reads like a decaying-backwards data
problem and is not one: the vendor emits an **empty placeholder row** for plays `pbp` does not
carry (~780/season, none after 2022) and *there is nothing in those rows to join with*. On
contentful rows the rate is **1.00000 every season**. Report both; never quietly re-denominate.

**producers vs readers.** The consumers register counts who *queries* a table, excluding the module
that **writes** it and excluding `tests/`. Its first version counted any mention and reported
**zero** unread tables — the ingesting step mentions its own table more than anyone, so a mention
count declares every freshly-landed table well-read. That is [[a grep cannot tell doing from
describing]] landing on the exact column written to catch T45. Second correction: a file can be
**both** (`small.py` writes `schedules` and reads it in `bye_weeks`), so the classification is not
an `elif` chain. **0 readers is a finding** — it found `ngs` (T45, reproduced independently) and
then `pfr_pass`/`pfr_rec`/`pfr_rush` (**T47**).

**named allowance (B0).** An additive session's bar is *"nothing that already existed moved"*, which
is strictly stronger than "all gates pass". Where a session *does* intend to change something
(0.12.7's DOUBLE→INT retype), the change is **declared** and everything else still fails — the same
shape as UI-1's leaf classifier. An allowance is deliberately narrow: it permits a retype of named
columns and **nothing else** (row count, column set and every unnamed column must hold), so it
cannot become a blanket pardon. Cf. [[a test that cannot fail]].

**backtestable flag.** Registered per table and **asserted**, not labelled. `ftn_charting` carries
`backtestable=False` because of arithmetic, not taste: `DEV_SEASONS` is 2014–2022 and FTN's
[[upstream floor]] is 2022, so it contributes exactly **one** development season, and this repo has
twice learned (T24, T40) what an n=1 bar produces. The arithmetic itself is unit-tested, so the flag
cannot drift from its reason.

### Scheme attribution & encoding provenance *(added 2026-08-03, Session DATA-2 scoping)*

**sentinel-fill (vs null-fill).** A vendor switching from `NULL` to a typed placeholder — `False`, `0`
— for "not applicable". The values look complete and mean less. Participation did exactly this at
**2023**: `was_pressure` goes from 31,207 nulls (2022) to 14 (2024), `number_of_pass_rushers` from 72
zeros to 23,754, and the unconditional fill rate climbs **0.38 → 1.00** while the column's meaning
inverts. *Fill rate measures presence; the failure is in meaning.* The companion defect is that a
one-directional gate cannot see it — see [[the gate that only sees drops]]. Diagnostic: a column whose
null share collapses **while its modal value's share explodes** is a re-encoding, not an improvement.
→ T50.

**the gate that only sees drops.** `validate.fill_rate_gate` fails on `was - rate > tol` — degradation
only. A null→sentinel re-encoding is a **rise**, so it passes by design; `store_fill_rates` counts
*nonnull*, so the sentinel counts as filled; and the gate is **whole-table, not per-season**, so a
mid-history break averages away regardless. Three independent blindnesses, each sufficient alone. *The
instrument written to catch `ngs_air_yards` silently going to zero is blind to the exact opposite
failure.* Same family as [[a table nobody reads]] (T45) and the [[wrapper ceiling]] (T46): **an
instrument that measures the thing it can see rather than the thing it is for.** The fix is a
**two-sided, per-season** gate reading a [[break map]].

**break map.** A probed, per-`(table, column, season)` classification — `observed` · `sentinel(<value>)`
· `absent` — that every rate routes its denominator through. Generated, never asserted by hand (the
16.5 derived-vs-curated rule). Its bar is a **control**, not a description: it must find the known 2023
discontinuity *without being pointed at it* and flag a **planted synthetic sentinel**. ⚠ Its job is to
**classify** the break, never to smooth it — *a normalization that makes a discontinuity disappear
without recording it is the same defect as the gate that cannot see it.*

**per-column floor.** An [[upstream floor]] is a property of the **column**, not the table. The register
listed participation at 2016 — correct for personnel, box counts and formation, and **wrong for
coverage**: `defense_man_zone_type`/`defense_coverage_type` are 0.000 in 2016–2017, so their true floor
is **2018** and man/zone has **five** DEV seasons, not seven. *A floor recorded one level too coarse is
worse than no floor: it is confidently wrong at the grain a query is actually written at.* → T49.

**attribution gap.** Data present at the right grain with **no subject to assign it to**. The store
holds 478,989 participation plays carrying `defense_personnel`, `number_of_pass_rushers` and coverage,
and `reference/coaches.csv` is offense-only — so `situation/fingerprint.py`'s whole regime apparatus
(within-season z-scoring, EB shrinkage by regime length, PARTIAL-season week-pinning) has nothing
defensive to run on. *The missing thing is not a number; it is a whole apparatus having nothing to run
on.* → T48.

**defensive regime table.** `reference/defense_coaches.csv` — the defensive twin of `coaches.csv`, and
the same artefact class: **no free source**, hand-researched, per-row `confidence`, **user sign-off
gate**. Copies every discipline deliberately, because the method is already proven: majority-of-games
inclusion, PARTIAL/SPLIT pinned to a week window or dropped outright, `head_coach` auto-filled from
`pbp` so review effort lands only on the coordinator columns, explicit `(none)`/`(unknown)` sentinels.
⚠ Carries **only what no feed knows — who called it**; `base_front` and `coverage_identity` are derived,
not curated.

**the three tiers of coverage.** "Safety coverage" is not one thing and a session must not blur them:
(1) the **charted shell** — `defense_coverage_type`, ~49 % of plays, 2018+; (2) the **derived safety
count** — FS/SS on the field from `defense_positions`, a single-high vs two-high **personnel proxy**,
~76 % pre-2023 and ~100 % after; (3) **pre-snap alignment depth and rotation**, which do not exist free
at any price and are registered as a floor rather than chased. *Labelling tier 2 a proxy is the whole
discipline.*

**team construction.** Cap $ and % by position group, draft capital invested by position over a trailing
window, roster age by group, snap-weighted experience, and **continuity** — the share of snaps returning
from the prior season. Computable today from four tables with **zero readers** (`contracts`,
`weekly_rosters`, `depth_charts_all`, `draft_picks`); computed nowhere. ⚠ `contracts` has no unique row
key — OTC emits 3,339 byte-identical duplicates — so a naive `count(*)` is wrong by construction.

**prove the trap, then prove the gate.** DATA-2's headline bar (B2): report the **naive** and **gated**
blitz rates as a stated difference, in that order. *A fix whose effect is unmeasured is a claim, not a
fix* — and a gate demonstrated only on data that no longer trips it has demonstrated nothing.

## Session DATA-2 run terms (2026-08-03) — the instruments, and the four vocabularies

**the roster names the team, the contract names the money.** 0.13.5's architecture, forced by the
discovery that **`contracts.team` is not a team code**: it is an OTC *nickname* ("Ravens", "49ers")
for 50,134 rows and a *career-path string* ("ARI/ATL/NYJ") for the other 1,659, yielding 90 distinct
values in a 32-team league. Team membership therefore comes from `weekly_rosters` (real codes, per
season, per week) and the contract joins to the **player**. Generalizes: when a dimension column is
unreliable, get the dimension from the table that is *keyed* on it and the measure from the table
that *owns* it.

**the four franchise vocabularies.** The store speaks four, and "we normalized the team codes" was
true of two: **pbp/participation** (the 32 modern codes — `LA`, `LV`, `JAX`), **nflverse alternates**
(`ARZ`/`BLT`/`CLV`/`HST`/`SL`, in `weekly_rosters` and `snaps`), **PFR codes**
(`GNB`/`KAN`/`LVR`/`NOR`/`NWE`/`SDG`/`SFO`/`TAM`, in `draft_picks`) and **OTC nicknames** (in
`contracts`). Each was found the same way — a join came up short and the shortfall had a pattern.
`data/teams.py` is the pbp-side canon; `nickname_map` **derives** the nicknames from `teams_meta`
rather than hand-listing them.

**two canons, and a canon is only canonical within its source.** `adp/panel._TEAM_ALIAS` collapses
the Rams to **`LAR`** (the fantasy boards write LAR); `pbp` writes **`LA`** in every season. Both are
correct *for their source*. Mixing them renames a franchise and the join drops it — **32 teams in, 31
out, no error**, because a missing team is just an absent row. `assert_canons_disagree_only_on_la`
pins the disagreement so a future edit to either is loud rather than silent.

**a reason that is always available is not a reason.** 0.13.8's guard required a dropped
regime-season to carry a stated `drop_reason`, and it passed while six LAR regime-seasons vanished
into the LAR/LA seam — because the reason given, *"no panel row for this team-season"*, is **true of
every possible drop** and so distinguishes a legitimate floor from a join failure not at all. A guard
must test something that **can be false**: the check is now "the drop is below the panel's floor".

**does this column measure football, or our coverage of football?** 0.13.7's distinction, and the
constructive half of T50. A column measuring **football** (`man_share`, `share_cover_3`) must be
**NULL** below its floor — a team that was never charted did not play zero man coverage. A column
measuring **coverage** (`charted_share`, every `*_denom`) is honestly **0** — "none of these snaps
were charted" is true, and it is the only column that *explains* the nulls beside it. Conflating them
made a floor bar fire on four columns doing exactly the right thing.

**a re-encoding that arrives as a population.** The failure mode T52 opens on. 0.13.0's detector keys
on **conservation** — mass leaving NULL for **one** in-domain value. Two of DATA-2's three encoding
seams have a different shape and pass silently: `participation.offense_personnel` (fill 0.7586 →
1.0000 at the same 2023 seam, but 1,468 distinct strings puts it over `MAX_CARDINALITY`, *and* the
arriving mass spreads over hundreds of new strings rather than one sentinel) and
`weekly_rosters.position` (a **vocabulary swap** among observed values at 2016 — nothing to
conserve). *"We have a break detector" is not "we would notice a break."*

**conditioning on a stable population.** The measurement that closes a population-shaped re-encoding,
and B2's shape with a different mechanism: restrict to a set whose membership rule did not change
(here, scrimmage plays) and compare the fill *within it*. `offense_personnel` is **1.0000 filled in
every season** on scrimmage plays — naive break 0.2414, conditioned break **0.0001** — which makes the
shared `play_type in ('pass','run')` filter a **provable** no-op on the rates rather than an
assumption.

**the behavioural denominator trap.** 0.13.6's sibling of the encoding traps, where the distortion is
in the *situation* rather than the vendor. Unconditional 4th-down go-rate (0.170) measures how often a
team faced a hopeless down; conditioned on the situation that offered the choice — 4th and ≤5, open
field, inside two scores — it is **0.296**, a factor of **1.74**. Aggression must be measured against
**opportunity**, never against plays.

**eleven-a-side is football's rule, not the file's.** Why 0.13.4's B4b first failed at ratio 1.0054:
the bar compared each exploded player table against `11 × plays`, but the vendor lists **twelve** men
on 2,739 scrimmage plays and **ten** on 2,171. The expected side was wrong, not the table. A
reconciliation must be written against **what the file emitted**, with the off-eleven rows counted
rather than filtered.

**a rate whose numerator is not a subset of its denominator is not a rate.** 0.13.4's B4a reported a
"resolve rate" of **1.016** because the numerator counted plays claiming 11 offensive men while the
denominator counted plays claiming 11 on *both* sides. A bar that can exceed 1.0 cannot fail; each
side now divides by its own denominator (both are exactly **1.000000**).

**a mean without its n is a number without a claim.** 0.13.6's reporting fix: the first readout
printed a dome mean temperature of **46.0 °F**, which was the mean of **two rows** from a single game
where the vendor logged outdoor conditions under a closed roof. Every mean in the artifact now ships
with the count it was taken over — a fill rate without its denominator, one level down.

**ratios of sums, never means of ratios.** 0.13.7's aggregation rule. A season blitz rate is total
blitzes over total dropbacks; the mean of seventeen weekly rates differs whenever the weekly
denominators differ, which they always do. Where a stored rate has a stored denominator the pair is
re-multiplied before dividing. FTN columns weight on **FTN-charted** snaps, since weighting a 2022+
column by a 2016+ denominator dilutes it with never-charted plays.

**a NULL z is never 0.** A z-score of 0.0 means *exactly league average*. Filling an unmeasured
column with it would put every 2017 team at the league mean for man coverage — the most misleading
thing a z-scored panel can do. `zscore_within_season` guards the division rather than coalescing.

**descriptive only, as an assertion.** 0.13.8's `assert_not_wired_into_the_optimizer` AST-parses
`draft/optimizer.py`, `valuation/value_board.py` and `valuation/cost_report.py` and fails if any
imports the fingerprint module. A future session that wants the wiring **deletes the assertion
deliberately**, which is the point — an unenforced "descriptive only" is a comment (UI-1's lesson 4).

**shrinkage tracks the floor.** In 0.13.8 the EB constant `k` is largest for `man_share` (2.25, a
2018-floor column) and smallest for `blitz_rate` (0.73, 2016 floor), so a one-season coordinator keeps
**28 %** weight on coverage and **58 %** on pressure. A short history pulling a fingerprint toward the
league mean is the machinery working, not a defect.

---

## Manager-model terms, as built (2026-08-05, MM-1a — supersedes the 2026-08-01 "planned" block above)

**`ManagerProfile`.** The file a `FittedManager` seat loads: `beliefs` (player → signed **pick
delta**, positive = drafted earlier), `avoid` (player → reason, a **hard filter**), `belief_scale`,
and a `policy` slot that is **empty until an elicitation session fills it**. A profile with beliefs
and no policy is a *complete* object, not a half-built one — the seat holds one person's opinions
about players and the corpus-average manager's tradeoffs, which is exactly the spec's own honest
expectation ("mostly prior").

**pick delta, as the unit of belief.** Reusing the 16.10 hype board's unit is not cosmetic:
`apply_hype` already converts picks → utility through the opponent model's own `β_adp_s` and
`AdpSpec`, so a belief means the same thing to the simulator as to the human who wrote it, and it
re-derives itself if 11.1 is ever refit. Capped at the same ±24 picks — *a personal board is a
re-ranking of a consensus board, not a replacement for it.*

**★ avoid-as-filter, not avoid-as-weight.** "I will not draft this player" is not a tradeoff, and a
large negative utility *is* a tradeoff — it loses to a strong enough opinion elsewhere on the board.
So declared avoids are applied to the candidate pool, the same class of object as T20's mandatory
needs and the reach budget. ⚠ And they can never empty a pool: a roster has to be completable, or
the preference surfaces as a crash three rounds into a mock.

**★ `unrated` ≠ declined.** A "blank means I would not draft him" rule is about rows the subject
**saw and skipped**. Applied to the whole draftable universe it forbids everyone below the sheet's
depth — here, the kicker he took in all three of his own mock drafts. The rule is scoped to rated
rows and everyone else is neutral: *a player who was never listed was never declined.*

**★ the personal board vs the T24 private board.** Same seam, different object. T24's
`adp + κ·adp_stdev·ε` was measured **harmful** because at the top of the board the draw is the same
size as the gaps it perturbs, so it destroys an ordering that was already correct. A **deterministic,
stated** offset moves a named player in a named direction for a written reason. *The seam is
reusable; the finding is not transferable* — and the two are refused together, because both rewrite
the seat's ADP and running them at once would silently discard one.

**★ where a belief is allowed ahead of the public board.** The personal ADP chooses the seat's
**candidate band** (so a "must-draft" can reach the set it is scored over) but **not** its reach
budget (`CORPUS_REACH_P95` is a measured fact about what real humans do, and a private opinion must
not be a way around it). 16.9 is why the first half is necessary: `top_k` is a hard rank filter
applied *before* utility, which is exactly why the narrative shock came back unidentified — *a
stated opinion that cannot reach the candidate set is a no-op with a note attached.*

**★ three statistics, three winners.** A sweep in which `mean_rank`, `median_rank` and `top1` each
prefer a different setting is **unresolved**, not a tie to be broken by whichever one was written
down first. The shipped rule is the smallest setting within one paired-bootstrap se of the argmin —
a deliberate tie-break toward deviating less from an already-validated room. VH.3's lesson, and
16.14R's dead end, arriving on a third sweep.

**leave-one-DRAFT-out.** The fold for anything scored on realized picks is a **draft**, never a
pick: picks inside one draft share a board, a seat and a running roster, so a pick-level split
leaves most of a draft's information in the training set. 16.8's sibling-derived-feature failure,
arriving on a cross-validation split.

**★ orthogonal beliefs.** `corr(this subject's stated value score, our own model-vs-ADP gap) = 0.135,
Spearman +0.008`. A personal board that is uncorrelated with the model is **new information**, and
by the same token cannot be expected to make the model's answers better. It buys *fidelity*, which
is what the seat is measured on, and nothing else.

**★ a season-scoped belief (the 16.18 PIT gate).** A belief board describes **one season's board on
one date**, so applying it to another season is *look-ahead*, not merely a mismatch — the workbook
was written by someone who had already watched the seasons a historical harness sweeps. Two
properties made it nearly undetectable and both generalize: the leak is **graded** (a profile keyed
on player identity fires on whoever is still on the board — 6 rows in 2017, 55 in 2024), so the seat
reads as *mildly opinionated* rather than broken; and its effect was **smaller than any bar written
to catch it** (profile distance moved 0.0007; all five T15 gates passed on both arms). *A bar that
cannot see a defect is not evidence the defect is absent, and the size of a defect is not the
argument for fixing it.* The fix **degrades rather than raises** — an uncovered season reproduces
the pre-change room bit-for-bit, which is what turns a re-measurement into a construction proof.

## 13-personnel usage terms (2026-08-05) — the productivity half of a package question

**usage within a personnel grouping, and the half that was missing.** `offense_player_week` shipped
`snaps_p11/p12/p21/p13` but targets and carries only for **11/12/21** — so "who was on the field in
13" was a column while "who ate in 13" required dropping to `participation_offense_player_play` ×
`offense_personnel_map` × `pbp`. `targets_p13`, `carries_p13` and `target_share_p13` close it.
*A snap count is presence; a target count is usage, and a package is only a fantasy fact once you
have the second one.*

**★ the thin denominator (`team_targets_p13`).** 13 personnel is a ~3–5% package league-wide, so a
team-week routinely throws **exactly one** target from it — 106 of the 213 team-weeks with any 2025
p13 target — and 106 of the 114 rows reading `target_share_p13 = 1.0000` are that case. The
denominator therefore ships as its own column, in the house `*_denom` idiom, and must be gated on
before anyone is ranked by the share. `p11`/`p12` need no such guard because their denominators are
never that thin. *A share whose denominator can be 1 is not a rate; it is a coin flip wearing a
percent sign.*

**rank beats z on a package column.** CHI's 2025 `share_p13` of 9.64% is **4th of 32**, but
`share_p13_z` reads only **0.78** — LA at 30.79% inflates the SD until a genuine outlier looks
ordinary. On any column with one runaway team, the z-score is a worse instrument than the rank.

**the midseason install.** A season-total package share blends two different offenses when the
package was **added** in-year: CHI ran 13 personnel on 2.5% of wk1–10 snaps and **14.5%** of
wk11–18, so the 9.64% season figure describes no team that ever took the field. Same shape as
[[role-change detection]] on a player, applied to a scheme column — the split is the finding.

**coach prior ≠ coach history.** Ben Johnson's Detroit ran 3.79 / 3.82 / 3.87% 13 personnel across
2022–24 — flat, bottom half, every year — so CHI's 2025 jump is **not** a signature being imported.
*A playcaller's prior is what he did with the personnel he had, not a constant he carries.*

**the mean that is one team.** League-wide `share_p13` went 3.62% → 5.15% in 2025, but roughly 40%
of that move is LA alone. The median (2.49% → 4.41%, highest in the ten stored seasons) and the
count of teams ≥5% (6 → 13) are the honest instruments. *When a distribution has one runaway, report
the median and say so.*


## Bar-sheet comparator terms (2026-08-17, Session UI-3 step 0 — T41 · T40 · T55)

**board vintage stamp.** The ADP snapshot a measurement was taken on, written *into the artifact* as
`board_vintage` (`mock.board_vintage(raw, src)` → `ffc-20260817`). Until this session the bar sheets
recorded their result and not their **input**, so after the mandated weekly Stage-0 pull a comparator
could see 122 leaves move and could not say whether the cause was the world or the code. *A sheet that
does not name its inputs cannot be re-read next week.* Sibling of [[T32]], where the same omission sat
in a cache key instead of a control.

**gate leaf vs readout leaf.** The partition that makes attribution honest. A **gate** is a leaf a
bar's verdict rests on — a `pass` flag, an identity (`differing: 0`), a difference count, an
`n_missing` — and it must hold on *any* board in *any* room, so a moved input can never excuse one. A
**readout** is a leaf the board decides: who got drafted, `capital`, a grade, `n_resolved`. Only
readouts are attributable to `vintage_changed` / `room_changed`, and only when the stamp actually
moved. Ported from `mock_room_bars.py`, whose live season already sat under a top-level `readout_2026`
its own docstring called *"an eyeball readout, never a gate"* — **a partition of the artifact, not an
allowance bolted onto the comparator.**

**the pinned control.** The second half of the same fix, and the half that carries the proof: re-run
today's code on the committed sheet's **board** (`build_board(..., asof=)`) and its **room**, and
require the old measurement back bit-for-bit. Classifying a moved leaf as *the board moved* is a
hypothesis; the replay is the test of it. *A named bucket is not evidence.* Its first run paid for
itself immediately — see the next entry.

**the room is an input.** T41 was written on 2026-08-01 and named one input, the ADP board. MM-1a
seated `fitted_manager` in `REALISTIC_ROOM` on 08-05, and VH.1's T33 divisor fix moved **20.7 % of
picks at k=1** before that — so the 122 unclassified leaves had **three** causes and the interim rule
("all the unclassified leaves are draft-outcome fields → re-baseline") would have waved all three
through as one. **The instrument that can only say "the world moved" is the instrument that says it
when the code moved too.**

**constructed control vs sampled control** ([[T40]]). A control that requires each construction glyph
to fire *somewhere in 40 sampled rows* is a control whose n can go to zero when the board refreshes —
`handcuff` fired exactly once on the 07-30 board and never on 08-01, flipping B3 to FAIL with
`mismatched: []`, i.e. every correctness claim intact. The repair is to **build** the case: the lead
back and his handcuff are deterministic from board order within a backfield, so the fixture seats that
pair and *requires* the glyph. The sampled tally stays in the sheet as a readout. Mirror image of K2's
*a test that cannot fail* — here a control that fails on n = 1 produces a **false alarm** rather than a
false pass, and both come from letting a sampled fixture decide whether the interesting case is there.

**an inert guard** ([[T55]]). A guard that cannot fire on the path a human uses. 16.18's PIT gate
degrades a `requires_profile` seat to `balanced` on a season the profile does not cover — but only if
the constructor is *told* the season, and `app/engine.start_draft` never told it. Third instance in
this repo after T22 and T35: *a guard that does not run on the path a human uses is not a guard.* Its
test's first assertion is that a profile is loaded at all, because an unloaded profile degrades to the
same `balanced` the gate produces — **an inert thing still passes**, for the sixth time.


## Session UI-3 terms (2026-08-17) — preferences as objects

**tag** (🎯 must · 🚫 never · ↑ reach · ↓ wait). A statement about a player, set from the board or
his card, stored by `player_key` and **priced**. The four are not new vocabulary: they are exactly
the four preference kinds `DraftConfig` already accepted, which is the point — *a fifth tag would be
a preference the cost report cannot price*, i.e. a sticker. `session.tag_config` is the one
translation, so the board and the Cost page cannot disagree about what a tag means.

**queue** (⭐). **Ordering, not preference** — a queue entry says *next*, a tag says *how much*. Kept
a separate object because it has no `DraftConfig` counterpart: putting an unpriceable mark on the
page whose whole subject is the price would be the first honesty leak in the feature.

**the workflow the old UI made impossible.** Before UI-3 the only way to state a preference was four
`st.multiselect`s on the **Cost page** — a ~200-entry ADP-sorted list, reached *after* the draft. So
a preference formed while drafting could not be priced, which is the direct-indexing thesis
([[REFRAME-2026-07-04]]) failing at the surface rather than in the model. Tag while drafting, price
afterwards: same object, two pages.

**the skip is rendered.** The queue button walks past a drafted or `🚫`-tagged player to the first
one you may legally take, and **names who it passed and why**. The user chose skip-to-next over
stop-and-say-so (2026-08-17); the naming is what keeps that choice honest, because *a silent skip is
how a queue drafts somebody you did not mean to take.*

**`never` is inviolable, and the UI is where that gets tested.** `never_draft` is a hard constraint
in the S1 preference contract, so the queue refuses a `🚫` player even when he is available, legal
and first in line — the case where refusing him actually costs something, which is the case the test
asserts. Roster legality comes for free by construction: the candidate set *is*
`DraftState.draftable_pool`. *A hard constraint that a button can soften is not a hard constraint.*

**a recorded baseline for a deleted path.** The four multiselects cannot be re-run once removed, so
the `DraftConfig` they produced was written to `analysis/ui3_cost_multiselect_baseline.json`
**before** the deletion, and bar B1 differences the tag-derived config against that record. *A
replacement is only checkable if the thing it replaced was written down first.*

### Step 2 (A2) — the selected-player strip

**the strip.** PLAYER-VIEW §3's glance card, rendered **inline under the board** instead of as a
modal over it. §11 records the compromise it replaces: Streamlit has no hover event, so K2 made one
`st.dialog` serve both §3's glance and §4's deep page — and the cost of that lands at the worst
possible moment, because *the modal covers the board you are picking from*. The strip is the glance
where the glance was specced to be; the dialog stays as the deep page, reached from the strip's own
footer. `views._card_button` ("What do we know about him?") is **deleted** rather than kept beside
it: two controls opening one surface is how the two drift.

**one selection, one `pending_pick`.** Row-select, the queue button, the search and (step 4) the
selectbox all now write the same piece of session state, and the strip renders off *that* rather
than off the selection event. It reads as tidiness and is actually the **testability** fix:
`st.dataframe(on_select=…)` is a client event `AppTest` cannot fire ([[T36]]), so a strip hung off
the selection would have been untestable by construction, while a strip hung off `pending_pick` is
exercised by every other route in. *Where a surface hangs decides whether it can be measured.*

**the two positional ranks** (the trap A2 walked into). The prepared board carries **`pos_rank`,
which is the ADP positional rank** (`_prepare_board` fills it from `adp_pos_rank`) — the market's
order, i.e. the **availability** signal. PLAYER-VIEW bar #1 is *Impact / **value***, so rendering
the column that was sitting right there would have put the availability signal into the value
channel under a label saying otherwise — precisely what the [[REFRAME-2026-07-04]] three-layer
contract forbids ("never one ADP input"). `session.value_pos_rank` is therefore its own function,
ranking `overall_rank` within position over the whole board, and its test **scrambles `pos_rank` and
requires that nothing moves**. On the live 2026 board the two disagree at the very top (ADP's RB1
Bijan Robinson is our RB2). *A name collision between two real quantities is the kind that survives
review, because neither side looks wrong on its own.*

**T39's slot.** The strip was specced as `name · pos · TIER · ADP · …`, but the tier feature
measured out as a null ([[T39]]) and shipped nothing, so the slot carries the **cliff** — 14.E's own
number, which answers what a tier was there to answer: *what does waiting at this position cost.* A
blank slot was the honest alternative; a `TIER` label over a null was not.

### Step 3 (A3) — the bars, drawn

**quasi-bar** (PLAYER-VIEW §5, finally rendered). A label, a number, a filled track and a tick,
built as a **string** (`views.bar_html`) rather than as a render call — which is what lets bar B3
assert §5 *on the markup* instead of on the document. The previous version of this rule lived only
in a document, and what shipped was `st.metric`: a number with no bar, no baseline and no tier. *A
spec is not a surface.*

**polarity, resolved before the renderer sees it.** §5's governing rule is *green = good for the
drafter, always*, so `session.bar_percentiles` returns percentiles that are **already inverted**
where the underlying number is a rate of failure. `CARD_BARS` carries `good = -1` on **`BUST`
alone** — the other seven read high-is-good, including `Q10`, because §2 deliberately chose the
*floor in points* for the downside bar so it would not need inverting. The renderer therefore never
knows which readouts are risk traits, which is the only version of this rule that cannot rot: a
tenth bar added later is inverted in the table or not at all.

**the dual baseline** (§5's Q2 decision, both halves static). The **fill** is the player's
percentile against the whole board; the **tick** beneath it is his percentile among his own
position, spelled out as *"top 15% at his position (n=…)"* so it is legible without measuring a
two-pixel marker. Both are taken over **every boarded player, never the available pool** (user
decision, 2026-08-17): a pool-relative fill would rise every time somebody else was drafted, so the
bar would be measuring *the draft* while claiming to measure the player — and the same player would
read differently on the Board page and in the room. Same static construction as [[the two
positional ranks]] and `_bargain`.

**no reading, no bar.** `pct_overall = None` renders a **dashed empty track** and a `—`, never a
zero-width fill. A zero-length bar is not "unknown", it draws as *worst on the board* — [[T22]]'s
defect in a new medium, arriving for the third time (blank ≠ zero on the board, `0` ≠ *no floor* on
`q10`, and now empty ≠ unmeasured on a bar).

**★ drawing a number is the first thing that asks what its maximum is.** The grade panel's four
contributions had been on screen and correct for two sessions as a table column formatted `%.2f`.
Drawing them required a denominator, the first draft assumed 0–100, and `score_*` is **0–1** — so
every contribution rendered as a near-empty red bar. Nothing about the number had changed; the
*question* had. Sibling of K2's "a scale and its labels have to be anchored to the same thing",
and the reason `views.grade_bars` returns a list a test can read rather than painting to the screen.

**the third tier, measured.** §5's band is green/amber/red and the two poles already existed
(`VALUE_GOOD`/`VALUE_BAD`), so A3 needed exactly one new colour. Okabe-Ito's own yellow `#F0E442`
is the obvious pick from the palette the app already committed to and it scores contrast **1.32 on
white** — a highlighter, legible on the dark theme and gone the moment a reader flips the toggle.
`TIER_MID = #A87900` clears the 3.0 mark floor on all three surfaces (4.86 · 4.43 · 3.89), above
both poles' own minimums. The band is **redundant with the bar's length**, so a reader who cannot
separate the hues loses a convenience and not the encoding — the same test `VALUE_GOOD` passed and
`POSITION_COLORS` deliberately failed.
