"""Phase 12.2 — signal extraction (fuzzy text → a structured, timestamped fact).

The reframe's guardrail (CLAUDE.md §4, `docs/REFRAME-2026-07-04.md`): **AI on the edges,
deterministic
core.** An LLM may turn a beat-writer sentence into a *structured object* — it never computes a
number
that has to be correct. So this module's only job is **extraction**: text → an
:class:`ExtractedSignal`
(what happened, to whom, how severe, how confident). The *pricing* of a signal into a points shift
lives
in the deterministic core (12.4 calibrates it on DEV), never here.

Two extractors, one seam:

* :func:`rules_extract` — a **deterministic, offline** keyword extractor. It is the default, runs
in the
  test suite with no network, and is what powers the historical structured feeds. Boring on purpose.
* :class:`ClaudeClient` — the **LLM seam**, gated behind ``ANTHROPIC_API_KEY`` + the ``anthropic``
SDK
  (a soft dependency — not installed by default). It reads free-text headlines (the forward-only
  path,
  since RSS can't be backfilled) into the same :class:`ExtractedSignal` shape. Never invoked unless
  a
  caller explicitly passes a live client, so the core stays LLM-free and every test stays offline.

:func:`structured_injury_signal` is the third, trivial extractor: the injury feed already *is*
structured
(report_status = Out/Doubtful/Questionable/Probable), so "extraction" there is a deterministic
mapping —
this is the historical, PIT, validatable signal Phase 12.3/12.4 actually run on.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# signal taxonomy: a downgrade (− severity) threatens value, an upgrade (+) adds it.
SIGNAL_TYPES = ("injury_out", "injury_questionable", "injury_return", "role_up", "role_down",
                "none")

# the gated LLM seam defaults to Haiku 4.5 — this is a high-volume, simple, fixed-schema extraction
# (a headline → one small object), exactly the "simple, speed-critical" tier Haiku targets, and it
# runs
# on the edges, never the core. Trivially overridable via ClaudeClient(model=...).
EXTRACT_MODEL = "claude-haiku-4-5"


@dataclass(frozen=True)
class ExtractedSignal:
    """One structured news fact. ``severity`` ∈ [−1, 1] is a *direction+magnitude* (− = the player's
    outlook worsened, + = improved), **not** a points shift — the deterministic core prices it
    (12.4).
    ``confidence`` ∈ [0, 1] is how sure the extractor is the text says what it thinks. ``source``
    records
    the extractor (``rules`` / ``structured`` / ``claude``) so a consumer never has to guess
    provenance."""
    signal_type: str
    severity: float
    confidence: float
    source: str
    player_name: str | None = None
    raw: str = ""

    def __post_init__(self) -> None:
        if self.signal_type not in SIGNAL_TYPES:
            raise ValueError(f"unknown signal_type {self.signal_type!r}; pick from {SIGNAL_TYPES}")


NONE_SIGNAL = ExtractedSignal("none", 0.0, 0.2, "rules")


# ------------------------------------------------------------------------------------------------
# the deterministic offline extractor (the default; test target)
# ------------------------------------------------------------------------------------------------
# ordered (regex, signal_type, severity, confidence) — first match wins. A *return* ("activated off
# injured reserve") is checked before the *out* rules, since it is the more specific event and the
# phrase "injured reserve" appears in both; the decisive out phrasings then precede the softer ones.
_RULES: tuple[tuple[str, str, float, float], ...] = (
    (r"\b(activated|returns?|cleared to (play|return)|will play|expected to (play|suit up)|"
     r"off (of )?injured reserve|back (to|at) (full )?practice|good to go)\b",
     "injury_return", 0.6, 0.7),
    (r"\b(ruled out|will not play|won'?t play|inactive|placed on i\.?r\.?|"
     r"injured reserve|out for the (season|year)|out indefinitely)\b", "injury_out", -1.0, 0.85),
    (r"\bdoubtful\b", "injury_out", -0.75, 0.75),
    (r"\b(questionable|game[- ]time decision|limited (in )?practice|did not practice|dnp)\b",
     "injury_questionable", -0.35, 0.55),
    (r"\b(named (the )?starter|will start|promoted|takes over|lead (back|role)|"
     r"every[- ]down|workhorse|feature back|expanded role|wr1|rb1|te1)\b", "role_up", 0.5, 0.6),
    (r"\b(benched|demoted|committee|time[- ]?share|lost (his|the) (starting )?job|"
     r"backup role|reduced role|phased out|split (carries|snaps)|buried)\b",
     "role_down", -0.5, 0.6),
)
_COMPILED = [(re.compile(p, re.IGNORECASE), st, sev, conf) for p, st, sev, conf in _RULES]


def rules_extract(text: str | None) -> ExtractedSignal:
    """Deterministic keyword extraction (offline, pure). First matching rule wins; no match ⇒
    ``none``.
    This is the default extractor and the one the test suite exercises — it never touches the
    network."""
    if not text:
        return ExtractedSignal("none", 0.0, 0.2, "rules", raw="")
    for rx, st, sev, conf in _COMPILED:
        if rx.search(text):
            return ExtractedSignal(st, sev, conf, "rules", raw=str(text))
    return ExtractedSignal("none", 0.0, 0.2, "rules", raw=str(text))


# ------------------------------------------------------------------------------------------------
# the structured-feed extractor (the historical, validatable path — deterministic by construction)
# ------------------------------------------------------------------------------------------------
# report_status is already the structured fact; "extraction" is a lookup. practice_status refines a
# Questionable (a player who Did Not Practice all week is a likelier sit than one who was Full).
_STATUS_SIGNAL: dict[str, tuple[str, float, float]] = {
    "Out": ("injury_out", -1.0, 0.95),
    "Injured Reserve": ("injury_out", -1.0, 0.97),
    "IR": ("injury_out", -1.0, 0.97),
    "Doubtful": ("injury_out", -0.75, 0.85),
    "Questionable": ("injury_questionable", -0.35, 0.6),
    "Probable": ("none", -0.1, 0.5),
}


def structured_injury_signal(report_status: str | None,
                             practice_status: str | None = None) -> ExtractedSignal:
    """Map an official injury-report designation straight to an :class:`ExtractedSignal`
    (deterministic,
    PIT, no LLM). A ``Questionable`` is nudged more severe when the practice report is DNP/limited
    — the
    market's own soft read of who actually sits. This is the signal 12.3/12.4 validate
    historically."""
    st, sev, conf = _STATUS_SIGNAL.get(str(report_status), ("none", 0.0, 0.3))
    if st == "injury_questionable" and practice_status:
        ps = str(practice_status).lower()
        if "did not" in ps or "dnp" in ps:
            sev, conf = -0.6, 0.7
        elif "limited" in ps:
            sev, conf = -0.4, 0.62
    return ExtractedSignal(st, sev, conf, "structured", raw=str(report_status or ""))


# ------------------------------------------------------------------------------------------------
# the LLM seam (gated; free-text / forward-only path)
# ------------------------------------------------------------------------------------------------
@runtime_checkable
class LLMClient(Protocol):
    """The extraction seam. Any object with ``available() -> bool`` and ``extract(text) -> dict``
    (the
    dict shaped like :class:`ExtractedSignal`'s fields) can drive :func:`extract_signal` — the real
    :class:`ClaudeClient`, or a fake in tests."""
    def available(self) -> bool: ...
    def extract(self, text: str) -> dict: ...


_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "player_name": {"type": ["string", "null"]},
        "signal_type": {"type": "string", "enum": list(SIGNAL_TYPES)},
        "severity": {"type": "number"},
        "confidence": {"type": "number"},
    },
    "required": ["player_name", "signal_type", "severity", "confidence"],
    "additionalProperties": False,
}

_EXTRACT_SYSTEM = (
    "You extract a single fantasy-football-relevant fact from a news headline into a structured "
    "object. signal_type is one of: injury_out (a player will miss or likely miss a game), "
    "injury_questionable (uncertain / game-time), injury_return (returning to health or lineup), "
    "role_up (a larger role — named starter, workhorse, promotion), role_down (a smaller role — "
    "benched, committee, demotion), or none. severity is in [-1, 1]: negative when the player's "
    "fantasy outlook worsened, positive when it improved, 0 for none. confidence is in [0, 1]. "
    "player_name is the affected player, or null. Report only what the text states; never invent a "
    "number that must be correct — you are extracting a fact, not projecting points."
)


@dataclass
class ClaudeClient:
    """The gated Claude extraction client — the LLM edge of Phase 12.

    Uses the Anthropic Messages API with structured outputs (``output_config.format``) so the
    response is
    schema-valid JSON. Gated three ways: it imports ``anthropic`` **lazily** (soft dependency),
    reports
    :meth:`available` only when both the SDK and a credential resolve, and is invoked by
    :func:`extract_signal` **only when a caller passes it in**. The deterministic core never
    constructs
    one. Model defaults to :data:`EXTRACT_MODEL` (Haiku 4.5 — cheap, fast, right-sized for a high-
    volume
    fixed-schema extraction on the edges)."""
    model: str = EXTRACT_MODEL
    max_tokens: int = 512
    _client: object = None

    def available(self) -> bool:
        """True iff the ``anthropic`` SDK is importable and a credential resolves — so a machine
        without
        either silently falls back to the rules extractor instead of erroring."""
        if os.getenv("ANTHROPIC_API_KEY") is None and os.getenv("ANTHROPIC_AUTH_TOKEN") is None:
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def _ensure(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    def extract(self, text: str) -> dict:
        """Extract one signal via Claude. Returns a dict matching :class:`ExtractedSignal`'s fields.
        Raises if called when :meth:`available` is False (the SDK/credential isn't there) — callers
        should
        gate on :func:`extract_signal`, which checks availability and falls back to rules."""
        client = self._ensure()
        resp = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=_EXTRACT_SYSTEM,
            output_config={"format": {"type": "json_schema", "schema": _EXTRACT_SCHEMA}},
            messages=[{"role": "user", "content": str(text)}],
        )
        payload = next((b.text for b in resp.content if b.type == "text"), "{}")
        return json.loads(payload)


def extract_signal(text: str | None, *, client: LLMClient | None = None) -> ExtractedSignal:
    """Extract a structured signal from free text — the 12.2 entry point.

    Uses ``client`` (the LLM seam) **only** when one is passed *and* it reports :meth:`available`;
    otherwise falls back to the deterministic :func:`rules_extract`. So the default path — and
    every unit
    test — is offline, and the LLM is a strictly opt-in edge. A malformed LLM payload also falls
    back to
    rules rather than raising (the edge never breaks the pipeline)."""
    if client is not None and client.available():
        try:
            d = client.extract(text or "")
            return ExtractedSignal(
                signal_type=str(d["signal_type"]),
                severity=float(d["severity"]),
                confidence=float(d["confidence"]),
                source="claude",
                player_name=d.get("player_name"),
                raw=str(text or ""),
            )
        except (KeyError, ValueError, TypeError, json.JSONDecodeError):
            return rules_extract(text)
    return rules_extract(text)
