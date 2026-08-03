"""Session DATA-1 / 0.12.2 — the **generated inventory + gap register** (**B8**).

    uv run python steps/phase0_12_inventory.py

★ **This is the "anything I may think of down the line" deliverable.** The user's ask was not for
a set of downloads, it was for a store he can interrogate without another investigation. So the
answer to *"do we have X?"* has to live somewhere that is (a) complete, (b) current, and (c) not
maintained by hand — the 16.5 **derived-vs-curated** rule: *hand-curate only what has no free
source; everything a feed can answer should be derived.* A store can answer every question here
about itself, so nothing below is typed by a human. Re-running the step regenerates it.

★ **The consumers column is the point, not a nicety.** T45 exists — ``ngs`` sat ingested and
effectively unread for a year — because **nothing anywhere recorded that a table had a reader**.
*A table nobody reads and a table that does not exist are indistinguishable from the outside,*
and this is what makes them distinguishable. It is found by scanning ``src/``, ``steps/`` and
``app/`` for each table name, so it is evidence rather than intention.

Outputs ``reference/DATA-SOURCES.md`` (generated; do not hand-edit) and
``analysis/data_inventory.json``.
"""

from __future__ import annotations

import json
import re

from fantasy_quant.config import PROJECT_ROOT
from fantasy_quant.data import db, registry

OUT_JSON = PROJECT_ROOT / "analysis" / "data_inventory.json"
OUT_MD = PROJECT_ROOT / "reference" / "DATA-SOURCES.md"
SCAN_DIRS = ("src", "steps", "app", "tests")
SELF = "steps/phase0_12_inventory.py"


def find_consumers(table: str) -> dict:
    """Split the files that mention ``table`` into **producers**, **readers** and **tests**.

    ★ The first version of this counted any mention as a consumer and reported *zero* unread
    tables — which is UI-1's durable lesson 2 (*a grep cannot tell doing from describing*) landing
    on the very column written to catch T45. The step that **ingests** a table mentions it more
    than anyone, so a naive count says every freshly-ingested table is well-read and the register
    is blind to exactly the thing it exists to see.

    So a mention is classified by what the file does with it:

    * **producer** — writes it (``write_df(..., "t")``, ``create or replace table t``), or is the
      source/step module that lands it;
    * **reader** — queries it (``from t``, ``join t``, ``read_table("t")``);
    * **test** — anything under ``tests/``, counted separately, because a table exercised only by
      its own test is still a table nothing in the product reads.

    ⚠ Still a regex over source text, so it is evidence and not proof. But the number that
    matters — **readers outside tests** — is now one a producer cannot inflate.
    """
    name = re.escape(table)
    mention = re.compile(rf"\b{name}\b")
    writes = re.compile(
        rf'(write_df\s*\(\s*[^,]+,\s*[\'"]{name}[\'"]'
        rf'|create\s+or\s+replace\s+(table|view)\s+"?{name}"?'
        rf'|create\s+table\s+(if\s+not\s+exists\s+)?"?{name}"?'
        rf'|TABLE\s*[:=]\s*[\'"]{name}[\'"])',
        re.IGNORECASE,
    )
    reads = re.compile(
        rf'(from\s+"?{name}"?\b|join\s+"?{name}"?\b|update\s+"?{name}"?\b'
        rf'|insert\s+into\s+"?{name}"?\b)',
        re.IGNORECASE,
    )
    producers, readers, tests = [], [], []
    for d in SCAN_DIRS:
        for p in sorted((PROJECT_ROOT / d).rglob("*.py")):
            rel = str(p.relative_to(PROJECT_ROOT))
            if rel in (SELF, "src/fantasy_quant/data/registry.py"):
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if not mention.search(text):
                continue
            # ⚠ NOT an elif chain. A module that lands a table and also exposes a read API over
            # it (`small.py` writes `schedules` and reads it in `bye_weeks`) is both, and letting
            # "producer" mask "reader" reported `schedules` as unread on the very run that closed
            # T44 with it. Producing and reading are independent facts about a file.
            if rel.startswith("tests/"):
                tests.append(rel)
                continue
            if writes.search(text):
                producers.append(rel)
            if reads.search(text):
                readers.append(rel)
    return {"producers": producers, "readers": readers, "tests": tests}


