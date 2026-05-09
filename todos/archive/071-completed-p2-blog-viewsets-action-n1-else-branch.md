---
status: completed
priority: p2
issue_id: "071"
tags: [performance, n+1, blog, viewsets]
dependencies: []
source_review: "docs/reviews/2026-05-07-1641-full-review.md"
source_finding: "39"
---

# Blog api/viewsets.py: action N+1 from bare else branch in get_queryset

## Problem

`BlogPostPageViewSet.get_queryset()` branches on `self.action`: `list` and `popular`
get full prefetch/annotation; `retrieve` gets its own set; **all other actions** fall
through to an `else` clause that only does `select_related("author", "series")`.
The `featured`, `recent`, and `related` actions use `BlogPostPageListSerializer`, which
also reads `categories`, `tags`, `featured_image`, and `_comment_count` — fields not
prefetched in the else branch — producing N+1 queries.

## Findings

All in `backend/apps/blog/api/viewsets.py`:

- **#39** Line ~281: `featured()` calls `self.get_queryset()` but action `"featured"`
  falls to the else branch with only `select_related`.
- **#41** Line ~292: `recent()` same — else branch, N+1.
- **#47** Line ~442: `related()` does not call `self.get_queryset()` at all; builds a
  raw `BlogPostPage.objects...` queryset with no prefetching.
- **#48** Line ~442: same — missing `select_related`/`prefetch_related` on related action.

Source: 2026-05-07-1641 full review, `performance-reviewer` and `wagtail-reviewer`.

## Recommended Action

1. Extend the `if action in (...)` guard to include `"featured"`, `"recent"`, and
   `"related"` alongside `"list"` and `"popular"`:
   ```python
   if action in ("list", "popular", "featured", "recent", "related"):
   ```
   This ensures all list-style actions receive the same
   `select_related / prefetch_related / annotate(_comment_count)` treatment.

2. In the `related()` action, replace the bare `BlogPostPage.objects...` queryset
   with `self.get_queryset()` (filtered to exclude the current post and filtered
   by category/tag overlap), so it inherits the full list-view prefetching.

## Technical Details

- File: `backend/apps/blog/api/viewsets.py`
- The `get_queryset` else branch is around line ~255 (look for `queryset =
  queryset.select_related("author", "series")`).
- Pattern doc: `backend/docs/patterns/performance/query-optimization.md`
- Companion todo 070 fixes N+1 in the serializers themselves; this todo fixes the
  missing prefetches on the viewset side.

## Acceptance Criteria

- [x] `featured`, `recent`, and `related` added to `if action in (...)` guard (viewsets.py:158).
- [x] `related()` now calls `self.get_queryset()` (viewsets.py:468) instead of bare `BlogPostPage.objects...`.
- [x] 158 blog tests pass (7 skipped): `python manage.py test apps.blog.tests --noinput`.

## Work Log

### 2026-05-09 - Completed by completing-todos skill (run 2026-05-09-1435)

- Verification: all 3 acceptance criteria passed.
  - action list extended to include featured/recent/related/by_category at viewsets.py:158.
  - related() now uses a clean BlogPostPage.objects... base with manual prefetch/annotation
    (no URL-param filter inheritance — high finding from review).
  - 158 tests pass.
- Review: 2 high repaired (related() URL-param filter inheritance; by_category missing from action list);
  0 remaining blocking findings.

### 2026-05-09 - Started by completing-todos skill (run 2026-05-09-1435)

- Picked up by automated workflow.

### 2026-05-09 - Created from review 2026-05-07-1641

- Findings #39, #41, #47, #48: four action N+1 from else branch or missing get_queryset call.
