# Glossary — fantasy-quant

Living reference for the fantasy + quant terms in this project. Updated as we complete steps (keep it
current — there is a standing memory note about glossary maintenance). New terms fold into the right
section, not just appended.

> **Last updated:** 2026-07-04 — added Phase-2 baseline/market terms; Phase 2 complete.

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
  of the intern repo's style-exposure matrix.

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
- **Quadratic / expected-utility roster scoring** — concave utility for starters (floor), convex for late
  dart-throws (ceiling) — makes "consistency vs volatility" concrete.

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
