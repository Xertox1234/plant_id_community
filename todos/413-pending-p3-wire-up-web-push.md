---
status: pending
priority: p3
issue_id: "413"
tags: [backend, web, notifications]
dependencies: []
source_review: "todos/405-pending-p3-backend-endpoints-no-client-triage.md"
source_finding: "owner decision 2026-09-23"
---

# Wire up browser (web) push notifications (`me/push-notifications/*`)

## Problem

`me/push-notifications/*` (3 routes) stores `PushSubscription` rows, but
`pywebpush` is not in `requirements.txt`. `users/services.py:14-60` degrades to
a no-op, so nothing can ever send. Mobile push is FCM and works separately. The
owner decided (todo 405) to wire web push up.

## Findings

Evidence is recorded in todo 405's 2026-09-23 Work Log. It came from a
`get_resolver()` route walk, client greps, and an adversarial verifier that ran
the endpoints against a test DB.

## Recommended Action

1. Add `pywebpush`, run a dependency audit, and generate VAPID keys (Railway
   secrets; never commit them).
2. Add a service worker and a permission prompt on the web, and subscribe via
   the endpoint.
3. Send forum notifications (the same events as FCM) to web subscribers.

## Technical Details

See the file references above, and todo 405's Work Log.

## Acceptance Criteria

- [ ] A subscribed browser receives a forum notification. Record the date and what was observed.
- [ ] The VAPID private key lives only in Railway and `.env`.

## Work Log

### 2026-09-23 - Filed from todo 405

The owner decided, during the endpoint triage, to wire this up rather than
remove it.
