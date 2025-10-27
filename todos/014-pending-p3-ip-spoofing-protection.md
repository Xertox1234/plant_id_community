---
status: ready
priority: p3
issue_id: "014"
tags: [security, configuration]
dependencies: []
---

# Configure IP Spoofing Protection

**CVSS**: 5.3 (Medium)

## Problem

`USE_X_FORWARDED_HOST` not explicitly set - defaults may allow IP spoofing in rate limiting/account lockout.

## Solution

```python
# settings.py
USE_X_FORWARDED_HOST = False  # Dev
# Production: USE_X_FORWARDED_HOST = True with trusted proxy
```

**Effort**: 15 minutes
