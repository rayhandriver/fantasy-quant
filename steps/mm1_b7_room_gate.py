"""MM-1a bar **B7** — prove the 16.18 season gate makes a historical measurement unmoved.

    uv run python steps/mm1_b7_room_gate.py [--seasons 2017 2018] [--seeds 6]

★ **Why this is a construction proof and not a re-measurement.** 16.18 gave one `balanced` seat in
:data:`~fantasy_quant.draft.personalities.REALISTIC_ROOM` to ``fitted_manager``, which normally
means every sheet measured on that room moves and each movement has to be stated. It does not,
because the seat carries a **season-scoped** belief board and
:func:`~fantasy_quant.draft.personalities.make_room` degrades it to ``balanced`` on any season the
profile does not describe — and ``balanced`` is precisely the chair 16.18 took. So on 2017–2024 the
shipped room *is* the pre-16.18 room, and this step asserts that rather than assuming it.

⚠ **The control must be able to fail** (T31's rule). The two arms differ only in how the room is
*specified* — one takes the shipped default and lets the gate fire, the other names the pre-16.18
ten seats explicitly. If the gate ever stopped firing, the first arm would seat the manager on a
historical board and these numbers would separate. That is exactly the failure this asserts against,
so a zero here is informative rather than tautological.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

OUT = Path("analysis/mm1_b7_room_gate.json")
BARS = Path("steps/mock_room_bars.py")

#: The ten seats `REALISTIC_ROOM` held before 16.18 — the arm the gated default must reproduce.
PRE_1618 = ("autopilot", "balanced", "balanced", "balanced", "balanced",
            "value_hawk", "safe_floor", "reacher", "upside_chaser", "chalk")

#: Leaves that describe the *run* rather than the *result*; they differ by construction.
SKIP_PREFIXES = ("config.", "label", "room", "generated", "seconds", "elapsed")


def _flat(d, prefix: str = "") -> dict:
    out: dict = {}
    for k, v in (d.items() if isinstance(d, dict) else []):
        kk = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flat(v, kk))
        elif isinstance(v, (int, float, str, bool)) or v is None:
            out[kk] = v
    return out


def _run(label: str, seasons: list[int], seeds: int, room: tuple[str, ...] | None) -> Path:
    cmd = [sys.executable, str(BARS), "--label", label, "--seeds", str(seeds),
           "--shuffle-room", "--no-readout", "--seasons", *[str(s) for s in seasons]]
    if room is not None:
        cmd += ["--room", *room]
    subprocess.run(cmd, check=True)
    return Path(f"analysis/mock_room_bars_{label}.json")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seasons", type=int, nargs="*", default=[2017, 2018])
    ap.add_argument("--seeds", type=int, default=6)
    args = ap.parse_args()

    gated = _flat(json.loads(_run("b7_gated", args.seasons, args.seeds, None).read_text()))
    pre = _flat(json.loads(_run("b7_pre1618", args.seasons, args.seeds, PRE_1618).read_text()))

    keys = [k for k in gated if k in pre and not k.startswith(SKIP_PREFIXES)]
    diff = {k: {"gated": gated[k], "pre_1618": pre[k]} for k in keys if gated[k] != pre[k]}
    report = {
        "bar": "B7 — the shipped room reproduces the pre-16.18 room on every uncovered season",
        "seasons": args.seasons, "seeds": args.seeds, "shuffle_room": True,
        "leaves_compared": len(keys), "leaves_differing": len(diff), "differing": diff,
        "pass": not diff,
        "why_this_is_a_construction_proof": (
            "make_room degrades a requires_profile seat to `balanced` on a season its profile does "
            "not cover, and `balanced` is the seat 16.18 took the chair from — so an uncovered "
            "season is the pre-16.18 room bit-for-bit. The control can fail: if the gate stopped "
            "firing, the gated arm would seat the manager and these numbers would separate."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "differing"}, indent=2))
    if diff:
        raise SystemExit(f"B7 FAIL — {len(diff)} leaves moved: {sorted(diff)[:10]}")


if __name__ == "__main__":
    main()
