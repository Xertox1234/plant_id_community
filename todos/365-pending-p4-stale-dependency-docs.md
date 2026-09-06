---
status: pending
priority: p4
issue_id: "365"
tags: [documentation, dependencies]
dependencies: []
---

# Retire or mark the two stale 2025 dependency docs

## Problem

`backend/docs/DEPENDENCY_SECURITY_AUDIT_2025.md` and
`backend/docs/DEPENDENCY_UPGRADE_QUICKREF.md` still prescribe installing
`django-celery-beat`, which PR #695 removed, alongside other 2025-era pins
(Django 5.2.7, etc.) that no longer reflect the stack. They read as actionable
guidance but are point-in-time artifacts.

## Findings

- Stale `django-celery-beat` prescriptions at
  `DEPENDENCY_SECURITY_AUDIT_2025.md:345,773,873` and
  `DEPENDENCY_UPGRADE_QUICKREF.md:27` (found by the PR #695 code review).
- Neither file is in the auto-injected set — `docs/rules/celery.md` and
  `backend/docs/patterns/domain/celery.md` were both verified clean — so this is
  documentation rot, not agent-facing guidance.
- **Why #695 did not just fix it:** markdownlint auto-fixes MD022 across the whole
  file on touch. Adding 4 marker lines produced 132 lines of unrelated blank-line
  churn, which would have buried the upgrade diff. This is the todo-117 friction.
- `docs/development/CELERY_INTEGRATION_TODOS.md` was already lint-clean and *was*
  marked in #695.

## Recommended Action

1. Decide the honest disposition: these are dated audit artifacts. Prefer moving both
   to `docs/archive/` over maintaining them in place.
2. If they stay, take the markdownlint reformat as its own commit **first**, then add
   the content markers in a second commit so the semantic change is reviewable.

## Technical Details

- Reformat noise is MD022 ("headings surrounded by blank lines"), purely mechanical.
- Related: todo 117 tracks the whole-file-reformat commit friction generally.

## Acceptance Criteria

- [ ] Neither file prescribes installing `django-celery-beat`
- [ ] Either both live under `docs/archive/`, or both are lint-clean with markers
- [ ] Any reformat lands as a separate commit from any content change

## Work Log

### 2026-09-06 - Filed

- Split out of PR #695 rather than dragging a 132-line reformat through a Django
  upgrade PR.

## Notes

p4: pure hygiene, no runtime effect. Bundle it with the next markdownlint cleanup.
