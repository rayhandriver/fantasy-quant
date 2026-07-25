"""Phase 16.3 / 16.3b — validate the playcaller-regime reference table; report 16.4 coverage.

    uv run python steps/phase16_3b_coach_history.py

`reference/coaches.csv` is the one input in this project with **no free source** — who calls the
plays is not in any feed we ingest — so it is a human-approved table, and this script is its gate.
It never edits the file. It:

1. loads it under the frozen schema and runs the structural gate,
2. **audits every pre-2026 `head_coach` against `pbp`** (free, exact, PIT) — the cheap check that
   a researched row is about the right regime,
3. runs the **move-graph cross-reference** (the method that found every error in the 2026 half
   with zero external lookups),
4. reports what 16.4 actually gets: the playcaller **regimes**, the 2026 **transport set**, the
   per-playcaller **prior-history coverage**, and — via `reference/coach_lineage.csv` — the
   **fingerprint source** for each team, including the fallback for first-time play-callers.

Some 2026 play-callers have never called a play anywhere, so no amount of research creates a
regime for them. They are not left blank: per the user's direction (2026-07-25) they fall back to
the regime they came up under (Doyle -> Ben Johnson's Bears), tagged as weaker evidence. The
done-bar is that the table passes every structural gate, the head-coach column is exactly right
where pbp can check it, every mentor is itself a fingerprint-able play-caller, and every remaining
finding is explained in `notes`.

Read-only and walled off: nothing here touches the frozen value stack.
"""

from __future__ import annotations

import json
from pathlib import Path

from fantasy_quant.data import db
from fantasy_quant.situation import coaches as C

OUT = Path(__file__).resolve().parents[1] / "analysis" / "phase16_3b_coach_history.json"
TARGET = 2026