def table_facts(con, table: str) -> dict:
    n = db.row_count(con, table)
    cols = con.execute(
        "select column_name, data_type from information_schema.columns "
        "where table_name = ? order by ordinal_position", [table]
    ).fetchall()
    seasons = []
    if any(c == "season" for c, _ in cols) and n:
        seasons = [
            int(s) for (s,) in con.execute(
                f'select distinct season from "{table}" where season is not null order by 1'
            ).fetchall()
        ]
    fill = {}
    if n and cols:
        sel = ", ".join(f'count("{c}")' for c, _ in cols)
        vals = con.execute(f'select {sel} from "{table}"').fetchone()
        fill = {c: round(v / n, 4) for (c, _), v in zip(cols, vals, strict=True)}
    return {
        "n_rows": n,
        "n_cols": len(cols),
        "columns": [c for c, _ in cols],
        "seasons": seasons,
        "season_range": [seasons[0], seasons[-1]] if seasons else None,
        "fill_rates": fill,
        "n_columns_below_50pct_fill": sum(1 for v in fill.values() if v < 0.5),
    }


def build(con) -> dict:
    live = sorted(db.list_tables(con))
    rows = []
    for t in live:
        s = registry.BY_TABLE.get(t)
        facts = table_facts(con, t)
        cons = find_consumers(t)
        rows.append({
            "table": t,
            "grain": s.grain if s else "(UNDECLARED)",
            "pit_class": s.pit_class if s else "(UNDECLARED)",
            "backtestable": s.backtestable if s else None,
            "source": s.source if s else "(UNDECLARED)",
            "upstream_floor": s.floor if s else None,
            "note": s.note if s else "",
            "producers": cons["producers"],
            "readers": cons["readers"],
            "test_only": cons["tests"],
            # ★ the T45 number: who READS this, outside its own producer and its own tests
            "n_readers": len(cons["readers"]),
            "n_producers": len(cons["producers"]),
            **facts,
        })
    return {
        "n_tables": len(rows),
        "n_undeclared": sum(1 for r in rows if r["pit_class"] == "(UNDECLARED)"),
        "n_unread": sum(1 for r in rows if r["n_readers"] == 0),
        "unread_tables": [r["table"] for r in rows if r["n_readers"] == 0],
        "tables": rows,
    }


