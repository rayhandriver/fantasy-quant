# Glossary — fantasy-quant

Living reference for the fantasy + quant terms in this project. Updated as we complete steps (keep it
current — there is a standing memory note about glossary maintenance). New terms fold into the right
section, not just appended.

> **Last updated:** 2026-07-07 — added personalization-spine implementation terms (`base_value` =
> risk-adjusted value-over-replacement, reach budget / secured fraction, leave-one-out attribution).
> *(Prior: 2026-07-05 Phase-4 value terms — consensus two-track, VBD value board contract, draft-time
> replacement, rookie model, bias ratio / correction / survivorship haircut; 2026-07-05 Phase-3 feature
> terms — exposure matrix, TD-regression, winsor-z.)*

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
- **Adaptive archetype** — a preset (Zero RB, Hero RB, …) that **abandons the plan when the board breaks**
  (elite RBs slide → drop Zero RB). The one archetype most worth the quant.
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
