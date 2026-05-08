---
status: completed
priority: p4
issue_id: "061"
tags: [backend, users, code-quality, testability]
dependencies: []
---

# Promote _ics_safe Lambda to Module-Level Helper

## Problem

`_ics_safe` is defined as a lambda inside `export_care_reminders_calendar` in `users/views.py`. Lambdas defined inside view functions are untestable in isolation and harder to find when debugging ICS encoding issues.

## Findings

- `backend/apps/users/views.py` — `_ics_safe` lambda inside `export_care_reminders_calendar`.
- Source: 2026-05-06 code review (Finding 19, INFO).

## Recommended Action

1. Extract `_ics_safe` to a named module-level function `_sanitize_ics_field()` in `users/views.py` (or in a `users/utils.py` if one exists).
2. Update the view to call `_sanitize_ics_field()`.

## Technical Details

- File: `backend/apps/users/views.py` — `export_care_reminders_calendar` function.

## Acceptance Criteria

- [ ] `_sanitize_ics_field` defined at module level (not inside the view function).
- [ ] `python manage.py test apps.users --noinput` passes.

## Work Log

### 2026-05-08 - Created from 2026-05-06 review Finding 19

- Source: `docs/todos/2026-05-06-review.md`, Finding 19 (INFO).
