---
status: pending
priority: p3
issue_id: "466"
tags: [backend, ci, typing, api-docs, decision]
dependencies: []
source_review: "todos/archive/394-completed-p3-triage-the-grandfathered-archived-todos.md"
---

# Decide whether CI gates mypy and OpenAPI schema warnings; request examples

## Problem

Two archived todos (002 and 031) asked for things that never landed. Both
are now `superseded`, pointing here.

- **Todo 002 (views type hints)** asked for "`mypy --strict` passes" on
  `backend/apps/users/views.py`. The hints landed (4d40c6ff), but mypy runs
  in no CI job or hook. An approximate run on 2026-09-27 reported 87
  errors: about 60 untyped decorators, 10 untyped calls, and about 10
  `get_*_display` attribute errors that need the django-stubs plugin.
  `pyproject.toml` sets `disallow_untyped_defs = false`.
- **Todo 031 (API docs)** asked for every endpoint to be documented. The CI
  step `spectacular --validate` (`.github/workflows/backend-ci.yml:92`)
  tolerates the standing "unable to guess serializer" warnings on the auth
  APIViews; there is no `--fail-on-warn`. It also asked for request examples
  in the docs UI. `OpenApiExample` appears only in the garden (9) and forum
  (4) views; none in plant_identification, users or blog.

## Acceptance Criteria

- [ ] Owner decision recorded: add a mypy gate (with scope, e.g. one app
      plus the django-stubs plugin) or not.
- [ ] Owner decision recorded: fix the schema warnings and add
      `--fail-on-warn`, or not.
- [ ] Owner decision recorded: add request examples for the remaining apps,
      or not.
- [ ] Each "yes" becomes its own implementation todo or is done here.
