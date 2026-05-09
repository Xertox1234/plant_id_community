---
status: pending
priority: p3
issue_id: "076"
tags: [style, blog]
dependencies: []
source_review: "docs/reviews/2026-05-07-1641-full-review-COMPLETED.md"
source_finding: ""
---

# Blog: add inline comment to RECENT_POSTS_DEFAULT_LIMIT; update get_queryset comment

## Problem

Two minor comment inconsistencies introduced in PR #266:

1. `RECENT_POSTS_DEFAULT_LIMIT = 10` in `backend/apps/blog/constants.py` has no inline
   comment. Every other constant in that file has one (e.g.,
   `RECENT_POSTS_MAX_LIMIT = 50  # Cap to prevent abuse / expensive slices`).
   Missing the inline doc for `DEFAULT_LIMIT` is inconsistent.

1. The comment on the `get_queryset()` action guard in `viewsets.py` (line ~162) says
   "List-style actions: full prefetch/annotation for BlogPostPageListSerializer". Since
   `by_category` was removed from this list (it builds its own queryset), the comment
   is slightly misleading — a reader might wonder why `by_category` is absent.

## Recommended Action

1. Add `# Default number of recent posts returned when ?limit is not specified` to
   `RECENT_POSTS_DEFAULT_LIMIT` in `constants.py`.
1. Update the comment on the `get_queryset()` action guard to mention that `by_category`
   and similar self-contained actions are intentionally excluded because they build their
   own querysets directly.

## Files

- `backend/apps/blog/constants.py`
- `backend/apps/blog/api/viewsets.py`

## Acceptance Criteria

- [ ] `RECENT_POSTS_DEFAULT_LIMIT` has an inline comment consistent with the rest of `constants.py`.
- [ ] The `get_queryset()` action-guard comment explains why `by_category` is absent.
- [ ] `python manage.py test apps.blog.tests --noinput` passes (no functional change).
