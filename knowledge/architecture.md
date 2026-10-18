# Architecture

```mermaid
flowchart LR
    U[User question] --> O[Orchestrator<br/>ReAct planner]
    O --> T[text2sql<br/>5 intents, SELECT-only gateway]
    O --> C[correlate<br/>alarm-correlation engine]
    O --> D[dispatch<br/>tech recommender]
    O --> R[sop_rag<br/>TF-IDF + citations]
    O --> F[fibersignal<br/>fake / live-gap]
    T --> DB[(SQLite telemetry<br/>4 read-only views)]
    C --> DB
    D --> DB
    O --> E[escalation<br/>T1–T4 + confirmation gates]
    O --> A[audit<br/>hash-chained log]
    FB[feedback<br/>PII-scrubbed] --> A
    E --> H{Human approval<br/>mass outage / SLA credit}
```

## Data flow
1. The orchestrator fans a question out to the matching tools.
2. `text2sql` answers governed questions over four read-only views; the
   gateway enforces SELECT-only with cited rule IDs.
3. `correlate` groups open alarms into incidents with a transparent
   explanation per group.
4. `dispatch` ranks on-shift, skilled techs by proximity and load.
5. `sop_rag` grounds procedural answers in the four SOPs with citations.
6. `fibersignal` adds third-party maintenance context, or an explicit gap.
7. T1–T4 tiers route the answer; gated actions wait for a human.
8. Every step lands in the hash-chained audit log, including user feedback.
