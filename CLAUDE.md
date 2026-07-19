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
- **Standing chore (Stage 0, from 2026-07-09 until the 2026 season starts):** the FFC 2026 ADP board is
  unrecoverable later, so keep the snapshot series fresh — if the latest 2026 snapshot in `adp_snapshots`
  is > 6 days old, run `uv run python steps/stage0_adp_snapshot.py` (idempotent, ~10 s). Any session
  working in this repo should check/refresh this. **After refreshing, back up the crown jewels off the WSL
  disk** (they're gitignored, single-copy): run `uv run python steps/backup_db.py` — it copies the 2026 ADP
  snapshots + 2025 backfill + a timestamped `.duckdb` to `/mnt/c/Users/rayha/fantasy-quant-backup/` and
  md5-verifies each. See `docs/TECH-DEBT.md` **T2** (done 2026-07-10).

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

> **Known problems & their exact fixes live in `docs/TECH-DEBT.md` (register T1–T9, opened 2026-07-10).**
> **T3 (coverage) + T4 (sim level bias) are ☑ done (2026-07-11).** Remaining hard gate before the lockbox
> eval: **T5** pre-registration (freeze the stack — incl. the T3/T4 params — and report metrics once).

> **★ Next-session pointer (2026-07-19, SESSION D COMPLETE — the engine is FINAL and the lockbox is spent).**
> Session D closed the pre-app pipeline: **(1) the optional MCTS research gate — BUILT & DROPPED** (user chose
> to build the benchmark; a determinized-UCT beats the greedy in-objective Δ CE +77 but not on realized OOS
> points Δ +32 CI∋0 at 8.5 s/pick → greedy stays the policy; CFR/self-play-RL stay out; `draft/mcts.py`,
> `steps/phase11_2_mcts.py`); **(2) T5 pre-registration** of the exact frozen stack + metrics + the ≈35–40
> DEV-decision count (`PLAN.md` §"⭐ T5 PRE-REGISTRATION"), committed **before** the eval; **(3) the LOCKBOX
> EVAL — spent EXACTLY ONCE** on 2023+2024 (`steps/lockbox_eval.py`, `analysis/lockbox_eval.json`,
> `findings.md` §"LOCKBOX EVALUATION"). **Result, as-is: the honest-value claims GENERALISE OOS** — title
> Brier **0.088 < 0.09** (championship calibration holds ≈ DEV), conditional coverage **80.1 %**, projection
> Spearman **0.54**, cheap personalization; **known level-optimism / unconditional-attrition limitation
> persists** (bias 0.62, uncond 72 %, marginal playoff Brier 0.240). **The modeling stack is FROZEN — nothing
> changes model-side on the basis of this result.** **★ WHAT'S NEXT: Session E = Phase 14.1 (Streamlit MVP
> hardening) — the app, built strictly last with every factor embedded; do not bundle anything onto it. Then
> F+ = the 14.2–14.4 go-live tail.** Two commits landed locally (`7bd6e10` freeze, then the lockbox-result
> commit) — **not pushed** (user's review-then-push habit). Opportunistic tech-debt left: **T10** (the S6
> `adaptive` archetype crashes `spine_4_validate`/`validate_archetypes` — worked around in the lockbox
> harness; fix before re-running the DEV cost-report). Run the Stage-0 FFC snapshot chore if >6 days stale
> (§2). **Resume: Phase 14.1.**
>
> _(Prior pointer — history.)_ **★ Next-session pointer (2026-07-13, SESSION C COMPLETE — not yet committed, left for user review).**
> **Session C = Phase 12 news/NLP + Phase 15 multi-format/auction — all done-bars PASS, ruff clean, 306
> tests (was 276; +19 `test_news`, +11 `test_phase15`).** Ran the overdue Stage-0 FFC snapshot chore first.
> **Phase 12 = a qualified KEEP:** the injury signal is real (exploitable lag +5.86 pts/start sig → the
> news-aware weekly forecast beats injury-blind 13.1 **+3.4→4.3 pts/pw on the designated subset, 6/6 DEV**),
> the depth-chart signal a DROP (no separation). LLM edge-only via a **gated `ClaudeClient`** (Haiku 4.5,
> behind `ANTHROPIC_API_KEY`); the deterministic **rules** extractor is the default and the core prices the
> signal — the guardrail literalized. `news/{sources,extract,event_study,validate}.py`; `steps/phase12_*`.
> **Phase 15:** 15.4 auction (`draft/auction.py` — budget-state bidder beats naive 6/6; **T9 discharged**,
> `faab_bid` consumes `endgame_cap`), 15.2 best-ball (`formats/bestball.py` — **variance-is-good**, ceiling
> beats mean 6/6; **weekly** CoV not season sd), 15.3 DFS GPP (`formats/dfs.py` — leverage beats chalk 6/6
> via duplication/prize-splitting, **MECHANICS only — no free DFS salary/ownership feed**). 15.1 dynasty
> deferred (user scope). **What's next: Session D = optional MCTS/RL research gate (explicit decision) → T5
> pre-registration (the only open pre-lockbox tech-debt) → the single LOCKBOX EVAL on 2023+2024 → then Phase
> 14 the app.** Analysis JSON: `analysis/phase12_*`, `analysis/phase15_*`. **Resume: commit Session C.**
>
> _(Prior pointers, kept as history.)_ **SESSION A ☑ COMPLETE** (S6 + 13.1 + 13.2,
> committed `87e6bae`). **SESSION B ☑ COMPLETE — 13.3 + 13.4 + 13.5 all DONE → Phase 13 / S7 COMPLETE.**
> **276 tests, ruff clean; 13.3 committed; 13.4 + 13.5 NOT yet committed — left for user review.** Lockbox
> (2023+24) untouched;
> DEV-only (2017–22 validation window). Session-A recap (S6 fade-melt archetype; 13.1 Kalman re-projection;
> 13.2 co-pilot start/sit + the variance-tilt "kept-not-default" finding):
> - **S6 adaptive archetypes** (`draft/config.py` `"adaptive"` + `_adaptive_tilt`; `steps/spine_5_adaptive.py`)
>   — a wrapper that **melts a static parent's *fade* by how far a candidate has slid off ADP** (`ADAPT_DECAY`,
>   `ADAPT_SLIDE_WEIGHT`; sliding value melts ~2× a reach; reaches untouched; no board context ⇒ = parent).
>   **Does no harm on an ADP board, banks team-value when the board breaks** (adaptive(zero_rb) +2.0,
>   adaptive(hero_rb) +15.6 in the realistic Phase-11 behavioral room).
> - **13.1 weekly re-projection** (`inseason/reproject.py`; `steps/phase13_1_reproject.py`) — a scalar
>   **Kalman** on each player's per-week level; **PIT**; a **reserved Phase-12 `news` slot** (no-op default,
>   so Phase-12 plugs in without a rebuild). **Beats static preseason OOS 6/6 seasons, +0.396 ppg/wk (CI
>   [+0.32,+0.48]).**
> - **13.2 start/sit** (`inseason/lineup.py`; `steps/phase13_2_lineup.py`) — **co-pilot done-bar PASS**:
>   mean-max on 13.1's re-projected means beats set-and-forget on realized points 6/6, **+2.08 pts/lineup-week**
>   (CI[+1.56,+2.54]). **FINDING:** the win-prob **variance tilt does NOT beat mean-max even for big underdogs**
>   (0/6; a single legal swap barely moves the ~35-pt team sd — cf. Phase-10.3 whole-team-only leverage), so
>   `optimal_lineup` default is now `objective="mean"`; the tilt is kept **opt-in** `objective="win"`, off by
>   default (the Phase-7 / props "kept, not the default" pattern).
> - **13.3 waivers/FAAB ☑** (`inseason/waivers.py`; `steps/phase13_3_waivers.py`) — pure `faab_bid` =
>   **marginal value** (rest-of-season over replacement, from 13.1) → `value_scale` willingness-to-pay,
>   **rationed** by the option value of budget `1/(1+κ·(weeks−1))`, **first-price shaded** vs a belief about
>   the field. **Beats naive %-of-budget 5/6 DEV** in a **mixed-field** sim (mean +30.0 value/szn, CI
>   [+21.7,+38.8]). **KEY FINDING:** the sim needs **diminishing returns** — score only a team's **top-4**
>   pickups + bid marginal-over-roster — or it rewards *volume* and naive aggression wins (0/6 → 5/6).
>   **DECISIONS (user, upfront):** *pragmatic now* (11.4/auction was deferred to 15.4, `draft/auction.py`
>   doesn't exist → rigor owed as **TECH-DEBT T9**); *mixed field* (sharp vs naive + alternating).
> - **13.4 streaming ☑** (`inseason/streaming.py`; `steps/phase13_4_streaming.py`) — pure, position-agnostic
>   `stream_pick`: a **contextual bandit** over the waiver pool = greedy exploit on `matchup_projection = own +
>   (opp_allow − league_mean)` (both empirical-Bayes shrunk toward the prior season, `PRIOR_GAMES=4`), with a
>   **switch-margin hysteresis** (`SWITCH_MARGIN=1.0`; UCB explore off by default). **Demonstrated on DST**:
>   matchup-streaming beats **static-hold 6/6 DEV, +1.46 pts/wk (CI[+0.88,+2.09])**, and beats a
>   **random-streaming** control 5/6 — so the *matchup signal*, not just the churn, pays (the 13.3 anti-churn
>   lesson: switch cost + random control). **Scope:** DST demo; `stream_pick` position-agnostic (QB/TE feed
>   13.1 means as `proj`) — documented extension, not built.
> - **13.5 trades ☑** (`inseason/trades.py`; `steps/phase13_5_trades.py`) — the **market-maker**. Three pure
>   kernels: `lineup_value` (a roster's value = its optimal starting-lineup sum only — reuses the 13.2 `_fill`;
>   the diminishing-returns lesson made positional), `evaluate_trade` (a swap's *change* in each side's
>   `lineup_value`; `mutual` iff both gain > `ACCEPT_MARGIN=5`), `find_trades` (searches every opponent's
>   surplus `_benched` for mutual **1-for-1 / 2-for-1** legal deals arbitraging complementary positional
>   surpluses, ranked by the **worse-off side's** gain `min(mine, theirs)`, with a sell-high/buy-low `market`
>   tilt). Done-bar via the **Phase-10 MC season sim**: proposed trades **raise both teams' playoff prob 6/6
>   DEV** (maker season-block CI **[+0.014,+0.021]**, partner **[+0.012,+0.021]**) vs a **random-trade** control
>   that lifts both ~never. **KEY CORRECTION:** ranking by the *maker's own* gain only cleared a marginal
>   partner floor (worse side died in MC noise) → rank by `min(maker, partner)` so the objective rewards
>   *mutual* benefit. **Scope:** value = preseason model ros mean (self-consistent → PIT-trivial); in-season
>   this `values` slot is 13.1's re-projected mean. Sim trades 1-for-1; 2-for-1 kernel-supported + unit-tested.
> **What's next (THE PIPELINE):** **Sessions A/B/C done → Phases 12, 13/S7, 15 (core) COMPLETE; T9 ☑.**
> Next = **Session D = optional MCTS/RL research gate (explicit decision) + T5 pre-registration + the single
> LOCKBOX EVAL on 2023+2024**, then **Session E = Phase 14.1** (Streamlit MVP) and **F+ = the go-live tail**.
> **T5** pre-registration (freeze the stack; T3/T4/T9 already ☑) is the **only open pre-lockbox item**, and
> must run strictly last among build steps. Corpus can be grown anytime via `reference/sleeper_seeds.txt` +
> `steps/phase0_10b_crawl.py`; `docs/SLEEPER.md`. **Resume here: commit Session C, then Session D.** (Full
> session-sizing guide in `ROADMAP.md`.)

## 4. Watch out for
- **Look-ahead via "current" snapshots.** End-of-season stats, final ADP, injury outcomes — never let them
  leak into a historical as-of step.
- **Survivorship** — panels of "players who stayed relevant" flatter results. Document it as a limitation.
- **Overfitting the tiny sample** (~3,750 player-seasons). Stay in regularized-linear / GBT / hierarchical-
  Bayes territory; **no deep nets**. Correct for multiple testing when mining ADP biases.
- **Personalization baking in bias.** Always show personalized boards next to the pure-projection baseline;
  treat large divergences as hypotheses to test, not preferences to lock in.
- **PIT-clean ≠ out-of-sample-clean (the lockbox rule, ⟳ 2026-07-04).** PIT stops temporal leakage, not
  overfitting from repeatedly selecting on the same ~10 seasons. **Lockbox = 2023 + 2024** (frozen; set
  2026-07-04): never touch it during development / feature+model selection; evaluate the final chosen
  stack there **exactly once**. All development runs on **`config.DEV_SEASONS` = 2014–2022**; only the
  final eval reads `config.LOCKBOX_SEASONS`. (**2025** is out of the *draft-backtest* lockbox because there
  is **no 2025 ADP board** — FFC empty; source via Sleeper later. Its realized weekly/seasonal *are*
  recoverable via the new nflverse `stats_player` release — **step 0.9** — so once ingested, 2025 serves as
  a **projection-calibration holdout** and upgrades to a full backtest season when ADP lands. `findings.md` 2026-07-04.)
- **No LLM in the core (⟳ 2026-07-04; timing amended 2026-07-09).** The deterministic core never depends
  on an LLM. Phase 12 (news/NLP) is now **in the pre-app pipeline** (ROADMAP ★ THE PIPELINE, stage 7 — no
  longer "post-MVP"), but the guardrail is unchanged: AI lives **on the edges** (fuzzy input → validated
  object, or numbers → narrative) — it never computes a number that must be correct.
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
| Season/playoff **simulation** + leverage | `src/fantasy_quant/simulation/` | exists |
| **In-season** co-pilot (re-project, lineup, waivers, streaming, trades) | `src/fantasy_quant/inseason/` | exists |
| PIT walk-forward **backtest** harness + metrics + significance | `src/fantasy_quant/backtest/` | exists |
| **ADP-bias mining** | `src/fantasy_quant/adp/` | exists |
| The **app** (FastAPI backend, Next.js frontend, widget) | `src/fantasy_quant/app/` (+ `app/frontend`) | planned |
| Multi-format (dynasty/best-ball/DFS) + auction | `src/fantasy_quant/formats/`, `draft/auction.py` | exists (best-ball/DFS/auction; dynasty roadmap) |
| Phased runnable scripts (one per step) | `steps/` | exists |
| Results / scorecards | `analysis/` | exists |

## 6. Do not
- Do **not** install into system Python or the intern-repo venv. Use this project's `uv`/`.venv` only.
- Do **not** evaluate a method on in-sample fit or a single season.
- Do **not** commit data artifacts (gitignored) or secrets (`.env`).
