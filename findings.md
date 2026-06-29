# Findings — fantasy-quant

Running record of what each step produced and what it taught. Newest at the bottom. (Mirrors the
intern-repo's findings log.)

---

## Setup — environment scaffold (2026-06-29)

**Goal:** stand up the repo and toolchain before any modeling code.

**What was done:**
- Repo at `~/dev/repo/fantasy-quant` (sibling to `intern-repo`).
- **uv** package manager + **pinned Python 3.12** (deliberately not the machine's system 3.14, for ML-wheel
  compatibility — XGBoost/LightGBM/PyMC).
- `pyproject.toml`: core scientific + scraping + viz + notebook stack; optional extras `data`
  (nfl_data_py) and `bayes` (pymc/arviz); `dev` group (pytest/ruff/mypy).
- **src layout** → the package installs editable, so `import fantasy_quant` needs no `sys.path` bootstrap
  (an improvement over the intern repo).
- Doc set mirroring intern-repo discipline: `README`, `CLAUDE`, `PROJECT`, `PLAN`, `ROADMAP`, `glossary`,
  `findings`; full strategy analysis ported to `docs/STRATEGY.md`.
- Local git initialized.

**Next:** Phase 0 — data pipeline + PIT walk-forward backtest harness.
