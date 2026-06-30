# Glossary — fantasy-quant

Living reference for the fantasy + quant terms in this project. Updated as we complete steps (keep it
current — there is a standing memory note about glossary maintenance). New terms fold into the right
section, not just appended.

> **Last updated:** 2026-06-29 — added betting-market & advanced (beyond-Alphathena) terms; Vegas markets
> are now a first-class data source.

## Fantasy / draft terms
- **ADP (Average Draft Position)** — consensus draft cost of a player; the "market price." Sources differ
  (best-ball vs redraft vs dynasty) with systematic biases.
- **VBD (Value-Based Drafting)** — value = a player's projected points minus a positional **replacement
  level** (e.g. RB24 in a 10-team league). Turns cross-position points into draftable value.
- **Conditional-VBD** — value of a pick = points now − **expected best-available at your next pick**
  (expectation over the random draft order between your picks). The option-pricing flavor of VBD.
- **Points-above-replacement (PAR)** — the simpler headline backtest metric: expected starting-lineup
  points above replacement.
- **Replacement level** — the baseline a position is measured against (last reliably startable player).
- **Tier / comparative dropoff** — the gap to the next player at a position; steep dropoffs justify reaching.
- **Handcuff** — a backup (usually RB) whose value is contingent on the starter's injury — a **real option**.
- **Stack** — correlated teammates (e.g. QB + WR1) drafted together to raise roster ceiling.
- **Structural alpha** — edge from roster/schedule/variance construction, *orthogonal to projection
  accuracy* — the tax-loss-harvesting analog. See `docs/STRATEGY.md` Part 12.
- **ADP alpha / ADP-residual** — how much a player out/under-performed their draft cost; the dependent
  variable in ADP-bias mining (Part 13).

## Feature / factor terms
- **Target share, snap share, route participation, carry/touch share** — opportunity/volume factors (the
  dominant predictors).
- **Air yards / aDOT / WOPR** — depth and weighted-opportunity measures.
- **YPRR (yards per route run)** — efficiency, relatively sticky for WRs.
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

## Discipline terms
- **Point-in-time (PIT)** — no post-as-of data may touch an as-of estimate.
- **Walk-forward / horse-race** — out-of-sample evaluation rolling through past seasons; the only honest test.
- **Look-ahead bias / survivorship bias** — the two classic backtest-inflators to design out.
- **Block bootstrap** — resample blocks of the realized-difference series for CIs that respect autocorrelation.
