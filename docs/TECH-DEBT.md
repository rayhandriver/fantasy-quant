# TECH-DEBT.md — known problems & the exact plan to fix each (the remediation register)

The durable, dated register of every known problem in the engine and **exactly what to do about it in
the long run**. Opened after a full-codebase audit (2026-07-10). One entry per problem, stable id
`T1…T9`, newest facts appended in place. This is the "what do we still have to fix" source of truth;
`ROADMAP.md ★ THE PIPELINE` sequences these against the phase build, `PLAN.md` logs the work as it's done.

**Severity:** 🔴 loss/operational (fix now) · 🟠 validity (fix before the lockbox eval) · 🟡 quality (opportunistic).
**Status:** ☐ open · ◐ in progress · ☑ done · ✗ won't-fix.

At a glance:

| id | 🔺 | problem | when | status |
|----|----|---------|------|--------|
| **T1** | 🔴 | Phase 10 + Stage 0 work uncommitted | now | ☑ |
| **T2** | 🔴 | Irreplaceable data (2026 ADP series, 2025 backfill) has no backup | now | ☑ |
| **T3** | 🟠 | Downside under-modeled — unconditional coverage 44 % / points coverage 62 % | before lockbox | ☑ |
| **T4** | 🟠 | Season-sim level bias −137 pts/team/season | before lockbox (with T3) | ☑ |
| **T5** | 🟠 | Lockbox is a one-shot; researcher-degrees-of-freedom accumulating on DEV | pre-register right before lockbox | ☑ |
| **T6** | 🟡 | Monte-Carlo draws recomputed / silently diverge across consumers | with Phase 9.5 | ☑ |
| **T7** | 🟡 | External scrapes (FantasyPros/FFC) fail silently; props layer a no-op | opportunistic | ☑ |
| **T8** | 🟡 | `objective` a dead label (**8a ☑**); opponent model still ADP+noise (**8b: ingest+crawler+real corpus ☑, fit ☑**) | 9.5 done / fit done | ◐→☑ |
| **T9** | 🟡 | Phase 13.3 FAAB bidder is the **pragmatic** heuristic; rigorous auction theory deferred | Phase 15.4 (auction support) | ☑ |
| **T10** | ✅ | `validate_archetypes`/`spine_4_validate` sweep S6's `adaptive` archetype → crash (needs `adaptive_parent`) | opportunistic (post-lockbox) | ☑ 2026-07-24 |
| **T11** | 🟡 | (a) Underdog ADP never ingested (no keyless endpoint). **(b) drift corpus thinness — CLOSED 2026-07-26**: re-asked 16.8 on 1,144 drafts, verdict held | (a) opportunistic; (b) done | ◐ 2026-07-26 |
| **T13** | ✅ | Phase-5 distribution cloud was **not reproducible across processes** — per-player q10/q90 varied run to run; dress coverage wobbled 75.5↔76.5 %. **Cause found 2026-07-29 and it was NOT the coupling** the register suspected: DuckDB's *parallel float aggregation* is order-dependent, so the fits' training frames differed in their last bits between processes. Fixed with `db.deterministic_reads` around the assembler's reads (cost: none — 10.2 s → 9.1 s); 3 fresh processes now agree bit-for-bit (`steps/t13_reproducibility.py`) | before any per-player distribution number is published in the app | ☑ 2026-07-29 |
| **T14** | ✅ | 11.2 does not scale. **Diagnosis corrected 2026-07-26**: the bootstrap was 0.79 s (0.008 %); the cost was pandas in `simulate_survival` (99.3 %). Fixed both → **396 s → 12.7 s, bit-identical** | when 11.2 is next re-run at scale | ☑ 2026-07-26 |
| **T12** | 🟠 | `data_health_report` is **permanently red** — the ADP uniqueness gate's key omits `snapshot_date`, so the Stage-0 2026 series trips it (1,028 groups, 0 genuine dups) | soon — a red-by-default gate protects nothing | ☑ 2026-07-25 |
| **T15** | ✅ | simulated draft-slot dispersion is **the wrong shape in board depth** — **escalated + measured 2026-07-27** against 1,420 realized human drafts: round-1 mean reach **11.4 picks vs a realized 3.3** (p90 27.7 vs 6.6) and round-15 **15.0 vs 27.1**, i.e. ~3.5× too wide early and ~1.8× too narrow late. Elite players fall past the corpus's 95th percentile every draft, and the `autopilot` seats harvest the spill (they won this mock). Cause is arithmetic: ADP is worth **0.034 utility/pick** vs `is_TE` +0.57 and `need` +0.47, softmaxed over a fixed top-40 | **the user-facing blocker on mock realism**; an 11.1 respecification (measured exponent ~0.5–0.6, *not* log) | ☑ 2026-07-27 (**steps 0–4 all done**; row corrected 2026-07-29 — the section below was already ☑ while this line still read open. Residuals, both named and neither reopening it: the **late-round** half of bar 1 is structurally out of reach for a one-board simulator, and the seat-faithfulness population was closed the rest of the way by T24/T25) |
| **T16** | ✅ | **a curated hype row cannot express in a standard 15-round league** — `top_k` admits only the top-40 available by ADP, so a board-rank-171 claim enters the candidate set in the last handful of a 150-pick draft: a **+12-pick** claim on Daniel Jones gave a **bit-identical** 30-draft result. **Closed 2026-07-28 by T15's widening band, exactly as option (2) predicted** (re-run at 15 rounds: sign agreement **1.00** vs a 0.75 bar, elasticity 0.57 picks/claimed pick, **14 of 20 claims resolvable**). Honest residue: 6 deep claims still cannot express | dissolved by T15 (16.14R step 7) | ☑ 2026-07-28 *(index row added 2026-07-30 — the section was ☑ while the table had no row at all; cf. T15's stale row)* |
| **T17** | ✅ | **the live season has no per-player availability at all** — `availability_projection(con, 2026)` returned **0 rows**, collapsing the live Phase-5 `mean` to **37 % of the consensus projection**. Fixed by rolling the covariates forward (`projected_availability_frame`) + a **level-band guard** that now runs on the live season, where it breaks | before Phase 14 shows a user any distribution number for the season they are drafting | ☑ 2026-07-27 |
| **T18** | ✅ | `sleeper_manager_profiles.avg_reach` was measured against a **pooled** ADP board, so it reported a **+91.9-pick** mean QB reach — a board mismatch, not a behaviour. **Fixed 2026-07-29:** the column is **gone** (not renamed), replaced by `avg_reach_rounds` from `sleeper.redraft_reach` → `drift_panel.manager_panel` — every pick scored against **its own draft's board** over the redraft-eligible corpus. Mean \|reach\| **35.8 picks → 0.776 rounds**; scored properly, QBs drift **later** (−0.58 rounds), the opposite sign to the artifact. Range gate `validate.manager_reach_gate` (±2 rounds) wired into the health report | before `avg_reach` is consumed by a model or shown to a user | ☑ 2026-07-29 |
| **T19** | ✅ | **the `floor` signal is inverted at board depth** — `q10` is **censored at exactly 0 for 42.9 %** of offensive rows, so residualizing it on `mean` gives the biggest "floor" to players just above the censoring point: `corr(floor, adp)` = **+0.179 RB / +0.124 WR**. The safest RBs on the live board are Jonah Coleman (ADP 171) and Jaydon Blue (ADP 140). Also **`boom_prob`/`bust_prob` are exactly 0 for 64.7 % / 56.0 %** of rows, so `safe_floor`'s `bust_prob: −0.35` is inert over half the board | **before any personality consumes it** — 16.14R Step 2 | ☑ 2026-07-28 |
| **T20** | ✅ | **no roster-legality guarantee, and no DST exists on any board** — every mock seat finishes with an unfillable DST slot and `autopilot` averages **0.16 kickers**. `adp_snapshots` *has* the defenses (60 DEF rows for 2026 FFC PPR 10-team); `_ffc_board`'s `gsis_id IS NOT NULL` drops them because they key on `ffc_player_id`. `draftable_pool` enforces soft caps only — nothing forces a legal lineup | **user-facing blocker on the Phase-14 mock** — 16.14R Step 1 | ☑ 2026-07-28 |
| **T21** | ✅ | **K/DST are in the simulation candidate band but not the fit's** — `build_choice_frame(skill_only=True)` (the default the shipped β was fit under) restricts candidates to QB/RB/WR/TE, while `make_opponent_pick_fn` bands the whole board. The fitted β therefore nominates kickers it never saw (`value_hawk` took Brandon Aubrey at pick 119). **Session-G choice-set contract violation, second home** | with T20 (the fix is what makes putting DST on the board safe) — 16.14R Step 1c | ☑ 2026-07-28 |
| **T22** | ✅ | **`boom_prob`/`bust_prob` are four seasons stale on any live board.** They are `weekly_volatility(max(train_seasons))`, and `train_seasons` for a live season is `DEV_SEASONS`, which ends at **2022** — so the 2026 board carries the **2022** rates (verified: 100 % exact match on the 39 % that join) and **292 of the 306 zeros are `fillna(0.0)`**, i.e. a player absent in 2022 is recorded as *never busting*. Frozen Phase-5 contract, so it is logged rather than edited; 16.14R routed both seats that weighted it onto `tail_risk`. **Fixed 2026-07-29, and it was already reaching a human:** `steps/mock_draft.py` printed BOOM/BUST at every turn, so the live 2026 board told the drafter that Bijan Robinson and Puka Nacua *never boom*. `enrichment.live_volatility` adds `boom_prob_live`/`bust_prob_live` from **season − 1** (read-only; the frozen column is untouched), guarded by `volatility_source`'s recency assertion; the CLI now shows those plus `tail_risk`. Exact-zero `bust_prob` **56.0 % → 8.2 %**; corr(frozen, live) **0.026** | before any *new* consumer weights it, and before Phase 14 shows a boom/bust number to a user | ☑ 2026-07-29 |
| **T23** | ✅ | **the T20 roster-legality guarantee misses TE** — `mandatory_needs` dropped every position in `slots.flex_positions`, and TE is in that tuple because a TE may *fill* FLEX, not because anything may fill TE. **12.1 % of seats finished unable to field a lineup, 100 % of them missing a TE** (46 % of `autopilot`, 47 % of `chalk`) | **user-facing** — 2×5 mock objection 1 | ☑ 2026-07-28 |
| **T24** | ✅ | **consensus elites fell past pick 4 26.6 % of the time against a realized 13.1 %** (seating-marginalized), and the aggregate \|drift\| bar could not see it. The ticket's prescription — a per-seat `adp_stdev`-scaled **private board** — was built and **REJECTED: it is monotonically harmful** (18.8 / 19.7 / 26.6 % at κ = 0/1/2), because at the top of the board `adp_stdev` is the same size as the gaps it perturbs. **The fix was the width *level*, split from the width *shape*:** `WidthCurve(base 1.0·γ0.8) → (base 0.6·γ1.0)` → **15.3 %**, every T15 bar still passing. Round 1 was too wide, not the wrong shape | **the user-facing blocker on mock realism** — 2×5 mock objection 3, T15's carry-forward | ☑ 2026-07-28 |
| **T25** | ✅ | **the corpus reach ceiling was applied to 2 of 10 seat types**, so `CORPUS_REACH_P95` bound `reacher`/`value_hawk` — the seats that had been *given* discipline — and nothing bound `balanced`, which is 4 of 10 seats in `REALISTIC_ROOM`. The asymmetry was the bug, not the budget | with T24 (it is T24's cheap half) — 2×5 mock objection 2 | ☑ 2026-07-28 |
| **T26** | 🟡 | **`pos_share_*` is pooled across formats while the fit that consumes it is redraft-only** — T18's sibling, found in the same audit and *not* fixed with it. The profiles are built over every complete human draft (dynasty, 2QB, IDP included); `mgr_lean` — a live Tier-B feature of the shipped β — is `share − mean(share)` over that table. Measured: mean \|Δ QB share\| **0.83 pp** across the 2,816 managers in both scopes (>5 pp for 3.3 %), and the pooled *baseline* is the bigger distortion (QB 13.65 % pooled vs 11.22 % redraft), though a constant per-position offset is largely absorbed by the position dummies | with the next 11.1 refit — **not before**: changing it refits β and moves every T15/T24 width bar, which is a whole session's calibration for a sub-1 pp feature shift | ☐ 2026-07-29 |
| **T32** | ✅ | **the enriched-board cache key omits the board vintage, so the mandated Stage-0 chore does not invalidate it.** `mock.room_board` caches on `(season, scoring, teams, include_dst, ENRICH_VERSION)` — nothing about *which snapshot* `resolve_board` answered with. Measured live on 2026-07-30, immediately after running the chore: `resolve_board` returns **244** rows and `room_board` serves the cached **223**, with **25 players on the fresh board invisible** to every caller and 4 stale ones still present. `ENRICH_VERSION` exists to force exactly this kind of rebuild and covers the enrichment but not its input. It bites hardest in-season, when the chore runs weekly and the boards diverge fastest | fix with the next batch measurement (the key change invalidates all 9 season caches → ~6 min/season cold). **Deliberately NOT fixed on 2026-07-30**: Session H.5's central claim is bit-identity against caches built before it, and invalidating them at the close would have made that claim unverifiable | ☐ 2026-07-30 — **still open, but its stated cost has already been paid.** T31 bumped `ENRICH_VERSION` to `v4-t31-level-cap` on 2026-07-30, so all nine caches were rebuilt anyway (~35 min) and the stale 07-24 2026 board is gone: the v3 and v4 parquets are **byte-identical for every historical season** and differ **only on 2026**, which is the vintage change this ticket is about. The deferral reason (H.5's bit-identity claim rested on the pre-existing caches) has also expired. Fixing the key now costs one more rebuild | **☑ 2026-07-30 (Session K1 step 0).** `mock.board_vintage(raw, src)` — `source` + the board's single `snapshot_date`, which names it completely because `_ffc_board` closes with `QUALIFY snapshot_date = MAX(...) OVER ()` — is now in the cache filename, plus a row-count guard that rebuilds rather than serves when a snapshot is edited under its own date. New `validate.board_vintage_gate` in the health report; 4 tests in `test_mock.py`. **Honest note on the measurement: by the time it was fixed the gate already passed** (244/244) — T31's `ENRICH_VERSION` bump had rebuilt the 2026 cache hours after the Stage-0 pull, so the 25 invisible players were gone by accident. The v2/v3 parquets still hold 223 rows and the v4 one holds 244, which is the defect and its accidental repair both on disk. So the fix was verified by **reverting the key and re-running the tests**: both mechanism tests fail on pre-T32 code with exactly the right error. *A coincidence that makes a bar pass is not a fix, and the control is what tells them apart.* |
| **T31** | ✅ | **on a LIVE board the Phase-5 level correction inverts for players consensus projects as backups — 22.8 % of the 2026 value index carries a *negative* haircut** (`mean` **above** `proj_points`, structurally impossible for a level correction) against **0.4 % on 2024**, and the per-position `spearman(haircut, games_played_mean)` flips sign (QB **+0.474** with 59 % negative, RB +0.225, TE +0.237). Inside the drafted range it is milder but still fails T27's pre-registered bar at **RB −0.288** (vs −0.50; QB −0.902, WR −0.538, TE −0.838 all pass, and every position passes on 2022/2024). **Cause: consensus prices ROLE, our level correction prices AVAILABILITY.** For a projected starter the two coincide; for a backup consensus says 22 points because he sits behind someone while the Phase-5 level — with no prior-season basis to shrink toward on a live season — hands him a starter-ish per-game rate times ~11 expected games (worst case `proj 22.3 → mean 102.9, sd 78.2`; sd ≈ mean is the fingerprint of a distribution built on nothing). Conditioning on `vbd ≥ 0` repairs it outright (RB −0.288 → **−0.599**, WR → −0.912), which is the confirmation. Rookies ruled out (non-rookie RB ρ −0.32) | **before Phase 14 shows a distribution number for a deep player**, and before anything downstream trusts `mean` off the drafted range. T27's `validate.value_scale_gate` ships **red** rather than softened | ☑ 2026-07-30 — **fixed, and the register's filed cause was WRONG** (the third in a row after T13/T24). There is no live-vs-historical branch in the fit: `train_seasons` is 2014–2022 for a **2024** board *and* a 2026 one, so the QuantReg models are **identical** and the defect is entirely in the **board**. Real cause = **linear extrapolation far below the support of the fit**, exposed by the live board running much deeper than any proxy board — median 2026 QB `calibrated_mean` **11.4** against a training *minimum* of **34.1**, **56.4 %** of 2026 QBs below support vs **2.3 %** on 2024 — with the low end *additionally* selection-biased upward (the fit's cohort is `weeks >= 0.85*season`, so a low-projection player in it is one who won a job). Fixed by `quantile.consensus_level_cap`, gated on `value_board.source` (a column already in the frozen 4.2 contract): a live-board row whose assembled `mean` exceeds `proj_points * avail_p / g_ref` is scaled onto that target. All six pre-registered bars PASS — negative-haircut share **38.75 % → 0.00 %**, drafted-range rho **RB −0.288 → −0.667** (QB −0.906 / WR −0.904 / TE −0.889), full-board rho **QB +0.474 → −0.980**, max `sd/proj` **23.06 → 0.90**, and 2022/2023/2024/**2025** **bit-identical** so the spent lockbox stands and the calibration holdout is **never read**. Top-24 ADP **untouched (0 % of rows)**; the effect ramps 2.9 % (ADP 25–60) → 96.5 % (undrafted). |
| **T27** | ✅ | **the board a human reads and the board every seat optimizes are different quantities, and they disagree by up to 179 points.** `steps/mock_draft.py` prints `PROJ` = `proj_points` (consensus, re-scored full-PPR); utility and the value hawk's objective run on `base_value` = `ce_vbd` = Phase-5 CE − positional replacement. On the live 2026 board **Drake Maye (proj 316.5) carries `base_value` +68.5 while Jayden Daniels (proj 313.4) carries −101.6** — 3 points apart on screen, 170 apart in the number that drives every pick. The mean haircut (0.28 QB / 0.33 RB / 0.28 WR / 0.30 TE) is the *intended* level correction; the **dispersion** (QB range 0.15–0.56, sd 0.12) is what makes the board unreadable. Nothing on screen explains which players get cut | **the user-facing blocker on the mock board** — Session H.5 step 1; display-layer only, the frozen stack does not move | ☑ 2026-07-30 — **shipped**; the value chain is on the board and `why` prints it. Also caught a divergence nobody was looking for: the *interactive* room ran `value_hawk` as `balanced`. Its gate **B2 FAILED at RB on the live board** and that failure is real → **T31** |
| **T28** | ✅ | **`team_value`/`portfolio_value` are slot-blind, so a bench QB2 is priced as if he starts.** `team_value` sums `base_value` over all 15 roster rows and nothing in `draft/optimizer.py` references starters. On the 2026 walkthrough the second QB alone moves a team's headline value by **−101.6** (T1 Caleb Williams), **−92.1** (T4 Kyler Murray) and **+51.0** (T3 Hurts), against a room total of 1,938 — the QB2 line nets **−122**. Consequence, measured over the same ten teams: Spearman(portfolio CE, title) **+0.758** and Spearman(VBD, title) **+0.685** against Spearman(starting-nine Phase-5 mean, title) **+0.915**; T4 is **9th of 10 on VBD and 3rd on starting-lineup projection**. It is not only a reporting artifact — `value_hawk` *maximizes* this quantity, and took Jaxson Dart (`base_value` +33.1) as a second QB at 9.09 | Session H.5 step 2 — **a decision, not a patch**: the frozen cost-report headline must not move, so a starter-aware metric ships **beside** it | ☑ 2026-07-30 — **closed as a LABELLING FIX, as pre-registered.** `starter_value` ships beside `team_value` and every surface prints both. **B5 failed** (−0.0230, CI[−0.0407,−0.0055] over 200 drafts): the slot-blind sum predicts title probability *better*, because bench value alone scores +0.711 in a sim that draws injuries. `value_hawk` keeps `objective=portfolio_ce` |
| **T29** | ✅ | **absolute probabilities are printed from a sim whose level bias is documented as −113 pts/team.** Any driver that calls `league_probabilities` prints `playoff_prob`/`title_prob` as bare percentages. The lockbox recorded title Brier **0.088** with reliability on-diagonal (ordering and championship calibration hold) but playoff Brier **0.240** as *marginal*, unconditional coverage **72–77 %**. So the weakest number in the stack is the one a user reads as fact | Session H.5 step 3 — labelling + a fair-share ratio | ☑ 2026-07-30 — `PROB_PROVENANCE` + `fair_share`/`playoff_fair_share` + `assert_probability_sums`; every driver leads with the multiple (0.170 → **1.70x**) |
| **T30** | ✅ | **`autopilot` is 1 of 10 seats against 0.2 % of realized seats — 50×**, and it is the seat that manufactures the spill the rest of the room harvests (walkthrough: mean `pool_rank` **1.77**, median **1.0**, harvest **+11.7 picks**, the largest in the room). 16.14R halved it from two seats *on this exact argument* and stopped there; bar 3 passes at +0.06 sd, so this is a **composition question that has never been argued explicitly**, not a known defect | Session H.5 step 4 — a cheap seating-marginalized A/B against a near-autopilot seat; **accept or change the mix, but state the argument** | ☑ 2026-07-30 — **argued and NOT changed**, under the pre-agreed rule (ship only if every bar holds or improves). The `chalk` swap closes **79 %** of the chalk-share gap (11.0 → 2.4 % vs a realized 0.2 %) and 63 % of the moderate-share gap, and costs **+0.0021** profile distance and **+0.97 pp** elite-past-10. Every gate passes both ways; bar 3 harvest is **0.00 in both**, so the spill the seat manufactures is not being harvested |
| **T34** | ☑ | **every mock draft is the same mock draft.** `app/engine.start_draft` defaults `seed=7` and `room_seed=None`, which freezes *both* sources of variation — the pick RNG and the seating — so a user re-drafting his slot gets the identical room, the identical picks and the identical story every time. Reported by the user from the live app (seat 6 always opens Gibbs · Chase · Taylor · McCaffrey · Cook) and **reproduced exactly**: same seed twice is identical, `seed=8` gives Gibbs · Nacua · Jeanty · Bijan · Chase, `room_seed=3` gives McCaffrey first. The engine is fine and the personalities *are* sampling — **the human-facing default is the measurement default**, and practising against one frozen draft is worse than not practising | **now** — it defeats the purpose of the mock drafter, which is repeated practice. Session K1.5 step 0. ⚠ **`steps/` must not move**: T24's sweep, 16.17's mapping check and every committed bar sheet are differenced against `--seed 7` | ☑ 2026-07-31 |
| **T35** | ☑ | **`st.tabs` executes every tab body on every rerun** — it hides inactive tabs client-side, it does not skip them. `app/main.py` calls `tab_settings()`, `tab_board()`, `tab_draft()` and `tab_cost()` unconditionally, so one keystroke in the draft room's player box also re-runs the cost tab's `_prepare_board` and its ADP-sorted option-label build over the entire board. Wasteful today; **a hard blocker on the 14.M pick clock**, which reruns on a timer and must rerun one fragment, not four tabs | with 14.K (Session K1.5 step 1) — the fix is `st.navigation`/`st.Page`, which the user asked for on ergonomic grounds independently | ☑ 2026-07-31 |
| **T36** | 🟡 | **no automated bar covers the board's row-selection path, and therefore not the player modal.** `st.dataframe(on_select="rerun")` is a *client* event: `AppTest` can click a button and set a widget value, but it cannot make a selection in a dataframe. So the two things a K2 drafter does most on the board — select a row to load the confirm bar, select a row to open the PLAYER-VIEW card — are exercised only by the pieces around them (`session.player_card` is unit-tested for content, `resolve_pick` for the typed path, and FLOW proves every page renders). This is the same shape as the gap K1 shipped through: *an import bar and a use bar are different claims*, and here the use bar stops one layer short of the click | opportunistic. The honest options are a real browser driver (Playwright — a new dev dependency and a slow bar) or a selection-independent duplicate control that would exist only to be testable, which is worse. Revisit if row-select ever carries a number rather than a navigation | ☐ 2026-07-31 |
| **T33** | 🟡 | **`make_value_hawk_pick_fn(n_teams=)` receives the ROOM size, not the league size** — both room builders pass `len(seats)`, so the *interactive* room (9 modelled seats) scales the value hawk's `_local_z` context weights by **9** and the *batch* room by **10**: the same seat prices step-3 context ~10 % apart depending on which harness it is sitting in. Pre-existing since 16.14R step 6, and 16.17 only made it visible — with k human seats the divisor becomes `10 − k`, so it now varies with the room shape rather than being one of two constants | **Session VH.1** *(scheduled 2026-08-01)* — the room measurement it was waiting for is now booked, and T33 sits directly in the path of the user's `value_hawk` objection: the seat he is judging is measurably not the seat that was measured. **Deliberately preserved verbatim by 16.17**, whose entire done-bar is bit-identity against both builders; fixing it changes the shipped room's picks and needs the full T24 seating-marginalized before/after as its own sub-step | ☐ 2026-07-30 |
| **T37** | ☑ | **the 16.12 reach-risk readout is hidden behind a collapsed expander, directly beneath a docstring arguing that it must not be.** `app/draft_room._reach_risk` opens with *"it renders inline rather than behind a button: a readout you have to ask for is a readout nobody asks for"* and then calls `st.expander("Who will still be there at your next pick?", expanded=False)`. The docstring is right and the code contradicts it. This matters more than a normal display slip because **`P(available)` with an un-drifted baseline is the one thing in the app no competitor ships at all** (FantasyPros' Pick Predictor has neither the baseline nor a validation claim), it had no surface at all between Session G and K2, it costs ~20 ms, and the two-line prose caveat around it is the *only* thing a drafter sees | **Session UI-1 step 0**, with S6 — out of the expander and into the right rail permanently, plus `P(THERE)` on the **slim** board, which under a clock is more decision-relevant than `PROJ`. Bar B5 asserts the slim column **is** `reach_risk_view`'s own number (one derivation, two placements) and that no expander sits in its render path | ☑ 2026-08-01 (Session UI-1 step 0) |
| **T38** | ☑ | **`app/post_draft.py` ships a raw JSON dump in a user-facing page.** `c1.json(frames["elite"])` (and its sibling column) render the elite-fall frame as pretty-printed JSON under the heading *"Elite fall (consensus top-12)"* — a debug artifact that survived into 14.N because the readouts were *moved* from the room page rather than rewritten. It is not wrong, it is unreadable, and it sits on the page whose entire job is to be a report card | **Session UI-1 step 0**, with A6 — a titled table, and the page led by **grade letter · title fair-share multiple · STARTABLE rank** (T29's ordering: the multiple leads, because the sim's documented −113 pts/team level bias is survived by the ratio and not by the percentage). Bar B6 asserts **zero** `st.json` calls remain in `app/` | ☑ 2026-08-01 (Session UI-1 step 0) |
| **T39** | 🟠 | **the overlap-based tier column — the UI plan's one differentiated feature — does not cut the live board, and the figure that sold it hides its own denominator.** Measured 2026-08-01: **1 tier per position** (62 RBs in one tier), **2 over the whole board**. Cause (a) **scale** — the median RB 80 % band is **228 pts** against a median adjacent gap of **16.3 pts**, so overlap is universal by construction; cause (b) a **category error** — Boris Chen clusters expert rank *dispersion*, we hold a *predictive interval*, and UI-PLAN calls them the same thing. ★ And `COIN`'s published **146 of 199** conflates *distinguishable* with *unknown*: only **147** pairs have both bands, **146** of those overlap, **1** is a genuine break and **52** are missing bands — the honest figure is **99.3 % of evaluable pairs overlap** | **when it is worth a modelling session**, not a display one: a 1-D clustering with model selection, run on a rank-**dispersion** quantity (`adp_stdev` is on the board already), never on a season-points interval. ⚠ The gap cut is **not** a fallback — a threshold at the median is exceeded by half of all pairs *by definition* | ☐ 2026-08-01 — **nothing shipped**: no `TIER` column on any view, `session.tier_series` runnable and unwired with both cuts, mechanism pinned by a unit test, and `coin_flags` + the `COIN` entry now carry the decomposition |
| **T41** | 🟠 | **a bar sheet records no vintage for the live board it was measured on, so the mandated weekly Stage-0 pull is indistinguishable from a regression.** Measured 2026-08-01, immediately after the chore banked an `ffc-20260801` board: UI-1's and UI-2's B0 went from `all_pass: True` with **zero** unclassified leaves to **122 unclassified in K1's sheet and 23 in K2's** — `app_summary[0].who: 'autopilot' → 'YOU (T7)'`, `grades.YOU: 'C+ 59' → 'D+ 39'`, `adjacent_overlapping_pairs: 146 → 150`. **Nothing broke**: every nested sheet still passes its own bars (`k1/k1_5/k2_all_pass: True`), the ADP board simply moved (3 arrivals, 2 departures, 91 players >2 picks) and the drafts played out differently. But `_ALLOWED_MOVES` classifies display counts, entropy, timings and column lists — it has **no category for *the input moved*** — so B0 fails by construction after every chore run, and the operator must re-derive by hand each week whether the cause was the board or the code. **This is T32 one level up**: there the cache key omitted the board vintage, here the *control* does | **before the next board-dependent session**, and it is cheap: stamp `mock.board_vintage(raw, src)` into each sheet, then have `_classify_moves` report `vintage_changed` and bucket board-driven moves under it — *not* a blanket allowance, which would delete B0's whole purpose. ⚠ Do **not** widen `_ALLOWED_MOVES` to swallow these leaves | ☐ 2026-08-01 — reported, not fixed; pre-pull sheets preserved at `analysis/session_ui_{1,2}.pre_ffc20260801.json` |
| **T40** | 🟡 | **a bar control that can be satisfied by a single observation, and was.** UI-2's B3 requires `every_glyph_fired_at_least_once` so the row-by-row glyph identity cannot pass vacuously — a good control, and on the 07-30 board `handcuff` fired **exactly once** in 40 rows (`{'bye': 6, 'stack': 8, 'handcuff': 1}`). The 08-01 board took it to **zero** (`{'bye': 13, 'stack': 12, 'handcuff': 0}`) and B3 flipped to FAIL. **Every correctness claim in the bar still holds** — `mismatched: []`, `FLAGS` byte-identical, unknown byes still unknown, zero week-0 rows — so the failure is the control's sampling, not the glyph logic. A control whose n is 1 is one board refresh from reporting a defect that does not exist, which is the same alarm-fatigue failure as T41 and arrives from the opposite direction | with the next UI session. Fix by **constructing** a roster that guarantees each glyph fires (the lead-back + handcuff pair is deterministic from the depth chart) rather than hoping the sampled rows contain one; keep the control, do not loosen it into a pass | ☐ 2026-08-01 |
| **T42** | ✅ | **the value hawk maximizes a slot-blind objective** — ANSWERED 2026-08-01 (Session VH). The diagnosis is **partly right, its flagship evidence is wrong, and its prescribed fix is blocked by its own bar.** The **TE2** this entry leads with is changed by **no** ablation — **TE is flex-eligible**, so a TE2 is a legal starter, not bench depth; the slot channel owns **QB2** only, and the entry pooled two things. **B1 = 38 %/29 % slot-driven → INCONCLUSIVE**; the **dominant** channel is the reach **window** (6 of 7–8 objected picks), which is also what the user's own labels track (`corr(reach, bad) = +0.767`). The interventional A/B (200 seat-shuffled drafts × 4 DEV seasons) then found **realized points and the sim's title probability disagree in sign**: `starter_aware` is **+50.4 realized** and **−0.295 title ×** with every shape measure improving, so **B3 blocks it on the metric we least trust** — recorded as a **finding about the sim** (T28's bench↔title link is the sim's, not the world's) and filed with the −113 pts/team level bias, **not acted on**. `blend_50` (bw 0.5) passes B3 | **closed as answered.** What is left is a *seat-character* ship decision for the user (`blend_50` needs a new per-`Personality` `bench_weight` seam; `RiskModel` carries it today and the room builds one model for all seats), plus the VH.3 window preference — both priced, neither chosen by argmax | ☑ 2026-08-01 |
| **T43** | 🟡 | **the value hawk's step-3 context term is scaled by `state.n_teams`, and nothing derives that.** `eff` is a priority rank and `_local_z` is a z-score, so the multiplier is a ranks-per-SD conversion; a league's team count is not that conversion, it is just the number that was there. VH.0 measured the consequence: against the whole pool the term is `sd(context)/sd(eff)` = **0.08** (negligible), but against the **contended top-10** — the only rows an argmax is decided between — it is **0.29–0.34 of the spread** and changes **6 of 15 picks**. *A term calibrated against the wrong dispersion looks small right up until it decides the pick*, which is how it survived 16.14R, T24, T27, T28 and 16.17. T33 fixed *which* count it is and made *why a count* visible | **with the next 11.1 refit, alongside T26** — re-derive the scale from what it should buy (a signal worth *k picks* of board position, the conversion `reach_cap` already does through the model's own ADP coefficient), then **refit `DEFAULT_CONTEXT_WEIGHTS`**, which absorbed the old scale. ⚠ Not before: the weights and the scale are one object | ☐ 2026-08-01 |
| **T44** | ✅ | **there is no `schedules` table in the store.** Session K2's 14.F bye-week readout needed a schedule and there was none, so it takes byes out of `ecr_snapshots` — a *ranking* feed — and that workaround is still shipping. Byes are consequently unknown for any player without an ECR row, which the surface honestly renders as unknown rather than as week 0, so nothing is wrong on screen; the defect is that a first-class fact about the season is being inferred from a third-party board that has no obligation to carry it | **Session DATA-1 / 0.12.6** — ingest the `schedules` release (small, full history) and repoint 14.F. It is also the cheapest real proof of the 0.12.1 loader | ☑ 2026-08-03 — `schedules` landed (7,548 games, 1999–2026) and `small.bye_weeks(con, season)` derives byes from the fixture list: **32 teams, exactly one bye each, weeks 5–14, in 2023/24/25 and 2026**. The 14.F repoint off `ecr_snapshots` is a one-line app change left for the next app session |
| **T45** | ◐ | **`ngs` is ingested and effectively unread — 26,723 weekly rows, 2016–2025, one consumer.** `data/panel.py:93` reads `stat_type='receiving'` only; **no `features/` module reads the table at all**, so the 48-column exposure matrix is built from `weekly`/`pbp`/`snaps`/`combine`/`game_lines`/`player_ids` and `percent_attempts_gte_eight_defenders`, `avg_separation`, `avg_cushion`, `rush_yards_over_expected_per_att`, `avg_yac_above_expectation` and CPOE are banked and unused. Ten seasons of the exact micro-detail the 2026-08-02 deep-dive scope is about, already on disk, already PIT-clean, already paid for. **It survived because nothing anywhere records a table's consumers** — the same blind spot as T22 (*a column's consumers are not only the models that weight it*), one level up: there the audit missed the display layer, here it missed that there was no reader at all | **register it in DATA-1 (0.12.2, the inventory carries a consumer column), wire it in M-1** — deliberately two sessions, because wiring changes a matrix that downstream models read and needs its own bars | ◐ 2026-08-03 — **register half ☑, wiring still open.** `reference/DATA-SOURCES.md` now carries a **readers** column and independently reproduces the hand-found result: `ngs` = **1 reader** (`data/panel.py`), zero in `features/`. ⚠ The column's *first* version counted any mention and reported **zero** unread tables — the ingesting step mentions a table more than anyone (UI-1 lesson 2). Split into producers/readers/tests, and a file can be both. **M-1 still owes the wiring.** |
| **T46** | ✅ | **the frozen `nfl_data_py` wrapper is our ingest ceiling, and we have been reading it as the data's ceiling.** The package is a wrapper over `nflverse-data` GitHub release assets; anything it does not expose is invisible to us. Already bit once and written off as a one-off — Phase 0.9's *"nflverse restructured stats releases post-2024; frozen `nfl_data_py` hits the dead old path"*. It is the general case. Verified 2026-08-02: **`pbp_participation` (2016–2025, play-level — `defenders_in_box`, `offense_personnel`, `defense_man_zone_type`, `route`, `was_pressure`, and the gsis IDs of all 22 players on every play) has no wrapper function and is absent from a store with sixteen tables.** Every future nflverse release is invisible on the same mechanism | **Session DATA-1 / 0.12.1** — a direct release-asset loader beside the wrapper (not replacing it; it is the provenance of sixteen tables), with the bit-identity control on an already-ingested table. Permanently decouples us from the wrapper's release cadence | ☑ 2026-08-03 — `data/sources/nflverse_release.py` ships beside `nflverse.py` (untouched, still the provenance of sixteen tables). B1: `combine` reproduces **bit-identically** through the new path (4,080 rows, dtypes included) with **two** negative controls — wrong-asset *and* single-perturbed-cell, since the first only proves schema detection. 25 release tags reachable; `participation` + `ftn_charting` + 13 small sources landed through it |
| **T47** | 🟠 | **`pfr_pass`, `pfr_rec` and `pfr_rush` are ingested and read by NOTHING — three more T45s, found by the instrument built for the first one.** 7,798 rows of PFR advanced receiving/rushing/passing charting (2018–2025: aDOT, YAC, broken tackles, air yards, pressure) sitting on disk with **zero readers** in `src/`, `steps/` or `app/`. The 48-column exposure matrix does not touch them. They cost a scrape, a source module and a place in the Phase-0 story, and then nobody wired them up. **The pattern is now confirmed as systemic rather than incidental**: T45 was not a one-off any more than T46's wrapper ceiling was — *a store with no consumer register accumulates paid-for, unread tables silently*, and this repo has now found four | **M-1, with the NGS wiring** — the same session, the same bars, and for the same reason: both change the exposure matrix that the rookie ridge, the QuantReg fits and the Phase-6 softness regression read. ⚠ Do **not** wire them opportunistically inside a data session | ☐ 2026-08-03 |
| **T48** | ☑ | **there is no defensive play-caller regime table, so every defensive scheme fact in the store is person-anonymous.** `reference/coaches.csv` is offense-only by construction — `season, team, head_coach, offensive_coordinator, play_caller, hc_calls_plays, in_house, confidence, notes`; 204 rows, 32 teams, 2014–2026, **48 distinct play-callers, zero defensive attribution.** DATA-1 banked 478,989 participation plays carrying `defense_personnel`, `number_of_pass_rushers`, `defense_man_zone_type` and `defense_coverage_type`, and none of it can be assigned to a coordinator, a tenure or a regime. Consequence: `situation/fingerprint.py`'s whole apparatus — within-season z-scoring, EB shrinkage by regime length, PARTIAL-season week-pinning — **has no defensive counterpart to run on**, and the user's defensive deep dives have no subject. ⚠ **No free source**, exactly as `coaches.csv`'s own header says of itself (*"THE ONE PIECE WITH NO FREE SOURCE"*) — this is research plus a review gate, not a download | **Session DATA-2 / 0.13.1** — `reference/defense_coaches.csv` + `reference/defense_lineage.csv`, copying every discipline from `coaches.csv` (majority-of-games rule, PARTIAL pinned or dropped, `head_coach` auto-filled from `pbp` and PIT, `in_house`, explicit sentinels, per-row confidence, **user sign-off gate**). ⚠ `base_front`/`coverage_identity` stay **out** of the CSV — derivable from 0.13.2, and the 16.5 rule says a question a feed can answer gets no human maintainer | **☑ 2026-08-03** — `reference/defense_coaches.csv` 153 rows (121 historical + 32 signed-off 2026), 33 play-callers, 52 regimes, 0 pbp audit mismatches; `defense_lineage.csv` 4 mentor rows. 0.13.8 fingerprints **26 defensive play-callers over 116 regime-seasons** on the *same* EB machinery (one optional `metrics` arg; every prior caller unchanged). Face-valid: Bowles +1.14 blitz, Spagnuolo +0.59 man, Quinn +0.77 man |
| **T49** | ☑ | **upstream floors are registered per TABLE, and they are a property of the COLUMN.** `reference/DATA-SOURCES.md` lists participation's floor as **2016** — correct for `offense_personnel`, `defense_personnel`, `defenders_in_box` and `offense_formation`, and **wrong for coverage**: `defense_man_zone_type` and `defense_coverage_type` are **0.000 in 2016 and 2017**, ~0.38 for 2018–2022, ~0.49 for 2023–2025. Their true floor is **2018**. With `DEV_SEASONS` = 2014–2022 that is **five** development seasons of man/zone, not seven — and getting this arithmetic right is the entire reason DATA-1 wrote floors down (*"stop re-investigating these"*). A floor recorded one level too coarse is worse than no floor: it is confidently wrong at the grain a query is actually written at | **Session DATA-2 / 0.13.9** — make the floor per-column in the register and in `data/registry.py`, and have the floor assertion name the column it tripped on. B6: a man/zone request for 2016 **raises**, naming 2018 | **☑ 2026-08-03** — `registry.COLUMN_FLOORS` + `column_floor` + `assert_column_floor`; the error names the column AND how it differs from its table. Declared floors are checked against the **measured** ones from the break map (a declaration nothing checks is a note). `team_scheme_columns` carries a per-column floor + PIT class + break provenance + per-season fill for all 190 panel columns |
| **T50** | ☑ | **from 2023 the participation vendor stopped emitting NULLs and started emitting SENTINELS, and the fill-rate gate is structurally blind to it.** Verified in the parquets 2026-08-03: `was_pressure` in **2022** = 31,207 null / 13,425 False / 5,518 True; in **2024** = **14 null** / 38,838 False / 7,067 True. `number_of_pass_rushers` = 72 zeros in 2022, **23,754** in 2024. Non-pass plays used to be NULL and are now `False`/`0`, so the unconditional fill rate reads **0.38 → 1.00** across the break while the column's meaning inverts underneath it. **Three independent reasons the gate cannot see this:** (i) `validate.store_fill_rates` measures the *nonnull* share, and a sentinel counts as filled; (ii) `validate.fill_rate_gate` fails only on drops (`if was - rate > tol`) and this is a **rise**; (iii) the gate is **whole-table, not per-season**, so a mid-history break averages away regardless. The instrument written to catch `ngs_air_yards` silently going to zero is blind to the exact opposite failure — **and the opposite failure is the one actually present in the data the mining program exists to mine.** A blitz rate computed naively across 2022→2023 reads as a league-wide scheme revolution that is entirely an encoding change. **This is T45 one level up**: there nothing recorded a table's consumers, here nothing records a column's *encoding*, so a re-encoding and a real trend are indistinguishable from outside. NB `participation.fill_rates()` does compute conditional rates correctly — the defect is in the **gate**, not the register's reporting | **Session DATA-2 / 0.13.0, before any other substep** — `data/breaks.py`, a probed per-`(table, column, season)` map of `observed`/`sentinel(<value>)`/`absent`; every rate routes its denominator through it; `fill_rate_gate` becomes **two-sided and per-season** and gains a distributional check (null share collapsing while the modal value's share explodes = a re-encoding, fail). ⚠ **Classify the break, do not smooth it** — a normalization that makes the discontinuity vanish without recording it is the same defect as the gate that cannot see it. B1/B2: the map must find the 2023 break **unprompted** and flag a planted synthetic sentinel, and the naive-vs-gated blitz rates must differ by a **stated** amount | **☑ 2026-08-03** — `data/breaks.py` + `validate.{store_fill_rates_by_season,fill_rate_gate_by_season,encoding_break_gate}`. B1 found the 2023 break unprompted and flagged a planted sentinel; **B2: naive league blitz 0.2803→0.1311 across the seam vs gated 0.2806→0.2638**. Found 4 sentinel columns, not the ticket's 2. ⚠ **But see T52** — the detector is blind to two OTHER encoding seams this session met |
| **T51** | 🟠 | **`pfr_rec.td` and `pfr_rush.td` are 100 % NULL from 2024** — 518/518 populated through 2023, 0/523 in 2024 and 0/531 in 2025 (same for `pfr_rush`: 346/346 → 0/341 → 0/349). This is the `ngs_air_yards` silent-degradation mode again, in tables **T47 already flags as ingested-and-unread**, which is why two seasons of receiving and rushing touchdowns went missing with nothing noticing. **★ The standing gate can never fire on it**: `store_fill_rates` is whole-table, so the recorded baseline is `td = 0.7448` — six full seasons averaged with two empty ones, a number that looks like an ordinary partially-filled column. *A baseline recorded after a degradation launders it into the norm.* Found by 0.13.0's break map as a `disappears`, not by the fill-rate gate | **Session DATA-2 / 0.13.0 ☑ detected + classified** (`breaks.KNOWN_BREAKS`, severity `defect`) and the per-season two-sided gate (`validate.fill_rate_gate_by_season`) would now catch it. **Still open: the DATA** — decide whether to re-scrape PFR for 2024–25 TDs or mark the column dead from 2024 in the register. Do not re-baseline the whole-table fill rate until that is decided, or the laundering is made permanent | ☐ 2026-08-03 |
| **T52** | 🟠 | **the break detector is blind to two of the three encoding seams DATA-2 actually met, and 'we have a break detector' is not 'we would notice a break'.** 0.13.0 keys on **conservation** — a re-encoding moves mass out of NULL onto ONE in-domain value, so `Δnull ≈ −Δvalue`. Two real seams in this session have a different shape and pass silently: **(1) over the cardinality ceiling** — `participation.offense_personnel` fill climbs **0.7586 → 1.0000** at the same 2023 seam as T50, but `probeable_columns` skips anything above `MAX_CARDINALITY` (64) and this column has **1,468** distinct strings from 2023 (106 before); even probed, the arriving mass spreads across hundreds of new special-teams strings rather than landing on one sentinel, so the conservation test could not fire either. **(2) under the conservation test** — `weekly_rosters.position` swaps vocabulary at 2016 (fine-grained CB/FS/DE/ILB/C/G/T through 2015, grouped DB/DL/LB/OL after); at 27 distinct values it is *under* the ceiling, but a **vocabulary swap among observed values** has nothing to conserve. Unmapped, it silently dropped the pre-2016 positions and left **64 team-seasons** whose position shares did not sum to 1. *A detector that keys on a single value is blind to a re-encoding that arrives as a population.* | **Add a population-level check to `data/validate.py`**: for high-cardinality and categorical columns, compare the **value-set** and the fill rate **conditioned on a stable population** season over season (0.13.4's `scrimmage_fill_by_season` is the worked example — naive break 0.2414, conditioned break 0.0001). A value set whose Jaccard overlap collapses between adjacent seasons is a vocabulary swap, and it must fail the same way a sentinel does. NB neither seam is a *defect in the data* — both are handled correctly now; the debt is that the standing gate would not have told us | ☐ 2026-08-03 |
| **T53** | 🟡 | **`team_construction_season`'s cap columns are not a cap sheet, and the gap is 23 %.** Accounted APY sums to **1.2324** of the cap on average (min 0.92, max 1.38), because OTC gives a contract's signing year / length / average-per-year and *not* per-season cap hits, dead money, restructures or June-1 mechanics — and because a player traded mid-season is counted on both rosters. The **normalized `cap_share_*`** columns are correct and are what the deep dives read (allocation within accounted money, a valid distribution on all 416 rows); **`cap_pct_*` must never be read as 'percent of cap spent'**, which is exactly the misreading its name invites. Player-level coverage is 88–97 % per season | Either (a) source a real per-season cap-hit feed (none free is known — this may be a permanent register floor like PFF alignment), or (b) **rename `cap_pct_*` to `apy_accounted_*`** so the column cannot be misread, and keep `cap_share_*` as the headline. (b) is cheap and should probably just happen; do it when something outside `situation/` first reads these columns | ☐ 2026-08-03 |
| **T54** | ☑ | **a manager profile is season-scoped, and applying one across seasons is LOOK-AHEAD — not a mismatch.** 16.18 seated `fitted_manager` in `REALISTIC_ROOM`, and every measurement harness in the repo sweeps **2017–2024**. The profile describes **2026** and was written in August 2026 by someone who watched those seasons happen, so a batch run fed the future into a historical measurement — `CLAUDE.md` §3.1's non-negotiable. **★ The leak is GRADED, which is what hid it:** the 2026 profile fires on **6** board rows in 2017, 21 in 2020, **55 in 2024** (a lockbox season) and 78 in 2026, so the seat is *almost* `balanced` early and *increasingly itself* toward the present — which reads as a seat with a mild opinion, not as a defect. **★★ And it was invisible to every bar written to catch it:** measured un-gated against the pre-16.18 room, profile distance moved **0.0894 → 0.0887**, elite past-10 **25.24 % → 25.16 %**, dispersion **−11.39 % → −11.24 %**, landing **15.31 % → 15.16 %** — *all five T15 gates PASS on both arms.* A session that had only read the bars would have shipped it | **Gate at room composition** — `ManagerProfile.covers(season)` + `make_room(..., season=)` degrading a `requires_profile` seat to `PROFILE_FALLBACK` (`balanced`). ⚠ Degrade, **do not raise**: a historical measurement legitimately wants the room *minus* the seat, and since `balanced` is exactly the chair 16.18 took, an uncovered season reproduces the pre-16.18 room **bit-for-bit** — which is what keeps every committed historical sheet a valid reference and makes spec bar **B7** hold by construction rather than by measurement | **☑ 2026-08-05** — `covers()` + the `make_room` gate + `full_room(season=)`; `steps/mock_room_bars.py` builds its room **per season**. Verified paired by the done-bar `steps/mm1_b7_room_gate.py` -> `analysis/mm1_b7_room_gate.json` (2017+2018 × 6 seeds, `--shuffle-room`): the gated default room and an explicitly pre-16.18 room agree on every result leaf. 2 tests pin it, including a control that the gate can fire. **The size of the leak was never the argument** |

---

## 🔴 T1 — Commit the Phase 10 + Stage 0 session
**Status ☐ · do now (minutes).**

**Symptom.** `git status` shows 16 changed/untracked files — the entire `simulation/` package (Phase 10),
both `steps/stage0_*.py`, `tests/test_phase10.py`, `tests/test_stage0.py`, the `distribution.py`/`adp.py`
edits, the doc updates, and `analysis/results/sleeper_probe.json` — all uncommitted. A full session's output
exists only in the working tree. 194 tests pass, ruff clean; there is no reason to hold it.

**Fix.**
1. Inspect `analysis/results/sleeper_probe.json` (`git diff --cached` it) — confirm no private
   username/league identifiers before it goes in git.
2. `git add` the simulation package, both stage-0 scripts, the two test files, the `distribution.py` +
   `adp.py` edits, `steps/README.md`, the doc set, and the probe json; commit
   (`"Phase 10 (season/playoff sim + leverage) + Stage 0 (2026 ADP snapshots, Sleeper probe)"`); push.
3. Keep the `.duckdb`/parquet artifacts out (already gitignored — verify they're not staged).

**Done-when.** `git status` clean; `origin/main` has the Phase 10 + Stage 0 commit.

---

## 🔴 T2 — Back up the irreplaceable data
**Status ☑ done (2026-07-10) — layers 1 & 2 shipped; layer 3 (git-LFS) left as an optional stretch.**

**Done (2026-07-10).** Added `steps/backup_db.py` (idempotent, checksum-verifying) and ran it: the 6 live
2026 FFC snapshot parquets + the 3 2025 `stats_player` backfill parquets + a date-stamped full `.duckdb`
dump (295 MB) now live off the WSL disk at `/mnt/c/Users/rayha/fantasy-quant-backup/`, all md5-verified
byte-identical to source. Wired into the weekly Stage-0 chore (CLAUDE.md §2). **Remaining optional:** layer
3 — put `data/raw/adp/snapshots/` under git-LFS for automatic versioned history (removes the manual step).

<details><summary>Original plan (kept for the record)</summary>

**Symptom.** `data/fantasy_quant.duckdb` (309 MB) and `data/raw/adp/snapshots/*.parquet` (6 banked) are
gitignored and live only on this WSL ext4 disk. Two assets in them are **not reproducible**: the **live
2026 FFC ADP snapshot series** (Stage 0's whole point — "unrecoverable later") and the **2025 nflverse
`stats_player` backfill** (the old frozen `nfl_data_py` path is dead — a 404). A disk/WSL loss wipes exactly
what we spent sessions to capture.

**Fix (layered — cheap first).**
1. **Immediate off-disk copy of the crown jewels** (tiny): copy `data/raw/adp/snapshots/*.parquet` to the
   Windows side, e.g. `/mnt/c/Users/rayha/fantasy-quant-backup/adp-snapshots/`. These are the
   replay-idempotent source of truth — the ingest self-heals from them.
2. **Periodic full-DB dump.** Add `steps/backup_db.py` (or a make target) copying the `.duckdb` to a
   timestamped file on `/mnt/c/...` or a cloud-synced folder. Hang it off the existing weekly Stage-0 chore
   (after each snapshot pull, dump the DB).
3. **Structural (recommended).** Put **just** `data/raw/adp/snapshots/` under **git-LFS** (or a private
   second repo) — a few KB per snapshot, fully versioned, no 309 MB bloat. Turns "back up sometime" into
   automatic history and removes the manual step.

**Done-when.** The 2026 snapshot parquets + a recent `.duckdb` exist off the WSL disk; the weekly chore
refreshes the backup; (stretch) snapshots are version-controlled.

</details>

---

## 🟠 T3 — Fix the under-modeled downside (unconditional coverage 44 %, points coverage 62 %)
**Status ☑ done (2026-07-11).** **2025 holdout (read once): unconditional coverage 44 % → 77 %,
conditional 76 % → 76 % (held); Phase-10 team-points coverage 62 % → 77 %.** DEV: uncond 39 % → 70 %,
cond 79 % → 75 %. 2025 is the calibration holdout (not the lockbox) — tuned only on DEV, read once.

**What shipped, and how it diverged from this plan.** Attribution first (`findings.md` 2026-07-11): 31 % of
board players realize below their own q10 and **~95 % of those barely played** (realized ≈ 0), so the
dominant unconditional miss is **availability / roster-security** (a projected body who never plays), not
the "plays-but-produces-less" case Root-cause-B's production haircut targeted.
- **A — cohort availability prior** (`injury.cohort_availability_prior`) — the **main lever** (uncond
  39 %→63 % alone). Routes the sub-`prior_games≥8` cohort to a `(pos × draft-capital tier)` prior for both
  `avail_p` and `rho` (hi-capital rookie RB plays 0.67 of games vs lo-capital 0.42; fat `rho` 0.37+ vs the
  0.15 shared fallback). Wired into `distribution.assemble_distribution` (replaces the median fallback).
- **B — role-loss WASHOUT mixture** (`injury.role_retention` + `distribution.sample_player_season`), the
  reformulation. The planned production haircut `Y=H·(G/G_ref)·R` added ~0 coverage and dropped conditional
  to ~72 %; role loss instead acts through the **availability channel** — a tier-specific washout rate
  `p_crater` (played < 40 % of games) draws games from a low `crater_avail` (≈0.15) *replacing* the hazard
  branch (injury never double-counted), applied to **established, deep-projected** players only (elite/starter
  washouts are injury, already in `G`). `covariance/estimate.role_ranks` reuse was **not** needed — role
  tiers key on projection rank vs the startable/replacement rank (`injury.role_tier`), simpler and PIT.
- Guard held: conditional coverage stayed in band (76 % holdout / 75 % DEV) and title Brier is unbroken.
- New unit tests in `tests/test_phase5.py` (capital/role tiers, backoff, washout left-tail widening);
  `steps/phase5_4_injury.py` extended with the T3 done-bar (cohort + washout assertions).

<details><summary>Original plan (kept for the record — Root-cause-B was overturned by the DEV diagnosis)</summary>

**Symptom.** Phase 5 unconditional 80 %-interval coverage = **44 %** (target 80 %); Phase 10 team-points
coverage = **62.4 %**. Distributions are too narrow on the draft-day (unconditional) axis; rank calibration
is fine (Spearman ≈ 0.57, title Brier 0.088) — it's the **level and left tail** that leak. Two independent
root causes.

**Root cause A — the availability universe excludes the volatile players.**
`injury.availability_frame` (`src/fantasy_quant/projections/injury.py:87`, gate `prior_games ≥ 8`) drops
rookies, second-year players, and anyone without a full prior season to a single median-availability
fallback; `availability_projection` (`injury.py:213`) then attaches **one shared `rho`** to every row. The
highest-attrition-variance cohort is modeled with the least specificity.

**Root cause B — role/depth attrition isn't modeled at all.** A projected WR2 benched to WR4 by October has
full "availability" (he plays) but craters — nothing captures this. It is the dominant *unconditional* miss.
The sample model is `Y = H·(G/G_ref)` (`distribution.py`) — injury only, no role term.

**Fix.**
1. **Cohort availability prior (A).** In `availability_frame`, route the `< min_prior_games` rows to a
   separate estimator keyed on `(pos, draft_capital/age)` instead of dropping them; draw both the fallback
   `avail_p` **and its dispersion `rho`** from that cohort (rookie RBs have fatter lost-season tails than the
   league median). Keep the established-contributor hazard as-is.
2. **Role-survival haircut (B) — the higher-value half.** Add `injury.role_retention(con, season)` →
   per-player `P(keeps ≥ projected role)` + a downside points-fraction if not, estimated on DEV seasons from
   realized role-rank transitions. **Reuse `covariance/estimate.py:role_ranks` (`:72`)** — do not rebuild
   role logic. Fold a third factor into `distribution.sample_player_season`:
   `Y = H·(G/G_ref)·R`, `R` a Bernoulli mixture (in-role → 1; lost-role → cohort downside fraction). This
   widens the **left tail specifically**, where the coverage leaks.

**Done-when.** Re-run the Phase-5 conformal coverage check and the Phase-10 gate: unconditional coverage
44 % → **≥ 70 %**, points coverage 62 % → **≥ 75 %**, **without** breaking conditional 76 % or title Brier
0.088. Guard against over-widening — if conditional coverage overshoots 80 %, back the haircut off.

**Effort.** A real 1–2 session phase. Highest-value modeling fix; strengthens every downstream probability
before the freeze.

</details>

---

## 🟠 T4 — Fix the season-sim level bias (−137 pts/team/season)
**Status ☑ done (2026-07-11) — with T3.** Phase-10 team-points coverage **62 % → 77.2 %**, mean bias
**−137 → −113 pts/team/season**; title Brier **0.0881** (< 0.09), playoff **0.2342** (< 0.24), stability
0.979/0.949, **all hard gates PASS** (1,800 DEV team-seasons). `steps/phase10_sim.py` unchanged as the gate.

**What shipped, and how it diverged from this plan.** Attribution (`findings.md` 2026-07-11) overturned both
candidates: (1) the bias is entirely in the **offense** path (−140); K/DST fallbacks run **+16** — jittering
them would *worsen* the bias, so they're left alone; (2) per-player weekly CoV is **already well-calibrated**
from the prior season (RB 0.67 model vs 0.63 realized) — pooling doesn't move the bias. The real cause is
**structural**: the mean-preserving Dirichlet week-split has tails too light to reproduce the weekly
optimal-lineup **max** (a tail statistic), because a mean-preserving split caps weekly upside at the season
total. Fix = `weekly.SPREAD_KAPPA`, a per-position **effective-CoV inflation** (mean-preserving, so season
totals / Phase-5 / T3 calibration are untouched) that restores the max, plus pooling `wk_cov` over the prior
**two** seasons. QB is a single mean-preserving lineup slot (barely responds) → smallest inflation.
**κ is a genuine trade-off** (higher → more coverage/less bias but sim over-dispersion + a broken dog-leverage
gate); locked at `{QB 1.4, RB/WR 1.8, TE 1.7}` = the highest κ that keeps **every** hard gate passing.
**Residual bias (documented):** ~−113 remains, concentrated in the early/COVID seasons (2017/18/20 start
~−220 at κ=1.0) and partly a **projection-level** shortfall κ can't fix; the deliverable probabilities are
relative so they stay calibrated. Fully closing it needs a non-mean-preserving weekly-upside term (breaks the
Phase-5 sum invariant, gated behind explicit approval) or better early-season projections — future work.

<details><summary>Original plan (kept for the record — both root-cause candidates were wrong)</summary>

**Symptom.** Phase-10 predicted optimal-lineup totals run ~**137 pts/team/season low** (~−8/wk). The
championship-prob deliverable is *relative within a league* so it calibrates anyway — but any absolute-points
consumer, and the variance machinery that feeds on spread (`valuation/utility.py` CE, `simulation/leverage.py`
mean-preserving spreads), inherit the understatement. Season totals are preserved; the **weekly
disaggregation** that feeds the lineup max is the suspect.

**Root cause (two candidates — attribute before fixing).**
1. **Stale/understated weekly CoV.** `build_weekly_model` (`src/fantasy_quant/simulation/weekly.py:203`)
   pulls `variance.weekly_volatility(con, [season-1], …)` — a **single** prior season of `wk_cov`
   (`variance.py:47`), noisy and biased low for players whose usage grew; the Dirichlet `α = 1/CoV²`
   (`weekly.py:92`) then makes weeks too flat, so the lineup max (which rewards spikes) comes out low.
2. **Flat constant fallbacks.** `replacement_weekly` + `kdst_weekly_baseline` (`weekly.py:120–140`) assign a
   *constant* weekly score — zero week-to-week variance, so those slots never spike and drag the team max down.

**Fix.**
1. **Attribute first.** Instrument `steps/phase10_sim.py` to print predicted-vs-realized mean lineup points
   **decomposed by roster slot** — this says whether the CoV path or the fallback path owns the −8/wk.
2. **CoV path:** pool `wk_cov` over **2–3 prior seasons** (widen the `[season-1]` window) and/or shrink each
   player's CoV toward his position median rather than filling missing with the flat `DEFAULT_COV = 0.9`.
3. **Fallback path:** give the K/DST + cloudless-offense fallbacks a modest lognormal jitter (position-typical
   CoV) instead of a hard constant.

**Done-when.** Level bias shrinks toward 0 **while** title Brier stays < 0.090 and the reliability diagonal
holds. (Widening spread also lifts T3 coverage — that's why they're done together.)

</details>

---

## 🟠 T5 — De-risk the one-shot lockbox
**Status ☑ (2026-07-19, Session D). Pre-registration committed BEFORE the eval (`7bd6e10`); lockbox
evaluated EXACTLY ONCE and reported as-is.** Pre-registration in `PLAN.md` §"⭐ T5 PRE-REGISTRATION": the
exact frozen stack + the exact metrics + the 2025 dress rehearsal + the ≈35–40 DEV-decision count. **2025
dress rehearsal** (`analysis/lockbox_dress_2025.json`): projection bias 0.575 / Spearman 0.568, coverage
75.5 % uncond / 81.5 % cond. **Lockbox result** (`steps/lockbox_eval.py --which lockbox`,
`analysis/lockbox_eval.json`, `findings.md` §"LOCKBOX EVALUATION"): **title Brier 0.088 < 0.09 (holds OOS,
≈ DEV) · conditional coverage 80.1 % · projection Spearman 0.54 · cheap personalization**; known
level-optimism / unconditional-attrition limitation persists (bias 0.62, uncond coverage 72 %, a marginal
playoff Brier 0.240). **No modeling change after this — the stack is frozen.**

<details><summary>Original plan (kept for the record)</summary>

**Symptom.** By design everything is developed on DEV 2014–2022 and 2023+2024 is evaluated **exactly once**
at the end (`config.LOCKBOX_SEASONS`, CLAUDE.md §4). Every phase has been selected/tuned on the same ~9 DEV
seasons — the multiple-testing burden is real and growing, and the whole external-validity claim rests on a
single eval with no retry. PIT-clean ≠ out-of-sample-clean.

**Fix (reduce what we implicitly fit before spending the one shot — you can't add trials, so freeze late).**
1. **Pre-register** in `PLAN.md`, dated and committed, immediately before the eval: the exact frozen stack
   (projection, λ default, archetypes, the T3 coverage fix) **and** the exact metrics to be reported. No
   post-hoc "one more tweak" after this.
2. **Use 2025 as the full-stack dress rehearsal.** It's already the calibration holdout
   (`config.CALIBRATION_SEASONS`); run the *assembled* system against it (not just projections) so the
   lockbox isn't the system's first contact with unseen data. Once a 2025 ADP board lands (Sleeper, step
   0.10) it upgrades to a full backtest season and this gets much stronger.
3. **Track a running count** in `findings.md` of selection decisions made on DEV, so a marginal lockbox
   result is read with the right skepticism (1.5σ after 40 decisions ≠ after 5).

**Done-when.** A committed, dated pre-registration exists; 2025 dress-rehearsal numbers are recorded; the
lockbox is evaluated once and reported as-is with the decision-count caveat.

</details>

---

## 🟡 T6 — Consolidate the Monte-Carlo draws
**Status ☑ done (2026-07-10, with Phase 9.5).**

**Done (2026-07-10).** Added `distribution.cached_distribution(con, season, ruleset, n_draws, seed)`
— memoized on `(season, ruleset_json, n_draws, seed)` (the `_CORR_CACHE` pattern), always computed
`return_games=True` and served as `(summary, samples, games)`; `samples` is bit-identical whether or
not `games` is captured (same rng stream), so the games-free consumer slices `[:2]` off the *same*
cloud. Both consumers now read it: `optimizer.assemble_value` (with a new threaded `seed`) and
`weekly.build_weekly_model`. `optimize_draft(winprob=True)` builds the sim's `WeeklyModel` on the
**same seed** as the value index, so the draft and sim reference one joint cloud. `test_phase9`
asserts the memoization (one underlying call per `(season, seed)`; a distinct seed recomputes).

<details><summary>Original plan (kept for the record)</summary>

**Symptom.** `distribution.assemble_distribution` (`N_DRAWS = 2000`, `seed = 0` default) is called
independently by `optimizer.assemble_value` (`src/fantasy_quant/draft/optimizer.py:100`) and
`build_weekly_model` (`src/fantasy_quant/simulation/weekly.py:195`). Today they share a base draw **only by
the coincidence of the default seed** — the moment any caller passes a non-zero seed (or parallelizes), the
value the greedy drafts against and the value the sim scores **silently diverge**, and the same 2000-draw
cloud is recomputed several times.

**Fix.**
1. Add `distribution.cached_distribution(con, season, ruleset, n_draws, seed)`, memoized on
   `(season, ruleset_json, n_draws, seed)` — mirror the existing `_CORR_CACHE` pattern
   (`optimizer.py:184`) — returning `(summary, samples, games)`; point both consumers at it.
2. Thread **one explicit seed** from the top-level entry points (cost report, `phase10_sim`) so a run is
   fully reproducible and the draft and sim reference the *same* joint draws.

**Done-when.** 194 tests still pass; a new test asserts the two consumers get identical `samples` for the
same `(season, seed)`. Do this **before** Phase 9.5 wires the sim into the draft objective (T8) — that's when
the divergence would start biasing results.

</details>

---

## 🟡 T7 — Harden the external-scrape dependencies
**Status ☑ done (2026-07-10) — all three parts shipped.**

**Done (2026-07-10).**
1. **Freshness/schema guards** (`data/validate.py`): pure, injectable gates `adp_freshness_gate`
   (live-season FFC snapshot ≤ 6 days old — the CLAUDE.md §2 chore as an assertion), `board_size_gate`
   (FantasyPros board row-count band 400–700), `match_rate_gate` (gsis-match ≥ 95 %), wired into
   `data_health_report` via `_scrape_gates`; guards fire only when the relevant live board is present
   (historical-only stores stay green). 7 new pure unit tests in `tests/test_validate.py`.
2. **Raw-payload archival** (`data/cache.py::archive_text`): each FFC (`_pull_ffc`) and FantasyPros
   (`_pull_fp`) pull date-stamps its raw JSON/HTML under `data/raw/**/payloads/` (gitignored) so a
   broken scrape can be diffed against last-good shape; best-effort (never sinks a pull). 3 new tests
   in `tests/test_cache.py`.
3. **Props decision — SHELVED** (user, 2026-07-10): the markets/props layer is **formally deferred**
   (not a silent no-op), consistent with the reframe's "don't fight the sharp market"; the de-vig math
   stays built + tested for a future `ODDS_API_KEY`. Marked in `markets/props_projection.py`,
   `ROADMAP.md` Phase 2.3 (⏸️).

<details><summary>Original plan (kept for the record)</summary>

**Symptom.** FantasyPros (value) and FFC (ADP) scrapes are the spine and rot silently when site markup
changes; `markets/props_projection.py` is a **no-op** (no free props data), so the "markets" signal layer is
effectively absent though half-wired.

**Fix.**
1. **Freshness/schema guards** in `data/validate.py` (where `data_health.json` already lives), as
   test-visible assertions, not prose: latest 2026 ADP snapshot ≤ 6 days old (promote the CLAUDE.md §2 chore
   to an assertion), FantasyPros board row-count in a sane band, gsis-match rate ≥ 95 %. Fail loudly instead
   of ingesting garbage.
2. **Persist the raw payload** on each pull (HTML/JSON alongside the cached parquet) so a broken scrape can be
   diffed against last-good shape.
3. **Props decision.** Per the reframe finding ("don't fight the sharp market"), **formally shelve** the
   markets layer in ROADMAP (a 5-min doc edit) rather than invest — or wire one free odds source if ever
   wanted. Either way, remove the ambiguous no-op limbo.

**Done-when.** A markup change trips a red test; raw payloads are archived; the props layer's status is an
explicit decision, not a silent no-op.

</details>

---

## 🟡 T8 — Make `objective` real (Phase 9.5) + the behavioral opponent model (0.10 → Phase 11)
**Status ◐ · 8a ☑ done (2026-07-10); 8b: step-0.10 ingest ☑ done (2026-07-11), the behavioral fit still
open (needs a real-league pick log — bot mocks carry no persistent opponent identity).**

**Done — 8b step 0.10 (2026-07-11).** The pick-by-pick **data pipe** is built + verified on 3 real mock
drafts (`src/fantasy_quant/data/sources/sleeper.py`, `steps/phase0_10_sleeper_ingest.py`, `tests/test_sleeper.py`;
`docs/SLEEPER.md`). Keyless public API; `sleeper_drafts` + `sleeper_draft_picks` (idempotent by `draft_id`);
gsis crosswalk **100 % skill / 80 % K / DEF bridged**; derived `sleeper_mock` ADP board written into
`adp_snapshots` (so `adp_asof(source="sleeper_mock")` + the simulator consume it unchanged — verified by
drafting a 2026 mock); POC `sleeper_tendencies` (per-slot cadence + reach). Corpus-ready (`ingest_drafts`
takes a list of ids **or** discovers a username/league). **What 0.10 confirmed that changes the fit:**
mocks are **solo-vs-bots** — `picked_by` is set for the *human's own* picks only, so there is **no
persistent opponent identity**; the behavioral fit + availability Brier need **real human leagues** (which
populate `picked_by`), not mocks.

**Done — 8a (2026-07-10).** `DraftConfig.objective` is now consumed. `winprob_pick_fn` (opt-in via
`optimize_draft(winprob=True)`) prefilters to the top-k portfolio-CE/scarcity candidates, finishes the
draft greedily for each, scores the league with a Phase-10 mini-sim, and takes the candidate that
maximizes the routed metric — `make_playoffs`→`playoff_prob`, `championship_or_bust`→`title_prob`.
Common random numbers across candidates make the comparison pure roster signal. 2022 DEV: the two
objectives draft **8–9 different roster slots** and the title-max board carries **+0.09 title prob** over
the playoff-max board on an independent eval (at 250 sims/pick). **Honest caveat:** `title_prob` is a
~1-in-10 event, so `championship_or_bust` needs ≥~200 sims or it chases sim noise (at 60 sims it
under-performed); `make_playoffs` resolves at far fewer. Portfolio CE stays the fast default.
`steps/phase9_policy.py` is the done-bar; **8b** (behavioral opponent model) remains below.

**Symptom.** `DraftConfig.objective` (`src/fantasy_quant/draft/config.py:141`, comment "MVP: label") is
validated and passed around but **nothing consumes it** — the optimizer maximizes portfolio CE, not win
probability, so `make_playoffs` vs `championship_or_bust` draft identically. Separately, opponents are still
**ADP + Gaussian noise** (`draft/simulator.py`); the reframe's *behavioral* opponent model (a hard contract)
isn't built.

**Fix — 8a (Phase 9.5, now).** Wire the greedy to the Phase-10 probabilities (findings already notes "9.5
consumes `title_probability`/`playoff_prob` directly"):
- Replace/augment the per-pick score with the **marginal championship/playoff probability** from a mini-sim
  (`LeagueSim.title_prob` / `.playoff_prob`, `simulation/season.py:114`).
- Route `objective`: `make_playoffs` → maximize `playoff_prob`; `championship_or_bust` → maximize
  `title_prob` (rewards ceiling/variance → genuinely different boards — the point).
- Keep portfolio CE as the fast default; gate the win-prob objective behind the `objective` field / a Phase-9.4
  lookahead budget (a mini-sim per candidate is expensive).

**Fix — 8b (step 0.10 ☑ → Phase 11 fit ☐). Full reference: `docs/SLEEPER.md`.**
- 0.10 ☑ (2026-07-11): ingest built + verified — pick-by-pick JSON shape confirmed, `sleeper_id → gsis`
  crosswalk ingested (100 % skill), per-slot/reach behavior + `sleeper_mock` ADP board derived. See the
  "Done — 8b step 0.10" note above.
- Phase 11 ☑ (2026-07-11 — fit on the real corpus): the behavioral opponent model (conditional/McFadden
  logit) **beats ADP-only** walk-forward (log-loss +0.113 CI[+0.101,+0.124]) and the **availability Brier**
  owed from spine-4 **beats best-tuned ADP+noise** (0.158 vs 0.316, +0.159 CI[+0.083,+0.264]) → the S4
  availability oracle promotes from opt-in to the default. `draft/opponent_model.py`, `draft/availability.py`,
  `draft/personalities.py`; `steps/phase11_opponent_model.py`. (2025→2026 still becomes a full backtest
  season once a real *2026* ADP board lands.)

**Blocker → CLEARED for a first fit (2026-07-11).** The crawler (0.10b/0.10c) + a live crawl from the
Sleeper docs' **public example leagues** built a real corpus — **149 human + 117 bot drafts (2017–2020),
289 manager profiles**, `sleeper_human` ADP board, skill match 99.8 %. Real-league drafts were confirmed to
carry full per-manager `picked_by`. So the *data* no longer blocks the fit — a first behavioral opponent
model + availability Brier can run on real human picks (older seasons, but with realized outcomes). What
would strengthen it: **more/newer seeds** (broader connected components; the current corpus is one co-manager
component off 2 seeds) — add `league:<id>`/usernames to `reference/sleeper_seeds.txt` and re-run
`steps/phase0_10b_crawl.py`.

**Done-when.** 8a: switching `objective` measurably changes the drafted roster on DEV, consuming calibrated
probs. 8b: ☑ ingest + crawler verified on real drafts; a real corpus exists; **☑ the opponent model beats
ADP+noise on a real-pick availability Brier** (done 2026-07-11 — behavioral 0.158 vs best-tuned ADP+noise
0.316, +0.159 CI[+0.083,+0.264]). **T8b CLOSED.**

---

## 🟡 T9 — Phase 13.3 FAAB bidder is pragmatic; rigorous auction theory owed
**Status ☑ done (2026-07-13, Session C — Phase 15.4).** `draft/auction.py` now exists (auction values,
the exact `endgame_cap` budget-state continuation, winner's-curse-shaded `auction_bid`, `nominate`), and
its own done-bar PASSES 6/6 DEV seasons (a budget-state bidder beats naive budget-splitting by +66→+128
realized starting-lineup pts, season-block CI [+78, +108]). **`inseason/waivers.faab_bid` consumes it**:
pass `slots_remaining` and it caps the willingness-to-pay by `auction.endgame_cap` instead of the
closed-form ration (the rigorous continuation value the pragmatic bidder lacked); `faab_skill(use_auction=
True)` exercises the path. The FAAB *value* done-bar is unchanged under the upgrade — winner-selection is
scale-invariant among symmetric bidders, so the continuation form changes prices (budget efficiency), not
who wins, and the sim passes identically (no regression). The closed-form ration stays the default so the
committed 13.3 result is untouched. **Done-when met:** `draft/auction.py` exists, `faab_bid` consumes
auction values + a DP continuation cap, the FAAB sim still passes. **T9 CLOSED.**

<details><summary>Original entry (kept for the record)</summary>
**Opened 2026-07-12 (Session B, 13.3).**

**Symptom / decision.** 13.3's spec (`docs/BUILD_PLAN.md`) said "reuse 11.4", but **11.4 (auction-draft
support) was deferred out of Phase 11 into Phase 15.4** and `draft/auction.py` does not exist. Per the user
decision (2026-07-12), 13.3 shipped the **pragmatic** FAAB bidder (`inseason/waivers.py::faab_bid`) — enough
to clear the done-bar — and the **rigorous** version is explicitly owed here.

**What's pragmatic (and its limitation).** `faab_bid` combines three forces with **fixed/heuristic**
parameters, not an equilibrium: (1) marginal value → willingness-to-pay via a linear `value_scale`; (2) the
option value of budget as a closed-form ration `1/(1+κ·(weeks−1))` (a monotone hoard-early curve, **not** a
budget-state dynamic program); (3) first-price shading against a **fixed belief** `opp_bids` (a static
naive-field sample, **not** a fitted/equilibrium opponent-bid distribution). Also: the sim's smart agent bids
marginal-value-over-its-own-roster, but against a **synthetic** field (no real FAAB transaction data exists —
the Sleeper corpus is draft picks only), so the done-bar is a relative sim result, not a Brier-verified fit.

**The exact fix (at Phase 15.4).** Build `draft/auction.py` with a real auction-value engine (budget-state
DP or an equilibrium bid-shading model calibrated to an opponent-bid distribution), then have 13.3 reuse it:
replace the `value_scale` map with auction values, the closed-form ration with the DP's continuation value,
and the fixed `opp_bids` with the fitted field. If/when real FAAB transaction logs are ever sourced (Sleeper
transactions endpoint), fit and Brier-score the opponent-bid model like the draft opponent model (11.1/11.2).

**Done-when.** `draft/auction.py` exists and `faab_bid` consumes auction values + a fitted/DP continuation
value; the FAAB sim still passes its done-bar under the upgraded machinery.

</details>

---

## ✅ T10 — the archetype sweep crashes on S6's `adaptive` — **DONE 2026-07-24 (Session E)**
**Status ☑ · fixed per parent.** `validate_archetypes` now expands `adaptive` into one distinct subject
per static parent — `adaptive(zero_rb)`, `adaptive(late_qb)`, `adaptive(elite_te)`, `adaptive(hero_rb)` —
so the sweep prices each variant against its parent (the more-informative option) instead of skipping it.
`steps/spine_4_validate.py` runs green; the frozen stack is untouched (harness/utility fix only). On an
ADP board adaptive reproduces its parent (as S6 predicted); the 2 REAL-GAIN reads (elite_te) are unchanged.
_Original diagnosis below (kept for the record)._

**Status ☐ · opportunistic (found during the lockbox eval; worked around there).**

**Symptom.** `valuation/cost_validation.validate_archetypes` defaults its sweep to `[a for a in ARCHETYPES
if a != "bpa"]` — which now includes **`adaptive`** (added by S6 in Session A). `replace(bench,
archetype="adaptive")` raises: the `adaptive` archetype requires an `adaptive_parent`. So the archetype
cost-report done-bar `steps/spine_4_validate.py` (and any default call) crashes post-S6 — a latent
regression the DEV done-bar hasn't re-run since 2026-07-09 (pre-S6). The lockbox eval hit it and worked
around it at the harness level (`steps/lockbox_eval.py::cost_report_par` passes an explicit
`archetypes=list(ADAPTIVE_PARENTS)`), so the frozen stack was untouched.

**Fix (opportunistic, post-lockbox — a harness/utility fix, not the modeling stack).** Either exclude
`adaptive` from `validate_archetypes`' default names, or price it against each of its parents (sweep
`adaptive(zero_rb)`, `adaptive(hero_rb)`, … as distinct subjects — the more informative option). Update
`spine_4_validate.py` to match.

**Done-when.** `steps/spine_4_validate.py` runs green again; the sweep either skips `adaptive` or prices it
per parent.

---

## 🟡 T11 — Underdog ADP never ingested; the drift corpus is too thin to re-ask 16.8
*(opened 2026-07-25, Session F)*

**Two loose ends left by Session F, both data-side, neither blocking.**

**(a) Underdog ADP — deferred, not attempted** (user decision). It was half of Phase 0.11's scope: the
sharp best-ball market, the cleanest `source_divergence` input, and the realistic board for 15.2 best-ball.
**Why it stopped:** no keyless endpoint — `underdogfantasy.com/rankings/nfl` 404s (it redirects to
`underdogsports.com`), and the plausible API paths return 404. The board is a JS app on an unpublished,
probably authenticated API. **Fix when wanted:** reverse-engineer the XHR the rankings page issues, or drop
it permanently and say so. Timebox it — this is exactly the open-ended scrape that eats a session.
*Note the pattern match with the shelved props layer (T7): both are "the free market data isn't free".*

**(b) The 16.7 drift panel is thin — 34 drafts over 8 seasons**, several seasons only 1–3 drafts deep,
4,495 boarded picks. That thinness is the main reason 16.8's verdict is a null rather than a measurement:
the honest read is "not resolvable at this sample size", not "the effect is zero". Two independent
constraints:
- **FFC publishes no 2025 board** (verified live: `"No ADP data found."`), which strands the largest
  single-season human cohort (18 drafts). Nothing to do about it — unrecoverable.
- The corpus itself is small once the preseason window, snake, redraft-scoring and completeness filters
  apply (117 human complete drafts → 42 → 34).

**Fix:** grow the human corpus — add league ids / usernames to `reference/sleeper_seeds.txt` and rerun
`uv run python steps/phase0_10b_crawl.py`, then re-run `steps/phase16_8_drift_model.py` unchanged. The
crawler reads **historical public leagues**, so this needs no live/in-season drafting. **Only re-ask 16.8
if the corpus grows materially** — re-running it on the same data after seeing the answer is exactly the
threshold-moving the phase's discipline forbids.

**Cost of not doing it:** 16.9 shapes its narrative shock from descriptive regularities (`rookie`,
`adp_stdev`) rather than a fitted per-player drift, and 16.10's curated board carries the narrative
signal. That is a defensible design, not a broken one — so this is 🟡, not 🟠.

## 🟠 T12 — the data-health report is permanently red (stale ADP uniqueness gate)
*(found 2026-07-25 while verifying Session F; **pre-existing — HEAD fails it too**, not introduced by 16.7/16.8)*

**Symptom.** `uv run python steps/phase0_8_validate.py` ends in **`GATES FAILED`** on every run. The single
failing gate is `adp: unique (gsis, season, source, scoring, teams)` with **1,028 offending groups**.

**Diagnosis (measured, benign).** Every offending group is **season 2026**, and **0 groups** contain more
rows than they have distinct `snapshot_date`s — i.e. there are **no genuine duplicates**. The gate's key
simply predates Stage 0. It was correct when each season had exactly one FFC board; since 2026-07-09 Stage 0
deliberately banks a **weekly snapshot series** for 2026, so `(gsis, season, source, scoring, teams)` is
legitimately non-unique and `snapshot_date` belongs in the key.

**Why this is 🟠 and not 🟡.** The gate is not wrong about data — it is wrong about the schema, and the cost
is that **the whole health report now reads FAILED by default**. A validator that is always red cannot warn
anyone: a genuinely broken ingest would produce the identical output. This is the alarm-fatigue failure mode,
and it silently disarms the T7 scrape-hardening work.

**Fix.** Add `snapshot_date` to that gate's uniqueness key in `data/validate.py` (`_dup_gates`), so it asserts
"one row per player per board **per snapshot**" — which is the invariant actually intended. Then confirm the
report returns to green and that a planted true duplicate still trips it.

**Deliberately not fixed in Session F.** Changing a validation rule is not a drive-by edit: it is exactly the
kind of "move the threshold after seeing the result" the repo's discipline forbids doing unannounced, and it
touches the frozen data layer rather than the walled-off Phase-16 track. Registered here for a decision.

**☑ Done 2026-07-25 (Session F.5), with the decision taken explicitly.** Folded into the corpus-expansion
session because that session multiplies `sleeper_human` ADP rows and would have made the red gate redder.
The key is now `(gsis, season, source, scoring, teams, snapshot_date)`. Two tests in `tests/test_validate.py`
pin **both** directions, which is the part that matters: a deliberate weekly snapshot **series** passes, and
two rows for the same player on the **same** snapshot still fail. Widening a uniqueness key is only safe if
you show it still catches the thing it was built to catch.

## Ordering (see `ROADMAP.md ★ THE PIPELINE` for the full sequence)
1. ~~**Now:** T1 (commit), T2 (backup).~~ ☑ both done (2026-07-10).
2. ~~**Opportunistic:** T7 (scrape guards + raw-payload archival + props shelved).~~ ☑ done (2026-07-10).
3. ~~**Phase 9 completion:** T8a (win-prob objective) with T6 (MC consolidation) folded in.~~ ☑ done (2026-07-10).
4. ~~**Before the lockbox:** T3 + T4 together (coverage + level bias).~~ ☑ done (2026-07-11).
5. ~~**Next build:** step 0.10 Sleeper ingest (the pick-by-pick data pipe).~~ ☑ done (2026-07-11).
6. ~~**Next build:** Phase 7 (opportunity-adjusted projection, keep-or-drop).~~ ✗ **built & DROPPED**
   (2026-07-11 — situation swap is a wash-to-worse than naive on role-changers; consensus already prices it).
7. ~~**When real leagues exist:** S4/Phase 11 (T8b behavioral opponent model + availability Brier).~~
   ☑ **done (2026-07-11)** — corpus cleared the blocker; fit + availability Brier both beat ADP+noise.
8. ~~**Next buildable pipeline item:** S6 → Phase 13/S7 → Phase 12 → Phase 15.~~ ☑ **all done**
   (Session A 2026-07-12: S6+13.1+13.2; Session B 2026-07-12: 13.3+13.4+13.5; **Session C 2026-07-13:
   Phase 12 news/NLP + Phase 15.2/15.3/15.4**).
9. ~~**At Phase 15.4 (auction support):** T9.~~ ☑ **done (2026-07-13, Session C)** — `draft/auction.py`
   built; `faab_bid` consumes `endgame_cap`; auction done-bar 6/6 DEV.
10. ~~**Right before the lockbox:** T5 (pre-register the frozen stack, incl. the T3/T4 params).~~
    ☑ done (2026-07-19, Session D) — the lockbox is **spent**; the modelling stack is frozen.
11. **NEXT (2026-07-30, user decision): Session H.5 — the mock-drafter value seam.**
    **T27** (the board a human reads ≠ the board the seats optimize) → **T28** (slot-blind
    `team_value`) → **T29** (bare absolute probabilities) → **T30** (the autopilot seat's share).
    Runs **before Session I / Phase 17**; the app stays strictly last. All four are display,
    labelling or composition — **none refits β and none touches the frozen value stack**, and every
    one carries a bit-identical re-measure of `analysis/mock_room_bars_verify_20260729.json` as a
    hard bar. Execution order + bars: `docs/BUILD_PLAN.md` §"Session H.5".
12. **Still deferred, with the reason on file:** T26 (`pos_share_*`) — with the next 11.1 refit,
    never on its own; T11(a) Underdog ADP (no keyless endpoint).


## ✅ T13 — the Phase-5 cloud is not reproducible across processes — **DONE 2026-07-29**
*(found 2026-07-26, Session F.6, while reconciling two dress-rehearsal runs; fixed 2026-07-29)*

**Status ☑ done.** `db.deterministic_reads` pins DuckDB to one thread around the assembler's reads;
three fresh interpreters now return a bit-identical cloud (`steps/t13_reproducibility.py` →
`analysis/t13_reproducibility.json`: `q10`, `q90`, `samples` and the key order all IDENTICAL, sum
spread exactly 0). Cost **negative** — 10.2 s → 9.1 s. Three unit tests cover the pin, its
restoration after an exception, and its no-op on a non-DuckDB stub.

**★★ The register's prime suspect was wrong, and it was wrong in an instructive way.** The
fingerprint on file — *"marginal sums near-invariant while the per-player assignment moves, which is
the fingerprint of a coupling/permutation step"* — is a perfectly good piece of reasoning that
happens to describe a second thing: an input that wobbles **below the noise floor of every aggregate
you were watching**. Ruled out by measurement, cheapest first:

| hypothesis | test | result |
|---|---|---|
| row order / a shuffle | md5 of the player-key sequence, 3 processes | **identical** — nothing is being reordered |
| Python hash randomization | `PYTHONHASHSEED=0` in both processes | still differs |
| BLAS/OpenMP thread non-determinism | `OMP/OPENBLAS/MKL_NUM_THREADS=1` | still differs |
| **DuckDB parallel aggregation** | `SET threads TO 1` | **bit-identical**, everywhere |

A parallel `SUM`/`AVG` over floats adds its partitions in whatever order the threads finish, and
floating-point addition is not associative. So the *training frames* differed in their last bits
run to run; the QuantReg and hazard coefficients differed at ~1e-11; and the sampler — whose rng
stream was never the problem — turned that into a per-player draw you could see. **A
reproducibility bug does not have to live in the random number generator**, and the noisy stage is
not always the stochastic one.

**It is not a model change.** The pin selects one of the values the old code was already
alternating between (75.5 ↔ 76.5 % dress coverage was the same result twice, as T13 always said).
Verified: the pinned digest equals one of the three unpinned runs measured before the fix.

_(Original entry, kept because the diagnosis it records is the one that had to be overturned.)_

**Symptom.** Identical inputs, fresh process, same seed: `cached_distribution(con, 2025, None)`
returns per-player `q10`/`q90` that differ every run. Downstream, the dress rehearsal's 80 %-interval
coverage alternates between **75.48 %** and **76.52 %** (508 vs 515 of 673 players inside). Observed
3:1 across five runs.

**What it is NOT** (both tested, both ruled out): the global NumPy RNG (perturbing it changes
nothing), and DuckDB row ordering (the first player keys are stable across processes). Determinism
holds *within* a process. Marginal sums are near-invariant while the per-player assignment moves,
which is the fingerprint of a coupling/permutation step rather than a marginal draw — the
Iman–Conover permutation in the Phase-8 correlation coupling is the prime suspect.

**Why it matters.** Any *per-player* distribution number — a player's q10/q90 in the app, a coverage
figure, a boom/bust probability — is only reproducible within one process. Aggregate and marginal
statistics are fine. Concretely: **Session D's 75.5 % and Session F.6's 76.5 % are the same result**,
and reading the difference as a T3 improvement would be wrong.

**Why it is not fixed here.** It lives in the **frozen** risk layer that the spent lockbox ran on.
Changing the sampler now would break comparability with the lockbox result for a defect that moves a
reported number by ~1pp. **Fix when the app is built** (Phase 14), by threading an explicit seed
through the coupling step and asserting cross-process reproducibility in a test.

> *(2026-07-29 — the "fix when the app is built" instinct was right about the deadline and wrong
> about the mechanism: no seed needed threading anywhere, because the sampler was innocent. The
> half of this paragraph that held up is the constraint — the fix had to leave the frozen sampler
> untouched, and pinning the **reads** does exactly that.)*

## ✅ T14 — 11.2 does not scale — **DONE 2026-07-26 (Session G), with the diagnosis corrected**
*(found 2026-07-26, Session F.6; fixed 2026-07-26, Session G)*

**Status ☑ done.** `availability_brier` at the committed budget went **396.4 s → 12.7 s (31×)** on
an identical call; projected at full committed scale (36,972 windows) **~163 min → ~5.2 min**.
Outputs are **bit-identical**, verified against the pre-fix implementation kept as a test oracle.

**★ The original diagnosis was wrong, and the way it was wrong is the lesson.** F.6 opened T14 by
*reading* the code, spotting an O(n_boot × n_drafts × n_windows) scan, and asserting it "dominated
a ~100-minute step run." Measured at exactly that scale, **the bootstrap takes 0.79 s** — about
**0.008 %** of the run. A `cProfile` of the real path put **99.3 % of the time in
`simulate_survival`**, and inside it not in the arithmetic but in **pandas**: `cand.iloc[ai]`
(195 s) and rebuilding the feature matrix column-by-column in `candidate_utility` (169 s), across
~648 k calls in a 9-draft sample — ~13 M at full scale. *A complexity class is not a profile.* The
scan was genuinely O(n³)-ish and genuinely irrelevant; the real cost was constant-factor pandas
overhead in a loop, which no amount of reading Big-O off the page surfaces.

**What was actually fixed (both, since the prescribed fix was cheap and correct on its own terms):**
1. **The real one — hoist invariant work out of the MC loop.** `OpponentModel.candidate_matrix` is
   split out of `candidate_utility`, and `simulate_survival` now builds **one design matrix per seat
   context** and indexes rows, instead of re-deriving every column from pandas at each simulated
   pick. `pos_run3` is the only column that moves within a draw, so it alone is overwritten in
   place. Rests on a **row-wise-columns invariant** (`candidate_matrix(board)[rows] ==
   candidate_matrix(board.iloc[rows])`) that is now asserted by its own test — if a future feature
   reads across rows (a rank, a share, a within-board z-score), that test fails rather than the
   hoist silently going wrong.
2. **The prescribed one** — `_draft_blocks` precomputes per-draft index blocks via one stable
   argsort. Kept because it removes a real scaling hazard as the corpus grows, and it is exactly
   bit-identical (proven by construction and by test).

**Why bit-identity mattered enough to design for.** 11.2's committed `brier_gain_vs_best = +0.0864`
is a reported result. A "pure refactor" that moved probabilities in the last bits would silently
invalidate it, so both changes preserve the **RNG call order and the summation order** — the
optimization computes the same `X[ai] @ beta` on the same rows, not an algebraically-equal
rearrangement. (A faster algebraic bootstrap — per-draft sums/counts, 460× — was measured and
**rejected**: exact in exact arithmetic, but it consumes the RNG differently, so the replicate draws
would not match. Speed on a 0.79 s component was not worth breaking comparability.)

**Consequence for Session G:** the 16.9 availability-Brier non-regression gate can be run at full
committed scale for ~5 min, so the "reduced sample" compromise it was scoped under is no longer
needed for the confirmation run.

## ✅ T15 — simulated draft-slot dispersion is flat in board depth — **DONE 2026-07-27 (steps 0–4)**

> **★ RE-MEASURED 2026-07-28 by 16.14R step 7** (60 seeded drafts x 9 seasons, shipped room
> `REALISTIC_ROOM`). **Four of the five bars improved on what T15 shipped** — profile distance
> **0.222 → 0.116**, round-1 mean 4.36 → **3.70**, harvest excess +0.21 → **+0.06 sd**, dispersion
> level error **+17.0 % → +5.6 %** — and the 11.2 Brier is **unchanged at +0.0890**. The open
> seat-faithfulness gap closed by about a third on all three of its statistics (median `pool_rank`
> 10.40 → **9.38**, moderate band 13.5 % → **27.8 %**, chalk 19.6 % → **10.6 %**).
>
> **⚠ Bar 2 now marginally FAILS and has been left failing.** 30.07 % of consensus top-12 players
> fall past pick 10 against a **30.0 %** ceiling, on n = 5,700 — binomial se 0.61 pp, so the miss is
> **+0.12 se** and is not distinguishable from the ceiling; the p95 half passes (19.0 ≤ 20.0) and
> the **2026 live board passes outright at 26.3 %**. The direction is a deliberate trade: the room
> dropped from two `autopilot` seats to one, and `autopilot` is the seat that *absorbs* elite
> players before they can fall. **Whoever picks this up should decide explicitly** whether to accept
> a 1.5 pp elite-fall cost for the realism/profile/dispersion/faithfulness gains, or re-add a
> chalkier seat — **and must not reweight a personality until the number crosses**, which is the
> anti-pattern 16.15 recorded.
>
> **Attribution measured, not asserted** (same code, 2021–24, 40 seeds, only the mix differing):
> the T15 room scores 28.72 % elite past-10 and the shipped room **29.47 %**, i.e. composition costs
> **+0.75 pp** — while profile distance falls 0.118 → **0.093**, dispersion error +10.4 % →
> **+6.5 %** and chalk share 19.9 % → **10.7 %**. That difference is itself **+0.51 se**, so the
> attribution establishes the *direction and the trade*, not a magnitude.
*(opened 2026-07-26, Session G, by the 16.9 done-bar · **escalated 🟡→🟠 and re-scoped 2026-07-27**
by a live human-in-the-loop mock draft — see `findings.md` §"Live mock draft (2026-07-27)")*

### ★ 2026-07-27 — measured from both sides, in the units a user sees, and it is worse than "flat"

A full 10-team mock was drafted by the user against `DEFAULT_ROOM`. Every reach he flagged as
impossible was real, and measuring the corpus proved him right on the number he guessed. Mean
|drift| in **10-team ADP picks**, simulator vs **1,420 realized human drafts / 197,227 boarded
picks (2017–2025)** via `adp/drift_panel.build_drift_panel`:

| round | corpus mean | **sim mean** | corpus p90 | **sim p90** |
|---|---|---|---|---|
| 1 | **3.3** | **11.4** | **6.6** | **27.7** |
| 2 | 5.7 | 15.2 | 12.4 | 30.8 |
| 3 | 7.8 | 9.4 | 16.5 | 15.2 |
| 5 | 11.6 | 12.8 | 25.2 | 19.5 |
| 8 | 15.1 | 10.3 | 35.6 | 20.3 |
| 12 | 18.0 | 21.4 | 35.8 | 33.4 |
| 15 | 27.1 | 15.0 | 51.7 | 23.6 |

**The corpus grows monotonically 3.3 → 27.1 picks; the simulator is flat at ~10–21 with no trend.**
So the defect is not "too wide" — it is **the wrong shape**: ~3.5× too wide in round 1 and ~1.8×
too *narrow* by round 15. A fix that only shrinks the softmax everywhere would make the late rounds
worse. (The user's own estimate before seeing any data — "5–8 picks is reasonable early" — matches
the corpus round-1 p90 of **6.6** almost exactly.)

**★ The fall side is the same defect and is the more visible failure.** Corpus players with ADP ≤ 12:
mean actual slot **pick 8.4**, only **23.7 %** fall past pick 10, **p95 = pick 17**. In the simulated
draft, Nacua (ADP 2.7) fell to **14**, CMC (5.1) to **19**, JSN (5.9) to **20**, J.Taylor (7.7) to
**21**, Achane (9.5) to **22** — five top-12 players past the corpus's 95th percentile *in one draft*
— and Rashee Rice (27.3) to **59**.

**★ The value leaks to the seats with no opinion.** Per-seat mean drift, in picks (+ = reached):
`autopilot` **−19.8** · `balanced` +4.3 · `safe_floor` +5.3 · `homer` +6.9 · `upside_chaser` +8.7 ·
`reacher` **+14.5** (max +52.2). The two autopilot seats finished **1st and 2nd** on top-9 consensus
projection. Everything the reaching seats spill is harvested by the ADP-followers, so "draft pure
chalk" is a free lunch this room serves and no real room does. **That is a cheap objective
regression test that needs no face-validity judgement: the autopilot seats must not systematically
out-value the room.**

### ★ Why the 7,699-draft corpus did not fix it — the arithmetic

`_ADP_SCALE = 50` and the fitted `adp_s = −1.683`, so **one ADP pick is worth 0.0337 utility**. In
those same units the other fitted coefficients are enormous: `is_TE` **+16.8 picks**, `need` **+14.1**,
`is_RB` **−12.1**, `fandom` **+35.5** (×2.5 for `homer` ⇒ **89**). The choice is then a softmax over
`CHOICE_TOP_K = 40` candidates spanning ~45 ADP picks in round 1, i.e. a **1.35 utility** spread end
to end: the 40th-best available is still **26 %** as likely as the best. Analytically that gives
`P(take the best available) = 4.8 %`, `P(20th-or-worse) = 33.8 %`, **expected reach 16.8 picks** —
before any personality tilt. Every observed reach (18, 26, 33, 42, 52) is that distribution.

**The fit is not wrong for the data it saw; the specification cannot represent the data.** `adp_s`
is linear in raw ADP pooled over every round, so one coefficient must simultaneously fit round 12
(top-40 spans ADP ~100–200) and round 1 (spans ADP 1–45). It compromises, and the compromise is
absurd exactly at the top of the board. **More data estimates a misspecified coefficient more
precisely.** That is why the F.5 corpus expansion could not have helped here.

### ★ The functional form is measured, not guessed — and it is NOT log

Fitting the corpus width against pick number: mean|reach| ∝ `pick^0.5…0.6`. A **log-ADP** utility
implies width ∝ `pick^1.0` (too tight in round 1, too wide at depth); the current **linear** term
implies `pick^0.0`. So the honest candidate is a **fractional power** (`adp^~0.45` in utility, or a
free exponent fit jointly), *not* the log transform an earlier read of T15 suggested. Rank-in-pool
transforms are also in-family. **Choose among them by refit log-loss, not by curve-fitting to this
table** — the table is the acceptance bar, not the estimator.

### ★ Acceptance bars (state before running — T5 habit)

1. Mean and p90 |reach| by round track the corpus curve above (esp. round 1: mean ≈ 3, p90 ≈ 7).
2. At most ~1 of the consensus top-6 survives past pick 10; no top-12 player past ~pick 17.
3. ~~**The `autopilot` seats stop systematically out-valuing the room.**~~ **REWRITTEN 2026-07-27**
   (user design review, *before* the session runs — a pre-registered bar must not change mid-flight):
   **the surplus an ADP-following seat harvests must match what the corpus's most ADP-faithful
   managers harvest** in the 1,420 real drafts. The standings half of the old bar is **withdrawn** —
   the user's objection is correct and decisive: a seat taking the best available *should* finish
   well, and "don't fight the sharp market" (Phase 2) says so. Autopilot's mock win was not skill,
   it was the **−19.8 picks of spill** the reaching seats handed it. Surplus is the defect; ranking
   never was. **Measure the corpus side of this in step 0** — same drift panel, one extra groupby.
4. 11.1 log-loss gain (+0.1738) and 11.2 availability Brier (+0.0708 banded) do not degrade.
5. The 16.9 depth profile is re-checked — its shock was calibrated under the old dispersion, so
   `NarrativeShock.intercept` is not transportable across this change (*a coefficient is not
   transportable without its controls*, again).

### ☑ Step 0 done (2026-07-27) — the harness exists and the baseline is frozen

`draft/mock.py` + `steps/t15_0_baseline.py` + `steps/mock_draft.py` + `tests/test_mock.py`; frozen at
`analysis/t15_baseline.json` over **900 seeded drafts** (8 FFC seasons × 100, plus 100 on 2026). No
model changed. Full writeup: `findings.md` §"T15 step 0". **Three things the register said that the
900-draft measurement corrects or sharpens:**

1. **"The simulator is flat" is superseded** — that was one draft. Spearman(round, mean|drift|) is
   **+0.646** (corpus +1.000): the sim curve *rises* to round 9 and then **turns over**. State the
   defect as the **ratio column**: **4.24× at round 1 → 0.57× at round 15**, crossing 1.0 at ~round 11.
2. **Bars 1 and 2 tighten** on the FFC-only corpus (1,144 drafts, ECR-boarded 2025 excluded per
   `adp/boards.py`): round-1 mean **2.87** / p90 **5.23** (was 3.3 / 6.6). Bar 2 measured at scale is
   worse than the anecdote: **57.9 %** of consensus top-12 fall past pick 10 vs the corpus's **18.9 %**;
   sim p95 **30.0** vs **17.5**. The live mock's five falling elites were the *median* draft.
3. **Bar 3 is already roughly passing, and the quantile form of it was wrong.** At *fixed* `pool_rank`
   edges the simulated chalk seat harvests **+20.5** against a human chalk seat's **+17.6** (corpus sd
   **17.0**) — inside the spread. The quantile form reports +20.4 vs +8.5, an artifact of comparing
   `pool_rank` 1.28 to 4.28. **Bar 3 should be read on the fixed-edge harvest curve only.**

**★ What step 0 found that the bars did not ask for — the missing middle.** Corpus seats: median
`pool_rank` **7.62**, **54.3 %** in the 2–8 band, **0.2 %** chalk (<2). Simulated seats: median 12.27,
**2.2 %** moderate, **19.6 %** chalk. The room is bimodal and has **no moderate drafters**, so T15's
target is the *distribution* of deviation, not its scale. Separately, `autopilot` at 2-of-10 seats
over-represents a behaviour that is 0.2 % of real seats by ~100× — **a 16.15 composition question, not
a T15 model change** (it does not reopen 16.14R's "autopilot: no change", which was about its *win*).
Also unasked-for and invisible in any mean: simulated within-bin harvest sd is **2.1–3.7** picks
against the corpus's **8.7–17.0** — the seats are far too homogeneous even where the means match.

### ☑ Step 1 done (2026-07-27) — respecified, and two selection criteria thrown out

`AdpSpec` + `BandSpec` in `draft/opponent_model.py` are now the single owner of a choice that had
**four** uncoordinated copies (fit, simulator, and two picks→utility inversions in `apply_hype` and
`reach_cap`). Both persist **next to β** and are read back with it. Grid: 4 bands × 11 exponents,
walk-forward on 23,934 real choice groups; every exponent inside a band refits from one built frame
(`build_choice_frame` keeps raw `adp`; `respec_adp` re-derives the column).

**The exponent is an estimate, and the two criteria agreed on it.** `fixed40`'s held-out log-loss has
an **interior** minimum at **p = 0.45** (3.2453 vs 3.2687 for the incumbent linear spec) — and the
width law independently derives p ≈ 0.4–0.5 from the corpus's measured `pick^0.5…0.6`. ⚠ A
4-draft/season smoke run had put the minimum at the grid *boundary* (reading as "the data want
log-ADP"); that was a budget artifact. **An optimum at your grid's edge is usually a statement about
your sample size.**

**★ Two selection criteria failed and were replaced — both would have shipped the defect:**

1. **"Gain over the ADP-only baseline" is not a selection criterion.** Inside `fixed40`, log-loss is
   minimized at p=0.45 while gain is maximized at **p=1.00, the incumbent linear spec**. Gain rises
   when the *baseline* gets worse, and a linear ADP term cripples ADP-only far more than a model
   that also has position dummies and `need`. Replaced by **`band_coverage`** — how often the
   candidate set fails to contain the pick a human actually made. A property of the set, not of a
   likelihood's normalization, hence comparable across bands and ungameable.
2. **A uniform width metric traded away the defect it was built to fix.** Averaged over all 15
   rounds it selected p=0.60, whose round-1 mean is 8.9 picks (realized 2.9) and which **fails the
   elite-fall gate** (p95 24.0 vs a 20.0 ceiling). Objective restricted to rounds 1–6, and **the
   gate made a hard constraint rather than a term** — a gate a metric can out-vote is not a gate.

**★ The shipped `fixed40` band was violating the Session-G contract and nobody had measured it.**
Coverage says it excludes the realized human pick **3.95 %** of the time — 1 in 25 real picks sat
outside the candidate set the fitted β was being applied to. `widen+5` (k = 40 + 5/round, cap 160)
cuts that to **0.78 %** and is the narrowest band inside the stated 1 % tolerance. This is the
judgement-free justification for widening; it also dissolves **T16** as a side effect.

**★ Structural limitation, recorded rather than closed.** Realized round-15 mean |drift| is **27.1
picks** and no exponent gets the room past ~13. At pick 150 ~30 boarded players remain and the room
takes near-best-available; a realized late pick often lands 40 picks off consensus because *that
room's managers held different boards*. That is board **heterogeneity between managers**, which this
simulator cannot express — all ten seats share one board by construction. **Bar #1's late half stays
open**; the fix is per-seat board perturbation, which belongs with 16.14R (direction), not T15
(width).

**Also shipped: `Personality.width_mult`** — 16.14R's *width* half only, pulled forward on the user's
instruction (`signal_weights`, the direction half, is untouched). `β_adp_s / width_mult`, because
width `∝ 1/|β_adp_s|`; depth-correct by construction, which is why it replaces `max_reach_picks` as
the primary reach control. autopilot 0 · chalk 0.55 · safe 0.8 · balanced 1.0 · homer 1.2 · upside
1.35 · reacher 2.0. Early effect: the missing middle largely closes — `moderate_share` 2.2 % →
**52–62 %** against a corpus 54.3 %.

### ☑ Steps 2–4 done (2026-07-27) — shipped, with one bar re-opened and re-closed on the way

**Shipped configuration:** `AdpSpec(power, p=0.15)` · `BandSpec(widening, k0=40, +5/round, cap 160)`
· `WidthCurve(γ=0.8)`, β refit under all three, specs persisted beside the coefficients. Pre-T15 β
preserved at `analysis/phase11_opponent_model.pre_t15.json`.

**★ Step 2 shipped a spec that step 3 caught trading one defect for another.** At `p=0.15, γ=0` the
elite-fall gate passed and 11.2's Brier *improved* (+0.0708 → **+0.0890**), but the room went
**uniformly too narrow** (rounds 2–15 at 0.94 → 0.26× the corpus width) and bar #5, the 16.9
dispersion match, broke: **+8.8 % → −53.6 %**. The register predicted this failure mode in advance
and it still landed — what caught it was measuring the bars **together in one run**, plus reporting
the full-profile distance next to the round-1 gate. **Bar #1's implementation was itself a lesson:**
a round-1-only pass criterion reported PASS while the curve it summarized had gone 0.388 → 0.791,
i.e. worse than before the fix. *Do not summarize a curve by one of its points.*

**★ Cause: the width derivation ignores pool exhaustion, so one knob cannot set both ends.**
`w_a ∝ a^(1-p)` assumes an unbounded local pool; by round 15 ~30 boarded players remain, so a seat
cannot deviate 27 picks from a board with less depth than that. Predicted late growth at p=0.15 was
~18×, measured **1.8×**. Curvature therefore buys little late width while costing full price at the
top — an **identification** problem, not a tuning one. Resolved with the round function T15 already
owed §16.14R: `personalities.WidthCurve`, giving **`width(round) × multiplier`**.

**★ The joint sweep: 16 (exponent × γ) configurations, both gates as hard constraints, one
survivor** — `p=0.15, γ=0.8`, which is *also* the best profile match in the grid (**distance 0.190
vs the pre-T15 baseline's 0.388**). The constrained optimum being the unconstrained one is the only
reason this reads as a fit rather than a threshold picked to admit a winner.

**☐ Still open, and deliberately not closed: the seat-faithfulness population.** Median `pool_rank`
**10.27 vs a corpus 7.62**; moderate band **14.3 % vs 54.3 %**. It trades directly against the reach
profile (the γ=0 configuration hits 65.9 % moderate but fails dispersion), it was never one of T15's
five bars, and closing it requires giving seats genuinely **different boards** — per-seat board
perturbation, which is 16.14R's *direction* half. Handed forward as a measured trade-off.

**☐ 16.9's `NarrativeShock.intercept` is now formally stale.** A size in utility units calibrated
under the old transform; β's scale changed, so it is meaningless. **Not re-fit** — 16.9 measured it
as unidentified (a 50× sweep moved the target less than its own between-run noise), so inventing a
value would manufacture precision. Instead `NarrativeShock.calibrated_under` + `assert_transportable`
now **refuse** to apply it across a spec change. Fourth instance of *a coefficient is not
transportable without its controls*, and the first caught before shipping.

### ★ 2026-07-27 — scheduled: this is the NEXT session (user decision)

The user chose **(a)**: a T15 respecification session runs **before Session I / Phase 17**, which
slides one session. The ordered plan (harness → respecify + refit → two judgement-free gates →
joint 11.1/11.2/16.9 re-verify + `NarrativeShock.intercept` re-fit → clip only if still needed)
lives in `PLAN.md` §2026-07-27 and is summarised in the `CLAUDE.md` ★★★ pointer. Two implementation
traps recorded there and repeated here because they are easy to miss: **(i)** `adp → adp_s` is built
in **two** places that must not diverge — `build_choice_frame` (fit) and `candidate_matrix` (sim) —
so extract one shared `adp_feature()` before changing either; **(ii)** the sim column in the table
above is **one draft**, so build the seeded ≥50-draft batch harness *before* the model change or
there is no usable before/after baseline.

**Hard clips are an override, not the fix.** A per-seat `max_reach_rounds` candidate filter (drop
candidates whose ADP exceeds `overall_pick + 1.5 × n_teams`) plus a top-25 fall cap would make the
room look right immediately, which matters for Phase 14. But they sit **outside** the fitted model
and silently move 11.2's Brier and 16.9's calibration, so they must ship labelled, documented and
separable from the estimated path — never confused with a modelling result. Note also that
`Personality.max_reach_picks` does **not** already do this: it clips only a seat's *own opinion*
(`signal_weights` + fandom excess), which is why `balanced` — no signal weights, no cap — produced
the draft's 42-pick reach.

---

**Symptom (original, 2026-07-26).** Realized cross-draft dispersion rises steeply with board depth — Spearman(`sd_drift`,
ADP rounds) = **+0.679** over 1,346 matched player-seasons. The simulator, with the choice-set band
correctly applied, is **+0.077**: essentially flat. The pooled *level* is right (1.976 vs realized
1.816, 8.8 %); the *shape* is not. Consensus top-of-board players are simulated as far more
volatile than they are, and deep fliers as far less.

**Why the 16.9 shock does not fix it** (measured, not assumed). `top_k` is a **hard rank filter
applied before utility**, so an additive utility shock cannot pull a player into the candidate set —
it only reshuffles within it. A player at ADP rank 100 cannot be taken until ~60 ahead of him are
gone, whatever his shock. Sweeping the shock over a 50× range moved the slope by less than its own
between-sample noise.

**Where it actually lives.** `adp_s = adp / 50` makes utility **linear in raw ADP**, which produces
dispersion that is roughly uniform *in rank* — exactly the flat profile measured. Real drafting is
sharp at the top and diffuse at depth.

**Fix (an 11.1 respecification, hence not done here):** either a **depth-varying candidate set**
(soft or widening band instead of a hard top-40) or **curvature in the ADP term** (log-ADP or
rank-based `adp_s`), then refit and re-verify against 11.1's log-loss gain (+0.1738), 11.2's
availability Brier (+0.0708 banded) **and** the 16.9 dispersion profile together — a change that
improves one of those and quietly degrades another is the failure mode to guard against.
*(2026-07-27: the measurement above supersedes "log-ADP" specifically — the measured exponent is
~0.5–0.6, so log over-corrects. Both mechanisms are still the right family.)*

**Who is affected.** Mock-draft realism and the honest `P(available at your pick)` readout
(16.12) — deep sleepers currently look more reliably gettable than they are. **Not** the frozen
value stack, which is untouched by all of this. ~~Worth doing before Phase 14 surfaces availability
numbers to a user; not worth blocking Session H on.~~ **Re-scoped 2026-07-27: this is now the
user-facing blocker on mock-draft realism** — the first time a human sat in the room, it was the
only thing he commented on, unprompted, four separate times. It is the strongest candidate for the
next build session (user decision pending; the alternative in the queue is Session I / Phase 17).

---

## ✅ T16 — a curated hype row cannot express in a standard 15-round league
*(opened 2026-07-26, Session G (2/2), by the 16.10 done-bar)*

**Symptom.** The 16.10 apply path works, but its effect depends on whether the claimed player is
inside the drafted range at all. At the league-standard **15 rounds** (150 picks against a 201-deep
2026 board), a **+12-pick** claim on Daniel Jones (board rank 171) produced a **bit-identical**
30-draft result — not a small effect, *no* effect — and only moved once the utility offset was
raised roughly fivefold. At **18 rounds** the same claim resolves normally. The 16.10 done-bar
therefore runs at 18 rounds, and its passing gates should be read as "the mechanism is correct",
not "these claims will be visible to a 15-round drafter".

**Why.** `top_k` admits only the top-40 available by ADP, so a board-rank-171 player enters a
candidate set only in the final handful of picks of a 150-pick draft. An additive offset applied to
a player who is almost never a candidate changes almost nothing. Compounding it, the measured
**elasticity is ≈0.44 realized picks per claimed pick**, so even an in-range claim is a nudge.

**Consequence for the product.** Of the 20 directional claims on the current board, the deep ones
(ADP > ~150: Cam Ward, Germie Bernard, Rashod Bateman, Brandon Aiyuk, Brian Robinson Jr.) are the
*most* likely to be genuine sleeper narratives and the *least* likely to express in the format most
users actually play. A hype board that visibly does nothing is worse than no hype board.

**Fix options, cheapest first.**
1. **Scale the offset by depth** in `apply_hype` so a deep claim gets the utility it needs to enter
   the band — a workaround, and it breaks the clean "`pick_delta` means an equivalent ADP shift"
   contract, so it must be documented if taken.
2. **Fix it properly via T15.** A depth-varying candidate set (soft/widening band) is the same
   change T15 already prescribes, and it dissolves this problem as a side effect: deep players
   become reachable candidates, so an offset on them has somewhere to act.
3. **Surface the limitation** rather than fix it — have `availability_readout` mark a claim as
   `unexpressible` when the player's ADP is beyond the league's pick count. Cheap, honest, and
   worth doing regardless of 1 or 2.

**Recommendation: (3) now, (2) with T15.** Do not do (1) alone — it trades a documented contract
for a cosmetic effect.

> **✅ 2026-07-28 — RE-MEASURED AND CLOSED (16.14R step 7).** The 16.10 done-bar was re-run at
> **15 rounds** on the live 2026 board: **sign agreement 1.00** against a 0.75 bar, elasticity
> 0.57 picks per claimed pick, mean |shift| 2.63 picks, **14 of 20 claims resolvable** (6
> unresolved, all deep). T15's widening candidate band dissolved this exactly as predicted —
> a deep curated claim now moves the room inside a standard league, where T16's own evidence
> was a *bit-identical* 30-draft result. The honest residue: **6 claims still cannot express**
> at 15 rounds, so the 18-round demonstration stays as the fuller check.
> `analysis/phase16_14r_t16.json`.
>
> _(Prior status, kept.)_ **◐ 2026-07-27 — option (2) SHIPPED; T16 very likely dissolved, NOT re-measured.**
> T15 shipped `BandSpec(widening, k0=40, +5/round, cap 160)`, so the candidate set is no longer a
> hard top-40: by round 15 it admits **110** players (and the still-available pool is smaller than
> that, i.e. **everything remaining is in contention**). A board-rank-171 player is therefore a
> genuine candidate late in a 15-round draft, which is exactly the mechanism T16 said was missing.
> Two supporting changes landed with it: the band was widened on **measured** grounds (`fixed40`
> excludes the realized human pick **3.95 %** of the time), and `apply_hype` now converts a
> `pick_delta` through the **exact** utility difference rather than the linear derivative, so a deep
> claim gets the utility it actually implies instead of a top-of-board approximation.
>
> **What is still owed before this can be marked ✅:** re-run the 16.10 done-bar **at 15 rounds** and
> confirm a deep curated claim now moves the room. T16's own evidence was a *bit-identical* 30-draft
> result at 15 rounds; the closing evidence has to be the same test coming out different. Until that
> is run, this is a mechanism that should work, not a measured fix.

**Who is affected.** Mock-draft realism and the 16.12 readout for deep players only. **Not** the
frozen value stack. Not a blocker for Session H.

---

## ✅ T17 — the live season has no per-player availability; the Phase-5 cloud halves
*(opened 2026-07-26, Session H, found by 16.13's enrichment coverage report · **CLOSED 2026-07-27**)*

> **☑ FIXED 2026-07-27 (Session H2), exactly as specced below.**
> `injury.projected_availability_frame(con, season)` builds the target-season frame from the most
> recent completed season, carrying covariates forward and taking `team_games` from the schedule
> rather than `week.nunique()` of an unplayed season; `availability_projection` falls back to it and
> **stamps `covariate_source` (`observed` | `rolled_forward`)** so the substitution is visible in the
> output rather than inferred. The cohort prior keeps the population it was written for.
> **Result: the 2026 level ratio goes 0.37 → 0.721**, against 0.683 on the 2025 holdout.
>
> **The guard shipped with it and is the durable half.** `distribution.level_ratio` +
> `assert_level_band` (band 0.55–0.85 on the top 60 by projection) now run in
> `steps/phase5_5_utility.py` **on the holdout *and* on the live unplayed season — the one that
> breaks**. A guard that only runs where the data is complete would not have caught this.
>
> **One honest caveat, printed rather than buried:** the rolled-forward path sits *above* the
> observed path's tight 0.638–0.683 range, because a draft-day forecast cannot condition on a player
> appearing. That is unconditionality, not a defect — but a live number is mildly optimistic
> relative to how the backtest seasons scored, and the step says so.
>
> **Knock-on that mattered more than the fix:** repairing this turned `games_played_mean` from four
> cohort constants into a real forecast **and, in the same move, into a level proxy** (+0.46…+0.90
> with `mean` within position), which silently converted `safe_floor`'s durability weight into a
> quality tilt. Consequence 2 below is therefore obsolete in a way that *created* work: see
> `enrichment.residual_shape`'s `durability` column. **An upstream data fix can break a downstream
> signal by making it better.**

**Symptom.** On the 2026 board the frozen distribution is roughly **half** the consensus projection
it is built from. Top-60 `mean / proj_points`: **0.37 in 2026 vs 0.75 in 2025**. The ratio tracks
`games_played_mean` exactly — 6.60 vs 12.85 — so the level loss is entirely the availability
multiplier, not the projection.

**Root cause, verified.** `injury.availability_projection(con, season)` predicts each player's
hazard at *his own covariates for the target season*, read from `availability_frame(con, [season])`
— which is built from `weekly`. A season that has not been played has no weekly rows, so:

```
availability_projection(con, 2025) -> 299 rows
availability_projection(con, 2026) ->   0 rows      # <- every player, no exceptions
```

Everyone therefore routes to the T3-A rookie/backup cohort prior, which is a per-(pos × draft
capital) constant: **4 distinct `games_played_mean` values across all 480 players**, and a mean of
~7 of 17 games for the whole league. The cohort prior is *correct for the population it was built
for* (players with no prior-season hazard); it is being applied to everybody.

**Two distinct consequences, and they are not equally bad.**
1. **Levels are wrong for the live season** — `mean`, `q10`, `q90`, `ce_value` are all ~halved.
   Anything that shows a user a projected point total for the season they are drafting is wrong by
   about a factor of two. This is the part that must be fixed before Phase 14.
2. **`games_played_mean` is inert as a signal** — with 4 distinct values it carries position and
   draft capital and nothing else. `corr(games_played_mean, mean)` = **+0.79 / +0.80 / +0.00** for
   2022 / 2025 / **2026**. `safe_floor`'s durability weight therefore does nothing on a live board
   and does work on backtest seasons; kept weighted deliberately, since the defect is upstream and
   temporary while the intent is permanent.

**What is NOT affected.** *Relative ordering within position* is nearly untouched, because the
collapse is close to a common multiplier — which is exactly why 16.14 standardizes every signal
**within position** before weighting it, and why the personality set is unaffected by this entry.
Rankings, VBD, and the cost report all read `value_board`, not the distribution, and are untouched.
The lockbox eval ran on 2023/2024, both fully played, and is untouched.

**Fix.** The target-season covariate read needs a fallback that does not depend on the season
having been played: predict at the player's **most recent completed season's** covariates (with an
age/experience roll-forward), falling back to the cohort prior only for players who genuinely have
no history — which is the population it was written for. Roughly: in
`availability_projection`, when `availability_frame(con, [season])` is empty, build the frame from
`season - 1` and carry it forward, stamping the result so the substitution is visible rather than
silent. `team_games` must then come from the schedule (17), not from `week.nunique()` of an
unplayed season.

**Guard to add with the fix.** A gate asserting the distribution's `mean` sits within a stated band
of the consensus projection it was built from — the check that would have caught this the day the
2026 board landed. `steps/phase5_5_utility.py` is the natural home.

**Who is affected.** Any consumer of `player_distributions` / `cached_distribution` **for a season
that has not started** — i.e. the live product, and nothing that has been validated so far. Not the
frozen value board, not the optimizer's ranking behaviour, not the lockbox. Not a blocker for
Session H or I; **is** a blocker for Phase 14 surfacing per-player distribution numbers.

---

## ✅ T18 — `avg_reach` in the manager profiles is a board mismatch — **DONE 2026-07-29**
*(opened 2026-07-27, Session H2, found while sanity-checking 16.15's room composition)*

**Status ☑ done.** The column is **gone rather than repaired in place**, because silently
redefining a stored column's meaning is this repo's most-repeated failure mode (F.5's hardcoded
`scoring="ppr"`, T19's changed `floor`). What replaces it says what it is:

* `sleeper.redraft_reach(con)` → `drift_panel.manager_panel(con)` — `build_drift_panel` (eligible
  human redraft snake drafts, **each scored against its own board**) joined back to `picked_by`.
  A separate function, not a new `PANEL_COLS` entry: those columns are the contract the *simulated*
  panel also fills, and a corpus-only column would break the "a function reading PANEL_COLS cannot
  tell sim from corpus apart" property the whole T15 harness rests on.
* `sleeper_manager_profiles` now carries **`avg_reach_rounds`** (mean drift, in rounds) and
  **`n_reach_picks`**. A manager with no eligible redraft picks is `NaN`, not 0.
* `validate.manager_reach_gate` (±2 rounds) is wired into `data_health_report` — the gate the
  original entry asked for by name.

**Measured on the rebuilt table (24,696 managers, 8,212 with an eligible reach):**

| | old (pooled board, picks) | new (own board, rounds) |
|---|---|---|
| mean \|reach\| | **35.8** | **0.776** (p1 −3.33 / p99 +4.26) |
| range | −532.8 … **+1411.7** | −10.8 … +10.5 |
| mean | +24.8 | +0.008 |

**★ The sign flips, which is the part that settles it.** Scored against each draft's own board, QBs
go **later** than consensus (−0.576 rounds), not ninety picks earlier. The original number was not
an exaggerated behaviour, it was a different quantity wearing a behaviour's name.

_(Original entry below.)_

**Symptom.** `sleeper_manager_profiles.avg_reach` reports a mean **QB reach of +91.9 picks**. No
manager reaches ninety picks for a quarterback; the number is not describing drafting.

**Root cause.** The stored per-manager reach is each pick's ADP minus its actual slot, where the ADP
comes from a **pooled** board while the picks come from drafts of many league sizes, scorings and
formats (the F.5 corpus is 7,699 human drafts spanning redraft, dynasty, 2QB and IDP). A superflex
or 2QB draft takes quarterbacks dozens of picks before a 1-QB consensus board says they should go,
and the difference is booked as manager behaviour. This is the F.5 `scoring="ppr"` lesson one level
down: *a derived per-entity statistic inherits every mismatch between the entity's context and the
reference it is scored against.*

**Why it has not bitten yet.** Nothing consumes `avg_reach`. 11.3's personalities are hand-set
tilts, not fitted from profiles, and 16.15's corpus check deliberately routes around it — position
share is computed **from picks alone, with no ADP reference**, which is why that check is
trustworthy where `avg_reach` is not.

**Fix.** Score each pick against the board for **its own draft's format** (size, scoring, superflex
flag are all on `sleeper_drafts`), or restrict the profile to the eligible-redraft subset the rest of
the behavioural work already filters to. Either way, add a range gate — a mean reach outside roughly
±2 rounds is a join defect, not a manager.

**Who is affected.** Nobody today. It becomes load-bearing the moment a manager-facing "you tend to
reach" readout (Phase 14) or an 11.3 refit keyed on profiles lands, so it is worth fixing before
either — and it is cheap while the corpus is fresh.

---

## 🟠 T19 — the `floor` signal is inverted at board depth (censored `q10`)
**Status ☐ · opened 2026-07-27 · fix in 16.14R Step 2, before any personality consumes it.**

**Symptom.** `safe_floor` drafts boom-or-bust players. Found by the user reviewing a 15-round mock by
eye: Zay Flowers (round 2), Malik Nabers (post-injury), Carnell Tate (rookie), Quentin Johnston,
Jaydon Blue — *"a lot of these guys are relatively boom-or-bust"*. The seat's aggregate z-means look
fine (`floor` +0.198, `bust_prob` −0.129 against `balanced`), which is why no gate caught it.

**Root cause — `q10` is censored, and residualizing a censored variable manufactures the inverse of
the intended signal.** `enrichment.residual_shape` builds `floor` = `q10` with `mean` regressed out
within position (16.14's fix for "the raw quantiles are just level"). But on the 2026 board **`q10`
is exactly 0 for 79 of 184 offensive rows = 42.9 %** — 59.0 % of players past ADP 100, only 5.7 %
inside ADP 50. A linear fit through a floored variable predicts a *negative* q10 for
replacement-level players, so anything sitting just above the censoring point scores a large positive
residual. Measured consequence:

| position | `corr(floor, adp)` | reading |
|---|---|---|
| RB | **+0.179** | the "safety" signal prefers **later** players |
| WR | **+0.124** | same |
| QB | −0.171 | ok (QB `q10` is rarely censored) |
| TE | −0.182 | ok |

The highest-`floor` players on the live board are the ones the user objected to:

| player | pos | ADP | mean | q10 | `floor` |
|---|---|---|---|---|---|
| Jonah Coleman | RB | 171.1 | 35.2 | 1.3 | **+30.4** |
| Jaydon Blue | RB | 140.0 | 38.7 | 1.8 | **+28.6** |
| Zachariah Branch | WR | 164.6 | 62.6 | 11.1 | **+38.7** |
| Zay Flowers | WR | 25.6 | 198.9 | 98.1 | +19.8 (4th-highest WR) |

**So the seat was not misbehaving against its spec — it drafted exactly what the board told it was
safest.** Removing the level did not make the signal orthogonal to quality; it made it
*anti*-correlated with quality among low-mean players. **This is the fourth member of the
level-vs-shape family** (`q90`/`q10` 16.14 · `games_played_mean` T17 · `vbd` this session), and the
first where **the fix for the previous instance created the next one**.

**Second defect in the same seat: two of its three weights are inert.** `boom_prob` is exactly 0 for
**64.7 %** of offensive rows and `bust_prob` for **56.0 %**, so `safe_floor` spends 0.35 of its 1.10
weight budget on a column that cannot fire for most of the board. *An inert thing still passes*,
fourth instance.

**Fix.**
1. Replace the linear residualization with a **censoring-aware** fit (Tobit), or drop to a
   rank-based conditional quantile — q10 percentile within an ADP neighbourhood rather than a global
   within-position regression.
2. Decide `boom_prob`/`bust_prob` explicitly: widen the Phase-5 threshold so they discriminate, or
   remove them from `SIGNAL_COLS`. Do not leave an inert weight in a shipped personality.
3. **Acceptance bar, stated as an opposition:** `corr(floor, adp) <= 0` within **every** position,
   and the top-10 `floor` list is not dominated by ADP > 130 players.

**Who is affected.** `safe_floor` today. `upside_chaser` uses the same machinery on `upside` and is
very likely to carry the mirror-image defect — **check it in the same pass**. Nothing frozen: the
enrichment is 16.13, read-only and DEV-only.

---

## 🟠 T20 — no roster-legality guarantee, and no DST on any board
**Status ☐ · opened 2026-07-27 (user instruction) · fix in 16.14R Step 1.**

**Symptom.** In a 10-team / 15-round mock, **no seat drafted a single team defense** and `autopilot`
averaged **0.16 kickers per seat** over 60 drafts. Every roster is therefore an illegal starting
lineup against `RosterSlots` (`k=1, dst=1`), which is invisible to the measurement harness (the drift
panel filters to offense) and immediately visible to a user in the Phase-14 mock.

**Root cause, two independent halves.**
1. **DST is filtered out of every board.** `adp/boards.py::_ffc_board` requires
   `gsis_id IS NOT NULL`; team defenses have no gsis and carry `ffc_player_id` instead. The data is
   present and good — 60 `DEF` rows for 2026 FFC PPR 10-team, with stdev, bye and draft counts
   (SEA 94.7, DEN 100.9, LAR 106.5). Everything downstream is **already built for them**:
   `board_player_key` name-keys defenses *by design* ("re-implementing the fallback is how a joiner
   silently misses team defenses"), `canon_pos` maps `DEF→DST`, `DRAFTABLE` includes `DST`.
2. **Nothing forces roster legality.** `draftable_pool` enforces *soft* position caps only — it
   steers away from over-drafting, never toward completing a lineup. A pure-ADP seat consequently
   never reaches kicker ADP (128–163) inside 15 rounds.

**Fix (user's stated contract: guarantee ≥1 K and ≥1 DST whenever `rounds >= slots.starters`).**
1. Thread `include_dst` through `_ffc_board`/`resolve_board`, **default OFF** so the 11.1 fit path
   and the drift panel stay byte-identical; `mock.room_board` turns it on.
2. Add `DraftState.mandatory_needs(team)` = unfilled **non-flexable** starter demand
   (`base_demand()` minus `flex_positions` ⇒ QB/K/DST). In `draftable_pool`, when a team's remaining
   picks equal its unfilled mandatory slots, restrict the pool to those positions — **a hard filter
   applied before utility**, the same class of object as `BandSpec`, so it does not change what the
   fitted β means.
3. Gate the whole rule on `rounds >= slots.starters`, exactly as specified.
4. **Fix T21 in the same pass** — it is what makes step 1 safe.

**Done.** A test asserts every seat ends with ≥1 K and ≥1 DST at `rounds=15`, and that **no** forcing
occurs at `rounds < 9`. Re-run the seeded batch and confirm T15 bars #1/#2 are unmoved.

**Note for whoever does this.** The drift panel (`adp/panel.py` `OFFENSE`, `_CANON` maps offense
only) drops K/DST automatically, so **no T15 measurement moves** when defenses join the board. Verify
that rather than assuming it.

---

## 🟠 T21 — K/DST are in the simulation candidate band but not the fit's
**Status ☐ · opened 2026-07-27 · fix with T20 (16.14R Step 1c).**

**Symptom.** `value_hawk` drafted Brandon Aubrey (K, ADP 128) at **pick 119** — a kicker nominated by
a β that was never estimated on kickers.

**Root cause.** `opponent_model.build_choice_frame` takes `skill_only: bool = True` and filters the
candidate set to `("QB", "RB", "WR", "TE")` — *"candidates are skill players only (K/DST availability
is trivially late)"* — and that is the default the shipped β was fit under. But
`personalities.make_opponent_pick_fn` bands the **whole board** by ADP, and the board carries 17 `PK`
rows. So the simulation's candidate set is a superset of the estimation set.

**This is the Session-G choice-set contract violation in a second home.** The first was
`make_opponent_pick_fn`/`simulate_survival` simulating against the whole board when the fit used
`top_k=40`; it inflated simulated draft-slot dispersion 59 %. The lesson recorded then was: *when a
fitted model gets a new caller, check the caller reproduces estimation-time conditions before
trusting the output.* The K path was missed because kickers are rare enough in a 15-round draft that
the effect is a handful of picks rather than a shifted distribution — **an aggregate metric cannot
see an occasional impossible event**, T15's own lesson.

**Fix.** Exclude K/DST from the model's candidate band so the sim matches `skill_only`, and let the
T20 roster-completion rule fill those slots outside the choice model. Add a test that fails if the
sim's candidate positions and `build_choice_frame`'s ever diverge — the same shape as the existing
`CHOICE_TOP_K` guard.

**Why it must land with T20.** Putting DST on the board (T20 step 1) *without* this fix would hand
the fitted β a second position class it never saw, making the mismatch worse rather than better.

---

## ✅ T19 / T20 / T21 — closed by 16.14R (2026-07-28)

All three were opened by the 2×5 mock and closed by the seven-step execution order. Full write-up in
`findings.md` §"16.14R steps 1–7"; the durable lessons are in `glossary.md`. Summary of what shipped:

**T19 ☑** — `floor` is no longer inverted. **The ticket's own framing was wrong**, which is the part
worth remembering: it said *OLS is the wrong likelihood for a censored variable*, and both repairs
that framing admits failed — `tobit` left a **100 %**-deep top-10, a neighbourhood `rank` on the raw
quantiles flipped `corr(upside, floor)` to **+0.94 QB**. The fix was the **scale**: rebuilding the
signals as ratios to the projected level (`shape_inputs`) puts a censored player at the *bottom* of
a bounded quantity. Shipped `residual_shape(method="rank")` on ratios — `corr(floor, adp)` ≤ 0 in
every position, top-10 deep share **70 % → 20 %**, `corr(upside, floor)` −0.49. `boom_prob`/
`bust_prob` were not repaired but **re-diagnosed** (see **T22**) and replaced by `tail_risk`.

**T20 ☑ — but see 🔴 T23, which partially reopens it (2026-07-28).** The deadline filter guards
QB/K/DST and **skips TE**, so 12.2 % of seats still finish unable to field a legal lineup. The
done-bar below asserted only the two positions the ticket was written about, and passed while the
same mechanism was broken for a third. Read T23 before treating this as closed.

**T20 ☑** — `include_dst` (default OFF, on only in `mock.room_board`) plus a **deadline filter**
(`DraftState.mandatory_needs`): **60/60 seats finish with ≥1 K and ≥1 DST at 15 rounds, 0/60 at 8**.
The register's own warning held — no T15 measurement moved (round-1 mean 4.36 → 4.36, elite-fall p95
17.0 → 17.0), because the drift panel filters to `OFFENSE` before measuring. **Verified, not
assumed.** Known side effect: round 14 now contains no offensive picks at all.

**T21 ☑** — `SKILL_POSITIONS` is one constant read by `build_choice_frame` and by the simulator, with
a test that fails if they diverge. The 11.2 availability Brier is **unchanged at +0.0890
CI[+0.0803,+0.0996]** against T15's shipped +0.0890, so aligning the candidate sets cost nothing.

---

## ✅ T22 — `boom_prob`/`bust_prob` are stale by construction on a live board — **DONE 2026-07-29**
**Status ☑ done · opened 2026-07-28 (found while fixing T19) · frozen layer, so read around, not
edited.**

**★ "Nobody is affected today" was wrong when it was written.** The original entry judged the
column latent because no personality weights it. It was already being **printed to a human**:
`steps/mock_draft.py`'s BEST AVAILABLE table shows BOOM and BUST at every turn, so on the live 2026
board the interactive drafter was told that **Bijan Robinson, Jahmyr Gibbs, Puka Nacua, Jaxon
Smith-Njigba and Ashton Jeanty never boom** (`boom_prob` exactly 0.000, because none of them played
in 2022) — with a `.2f` that reads like a measurement. *A column's consumers are not only the models
that weight it.*

**Fix (read-only, the frozen contract untouched):**

* `enrichment.live_volatility(con, season)` → `boom_prob_live` / `bust_prob_live`, the same
  estimator (`variance.weekly_volatility`) measured on **season − 1**;
* `enrichment.volatility_source` picks that season **from the `weekly` table, not from a constant**
  — the whole defect was a constant that fell four years behind the data — and asserts the lag is
  ≤ `VOL_MAX_LAG` (1). The guard T17 earned, stated where it can fire;
* unseen players stay **NaN**, never 0.0. The CLI prints "-" for them, and gained a `TAIL` column
  (`tail_risk`), which is what 16.14R shipped as the honest boom-or-bust read;
* `ENRICH_VERSION` bumped to `v3-t22-live-vol` so every cached board rebuilds.

**Measured on the 2026 offensive board:** `bust_prob` exactly zero **56.0 % → 8.2 %**, `boom_prob`
**~65 % → 18.5 %**, and **corr(frozen, live) = 0.026** on the 165 players in both — the frozen
column is not a stale version of the live one, it is unrelated to it. 50 players the frozen column
calls "never busts" bust in >20 % of 2025 weeks, including Breece Hall, Ladd McConkey and Malik
Nabers.

**The `max(train_seasons)` sweep the entry asked for, done and recorded.** Exactly two instances of
the pattern *"a live season reads a **covariate** from the newest training season"* ever existed:
`injury.availability_projection` (**T17**, fixed) and `variance.weekly_volatility` here (**T22**).
Every other `DEV_SEASONS`-defaulted `train_seasons` in `src/` is a **fit** — quantile, rookie,
conformal, injury hazard, news multipliers — where training on strictly-prior DEV seasons is the PIT
discipline working as designed, not a staleness bug. One forward-looking note, not a defect today:
`app/streamlit_app.py`'s season selector is `list(DEV_SEASONS)`, so the Phase-14 MVP cannot yet
select the season anyone is actually drafting.

_(Original entry below.)_

**Symptom.** On the 2026 board `boom_prob` is exactly 0 for **65.2 %** of offensive rows and
`bust_prob` for **56.5 %**. T19 recorded this as *inert*. It is worse than inert.

**Root cause.** `distribution.season_distribution` reads
`variance.weekly_volatility(con, [max(train_seasons)])` — the *prior season's* realized weekly
rates. But `train_seasons` defaults to `[s for s in DEV_SEASONS if s < season]`, and `DEV_SEASONS`
ends at **2022**. So for **any** season after 2022 — including the one a user is drafting — these
columns are the **2022** rates. Verified: of the 480 rows in the 2026 distribution, 39.2 % join
`weekly_volatility(2022)` and **100 % of those match exactly**; of the 306 `bust_prob == 0` rows,
**292 are `fillna(0.0)`** — players who were not in the league in 2022.

**Why that is not merely inert.** A zero here does not read as "unknown", it reads as *never busts*.
It is a confident, false, **safety** claim, and it is worst precisely for the rookies and
second-year players a floor-seeking manager should most distrust. `weekly_volatility` itself is
fine — measured directly on 2025 it has `bust_prob == 0` for only **3.4 %** of players.

**Who is affected.** Nobody today: 16.14R routed `safe_floor` and `upside_chaser` onto `tail_risk`
(built from the current quantiles) and `test_personalities` asserts no shipped personality weights
either column. It becomes live the moment (a) a new consumer weights them, or (b) Phase 14 surfaces
a boom/bust number for the season being drafted — which is the T17 failure exactly.

**Fix.** Not here: the Phase-5 contract is frozen and lockbox-evaluated. The honest options, for
whoever picks this up — pass an explicit `train_seasons` at the live-season call site (the T17
pattern: roll the covariates forward), or compute a live boom/bust in the 16.13 enrichment where
it is DEV-only and read-only. **Do not edit the frozen column.** Either way, add the guard T17
earned: assert the volatility source season is within one year of the target.

**Note for whoever does this.** The same `max(train_seasons)` idiom appears wherever a live season
reads a "prior season" input. T17 was one instance, this is another; a sweep for the pattern is
probably worth more than either fix alone.

---

## ✅ T23 — the T20 roster-legality guarantee misses TE
**Status ☑ done 2026-07-28 · opened the same day (2×5 mock re-run, found by the user's eye) ·
partially reopened T20.**

> **As built.** `mandatory_needs` is now simply `slots.base_demand()` — FLEX is excluded from it by
> construction, so nothing is exempt and a roster-shape change is picked up for free. The induction
> argument in the docstring is the safety proof, and `tests/test_draft.py` executes it.
>
> **Measured over 40 seeded drafts × 10 seats × 9 seasons** (`analysis/mock_room_bars_{baseline,
> t23}.json`, one harness both sides): seats that could not fill a *dedicated* slot **23.2 % → 12.3 %**,
> and the half that was **avoidable** — a slot the season's board could actually have supplied —
> **12.08 % → 0.03 %**. The residual is unavoidable: 2017-era FFC boards carry fewer than ten kickers
> or defenses for ten seats, which no policy can fix, so `roster_legality` reports the two separately
> rather than pretending the bar is 0 %.
>
> **No T15 bar moved, verified rather than assumed** (T20's own note): round-1 mean **3.5242 →
> 3.5242**, profile distance 0.1074 → 0.1052, bar 2 identical at p95 19.0 / 29.74 %, bar 5 −5.99 % →
> −5.72 %. The drift panel filters to `OFFENSE`, so K/DST/TE deadline picks are dropped on the
> measurement side exactly as predicted.

**Symptom.** Over 40 seeded 15-round drafts, **49 of 400 seats (12.2 %) finish unable to field a
legal starting lineup**, and **100 % of the failures are a missing TE** — QB, RB, WR, K and DST are
never short. By seat: `autopilot` **46.2 %**, `balanced` / `reacher` / `safe_floor` 5.0 % each,
`value_hawk` 0 %.

**Root cause — one line, and it reads a membership backwards.** `DraftState.mandatory_needs`
(`src/fantasy_quant/draft/simulator.py:149`) computes unfilled starter demand and then drops every
position in `slots.flex_positions`, which is `("RB", "WR", "TE")`:

```python
owed = {p: n - counts.get(p, 0) for p, n in self.slots.base_demand().items()
        if p not in flex}          # <-- TE leaves here
