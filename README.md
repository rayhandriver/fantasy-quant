# fantasy-quant

[![CI](https://github.com/rayhandriver/fantasy-quant/actions/workflows/ci.yml/badge.svg)](https://github.com/rayhandriver/fantasy-quant/actions/workflows/ci.yml)
[![Team Book](https://github.com/rayhandriver/fantasy-quant/actions/workflows/teambook-weekly.yml/badge.svg)](https://github.com/rayhandriver/fantasy-quant/actions/workflows/teambook-weekly.yml)

An NFL analytics platform built on the methods of quantitative portfolio management: point-in-time
data, walk-forward evaluation, calibrated distributions, and a held-out test set spent exactly once.
It has two public faces:

- **[Team Book](https://rayhandriver.github.io/fantasy-quant/)** — every NFL team's offensive and
  defensive scheme, players and play-callers, ranked against the league for every season from 2018
  to the one being played. 32 teams × 9 seasons, ~90 metrics per book, refreshed weekly by a GitHub
  Actions job with no database behind it.
- **A fantasy draft engine and app** — builds the roster a user actually wants under their own
  constraints, and prices what each preference costs against the consensus-optimal team.

[![Team Book — Chicago Bears 2025, offense](docs/img/teambook-offense.png)](https://rayhandriver.github.io/fantasy-quant/#/CHI/2025/offense)

**~32k lines of Python · 1,000+ tests · June–October 2026.**

---

## How it got here

The project began as one question and changed shape every time the data answered it.

**Jun 29 – Jul 3 · The foundation.** A DuckDB store of point-in-time tables (play-by-play, weekly
stats, rosters, ADP snapshots, betting lines, injuries), a league scoring engine, a draft simulator,
and a walk-forward backtest harness with block-bootstrap confidence intervals. Every feature is
filtered *at the read* to what was known on its as-of date, so a look-ahead leak is a query that
cannot be written rather than a bug to find later.

**Jul 4 · The pivot.** The first models went through the harness and the harness gave an honest
answer: a projection model scored **−59 points/season against consensus ADP, 95% CI [−162, +33]**.
A power calculation on those standard errors showed that detecting even a large edge would need
~27 seasons of history; there are ~10. Rather than keep fighting an unwinnable inference problem,
the objective changed to one that *can* be checked inside a single draft — the
[direct-indexing](docs/REFRAME-2026-07-04.md) idea from asset management: take the market's
consensus for value, personalize the portfolio, and report the cost of every deviation.

**Jul 5 – 12 · The engine.** Value from consensus projections; a per-player distributional layer
(quantiles, injury and games-played risk); a covariance model so roster construction sees
correlated outcomes; a Monte Carlo season and playoff simulator; a draft policy with positional
scarcity and lookahead; and an in-season co-pilot — a Kalman-filter re-projection that beat static
preseason projections in **6 of 6** seasons out of sample, and a start/sit optimizer worth
**+2.1 points per lineup-week**.

**Jul 10 – 19 · Audit, then the lockbox.** A full-codebase audit opened a technical-debt register
that is still the project's backbone (now 57 entries, each with a cause, a fix and a verification).
A Monte Carlo tree search draft engine was built, beat the greedy policy on its own objective, failed
to beat it on realized points (Δ +32, CI spans zero, at 100× the compute), and was **dropped on a
bar set before it ran**. The full stack was then frozen, the evaluation pre-registered, and the
2023–24 lockbox read **once**: championship-probability Brier **0.0884 vs a 0.09 baseline**, 80%
prediction intervals covering **80.1%** of outcomes for players who play.

**Jul 23 – 30 · Modelling the other nine drafters.** A crawler over Sleeper's public API grew a
corpus of real human drafts from **149 to 7,699 (1.2M picks)** — after finding that the "exhausted"
crawl had simply never been reseeded. At that scale a hardcoded format label turned out to have
mixed dynasty, superflex and IDP rooms into one PPR board (82% of drafts); every downstream result
was re-derived on the clean corpus, and two plausible "behavioural findings" disappeared. The
behavioural opponent model beats ADP on log-loss by **+0.174** over 70,614 real picks, and the
simulated mock-draft room is validated against 1,144 real drafts.

**Jul 30 – Aug 17 · The product and the scheme layer.** A Streamlit draft app (live board, draft
room, preference tags, cost report, post-draft grades), support for any league format (superflex,
custom scoring, keepers), and a scheme data layer built on nflverse's 22-man participation data:
personnel groupings, formations, coverage shells, man/zone and pressure for every play since 2016,
attributed to offensive *and* defensive play-callers.

**Oct · The Team Book.** A one-off hand-built report on the 2025 Bears, generalized into a pipeline
and a static site for every team and season, plus a store-free path that rebuilds the live season
from nflverse each week. Building it surfaced three metrics in the scheme layer that were encoding
artifacts rather than football — a pressure rate of exactly 1.0 for every team from 2023, and
formation shares zeroed by a vocabulary change in the source — which the book's guard now refuses
structurally.

## How the work is done

- **Point-in-time at the read.** Nothing dated after an as-of date can reach a feature built for it.
- **Pre-registered bars that can fail.** Every step ships with a done-bar written before the result
  is read, plus a control showing the bar is capable of failing. Nulls are reported as nulls: several
  research tracks ended that way and are written up as such.
- **One held-out test, spent once.** Development used 2014–2022; 2023–24 was read a single time
  against a committed pre-registration.
- **Determinism is tested, not assumed.** Monte Carlo results that wobbled between processes were
  traced to DuckDB's parallel floating-point aggregation, not to the random-number code every
  hypothesis pointed at; reads that feed a simulation are now single-threaded and bit-reproducible.
- **Missing is never zero.** A metric outside the seasons its source covers is NULL with a stated
  reason, end to end — in the store, in the JSON, and on the page.
- **Two kinds of agreement.** A re-implementation is checked for *code parity* exactly (same data,
  identical output) and for *data vintage* within a bound (the upstream restates history), so a code
  bug cannot hide inside a data revision.
- **A written record.** [`findings.md`](findings.md) logs what every step produced and taught,
  [`PLAN.md`](PLAN.md) the decisions and dead ends, [`docs/TECH-DEBT.md`](docs/TECH-DEBT.md) every
  known defect with its fix.

## Architecture

```
nflverse releases ─┐                                   ┌─► draft engine ─► Streamlit app (app/)
Sleeper API ───────┼─► ingest + gates ─► DuckDB store ─┤
FantasyPros / FFC ─┘   (data/)          (PIT tables)   └─► teambook/ ─► site/data/*.json ─► GitHub Pages
                                                             ▲
nflverse releases ── teambook/inseason.py (in-memory, no store) ── weekly Actions job
```

| Package | What it does |
|---|---|
| `data/` | Ingest from nflverse, Sleeper, FantasyPros and FFC; point-in-time tables; validation and encoding-break gates |
| `projections/`, `covariance/`, `valuation/` | Consensus value, per-player distributions, correlation, VBD and utility |
| `draft/`, `simulation/` | Draft simulator, behavioural opponent model, optimizer, season and playoff Monte Carlo |
| `inseason/` | Kalman re-projection, start/sit, waivers/FAAB, streaming, trade finder |
| `situation/` | The scheme layer: participation, coverage, play-caller regimes, scheme fingerprints |
| `teambook/` | Metric registry, book builder, store-free live path, output guard, site export |
| `backtest/` | Walk-forward harness, PAR metrics, block-bootstrap significance |

## Run it

```bash
uv sync --extra data                       # Python 3.12, pinned via uv
uv run python -m pytest -m "not needs_db"  # the suite that runs without the local store
uv run python -m http.server -d site       # browse the Team Book at localhost:8000
uv run python steps/teambook_export.py --live   # rebuild the live season from nflverse
```

The full pipeline (`steps/`) rebuilds the 765 MB DuckDB store from public sources; tests that need
it are marked `needs_db` and run locally. The draft app runs with
`uv sync --extra ui && uv run streamlit run app/main.py` once the store exists.

## Data and attribution

Play-by-play, participation, rosters, contracts, snap counts and schedules from
[nflverse](https://github.com/nflverse) (CC-BY 4.0). Play-design and charted blitz/box fields from
[FTN Data](https://ftnfantasy.com) via nflverse (CC-BY-SA 4.0). Draft data from Sleeper's public API;
ADP from Fantasy Football Calculator; consensus rankings from FantasyPros. Regular season only. Not
affiliated with the NFL or any team.

## What's next

- **League import** for the draft app — Sleeper first, then ESPN — so a user's real settings and
  league-mates load in one step.
- **The full 2026 book** when nflverse publishes the season's participation file (expected February):
  personnel, coverage and pressure for the live season, through the same store-backed export.
- **Matchup view** in the Team Book: an offense's tendencies laid against the opposing defense's,
  week by week.
- **Fix the scheme panel at the source** (register entries T56 and T57) and add a league-constant
  check to the standing data gates, so the next encoding change fails ingest rather than export.
- **Close the attrition gap**: unconditional interval coverage is 72% against 80% for players who
  play; a role and depth-chart survival model is the planned fix.
- **A hosted draft app**, which needs a slimmed, read-only extract of the store.

## Repository guide

| File | Role |
|---|---|
| [`docs/STRATEGY.md`](docs/STRATEGY.md) | Why: feasibility, the finance parallels, the factor taxonomy |
| [`docs/REFRAME-2026-07-04.md`](docs/REFRAME-2026-07-04.md) | The pivot to personalization, and the numbers behind it |
| [`PROJECT.md`](PROJECT.md) · [`ROADMAP.md`](ROADMAP.md) | Scope, phase plan and status |
| [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md) | Step-by-step execution manual with every done-bar |
| [`findings.md`](findings.md) · [`PLAN.md`](PLAN.md) | What each step found; decisions and dead ends |
| [`docs/TECH-DEBT.md`](docs/TECH-DEBT.md) | The defect register |
| [`glossary.md`](glossary.md) | Fantasy and quant terms as this repo uses them |
| [`CLAUDE.md`](CLAUDE.md) | Working rules for anyone changing the code |
