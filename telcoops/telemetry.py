"""Synthetic NOC telemetry on SQLite.

All data is fictional and deterministic (seeded). Times are minutes relative
to ``BASE_EPOCH`` so every run produces identical rows.

Tables:
- network_elements(element_id, element_type, site_id, region)
- alarms(alarm_id, element_id, severity, cause_code, raised_min, cleared_min, source)
- incidents(incident_id, title, severity, status, opened_min, alarm_ids)
- techs(tech_id, name, skills, home_site, region, on_shift, current_load)
"""

from __future__ import annotations

import sqlite3

BASE_EPOCH = 1_700_000_000  # fixed anchor; raised_min/cleared_min are offsets

SEED_ELEMENTS = [
    # element_id, type, site, region
    ("NE-CORE-01", "core-router", "SITE-NORTH", "NORTH"),
    ("NE-CORE-02", "core-router", "SITE-NORTH", "NORTH"),
    ("NE-AGG-11", "aggregation-switch", "SITE-NORTH", "NORTH"),
    ("NE-OLT-21", "olt", "SITE-EAST", "EAST"),
    ("NE-OLT-22", "olt", "SITE-EAST", "EAST"),
    ("NE-DWDM-31", "dwdm", "SITE-WEST", "WEST"),
    ("NE-CELL-41", "cell-site", "SITE-SOUTH", "SOUTH"),
    ("NE-CELL-42", "cell-site", "SITE-SOUTH", "SOUTH"),
]

SEED_TECHS = [
    # tech_id, name, skills, home_site, region, on_shift, load
    ("TECH-001", "A. Rao", "fiber-splicing,optical-testing", "SITE-NORTH", "NORTH", 1, 0.2),
    ("TECH-002", "B. Iyer", "ip-routing,bgp", "SITE-NORTH", "NORTH", 1, 0.6),
    ("TECH-003", "C. Nair", "fiber-splicing", "SITE-EAST", "EAST", 1, 0.8),
    ("TECH-004", "D. Menon", "radio-rf,cell-site", "SITE-SOUTH", "SOUTH", 1, 0.3),
    ("TECH-005", "E. Kumar", "ip-routing,fiber-splicing", "SITE-WEST", "WEST", 0, 0.0),
]

# Anchor: an alarm storm — 12 LINK-DOWN alarms on NE-CORE-01 inside 10 minutes.
STORM_ALARMS = [
    ("ALM-STORM-%02d" % i, "NE-CORE-01", "critical", "LINK-DOWN", 5 + i, None, "ems")
    for i in range(1, 13)
]

SEED_ALARMS = [
    # alarm_id, element_id, severity, cause_code, raised_min, cleared_min, source
    ("ALM-0001", "NE-OLT-21", "major", "PORT-FLAP", 30, 90, "ems"),
    ("ALM-0002", "NE-OLT-21", "major", "PORT-FLAP", 42, None, "ems"),
    ("ALM-0003", "NE-OLT-22", "minor", "HIGH-CPU", 60, 120, "ems"),
    ("ALM-0004", "NE-DWDM-31", "critical", "FIBER-CUT", 75, None, "field-report"),
    ("ALM-0005", "NE-CELL-41", "warning", "HIGH-TEMP", 100, 160, "ems"),
    ("ALM-0006", "NE-CORE-02", "major", "BGP-DOWN", 130, None, "ems"),
    ("ALM-0007", "NE-AGG-11", "minor", "LINK-DOWN", 200, 260, "ems"),
    ("ALM-0008", "NE-CELL-42", "major", "RADIO-FAIL", 300, None, "ems"),
    # SLA-breach anchor: critical incident open far past its target.
    ("ALM-0009", "NE-DWDM-31", "critical", "FIBER-CUT", 10, None, "field-report"),
] + STORM_ALARMS

SEED_INCIDENTS = [
    # incident_id, title, severity, status, opened_min, alarm_ids (csv)
    ("INC-101", "Fiber cut on west ring", "critical", "open",
     10, "ALM-0009,ALM-0004"),
    ("INC-102", "OLT-21 port flapping", "major", "open",
     30, "ALM-0001,ALM-0002"),
    ("INC-103", "BGP session down core-02", "major", "acknowledged",
     130, "ALM-0006"),
    ("INC-104", "Cell-42 radio failure", "major", "open",
     300, "ALM-0008"),
]

SLA_TARGETS_HOURS = {"critical": 4.0, "major": 8.0, "minor": 24.0, "warning": 72.0}


def build_db(path: str = ":memory:") -> sqlite3.Connection:
    """Create and seed the telemetry database. Deterministic."""
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE network_elements(
            element_id TEXT PRIMARY KEY, element_type TEXT, site_id TEXT, region TEXT);
        CREATE TABLE alarms(
            alarm_id TEXT PRIMARY KEY, element_id TEXT, severity TEXT,
            cause_code TEXT, raised_min INTEGER, cleared_min INTEGER, source TEXT);
        CREATE TABLE incidents(
            incident_id TEXT PRIMARY KEY, title TEXT, severity TEXT,
            status TEXT, opened_min INTEGER, alarm_ids TEXT);
        CREATE TABLE techs(
            tech_id TEXT PRIMARY KEY, name TEXT, skills TEXT, home_site TEXT,
            region TEXT, on_shift INTEGER, current_load REAL);
        """
    )
    cur.executemany(
        "INSERT INTO network_elements VALUES (?,?,?,?)", SEED_ELEMENTS)
    cur.executemany(
        "INSERT INTO alarms VALUES (?,?,?,?,?,?,?)", SEED_ALARMS)
    cur.executemany(
        "INSERT INTO incidents VALUES (?,?,?,?,?,?)", SEED_INCIDENTS)
    cur.executemany(
        "INSERT INTO techs VALUES (?,?,?,?,?,?,?)", SEED_TECHS)
    conn.commit()
    return conn
