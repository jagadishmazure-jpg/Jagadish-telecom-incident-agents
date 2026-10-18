# Interview points

- **Why correlation is the differentiator.** Alarm storms are the NOC's
  hardest scaling problem; grouping by element/site/cause-affinity/time
  with a transparent explanation is what turns 12 alarms into 1 incident.
- **Gateway design.** SELECT-only with cited rule IDs; string literals are
  stripped *before* the write-keyword scan so `'UPDATE'` in a filter can't
  false-positive — a real bug class, with a regression test.
- **Gap behavior.** The live fiber feed returns an explicit gap instead of
  hallucinating maintenance windows. Never invent external data.
- **PII in feedback.** Free-text corrections are scrubbed (email/phone/SSN)
  *before* storage, and the scrub count is recorded. Storing first and
  scrubbing later is a breach.
- **Human gates.** Mass-outage declarations and SLA credits always need a
  human; the agent drafts, never approves.
- **Determinism.** Seeded telemetry, fixed epochs, sorted outputs — every
  test reproduces exactly, which is why the suite runs in 0.2s.
- **Honest numbers.** 71 tests are regression checks on synthetic data;
  the README says so explicitly.
