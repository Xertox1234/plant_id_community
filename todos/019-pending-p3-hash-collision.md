---
status: ready
priority: p3
issue_id: "019"
tags: [performance, caching, low-probability]
dependencies: []
---

# Fix Blog Cache Hash Collision Risk

## Problem

16-character SHA-256 hash (64 bits) has birthday paradox collision after ~5 billion combinations.

## Solution

Use full 64-character hash:
```python
# Before
filters_hash = hashlib.sha256(...).hexdigest()[:16]
# After
filters_hash = hashlib.sha256(...).hexdigest()  # Full hash
```

**Effort**: 5 minutes  
**Risk**: Low probability but easy fix
