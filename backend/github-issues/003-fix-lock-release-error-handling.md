# fix: Add error handling for distributed lock release failures

## Overview

⚠️ **HIGH** - Distributed lock release operations can throw exceptions, but errors are not caught or logged in the `finally` block, leading to silent failures that mask lock cleanup problems in production.

**Severity:** HIGH (Data Integrity Risk)
**Category:** Data Integrity / Error Handling
**Impact:** Silent lock release failures, invisible lock contention issues, difficult debugging
**Timeline:** Fix within 7 days

## Problem Statement / Motivation

**Current State:**
```python
# File: /backend/apps/plant_identification/services/plant_id_service.py:209-212
finally:
    # Always release lock
    lock.release()  # ← Can throw exception if lock expired or connection lost
    logger.info(f"[LOCK] Released lock for {image_hash[:8]}... (id: {lock_id})")
```

**Problem:**
If `lock.release()` throws an exception, the `logger.info` line never executes, and the error is silently swallowed by the `finally` block. This creates several issues:

1. **No visibility**: Lock release failures are invisible in production logs
2. **Debug difficulty**: Impossible to diagnose lock contention without error logs
3. **False assumptions**: Code assumes lock was released when it may have failed

**Exception Scenarios:**
- `redis.exceptions.LockNotOwnedError`: Lock already expired or released
- `redis.exceptions.ConnectionError`: Redis connection lost
- `redis.exceptions.TimeoutError`: Redis unresponsive
- General `Exception`: Unexpected errors

**Why This Matters:**
- Locks auto-expire after 30s (CACHE_LOCK_EXPIRE), so failures don't cause deadlocks
- However, silent failures hide problems:
  - Redis connection issues
  - Lock contention patterns
  - Performance degradation
- Without logs, impossible to diagnose production issues

## Proposed Solution

**Option 1: Catch and Log All Lock Release Errors (RECOMMENDED)**

```python
# File: /backend/apps/plant_identification/services/plant_id_service.py:209-212

finally:
    try:
        lock.release()
        logger.info(f"[LOCK] Released lock for {image_hash[:8]}... (id: {lock_id})")
    except Exception as e:
        logger.error(
            f"[LOCK] Failed to release lock for {image_hash[:8]}...: {e}. "
            f"Lock will auto-expire after {CACHE_LOCK_EXPIRE}s (from constants.py:209)"
        )
        # Don't raise - lock will auto-expire, no need to crash the request
```

**Option 2: Enhanced Error Handling with Specific Exception Types**

```python
import redis.exceptions

finally:
    try:
        lock.release()
        logger.info(f"[LOCK] Released lock for {image_hash[:8]}... (id: {lock_id})")
    except redis.exceptions.LockNotOwnedError:
        # Lock already expired or released by another process
        logger.warning(
            f"[LOCK] Lock for {image_hash[:8]}... already released "
            f"(expired after {CACHE_LOCK_EXPIRE}s or released by another process)"
        )
    except redis.exceptions.ConnectionError as e:
        # Redis connection lost during lock release
        logger.error(
            f"[LOCK] Redis connection lost during lock release for {image_hash[:8]}...: {e}. "
            f"Lock will auto-expire after {CACHE_LOCK_EXPIRE}s"
        )
    except redis.exceptions.TimeoutError as e:
        # Redis timed out during lock release
        logger.error(
            f"[LOCK] Redis timeout during lock release for {image_hash[:8]}...: {e}. "
            f"Lock will auto-expire after {CACHE_LOCK_EXPIRE}s"
        )
    except Exception as e:
        # Unexpected error during lock release
        logger.error(
            f"[LOCK] Unexpected error releasing lock for {image_hash[:8]}...: {e}. "
            f"Lock will auto-expire after {CACHE_LOCK_EXPIRE}s",
            exc_info=True  # Include full traceback for debugging
        )
```

**Option 3: With Prometheus Metrics (Future Enhancement)**

```python
from prometheus_client import Counter

lock_release_errors = Counter(
    'lock_release_errors_total',
    'Total lock release failures',
    ['service', 'error_type']
)

finally:
    try:
        lock.release()
        logger.info(f"[LOCK] Released lock for {image_hash[:8]}...")
    except redis.exceptions.LockNotOwnedError:
        logger.warning(f"[LOCK] Lock already released for {image_hash[:8]}...")
        lock_release_errors.labels(service='plant_id', error_type='lock_not_owned').inc()
    except redis.exceptions.ConnectionError as e:
        logger.error(f"[LOCK] Redis connection lost: {e}")
        lock_release_errors.labels(service='plant_id', error_type='connection').inc()
    except Exception as e:
        logger.error(f"[LOCK] Unexpected error: {e}", exc_info=True)
        lock_release_errors.labels(service='plant_id', error_type='unknown').inc()
```

## Technical Considerations

**Auto-Expiry Safety Net:**
- Locks auto-expire after 30 seconds (CACHE_LOCK_EXPIRE from constants.py:209)
- Even if `lock.release()` fails, lock won't be held indefinitely
- This is a **safety mechanism**, not an excuse to ignore failures

