---
status: pending
priority: p3
issue_id: "410"
tags: [backend, mobile, web, users, notifications]
dependencies: []
source_review: "todos/archive/405-completed-p3-backend-endpoints-no-client-triage.md"
source_finding: "owner decision 2026-09-23"
---

# Wire up plant care reminders (users `me/care-reminders/*`)

## Problem

`users.CareReminder` and `CareReminderLog` sit behind six `me/care-reminders/*`
routes, about 570 LOC in `apps/users/views.py`. They are dead end to end:

- rows are created only through this API, which no client calls;
- no Celery beat task sends the reminders (beat schedules only the forum
  digest);
- `CareReminderService` has no other caller.

The owner decided (todo 405) to wire this up. It fits a houseplant app.

## Findings

Evidence is recorded in todo 405's 2026-09-23 Work Log. It came from a
`get_resolver()` route walk, client greps, and an adversarial verifier that ran
the endpoints against a test DB.

## Recommended Action

1. Decide whether reminders are scheduled by Celery beat (a periodic "due
   reminders" task) or by per-reminder ETA tasks.
2. Choose delivery: FCM push (the mobile bootstrap is `apps/core/firebase_config.py`)
   and/or email.
3. Build the UI on mobile (todo 386's care hub) and/or web (My Plants).
4. Cover the dead path with tests before relying on it.

## Technical Details

See the file references above, and todo 405's Work Log.

## Acceptance Criteria

- [ ] A reminder created in a client fires a notification when it falls due. Verify end to end.
- [ ] The views have tests; today there are none.

## Work Log

### 2026-09-23 - Filed from todo 405

The owner decided, during the endpoint triage, to wire this up rather than
remove it.
