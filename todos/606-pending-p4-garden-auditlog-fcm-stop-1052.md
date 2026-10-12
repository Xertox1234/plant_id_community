---
status: pending
priority: p4
issue_id: "606"
tags: [backend, garden, fcm, privacy, follow-ups]
dependencies: []
---

# Follow-ups from PR #1052 (todos 586 and 593, garden audit-log purge and FCM credentials stop)

## Problem

Todo-sweep run 2026-10-11-2219 merged PR #1052 (todos 586 and 593, garden audit-log purge and FCM credentials stop). The non-blocking review findings are below. The curator merged duplicates and checked each item against main, and the refuter dismissed what is listed as dropped. An item the curator did not return was kept as stored, unchecked. Line numbers are as of the PR head, so re-check each against main before acting on it.

Two items need the owner's eye. **Item 1**: the forum push batch drops untried recipients on a credentials stop with no re-enqueue (the care sweep releases its claims; the forum batch has nothing to release). **Item 2**: the account-deletion purge (owner decision 'Purge rows', 2026-10-11) misses rows for garden objects the user deleted before the account, so a username can outlive the account in GardenBed's object_repr. #1052 needed an owner-approved round 3. The cap of 10 left out 29 more locations, among them the forum batch's unordered profiles queryset and its overstated `unsent_on_stop` count.

## Findings

PR #1052 (todo sweep run 2026-10-11-2219, group g4, todos 586, 593); follow-ups: verified; 1 item(s) the curator did not return were kept as stored.

1. **medium** `backend/apps/forum_host/tasks.py:322` send_forum_push_batch breaks on a credentials-class error and never sends or re-enqueues the remaining recipients. If the first recipients have stale cross-project tokens or hit an APNs-only fault, later recipients lose the push, Android ones included, since profiles are unordered. | also: On the stop path the batch breaks and the untried recipients are never sent or re-enqueued. ThirdPartyAuthError is an APNs (iOS-only) fault, and profiles have no order_by, so 3 iOS recipients tried first silently drop every Android recipient's push, though those sends would have worked. | The forum batch breaks on the FIRST credentials error. The garden sweep needs 3 distinct owners because one bad device token (SenderIdMismatch from a dev build) is per device. Here one such recipient drops every later recipient's push, with no retry or re-enqueue. | unsent_on_stop = len(profiles) - index - 1 counts every remaining profile, including opted-out, event-muted and tokenless ones that would never have been sent. The ERROR's 'N recipient(s) not tried' overstates the loss. | A credentials error is logged by _permanent_failure_level (probably ERROR) and again by the new logger.error before the break. That is two ERROR lines for one event. | On a credentials error the batch breaks and the remaining recipients are dropped without any retry hand-off, so those pushes are lost. This is logged, but unlike the care-reminder path nothing re-queues them.
2. **medium** `backend/apps/garden_calendar/auditlog.py:173` The account-deletion purge only finds garden rows that still exist at deletion. A bed, plant, task, log or harvest the user deleted earlier keeps its LogEntry rows forever, and a GardenBed object_repr carries the username. That contradicts the docstring and the owner decision. | also: The purge targets only garden objects that still exist when the account is deleted. A bed, plant or task the user deleted earlier keeps its CREATE/UPDATE/DELETE LogEntry rows forever, and GardenBed's object_repr carries the username. That breaks the docstring's claim that these rows 'live only as long as the account'.
3. **medium** `backend/apps/garden_calendar/services/care_schedule_service.py:484` reschedule_overdue_tasks reads overdue tasks into a list, then saves each one with no select_for_update. A task completed or skipped between the read and its save is still rescheduled, its notes are overwritten and notification_sent is reset. The old filtered update() was atomic. | also: Replacing one atomic filtered UPDATE with list() then per-row save() opens a race. A task completed or skipped between the read and the save is rescheduled and its notes overwritten, since the completed=False filter no longer applies at write time. | The reschedule now reads every overdue task into a list and saves each from that stale read, with no select_for_update. A task completed or skipped between the read and its save is still moved to tomorrow, with notification_sent reset. The old filtered update() was atomic.
4. **medium** `backend/apps/garden_calendar/tests/test_auditlog_registration.py:581` The purge test fixture puts created_by=user and CareLog.user=user only on the owner's own plant. Dropping the Q(created_by=user) or Q(user=user) operand from _garden_objects_of would still pass; only the plant__owner operand is covered.
5. **medium** `backend/apps/garden_calendar/tasks.py:547` Claims run oldest-first and released tasks are re-claimed every sweep. So 3 owners with a lasting credentials error at the head of the batch (APNs misconfig on iOS, dev-build tokens) stop every sweep and release later owners, starving Android and healthy owners until the head tasks age out of the 24h lookback.

29 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- medium: backend/apps/garden_calendar/tasks.py:300 The care sweep stops on SenderIdMismatchError or ThirdPartyAuthError, and either can come from one token or from iOS only. Claims run oldest-first and released tasks are re-claimed, so a few bad owners at the head can block every owner's reminders until the 24h lookback ages them out. (fixed on main: On main a credentials-error owner goes into done (its claim stands, so it is not re-claimed first). The sweep stops only after FCM_CREDENTIALS_STOP_FAILURES failures with no successful send, and it releases only untried owners, so the next sweep moves past the bad owners.; the refuter agreed: On main a credentials-error owner goes into done, so its notification_sent=True claim stands and the oldest-first claim does not pick it up again. The stop releases only untried owners that have a token, so the next sweep moves past the bad head.)

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1052 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g4`.
