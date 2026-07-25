"""Phase 16.4 — build play-caller scheme fingerprints and transport them onto 2026 rosters.

    uv run python steps/phase16_4_fingerprint.py

The done-bar here is **"computes correctly and is honestly labeled"**, not "beats a baseline".
BUILD_PLAN scopes 16.4 as descriptive-only: the clean-transport sample is far too thin for an
edge claim, so there is no FDR gate and nothing to out-predict. What the script must prove is
that the arithmetic is right, the partial regimes were cut to the right weeks, every new-regime
team is either fingerprinted or explicitly silent, and the output says out loud how much of each
number is actually the incoming coach.

That last point is the one worth reading. Role shares are mostly a **roster** fact, not a scheme
fact — so most of a transported "delta" is the incumbent slot regressing toward the league
average, which any hire whatsoever would produce. The player board splits every move into
`reversion_pp` (would have happened anyway) and `scheme_pp` (what the fingerprint actually
claims), and this script reports the ratio. Shipping only the total would overstate the phase.

Read-only and walled off: nothing here touches the frozen value stack.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from fantasy_quant.data import db
from fantasy_quant.situation import coaches as C
from fantasy_quant.situation import fingerprint as F

OUT = Path(__file__).resolve().parents[1] / "analysis" / "phase16_4_fingerprint.json"
TARGET = 2026


def main() -> None:
    con = db.connect(read_only=True)

    # --- 1. the warehouse reads, at week grain so a partial regime can be cut to its games ----
    tend = F.team_week_tendencies(con)
    usage = F.player_week_usage(con)
    prof = F.league_profiles(tend, usage)
    mom = F.league_moments(prof)
    zs = F.zscore(prof, mom)
    print(f"16.4  league baseline: {len(prof)} team-seasons "
          f"({int(prof['season'].min())}-{int(prof['season'].max())}), "
          f"{len(F.METRICS)} metrics, z-scored within season")

    # --- 2. regime-seasons, with the partial windows applied ---------------------------------
    coaches = C.load_coaches()
    C.assert_coaches_schema(coaches)
    rst = F.regime_season_table(coaches, tend)
    F.assert_regime_coverage(rst)
    kept, dropped = rst[~rst["dropped"]], rst[rst["dropped"]]
    print(f"\n      regime-seasons: {len(rst)} in the table, {len(kept)} usable, "
          f"{len(dropped)} dropped, {int(rst['partial'].sum())} cut to a partial window")
    for r in rst[rst["partial"]].sort_values(["season", "team"]).itertuples():
        print(f"        • {r.season} {r.team} {r.play_caller}: {r.n_weeks} weeks "
              f"({F.PARTIAL_WEEKS[(r.season, r.team, r.play_caller)]})")
    for r in dropped.sort_values(["season", "team"]).itertuples():
        print(f"        ✗ {r.season} {r.team} {r.play_caller} — {r.drop_reason}")

    # --- 3. fingerprints ----------------------------------------------------------------------
    rp = F.regime_profiles(rst, tend, usage, mom)
    k = F.eb_weights(rp)
    fp = F.fingerprints(rp, k)
    per_spell = F.fingerprints(rp, k, by=("play_caller", "team"))
    F.assert_fingerprints_sane(fp)
    print(f"\n      fingerprints: {len(fp)} play-callers ({len(per_spell)} play-caller×team "
          f"spells) over {len(rp)} regime-seasons — EB-shrunk toward the league baseline")

    # how coach-stable is each trait? this is the interesting half of the output.
    stab = sorted(((c, k[c], float(fp[f"{c}_w"].max())) for c in F.METRICS), key=lambda t: t[1])
    print("\n      ★ trait stability (low k = the coach really does carry it between jobs):")
    for c, kk, wmax in stab:
        print(f"        {c:22s} k={kk:5.1f}  max weight {wmax:.2f}")
    least = stab[-1]
    print(f"      → {least[0]} is the LEAST coach-stable trait (k={least[1]:.1f}): the alpha "
          "receiver's target share is a roster fact, not a scheme fact.")

    # --- 4. transport -------------------------------------------------------------------------
    src = C.fingerprint_source(coaches, TARGET)
    tr = F.transport(fp, zs, src, TARGET)
    F.assert_transport_honest(tr, src)
    n_fp = int(tr["fingerprinted"].sum())
    print(f"\n      transport: {len(tr)} new-regime teams, {n_fp} fingerprinted, "
          f"{len(tr) - n_fp} silent · "
          + ", ".join(f"{a}={b}" for a, b in tr["source"].value_counts().items()))
    both = tr[tr["alt_prior_on"].notna()]
    print(f"      ★ {len(both)} teams get TWO priors (mentor lineage vs. the outgoing caller) — "
          "reported side by side, never resolved silently:")
    for r in both.itertuples():
        print(f"        • {r.team}: lineage {r.fingerprint_on}  vs  continuity {r.alt_prior_on}")

    # --- 5. the per-player board ---------------------------------------------------------------
    pb = F.player_board(con, tr, fp, prof, mom, TARGET)
    rev, sch = pb["reversion_pp"].abs(), pb["scheme_pp"].abs()
    scheme_share = float(sch.sum() / (sch.sum() + rev.sum()))
    print(f"\n      player board: {len(pb)} draftable players across {pb['team'].nunique()} "
          f"transport teams")
    print(f"      ★ HONESTY CHECK — only {scheme_share:.1%} of the implied role-share movement is "
          f"the incoming coach; the other {1 - scheme_share:.1%} is the incumbent slot regressing "
          "toward the league mean, which ANY hire would produce.")
    print(f"        mean |reversion| {rev.mean():.2f}pp vs mean |scheme| {sch.mean():.2f}pp")
    top = pb.reindex(pb["scheme_pp"].abs().sort_values(ascending=False).index).head(10)
    print("\n      largest genuine scheme effects (not reversion):")
    print(top[["player", "position", "team", "adp", "fingerprint_on", "source",
               "share_prev", "share_implied", "scheme_pp", "reversion_pp",
               "multiplier"]].round(3).to_string(index=False))

    # --- 6. done-bar --------------------------------------------------------------------------
    assert len(fp) and len(tr) == 17 and len(pb), "16.4 produced an empty deliverable"
    assert scheme_share < 0.5, "scheme effect exceeds reversion — check the league normalization"
    print("\n      ✅ 16.4 DONE-BAR: fingerprints computed, partial regimes cut to their own "
          "weeks,\n         every new-regime team resolved, both priors reported where they "
          "disagree,\n         and the scheme-vs-reversion split published. DESCRIPTIVE ONLY — "
          "no FDR gate,\n         no edge claim, nothing wired into the frozen value stack.")

    payload = {
        "target_season": TARGET,
        "metrics": list(F.METRICS),
        "league_baseline_team_seasons": int(len(prof)),
        "regime_seasons": {"total": int(len(rst)), "usable": int(len(kept)),
                           "partial_windowed": int(rst["partial"].sum()),
                           "dropped": {f"{r.season} {r.team} {r.play_caller}": r.drop_reason
                                       for r in dropped.itertuples()}},
        "fingerprints": {"play_callers": int(len(fp)), "spells": int(len(per_spell))},
        "trait_stability": {c: {"k": round(kk, 3), "max_weight": round(w, 3)}
                            for c, kk, w in stab},
        "transport": {"teams": int(len(tr)), "fingerprinted": n_fp,
                      "by_source": {a: int(b) for a, b in tr["source"].value_counts().items()},
                      "two_priors": {r.team: {"lineage": r.fingerprint_on,
                                              "continuity": r.alt_prior_on}
                                     for r in both.itertuples()}},
        "player_board": {"rows": int(len(pb)), "teams": int(pb["team"].nunique()),
                         "scheme_share_of_movement": round(scheme_share, 4),
                         "mean_abs_reversion_pp": round(float(rev.mean()), 3),
                         "mean_abs_scheme_pp": round(float(sch.mean()), 3)},
        "largest_scheme_effects": [
            {"player": r.player, "team": r.team, "position": r.position, "adp": float(r.adp),
             "fingerprint_on": r.fingerprint_on, "source": r.source,
             "scheme_pp": round(float(r.scheme_pp), 3),
             "reversion_pp": round(float(r.reversion_pp), 3),
             "multiplier": None if not np.isfinite(r.multiplier) else round(float(r.multiplier), 3)}
            for r in top.itertuples()],
        "labeling": "DESCRIPTIVE ONLY — unvalidated hypothesis, no FDR gate, no edge claim.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\n      wrote {OUT.relative_to(OUT.parents[1])}")


if __name__ == "__main__":
    main()
