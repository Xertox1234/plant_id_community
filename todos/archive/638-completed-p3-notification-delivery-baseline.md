---
status: completed
priority: p3
issue_id: "638"
tags: [notifications, email, observability, operations, owner, prod]
dependencies: []
completed_at: "2026-11-03"
owner_decision: "Record the baseline now from the data that exists; provider delivery outcomes and delivery latency re-pointed to todo 692 (owner approved the read-only aggregate prod read, 2026-11-03)"
---

# Record a controlled delivery test and an initial notification baseline

## Problem

Split from todo 625 at triage (run 2026-10-12-1748, owner decision 2026-10-12). A baseline needs test sends to approved inboxes/devices and aggregate production data over an observation window. Test sends were not approved on 2026-10-12, and the todo engine never reads production data, so this stays with the owner.

## Recommended Action

1. After 619/623/625 land, send each email family to approved test inboxes and a push to an approved test device; record latency and outcomes.
2. Over a stated observation window, record aggregate denominators (eligible, opted-out, unavailable-device, attempted, accepted/delivered), click/action, unsubscribe/complaint rates and reminder lateness, using 623/625's outcome and feedback data. No raw addresses or message bodies.

## Acceptance Criteria

- [x] Controlled test-inbox/device delivery evidence and an initial aggregate baseline are recorded, with observation window, denominators and click/action/unsubscribe outcomes; existing evidence from 547 is reused with its build/date stated. (completed 2026-11-03: `docs/operations/notification-baseline.md` → "Initial baseline")
- [ ] Provider delivery outcomes (delivered/bounced/complained) and delivery latency in the baseline → todo 692 (re-pointed 2026-11-03; the Resend webhook is not configured, so prod has no delivery events to count)

## Work Log

### 2026-10-12 - Split from 625 at triage

- 625 AC4 re-pointed here by owner decision; wording carried over unchanged.

### 2026-11-03 - Baseline recorded; delivery outcomes re-pointed to 692

- Owner approved a read-only, aggregate-only prod read ("approved, record the baseline now"). The owner ran it (`railway ssh … manage.py shell` at 2026-11-03 19:57 UTC; the classifier refused it from the agent). Output: counts only, no addresses or bodies.
- Results and evidence reuse are in `docs/operations/notification-baseline.md` → "Initial baseline (2026-11-03)".
- `RESEND_WEBHOOK_SECRET` is unset, so delivered/bounced/complained and send→delivered latency cannot be measured. Re-pointed to todo 692 with the webhook setup, not ticked here.

## Notes

Owner-only and production-dependent. Needs explicit approval for test sends and any prod data read.
