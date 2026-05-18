---
status: completed
priority: p3
issue_id: "074"
tags: [testing, performance, blog]
dependencies: []
source_review: "docs/reviews/2026-05-07-1641-full-review-COMPLETED.md"
source_finding: ""
---

# Blog tests: pin exact query count in ByCategoryQueryCountTestCase

## Problem

`ByCategoryQueryCountTestCase.test_by_category_query_count_fixed_across_n_categories`
uses a soft upper bound (`assertLessEqual(count, 15)`) rather than an exact equality
assertion. The project convention (see `test_list_action_uses_limited_prefetch` which
pins exactly 13, and `PERFORMANCE_TESTING_PATTERNS_CODIFIED.md`) is to use strict
exact-count assertions so that unexpected query additions are caught by CI.

The test currently proves N+1 is absent but does not catch future query bloat within
the 15-query budget.

## Findings

From PR #266 code review (low severity):

> "The absolute bound ≤15 is soft. Per project conventions, strict query-count assertions
> with exact values are preferred. For two empty categories, the actual count should be
> knowable and fixed. This is the same pattern used in `test_list_action_uses_limited_prefetch`
> which asserts exactly 13."

## Recommended Action

1. Run `ByCategoryQueryCountTestCase.test_by_category_query_count_fixed_across_n_categories`
   with `CaptureQueriesContext` and print each SQL statement to establish the exact baseline count.
2. Replace `self.assertLessEqual(count_2_cats, 15, ...)` with `self.assertEqual(count_2_cats, N, ...)`
   where N is the confirmed baseline, with a breakdown comment listing each query.

File: `backend/apps/blog/tests/test_blog_viewsets_caching.py`
Class: `ByCategoryQueryCountTestCase`
Method: `test_by_category_query_count_fixed_across_n_categories`

## Work Log

### 2026-05-18 - Started by completing-todos skill (run 2026-05-18-1053)

- Picked up by automated workflow.

### 2026-05-18 - Implemented

- Ran `ByCategoryQueryCountTestCase.test_by_category_query_count_fixed_across_n_categories` with
  `CaptureQueriesContext`; confirmed exact baseline count for 2 empty featured categories is **3**.
- Replaced `assertLessEqual(count_2_cats, 15)` with `assertEqual(count_2_cats, 3)` and added
  per-query breakdown comment per project convention.
- Verification: `python manage.py test apps.blog.tests.test_blog_viewsets_caching.ByCategoryQueryCountTestCase.test_by_category_query_count_fixed_across_n_categories --noinput` → OK (1 test passed).
- Verification: `python manage.py test apps.blog.tests --noinput` → exit code 0 (all tests passed).

### 2026-05-18 - Completed by completing-todos skill (run 2026-05-18-1053)

- Verification: all 2 acceptance criteria passed.
- Review: no blocking findings (minimal test-only change; 1 file affected).

## Acceptance Criteria

- [x] The `assertLessEqual(count_2_cats, 15)` is replaced with `assertEqual(count_2_cats, 3)`
      where N is documented with a per-query breakdown comment.
- [x] `python manage.py test apps.blog.tests --noinput` passes.
