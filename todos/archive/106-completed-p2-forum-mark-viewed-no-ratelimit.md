---
status: completed
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

- [x] `TopicMarkViewedView` has a `@ratelimit` decorator.
- [x] Rate limit constant defined in `constants.py` (no magic number).
- [x] Rapid POST requests from the same IP return 429 after the limit is hit.

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.

### 2026-05-28 - Completed by completing-todos skill (run 2026-05-28-2019)

- Added `@method_decorator(ratelimit(key="ip", rate=FORUM_RATE_LIMITS["mark_viewed"],
  method="POST", block=True), name="post")` to `TopicMarkViewedView`; added
  `mark_viewed: "60/m"` to `FORUM_RATE_LIMITS`. Used the dict constant directly
  (not the todo's `.get(..., "60/m")` fallback) per the no-magic-number rule.
- Verification: `MissingRateLimitTests.test_mark_viewed_rate_limited` — 60 IP-keyed
  POSTs are non-429, the 61st is 429. Full suite `Ran 57 tests ... OK`.
- Review (batch 106-109): no blocking findings; `name=`/`key=`/`method=`/429-wiring
  all verified correct.
