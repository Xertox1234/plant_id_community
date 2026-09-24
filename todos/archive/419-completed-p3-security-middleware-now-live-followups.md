---
status: completed
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

- [x] Tracked failed logins carry the attempted username, and a test asserts
      the argument.
- [x] The security-metrics write is bounded (or removed), with a test.
- [x] The Firebase token exchange is covered by tracking, or its exclusion is
      stated.
- [x] Items 4–6 are done, or each is closed with a reason.

## Work Log

### 2026-09-23 - Filed from the todo 405 slice 4 code review

Round 1 of bundled `/code-review`: 10 findings. Two were blocking and fixed in
the slice PR; findings 3–8 are collected here. Finding 9 (the template-fetch
test did not pin the `pk` kwarg) was a one-line test fix, done in the slice.

### 2026-09-24 - Done: items 1-5 fixed, item 6 closed with a reason

- **Item 1 (hypothesis confirmed, then fixed).** Before the change, a JSON
  login 401 reached `track_failed_login('127.0.0.1', None)`. Two causes: the
  extraction's `elif` chain gave up once the stream was read, and nothing
  guaranteed the body was still readable. `SecurityMiddleware` now reads
  `request.body` for a tracked auth POST before the view runs (Django caches
  it, DRF parses from the cache). `_attempted_username` then reads form or
  JSON, returns only a non-empty `str`, and caps it at 150 characters.
  Tests: `test_rejected_v1_login_is_tracked` now asserts `(ANY, "nobody")`
  and failed before; `test_middleware_keeps_the_username_when_the_view_consumes_the_stream`
  pins the pre-read itself, because the end-to-end test also passed with the
  pre-read removed (something upstream in the test client caches the body).
  Mutation, dropping the pre-read: the stream test goes red.
- **Item 2.** The `security_metrics:*` cache write is removed. Nothing read
  it, and it was unbounded (TTL reset per write, growing raw-IP set, lost
  updates). The middleware keeps only its slow-request warning. Test:
  `test_security_metrics_keep_no_per_endpoint_cache_state` failed before
  (the key held `unique_ips: ['127.0.0.1']`).
- **Item 3.** `/api/v1/auth/firebase-token-exchange/` is in both lists. Its
  401s count per IP (there is no username). Test:
  `test_rejected_firebase_token_exchange_is_tracked` failed before; mutation,
  dropping it from the tuple: red.
- **Item 4.** Both tuples moved to `apps/core/constants.py` (re-exported from
  their old modules). Matching `view_name` instead of literals: **not done**.
  The pin test already fails CI for any entry that isn't a real route, which
  is the drift this item was about; changing the matching strategy of two
  security middlewares is more risk than that residue is worth.
- **Item 5.** Deleted `backend/static/blog/js/plant_block_autopop.js`
  (`git grep` found no loader). Fixed the `api_schema.py` docstring and the
  two `/api/auth/login/` request paths in `test_ip_spoofing_protection.py`.
- **Item 6: closed, not changed.** `BlogSeriesSerializer.posts_url` reverses
  `v1:blog:blog-series-posts`. The route exists only under the `v1`
  namespace (v2 is Wagtail's), so following `request.version` changes
  nothing today. DRF's `reverse(..., request=request)` also falls back to
  the unversioned name when the request has no versioning scheme (the
  serializer's own test passes a plain `RequestFactory` request), and that
  name doesn't exist.
- `pytest apps/core apps/users --create-db`: 1580 passed. flake8 clean.

### 2026-09-24 - Review round 1 (bundled /code-review, PR #818): 4 repaired

- **Item 1 was fixed only for a client nobody uses.** The web posts
  `{email, password}`; the extractor read only `username`, so real web
  failures still tracked `None`. It now reads `username or email`. Test:
  `test_rejected_email_login_is_tracked_with_the_email` (red with the email
  fallback removed).
- **The identifier is attacker-controlled and was logged raw** (often an
  email: PII; a newline could forge a log line). `track_failed_login` now
  keeps only `log_safe_username(...)` in the log line, the cached attempts
  and the alert payload, and the extractor drops non-printable characters.
  Tests: `test_failed_login_logs_and_alerts_only_a_pseudonym`,
  `test_attempted_username_is_stripped_of_control_characters` (each red with
  its fix removed).
- **Item 3 reversed: the Firebase exchange is deliberately untracked.** It
  returns 401 for server-side failures too (Firebase init degrading, a cert
  fetch failing), so an outage like 2026-09-13's would count every mobile
  sign-in as a failed login, and a success never clears the per-IP counter.
  The exclusion and its reason are in `constants.py`, pinned by
  `test_firebase_exchange_is_deliberately_untracked`. This also removes the
  round-1 test that initialized the process-global Firebase app. The AC
  allows "or its exclusion is stated".
- **The metrics test checked one key shape.** A new test patches the
  middleware's `cache` and asserts no `set` at all.
- Deferred to todo 435: track failures from the login view instead of
  re-parsing the body; drop the unused `ip_address`/`method` params; the dead
  `ImportError` fallback in `security.py`/`middleware.py`; the body pre-read
  running before the view's rate limiter.
- `pytest apps/core apps/users --create-db`: 1585 passed.