```

The docstring's reasoning is correct for RB and WR and wrong for TE. A team short one RB still
fields a legal lineup because the FLEX absorbs it. A team with **zero TE cannot fill the dedicated
TE slot**, and nothing else can go there. **TE is in `flex_positions` because a TE may fill FLEX,
not because anything may fill TE.** So T20's deadline filter guards QB/K/DST and silently skips the
one position that actually goes unfilled.

**Fix.** Mandatory need = the full `base_demand()` (1 QB / 2 RB / 2 WR / 1 TE / 1 K / 1 DST); FLEX
stays the only substitutable slot, and it is excluded from `base_demand()` by construction, so the
change is to delete the `if p not in flex` filter and the `flex` local.

**Why that is safe, not over-constraining.** `draftable_pool` applies the filter only when
`picks_remaining <= sum(need.values())`, and a position leaves `need` the moment its demand is met —
so every pick taken from the forced pool decrements the sum by exactly one and the condition stays
satisfiable by induction. Worst case it binds 8 picks from the end; in practice RB/WR demand is long
since met and it binds at 3–4, exactly as today. Still gated on `rounds >= slots.starters`.

**Done-bar.** 0 illegal rosters over ≥40 seeded drafts × 10 seats, asserted on the full lineup
(`QB≥1, RB≥2, WR≥2, TE≥1, K≥1, DST≥1`) rather than on K/DST alone; plus the T20 checks unchanged,
and confirm no T15 bar moves (the drift panel filters to `OFFENSE`, so it should not — **verify,
do not assume**, per T20's own note).

**★ The lesson, which is about the verification and not the code.** T20's done-bar was *"60/60 seats
finish with ≥1 K and ≥1 DST"* — the two positions the ticket was written about. It passed, while the
same mechanism was broken for a third position nobody thought to assert. *A guarantee stated as "no
unfillable starting slot" must be tested against the whole lineup, not against the slots that
motivated the ticket.* Sibling of the 16.14 "state your bars as oppositions" lesson: **a bar written
from the symptom passes the general defect.**

---

## ✅ T24 — the room was too wide at the top of the board (the *private board* prescription was wrong)
**Status ☑ done 2026-07-28 · opened the same day · the T15 carry-forward, closed by a different
mechanism than the one it named.**

> **The objection, measured honestly for the first time.** Consensus-elite players (ADP ≤ 2.5) clear
> pick 4 in **26.6 %** of simulated drafts against a realized **13.1 %** — seating-marginalized, 8
> seasons, `analysis/mock_t24_sweep_shuffled*.json`. Every earlier number understated it: a
> fixed-seating batch reads 5–7 pp lower, and no number of extra seeds fixes that (see the seating
> confound in `findings.md`).
>
> ### ★ The prescription was built and rejected
>
> This entry proposed `adp_seat = adp + κ · adp_stdev · ε` as *one mechanism for three problems*. It
> is implemented (`personalities.private_adp`, `stdev` added to `PASSTHROUGH_COLS` — the column
> genuinely was unread), and it is **monotonically harmful on the objection it was designed for**:
>
> | seating-marginalized elite past pick 4 | κ = 0 | κ = 1 | κ = 2 |
> |---|---|---|---|
> | `base` 0.70 | **18.8 %** | 19.7 % | 26.6 % |
> | `base` 0.50 / γ 1.0 | **11.2 %** | — | 23.4 % |
>
> **Why: at the top of the board `adp_stdev` is the same size as the gaps it perturbs.** Bijan 0.7 ·
> Gibbs 0.8 · Chase 1.0 sit ~0.2 picks apart, so a per-seat draw of ±κ·0.8 does not *create* tier
> structure — it **destroys the ordering that was already there**, which is exactly how an elite
> falls. The measured corpus law `|drift| ≈ 2 × adp_stdev` is real but is about **realized** drift,
> an outcome of the whole room; re-injecting it as **per-seat perception noise** is a different
> object. *A relationship measured on outcomes is not a specification for the mechanism.*
>
> Kept in the code, **default-off**, with the verdict written onto `analysis/phase11_opponent_model
> .json` beside the parameter. **Nothing may switch it on without re-running the sweep.**
>
> ### ★ What fixed it: the width *level*, separated from the width *shape*
>
> `WidthCurve` became `width(round) = base · round^gamma`. `base` is how wide round 1 is, `gamma` how
> fast width grows with depth — one number until now, which is why T15 concluded *one knob cannot set
> both ends*. With two:
>
> Final measurement, the **40-seed seating-marginalized pair** (`analysis/mock_room_bars_
> {baseline_shuffled,t24_shuffled}.json`):
>
> | | before | after | corpus |
> |---|---|---|---|
> | `WidthCurve` | `base 1.0 · γ 0.8` | **`base 0.6 · γ 1.0`** | — |
> | **elite past pick 4** | 25.8 % **FAIL** | **15.3 % PASS** | 13.1 % |
> | bar 2 · p95 / past-10 | 17.0 / 28.8 % | **16.0 / 25.2 %** | ≤ 20 / ≤ 30 % |
> | bar 3 harvest | 0.00 sd | 0.00 sd | ≤ 1.0 |
> | bar 5 dispersion | −7.1 % | **−11.4 %** | ±20 % |
> | bar 1 round-1 mean | 3.33 | **2.64** | 2.87 |
> | bar 1 profile distance | 0.107 | **0.089** | — |
> | median `pool_rank` | 8.69 | **8.04** | 7.62 |
> | moderate share | 33.7 % | **38.2 %** | 54.3 % |
>
> γ 0.8 → 1.0 keeps **90 %** of the old round-15 width while `base` narrows round 1 by 40 %.
> **The cost, stated:** dispersion −7.1 % → **−11.4 %** — narrowing the top takes spread out of the
> whole room and only `gamma` gives it back — comfortably inside bar 5. Everything else moves *toward*
> the corpus, including bar 1's profile distance (0.107 → **0.089**), which is what separates `base
> 0.6` from the `0.5` that shipped an hour earlier: 0.5 overshoots to **tighter than real humans**
> (11.3 % past-4) and pays 0.154 distance and −17.4 % dispersion for it.
> The fixed-seating sheet agrees (past-4 11.3 %, dispersion −12.2 %), and the 2026 live board reads
> p95 **16.0** / 24.4 % past pick 10.
>
> ### ⚠ Two measurement notes that outlive this ticket
>
> 1. **`ceiling_saturation` never bound** (1.5–2.3 % at every κ), so the "the budget, not the belief,
>    is picking" hypothesis that motivated the gate was **wrong**. Kept as a standing check anyway.
> 2. **The round-1 half-split is not resolvable at this sample size** — the same room reads 0.54 /
>    0.82 / 1.11 / 1.22 across measurement configurations, because a few large first-half reaches
>    dominate a mean over ~1,600 picks. **The landing *share* (n ≈ 640) is the bar; the rise is a
>    diagnostic** until it gets a trimmed estimator.
>
> ### Next, if the residual is ever worth more (15.3 % vs 13.1 % says it is not, today)
>
> The top-of-board gaps (0.2 picks) are smaller than any width the fitted β can express, so the top
> ~6 are near-interchangeable to every seat; `base` works by making the whole room follow those gaps
> more faithfully. The surgical version is a **steeper `AdpSpec.exponent`** with `base`/`gamma`
> restoring depth width — the three-knob form of T15's trade. ⚠ That **refits β**
> (`steps/t15_1_respecify.py`); it is not an artifact edit.

---

## ✅ T25 — the corpus reach ceiling is applied to 2 of 10 seat types, so the disciplined seats look tamer than the average one
**Status ☑ done 2026-07-28 · opened the same day · shipped with T24, as its own entry said it should be.**

> **As built.** `ROOM_CEILING = ceiling_only()` is the floor of discipline **every** seat inherits:
> `reach_budget=None` now means *inherit the room ceiling*, not *unconstrained*. It is a ceiling
> only — no count tiers, no early clamp — because the reacher's quiet opening is a deliberate spec
> and imposing it room-wide would flatten every seat into the same round 1. `unbounded_budget()`
> exists so the A/B controls that measured a genuinely unconstrained seat
> (`steps/phase16_14r_5_reacher.py`) still measure that, instead of silently re-pointing at the new
> default and changing what an already-run done-bar meant.
>
> **Measured (`analysis/mock_room_bars_{t23,t25}.json`).** `balanced` — the seat nothing bound — R1–3
> `pool_rank` **6.36 → 5.98**, overall **10.19 → 9.32**; `upside_chaser` R1–3 **10.80 → 8.76**. The
> room moved *toward* the corpus on every population statistic: median `pool_rank` 9.31 → **8.85**
> (corpus 7.62), moderate share 28.8 % → **32.7 %** (corpus 54.3 %), profile distance 0.1052 →
> **0.0894**, round-1 mean 3.52 → **3.35**, bar 2 past-10 29.7 % → **29.0 %**, bar 5 −5.7 % → −8.1 %.
> Unlike T23 this **does** move the bars, which is expected: it constrains eight seat types that were
> previously unconstrained.
>
> ⚠ **The done-bar's ordering was written wrong and is not claimed.** It asked for
> `autopilot < chalk < safe_floor < value_hawk < balanced < reacher` in R1–3; what ships is
> `autopilot 1.00 < chalk 2.05 < safe_floor 3.37 < reacher 4.91 < balanced 5.98 < upside 8.76 <
> value_hawk 10.09`. Both deviations are the ticket's own analysis contradicting its own bar: the
> reacher sitting below `balanced` in R1–3 **is the user's 2026-07-27 spec** (`early_rounds=3`), which
> this entry states two paragraphs above the bar, and the value hawk is a bounded value argmax, which
> is the most deviant thing in the room by construction wherever its window allows. *A done-bar
> written from a symptom can contradict the fix it is attached to* — sibling of T23's lesson.

**Symptom.** In rounds 1–3 the `reacher` is **more chalk than `balanced`** — mean `pool_rank`
**4.99 vs 6.44**, mean reach **+1.89 vs +2.76** over 40 drafts. (Overall the ordering is correct —
reacher 13.40 vs balanced 11.74 — so this is a *depth-localized* inversion, not a broken seat.)

**Root cause.** `ReachBudget` is attached to **`reacher` and `value_hawk` only**; the other eight
shipped personalities carry `reach_budget=None`. So `CORPUS_REACH_P95[0]` = **14.6 picks** binds the
two seats that were given discipline and *nothing* binds `balanced` — which is **4 of 10 seats** in
`REALISTIC_ROOM`. The reacher's rounds-1–3 quiet is itself correct and specified (`early_rounds=3`,
`early_max_picks=8.0`, `medium_from_round=3`, `large_from_round=5`, user spec 2026-07-27, from *"a
real reacher does not open with one"*). **The asymmetry is the bug, not the budget.**

**Fix.** Apply `round_ceiling=CORPUS_REACH_P95` room-wide as a floor of discipline every seat
inherits, with per-seat `ReachBudget` counts modulating on top. Note this is also **T24's cheap
half** — it clamps the round-1 symptom without fixing the shape, so ship it *with* T24, not instead.

**Second half — reporting.** The per-personality summary must lead with **`pool_rank`, split R1–13 /
R14–15**, not a 15-round mean reach. Mean reach over all rounds is dominated by late-board ADP noise
(`balanced`'s apparent edge came from R11–13 at +12.94: Tyler Allgeier at ADP 167 taken at pick 119
scores **+48** and means nothing) and by *when* a seat takes K/DST. **This mis-reporting is what
produced the objection in the first place** — see `findings.md` for both method errors.

**Done-bar.** `pool_rank` in R1–3 orders `autopilot < chalk < safe_floor < value_hawk < balanced <
reacher`; no seat exceeds `CORPUS_REACH_P95` by round; the reacher's R4+ behaviour is unchanged.

⚠ **Do not fix this by raising the reacher's `temperature` or `width_mult` in the early rounds.** Its
direction channels (`cos`, `rookie`, `upside`, hype) are structurally dead at the top of the board —
every consensus elite is an established veteran with compressed within-position z-scores — so width
with nothing to steer it is precisely the *"width with no direction"* that 16.14R step 5 deleted.
The channel that is live in round 1 is **T24's private board**.

---

## 🟡 T26 — the profiles' position shares are pooled across formats, and `mgr_lean` reads them
*(opened 2026-07-29, found in the same audit that closed T18 — it is the sibling defect)*

**Symptom.** None visible. That is why it is worth writing down.

**Root cause.** `build_and_store_profiles` counts position shares over **every** complete human
draft in the corpus — measured 2026-07-29: 271k picks from `dynasty_2qb`, 212k from `2qb`, 202k from
`ppr`, 167k `dynasty`, 101k `idp`. `build_choice_frame`, since Session F.6, fits on the
**redraft-eligible** subset only. So a Tier-B feature of the shipped β — `mgr_lean`, defined as a
manager's share minus the table-wide mean share — is estimated on one population and applied to
another. Pooled QB share is **13.65 %** against the redraft corpus's **11.22 %** (and DEF 1.70 % vs
4.61 %, the tell that the pooled rooms have different roster rules).

**Why it is smaller than T18.** Two reasons, both measured rather than assumed. Per *manager*, the
scopes mostly agree — mean \|Δ QB share\| **0.83 pp** over the 2,816 managers with ≥20 picks in
both, median **0.00**, >5 pp for **3.3 %** — because a manager who shows up in the redraft corpus
mostly drafts redraft. And the pooled *baseline* enters as a constant per position, which a
conditional logit that already carries position dummies largely absorbs; what identifies `mgr_lean`
is the **spread** across managers, not its level.

**Fix.** Compute the shares on the eligible subset (the population the fit uses), or carry both and
let the consumer choose. Either is a few lines.

**When — and the reason to wait.** With the **next 11.1 refit**, never on its own. Changing
`mgr_lean` refits β, and β's scale is what `WidthCurve`/`AdpSpec` were calibrated against across two
full sessions (T15, then T24) — *a coefficient is not transportable without its controls*, the
repo's most-repeated lesson, and it applies to the controls' own controls. Spending that
re-verification on a sub-1 pp feature shift is the wrong trade until something else forces the refit.

**Who is affected.** The mock room's opponents, faintly and unmeasurably. Nothing user-facing.

---

## ✅ T27 — the board a human reads is not the board the seats optimize — **DONE 2026-07-30**
*(opened 2026-07-30, from the first fully-simulated ten-personality walkthrough —
`findings.md` §"The all-personality walkthrough (2026-07-30)")*

**Symptom.** `steps/mock_draft.py` prints a `PROJ` column. Every seat's utility, and `value_hawk`'s
whole objective, run on `base_value`. These are different quantities built from different means, and
on the live 2026 board the gap is large, non-monotone, and **unexplained by anything on screen**:

| QB | `proj_points` | Phase-5 `mean` | haircut | `base_value` |
|---|---|---|---|---|
| Drake Maye | 316.5 | 261.3 | **0.17** | **+68.5** |
| Jayden Daniels | 313.4 | 137.1 | **0.56** | **−101.6** |
| Trevor Lawrence | 290.8 | 246.0 | 0.15 | +53.4 |
| Joe Burrow | 299.3 | 162.5 | 0.46 | −55.6 |
| Kyler Murray | 261.9 | 127.3 | 0.51 | −92.1 |

Maye and Daniels are **3 points apart on the screen and 170 apart in the number that decides every
pick**. A user cannot audit that, and the natural reading is that the engine is broken.

**Root cause — not a bug, a missing bridge.** `assemble_value` merges `value_board` (`proj_points`,
`vbd`) with `utility.risk_adjusted_board` (`mean`, `sd`, `ce_value`, `ce_vbd`) and sets
`base_value = ce_vbd`. So the priced quantity is `ce_value − ce_replacement(pos)` where
`ce_value = Phase-5 mean − λ·Var`, λ = 0.01. Two things enter that the consensus projection knows
nothing about: the **T3 availability channel** inside the Phase-5 `mean` (`avail_p`, `rho`,
`crater_avail`, the cohort prior) and a **variance charge** that for a QB reaches ~119 points
(sd up to 109.2, median 75.2). `ce_replacement(QB)` is 119.4 on this board. The CLI shows the input
that is *not* used and hides both channels that move it.

**The level itself is correct and intended — the dispersion is the problem.** Mean haircut by
position: **QB 0.28 · RB 0.33 · WR 0.28 · TE 0.30**, which is Phase 4.4's measured level optimism
(bias 0.575) and the lockbox's 0.62, working as designed. What is new is the *spread* —
QB 0.15–0.56 (sd 0.12), RB 0.16–0.55, WR 0.15–0.58, TE 0.17–0.46.

**A second, mechanical half.** `proj_points` is **not** in `simulator.PASSTHROUGH_COLS`, so
`_prepare_board` drops it and `st.roster()`/`draftable_pool` never carry it. `steps/mock_draft.py`
re-attaches it by hand after `_prepare_board` (`cmd_start`, with a comment saying it is display-only).
That is correct and also a trap: **any new driver silently shows an empty column** — verified by
writing one on 2026-07-30 and getting `-` for all 150 picks. `optimizer.attach_value` adds only
`base_value` and `value`.

**Fix — display layer only. The frozen value stack is untouched; nothing here refits or re-scores.**
1. Put `proj_points`, `mean` and `base_value` in `PASSTHROUGH_COLS` and attach `proj_points` inside
   `mock.room_board`, so the re-attach cannot be forgotten. Additive: `_prepare_board` copies only
   columns the caller supplied, so an ADP-only board is byte-for-byte unchanged.
   ⚠ **Assert no personality can weight them.** They are *level* columns; a `signal_weights` entry on
   one would recreate the 16.14 level-vs-shape defect exactly. `SIGNAL_COLS` stays as it is and a test
   fails if any of the three is added to it.
2. The CLI board shows `PROJ` · `MEAN` · `BV` · `AVAIL` (`games_played_mean`) — the fourth column is
   the one that *explains* the first three.
3. **`mock_draft.py why "<player>"`** — print the whole chain for one player:
   `proj_points → Phase-5 mean → games_played_mean → sd → ce_value → ce_replacement(pos) → base_value`,
   with the arithmetic shown. This is the actual product fix: an auditable path from the number a
   human trusts to the number the engine uses.
4. `validate.value_scale_gate` in `data_health_report`: per-position median haircut reported, and the
   **auditability bar** below asserted.

**Pre-registered bars (state before running — the T5 habit).**
- **B1** every row the CLI prints for a drafted-range player (top-180 by ADP, skill positions) carries
  all four columns non-null, except where the player is genuinely absent from the Phase-5 cloud — and
  those print `-`, never a fabricated 0 (the T22 rule).
- **B2** `spearman(haircut, games_played_mean) ≤ −0.50` within **each** of QB/RB/WR/TE on the live
  2026 board. ⚠ **If B2 fails, that is a modelling finding, not a display bug** — it would mean the
  level cut is being driven by something other than projected availability. Record it, stop, and open
  a ticket; do **not** paper over it with a caption.
- **B3** `steps/mock_room_bars.py` reproduces `analysis/mock_room_bars_verify_20260729.json`
  **bit-identically** (distance 0.0894, round-1 2.64, elite past-10 25.24 %, dispersion −11.4 %,
  past-pick-4 15.3 %). A display change that moves a bar is not a display change.

**Done-when.** B1–B3 pass; `why` reproduces the chain to the digit; the gate is in the health report.

**Who is affected.** Every human who reads the mock board — i.e. the entire purpose of the drafter,
and Phase 14's board view inherits it verbatim.

**★ Why this is the T22 lesson again, one level up.** T22 was audited by grepping `signal_weights`,
which is why it sat on file as "latent" while the drafter was printing it. *A column's consumers are
not only the models that weight it.* `proj_points` is the same shape of defect and a much bigger
number: it is the **first** thing a human reads.

---

### ✅ RESOLVED 2026-07-30 (Session H.5 step 1) — shipped, and the gate found something

**What shipped.** `proj_points`/`base_value` added to `simulator.PASSTHROUGH_COLS` (`mean` was
already there) + `simulator.VALUE_SCALE_COLS`; `mock.attach_proj_points` called from `room_board`
**outside** the parquet-cache boundary — deliberately *not* folded into `enrichment.VALUE_COLS`,
because that would bump `ENRICH_VERSION` and force a 9-season cold rebuild for a column no model
consumes; the hand-rolled re-attach in `cmd_start` is deleted; the CLI board leads with
`PROJ · MEAN · AVAIL · BV`; `mock_draft.py why "<player>"` prints the chain, every line an identity
(`lambda*Var` as `mean − ce_value`, replacement as `ce_value − ce_vbd`) so it cannot drift from the
frozen stack it describes.

**The `SIGNAL_COLS` assertion, strengthened.** The spec asked for a test that `proj_points`/`mean`/
`base_value` never enter `SIGNAL_COLS` — but **`mean`, `vbd` and `overall_rank` were already in it**,
latent, weighted by nothing. Rather than a test that was already failing or a list edit that would
make the registry lie, the invariant moved to the point of use: new `personalities.LEVEL_COLS` +
a `Personality.__post_init__` guard, so naming a level column in `signal_weights` now raises at
construction. No shipped seat weights one, so it is a guardrail over a live invariant.

**★ The divergence this uncovered — the interactive room was not the shipped room.** Wiring the risk
model into the CLI revealed that `steps/mock_draft.py` built its nine opponents through
`personalities.make_room_pick_fn`, which had **no `risk` parameter**, while the batch harness used
`mock.full_room_pick_fn`, which does. `value_hawk` therefore ran the Phase-9 greedy in every batch
measurement in the repo and the plain behavioural softmax in every *human* mock — `balanced` wearing
its name, which is precisely what `assert_room_objectives` exists to prevent. The guard could not see
it because it only ran in the other builder. `assert_room_objectives` moved down into
`personalities.py` (re-exported from `mock`, no caller changed) and `make_room_pick_fn` gained the
same routing. *A guard that does not run on the path a human uses is not a guard* — T22's lesson
about display consumers, restated about assertions.

**Bars.** B1 **PASS** (183/184 drafted-range skill rows carry all four; Brandon Aiyuk has no upstream
consensus projection and prints `-`, the T22 rule). B3 **PASS** — bit-identical on every field
including the 2026 readout. **B2 FAILED at RB** and was neither softened nor papered over: the gate
ships red and the finding is **T31**.

---

## ✅ T28 — `team_value`/`portfolio_value` are slot-blind — **CLOSED AS A LABELLING FIX 2026-07-30**
*(opened 2026-07-30, same walkthrough)*

**Symptom.** `optimizer.team_value` is `Σ base_value` over every roster row;
`portfolio_value` adds the covariance cross-term and nothing else. `grep -n "starters" ` over
`draft/optimizer.py` returns **nothing** — there is no slot logic in the value path at all. A 1-QB
roster's second quarterback is therefore priced at full weight, in both directions:

| team | seat | QB2 | `base_value` contributed |
|---|---|---|---|
| T1 | balanced | Caleb Williams | **−101.6** |
| T4 | reacher | Kyler Murray | **−92.1** |
| T5 | upside_chaser | Patrick Mahomes | −55.6 |
| T3 | balanced | Jalen Hurts *(taken second)* | **+51.0** |
| T9 | value_hawk | Jaxson Dart | +33.1 |

Room total `base_value` 1,938; the QB2 line alone nets **−122**. Those players sit on a bench and
cost their teams nothing real.

**Consequence, measured over the ten walkthrough teams.** Spearman against the Phase-10 title
probability: `portfolio_ce` **+0.758** · `team_value` **+0.685** · starting-nine consensus projection
**+0.455** · **starting-nine Phase-5 mean +0.915**. The clean case is **T4 reacher — 9th of 10 on
VBD, 3rd of 10 on starting-lineup projection, 9th on title**; and T1, 7th on VBD and 2nd on title.

**Why it matters twice.**
1. `portfolio_value` is the **cost report's headline** ("portfolio CE + risk profile"), so a
   preference that buys depth is priced as though the depth plays.
2. `value_hawk` **optimizes it** (`objective="portfolio_ce"`), so this steers picks, not just
   reporting. Dart at 9.09 is the visible instance.

**Fix — a decision, and the frozen output must not move.** Two candidates:
- **(i) a starter-aware metric.** The machinery exists: `simulation.season.lineup_points_matrix` /
  `rosters_weekly` already compute exactly "what this roster can actually field", on the same shared
  draws (T6). Ship `optimizer.starter_value(roster, value_index, slots)` as a **second, labelled**
  metric — never an edit to `team_value`, because the cost report's numbers are frozen output and the
  lockbox is spent.
- **(ii) fix the label.** Keep `team_value` as *total roster capital*, stop presenting it as team
  strength, and print starting-nine value beside it everywhere (cost report, mock summary,
  walkthroughs).

**Recommendation: (ii) now, (i) as the additive labelled metric, and leave `value_hawk`'s objective
alone this session.** Changing the seat's objective refits nothing but does change the room's picks,
so it moves T15 bars 1/2/5 and the faithfulness population — that needs the full T24 treatment
(seating-marginalized, before/after on the shipped measurement path), which is its own sub-step.

**Pre-registered bars.**
- **B4** `starter_value` equals `team_value` exactly when the roster *is* the starting nine
  (self-consistency — a new metric that disagrees with the old one on the case where they must agree
  is wrong).
- **B5** `spearman(starter_value, title_prob) > spearman(portfolio_value, title_prob)` over ≥40
  seeded drafts × ≥4 DEV seasons, seating reshuffled per seed. ⚠ Pre-register the **direction**: if
  B5 fails, slot-blindness is costing nothing measurable and **T28 closes as a labelling fix only** —
  do not ship (i) on the strength of the ten-team walkthrough, which is one draw.
- **B6** the frozen cost report is **bit-identical** (`steps/spine_3_cost_report.py`), and so is
  `analysis/mock_room_bars_verify_20260729.json`.

**Done-when.** B4/B6 pass, B5 is measured and reported either way, and no surface calls a slot-blind
sum "team strength".

**★ The lesson to state.** *A sum over a roster is not a forecast of a lineup.* The metric was
built as "value over replacement, independent players" and is correct as that; it acquired the second
meaning by being the only team-level number anyone printed.

---

### ✅ RESOLVED 2026-07-30 (Session H.5 step 2) — closed as a LABELLING FIX, as pre-registered

**What shipped.** `optimizer.starter_value(roster, value_index, slots)` as a **second, labelled**
metric — never an edit to `team_value`, whose numbers are the frozen cost report's input. It calls
`simulation.season.lineup_points_matrix` (the Phase-10 solver, itself regression-tested against the
1.3 reference) rather than writing a third definition of "starting"; the pick-path fast form
`optimizer.starter_marginal` is closed-form and asserted equal to it on 120 random rosters. Every
team-level surface prints both, labelled **STARTABLE** vs **CAPITAL**.

**B5 FAILED, significantly and in the opposite direction** (200 seeded drafts x 10 teams, seating
reshuffled per seed, `steps/t28_starter_value.py`, `analysis/t28_starter_value.json`):

| metric | mean per-draft Spearman vs title probability |
|---|---|
| `team_value` (slot-blind) | **+0.8382** |
| `portfolio_value` (shipped headline) | +0.8202 |
| `starter_value` (T28) | +0.7971 |
| `starter_mean` (the walkthrough's +0.915) | +0.7920 |

`starter_value − portfolio_value` = **−0.0230, CI[−0.0407, −0.0055]**. The walkthrough's **+0.915 did
not replicate** — one draw of ten teams, exactly as the spec warned.

**★ Why, chased rather than assumed: in a sim that draws injuries, the bench is load-bearing.**
Bench value alone (`team_value − starter_value`) predicts title probability at **+0.711 (sd 0.175),
positive in 100 % of the 200 drafts**. Sweeping the blend `starter + w·(team − starter)` — the knob
`RiskModel.bench_weight` implements — peaks at **w = 0.90 (+0.8399)** against the shipped
**w = 1.0 (+0.8382)**, well inside the noise, flat from 0.7 to 1.2, with **w = 0 the worst point**.
A starter who misses games is replaced from the bench, so pricing depth at zero discards real
information. **The slot-blind sum was never wrong as a *predictor*; it is wrong as a *display*.**

The display claim survives, and the per-seat numbers show it is seat-dependent: the gap
`capital − startable` is **negative for every seat except `value_hawk`** (upside_chaser −229.5,
balanced −171.5, autopilot −144.9, … **value_hawk +152.0**), because only the seat that *maximizes*
the slot-blind sum hoards startable-elsewhere value on its own bench. That is the Jaxson-Dart-QB2
objection — a reporting distortion, not a predictive one.

**The T24 treatment ran anyway** (the user's decision was to switch it *with* the treatment): `--bench-weight 0.0`, seating-marginalized, one knob. Every gate still passes and only `value_hawk` moves, but **bar 1 profile distance 0.0894 → 0.1020** (+14 % relative) and **bar 5 dispersion −11.39 % → −12.48 %**, while its `pool_rank` drifts **10.12 → 9.23** — priced by the lineup it stops paying for bench depth and moves *toward* best-available, the opposite of what the room needs. So the swap is refused on two independent grounds: a worse predictor (B5) and a worse room (the treatment). `analysis/mock_room_bars_t28_benchw0.json`.

**The decision.** `value_hawk` keeps `objective="portfolio_ce"`; `bench_weight` stays **1.0**. The
user's choice was to switch it with the full T24 treatment; the treatment ran and the pre-registered
bar that authorises the switch failed first. The knob ships default-off and nests exactly —
`bench_weight=1.0` re-runs the greedy pick-for-pick (`test_phase9`) — so re-asking costs one flag.

---

## ✅ T29 — absolute probabilities are printed from a sim with a documented level bias — **DONE 2026-07-30**
*(opened 2026-07-30, same walkthrough)*

**Symptom.** `league_probabilities` returns `playoff_prob`/`title_prob` and every driver prints them
as bare percentages (`playoff 0.685  title 0.140`). What the lockbox actually established: title
Brier **0.088** with reliability on-diagonal — the championship calibration and the **ordering** hold
OOS — but playoff Brier **0.240** (recorded as *marginal*), unconditional coverage **72–77 %**, and a
residual season-sim level bias of **−113 pts/team** that T4 could not remove (κ is mean-preserving).
So the least trustworthy number in the stack is the one printed most confidently.

**Fix.** Cheap and entirely presentational.
1. `simulation.season.PROB_PROVENANCE` — one constant carrying `n_sims`, the lockbox Brier pair, and
   the "relative, not absolute" statement. Every driver that prints a probability prints it.
2. Report title probability **as a multiple of fair share** (`title_prob · n_teams`): a 10-team
   league's fair share is 0.100, so T9's 0.170 reads **1.70× fair share**. A ratio to the uniform is
   immune to the level bias, which is the honest way to publish this number.
3. Playoff probability keeps its number and gains the *marginal* label.

**Done-when.** No driver prints a bare probability; the mock summary leads with the fair-share
multiple. **Internal consistency check to keep:** title probabilities sum to 1.000 and playoff to
`n_playoff` (6.000 measured) — cheap, and it catches a broken sim immediately.

---

### ✅ RESOLVED 2026-07-30 (Session H.5 step 3)

`simulation/season.py` gained `PROB_PROVENANCE`, `fair_share`, `playoff_fair_share`,
`provenance_lines` and `assert_probability_sums`. Every driver that prints a probability leads with
the **fair-share multiple** (0.170 in a 10-team league → **1.70x**): the −113 pts/team level bias
moves all ten teams together, so it cancels in a ratio to the uniform and survives in the percentage.
The caption carries the *weak* numbers — playoff Brier 0.240 recorded as MARGINAL, 72–77 %
unconditional coverage — not only the flattering title Brier 0.088. New human surface:
`mock_draft.py summary --odds`, which asserts the structural identity (titles sum to 1.000, playoff
berths to 6.000) every time it prints.

---

## 🟡 T30 — `autopilot` is 1 of 10 seats against 0.2 % of real seats, and that has never been argued
*(opened 2026-07-30, same walkthrough)*

**Symptom.** `REALISTIC_ROOM` carries one `autopilot`. Realized full-autopick behaviour is **0.2 %**
of corpus seats (T15 step 0), so the room over-represents it **50×** — and it is precisely the seat
that manufactures the spill the rest of the room harvests. Walkthrough numbers: mean `pool_rank`
**1.77**, median **1.0** (i.e. usually *literally* the top of the board), harvest **+11.7 picks**,
the largest in the room; highest starting-lineup projection (2,009) on a 3rd-place title probability.

**Why it is a question and not a defect.** 16.14R cut the seat from two to one **on this exact
argument** and stopped, and bar 3 (harvest excess vs corpus-faithful managers) passes comfortably at
**+0.06 sd**. There is also a real defence: "one manager is asleep for part of the draft" is far more
common than "one manager autopicks all fifteen rounds", and the seat is the room's cheapest way to
represent it. That defence has never been written down or measured.

**Fix — argue it or change it, with a cheap A/B.** Replace the `autopilot` seat with a
**near**-autopilot (a `chalk`-shaped seat: `zero_out` features, cooled softmax, narrow width) and
re-measure seating-marginalized. `chalk` already sits between them behaviourally — walkthrough mean
`pool_rank` 3.38 / median 2.0, harvest +7.3 — so the swap is a small, legible move.

**Pre-registered bars.** All five T15 bars, the landing gate and the legality report unmoved within
noise; `bar3_harvest.worst_excess_sds` unchanged or lower; `median_pool_rank` no further from the
corpus's 7.62 than the shipped 8.04. **If every bar is flat, keep the autopilot seat and write the
paragraph** — a null here is a decision, not a failure.

⚠ **Do not delete the personality.** `autopilot` is also the deterministic control that reproduces
`pick_by_adp(noise=0)` exactly, which several tests rely on. This ticket is about **room
composition**, nothing else.

---

## ✅ T31 — on a live board the level correction inverts for players consensus projects as backups — **DONE 2026-07-30**
*(opened 2026-07-30 by T27's own pre-registered gate, Session H.5 step 1 — the bar was written to be
falsifiable and it fired)*

**Symptom.** `spearman(haircut, games_played_mean)` — where `haircut = 1 − mean/proj_points` — is the
claim that the Phase-5 level correction *is* the projected-availability discount. On the drafted range
(top-180 ADP) it holds almost everywhere and fails in one cell:

| season | QB | RB | WR | TE |
|---|---|---|---|---|
| **2026 (live)** | −0.902 | **−0.288 FAIL** | −0.538 | −0.838 |
| 2024 | −0.898 | −0.594 | −0.681 | −0.812 |
| 2022 | −0.643 | −0.716 | −0.773 | −0.662 |

**Off the drafted range the live board is far worse, and the tell is a sign.** Over the whole 2026
value index **22.8 % of rows carry a *negative* haircut** — Phase-5 `mean` **above** the consensus
projection, which a level correction cannot produce — against **0.4 % on 2024**. Per position the
correlation flips outright: **QB +0.474 with 59 % negative**, RB +0.225 / 42 %, TE +0.237 / 33 %,
WR −0.011 / 31 %. On 2024 the same whole-index numbers are −0.93 / −0.65 / −0.84 / −0.88 with ~0 %
negative, so this is a **live-season** phenomenon, not a depth phenomenon.

**Root cause — two quantities that agree for starters and diverge for backups.** The consensus
projection prices **role**: a backup is projected for 22 points because he sits behind someone. Our
level correction prices **availability**: `mean = H · (avail_frac / G_ref)`, an injury/games-played
discount. For a player consensus expects to start, role ≈ full and the two coincide — which is why the
identity holds at −0.6 to −0.9 on every historical board and at three of four positions on the live
one. For a projected backup they do not, and on a **live** season there is no realized prior-season
basis to shrink the per-game level `H` toward, so he inherits a starter-ish rate multiplied by ~11
expected games. The worst offenders have exactly that fingerprint:

| player | `proj_points` | `mean` | `sd` | `games_played_mean` |
|---|---|---|---|---|
| QB `00-0039923` | 22.3 | **102.9** | 78.2 | 11.2 |
| QB `BEC122142` | 22.1 | 75.2 | 73.8 | 7.7 |
| RB `00-0036893` | 22.4 | 54.4 | 42.9 | 11.4 |

**`sd ≈ mean` is the signature of a distribution built on nothing.**

**Confirmation, and two ruled-out alternatives.** Conditioning on "consensus thinks he starts"
(`vbd ≥ 0`) repairs the failing cell outright — 2026 RB **−0.288 → −0.599**, WR −0.538 → **−0.912**,
QB −0.902 → −0.976 — so the break is at the role boundary. **Rookies are not the cause** (non-rookie
RB ρ is −0.32 against −0.29 pooled, and the worst drafted-range offender, Ray Davis, is not a rookie).
Nor is it a thin tail: 22.8 % of the index.

**Why it was not fixed on the spot.** Session H.5 was a display session with a hard bit-identity bar on
every step; this is a modelling defect in the frozen Phase-5 level path. The honest interim is what
shipped: `validate.value_scale_gate` asserts the pre-registered −0.50 on the drafted range and reports
the whole-index numbers beside it, so the health report is **red for a real reason** rather than green
by a softened threshold. (Contrast **T12**, which is red for no reason — that one is worth silencing,
this one is not.)

**Fix — a sketch, not a prescription** (the register's own lesson: T13's and T24's filed prescriptions
were both wrong). The natural shape is a **role floor on the live-season level**: shrink `H` toward the
consensus per-game rate when there is no prior-season basis, so a player consensus prices as a backup
cannot inherit a starter's rate. That would make the haircut non-negative by construction, which is the
property being violated. It touches the frozen Phase-5 assembler, so it needs its own session and its
own before/after on the 2025 dress-rehearsal calibration (coverage 75.5 % uncond / 81.5 % cond) — a fix
that repairs the deep board and moves those is not a fix.

**Who is affected.** Nothing in the shipped room: the personalities weight *shape* columns, and
`base_value` off the drafted range is not reachable inside 15 rounds. It matters for **Phase 14**, which
will show a distribution for any player a user clicks, and for anything that later trusts `mean` below
replacement.

**★ The lesson, and it is about the bar rather than the defect.** B2 was written into the plan before
the number was known, with an explicit instruction not to soften it. It failed at one position out of
four on one board out of three — a result that would have been effortless to round off as "basically
fine" if the threshold had been chosen after looking. *A pre-registered bar earns its keep on the day
it fails by a little.*

---

### ✅ RESOLVED 2026-07-30 (its own session) — fixed, and **the filed cause above was wrong**

**All six pre-registered bars PASS** (`PLAN.md` §2026-07-30 session 4, written before the fix existed;
`analysis/t31_level_cap.json`, `steps/t31_level_cap.py`).

| bar | before | after | pass |
|---|---|---|---|
| B1 whole-board negative-haircut share | 38.75 % (186/480) | **0.00 %** (0/480) | ≤ 2 % ☑ |
| B2 drafted-range `spearman(haircut, games)` | QB −0.902 · **RB −0.288** · WR −0.538 · TE −0.838 | QB −0.906 · **RB −0.666** · WR −0.904 · TE −0.889 | ≤ −0.50 ☑ |
| B3 full-board `spearman` sign | QB **+0.474** · RB **+0.225** · TE **+0.237** · WR −0.011 | QB −0.980 · RB −0.879 · TE −0.949 · WR −0.936 | ≤ 0 ☑ |
| B4 `sd / proj_points` | median QB **3.57**; max **23.06** | median QB 0.367 (RB 0.460 · TE 0.464 · WR 0.490); max **0.903** | ≤ 1.0 / ≤ 3.0 ☑ |
| B5 historical bit-identity 2022/23/24/**25** | — | **byte-identical** (samples, games *and* summary) | ☑ |
| B6 T17 band + top-60 drift | 0.7210 | 0.7204, drift **0.078 %** | band + < 0.5 % ☑ |

**★ The register's cause line was wrong — and one line of code falsified it.** The entry above says a
live season "has no realized prior-season basis to shrink the per-game level toward". There is no such
branch. `train_seasons` is `[s for s in DEV_SEASONS if s < season]`, which for a **2024** board and a
**2026** board is the *same nine seasons* (2014–2022) — so the fitted QuantReg models are **identical**
between the board that fails the gate and the board that passes it. Whatever the defect was, it could
not be in the fit. **This is the third filed prescription in a row that would have been built and would
not have worked (T13's coupling seed, T24's private board, now T31's live-season branch.)**

**★ The measured cause: extrapolating a linear fit far below its own support.** The level is
`b0_tau + b1_tau * calibrated_mean` per position, fit on the **conditional cohort**
(`weeks >= 0.85 * season_games`) — necessarily starters. Intercepts are large and positive (**QB q50
`b0` = 169.35**, RB 68.95, WR 43.70, TE 36.24), so the fitted level exceeds the projection it is built
from for any `proj_points` under **272 (QB) / 187 (WR) / 170 (RB) / 150 (TE)**. Training support of
`calibrated_mean` bottoms out at **QB 34.1 / TE 11.0 / WR 12.0 / RB 4.9**; the **2026 board's median QB
`calibrated_mean` is 11.4**, below the training *minimum*. **56.4 % of 2026 QBs sit below training
support against 2.3 % on 2024 and 6.7 % on 2022.** It is **board depth, not season liveness** — the live
FantasyPros scrape carries 490 players down to `proj_points` 1.8, where the historical proxy board stops
at ~10 and only projects players with prior-season production.

**★ The low end is *additionally* selection-biased upward, which is why "don't extrapolate" was not
enough on its own.** A low-projection player who nonetheless played 85 % of a season is one who **won a
job**, so the training cohort's low tail is made of breakouts. Interpolating the fit to the origin was
tried on paper and rejected: the origin slope is still ~3.4× steeper than `1/correction`, so the sign of
the violation survives. The repair has to reach for the consensus level, not just refuse to extrapolate.

**★ A plain cap at `proj_points` was BUILT FIRST and was not enough — the tie mass is the tell.** It
moved the whole-board negative share **38.75 % → 8.1 %** and passed B4/B5/B6, but it left every capped
row at `haircut == 0`: a mass of players with a *low* `games_played_mean` and *no* haircut at all, which
is the identity failing in the other direction. **Full-board QB spearman went the wrong way,
+0.474 → +0.523**, and drafted-range RB got worse (−0.288 → −0.250). *Cap to the identity, not to the
boundary* — the shipped target is `proj_points * avail_p / g_ref`, which is exactly what
`value_scale_gate` tests (`haircut == 1 − avail_p/g_ref`, decreasing in games played). Same shape as
T19's lesson: **a one-sided repair is passed by the same defect pointing the other way.**

**The fix.** `quantile.consensus_level_cap` (pure) + four lines in `distribution.assemble_distribution`.
Gated on **`value_board.source`**, a column already in the frozen 4.2 contract: 2022/2023/2024/**2025**
are `proxy`+`rookie`, 2026 is 490/490 `consensus`. Applied to the **draws** rather than the quantile
band — `Y` is linear in the band, so scaling every draw is exactly equivalent and sidesteps the
`max(0, q10 − adj)` clamp's non-linearity. `games` is untouched: availability was never what was wrong.
Non-live rows multiply by **exactly 1.0**, which is exact in IEEE-754, so B5 holds *by construction*
rather than by tolerance. `ENRICH_VERSION` → `v4-t31-level-cap` (the 16.13 board caches read the cloud).

**★ It is a repair, not a replacement — the gradient is the evidence.** Share of rows whose level moved,
by ADP band: **1–24 → 0.0 %** · 25–60 → 2.9 % (median scale 0.988) · 61–120 → 11.9 % (0.971) ·
121–180 → 51.9 % (0.883) · undrafted → 96.5 % (0.443). The top of the board is *literally* untouched and
the effect ramps exactly where the fit runs out of support. Board-wide `sum(mean)` falls 41 155 → 33 998
(−17.4 %), essentially all of it below ADP 120.

**★ The 2025 calibration holdout was NOT spent.** The user pre-authorised one further read to check the
fix had not broken coverage. The source gate made it unnecessary: 2025 is proxy-sourced, so it is
bit-identical, and B5 verifies that **by hash** rather than by reading its calibration. The holdout is
still unspent for whoever needs it next.

**⚠ Method warning worth more than the ticket — a before/after harness that cannot fail is worse than
none.** The B5 control was run twice from a `git worktree` at the pre-T31 commit and **twice silently
executed post-fix code**: (1) the project installs **editable**, so `uv run --project <main>` from a
worktree resolves `fantasy_quant` to the *main* tree's `src`; (2) on the retry a persistent `cd` in a
chained command sent the *working-tree* run into the worktree instead. Both failures produced
**identical hashes** — which reads as "bit-identical, great", the exact answer the bar was hoping for.
Fix: `PYTHONPATH=<worktree>/src`, and assert the control produces a **known difference** before trusting
it to show none. Recorded in `steps/t31_level_cap.py`'s docstring.

### ✅ T30 — RESOLVED 2026-07-30 (Session H.5 step 4): argued, measured, and deliberately not changed

**The A/B.** `autopilot` → a second `chalk` seat (zero-out overrides, temperature 0.6,
`width_mult` 0.55 — already the nearest thing in the library), seating-marginalized over
40 seeds × 8 seasons × 10 seats on the shipped measurement path.
`analysis/mock_room_bars_t30_chalk_swap.json` vs `analysis/mock_room_bars_h5_baseline.json`.

**Result: every gate passes in both rooms, and the trade splits cleanly by category.** Realism
improves a lot — chalk share (`pool_rank` < 2) **11.0 % → 2.4 %** against a realized **0.2 %**,
moderate share 38.2 → **48.3 %** (corpus 54.3 %), median `pool_rank` 8.07 → **7.92** (corpus 7.62),
round-1 mean \|reach\| 2.64 → **2.77** (corpus 2.87). Two reach bars regress slightly — profile
distance 0.0894 → **0.0914**, elite past-10 25.24 → **26.21 %** (ceiling 30 %). Landing, legality and
bar 3 are unchanged to the digit.

**Why it was not shipped.** The rule was fixed before the run: *change the mix only if every bar holds
or improves*. Two did not. The regressions are small and the gains are large, so this is a live
candidate for a deliberate overrule rather than a settled null — but the point of agreeing the rule
first is that it decides the borderline case instead of the borderline case deciding the rule.
Reversing it is one flag on `steps/mock_room_bars.py --room ...`.

**The argument the ticket asked for.** `autopilot` at 1-of-10 is **not** defensible as a frequency
claim: 0.2 % of realized seats behave that way, so the room over-represents it ~50×, and its overall
`pool_rank` of **1.23** (the literal best available, almost every pick) is what produces most of the
sim's 11 % chalk share. It **is** defensible as a **role** — it is the deterministic control that
reproduces `pick_by_adp(noise=0)` exactly and several tests depend on it. And the suspicion that
motivated the ticket does not survive measurement: **bar 3 (harvest) reads 0.00 excess sds in both
rooms**, so the spill this seat manufactures is not currently being harvested by anybody. Net: it
costs realism on the faithfulness axis and costs nothing on the axis it was suspected of corrupting.
**Do not delete the personality** — this was always a composition question.

---

## ☑ T33 — `n_teams` in the value hawk is the room size, not the league size
**Status ☑ DONE 2026-08-01 (Session VH.1) · opened 2026-07-30 (Session I.5 / 16.17).**

> **Resolution.** `make_value_hawk_pick_fn(..., n_teams=None)` now reads **`state.n_teams`** at
> pick time — the league size under every room shape, including k > 1 human seats — and
> `make_room_pick_fn` passes nothing at all. An explicit int still pins it, which is what the
> frozen pre-16.17 control in `steps/phase16_17_seat_map.py` and VH.0's ablations use.
>
> **B2, measured (`steps/vh_1_t33_divisor.py`, `analysis/vh_t33_divisor.json`, 8 seeds × 15 rounds
> on the live 2026 board):**
>
> | k humans | room | divisor | picks changed |
> |---|---|---|---|
> | **0** | 10 | 10 → 10 | **0 / 1200 — bit-identical** |
> | 1 | 9 | 9 → 10 | **248 / 1200 (20.7 %)** |
> | 2 | 8 | 8 → 10 | 122 / 1200 (10.2 %) |
> | 3 | 7 | 7 → 10 | 689 / 1200 (57.4 %) |
>
> **So no committed batch measurement moves** (k = 0 is every T15/T24 bar, the room bar sheet and
> `phase16_14r_*`), while **one pick in five changed in the room a human actually drafts against**
> — this entry guessed "~11 % in pricing"; the pricing gap is not the quantity that matters, the
> **pick** is. The share is **not monotone in k** (10.2 % at k=2 sits under both neighbours)
> because one changed pick cascades: the number is a chaotic amplification of the divisor gap, not
> a dose-response, and should not be read as one.
>
> ⚠ **The 16.17 control had to move with it.** `_legacy_fns` passed `n_teams=len(seats)` verbatim;
> left that way it would report a T33 difference as a 16.17 *mapping* difference and fail bars 1–3
> for a reason they were never built to test. *A control has to differ from the thing it controls
> on exactly one axis.* The mapping arithmetic itself is untouched.
>
> **Covered by** `tests/test_vh.py` — and note **749 tests passed over this bug**, because the only
> harness that ever exercised the value hawk ran at k = 0, where room size and league size
> coincide. *A bug that only appears off the measured path needs a test on the unmeasured one.*
>
> **→ opened T43:** fixing *which* number the divisor is does not justify it being a **team count**
> at all.

**Opened 2026-07-30 (Session I.5 / 16.17).** Found while unifying the two room builders: they are
identical except for the `team -> seat` mapping *and* one argument nobody had lined up.

```python
make_value_hawk_pick_fn(replace(p, hype_gain=g), risk, n_teams=len(seats))
```

`seats` is the **room** — the modelled seats — so `n_teams` is 9 in `make_room_pick_fn` (nine
opponents opposite a human) and 10 in `mock.full_room_pick_fn` (a fully simulated room). Inside the
hawk it is a **scale on the step-3 context weights**:

```python
eff = eff - w * n_teams * _local_z(pool[col], adp, pos)
```

So `role_share` / `role_delta` / `td_regression` are priced ~11 % harder in every batch measurement
than in the interactive mock a human actually watches. It is the T27 divergence one argument along:
*the interactive room was never quite the shipped room*, for a second and much smaller reason.

**Why it was not fixed in 16.17.** That substep's entire done-bar is **bit-identity against both
builders**, and `n_teams` is the one place they legitimately disagreed. Changing it moves the value
hawk's picks in one room or the other by construction, which is a behaviour change wearing a
plumbing change's clothes — exactly what the bar exists to catch. The line is preserved verbatim
with a comment pointing here.

**16.17 also makes it worse in a specific way, and that is the argument for fixing it soon.** With
k human seats the divisor is `10 − k`, so a value hawk in a 4-human room prices context **1.7×**
harder than the same seat in the batch room. Two constants was a wart; a knob that moves with the
room shape is a defect.

**The fix.** Pass the **league** size (`state.n_teams`, or a `n_teams=` threaded from the caller
that built the room) and re-measure. Accountable bars: the five T15 bars + landing + legality,
seating-marginalized (`steps/mock_room_bars.py --shuffle-room`), before/after, exactly as T24 was
run — the hawk is 1 of 10 seats so the effect should be small, but "should be small" is what the
harness is for. **Done-when:** one sheet each way, the difference stated, and whichever divisor
ships is the one both builders use.

---

## ☑ T34 — Every mock draft is the same mock draft
**Status ☑ DONE 2026-07-31 (Session K1.5 step 0) · opened 2026-07-30 (session 4, from the user's first real use of the K1 app).**

> **Resolution.** `app/engine.draw_seeds()` + `start_draft(seed=None, room_seed=None)` meaning *draw
> from OS entropy*; both drawn values land in `meta` and are printed on the draft page, so a
> randomized draft is still replayable by locking them. The app's control is **Randomize (default) /
> lock to a seed**. `steps/mock_draft.py` did **not** move: `--seed 7`, `--room-seed` unset.
> `meta["room_seed"]` was added on *both* surfaces so an exported draft carries the same keys either
> way.
>
> **Bar B0, on the live board:** 20 app drafts from seat 6 gave **20 distinct** first-five sequences
> (was 1); a locked seed pair replays its draft pick-for-pick *and* reproduces the seating; and the
> CLI at its frozen defaults still returns `engine.T34_REFERENCE` — Gibbs · Chase · Taylor ·
> McCaffrey · Cook — identical across two subprocess runs. The reference sequence is stored **as
> data** in `app/engine.py` precisely so "the measurement default has not moved" is an assertion
> rather than a memory.
>
> **What the fix confirmed:** the engine was never broken and the personalities were sampling the
> whole time. The only defect was which of two correct defaults the app inherited.

**Symptom (the user's words).** *"The log shows that the previous personality picks are the exact same
every single time I run from the same slot (running from p6: Gibbs 1, Chase 2, Taylor 3, McCaffrey 4,
Cook 5). This is a bug. Every time I run a draft, the picks should re-run according to the drafter like
intended and be different draft after draft according to what we've developed."*

**Reproduced, exactly, before it was written down.** On the live 2026 board, seat 6, `REALISTIC_ROOM`:

| run | first five picks |
|---|---|
| `seed=7, room_seed=None` — **the shipped app default** | Gibbs · Chase · Taylor · McCaffrey · Cook |
| the same call again | **identical** — the user's report, to the player |
| `seed=8, room_seed=None` | Gibbs · **Nacua · Jeanty · Bijan · Chase** |
| `seed=7, room_seed=3` | **McCaffrey** · Gibbs · Taylor · Chase · Cook |
| `seed=12345, room_seed=99` | Chase · Bijan · Gibbs · Nacua · McCaffrey |

**Cause — two defaults, both frozen, neither an accident.**
1. `app/engine.start_draft(..., seed: int = 7)` → `DraftState.rng = np.random.default_rng(7)`. Every
   personality that samples (all of them except `autopilot` and `chalk`, which carry `sample=False`)
   draws from that one generator, so the entire pick sequence is a pure function of the seed.
2. `room_seed=None` → `SeatMap.of` **keeps `REALISTIC_ROOM`'s listed order** rather than shuffling, so the
   same personality occupies the same chair in every draft. The shuffle exists (`personalities.py:1134`)
   and the app never asks for it.

**★ The lesson, and it is why this is 🔴 rather than a one-line default change: a measurement default and
a human default are different objects, and this repo has been shipping one of them twice.** Fixed seeds
are *correct* for `steps/` — T24's seating-marginalized sweep, 16.17's bit-identity bars,
`mock_room_bars.py`, every committed artifact is differenced against `--seed 7`. They are *wrong* for a
drafter, whose entire use case is drafting the same slot twenty times to see twenty rooms. The K1 port
carried the CLI's default into the app because the CLI's default was the only one that existed.

**Fix.**
1. `app/engine.start_draft` gains `seed: int | None = None` meaning **draw from OS entropy**, and draws a
   `room_seed` the same way. **Display both** on the draft page, so any draft is replayable.
2. The app's setup control becomes **Randomize (default) / lock to a seed**. Locking reproduces a draft
   pick-for-pick — reproducibility stays available, it stops being compulsory.
3. **`steps/mock_draft.py` keeps `--seed 7` and `--room-seed None`.** Do not "make them consistent".
4. Shuffling the seating per draft is also *more faithful to how the room was measured* — T24's third
   method failure was measuring on **one fixed seating**, which flatters by 5–7 pp and is a **bias** that
   more seeds do not remove. The app has been showing the user exactly that fixed seating.

**Done-when.** Twenty app-started drafts from one seat share no identical first-five sequence; a locked
seed + room seed replays its own draft exactly; and `steps/mock_draft.py`'s committed output is
**byte-identical** to its pre-change self.

---

## ☑ T35 — `st.tabs` runs every tab body on every rerun
**Status ☑ DONE 2026-07-31 (Session K1.5 step 1, with 14.K) · opened 2026-07-30 (session 4).**

> **Resolution.** `app/main.py` is a router: `st.navigation` / `st.Page` over five pages
> (Settings · Board · Draft room · The room · Cost), each in its own module. The nested
> `st.tabs(["Summary", "Season odds", "Draft flow", "Log"])` *inside* the old draft tab had the same
> defect and is gone too — those readouts sit behind a **radio** on the room page, which renders one.
>
> **Bar B1** counts page-body executions with `app/probe.py`, a counter in the shipped code rather
> than a patch applied by the test: first run `{settings: 1}`, rerun `{settings: 1}`, rerun on the
> draft page `{draft: 1}`. Under `st.tabs` every one of those would read 4.
>
> **The instrument is the point.** T35's claim is about *how many times a function runs*, which a
> stopwatch can only imply — and a timing bar would have passed on any day the cost page happened to
> be cheap. It also unblocked 14.M exactly as predicted: the clock is an `st.fragment(run_every=…)`
> and a tick now reruns one fragment.

**Symptom.** `app/main.py`'s `main()` calls `tab_settings()`, `tab_board()`, `tab_draft()` and
`tab_cost()` unconditionally inside `with tabs[i]:` blocks. Streamlit renders **all** tab contents and
hides the inactive ones in the browser — it does not skip their script bodies. So a single keystroke in
the draft room's player search also re-runs `tab_cost`'s `_prepare_board(built["board"])` and its
ADP-sorted `{label: player_key}` build over every row of the board, plus `tab_board`'s own render.

**Why it is 🟠 and not 🟡.** It is a **hard blocker on 14.M**, the pick clock. A clock that reruns on a
timer must rerun *one fragment*; on `st.tabs` it reruns four tab bodies including the cost tab's
whole-board work, several times a second. The feature cannot be built correctly on this structure.

**Fix.** `st.navigation` / `st.Page` — one page body per rerun, real URLs, and the draft room gets the
screen to itself. This is **14.K**, which the user asked for independently on ergonomic grounds
(*"everything should be on a completely separate designated draft room page"*): the ergonomic request and
the performance defect have the same fix, which is the argument for doing it first rather than bolting
pages on later.

**Done-when.** A rerun triggered on the draft page executes the draft page body **only** — asserted with
a per-page probe counter under `AppTest`, not eyeballed — and K1's B1 identity (app == CLI at the same
seed) still holds after the move.

## 🟡 T36 — the row-selection path has no automated bar
**Status ☐ · opened 2026-07-31 (Session K2) · opportunistic.**

`st.dataframe(selection_mode="single-row", on_select="rerun")` is how a drafter picks a player and how
the 14.N-era player card is opened. **`AppTest` cannot drive it** — selection is a client-side event
with no scriptable equivalent, unlike `st.button.click()` or setting a widget value.

**What is covered instead**, so the gap is stated at its real size rather than its scariest one:
- `session.player_card` is unit-tested against the board row it reads (all eight bars, the T27 chain,
  the cliff), so the modal's *content* is asserted.
- `session.resolve_pick` and the quick-pick buttons cover the other two ways into a pick, and Session
  K1.5's bar B2 asserts a row-select and a typed query resolve to the **same board index**.
- K2's FLOW bar opens all six pages with a live draft and asserts zero exceptions, so a crash *on* the
  board page would be caught even though the selection itself is not driven.

**What is not covered:** that a selection produces the confirm bar, and that the confirm bar's button
drafts the player it names.

**Why it is 🟡 and not 🟠.** Nothing here computes a number — the selection resolves to a board index
that `_apply_pick` already validates, and a wrong index would surface immediately as the wrong player
in the confirm bar, which is exactly why the confirm bar exists (*never a one-click irreversible pick
without the name in front of the user*).

**The honest fix, and why it has not been taken.** A real browser driver (Playwright) would cover it
and adds a dev dependency plus a slow, flaky-by-nature bar. The alternative — a second, selection-free
control that exists only so a test can reach it — would be *testing a path the human does not use*,
which is the T27/K1 failure mode inverted, and worse than the gap. Revisit if row-select ever carries a
number rather than a navigation.

## ☑ T37 — the reach-risk readout was hidden behind a collapsed expander
**Status ☑ done 2026-08-01 (Session UI-1, step 0 + step 5) · was 🟡.**

`app/draft_room._reach_risk` rendered `session.reach_risk_view` inside
`st.expander("Who will still be there at your next pick?", expanded=False)` — **directly beneath its own
docstring arguing that it must not**: *"it is cheap (~20 ms for 25 players) so it renders inline rather
than behind a button: a readout you have to ask for is a readout nobody asks for."*

**Why it mattered more than an ordinary display slip.** `P(available)` with an **un-drifted baseline**,
from the Brier-validated 11.2 survival oracle, is one of the seven things this app ships that has no
competitor equivalent — FantasyPros' Pick Predictor has neither the baseline nor a validation claim. It
had no surface at all between Session G and K2, and then arrived collapsed.

**Fixed:** the expander is gone; the readout lives in the **right rail, permanently, beneath the roster**,
and `P(THERE)` also joins the **slim** board — under a clock it is more decision-relevant than `PROJ`.
Both placements read the *same* `session.reach_risk_view` call (`session.attach_reach` is a placement,
not a derivation), and the CLI's `board --view slim` carries the same column with the same numbers.

**Bar B5** asserts the column *is* the readout's number row for row, that rows the readout did not
simulate stay **NaN** rather than printing `0.00` (T22's rule with the other sign), and that the draft
room renders **zero expanders** — a claim a future edit cannot satisfy by accident.

**★ The durable lesson: a docstring is not a guard.** The argument against collapsing it was written,
correct, and sitting two lines above the code that collapsed it, through a whole session in which every
K2 bar passed. Where prose and code disagree, the code is what the user gets — so the fix ships with a
bar, not with a stronger comment.

## ☑ T38 — a raw JSON dump on the page whose job is to be a report card
**Status ☑ done 2026-08-01 (Session UI-1, step 0 + A6) · was 🟡.**

`app/post_draft.py` rendered `c1.json(frames["elite"])` — the elite-fall profile as pretty-printed JSON,
under the heading *"Elite fall (consensus top-12)"*, on 14.N.

**Fixed:** `views.elite_fall_table` renders it as a titled table with the label **and the unit** each
number needs — the slots are **10-team picks**, so a 12-team draft's pick 20 is not silently compared to
a 10-team draft's pick 20, and the readout is worthless without saying so. The `share_past_*` row is
matched by prefix because `mock.elite_fall_profile` names that key after its own threshold; hard-coding
the 10 would be a second definition of the bar's cut. 14.N was rebuilt around it as a report card: a hero
row of **grade letter · title fair-share multiple · STARTABLE rank**, the biggest-reach / best-value pair
promoted out of a six-row table nobody read, and standings / odds / every-team / draft-flow behind
`st.tabs`. **Bar B6** asserts `app/` contains zero `st.json` calls and that the elite table renders.

**★ Why it survived.** K2 **moved** the readouts here from the room page rather than rewriting them, so
the defect changed address without being looked at. *That is the cheapest kind of defect to keep* — and
the reason a move should be read as a rewrite opportunity, not as a no-op.

**⚠ Method note for the next register entry.** The first version of B6 counted `st.json` with a regex and
reported 1 — the hit was the *comment* recording what T38 replaced. B1's palette census had the identical
failure with the hex strings in a docstring. Both now parse the AST. **A grep does not know the
difference between doing a thing and describing it**, and in a repo whose comments quote the code they
replaced, that is not a rare edge case.

## 🟠 T39 — the tier feature is a null, and the number that sold it hides its own denominator
**Status 🟠 open 2026-08-01 (Session UI-2, step 1) · found by building the feature.**

`docs/UI-PLAN.md` §S2 and `docs/BUILD_PLAN.md` §UI-2 step 1 both specify, and both recommend, an
**overlap-based tier column**: *a tier ends where adjacent players' 10–90 bands stop overlapping*.
Both call it the one differentiated item in the whole UI plan — *"the single item no competitor could
copy without building our distribution stack first"* — on the strength of `COIN`'s published figure,
**146 of 199 adjacent pairs overlap**.

**Measured on the live 2026 board, the rule cuts nothing at any scope:**

| | |
|---|---|
| within RB / WR / QB / TE | **1 tier each** — 62, 83, 29 and 24 players in one undivided tier |
| whole board order | **2 tiers** over 244 available players |
| adjacent pairs in the top 200 | 199 |
| …with **both** bands present | **147** |
| …of those, overlapping | **146** |
| …**genuine** non-overlaps | **1** |
| …pairs where a band is **missing** | **52** |

**Two causes, and the second is worth more than the feature.**

1. **Scale.** The median RB 80 % band is **228 points** wide; the median gap between adjacent RBs is
   **16.3 points**. That is **14×**. A pairwise-overlap rule cannot cut a sequence whose neighbours sit
   at a fourteenth of their own interval width — overlap is near-universal *by construction*, and that
   is a fact about season-total predictive intervals, not about football.
2. **A category error in the premise.** UI-PLAN says the design is *"precisely Boris Chen's thesis
   executed on our own distributions rather than on expert ranks."* It is not. Chen clusters **expert
   rank dispersion** — a measure of how much rankers *disagree about where a player belongs*. We hold a
   **predictive interval for a season total**. Disagreement is narrow; outcome uncertainty is enormous.
   Two different quantities wearing one name. This is **T24's lesson** (*a relationship measured on one
   object is not a specification for the mechanism that produced it*) arriving on a visualisation
   instead of on a draft room, and it presented the same way both times: as a plausible design idea.

**★ The half that outlives the feature — a published figure that conflates two answers.**
`session.coin_flags` returns `False` **both** for *these two are distinguishable* and for *we cannot
tell*, and **its own docstring says those are different answers**. But every published statement of the
column reports the single number: K2's bar B4, UI-PLAN §3.3, the `COIN` dictionary entry, and this
session's own bar B1 anchor. Read as *"73 % overlap, so 27 % are resolvable"* it is wrong by a factor of
fifty: **52 of the 53 non-overlaps are missing bands.** The honest statement is *of the adjacent pairs
we can evaluate at all, **99.3 %** overlap* — which is a **stronger** version of the honesty claim the
column exists to make, and a fatal one for anything trying to navigate by it.

**What shipped instead:** nothing. No `TIER` column is on any rendered view, `SLIM` keeps `PROJ`, and
`session.tier_series` ships **runnable and unwired** with both cuts (`method="overlap"` and
`method="gap"`) so the null stays checkable rather than becoming a sentence in a write-up — the 16.9 /
16.16 precedent (*built, wired, tested, default OFF*). A unit test pins the mechanism so the rule cannot
be quietly re-adopted, and `coin_flags`' docstring and the `COIN` dictionary entry now both carry the
decomposition.

**⚠ The gap cut is not a fallback, and this is why.** `BUILD_PLAN`'s option (a) — *"a tier ends where
`base_value` falls by more than the pool's local median gap"* — was built and measured too. **A
threshold at the median is exceeded by half of all pairs by definition**, so it returns ~n/2 tiers (31
over 62 RBs) regardless of the data: it is a coin flip wearing a tier's name. Cutting on the *board*
order rather than the value order makes it worse still, because the board is ADP-sorted and
`base_value` is not monotone in it (one tier came out spanning 0.0 → 63.5). The drop distribution is
heavy-tailed, not bimodal — max/median **8–16×** per position, with only **1–2** drops per position past
mean + 2 sd — so *how many tiers exist* is entirely a function of where the threshold is put.

**Fix, when it is worth a session:** a real 1-D clustering with model selection (Chen uses a Gaussian
mixture with an information criterion), on a **rank-dispersion** quantity rather than on a season-points
interval — `adp_stdev` is already on the board and is exactly the disagreement measure Chen's method
wants. That is **modelling**, with its own validation, and it is not a display session's work. Until
then the board's scarcity question is answered by `CLIFF` (14.E), which is per-position, threshold-free
and already shipped.

## 🟠 T41 — a control that cannot tell "the world moved" from "the code broke"

> **★ Update 2026-08-01 (Session VH, B0): the structure this entry asks for already exists one
> harness along — copy it, do not invent it.** VH's B0 re-ran `steps/mock_room_bars.py
> --shuffle-room` across the same `ffc-20260724 → ffc-20260801` board move that broke the UI
> sheets, and audited all **628** leaves. **84 differed and not one was a gate:** 71 sat under
> `readout_2026`, 11 under `config`, 2 under `generated`/`label`. Every measured gate value came
> back **bit-identical to the digit** and all eight `pass` flags held.
>
> The reason is structural, not luck: `mock_room_bars.py` gates on **historical** seasons, whose
> boards cannot move, and files the live 2026 season under a top-level `readout_2026` that its own
> docstring calls *"an eyeball readout, never a gate"*. So board-driven movement lands in a named
> bucket **by construction**, which is exactly the `vintage_changed` category this entry prescribes
> for `_classify_moves` — and it is a partition of the artifact, not an allowance bolted onto the
> comparator. That is the shape to port to the UI sheets.
>
> Also landed this session and useful here: **`resolve_board(..., asof=)`** (VH.0) lets a
> measurement *choose* a vintage rather than only report one. T41 is still open — it asks a sheet to
> **stamp** its vintage and classify against it — but the two halves now exist: pin the input, and
> partition the output.

Opened 2026-08-01, by the Stage-0 chore itself. The pull banked an `ffc-20260801` board (1,288 rows,
gsis 98.0 %, every data-health gate PASS) and the reconciliation that followed re-ran the bar sheets.

**The before/after is unambiguous, and it was checked in that order** — the pre-pull sheets were read
*first*, so the attribution is measured rather than assumed:

| | pre-pull (`ffc-20260730`) | post-pull (`ffc-20260801`) |
|---|---|---|
| UI-1 / UI-2 `all_pass` | **True** | **False** |
| `session_k1_app.json` moved | `display_count: 1` | `display_count: 1`, **UNCLASSIFIED: 122** |
| `session_k2_app.json` moved | `display_count: 4` | `display_count: 4`, **UNCLASSIFIED: 23** |
| nested `k1 / k1_5 / k2_all_pass` | True | **True — unchanged** |

Every nested sheet still passes its own bars. The 150-of-150 app-vs-CLI identity, the cliff identity,
the Brier and the probability fields are all untouched. What moved is what a different board makes
different: the room drafts other players, so the standings re-order (`app_summary[0].who: 'autopilot'
→ 'YOU (T7)'`, `team: 2 → 7`), the grades re-scale (`grades.YOU: 'C+ 59' → 'D+ 39'`), and board-shaped
counts shift (`adjacent_overlapping_pairs: 146 → 150`, `at_censoring_point: 70 → 72`).

**The defect is that none of that is *sayable* by the instrument.** `_ALLOWED_MOVES` names five
rendered-element counts, six entropy draws, eight timings, one stat-dictionary entry and one column
list. There is no category for *the input moved*, and no field in the sheet records **which board it
was measured on** — so B0 cannot distinguish a weekly chore from a regression, and says the alarming
thing both times. `CLAUDE.md` §2 mandates that pull whenever the board is >6 days old, which means
**this failure is scheduled**, not incidental.

★ **It is T32 one level up, and the fix is T32's fix.** There, `mock.room_board` cached on
`(season, scoring, teams, include_dst, ENRICH_VERSION)` and omitted *which snapshot answered*, so a
fresh board and a stale one shared a filename. `board_vintage(raw, src)` went into the key and the
cache became self-healing. Here the same omission sits in the **control** rather than the cache: stamp
the vintage into each sheet, have `_classify_moves` compare it, and bucket board-driven leaves under a
reported `vintage_changed` — a *classification*, so the leaves are still enumerated and still visible.

⚠ **Do not widen `_ALLOWED_MOVES` to swallow them.** The list's docstring says what a display session
is allowed to move; a blanket board allowance would wave through exactly the regressions B0 exists to
catch, and the UI-1 pointer already records what that costs — the one leaf its first version missed was
`bars.b3.worst_seat`, an argmax over a noisy vector, caught only because the bar refused to generalise.

**Interim rule until it is built:** after a Stage-0 pull, a B0 failure whose unclassified leaves are all
draft-outcome or board-count fields, *with every nested sheet still passing*, is a **re-baseline**, not a
regression. Re-run, read the nested `*_all_pass` flags, and commit the sheets so `HEAD` carries the new
vintage. Pre-pull evidence for this instance is preserved at
`analysis/session_ui_{1,2}.pre_ffc20260801.json` (the `phase11_opponent_model.pre_t15.json` convention).

## 🟡 T40 — the control fired once, so it was one board refresh from firing never

Opened 2026-08-01, alongside T41 and from the same run. UI-2's B3 asserts that each construction glyph
**is** `roster_construction_risk` evaluated on (roster + candidate), row by row, and — because the UI-1
pointer records that the first build had `⚑` firing **zero times in 40 rows** — it carries a control
requiring every glyph to fire at least once, so the identity cannot pass vacuously.

The control was right to exist and is too weak as written:

| | pre-pull | post-pull |
|---|---|---|
| `glyphs_that_fired` | `{'bye': 6, 'stack': 8, 'handcuff': 1}` | `{'bye': 13, 'stack': 12, 'handcuff': 0}` |
| `every_glyph_fired_at_least_once` | True | **False** |
| `mismatched` | `[]` | **`[]` — the identity still holds** |
| `FLAGS_string_byte_identical` | True | **True** |

**`handcuff` fired exactly once**, on whichever sampled row happened to pair a lead back with his
backup. A different board seats a different room, and the pair vanished. Nothing about the glyph logic
changed: `mismatched` is still empty, `FLAGS` is still byte-identical, unknown byes still stay unknown,
and there are still zero fabricated week-0 rows.

★ **The lesson is the repo's own, from the other side.** K2 recorded that *a test that cannot fail is
the same defect as a bar that cannot fail* — a handcuff unit test that drove a draft seating **no lead
back at all**, asserted over an empty frame and passed while proving nothing. This is its mirror: a
control that *can* fail, and does, on n = 1 — a sample of one is indistinguishable from a coincidence,
and it produces a **false** failure rather than a false pass. Both come from letting a sampled fixture
decide whether the interesting case is present.

**Fix:** construct the case instead of sampling for it. A lead back and his handcuff are deterministic
from the depth chart, so the control can seat that pair on the hypothetical roster and *require* the
glyph, rather than drafting 40 rows and hoping. Keep the control — do not loosen it into a pass, which
would be tuning a bar to a board.

---

## 🟠 T42 — the value hawk maximizes a slot-blind objective, and it is the only seat that fully expresses it

> **★ ANSWERED 2026-08-01 (Session VH.0 + VH.2). The experiment ran; the ticket's diagnosis is
> partly right, its flagship evidence is wrong, and its prescribed fix is blocked by its own bar.**
>
> **1 — the flagship pick was never slot-driven.** This entry leads with "a QB2 in round 8 **and a
> TE2 in round 9**". VH.0 re-took every one of the seat's picks under one-knob ablations with the
> draft state held fixed: the **TE2 is changed by nothing** — not `starter_aware`, not the window,
> not the context, not the raw board argmax. **TE is flex-eligible** in this league
> (`flex_groups = ((1, ('RB','WR','TE')))`), so a second TE is a *legal starter*, not bench depth,
> and a slot-aware objective has no complaint about it. The slot channel owns **QB2** — QB is not
> flex-eligible — and this entry pooled two different things behind one number.
>
> **2 — B1 came back INCONCLUSIVE: 38 % slot-driven (pinned `ffc-20260724`), 29 % (live).**
> Pre-registered ≥50 % confirms, <25 % kills. Real, minority, narrower than its ticket. The
> **dominant** channel is the reach **window** (6 of 7–8 objected picks on both vintages), and it is
> the one aligned with what the user actually objects to: his labels track reach at `corr = +0.767`.
>
> **3 — the prescribed fix moves the seat the wrong way on his criterion.** Δ mean reach:
> `window_none` **−5.8 / −5.2 picks**, `context_off` −3.7 / −2.1, `starter_aware` **−0.2 and, on the
> live board, +5.4**.
>
> **4 — ★ the interventional result, and the reason B3 blocks the ship.** 200 seating-marginalized
> drafts × 4 DEV seasons (`analysis/vh_objective_ab.json`):
>
> | vs shipped | `starter_aware` (bw 0.0) | `blend_50` (bw 0.5) |
> |---|---|---|
> | realized points | **+50.4** CI[+25.0,+76.7] | +18.3 CI[−4.3,+41.0] |
> | title multiple | **−0.295** CI[−0.363,−0.230] | **+0.144** CI[+0.079,+0.212] |
> | every shape measure | improves | 3 of 4 improve |
> | **B3** | **SHIP = False** | **SHIP = True** |
>
> **Realized points and the sim's title probability disagree in sign.** The ⚠ on this entry
> anticipated "shape improves, outcome degrades → a finding about the sim" — it arrived in a sharper
> form, because *realized points improved*. T28 established bench↔title **correlationally**; run
> interventionally the relationship is **the sim's, not the world's**. Recorded as a sim finding,
> **not acted on**, and filed as a candidate cause of the standing −113 pts/team level bias.
>
> **What remains open is not this ticket.** `blend_50` passes B3 and is a *seat-character* decision
> the user should take (it needs a new per-`Personality` `bench_weight` seam — `RiskModel` carries
> it today and the room builds one model for all seats). Realism cost measured separately. **This
> entry closes as ANSWERED; the ship decision is the user's.**

**Opened 2026-08-01 (session 5), from a user report:** `value_hawk` "is consistently underperforming …
it consistently makes picks that are characteristically uncalled for", and — asked to separate the two
readings — **both**: the picks look wrong *and* the roster finishes weak. That pairing is the ticket.
One cause produces both.

### What the seat is

`draft/personalities.py:713` / `:989` — not a `signal_weights` seat but the **Phase-9 greedy in an
opponent seat**: `RiskModel.effective_rank` scoring each candidate by its marginal contribution to
**portfolio CE**, bounded by a reach window and tilted by three context weights. 16.14R built it that way
deliberately, and correctly: a `signal_weights` hawk provably cannot work, because `pos_z(vbd)` deletes
VBD's only non-ADP content (`corr(vbd, adp)` within position −0.86…−0.96).

### The defect

**The value path is slot-blind** — nothing in `draft/optimizer.py` references starters — and `value_hawk`
is the only seat that **maximizes** that quantity. T28 recorded the fingerprint without connecting it to a
pick objection:

> the gap `capital − startable` is negative for every seat **EXCEPT** `value_hawk` (**+152**), the only
> seat that maximizes the sum, so the display defect is real and **seat-dependent** while the objective is not.

The shape is visible in the shipped mock (`analysis/mock_16_14R_picks.csv`, seat 8, 15 rounds):

| round | 1 | 2 | **3** | 4 | 5 | 6 | 7 | **8** | **9** | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pos | WR | WR | **QB** | TE | WR | RB | RB | **QB** | **TE** | RB | WR | RB | WR | K | DST |
| adp | 10.3 | 25.6 | 27.9 | 46.8 | 45.5 | 60.2 | 58.0 | **63.3** | **85.2** | 72.8 | 84.9 | 127.3 | 130.7 | 128.4 | 132.4 |

A **QB2 in round 8** and a **TE2 in round 9** in a **10-team 1-QB full-PPR** league, with the first RB in
round 6. Correct as capital accumulation; indefensible as a roster. It is the same failure the user's two
symptoms describe from two sides — the picks read as uncalled for *because* the capital they buy cannot start.

### ★★ Why T28 did not settle it, and could not have

T28's bar B5 asked **which roster-value definition best *correlates* with title probability**, over 200
seated-reshuffled drafts:

| definition | Spearman vs title |
|---|---|
| `team_value` (slot-blind sum) | **+0.8382** |
| `portfolio_ce` (shipped objective) | +0.8202 |
| `starter_value` | +0.7971 |
| `starter_mean` | +0.7920 |

…and used that ranking to decide what the seat should **maximize**, closing the ticket as a labelling fix.

**Those are different questions.** *A relationship measured on outcomes is not a specification for the
mechanism that produced them* — **T24's own durable lesson, arriving one level up.** T24 learned it about
`|drift| ≈ 2·adp_stdev`: a law true of realized drift, harmful when re-injected as a per-seat perception.
Here it is `starter_value`: a *worse predictor* of title probability across rosters, which says nothing
directly about whether a seat that *optimizes* it builds better rosters. The interventional experiment has
never been run.

T28 also flagged the seat-dependence in its own write-up and did not follow it: the correlational bar
pools ten seats, nine of which do not maximize the quantity at all.

### The fix — Session VH.2

Run `value_hawk` on `objective="portfolio_ce"` vs a **starter-aware** objective, ≥200 seating-marginalized
drafts (`--shuffle-room`, the T24 protocol) × ≥4 DEV seasons. `RiskModel.bench_weight` already exists from
T28 (default **1.0**, and 1.0 nests the shipped greedy pick-for-pick per `test_phase9`), so the sweep has a
knob and needs no new one.

**Report outcome and roster shape as separate claims:**

| | measured |
|---|---|
| **outcome** | realized points · `starter_value` · title/playoff **fair-share multiple** (T29: the multiple, never the bare percentage) |
| **shape** | QB2/TE2 count before round 12 · `capital − startable` gap · RB1 arrival round |

**Done-when:** ship starter-awareness only if **shape improves AND outcome does not degrade beyond its
CI**. B0 holds throughout — the five T15 bars + landing + legality, seating-marginalized.

### ⚠ Two traps written down before the session, not after

1. **If shape improves and the outcome degrades, that is a FINDING and not a tuning target.** Our sim draws
   injuries, and T28 measured **bench value alone predicting title +0.711, positive in 100 % of drafts**,
   with the blend sweep peaking at `w=0.90` against a shipped 1.0. So the sim may genuinely prefer the
   roster a knowledgeable human calls indefensible. That would be a statement about the sim's documented
   under-modelled availability, and it gets reported, not reweighted away.
2. **Do not delete or replace the seat, and do not rebuild it as `signal_weights`.** It is 1 of 10 in
   `REALISTIC_ROOM`; every T15/T24 bar was measured with it there, and 16.14R already measured what the
   `signal_weights` version becomes (a chalk tilt with extra width, finishing 5.5/10 behind `safe_floor`).

**Travelling with it:** **T33** (VH.1 — `n_teams` is the room size, so the interactive seat the user
watches prices context ~10 % differently from every seat that was ever measured) and the unresolved
window sweep (`analysis/phase16_14r_value_hawk.json`, `sweep_resolved: false`, +13.1 CE against a pooled
se of 10.7 — the shipped window is a **default, not a result**).

---

## 🟡 T43 — the context term is scaled by a team count, and nobody has ever said why

**Opened 2026-08-01 (Session VH.1), out of T33's fix.** T33 asked *which* number the value hawk's
step-3 context scale should be and answered "the league size, not the room size". Fixing it made
the prior question visible: **why is it a team count at all?**

```python
eff = eff - w * state.n_teams * _local_z(pool[col], adp, pos)
```

`eff` is a **priority rank** and `_local_z` is a **z-score**, so the product is "ranks per standard
deviation" — a units conversion. `n_teams` is not that conversion; it is the number of seats in the
league, which appears here for no stated reason. Nothing in 16.14R step 6 derives it, and the
weights (`role_share` +0.30 / `role_delta` +0.25 / `td_regression` −0.30) were chosen *against* it,
so the two are not separately identified.

**Why it matters, measured (VH.0, `analysis/vh_attribution.json`).** Judged against the whole pool
the term looks negligible — `sd(context) / sd(eff)` = **0.08**. Judged against the **contended set**
(the top-10 candidates, the only rows an argmax is ever decided between) it is **0.29–0.34 of the
spread**, and it changes **6 of 15 picks**. Both numbers are correct; only the second is relevant.
*A term calibrated against the wrong dispersion looks small right up until it decides the pick* —
and that is why this sat unexamined through 16.14R, T24, T27, T28 and 16.17.

**The fix is a measurement, not an edit.** Re-derive the scale from what it is supposed to buy — a
context signal worth *k picks* of board position — the way `reach_cap` already converts picks
through the model's own ADP coefficient (`personalities.py`, and the pattern is right there). Then
refit `DEFAULT_CONTEXT_WEIGHTS` against the new scale, because they absorbed the old one.

**When:** with the next 11.1 refit, alongside **T26** — both change what β was estimated against, so
they should move together and be measured once. ⚠ Not before: the shipped weights and the shipped
scale are one object, and changing either alone re-prices the seat by an unmeasured amount.

**Done-when:** the scale has a stated derivation, the weights are refit against it, and the T15
bars + landing + legality are re-run seating-marginalized before/after.

**☐ 2026-08-01.**

---

## 🟡 T44 — there is no `schedules` table, and the bye weeks come out of a rankings feed

Session K2 built the 14.F roster-risk readout, which clusters a roster's starters by bye week, and
discovered the store has **no schedule table**. The workaround — take byes from `ecr_snapshots` —
still ships.

It is 🟡 and not 🟠 because the surface is *honest* about it: a player with no ECR row has an unknown
bye and is rendered unknown, never as week 0 (K2's B3 asserts exactly that). Nothing on screen is
wrong. The defect is upstream of the display: **a first-class, free, immutable fact about the season
is being inferred from a third-party ranking board that has no obligation to carry it**, and the
coverage of that inference silently tracks the vendor's board depth.

**Fix:** ingest the `schedules` release (game grain, full history, tiny) in **DATA-1 / 0.12.6** and
repoint 14.F. It is also the cheapest honest proof of the 0.12.1 loader — a *new* table, small enough
to eyeball, unlike the bit-identity control which only proves the loader reproduces what we have.

**Done-when:** `schedules` is in the store with a coverage gate; `session.py`'s bye read comes from it;
K2's 14.F bar re-runs with byes known for **every** rostered player, and the "unknown stays unknown"
branch is kept and unit-tested rather than deleted (it is still correct for a player with no game).

**☐ 2026-08-02.**

---

## 🟠 T45 — `ngs` is ingested and effectively unread

`ngs` holds **26,723 weekly rows, 2016–2025**. Its only consumer is `data/panel.py:93`, which reads
`stat_type='receiving'`. **No module in `features/` reads the table at all** — `build_exposures`
assembles its 48 columns from `weekly`, `pbp`, `snaps`, `combine`, `game_lines` and `player_ids`.

So the following are on disk, PIT-clean, ten seasons deep, and feed nothing:
`percent_attempts_gte_eight_defenders` (box counts faced, per RB per week) · `avg_separation` /
`avg_cushion` (the free coverage proxy) · `rush_yards_over_expected_per_att` · `avg_time_to_los` ·
`avg_yac_above_expectation` · `percent_share_of_intended_air_yards` · `cpoe` · `avg_time_to_throw`.

**Why it survived.** Nothing anywhere records which modules consume a table. This is **T22 one level
up** — T22's lesson was *a column's consumers are not only the models that weight it* (the audit
grepped `signal_weights` and never looked at the display layer). Here the audit never happened at
all, because there was no artifact that would have shown a table with one reader sitting next to
tables with fifteen. *A table nobody reads and a table that does not exist are indistinguishable from
the outside.*

**Fix, deliberately split across two sessions:**
- **DATA-1 / 0.12.2** — the generated inventory carries a **consumers** column, so this class of
  defect is visible by construction rather than by someone happening to look.
- **M-1** — wire the NGS families into `features/` as weekly matchup exposures. Held back from DATA-1
  on purpose: it changes a matrix that the rookie ridge, the QuantReg quantile fits and the Phase-6
  softness regression all read, so it needs its own pre-registered bars and its own before/after.

⚠ **Expect the level trap.** These are rate/efficiency columns and this repo has hit level-vs-shape
four times (16.14 `q90`/`q10`, T17 `games_played_mean`, T19 `floor`, T31). Residualize on the
projected level *before* reading any of them as a shape signal.

**Done-when:** the inventory shows consumers for every table; M-1 lands the NGS exposures with the
level control in place and reports the correlation of each new column with the level.

**☐ 2026-08-02.**

---

## 🟠 T46 — the frozen `nfl_data_py` wrapper is our ingest ceiling

`nfl_data_py` is a **wrapper** over the `nflverse-data` GitHub release assets. We have been treating
its function list as the boundary of what exists. Anything the wrapper does not expose is not
unavailable — it is **invisible**, which is worse, because an absence nobody can see never gets
prioritised.

This already bit once and was recorded as a one-off. Phase 0.9: *"nflverse restructured stats releases
post-2024; frozen `nfl_data_py` hits the dead old path."* That was not a one-off; it is the general
failure mode, and the wrapper's release cadence is not ours to control.

**The measurement, 2026-08-02.** The `nflverse-data` repo publishes **25 release tags**. The wrapper
exposes a subset. Missing entirely, with no wrapper function: **`pbp_participation`, 2016–2025, play
grain** — `defenders_in_box`, `offense_personnel`/`defense_personnel`, `offense_formation`,
`defense_man_zone_type`, `defense_coverage_type`, `route`, `was_pressure`, `time_to_throw`,
`number_of_pass_rushers`, and `offense_players`/`defense_players`/`players_on_play`, the **gsis IDs of
all 22 men on the field for every play**. Also missing: `schedules` (T44), `espn_data`, `officials`,
`trades`, `players_components`, `contracts`.

**Fix: DATA-1 / 0.12.1** — `data/sources/nflverse_release.py`, reading
`releases/download/<tag>/<asset>.parquet` directly, cached under `data/raw/nflverse/**`.
⚠ **It sits beside `data/sources/nflverse.py`, which is not deleted or bypassed** — that module is the
provenance of sixteen ingested tables, and migrating them is opportunistic, not a goal.

⚠ **The bar is a control, not a smoke test.** Reproduce an already-ingested table (`combine`)
bit-identically through the new path, **and assert the control can fail** by pointing it at a wrong
asset. T31's method warning, verbatim: *assert the control can produce a known difference before
trusting it to show none.*

**Done-when:** the loader enumerates every release tag; the bit-identity control passes and its
negative control fails; participation, FTN and the small sources land through it; and
`reference/DATA-SOURCES.md` is generated with each source's **upstream floor**, so the difference
between *we have not ingested it* and *it does not exist* is written down once instead of
re-investigated.

**☐ 2026-08-02.**

---

## 🔴 T50 — the vendor stopped emitting nulls, and the gate only knows how to see nulls

**Opened 2026-08-03 (Session DATA-2 scoping). Verified in the parquets, not inferred.**

| season | `was_pressure` | `number_of_pass_rushers` |
|---|---|---|
| **2022** | 31,207 **null** · 13,425 False · 5,518 True | 72 zeros |
| **2024** | **14 null** · 38,838 False · 7,067 True | **23,754 zeros** |

Non-pass plays used to be `NULL`. From 2023 they are `False` and `0`. The unconditional fill rate
therefore climbs **0.38 → 1.00** at the break while the column's meaning inverts underneath it.

**Why the instrument cannot see it — three independent reasons, each sufficient on its own:**

1. `validate.store_fill_rates` computes the **nonnull share**. A sentinel `False` and a sentinel `0`
   both count as filled. The gate measures *presence*; the failure is in *meaning*.
2. `validate.fill_rate_gate` fails only on drops — `if was - rate > tol`. Null→sentinel is a **rise**,
   so it passes silently, by design.
3. The gate is **whole-table, not per-season**. A mid-history break averages away even if the
   direction were handled.

> **★ The gate written to catch `ngs_air_yards` silently going to zero is blind to the exact opposite
> failure — and the opposite failure is the one actually present in the data the mining program exists
> to mine.** A blitz rate computed naively across 2022→2023 reads as a league-wide scheme revolution
> that is entirely an encoding change.

**This is T45 one level up.** There, nothing anywhere recorded a table's *consumers*. Here, nothing
records a column's *encoding* — so a re-encoding and a real trend are indistinguishable from the
outside. The repo has now found this shape four times (T45, T46, T47, T50): **an instrument that
measures the thing it can see rather than the thing it is for.**

⚠ **Not a defect in `participation.fill_rates()`** — that function does state conditional rates against
the right denominator, and DATA-1's B5 was met. The defect is in the **standing gate** in
`data/validate.py`, which is what runs on every future ingest.

**Fix: DATA-2 / 0.13.0, before any other substep.** `src/fantasy_quant/data/breaks.py` — a probed
per-`(table, column, season)` map of `observed` · `sentinel(<value>)` · `absent`. Every rate the
session computes routes its denominator through it. `fill_rate_gate` becomes **two-sided and
per-season**, plus a distributional check: a column whose null share collapses while its modal value's
share explodes is a **re-encoding**, not an improvement, and must fail.

⚠ **Classify the break; do not smooth it.** A normalization that makes the discontinuity disappear
without recording it is the same defect as the gate that cannot see it.

**Done-when:** the map finds the 2023 `was_pressure` break **without being pointed at it**, flags a
deliberately-planted synthetic sentinel, and the naive-vs-gated blitz rates are reported as a **stated
difference** — proving the trap is real before proving the gate closes it.

**☐ 2026-08-03.**

---

## 🟠 T48 — the defensive scheme data has no subject to attribute it to

**Opened 2026-08-03 (Session DATA-2 scoping).**

DATA-1 banked 478,989 participation plays carrying `defense_personnel` (3,306 distinct strings),
`number_of_pass_rushers`, `defenders_in_box`, `defense_man_zone_type`, `defense_coverage_type` and the
gsis IDs of all eleven defenders. **None of it can be assigned to a coordinator, a tenure or a regime**,
because `reference/coaches.csv` is offense-only by construction — its columns are `season, team,
head_coach, offensive_coordinator, play_caller, hc_calls_plays, in_house, confidence, notes`. 204 rows,
32 teams, 2014–2026, **48 distinct play-callers, zero defensive attribution.**

The consequence is not that a number is missing; it is that a whole apparatus has nothing to run on.
`situation/fingerprint.py` implements within-season z-scoring, empirical-Bayes shrinkage by regime
length, and PARTIAL-season week-pinning — all keyed to `coaches.csv` through
`coaches.fingerprint_source`. **There is no defensive counterpart**, so a defensive scheme fact is
team-anonymous and person-anonymous, and the user's defensive deep dives have no subject.

⚠ **There is no free source.** `coaches.csv`'s own header says it of itself — *"THE ONE PIECE WITH NO
FREE SOURCE"* — and it took three correction rounds before user sign-off. The defensive table is the
same artefact with a different subject: research plus a review gate, not a download.

**Fix: DATA-2 / 0.13.1.** `reference/defense_coaches.csv` + `reference/defense_lineage.csv`, copying
every discipline from the offensive table **deliberately**, because the method is already proven and
reviewed: majority-of-games inclusion; `PARTIAL`/`SPLIT` pinned to a week window or dropped outright
(*averaging two coordinators' games into one fingerprint is the easiest way to make the module lie*);
`head_coach` auto-filled from `pbp.home_coach`/`away_coach` so review effort lands only on the
coordinator columns; `in_house`; explicit `(none)`/`(unknown)` sentinels; a per-row confidence; and a
**user sign-off gate before 0.13.8 consumes it**.

⚠ **`base_front` and `coverage_identity` stay out of the CSV.** They are derivable from 0.13.2, and the
16.5 derived-vs-curated rule says a question a feed can answer gets no human maintainer. **The CSV
carries only what no feed knows: who called it.**

**Done-when:** B3 — 32 teams for 2026; every row carries a confidence; **no team-season has two majority
play-callers**; PARTIAL seasons pinned or dropped, never averaged; `head_coach` reconciles exactly
against `pbp`.

**☐ 2026-08-03.**
