---
status: pending
priority: p3
issue_id: "727"
tags: [forum, celery, notifications, performance, launch-readiness]
dependencies: []
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

- [ ] A 120-follower reply enqueues ⌈120/chunk⌉ batches per channel, each with its own declared time limits (a test).
- [ ] The Firebase app is initialized with an `httpTimeout` below the soft limit (a test reads the option).
- [ ] `pace` issues a constant number of queries whatever the recipient count (a query-count test at 3 and at 30 recipients).
- [ ] An `OperationalError` in `pace` after the claim leaves the run's rows pending and unclaimed (a test).

## Work Log

### 2026-11-21 - Filed from the forum backend audit

- Deferred from `docs/audits/2026-11-21-forum-backend.md` M3 (the remainder after the clean-stop fix), L7 and L11. The owner approved the M3 split on 2026-11-21: the clean stop now, with chunking and limits deferred.

## Notes

- From the close review (manifest Phase 6):
  - **R7:** when the soft limit cuts a member off in the middle of their devices, the row is recorded as sent once one device has the push, and the remaining devices are not tried. Per-device retry would need device-level outbox rows.
  - **R2:** the topic-summary pending lock is now released on terminal exits, so a later poll can start a fresh provider cycle. This is bounded per user by the `topic_summary` throttle and the web's `MAX_POLLS`. A failure-cooldown key separate from the pending lock would keep both properties.
  - **Round 2 residuals** (narrow, no loss):
    - A limit landing inside `finish_folds`, after `mark_suppressed` commits, can release fold rows that were already suppressed.
    - The email loop guards only the send, so a limit elsewhere in an iteration delays later rows to the lease instead of releasing them now.
    - A limit partway through the web-push `finish_folds` loop leaves the remaining folds claimed until the lease.
    - `_track_email_sent`'s re-raise has no dedicated test.
