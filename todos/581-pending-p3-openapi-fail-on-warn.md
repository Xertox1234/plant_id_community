---
status: pending
priority: p3
issue_id: "581"
tags: [backend, ci, api-docs]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "Fix all (large): keep the AC as written; fix every spectacular warning and error in all apps so --validate --fail-on-warn exits 0; runs in sequence with 582, which touches the same views (2026-10-11)"
---

# Fix the auth schema warnings and run `spectacular` with `--fail-on-warn`

## Problem

The CI step "Validate OpenAPI schema generation"
(`.github/workflows/backend-ci.yml`) runs
`python manage.py spectacular --file /dev/null --validate` without
`--fail-on-warn`. Its comment explains why: the auth APIViews emit standing
"unable to guess serializer" warnings, and those are tolerated. So a new
warning anywhere in the API goes unnoticed, and the auth endpoints have no
documented request or response shape in `/api/docs`.

The owner decided (todo 466, 2026-10-11) to fix the warnings and make CI fail
on any new one.

## Acceptance Criteria

- [ ] `python manage.py spectacular --file /dev/null --validate --fail-on-warn`
      (run from `backend/`) exits 0. Each auth APIView that warned now declares
      its request and response shapes (`@extend_schema` with a serializer or
      `inline_serializer`), rather than having the warning silenced.
- [ ] The CI step passes `--fail-on-warn`, and its comment no longer describes
      tolerated warnings.
- [ ] A view added without a serializer makes the step fail (shown once, then
      reverted).

## Work Log

## Notes

Split out of todo 466 (owner decision 2026-10-11).
