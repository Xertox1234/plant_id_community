---
status: completed
priority: p4
issue_id: "593"
tags: [todos, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "Finding 1: on an FCM credentials error, release the claims and stop the batch so the next sweep retries (owner, 2026-10-11)"
---

# Follow-ups from PR #1034 (todos 566, 570, 573)

## Problem

Todo-sweep run 2026-10-11-1448 merged PR #1034 (care-reminder FCM errors, garden list and log prefixes). Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1034 (todo sweep run 2026-10-11-1448, group g8, todos 566, 570, 573); follow-ups: verified; 1 item(s) the curator did not return were kept as stored.

1. **medium** `backend/apps/garden_calendar/tasks.py:282` A credentials error (SenderIdMismatch/ThirdPartyAuth) is treated as server misconfiguration, but its tasks still take the permanent-failure path: owner added to `done`, claim kept. One bad FIREBASE_CREDENTIALS_B64 deploy drops every reminder due until fixed. | also: A project-wide credentials failure logs one ERROR per owner per sweep. The care sweep and send_forum_push_batch keep sending to every remaining recipient even though they fail identically, which floods the ERROR channel and wastes FCM calls.
2. **low** `backend/apps/garden_calendar/tasks.py:195` When autoretry is still possible, the age-out warning is turned off for every released task. A task within the retry delay of the lookback edge leaves the window before the retry claims it and is dropped with no warning. | also: The `autoretries` guess (OperationalError and retries < max_retries) mirrors the decorator's autoretry config by hand. If autoretry_for or max_retries changes, the age-out warning silently goes wrong. | On an OperationalError with retries left, the age-out warning is turned off for the whole batch. But the autoretry countdown (retry_backoff=60 with jitter, up to 240s on the 3rd try) can pass a task's 24h lookback edge. The retry's new `now` then never re-claims that task, and it is dropped with no warning.
3. **low** `plant_community_mobile/lib/features/garden/garden_screen.dart:295` careTaskTitle measures and cuts in UTF-16 code units; substring can split a surrogate pair at the cut, leaving a lone surrogate (sent as U+FFFD). The server counts code points, so emoji titles are also cut shorter than needed. | also: careTaskTitle cuts the title with String.substring on UTF-16 code units. A long plant name with an emoji or other non-BMP character at position 198/199 can be split mid surrogate pair, which sends a lone surrogate (it becomes U+FFFD or bad text) in the task title. | (garden_screen.dart:258) careTaskTitle truncates by UTF-16 code units. substring can split a surrogate pair (emoji at the cut), leaving a malformed string. The server counts code points, so this is also stricter than needed.
4. **low** `backend/apps/garden_calendar/models.py:1232` refresh_from_db under the lock clears cached relations (e.g. self.plant), so mark_complete/mark_skip may re-query plant for the next-occurrence build, discarding the view's select_related.
5. **low** `backend/apps/garden_calendar/signals.py:153` signals.py still holds a leftover management Command class; it is dead/misplaced code that manage.py never discovers. | also: A management `Command` class still lives in signals.py (pre-existing); the docstring rewrite documents it rather than moving it, so it is dead and never discoverable by manage.py.
6. **low** `plant_community_mobile/lib/features/garden/garden_screen.dart:253` The doc comment on careTaskTitle runs past 80 columns after a mid-edit reflow; dart format will not rewrap comments.
7. **low** `backend/apps/garden_calendar/signals.py:60` logger.exception already appends the traceback and exception; also passing `e` as a %s arg duplicates the message (same at the RSVP, weather and cleanup handlers). | also: logger.exception(..., %s, e) repeats the exception text already included by the traceback; harmless redundancy repeated in four handlers. | logger.exception already appends the traceback and exception; also passing `e` as a %s arg duplicates the message in each of the four converted handlers.
8. **low** `backend/apps/core/fcm.py:52` A token truly belonging to another sender now raises SenderIdMismatchError on every send; it is never cleared and logs ERROR each time, so a stale device token keeps firing alerts. Deliberate trade-off (owner decision, todo 566).
9. **low** `backend/apps/forum_host/tests/test_tasks.py:1021` The test calls cache.delete('wagtail_forum:digest-run:weekly') on the default cache; in dev/sweep runs that is shared Redis, so it can release a digest run lock held by a live local worker.
10. **low** `plant_community_mobile/lib/features/garden/garden_screen.dart:258` careTaskTitle truncates by UTF-16 code units. substring can split a surrogate pair (emoji at the cut), leaving a malformed string. The server counts code points, so this is also stricter than needed.

4 more location(s) were dropped by the cap of 10 (the most severe are kept).

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1448

Follow-ups for PR #1034 (todos 566, 570, 573).

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-2219)

