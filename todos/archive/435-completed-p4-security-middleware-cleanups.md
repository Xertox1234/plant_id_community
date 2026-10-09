---
status: completed
priority: p4
issue_id: "435"
tags: [backend, security, cleanup]
dependencies: []
source_review: "PR #818"
triage: ready
triaged: 2026-10-02
owner_decision: "Finding 5: pseudonymize the IP in the log line only; the brute-force alert email keeps the raw IP so operators can block it (2026-10-02)"
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

- **Raw IP in the failed-login warning and alert** (round 2).
  `track_failed_login` pseudonymizes the identifier but still logs
  `ip_address` raw; the rest of the file uses `log_safe_ip`. Predates #818.

## Acceptance Criteria

- [x] Each finding is fixed with a test, or declined with a reason.

## Work Log

### 2026-09-24 - Filed from PR #818 review round 1

### 2026-10-02 - Implemented by the todo sweep (run 2026-10-02-0335)

- Finding 1 (and 4, which it makes moot): the login view calls
  `SecurityMonitor.track_failed_login(ip, username)` at its failed-login
  point, with the identifier it already resolved (`username` or `email`).
  `SecurityMiddleware` lost the body pre-read, `_post_request_tracking`,
  `_attempted_username` and `MAX_TRACKED_USERNAME_LENGTH`;
  `FAILED_AUTH_TRACKED_PATHS` is deleted, since only that branch read it. One
  deliberate semantic shift: the middleware counted 401 responses, so the
  attempt that crosses the lockout threshold (a 429) was never counted; the
  view counts every rejected credential, that one included. The early returns
  for an already-locked or disabled account never check the password and stay
  uncounted, as before. The control-character stripping moved into
  `track_failed_login` (the sink that logs); the length cap went with the
  extractor, because the pseudonym is bounded. The Firebase exchange's
  exclusion and its reasons moved to the tracker's docstring, pinned over HTTP
  by `test_rejected_token_is_not_counted_as_a_failed_login` in
  `apps/users/tests/test_firebase_auth.py`, the file that already owns
  Firebase init.
- Finding 2: `SecurityMetricsMiddleware._track_security_metric` dropped its
  unused `method` and `ip_address` parameters and the IP resolution behind
  them. Tests: `test_security_metrics_middleware_logs_a_slow_request` (the
  kept behaviour) and `..._does_not_resolve_the_client_ip` (an invalid
  X-Forwarded-For entry no longer logs a second "Invalid IP" WARNING; the test
  first proves the resolver would warn on that request).
- Finding 3: both modules import their constants unconditionally; the
  `except ImportError` fallbacks are gone.
  `test_security_modules_import_their_constants_unconditionally` walks both
  modules' AST for an `ImportError` handler.
- Finding 5 (owner decision 2026-10-02): the failed-login warning logs
  `log_safe_ip(ip)`; the `brute_force_login` alert payload keeps the raw IP.
  That payload is what `_trigger_security_alert` logs at ERROR and caches;
  nothing emails it today. Test:
  `test_failed_login_warning_pseudonymizes_the_ip_but_the_alert_keeps_it`.
- Existing tests edited because each pinned the removed mechanism, each
  replaced by a pin of the behaviour:
  `test_attempted_username_is_stripped_of_control_characters` ->
  `test_failed_login_tracker_strips_control_characters`;
  `test_middleware_keeps_the_username_when_the_view_consumes_the_stream` ->
  `test_security_middleware_does_not_read_the_login_body` (and
  `test_rejected_v1_login_is_tracked`'s `assert_called_once_with` now also
  rules out a second, middleware count of the same 401);
  `test_firebase_exchange_is_deliberately_untracked` -> the HTTP test above;
  `test_every_listed_path_is_a_real_route` iterates only
  `SECURITY_SENSITIVE_PATHS`. Mutation-checked: removing the view call, the
  stripping or the `log_safe_ip` call each turns its test red.

### 2026-10-02 - Verified by the todo sweep (run 2026-10-02-0335)

- AC 1: `cd backend && python3 scripts/todos/slot_env.py 1 -- backend/venv/bin/python -m pytest apps/core/tests/test_legacy_api_mount_removed.py "apps/users/tests/test_firebase_auth.py::FirebaseTokenExchangeTestCase::test_rejected_token_is_not_counted_as_a_failed_login" apps/users/tests/test_account_lockout.py apps/users/tests/test_ip_spoofing_protection.py --create-db` — evidence `.sweep-evidence/g1/435-ac0.txt` (not committed), last lines:

  ```text
    backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ============= 58 passed, 3 warnings, 25 subtests passed in 30.39s ==============
  ```

### 2026-10-02 - Completed by the todo sweep (run 2026-10-02-0335)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
