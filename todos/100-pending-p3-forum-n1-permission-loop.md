---
status: pending
priority: p3
issue_id: "100"
tags: [forum, backend, performance]
dependencies: []
---

# Eliminate N+1 permission checks in forum topic list views

## Problem

Several forum list endpoints call `PermissionHandler.forum_has_perm()` inside a Python loop
over topics or posts. Each call hits Django Machina's per-object permission tables, resulting
in N+1 queries for N items — measurable at page sizes above ~20.

## Recommended Action

1. Identify all loops over topics/posts that call `perm_handler.*` inside the loop body.
2. Bulk-fetch the required permission rows before the loop using `prefetch_related` or a
   single `IN` query.
3. Add `assertNumQueries(expected)` assertions to the relevant test cases to pin the count.

## Acceptance Criteria

- [ ] No `PermissionHandler` call inside a Python `for` loop over a queryset in `api_views.py`.
- [ ] At least one `assertNumQueries` test covers the previously affected endpoint.
