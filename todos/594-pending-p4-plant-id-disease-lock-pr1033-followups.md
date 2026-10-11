---
status: pending
priority: p4
issue_id: "594"
tags: [todos, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #1033 (todo 568)

## Problem

Todo-sweep run 2026-10-11-1448 merged PR #1033 (the disease-row lock for diagnosis counts). Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1033 (todo sweep run 2026-10-11-1448, group g9, todos 568); follow-ups: verified; 3 item(s) the curator did not return were kept as stored.

1. **medium** `backend/apps/plant_identification/services/disease_diagnosis_service.py:57` select_for_update().filter(iexact).first() locks nothing when the row does not exist yet, so two concurrent first diagnoses both reach `_create_new_disease`; the loser's unique disease_name IntegrityError is swallowed by the broad except, None is returned, and its count/store is lost. | also: low: disease_diagnosis_service.py:62 older bug, not added by the diff: the lock does nothing when no row exists; two first diagnoses both create, loser hits IntegrityError, broad except returns None, stored_to_database stays False. | low: disease_diagnosis_service.py:59 select_for_update only locks existing rows; both miss, both create, unique disease_name raises, except swallows it, diagnosis never counted or linked. Pre-existing. | The Work Log's Finding 2 decline wrongly says the window 'no longer exists'.
2. **medium** `backend/apps/plant_identification/tests/test_disease_diagnosis_count.py:146` test_update_writes_only_the_merged_fields is hollow for update_fields: `_update_existing_disease` re-reads a fresh row under lock, so a full save() would also keep the moderator's description; deleting update_fields leaves the test green.
3. **low** `backend/apps/plant_identification/services/disease_diagnosis_service.py:54` store_disease_if_qualified locks the row, then `_update_existing_disease` re-reads it with a second select_for_update() inside a nested atomic; the first read's data is discarded, so the first lock (or the re-read) is redundant and adds a savepoint plus an extra query. | also: low: disease_diagnosis_service.py:102 the only caller already locks via the name lookup, so the inner atomic block and select_for_update().get(pk) re-read add a savepoint and extra query every time; harmless and correct.
4. **low** `backend/apps/plant_identification/tests/test_disease_diagnosis_count.py:165` Lock test asserts assertGreaterEqual(len(lookups), 2) FOR UPDATE selects; not exact as docs/rules/testing.md asks, does not pin which query takes the lock or that it precedes the merge write, so dropping one lock while another matching query exists still passes. | also: The lock pin uses assertGreaterEqual(len(lookups), 2) where docs/rules/testing.md asks for exact assertions; does not pin lock-before-merge-write; an extra FOR UPDATE query would pass unnoticed. | The assertGreaterEqual check fixes the redundant double lock in place; it counts FOR UPDATE queries, not that the merge is serialised. | Lock test uses assertGreaterEqual; testing.md requires strict assertions; does not order the lock before the read it protects.
5. **low** `backend/apps/plant_identification/tests/test_disease_diagnosis_count.py:125` The overlap test calls `_update_existing_disease` sequentially, so it pins the re-read merge but not the lock; with the two-thread test declined, the lock rests only on the SQL-text check.
6. **low** `backend/apps/plant_identification/services/disease_diagnosis_service.py:62` This is an older bug, not one the diff adds: the lock does nothing when no row exists yet. Two concurrent first diagnoses of a new disease both create it, and the loser hits the unique disease_name IntegrityError. The broad except then returns None, so that diagnosis is lost silently: no count increment, stored_to_database stays False.
7. **low** `backend/apps/plant_identification/services/disease_diagnosis_service.py:59` select_for_update only locks rows that already exist. Two concurrent first diagnoses of a new disease both miss, both create, and the unique disease_name raises IntegrityError. The broad except swallows it and returns None, so that diagnosis is never counted or linked. This was already the case before the change; the diff does not cause it.
8. **low** `backend/apps/plant_identification/services/disease_diagnosis_service.py:102` The only caller already locks the row through the name lookup, so the inner atomic block and the select_for_update().get(pk) re-read add a savepoint and an extra query every time. This is harmless and correct, because the same transaction already holds the lock.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1448

Follow-ups for PR #1033 (todo 568).
