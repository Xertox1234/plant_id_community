---
status: pending
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

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1075 review (todo sweep run 2026-10-12-0349)

Filed by the closing step of the run from `state.py followups-md g6`.
