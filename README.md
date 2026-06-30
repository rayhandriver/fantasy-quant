# fantasy-quant

A quant-finance-inspired **fantasy football draft model** and (eventually) a **shareable league
app** — applying the factor-risk / direct-indexing techniques from the Alphathena internship to NFL
fantasy: point-in-time features, factor + idiosyncratic decomposition, shrinkage, distributional
projections, correlation-aware roster construction, and a **walk-forward backtest harness** that
doesn't lie.

> **The thesis in one line:** you probably *won't* out-predict consensus ADP on raw points — so the
> edge comes from **structural alpha** (roster/schedule/variance optimization, the tax-loss-harvesting
> analog), **mining persistent biases in the under-scrutinized ADP market**, and **borrowing the much
> sharper betting market** (props / totals). See `docs/STRATEGY.md`.

## Docs (read in this order)
| File | Role |
|---|---|
| `docs/STRATEGY.md` | The **WHY** — feasibility, parallels to Alphathena, factor taxonomy, advanced topics. **Start here.** |
| `docs/BUILD_PLAN.md` | The **detailed step-by-step execution manual** — every step's Goal · Do · Out · Done · Reuse. |
| `PROJECT.md` | The **WHAT** — goal, scope, decisions, and the granular Phase 0–15 plan index (one file per aspect). |
| `PLAN.md` | The **HOW** — lab-notebook: per-step working notes only (no scope/decisions duplication). |
| `ROADMAP.md` | Phase/step **status** checklist. |
| `CLAUDE.md` | Working guide + discipline rules for anyone (incl. Claude) touching this repo. |
| `glossary.md` | Living glossary of fantasy + quant terms. |
| `findings.md` | Running log of what each step produced and taught. |

## Setup
Uses [uv](https://docs.astral.sh/uv/) with a pinned **Python 3.12** (chosen over the machine's 3.14 for
ML-wheel compatibility — see `CLAUDE.md`).

```bash
cd ~/projects/fantasy-quant
uv sync                 # creates .venv (Python 3.12) + installs the core stack
uv sync --extra data    # add NFL data sources (nfl_data_py) — see CLAUDE.md
uv run python -c "import fantasy_quant; print(fantasy_quant.__version__)"
```

Run things with `uv run <cmd>` (no manual venv activation needed). The package installs editable, so
`import fantasy_quant` works anywhere — no `sys.path` bootstrap.

## Layout
```
src/fantasy_quant/   # the importable package — one focused module per aspect.
                     #   existing: data, features, projections, covariance, valuation, draft, backtest, adp
                     #   planned (added as phases are reached): markets, news, causal, simulation, inseason, app, formats
steps/               # phased, runnable scripts (one per PROJECT.md step)
notebooks/           # exploration
analysis/            # results, scorecards, figures
data/                # raw / interim / processed + the DuckDB store (gitignored)
tests/               # pytest
docs/                # STRATEGY.md (the WHY) and design notes
```

Status: **environment scaffold + docs only — no modeling code yet.** Next: **Phase 0.2** (nflverse ingest);
see `PROJECT.md` §5 and `ROADMAP.md`.
