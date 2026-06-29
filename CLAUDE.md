# CLAUDE.md — working guide for the fantasy-quant repo

Instructions for anyone (including Claude) working in this repo. Mirrors the discipline that made the
Alphathena `intern-repo` work. **Read `docs/STRATEGY.md` and `PROJECT.md` before writing code.**

## 1. What this is
A quant-inspired fantasy football draft model (factor model + covariance + distributional projections
+ a walk-forward backtest), heading toward a shareable league app. The honest edge is **structural
alpha** and **ADP-bias mining**, not out-forecasting consensus — see `docs/STRATEGY.md` Parts 11–14.

## 2. Environment & how to run
- **Package/Python manager: `uv`** with a **pinned Python 3.12** (`.python-version`). We deliberately do
  **not** use the machine's system Python 3.14 — some ML wheels (XGBoost/LightGBM/PyMC) lag on brand-new
  Python. uv downloads and manages the 3.12 toolchain itself.
- Create/refresh the env: `uv sync` (core) · `uv sync --extra data` (NFL sources) · `uv sync --extra bayes`
  (PyMC, when Phase 2 needs hierarchical priors).
- Run anything with **`uv run`** (e.g. `uv run python steps/<script>.py`, `uv run pytest`, `uv run ruff check`).
  No manual `source .venv/bin/activate` needed.
- The project installs **editable** (src layout), so `import fantasy_quant` works with no `sys.path` hack
  (an improvement over the intern-repo's bootstrap). Put reusable logic in `src/fantasy_quant/`, runnable
  phase scripts in `steps/`.
- Jupyter kernel: **"Python (fantasy-quant)"** (registered via ipykernel). Notebooks live in `notebooks/`.

## 3. The discipline (non-negotiable — ported from the intern project)
1. **Point-in-time (PIT) everywhere.** When building any as-of feature/projection/ranking, **no data
   dated after the as-of** may touch it. Enforce it structurally (filter at the read), not after the fact.
   This is the single easiest way to fool yourself.
2. **Walk-forward, never in-sample.** Rank methods on **realized out-of-sample** outcomes (backtest over
   past seasons), not on in-sample fit. Report effect size **+ bootstrap CIs**, not a single season.
3. **Beat the baseline before getting fancy.** Every modeling step must beat (a) the prior step **and**
   (b) consensus ADP on the walk-forward, or it doesn't ship. Expect fancy models to lose — that's a
   finding, not a failure (cf. PCA beating the fundamental factor model in the intern project).
4. **Reuse before you write.** Search `src/fantasy_quant/` first; don't rebuild a primitive.
5. **Guard every output.** Projections/rankings pass sanity gates (no impossible values, plausible ranges,
   calibrated intervals) — the analog of the intern repo's covariance hard gate.
6. **Document as you go.** Decisions + dead ends → `PLAN.md`; what each step produced/taught → `findings.md`;
   new terms → `glossary.md` (keep it current — see the memory note on glossary maintenance).

## 4. Watch out for
- **Look-ahead via "current" snapshots.** End-of-season stats, final ADP, injury outcomes — never let them
  leak into a historical as-of step.
- **Survivorship** — panels of "players who stayed relevant" flatter results. Document it as a limitation.
- **Overfitting the tiny sample** (~3,750 player-seasons). Stay in regularized-linear / GBT / hierarchical-
  Bayes territory; **no deep nets**. Correct for multiple testing when mining ADP biases.
- **Personalization baking in bias.** Always show personalized boards next to the pure-projection baseline;
  treat large divergences as hypotheses to test, not preferences to lock in.

## 5. Structure map
| Concern | Location |
|---|---|
| Data ingest + scraping + DuckDB store | `src/fantasy_quant/data/` |
| Factor taxonomy / exposure building | `src/fantasy_quant/features/` |
| Mean + quantile projections | `src/fantasy_quant/projections/` |
| Player-week covariance + shrinkage | `src/fantasy_quant/covariance/` |
| VBD / conditional-VBD / structural-alpha valuation | `src/fantasy_quant/valuation/` |
| Draft simulator + policies (MCTS later) | `src/fantasy_quant/draft/` |
| **PIT walk-forward backtest harness** | `src/fantasy_quant/backtest/` |
| **ADP-bias mining** (the self-contained early workstream) | `src/fantasy_quant/adp/` |
| Phased runnable scripts | `steps/` |
| Results / scorecards | `analysis/` |

## 6. Do not
- Do **not** install into system Python or the intern-repo venv. Use this project's `uv`/`.venv` only.
- Do **not** evaluate a method on in-sample fit or a single season.
- Do **not** commit data artifacts (gitignored) or secrets (`.env`).
