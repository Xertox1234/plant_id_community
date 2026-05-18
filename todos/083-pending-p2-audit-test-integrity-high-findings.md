---
status: pending
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

- [ ] No `assertIn(status, [...])` over mutually-exclusive pass/fail states.
- [ ] No wall-clock `assertLess` on elapsed time.
- [ ] Affected suites pass with strict assertions.

## Work Log

### 2026-05-17 - Created

- Deferred from the 2026-05-17 full audit (Phase 4).
