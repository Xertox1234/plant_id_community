---
status: completed
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

- [ ] A reminder created in a client fires a notification when it falls due → todo 386 (re-pointed 2026-09-27)
      No client creates CareTasks yet. The mobile garden (386) is that client,
      and 386 now carries this end-to-end check.
- [x] The views have tests; today there are none. (completed 2026-09-27)
      The dead `me/care-reminders/*` views were deleted (slice B, removal pinned
      by `apps/users/tests/test_care_reminders_removed.py`). The reminder path
      that replaced them has 23 tests in
      `apps/garden_calendar/tests/test_care_reminders.py` (slice A, #853).

## Work Log

### 2026-09-23 - Filed from todo 405

The owner decided, during the endpoint triage, to wire this up rather than
remove it.

### 2026-09-24 - Owner decisions: Celery beat + FCM push (gate removed)

Decided by the owner:

- **Scheduling:** a periodic Celery beat task finds due reminders (not
  per-reminder ETA tasks). The worker already runs in prod (todo 335).
- **Delivery:** FCM push only (the live mobile path, `apps/core/firebase_config.py`).
  No email.
- **UI:** mobile care hub (todo 386) and/or web My Plants, as the sweep sees
  fit; the backend + beat task + push are the core of this todo.
Ready for a sweep.

### 2026-09-26 - Owner decision: one reminder model, garden_calendar (supersedes "wire up users me/care-reminders")

Two reminder systems exist, and neither fit the 2026-09-24 decisions as
written:

- `users.CareReminder` has a required FK to
  `plant_identification.SavedCareInstructions`. No client can create one of
  those.
- `garden_calendar.CareTask` hangs off `Plant`, which has a required
  `garden_bed` FK. Todo 386 ruled beds out.

The owner chose **garden_calendar only**:

- **Houseplants without beds.** Add a direct `Plant.owner` FK, backfilled from
  `garden_bed.owner`. Make `Plant.garden_bed` nullable. Re-scope every
  queryset, permission and serializer check that goes through
  `garden_bed__owner` (about 8 sites in `garden_calendar/api/views.py`,
  `api/serializers.py` and `permissions.py`, plus the admin search field) to
  the plant's owner.
- **Reminders are CareTask due dates.** `CareTask` already has
  `scheduled_date`, `is_recurring` and `recurrence_interval_days`. The
  periodic Celery beat task finds due, incomplete CareTasks and sends FCM
  push. Delivery stays FCM only.
- **Delete `users.CareReminder`, `CareReminderLog` and the six
  `me/care-reminders/*` routes.** Survey and remove what references them:
  `plant_identification/services/plant_care_reminder_service.py`, the
  care-reminder rows and preferences in `apps/core` (`models.py`,
  `services/email_service.py`), the users services, and
  `OnboardingProgress.first_care_reminder_created`, which todo 412 re-points
  to "first care task".
- Order: todo 412 goes first, since both edit `users/views.py` and
  `users/services.py`.

### 2026-09-26 - Note from todo 412: no care step in the onboarding checklist

Todo 412 shipped the checklist with `identify_plant`, `forum_post` and
`save_topic`. It dropped `first_care_reminder_created` instead of
re-pointing it, because the mobile garden (todo 386) does not exist yet.
Once 386 ships care tasks, a "first care task" step can be added to
`apps/users/onboarding.CHECKLIST_STEPS`, derived from `CareTask.created_by`.

### 2026-09-27 - Owner decisions (bed delete, backlog) and the slice split

Decided by the owner:

- **Deleting a bed keeps its plants.** `Plant.garden_bed` is `SET_NULL`, so
  the plants stay the owner's, bedless.
- **The reminder sweep looks back 24 hours.** Only tasks that fell due in the
  last 24 hours push. An older overdue task never pushes, but still shows as
  overdue in the app. The migration also stamps tasks that were already
  overdue at deploy as notified.

Split into two PRs:

- **Slice A (garden_calendar):** `Plant.owner` plus the backfill, an optional
  `garden_bed`, every ownership check re-scoped to the owner, and the
  15-minute beat sweep `send_due_care_task_reminders` (FCM only; the opt-out
  is `User.care_reminder_notifications`). The FCM helpers moved to
  `apps/core/fcm.py`. Care-log and harvest creation now refuse another user's
  plant; they had no check.
- **Slice B (delete the old model):** `users.CareReminder`,
  `CareReminderLog`, the six `me/care-reminders/*` routes,
  `plant_care_reminder_service`, `core.PlantCareReminder` and the email
  preference. Starts after #851 (412) and #852 (413) merge, since both edit
  `users/services.py` and `users/views.py`.

AC 1 ("a reminder created in a client fires") needs a client that creates
CareTasks. That client is todo 386's mobile garden, which is built on slice
A. Until then the push has no tap destination (the mobile router ignores a
payload without `topic_id`), so 386 adds the `care_task_due` route.

### 2026-09-27 - Completed: slice A (#853) and slice B

- **Slice A, PR #853 (merged).** `Plant.owner`, optional `garden_bed`
  (`SET_NULL`), all 17 ownership sites re-scoped, and the 15-minute FCM
  sweep `send_due_care_task_reminders` (24-hour lookback, claim with
  `skip_locked`, un-claim on any escape). Two review rounds. The
  non-blocking findings are todo 457.
- **Slice B (this PR).** Deleted `users.CareReminder`, `CareReminderLog`,
  the six routes, `core.PlantCareReminder`, `plant_care_reminder_service`,
  the email type, template and preference. The full backend suite passed:
  4114.
- AC 1 (end to end from a client) moves to todo 386, which builds the
  first client that creates CareTasks.
