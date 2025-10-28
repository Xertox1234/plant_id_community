---
status: ready
priority: p2
issue_id: "012"
tags: [security, cors, configuration]
dependencies: []
---

# Fix CORS Allow All Origins in DEBUG Mode

**CVSS**: 7.5 (High)

## Problem

`CORS_ALLOW_ALL_ORIGINS = True` in DEBUG mode accepts requests from ANY origin with credentials.

## Solution

Whitelist specific dev origins even in DEBUG:
```python
if DEBUG:
    CORS_ALLOWED_ORIGINS = [
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'http://localhost:5174',
        'http://127.0.0.1:5174',
    ]
    CORS_ALLOW_ALL_ORIGINS = False
```

**Effort**: 15 minutes
