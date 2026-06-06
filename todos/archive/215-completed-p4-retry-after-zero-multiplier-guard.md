---
status: completed
priority: p4
issue_id: "215"
tags: [backend, rate-limiting, tech-debt]
dependencies: []
source_review: "PR #341 review (todo-sweep 206-210)"
source_finding: "review nit — zero-multiplier Retry-After"
---

# Guard `_retry_after_seconds` against a zero/negative multiplier

## Problem

The L5 rewrite of `apps/core/exceptions.py::_retry_after_seconds` parses the
numeric multiplier in a rate window, but a zero multiplier slips through:

```python
_retry_after_seconds("5/0m")  # -> 0  (count=0 * 60)
```

A `Retry-After: 0` tells the client to retry immediately, which defeats the
rate limit. This is **latent** — no configured rate uses a `0` window — so it is
a hardening nit, not a live bug.

## Recommended Action

In `_retry_after_seconds`, treat a non-positive parsed `count` as invalid and
fall back to the safe default (one hour) — same branch as an unparseable
multiplier:

```python
count = int(multiplier) if multiplier else 1
if count <= 0:
    return 3600
return count * unit_seconds
```

(`try/except ValueError` already returns 3600; fold `count <= 0` into the same
fallback.)

## Technical Details

- File: `backend/apps/core/exceptions.py` (`_retry_after_seconds`).
- Tests: `backend/apps/core/tests/test_retry_after.py` — add a case asserting
  `_retry_after_seconds("5/0m")` returns `3600` (or whatever the chosen sane
  floor is), alongside the existing fallback cases.

## Acceptance Criteria

- [x] `_retry_after_seconds("5/0m")` returns a positive value (>= one unit
      window / `3600`), never `0`.
- [x] A regression case in `test_retry_after.py` covers it; existing cases stay
      green.

## Work Log

### 2026-06-05 - Filed

- Surfaced in the PR #341 (`/review`) pass as a 🟢 minor nit. Non-blocking; no
  configured rate hits this path today.

### 2026-06-05 - Started by completing-todos skill (run 2026-06-05-2256)

- Picked up by automated workflow.

### 2026-06-05 - Implemented

- `apps/core/exceptions.py::_retry_after_seconds`: added `if count <= 0: return
  3600` immediately after the `int()` parse, folding a zero/negative multiplier
  into the same safe 1-hour fallback as an unparseable one (the todo's
  recommended option). Covers `"5/0m"` and defensively `"5/-1m"`.
- `apps/core/tests/test_retry_after.py`: added
  `test_non_positive_multiplier_falls_back_to_one_hour` asserting both `"5/0m"`
  and `"5/-1m"` return `3600`.

**Verification — full suite green (existing cases stay green):**

```
$ python manage.py test apps.core.tests.test_retry_after --keepdb
Ran 4 tests in 0.000s
OK
```

**Verification — criterion 1 (direct return values, never 0):**

```
5/0m  -> 3600
5/-1m -> 3600
5/15m -> 900     # non-degenerate windows unaffected
30/m  -> 60
```

### 2026-06-05 - Code review

- Reviewed via api-design + security + test-quality lenses (code-review-
  orchestrator routing). The guard was confirmed correct and complete: placed
  after the `int()` parse and before the multiply, it intercepts every zero/
  negative path (`5/0m`, `5/-1m`, and the same across `s`/`h`/`d`) while leaving
  valid windows untouched; after the guard `count >= 1` and all unit values are
  positive, so no input can yield `Retry-After <= 0`. The rate string is
  developer `@ratelimit` config, not request input — not attacker-injectable.
- 0 blocking findings.

**Known issues (non-blocking, out of scope):**

- [low] `_retry_after_seconds` has no *upper* bound on the multiplier
  (`5/<huge>m` → an absurd-but-RFC-valid `Retry-After`). This is **pre-existing**
  (the multiply predates this change, which only adds the `count <= 0` guard) and
  config-only. Left as-is to keep this todo surgical; capture separately if ever
  worth bounding (`min(count * unit_seconds, 86400)`).

### 2026-06-05 - Completed by completing-todos skill (run 2026-06-05-2256)

- Verification: both acceptance criteria passed (`5/0m`/`5/-1m` → 3600; new
  regression test green; existing 3 cases stay green).
- Review: 1 finding total, 0 blocking (1 low, pre-existing + out of scope —
  recorded under Known issues, not addressed).

## Notes

p4 — defensive hardening of a fallback helper. Trivial fix + one test case.
