---
status: completed
priority: p2
issue_id: "116"
tags: [forum, backend, data-integrity]
dependencies: []
---

# ForumPostImage.save() upload_order collision — a post can never hold >1 image

## Problem

`ForumPostImage.save()` auto-assigns `upload_order` with:

```python
self.upload_order = (max_order or -1) + 1
```

When the post's current max `upload_order` is `0` (it already has one image),
`max_order or -1` evaluates to `-1` because `0` is falsy in Python. So the second
image also gets `upload_order = 0`, violating
`unique_together = ['post', 'upload_order']` → `IntegrityError`.

Net effect: **no forum post can ever store more than one image**, even though the
UI and `FORUM_IMAGE_MAX_PER_POST = 6` advertise up to six. The 2nd upload (a
separate request, or the 2nd file in a batch) fails; in `PostImageUploadView` it
is caught per-file and reported as "Failed to upload … : upload error".

Discovered while writing tests for todo 113 (the per-post cap was effectively
unreachable beyond 1 image because >1 could never be stored). Confirmed by a real
`UniqueViolation ... Key (post_id, upload_order)=(N, 0) already exists`.

## Evidence

`backend/apps/forum_integration/models.py` ~700:

```python
def save(self, *args, **kwargs):
    if self.upload_order is None or self.upload_order == 0:
        max_order = ForumPostImage.objects.filter(post=self.post).aggregate(
            models.Max('upload_order')
        )['upload_order__max']
        self.upload_order = (max_order or -1) + 1   # bug: 0 is falsy
```

## Recommended Action

Distinguish "no rows" (None) from "max is 0":

```python
self.upload_order = (max_order if max_order is not None else -1) + 1
```

Also consider performing this assignment under the `select_for_update` lock that
`PostImageUploadView` now holds (todo 113), to avoid an order race between
concurrent uploads to the same post.

## Acceptance Criteria

- [x] A post can store up to `FORUM_IMAGE_MAX_PER_POST` images, each with a
  distinct `upload_order` (0, 1, 2, …).
- [x] Uploading multiple images in one request assigns sequential orders without
  collision.
- [x] Regression test: upload 3 images to a post → 3 stored with orders 0/1/2.

## Work Log

### 2026-05-28 - Created

- Found while implementing todo 113 (image cap concurrency). The auto-assign
  `(max_order or -1)` collides on the 2nd image. Tracked separately to keep 113
  scoped to the cap race.

### 2026-05-28 - Completed by completing-todos skill (run 2026-05-28-2019)

- Fixed `ForumPostImage.save()`: `(max_order or -1)` -> `(max_order if max_order
  is not None else -1)`, AND gated the auto-assign on `self.pk is None` so it runs
  on INSERT only.
- The pk-is-None guard was prompted by code review: with only the falsy fix, a
  bare `image.save()` in `PostImageUpdateView.patch()` would re-fire the
  auto-assign and *relocate* an order-0 image when editing its alt_text. Insert-only
  assignment fixes that (and lets reorder set order 0 explicitly, which the old
  `== 0` guard blocked).
- Tests (`test_security.py::ImageUploadValidationTests`):
  `test_multiple_images_get_sequential_upload_orders` (upload 3 -> orders 0/1/2) and
  `test_update_image_metadata_preserves_upload_order` (patch alt_text -> order
  unchanged). Both fail without the respective fix.
- Concurrency: safe — the sole create path is `PostImageUploadView`, which holds
  the todo-113 `select_for_update` lock across the Max-read + assign.
- Verification: `Ran 66 tests ... OK`.
- Review (feature-dev:code-reviewer): fix correct for all cases (first/subsequent/
  gap); 0 critical/high; the medium finding (update-path relocation) is what the
  pk-is-None guard resolves.
