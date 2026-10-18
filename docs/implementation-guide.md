# Implementation guide

How to adopt the patterns in this repo in a real NOC.

## 1. Replace the telemetry seam
`telcoops/telemetry.py` is the only module that knows about SQLite. Swap
`build_db()` for a read-only connector to your inventory/alarm systems
(keep it read-only: the gateway rules assume the agent cannot write).

## 2. Tune correlation for your network
`CAUSE_AFFINITY` in `correlate.py` encodes which cause codes travel
together. Seed it from your historical tickets: mine six months of
incidents, keep pairs that co-occur, and re-tune `window_minutes` until
the group count matches how your NOC actually works incidents.

## 3. Wire the fiber feed
`fibersignal.LiveFiberFeed` is a stub that returns an explicit gap. A
production adapter implements `fetch(region)` and must return `ok=False`
with a gap explanation on any failure — never synthesized windows.

## 4. Connect the gates to your paging
`ConfirmationGate.request()` takes a `decide` callback. Wire it to your
paging/chat-ops tool so mass-outage declarations and SLA-credit approvals
reach a human with one tap.

## 5. Keep the audit trail
`AuditLog` is in-memory here. Persist entries to append-only storage
(WORM bucket, ledger table) in production; `verify_chain()` works
unchanged.

## 6. Evals before autonomy
Add a golden set of (question, expected intent, expected group) pairs and
gate CI on it. The 44 tests here are regression checks on synthetic data,
not quality claims — say so in your own README too.
