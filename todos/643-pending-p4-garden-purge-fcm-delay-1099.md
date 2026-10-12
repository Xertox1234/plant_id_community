---
status: pending
priority: p4
issue_id: "643"
tags: [garden, forum, celery, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
---

# Follow-ups from PR #1099 (todo 631, garden actor, FCM requeue)

## Problem

Todo-sweep run 2026-10-12-1724 merged PR #1099 (todo 631, garden actor, FCM requeue). The non-blocking review findings are
below. The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: these follow-ups are the end state of the
one extra pass, so this todo is filed, not swept.

## Findings

PR #1099 (todo sweep run 2026-10-12-1724, group g5, todos 631); follow-ups: verified.

1. **low** `backend/apps/forum_host/tasks.py:372` The guard covers only the re-enqueue. A transient send in the same loop still calls send_forum_push.delay() unguarded, so a broker outage raises kombu OperationalError mid-batch before the credentials ERROR is logged, the failure todo 631 #1 fixed for apply_async. Pre-existing. | also: The re-enqueue is now guarded against a broker refusal, but the transient-path send_forum_push.delay inside the same loop is not. During a broker outage it raises kombu OperationalError mid-batch: the rest of the batch is never tried and the single credentials ERROR is never logged, the same failure todo 631 #1 fixed for apply_async.
2. **low** `backend/apps/forum_host/tasks.py:391` The re-enqueue failure note interpolates str(exc) from a broker exception into the ERROR log. A kombu/broker error message can carry connection detail (host, URL fragments), which then reaches logs and Sentry. | also: The re-enqueue failure note interpolates str(exc) from a broker exception into the ERROR log, and the broad `except Exception` has no logger-prefix context. A broker error message could carry a connection URL. | The re-enqueue failure note interpolates str(exc) from a broker exception into the ERROR log. Kombu/redis messages can include host/URL details, which may reach Sentry.
3. **low** `backend/apps/forum_host/tasks.py:389` A failed re-enqueue (broker refusal) drops the untried recipients permanently; the stop is only noted in the ERROR line and nothing hands the batch back. Acceptable since counted and logged, but no retry of the enqueue is attempted.
4. **low** `backend/apps/garden_calendar/auditlog.py:157` _delete_in_chunks re-runs values_list['pk'](:500) with LogEntry's default ordering ['-timestamp'], so each chunk re-sorts all remaining matching rows: about N^2/500 rows sorted, inside the account-delete transaction.
5. **low** `backend/apps/garden_calendar/tests/test_auditlog_registration.py:470` The test patches time.time, but nothing it runs reads the clock any more (garden_audit_actor is a ContextVar), and it calls garden_audit_actor directly, so it would still pass if AuditActorMixin went back to auditlog's set_actor.
6. **low** `backend/apps/garden_calendar/tests/test_auditlog_registration.py:599` Chunking test is weakly discriminating: the sql.count(',') <= 1 check reads only DELETEs, which _delete_in_chunks caps anyway, and >= 6 deletes passes from actor-row chunks alone, so removing the per-slice object_pk__in split would go undetected. | also: The chunking test cannot detect removal of the per-slice object_pk__in split in purge_garden_audit_entries: its comma check reads only DELETE statements, and _delete_in_chunks already caps those at 2 pks. The SELECT holding the unbounded IN is never checked.

5 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- low: backend/apps/garden_calendar/auditlog.py:196 Actor-row purge moved to pre_delete. A cascade-aborted user delete still rolls back with the transaction, but a non-atomic caller of delete would lose rows early. Only the happy path has a test. (refuted: Django's Collector.delete sends pre_delete inside transaction.atomic(savepoint=False), and pre_delete receivers disable the fast-delete path. Every delete is atomic, so no caller can be non-atomic around the purge; ProtectedError is raised in collect(), before pre_delete.)

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1099 review (todo sweep run 2026-10-12-1724)

Filed by the closing step of the run from `state.py followups-md g5`.
