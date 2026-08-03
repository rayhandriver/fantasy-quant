"""Session DATA-1 / 0.12.6 — land the small sources and close **T44**.

    uv run python steps/phase0_12_6_small_sources.py

Thirteen sources that were individually never worth a session. The done-bar is not "they
downloaded" but that each one lands with a **declared grain, a key that is actually unique, and a
PIT class** — and that ``schedules`` demonstrably replaces the ``ecr_snapshots`` bye workaround.

Writes ``analysis/phase0_12_6_small_sources.json``.
"""

from __future__ import annotations

import json

from fantasy_quant.config import PROJECT_ROOT
from fantasy_quant.data import db
from fantasy_quant.data.sources import small

OUT_JSON = PROJECT_ROOT / "analysis" / "phase0_12_6_small_sources.json"


def t44_check(con) -> dict:
    """T44 — every team gets exactly one bye, derived from the schedule rather than a board."""
    out = {}
    for season in (2023, 2024, 2025, 2026):
        try:
            byes = small.bye_weeks(con, season)
        except Exception as e:
            out[str(season)] = {"error": f"{type(e).__name__}: {e}"}
            continue
        per_team = byes.groupby("team").size()
        out[str(season)] = {
            "n_teams": int(len(per_team)),
            "n_teams_with_exactly_one_bye": int((per_team == 1).sum()),
            "bye_week_range": (
                [int(byes["bye_week"].min()), int(byes["bye_week"].max())]
                if len(byes) else None
            ),
            "ok": bool(len(per_team) == 32 and (per_team == 1).all()),
        }
    return out


def main() -> dict:
    con = db.connect()
    reports = small.ingest_all_small(con)
    errors = [r for r in reports if "error" in r]
    missing_key = [r for r in reports if r.get("key_columns_missing")]
    # ★ Not "no source has duplicate keys" — five of them legitimately do. The bar is that every
    # source's *declaration* about its own grain is true, which is the claim a downstream join
    # will rely on.
    bad_decl = [r for r in reports
                if "error" not in r and not r.get("key_declaration_holds", False)]

    t44 = t44_check(con)
    # 2026 has not been played, so a bye check on it is a check the *fixture list* exists; the
    # claim the bar makes is about the seasons that have one.
    t44_ok = all(v.get("ok") for k, v in t44.items() if k in ("2023", "2024", "2025"))

    result = {
        "substep": "0.12.6",
        "n_sources": len(reports),
        "n_ok": len(reports) - len(errors),
        "errors": errors,
        "sources_without_a_unique_row_key": [
            {"table": r["table"], "grain": r["grain"], "key": r["key"],
             "n_dup": r["n_duplicate_keys"]}
            for r in reports if "error" not in r and not r["key_declared_unique"]
        ],
        "sources_whose_grain_declaration_is_false": [
            {"table": r["table"], "key": r["key"], "declared_unique": r["key_declared_unique"],
             "n_dup": r["n_duplicate_keys"], "missing": r["key_columns_missing"]}
            for r in bad_decl
        ],
        "T44_byes_from_schedule": t44,
        "T44_closed": t44_ok,
        "reports": reports,
        "passed": not errors and not missing_key and not bad_decl and t44_ok,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True, default=str))

    for r in reports:
        if "error" in r:
            print(f"  ERR  {r['table']:20s} {r['error']}")
        else:
            flag = "" if r["key_declaration_holds"] else "  ← DECLARATION FALSE"
            uniq = "unique" if r["key_declared_unique"] else f"group({r['n_duplicate_keys']} dup)"
            print(f"  ok   {r['table']:20s} {r['n_rows']:>8,} rows  {r['n_cols']:>3} cols  "
                  f"{str(r['seasons']):>14}  key={uniq:<16} {r['pit_class']}{flag}")
    print("\nT44:", json.dumps(t44, indent=2))
    print(f"\n0.12.6 {'PASS' if result['passed'] else 'FAIL'}")
    return result


if __name__ == "__main__":
    raise SystemExit(0 if main()["passed"] else 1)
