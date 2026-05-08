---
status: completed
priority: p4
issue_id: "059"
tags: [backend, plant-identification, code-quality]
dependencies: []
---

# Consolidate PlantDiseaseDatabaseViewSet Queryset Into get_queryset()

## Problem

`PlantDiseaseDatabaseViewSet` has a class-level `queryset = PlantDiseaseDatabase.objects.filter(...)` alongside `get_queryset()` which recreates the queryset on every request. The class-level attribute is evaluated once at class definition time; having both is a style inconsistency that can confuse readers.

## Findings

- `backend/apps/plant_identification/views.py:1014` — class-level `queryset` and `get_queryset()` both present.
- Source: 2026-05-06 code review (Finding 17, INFO).

## Recommended Action

1. Remove the class-level `queryset` attribute.
2. Keep all filtering logic in `get_queryset()`.

## Technical Details

- File: `backend/apps/plant_identification/views.py:1014`

## Acceptance Criteria

- [ ] Class-level `queryset` attribute removed from `PlantDiseaseDatabaseViewSet`.
- [ ] All filtering consolidated into `get_queryset()`.
- [ ] `python manage.py test apps.plant_identification --noinput` passes.

## Work Log

### 2026-05-08 - Created from 2026-05-06 review Finding 17

- Source: `docs/todos/2026-05-06-review.md`, Finding 17 (INFO).
