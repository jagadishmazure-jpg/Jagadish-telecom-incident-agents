# Domain notes: telecom network incident operations

Distilled operational knowledge behind this repo. All vendor, element, and
people names are fictional.

## The alarm-storm problem
A single fiber cut can raise hundreds of alarms in minutes as downstream
elements lose their links. NOC engineers drown in the alarm list while the
actual fault — one cut — sits unidentified. Correlation (grouping alarms by
element, site, cause affinity, and time window) is the standard industry
answer; this repo implements a transparent, rule-based version so every
grouping decision is explainable.

## Severity vs impact
Severity is a property of an alarm; impact is a property of an incident.
A critical alarm on a core router with no customer traffic matters less
than a major alarm on the one OLT serving a hospital district. The
escalation tiers here key off severity *and* scope (alarm count, SLA
breach) for that reason.

## Dispatch economics
A wasted truck roll (wrong skill, wrong site) costs hours. The dispatch
recommender treats the required skill as a hard filter, then trades off
proximity against current load — the same triage a regional dispatcher
does by hand, but scored and auditable.

## SLA clocks
Restoration targets in this repo (critical 4h, major 8h, minor 24h,
warning 72h) mirror common enterprise carrier contracts. The clock starts
at acknowledgement, and credits are a finance decision — the agent drafts,
a human approves.

## Why this is agentic, not a dashboard
A dashboard shows the storm. The agent *works* it: correlates, recommends
a tech, cites the SOP that governs the next step, gates the risky actions,
and writes every decision into a tamper-evident audit trail.
