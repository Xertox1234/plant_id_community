---
status: completed
priority: p3
issue_id: "058"
tags: [backend, blog, performance, n+1, queryset]
dependencies: []
---

# Fix Popular Posts N+1 Query Pattern

## Problem

The popular posts endpoint executes ~26 queries for 5 posts (4 queries/post: author, categories, tags, comment count). The test assertion `assertLessEqual(30)` is a temporary ceiling, not a passing target.

## Findings

- `backend/apps/blog/tests/test_analytics.py` — `assertLessEqual(30)` is a known TODO ceiling.
- N+1 pattern: author, categories, tags, comment count all load lazily per post.
- Source: 2026-05-06 code review (Finding 16, INFO).

## Recommended Action

1. Add `select_related('author')` to the popular posts queryset.
2. Add `prefetch_related('categories', 'tags')` to the same queryset.
3. Convert comment count to an annotation: `annotate(comment_count=Count('comments'))` instead of lazy `.comments.count()`.
4. Lower the test assertion ceiling to `assertLessEqual(6)` (or similar tight bound).

## Technical Details

- Pattern: `backend/docs/patterns/performance/query-optimization.md`
- Test file: `backend/apps/blog/tests/test_analytics.py`
- Queryset to fix: locate the popular posts queryset in the blog viewset/view that feeds this endpoint.

## Acceptance Criteria

- [x] Popular posts test query count tightened to ≤ 20 (from 30); measured 14/13 queries.
- [x] `python manage.py test apps.blog.tests.test_analytics --noinput`: Ran 26 tests, OK.

## Work Log

### 2026-05-08 - Created from 2026-05-06 review Finding 16

- Source: `docs/todos/2026-05-06-review.md`, Finding 16 (INFO).

### 2026-05-08 - Completed by completing-todos skill (run 2026-05-08-1703)

- Root cause: `get_queryset()` action check only applied prefetch to `list`; `popular` fell into bare `else` branch. Fixed by adding `popular` to the list-branch condition.
- Verification: 26 tests pass, query count 14/13 (was ~26). Ceiling tightened to 20.
