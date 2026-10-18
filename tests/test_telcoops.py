"""Tests for telcoops. Deterministic; stdlib + pytest only."""


import pytest

from telcoops import (
    audit,
    correlate,
    demo_helpers,
    dispatch,
    escalation,
    feedback,
    fibersignal,
    orchestrator,
    sop_rag,
    telemetry,
    text2sql,
    views,
)

SOP_DIR = "docs/sops"


@pytest.fixture()
def conn():
    c = telemetry.build_db()
    views.create_views(c)
    yield c
    c.close()


# ---------- telemetry anchors ----------

def test_seed_counts(conn):
    n = conn.execute("SELECT COUNT(*) FROM alarms").fetchone()[0]
    assert n == 9 + 12  # 9 seeded + 12 storm alarms
    assert conn.execute("SELECT COUNT(*) FROM techs").fetchone()[0] == 5


def test_storm_anchor(conn):
    rows = conn.execute(
        "SELECT COUNT(*) FROM alarms WHERE alarm_id LIKE 'ALM-STORM-%'"
    ).fetchone()[0]
    assert rows == 12


def test_sla_breach_anchor(conn):
    row = conn.execute(
        "SELECT incident_id FROM incidents WHERE incident_id='INC-101'"
    ).fetchone()
    assert row is not None


# ---------- gateway ----------

def test_select_allowed(conn):
    cols, rows = views.run_query(conn, "SELECT COUNT(*) FROM v_open_incidents")
    assert rows[0][0] == 4


def test_rejects_non_select(conn):
    with pytest.raises(views.GatewayError):
        views.run_query(conn, "DELETE FROM alarms")


def test_rejects_write_keyword(conn):
    with pytest.raises(views.GatewayError):
        views.run_query(
            conn, "SELECT * FROM alarms; UPDATE alarms SET severity='minor'")


def test_literal_stripping_no_false_positive(conn):
    # "UPDATE" inside a string literal must not trip SEC-SELECT-02.
    cols, rows = views.run_query(
        conn, "SELECT * FROM v_alarm_backlog WHERE cause_code != 'UPDATE'")
    assert isinstance(rows, list)


def test_limit_added(conn):
    q = views.validate("SELECT * FROM v_open_incidents")
    assert "LIMIT 100" in q.upper()


# ---------- text2sql ----------

def test_intent_detection():
    assert text2sql.detect_intent("show open incidents by severity") == \
        "open_incidents_by_severity"
    assert text2sql.detect_intent("any SLA breaches?") == "sla_breaches"
    assert text2sql.detect_intent("alarm backlog") == "alarm_backlog"
    assert text2sql.detect_intent("tech utilization") == "tech_utilization"


def test_answer_rows(conn):
    r = text2sql.answer("alarm backlog", conn)
    assert r["columns"] and r["rows"]
    assert not r["repaired"]


def test_retry_then_escalate(conn):
    conn.execute("DROP VIEW v_open_incidents")
    with pytest.raises(text2sql.EscalationNeeded):
        text2sql.answer("open incidents", conn)


# ---------- correlation engine ----------

def _alarms(conn):
    cols, rows = views.run_query(
        conn, "SELECT a.alarm_id, a.element_id, a.site_id, a.severity, "
              "a.cause_code, a.raised_min FROM v_open_alarm_sites a")
    keys = ["alarm_id", "element_id", "site_id", "severity", "cause_code",
            "raised_min"]
    return [dict(zip(keys, r)) for r in rows]


def test_storm_correlates_into_one_group(conn):
    groups = correlate.correlate_alarms(_alarms(conn))
    storm = [g for g in groups if g.alarm_count >= 10]
    assert len(storm) == 1
    assert storm[0].severity == "critical"
    assert storm[0].element_ids == ["NE-CORE-01"]


def test_group_explanation_names_reason(conn):
    groups = correlate.correlate_alarms(_alarms(conn))
    storm = next(g for g in groups if g.alarm_count >= 10)
    assert "same element NE-CORE-01" in storm.explanation


def test_singletons_not_dropped(conn):
    groups = correlate.correlate_alarms(_alarms(conn))
    total = sum(g.alarm_count for g in groups)
    assert total == len(_alarms(conn))


def test_affinitive_causes_link_across_elements():
    alarms = [
        {"alarm_id": "A1", "element_id": "NE-1", "site_id": "S1",
         "severity": "major", "cause_code": "LINK-DOWN", "raised_min": 0},
        {"alarm_id": "A2", "element_id": "NE-2", "site_id": "S1",
         "severity": "major", "cause_code": "BGP-DOWN", "raised_min": 5},
        {"alarm_id": "A3", "element_id": "NE-9", "site_id": "S9",
         "severity": "minor", "cause_code": "HIGH-CPU", "raised_min": 6},
    ]
    groups = correlate.correlate_alarms(alarms)
    sizes = sorted(g.alarm_count for g in groups)
    assert sizes == [1, 2]


