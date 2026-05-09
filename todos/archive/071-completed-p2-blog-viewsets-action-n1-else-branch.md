---
status: pending
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

- [ ] `featured`, `recent`, and `related` actions are in the list-view branch of
      `get_queryset` (or equivalent prefetch/annotation applied).
- [ ] `related()` builds its queryset off `self.get_queryset()` rather than a bare
      `BlogPostPage.objects...` call.
- [ ] `python manage.py test apps.blog --noinput` passes.

## Work Log

### 2026-05-09 - Created from review 2026-05-07-1641

- Findings #39, #41, #47, #48: four action N+1 from else branch or missing get_queryset call.
