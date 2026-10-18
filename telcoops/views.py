"""Read-only views + SELECT-only SQL gateway.

Rule IDs (cited in code and tests):
- SEC-SELECT-01: only SELECT statements are allowed.
- SEC-SELECT-02: string literals are stripped before the write-keyword scan,
  so keywords inside quotes cannot false-positive.
- SEC-SELECT-03: every query is capped with LIMIT 100.
"""

from __future__ import annotations

import re
import sqlite3

WRITE_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE",
    "TRUNCATE", "GRANT", "REVOKE", "ATTACH", "DETACH",
)

MAX_LIMIT = 100


def create_views(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE VIEW IF NOT EXISTS v_open_incidents AS
        SELECT incident_id, title, severity, status, opened_min
        FROM incidents WHERE status != 'closed';

        CREATE VIEW IF NOT EXISTS v_alarm_backlog AS
        SELECT alarm_id, element_id, severity, cause_code, raised_min,
               CASE WHEN cleared_min IS NULL THEN 1 ELSE 0 END AS is_open
        FROM alarms WHERE cleared_min IS NULL;

        CREATE VIEW IF NOT EXISTS v_tech_utilization AS
        SELECT tech_id, name, skills, home_site, region, on_shift, current_load
        FROM techs;

        CREATE VIEW IF NOT EXISTS v_sla_status AS
        SELECT i.incident_id, i.title, i.severity, i.status, i.opened_min,
               CASE i.severity
                 WHEN 'critical' THEN 4.0 WHEN 'major' THEN 8.0
                 WHEN 'minor' THEN 24.0 ELSE 72.0 END AS sla_target_hours
        FROM incidents i WHERE i.status != 'closed';
        """
    )
    conn.commit()


class GatewayError(ValueError):
    """Raised when a query violates the gateway rules."""


def _strip_literals(sql: str) -> str:
    # SEC-SELECT-02: remove '...' and "..." before scanning for keywords.
    return re.sub(r"'[^']*'|\"[^\"]*\"", " ", sql)


def validate(sql: str) -> str:
    """Validate a query; return a LIMIT-capped version. Raises GatewayError."""
    cleaned = sql.strip().rstrip(";")
    if not re.match(r"(?is)^\s*select\b", cleaned):
        raise GatewayError("SEC-SELECT-01: only SELECT statements are allowed")
    if re.search(r"(?i)\b(" + "|".join(WRITE_KEYWORDS) + r")\b",
                 _strip_literals(cleaned)):
        raise GatewayError("SEC-SELECT-02: write keyword detected")
    if not re.search(r"(?i)\blimit\s+\d+", cleaned):
        cleaned = f"{cleaned} LIMIT {MAX_LIMIT}"  # SEC-SELECT-03
    return cleaned


def run_query(conn: sqlite3.Connection, sql: str):
    """Validate then execute; returns (columns, rows)."""
    safe = validate(sql)
    cur = conn.cursor()
    cur.execute(safe)
    cols = [d[0] for d in cur.description] if cur.description else []
    return cols, cur.fetchall()