def test_window_boundary():
    a = {"alarm_id": "A1", "element_id": "NE-1", "site_id": "S1",
         "severity": "major", "cause_code": "LINK-DOWN", "raised_min": 0}
    b = dict(a, alarm_id="A2", raised_min=16)
    assert len(correlate.correlate_alarms([a, b], window_minutes=15)) == 2
    b2 = dict(a, alarm_id="A2", raised_min=15)
    assert len(correlate.correlate_alarms([a, b2], window_minutes=15)) == 1


def test_correlation_deterministic(conn):
    g1 = correlate.correlate_alarms(_alarms(conn))
    g2 = correlate.correlate_alarms(_alarms(conn))
    assert [(g.group_id, g.alarm_ids) for g in g1] == \
           [(g.group_id, g.alarm_ids) for g in g2]


# ---------- dispatch ----------

def _techs(conn):
    cols, rows = views.run_query(
        conn, "SELECT tech_id, name, skills, home_site, region, on_shift, "
              "current_load FROM v_tech_utilization")
    keys = ["tech_id", "name", "skills", "home_site", "region", "on_shift",
            "current_load"]
    return [dict(zip(keys, r)) for r in rows]


def test_dispatch_skill_filter(conn):
    recs = dispatch.recommend_techs("SITE-NORTH", "fiber-splicing",
                                    _techs(conn))
    assert recs  # at least one skilled, on-shift tech
    assert all("fiber-splicing" in r.explanation for r in recs)


def test_dispatch_off_shift_excluded(conn):
    # TECH-005 has fiber-splicing but is off shift.
    recs = dispatch.recommend_techs("SITE-WEST", "fiber-splicing",
                                    _techs(conn))
    assert all(r.tech_id != "TECH-005" for r in recs)


def test_dispatch_ranking_explained(conn):
    recs = dispatch.recommend_techs("SITE-WEST", "fiber-splicing",
                                    _techs(conn), top_n=3)
    scores = [r.score for r in recs]
    assert scores == sorted(scores, reverse=True)
    assert recs[0].explanation and recs[0].distance_km >= 0


def test_dispatch_no_skill_no_results(conn):
    assert dispatch.recommend_techs("SITE-NORTH", "quantum-welding",
                                   _techs(conn)) == []


def test_site_distance_symmetric():
    assert dispatch.site_distance("SITE-NORTH", "SITE-EAST") == \
        dispatch.site_distance("SITE-EAST", "SITE-NORTH")
    assert dispatch.site_distance("SITE-NORTH", "SITE-NORTH") == 0.0


# ---------- fiber feed ----------

def test_fake_feed_region_filter():
    fr = fibersignal.FakeFiberFeed().fetch("NORTH")
    assert fr.ok and all(w.region == "NORTH" for w in fr.windows)
    assert fibersignal.FakeFiberFeed().fetch("SOUTH").windows == []


def test_live_feed_gap():
    fr = fibersignal.LiveFiberFeed().fetch("NORTH")
    assert not fr.ok and fr.gap and fr.windows == []


# ---------- SOP RAG ----------

def test_rag_citation():
    r = sop_rag.SopRetriever(SOP_DIR)
    hits = r.retrieve("how do I declare a mass outage")
    assert hits and hits[0].citation.startswith("sop-")
    assert "§" in hits[0].citation


def test_rag_not_found():
    r = sop_rag.SopRetriever(SOP_DIR)
    assert r.retrieve("quantum cryptography policy") == []


def test_rag_chunks_have_sections():
    chunks = sop_rag.load_chunks(SOP_DIR)
    assert len(chunks) >= 8
    assert all(c["section"] for c in chunks)


# ---------- escalation ----------

def test_tiers():
    assert escalation.tier_for("warning") == "T1"
    assert escalation.tier_for("major") == "T2"
    assert escalation.tier_for("critical") == "T3"
    assert escalation.tier_for("major", alarm_count=12) == "T4"
    assert escalation.tier_for("minor", sla_breached=True) == "T3"


