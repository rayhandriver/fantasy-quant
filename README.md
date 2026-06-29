# fantasy-quant

A quant-finance-inspired **fantasy football draft model** and (eventually) a **shareable league
app** — applying the factor-risk / direct-indexing techniques from the Alphathena internship to NFL
fantasy: point-in-time features, factor + idiosyncratic decomposition, shrinkage, distributional
projections, correlation-aware roster construction, and a **walk-forward backtest harness** that
doesn't lie.

> **The thesis in one line:** you probably *won't* out-predict consensus ADP on raw points — so the
> edge comes from **structural alpha** (roster/schedule/variance optimization, the tax-loss-harvesting
> analog) and **mining persistent biases in the under-scrutinized ADP market**. See `docs/STRATEGY.md`.

## Docs (read in this order)
| File | Role |
|---|---|
| `docs/STRATEGY.md` | The full feasibility analysis, parallels to Alphathena, factor taxonomy, and rationale. **Start here.** |
| `PROJECT.md` | The **WHAT** — goal, scope, phases, done-when bars. |
| `PLAN.md` | The **HOW** — living working notes (decisions, dead ends). Owned by Rayhan. |
| `ROADMAP.md` | Phase-by-phase status tracker. |
| `CLAUDE.md` | Working guide + discipline rules for anyone (incl. Claude) touching this repo. |
| `glossary.md` | Living glossary of fantasy + quant terms. |
| `findings.md` | Running log of what each step produced and taught. |

## Setup
Uses [uv](https://docs.astral.sh/uv/) with a pinned **Python 3.12** (chosen over the machine's 3.14 for
ML-wheel compatibility — see `CLAUDE.md`).

```bash
cd ~/dev/repo/fantasy-quant
uv sync                 # creates .venv (Python 3.12) + installs the core stack
uv sync --extra data    # add NFL data sources (nfl_data_py) — see CLAUDE.md
uv run python -c "import fantasy_quant; print(fantasy_quant.__version__)"
```

Run things with `uv run <cmd>` (no manual venv activation needed). The package installs editable, so
`import fantasy_quant` works anywhere — no `sys.path` bootstrap.

## Layout
```
src/fantasy_quant/   # the importable package (data, features, projections, covariance,
                     #   valuation, draft, backtest, adp)
steps/               # phased, runnable scripts (one per PROJECT.md phase/step)
notebooks/           # exploration
analysis/            # results, scorecards, figures
data/                # raw / interim / processed + the DuckDB store (gitignored)
tests/               # pytest
docs/                # STRATEGY.md and design notes
```

Status: **environment scaffold only — no modeling code yet.** Phase 0 (data pipeline + PIT backtest
harness) is next.
