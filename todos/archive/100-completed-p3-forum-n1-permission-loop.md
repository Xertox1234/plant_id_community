---
status: completed
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

- [x] No `PermissionHandler` call inside a Python `for` loop over a queryset in `api_views.py`.
- [x] At least one `assertNumQueries` test covers the previously affected endpoint.

## Work Log

### 2026-05-28 - Started by completing-todos skill (run 2026-05-28-1516)

- Picked up by automated workflow.
- Found 2 loops in `UserTopicsListView` and `UserWatchedTopicsListView` calling `perm_handler.can_read_forum(forum, user)` for each forum.
- Replaced both with `perm_handler.get_readable_forums(Forum.objects.filter(type=Forum.FORUM_POST), user)` — Machina's bulk permission check.
- Added `test_query_counts.py` with `assertNumQueries(7)` covering `UserTopicsListView` with 3 forums.
- Verification: `python manage.py test apps.forum_integration --noinput` → Ran 39 tests, OK (skipped=3).

### 2026-05-28 - Completed by completing-todos skill (run 2026-05-28-1516)

- Verification: all 2 acceptance criteria passed.
- Review: 1 high (missing watched-topics test → repaired), 1 medium (tree-hierarchy comment → added). Loop exited after this todo per repair policy.
