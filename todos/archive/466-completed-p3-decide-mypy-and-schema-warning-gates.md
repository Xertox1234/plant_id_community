---
status: completed
priority: p3
issue_id: "466"
tags: [backend, ci, typing, api-docs, decision]
dependencies: []
source_review: "todos/archive/394-completed-p3-triage-the-grandfathered-archived-todos.md"
triage: ready
triaged: 2026-10-11
blocked_on: "Three owner decisions: a mypy CI gate (and its scope), schema warnings plus --fail-on-warn, and request examples for the remaining apps."
owner_decision: "Owner: close 466 by filing three implementation todos (580 mypy CI gate for one app with django-stubs, suggested app: users; 581 fix the auth schema warnings + add --fail-on-warn; 582 OpenApiExample request examples for plant_identification, users and blog) and archiving 466 (2026-10-11)"
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

- [x] Owner decision recorded: add a mypy gate (with scope, e.g. one app
      plus the django-stubs plugin) or not.
- [x] Owner decision recorded: fix the schema warnings and add
      `--fail-on-warn`, or not.
- [x] Owner decision recorded: add request examples for the remaining apps,
      or not.
- [x] Each "yes" becomes its own implementation todo or is done here.

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1434)

- Recorded the owner's three decisions (2026-10-11): all three are "yes", each
  as its own implementation todo.
- Filed todo 580 (mypy CI gate for one app, suggested `users`, with the
  django-stubs plugin; `backend/pyproject.toml` does not load the plugin today).
- Filed todo 581 (fix the auth "unable to guess serializer" warnings and add
  `--fail-on-warn` to the `spectacular` step in
  `.github/workflows/backend-ci.yml`).
- Filed todo 582 (`OpenApiExample` request examples for plant_identification,
  users and blog).

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1434)

- AC 1: `grep -n -E '^owner_decision:.*580 mypy CI gate for one app with django-stubs' todos/archive/466-completed-p3-decide-mypy-and-schema-warning-gates.md` — evidence `.sweep-evidence/g1/466-ac0.txt` (not committed), last lines:

  ```text
  11:owner_decision: "Owner: close 466 by filing three implementation todos (580 mypy CI gate for one app with django-stubs, suggested app: users; 581 fix the auth schema warnings + add --fail-on-warn; 582 OpenApiExample request examples for plant_identification, users and blog) and archiving 466 (2026-10-11)"
  ```

- AC 2: `grep -n -E '^owner_decision:.*581 fix the auth schema warnings \+ add --fail-on-warn' todos/archive/466-completed-p3-decide-mypy-and-schema-warning-gates.md` — evidence `.sweep-evidence/g1/466-ac1.txt` (not committed), last lines:

  ```text
  11:owner_decision: "Owner: close 466 by filing three implementation todos (580 mypy CI gate for one app with django-stubs, suggested app: users; 581 fix the auth schema warnings + add --fail-on-warn; 582 OpenApiExample request examples for plant_identification, users and blog) and archiving 466 (2026-10-11)"
  ```

- AC 3: `grep -n -E '^owner_decision:.*582 OpenApiExample request examples for plant_identification, users and blog' todos/archive/466-completed-p3-decide-mypy-and-schema-warning-gates.md` — evidence `.sweep-evidence/g1/466-ac2.txt` (not committed), last lines:

  ```text
  11:owner_decision: "Owner: close 466 by filing three implementation todos (580 mypy CI gate for one app with django-stubs, suggested app: users; 581 fix the auth schema warnings + add --fail-on-warn; 582 OpenApiExample request examples for plant_identification, users and blog) and archiving 466 (2026-10-11)"
  ```

- AC 4: `grep -H -E '^(issue_id|status):|^# ' todos/580-pending-p3-mypy-ci-gate-one-app.md todos/581-pending-p3-openapi-fail-on-warn.md todos/582-pending-p3-openapi-request-examples.md` — evidence `.sweep-evidence/g1/466-ac3.txt` (not committed), last lines:

  ```text
  todos/581-pending-p3-openapi-fail-on-warn.md:issue_id: "581"
  todos/581-pending-p3-openapi-fail-on-warn.md:# Fix the auth schema warnings and run `spectacular` with `--fail-on-warn`
  todos/580-pending-p3-mypy-ci-gate-one-app.md:status: pending
  todos/580-pending-p3-mypy-ci-gate-one-app.md:issue_id: "580"
  todos/580-pending-p3-mypy-ci-gate-one-app.md:# Gate one backend app on mypy in CI, with the django-stubs plugin
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1434)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-11 - AC 4 evidence corrected by the todo sweep (run 2026-10-11-2219, todo 583)

- The AC 4 "last lines" quoted above are out of order (581 before 580) and show
  nothing from 582, so they do not prove 582 was filed with `status: pending`.
  The quoted block is left as Land wrote it; this entry supersedes it.
- Todos 580–582 have since been archived (PR #1040), so the AC 4 command no
  longer matches today's paths. Re-run against the tree PR #1022 merged
  (`9338c8a6`), each file read with `git show 9338c8a6:<path>` and the same
  `grep -E '^(issue_id|status):|^# '`, the full output is:

  ```text
  todos/580-pending-p3-mypy-ci-gate-one-app.md:status: pending
  todos/580-pending-p3-mypy-ci-gate-one-app.md:issue_id: "580"
  todos/580-pending-p3-mypy-ci-gate-one-app.md:# Gate one backend app on mypy in CI, with the django-stubs plugin
  todos/581-pending-p3-openapi-fail-on-warn.md:status: pending
  todos/581-pending-p3-openapi-fail-on-warn.md:issue_id: "581"
  todos/581-pending-p3-openapi-fail-on-warn.md:# Fix the auth schema warnings and run `spectacular` with `--fail-on-warn`
  todos/582-pending-p3-openapi-request-examples.md:status: pending
  todos/582-pending-p3-openapi-request-examples.md:issue_id: "582"
  todos/582-pending-p3-openapi-request-examples.md:# Add `OpenApiExample` request examples for plant_identification, users and blog
  ```