- #1 fixed (owner decision): in `backend/apps/garden_calendar/tasks.py`, a Firebase credentials error releases the failing owner's tasks and every owner's not yet tried, logs one ERROR and stops the sweep; the next sweep retries. `send_forum_push_batch` (`backend/apps/forum_host/tasks.py`) stops at the first credentials error too. Tests in `test_care_reminders.py` and `forum_host/tests/test_tasks.py`.
- #2 fixed: `_next_claim_within()` reads `autoretry_for`, `retry_backoff`, `retry_backoff_max` and `max_retries` from the task itself. The age-out warning now fires for any task that leaves the lookback before the next claim, autoretry or beat sweep, instead of being switched off whenever an autoretry follows.
- #3, #6, #10 fixed: `careTaskTitle` (`plant_community_mobile/lib/features/garden/garden_screen.dart`) counts and cuts in runes (code points, as the server counts), so an emoji at the cut is never split; the doc comment is rewrapped to 80 columns. #4 fixed: `CareTask._resolve` re-attaches cached relations whose key did not change after the lock's `refresh_from_db()`. #5 fixed: the dead `Command` in `signals.py` is now the `deactivate_expired_weather_alerts` management command (smoke test). #9 fixed: the digest relay test runs on a private LocMem cache, not the shared default.
- #7 declined: `test_signals.py` (todo 573) pins the message template ending in `%s` with the exception, so a one-line log view still shows the cause next to the traceback.
- #8 declined: keeping the token on `SenderIdMismatchError` is the owner's todo 566 decision. With #1, a truly device-level mismatch now stops each sweep at that owner; revisit if that is seen in the logs.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-2219)

