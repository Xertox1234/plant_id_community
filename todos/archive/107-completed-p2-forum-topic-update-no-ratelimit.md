---
status: completed
priority: p2
issue_id: "107"
tags: [forum, backend, security, rate-limiting]
dependencies: []
---

# TopicUpdateView missing rate limit decorator

## Problem

`TopicUpdateView` (api_views.py ~541) handles pin/lock/solve topic actions and has
`permission_classes = [IsAuthenticated]` but no `@ratelimit` decorator. An authenticated
user can send unlimited PATCH requests with no throttle.

A grep of all ratelimit usages in api_views.py shows 9 total — every other mutating CBV
(CreateTopicView, CreatePostView, PostCreateView, PostUpdateView, PostDeleteView,
PostReactionView, PostImageUploadView) has one. `TopicUpdateView` was missed.

Note: `PostImageDeleteView` (~886) and `PostImageUpdateView` (~936) are also missing
rate limits — see todos 108 and 109.

## Recommended Action

```python
@method_decorator(
    ratelimit(key='user', rate=FORUM_RATE_LIMITS.get('update_topic', '30/m'), block=True),
    name='patch',
)
class TopicUpdateView(APIView):
```

Add `'update_topic': '30/m'` to `FORUM_RATE_LIMITS` in `constants.py`.

## Acceptance Criteria

- [x] `TopicUpdateView` has a `@ratelimit` decorator.
- [x] Rate limit constant in `constants.py`.
- [x] Excessive PATCH requests return 429.

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.

### 2026-05-28 - Completed by completing-todos skill (run 2026-05-28-2019)

- Added `@method_decorator(ratelimit(key="user", rate=FORUM_RATE_LIMITS["update_topic"],
  method="PATCH", block=True), name="patch")`; added `update_topic: "30/m"`.
  Note: the view is `generics.UpdateAPIView` (todo said `APIView`) but overrides
  `patch()` directly, so `name="patch"` is correct (NOT `partial_update`) —
  confirmed by the reviewer.
- Verification: `test_topic_update_rate_limited` — 30 user-keyed PATCHes non-429,
  31st is 429. Full suite `Ran 57 tests ... OK`.
- Review (batch 106-109): no blocking findings. Informational note: the test's
  `{"is_locked": True}` body is ignored for non-staff (rate-limit correctness
  unaffected — the method is still entered and counted).
