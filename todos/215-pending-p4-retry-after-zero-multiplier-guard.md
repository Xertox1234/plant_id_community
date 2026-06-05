---
status: pending
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

- [ ] `_retry_after_seconds("5/0m")` returns a positive value (>= one unit
      window / `3600`), never `0`.
- [ ] A regression case in `test_retry_after.py` covers it; existing cases stay
      green.

## Work Log

### 2026-06-05 - Filed

- Surfaced in the PR #341 (`/review`) pass as a 🟢 minor nit. Non-blocking; no
  configured rate hits this path today.

## Notes

p4 — defensive hardening of a fallback helper. Trivial fix + one test case.
