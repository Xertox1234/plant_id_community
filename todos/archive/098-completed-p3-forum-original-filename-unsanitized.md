---
status: completed
priority: p3
issue_id: "098"
tags: [forum, backend, security]
dependencies: []
source_review: "docs/superpowers/plans/2026-05-25-forum-phase2-security.md"
source_finding: "M2"
---

# Forum: sanitize `original_filename` before storing/returning it

## Problem

`PostImageUploadView` stores the raw `uploaded_file.name` from the HTTP request as `ForumPostImage.original_filename` (`api_views.py:716`) and returns it in every image API response. This is user-controlled data persisted to the DB and echoed back with no sanitization.

## Recommended Action

Before assigning to `original_filename`, strip path components and limit length:

```python
import os
safe_name = os.path.basename(uploaded_file.name)[:255]
```

## Acceptance Criteria

- [x] `original_filename` is stripped of path separators and capped at 255 chars before storage.
- [x] `python manage.py test apps.forum_integration --noinput` still green.

## Work Log

### 2026-05-26 - Created

- Surfaced by security-reviewer during Phase 2 audit (MEDIUM — out of scope for Phase 2).

### 2026-05-26 - Implemented by completing-todos skill (run 2026-05-26-1959)

- `os` was already imported. One-line fix at `api_views.py:821`:
  `original_filename=uploaded_file.name` → `original_filename=os.path.basename(uploaded_file.name)[:255]`
- Verification: `python manage.py test apps.forum_integration --noinput` → Ran 38 tests in 6.843s — OK (skipped=3).

### 2026-05-26 - Completed by completing-todos skill (run 2026-05-26-1959)

- Verification: all 2 acceptance criteria passed.
- Review: 0 findings — clean.
