---
status: ready
priority: p3
issue_id: "015"
tags: [security, cookies, ux]
dependencies: []
---

# Fix Session Cookie SameSite Too Strict

**CVSS**: 4.3 (Medium)

## Problem

`SESSION_COOKIE_SAMESITE = 'Strict'` breaks external navigation (email links, social media).

## Solution

Change to 'Lax' (maintains CSRF protection):
```python
SESSION_COOKIE_SAMESITE = 'Lax'  # Allows top-level navigation
```

**Effort**: 5 minutes
