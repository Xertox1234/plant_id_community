---
status: pending
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

- [ ] The count check and insert are inside `transaction.atomic()` with `select_for_update()`.
- [ ] Concurrent upload requests cannot collectively exceed `FORUM_IMAGE_MAX_PER_POST`.

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.
