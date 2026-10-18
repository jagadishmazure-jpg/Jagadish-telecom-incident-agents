"""Demo helpers (stdlib only). Imported lazily by demo/app.py so the package
never requires streamlit."""

from __future__ import annotations

import sqlite3

from . import correlate, dispatch, telemetry
from .orchestrator import _load_alarms, _load_techs  # noqa: F401  (test seam)
from .views import create_views


def build_demo_db() -> sqlite3.Connection:
    conn = telemetry.build_db()
    create_views(conn)
    return conn


def demo_correlation() -> dict:
    """Run the correlation engine on the seeded storm; return a summary."""
    conn = build_demo_db()
    groups = correlate.correlate_alarms(_load_alarms(conn))
    storm = [g for g in groups if g.alarm_count >= 10]
    return {
        "group_count": len(groups),
        "storm_group": storm[0].group_id if storm else None,
        "storm_alarms": storm[0].alarm_count if storm else 0,
        "storm_severity": storm[0].severity if storm else None,
    }


def demo_dispatch() -> dict:
    """Recommend a fiber-splicing tech for SITE-WEST."""
    conn = build_demo_db()
    recs = dispatch.recommend_techs("SITE-WEST", "fiber-splicing",
                                    _load_techs(conn))
    top = recs[0]
    return {"tech_id": top.tech_id, "score": top.score,
            "explanation": top.explanation}


def demo_questions() -> list[str]:
    return [
        "Which open incidents are at SLA risk?",
        "Correlate the alarm storm on NE-CORE-01",
        "Dispatch a fiber tech to the west region",
        "What does the SOP say about declaring a mass outage?",
    ]
