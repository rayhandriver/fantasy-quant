"""Phase 12.2 runner — the extraction seam (deterministic default + gated LLM edge).

    uv run python steps/phase12_2_extract.py

Shows the offline rules extractor on sample headlines, the deterministic structured-injury mapping
(the
validated historical path), and the availability status of the gated Claude client — which stays
off unless
both the `anthropic` SDK and a credential resolve, so the core is LLM-free and this script runs
anywhere.
"""

from __future__ import annotations

from fantasy_quant.news.extract import ClaudeClient, extract_signal, structured_injury_signal

SAMPLES = [
    "Report: star RB ruled out for Sunday with a hamstring injury",
    "WR listed as questionable, game-time decision after limited practice",
    "Veteran TE activated off injured reserve, expected to play Week 10",
    "Backup RB named the starter; team moves to a workhorse role",
    "Coach: receiver benched, moving to a committee at the position",
    "Quarterback throws for 3 TDs in a comfortable win",   # → none
]


def main() -> None:
    print("=== Phase 12.2 extraction (deterministic offline default) ===")
    for text in SAMPLES:
        s = extract_signal(text)
        print(f"  [{s.signal_type:20} sev={s.severity:+.2f} conf={s.confidence:.2f}] {text[:60]}")

    print("\n=== structured injury signal (the validated historical path) ===")
    for status, practice in [("Out", None), ("Doubtful", None),
                             ("Questionable", "Did Not Practice"),
                             ("Questionable", "Full Participation"), ("Probable", None)]:
        s = structured_injury_signal(status, practice)
        print(f"  {status:14} practice={str(practice):18} -> {s.signal_type:20} "
              f"sev={s.severity:+.2f} conf={s.confidence:.2f}")

    print("\n=== LLM seam (gated) ===")
    client = ClaudeClient()
    avail = client.available()
    print(f"  ClaudeClient.available() = {avail}  (model={client.model})")
    print("  " + ("LLM edge is live — free-text headlines would route to Claude." if avail else
                  "no ANTHROPIC_API_KEY / anthropic SDK → falls back to rules (core LLM-free)."))

    # correctness spot-checks on the deterministic path.
    assert extract_signal("player ruled out for the game").signal_type == "injury_out"
    assert extract_signal("activated off injured reserve").signal_type == "injury_return"
    assert extract_signal("moving to a committee backfield").signal_type == "role_down"
    assert extract_signal("threw for 300 yards").signal_type == "none"
    print("\n=== phase12_2_extract: PASS ===")


if __name__ == "__main__":
    main()
