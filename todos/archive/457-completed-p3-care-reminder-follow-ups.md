---
status: completed
priority: p3
issue_id: "457"
tags: [backend, garden_calendar, celery, notifications]
dependencies: ["410"]
triage: ready
triaged: 2026-10-10
owner_decision: "Item 1: date the next occurrence from max(scheduled_date, completed_at). Item 3: clear dead FCM tokens in both the care sweep and the forum push (2026-10-10)"
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

- [x] Items 1–7 and 9–12 are fixed with tests, or each is closed with a recorded reason.
- [x] Item 8 is handled in todo 386. Link it there.

## Work Log

### 2026-09-27 - Filed from the PR #853 round-1 review

### 2026-09-27 - Round-2 notes added (PR #853 verification)

- **9. CareTaskAdmin does not re-arm on reschedule.** Staff can edit
  `scheduled_date` without clearing `notification_sent`. Override
  `save_model` to clear it when the date changes.
- **10. GardenBedAdmin allows an owner change that diverges a bed's plants.**
  Nothing leaks, because reads filter on the owner, but the old owner's
  PATCH on such a plant fails with a generic 400. Make the owner read-only on
  change, or refuse the change.
- **11. The soft limit can fire after a send returns but before the owner is
  recorded as done.** That owner is then released and pushed a second time.
  The window is a few bytecodes wide.
- **12. Unfiltered reads with no caller.** `GardenBed.plant_count`'s
  non-annotated fallback and `companion_planting_service`'s bed reads do not
  filter on the owner. Filter them, or delete the dead service.

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-11-0053)

- Items 1, 2, 9, 10, 12: `CareTask._create_next_occurrence` dates the next task from
  max(`scheduled_date`, `completed_at`), and checks the end date against that date (owner
  decision). The bed cap excludes the plant by pk and counts only the bed owner's plants.
  `CareTaskAdmin.save_model` clears `notification_sent` when staff move the date.
  `GardenBedAdmin` makes `owner` read-only on change. `GardenBed.plant_count`'s fallback and
  both bed reads in `companion_planting_service` filter on the bed owner. The service is kept,
  because tests call it.
- Item 3 (owner decision: both paths): `backend/apps/core/fcm.py` adds `is_dead_fcm_token_error` and
  `clear_dead_fcm_token`. They run in the care sweep, `send_forum_push` and
  `send_forum_push_batch`. Only `UnregisteredError` and `SenderIdMismatchError` clear a token.
  `ThirdPartyAuthError` (APNs credentials) and `InvalidArgumentError` (a bad message) are
  permanent too, but the token is fine, so clearing on them would wipe healthy devices. The
  clear matches on the failed token, so a device that re-registered in the meantime keeps its
  new one.
- Items 4, 5, 6, 7: the sweep is `bind=True` and logs `task=<id>`. When a released task will
  leave the lookback before the next sweep, it logs a warning (new
  `CARE_REMINDER_SWEEP_INTERVAL_MINUTES`, pinned to the crontab by a test). The
  `retry_backoff=60` countdowns (60/120/240) are pinned with `push_request`. The
  `_send_fcm_message` and `_is_permanent_fcm_error` wrappers are gone, and
  `test_notification_preferences.py` now patches `apps.core.fcm.send_fcm_message`.
- Item 11 closed without a code change. The soft-limit signal can land between any two
  bytecodes, so Python cannot close the window between a send returning and the owner being
  marked done. Moving the mark earlier only trades a duplicate for a lost reminder. The care
  collapse key makes the rare duplicate replace the tray entry rather than stack.
- Item 8 is already linked in todo 386: its criterion "`GardenPlant.gardenBed` is nullable ...
  (todo 457 item 8)".

### 2026-10-10 - Verified by the todo sweep (run 2026-10-11-0053)

- AC 1: `cd backend && python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest backend/apps/garden_calendar/tests/test_care_reminders.py backend/apps/garden_calendar/tests/test_admin.py backend/apps/forum_host/tests/test_tasks.py backend/apps/forum_host/tests/test_notification_preferences.py --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g4/457-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ============= 106 passed, 3 warnings, 6 subtests passed in 19.07s ==============
  ```

- AC 2: `grep -n -B1 "todo 457 item 8" todos/386-pending-p3-mobile-garden-and-care-are-hollow.md` — evidence `.sweep-evidence/g4/457-ac1.txt` (not committed), last lines:

  ```text
  69-- [ ] `GardenPlant.gardenBed` is nullable: the API returns `null` for a
  70:      bedless plant (todo 457 item 8).
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-11-0053)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
