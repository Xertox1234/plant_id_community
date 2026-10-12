---
status: completed
priority: p4
issue_id: "631"
tags: [garden, forum, celery, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Finding 6 fixed: chunk the garden actor purge. Finding 4 fixed: work around auditlog's time-based set_actor dispatch_uid (e.g. per-request unique uid or contextvar) with a test. Fix the other findings (2026-10-12)"
---

# Follow-ups from PR #1075 (todo 606, garden audit actor, FCM requeue)

## Problem

Todo-sweep run 2026-10-12-0349 merged PR #1075 (todo 606, garden audit actor, FCM requeue). The non-blocking review findings are below.
The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: follow-ups from this run get one extra
sweep pass.

## Findings

PR #1075 (todo sweep run 2026-10-12-0349, group g6, todos 606); follow-ups: verified; 1 item(s) the curator did not return were kept as stored.

1. **medium** `backend/apps/forum_host/tasks.py:380` The follow-up send_forum_push_batch.apply_async(...) is unguarded and runs before the [FCM] credentials ERROR is logged. If the broker is down, the task raises and the ERROR for the stop is lost. The re-enqueue is not on_commit-safe or deduplicated, and its new `requeued` kwarg breaks a rollback. | also: The new `requeued` kwarg is part of the task's message contract; a follow-up queued with a 300s countdown sits in the ETA queue, and a rollback in that window gives the old worker an unexpected kwarg (TypeError), losing the batch silently. | also: The re-enqueue apply_async runs before the single ERROR log; if the broker is down it raises and the credentials-stop ERROR is never emitted, though sends happened. | The requeue apply_async is unguarded before the credentials-failure logger.log; a broker outage skips the error log and leaves untried recipients unaccounted for. | The re-enqueue apply_async runs before the credentials ERROR log. If the broker raises (kombu OperationalError, not the Django one in autoretry_for), the task errors out and the single ERROR naming the failed users and the stop is never logged.
2. **medium** `backend/apps/garden_calendar/tests/test_auditlog_registration.py:313` Actor tests drive only GardenBedViewSet. AuditActorMixin was added to Plant, CareTask, CareLog and Harvest viewsets too; removing it from any of those four leaves the suite green, so their actor writes (and the actor-based purge of their rows) are unpinned. | also: Actor tests drive only GardenBedViewSet. Removing AuditActorMixin from PlantViewSet, CareTaskViewSet, CareLogViewSet or HarvestViewSet leaves the suite green, yet those rows would then keep a NULL actor and escape the account-deletion purge.
3. **medium** `backend/apps/forum_host/tasks.py:382` The new `requeued` kwarg is part of the task's message contract. A follow-up enqueued with a 300s countdown sits in the worker's ETA queue. If the deploy is rolled back inside that window, the old worker gets an unexpected kwarg, raises TypeError, and the follow-up batch is lost silently. | also: The re-enqueue apply_async runs before the single ERROR log. If the broker is down it raises, so the task fails and the credentials-stop ERROR is never emitted, though sends already happened. | The requeue apply_async runs before the credentials-failure logger.log and is not guarded. If the broker is down, the exception skips the [CELERY] error log and fails the task, leaving the untried recipients unaccounted for.
4. **low** `backend/apps/garden_calendar/api/audit_actor.py:33` auditlog 3.4.1 set_actor uses dispatch_uid=('set_actor', time.time()); two threaded requests starting in the same clock tick share one receiver, and the first to exit disconnects it, so the other's later LogEntries get a NULL actor and escape the purge. A rare library race. | also: No test covers the ExitStack cleanup claim (receiver removed when the view raises) or the unauthenticated path (no actor set); only the happy path is pinned.
5. **low** `backend/apps/garden_calendar/tests/test_auditlog_registration.py:88` The item-3 test checks only that the read SQL ends with FOR UPDATE OF caretask. It does not show that a task completed concurrently is left alone, so the docstring claims more than the test proves. reschedule_overdue_tasks has no production caller.
6. **low** `backend/apps/garden_calendar/auditlog.py:176` collect_garden_audit_targets loads every actor-matched LogEntry pk into a Python list, and the purge builds Q(pk__in=acted). For a heavy user this is one very large IN clause inside the delete transaction, and bound-parameter limits can break the account delete. | also: collect_garden_audit_targets materializes every actor-matched LogEntry pk into a Python list; a long-lived heavy user makes the later `pk__in=acted` delete query very large. | The actor-based purge collects every actor LogEntry pk into a Python list and then builds a Q(pk__in=...) on it. A very active user means a large IN clause during account deletion, inside the delete transaction.

8 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- low: backend/apps/garden_calendar/services/care_schedule_service.py:475 The comment says a concurrent complete/skip 'waits for this reschedule', but only this read takes a lock. A completion that read the task before the lock and then does an unlocked full save() would overwrite the new scheduled_date and notes. (fixed on main: On main mark_complete/mark_skip go through CareTask._resolve, which does refresh_from_db(from_queryset=select_for_update()) on every field before saving, so the completion waits for the lock and saves the rescheduled values. The stale-overwrite path does not exist.; the refuter agreed: mark_complete and mark_skip go through CareTask._resolve (models.py:1211). It runs refresh_from_db with select_for_update, which waits for the reschedule's lock and reloads it, then saves update_fields=[changes, updated_at]. It is not an unlocked full save, so it cannot overwrite scheduled_date or notes.)

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1075 review (todo sweep run 2026-10-12-0349)

Filed by the closing step of the run from `state.py followups-md g6`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-1724)

- #1/#3 fixed: the re-enqueue in `send_forum_push_batch` (`backend/apps/forum_host/tasks.py`) is guarded, so a broker error no longer fails the task before the credentials ERROR; that ERROR now says the re-enqueue failed and how many recipients were dropped (test `test_a_re_enqueue_the_broker_refuses_still_logs_the_credentials_error`). Declined: `on_commit` (the task runs in a worker with no enclosing transaction, and the follow-up reads nothing this task writes); dedup (it enqueues once per execution, and nothing after it can retry the task); the `requeued` kwarg (it shipped in #1075, so only a rollback to before #1075 inside a 300 s window is exposed, and moving the flag would break messages already queued with it).
- #4 fixed (owner decision): garden views no longer use auditlog's `set_actor`. `backend/apps/garden_calendar/api/audit_actor.py` keeps the actor in a `ContextVar` and connects one `pre_save` receiver with a fixed uid for the process, so overlapping requests cannot disconnect each other's receiver. New tests cover two overlapping contexts in one clock tick, a view that raises, and an anonymous request.
- #6 fixed (owner decision): the account-deletion purge (`backend/apps/garden_calendar/auditlog.py`) deletes in chunks of `PURGE_CHUNK_SIZE` (500). Actor rows are deleted in `pre_delete`, inside the delete's transaction, instead of a pk list carried to `post_delete`; object rows are chunked in `post_delete`. Test `test_the_purge_deletes_in_chunks_and_misses_nothing`.
- #2 fixed: `test_every_garden_viewset_records_the_user_as_actor` creates a plant, care task, care log and harvest through the API and asserts each CREATE row's actor, and asserts all five viewsets carry the mixin.
- #5 fixed: the lock test's docstring now claims only what it checks (the `FOR UPDATE OF` read). `reschedule_overdue_tasks` still has no production caller; it is kept because four test modules call it.

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-1724)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 5 -- venv/bin/python -m pytest apps/garden_calendar/tests/test_auditlog_registration.py apps/forum_host/tests/test_tasks.py --create-db -v` — evidence `.sweep-evidence/g5/631-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 96 passed, 3 warnings in 22.59s ========================
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-1724)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
