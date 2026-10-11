---
status: pending
priority: p4
issue_id: "566"
tags: [backend, garden-calendar, fcm, follow-ups]
dependencies: []
---

# Follow-ups from PR #1002 (todo 457, care-reminder follow-ups)

## Problem

Todo-sweep run 2026-10-11-0053 merged PR #1002. Its two review rounds reported the non-blocking
findings below. The curator merged duplicates and confirmed each item is still on main; the refuter dismissed none.
Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1002 (todo sweep run 2026-10-11-0053, group g4, todos 457); follow-ups: verified; 4 item(s) the curator did not return were kept as stored.

1. **medium** `backend/apps/core/fcm.py:48` is_dead_fcm_token_error treats SenderIdMismatchError as a dead token. That error usually means the server's Firebase credentials belong to another project, so one bad FIREBASE_CREDENTIALS_B64 deploy would wipe every user's fcm_token. The app re-registers only on login or launch. | also: SenderIdMismatchError clears the token, but it usually means the server's Firebase credentials belong to another project. A wrong FIREBASE_CREDENTIALS_B64 would wipe every pushed user's healthy token, the same project-wide failure the PR gives as its reason to spare ThirdPartyAuthError. Mobile only re-PATCHes on login or relaunch. (fcm.py:50)
2. **medium** `backend/apps/garden_calendar/admin.py:600` The save_model guard has three operands (change, scheduled_date changed, notification_sent not changed). The tests cover only the date-moved and date-kept cases, so dropping the 'notification_sent not in changed_data' operand, or `change`, would still pass. The staff override is not pinned. | also: test_admin.py:699 The save_model guard has an `and notification_sent not in form.changed_data` arm no test covers. Deleting it (always re-arm on date change) still passes both tests, so the staff override is unpinned.
3. **medium** `backend/apps/garden_calendar/tests/test_admin.py:699` The save_model guard has an `and notification_sent not in form.changed_data` arm no test covers. Deleting it (always re-arm on date change) still passes both tests, so the staff override is unpinned.
4. **medium** `backend/apps/core/fcm.py:50` SenderIdMismatchError clears the token, but it usually means the server's Firebase credentials belong to another project. A wrong FIREBASE_CREDENTIALS_B64 would wipe every pushed user's healthy token, the same project-wide failure the PR gives as its reason to spare ThirdPartyAuthError. Mobile only re-PATCHes on login or relaunch.
5. **low** `backend/apps/garden_calendar/models.py:1207` _create_next_occurrence dates the next task from completed_at when it is later than the due date, time of day included. Any late completion, even by minutes, shifts the series, and the reminder moves to whenever the user tapped done (e.g. 23:40 instead of 09:00). The drift adds up with each cycle. | also: A late completion now dates the next occurrence from completed_at, including its time of day. A task due at 09:00 and completed at 23:40 next fires its reminder at 23:40, and the time drifts on every late completion. This follows the owner decision but may not be intended. | models.py:1208 Dating the next occurrence from completed_at also takes the completion's time of day. A 09:00 watering completed late at 23:30 recurs at 23:30, so its push reminder now fires at night. | models.py:1200 Next recurrence is dated from completed_at, which carries the completion time of day, so a recurring task's schedule time drifts to whenever the user completed a late task.
6. **low** `backend/apps/garden_calendar/tasks.py:183` The age-out warning also fires on the BaseException release path. An OperationalError there triggers autoretry, which re-claims the tasks about 60s later, so the log can say a reminder 'will not be sent' when it will be. That makes the new signal noisy.
7. **low** `backend/apps/garden_calendar/tests/test_care_reminders.py:583` test_a_token_reregistered_since_the_send_is_kept calls clear_dead_fcm_token directly with a different token and never drives the sweep. The care path's token-matching clear during a send is not exercised; the forum test covers only its own path.
8. **low** `backend/apps/forum_host/tests/test_tasks.py:254` test_the_fcm_wrappers_are_gone asserts only that the_send_fcm_message and _is_permanent_fcm_error attributes are absent. It pins no behaviour and fails only if someone re-adds a wrapper, so it is a tombstone test. | also: test_the_fcm_wrappers_are_gone only asserts that attributes are absent. It pins no behaviour and fails only if someone re-adds a wrapper.
9. **low** `backend/apps/garden_calendar/models.py:1208` Dating the next occurrence from completed_at also takes the completion's time of day. A 09:00 watering completed late at 23:30 recurs at 23:30, so its push reminder now fires at night.
10. **low** `backend/apps/garden_calendar/models.py:1200` Next recurrence is dated from completed_at, which carries the completion time of day, so a recurring task's schedule time drifts to whenever the user completed a late task.

5 more location(s) were dropped by the cap of 10 (the most severe are kept).

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log
