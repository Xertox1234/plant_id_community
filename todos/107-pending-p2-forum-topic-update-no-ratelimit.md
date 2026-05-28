---
status: pending
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

- [ ] `TopicUpdateView` has a `@ratelimit` decorator.
- [ ] Rate limit constant in `constants.py`.
- [ ] Excessive PATCH requests return 429.

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.
