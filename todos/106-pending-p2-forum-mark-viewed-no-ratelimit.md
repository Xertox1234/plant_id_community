---
status: pending
priority: p2
issue_id: "106"
tags: [forum, backend, security, rate-limiting]
dependencies: []
---

# TopicMarkViewedView has no rate limit — unauthenticated view count inflation

## Problem

`TopicMarkViewedView` (api_views.py ~519) has `permission_classes = [AllowAny]` and no
`@ratelimit` decorator. Every POST call unconditionally increments `views_count` via an
`F()` expression. An unauthenticated caller can drive any topic's view counter to an
arbitrary value with no throttle.

Every other mutating view in api_views.py carries an explicit `@method_decorator(ratelimit(...))`.
This one was omitted.

## Recommended Action

Add a rate limit decorator. Since the view is `AllowAny`, use `key='ip'`:

```python
@method_decorator(
    ratelimit(key='ip', rate=FORUM_RATE_LIMITS.get('mark_viewed', '60/m'), block=True),
    name='post',
)
class TopicMarkViewedView(APIView):
```

Add `'mark_viewed': '60/m'` to `FORUM_RATE_LIMITS` in `constants.py`.

## Acceptance Criteria

- [ ] `TopicMarkViewedView` has a `@ratelimit` decorator.
- [ ] Rate limit constant defined in `constants.py` (no magic number).
- [ ] Rapid POST requests from the same IP return 429 after the limit is hit.

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.
