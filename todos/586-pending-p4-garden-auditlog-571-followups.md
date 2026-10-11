---
status: pending
priority: p4
issue_id: "586"
tags: [backend, garden-calendar, auditlog, privacy, follow-ups]
dependencies: []
---

# Follow-ups from PR #1025 (todo 571, garden auditlog registration)

## Problem

Todo-sweep run 2026-10-11-1434 merged PR #1025 (the garden auditlog registration). Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before acting on it.

The owner deferred LogEntry purge on account deletion when scoping todo 571 (2026-10-11). Items 1, 7, 9 and 10 are that gap: garden LogEntry rows, including object_repr with the owner's username and plant names, outlive the data and the account. Decide purge vs anonymise before shipping anything that relies on erasure being complete.

## Findings

PR #1025 (todo sweep run 2026-10-11-1434, group g4, todos 571); follow-ups: verified; 4 item(s) the curator did not return were kept as stored.

1. **medium** `backend/apps/garden_calendar/auditlog.py:24` With registration on, garden deletes, including cascades from user.delete(), write DELETE LogEntry rows. These keep old include_fields values (common_name, variety, bed name) and an object_repr that carries the owner's username. No code purges LogEntry, and no follow-up todo for the purge exists. | also: auditlog.py:17 - deleting garden data writes DELETE LogEntry rows that outlive it. No purge exists, and the owner-deferred follow-up has no todo yet. | auditlog.py:15 - audited GardenBed/Plant/Harvest rows hold user data in LogEntry with no purge on account deletion. The follow-up is acknowledged only in a docstring, so the GDPR erasure gap remains.
2. **low** `backend/apps/garden_calendar/auditlog.py:11` The docstring says only include_fields reach a LogEntry. But auditlog also stores object_repr=str(instance), which include_fields does not filter. GardenBed.**str** includes owner.username, and the Plant/CareTask/CareLog/Harvest reprs include the plant common_name or bed name. Every garden write therefore stores these indefinitely. | also: auditlog.py:28 - LogEntry.object_repr is smart_str(instance) and is kept indefinitely. GardenBed.**str** includes owner.username, and the others include the plant common_name or bed name. So the username lands in audit rows beyond what include_fields limits.
3. **low** `backend/apps/garden_calendar/apps.py:29` Registering the five models adds post_delete receivers, so Django can no longer fast-delete them. Deleting a plant, bed or user now loads every row and writes one DELETE LogEntry per row. Each **str** adds about 2-3 queries per row (plant.common_name, garden_bed, owner).
4. **low** `backend/apps/garden_calendar/auditlog.py:26` Neither AuditlogMiddleware nor set_actor is used anywhere, so every garden LogEntry has actor=NULL. The CareTask/CareLog/Harvest include_fields hold no owner or plant FK. So these rows cannot answer 'who modified X?', which is the module's stated purpose.
5. **low** `backend/apps/garden_calendar/tests/test_auditlog_registration.py:112` test_no_free_text_field_is_audited checks include_fields only against a hardcoded set of five names (FREE_TEXT_FIELDS). If someone adds a prose field under a different name (e.g. a new TextField 'comment') to include_fields, the test still passes. The owner's 'no prose in LogEntry' rule is not truly pinned. | also: test_auditlog_registration.py:22 - the test only blocklists five names, so a newly added prose TextField passes. The guard does not enforce the 'no free text' rule it claims to pin. | The test pins a fixed denylist. A new prose field with another name (e.g. 'comment', 'observations') added to include_fields would pass.
6. **low** `backend/apps/garden_calendar/services/care_schedule_service.py:483` The overdue reschedule changes the audited CareTask.scheduled_date through QuerySet.update(), which sends no save signals. These bulk reschedules write no LogEntry, so the newly enabled audit trail misses them, even though the new docstrings say scheduling changes are audited. The code predates the PR. | also: Now that CareTask is audited, the overdue reschedule still uses QuerySet.update() on scheduled_date. These changes write no LogEntry, so the audit trail silently misses bulk reschedules.
7. **low** `backend/apps/garden_calendar/auditlog.py:17` Turning registration on means deleting garden data now writes DELETE LogEntry rows that outlive it: old include_fields values plus object_repr (GardenBed **str** has owner.username, the others have common_name). No code purges LogEntry. The owner deferred this, but no follow-up todo exists yet. | also: Garden owner FKs CASCADE from User, so deleting a user now writes a DELETE LogEntry for every bed, plant, task, log and harvest. These keep common_name/variety/bed name, and GardenBed object_repr is 'name (username)'. Rows persist indefinitely; the purge follow-up has no todo in this diff.
8. **low** `backend/apps/garden_calendar/tests/test_auditlog_registration.py:22` test_no_free_text_field_is_audited only blocklists five names, so a newly added prose TextField (e.g. Plant.removal_reason-style or a new notes2) passes. The guard does not enforce the 'no free text' rule it claims to pin.
9. **low** `backend/apps/garden_calendar/auditlog.py:15` Audited GardenBed/Plant/Harvest rows will now hold user data in LogEntry with no purge on account deletion (acknowledged as a follow-up only in a docstring); GDPR erasure gap persists.
10. **low** `backend/apps/garden_calendar/auditlog.py:28` LogEntry.object_repr is smart_str(instance), and it is kept indefinitely. GardenBed.**str** includes owner.username, and Plant, CareTask, CareLog and Harvest include the plant common_name or bed name. Every garden write now stores the username in audit rows, beyond what include_fields limits.

2 more location(s) were dropped by the cap of 10 (the most severe are kept).

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1434

Follow-ups for PR #1025 (todo 571).
