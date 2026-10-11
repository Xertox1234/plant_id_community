---
status: pending
priority: p3
issue_id: "582"
tags: [backend, api-docs]
dependencies: []
---

# Add `OpenApiExample` request examples for plant_identification, users and blog

## Problem

Todo 031 asked for request examples in the API docs UI. `OpenApiExample`
appears only in `backend/apps/garden_calendar/api/views.py` and
`backend/packages/wagtail_forum/wagtail_forum/api/views.py` (checked
2026-10-11). The plant_identification, users and blog APIs have none, so
`/api/docs` shows no sample request body for them.

The owner decided (todo 466, 2026-10-11) to add them for those three apps.

## Acceptance Criteria

- [ ] Each write endpoint (POST, PUT, PATCH) in `apps/plant_identification`,
      `apps/users` and `apps/blog` that takes a request body has at least one
      `OpenApiExample` with `request_only=True`, following the garden_calendar
      pattern.
- [ ] Example values are obviously fake: no real email addresses, tokens, API
      keys or user data.
- [ ] The generated schema contains the examples: a test or script counts the
      request examples per app in the `spectacular` output and the count is
      non-zero for each of the three apps.
- [ ] `python manage.py spectacular --file /dev/null --validate` still passes.

## Work Log

## Notes

Split out of todo 466 (owner decision 2026-10-11).
