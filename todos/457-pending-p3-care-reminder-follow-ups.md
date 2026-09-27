---
status: pending
priority: p3
issue_id: "457"
tags: [backend, garden_calendar, celery, notifications]
dependencies: ["410"]
---

# Care reminder follow-ups (PR #853 review, todo 410 slice A)

## Problem

Round 1 of the PR #853 review (bundled `/code-review`, django-drf and
celery-async reviewers) raised these. None is blocking, so none was fixed in
that PR.

1. **A late completion can skip the next reminder.** `CareTask._create_next_occurrence`
   dates the next task from the old `scheduled_date`. A weekly task completed
   9 days late creates a next occurrence already 2 days overdue, outside the
   24-hour lookback, so it never pushes. A habitually late user stops getting
   reminders for that series. Date the next one from the later of
   `scheduled_date` and `completed_at`, or re-arm it within the window.
2. **The bed cap is miscounted when a plant moves beds.**
   `PlantCreateUpdateSerializer.validate` subtracts 1 on every update, even
   when the plant is moving INTO this bed. Bedless plants make moves common.
   A full bed can end up with MAX+1 plants. This was already true before #853.
3. **A dead FCM token is never cleared.** A permanent `UnregisteredError`
   is only logged, and every later sweep that claims that user's tasks sends
   to the dead token again. Clear `ForumProfile.fcm_token` on a permanent
   error, as the forum push should too.
4. **A reminder that keeps failing is dropped silently.** A task released
   after a transient failure is re-claimed every 15 minutes until it leaves
   the 24-hour lookback, then it is never selected again, with no log saying
   it went unsent. Log a warning when a released task is about to age out.
5. **No task id in the sweep's logs.** `send_due_care_task_reminders` is not
   `bind=True`, so its logs carry no request id. The sibling FCM tasks log
   `self.request.id`.
6. **The autoretry countdown is not pinned.** No test pins
   `retry_backoff=60` for `OperationalError`. Use `push_request(retries=N)`
   and a mocked `retry()` (docs/rules/celery.md).
7. **`forum_host.tasks` keeps two one-line wrappers**
   (`_is_permanent_fcm_error`, `_send_fcm_message`) that exist only because
   tests patch those names. Point the tests at `apps.core.fcm` and drop the
   wrappers.
8. **The mobile model can't parse a bedless plant.** `garden_plant.dart`
   casts `json['garden_bed'] as String`, but the API now returns null for a
   bedless plant. Todo 386 must make the field nullable when it wires this
   model up.

## Acceptance Criteria

- [ ] Items 1–7 are fixed with tests, or each is closed with a recorded reason.
- [ ] Item 8 is handled in todo 386. Link it there.

## Work Log

### 2026-09-27 - Filed from the PR #853 round-1 review
