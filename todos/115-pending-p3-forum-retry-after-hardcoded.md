---
status: pending
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

- [ ] `Retry-After` reflects the actual rate limit window (60s for `/m`, 3600s for `/h`).
- [ ] A search rate-limit response returns `Retry-After: 60`, not `3600`.

## Work Log

### 2026-05-28 - Created

- Found during code review of feat/forum-web-modernization branch.
