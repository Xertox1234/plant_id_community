---
status: pending
priority: p3
issue_id: "638"
tags: [notifications, email, observability, operations, owner, prod]
dependencies: []
---

# Record a controlled delivery test and an initial notification baseline

## Problem

Split from todo 625 at triage (run 2026-10-12-1748, owner decision 2026-10-12). A baseline needs test sends to approved inboxes/devices and aggregate production data over an observation window. Test sends were not approved on 2026-10-12, and the todo engine never reads production data, so this stays with the owner.

## Recommended Action

1. After 619/623/625 land, send each email family to approved test inboxes and a push to an approved test device; record latency and outcomes.
2. Over a stated observation window, record aggregate denominators (eligible, opted-out, unavailable-device, attempted, accepted/delivered), click/action, unsubscribe/complaint rates and reminder lateness, using 623/625's outcome and feedback data. No raw addresses or message bodies.

## Acceptance Criteria

- [ ] Controlled test-inbox/device delivery evidence and an initial aggregate baseline are recorded, with observation window, denominators, delivery latency and click/action/unsubscribe outcomes; existing evidence from 547 may be reused with its build/date stated.

## Work Log

### 2026-10-12 - Split from 625 at triage

- 625 AC4 re-pointed here by owner decision; wording carried over unchanged.

## Notes

Owner-only and production-dependent. Needs explicit approval for test sends and any prod data read.
