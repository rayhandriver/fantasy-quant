# CLAUDE.md — working guide for the fantasy-quant repo

Instructions for anyone (including Claude) working in this repo. Mirrors the discipline that made the
Alphathena `intern-repo` work. **Read `docs/STRATEGY.md` (esp. its Part 0 reframe), `PROJECT.md`, and
`docs/PERSONALIZATION.md` before writing code.**

> **⟳ REFRAME (2026-07-04).** Objective is now **direct-indexing personalization**, not beating ADP:
> `docs/REFRAME-2026-07-04.md`. Value = **consensus projections → VBD**; availability = **ADP + a
> behavioral model**; variance = **our own distributions** (never one "ADP" input). **No LLM in the core.**

## 1. What this is
A quant-inspired fantasy football **personalization engine**: build each user a fully-optimized team from
their own constraints and **honestly price the cost** of each preference vs the consensus-optimal team
(the direct-indexing reframe). The honest value is **personalization + cost transparency + calibrated
projections + correlation-aware construction** — **not** out-forecasting consensus (which our own Phase-2
backtest shows is unwinnable on ~10 seasons). Team strength is a **tracked benchmark**, not the objective.

## 2. Environment & how to run
- **Package/Python manager: `uv`** with a **pinned Python 3.12** (`.python-version`). We deliberately do
  **not** use the machine's system Python 3.14 — some ML wheels (XGBoost/LightGBM/PyMC) lag on brand-new
  Python. uv downloads and manages the 3.12 toolchain itself.
- Create/refresh the env: `uv sync` (core) · `uv sync --extra data` (NFL sources) · `uv sync --extra bayes`
  (PyMC, when Phase 4 needs hierarchical priors).
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
3. **Calibration > edge (⟳ reframed 2026-07-04).** The bar is **well-calibrated**, not ADP-beating:
   value projections pass reliability/coverage checks; availability beats ADP+noise on **Brier** over real
   picks; the cost report leads with robust **relative** numbers. *(Old rule — "beat ADP + the betting
   market" — is retired: our own Phase-2 backtest shows an 80-PAR edge is unresolvable on ~10 seasons, so
   we stop fighting that fight. "Beat ADP" is an optional curiosity.)* Value = **consensus projections →
   VBD**; don't rebuild a beat-the-market projection.
4. **Reuse before you write.** Search `src/fantasy_quant/` first; don't rebuild a primitive.
5. **Guard every output.** Projections/rankings pass sanity gates (no impossible values, plausible ranges,
   calibrated intervals) — the analog of the intern repo's covariance hard gate.
6. **Document as you go.** Decisions + dead ends → `PLAN.md`; what each step produced/taught → `findings.md`;
   new terms → `glossary.md` (keep it current — see the memory note on glossary maintenance).
7. **Sub-phase gate — STOP between every sub-step.** After finishing each numbered sub-step (0.2, 0.3, …,
   1.1, …) deliver a short overview of what was accomplished and **explicitly ask the user for permission
   before starting the next sub-step.** Never chain sub-steps without that approval. This applies across the
   **entire** project, every phase. (User instruction, 2026-06-30.)

## 4. Watch out for
- **Look-ahead via "current" snapshots.** End-of-season stats, final ADP, injury outcomes — never let them
  leak into a historical as-of step.
- **Survivorship** — panels of "players who stayed relevant" flatter results. Document it as a limitation.
- **Overfitting the tiny sample** (~3,750 player-seasons). Stay in regularized-linear / GBT / hierarchical-
  Bayes territory; **no deep nets**. Correct for multiple testing when mining ADP biases.
- **Personalization baking in bias.** Always show personalized boards next to the pure-projection baseline;
  treat large divergences as hypotheses to test, not preferences to lock in.
- **PIT-clean ≠ out-of-sample-clean (the lockbox rule, ⟳ 2026-07-04).** PIT stops temporal leakage, not
  overfitting from repeatedly selecting on the same ~10 seasons. **Freeze a lockbox** (the two most recent
  affordable seasons), never touch it during development, and evaluate the final chosen stack there **once**.
- **No LLM in the core (⟳ 2026-07-04).** All in-app AI is deferred post-MVP; the deterministic core never
  depends on an LLM. When AI is added later it's **on the edges** (fuzzy input → validated object, or
  numbers → narrative) — it never computes a number that must be correct.
- **Own the contracts.** The human owns the data contracts between components (the `DraftConfig` constraint
  object, the projection output shape); delegate the interiors. Contracts drift silently if the AI owns them.

## 5. Structure map (one focused file per aspect — the AlphaThena methodology)
Each step in `PROJECT.md` §5 lands in its **own module** (mirroring the intern repo's separate files for
wash-sales / rebalancing / construction). Packages beyond the current eight are **created as we reach their
phase** — do not pre-create empty trees.

| Concern | Package | Status |
|---|---|---|
| Data ingest (nflverse/PFR/ADP) + DuckDB panel + validation | `src/fantasy_quant/data/` | exists |
| **Vegas markets** (odds ingest, de-vig, props projection) | `src/fantasy_quant/markets/` | exists |
| **News/NLP** ingest + LLM extraction + event studies | `src/fantasy_quant/news/` | exists |
| Feature/exposure engineering (`X`) | `src/fantasy_quant/features/` | exists |
| Projections (baseline, GBT, age curves, hier-Bayes, quantile, conformal, injury) | `src/fantasy_quant/projections/` | exists |
| **Causal** player-in-system (decompose, counterfactual, transport) | `src/fantasy_quant/causal/` | planned |
| Player-week covariance + shrinkage + copulas | `src/fantasy_quant/covariance/` | exists |
| Valuation (VBD, conditional-VBD, structural-alpha, utility, objective, handcuff) | `src/fantasy_quant/valuation/` | exists |
| Draft (simulator, greedy policy, opponent model, MCTS, CFR, auction) | `src/fantasy_quant/draft/` | exists |
| Season/playoff **simulation** + leverage | `src/fantasy_quant/simulation/` | planned |
| **In-season** co-pilot (re-project, lineup, waivers, streaming, trades) | `src/fantasy_quant/inseason/` | planned |
| PIT walk-forward **backtest** harness + metrics + significance | `src/fantasy_quant/backtest/` | exists |
| **ADP-bias mining** | `src/fantasy_quant/adp/` | exists |
| The **app** (FastAPI backend, Next.js frontend, widget) | `src/fantasy_quant/app/` (+ `app/frontend`) | planned |
| Multi-format (dynasty/best-ball/DFS) | `src/fantasy_quant/formats/` | roadmap |
| Phased runnable scripts (one per step) | `steps/` | exists |
| Results / scorecards | `analysis/` | exists |

## 6. Do not
- Do **not** install into system Python or the intern-repo venv. Use this project's `uv`/`.venv` only.
- Do **not** evaluate a method on in-sample fit or a single season.
- Do **not** commit data artifacts (gitignored) or secrets (`.env`).
