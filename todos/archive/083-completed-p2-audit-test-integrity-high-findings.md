---
status: completed
priority: p2
issue_id: "083"
tags: [testing, audit-2026-05-17]
dependencies: []
source_review: "docs/audits/2026-05-17-full.md"
source_finding: "H30,H31,H32,H33,H34,H36"
---

# Test-integrity High-severity audit findings

## Problem

Tests that cannot fail (or are flaky) from the 2026-05-17 full audit. A test that
accepts both the pass and the fail outcome verifies nothing — these are security-
and performance-critical paths. Full detail in `docs/audits/2026-05-17-full.md`.
(H35 is tracked separately in the forum backlog todo — `apps/forum/` is not
currently installed.)

## Findings

- **H30** — Rate-limiting tests `assertIn(status,[200,429])` — cannot fail.
  `apps/users/tests/test_rate_limiting.py:150`.
- **H31** — Account-lockout tests `assertIn(status,[401,403,429])` — cannot fail.
  `apps/users/tests/test_account_lockout.py:429,434,461`.
- **H32** — Token-refresh test `assertIn(status,[200,401])`.
  `apps/users/tests/test_token_refresh.py:220`.
- **H33** — AI-integration auth tests `assertIn(status,[302,403])` for two
  distinct security states. `apps/blog/tests/test_ai_integration.py:261,279`.
- **H34** — Wall-clock timing assertions (flaky under CI load).
  `apps/plant_identification/test_executor_caching.py:414,493`, `test_analytics.py:794`.
- **H36** — Popular-posts query-count `assertLessEqual(20)` tolerates a 6-query
  N+1 regression — should be `assertEqual`. `apps/blog/tests/test_analytics.py:521,545`.

## Recommended Action

For each test, pin the exact expected status/value. Determine the *correct*
behavior first (does the endpoint rate-limit / lock out / return 401?), then assert
that one outcome. Replace timing assertions (H34) with deterministic checks (call
ordering, cache-hit counts). Replace `assertLessEqual` query bounds with
`assertEqual` (H36).

## Acceptance Criteria

- [x] No `assertIn(status, [...])` over mutually-exclusive pass/fail states.
- [x] No wall-clock `assertLess` on elapsed time.
- [x] Affected suites pass with strict assertions.

## Work Log

### 2026-05-17 - Created

- Deferred from the 2026-05-17 full audit (Phase 4).

### 2026-05-21 - Started by completing-todos skill (run 2026-05-21-0238)

- Picked up by automated workflow (worked alongside 082's web subagent — no file overlap).

### 2026-05-21 - Fixes (behavior determined empirically by running each test)

- **H30 — fixed.** `test_rate_limiting`: the 6th login is deterministically 429
  (the `@ratelimit(5/15m)` decorator counts every login POST by IP, success or
  fail — confirmed by run). Changed `assertIn([200,429])` → `assertEqual(429)` and
  renamed the test/docstring (old name `..._not_rate_limited` asserted the opposite
  of the real behavior).
- **H31 — fixed.** `test_account_lockout::test_complete_lockout_flow_via_api`: the
  5/15m login rate limit was masking the lockout path (threshold 10), so the test
  could never actually exercise lockout. Added `@override_settings(RATELIMIT_ENABLE=False)`
  so the threshold is reachable, then pinned exact statuses: 401 for the first 9
  attempts, 429 + `code == 'ACCOUNT_LOCKED'` on the 10th, exactly 1 lockout email,
  and 429 + ACCOUNT_LOCKED for a subsequent correct-password attempt. (Also updated
  the trailing assertion to the flat error shape from todo 081's H13.)
- **H32 — fixed.** `test_token_refresh`: first 10 refreshes succeed within the 10/h
  limit — `assertIn([200,401])` → `assertEqual(200)`; 11th stays `assertEqual(429)`.
- **H33 — fixed.** `test_ai_integration`: `/blog-admin/api/generate-field-content/`
  is `@staff_member_required`, which redirects; both auth tests `assertIn([302,403])`
  → `assertEqual(302)` (confirmed by run).
- **H34 — fixed.** Replaced 3 wall-clock assertions: (1) the parallel-execution test
  now proves concurrency with a `threading.Barrier(2)` (sequential execution would
  break the barrier and empty the result) instead of `assertLess(elapsed, 0.18)`;
  (2) `test_cache_hit_is_instant` → `test_cache_hit_returns_stored_value` asserting
  the value round-trips, dropping `assertLess(cache_time, 0.01)`; (3) the trending
  EXPLAIN test drops `assertLess(exec_time_ms, 100)` and keeps the structural
  `assertIn("Execution Time:", ...)` check (time is logged, not asserted).
- **H36 — fixed.** Popular-posts query counts pinned exactly (measured by run):
  `assertLessEqual(20)` → `assertEqual(8)` (days=30) and `assertEqual(7)` (days=0).

Verification (`python manage.py test --keepdb`): test_rate_limiting 9 OK,
test_account_lockout 18 OK, test_token_refresh 20 OK, test_ai_integration 20 OK
(skipped=7), test_executor_caching 20 OK, test_analytics 26 OK.

Observation (not in scope, noted for backlog): the login endpoint rate-limits
successful logins too, and the 5/15m limit makes account lockout (threshold 10)
unreachable via the real `/auth/login/` endpoint — a possible product gap.

### 2026-05-21 - Code review + completion

- Code review (code-review-orchestrator → test-quality-reviewer): **no critical/high
  findings**. All strict assertions confirmed against source. One MEDIUM: the
  barrier concurrency test depended on the shared `ThreadPoolExecutor` having ≥2
  workers (would fail on a 1-CPU runner). **Repaired** — the test now recreates the
  executor with `PLANT_ID_MAX_WORKERS=2` and resets it via `addCleanup`;
  `test_executor_caching` re-run 20 OK.
- Manifest `docs/audits/2026-05-17-full.md` High table updated: H30/H31/H32/H33/
  H34/H36 → verified.

### 2026-05-21 - Completed by completing-todos skill (run 2026-05-21-0238)

- Verification: all 3 acceptance criteria passed (no `assertIn` over pass/fail
  states, no wall-clock `assertLess`, all 6 affected suites green with strict
  assertions).
- Review: test-quality review — 0 blocking findings; 1 MEDIUM (barrier worker-count)
  repaired.