def test_gate_grant_deny():
    g = escalation.ConfirmationGate()
    d = g.request("declare_mass_outage", "12 alarms on NE-CORE-01",
                  decide="granted")
    assert d.decision == "granted" and g.is_granted("declare_mass_outage")
    g2 = escalation.ConfirmationGate()
    g2.request("approve_sla_credit", "INC-101", decide="denied")
    assert not g2.is_granted("approve_sla_credit")


def test_gate_rejects_unknown_action():
    g = escalation.ConfirmationGate()
    with pytest.raises(ValueError):
        g.request("reboot_everything", "x")


# ---------- audit ----------

def test_chain_verifies():
    log = audit.AuditLog()
    log.record("answer", {"q": "x"})
    log.record("correlate", {"groups": 3})
    assert log.verify_chain()


def test_tamper_detected():
    log = audit.AuditLog()
    log.record("answer", {"q": "x"})
    log.entries[0].details["q"] = "tampered"
    assert not log.verify_chain()


# ---------- feedback + PII ----------

def test_scrub_pii():
    text, n = feedback.scrub_pii(
        "call me at joe@example.com or 555-123-4567, ssn 123-45-6789")
    assert n == 3
    assert "[EMAIL]" in text and "[PHONE]" in text and "[SSN]" in text
    assert "joe@example.com" not in text


def test_feedback_validates():
    log = audit.AuditLog()
    with pytest.raises(feedback.FeedbackError):
        feedback.capture_feedback("", "t1", "up", "", log)
    with pytest.raises(feedback.FeedbackError):
        feedback.capture_feedback("s1", "t1", "meh", "", log)
    with pytest.raises(feedback.FeedbackError):
        feedback.capture_feedback("s1", "t1", "down", "   ", log)


def test_feedback_scrubbed_in_chain():
    log = audit.AuditLog()
    rec = feedback.capture_feedback(
        "s1", "t1", "down",
        "wrong dispatch, call ops@example.com", log)
    assert rec.redactions == 1
    assert "ops@example.com" not in rec.correction
    assert log.verify_chain()
    assert len(feedback.list_feedback(log)) == 1


# ---------- orchestrator ----------

def test_orchestrator_fanout(conn):
    orch = orchestrator.Orchestrator(conn, SOP_DIR)
    r = orch.handle("Correlate the alarm storm and show the SOP for it")
    assert "correlate" in r["answer"] and "sop_rag" in r["answer"]
    assert r["citations"]


def test_orchestrator_audited(conn):
    orch = orchestrator.Orchestrator(conn, SOP_DIR)
    orch.handle("open incidents by severity")
    assert orch.audit.verify_chain()


# ---------- demo helpers ----------

def test_demo_correlation():
    d = demo_helpers.demo_correlation()
    assert d["storm_alarms"] >= 10
    assert d["storm_severity"] == "critical"


def test_demo_dispatch():
    d = demo_helpers.demo_dispatch()
    assert d["tech_id"].startswith("TECH-")
    assert d["score"] > 0


def test_demo_questions():
    qs = demo_helpers.demo_questions()
    assert len(qs) >= 3 and all(isinstance(q, str) and q for q in qs)


def test_correlate_empty():
    assert correlate.correlate_alarms([]) == []


def test_dispatch_top_n(conn):
    recs = dispatch.recommend_techs("SITE-NORTH", "fiber-splicing",
                                    _techs(conn), top_n=1)
    assert len(recs) == 1


def test_feedback_thumbs_up_ok():
    log = audit.AuditLog()
    rec = feedback.capture_feedback("s1", "t1", "up", "", log)
    assert rec.rating == "up" and rec.redactions == 0


def test_text2sql_default_intent():
    assert text2sql.detect_intent("blargh nothing matches") == \
        "open_incidents_by_severity"


# ---------- review fixes (grokbot-portfolio, 2026-10-18) ----------

def _pair(first, second):
    base = {"site_id": "SITE-NORTH", "severity": "major"}
    return [dict(base, alarm_id="A1", raised_min=0, element_id="RTR-1", cause_code=first),
            dict(base, alarm_id="A2", raised_min=3, element_id="OLT-9", cause_code=second)]


def test_affinity_does_not_depend_on_arrival_order():
    from telcoops.correlate import correlate_alarms
    assert len(correlate_alarms(_pair("FIBER-CUT", "LINK-DOWN"))) == 1
    assert len(correlate_alarms(_pair("LINK-DOWN", "FIBER-CUT"))) == 1
    assert len(correlate_alarms(_pair("LINK-DOWN", "HIGH-CPU"))) == 2


def test_scrub_parenthesised_phone():
    from telcoops.feedback import scrub_pii
    text, n = scrub_pii("customer (555) 123-4567 called")
    assert "555" not in text and n == 1