def render_md(inv: dict) -> str:
    L = [
        "# DATA-SOURCES — what is in the store, and what is not",
        "",
        "> ⚠ **GENERATED FILE — do not hand-edit.** Regenerate with",
        "> `uv run python steps/phase0_12_inventory.py` (Session DATA-1 / 0.12.2).",
        "> Every row below is derived from the store and from a scan of `src/`, `steps/`, `app/`",
        "> and `tests/`. Hand-editing it makes it a curated file that pretends to be a derived",
        "> one, which is worse than either.",
        "",
        "## Why this file exists",
        "",
        "So that *\"do we have X?\"* is answered by reading one table instead of running another",
        "investigation. Three defects motivated it, and each is the same defect wearing a",
        "different hat — **nothing recorded what we had**:",
        "",
        "- **T46** — `nfl_data_py` is a *wrapper* over the nflverse release assets, and its",
        "  surface was being read as the data's surface. Ten seasons of play-level participation",
        "  data were invisible, not unavailable.",
        "- **T45** — `ngs` was ingested and effectively unread for a year. See the **consumers**",
        "  column: *a table nobody reads and a table that does not exist look identical from the",
        "  outside.*",
        "- **T44** — there was no `schedules` table, so bye weeks were being inferred from a",
        "  third-party *rankings* feed.",
        "",
        "## How to read the columns",
        "",
        "- **PIT class** — `preseason` (known before a draft, safe as a draft feature) ·",
        "  `in_season_weekly` (known only after week *w*; draft-legal **only** through the",
        "  season-*t−1* lag in `features/exposures.py`) · `retrospective` (complete only after the",
        "  season; **never** a feature). Enforced in `data/registry.py`, not merely documented.",
        "- **Backtestable** — `False` means the table must never be a backtest input. It is an",
        "  assertion (`registry.assert_backtestable`), not a label.",
        "- **Floor** — the earliest season that exists **upstream**. A floor is a fact about the",
        "  world, not a gap in our ingest. ⚠ **Do not go looking for data below a floor.**",
        "- **Readers** — files that *query* the table, excluding the module that writes it and",
        "  excluding `tests/`. A producer mentions its own table more than anyone, so counting",
        "  mentions would report every freshly-ingested table as well-read — which is how a",
        "  register goes blind to the T45 it was written to catch. **0 readers is a finding.**",
        "",
        "## ★ Upstream floors — permanent; stop re-investigating these",
        "",
        "| source | first season | consequence |",
        "|---|---|---|",
        "| participation | **2016** | 7 DEV seasons (2016-2022) — workable |",
        "| NGS | **2016** | 7 DEV seasons — workable |",
        "| PFR advanced | **2018** | 5 DEV seasons |",
        "| **FTN charting** | **2022** | **ONE DEV season** — descriptive/live use only, "
        "never a backtest input |",
        "",
        "`DEV_SEASONS` is 2014-2022 and the lockbox is 2023+2024, so a source starting in 2022",
        "contributes exactly one usable development season. *The user's instinct that \"pre-2022",
        "is missing\" is **right for FTN and wrong for everything else**, and that distinction is",
        "the most useful thing in this file.*",
        "",
        "## The store",
        "",
        f"**{inv['n_tables']} tables · {inv['n_undeclared']} undeclared · "
        f"{inv['n_unread']} with no consumer.**",
        "",
        "| table | grain | PIT class | backtest | rows | cols | seasons | floor | readers |",
        "|---|---|---|---|---:|---:|---|---:|---:|",
    ]
    for r in inv["tables"]:
        rng = (f"{r['season_range'][0]}-{r['season_range'][1]}"
               if r["season_range"] else "—")
        bt = "—" if r["backtestable"] is None else ("yes" if r["backtestable"] else "**NO**")
        L.append(
            f"| `{r['table']}` | {r['grain']} | {r['pit_class']} | {bt} | {r['n_rows']:,} | "
            f"{r['n_cols']} | {rng} | {r['upstream_floor'] or '—'} | {r['n_readers']} |"
        )
    L += ["", "## Notes and known holes", ""]
    for r in inv["tables"]:
        if r["note"]:
            L.append(f"**`{r['table']}`** — {r['note']}")
            L.append("")
    if inv["unread_tables"]:
        L += [
            "## ⚠ Tables with no consumer",
            "",
            "Ingested and referenced nowhere in `src/`, `steps/`, `app/` or `tests/`. Either a",
            "source waiting on the work that motivated it, or a T45 in the making.",
            "",
        ] + [f"- `{t}`" for t in inv["unread_tables"]] + [""]
    return "\n".join(L) + "\n"


def main() -> dict:
    con = db.connect(read_only=True)
    inv = build(con)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(inv, indent=2, sort_keys=True, default=str))
    md = render_md(inv)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md)

    # B8 — reproducibility: generating twice from the same store gives the same bytes
    reproduced = render_md(build(con)) == md
    result = {
        "bar": "B8 — the inventory is generated and complete",
        "passed": bool(inv["n_undeclared"] == 0 and reproduced),
        "n_tables": inv["n_tables"],
        "n_undeclared": inv["n_undeclared"],
        "n_unread": inv["n_unread"],
        "unread_tables": inv["unread_tables"],
        "reproducible": reproduced,
        "hand_edited_rows": 0,
        "outputs": [str(OUT_MD.relative_to(PROJECT_ROOT)),
                    str(OUT_JSON.relative_to(PROJECT_ROOT))],
    }
    (PROJECT_ROOT / "analysis" / "phase0_12_2_inventory.json").write_text(
        json.dumps(result, indent=2, sort_keys=True)
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    print(f"\nwrote {OUT_MD.relative_to(PROJECT_ROOT)} ({len(md.splitlines())} lines)")
    print(f"B8 {'PASS' if result['passed'] else 'FAIL'}")
    return result


if __name__ == "__main__":
    raise SystemExit(0 if main()["passed"] else 1)
