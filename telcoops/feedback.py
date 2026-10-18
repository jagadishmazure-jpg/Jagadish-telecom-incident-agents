"""User feedback capture with PII scrubbing.

Thumbs up/down plus free-text corrections, written into the audit chain so
feedback is tamper-evident. Free text is scrubbed for personal data BEFORE
storage (emails, phone-like digit runs, SSN patterns) — never store raw PII.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .audit import AuditLog

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE_RE = re.compile(r"(?<!\w)(?:\+?1[-.\s]?)?(?:\(\d{3}\)\s?|\d{3}[-.\s]?)\d{3}[-.\s]?\d{4}\b")


def scrub_pii(text: str) -> tuple[str, int]:
    """Redact PII patterns. Returns (scrubbed_text, redaction_count)."""
    count = 0

    def _sub(pattern: re.Pattern, repl: str, s: str) -> str:
        nonlocal count
        s, n = pattern.subn(repl, s)
        count += n
        return s

    text = _sub(EMAIL_RE, "[EMAIL]", text)
    text = _sub(SSN_RE, "[SSN]", text)
    text = _sub(PHONE_RE, "[PHONE]", text)
    return text, count


class FeedbackError(ValueError):
    """Raised for malformed feedback (empty correction, bad rating, ...)."""


@dataclass
class FeedbackRecord:
    session_id: str
    turn_id: str
    rating: str  # "up" | "down"
    correction: str
    redactions: int


def capture_feedback(session_id: str, turn_id: str, rating: str,
                     correction: str, audit: AuditLog) -> FeedbackRecord:
    """Validate, scrub, and append feedback to the audit chain."""
    if not session_id or not str(session_id).strip():
        raise FeedbackError("session_id must be non-blank")
    if not turn_id or not str(turn_id).strip():
        raise FeedbackError("turn_id must be non-blank")
    if rating not in ("up", "down"):
        raise FeedbackError("rating must be 'up' or 'down'")
    correction = (correction or "").strip()
    if rating == "down" and not correction:
        raise FeedbackError("thumbs-down requires a non-blank correction")
    scrubbed, n = scrub_pii(correction)
    record = FeedbackRecord(session_id=session_id, turn_id=turn_id,
                            rating=rating, correction=scrubbed,
                            redactions=n)
    audit.record("user_feedback",
                 {"session_id": session_id, "turn_id": turn_id,
                  "rating": rating, "correction": scrubbed,
                  "redactions": n},
                 actor="user")
    return record


def list_feedback(audit: AuditLog) -> list[dict]:
    """Return the feedback entries already in the audit chain."""
    return [e.details for e in audit.entries if e.action == "user_feedback"]
