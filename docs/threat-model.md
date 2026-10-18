# Threat model (STRIDE-lite)

| Threat | Mitigation in this repo |
|---|---|
| **Spoofing** — fake alarms injected into telemetry | Telemetry is read-only and seeded; production must authenticate the alarm source before ingestion. |
| **Tampering** — audit log edited to hide a bad dispatch | Hash-chained log; `verify_chain()` detects any edit (tested). |
| **Repudiation** — "I never approved that outage" | Gate decisions record `decided_by`, timestamp, and reason. |
| **Information disclosure** — PII in feedback text | Scrubbed before storage; redaction count recorded. Error paths never echo row data. |
| **Denial of service** — expensive queries | SELECT-only gateway, 100-row LIMIT cap, literals stripped pre-scan. |
| **Elevation of privilege** — agent writes to network | No write path exists: views are read-only, gateway rejects DDL/DML. |
| Prompt injection via alarm text | Alarms are data, never instructions; the planner matches fixed intent patterns, not free-form LLM output. |

## LLM-specific (OWASP LLM Top 10, where relevant)
- **LLM01 Prompt injection:** N/A in the deterministic core — no model
  inference runs here; when a live model is wired in, treat all telemetry
  as untrusted data.
- **LLM06 Sensitive information disclosure:** feedback PII scrubbing +
  no row data in errors.
- **LLM08 Excessive agency:** confirmation gates on mass-outage and
  SLA-credit actions; least-privilege read-only tools.
