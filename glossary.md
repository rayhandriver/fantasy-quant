# Glossary — fantasy-quant

Living reference for the fantasy + quant terms in this project. Updated as we complete steps (keep it
current — there is a standing memory note about glossary maintenance). New terms fold into the right
section, not just appended.

> **Last updated:** 2026-07-25 — **16.3b playcaller-regime terms** (play-caller vs HC vs OC · playcaller
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
