"""T1–T4 escalation tiers + confirmation gates.

- T1: informational (single minor/warning alarm).
- T2: NOC action (major alarm or correlated group, no customer impact yet).
- T3: major incident bridge (critical alarm, SLA at-risk, confirmed impact).
- T4: mass outage (multi-element critical storm, regional impact).

ConfirmationGate: mass-outage declarations and SLA-credit approvals always
require an explicit human decision (grant/deny/timeout).
"""

from __future__ import annotations

from dataclasses import dataclass

TIERS = ("T1", "T2", "T3", "T4")

GATED_ACTIONS = {
    "declare_mass_outage",
    "approve_sla_credit",
}


def tier_for(severity: str, alarm_count: int = 1,
             sla_breached: bool = False) -> str:
    if alarm_count >= 10 or severity == "mass-outage":
        return "T4"
    if severity == "critical" or sla_breached:
        return "T3"
    if severity == "major":
        return "T2"
    return "T1"


@dataclass
class GateDecision:
    action: str
    decision: str  # granted | denied | timeout
    decided_by: str = ""
    reason: str = ""


class ConfirmationGate:
    """Human-in-the-loop gate. ``decide`` is injected by the caller."""

    def __init__(self) -> None:
        self.log: list[GateDecision] = []

    def request(self, action: str, context: str,
                decide: str = "timeout",
                decided_by: str = "on-call", reason: str = "") -> GateDecision:
        if action not in GATED_ACTIONS:
            raise ValueError(f"action '{action}' is not a gated action")
        if decide not in ("granted", "denied", "timeout"):
            raise ValueError(f"bad decision '{decide}'")
        d = GateDecision(action=action, decision=decide,
                         decided_by=decided_by,
                         reason=reason or context)
        self.log.append(d)
        return d

    def is_granted(self, action: str) -> bool:
        return any(d.action == action and d.decision == "granted"
                   for d in self.log)
