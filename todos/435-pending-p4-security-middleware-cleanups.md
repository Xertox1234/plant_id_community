---
status: pending
priority: p4
issue_id: "435"
tags: [backend, security, cleanup]
dependencies: []
source_review: "PR #818"
---

# Security middleware cleanups from the todo 419 review

## Problem

The bundled `/code-review` of PR #818 raised these as non-blocking.

## Findings

- **Wrong depth for the username.** `SecurityMiddleware` pre-reads and
  re-parses the login body to recover an identifier the login view already
  resolved (`request.data.get('username') or request.data.get('email')`).
  Calling `SecurityMonitor.track_failed_login(ip, identifier)` from the view,
  and dropping the middleware's 401 branch, removes the pre-read, the second
  JSON parse and the field-name drift in one step.
- **Unused parameters.** With the cache write gone,
  `SecurityMetricsMiddleware._track_security_metric` ignores `ip_address` and
  `method`, but the caller still computes the IP (and `_get_client_ip` logs a
  WARNING per invalid X-Forwarded-For entry, duplicating SecurityMiddleware's).
- **Dead fallback.** The unconditional `from .constants import ...` lines
  added in todo 419 sit above the `try: from .constants import ... except
  ImportError:` blocks in `security.py` and `middleware.py`, so the fallbacks
  can never run. Delete them or fold the new names in.
- **Pre-read before the rate limiter.** The body is buffered before the
  view's `ratelimit` decorator rejects a request. Moot if the first finding
  lands.

## Acceptance Criteria

- [ ] Each finding is fixed with a test, or declined with a reason.

## Work Log

### 2026-09-24 - Filed from PR #818 review round 1