def main() -> None:
    con = db.connect(read_only=True)

    df = C.load_coaches()
    C.assert_coaches_schema(df)
    hist = df[df["season"] < TARGET]
    print(f"16.3  table: {len(df)} rows — {len(hist)} historical "
          f"({hist['season'].min()}-{hist['season'].max()}) + "
          f"{len(df) - len(hist)} for {TARGET}")
    print("      confidence: " + ", ".join(f"{k}={v}" for k, v in
                                           df["confidence"].value_counts().items()))

    # --- 1. the free audit ------------------------------------------------------------------
    scaffold = C.head_coach_scaffold(con)
    splits = scaffold[scaffold["interim"] != ""]
    print(f"\n16.3b pbp scaffold: {len(scaffold)} team-seasons "
          f"({scaffold['season'].min()}-{scaffold['season'].max()}), "
          f"{len(splits)} showing a mid-season coaching change")
    print(f"      NB pbp's coach field is game-level only through {int(splits['season'].max())}; "
          "from 2024 it is a season-level coach of record (Daboll shows for all 17 of NYG 2025 "
          "though he was fired in-season), so that count is a LOWER BOUND.")
    audit = C.audit_against_pbp(df, scaffold)
    hard = audit[audit["verdict"] == "MISMATCH"]
    print(f"      head-coach audit: {len(hist)} auditable rows, {len(audit)} not matching the "
          f"primary coach ({len(hard)} MISMATCH, {len(audit) - len(hard)} split-season)")
    if len(audit):
        print(audit.to_string(index=False))
    assert not len(hard), "a curated head_coach names someone who did not coach that team"

    # --- 2. the move-graph cross-reference --------------------------------------------------
    findings = C.move_graph_check(df)
    n_hard = sum(f.startswith("HARD") for f in findings)
    print(f"\n      move-graph: {len(findings)} findings ({n_hard} HARD)")
    for f in findings:
        print(f"        • {f}")
    assert n_hard == 0, "the table contradicts itself — see the HARD findings above"

    # --- 3. what 16.4 gets ------------------------------------------------------------------
    regimes = C.playcaller_regimes(hist)
    print(f"\n16.4  historical regimes available: {len(regimes)} spells over "
          f"{len(hist)} team-seasons, {regimes['play_caller'].nunique()} distinct play-callers")

    transport = C.new_regimes(df, TARGET)
    print(f"      {TARGET} transport set: {len(transport)} of "
          f"{(df['season'] == TARGET).sum()} teams have a new play-caller "
          + ", ".join(f"{k}={v}" for k, v in transport["trigger"].value_counts().items()))
    print("        " + ", ".join(sorted(transport["team"])))

    cov = C.coverage(df, TARGET)
    fingerprintable = cov[cov["prior_seasons"] > 0]
    print(f"\n      coverage: {len(fingerprintable)}/{len(cov)} {TARGET} play-callers have prior "
          f"history (median {int(fingerprintable['prior_seasons'].median())} seasons)")
    print(cov.sort_values("prior_seasons", ascending=False).to_string(index=False))

    # --- 4. what 16.4 fingerprints each team on, incl. the first-time-play-caller fallback -----
    lineage = C.load_lineage()
    src = C.fingerprint_source(df, TARGET, lineage)
    new = src[src["is_new_regime"]]
    own = new[new["source"] == "own"]
    lin = new[new["source"] == "lineage"]
    none = new[new["source"] == "none"]
    print(f"\n      ★ 16.4 fingerprint source for the {len(new)} {TARGET} new-regime teams: "
          f"{len(own)} own · {len(lin)} lineage · {len(none)} none")
    print(f"        own      ({len(own)}): {', '.join(sorted(own['team']))}")
    print(f"        lineage  ({len(lin)}): " + ", ".join(
        f"{r.team}<-{r.fingerprint_on}" + (" [same team]" if r.same_team is True else "")
        for r in lin.sort_values("team").itertuples()))
    if len(none):
        print(f"        none     ({len(none)}): {', '.join(sorted(none['team']))} — 16.4 must stay "
              "silent on these")
    # where lineage and team continuity disagree, 16.4 owes the user both readings
    split = lin[lin["same_team"] != True]  # noqa: E712 — pandas NA-safe identity, not truthiness
    for r in split.itertuples():
        print(f"        NB {r.team}: lineage says {r.fingerprint_on}, but {TARGET - 1} continuity "
              f"says {r.prev_play_caller} — report both, do not pick silently")

    # --- gates -------------------------------------------------------------------------------
    assert len(regimes) >= 40, "too few historical regimes to fingerprint anything"
    assert (regimes["n_seasons"] >= 1).all(), "a regime with no seasons"
    assert len(own) + len(lin) >= 12, "16.4 would cover too little of the league to be worth it"
    # the fallback is only worth anything if every mentor is itself a play-caller we can fingerprint
    for r in lineage.itertuples():
        assert (df["play_caller"] == r.mentor).any(), f"lineage mentor {r.mentor} has no regime"

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "n_rows": len(df), "n_historical": len(hist), "n_target": int((df["season"] ==
                                                                      TARGET).sum()),
        "seasons": [int(hist["season"].min()), int(hist["season"].max())],
        "confidence": {k: int(v) for k, v in df["confidence"].value_counts().items()},
        "pbp_scaffold_team_seasons": len(scaffold),
        "pbp_split_seasons_visible": len(splits),
        "pbp_game_level_coach_through": int(splits["season"].max()),
        "audit_mismatches": len(hard), "audit_split_seasons": len(audit) - len(hard),
        "move_graph_findings": findings,
        "n_regimes": len(regimes), "n_distinct_playcallers": int(regimes["play_caller"].nunique()),
        "transport_set": sorted(transport["team"]),
        "transport_triggers": {k: int(v) for k, v in transport["trigger"].value_counts().items()},
        "fingerprint_source_counts": {"own": len(own), "lineage": len(lin), "none": len(none)},
        "fingerprintable_teams": sorted(own["team"]),
        "lineage_fallback_teams": sorted(lin["team"]),
        "unfingerprintable_teams": sorted(none["team"]),
        "coverage": cov.to_dict("records"),
        "fingerprint_source": src.to_dict("records"),
    }, indent=2) + "\n")
    print(f"\nwrote {OUT.relative_to(OUT.parents[1])}")
    print("\n16.3b DONE-BAR: schema PASS · head-coach audit PASS · move-graph PASS (no HARD "
          "findings).\n★ GATE: the historical half is Claude-researched — USER REVIEW is owed "
          "before 16.4 consumes it.")


if __name__ == "__main__":
    main()
