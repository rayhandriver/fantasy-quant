"""Personalization spine · step 1 — the DraftConfig contract (construct, validate, resolve).

    uv run python steps/spine_1_config.py

Done when: the constraint object (PERSONALIZATION §3, MVP subset) constructs and normalizes cleanly,
the archetype "master dial" produces sensible per-position round tilts, the benchmark strips every
preference (the direct-indexing peer), and the validation gates reject contradictory configs. No DB.
"""

from __future__ import annotations

from fantasy_quant.draft.config import ARCHETYPES, DraftConfig, LeagueSetup, archetype_tilt


def main() -> None:
    print("archetypes (the master dial):", ", ".join(ARCHETYPES))
    print("\npositional tilt schedule (rounds early/late; + = reach sooner, − = fade):")
    print("  archetype   round   QB     RB     WR     TE")
    for arch in ARCHETYPES:
        for rnd in (1, 3, 8):
            t = {p: archetype_tilt(arch, p, rnd) for p in ("QB", "RB", "WR", "TE")}
            print(f"  {arch:10s}  r{rnd:<4d}  {t['QB']:+.2f}  {t['RB']:+.2f}  "
                  f"{t['WR']:+.2f}  {t['TE']:+.2f}")

    # a fully-specified personalized config: seat 5, zero-RB, one must, one refusal, one tilt.
    cfg = DraftConfig(
        league=LeagueSetup(draft_slot=5),
        archetype="zero_rb",
        must_draft=["MY_GUY", ("MY_TE", 3.0)],     # bare key → default 2-round reach budget
        never_draft={"A_RIVAL"},
        tilts={"A_SLEEPER": 1.5},
        risk_lambda=0.02,
    )
    print("\nresolved config:")
    print(f"  seat (0-indexed)   : {cfg.league.your_team}")
    print(f"  must_draft         : {[(m.player_key, m.reach_budget) for m in cfg.must_draft]}")
    print(f"  active constraints : {cfg.constraint_labels()}")

    # the direct-indexing benchmark: same seat & risk appetite, zero preferences.
    b = cfg.benchmark()
    assert b.archetype == "bpa" and not b.must_draft and not b.never_draft and not b.tilts
    assert b.league is cfg.league and b.risk_lambda == cfg.risk_lambda
    print(f"  benchmark          : archetype={b.archetype}, no preferences, λ={b.risk_lambda}")

    # leave-one-out (hyphen-safe even for gsis keys): drop exactly one preference.
    dropped = cfg.without_constraint("tilt:A_SLEEPER+1.5")
    assert dropped.tilts == {} and dropped.archetype == "zero_rb"

    # validation gates.
    for bad, msg in [
        (dict(archetype="hero_qb"), "unknown archetype"),
        (dict(risk_lambda=-1.0), "risk_lambda"),
        (dict(must_draft=["X"], never_draft={"X"}), "both must_draft and never_draft"),
        (dict(league=LeagueSetup(draft_slot=99)), "draft_slot"),
    ]:
        try:
            DraftConfig(**bad)
        except ValueError as e:
            assert msg in str(e), f"wrong error for {bad}: {e}"
        else:
            raise AssertionError(f"expected ValueError ({msg}) for {bad}")
    print("\n  [PASS] construction, benchmark, leave-one-out, and 4 validation gates all hold.")
    print("\nSpine step 1 (DraftConfig) — all checks PASS.")


if __name__ == "__main__":
    main()
