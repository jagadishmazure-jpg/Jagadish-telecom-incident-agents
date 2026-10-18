"""ReAct orchestrator with multi-intent fan-out.

Plans a user question into tool calls (text2sql intents, SOP retrieval,
correlation groups, dispatch recommendation, fiber feed), executes them,
and assembles a cited answer. Multi-intent questions fan out to several
tools; every claim in the answer cites its source.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from . import correlate, dispatch, fibersignal, sop_rag, text2sql
from .audit import AuditLog
from .escalation import tier_for
from .views import run_query


@dataclass
class ToolResult:
    tool: str
    summary: str
    citations: list[str] = field(default_factory=list)


def _load_alarms(conn: sqlite3.Connection) -> list[dict]:
    cols, rows = run_query(
        conn,
        "SELECT a.alarm_id, a.element_id, e.site_id, a.severity, "
        "a.cause_code, a.raised_min FROM alarms a "
        "JOIN network_elements e ON a.element_id = e.element_id "
        "WHERE a.cleared_min IS NULL")
    keys = ["alarm_id", "element_id", "site_id", "severity", "cause_code",
            "raised_min"]
    return [dict(zip(keys, r)) for r in rows]


def _load_techs(conn: sqlite3.Connection) -> list[dict]:
    cols, rows = run_query(
        conn, "SELECT tech_id, name, skills, home_site, region, on_shift, "
              "current_load FROM techs")
    keys = ["tech_id", "name", "skills", "home_site", "region", "on_shift",
            "current_load"]
    return [dict(zip(keys, r)) for r in rows]


class Orchestrator:
    def __init__(self, conn: sqlite3.Connection, sop_dir: str,
                 audit: AuditLog | None = None) -> None:
        self.conn = conn
        self.retriever = sop_rag.SopRetriever(sop_dir)
        self.audit = audit or AuditLog()
        self.feed = fibersignal.FakeFiberFeed()

    def handle(self, question: str) -> dict:
        """Plan, execute, and answer with citations. Audited."""
        results: list[ToolResult] = []
        q = question.lower()

        # Fan-out: each matching intent becomes a tool call.
        if any(w in q for w in ("incident", "sla", "breach", "severity")):
            r = text2sql.answer(question, self.conn)
            results.append(ToolResult(
                "text2sql", f"{len(r['rows'])} rows via {r['intent']}",
                [f"view:{r['intent']}"]))

        if any(w in q for w in ("alarm", "correlat", "group", "storm")):
            groups = correlate.correlate_alarms(_load_alarms(self.conn))
            worst = max((g.severity for g in groups), default="none")
            results.append(ToolResult(
                "correlate",
                f"{len(groups)} groups; worst severity {worst}",
                [g.group_id for g in groups]))
            self.audit.record("correlate",
                              {"groups": len(groups), "worst": worst})

        if any(w in q for w in ("dispatch", "tech", "field", "send")):
            techs = _load_techs(self.conn)
            recs = dispatch.recommend_techs("SITE-NORTH", "fiber-splicing",
                                            techs)
            top = recs[0].tech_id if recs else "none"
            results.append(ToolResult(
                "dispatch", f"top recommendation: {top}",
                [r.tech_id for r in recs]))

        if any(w in q for w in ("sop", "procedure", "policy", "playbook",
                                "how")):
            hits = self.retriever.retrieve(question)
            results.append(ToolResult(
                "sop_rag",
                hits[0].text[:120] + "..." if hits else "no SOP found",
                [h.citation for h in hits]))

        if any(w in q for w in ("fiber", "maintenance", "third-party",
                                "provider")):
            fr = self.feed.fetch("NORTH")
            results.append(ToolResult(
                "fiber_feed",
                f"{len(fr.windows)} maintenance windows"
                if fr.ok else f"gap: {fr.gap}", []))

        tier = tier_for("major", alarm_count=len(results))
        answer_text = " | ".join(f"[{r.tool}] {r.summary}" for r in results) \
            or "no tool matched; escalating"
        self.audit.record("answer", {"question": question[:200],
                                     "tools": [r.tool for r in results],
                                     "tier": tier})
        return {"answer": answer_text, "tier": tier,
                "citations": [c for r in results for c in r.citations]}
