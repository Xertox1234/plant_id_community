---
status: completed
priority: p2
issue_id: "108"
tags: [forum, backend, security, rate-limiting]
dependencies: []
---

# PostImageDeleteView missing rate limit decorator

## Problem

`PostImageDeleteView` (api_views.py ~886) has no `@ratelimit` decorator. An authenticated
user can hammer `DELETE /posts/{id}/images/{img_id}/delete/` in a tight loop with no
throttle, bulk-deleting images or generating high DB write load.

## Recommended Action

```python
@method_decorator(
    ratelimit(key='user', rate=FORUM_RATE_LIMITS.get('image_delete', '30/m'), block=True),
    name='delete',
)
class PostImageDeleteView(APIView):
```

Add `'image_delete': '30/m'` to `FORUM_RATE_LIMITS` in `constants.py`.

Consider batching todos 107, 108, 109 into a single "add missing rate limits" PR.

## Acceptance Criteria

- [x] `PostImageDeleteView` has a `@ratelimit` decorator.
- [x] Rate limit constant in `constants.py`.

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.

### 2026-05-28 - Completed by completing-todos skill (run 2026-05-28-2019)

- Added `@method_decorator(ratelimit(key="user", rate=FORUM_RATE_LIMITS["image_delete"],
  method="DELETE", block=True), name="delete")`; added `image_delete: "30/m"`.
- Verification: `test_image_delete_rate_limited` — 30 user-keyed DELETEs non-429,
  31st is 429 (uses a nonexistent image_id; the handler is still entered and the
  rate-limit increments before the 404). Full suite `Ran 57 tests ... OK`.
- Review (batch 106-109): no blocking findings.
