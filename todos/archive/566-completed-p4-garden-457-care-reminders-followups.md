---
status: completed
priority: p4
issue_id: "566"
tags: [backend, garden-calendar, fcm, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "Recurrence: the next task keeps the completion timestamp, time of day included (reconfirms 2026-10-10); findings 5/9/10 are declined. SenderIdMismatchError: stop clearing the token and log an error, as for ThirdPartyAuthError (2026-10-11)"
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

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1448)

- #1, #4 fixed (owner decision 2026-10-11): `SenderIdMismatchError` no longer clears the token. `backend/apps/core/fcm.py` narrows `is_dead_fcm_token_error` to `UnregisteredError` and adds `is_fcm_credentials_error` (SenderIdMismatch + ThirdPartyAuth); the care sweep and both forum send paths keep the token and log those at ERROR. Tests: `test_a_sender_id_mismatch_keeps_the_token_and_logs_an_error`, `test_a_credentials_error_logs_at_error_level`; the forum `_DEAD_TOKEN_CLASSES` set shrank to match.
- #2, #3 fixed: `test_staff_setting_the_flag_with_the_new_date_keeps_it` pins the `notification_sent not in changed_data` operand, and `test_an_add_is_never_re_armed` pins `change` (each fails with its operand deleted).
- #6 fixed: `_release(..., warn_age_out=False)` when an `OperationalError` will be autoretried (retries left), so the "will not be sent" line no longer fires for a reminder the retry re-claims; tests cover the retry and the last-retry cases. #7 fixed: `test_a_token_reregistered_during_the_sweep_send_is_kept` drives the sweep with the token swapped mid-send.
- #5, #9, #10 declined: the owner decided the next occurrence keeps the completion timestamp, time of day included (owner decision, reconfirmed 2026-10-10).
- #8 declined: `test_the_fcm_wrappers_are_gone` is a cheap structural guard against re-adding the forwarding wrappers todo 457 removed; it pins a decision, not behaviour, and costs nothing to keep.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1448)

- AC 1: `bash -c 'cd backend && python3 scripts/todos/slot_env.py --main-root . 2 -- backend/venv/bin/python -m pytest apps/garden_calendar/tests/test_care_reminders.py apps/garden_calendar/tests/test_admin.py apps/forum_host/tests/test_tasks.py --create-db -q -p no:cacheprovider'` — evidence `.sweep-evidence/g8/566-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 116 passed, 3 warnings in 18.33s =======================
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1448)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
