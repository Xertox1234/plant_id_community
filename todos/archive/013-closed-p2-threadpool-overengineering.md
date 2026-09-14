---
status: closed
resolution: wont-fix
priority: p2
issue_id: "013"
tags: [code-review, simplification, optional, analyzed]
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

---

## Resolution: KEEP AS-IS (Won't Fix)

**Date**: 2025-10-27
**Decision**: After comprehensive analysis, keep the 77-line implementation

**Rationale**:
1. **Prevents resource leaks**: Django creates new service instances per request. Without singleton pattern, each request creates a new ThreadPoolExecutor with threads that persist after request completes (100 requests = 200 lingering threads)
2. **Production-ready**: Environment variable support (PLANT_ID_MAX_WORKERS) enables Kubernetes tuning
3. **Django pattern**: Follows same patterns as Django's connection pools and cache backends
4. **Test coverage**: 8 comprehensive tests validate thread safety, configuration, cleanup
5. **Future-proof**: Scales naturally via config if more than 2 APIs needed

**What appears as "over-engineering" is actually**:
- Thread-safe singleton (prevents race conditions)
- Input validation (prevents config errors)
- Cleanup hooks (prevents memory leaks)
- Logging (enables production debugging)
- Environment support (container compatibility)

**Cost of simplification**: 6+ hours to rewrite tests and validate, for negative value (introduces resource leak risks)

**Detailed analysis**: See `/todos/013-pending-p2-threadpool-analysis.md` (6,500 words)

**Status**: CLOSED - Current implementation is appropriately engineered, not over-engineered

## Work Log

### 2026-09-13 - Renamed (todo 390)

Renamed from `013-completed-p2-threadpool-overengineering.md`. The frontmatter is
authoritative and always said `status: closed` / `resolution: wont-fix`; the
filename claimed `completed`, which reads as "we did it" rather than "we decided
not to". Caught by `scripts/check_archived_todo_status.py` as the repo's only
FILENAME_OVERCLAIM.
