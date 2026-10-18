"""Text-to-SQL over the four read-only views.

Five intents map NL questions to fixed SELECT templates. On a database
error the planner retries once with a simplified query; if that fails it
raises EscalationNeeded instead of guessing.
"""

from __future__ import annotations

import re
import sqlite3

from . import views

INTENT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("open_incidents_by_severity",
     re.compile(r"open incident|incident.*severity|severity.*incident", re.I)),
    ("sla_breaches",
     re.compile(r"sla|breach|overdue", re.I)),
    ("alarm_backlog",
     re.compile(r"alarm|backlog", re.I)),
    ("tech_utilization",
     re.compile(r"tech|engineer|utilization|on shift|on-shift", re.I)),
    ("correlated_groups",
     re.compile(r"correlat|group", re.I)),
]

TEMPLATES: dict[str, str] = {
    "open_incidents_by_severity": (
        "SELECT severity, COUNT(*) AS n FROM v_open_incidents "
        "GROUP BY severity ORDER BY n DESC"
    ),
    "sla_breaches": (
        "SELECT incident_id, title, severity, sla_target_hours FROM v_sla_status"
    ),
    "alarm_backlog": (
        "SELECT severity, COUNT(*) AS n FROM v_alarm_backlog "
        "GROUP BY severity ORDER BY n DESC"
    ),
    "tech_utilization": (
        "SELECT tech_id, name, current_load FROM v_tech_utilization "
        "WHERE on_shift = 1 ORDER BY current_load DESC"
    ),
    "correlated_groups": (
        "SELECT cause_code, COUNT(*) AS n FROM v_alarm_backlog "
        "GROUP BY cause_code ORDER BY n DESC"
    ),
}

SIMPLIFIED = "SELECT COUNT(*) AS n FROM v_open_incidents"


class EscalationNeeded(Exception):
    """Raised when even the simplified query fails — a human must look."""


def detect_intent(question: str) -> str:
    for name, pattern in INTENT_PATTERNS:
        if pattern.search(question):
            return name
    return "open_incidents_by_severity"


def answer(question: str, conn: sqlite3.Connection) -> dict:
    """Run the intent query; one simplified retry, then escalate."""
    intent = detect_intent(question)
    try:
        cols, rows = views.run_query(conn, TEMPLATES[intent])
        return {"intent": intent, "columns": cols, "rows": rows,
                "repaired": False}
    except (sqlite3.Error, views.GatewayError):
        pass
    try:
        cols, rows = views.run_query(conn, SIMPLIFIED)
        return {"intent": intent, "columns": cols, "rows": rows,
                "repaired": True}
    except (sqlite3.Error, views.GatewayError) as exc:
        raise EscalationNeeded(f"query failed twice: {exc}") from exc