**Impact on Application:**
- Lock release failures don't crash the request (caught in finally block)
- Application continues serving requests normally
- Only observability is affected (logs, metrics)

**Redis Connection Patterns:**
- Connection pool managed by django-redis
- Transient connection errors are normal and expected
- Persistent connection errors indicate Redis issues needing attention

**Error Types by Severity:**
- `LockNotOwnedError`: **WARNING** (expected, lock expired naturally)
- `ConnectionError`: **ERROR** (Redis infrastructure issue)
- `TimeoutError`: **ERROR** (Redis performance issue)
- `Exception`: **ERROR** (unexpected, needs investigation)

## Acceptance Criteria

**Code Changes:**
- [ ] Lock release wrapped in try/except in plant_id_service.py:209-212
- [ ] All lock release errors logged at appropriate level (WARNING/ERROR)
- [ ] Log messages include lock expiry timeout (30s)
- [ ] Different exception types handled appropriately
- [ ] Same pattern applied to PlantNet service (when distributed locks added)

**Error Messages:**
- [ ] Include image hash (first 8 characters) for request tracing
- [ ] Include lock expiry timeout (CACHE_LOCK_EXPIRE) for context
- [ ] Include exception details for debugging
- [ ] Use bracketed [LOCK] prefix for log filtering

**Testing:**
- [ ] Unit test: Mock lock.release() to raise LockNotOwnedError
  ```python
  def test_lock_release_already_released(self):
      with patch.object(lock, 'release', side_effect=redis.exceptions.LockNotOwnedError()):
          result = service.identify_plant(image_file)
          # Should log warning but not crash
          assert result is not None
  ```

- [ ] Unit test: Mock lock.release() to raise ConnectionError
  ```python
  def test_lock_release_connection_error(self):
      with patch.object(lock, 'release', side_effect=redis.exceptions.ConnectionError("Connection lost")):
          result = service.identify_plant(image_file)
          # Should log error but not crash
          assert result is not None
  ```

- [ ] Unit test: Verify lock release success is logged
  ```python
  def test_lock_release_success(self):
      result = service.identify_plant(image_file)
      assert "[LOCK] Released lock" in caplog.text
  ```

- [ ] Integration test: Verify auto-expiry works even if release fails
  ```python
  def test_lock_auto_expiry(self):
      # Acquire lock and force failure
      # Wait CACHE_LOCK_EXPIRE seconds
      # Verify lock is auto-released
  ```

**Documentation:**
- [ ] Lock error handling documented in /backend/docs/quick-wins/distributed-locks.md
- [ ] Troubleshooting section added with common lock errors
- [ ] Monitoring guidance added (what to alert on)

## Success Metrics

**Immediate (Within 7 days):**
- ✅ Zero silent lock release failures (all errors logged)
- ✅ Lock release error rate < 1% (measured from logs)
- ✅ No application crashes from lock release errors

**Long-term (Within 30 days):**
- 📋 Prometheus metrics for lock release errors (Option 3)
- 📋 Alerting for persistent lock release failures (>5% error rate)
- 📋 Dashboard showing lock contention patterns

## Dependencies & Risks

**Dependencies:**
- python-redis-lock library (already installed)
- Redis running and accessible (already configured)

**Risks:**
- **Low:** Error handling adds minor complexity
  - **Mitigation:** Well-documented exception types
  - **Mitigation:** Unit tests verify error handling

- **Low:** Increased log volume from lock errors
  - **Mitigation:** Use WARNING for expected errors (LockNotOwnedError)
  - **Mitigation:** Use ERROR only for unexpected failures
  - **Mitigation:** Log rotation configured to handle volume

## References & Research

### Internal References
- **Code Review Finding:** data-integrity-guardian agent (Finding #1)
- **Data Integrity Audit:** `/backend/docs/development/DATA_INTEGRITY_REVIEW.md`
- **Distributed Locks Implementation:** `/backend/apps/plant_identification/services/plant_id_service.py:118-248`
- **Quick Win #4 Documentation:** `/backend/docs/quick-wins/distributed-locks.md`
- **Constants:** `/backend/apps/plant_identification/constants.py:209` (CACHE_LOCK_EXPIRE)

### External References
- **python-redis-lock Documentation:** https://python-redis-lock.readthedocs.io/
- **Redis Distributed Locks:** https://redis.io/docs/manual/patterns/distributed-locks/
- **Martin Fowler - Patterns of Distributed Systems:** https://martinfowler.com/articles/patterns-of-distributed-systems/
- **Best Practices for Lock Error Handling:** https://redislabs.com/ebook/part-2-core-concepts/chapter-6-application-components-in-redis/6-2-distributed-locking/

### Related Work
- **Issue #004:** File upload validation (also uses finally blocks)
- **Git commit:** b4819df (Week 3 Quick Wins - Distributed locks implementation)
- **Performance:** 90% reduction in duplicate API calls (documented impact of locks)

---

**Created:** 2025-10-22
**Priority:** ⚠️ HIGH
**Assignee:** @williamtower
**Labels:** `priority: high`, `type: bug`, `area: backend`, `week-3`, `code-review`, `data-integrity`
**Estimated Effort:** 30 minutes (code changes) + 30 minutes (testing)
