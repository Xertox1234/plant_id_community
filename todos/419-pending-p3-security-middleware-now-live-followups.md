---
status: pending
priority: p3
issue_id: "419"
tags: [backend, security, middleware, cleanup]
dependencies: []
source_review: "todos/archive/405-completed-p3-backend-endpoints-no-client-triage.md"
source_finding: "slice 4 code review, non-blocking 3-8"
---

# Security middlewares are live now: fix what they record, and cleanup left by slice 4

## Problem

Todo 405 slice 4 repointed the security path lists from the removed
`/api/auth/...` to `/api/v1/auth/...`. Both middlewares had matched nothing
since clients moved to `/api/v1/`, so their code paths are **live for the first
time**. Review (bundled `/code-review`, round 1) raised these non-blocking
findings. The two blockers were fixed in the slice: comments rendered through
`innerHTML`, and register 400s or CSRF 403s counted as failed logins.

1. **The username is probably never captured** (hypothesis, not verified).
   `SecurityMiddleware._post_request_tracking` (`apps/core/security.py`) sees a
   Django `WSGIRequest`, not DRF's `Request`:
   - `request.data` is absent;
   - `request.POST` is empty for JSON bodies;
   - DRF has already read the stream.

   So every tracked failure and brute-force alert records `username=None`.
   Verify with a JSON login 401, then fix it: have the login view report the
   username, or cache the body before DRF reads it.
2. **`SecurityMetricsMiddleware._track_security_metric`**
   (`apps/core/middleware.py`) rewrites one cache key per endpoint and method,
   holding a growing `unique_ips` set, on every login, register, logout and
   token refresh.
   - The 24h TTL resets on each write, so under steady traffic the key never
     expires.
   - The read-modify-write loses updates under concurrency.
   - Raw IPs are kept indefinitely.
   - Nothing reads the key (`get_security_metrics()` doesn't).

   Use `cache.incr` counters with a bounded structure, or drop the write.
3. **Mobile sign-in is not covered.** `/api/v1/auth/firebase-token-exchange/`
   (every mobile sign-in) is in neither list.
4. **The lists are hand-maintained URL literals**, which is how they drifted
   before. A pin test now requires every entry to be a real route. Matching
   `request.resolver_match.view_name` against route names would remove the
   drift outright. The tuples also belong in `apps/core/constants.py`, per the
   backend "no hardcoded config" convention.
5. **`backend/static/blog/js/plant_block_autopop.js`** hardcodes the removed
   `/api/blog-api/plant-lookup|plant-suggestions|ai-content/`. Nothing loads the
   file (no `insert_editor_js` hook or template reference), so delete it.
   Also stale: the `api_schema.py:23` docstring, and
   `test_ip_spoofing_protection.py:250/264`, which build requests for
   `/api/auth/login/`. The path does not affect those tests.
6. **`BlogSeriesSerializer.posts_url`** hardcodes `v1:`.
   `rest_framework.reverse.reverse("blog:blog-series-posts", ..., request=request)`
   would follow `request.version` and return an absolute URI.

## Acceptance Criteria

- [ ] Tracked failed logins carry the attempted username, and a test asserts
      the argument.
- [ ] The security-metrics write is bounded (or removed), with a test.
- [ ] The Firebase token exchange is covered by tracking, or its exclusion is
      stated.
- [ ] Items 4–6 are done, or each is closed with a reason.

## Work Log

### 2026-09-23 - Filed from the todo 405 slice 4 code review

Round 1 of bundled `/code-review`: 10 findings. Two were blocking and fixed in
the slice PR; findings 3–8 are collected here. Finding 9 (the template-fetch
test did not pin the `pk` kwarg) was a one-line test fix, done in the slice.
