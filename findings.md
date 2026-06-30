# Findings — fantasy-quant

Running record of what each step produced and what it taught. Newest at the bottom. (Mirrors the
intern-repo's findings log.)

---

## Setup — environment scaffold (2026-06-29)

**Goal:** stand up the repo and toolchain before any modeling code.

**What was done:**
- Repo at `~/projects/fantasy-quant` (kept fully separate from the internship — see the relocation note below).
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



## Relocation & internship separation (2026-06-29)

**Goal:** guarantee this project is 100% separate from the Bitbucket-based internship environment.

**Audit (all clean):** independent git repo (no umbrella git over `~/dev`); **no remote** on this repo
(internship's `intern-repo` → bitbucket, untouched); no hard path deps on the internship's `dev/venv` or
`dev/data`; separate uv-managed Python 3.12 venv; no global git URL rewrites forcing bitbucket.

**Action taken:** moved the repo **out of the internship's `~/dev/repo/` tree** to `~/projects/fantasy-quant`
(uv re-synced + Jupyter kernel re-registered at the new path; `import fantasy_quant` verified). Remote will
be a **private GitHub** repo only — never Bitbucket.

