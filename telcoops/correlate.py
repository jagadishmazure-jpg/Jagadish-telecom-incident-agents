"""Alarm-correlation engine (domain differentiator).

Groups raw alarms into incidents so the NOC triages *incidents*, not an alarm
storm. Two alarms are linked when, within ``window_minutes``:

- they share the same network element, OR
- they share the same site AND their cause codes are affinitive
  (see ``CAUSE_AFFINITY``). Affinity is checked in both directions, so the
  result does not depend on which alarm was raised first.

Connected components become correlation groups. Every group carries a
transparent explanation: which alarms, why they were linked, and the group's
dominant severity. Single isolated alarms are returned as singleton groups so
nothing is silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CAUSE_AFFINITY: dict[str, set[str]] = {
    "LINK-DOWN": {"LINK-DOWN", "PORT-FLAP", "BGP-DOWN"},
    "PORT-FLAP": {"PORT-FLAP", "LINK-DOWN"},
    "BGP-DOWN": {"BGP-DOWN", "LINK-DOWN"},
    "FIBER-CUT": {"FIBER-CUT", "LINK-DOWN", "OPTICAL-LOS"},
    "OPTICAL-LOS": {"OPTICAL-LOS", "FIBER-CUT"},
    "HIGH-CPU": {"HIGH-CPU"},
    "HIGH-TEMP": {"HIGH-TEMP"},
    "RADIO-FAIL": {"RADIO-FAIL"},
}

SEVERITY_RANK = {"warning": 0, "minor": 1, "major": 2, "critical": 3}


@dataclass
class CorrelatedGroup:
    group_id: str
    alarm_ids: list[str]
    element_ids: list[str]
    cause_codes: list[str]
    severity: str  # dominant (max) severity
    explanation: str
    alarm_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.alarm_count = len(self.alarm_ids)


def _affine(x: str, y: str) -> bool:
    """Symmetric cause affinity (the table lists each pair from one side)."""
    return y in CAUSE_AFFINITY.get(x, {x}) or x in CAUSE_AFFINITY.get(y, {y})


def _linked(a: dict, b: dict, window_minutes: int) -> str | None:
    """Return the link reason, or None when the alarms are unrelated."""
    if abs(a["raised_min"] - b["raised_min"]) > window_minutes:
        return None
    if a["element_id"] == b["element_id"]:
        return f"same element {a['element_id']}"
    if a["site_id"] == b["site_id"] and _affine(a["cause_code"], b["cause_code"]):
        return (f"same site {a['site_id']} with affinitive causes "
                f"{a['cause_code']}/{b['cause_code']}")
    return None


def correlate_alarms(alarms: list[dict], window_minutes: int = 15
                     ) -> list[CorrelatedGroup]:
    """Group alarms into correlated incidents. Deterministic."""
    if not alarms:
        return []
    ordered = sorted(alarms, key=lambda a: (a["raised_min"], a["alarm_id"]))
    parent = list(range(len(ordered)))
    reasons: dict[tuple[int, int], str] = {}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(i: int, j: int, reason: str) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)
            reasons[(min(i, j), max(i, j))] = reason

    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            reason = _linked(ordered[i], ordered[j], window_minutes)
            if reason:
                union(i, j, reason)

    buckets: dict[int, list[int]] = {}
    for i in range(len(ordered)):
        buckets.setdefault(find(i), []).append(i)

    groups: list[CorrelatedGroup] = []
    for gid, (root, members) in enumerate(sorted(buckets.items()), start=1):
        members = sorted(members)
        member_alarms = [ordered[i] for i in members]
        why = "; ".join(
            f"{ordered[i]['alarm_id']}~{ordered[j]['alarm_id']} ({reasons[(i, j)]})"
            for (i, j) in sorted(reasons)
            if find(i) == root and find(j) == root
        ) or "singleton: no related alarms in window"
        sev = max((a["severity"] for a in member_alarms),
                  key=lambda s: SEVERITY_RANK[s])
        groups.append(CorrelatedGroup(
            group_id=f"CG-{gid:03d}",
            alarm_ids=[a["alarm_id"] for a in member_alarms],
            element_ids=sorted({a["element_id"] for a in member_alarms}),
            cause_codes=sorted({a["cause_code"] for a in member_alarms}),
            severity=sev,
            explanation=why,
        ))
    return groups
