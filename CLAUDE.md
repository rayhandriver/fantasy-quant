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
  - ⚠ **Stop the Streamlit app first.** `db.connect()` is read-write and DuckDB is single-writer, so a
    running `app/main.py` holds the lock and the chore dies with `Conflicting lock is held`. Read-only
    connections still work, and `adp._pull_ffc` is a pure network call — so you can check *whether a
    pull would bank anything* (FFC's `meta.end_date` vs the newest `snapshot_date`) before stopping it.
  - ⚠ **A pull invalidates the live-board bar sheets.** Re-running them after the chore is expected to
    fail B0 until **T41** lands; see the 2026-08-01 session-4 pointer below for the re-baseline rule,
    and note `analysis/session_ui_*.json` are **untracked** — back them up before a re-run overwrites
    them, because `git` cannot.

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

> **★★★ Next-session pointer (2026-08-05 — ✅ MM-1a: THE BELIEF BOARD IS A SEAT. 16.18e built,
> policy deliberately NOT fitted. READ THIS FIRST.)**
>
> **State: 977 tests (was 954; +23 `test_manager_profile`), ruff clean. UNCOMMITTED**, on top of
> `2611e95`, now one tree with Session VH, DATA-1, DATA-2 and this. **No refit, no lockbox read,
> the frozen value stack / `value_board` / cost report untouched.**
>
> **Run it:** `uv run --extra reports python steps/mm1_profile.py --write` →
> `reference/manager_profiles/mm1_2026.json` + `analysis/mm1_profile.json`.
>
> **★★ THE SESSION IN ONE LINE: "mimic me" is two objects, and only one of them had any input.**
> The user's filled top-150 workbook is a **beliefs** board (16.18e) and it is far richer than the
> ~50 rows scoped. It contains **no policy data at all** — so `policy_source='corpus'` ships, and a
> validator *refuses* a profile that carries coefficients while claiming otherwise. Full write-up:
> `findings.md` §"SESSION MM-1a"; decisions in `PLAN.md` §2026-08-05; the spec's own scorecard in
> `docs/BUILD_PLAN.md` §"✅ MM-1a RUN 2026-08-05".
>
> **★ Eight decisions the user took up front — do not re-litigate:** seat is **opponent AND own
> autodraft** · policy waits for an **elicitation session, as a Streamlit page** · **blank note =
> never draft** · scale **calibrated LOO against his 45 real mock picks** · **hard Packers rule,
> Tucker Kraft the one named exception** · **one `balanced` gives up its seat** in `REALISTIC_ROOM`
> · the elicitation page is **also owed as a product feature for every user** (→ **14.P**) · the
> measured positional lean is **NOT** generalized structurally.
>
> **★ Do not re-derive these — they are measured:**
> - **His beliefs are ORTHOGONAL to our value board** — `corr = 0.135`, **Spearman +0.008** over 149
>   rated players. New information, and by the same token *no reason to expect better answers*. The
>   seat buys **fidelity**; every honesty surface must say so.
> - **He is RB-averse net of depth** — QB **+0.64** (t 2.80) / TE **+0.59** / WR **+0.45** against an
>   RB base, with `log(depth)` only +0.13 (t 1.86). The "he just likes deep players" read is wrong.
> - **The scale is UNRESOLVED and the direction is RESOLVED.** `mean_rank` prefers 10, `median_rank`
>   5–6, `top1` 3–4 — three statistics, three winners on n=40 — so `sweep_resolved: false` and the
>   shipped scale is the **smallest within 1 paired-bootstrap se of the argmin** (3.0). But the
>   paired bootstrap vs the consensus null is **−0.60 ranks, CI [−1.03, −0.20]**, and
>   leave-one-**draft**-out gives **7.79 vs 8.78** / top-1 **0.229 vs 0.200**.
> - **His 38 board-matched real picks average Value Score +0.92 vs a board mean of +0.25** — computed
>   before any fit. Egbuka R5 ×2, Kraft R7 ×2, Jadarian Price ×3, Corum R9, LA Rams DEF R14 ×2.
> - **"Blank = never draft" MUST be scoped to rated rows.** Applied to the whole draftable universe
>   it forbids Cameron Dicker, whom he took in **all three** of his own mocks. `unrated: "neutral"` —
>   *a player who was never listed was never declined.*
> - **Three stated-vs-revealed conflicts are on file (B5), reported not patched:** Jayden Reed R12
>   (blank note + Undervalued + a Packer, all three rules at once), and Jeanty R3 / Herbert R8 taken
>   against a stated fade.
>
> **⚠ Do not "fix":**
> - **The personal board is applied to the candidate BAND but not to the reach budget.** 16.9 is why
>   the first half is necessary (`top_k` is a hard rank filter before utility — a stated opinion that
>   cannot reach the set it is scored over is a no-op with a note attached) and `CORPUS_REACH_P95` is
>   why the second is: a private opinion must not be a way around a measured population fact.
> - **A profile and a T24 private board are refused together** — both rewrite the seat's ADP, and
>   T24's κ was measured *harmful* anyway. The seam is reusable; the finding is not transferable.
> - **Avoids are a FILTER, not a weight**, and can never empty a pool.
> - **`assert_room_profiles`** exists because a `fitted_manager` with nothing loaded is a `balanced`
>   wearing someone's name — *an inert thing still passes*, for the fifth time in this repo.
> - **The RB fade is inside the per-player deltas**; adding a positional dummy double-counts it.
>
> **★ A synthetic fixture caught a defect the live board could not.** `name_key` stripped every
> non-letter, silently colliding any two names differing only by a digit. No real board shows it; a
> fixture of `Player 1 … Player 40` did, on its first run.
>
> **★★★ B7 ☑ — and getting there found the session's real defect, which every bar was blind to.**
> `REALISTIC_ROOM` moved, so both arms were run (`analysis/mock_room_bars_mm1_{control,fitted}.json`,
> 40 seeds × 8 seasons, `--shuffle-room`). Then a question no bar asks — *what season is this profile
> about?* — turned up a **point-in-time violation**: the profile describes **2026**, every harness
> sweeps **2017–2024**, and the workbook was filled in **August 2026 by someone who watched those
> seasons happen.** → **T54 ☑**.
> - **The leak is GRADED, which is what hid it.** A profile keyed on player identity fires on
>   whoever is still on the board: **6** rows in 2017, 21 in 2020, **55 in 2024** (a lockbox season),
>   78 in 2026. The seat is nearly `balanced` early and increasingly itself toward the present, so it
>   reads as *a seat with a mild opinion*, not as a defect.
> - **★★ Its measured effect is smaller than any bar in the harness can resolve** — profile distance
>   **0.0894 → 0.0887**, elite past-10 **25.24 % → 25.16 %**, dispersion **−11.39 % → −11.24 %**,
>   landing **15.31 % → 15.16 %**, and **all five T15 gates PASS on both arms.** *A session that read
>   only its own pre-registered bars would have shipped it and reported "no movement".* **The size of
>   a defect is not the argument for fixing it.**
> - **The fix is structural and dissolves the ticket.** `ManagerProfile.covers(season)` +
>   `make_room(..., season=)` degrade a `requires_profile` seat to `balanced` on an uncovered season.
>   ⚠ **Degrade, do not raise** — a historical measurement legitimately wants the room *minus* the
>   seat, and `balanced` is exactly the chair 16.18 took, so an uncovered season reproduces the
>   pre-16.18 room **bit-for-bit**. `steps/mock_room_bars.py` now builds its room **per season**.
> - **Verified paired**, not asserted, by the done-bar `steps/mm1_b7_room_gate.py` →
>   `analysis/mm1_b7_room_gate.json` (2017+2018 × 6 seeds, `--shuffle-room`): the gated default room
>   and an explicitly pre-16.18 room agree on **every result leaf**. B7 holds by *construction*, and
>   the control **can** fail — if the gate stopped firing the two arms would separate.
> - ⚠ **Any future harness that sweeps seasons must pass `season=`.** Without it the gate is inert
>   and the seat silently re-enters historical measurements.
>
> **★ NEXT: user reviews + commits, then Session MM-1b** = the Streamlit elicitation page + the
> 16.18c fit. ⚠ **The 45 mock picks are now partly spent** (one scalar, under LOO), so B4's primary
> arm should become the **withheld comparisons**; decide before the fit is read. Then **14.P**, the
> personality builder as a product feature. Register: **T54 ☑** (opened and closed this session). Stage-0 FFC chore current (`ffc-20260801`), next due
> after **08-07**.
>
> _(The DATA-2 run pointer, still the authority on the scheme panel, follows.)_
>
> **★★★ Next-session pointer (2026-08-03 session 3 — ✅ SESSION DATA-2 (Phase 0.13) RUN AND COMPLETE.
> 0.13.0–0.13.9, all 10 bars PASS. READ THIS FIRST.)**
>
> **State: 954 tests (was 843), ruff clean, B0 PASS, backup checksum-verified. UNCOMMITTED**, on top
> of `2611e95`, now one tree with Session VH, DATA-1, the DATA-2 scoping docs and the whole DATA-2
> run. **No refit, no lockbox read, the frozen value stack untouched, and 0.13.8 is asserted not to
> be wired into it.** Store: **45 → 63 registered tables** (16 new + 2 views).
>
> **Four decisions the user took up front:** straight through 0.13.4→0.13.9 · 0.13.1's 121
> historical rows **accepted at recorded confidence** (the 32 2026 rows were already signed off) ·
> 0.13.4 built in full with FTN asserted `backtestable:false` · leave uncommitted. Also: B0 =
> byte-identity + the suite once at the end · 0.13.5 all four tables **including cap $** · 0.13.7
> **both grains** materialized · 0.13.8 defense **+ a widened offensive vector**.
>
> **★★ THE SESSION IN ONE LINE: DATA-1 banked the plays and left them unattributable; DATA-2
> attributed them — and the three worst hazards were in the INSTRUMENTS, not the data.**
>
> **★ Do not re-derive these — they are measured, and three are corrections to the spec:**
> - **Slot/wide/inline alignment DOES NOT EXIST FREE.** The spec asked for it "from
>   `offense_positions`"; that column is the **listed roster position** — it says a man is a WR,
>   never that he lined up in the slot. Registered as a floor beside PFF safety-alignment depth.
>   Free substitutes: NGS `avg_cushion`/`avg_separation` + personnel context. **Do not chase.**
> - **`contracts.team` is an OTC nickname ("Ravens") or a career-path string ("ARI/ATL/NYJ"), never
>   a team code** — 90 distinct values in a 32-team league. Hence **the roster names the team, the
>   contract names the money**: membership from `weekly_rosters`, money joined to the **player**
>   (88–97 % of rostered players resolve to a contract in force).
> - **The store speaks FOUR franchise vocabularies** — pbp (`LA`/`LV`), nflverse alternates
>   (`ARZ`/`BLT`/`CLV`/`HST`/`SL`), **PFR** (`GNB`/`KAN`/`LVR`/`NOR`/`NWE`/`SDG`/`SFO`/`TAM`, in
>   `draft_picks`), **OTC nicknames** (`contracts`). `data/teams.py` is the pbp-side canon.
> - **⚠ There are TWO legitimate canons and they disagree on the Rams.** `adp/panel._TEAM_ALIAS`
>   says **`LAR`** (fantasy boards); `pbp` says **`LA`**. Mixing them drops a franchise silently —
>   32 teams in, 31 out, no error. `teams.assert_canons_disagree_only_on_la` pins it.
> - **The route tree is 19 values, not 14**, and is attributed to the **targeted receiver only**
>   (the vendor charts one route per play).
> - **`cap_pct_*` is NOT cap spend** (accounted APY sums to **1.2324** of the cap). Read
>   **`cap_share_*`**, which is a valid distribution. → **T53**.
>
> **★★ T52 (🟠, new) — the break detector is blind to two of the three encoding seams this session
> met, and "we have a break detector" is not "we would notice a break."** 0.13.0 keys on
> **conservation** (mass leaving NULL for **one** value). Both misses are real:
> (1) `participation.offense_personnel` fill climbs **0.7586 → 1.0000** at the same 2023 seam as
> T50 — but 1,468 distinct strings puts it over `MAX_CARDINALITY` (64), **and** the arriving mass
> spreads over hundreds of new special-teams strings rather than one sentinel, so the conservation
> test could not fire even if probed; (2) `weekly_rosters.position` **swaps vocabulary at 2016**
> (fine-grained CB/FS/DE/ILB/C/G/T → grouped DB/DL/LB/OL) — under the ceiling, but a vocabulary
> swap among *observed* values has nothing to conserve. Unmapped it left **64 team-seasons** whose
> position shares did not sum to 1. Both are handled correctly now; **the debt is the gate.**
> The fix shape is **conditioning on a stable population** — 0.13.4's `scrimmage_fill_by_season` is
> the worked example (naive break 0.2414 → conditioned break **0.0001**).
>
> **★★ "A reason that is always available is not a reason."** 0.13.8's first run dropped **six LAR
> defensive regime-seasons** (and nine offensive) into the LAR/LA seam while **passing** its guard,
> because the drop carried the reason *"no panel row for this team-season"* — true of every
> possible drop. The guard now checks the drop is **below the panel floor**, something that can be
> false. Recovered: defense 24 → **26** play-callers, 110 → **116** regime-seasons.
> ⚠ `fingerprint.assert_regime_coverage`'s own docstring already recorded this exact failure
> (McVay's Rams tenure). **The repo had met it before.**
>
> **★ Four of my own bars measured something other than what they claimed**, each caught by making
> the bar able to fail: a rate whose numerator was not a subset of its denominator (B4a read
> **1.016**); an expected value from football's rules rather than the file's (B4b used `11 × plays`;
> the vendor lists **12** on 2,739 plays and **10** on 2,171); a 53-man check against a
> season-cumulative roster (B7a, wrong twice); a dome "climate" that was the mean of **two rows**.
>
> **★ The 0.13.7 distinction worth keeping: does a column measure FOOTBALL or our COVERAGE of it?**
> Football columns (`man_share`, `share_cover_3`) must be **NULL** below their floor — a team never
> charted did not play zero man. Coverage columns (`charted_share`, every `*_denom`) are honestly
> **0**, and are the only thing explaining the nulls beside them. **A NULL z is never filled with 0**
> (0.0 means *exactly league average*).
>
> **★ Results:** B4a **1.000000** both sides · B7b draft-capital identity **1.0000 exactly** (0.8105
> before the PFR codes were mapped) · 4th-down go-rate naive **0.170** vs conditioned **0.296** ·
> coach attribution **0 mismatches** vs `coaches.csv` · panel **190 registered columns**, z mean
> 0.0000 sd 1.0000 · defensive fingerprints **face-valid** (Bowles **+1.14** blitz, Spagnuolo
> **+0.59** man, Quinn **+0.77** man; `man_share` shrinks hardest because its floor is 2018) ·
> **B5: all six deep-dive questions answered from one query each** (Barkley 439 carries / 59.1 % of
> PHI's 2024 backfield; Chase 114 targets in 11 personnel / 28 %).
>
> **★ Register: T48 ☑ · T49 ☑ · T50 ☑; T52 · T53 opened.** T51 still open on the *data* question
> (re-scrape PFR 2024–25 TDs, or mark the column dead from 2024).
>
> **★ NEXT: user reviews + commits.** **The team-by-team deep dives are unblocked** — they read
> `team_scheme_season`/`team_scheme_week` (z-scored within season, every column carrying a
> per-column floor and a PIT class) and `team_scheme_columns` says what each column's nulls mean.
> Independent and unblocked, the user's call on order: **M-1** (T45 NGS + T47 `pfr_*`) · **VH's two
> open decisions** · **Sessions MM-1 · MM-2** · the **M-0…M-6** mining program (still unscoped).
> Open register: **T52** · **T53** (new), T51, T47, T45, T43, T41, T40, T39, T36, T26.
> Stage-0 FFC chore current (`ffc-20260801`), next due after **08-07**.
>
> _(The DATA-2 scoping pointer, still the authority on what was planned and why, follows.)_
>
> **★★★ Next-session pointer (2026-08-03 session 2 — the scheme inventory → SESSION DATA-2 (Phase 0.13)
> SCOPED. Docs-only, no code, nothing ran. READ THIS FIRST.)**
>
> **State: 800 tests (unchanged), ruff clean. Still UNCOMMITTED**, on top of `2611e95`, now one tree with
> Session DATA-1 and this. **No `src/` change, no refit, no lockbox read, the frozen value stack
> untouched.** Edited: `docs/BUILD_PLAN.md` §"Session DATA-2" (the plan of record), `docs/TECH-DEBT.md`
> (**T48** · **T49** · **T50** + detail sections for T48/T50), `ROADMAP.md` (0.13 line + the ★ ← NOW
> pointer; the stale "0.12 is the next session" header was also corrected to ☑), `PROJECT.md` §5 Phase 0,
> `PLAN.md` §2026-08-03 (session 2), `glossary.md`.
>
> **What happened.** The user asked first for **every scheme-related data point in the store, per
> position** — then, on reading it, for a session that fills **all** the gaps: *"especially defensively …
> as much data as possible about each and every defensive scheme, defensive playcaller, team construction,
> safety coverage … deep dive into every single team's entire data construction — what offensive/defensive
> schemes they play the most, which sets they use, target shares, backfield splits, blitz percentages,
> literally everything."* That is **DATA-2 = Phase 0.13**, and the team-by-team deep dives come after it.
>
> **★★ THE FRAME: DATA-1 banked the plays and left them UNATTRIBUTABLE.** Every question in the ask that
> starts with the word *defensive* is currently team-anonymous and person-anonymous.
>
> **Three structural gaps, each verified in the store:**
> 1. **T48 🟠 — no defensive play-caller regime table.** `reference/coaches.csv` is offense-only by
>    construction (204 rows, 32 teams, 2014–2026, **48 play-callers, zero defensive attribution**), so
>    `situation/fingerprint.py`'s whole apparatus — within-season z-scoring, EB shrinkage by regime length,
>    PARTIAL-season week-pinning — **has no defensive counterpart to run on.** ⚠ **No free source**; same
>    artefact class as `coaches.csv`, which says so in its own header and took three correction rounds
>    before sign-off.
> 2. **The defensive half of participation was deliberately never materialized.**
>    `build_participation_player_week` filters `where v.side = 'offense'` and its docstring says why.
>    **Right for DATA-1, and exactly what blocks DST now** — the `participation_player_play` view already
>    carries the defensive side and nothing reads it.
> 3. **Team construction is four zero-reader tables** — `contracts` (51,793) · `weekly_rosters` (533,275) ·
>    `depth_charts_all` (955,989) · `draft_picks` (3,077). T45/T47's pattern for a third and fourth time.
>
> **★★ THE FINDING — the vendor stopped emitting nulls, and the gate only knows how to see nulls (T50, 🔴).**
> Read from the parquets, not inferred:
>
> | season | `was_pressure` | `number_of_pass_rushers` |
> |---|---|---|
> | **2022** | 31,207 **null** · 13,425 False · 5,518 True | 72 zeros |
> | **2024** | **14 null** · 38,838 False · 7,067 True | **23,754 zeros** |
>
> Non-pass plays used to be `NULL`; from 2023 they are `False`/`0`. Unconditional fill climbs **0.38 →
> 1.00** while meaning inverts. **Three independent reasons `validate.fill_rate_gate` cannot see it, each
> sufficient alone:** `store_fill_rates` counts the **nonnull** share, so a sentinel counts as filled · the
> gate fails only on **drops** (`was - rate > tol`) and this is a **rise** · it is **whole-table, not
> per-season**, so a mid-history break averages away. *The instrument written to catch `ngs_air_yards`
> silently going to zero is blind to the exact opposite failure — and the opposite failure is the one
> actually in the data the mining program exists to mine.* **A blitz rate computed naively across 2022→2023
> reads as a league-wide scheme revolution that is entirely an encoding change.**
> ⚠ **Not a defect in `participation.fill_rates()`** — that does state conditional rates correctly and
> DATA-1's B5 was met. The defect is the **standing gate**, which runs on every future ingest.
>
> **★ Second correction: floors are per COLUMN, not per table (T49).** The register lists participation at
> **2016** — right for personnel/box/formation, **wrong for coverage**: `defense_man_zone_type` and
> `defense_coverage_type` are **0.000 in 2016 and 2017**, ~0.38 for 2018–22, ~0.49 for 2023–25. True floor
> **2018** ⇒ **five** DEV seasons of man/zone, not seven.
>
> **★ Do not re-derive these, they are measured:**
> - **The three tiers of "safety coverage", and they must not be blurred:** charted shell
>   (`defense_coverage_type`, ~49 %, **2018+**) · derived safety count from `defense_positions` (a
>   single-high vs two-high **personnel proxy**, ~76 % pre-2023 / ~100 % after) · **pre-snap alignment
>   depth and rotation, which do not exist free** and go in the register as a floor. DATA-1's do-not-chase
>   rule applies verbatim.
> - **`base_front`/`coverage_identity` stay OUT of the curated CSV** — derivable from 0.13.2, and the 16.5
>   rule says a question a feed can answer gets no human maintainer. **The CSV carries only what no feed
>   knows: who called it.**
> - **No ST coordinator table.** 4th-down and 2-point aggression are **head-coach** decisions and `pbp`
>   already carries the head coach exactly and PIT.
> - **`contracts` has no unique row key** — 3,339 byte-identical OTC duplicates. Aggregate deliberately.
> - **0.13.0 goes FIRST.** Every rate routes its denominator through the break map; building it later means
>   rebuilding whatever came before it.
> - **Classify the break, do not smooth it.** A normalization that makes the discontinuity vanish without
>   recording it is the same defect as the gate that cannot see it.
> - **DATA-2 builds NO feature.** 0.13.8 extends a *descriptive* module nothing downstream reads; M-1 still
>   owes **two** wirings (T45 NGS + T47 `pfr_*`). **Derive all seasons, analyse DEV only.**
>
> **★ A correction I made to my own reporting, mid-session, and it is the same defect as T50.** My first
> fill-rate pass reported `route` and `defense_man_zone_type` at 1.00 for 2023+. Wrong — those columns are
> pyarrow-string typed, so `dtype == object` was False and **empty strings were never counted as missing**.
> Corrected: `route` ~0.37–0.42 throughout, `defense_man_zone_type` ~0.49 in 2023+. *A missingness check
> that only knows about NULL* — committed by the person opening T50, an hour before opening it.
>
> **★ TEN pre-registered bars, and the headline is B2:** the **naive** and **gated** blitz rates must
> differ by a **stated amount** — *prove the trap is real first, then prove the gate closes it; a fix whose
> effect is unmeasured is a claim.* Paired with **B1**: the break map must find the 2023 discontinuity
> **without being pointed at it** and flag a **planted synthetic sentinel** (T31's rule verbatim).
>
> **★ THREE DECISIONS MUST BE ASKED before a straight run** (`docs/BUILD_PLAN.md` §"Session DATA-2"):
> (1) defensive regime scope — **recommend mirroring `coaches.csv`** (2026 + prior regimes of current DCs);
> (2) ST coordinator table — **recommend skip**; (3) `base_front`/`coverage_identity` — **recommend
> derived, not curated**.
>
> **★ Sizing and the real long pole:** ~700–1,000L / 9–13 files / ~20–25 tests for the derived half, **plus
> a research-and-review block for 0.13.1** that needs a user sign-off gate and cannot be made faster by
> writing better code.
>
> **⚠ Stop the Streamlit app before running anything** — `db.connect()` is read-write, DuckDB is
> single-writer.
>
> **★ NEXT: user reviews + commits, then Session DATA-2.** After it, the team-by-team deep dives have a
> complete, attributable, provenance-flagged panel to read. Independent and unblocked, the user's call on
> order: **M-1** (T45 + T47) · **VH's two open decisions** · **Sessions MM-1 · MM-2**. Open register:
> **T48** · **T49** · **T50** (new), T47, T45, T43, T41, T40, T39, T36, T26. Stage-0 FFC chore current
> (`ffc-20260801`), next due after **08-07**.
>
> _(The DATA-1 run pointer, still the authority on what was built and the four things its spec got wrong,
> follows.)_
>
> **★★★ Next-session pointer (2026-08-03 — ✅ SESSION DATA-1 (Phase 0.12) RUN AND COMPLETE. 9/9 bars
> PASS.)**
>
> **State: 800 tests (was 765), ruff clean. Store 27 → 45 tables. Still UNCOMMITTED**, on top of
> `54114bc`, now one tree with Session VH, the DATA-1 scoping docs and this. **No refit, no lockbox
> read, no model number moved, the frozen value stack untouched.**
>
> **New code:** `src/fantasy_quant/data/sources/{nflverse_release,participation,small}.py`,
> `data/{registry,reconcile}.py`, `steps/phase0_12_*.py` (8 done-bars), `tests/test_data1.py` (35).
> **Modified:** `data/validate.py` (fingerprints + B0 allowances + coverage/fill-rate/registry gates),
> `data/cache.py` (`archive_bytes`). **Generated:** `reference/DATA-SOURCES.md` — *the standing answer
> to "do we have X?"; read it before investigating whether we have a source.*
>
> **★★ THE SESSION IN ONE LINE: the binding constraint was never the modelling, it was that nothing
> recorded what we had** — and every defect found is that one defect wearing a different hat.
>
> **Register: T46 ☑** (release loader ships beside `nflverse.py`, which is untouched) · **T44 ☑**
> (`schedules` landed; byes derive from the fixture list, 32 teams × 1 bye × 4 seasons — the 14.F
> repoint off `ecr_snapshots` is a one-line app change still owed) · **T45 ◐** (register half done;
> **M-1 still owes the wiring**) · **T47 opened 🟠** — `pfr_pass`/`pfr_rec`/`pfr_rush` are ingested
> and read by **nothing**. Three more T45s, found by the instrument built for the first one.
>
> **★ Four findings a later reader must not re-derive** (full text: `findings.md` §"SESSION DATA-1"):
> - **`depth_charts` was never missing 2025.** It held **two grains** — 554,215 of its 955,989 rows
>   ARE the ts series, appended with a **NULL `season`** — so `group by season` dropped 58 % of it and
>   reported the data as ending in 2024, *which is how the scoping mis-read it.* Read
>   **`depth_charts_all`** (season-complete 2014–2025, grain is a column).
> - **A join rate needs its denominator too.** B3 failed at 0.983 on its first run; the residual is
>   entirely the vendor's **empty placeholder rows** (~780/season, none after 2022). On contentful
>   rows it is **1.00000 every season**. The empty rows are KEPT — filter with `n_offense > 0`.
> - **The consumers column was blind to its own purpose** in v1 (counted mentions; the ingesting step
>   mentions a table most). Now producers/readers/tests, and a file can be both.
> - **The explode is 9.9M rows, not ~100M** — the scope multiplied by seasons twice. Still a **view**,
>   for the same reason (1.5× the rest of the store).
>
> **⚠ Standing rules that did not change:** ingest all seasons, **analyse DEV only** (2023/24 is on
> disk; loading it does not spend the lockbox, a feature on it does) · **DATA-1 built NO feature** ·
> `data/sources/nflverse.py` is still the provenance of sixteen tables, do not bypass it · stop
> Streamlit before any step (DuckDB is single-writer).
>
> **★ NEXT: user reviews + commits.** Then, all independent and the user's call: **M-1** (now owes
> **two** wirings — NGS T45 *and* `pfr_*` T47 — same session, same bars, since both change the
> exposure matrix) · **VH's two open decisions** · **Sessions MM-1 · MM-2**. The M-0…M-6 mining
> program is unblocked but **still unscoped**. Stage-0 FFC chore current (`ffc-20260801`), next due
> after **08-07**.
>
> _(The DATA-1 scoping pointer, still the authority on what was planned and why, follows.)_
>
> **★★★ Next-session pointer (2026-08-02 — the micro-detail deep dive → SESSION DATA-1 (Phase 0.12) SCOPED. Docs-only, no code, nothing ran.)**
>
> **State: 765 tests (unchanged), ruff clean. Still UNCOMMITTED**, on top of `c712f86`, now one tree with
> Session VH and this. **No `src/` change, no refit, no lockbox read, the frozen value stack untouched.**
> Edited: `docs/BUILD_PLAN.md` §"Session DATA-1" (the plan of record), `docs/TECH-DEBT.md` (**T44** ·
> **T45** · **T46**), `ROADMAP.md` (Phase 0.12 line + ★ SESSION PLAN ← NOW), `PROJECT.md` §5 Phase 0,
> `PLAN.md` §2026-08-02, `findings.md` §"THE DATA AUDIT", `glossary.md`.
>
> **What happened.** The user asked for a scope of sessions dedicated to finding "the proverbial chinks in
> the armor" — the position-group micro-detail he sees on TikTok/Reels: **opponent box stacking for RBs,
> coverage schemes for WRs, usage of 1–3 TE sets, play-calling tempo.** Then, after the data audit, he
> asked for **one session dedicated solely to obtaining and perfecting all of it** — *"not just for the
> categories I mentioned but also for anything I may think of down the line."* That is **DATA-1 = Phase
> 0.12**. The mining half (Sessions M-0 … M-6) is sketched in `PLAN.md` and is **NOT scoped**.
>
> **★★ THE FINDING — the binding constraint is our ingest architecture, not our modelling.**
> `nfl_data_py` is a **wrapper** over `nflverse-data` GitHub release assets, and we have been reading its
> surface as the data's surface. Phase 0.9 met a symptom of this and filed it as a one-off; it is the
> general case. Verified live against the release API on 2026-08-02:
>
> > **`pbp_participation` — 2016–2025, one row per play, no wrapper function, never ingested.**
> > `defenders_in_box` · `offense_personnel`/`defense_personnel` · `offense_formation` ·
> > `defense_man_zone_type`/`defense_coverage_type` · `route` · `was_pressure` · `time_to_throw` ·
> > `number_of_pass_rushers` · **and the gsis IDs of all 22 men on the field for every play.**
>
> That is his first three questions, as columns, at play grain, for ten seasons, free — plus the on-field
> record that lets each be computed **per player conditional on personnel grouping**, which no public site
> publishes. → **T46.**
>
> **Two more, both found by asking "who reads this?":** **`ngs` is ingested and effectively unread**
> (26,723 rows 2016–2025; one consumer at `data/panel.py:93`, receiving only; **no `features/` module
> reads it**) → **T45**. **There is no `schedules` table** — K2's bye readout takes byes from
> `ecr_snapshots`, a rankings feed → **T44**.
>
> **⚠ A correction that is on the record.** Earlier the same day the user was told participation data was
> cut off after 2023 and that man/zone coverage was not free. **Both wrong** — the release is current
> through 2025 and the coverage fields are in it. Stated from recall about a vendor policy; the check was
> one API call.
>
> **★ Do not re-derive these, they are measured:**
> - **Upstream floors are permanent:** participation **2016** · NGS **2016** · PFR **2018** · FTN
>   **2022**. With `DEV_SEASONS` = 2014–22, **FTN contributes exactly ONE development season** → it ships
>   `backtestable: false` as an *assertion*. The user's "pre-2022 is missing" read is **right for FTN and
>   wrong for everything else**, and that distinction is the register's most useful column. **A session
>   that ends with "still missing pre-2022 FTN" has misunderstood the register.**
> - **Fill rates need their denominator.** `route`/`defense_man_zone_type`/`was_pressure` at ~0.38 of all
>   rows (2016–22) is the **pass-play share**, not 62 % missing. Personnel/box ~0.76 (2016–22) → **1.00**
>   (2023–25). Real holes: `defense_coverage_type` ~0.50 throughout, and **`ngs_air_yards` = 0.00 from
>   2023** — a field that silently stopped being populated, which is what the 0.12.8 fill-rate gate is for.
> - **The explode is ~100M rows** (`offense_players` × 22 × 10 seasons), larger than the rest of the store
>   combined. **Land play grain, materialize `participation_player_week`, keep the exploded form a view.**
> - **DATA-1 builds NO feature.** Wiring NGS into `features/` changes a matrix the rookie ridge, the
>   QuantReg fits and the Phase-6 softness regression all read → that is **M-1**, with its own bars.
> - **Ingest all seasons, analyse DEV only.** Loading 2023/24 does **not** spend the lockbox; building a
>   feature on it does. The wall stays at the modelling step.
> - **Do not fold in the consensus-projection re-pull** (moves every value number in the app; own step).
> - **Do not delete or bypass `data/sources/nflverse.py`** — it is the provenance of sixteen tables.
>
> **★ THREE DECISIONS MUST BE ASKED before a straight run** (`docs/BUILD_PLAN.md` §"Session DATA-1"):
> (1) participation grain — **recommend play**; (2) storage shape — **recommend one DuckDB file**;
> (3) small-source scope — **recommend all of 0.12.6**.
>
> **★ Nine pre-registered bars, and the headline is B4:** the four questions that motivated the session
> each return an answer from one query, on real data. *A source is not ingested until the question that
> motivated it returns an answer.* B0 is the usual rule inverted for an additive session — **every
> pre-existing table byte-identical, all existing gates PASS, one committed sheet re-runs**; ingest is
> additive by construction, so if a number moved it was not an ingest.
>
> **⚠ Stop the Streamlit app before running anything** — `db.connect()` is read-write, DuckDB is
> single-writer, and a running `app/main.py` holds the lock (hit live while scoping: PID 925712).
>
> **★ NEXT: user reviews + commits, then Session DATA-1.** VH's two open decisions and Sessions MM-1 ·
> MM-2 are **independent of this and stay unblocked** — ordering is the user's call. Open register:
> **T44** · **T45** · **T46** (new), T43, T41, T40, T39, T36, T26. Stage-0 FFC chore current
> (`ffc-20260801`), next due after **08-07**.
>
> _(Session VH's pointer, still the authority on the value hawk and the two open decisions, follows.)_
>
> **★★★ Next-session pointer (2026-08-01 session 6 — ✅ SESSION VH RUN AND COMPLETE. READ THIS FIRST.)**
>
> **State: 765 tests (was 749), ruff clean. UNCOMMITTED** on top of `c712f86` (UI-1+2, which the user
> committed mid-session — verified to contain **none** of VH's work). **No refit, no lockbox read, the
> frozen value stack untouched.** New: `steps/vh_{0,1,2,3}_*.py`, `tests/test_vh.py`,
> `analysis/vh_*.json`, `analysis/mock_room_bars_vh_*.json`. Modified: `adp/boards.py`
> (`asof`), `draft/mock.py`, `draft/personalities.py` (**T33**), `steps/mock_room_bars.py`
> (`--vh-window`), `steps/phase16_17_seat_map.py` (the control moved with the fix).
>
> **★★ THE SESSION IN ONE LINE: the leading hypothesis was demoted by its own first substep, and the
> arm that passed the bar is not the arm the ticket proposed.** Full write-up in `findings.md`
> §"SESSION VH"; per-substep notes in `PLAN.md` §2026-08-01; the spec's own scorecard is in
> `docs/BUILD_PLAN.md` §"✅ RUN 2026-08-01 — what the spec got right, and what it got wrong".
>
> **What was settled (do not re-derive):**
> - **T33 ☑.** The divisor reads `state.n_teams`. **k=0 bit-identical (0/1200 picks)** — no committed
>   batch measurement moves — while **k=1, the room a human actually drafts against, moved 20.7 %**.
>   Not monotone in k (10.2 % at k=2): one changed pick cascades, so it is chaotic amplification, not
>   a dose-response. **749 tests passed over this bug** because every harness ran at k=0.
> - **T42 answered, and its flagship evidence was wrong.** The **TE2** the ticket leads with is
>   changed by **no** ablation — **TE is flex-eligible**, so a TE2 is a legal starter, not bench
>   depth. The slot channel owns **QB2 only**. **B1 = 38 %/29 % → INCONCLUSIVE.**
> - **★ The dominant channel is the reach WINDOW**, not the objective — 6 of 7–8 objected picks, and
>   it is what the user's own labels track (`corr(reach, labelled-bad) = +0.767`; his bad picks
>   average **+5.5** reach, his good ones **−10.6**). `starter_aware` cuts reach 0.2 and on the live
>   board **raises** it +5.4.
> - **★★ Realized points and the sim's title probability DISAGREE IN SIGN.** `starter_aware` is
>   **+50.4 realized** / **−0.295 title ×** with every shape measure improving. B3 blocks it on the
>   metric we least trust. T28's bench↔title link was **correlational**; interventionally it is
>   **the sim's, not the world's**. Filed with the −113 pts/team level bias. **Not reweighted.**
> - **B0: 628 leaves, zero gate values moved, all 8 pass flags hold.**
>
> **★ TWO DECISIONS ARE OPEN AND BOTH ARE THE USER'S** (measured, priced, deliberately not shipped —
> each is a seat-**character** change, and 16.14R's own lesson is not to read an argmax off noise):
> 1. **`blend_50` (`bench_weight = 0.5`)** passes B3 (+0.144 title ×, +0.026 playoff, +19.9 starter
>    value, 3 of 4 shape measures, nothing degraded) at a **stated realism cost of +0.0051 profile
>    distance** (0.0894 → 0.0945; bw 0.0 is 0.1020). For scale, **T30's swap cost +0.0021 and was not
>    shipped.** Needs a seam that does not exist: `bench_weight` is on `RiskModel` and the room builds
>    **one** model for all ten seats.
> 2. **The reach window — RECOMMEND KEEP 1.0**, and the realism sheet is why. B4 = unresolved on
>    outcome (non-monotone, ±25 vs se 9–13) and the knob is monotone/clean on reach (0.70 → 3.77),
>    but w=0.5 costs **+0.0360 profile distance** (0.0894 → **0.1254**) — **7× T30's unshipped
>    +0.0021, and worse than 16.14R's own baseline 0.1156**, i.e. it gives back the realism T24
>    bought. **Free on outcome, expensive on realism.**
>    **★★ And that reframes the whole objection.** Corpus round-1 mean reach is **2.868**; the
>    shipped seat's is **2.6405** — *the seat already reaches slightly LESS than a real human
>    drafter*. So **the seat is realistic; it just is not a *value hawk***. One seat is being asked
>    to do two jobs — be a plausible tenth of a calibrated room, and be the sharp value-seeker in it
>    — and only the first has a corpus to price it against. That is a **design** question (keep the
>    window and accept the name, or add a sharper seat **beside** it and re-measure the mix, which is
>    T30-shaped with a T15 re-run attached), not a knob turn. ⚠ The spec's "⚠ Do not" opens with
>    *do not delete or replace `value_hawk`*.
>
> **⚠ A harness bug VH introduced and caught — read before trusting any `--vh-window` sheet.** The
> flag rewrote the room built once in `main()`, but `--shuffle-room` re-draws the seating **per seed**,
> so it never reached the measured path. The sheet came back byte-identical while its config block
> reported `vh_window: 0.5`. **An echoed flag is not an applied flag**; the check that works is that
> the treatment and control arms must not produce identical numbers. Fixed (override is now a function
> applied to every room) + 2 regression tests. `--bench-weight` was never affected.
>
> **→ T43 opened (🟡):** T33 settled *which* count the context scale is and made visible that nobody
> justified it being a **count**. `eff` is a priority rank, `_local_z` is a z-score, so the multiplier
> is a ranks-per-SD conversion. Against the pool it reads **0.08**; against the **contended top-10**
> — the only rows an argmax is decided between — **0.29–0.34**, changing 6 of 15 picks. Fix **with the
> next 11.1 refit, alongside T26**: the weights absorbed the old scale, so they move together.
>
> **★ NEXT: the two decisions above, then Sessions MM-1 · MM-2** (the fitted manager model, 16.18) —
> unchanged and unblocked by any of this. Stage-0 FFC chore is current (`ffc-20260801`), next due
> after **08-07**. Open register: **T43** (new), T41, T40, T39, T36, T26.
>
> _(The VH/MM scoping pointer this replaces follows, still the spec of record for MM-1 · MM-2.)_
>
> **★★★ Next-session pointer (2026-08-01 session 5 — the `value_hawk` objection → SESSIONS VH · MM-1 · MM-2 SCOPED. Docs-only, no code, nothing ran. READ THIS FIRST.)**
>
> **State: 749 tests (unchanged), ruff clean. Still UNCOMMITTED**, on top of `5eff21d` (K2), now one tree
> with UI-1, UI-2, the 08-01 scoping docs, the Stage-0 reconciliation and this. **No `src/` change, no
> refit, no lockbox read, the frozen value stack untouched.** Edited: `docs/BUILD_PLAN.md` §"Sessions VH ·
> MM-1 · MM-2" (the plan of record), `docs/TECH-DEBT.md` (**T42** + T33's fix-when), `PLAN.md`
> §2026-08-01 (session 5), `findings.md`, `glossary.md`, `PROJECT.md` §5 (16.18), `ROADMAP.md`.
>
> **What happened.** The user reported that `value_hawk` "is consistently underperforming" and
> "consistently makes picks that are characteristically uncalled for" — a seat meant to be *"one of the
> most realistic replicas of a genuinely intelligent and knowledgeable fantasy player"* — and proposed
> rebuilding it as a personality **modelled on himself**, accepting it would take many drafts or a new
> narration system. He asked for a plan and recommendations.
>
> **★ Three decisions were ASKED before scoping** (they change the build — do not re-litigate):
> **(a) what "underperforming" means → both the picks and the finish, and they feel related**;
> **(b) what the model-of-him is FOR → a realistic opponent** (so: a **personality**, not a `DraftConfig`
> archetype; bar = held-out pick prediction, not realized points); **(c) time budget → ~1–2 hours,
> concentrated** (so: **designed elicitation**, not 20 mock drafts).
>
> **★★ THE DIAGNOSIS — the objection has a cause already on file, and it was filed as the wrong kind of
> thing.** `value_hawk` is the Phase-9 greedy in an opponent seat maximizing **portfolio CE**, and the
> value path is **slot-blind** (nothing in `draft/optimizer.py` references starters). T28 measured the
> fingerprint and left it as a *display* defect — but it recorded that `capital − startable` is negative
> for every seat **EXCEPT** `value_hawk` (**+152**), *the only seat that maximizes the sum*. The shipped
> mock shows what that buys (`analysis/mock_16_14R_picks.csv`, seat 8): a **QB2 in round 8** (ADP 63.3)
> and a **TE2 in round 9** (ADP 85.2) in a **10-team 1-QB full-PPR** league, first RB in round 6. Correct
> as capital accumulation, indefensible as a roster — and **one cause for both halves of his report**,
> which is exactly why answer (a) mattered. → **T42**.
>
> **★★ THE METHOD FINDING — T28 answered a correlational question and closed an interventional one.** Its
> bar B5 ranked roster-value definitions by **Spearman against title probability** (`team_value` +0.8382 >
> `portfolio_ce` +0.8202 > `starter_value` +0.7971) and used that to decide what the seat should
> **maximize**. *A relationship measured on outcomes is not a specification for the mechanism that produced
> them* — **T24's own lesson one level up, and the third time this repo has met that shape.** The
> interventional experiment (run the seat on each objective; measure the rosters it builds) has **never
> been run** and is cheap. A second reason the bar was blind to it, visible in T28's own write-up and not
> followed: **it pools ten seats, nine of which do not maximize the quantity at all.**
>
> **★★ THE SCOPING FINDING — "mimic me" is TWO objects, and conflating them is what made it look
> expensive.** *Beliefs* = where he disagrees with consensus about **players** (a board — and only
> disagreements need eliciting, **~50 rows** of 250, because consensus already encodes agreement).
> *Policy* = how he trades value/risk/need/scarcity **given** a board (a decision rule — ~300 **designed**
> pairwise comparisons). A mock draft observes both at once and identifies neither cheaply. Three facts
> make the hour sufficient, all properties of machinery that already exists: **(1)** a pairwise comparison
> and a real 40-way pick are the **same conditional-logit likelihood**, so elicited and realized data
> **pool into one fit**; **(2)** *his easy picks teach us nothing* — the informative observations are the
> ones where he is **torn**, and **you can design for that region, you cannot sample your way into it**;
> **(3)** the fit is a **shrunk deviation from the corpus β** (16.4's `k = σ²/τ²` EB machinery pointed at
> a manager), not a fresh fit that n ≈ 300 could not support.
>
> **★ THE BAR, fixed before the build because it cannot be fixed after.** A model fit on his stated
> preferences and scored **by him** always looks right — the **scoring trap** with a sharper edge, since
> the optimizer and the grader are the same human. Only **held-out prediction** is falsifiable: beat the
> corpus-fit `balanced` on top-1 accuracy **and** log-loss against **withheld comparisons** *and* **real
> mock picks never used in fitting** — or **report the null as a null**. And say plainly: **a faithful
> replica is a more *realistic* seat, not a stronger one** (the spent lockbox already called
> personalization noise-dominated on realized points).
>
> **⚠ Do not re-derive / do not "fix":**
> - **`value_hawk` is repaired, NOT replaced.** It is 1 of 10 in `REALISTIC_ROOM` and every T15/T24 bar was
>   measured with it there. The self-model ships **beside** it.
> - **Do not rebuild it as a `signal_weights` seat.** 16.14R measured why that cannot work — `pos_z(vbd)`
>   deletes VBD's cross-position content and the seat becomes a chalk tilt with extra width (5.5/10).
> - **If starter-awareness improves roster SHAPE and degrades the OUTCOME, that is a FINDING about the
>   sim**, not a tuning target: it draws injuries, and T28 measured **bench value alone predicting title
>   +0.711**, blend peaking at `w=0.90` against a shipped 1.0. Report it.
> - **VH.0 is written so it can kill its own hypothesis** (≥50 % slot-driven confirms; <25 % abandons).
>   Three tickets in a row here — T13, T24, T31 — had the wrong cause on file, and T24's prescription was
>   built and rejected.
> - **The personal board must never reach the cost report's baseline.** That report prices preference
>   *against* consensus; contaminating the baseline deletes the measurement. Per-seat, opt-in.
> - **T24's per-seat private board was measured harmful in its NOISE form.** A deterministic systematic
>   offset is a different object — **the seam may be reusable, the finding is not transferable.** Verify.
> - **16.18 narrowly reverses 2026-07-23's "nothing personal to the user" exclusion, and preserves its
>   reasoning**: `FittedManager` loads a **profile file**, so the mechanism is general and he is subject #1.
>   Same shape as K3's narrow reversal of "not auto-import".
>
> **★ NEXT: user reviews + commits, then Session VH.** Ordering against **K3** (league import) and **UI-3**
> is the user's call — VH and MM are independent of both, and the previously recommended order was K3 → UI-3.
> Open: **T42** (new), **T33**, **T41**, **T40**, **T39**, **T36**, **T26**. Stage-0 FFC chore is current
> (`ffc-20260801`), next due after **08-07**.
>
> _(The Stage-0 reconciliation pointer, still the authority on the chore and the two failing bars, follows.)_
>
> **★★★ Next-session pointer (2026-08-01 session 4 — STAGE-0 PULL + RECONCILIATION. Chore-only, no model change. READ THIS FIRST, especially before re-running any bar sheet.)**
>
> **State: 749 tests (unchanged), ruff clean. Still UNCOMMITTED**, on top of `5eff21d` (K2), now one
> tree with UI-1, UI-2, the 08-01 scoping docs and this. **Nothing refits, no frozen contract moved,
> the spent lockbox was not re-read, and the value stack is untouched.**
>
> **Stage-0 FFC chore: pulled `ffc-20260801` (this session). Next due after 08-07.** Backup verified.
>
> | step | result |
> |---|---|
> | `stage0_adp_snapshot.py` | **PASS** — 1,288 rows, gsis 98.0 %, `adp_asof` PIT verified |
> | `backup_db.py` | ☑ 08-01 snapshots + timestamped DB, checksums verified |
> | `phase0_8_validate.py` | **all gates PASS**, incl. `live-season snapshot fresh` age 0 |
> | T32 vintage gate (2026) | **PASS — 244 resolved == 244 served**, cache rebuilt in 12.9 s |
> | `phase16_5_situation_events.py --write` | gate fired → **138 → 154 rows**, annotations merged forward |
> | `pytest` | **749 passed** |
> | K1 / K1.5 / K2 sheets | **all still pass their own bars** |
> | UI-1 / UI-2 sheets | **B0 fails → T41** · **UI-2 B3 fails on its control only → T40** |
>
> **★★ READ BEFORE YOU "FIX" THE TWO FAILING BARS — they are the chore, not a regression.** The board
> moved (247 vs 246 rows: 3 arrivals, 2 departures, **91 players >2 picks**), so the room drafts other
> players and every draft-outcome leaf moves with it: `app_summary[0].who: 'autopilot' → 'YOU (T7)'`,
> `grades.YOU: 'C+ 59' → 'D+ 39'`, `adjacent_overlapping_pairs: 146 → 150`. **No model number moved and
> every nested sheet still passes.** The attribution is *measured*: the pre-pull sheets were read first
> and showed `all_pass: True` with **zero** unclassified leaves, preserved at
> `analysis/session_ui_{1,2}.pre_ffc20260801.json`.
> - **T41 🟠 — a bar sheet records no vintage for the board it was measured on**, and `_ALLOWED_MOVES`
>   has no category for *the input moved*, so B0 fails **by construction after every mandated pull**.
>   This is **T32 one level up** and takes T32's fix: stamp `mock.board_vintage` into the sheet and have
>   `_classify_moves` bucket board-driven leaves under a reported `vintage_changed`. ⚠ **Do NOT widen
>   `_ALLOWED_MOVES`** — a blanket allowance deletes the bar's entire purpose.
> - **T40 🟡 — UI-2's B3 control was passing on n = 1.** `handcuff` fired **exactly once** in 40 rows on
>   the 07-30 board and **zero** times on 08-01. `mismatched: []`, `FLAGS` byte-identical and unknown
>   byes preserved throughout — the identity holds, the *sampling* failed. Fix by **constructing** a
>   lead-back/handcuff pair, never by loosening the control.
> - **Interim rule:** after a Stage-0 pull, a B0 failure whose unclassified leaves are all draft-outcome
>   or board-count fields, **with every nested `*_all_pass` still True**, is a **re-baseline** — re-run,
>   check those flags, and commit the sheets so `HEAD` carries the new vintage.
>
> **⚠ The pull needs the DuckDB WRITE lock and a running Streamlit app holds it** (`db.connect()` is
> read-write; DuckDB is single-writer). Stop the app before the chore. You can still probe read-only,
> and `_pull_ffc` is a pure network call — so *whether a pull would yield anything* is answerable
> without the lock by reading FFC's `meta.end_date`.
>
> **☐ OPEN DECISION, not taken this session — consensus projections are dated 2026-07-05, 27 days behind
> the board.** This is **not** a mismatch the pull created: the reframe makes value (projections) and
> availability (ADP) *separate signals*. Coverage is fine — **4 of 201** skill rows uncovered, 3 of them
> the new arrivals. But the FantasyPros board is **as perishable as FFC's and has no recurring chore**,
> only `steps/phase4_1_consensus.py` (last run 07-05). ⚠ Re-pulling moves **every value number in the
> app**, so do it as its own step, not folded into a review. *And check coverage on `gsis_id`, never on
> `name` — a name join reports "Patrick Mahomes II" as a missing projection.*
>
> **★ NEXT is unchanged: user reviews + commits** (UI-1 + UI-2 + this are one tree), then **Session K3 =
> league import** (17.5 Sleeper → 17.6 ESPN), then **UI-3**. Open: **T41**, **T40**, **T39**, **T36**,
> **T33**, **T26**.
>
> _(Session UI-2's pointer, still the authority on the board columns and the tier null, follows.)_
>
> **★★★ Next-session pointer (2026-08-01 session 3 — ★ SESSION UI-2 ☑ COMPLETE: "the board answers the question" — AND ITS HEADLINE FEATURE IS A NULL. READ THIS FIRST.)**
>
> **State: 749 tests (was 737), ruff clean. UNCOMMITTED**, on top of `5eff21d` (K2), in one tree with
> UI-1 and the 08-01 scoping docs. Nothing refits, no frozen contract moved, the spent lockbox was not
> re-read, and **all fifteen existing board columns are bit-identical.**
>
> **Run it:** `uv sync --extra ui && uv run streamlit run app/main.py`
> **Re-check it:** `uv run python steps/session_ui_2.py` → `analysis/session_ui_2.json`
> *(`--only <bar>` writes `analysis/session_ui_2.partial.json` — UI-1's rule, kept.)*
>
> | bar | result |
> |---|---|
> | **B0** | UI-1's sheet re-runs passing (K2, K1.5, K1 nested), every moved leaf named, **and the fifteen existing columns are bit-identical** with the three new ones attached |
> | **B1** | **NULL, reported as one.** The overlap rule reproduces `coin_flags` exactly and cuts **1 tier per position, 2 over the board**. No `TIER` column ships → **T39** |
> | **B2** | `Δ` **is** `adp − overall_pick` and falls by exactly 1 per pick; `BARGAIN` == the card's field for **every player on the live board** |
> | **B3** | every glyph **is** `roster_construction_risk` on (roster + him), row by row, with a control requiring each to fire; unknown byes stay unknown; `FLAGS` byte-identical |
> | **B4** | one query, N projections — 5 modes × 6 filters; the split covers the fifteen, every app mode narrower |
> | **B5** | every new column documented with a worked example **and printing in the CLI** (`board --view value\|risk`, driven in a subprocess) |
> | **B6** | A6's chart equals `starter_value` exactly; the diverging pair clears 3.0 on both surfaces and white |
> | **FLOW** | six pages × k ∈ {0,1,4}, every board mode, zero exceptions, a pick made **by clicking** |
>
> **★ The user's eight decisions, taken before the run** (do not re-litigate): tier cut = **overlap,
> adjacent-chain** · tier scope = **within position** · `SLIM` to trade `PROJ` for `TIER` + `Δ` · modes
> = **SLIM · RANGES · VALUE · RISK** with `advanced` kept in `session.py` · glyphs in a **new `RISKS`
> column**, `FLAGS` untouched · `BARGAIN` a card **field**, not a ninth bar · **A6's chart built here** ·
> rule 7 waived, tree left uncommitted. **Two were overtaken by measurement and reversed in the open**
> — the tier column does not ship at all, so `SLIM` keeps `PROJ`; and `BARGAIN` ships with the opposite
> sign to the expression the plan writes.
>
> **★★ THE FINDING — the plan's one differentiated feature is a null, and the number that sold it hides
> its own denominator.** S2 was scoped as *"the single item in this plan that no competitor could copy
> without building our distribution stack first."* Measured on the live board: **1 tier per position**
> (62 RBs in one tier), **2 over the whole board**. Two causes. **(a) Scale** — the median RB 80 % band
> is **228 pts** against a median adjacent gap of **16.3**, i.e. **14×**, so overlap is universal *by
> construction*. **(b) A category error in the premise** — UI-PLAN calls it *"precisely Boris Chen's
> thesis on our own distributions"*, but Chen clusters **expert rank dispersion** (disagreement about
> placement) and we hold a **predictive interval** (uncertainty about outcome). T24's lesson arriving on
> a visualisation. **⚠ And `COIN`'s published `146 of 199` conflates *distinguishable* with *unknown*:**
> only **147** pairs have both bands, **146** overlap, **1** is a genuine break and **52** are missing
> bands. The honest figure is **99.3 % of evaluable pairs overlap** — a *stronger* honesty claim and a
> fatal one for navigating by it. All of it is **T39**; `coin_flags`' docstring and the `COIN` entry now
> carry the decomposition.
>
> **⚠ The gap cut is NOT a fallback.** `BUILD_PLAN`'s option (a) — *"falls by more than the pool's local
> median gap"* — is exceeded by **half of all pairs by definition**, so it returns ~n/2 tiers whatever
> the data says (31 over 62 RBs). The drop distribution is heavy-tailed, not bimodal. A real cut needs
> 1-D clustering with model selection on a **dispersion** quantity (`adp_stdev` is already on the board),
> which is modelling with its own validation — not a display session's work.
>
> **★ What shipped:** `Δ` (`adp − DraftState.overall_pick`) · `BARGAIN` (`adp rank − overall_rank`, whole
> board, **static**) · `RISKS` (`⚑⛓🛡⌀◔`) · `ADVANCED`(15) → `VALUE`(12) + `RISK`(9) via
> `st.segmented_control` · **A6's positional-strength chart** on 14.N (`session.positional_strength`) ·
> `roster_construction_risk(..., roster=)` for hypothetical evaluation · `app.state.byes/elevation`.
>
> **⚠ Do not re-derive / do not "fix":**
> - **`FLAGS` is byte-identical and must stay so** — K2's bar B4 matches on its text. `RISKS` is the
>   *scan* channel beside it; `⌀`/`◔` appear in both deliberately.
> - **The construction glyphs read the candidate's OWN row in the hypothetical readout**, not a movement
>   in its maximum. The first build tested `max_bye_starters` going up, which fires only when he joins
>   the already-largest cluster: **`⚑` fired zero times in 40 rows** and the bar's control caught it.
> - **`roster_construction_risk(..., roster=)` adds no arithmetic** and its default path is unchanged —
>   that is what keeps K2's 14.F bar and B0 unmoved.
> - **`RISKS` is scoped to the rendered rows and that is not the cliff/tier error.** A tier is a fact
>   about the pool; a construction flag is a fact about the *pair* (your roster, this player). **554 ms
>   for 40 rows** — one lineup solve per row, so a 200-row board page costs ~2.7 s per rerun.
> - **`advanced` stays in `session.py`, off the app's control.** K1.5's and K2's committed sheets
>   difference against `project_view(advanced=True)` returning exactly `BOARD_VIEW_COLS`.
> - **The mode control's option *values* stay UPPERCASE.** `board_mode` is a widget key, hence session
>   state, and UI-1's bar B3 pre-sets it to `"RANGES"`. Lowercasing them made B3 report **two honesty
>   surfaces missing** — a deletion alarm caused entirely by a renamed enum. *A display string anything
>   else can write is an interface.*
> - **`_ALLOWED_MOVES` in `steps/session_ui_1.py` is cumulative by design** and UI-2 added one entry
>   (`slim_columns`) with a dated note. A list getting longer is a display change; a number inside it
>   moving is not, and the latter is checked column by column by UI-2's own B0.
> - **`session.tier_series` is a null, not an unfinished feature.** Runnable, unwired, unit-pinned.
> - **The A6 chart deliberately does NOT inherit `chartCategoricalColors`** — UI-1 set that key so
>   future charts would, which was right for a *categorical* chart. This one is **diverging**.
> - **`palette.VALUE_GOOD/BAD` were measured, not chosen.** The first pair failed contrast twice (2.63
>   as a mark on the app's own background; both poles under AA as text on both themes at once).
>
> **★ NEXT: user reviews + commits (UI-1 and UI-2 are one tree), then — per the plan's recommended
> order — Session K3 = league import** (17.5 Sleeper for the contract → 17.6 ESPN, the one he needs;
> 17.7 Yahoo deferred to 14.4), **then UI-3** (A1 queue/tags + Cost rewire · A2 selected-player strip ·
> A3 draw the bars · A7 fewer taps). Open: **T39** (new, does not block UI-3) · **T36** (UI-3 sits on
> top of it) · **T33** · **T26**. Still ☐ in Phase 14/16: **16.6** the Beta Lab (skipped by decision)
> and **14.H** playoff-SOS (specced for the 14.3 frontend). Stage-0 FFC chore last pulled **2026-07-30**,
> next due after **08-05**.
>
> _(Session UI-1's pointer, still the authority on the palette, the theme and the seat strip, follows.)_
>
> **★★★ Next-session pointer (2026-08-01 session 2 — ★ SESSION UI-1 ☑ COMPLETE: "it looks like a product". READ THIS FIRST.)**
>
> **State: 737 tests (was 726), ruff clean. UNCOMMITTED**, on top of `5eff21d` (K2), together with the
> 08-01 scoping docs. Nothing refits, no frozen contract moved, the spent lockbox was not re-read.
>
> **Run it:** `uv sync --extra ui && uv run streamlit run app/main.py`
> **Re-check it:** `uv run python steps/session_ui_1.py` → `analysis/session_ui_1.json`
> *(`--only <bar>` writes `analysis/session_ui_1.partial.json` — see the ⚠ below.)*
>
> | bar | result |
> |---|---|
> | **B0** the K1 rule | the K2 sheet re-runs passing in full, K1.5's and K1's nested — **and every changed leaf is classified** |
> | **B1** one palette | six hexes, one home, `config.toml` asserted equal, **five surfaces styled**, every chip ≥ **4.88** contrast |
> | **B2** compression | prose **68 → 23** against ≤ 25, "before" read from `git show HEAD:` |
> | **B3** honesty | **all seven surfaces still render**, asserted by driving, both lockbox branches |
> | **B4** seat strip | order == `SeatMap`, on-deck == `team_for_pick`, next pick == the optimizer's; **150/150** picks differenced |
> | **B5** `P(THERE)` | **is** `reach_risk_view`'s number; uncovered rows NaN; **zero expanders**; the CLI has it |
> | **B6** T38 | **zero** `st.json`; the dump is a titled table |
> | **FLOW** | six pages × k ∈ {0,1,4}, zero exceptions; a pick **made by clicking** finished the draft |
>
> **★ The user's four decisions, taken before the run** (do not re-litigate): palette = **Okabe-Ito**,
> colourblind-safe, over the market convention — the convention puts QB gold / RB red / TE orange in one
> hue family, i.e. **three positions a deuteranope reads as one** · theme base = **dark** · prose target
> = **≤ 25** · and `P(THERE)` gets a **small labelled placement in `session.py`** rather than a merge in
> `app/`.
>
> **★★ THE FINDING TO CARRY FORWARD — "all bars pass" is a weaker claim than B0 was written to make.**
> The three nested sheets came back **passing** and **23 of their 538 leaves had moved**. Passing and
> unchanged are different statements. B0 now diffs each committed sheet against `git show HEAD:` and
> requires every changed leaf to fall under a **named** allowance — 5 rendered-element counts (UI-1 adds
> a table to 14.N and a panel to the rail), 6 T34 entropy draws (*a sheet that reproduced these would
> mean the randomisation had stopped working*), 8 wall-clock timings, 1 stat-dictionary entry for the
> attached column. **An unclassified move fails the bar.** No model number moved. ⚠ **It earned its
> keep by failing on its first run**: the one leaf it flagged was `bars.b3.worst_seat`
> (`upside_chaser` → `reacher`), the **argmax** of a per-seat millisecond vector whose entries sit
> within a few ms of each other — *the argmax of a noisy vector is noisier than the vector*, and it
> does not look like a number, so an eyeballed sweep goes straight past it.
>
> **★★ The second finding, paid for three times in one afternoon — a grep cannot tell doing from
> describing.** B1's palette census read 9 hexes in `palette.py`, three of them out of the **docstring
> explaining** why a 35 % tint fails; B6's `st.json` census read 1, and the hit was the **comment
> recording what T38 replaced**. Both are AST parses now. In a repo whose comments deliberately quote the
> code they replaced, *a text scan over source is not a measurement of behaviour.* Third instance the
> same day: B1 reported four of five surfaces coloured, and the missing one was the **log** — at k=1 the
> human seat drafts first, so the fixture's log was **empty**, and *a surface with no rows is not a
> surface that failed to colour.*
>
> **⚠ Do not re-derive / do not "fix":**
> - **`app/palette.py` is the only home for the six hex strings** (B1 asserts it, on the AST). The
>   `.streamlit/config.toml` copy is unavoidable — a TOML file is read before any of our Python runs —
>   and is **asserted equal** rather than hoped about. *A duplication you assert is a duplication; a
>   duplication you hope about is a bug.*
> - **Chip ink is chosen by comparing both contrasts, never by a luminance threshold.** The break-even
>   is **0.179**, not 0.5; a 0.42 cut lettered QB (`#E69F00`, luminance 0.410) in white at 2.3 : 1.
> - **Two treatments, not one.** UI-PLAN §S1's "35 % tint with full-strength text" is right for dark and
>   **wrong for light** (2.4 : 1) — hence solid chip where the cell *is* a position, rgba tint with **no
>   colour set** where it merely mentions one. A colour that works in one theme breaks on the toggle.
> - **The `FLAGS` string was NOT edited to carry the `⌀` glyph.** K2's bar B4 matches on it; a display
>   layer must not edit the thing a bar reads. The glyph is on the chip.
> - **`session.team_for_pick` is a licensed second copy of the snake formula** — licensed *only* by B4
>   differencing it against `DraftState.team_on_clock` at every one of 150 picks (16.17's precedent).
>   A third copy voids that. ⚠ B4's first version checked **15** picks and called itself exhaustive
>   because it advanced the room between checks.
> - **`app/palette.STYLED` ships in the app, not in the bar** (the `probe.py` rule): Streamlit encodes a
>   Styler's CSS into the Arrow payload rather than exposing it, so counting the call is the only honest
>   instrument for "did this surface get coloured".
> - **`--only` writes `analysis/session_ui_1.partial.json`.** The house pattern overwrites the real
>   artifact; a 30-second `--only b6` against the **K2** runner destroyed its committed eight-bar sheet
>   this session and it was restored from git. *A partial measurement should not look like a full one.*
>
> **★ Deferred out of UI-1 deliberately, and owed by name:** **A6's positional-strength chart → UI-2**
> (it needs per-position value sums per team — a genuinely new derivation) and **the hatched `censored
> floor` bar → UI-3's A3** (where `st.html` quasi-bars get drawn; UI-1 ships the `⌀` chip + tooltip).
>
> **★ NEXT: user reviews + commits, then — per the plan's recommended order — Session K3 = league
> import** (17.5 Sleeper for the contract → 17.6 ESPN, the one he needs; 17.7 Yahoo deferred to 14.4),
> **then UI-2** (`docs/BUILD_PLAN.md` §"Sessions UI-1 … UI-4"). Still ☐ in Phase 14/16: **16.6** the
> Beta Lab (skipped by decision, not a defect) and **14.H** playoff-SOS (specced for the 14.3 frontend).
> **T36** is still open and UI-3 sits on top of it. Stage-0 FFC chore last pulled **2026-07-30**, next
> due after **08-05**.
>
> _(The scoping session that produced the plan, still the authority on the survey and the four sessions, follows.)_
>
> **★★★ Next-session pointer (2026-08-01 — the competitive UI/UX deep dive → SESSIONS UI-1 … UI-4 SCOPED. docs-only, no code.)**
>
> **State: unchanged — 726 tests, ruff clean, still UNCOMMITTED.** Nothing ran, no `src/` change, no
> `app/` change, no test-count change. Edited: `docs/UI-PLAN.md` (new), `docs/BUILD_PLAN.md`
> §"Sessions UI-1 … UI-4", `docs/TECH-DEBT.md` (**T37**, **T38**), `ROADMAP.md`, `glossary.md`,
> `findings.md`, `PLAN.md` §2026-08-01.
>
> **What happened.** The user asked for a deep dive into the prominent fantasy football UIs (PFF,
> FantasyPros, Draft Sharks, "etc."), on the premise that theirs are more usable than ours, and for a
> comprehensive plan with **both** recommendations and non-recommendations. **Eleven products
> surveyed** — FantasyPros Draft Wizard · Draft Sharks War Room · PFF 2026 · 4for4 Draft Hero ·
> RotoWire · Sleeper · ESPN · Yahoo · Underdog · UDK · Footballguys, plus Boris Chen and KeepTradeCut —
> then `app/` audited page by page.
>
> **★ The premise is right and its obvious reading is wrong.**
>
> > **We are not missing analysis. We have *more* decision-relevant content than any product surveyed.
> > We are missing an information architecture.**
>
> The census over `app/`'s 1,903 lines: **22 `st.dataframe` · 37 `st.caption` · 31 banners · 28 markdown
> blocks · 9 `st.metric` · 0 uses of colour to encode anything · 0 status icons · 0 tier breaks drawn** —
> **68 prose blocks to 9 visual elements**, a ratio every competitor inverts. And the density argument
> runs the other way from the intuition: our `ADVANCED` view is **15 columns, two more than Draft Sharks'
> full rankings table**, whose density is the most-criticised property in its own category reviews.
> **The work is ranking, encoding and hiding. It is not adding.**
>
> **★ The corollary that decides the design.** Seven things we ship have **no competitor equivalent**:
> validated `P(available)` with an un-drifted baseline · `COIN` · `censored floor` · the T27 chain ·
> lockbox provenance · the **printed** 14.I grade weights · the cost report. Every one currently reads
> as an **apology**. Give them a visual language and they become the reason to use this instead of
> FantasyPros — hence *a censored quantity should look different, not be described as different*, and
> hence the compression bar is **paired** with a render bar: **compress and relocate, never delete.**
>
> **★ The one differentiated feature (UI-2's S2): cut tiers by band overlap, not by value gaps.** A tier
> ends where adjacent 10–90 bands stop overlapping, which makes it a claim of statistical
> indistinguishability — exactly what `session.coin_flags` already computes (146/199) and buries behind a
> checkbox. Boris Chen's thesis on **our** distributions. Nobody can copy it without a distribution stack.
>
> **★ Two defects, both ticketed and both UI-1 step 0.** **T37** — `draft_room._reach_risk` renders
> inside `st.expander(expanded=False)` *directly beneath its own docstring* saying *"a readout you have
> to ask for is a readout nobody asks for."* **T38** — `post_draft` ships `c1.json(frames["elite"])`, a
> raw JSON dump, on the page whose job is to be a report card.
>
> **★ NEXT: user reviews, then Session UI-1** — pure formatting, nothing enters `session.py`, done-bar is
> that the K2 sheet re-runs unchanged (`docs/BUILD_PLAN.md` §"Sessions UI-1 … UI-4"). **⚠ Three
> decisions must be ASKED before a straight run:** (a) the **palette** — market convention (QB gold · RB
> red · WR blue · TE orange · K purple · DST green) or ours; (b) **theme base** dark or light; (c) the
> **prose target** — ≤ 25 blocks is proposed and is a judgement call.
> **Recommended order: UI-1 → K3 → UI-2 → UI-3 → UI-4** (UI-1 has zero engine risk; K3 makes the app
> *correct* for his league and should not queue behind three UI sessions; the only coupling is UI-4's
> presets sitting above the 17.3 form K3's importer fills). Stage-0 FFC chore last pulled 2026-07-30,
> **next due after 08-05**.
>
> _(Session K2's pointer, still the authority on the app's surfacing and its bars, follows.)_
>
> **★★★ Next-session pointer (2026-07-31 session 2 — ★ SESSION K2 ☑ COMPLETE: surfacing + the post-draft page.)**
>
> **State: 726 tests (was 702), ruff clean. UNCOMMITTED**, on top of `455fb8e` (K1.5). Nothing
> refits, no frozen contract moved, the spent lockbox was not re-read, and **B0 re-runs both
> committed sheets** — K1.5's, which nests K1's — because the rule that outranks the other seven is
> still *if a display change moves a number, it is not a display change.*
>
> **Run it:** `uv sync --extra ui && uv run streamlit run app/main.py`
> **Re-check it:** `uv run python steps/session_k2_app.py` → `analysis/session_k2_app.json`
>
> | bar | result |
> |---|---|
> | **B0** the K1 rule | K1.5's whole sheet re-runs passing, K1's nested inside it |
> | **B1** 14.N | renders at k ∈ {0,1,4}, one page body, standings identical to `session.summary_table`, odds led by the multiple, both 16.17 honesty rules on screen |
> | **B2** 14.E | the `CLIFF` column **is** `optimizer.positional_cliff(pool, risk.bv)`, and does not move when the board is truncated |
> | **B3** 14.F | 9 starters accounted for once, **1 unknown bye stays unknown**, 0 week-0 rows, handcuffs lead-back-only |
> | **B4** 14.G | one query / three projections; **70 of 200 rows censored, all flagged**; 146 of 199 adjacent pairs overlap |
> | **B5** 14.I | weights sum to 100, the total re-adds from the printed parts, **median team = C**, k=4 → 4 rows, no combined column |
> | **B6** 16.12 | labels are the engine's, both probabilities present, window == the optimizer's `_next_own_pick` |
> | **FLOW** | a draft **finished by clicking** lands on 14.N; **all six pages render, zero exceptions** |
>
> **★ The finding to carry forward — a scale and its labels have to be anchored to the same thing.**
> 14.I scores four components min–max across the ten teams, so a middling roster lands near **50 by
> construction**. On plain US bands (90/80/70/60) that is a **D+**, and six of ten teams in an
> ordinary room graded D or F — the app calling an average draft a failure. The scoring was never
> wrong; the letters were anchored to a different scale. `GRADE_BANDS` now put `C` at 50. It was only
> caught because the first run printed **all ten** letters instead of one: *a curve is only legible
> next to the population it was drawn on.*
>
> **★★ Two more defects, and neither was in the spec.** (1) The handcuff readout had the depth chart
> **upside down** — "the next RB on the same team" reported *Tyjae Spears → backup Tony Pollard*,
> pricing insurance on the wrong life; only a backfield's **lead** back generates a row now. Its
> first unit test drove a full draft on the synthetic board, which seated **no lead back at all**, so
> it asserted over an empty frame and passed while proving nothing — *a test that cannot fail is the
> same defect as a bar that cannot fail.* (2) Deriving the CLI board's header from the same dict that
> formats its cells immediately raised *Sign not allowed in string format specifier* — a crash the
> pre-K2 code would also have hit on the first NaN in the signed `BV` column and had simply never
> met. **Two descriptions of one thing hide each other's bugs until you make one read the other.**
>
> **⚠ Two things a later session must not undo.** (1) **`session.lineup_choice` is the single
> starters read** — 14.F, the 14.L grid and the roster rail all go through it, which is 17.1's
> `flex_groups` rule one altitude down; a fourth display-layer fill order would be the copy nobody
> thinks to test. (2) **The room page gave up the standings/odds/draft-flow readouts** to 14.N —
> *moved, not copied*. Do not restore versions of them there.
>
> **★ Structure now:** `app/post_draft.py` is 14.N; `app/room_grid.py` keeps only the grid, the log
> and the stat dictionary; the board page and the draft room both offer **SLIM / RANGES / ADVANCED**
> over one `session.board_view` frame. K1's rule holds unchanged: `session.py` is the one derivation
> site, `app/` only formats — every K2 readout is a new function *there*, not in `app/`.
>
> **★ NEXT: user reviews + commits, then Session K3 = league import** (17.5 Sleeper for the contract →
> 17.6 ESPN, the one the user needs; 17.7 Yahoo deferred to 14.4) — `docs/BUILD_PLAN.md` §"Session K3"
> + §"Phase 17 — league import". Then **L+** the go-live tail. **Still open in Phase 14/16: 16.6** the
> Beta Lab tab (**skipped by user decision this session** — the value-side track is an honest null,
> not a defect) and **14.H** the playoff-SOS lens (specced for the 14.3 frontend, not the Streamlit
> MVP). Stage-0 FFC chore last pulled 2026-07-30, **next due after 08-05**.
>
> _(Session K1.5's pointer, still the authority on the draft room and its bars, follows.)_
>
> **★★★ Next-session pointer (2026-07-31 — ★ SESSION K1.5 ☑ COMPLETE: the draft room a human can use.)**
>
> **State: 702 tests (was 691), ruff clean. UNCOMMITTED**, on top of `3494ccc`. Nothing refits, no
> frozen contract moved, the spent lockbox was not re-read, and **Session K1's own bar sheet re-runs
> passing** — B1's 150-pick app-vs-CLI identity included. That is the rule that outranks the six:
> *if a display change moves a number, it is not a display change.*
>
> **Run it:** `uv sync --extra ui && uv run streamlit run app/main.py`
> **Re-check it:** `uv run python steps/session_k1_5_app.py` → `analysis/session_k1_5_app.json`
>
> | bar | result |
> |---|---|
> | **B0** T34 the seeding default | 20 app drafts from seat 6 → **20 distinct** openings (was 1); a locked seed pair replays picks *and* seating; the CLI still returns `engine.T34_REFERENCE`, identical twice |
> | **B1** 14.K one page body per rerun | `{settings: 1}` · `{settings: 1}` · `{draft: 1}` — under `st.tabs` all three read 4 |
> | **B2** slim ≡ advanced | 5 position filters, 40 rows, one query and two projections; `#` handle kept |
> | **B3** clocked ≡ stepped | identical logs over 150 picks; worst modelled pick **10.2 ms** |
> | **B4** both grids | BY PICK re-reads the log exactly; BY SLOT sums to `starter_value`, **gap 0.0**, k ∈ {1,4} |
> | **B5** 14.O | 14 columns documented with worked examples; rail == `starter_needs`; CLI `stats` serves the same dict |
> | **FLOW** *(new)* | a draft **started by clicking** and a pick **made by clicking**: 5 picks → 14, Bijan Robinson on the roster |
> | **K1** | Session K1's whole sheet re-run, all PASS |
>
> **★ The finding to carry forward — a pre-registered worry can be retired by its own measurement, and
> the guard should survive anyway.** 14.M was built around the fear that `value_hawk`'s Phase-9 greedy
> would be too slow for a 5-second clock. Measured on a full live draft: **worst single modelled pick
> ~10 ms**, with `value_hawk` within a millisecond of the behavioural seats. The 8.5 s/pick number that
> seeded the worry is `draft/mcts.py`'s *search*, dropped in Session D — a figure that travelled to a
> place it did not describe. The floor (`MIN_CLOCK_SECONDS = 1`) ships anyway, carrying its measurement
> and its date, plus `_overrun_notice`, which reports the actual worst tick against the chosen interval:
> *a constant justified by a measurement needs something that notices when the measurement goes stale.*
>
> **★★ The second finding, and it is K1's lesson one level up.** All six bars passed; then the app was
> driven under `AppTest` the way a human drives it — click **Start draft**, click a player — and the
> click surfaced `st.session_state.setdefault("clock_secs", …)` sitting directly above the slider that
> owns that key (Streamlit's documented anti-pattern; a warning, not a crash, which is why nothing else
> caught it). K1 answered its own broken launch with `bar_imports`, which proves the entry point
> **imports**. It does not prove the app **works**. Hence the new **`bar_flow`**. *An import bar and a
> use bar are different claims, and any session that adds UI owes the second one.*
>
> **⚠ Two things a later session must not undo.** (1) **`steps/` keeps `--seed 7` and an unset
> `--room-seed`** — T24's sweep, 16.17's 1,014-triple check and every committed bar sheet are
> differenced against them; the entropy default is the app's and stops at `app/engine.draw_seeds`, and
> `engine.T34_REFERENCE` exists so a bar can *assert* that rather than a comment claiming it.
> (2) **`app/probe.py` ships in the app**, not in the test — a probe that only exists under the test
> measures the test.
>
> **★ Structure now:** `app/main.py` is a **router** (`st.navigation`, five `st.Page`s); bodies live in
> `screens.py` (Settings · Board · Cost), `draft_room.py` (the room, the clock, the pick controls, the
> rail) and `room_grid.py` (14.L + the standings/odds/draft-flow/log readouts behind a **radio** — the
> nested `st.tabs` had T35's defect too). `state.py` holds the cached engine seam, `nav.py` the page
> registry. **K1's rule holds: `session.py` is the one derivation site, `app/` only formats.**
>
> **★ NEXT: user reviews + commits, then Session K2 = surfacing + 14.N the post-draft page**
> (`docs/BUILD_PLAN.md` §"Session K2"). **14.N absorbs the standings/odds/draft-flow readouts currently
> parked on the room page** — move them, do not duplicate them. Then **K3** league import (17.5–17.7)
> → **L+** the go-live tail. Stage-0 FFC chore last pulled 2026-07-30, **next due after 08-05**.
>
> _(Session 8's scoping pointer, which is where all of this came from, follows.)_
>
> **★★★ Next-session pointer (2026-07-30, session 8 — the app's FIRST REAL USE → SESSION K1.5 SCOPED. docs-only, no code.)**
>
> **State: unchanged — 691 tests, ruff clean, still UNCOMMITTED** on top of `945e302`. Nothing ran, no
> `src/` change, no test-count change. Edited: `docs/BUILD_PLAN.md` (§14.K–§14.O, §"Phase 17 — league
> import", §"Session K1.5", §"Session K2", §"Session K3"), `docs/TECH-DEBT.md` (**T34**, **T35**),
> `ROADMAP.md`, `PROJECT.md` §5, `docs/PLAYER-VIEW.md` §10, `PLAN.md` §2026-07-30 (session 8), `glossary.md`.
>
> **What happened.** The user drove the K1 app and came back with eleven notes. **Ten are UX. One is a bug,
> and it was reproduced before it was written down.**
>
> **★ T34 🔴 — every mock draft is the same mock draft.** He reported that from seat 6 the room always opens
> Gibbs · Chase · Taylor · McCaffrey · Cook. It does. `app/engine.start_draft` defaults **`seed=7`** and
> **`room_seed=None`**, which freezes *both* sources of variation — the pick RNG (`DraftState.rng =
> default_rng(7)`) and the seating (`room_seed=None` keeps `REALISTIC_ROOM`'s listed order instead of
> shuffling, so the same personality sits in the same chair every draft). Measured on the live 2026 board:
>
> | run | first five picks |
> |---|---|
> | `seed=7, room=None` — **the shipped default** | Gibbs · Chase · Taylor · McCaffrey · Cook |
> | the same call again | **identical** — his report, to the player |
> | `seed=8, room=None` | Gibbs · **Nacua · Jeanty · Bijan · Chase** |
> | `seed=7, room=3` | **McCaffrey** · Gibbs · Taylor · Chase · Cook |
>
> So **the engine is fine and the personalities are sampling** — the human-facing default is the measurement
> default. **⚠ The fix is two defaults, not one behaviour: `steps/` must keep `--seed 7`**, because T24's
> sweep, 16.17's 1,014-triple mapping check and every committed bar sheet are differenced against it.
> *A measurement default and a human default are different objects, and the K1 port carried the CLI's into
> the app because the CLI's was the only one that existed.* Bonus: shuffling the seating per draft is also
> **more faithful to how the room was measured** — T24's third method failure was measuring on one fixed
> seating, which flatters by 5–7 pp and is a *bias* more seeds cannot remove. The app has been showing him
> exactly that seating.
>
> **★ T35 🟠 — found while reading the notes, and his own first request is its fix.** `st.tabs` executes
> **every** tab body on every rerun (it hides the inactive ones client-side), so one keystroke in the draft
> room also re-runs `tab_cost`'s `_prepare_board` + whole-board option build. 🟠 rather than 🟡 because it is
> the **hard blocker on the 14.M pick clock**: a timer-driven rerun must rerun one fragment, not four tabs.
> The remedy is `st.navigation`/`st.Page` = **14.K**, which he asked for on ergonomic grounds. *The
> ergonomic request and the performance defect have the same fix.*
>
> **★ NEXT: Session K1.5 — the draft room a human can use** (`docs/BUILD_PLAN.md` §"Session K1.5", six
> pre-registered bars, **rule-7 gate NOT waived**). Steps: **0** T34 the seeding default · **1** 14.K pages
> not tabs (T35) · **2** the slim board (`# · PLAYER · POS · ADP · PROJ`) + advanced toggle, **pick buttons
> in the row**, **search results under the box** · **3** 14.M the pick clock · **4** 14.L the room grid
> (every team across the top, by pick or by slot) · **5** the roster rail + 14.O tooltips.
> Then **K2** (surfacing + **14.N** the post-draft page) → **K3** (league import) → L+.
>
> **⚠ Two user decisions must be ASKED at their step, not defaulted:** (a) **your own pick clock** — no
> clock on your seat / auto-pick at 0 / pause at 0; (b) nothing may promise a clock interval the room
> cannot meet — `value_hawk` runs the Phase-9 greedy per pick, so **measure worst-case per-seat latency on
> the live board first**.
>
> **⚠ Do not:** put a derivation in `app/` (K1's rule — `session.py` is the one derivation site, which is
> why B1 holds by construction) · build a second board frame for the slim view (it is a **projection** of
> `board_view`, two column subsets of one query) · make the CLI's `--seed` random to match the app · let the
> slim board drop the `#` pick handle · re-derive the roster-slot fill order in the 14.L grid (17.1:
> `flex_groups()` is the **single** fill-order rule, and three solvers had each re-derived it once).
>
> **★ League import (17.5–17.7, Session K3) narrowly reverses the 2026-07-23 "not auto-import" decision.**
> The manual form stays primary; import is an **alternative constructor for `LeagueSettings`**, so nothing
> downstream changes. Order and honest cost: **Sleeper first for the contract** (free, keyless, client
> already built, offline fixture — say plainly that its user value is the contract, since he is not on
> Sleeper) → **ESPN** (the one he needs; pasted `espn_s2`+`SWID` for private leagues, labelled fragile,
> last-good cached, **cookies never logged**) → **Yahoo deferred to 14.4** (OAuth2 needs a hosted redirect
> the Streamlit MVP does not have). An import always lands in the 17.3 form for the user to **confirm**: a
> wrong scoring setting does not fail loudly, it silently re-ranks every player.
>
> _(Session K1's pointer, still the authority on the app's structure and its bars, follows.)_
>
> **★★★ Next-session pointer (2026-07-30, session 7 — ★ SESSION K1 ☑ COMPLETE: THE APP EXISTS.)**
>
> **State: 691 tests (was 669), ruff clean. UNCOMMITTED**, on top of `945e302` (Session I.5, pushed).
> Nothing in the engine moved: no fitted β, no frozen contract, the spent lockbox not re-read.
>
> **⚠ READ THIS BEFORE TRUSTING ANY BAR IN THIS SESSION.** The app **shipped broken** —
> `uv run streamlit run app/main.py` raised `ModuleNotFoundError: No module named 'app'` for the
> user on first run — while **nine bars reported PASS**. Streamlit puts the *script's* directory on
> `sys.path`, not the repo root. Fixed by a `sys.path` bootstrap at the top of `app/main.py`
> (**do not delete it**; it is load-bearing, not boilerplate). Why nothing caught it: the unit tests
> ran under pytest's `pythonpath = ["src", "."]`; `AppTest` ran in a process that had already
> inserted the root; and the server bar fetched `/` — but **Streamlit does not execute the script
> until a browser opens a websocket session**, so an HTTP GET returns the same HTML shell either
> way, *and the bar's own launcher used `python -m streamlit`, which adds the cwd, while every doc
> tells a human to use the console script.* New **`bar_imports`** runs the entry point as a bare
> script from `/tmp` with `PYTHONPATH` scrubbed and reproduces the user's traceback exactly on the
> unfixed file; `bar_server` now launches **both** ways and its name says what it does not prove.
> Full write-up: `findings.md` §"The app shipped broken and every bar said PASS". **Durable rule:
> for anything with an entry point, one bar must run it the way the documentation says to run it,
> from outside the repo, with the environment scrubbed.**
>
> **Run it:** `uv sync --extra ui && uv run streamlit run app/main.py`
> **Re-check it:** `uv run python steps/session_k1_app.py` → `analysis/session_k1_app.json`
>
> **★ Phase 14.1 — four tabs on the LIVE board.** Settings (17.3) · Board + `why` · Draft room
> (any k of n, 14.J) · Cost. Plus **T32 ☑**. Write-ups: `findings.md` §"Session K1",
> `PLAN.md` §2026-07-30 (session 7), `docs/BUILD_PLAN.md` §"Session K1" ✅ OUTCOME,
> `docs/TECH-DEBT.md` T32 ☑, `ROADMAP.md`, `glossary.md`.
>
> | bar | result |
> |---|---|
> | **B1** app == CLI, same seed | **150/150 picks identical**, 10/10 teams, 0 differing numbers |
> | **B2** T32 row identity | `resolve_board` 244 == `room_board` 244, 0 missing |
> | **B3** settings round-trip | lockbox case rebuilds the engine defaults exactly; 11 teams refused |
> | **B4** k of n ∈ {0,1,4,9,10} | all complete, **0 avoidable** unfilled slots |
> | **B5** `why` identities | 40/40 on the live board, 0 mismatched |
> | **B6** cache-key safety | `full_ppr` returns `RuleSet()` itself; scoring change gated |
> | **APP** AppTest / imports / server | 4 tabs 0 exceptions · bare-script import from `/tmp` OK · both launchers serve 200 |
>
> **★★ THE ONE THING TO CARRY FORWARD — the fixture was too rich to fail.** Two real bugs
> (`explain_chain` and the cost picker were handed the **raw** board, not `_prepare_board`'s) shipped
> past **17 passing unit tests**, because the test fixture was hand-built with every column any
> consumer wanted. B5 on the live board caught one; **booting the app under `AppTest` caught the
> other**. *A column set is part of a function's contract even when nothing declares it, and a
> fixture that satisfies every consumer at once cannot detect that one is being handed the wrong
> frame.* T22 one level down. **Keep the live-boot bars in every future app session.**
>
> **⚠ Do not re-derive / do not "fix":**
> - **`draft/session.py` is the ONLY place a derived draft frame is computed.** `steps/mock_draft.py`
>   and `app/` are **renderers** — they choose column widths, not what a number is. If you are about
>   to compute something in either, it belongs in `session.py`. B1 holds *by construction*; a second
>   copy is how T18/F.5/T27 happened. The CLI's output was banked before the refactor and is
>   **byte-identical across seven commands** — re-bank and re-diff if you touch it.
> - **`app/` is top-level, outside `src/`** (user decision). `pyproject.toml` carries
>   `pythonpath = ["src", "."]` for pytest and `app` in ruff's `src`. Do not move it into the package
>   — the engine is a library that knows nothing about how it is displayed.
> - **`src/fantasy_quant/app/` is deleted, not renamed** (the T18 rule). Do not resurrect it; stale
>   references to `app/streamlit_app.py` survive in `PROJECT.md`, `docs/BUILD_PLAN.md` §16.6/§16.12
>   and older `CLAUDE.md`/`PLAN.md` entries — they mean **`app/main.py`** now, and are left rather
>   than rewritten because those sections are historical.
> - **T32's pass was accidental before the fix** — `ENRICH_VERSION`'s bump had rebuilt the 2026 cache
>   after the Stage-0 pull, so the gate read 244/244 anyway. The v2/v3 parquets still hold **223**
>   rows. The claim rests on the **control** (revert the key → both mechanism tests fail correctly),
>   not on the gate. *A coincidence that makes a bar pass is not a fix.*
> - **The honesty surfaces must keep rendering, not merely be true**: `lockbox_validated()` as a
>   banner (both branches are *supported* leagues — the difference is evidence, not capability), the
>   T28 `STARTABLE`/`CAPITAL` pair labelled, T29's fair-share multiple **leading** the percentage, and
>   the two 16.17 rules with the actual k in them.
> - **The scoring dropdown needs explicit confirmation** and that is not UI politeness: `RuleSet` is
>   serialized into `cached_distribution`'s key, so a cosmetic change forces a silent nine-season
>   rebuild (B6).
>
> **★ NEXT: user reviews + commits, then Session K2 = surfacing** — 14.E tier-cliff · 14.F roster
> risk · 14.G uncertainty board · 14.I draft grade · the 16.6 Beta Lab tab · the 16.12
> availability/reach-risk readout · the `PLAYER-VIEW.md` cards. All read already-frozen machinery.
> **Not in the app yet, deliberately:** auction (15.4), keeper entry (17.4), `draft_type` — engine-
> complete, K2/L questions. Open against the mock drafter: **T33** · **T26**. Stage-0 FFC chore last
> pulled **2026-07-30**, next due after 08-05.
>
> _(Session I.5's pointer, still the authority on the seat map, follows.)_
>
> **★★★ Next-session pointer (2026-07-30, session 5 — ★ SESSION I.5 ☑ COMPLETE. READ THIS FIRST.)**
>
> **State: 668 tests (was 658), ruff clean. UNCOMMITTED**, sitting on top of Session I (`63fc304`).
> Nothing refits: no fitted β, no frozen contract, the spent lockbox untouched.
>
> **★ 16.17 — the seat map. A user can now drive as many seats as they like.**
> `steps/mock_draft.py start --seats 3,7 --auto 7` · `pick --team 3` · per-seat `summary`.
> One `SeatMap` (`draft/personalities.py`) replaced **four** copies of the one-human `team → seat`
> arithmetic — the spec named three and missed the one in `steps/phase16_15_mock_room.py`'s
> hype-routing measurement. `DraftState` gained `human_teams` (default `{your_team}`, which is why
> nothing outside `draft/` changed) + `seat_roles`; `run_to_completion` takes a `dict[team, pick_fn]`;
> `mock.full_room_pick_fn` is now one call with a zero-human map.
> Done-bar `steps/phase16_17_seat_map.py` → `analysis/phase16_17_seat_map.json`. Write-ups:
> `findings.md` §"Session I.5", `PLAN.md` §2026-07-30 (session 5), `docs/TECH-DEBT.md` **T33**,
> `docs/BUILD_PLAN.md` §16.17 ☑, `ROADMAP.md`, `glossary.md`, `docs/PLAYER-VIEW.md` §9.5.
>
> | bar | result |
> |---|---|
> | `room_index` == the deleted formula, **exhaustively** | 1,014 triples, 0 mismatches |
> | k=1 / k=0 reproduce the deleted arithmetic pick-for-pick | 54 draft pairs, **0 differ** |
> | **the control can fail** (poisoned mapping) | 36/36 poisoned runs differ |
> | k ∈ {0,1,4,9,10} complete + legal | 15 drafts, **0.00 % avoidable illegality at every k** |
> | the room bar sheet | **0/628 fields differ** vs a pre-16.17 control on today's board |
>
> **⚠ Do not re-derive / do not "fix":**
> - **`analysis/mock_room_bars_verify_20260729.json` is NO LONGER a clean reference.** It differs on
>   **79/628** fields — all in `readout_2026` (Stage-0 banked a 07-30 board; T31's `ENRICH_VERSION`
>   bump rebuilt the caches against it) or in two `config` provenance fields that postdate it. **0 of
>   the 412 gate fields** differ. To claim bit-identity against it, run a *pre-change control* on
>   today's board (`git worktree` + **`PYTHONPATH=<wt>/src`**, then assert the old module lacks the
>   new symbol) — `steps/phase16_17_seat_map.py --control-bars`. *A committed artifact is a control
>   only while nothing else it depends on has moved.*
> - **`is_you` stays the PRIMARY seat**, not `team in human_teams` — the frozen cost report and every
>   backtest step difference on it. `your_team` likewise stays a single int and stays primary;
>   `cost_report.py`, the 9.5 objective, `formats/bestball.py` and `draft/mcts.py` must never learn a
>   second human exists.
> - **`seat_role` is opt-in** (written only when `DraftState.seat_roles` is set) so the batch pick log
>   keeps the exact column set the committed artifacts were differenced on. Do not make it default.
> - **`make_value_hawk_pick_fn(n_teams=len(seats))` is the ROOM size and was preserved on purpose** —
>   9 interactive vs 10 batch, and now `10 − k`. That is **T33**, and fixing it needs a T24-style
>   seating-marginalized before/after, not an edit.
> - `SeatMap` lives in `personalities.py`, **not** `simulator.py` (16.15's layering rule): the draft
>   engine every earlier phase imports must not learn the personality library.
> - The two **honesty rules** are rendered by the readouts, not just documented: *k human teams in one
>   draft are ONE observation* (`summary` has nowhere to put a combined number) and *the T15 realism
>   bars describe a fully-simulated room* (`drift` prints its scope). 14.J must keep both.
>
> **★ NEXT: user reviews + commits, then Session J (optional Phase 15.1 dynasty) → Session K =
> Phase 14.1 MVP + all surfacing, strictly last, do not bundle.** Open against the mock drafter:
> **T33** (new) · **T26** (next 11.1 refit) · **T32** (next batch measurement). Stage-0 FFC chore last
> pulled **2026-07-30**, next due after 08-05.
>
> _(Session I's pointer, still the authority on Phase 17, follows.)_
>
> **★★★ Next-session pointer (2026-07-30, session 4 — T31 ☑ + SESSION I ☑.)**
>
> **State: 658 tests, ruff clean. Two commits this session, both LOCAL (not pushed).** T31 is
> `496836f`; Session I sits on top. The spent lockbox and the frozen value stack are untouched: T31
> changed only live-consensus boards (2022/23/24/**25** byte-identical) and Phase 17 is a config
> generalization whose default path is asserted unmoved (gate G3).
>
> **★ SESSION I ☑ — Phase 17 League-Format Fidelity (17.1–17.4).** All five gates PASS
> (`steps/phase17_formats.py`, `analysis/phase17_formats.json`); +41 tests in `tests/test_phase17.py`.
> Write-up: `findings.md` §"Session I", `PLAN.md` §2026-07-30 (session 4, cont.), `glossary.md`.
>
> | | |
> |---|---|
> | **17.1** | `RosterSlots.flex_groups()` is now the **single** fill-order rule — three solvers had each re-derived it. Multi-flex/superflex stays vectorized via **the carry** (sort a group's pool, take its top *n*, pass the unused tail to the next wider group). **Non-nested eligibility is REFUSED** (`assert_nested`), not approximated. |
> | **17.1 replacement** | **The superflex replacement level was quietly wrong**: the old proportional rule gave QB **1/6** of the slot. A superflex admits only QB beyond the base flex → **QB10 → QB20**; nothing else moves. Live 2026: best QB overall rank **15 → 3**. |
> | **17.2** | `SCORING_PRESETS` + `ruleset_from_preset` + `te_rec_bonus` + yardage-milestone bonuses. |
> | **17.3** | `LeagueSettings` (platform-agnostic; **not** Sleeper auto-import) + `lockbox_validated()`. Bracket now **4/6/8 with derived byes** — a 12-team/8-playoff league was previously unconstructible. Odd `n_teams` refused with a reason. |
> | **17.4** | Round-based keepers. `apply_keepers` + `DraftState.skipped_picks`: 147 picks, not 150. |
>
> **⚠ Do not re-derive / do not "fix":**
> - **Never add a third lineup solver, and never check one against another.** Both consume
>   `flex_groups()`, so agreement between them tests the plumbing. The gate is an **exhaustive brute
>   force** (worst abs error 0.0). *Two greedies that share a bug agree perfectly.*
> - **Keepers have no "ADP adjustment" and must not gain one** — ADP is a rank on the remaining
>   board, so removing the kept player *is* the re-inflation; a separate shift double-counts.
> - `ruleset_from_preset("full_ppr")` returns `RuleSet()` **itself**, name included, because
>   `RuleSet` is serialized into `cached_distribution`'s cache key — a cosmetic name difference
>   would split the cache and force a silent nine-season rebuild.
> - `OffenseRules` and friends are `extra="forbid"` (`_Rules`). That is the whole argument for a
>   bounded field set over an open `{stat: value}` map; the first implementation lacked it and
>   silently accepted `rec_typo=1.0`.
> - `starter_marginal` **routes multi-flex to the exact solver** rather than approximating with its
>   one-flex closed form. Leave it routing.
> - **`lockbox_validated()` is an honesty method, not a feature flag.** Non-default formats are
>   supported and correctness-tested and carry **no** out-of-sample claim. Phase 14 must render that.
>
> **★ Session I.5 = 16.17 the seat map ☑ DONE 2026-07-30** — see the pointer above. (Its bar-6
> instruction here was right about `--shuffle-room` and wrong about the reference being clean: the
> 07-29 sheet's `readout_2026` block had already moved with the board refresh, so the claim was
> settled by a pre-change control run instead.)
>
> _(T31's entry, still the authority on the level cap, follows.)_
>
> **★★★ Next-session pointer (2026-07-30, session 4 — T31 ☑ DONE. READ THIS FIRST.)**
>
> **Running order agreed with the user for this stretch: T31 → Session I (Phase 17) → hard stop →
> Session I.5 (16.17).** §3.7 gates waived *within* T31 and Session I; one commit per session, **not
> pushed**. Ten scope decisions were taken up front and are recorded in `PLAN.md` §2026-07-30
> (session 4) — 17.1 **nested-eligibility flex only** (non-nested refused at `LeagueSettings`),
> bracket **4/6/8 with derived byes** and **odd `n_teams` rejected**, 17.2 **presets + a bounded knob
> set** (not an open stat map), 17.4 **round-based keepers only**.
>
> **T31 ☑ — and the register's filed cause was WRONG, the third in a row after T13 and T24.** There
> is no live-vs-historical branch in the level fit: `train_seasons` is 2014–2022 for a **2024** board
> *and* a 2026 one, so the QuantReg models are **identical** and the defect was entirely in the
> **board**. Measured cause = **linear extrapolation far below the support of the fit** (median 2026
> QB `calibrated_mean` **11.4** vs a training *minimum* of 34.1; **56.4 %** of 2026 QBs below support
> against **2.3 %** on 2024), with the low end *additionally* selection-biased upward because the fit
> trains on `weeks >= 0.85*season`. Fixed by `quantile.consensus_level_cap` + four lines in
> `distribution.assemble_distribution`, gated on **`value_board.source`** (already a frozen 4.2
> contract column). **All six pre-registered bars PASS**: negative-haircut share **38.75 % → 0.00 %**,
> drafted-range rho **RB −0.288 → −0.666**, full-board **QB +0.474 → −0.980**, max `sd/proj`
> **23.06 → 0.90**, 2022/23/24/**25 bit-identical**, T17 band held (top-60 moved 0.078 %).
>
> **⚠ Do not re-derive / do not "fix":** the target is `proj_points * avail_p / g_ref`, **not** a bare
> cap at `proj_points` — the bare cap was built first, moved B1 to 8.1 % and pushed **full-board QB
> spearman the wrong way (+0.474 → +0.523)** by parking every capped row at `haircut == 0`. *Cap to
> the identity, not to the boundary.* · The scale is applied to `samples`, not to the quantile band ·
> `games` is deliberately unscaled · non-live rows multiply by **exactly 1.0**, which is what makes
> the bit-identity bar hold by construction · **the 2025 calibration holdout was authorised for one
> more read and then NOT spent** — the source gate leaves it bit-identical, verified by hash.
>
> **⚠ Method warning that outlives the ticket — a control that cannot fail.** The B5 before/after ran
> **post-fix code twice**: `uv run --project <main>` from a `git worktree` resolves the **editable**
> install to the *main* tree's `src`, and on the retry a persistent `cd` sent the working-tree run
> into the worktree. Both produced *identical hashes* — indistinguishable from "nothing moved".
> Use `PYTHONPATH=<worktree>/src`, and **assert the control can produce a known difference before
> trusting it to show none**. See `steps/t31_level_cap.py`'s docstring.
>
> **`ENRICH_VERSION` → `v4-t31-level-cap`**, so all nine 16.13 board caches rebuild (~35 min).
> Artifacts: `analysis/t31_level_cap.json`, `analysis/t31_hashes_{before,after}.json`. New steps:
> `t31_level_cap.py`, `t31_hash_distributions.py`, `t31_dump_summary.py`. Write-ups: `findings.md`
> §"T31", `docs/TECH-DEBT.md` T31 (☑), `PLAN.md`, `glossary.md`.
>
> **★ NEXT: Session I = Phase 17 formats**, then a hard stop, then Session I.5 = 16.17.

> **★ ☑ BUILT 2026-07-30 (Session I.5). Scoped 2026-07-30 (session 3, docs-only): 16.17 multi-seat human control.**
> User asked for the finished mock drafter to let a user **drive as many seats as they like** (e.g. 6
> personalities + 4 teams drafted by hand). **It was in none of the md files, and the gap is structural:**
> `DraftState.your_team` is a single int and the `team → seat` map is positional arithmetic repeated in
> three places (`personalities.make_room_pick_fn`, `mock.full_room_pick_fn`, `steps/mock_draft.py::seat_of`),
> correct only at k=1 — so the engine supports exactly two room shapes, 1-human and 0-human. Scoped as
> **16.17** (engine: a `SeatMap` + `DraftState.human_teams` + per-seat pick fns + `--seats` CLI;
> **done-bar = bit-identity** at k=1 and k=0 plus the 07-29 bar sheet to the digit) and **14.J** (UI: a
> YOU toggle per seat chip, clock routing, per-seat 14.I grade). Slotted as **Session I.5**, after Phase
> 17, **pullable into Session I as a warm-up** — it depends on nothing in Phase 17 and refits nothing.
> Spec: `docs/BUILD_PLAN.md` §16.17/§14.J · `docs/PLAYER-VIEW.md` §9.5 (and §9.1's `n_opponents`
> contract, which was wrong as written) · `ROADMAP.md` ★ SESSION PLAN · `PROJECT.md` §5 · `PLAN.md`
> §2026-07-30 (session 3) · `glossary.md`. **Two honesty rules travel with it:** k human teams in one
> draft are **one** observation (their picks deplete each other's pools — never aggregate a record
> across them), and the T15 realism bars describe a **fully-simulated** room.

> **★★★ Next-session pointer (2026-07-30, session 2 — SESSION H.5 COMPLETE. T27/T28/T29/T30 all ☑,
> **T31 opened**. 612 tests, ruff clean, UNCOMMITTED. READ THIS FIRST.)**
>
> **State:** **612 tests** (was 597), ruff clean. The spent lockbox, the frozen value stack and the
> fitted β are untouched — nothing here refits anything, and both bit-identity bars hold: the room bar
> sheet reproduces `analysis/mock_room_bars_verify_20260729.json` on **every field**, and the frozen
> cost report was diffed against a **`git worktree` at the session-start commit**. Artifacts:
> `analysis/session_h5_seam.json` (the six bars), `analysis/t28_starter_value.{json,csv}`,
> `analysis/mock_room_bars_{h5_baseline,h5_step1,t30_chalk_swap,t28_benchw0}.json`. New steps:
> `steps/t28_starter_value.py`, `steps/session_h5_seam.py`. Write-ups: `findings.md` §"Session H.5",
> `docs/TECH-DEBT.md` (T27–T30 ☑ + **T31**), `PLAN.md` §2026-07-30 (session 2), `glossary.md`, `ROADMAP.md`.
>
> **The shape of the session: the two hard bars held and both falsifiable bars failed.**
>
> | | outcome |
> |---|---|
> | **T27** ☑ | The value chain is on the board (`PROJ · MEAN · AVAIL · BV`) and `mock_draft.py why "<player>"` prints it — Maye +68.5 vs Daniels −101.6 explained by **14.4 games against 7.7**. ⚠ **It also uncovered that the *interactive* room was never the shipped room**: `personalities.make_room_pick_fn` had no `risk` parameter, so `value_hawk` ran the Phase-9 greedy in every batch measurement and the plain behavioural softmax in every *human* mock. `assert_room_objectives` moved down into `personalities.py` so both builders share it. |
> | **T28** ☑ | **Closed as a LABELLING FIX, as pre-registered.** `starter_value` ships beside `team_value`, both printed. **B5 failed**: −0.0230, CI[−0.0407, −0.0055] over 200 seated-reshuffled drafts. The slot-blind sum is the *better* predictor of title probability because the sim draws injuries — **bench value alone scores +0.711, positive in 100 % of drafts**, and the blend sweep peaks at w=0.90 against the shipped w=1.0. `value_hawk` keeps `objective="portfolio_ce"`. |
> | **T29** ☑ | `PROB_PROVENANCE` + `fair_share`/`playoff_fair_share` + `assert_probability_sums`; every driver leads with the multiple (0.170 → **1.70×**). New surface: `mock_draft.py summary --odds`. |
> | **T30** ☑ | **Argued and deliberately NOT changed.** The `chalk` swap closes **79 %** of the chalk-share gap (11.0 → 2.4 % vs a realized 0.2 %) and regresses two reach bars slightly; the rule ("every bar holds or improves") was fixed first, so it does not ship. **The closest call in the session** — reversal is one `--room` flag and the evidence is written down. |
> | **T31** 🟠 NEW | T27's gate B2 fired: on a **live** board the level correction inverts for players consensus projects as backups — **22.8 % of the 2026 value index has `mean` ABOVE `proj_points`** (0.4 % on 2024). Cause: **consensus prices ROLE, our correction prices AVAILABILITY**; they agree for starters and diverge for backups, and a live season has no prior year to shrink the per-game level toward. The gate ships **red** rather than softened. |
>
> **⚠ Do not re-derive / do not "fix":** `value_hawk`'s objective is **settled by measurement** — do not
> switch it to starter-aware without re-running `steps/t28_starter_value.py` and beating B5 · the
> `bench_weight` knob is in `RiskModel`, default **1.0**, and 1.0 re-runs the greedy pick-for-pick
> (`test_phase9`) · `mean`/`vbd`/`overall_rank` stay in `SIGNAL_COLS` (it is also the typo registry) but
> `personalities.LEVEL_COLS` + `Personality.__post_init__` now make weighting one raise · the T30 swap
> is a *composition* question, never delete the `autopilot` personality (it is the deterministic control
> several tests depend on).
>
> **★ NEXT: review + commit (this session sits on top of the still-uncommitted docs tree), then
> Session I = Phase 17 formats.** Against the mock drafter only **T31** is open, and it needs its own
> session with a before/after against the 2025 dress-rehearsal calibration. **T26** still waits on the
> next 11.1 refit. Stage-0 FFC chore was run at the **close** of this session (deliberately not the
> start — a mid-session board refresh would have broken the live-board measurements).
>
> _(Prior pointer — the H.5 scoping session, still the authority on why these four tickets exist.)_
>
> **★★★ (2026-07-30 — SESSION H.5 SCOPED, docs-only; T27/T28/T29/T30 opened.)**
>
> **State:** **docs-only, no `src/` change, no test-count change (597, ruff clean).** The lockbox, the
> frozen value stack and the fitted β are untouched. New artifacts: the walkthrough itself at
> `analysis/mock_walkthrough_20260729_{picks,teams,seats}.csv` (untracked). Write-ups: `findings.md`
> §"The all-personality walkthrough (2026-07-30)", `docs/TECH-DEBT.md` **T27–T30** + ordering item 11,
> **`docs/BUILD_PLAN.md` §"Session H.5 — THE MOCK-DRAFTER VALUE SEAM" (the plan of record)**,
> `ROADMAP.md` ★ SESSION PLAN, `PLAN.md` §2026-07-30, `glossary.md`.
>
> **What happened.** The user asked for a full 15-round mock with **all ten seats played by
> personalities** (`REALISTIC_ROOM`, `room_seed=17`, `seed=0`, live 2026 board) and then for an
> assessment of the mock drafter **as a shippable product**. The room *simulation* passed every bar it
> was asked — see below — and the failures are all in the **seam between a correct engine and a human
> reading it**. User instruction: **fix the mock-drafting system before any other session; the app
> stays strictly last.** So Session H.5 is inserted ahead of Session I; E→L order is otherwise unchanged.
>
> | | ticket | the number that opened it |
> |---|---|---|
> | **T27** 🟠 | the board a human reads ≠ the board the seats optimize | CLI prints `proj_points`; seats optimize `base_value`. **Drake Maye proj 316.5 → +68.5, Jayden Daniels proj 313.4 → −101.6** — 3 points apart on screen, 170 apart in the number that decides every pick |
> | **T28** 🟠 | `team_value`/`portfolio_value` are **slot-blind** | no slot logic in the value path at all; the walkthrough's QB2 line nets **−122** of a 1,938 room total, and **T4 is 9th of 10 on VBD, 3rd on starting-lineup projection**. Spearman vs title: portfolio CE **+0.758** vs starting-nine Phase-5 mean **+0.915** |
> | **T29** 🟡 | bare absolute probabilities | printed from a sim with a documented **−113 pts/team** level bias and a *marginal* playoff Brier 0.240 (title 0.088 is fine) |
> | **T30** 🟡 | `autopilot` is 1 of 10 seats vs **0.2 %** of real seats | and it is the seat that manufactures the spill: mean `pool_rank` **1.77**, median **1.0**, harvest **+11.7 picks** |
>
> **★★ THE FINDING TO CARRY FORWARD — T22's lesson one level up, on the first number a human reads.**
> T22 sat on file as "latent, no personality weights it" while `steps/mock_draft.py` was *printing* it.
> `proj_points` is the identical defect on a much bigger number. *A column's consumers are not only the
> models that weight it.* Its mechanical half bit immediately: `proj_points` is **not** in
> `simulator.PASSTHROUGH_COLS`, so `_prepare_board` drops it and a **fresh driver written this session
> printed `-` for all 150 picks**. `mock_draft.cmd_start` already re-attaches it by hand — the fix is to
> make the attach unnecessary, not to repair the CLI.
>
> **★ Two more, each one line.** **(1) Decompose before diagnosing** — `base_value` differs from `vbd`
> through *two* channels (the T3 availability haircut inside the Phase-5 mean, then λ·Var, then
> subtracting the replacement's own CE, 119.4 for QB here). The one-channel reading "λ is too big" fits
> neither end: Allen +70.0 → +55.2 while Daniels +22.6 → −101.6. **(2) The level is intended, the
> dispersion is the defect** — the mean haircut (0.28 QB / 0.33 RB / 0.28 WR / 0.30 TE) *is* Phase 4.4's
> calibrated level correction; the spread around it (QB 0.15–0.56) with nothing on screen explaining it
> is what makes the board unreadable.
>
> **★ What the walkthrough CLEARED, and do not re-open** — four suspicions that died on contact with
> the corpus, each in one query: **the QB market is fine** (17 QBs for 10 teams against a realized
> **median of 16** over 333 matched 10-team/15-round human drafts; the full mix matches at the median on
> all six positions) · **the fit is not stale** (70,614 groups over **9 seasons**, bulk 2021–25, not a
> 2017–20 extrapolation) · **elite fall is on distribution** (25.0 % past pick 10 vs a committed 25.2 %)
> · **the reach budget works exactly as specified** (`reacher` spent 3 of 3 swings and 5 of 5 leans with
> a rounds-1–3 max reach of **−0.1**; `upside_chaser`, which has no early clamp, reached +11.3 in round
> 2). *An audit's value is in what it clears.*
>
> **⚠ Constraints on H.5, all pre-registered in `BUILD_PLAN.md` before anything runs:** every step's
> hard bar is that `analysis/mock_room_bars_verify_20260729.json` reproduces **bit-identically** — *a
> display change that moves a bar is not a display change* · **nothing refits β** and **nothing touches
> the frozen value stack**; T26 stays deferred to the next 11.1 refit · **T28 ships a labelled second
> metric, never an edit to `team_value`** (the cost report is frozen output, the lockbox is spent) ·
> **§3.7 gates are NOT waived** (contrast 16.14R) — step 2 contains a decision that is the user's:
> whether `value_hawk` keeps `objective="portfolio_ce"`, which changes the room's picks and therefore
> needs the full T24 seating-marginalized treatment as its own sub-step · **B2 and B5 can fail
> informatively** — if the level haircut is not explained by `games_played_mean` that is a *modelling*
> finding (stop, open a ticket, do not caption it), and if starter-aware value does not out-rank
> portfolio CE against title probability over ≥40 drafts × ≥4 seasons then **T28 closes as a labelling
> fix only**.
>
> **★ NEXT: Session H.5, steps 1→5, gate after each** (`docs/BUILD_PLAN.md` §"Session H.5"). Then
> Session I = Phase 17 formats → J (optional dynasty) → **K = Phase 14.1 MVP + surfacing, strictly
> last**. **Stage-0 FFC chore: the board used here is the 2026-07-24 snapshot and is now at the 6-day
> mark — run `steps/stage0_adp_snapshot.py` then `steps/backup_db.py` at the top of H.5.** Also still
> owed: review + commit sessions 6, 7 and 2026-07-29 (one tree) plus these docs.
>
> _(Prior pointer — the 2026-07-29 completion audit, still the authority on T13/T18/T22.)_
>
> **★★★ (2026-07-29 — THE MOCK DRAFTER IS COMPLETE. T13 + T18 + T22 ☑,
> T26 opened. NOT COMMITTED — sessions 6, 7 and this one are one tree.)**
>
> **State:** **597 tests** (was 587), ruff clean. The lockbox, the frozen value stack and the fitted
> β are untouched — nothing here refits anything. New artifacts:
> `analysis/mock_room_bars_verify_20260729.json` (the shipped room re-measured) and
> `analysis/t13_reproducibility.json`. New step `steps/t13_reproducibility.py`. Write-ups:
> `findings.md` §"The mock-drafter completion audit (2026-07-29)", `docs/TECH-DEBT.md`
> T13/T18/T22 ☑ + **T26**, `PLAN.md` §2026-07-29, `glossary.md`.
>
> **The mock-draft arc was already done** — T15 steps 0–4, 16.14R's seven steps, T23/T25/T24 — and
> re-measuring it confirmed that: all five T15 bars, the landing gate and the legality report come
> back **unchanged to the digit** (distance 0.0894, round-1 2.64, elite past-10 25.24 %, dispersion
> −11.4 %, top-band past-pick-4 15.3 % vs a realized 13.1 %). ⚠ The register's at-a-glance table had
> been carrying **T15 as open** while its own section was ☑ since 07-27; that row is corrected. What
> was genuinely unfinished were the three entries *behind* the room, each of which reaches the board
> a human drafts from:
>
> | | was on file as | what it actually was |
> |---|---|---|
> | **T22** | "latent — no personality weights it" | **already on screen**: `steps/mock_draft.py` prints BOOM/BUST, so the live 2026 board told the user Bijan Robinson and Puka Nacua *never boom* (0.000 — neither played in 2022, where `max(train_seasons)` lands). Fixed read-only in the enrichment: `boom_prob_live`/`bust_prob_live` from season − 1, `NaN` where unseen, `volatility_source` asserting ≤ 1 season of lag. Exact-zero `bust_prob` **56.0 % → 8.2 %**; **corr(frozen, live) = 0.026** |
> | **T13** | "prime suspect: the Iman–Conover coupling" | **DuckDB's parallel float aggregation.** Row order, `PYTHONHASHSEED` and BLAS threads were all ruled out first; pinning DuckDB to one thread makes the cloud **bit-identical** across processes. `db.deterministic_reads`; cost **negative** (10.2 s → 9.1 s) |
> | **T18** | "+91.9-pick mean QB reach — a board mismatch" | correct, and worse than stated: fixing the reference **reverses the sign** (QBs go −0.58 rounds *later*). Column deleted, not repaired: `avg_reach_rounds` + `n_reach_picks` from `redraft_reach`, mean \|reach\| **35.8 picks → 0.776 rounds**, ±2-round health gate |
>
> **★★ The three carry-forward lessons** (all in `glossary.md`): **(1) a column's consumers are not
> only the models that weight it** — T22 was audited by grepping `signal_weights` and the display
> layer was never looked at. **(2) The noisy stage is not always the stochastic one** — every T13
> hypothesis on file involved randomness; the cause was arithmetic in a database, and the
> prescription on file (*thread a seed through the coupling*) would have been built, tested, and
> would not have worked. **(3) When the sign flips, it was never a behaviour** — T18's magnitude
> falling was suggestive; its *direction reversing* is what proved the old number was a different
> quantity wearing a behaviour's name.
>
> **⚠ Do not re-derive / do not "fix":** the coupling is **not** T13's cause, whatever the
> "marginals invariant, assignment moves" fingerprint suggests · **T26** (`pos_share_*` pooled across
> formats, read by `mgr_lean`) is **measured and deliberately deferred** — fixing it refits β and
> moves every T15/T24 width bar for a 0.83 pp feature shift; do it with the next 11.1 refit ·
> `build_tendencies`'s `avg_reach` keeps the T18 defect by design (labelled POC; use `redraft_reach`)
> · `app/streamlit_app.py`'s season selector is DEV-only — Phase-14 work, noted not fixed.
>   **(RESOLVED 2026-07-30, Session K1: that file is deleted; `app/main.py` defaults to the
>   live season and lists every boarded season.)**
>
> **★ NEXT: review + commit (sessions 6 + 7 + this one, one tree), then Session I = Phase 17
> formats.** No register entry is open against the mock drafter. **Stage-0 FFC chore: last pulled
> 2026-07-24, DUE after 07-30** — run `steps/stage0_adp_snapshot.py` then `steps/backup_db.py`.
>
> _(Prior pointer — session 7, T23/T25/T24 as they were built.)_
>
> **★★★ (2026-07-28 session 7 — T23 + T25 + T24 all ☑ BUILT. The mock room is
> fixed; T24's own prescription was rejected on the way.)**
>
> **State:** 596 tests (was 577), ruff clean, **UNCOMMITTED** together with sessions 6's docs. DEV-only;
> the spent lockbox and the frozen value stack are untouched (`draft/availability.py` imports nothing
> from `personalities`, so the 11.2 Brier is **bit-identical**: +0.0890, CI [+0.0803, +0.0996]).
> Artifacts: `analysis/mock_room_bars_{baseline,t23,t25,t24,baseline_shuffled,t24_shuffled}.json`
> (+ the rejected `t24_kappa2{,_shuffled}`) and `analysis/mock_t24_sweep{,_rep,_full,_shuffled,
> _shuffled2,_shuffled3}.json`. Write-ups: `findings.md` §"T23 / T25 / T24 (2026-07-28, session 7)",
> `docs/TECH-DEBT.md` T23/T24/T25 (all ☑), `PLAN.md` §2026-07-28 (session 7), `glossary.md`.
>
> | | result |
> |---|---|
> | **T23** | `mandatory_needs` = `base_demand()`. Seats unable to fill a dedicated slot **23.2 % → 12.3 %**; the *avoidable* half **12.08 % → 0.03 %**. No T15 bar moved (verified). |
> | **T25** | `ROOM_CEILING` — `reach_budget=None` now means *inherit*. `balanced` R1–3 `pool_rank` 6.36 → 5.98; median `pool_rank` 9.31 → **8.85** (corpus 7.62); moderate share 28.8 → **32.7 %**. |
> | **T24** | Elite (ADP ≤ 2.5) past pick 4 **25.8 % → 15.3 %** (realized 13.1 %); bar 2 p95/past-10 17.0/28.8 % → **16.0/25.2 %**; bar 1 distance 0.107 → **0.089**; median `pool_rank` 8.69 → **8.04** (corpus 7.62); moderate share 33.7 → **38.2 %**. Cost: bar 5 dispersion −7.1 → **−11.4 %**. All five T15 bars + the new landing gate PASS. |
>
> **★★ THE FINDING — T24's prescription was built and REJECTED; the fix was the knob added to
> support it.** The per-seat `adp_stdev`-scaled **private board** is *monotonically harmful* on the
> objection it was designed for (18.8 / 19.7 / **26.6 %** at κ = 0/1/2). **At the top of the board
> `adp_stdev` (0.7–2.5) is the same size as the gaps it perturbs (~0.2 picks), so the draw destroys
> the ordering that was already there** — which is exactly how an elite falls. The corpus law behind
> the idea (`|drift| ≈ 2 × adp_stdev`) is about **realized** drift, an outcome of ten seats
> interacting; re-injecting it as a **per-seat perception** is a different object. *A relationship
> measured on outcomes is not a specification for the mechanism that produced them.* Kept in code,
> **default-off**, verdict written onto `analysis/phase11_opponent_model.json` next to κ. **What
> worked: `WidthCurve` gained `base`**, splitting the width *level* from the *shape*
> (`width = base·round^gamma`); `base 1.0·γ0.8 → 0.6·γ1.0` halves round 1 while keeping 86 % of the
> round-15 width. **Round 1 was simply too wide — the ticket had the right symptom and the wrong cause.**
>
> **★ Three method failures, in the order they were caught — each by the next measurement:**
> (1) **calibrated on a 4-season subsample** and shipped off it; the 8-season sweep failed that config
> (20.4 % vs an 18.1 % ceiling). (2) **Measured on one fixed seating**, which flatters by 5–7 pp
> (`0.5/1.0/2.0`: 16.2 % fixed vs **23.4 %** marginalized) — and ⚠ **more seeds do not fix it**, the
> seating error is a *bias* until the seating is redrawn (`--shuffle-room`). (3) **Moved two knobs
> together**, so the narrowing wore the private board's credit for three runs; the isolating row
> (`base 0.7, κ 0`) was in no grid and is what decided the ticket.
>
> **⚠ Do not re-derive:** the private board is **not a null, it is harmful** — do not switch κ on
> without re-running the seating-marginalized sweep · `ceiling_saturation` was a **wrong** hypothesis
> (1.5–2.3 % at every κ; the diagnostic is kept as a standing check) · the **round-1 half-split is
> unresolvable** at this n (0.54 / 0.82 / 1.11 / 1.22 for the same room) — use the landing **share**
> (n ≈ 640) as the bar, the rise as a diagnostic · `base` below 0.5 fails bar 5 (`0.35/1.1`: 9.4 %
> past-4 but **−20.3 %** dispersion) · **`base 0.5` was shipped and then withdrawn** — it passes the
> same gates but overshoots to *tighter than real humans* (11.3 % past-4) at 0.154 distance and
> −17.4 % dispersion; the un-sampled midpoint 0.6 beats it on every secondary. **A sweep whose winner
> sits at the edge of the grid has not finished.** The residual cost at 0.6 is dispersion −7.1 % →
> **−11.4 %** — that is the trade, do not tune it away without re-measuring.
>
> **★ NEXT: review + commit (sessions 6 + 7 in one tree), then Session I = Phase 17 formats.** The
> residual elite-fall gap (15.3 % vs 13.1 %) is closed; if it is ever reopened, the surgical fix is a
> steeper `AdpSpec.exponent` with `base`/`gamma` restoring depth width — which **refits β**
> (`steps/t15_1_respecify.py`), not an artifact edit. Stage-0 FFC chore last pulled **2026-07-24**
> (verified in-DB), next due after 07-30.
>
> _(Prior pointer — session 6, the three objections as they were opened.)_
>
> **★★★ (2026-07-28 session 6 — the 2×5 mock re-run. T23/T24/T25 opened,
> NOTHING BUILT, at the rule-7 gate.)**
>
> **State:** **docs-only, no `src/` change.** One new read-only driver, `steps/mock_2x5_diag.py`
> (ruff clean, untracked); five docs edited. **16.14R and everything before it is committed at
> `7c13402`** — the prior pointer's "NOT COMMITTED" was stale, the tree was clean on arrival.
> Writeups: `findings.md` §"The 2×5 mock re-run (2026-07-28)", `docs/TECH-DEBT.md` **T23/T24/T25**,
> `PLAN.md` §2026-07-28 (session 6), `glossary.md`. DEV-only; nothing written to `analysis/`.
>
> **What happened.** The 2×5 room re-run with the *shipped* `value_hawk` — one showcased draft (room
> seed 20260728, draft seed 728) plus **40 seeded drafts, room reshuffled per seed**. The user read
> the picks by eye and raised **three** objections. All three hold.
>
> | | ticket | what it is | cost |
> |---|---|---|---|
> | 1 | **🔴 T23** | `mandatory_needs` drops TE because TE ∈ `flex_positions` → **12.2 % of seats finish with no TE** (46 % of `autopilot`). Bug against a stated contract. | ~5 lines |
> | 2 | **🟡 T25** | `ReachBudget` is on 2 of 10 seat types, so the round ceiling binds `reacher`/`value_hawk` and **not `balanced`** (4 of 10 seats in `REALISTIC_ROOM`). | small |
> | 3 | **🟠 T24** | Width is per-**round**, never per-**player**; the board's `adp_stdev` is **unread in the pick path**. Consensus #2 lands at a **median pick of 4**. | a full sub-step |
>
> **★ RESUME HERE: the user was asked to choose 1→2 first, or straight at 3. No answer yet.** T23 and
> T25 are contained and re-measurable in one pass; T24 moves T15 bars 1/2/5 and the seat-faithfulness
> population, so it needs its own gated sub-step with a before/after on the shipped measurement path.
>
> **★★ THE FINDING TO CARRY FORWARD — an aggregate that pools reaches and falls cannot see a
> one-sided defect.** Round-1 mean |reach| is **2.91 sim vs 2.87 corpus** — the bar **passes** —
> while Gibbs (ADP 1.8) lands at a **median pick of 4** and clears pick 4 **42 %** of the time against
> a realized **12 %**. A reach and a fall have the same absolute value and cancel inside the mean.
> This is T15's *"an aggregate metric cannot see an impossible event"* one level down: there the
> aggregation was over **drafts**, here it is over **direction**, inside a metric that already passes.
> **Bars over |drift| need a signed companion — here, a landing-spot distribution for the consensus
> top tier.**
>
> **★ The mechanism T24 proposes, and why it is ONE object for THREE open problems.** A **per-seat
> private board**, `adp_seat = adp + κ_seat · adp_stdev · ε`, drawn once per seat per draft. Measured
> basis, on 1,144 corpus drafts: **|drift| ≈ 2 × adp_stdev** (stable through the usable range; the
> decay above stdev 12 is pool exhaustion, T15's own finding arriving independently);
> Spearman(`adp_stdev`, |drift|) **0.484** vs Spearman(round, |drift|) **0.535**; and **within rounds
> 1–3 the stdev terciles drift 2.11 / 3.33 / 8.91** — a 4.2× spread no round-indexed curve can
> express. It buys (a) round-1 tier structure without hard-coding a tier, (b) **the T15 carry-forward
> verbatim** — *"needs per-seat board perturbation, not another width parameter"* (plausible,
> **untested**), (c) the only direction channel that is **live in round 1** for `reacher`.
> ⚠ **`adp_stdev` is on the board and nothing in `draft/` reads it** — `stdev` appears only at
> `mock.py:301`, copied onto the *output* panel. 16.8 already measured it as a drift driver
> (+0.35/SD). *The finding existed in this repo and was never fed back into the room.*
>
> **★ Second lesson — a bar written from the symptom passes the general defect.** T20's done-bar was
> *"60/60 seats finish with ≥1 K and ≥1 DST"*, the two positions the ticket was about. It passed while
> the same deadline filter left **TE** unguarded. State a guarantee's bar against the whole contract.
>
> **⚠ Do not re-derive these dead ends:** the `reacher`'s rounds-1–3 quiet is **the user's own
> 2026-07-27 spec** (`early_rounds=3`, `early_max_picks=8.0`, `large_from_round=5`) and is **not** to
> be "fixed" — the defect is that `balanced` has no equivalent constraint (T25) · do **not** raise the
> reacher's `temperature`/`width_mult` early (its `cos`/`rookie`/`upside`/hype channels are
> structurally dead at the top of the board — that is the *"width with no direction"* 16.14R step 5
> deleted) · do **not** narrow round 1 with another global width parameter (one knob cannot set both
> ends; the round-1 problem is *within-round* heterogeneity) · do **not** read a behavioural ordering
> off one draft — over 40 drafts `reacher` **does** out-reach `balanced` (`pool_rank` 13.40 vs 11.74);
> the inversion is real only in **R1–3** · the corpus far tail (p99 = pick 33 for an ADP 1–2.5 player)
> is a **data question first** — check `days_to_board` and keeper/dynasty leakage before fitting it.
>
> **★ Reporting rule adopted:** the per-personality summary leads with **`pool_rank`, split R1–13 /
> R14–15**, not a 15-round mean reach — which is dominated by late-board ADP noise (Tyler Allgeier at
> ADP 167 taken at pick 119 scores **+48** and means nothing) and by *when* a seat takes K/DST.
> **Mis-reporting it this way is what produced objection 3 in the first place.**
>
> _(Prior pointer — 16.14R's own closeout, still the authority on the seven steps and the T15 bars.)_
>
> **★★★ (2026-07-28 — ★ 16.14R COMPLETE, all seven steps. T19/T20/T21 ☑,
> T22 opened. NOT COMMITTED.)**
>
> **State:** **569 tests** (was 549), ruff clean, **UNCOMMITTED** together with the prior docs-only
> sessions. New steps `steps/phase16_14r_{2..7}_*.py` + `phase16_14r_signal_report.py`; artifacts
> `analysis/phase16_14r_{floor,context,safe_floor,reacher,value_hawk,room,signal_report,brier}.json`
> + **`analysis/mock_16_14R_picks.csv`** (a full 15-round mock, for your eye) +
> `analysis/t19_signals.csv`. DEV-only; the spent lockbox and the frozen value stack are untouched.
>
> **What ran.** The seven-step execution order, straight through under a **waived §3.7 gate** (your
> instruction), with eight decisions taken up front (`PLAN.md` §2026-07-27/28). Step 1 roster
> legality + K/DST · 2 the `floor` repair · 3 the three blind spots · 4 `safe_floor` · 5 `reacher` ·
> 6 `value_hawk` · 7 composition + re-measure.
>
> | bar | T15 shipped | 16.14R | |
> |---|---|---|---|
> | 1 profile distance · round-1 | 0.2220 · 4.36 | **0.1156 · 3.70** | PASS |
> | 2 elite p95 · past pick 10 | 17.0 · 28.5 % | 19.0 · **30.07 %** | **marginal FAIL** |
> | 3 worst harvest excess | +0.21 sd | **+0.06 sd** | PASS |
> | 4 11.2 Brier | +0.0890 | **+0.0890** | PASS, unchanged |
> | 5 dispersion error | +17.0 % | **+5.6 %** | PASS |
> | seat faithfulness | 10.40 · 13.5 % · 19.6 % | **9.38 · 27.8 % · 10.6 %** | corpus 7.62 · 54.3 % · 0.2 % |
>
> **★ Bar 2 is a marginal miss and is deliberately NOT tuned into a pass.** 30.07 % vs a 30.0 %
> ceiling on n = 5,700, binomial se 0.61 pp ⇒ **+0.12 se**, i.e. indistinguishable; the p95 half
> passes (19.0 ≤ 20.0) and the **2026 live board passes outright at 26.3 %**. The direction is a
> real trade, **measured** (same code, 2021–24, 40 seeds, only the mix differing): the T15 room
> scores 28.72 % and the shipped room 29.47 %, so composition costs **+0.75 pp** while profile
> distance falls 0.118 → **0.093**, dispersion +10.4 % → **+6.5 %** and chalk 19.9 % → **10.7 %**.
> That difference is itself +0.51 se, so the attribution gives the *direction and the trade*, not a
> magnitude. **Decide explicitly whether to accept it or re-add a chalkier seat — do not reweight a
> personality until the number crosses.**
>
> **★★ THE FINDING TO CARRY FORWARD — the problem was the SCALE, not the fit.** T19 framed itself as
> *"OLS is the wrong likelihood for a censored variable"*, and **both** repairs that framing admits
> failed: a censored-normal Tobit left a **100 %**-deep top-10 floor list, and a distribution-free
> neighbourhood rank flipped `corr(upside, floor)` to **+0.94 QB** — 16.14's original defect,
> restored, while passing T19's one-sided bar cleanly. A variable that piles up on a boundary of its
> own support has no well-behaved residual however it is fitted. Rebuilding the signals as **ratios
> to the projected level** (`shape_inputs`) puts a censored player at the *bottom* of a bounded
> quantity, which is the honest reading, and only then does an estimator pass. *Before choosing an
> estimator, check the variable is on a scale the estimator can be right about.*
>
> **★ Three more, each one line:**
> 1. **A one-sided bar is passed by the same defect in the other direction.** Selection now requires
>    T19's bar **and** 16.14's oppositions. That check is the only thing that rejected `rank` on raw
>    quantiles.
> 2. **`boom_prob`/`bust_prob` are four seasons stale on any live board (T22, new 🟡)** — they read
>    `max(train_seasons)` and `train_seasons` for a live season is `DEV_SEASONS`, ending **2022**.
>    **292 of 306 zeros are `fillna(0.0)`**, i.e. a player absent in 2022 reads as *never busts*: a
>    fabricated safety claim, worst for exactly the rookies a floor-seeker should distrust. Frozen
>    contract → logged, not edited; both seats now weight `tail_risk`. Same `max(train_seasons)`
>    idiom as T17 — **a sweep for the pattern is probably worth more than either fix.**
> 3. **`floor` is not what fixed the objected picks — `tail_risk` is.** Zay Flowers went *up* the
>    floor percentile (0.76 → 0.85). The objection was about **width**, and width is not floor:
>    Johnston 0.85 / Blue 0.84 / Metcalf 0.76 on `tail_risk`. T19 repaired the input to "highest
>    floor"; step 4 changed the objective to "lowest downside". Both were needed.
>
> **⚠ Do not re-derive these dead ends** (all kept runnable, `PLAN.md` has the list): Tobit ·
> neighbourhood rank on raw quantiles · `rank_delta` · a **pool-relative** `level_floor` (measured
> inert — inside a 40-player band the worst candidate is z ≈ −1.5 whoever he is) · a rounds-derived
> corpus reach ceiling (wrong by **6×**; the panel carries its own `round`, and `reach_profile`
> pools |drift| so its round-15 p90 is mostly players *falling*) · picking the value-hawk window by
> argmax (the sweep is inside its own noise, **+13.1 CE vs a pooled se of 10.7** → the tightest
> window ships).
>
> **★ NEXT:** review + commit (7 steps' worth, one working tree). Then **Session I = Phase 17
> League-Format Fidelity 17.1–17.4**, then J (optional dynasty) → **K = Phase 14.1 MVP + surfacing,
> strictly last**. Stage-0 FFC chore: last pull **2026-07-24**, next due after 07-30.
>
> _(Prior pointer — the 2×5 mock that opened 16.14R, still the authority on why the order changed.)_
>
> **★★ (2026-07-27 session 5 — 16.14R RE-ORDERED, `docs/BUILD_PLAN.md` §"16.14R — THE EXECUTION ORDER".)**
>
> **State:** no code changed this session. Docs only: `docs/BUILD_PLAN.md` §16.14R execution order
> (the 7-step plan of record), `docs/TECH-DEBT.md` **T19/T20/T21**, `findings.md` §"The 2×5 mock
> room", `PLAN.md` §2026-07-27 (session 5), `glossary.md`. T15 remains COMPLETE (steps 0–4 ☑, five
> bars PASS). The mock itself was a DEV run — driver + CSVs in the session scratchpad, nothing
> written to `analysis/`.
>
> **What happened.** A full 15-round mock with **2 seats each of autopilot / value_hawk / safe_floor /
> reacher / balanced**, plus 60 seeded drafts of the same mix. The T15 fix holds on the live board
> (round-1 reach **12.31 → 4.58** picks, elite-fall p95 **30.0 → 17.0** vs a corpus 17.5, profile
> distance r1–6 **0.713 → 0.244**). Then **the user reviewed all 150 picks by eye and raised three
> seat-level objections — and two of them are defects in the *signals* 16.14R was going to build on
> top of.** Hence the re-order.
>
> **★★ THE FINDING TO CARRY FORWARD — the fix for a level-vs-shape defect created the next one.**
> `safe_floor` drafts boom-or-bust players because **`q10` is censored at exactly 0 for 42.9 % of
> offensive board rows** (59.0 % past ADP 100). `residual_shape` regresses it on `mean`, so the
> largest positive residuals go to players just above the censoring point and
> **`corr(floor, adp)` = +0.179 RB / +0.124 WR** — the *safety* signal prefers *deeper* players. The
> board's safest RBs are Jonah Coleman (ADP 171) and Jaydon Blue (ADP 140). **The seat drafted exactly
> what the board told it was safest.** Fourth member of the family (`q90`/`q10` 16.14 ·
> `games_played_mean` T17 · `vbd` · **`floor`**) and the first **self-inflicted** one: 16.14
> residualized to remove a level proxy and produced a *depth* proxy, because removing the level from a
> censored variable leaves something anti-correlated with quality rather than orthogonal to it.
> *A residualization is a modelling assumption about the tail.* **T19.**
>
> **★ Three more things, each a one-line diagnosis:**
> 1. **The `reacher` has width with no direction — literally.** It is
>    `Personality("reacher", temperature=2.2, width_mult=WIDTH_REACHER)`, **no `signal_weights` at
>    all**. Mean `pool_rank` 20.5 vs a corpus p90 of 13.1. Give it direction (rookies · 16.10 hype ·
>    the 16.9 shock, all already assigned to it) **before** applying the user's reach budget — a
>    budget over directed reaching is a different object from a budget over noise.
> 2. **The value hawk's bad picks are blind spots, not mis-weights.** Signed situation, committee
>    share and TD-regression are **not on the 16.13 board** (`cos` exists but is **unsigned** —
>    Rachaad White 1.0, DK Metcalf 0.6). No objective over today's board avoids those picks ⇒ board
>    scope moves first (open decision #3, settled). Separately: `pos_z(vbd)` deletes VBD's only
>    non-ADP content (`corr(vbd, adp)` within position −0.86…−0.96), so a `signal_weights` value hawk
>    **cannot** work ⇒ objective is **portfolio CE** (open decision #1, settled, measured).
> 3. **K/DST — a filter, not a data gap.** `adp_snapshots` has the defenses (60 `DEF` rows, 2026 FFC
>    PPR 10-team); `_ffc_board`'s `gsis_id IS NOT NULL` drops them because they key on
>    `ffc_player_id`, and `board_player_key`/`canon_pos`/`DRAFTABLE` already support DST. **T20.**
>    Found alongside it: **K is in the sim's candidate band but not the fit's** (`skill_only=True`) —
>    Session-G choice-set violation, second home. **T21**, must land with T20.
>
> **★ NEXT = 16.14R Step 1** (roster legality + the K/DST guarantee — user instruction: ≥1 K and ≥1
> DST per seat whenever `rounds >= slots.starters`). Then Step 2 **repair `floor` before any
> personality consumes it**, Step 3 board scope, Step 4 safe_floor, Step 5 reacher, Step 6 value hawk,
> Step 7 composition + re-measure. **Gate after each** (rule 7). Full text: `docs/BUILD_PLAN.md`.
>
> **⚠ Do not re-derive these:** `autopilot` won **48.3 %** of 60 drafts at mean finish 1.69/10 ⇒ the
> default room drops to ≤1 autopilot (Step 7). Composition **alone** moved T15's open faithfulness gap
> from median `pool_rank` 10.40 → **8.59** (corpus 7.62) with no model change. The late-round 0.61×
> narrowness is **unchanged and expected** — it needs per-seat board perturbation, not another width
> parameter. Dead end: rookies do **not** reach `pos_z` as NaN (0 of 31 on the 2026 board) — that was
> the first, wrong, hypothesis for T19.
>
> _(Prior pointer — T15's own closeout, still the authority on the T15 bars.)_
>
> **★★ (2026-07-27, ★ T15 COMPLETE — steps 0–4 ☑, all five bars PASS. NEXT was 16.14R.)**
>
> **State:** **549 tests**, ruff clean, **UNCOMMITTED** (user's choice) together with the three prior
> docs-only sessions. New: `draft/mock.py`, `steps/t15_{0,1,2,3,4}_*.py`, `steps/mock_draft.py`,
> `tests/test_mock.py`. Artifacts `analysis/t15_{baseline,respecify,calibrate,width_curve,verify}.json`;
> **pre-T15 β preserved at `analysis/phase11_opponent_model.pre_t15.json`** so before/after stays
> runnable. DEV-only; the spent lockbox and the frozen value stack are untouched.
>
> **★ SHIPPED:** `AdpSpec(power, p=0.15)` · `BandSpec(widening, k0=40, +5/round, cap 160)` ·
> `WidthCurve(γ=0.8)` · per-seat `Personality.width_mult`. **All three specs travel with β** in
> `analysis/phase11_opponent_model.json` and are read back with it.
>
> | bar | pre-T15 | shipped | corpus |
> |---|---|---|---|
> | #1 profile distance · round-1 mean | 0.388 · 12.15 | **0.222 · 4.36** | 0 · 2.87 |
> | #2 elite p95 · past pick 10 | 30.0 · 57.9 % | **17.0 · 28.5 %** | 17.5 · 18.9 % |
> | #3 worst harvest excess | — | **+0.21 sd** | tol 1.0 |
> | #4 11.2 Brier gain | +0.0708 | **+0.0890** | — |
> | #5 dispersion error | +8.8 % | **+17.0 %** | tol ±20 % |
>
> **⚠ Two things did NOT improve, and the verdict hides them:** dispersion error grew +8.8 % →
> +17.0 % (passes tolerance, but Session G had it better), and **11.1's log-loss gain is not
> comparable across this change** (+0.1715 at the shipped band vs a committed +0.1738 on `fixed40` —
> different candidate sets, and this session's own finding is that log-loss is not comparable across
> bands). Only the 11.2 Brier supports a clean before/after.
>
> **★★ THE FINDINGS TO CARRY FORWARD — four method errors, each of which would have shipped a
> plausible wrong answer:**
> 1. **"Gain over the baseline" is not a selection criterion.** Inside one band, log-loss picks
>    p=0.45 while gain picks **p=1.00 — the incumbent spec T15 exists to replace.** Gain rises when
>    the *baseline* degrades. Twin of F.6's ablation rule. Replaced by **`band_coverage`**.
> 2. **The shipped `fixed40` band was violating the Session-G contract, unmeasured** — it excludes
>    the realized human pick **3.95 %** of the time. That, not a fit statistic, is the judgement-free
>    case for widening.
> 3. **A uniform width metric traded away the defect it was built to fix**, selecting a spec that
>    failed the elite-fall gate. Objective restricted to rounds 1–6 and **gates promoted from terms
>    to hard constraints** — *a gate a metric can out-vote is not a gate.* Related: **a scalar gate
>    over a curve** reported PASS while the curve went 0.388 → 0.791.
> 4. **One knob cannot set both ends.** The `w_a ∝ a^(1-p)` derivation ignores **pool exhaustion**
>    (~30 boarded players remain by round 15): predicted late growth 18×, measured 1.8×. Fixed with
>    the round function T15 already owed 16.14R.
>
> **☐ OPEN, handed to 16.14R with numbers attached:** the **seat-faithfulness population** — median
> `pool_rank` **10.40 vs a corpus 7.62**, moderate band **13.5 % vs 54.3 %**, chalk **19.6 % vs
> 0.2 %**. It trades against the reach profile (γ=0 gives 65.9 % moderate but fails dispersion), was
> never one of T15's five bars, and needs **per-seat board perturbation** (16.14R's *direction* half)
> plus a **room-composition** decision on the two `autopilot` seats (16.15). **☐ Also:** 16.9's
> `NarrativeShock.intercept` is formally **stale** — `assert_transportable` now refuses it across a
> spec change; not re-fit, because 16.9 measured it as unidentified. **◐ T16** is very likely
> dissolved by the widening band but is **not re-measured** — re-run the 16.10 done-bar at 15 rounds
> before marking it ✅.
>
> _(Prior pointer — step 0, superseded above.)_ Baseline **frozen** at `analysis/t15_baseline.json`
> — 900 seeded drafts vs 1,144 realized FFC-boarded human drafts, one measurement code path over
> both. Writeups: `findings.md` §"T15 step 0", `PLAN.md` §2026-07-27 (session 3),
> `docs/TECH-DEBT.md` T15 §"Step 0 done".
>
> **★ Three corrections the 900-draft baseline makes to the text below — the older numbers came off
> ONE draft, so prefer these:** (1) **"the sim is flat" is wrong** — Spearman +0.646 (corpus +1.000),
> it rises to round 9 then **turns over**; state the defect as the **ratio column, 4.24× at round 1 →
> 0.57× at round 15**. (2) **Bars 1–2 tighten on the FFC-only corpus**: round-1 mean **2.87** / p90
> **5.23**; and bar 2 is worse than the anecdote — **57.9 %** of consensus top-12 fall past pick 10 vs
> **18.9 %** realized (p95 **30.0 vs 17.5**). (3) **Bar 3 already roughly passes** on *fixed*
> `pool_rank` edges (+20.5 sim vs +17.6 corpus, sd 17.0); its **quantile** form is an artifact
> (compares `pool_rank` 1.28 to 4.28) and must not be used.
>
> **★★ THE FINDING TO CARRY FORWARD — the room has no moderate drafters.** 54.3 % of real seats sit at
> `pool_rank` 2–8; the sim puts **2.2 %** there and **19.6 %** below 2. The room is **bimodal**, so
> **T15's target is the distribution of deviation, not its scale** — a uniform shrink moves the
> extremists and leaves the middle empty. Two corollaries: `autopilot` at 2-of-10 seats over-represents
> a behaviour that is **0.2 %** of real seats (**a 16.15 composition question**, and it does *not*
> reopen 16.14R's "autopilot: no change", which was about its win); and simulated within-bin harvest sd
> is **2.1–3.7** picks vs the corpus's **8.7–17.0**, so the seats are too homogeneous even where the
> means match.
>
> **★ STEP 1, and the arithmetic that decides it (derived in `PLAN.md` session 3).** With utility
> `u = β·f(a)`, width in ADP picks is `w_a ∝ 1/f'(a)` — **board density cancels**. So linear ⇒ flat
> (the defect, derived); `a^p` ⇒ `w_a ∝ a^(1-p)`, and the measured `pick^0.5…0.6` gives **p ≈ 0.4–0.5**;
> `log a` ⇒ over-corrects. **Rank-in-pool ⇒ `w_a ∝ board density`, which grows ~2.3× where the corpus
> grows 5.5× — it structurally under-corrects and is nearly a no-op** (linear-in-ADP inside a fixed
> top-K already *is* rank-in-pool up to a level that cancels in the softmax). Still choose by refit
> log-loss, but grid the **exponent**. ⚠ Two things the plan did not record: `apply_hype` and
> `Personality.reach_cap` hardcode the **linear** derivative `−β/_ADP_SCALE`, so the extraction owes a
> `utility_per_pick(adp)` next to `adp_feature(adp)`; and **persist the fitted exponent alongside the
> coefficients** in `analysis/phase11_opponent_model.json` or `load_opponent_model` pairs a new β with
> the old transform. Keep raw `adp` on the choice frame so an exponent grid refits from one built frame.
>
> **⚠ Environment:** `.venv/bin/pytest` has a stale shebang from the pre-move path — use
> `uv run python -m pytest`, or repair with `uv sync --reinstall`.
>
> _(Prior pointer — the live mock that opened this session; its one-draft numbers are superseded above.)_
>
> **What happened.** The user drafted a full 10-team mock from seat 7 against `DEFAULT_ROOM`, live,
> one pick at a time. He raised **one** issue, four times, unprompted: the room's reaches and falls
> are impossible. He is right, and it is measured — `findings.md` §"Live mock draft (2026-07-27)",
> register entry `docs/TECH-DEBT.md` **T15**.
>
> **The number to carry:** round-1 mean reach is **11.4 ADP picks simulated vs 3.3 realized**
> (p90 **27.7 vs 6.6**) over 1,420 human drafts / 197,227 boarded picks; by round 15 it inverts
> (**15.0 vs 27.1**). The corpus curve grows monotonically, the sim is flat — **a shape error, not
> a scale error**, so do not "just make it chalkier". Elite falls mirror it: corpus ADP ≤ 12 has
> **p95 = pick 17**; the sim dropped five top-12 players past that in one draft. And the spill is
> harvested — `autopilot` mean drift **−19.8 picks**, both autopilot seats finished **1st and 2nd**.
>
> **★ Why it survived every gate: an aggregate metric cannot see an impossible event.** 11.1
> log-loss +0.174, 11.2 Brier +0.086 and 16.9's dispersion match are all still true. They score
> *better than a baseline*, never *possible*. **Every subsystem needs one bar a domain expert could
> fail by eye, run in front of one before it ships.**
>
> **★ It is a specification error, so more data cannot fix it** — ADP is worth **0.0337 utility per
> pick** while `is_TE` is +0.567 (**17 picks**) and `need` +0.474 (**14 picks**), softmaxed over a
> fixed top-40 ⇒ **expected reach 16.8 picks before any personality tilt**. `adp_s` is linear in raw
> ADP pooled over all rounds; one coefficient cannot be sharp at the top and diffuse at depth.
> F.5's 52× corpus expansion estimated the wrong coefficient more precisely. **Measured fix family:
> width ∝ `pick^0.5…0.6`, i.e. a fractional power or rank-in-pool — NOT log-ADP (`pick^1.0`),
> which over-corrects; T15's earlier log suggestion is superseded.** Five acceptance bars are
> pre-registered in T15.
>
> **⚠ `Personality.max_reach_picks` is not a total-reach cap** and was misread as one: it clips a
> seat's *own opinion* only. The draft's 42-pick reach came from **`balanced`** — every tilt off.
>
> **★ DECIDED 2026-07-27 (user): (a) — the T15 respecification session goes NEXT, before Session I.**
> Phase 17 / Session I slides one session; nothing in it depends on T15 or vice versa. Rejected: (b)
> keep Session I first, (c) ship the hard-clip override now. **The clip is a step-4 fallback only** —
> shipped only if the refit leaves a gap, and then labelled/separable (see T15). Ordered plan:
> **0** promote `mockdraft.py` to `steps/` + seeded batch mode + a sim→`build_drift_panel` helper (the
> A/B harness — build it before anything else; the single-draft evidence is noisy) · **1** respecify
> `adp_s` (fractional power `adp^~0.45` **or** rank-in-pool; choose by **refit log-loss**, not by
> curve-fitting the corpus table) and **refit** — the point is that `is_TE`/`need` shrink in
> pick-units at the top of the board. ⚠ `adp → adp_s` is built in **two** places that must not
> diverge (`opponent_model.py` `build_choice_frame` fit path + `candidate_matrix` sim path) → extract
> one shared `adp_feature()` · **2** add the two judgement-free gates (no top-12 past ~pick 17; the
> `autopilot` seats stop out-valuing the room) · **3** re-verify 11.1 / 11.2 / 16.9 **together**, and
> **re-fit `NarrativeShock.intercept`** (not transportable) · **4** clip only if still needed. See
> `PLAN.md` 2026-07-27.
>
> **★ THEN (2026-07-27 session 2, docs-only): the 16.14R personality contract is SPEC-AGREED** —
> `docs/BUILD_PLAN.md` §16.14R, `PLAN.md` §2026-07-27 (session 2), `findings.md` §"Personality design
> review". It is the session **after** T15 (it needs T15's round-varying width function). Headlines:
> **width vs direction** replaces the absolute `max_reach_picks` ceiling (autopilot 0 · safe ~0.8 ·
> balanced 1.0 · reacher ≤2.0) · **autopilot unchanged** (its win was harvested spill, so T15 fixes it
> by fixing everyone else — **T15 bar #3 was rewritten to measure surplus, not standings**) ·
> **balanced was never given its holistic tilts** (raw β, every tilt off — that is the 42-pick reach) ·
> **Value Hawk replaces Homer** (reverses 2026-07-23; `fandom` becomes fitted-and-unused, do not delete)
> · reacher inherits the 16.9 shock + 16.10 hype. **★ "The level, not the residual"**: situation flags
> are null for *drift* and that is consistent with them driving human behaviour — ADP already absorbed
> them — so situation ships opt-in/default-OFF and never as a deviation driver. **⚠ Scoring trap:** the
> value hawk optimizing our board and scored on our board wins by construction; projected-points
> rankings are **descriptive**, evaluative claims run on **realized** points. **☐ 3 opens before 16.14R
> only** (value hawk objective VBD-vs-**CE**, its reach window, whether 16.4/16.5 join the 16.13 board)
> — **none of them block T15.**
>
> **Reusable artifact:** the interactive human-vs-personalities driver lives in the session
> scratchpad (`mockdraft.py`, ~330 lines, thin over `DraftState` + `make_room_pick_fn`). **Promote
> it to `steps/` if we want repeatable human mocks** — it is how this defect was found, and it is
> the natural before/after harness for the T15 fix (re-measure over ≥50 seeded drafts).
>
> _(Prior pointer — history.)_ **★★ (2026-07-27, ★ SESSION H COMPLETE — 16.13 ☑ · 16.14 ☑ · 16.15 ☑ ·
> T17 ☑. NEXT = Session I, Phase 17 formats.)**
>
> **State:** **524 tests** (was 496), ruff clean, every done-bar gate PASS on the live 2026 board.
> `steps/phase16_15_mock_room.py` → `analysis/phase16_15_mock_room.json`; the T17 guard lives in
> `steps/phase5_5_utility.py`. **Committed** — Session H is one commit on top of `5f6383b`
> (Session G). DEV-only; the spent lockbox untouched; the frozen value/distribution/optimizer/VBD/
> cost-report stack untouched (16.13 only *reads* it). Stage-0 FFC chore: last pull 2026-07-24,
> **next due after 07-30** (`steps/stage0_adp_snapshot.py`).
>
> **★★ THE FINDING TO CARRY FORWARD — an upstream fix can break a downstream signal by making it
> better.** T17 turned `games_played_mean` from four cohort constants into a real forecast, and in
> the same move into a **level** column (`corr` with `mean` within position: +0.00 before, then
> +0.46…+0.90). `safe_floor`'s durability weight silently became a quality tilt — no code change, a
> green suite, and a plausible-looking personality. Third instance of the *level vs shape* lesson,
> first to arrive through **data** rather than code, fixed the same way (`residual_shape` gained
> `durability`). **A regression test pins a signal's behaviour, not its meaning:** nothing in the
> suite could have caught this. What catches it is re-measuring a signal's correlation with the
> level after **any** change to the data it is built from — the F.5 "re-audit after a step change in
> input volume" rule, generalized from volume to quality.
>
> **★ 16.15 = Phase 16's FIFTH null, and it is 16.9's null.** At the shipped shock (1.48 ADP picks)
> the room does nothing: largest per-seat move **0.036**, routing-vs-gain **+0.07**. The same shock
> ×10 gives **+0.91** (sweep ×1→×40: +0.07 · +0.53 · +0.84 · +0.91 · +0.95). So the coupling is
> **built correctly and waiting on a signal worth routing**. The done-bar **gates the mechanism** at
> `AMP_GATE` and **reports** the shipped size — turning the shock up to pass would tune a calibrated
> parameter to a face-validity check. (Same shape as 16.16: the detector works, reacting does not.)
>
> **★ The reach ceiling bounds a seat's OWN OPINION, not the room's story.** `max_reach_picks` caps
> `signal_weights` + fandom excess; the shared 16.9 draw is applied outside the clip, because 16.9
> fitted it **uncapped and uniform**. Folded in, a seat whose signals saturate its ceiling cannot
> express the story at all — and nothing fails, since a personality that ignores the shock still
> drafts legally. **Two bar-design lessons came out of finding it:** (1) a **two-ended** bar
> (*chasers − autopickers*) passes on a room routing the story backwards, because autopickers get
> sniped either way — state the bar across **every** seat; (2) a **zero vector is not an off
> control** — `argsort` on zeros labels the top-N by board order, i.e. by ADP, which autopick seats
> take by construction, manufacturing a large fake effect on exactly the seats it should be silent
> about. Close the channel, keep the same labels.
>
> **⚠ Correction recorded, because the number is quotable and was wrong:** "homer clips 90 % of
> candidates" was measured on the **test fixture** (`β_adp_s = −0.85`). On the live board's fitted β
> (−1.68) homer clips **0.0 %** (upside 26 %, safe 33 %). The fix stands on the estimation-conditions
> argument, not on a large current effect. *Measure the real board before quoting a fixture number
> as the system's behaviour.*
>
> **★ NEXT: Session I — Phase 17 League-Format Fidelity 17.1–17.4** (roster/lineup generalization
> incl. superflex + format-aware VBD replacement, custom scoring, the generic settings contract,
> keeper). A full-phase item, ~1,000–1,800 lines. Then J (optional dynasty 15.1) → **K = Phase 14.1
> MVP + all surfacing, strictly last, do not bundle.** `docs/TECH-DEBT.md`: **T17 ☑**, new **T18**
> (🟡 `avg_reach` is a pooled-board mismatch, unconsumed today); T13/T15 still open.
>
> _(Prior pointer — history.)_ **★★ (2026-07-26, ◐ SESSION H PART 1/2 — 16.13 ☑ · 16.14 ☑.)**
>
> **State:** **496 tests** (was 466), ruff clean, every done-bar gate PASS.
> `steps/phase16_13_personalities.py` → `analysis/phase16_13_personalities.json`. **UNCOMMITTED**
> (13 files), your choice — Session G is fully committed through `5f6383b`, so the working tree holds
> Session H alone. DEV-only; the frozen value/distribution/optimizer/VBD/cost-report stack is untouched
> (16.13 only *reads* it). Stage-0 FFC chore: last pull 2026-07-24, **next due after 07-30**.
>
> **★★ THE FINDING TO CARRY FORWARD — a signal is not a *shape* signal without its level control.**
> 16.14's spec says the upside chaser weights `q90` and the safe drafter weights `q10`. Built exactly
> that way, **they agree with each other**: on the real board `safe_floor` drafted a *higher* mean
> `q90` than `upside_chaser`. Measured within position, `corr(q90, mean)` = **+0.984 / +0.985 /
> +0.999** (2022 / 2025 / 2026) and `corr(q90, q10)` = +0.62…+0.74. The quantiles are almost entirely
> **level** — "is this player good" — so both weights are quality tilts wearing risk-tilt clothes.
> The fix is `enrichment.residual_shape`: regress the level out inside each position, giving
> `upside`/`floor`, orthogonal to level by construction and `corr = −0.86` with each other.
> **This is the 16.10 finding again** (*a coefficient is not transportable without its controls*) —
> same failure mode, one level down, on a **signal** instead of a coefficient, and it presented the
> same way: as a plausible modelling result rather than as an error. It was caught only because the
> face-validity bar was stated as *the two must disagree with each other* rather than *each must
> differ from balanced*; the weaker bar passes the broken build. **State your bars as oppositions.**
>
> **★ The other lesson: an inert thing still passes.** `homer` had been scaling a `fandom`
> coefficient whose feature was identically 0 (nothing in the mock path ever passed `fav`) and
> `rookie_hawk` scaled a column `_prepare_board` discarded. Both were **literal no-ops from Phase
> 11.3 through a full phase and a green suite**, because a personality that does nothing still
> completes a legal draft. Assert that a tilt *moves* something, not merely that it runs.
>
> **★ Effect sizes here are small and that is honest.** ±0.05 z on a pooled drafted pool; a manager
> who reaches 1–2 rounds cannot move 90 picks much. One seeded draft cannot even resolve the *sign* —
> every face-validity number pools 8–12 drafts. The reach ceilings (18 / 15 / 24 picks) were
> **measured**: at 10 the personalities sit inside `balanced`'s own noise.
>
> **★ New tech debt: T17 (🟠) — the live season has no per-player availability.**
> `availability_projection(con, 2026)` returns **0 rows** (a future season has no played weeks to
> predict on), so every player falls to the T3-A cohort prior: **4 distinct `games_played_mean`
> values across 480 players** and the Phase-5 `mean` collapses to **37 % of the consensus projection
> it is built from** (2025: 75 %). Session H is insulated because every signal is standardized
> *within position*, so a uniform multiplier cancels — but this **blocks Phase 14** showing a user
> any distribution number for the season they are drafting. Fix + guard in `docs/TECH-DEBT.md`.
>
> **★ NEXT: 16.15** — mock-room seat composition (a default realistic mix over the 9 opponents,
> user-overridable), routing the 16.9 narrative shock through the seats that would chase it, and the
> app selector spec. The plumbing is already in: `Personality.hype_gain` is the per-seat multiplier
> on the shared shock and `fav_teams` makes a homer's team configurable. Then Session I (Phase 17
> formats) → K (Phase 14 app, last).
>
> _(Prior pointer — history.)_ **★★ (2026-07-26, ★ SESSION G COMPLETE — T14 ☑ · 16.9 ☑ · 16.11 ☑
> · 16.10 ☑ · 16.12 ☑ · 16.16 ☑.)**
>
> **State:** **466 tests** (was 425), ruff clean, every done-bar gate PASS. **UNCOMMITTED** — left on
> a clean-diff basis for your review (your choice this session). DEV-only; the spent lockbox is
> untouched; the frozen value/distribution/optimizer/VBD/cost-report stack is **provably** untouched
> (see the isolation gate below). Stage-0 FFC chore: last pull 2026-07-24, **next due after 07-30**.
>
> **★★ THE FINDING TO CARRY FORWARD — a coefficient is not transportable without its controls.**
> 16.10 ranks nominations using the three weights that survived 16.8's ablation. Those are *partial*
> coefficients, fit with `adp_rounds` and position dummies in the model. Used unconditionally they
> ranked players by **board depth** (ADP standard deviation grows mechanically with ADP: 0.7 picks at
> the top of the 2026 board, 33 near the bottom) and then, once depth was controlled, by **position**
> (our value board likes every TE more than ADP does). Two plausible-looking, wrong candidate lists.
> A third defect hid in the *units* — the weights are in rounds, velocity is rounds/week, so momentum
> was nearly inert until multiplied by a horizon. **This is the F.5/F.6/16.9 family again: every one
> presented as a modelling result rather than as an error.** When reusing a fitted coefficient
> anywhere new, reproduce its controls and check its units before reading the output.
>
> **★ Phase 16's availability track is DONE and it is four honest nulls** (16.8 drift model, 16.9
> narrative shock, 16.16 run reaction — plus the value side's 16.1/16.2 and 16.4's deflationary
> 20.9 %). Everything that ships is either a **contract fix** that improved a validated metric (16.9's
> choice-set band) or an explicitly **curated, opt-in, default-OFF** channel. Phase 16 found no edge;
> it found four ways the apparent edges were measurement artifacts.
>
> **★ 16.16 = the detector works, reacting to it does not.** Run intensity measured against the **live
> candidate set** (top-40 by ADP, *not* the whole remaining pool — that version fired on 61 % of
> windows and anti-discriminated) gives monotone discrimination, **+0.109** at threshold 0.50 across
> 7,957 replayed windows. But paired availability Brier on 4,300 run-opened windows degrades
> monotonically in the bump size: **0.2121 → 0.2123 → 0.2128 → 0.2186**. Likely double-counting
> (11.1 already carries `pos_run3`); confirming it needs an 11.1 refit, cf. T15. **Default OFF**,
> detector kept as a live-draft alert for 14.4.
>
> **★ What you owe the hype board.** `reference/hype_board.csv` ships **24 rows / 20 directional
> claims, all `reviewed=false` — therefore inert.** Nothing consumes it until you set `reviewed=true`
> per row. Your review surface is `pick_delta` / `note` / `confidence`; the rows themselves are
> derived and regenerate safely (`steps/phase16_10_hype_board.py --write` merges your edits forward).
> Four rows are deliberate **non-claims** (`pick_delta=0`, e.g. Brian Robinson Jr., whose board-topping
> ADP disagreement is *handcuff contingency*, not hype) — kept visible so you can see where the
> derivation fired and the research found nothing.
>
> **★ New tech debt: T16** (🟡 a deep curated claim cannot express in a standard **15-round** league —
> a +12-pick claim on a board-rank-171 player gave a *bit-identical* 30-draft result and needed ~5×
> the offset to move; the 16.10 done-bar therefore runs at 18 rounds. Recommendation: surface the
> limitation now, and let **T15**'s depth-varying candidate set dissolve it properly. Do not hack the
> offset scale alone.) **T14 ☑, T15 still open.**
>
> **★ NEXT: Session H — opponent personalities 16.13–16.15.** 16.13 board enrichment (attach the frozen
> Phase-5 distribution + `value_board` fields read-only), 16.14 the five headline personalities
> (`signal_weights`), 16.15 mock-room composition + hype coupling. Validation = face-validity + unit
> tests, **no Brier gate** (decided 2026-07-23). Then I (Phase 17 formats) → K (Phase 14 app, last).
>
> _(Prior pointer — history.)_ **★★ (2026-07-26, ★ SESSION G part 1/2 — T14 ☑ + 16.9 ☑.)**
>
> **State:** **425 tests** (was 411), ruff clean. Committed on `main`. DEV-only; the spent lockbox is
> untouched; the frozen value/distribution/optimizer/VBD/cost-report stack is not touched by any of
> this. Stage-0 FFC chore: last pull 2026-07-24, **next due after 07-30**.
>
> **★★ THE FINDING TO CARRY FORWARD — the choice-set contract.** 11.1 is a conditional logit fit on
> `build_choice_frame(top_k=40)` = the top-40 available by ADP. **Both** consumers of that fitted β
> were simulating against the *whole board*: `personalities.make_opponent_pick_fn` and
> `availability.simulate_survival`. A conditional logit's coefficients only mean anything relative to
> the candidate set they were estimated on. This inflated simulated draft-slot dispersion **59 %**.
> Both now read `opponent_model.CHOICE_TOP_K` and a test fails if fit and simulation drift apart.
> **This is the fourth member of the F.5/F.6 family** (hardcoded `scoring="ppr"` → contaminated
> behavioural corpus → modal board size → candidate set): *every one was a fit/use mismatch that
> presented as a modelling result.* When a fitted model gets a new caller, check the caller
> reproduces estimation-time conditions before trusting the output.
>
> **★ 16.9 = an honest NULL (Phase 16's third).** The premise inverted: the phase assumed
> independent per-seat sampling **under**-disperses; measured, the simulator **over**-dispersed.
> After the contract fix — level error **59.5 % → 8.8 %** (pooled sd 2.897 → 1.976 vs realized
> 1.816) and availability Brier **+0.0644 → +0.0708** on 7,792 windows, so *two independent metrics
> improved and it is not a tuning choice*. The shock itself does nothing: realized depth slope
> **+0.679**, banded **+0.077**, +shock **+0.057**; swept over a **50× size range** the slope stays
> inside its own between-sample noise (two runs at one setting: +0.249 / +0.057) → the calibration is
> **unidentified**, and its "best intercept" is a noise draw, reported as such rather than as a fit.
> **Structural reason it cannot work:** `top_k` is a hard rank filter applied *before* utility, so no
> additive shock pulls a player into the candidate set. **Shipped: band ON by default; shock built,
> wired, tested, default OFF** — kept because 16.10/16.15 need an expression channel for a curated
> narrative, and that channel is now correct.
>
> **★ New tech debt: T15** (🟡 simulated dispersion is flat in board depth — `adp_s` is linear in raw
> ADP, so dispersion is uniform *in rank*; real drafting is sharp at the top and diffuse at depth.
> Fix is an **11.1 respecification** — soft/widening band or log-ADP/rank utility — and must be
> re-verified against 11.1 log-loss, 11.2 Brier **and** the 16.9 profile *together*. Do it before
> Phase 14 surfaces `P(available)` to a user; do not block Session H on it.) **T14 ☑** — see its
> register entry for the "a complexity class is not a profile" lesson.
>
> **★ NEXT: 16.10** — the curated hype board. User decision already taken: **build the mechanism now
> (loader + schema + tests + a Claude-drafted 2026 board stamped `reviewed=false`, apply path refuses
> unreviewed rows), user reviews the CSV afterwards** — do NOT stall the session on review. Then
> 16.11 momentum (live-2026-only, forward-only label) → 16.12 consumption → 16.16 run detection.
> Then Session H (personalities 16.13–16.15) → I (Phase 17 formats) → K (Phase 14 app, last).
>
> _(Prior pointer — history.)_ **★★ (2026-07-26, ★ SESSION F.6 COMPLETE — the re-derivation sweep.)**
>
> **State:** **411 tests** (was 395), ruff clean, all data-health gates PASS. Committed on `main`,
> **not pushed**. Stage-0 FFC chore: next due after 07-30. DEV-only; the spent lockbox is untouched.
>
> **★★ THE FINDING TO CARRY FORWARD — a contaminated corpus invents effects.** F.5 fixed format
> contamination on the ADP board path but the **behavioral** path had the identical bug:
> `build_choice_frame`/`availability_brier` read all 7,699 human drafts (74 % dynasty/2QB/IDP/
> auction/abandoned) against one hardcoded 10-team PPR board. Of those, **1,426 are eligible**.
> Re-fitting on the clean corpus deleted two "behavioral findings": `rookie` +0.45→**+0.11** (that
> was dynasty rooms) and `is_QB` +0.17→**−0.03** (2QB rooms), while `adp_s` doubled
> −0.85→**−1.68**. *Noise shows up in a CI; contamination shows up as a plausible result.*
> Eligibility now lives in one place — `adp/boards.py` + `drift_panel.eligible_drafts` — and
> `tests/test_boards.py` fails on the old rule (verified by reverting, not by inspection).
>
> **★ Results after the sweep.** 11.1: **+0.1738** log-loss gain CI[+0.1693,+0.1781] on 70,614
> groups (was +0.1126 / 7,900) — beats ADP. 11.2: gain **+0.0864** CI[+0.0769,+0.0980] on 36,972
> windows over 252 drafts — still beats best-tuned ADP+noise, but **half** the +0.1587 that 21
> drafts implied (`n_drafts: 21` was a *default argument*, not a corpus limit). S6 adaptive
> re-validated and stronger: adaptive(hero_rb) **+19.4 CI[+4.5,+32.9]**.
>
> **★ 16.8: the leak got stronger with more data.** Headline **+9.25 %** CI[+3.29,+13.91] (bar is
> 2 %) — and the mandatory ablation without `source_divergence` is **+0.01 %** CI[−1.98,+1.84].
> With more sibling drafts the leave-one-draft-out board estimates each room's own consensus
> better, so the leak-prone feature predicts better. **Scale does not launder a leak — a rising
> headline is what a leak looks like from outside.** Verdict stands: no per-player drift forecast
> for 16.9; it shapes its shock from the ablation survivors (`rookie`, `adp_stdev`, `vbd_gap`,
> `pos_WR`, `pos_TE`).
>
> **★ Decisions taken this session (do not re-litigate):** ECR adopted as the 2025 board fallback
> but **calibrated** (isotonic rank→ADP + truncation at FFC's median depth 182 — raw rank produced
> +17.5-round fake reaches and a 2025 sd of 2.67 vs 1.82 after); the pre-registered 16.8 headline
> stays **FFC-only** with ECR as a labelled sensitivity; **no per-manager random effects**
> (ablating `mgr_lean` costs 16 % of the gain, and the eligible corpus has only 111 managers with
> ≥10 drafts — the "1,330 with 10+" figure counted all formats); 11.1 fits a **sampled 60
> drafts/season** because the full frame is ~8M rows and this box has ~3 GB.
>
> **★ New tech debt: T13** (🟠 the Phase-5 cloud is **not reproducible across processes** — dress
> coverage wobbles 75.5↔76.5 %, so Session D's 75.5 % and today's 76.5 % are *the same number*;
> frozen layer, fix at Phase 14) and **T14** (🟡 11.2's bootstrap is O(n_boot × n_drafts ×
> n_windows), ~45 min at 252 drafts). **T11(b) closed.**
>
> **★ The 2025 dress rehearsal ran its season sim for the first time** (Session D could not): 300
> team-seasons, playoff Brier 0.2325 < 0.240, title Brier 0.0905 vs 0.090 (marginal miss), points
> coverage 0.88. Cause of the old skip: `sleeper_human` boards are labelled with the **modal**
> league size (12 from 2019 on) while every consumer asks for `teams=10` — the hardcoded-label
> family, third instance. Fixed at harness level; frozen readers untouched.
>
> **★ NEXT: Session G** — apply the drift, 16.9–16.12 + 16.16, under the null's constraint
> (dispersion match, no mean signal). Then H (personalities) → I (Phase 17 formats) → K (Phase 14
> app, last). Re-running 11.2 at scale first? Fix T14 or it costs ~45 min of bootstrap.
>
> _(Prior pointer — history.)_ **★★ (2026-07-25, ★ SESSION F.5 COMPLETE — corpus expansion.)**
>
> **State:** **395 tests** (was 382), ruff clean, **all data-health gates PASS for the first time**
> (T12 closed). DB backed up 2026-07-25 (357 MB, checksums verified). Stage-0 FFC chore: current,
> next due after 07-30. Session F.5 is **left uncommitted for your review**, same as prior sessions.
>
> **★ What happened: the Sleeper corpus grew ~52× and the 16.7 drift panel grew 33.6×.**
>
> | | Before | After |
> |---|---|---|
> | Human drafts | 149 | **7,699** |
> | Picks | 17,082 | **1,207,687** |
> | Manager profiles | 289 | **24,696** |
> | **16.7 panel drafts** | **34** | **1,144** |
> | `drift_centered_sd` (16.9's target) | 1.5375 | **1.8161** |
>
> The old crawl was **un-reseeded, not exhausted** — three mechanical defects (frontier never fed back
> in from `sleeper_manager_profiles`; participant expansion dead-ended because it keyed on "is this
> draft new" while the caller pre-seeds the whole store; budget counted *discovered* not *ingested* ids,
> burning 263/500 on dead ids). All fixed, all regression-tested. `steps/phase0_10b_crawl.py --mode
> frontier` is resumable via `sleeper_crawl_users`/`_leagues`/`_queue`. Full detail: `findings.md`
> §"Session F.5", `docs/SLEEPER.md`.
>
> **★★ THE FINDING TO CARRY FORWARD — format contamination.** `_refresh_board` hardcoded
> `scoring="ppr"`, so every complete human snake draft landed on one board labelled PPR redraft. At 149
> drafts that was harmless; at 7,399 it was **82 % wrong** (only 1,312 are PPR redraft; 2,547 are
> dynasty_2qb, 952 2qb, 861 dynasty, 610 IDP). It surfaced as an *unrelated-looking* gate failure — `ADP
> top-150 gsis match` red at 3.5 % unmatched, because IDP rooms pushed DB/DL/LB onto an offensive-redraft
> board. Boards are now **redraft-only, split per (season, scoring)**, in FFC's vocabulary; unmatched
> fell to 0.61 %. **A hardcoded label is a bug that scales with your corpus — re-audit derived artifacts
> after any step change in input volume, not just after code changes.**
>
> **★ NEXT: Session F.6 — the re-derivation sweep**, in this order, and note each item's *decision*
> status because F.5 deliberately took none of them:
> 1. **Phase 11.2 availability Brier (T8b)** — the thinnest result in the repo (`n_drafts: 21`). The
>    binding constraint was repeated managers; there are now **12,578 with ≥2 drafts, 1,330 with 10+**.
>    Largest proportional firming available; do this first.
> 2. **Phase 11.1 opponent model** — 7,900 choice groups → ~200k. **Decide explicitly: re-fit, or
>    *extend*** (per-manager random effects are only now viable). A re-fit is mechanical; an extension is
>    a modelling session. Recommendation was: re-fit first, look, then decide.
> 3. **16.8 drift model** — CI shrinks ~5.8× (√(1144/34)). **The pre-registered >2 % skill bar stands
>    unmoved** and the `source_divergence` **ablation remains mandatory** (see the Session F ablation
>    rule below — it is the single most important carry-forward in this file). Honest expectation: the CI
>    clears zero, the point estimate stays under 2 %, i.e. real but too small to use.
> 4. **Phase 11.3 personalities** + **S6 adaptive** (`spine_5_adaptive.py`) — both ride the fitted β and
>    the behavioural room, so both move once (1)–(2) land.
> 5. **Open decisions not taken in F.5:** (a) adopt **ECR as the board fallback** to recover 2025 (278
>    eligible drafts, no FFC board; ECR covers 2017–2026 — mind the 2023 PPR `is_preseason=False` trap);
>    (b) whether to **re-run the 2025 dress rehearsal**, which is a further read of the 2025 calibration
>    holdout.
>
> **★ Banked for Phase 17 (Session I):** ingest filters nothing, so **5,693 complete human non-redraft
> drafts** (dynasty_2qb 2,607 · 2qb 1,021 · dynasty 861 · idp 610 · …) are already in the store. Phase 17
> would otherwise have re-paid the 70-minute crawl.
>
> **★ The lockbox is safe — verified three ways, do not re-litigate.** `lockbox_eval.py --which lockbox`
> routes to `source="ffc"`/`_board_ffc`; its seats use `_noisy_adp_pick` (ADP+noise, not the behavioural
> model); `cost_validation.py` likewise. Only `--which dress` (2025) reads `sleeper_human`. Growing the
> corpus **cannot** contaminate the spent 2023+2024 lockbox or the frozen value stack. Phase 9.1's
> scarcity is also Sleeper-independent (`survival_prob` lives in `draft/optimizer.py`).
>
> _(Prior pointer — history, and still the authority on the ablation rule.)_ **★★ (2026-07-25, ★ SESSION F
> COMPLETE — data 0.11 + availability drift 16.7–16.8.)**
>
> **State (as of Session F, superseded above):** 382 tests, ruff clean. Session F was committed at
> `6a047a7`. Stage-0 FFC chore: done 2026-07-24, **next due after 07-30**.
> New files: `data/sources/ecr.py`, `adp/drift_panel.py`, `adp/drift_model.py`, three `steps/`, two
> `tests/`, `tests/fixtures/ecr/`, three `analysis/*.json`; one edit to `adp/regression.py` (a
> backward-compatible `target`/`continuous` kwarg — the frozen softness path is untouched and its
> tests pass).
>
> **★ THE VERDICT: the availability side is an honest null too.** 16.8 = **DOES NOT PREDICT** against a
> bar fixed before the result was read (skill > 2 %, CI clear of 0): headline **+1.05 % CI[−1.48,+4.96]**.
>
> **★★ The single most important thing to carry forward — the ablation rule.** The headline's entire
> apparent skill came from `source_divergence`, a feature derived from the target's own sibling drafts.
> It was **already** computed leave-one-draft-out; the ablation that drops it scores **−1.75 %**, i.e.
> *worse than assuming everyone drafts at ADP*. **Leave-one-out is NOT sufficient for a sibling-derived
> feature** — drafts from the same season still share rooms, drafters and local ADP quirks. Always report
> the fit without it. Without that ablation (added on your instruction) this would have been written up
> as a weak positive.
>
> **What this means for Session G, concretely:** **16.9 must NOT be handed a quantitative drift
> prediction to amplify.** Its done-bar is a *dispersion* (variance) match, which needs no mean signal —
> `drift_panel.aggregate_player_season` already emits `sd_drift` for exactly that. Shape the shared
> per-draft shock with the things that **did** survive the ablation, as descriptive room behaviour rather
> than a per-player forecast: **`rookie` +0.73 rounds** (rooms reach for rookies by three-quarters of a
> round), **`adp_stdev` +0.35/SD** (where the crowd disagrees with itself, someone jumps), `vbd_gap`
> +0.18/SD, `pos_WR` +0.47. And **16.10's curated hype board is now the primary narrative channel** — its
> "curated, not a backtested claim" label is load-bearing, not a caveat.
>
> **Situation flags are null on the availability side too** (`team_changed`, `new_starting_qb`, both
> competition flags — insignificant, sign-unstable), exactly as in 16.1/16.2. Measured twice now from two
> independent directions: **situation change is a smaller lever than the narrative around it.**
>
> **★ 16.7's three deviations from BUILD_PLAN, each forced by a measurement — do not "fix" them back:**
> 1. **`PRESEASON_WINDOW` (Aug 1 – Sep 15)**, which the plan lacked. The Sleeper corpus contains drafts
>    from **February to November**; an offseason dynasty startup or a November in-season draft measured
>    against a September board is a different market, not drift. Biggest single filter: 117 → 42 drafts.
> 2. **Units are rounds** (`pick_no / teams`), so 6/8/14/16-team rooms join the 10/12-team FFC board.
> 3. **Sign flipped**: `drift > 0` = drafted **EARLIER** (matching `sleeper.build_tendencies`' `reach`),
>    and **`drift_centered`** — drift minus its own draft's mean — is the headline target, removing each
>    room's level offset. Never model raw `drift`.
>
> Panel: **34 drafts / 4,495 picks / 436 players / 2017–2024**. 2025 drops entirely because **FFC
> publishes no 2025 board** (confirmed against the live API). It is thin, and the one thing that would let
> 16.8 be re-asked is a bigger human corpus: add seeds to `reference/sleeper_seeds.txt` → run
> `steps/phase0_10b_crawl.py`.
>
> **★ 0.11 — I was wrong first, then measured it.** The FantasyPros ECR `?year=` archive **is** genuinely
> historical (2020 → McCaffrey/Barkley/Elliott). An initial check said otherwise because it regex'd a
> *different* embedded block out of the page — a widget that renders current-season players on every
> archived page. **Always parse the `ecrData` blob**, never loose `player_name` matches.
> **But the archive is kickoff-dated**: every board is a single end-of-preseason snapshot stamped
> 9/06–9/11, *after* the drafts it would explain — **1 of 38** corpus drafts post-dates its own stamp. So
> BUILD_PLAN's "does true-ECR beat the VBD proxy on drift MAE" is **unanswerable**, 16.8 keeps the proxy,
> and `ecr_asof` enforces this **structurally** (a draft-day as-of returns an **empty frame**, not a
> future board). The general lesson: *an archive existing is not the same as an archive being
> point-in-time — read the vendor's own timestamp before treating history as backtestable.*
> ECR is banked anyway (17,264 rows, 2017–2026 × 3 scorings, 99.2 % gsis) because it is free, deletable
> by the vendor, PIT-clean for **season-outcome** work, and **covers 2025 where FFC has nothing**.
> **⚠ 2023 PPR is flagged `is_preseason=False`** — `as_of = 2024-02-12`, re-touched after the Super Bowl,
> so it saw the season it should precede. Exclude it from any draft-season expert baseline.
> **Underdog is deferred, not attempted** (your decision): no keyless endpoint — marketing routes 404,
> board is a JS app on an unpublished API.
>
> **★ NEXT: Session G — apply the drift, 16.9–16.12 + 16.16**, under the constraint above. Then Session H
> (personalities 16.13–16.15) → I (Phase 17 formats) → K (Phase 14 app, strictly last).
>
> _(Prior pointer — history.)_ **★ (2026-07-25, SESSION E COMPLETE — the Phase-16 value-side track.)**
>
> **What closed this session:** the **user review gate** — `reference/coaches.csv` is **204 rows, all
> `confidence=high`**, fact-checked and signed off end to end (the edits were confidence-only, so 16.3b's
> machine audits stand) — and **16.4**, the last unbuilt substep.
>
> **16.4 (`situation/fingerprint.py`, `steps/phase16_4_fingerprint.py`) — descriptive only, as scoped.**
> 14 metrics per team-season, **z-scored within season** so league drift never reads as personality, pooled
> per play-caller and **EB-shrunk** by regime length (`k = σ²/τ²`). 41 play-callers / 64 spells / 169
> regime-seasons; all **17** transport teams resolve (12 own · 5 lineage · 0 silent); BAL/PHI/SEA report
> **both** priors (mentor lineage vs. outgoing caller). Decisions locked with the user: **no season cap**
> (2014–2025, lockbox years included, no provenance column — an initial DEV-cap answer was reversed),
> partial regimes cut to the weeks actually called, metrics extended with HHI/aDOT/pace, output at team and
> player grain, deltas + implied multiplier and **no points column**.
>
> **★ Two results worth carrying into any later phase that touches this:**
> 1. **The transport effect is small and mostly isn't the coach.** Only **20.9 %** of implied role-share
>    movement is the incoming play-caller; **79.1 %** is the incumbent slot regressing toward the league
>    mean, which any hire would produce. Every player row carries `reversion_pp` + `scheme_pp` — **never
>    surface `delta_pp` alone**, it overstates the phase ~5×.
> 2. **Trait portability is the real deliverable.** What a coach carries between jobs: `rz_pass_rate`
>    (k=1.7), `team_adot`/`plays_pg` (1.8), **`carry_hhi` (2.0)**. What he does **not**:
>    **`wr1_tgt_share` (k=17.9)** — the alpha receiver's target share is a **roster** fact. If a later phase
>    wants a "this coach will feed X" claim, the concentration and tempo traits support it; WR1 share doesn't.
>
> **★ Repo-wide lesson from a real bug here — `LA` vs `LAR`.** `pbp`/`weekly` write the Rams as `LA`,
> `reference/coaches.csv` as `LAR`, and 16.4's first run **silently deleted Sean McVay's entire nine-season
> tenure**, reporting it as an ordinary empty result. **A missing entity and a failed join look identical.**
> Route every cross-source team comparison through `adp.panel._canon_team`, and make "dropped with no stated
> reason" an assertion (`fingerprint.assert_regime_coverage`), not an empty row.
>
> **★ NEXT: Session F — data 0.11 (ECR + Underdog ADP ingest) + availability drift 16.7–16.8**
> (`adp/drift_panel.py` on the Sleeper human corpus, `adp/drift_model.py` consuming 16.1/16.2 features +
> the new ECR; walk-forward drift MAE/Spearman). **16.6 Beta Lab tab stays deferred to the Phase-14 app
> block.** Value-side reads as an honest null → Phase 16's edge is the availability side. Run the Stage-0
> chore first if the latest 2026 FFC snapshot is >6 days old.
>
> _(Prior pointer — history.)_ **★ (2026-07-25, SESSION E mid-flight — the review gate that is now closed.)**
> `reference/coaches.csv` was **204 rows**: the 32
> signed-off 2026 rows plus **172 Claude-researched historical rows (2014–2025)**. The historical half has
> **not** been reviewed, and **16.4 must not consume it until the user signs it off** — the same contract as
> the 2026 half. **The review surface is deliberately narrow: `offensive_coordinator`, `play_caller` and
> `hc_calls_plays` only.** `head_coach` is machine-audited against `pbp` (172 rows, **0 MISMATCH**) so it does
> not need human eyes. Sort by `confidence` — **25 `med` + 1 `low`** rows are where the doubt is concentrated;
> the 178 `high` rows were web-verified this session. Also awaiting review: **`reference/coach_lineage.csv`**
> (5 rows, new — see below).
>
> **★ 16.5 is now DERIVED, not researched (2026-07-25) — `reference/situation_events_2026.csv` is a
> GENERATED file: do not hand-edit rows.** Re-run `uv run python steps/phase16_5_situation_events.py
> --write`; research goes in that step's `ANNOTATIONS` block and is merged onto the derived rows. The
> hand-built 9-row version **missed 16 of the 23 team changes among draftable players** (incl. A.J. Brown
> PHI→NE at ADP 13.6) and had no row for the two highest-ADP players in the league. It is now **138 events
> over 30 teams**, dual-sourced (2026 `adp_snapshots` × `consensus_projections`, 0 disagreements) against
> 2025 `weekly`. **Its review surface is only `mechanism`/`confidence`/`notes` — 111 rows are still
> `mechanism=unknown`** (i.e. trade-vs-FA unresearched); every other column is machine-checked.
>
> **★ THEN, IN ORDER:** (1) build **16.4** on the reviewed table — scheme fingerprint + transport,
> `situation/fingerprint.py`, **descriptive-only, no FDR gate**; (2) **commit Session E**; (3) **Session F**
> (data 0.11 + drift 16.7–16.8). **16.6 tab stays deferred to the Phase-14 app block.**
>
> **★ What 16.4 is entitled to assume (consume via the API, do not re-derive):**
> - **The transport set is 17 teams, not the 13 the old pointer said** — `situation.coaches.new_regimes(df,
>   2026)` returns 13 `external` + **4 `internal_promotion`** (DEN, MIA, PHI, WAS). Deriving it from
>   `in_house==0` alone silently drops the promotions.
> - **★ Ask `coaches.fingerprint_source(df, 2026)` what to fingerprint each team on — do not work this out
>   from `coverage()` alone.** It returns `own` / `lineage` / `none` per team. Currently **12 own · 5 lineage
>   · 0 none**, i.e. **all 17 transport teams are covered**.
> - **The lineage fallback (user direction, 2026-07-25) replaced the earlier "say nothing" plan.** BAL, DEN,
>   PHI, SEA and WAS have genuinely FIRST-TIME play-callers (Doyle, Webb, Mannion, Fleury, Blough), but a
>   first-timer is not a blank — they came up inside somebody's system, so fall back to **that mentor's**
>   regimes and tag the evidence as weaker. `reference/coach_lineage.csv` names the mentor; every mentor is
>   itself a play-caller in `coaches.csv` (a gate asserts it), so the fallback always lands on a real
>   fingerprint. Doyle→Ben Johnson (CHI 2025), Webb→Sean Payton, Mannion→Matt LaFleur (GB), Fleury→Kyle
>   Shanahan (SF), Blough→Kliff Kingsbury. **Sean Payton (NO 2014–21, DEN 2023–25) and Kliff Kingsbury (ARI
>   2019–22, WAS 2024–25) were added to `coaches.csv` purely to make their mentees fingerprint-able.**
> - **Where lineage and team continuity disagree, 16.4 owes BOTH readings** — `same_team` marks the cases
>   where they coincide (DEN, WAS: same-team promotions, the strongest form). They **disagree at BAL**
>   (lineage Ben Johnson vs 2025 Monken), **PHI** (Matt LaFleur vs Patullo) and **SEA** (Shanahan vs Kubiak);
>   `prev_play_caller` carries the continuity side. Report both, do not pick silently.
> - **Regime grain:** `coaches.playcaller_regimes()` — a contiguous `(play_caller, team)` spell, with returns
>   split into separate spells. 70 regimes / 43 play-callers / 172 team-seasons; median 4 prior seasons for a
>   2026 play-caller (was ~1).
> - **Most prior regimes sit in 2023–2025** (Petzing/ARI, Monken/BAL, Slowik/HOU, Caley/HOU, Kubiak/SEA …),
>   i.e. **lockbox + calibration seasons**. The *names* are not outcome data, but 16.4's fingerprints are
>   built from realized role-shares — **decide explicitly how to treat 2023–24 before computing them**, and
>   note that the lockbox was already spent once in Session D and the value stack is frozen.
>
> **★ Decisions locked (do not re-litigate):** 16.3 signs off at **`confidence=high`** (2026-07-24) · 16.4
> gets the **full historical build** · schema **drops `change_from_prev`, keeps `in_house`** · research scope
> = **targeted** (the 23 uncovered play-callers' prior regimes, not a full staff history) · verification =
> **web-verify + move-graph** (2026-07-25).
>
> **★ Carry-forward caveats:**
> - **Three aggregates in the 2026 table were never externally verified** and the user signed off knowing it:
>   **10 new head coaches**, **McDaniel leaving the MIA HC job to be LAC's OC**, **56 % of HCs calling plays**
>   (18/32). Internal consistency ≠ factual accuracy — label 16.4 output accordingly.
> - **`pbp`'s coach field is game-level only through 2023.** From **2024** it is a season-level *coach of
>   record* (Dennis Allen shows for all 17 of NO 2024, Daboll for all 17 of NYG 2025, both fired in-season),
>   so `head_coach_scaffold()`'s `interim` column is a **lower bound** on mid-season changes. Fine for the
>   audit; not a source for "who was fired when" in 2024–25.
>
> **Useful method (reused, worked twice):** the **move-graph cross-reference** — each "X departs" must match
> an "X arrives", nobody holds two jobs in a season, a continuity flag must agree with the table's own
> history, and a spell must have no one-season holes. Zero external lookups. `coaches.move_graph_check()`
> grades findings `HARD:` / `check:` / `note:`; the merged table returns **12 findings, 0 HARD**.
>
> **Stage-0 chore: DONE 2026-07-24** (FFC 2026 snapshot banked, 6 configs, 1,202 rows, gsis 99.3 %, PASS;
> `backup_db.py` verified). Next due after **2026-07-30**.
>
> _(Prior pointer — history.)_ **★ Next-session pointer (2026-07-24, SESSION E IN PROGRESS — value-side situation track is an honest
> NULL; at the 16.3 review gate).** Completed T10 + Phase-16 value-side 16.1–16.2; drafted the 16.3/16.5
> CSVs; **16.4 is gated on the user reviewing `reference/coaches.csv`.** **NOT committed — left for user.**
> 316 tests (was 311), ruff clean; DEV-only, lockbox untouched, walled off from the frozen cost report.
> - **T10 ☑** — `validate_archetypes` prices the S6 `adaptive` archetype **per parent** (`adaptive(zero_rb)`
>   …); `steps/spine_4_validate.py` green.
> - **16.1 ☑ (NULL)** — `team_changed` (−2.5 VOR/SD, p_fdr 0.82) + `new_starting_qb` (−0.1, p_fdr 0.98) both
>   ruled out. **PIT catch:** the `adp_snapshots.team` column leaks an end-of-season crosswalk (Sep-1 2022
>   board lists mid-season trades McCaffrey→SF etc.) → team-of-record derived from `weekly` Week-1 instead.
> - **16.2 ☑ (BOTH WASH OUT)** — `competition_change_roster` (−9.9) and `competition_change_depth` (+9.8)
>   flip sign, neither survives FDR (p_fdr 0.087) → echoes Phase 12.3. Depth uses `depth_charts` (2014–24),
>   not `depth_charts_ts` (2025-only).
> - **Wall-off:** `FEATURES` pinned (5-trait softness model); situation flags in `SITUATION_FEATURES` /
>   `PHASE16_FEATURES`, mined only by `steps/phase16_1_*` / `phase16_2_*`. Phase-6 drift check reproduces
>   frozen `DURABILITY` +14.6 — cost report untouched.
> - **16.3/16.5 DRAFTED, awaiting review:** `reference/coaches.csv` + `reference/situation_events_2026.csv`,
>   both with a `confidence` column. **2026 web data was contradictory (esp. head coaches) — those rows are
>   flagged low/VERIFY.** **★ RESUME: user reviews/corrects `reference/coaches.csv` → then build 16.4 (scheme
>   fingerprint, `situation/fingerprint.py`, descriptive-only) → 16.6 tab defers to Phase 14.** Then Session F
>   (data 0.11 + drift 16.7–16.8). Value-side null means Phase 16's edge is the availability side.
>
> _(Prior pointer — history.)_ **★ Next-session pointer (2026-07-19, SESSION D COMPLETE — the engine is FINAL and the lockbox is spent).**
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
> changes model-side on the basis of this result.** **★ WHAT'S NEXT (revised 2026-07-19): Session E = Phase
> 16 — Situation-Change Beta Lab** (new, non-core research track, user request — mine whether ADP misprices
> "changed situation" events: team change, QB change, teammate competition change, coaching/scheme change;
> ship as a walled-off, read-only tab, never wired into the frozen optimizer/VBD/cost-report). **Scoped, not
> yet built** — 4 scoping questions answered 2026-07-19 (`PLAN.md`): competition-change is **dual-sourced**
> (roster-turnover-derived + depth-chart-derived, compared, since the depth-chart source already failed once
> in Phase 12.3); the coaching/playcaller history table is **Claude-drafted via web research, user-reviewed
> before use** (no free source exists); the scheme-fingerprint/transport piece ships **descriptive-only,
> explicitly unvalidated** (thin sample, no FDR gate); **this year's (2026) real situation-change events are
> populated now**, not deferred. Substeps 16.1–16.6 in `PROJECT.md` §5 / `ROADMAP.md`. **★ EXPANDED
> 2026-07-23 — Phase 16 now has a second, AVAILABILITY-SIDE track (substeps 16.7–16.12):** where 16.1–16.6
> ask "does a changed situation make a player *out-earn* ADP?", 16.7–16.12 ask the sibling "does narrative/
> situation make a player *drafted earlier* than ADP (draft-slot **drift**)?" — the fix for the user's UX
> failure (a target falls in 10 mock drafts, then gets sniped in the real draft). It **extends the
> availability/opponent model** (`draft/opponent_model.py`, `draft/availability.py`, `draft/simulator.py`),
> which is **already OUTSIDE the value lockbox** (predicts draft flow, walk-forward-scored) — so it doesn't
> spend/contaminate the frozen value eval. 4 decisions (user 2026-07-23): fold into Phase 16 · walk-forward +
> own held-out metric (momentum live-only on 2026 — no historical intra-season ADP series) · a curated
> `reference/hype_board.csv` override · BOTH realism (mocks) + advice (9.4 lookahead) + honest `P(available)`.
> Substeps: 16.7 drift panel (`adp/drift_panel.py`) · 16.8 drift model (`adp/drift_model.py`) · 16.9
> correlated per-draft narrative shock · 16.10 hype board (`adp/hype_board.py`) · 16.11 live momentum
> (`adp/momentum.py`) · 16.12 consumption. **★ ALSO ADDED 2026-07-23 — opponent-personality set (16.13–16.15),
> folded into the same availability track:** heterogeneous mock-draft opponents extending the existing
> `draft/personalities.py` (Phase 11.3, which already has 6 ADP/behavioral tilts but none on risk/value). The
> **5 headliners**: Autopilot (deterministic ADP autopick), Balanced, Upside Chaser (boom/q90), Safe/Floor
> (q10/durability), Homer/Narrative-Chaser (fandom + hype board — the seat the 16.9 shock rides). Decisions
> (user 2026-07-23): BPA = **ADP autopilot only** (no value-board opponent) · **enrich the sim board with the
> real frozen Phase-5 dist + value_board fields** (read-only) · validation = **face-validity + unit-tested
> mechanics** (no Brier gate). 16.13 board enrichment · 16.14 the personalities · 16.15 mock-room composition
> + hype coupling + app selector. Full scope: `PLAN.md` 2026-07-23 (personalities) + `PROJECT.md` §5 /
> `BUILD_PLAN.md`. Still awaiting
> go-ahead to build.
> **★★ BACKLOG EXPANDED + FULL SESSION RE-ORDER (2026-07-23) — the current source of truth for what's next.**
> User added 10 broadly-useful "better for all users" items (explicitly NOT anything personal to the user —
> league-mate/self models were excluded). **New Phase 17 — League-Format Fidelity** (superflex/multi-flex/
> custom-scoring/**platform-agnostic manual settings form**/keeper — correct advice for ANY league; a config
> generalization, NOT a modeling change; non-default formats labeled not-lockbox-validated). **New data 0.11**
> (ECR + Underdog ADP → feeds 16.8). **New 16.16** (live run-detection). **New Phase-14 surfacing 14.E–14.I**
> (tier-cliff / roster-risk / uncertainty / playoff-SOS / draft-grade — all read frozen machinery). Decisions
> (user 2026-07-23): new Phase 17 + distribute the rest · **app strictly last** (all UI/tabs/surfacing → Phase
> 14) · same ~1.5–2.2k one-concept sessions · **dependency-optimal order**. **★ THE SESSION PLAN (full detail
> in `ROADMAP.md` ★ SESSION PLAN): E** Phase-16 value-side 16.1–16.5 (+T10 warm-up; 16.6 tab→app) — **RESUME
> HERE** · **F** data 0.11 + drift 16.7–16.8 · **G** apply drift 16.9–16.12 + 16.16 · **H** personalities
> 16.13–16.15 · **I** Phase 17 formats 17.1–17.4 · **J** (optional) dynasty 15.1 · **K** Phase 14.1 MVP + all
> surfacing (do not bundle) · **L+** Phase 14 go-live tail. Lead pinned by: 16.8 reuses 16.1/16.2 features;
> 0.11 feeds 16.8. Scoping in `PLAN.md` (2026-07-23 backlog-expansion entry) + `PROJECT.md` §5 + `BUILD_PLAN.md`.
> **Prior pointer (Session E = Phase 16) still valid — value-side is the lead; the plan just now spells out E→L+.**
> **App-UI spec added 2026-07-23:
> `docs/PLAYER-VIEW.md`** — the interactive player card (hover → 5-bar overview) + per-player deep page
> (click → all 8 bars); quasi-bars over frozen contracts, green=good, dual-baseline (overall + within-pos),
> the Phase-16 situation bar walled-off + tagged unvalidated. Its **one gating dependency is bar #6 →
> Phase 16** (a further reason 16 goes next); it lands in the Next.js frontend at **14.3**, fed by a
> per-player endpoint at **14.1**. See `PLAN.md` 2026-07-23. Two commits landed locally
> (`7bd6e10` freeze, then the lockbox-result commit) — **not pushed** (user's review-then-push habit).
> Opportunistic tech-debt left: **T10** (the S6 `adaptive` archetype crashes
> `spine_4_validate`/`validate_archetypes` — worked around in the lockbox harness; fix before re-running the
> DEV cost-report — now folded into Session E as a warm-up). Run the Stage-0 FFC snapshot chore if >6 days
> stale (§2). **Resume: Session E = Phase 16 value-side 16.1–16.5 + T10 (awaiting user go-ahead to start
> coding). Full E→L+ ordering in `ROADMAP.md` ★ SESSION PLAN.**
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
