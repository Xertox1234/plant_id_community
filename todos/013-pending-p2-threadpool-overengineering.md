---
status: ready
priority: p2
issue_id: "013"
tags: [code-review, simplification, optional]
dependencies: []
---

# Simplify ThreadPoolExecutor (Optional)

## Problem

77 lines for 2-worker thread pool with double-checked locking, CPU detection, validation - but only 2 APIs ever called.

## Simplification Option

```python
# Current: 77 lines
# Proposed: 3 lines
class CombinedPlantIdentificationService:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
```

**Trade-off**: Lose configurability, gain simplicity  
**Effort**: 30 minutes  
**Decision**: OPTIONAL (current works fine, just complex)
