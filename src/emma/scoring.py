"""Rules-based lead scorer for Emma calls.

Pure function: takes a call record dict (and optionally the transcript
text) and returns a deterministic score + tier + human-readable reasons.

Designed to be swappable for an LLM-based scorer later by keeping the
signature stable. Scoring runs at write-time (post-call webhook +
log_call_outcome handler), not on every dashboard render.
"""

from dataclasses import dataclass, field
from typing import Any


_DECISION_MAKER_KEYWORDS = (
    "practice manager",
    "partner",
    "decision",
    "decision-maker",
    "decision maker",
    "owner",
    "approver",
)

_OUTCOME_POINTS: dict[str, int] = {
    "meeting_booked": 50,
    "pilot_agreed": 60,
    "follow_up_scheduled": 25,
    "not_now": 5,
    "do_not_call": -50,
}


@dataclass(frozen=True)
class Score:
    score: int
    tier: str
    reasons: list[str] = field(default_factory=list)


def tier_for_score(score: int) -> str:
    """Single source of truth for the score -> tier mapping."""
    if score >= 60:
        return "HOT"
    if score >= 30:
        return "WARM"
    if score >= 1:
        return "COLD"
    return "DEAD"


def score_call(call_record: dict[str, Any], transcript: str | None = None) -> Score:
    """Score one call's record with simple deterministic rules."""
    reasons: list[str] = []
    score = 0

    outcome = str(call_record.get("outcome") or "").strip()
    pts = _OUTCOME_POINTS.get(outcome)
    if pts is not None:
        score += pts
        reasons.append(f"outcome {outcome!r}: {pts:+d}")

    if call_record.get("email"):
        score += 20
        reasons.append("email captured: +20")

    duration = int(call_record.get("duration_s") or 0)
    if duration > 60:
        score += 10
        reasons.append(f"duration {duration}s > 60s: +10")

    haystack = " ".join(
        str(v) for v in (call_record.get("summary"), transcript) if v
    ).lower()
    if any(kw in haystack for kw in _DECISION_MAKER_KEYWORDS):
        score += 15
        reasons.append("decision-maker mentioned: +15")

    return Score(score=score, tier=tier_for_score(score), reasons=reasons)
