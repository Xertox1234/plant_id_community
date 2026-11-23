---
status: completed
priority: p3
issue_id: "727"
tags: [forum, celery, notifications, performance, launch-readiness]
dependencies: []
triage: ready
triaged: 2026-11-22
owner_decision: "50 recipients per task, ~30 s Firebase httpTimeout (owner 2026-11-22)"
---

# Forum notification fan-out: chunk recipients, size time limits, bound FCM sends

## Problem

The forum batch tasks give one task every follower or watcher, under the global
90 s soft and 120 s hard time limits. Audit 2026-11-21 M3 made a batch stop
cleanly at the soft limit, recording what it sent and releasing the rest. A big
fan-out still needs several reconciliation passes, though, and one FCM send can
outlast the soft limit. Nothing triggers this today: the app is not live and has
one real user. It becomes a problem at launch, once a topic has 100 or more
followers.

## Findings

- Recipient lists are unbounded: `apps/forum_host/notifications.py:306-312, 355-365, 812-821` → `send_forum_{push,web_push,email}_batch` (`tasks.py`). There is no per-task `soft_time_limit`, so each task inherits `CELERY_TASK_SOFT_TIME_LIMIT=90` / `TIME_LIMIT=120` (`settings.py:1512-1515`). Source: audit M3 (celery-async-reviewer).
- `firebase_admin`'s HTTP client defaults to a **120 s** timeout (`firebase_admin/_http_client.py:79`), and `apps/core/firebase_config.py` does not set `httpTimeout`. A single send can therefore run past the soft limit, and no deadline checked between sends can bound it.
- **L7:** `pacing.pace` runs `delivery.claim_related` once per non-coalesced recipient, about 2 queries each (`apps/forum_host/pacing.py:165`, `apps/core/delivery.py:241-260`). A 1,000-follower topic issues about 2,000 queries before its first send, once on each of the three channels.
- **L11:** the pacing reads after `claim_batch` (`pace`, `schedule_fold`) are not guarded. An `OperationalError` there autoretries, the retry finds its own claim, and the run does nothing, so delivery waits for the 15-minute lease to reconcile. Nothing is lost or duplicated. See `tasks.py:820-821` for the invariant this breaks.

## Recommended Action

1. Chunk the recipients at enqueue, for example 50 per task, with a constant in `apps/forum_host/constants.py`. Give each batch task an explicit `soft_time_limit`/`time_limit` sized to one chunk.
2. Initialize the Firebase app with `options={"httpTimeout": <seconds>}`, kept well below the soft limit, as a constant. Check that the token exchange in `apps/users` still works with it.
3. Claim the related rows for every recipient in one UPDATE keyed on `recipient_id__in`, then group in Python (L7).
4. Wrap `pace` and `schedule_fold` in `try/except OperationalError` that releases this run's claim and re-raises, as the care-reminder sweep does (L11).

## Technical Details

- The audit M3 fix is in `tasks.py`: the `time_limit_hit` paths in the push and web-push batches and `except SoftTimeLimitExceeded` in the email batch. The shared senders re-raise the limit (`apps/core/services/email_service.py`, `notification_service.py`, `apps/users/services.py`).
- Rules: `docs/rules/celery.md` ("size a cohort task's limits yourself").

## Acceptance Criteria

- [x] A 120-follower reply enqueues ⌈120/chunk⌉ batches per channel, each with its own declared time limits (a test).
- [x] The Firebase app is initialized with an `httpTimeout` below the soft limit (a test reads the option).
- [x] `pace` issues a constant number of queries whatever the recipient count (a query-count test at 3 and at 30 recipients).
- [x] An `OperationalError` in `pace` after the claim leaves the run's rows pending and unclaimed (a test).

## Work Log

### 2026-11-21 - Filed from the forum backend audit

- Deferred from `docs/audits/2026-11-21-forum-backend.md` M3 (the remainder after the clean-stop fix), L7 and L11. Owner decisions 2026-11-21: at triage, "per-task time limit + re-raise, chunking deferred"; then, offered a push-only split, they chose to fix all three channels now (done in the audit PR). The approved per-task time limit did not ship (it has to be sized to a chunk), so it is in this todo.

### 2026-11-23 - Implemented by the todo sweep (run 2026-11-22-1957)

