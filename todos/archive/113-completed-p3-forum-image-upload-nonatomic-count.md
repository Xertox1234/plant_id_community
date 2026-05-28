---
status: completed
priority: p3
issue_id: "113"
tags: [forum, backend, concurrency]
dependencies: []
---

# Non-atomic image count check — concurrent uploads can exceed per-post image cap

## Problem

`PostImageUploadView.post()` (api_views.py ~781) reads `existing_count`, checks
`total = existing_count + len(files) <= FORUM_IMAGE_MAX_PER_POST`, then inserts.
No `select_for_update()` or `transaction.atomic()` wraps the check + insert.

Two concurrent upload requests when `existing_count=5` (cap=6) can both read 5, both
compute total=6, both pass the guard, and together store 7 images against the post.

## Recommended Action

Wrap the count check and insert in an atomic block with a row lock:

```python
from django.db import transaction

with transaction.atomic():
    post = get_object_or_404(Post.objects.select_for_update(), id=post_id)
    existing_count = ForumPostImage.objects.filter(post=post).count()
    total_count = existing_count + len(uploaded_files)
    if total_count > FORUM_IMAGE_MAX_PER_POST:
        return Response({"error": "..."}, status=400)
    # ... proceed with uploads
```

## Acceptance Criteria

- [x] The count check and insert are inside `transaction.atomic()` with `select_for_update()`.
- [x] Concurrent upload requests cannot collectively exceed `FORUM_IMAGE_MAX_PER_POST`.

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.

### 2026-05-28 - Completed by completing-todos skill (run 2026-05-28-2019)

Changes (`api_views.py` `PostImageUploadView.post`):
- Added `from django.db import transaction`.
- Wrapped the cap check + insert loop in `with transaction.atomic()`, re-fetching
  the post under a row lock: `Post.objects.select_for_update()`. Concurrent
  uploads to the same post now serialize, so the count guard can't be bypassed.
- Each `ForumPostImage.objects.create()` runs in a NESTED `atomic()` savepoint so
  a failed insert rolls back only that file and doesn't poison the outer
  transaction — preserving the existing per-file partial-success behavior.

Tests (`test_security.py::ImageUploadValidationTests`):
- `test_upload_exceeding_max_per_post_rejected` (batch > cap → 400, 0 created).
- `test_cap_enforced_with_existing_images` (existing rows + new batch crosses the
  cap → 400, existing rows untouched).
- `test_partial_success_with_invalid_file_in_batch` (mixed batch still commits the
  valid file under the atomic block).

Verification: `Ran 62 tests ... OK`. (True concurrency isn't exercisable in
Django's transactional TestCase; the lock structure is verified by code + review,
the count enforcement by the behavioral tests.)

Review (feature-dev:code-reviewer): 0 critical/high. Confirmed the Post-row lock
is the correct target, the early `return 400` inside `atomic()` is safe (read-only
txn), and the nested savepoint is *required* (not just convenient). 1 medium
(initial cap test didn't exercise the new path — it hit the early return that the
old code shared) → **fixed** by adding the existing-images + partial-success tests.
Low (lock held across image I/O) accepted: per-post lock, ≤6 files, 20/h rate cap.

**Spun off todo 116 (p2):** while testing this, found a *separate* pre-existing
bug — `ForumPostImage.save()` does `(max_order or -1) + 1`; since `0` is falsy, the
2nd image on any post collides on `unique_together(post, upload_order)`, so a post
can never hold more than one image. Out of scope for the cap-race fix; tracked
separately with evidence + a one-line fix.
