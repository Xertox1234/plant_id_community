---
status: completed
priority: p3
issue_id: "063"
tags: [backend, plant-identification, celery, reliability]
dependencies: []
---

# Add Idempotency Guard to run_identification Celery Task

## Problem

The `run_identification` Celery task has no guard against duplicate execution. If Celery retries the task on a transient failure, the identification runs twice — wasting API quota and potentially producing duplicate results.

## Findings

- `backend/apps/plant_identification/tasks.py` — `run_identification` task called via `.delay(str(request_obj.request_id))`.
- No status check at task entry; task will re-run even if the request is already `completed` or `failed`.
- Pattern doc: `backend/docs/patterns/domain/celery.md`.
- Source: 2026-05-06 code review (Finding 21, INFO).

## Recommended Action

1. At the start of `run_identification`, fetch the `PlantIdentificationRequest` by `request_id`.
2. If `status != 'pending'`, log and return early:

   ```python
   if request_obj.status != 'pending':
       logger.info("[CELERY] Skipping duplicate task for %s (status=%s)", task_request_id, request_obj.status)
       return
   ```

3. Add a test that verifies a task called twice on a non-pending request completes without side effects.

## Technical Details

- File: `backend/apps/plant_identification/tasks.py`
- Pattern: `backend/docs/patterns/domain/celery.md` — idempotency section.

## Acceptance Criteria

- [ ] Idempotency guard present at start of `run_identification`.
- [ ] Test verifies that calling the task on an already-completed request produces no duplicate identification.
- [ ] `python manage.py test apps.plant_identification --noinput` passes.

## Work Log

### 2026-05-08 - Created from 2026-05-06 review Finding 21

- Source: `docs/todos/2026-05-06-review.md`, Finding 21 (INFO).
