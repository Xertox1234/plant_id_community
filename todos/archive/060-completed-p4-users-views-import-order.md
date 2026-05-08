---
status: completed
priority: p4
issue_id: "060"
tags: [backend, users, code-quality, pep8]
dependencies: []
---

# Fix PEP 8 Import Order in users/views.py

## Problem

A local import (`from .constants import ...`) was added after a cross-app import (`from apps.plant_identification.constants import ...`), violating PEP 8 import grouping (local imports should precede cross-app imports, or at least be grouped with other local imports).

## Findings

- `backend/apps/users/views.py:26` — `from .constants import RATE_LIMIT_DEMO_DATA_CREATE, RATE_LIMIT_ONBOARDING_EVENT` appears after `from apps.plant_identification.constants import RATE_LIMITS`.
- Source: 2026-05-06 code review (Finding 18, INFO).

## Recommended Action

1. Reorder imports so `from .constants import ...` precedes `from apps.plant_identification.constants import ...`.

## Technical Details

- File: `backend/apps/users/views.py` around line 26.

## Acceptance Criteria

- [ ] `from .constants import ...` appears before `from apps.plant_identification.constants import ...` in the import block.
- [ ] `python manage.py test apps.users --noinput` passes.

## Work Log

### 2026-05-08 - Created from 2026-05-06 review Finding 18

- Source: `docs/todos/2026-05-06-review.md`, Finding 18 (INFO).
