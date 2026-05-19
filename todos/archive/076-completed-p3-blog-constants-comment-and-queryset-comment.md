---
status: completed
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

- [x] `RECENT_POSTS_DEFAULT_LIMIT` has an inline comment consistent with the rest of `constants.py`.
- [x] The `get_queryset()` action-guard comment explains why `by_category` is absent.
- [x] `python manage.py test apps.blog.tests --noinput` passes (no functional change).

## Work Log

### 2026-05-18 - Started by completing-todos skill (run 2026-05-18-2300)

- Picked up by automated workflow.

### 2026-05-18 - Implementation

- `backend/apps/blog/constants.py:84` — added inline comment to
  `RECENT_POSTS_DEFAULT_LIMIT`, matching the style of the rest of the file.
- `backend/apps/blog/api/viewsets.py:165` — extended the list-action prefetch
  comment to note `by_category` is intentionally absent (it builds its own
  queryset and does not flow through `get_queryset()`).
- Comment-only change, no functional impact.
- Verification: `python manage.py test apps.blog.tests --noinput` → `Ran 173
  tests in 21.670s` / `OK (skipped=7)` / exit 0.

### 2026-05-18 - Completed by completing-todos skill (run 2026-05-18-2300)

- Verification: all 3 acceptance criteria passed.
- Review: code-review-orchestrator dispatched (wagtail / api-design / performance
  reviewers) — 0 findings, no blocking.
- `source_finding` is empty — no source-review checkoff needed.
