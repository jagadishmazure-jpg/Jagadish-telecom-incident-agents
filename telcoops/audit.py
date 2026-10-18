"""Hash-chained audit log.

Every entry commits to the previous entry's hash, so tampering with any
record breaks ``verify_chain()``. Used for all agent actions, gate
decisions, and user feedback.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class AuditEntry:
    seq: int
    action: str
    details: dict
    actor: str = "agent"
    timestamp: str = field(default_factory=_utcnow)
    prev_hash: str = ""
    entry_hash: str = ""

    def compute_hash(self) -> str:
        payload = json.dumps(
            {"seq": self.seq, "action": self.action, "details": self.details,
             "actor": self.actor, "timestamp": self.timestamp,
             "prev_hash": self.prev_hash},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()


class AuditLog:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def record(self, action: str, details: dict | None = None,
               actor: str = "agent") -> AuditEntry:
        prev = self.entries[-1].entry_hash if self.entries else "GENESIS"
        entry = AuditEntry(seq=len(self.entries) + 1, action=action,
                           details=details or {}, actor=actor, prev_hash=prev)
        entry.entry_hash = entry.compute_hash()
        self.entries.append(entry)
        return entry

    def verify_chain(self) -> bool:
        prev = "GENESIS"
        for e in self.entries:
            if e.prev_hash != prev:
                return False
            if e.entry_hash != e.compute_hash():
                return False
            prev = e.entry_hash
        return True