- AC 1: `bash -c 'set -eo pipefail; cd backend && python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest apps/garden_calendar/tests/test_care_reminders.py apps/garden_calendar/tests/test_signals.py apps/forum_host/tests/test_tasks.py --create-db -q -p no:cacheprovider 2>&1 | tail -n 8; cd plant_community_mobile && flutter test test/features/garden/garden_screen_test.dart 2>&1 | tail -n 4; sed -n "/^## Work Log/,/^## Notes/p" todos/archive/593-completed-p4-garden-care-reminders-pr1034-followups.md'` — evidence `.sweep-evidence/g4/593-ac0.txt` (not committed), last lines:

  ```text
  - #1 fixed (owner decision): in `backend/apps/garden_calendar/tasks.py`, a Firebase credentials error releases the failing owner's tasks and every owner's not yet tried, logs one ERROR and stops the sweep; the next sweep retries. `send_forum_push_batch` (`backend/apps/forum_host/tasks.py`) stops at the first credentials error too. Tests in `test_care_reminders.py` and `forum_host/tests/test_tasks.py`.
  - #2 fixed: `_next_claim_within()` reads `autoretry_for`, `retry_backoff`, `retry_backoff_max` and `max_retries` from the task itself. The age-out warning now fires for any task that leaves the lookback before the next claim, autoretry or beat sweep, instead of being switched off whenever an autoretry follows.
  - #3, #6, #10 fixed: `careTaskTitle` (`plant_community_mobile/lib/features/garden/garden_screen.dart`) counts and cuts in runes (code points, as the server counts), so an emoji at the cut is never split; the doc comment is rewrapped to 80 columns. #4 fixed: `CareTask._resolve` re-attaches cached relations whose key did not change after the lock's `refresh_from_db()`. #5 fixed: the dead `Command` in `signals.py` is now the `deactivate_expired_weather_alerts` management command (smoke test). #9 fixed: the digest relay test runs on a private LocMem cache, not the shared default.
  - #7 declined: `test_signals.py` (todo 573) pins the message template ending in `%s` with the exception, so a one-line log view still shows the cause next to the traceback.
  - #8 declined: keeping the token on `SenderIdMismatchError` is the owner's todo 566 decision. With #1, a truly device-level mismatch now stops each sweep at that owner; revisit if that is seen in the logs.
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-2219)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-11 - Repaired by the todo sweep (run 2026-10-11-2219)

- Round-1 review (high): stopping the care-reminder sweep on the first credentials error let one device-level `SenderIdMismatchError` or APNs-only `ThirdPartyAuthError` on the oldest due task stall every other owner each sweep until their reminders aged out.
- `_push_to_owners` in `backend/apps/garden_calendar/tasks.py` now releases only the failing owner's tasks (token kept, one WARNING) and goes on; it stops and releases everyone not yet tried only after a credentials error on `CARE_REMINDER_CREDENTIALS_STOP_OWNERS` (3, `backend/apps/garden_calendar/constants.py`) distinct owners. Each sweep still logs one ERROR.
- Tests in `backend/apps/garden_calendar/tests/test_care_reminders.py`: a credentials error on the first owner still sends the second; the stop test now uses four owners (three fail, the fourth is never tried), replacing the two-owner version that asserted the old stop-at-first behaviour.

### 2026-10-11 - Round 3 (owner-approved)

- Round-2 review (blocking): (a) the care sweep released the failed owners' tasks, and claims are re-claimed oldest-first, so a few owners whose devices always fail stopped every sweep and starved healthy owners until the lookback; (b) `send_forum_push_batch` broke on the first credentials error and dropped every remaining recipient.
- Owner decision (2026-10-11), applied to both paths: "Stop only when every send so far in the sweep/batch failed with a credentials error (none succeeded), and keep claims on device-level failures."
- `backend/apps/core/fcm.py`: one shared `FCM_CREDENTIALS_STOP_FAILURES = 3` replaces `CARE_REMINDER_CREDENTIALS_STOP_OWNERS` (removed from `backend/apps/garden_calendar/constants.py`).
- `_push_to_owners` (`backend/apps/garden_calendar/tasks.py`): a credentials error leaves that owner's claim standing (token kept, one WARNING) and goes on. The sweep stops only with no successful send and 3 credentials failures; it then releases the untried owners who have a token, and tokenless or opted-out owners keep their claims. The failed owners' claims stand on the stop too, as the code comment explains: released, they would be re-claimed first and stop the next sweep again, so a real outage costs at most 3 owners' reminders per sweep, named in the one ERROR.
- `send_forum_push_batch` (`backend/apps/forum_host/tasks.py`): continues past a credentials error and stops only with no successful send and 3 credentials failures. It logs one ERROR per batch, naming the failed users and, on a stop, the number of recipients not tried. It no longer logs an ERROR per recipient.
- Tests, `backend/apps/garden_calendar/tests/test_care_reminders.py` (`CareReminderCredentialsErrorTest`): a success first, then 4 credentials failures, does not stop and every claim stands. 3 failures at the head with no success stop the sweep: those claims stand, the untried owner with a token is released and the tokenless one keeps her claim. The next sweep moves past the failed owners. A failure on the first owner still sends the second.
- Tests, `backend/apps/forum_host/tests/test_tasks.py`: `test_a_credentials_error_stops_the_batch` became `test_a_credentials_error_on_every_send_stops_the_batch_at_the_threshold`, which stops at 3 of 5 and logs one ERROR with "2 recipient(s) not tried". Its docstring records the owner-approved behaviour change. Also new: the first recipient fails with `ThirdPartyAuthError` and all 4 are sent; a success first, then failures, and all 5 are sent.
- Results: the targeted two files went from 124 collected to 125 passed. `pytest apps/garden_calendar/tests/test_care_reminders.py apps/forum_host/tests/test_tasks.py apps/garden_calendar` gave 316 passed and 1 skipped (`PYTHONPATH=backend/packages/wagtail_forum`, so the worktree's package is imported).
- Mutation checks (files copied aside, restored with `cp`, then grepped):
  - Dropping "no success yet" fails the two after-a-success tests.
  - Releasing failed owners plus break-on-first fails 10.
  - Releasing tokenless untried owners fails the threshold test.
  - After restoring, all pass.
