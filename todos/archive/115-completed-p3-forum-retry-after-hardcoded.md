---
status: completed
priority: p3
issue_id: "115"
tags: [forum, backend, api, rate-limiting]
dependencies: []
---

# Retry-After response header hardcoded to 3600 — wrong for sub-minute rate limits

## Problem

`backend/apps/core/exceptions.py` line 76: `response['Retry-After'] = '3600'` is set
unconditionally for every `Ratelimited` exception. The comment confirms the value was
only considered for the upload endpoint (`20/h`). However, forum rate limits include
windows as short as 1 minute (`react: 60/m`, `search: 30/m`).

A client hitting the search rate limit receives `Retry-After: 3600` (1 hour) instead
of ~60 seconds, causing RFC 7231-compliant clients to back off 60× longer than needed.

## Recommended Action

Derive the `Retry-After` value from the rate limit window, not a hardcoded constant.
`django-ratelimit` stores the rate string on the exception: `exc.rate` (e.g. `'30/m'`).

```python
def _retry_after_seconds(rate: str) -> int:
    """Convert a ratelimit rate string (e.g. '30/m', '20/h') to window seconds."""
    if rate.endswith('/m'):
        return 60
    elif rate.endswith('/h'):
        return 3600
    elif rate.endswith('/d'):
        return 86400
    return 3600  # safe fallback

# In the handler:
response['Retry-After'] = str(_retry_after_seconds(getattr(exc, 'rate', '1/h')))
```

## Acceptance Criteria

- [x] `Retry-After` reflects the actual rate limit window (60s for `/m`, 3600s for `/h`).
- [x] A search rate-limit response returns `Retry-After: 60`, not `3600`.

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.

### 2026-05-28 - Completed by completing-todos skill (run 2026-05-28-2019)

**Todo's premise was wrong.** It assumed `exc.rate` exists, but django-ratelimit
4.1.0's `Ratelimited` is a bare exception and the decorator discards the rate
(keeps only `request.limited`). So the rate had to be captured at the decorator
site. Verified against the installed package.

Changes:
- NEW `apps/core/ratelimit.py`: a drop-in `ratelimit` wrapper that re-raises
  `RatelimitedWithRate(Ratelimited)` carrying `.rate` (preserves all behavior;
  django-ratelimit sets `request.limited` before raising, so counting is intact).
- `apps/core/exceptions.py`: `_retry_after_seconds(rate)` helper (`/s`→1, `/m`→60,
  `/h`→3600, `/d`→86400, else 3600); the (only reachable) Ratelimited handler now
  sets `Retry-After` from `getattr(exc, 'rate', None)`. Bare Ratelimited from other
  apps still falls back to 3600 — no regression.
- `apps/forum_integration/api_views.py`: one-line import swap to the wrapper, so
  all forum decorators benefit uniformly (incl. 106-109).
- Tests: search (30/m) asserts `Retry-After == '60'`; new
  `test_retry_after_reflects_hourly_window` (create_topic 10/h) asserts `'3600'`.
  The /m=60 assertion proves the value is *derived* (60 ≠ the 3600 fallback).

Verification: `apps.forum_integration apps.core` → `Ran 131 tests ... OK` (x2).

Review (feature-dev:code-reviewer): 0 critical/high. Confirmed wrapper correctness,
`request.limited`/counting preserved, isinstance chain intact, import blast-radius
safe (6 other apps unaffected). Low finding — **fixed**: added an `isinstance(rate,
str)` guard in `_retry_after_seconds` so a (hypothetical) callable rate can't turn a
429 into a 500 inside the handler.

**Test flakiness fixed (found during verification):** the hammer-to-limit rate-limit
tests (this one's search assertion, the 106-109 tests via the shared helper, and the
new /h test) could flake when django-ratelimit's jittered 60s window rolled over
mid-hammer (reproduced once in a long combined run: 200≠429). Wrapped every hammer in
`freeze_time(...)` (freezegun, already a dep) so all requests share one window —
deterministic. This also hardens the pre-existing search test.
