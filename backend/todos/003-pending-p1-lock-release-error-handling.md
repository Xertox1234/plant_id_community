---
status: pending
priority: p1
issue_id: "003"
tags: [data-integrity, distributed-locks, error-handling]
dependencies: []
---

# Fix Lock Release Error Handling (CRITICAL)

## Problem Statement

Lock release in `finally` block can throw exceptions, but errors are not caught or logged:

```python
# plant_id_service.py:209-212
finally:
    # Always release lock
    lock.release()  # ← Can throw exception if lock expired or connection lost
    logger.info(f"[LOCK] Released lock for {image_hash[:8]}... (id: {lock_id})")
```

**Impact:**
- If lock.release() fails, the logger.info line never executes
- Silent failures mask lock cleanup problems
- No visibility into lock release failures in production
- Locks auto-expire after 30s, but failures are invisible

## Findings

- Discovered during data integrity review by data-integrity-guardian agent
- Location: `/backend/apps/plant_identification/services/plant_id_service.py:209-212`
- Similar pattern in PlantNet service (when distributed locks added)
- Risk Level: CRITICAL (silent failures)

## Proposed Solutions

### Option 1: Catch and Log Lock Release Errors (RECOMMENDED)
- **Pros**: Visibility into lock failures, doesn't crash application
- **Cons**: Lock may remain held (but will auto-expire after 30s)
- **Effort**: Small (15 minutes)
- **Risk**: Low (improves observability)

**Implementation:**
```python
# plant_id_service.py:209-212
finally:
    try:
        lock.release()
        logger.info(f"[LOCK] Released lock for {image_hash[:8]}... (id: {lock_id})")
    except Exception as e:
        logger.error(
            f"[LOCK] Failed to release lock for {image_hash[:8]}...: {e}. "
            f"Lock will auto-expire after {CACHE_LOCK_EXPIRE}s"
        )
        # Don't raise - lock will auto-expire
```

### Option 2: Enhanced Error Handling with Metrics
- **Pros**: Visibility + metrics for alerting
- **Cons**: Requires Prometheus integration
- **Effort**: Medium (30 minutes with existing metrics setup)
- **Risk**: Low

**Implementation:**
```python
from prometheus_client import Counter

lock_release_errors = Counter('lock_release_errors_total', 'Lock release failures', ['service'])

finally:
    try:
        lock.release()
        logger.info(f"[LOCK] Released lock for {image_hash[:8]}...")
    except redis.exceptions.LockNotOwnedError:
        # Lock already expired or released by another process
        logger.warning(f"[LOCK] Lock for {image_hash[:8]}... already released (expired?)")
        lock_release_errors.labels(service='plant_id').inc()
    except redis.exceptions.ConnectionError as e:
        # Redis connection lost
        logger.error(f"[LOCK] Redis connection lost during lock release: {e}")
        lock_release_errors.labels(service='plant_id').inc()
    except Exception as e:
        logger.error(f"[LOCK] Unexpected error releasing lock: {e}")
        lock_release_errors.labels(service='plant_id').inc()
```

## Recommended Action

**Implement Option 1** immediately (15 minutes)
**Upgrade to Option 2** when Prometheus metrics are added (Phase 2)

## Technical Details

- **Affected Files**:
  - `/backend/apps/plant_identification/services/plant_id_service.py:209-212`
  - `/backend/apps/plant_identification/services/plantnet_service.py` (when locks added)

- **Related Components**:
  - Redis distributed locks (python-redis-lock library)
  - Cache stampede prevention
  - API quota protection

- **Lock Auto-Expiry**: 30 seconds (CACHE_LOCK_EXPIRE in constants.py:209)

- **Database Changes**: No

## Resources

- Data integrity audit: `/backend/docs/development/DATA_INTEGRITY_REVIEW.md`
- Agent report: data-integrity-guardian (Finding #1)
- python-redis-lock docs: https://python-redis-lock.readthedocs.io/

## Acceptance Criteria

- [ ] Lock release wrapped in try/except block
- [ ] Lock release failures logged at ERROR level
- [ ] Log message includes lock expiry timeout (30s)
- [ ] Different exception types handled appropriately (LockNotOwnedError, ConnectionError)
- [ ] Tests verify lock release error handling
- [ ] Applied to both plant_id_service.py and plantnet_service.py

## Work Log

### 2025-10-22 - Code Review Discovery
**By:** data-integrity-guardian agent
**Actions:**
- Discovered unhandled lock release exceptions during data integrity audit
- Analyzed impact of silent failures
- Categorized as CRITICAL priority (data integrity risk)

**Learnings:**
- Always wrap cleanup operations in try/except, even in finally blocks
- Log all failures with appropriate severity level
- Include auto-recovery information in error messages (lock auto-expires)
- Consider metrics for alerting on repeated lock failures

## Notes

**Urgency:** CRITICAL - Fix within 24 hours
**Deployment:** No environment changes needed
**Testing:**
```python
# Test case: Mock lock.release() to raise exception
with patch.object(lock, 'release', side_effect=redis.exceptions.ConnectionError("Connection lost")):
    # Verify error is logged but doesn't crash
    result = service.identify_plant(image_file)
```

**Auto-Expiry Safety:**
Locks automatically expire after 30s (CACHE_LOCK_EXPIRE), so even if release fails, lock won't be held indefinitely. This is a safety mechanism, not an excuse to ignore failures.