- Chunking (owner decision 2026-11-22: 50 per task): every batch enqueue in `backend/apps/forum_host/notifications.py` and the re-drive in `backend/apps/forum_host/tasks.py` now sends one task per `NOTIFICATION_BATCH_CHUNK_SIZE` recipients, all under the one outbox batch id. Each chunk's enqueue is guarded on its own. The three batch tasks declare `soft_time_limit` 240 s and `time_limit` 300 s (`backend/apps/forum_host/constants.py`), under the 15-minute claim lease. This replaces the 2026-10-11 "no chunked subtasks" decision for browser push.
- Firebase (owner decision: about 30 s): `firebase_app_options()` in `backend/apps/core/firebase_config.py` sets `httpTimeout` to `FIREBASE_HTTP_TIMEOUT_SECONDS` (30). The projectId-only init in `backend/apps/users/firebase_auth_views.py` passes it too, because the FCM sender adopts whichever default app exists. The users Firebase tests still pass. One existing assertion in `backend/apps/core/tests/test_firebase_config.py` now expects the `options` argument.
- L7: `delivery.claim_related_many` claims every recipient's fold rows in one UPDATE and reads them in one SELECT; `pacing.pace` calls it once for the recipients it will send to now.
- L11: `pacing.pace_claimed` wraps `pace` and `schedule_fold`. On an `OperationalError` it releases the rows this run still owns and re-raises. Rows already suppressed or held are left alone, and fold rows claimed inside `pace` are handed back there.

### 2026-11-23 - Verified by the todo sweep (run 2026-11-22-1957)

- AC 1: `python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest --rootdir backend -c backend/pytest.ini backend/apps/forum_host/tests/test_notification_chunking.py --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g11/727-ac0.txt` (not committed), last lines:

  ```text

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 5 passed, 2 warnings in 21.53s ========================

  exit code: 0
  ```

- AC 2: `python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest --rootdir backend -c backend/pytest.ini backend/apps/core/tests/test_firebase_config.py --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g11/727-ac1.txt` (not committed), last lines:

  ```text

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 6 passed, 2 warnings in 0.30s =========================

  exit code: 0
  ```

- AC 3: `python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest --rootdir backend -c backend/pytest.ini backend/apps/forum_host/tests/test_pacing.py::test_pace_issues_the_same_number_of_queries_at_3_and_at_30_recipients --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g11/727-ac2.txt` (not committed), last lines:

  ```text

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 1 passed, 2 warnings in 20.73s ========================

  exit code: 0
  ```

- AC 4: `python3 scripts/todos/slot_env.py --main-root . 4 -- backend/venv/bin/python -m pytest --rootdir backend -c backend/pytest.ini backend/apps/forum_host/tests/test_pacing.py::test_an_operational_error_in_pace_after_the_claim_leaves_the_rows_pending backend/apps/forum_host/tests/test_pacing.py::test_an_error_while_counting_folds_also_hands_back_the_fold_rows backend/apps/forum_host/tests/test_pacing.py::test_a_row_already_suppressed_is_not_reopened_by_the_release --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g11/727-ac3.txt` (not committed), last lines:

  ```text

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 5 passed, 2 warnings in 20.74s ========================

  exit code: 0
  ```

### 2026-11-23 - Completed by the todo sweep (run 2026-11-22-1957)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

## Notes

- From the close review (manifest Phase 6):
  - **R7:** when the soft limit cuts a member off in the middle of their devices, the row is recorded as sent once one device has the push, and the remaining devices are not tried. Per-device retry would need device-level outbox rows.
  - **R2:** the topic-summary pending lock is now released on terminal exits, so a later poll can start a fresh provider cycle. This is bounded per user by the `topic_summary` throttle and the web's `MAX_POLLS`. A failure-cooldown key separate from the pending lock would keep both properties.
  - **Round 2 residuals** (narrow, no loss):
    - A limit landing inside `finish_folds`, after `mark_suppressed` commits, can release fold rows that were already suppressed.
    - The email loop guards only the send, so a limit elsewhere in an iteration delays later rows to the lease instead of releasing them now.
    - A limit partway through the web-push `finish_folds` loop leaves the remaining folds claimed until the lease.
    - `_track_email_sent`'s re-raise has no dedicated test.
