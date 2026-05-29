---
status: completed
priority: p2
issue_id: "109"
tags: [forum, backend, security, rate-limiting]
dependencies: []
---

# PostImageUpdateView missing rate limit decorator

## Problem

`PostImageUpdateView` (api_views.py ~936) handles image reorder PATCHes and has no
`@ratelimit` decorator. `reorderPostImages` in forumService.ts fires one PATCH per
attachment in sequence — with no server-side throttle, a post with 6 images generates
6 unguarded writes per reorder action.

## Recommended Action

```python
@method_decorator(
    ratelimit(key='user', rate=FORUM_RATE_LIMITS.get('image_update', '60/m'), block=True),
    name='patch',
)
class PostImageUpdateView(APIView):
```

Add `'image_update': '60/m'` to `FORUM_RATE_LIMITS` in `constants.py`.

Consider batching todos 107, 108, 109 into a single "add missing rate limits" PR.

## Acceptance Criteria

- [x] `PostImageUpdateView` has a `@ratelimit` decorator.
- [x] Rate limit constant in `constants.py`.

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.

### 2026-05-28 - Completed by completing-todos skill (run 2026-05-28-2019)

- Added `@method_decorator(ratelimit(key="user", rate=FORUM_RATE_LIMITS["image_update"],
  method="PATCH", block=True), name="patch")`; added `image_update: "60/m"`.
- Verification: `test_image_update_rate_limited` — 60 user-keyed PATCHes non-429,
  61st is 429. Full suite `Ran 57 tests ... OK`.
- Review (batch 106-109): no blocking findings.
