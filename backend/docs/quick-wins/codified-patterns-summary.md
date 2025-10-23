# Codified Review Patterns - Week 3 Quick Wins

**Date:** 2025-10-22
**Reviewer Agent Updated:** code-review-specialist
**Source:** Week 3 Quick Wins implementation (authentication, circuit breakers, API versioning, distributed locks)

---

## Overview

This document summarizes the production-readiness patterns that have been codified into the `code-review-specialist` agent based on the Week 3 Quick Wins implementation. These patterns will now be automatically checked in all future Python/Django code reviews.

---

## Patterns Codified

### 1. Environment-Aware Permission Classes

**Pattern Extracted From:**
- File: `backend/apps/plant_identification/permissions.py`
- Documentation: `backend/docs/quick-wins/authentication.md`

**Review Check Added:**
- **Severity:** BLOCKER
- **Pattern:** Never use `AllowAny` in production without environment checks
- **Detection:** `grep -n "AllowAny" changed_file.py`
- **Validation:** Verify conditional uses `settings.DEBUG`

**Example from Implementation:**
```python
@permission_classes([
    IsAuthenticatedOrAnonymousWithStrictRateLimit if settings.DEBUG
    else IsAuthenticatedForIdentification
])
```

**Why This Matters:**
- Prevents API quota exhaustion from anonymous users
- Plant.id free tier: 100 IDs/month (can be exhausted in 1 day without protection)
- Production requires authentication to track and limit usage
- Development allows testing without authentication overhead

**Impact on Future Reviews:**
- All API endpoints with `AllowAny` will be flagged
- Reviewer will require environment-aware permission pattern
- Prevents accidental production exposure of expensive APIs

---

### 2. Circuit Breaker Pattern for External APIs

**Pattern Extracted From:**
- File: `backend/apps/plant_identification/services/plant_id_service.py:46-53, 199-205`
- File: `backend/apps/plant_identification/circuit_monitoring.py`
- Documentation: `backend/docs/quick-wins/circuit-breaker.md`

**Review Check Added:**
- **Severity:** BLOCKER
- **Pattern:** Wrap all external API calls with circuit breaker
- **Detection:** `grep -n "requests\.\(get\|post\|put\)" service_file.py`
- **Validation:** Verify circuit breaker usage and exception handling

**Example from Implementation:**
```python
# Module-level circuit breaker (singleton pattern)
_plant_id_circuit, _plant_id_monitor, _plant_id_stats = create_monitored_circuit(
    service_name='plant_id_api',
    fail_max=PLANT_ID_CIRCUIT_FAIL_MAX,
    reset_timeout=PLANT_ID_CIRCUIT_RESET_TIMEOUT,
)

# In service class
def __init__(self):
    self.circuit = _plant_id_circuit

# In API call method
result = self.circuit.call(
    self._call_plant_id_api,
    image_data,
    cache_key,
    image_hash
)
```

**Why This Matters:**
- **Performance:** 99.97% faster failure response (30s → <10ms)
- **Resilience:** Prevents cascading failures when external API is down
- **User Experience:** Fast-fail instead of 30s timeout
- **Resource Protection:** Prevents thread pool exhaustion

**Impact on Future Reviews:**
- All external API calls in service files will be checked
- Reviewer will require circuit breaker wrapper
- Must include `CircuitBreakerError` exception handling
- Module-level circuit breaker pattern will be enforced

---

### 3. Distributed Locks for Cache Stampede Prevention

**Pattern Extracted From:**
- File: `backend/apps/plant_identification/services/plant_id_service.py:163-228`
- Documentation: `backend/docs/quick-wins/distributed-locks.md`

**Review Check Added:**
- **Severity:** WARNING
- **Pattern:** Redis-based distributed lock before expensive operations
- **Detection:** `grep -n "def.*identify\|def.*process" service_file.py`
- **Validation:** Verify lock acquisition, double-check cache, finally block release

**Example from Implementation:**
```python
import redis_lock

lock_key = f"lock:plant_id:{self.API_VERSION}:{image_hash}:{include_diseases}"
lock_id = get_lock_id()

lock = redis_lock.Lock(
    self.redis_client,
    lock_key,
    expire=CACHE_LOCK_EXPIRE,
    auto_renewal=CACHE_LOCK_AUTO_RENEWAL,
    id=lock_id,
)

if lock.acquire(blocking=CACHE_LOCK_BLOCKING, timeout=CACHE_LOCK_TIMEOUT):
    try:
        # Double-check cache (another process may have populated it)
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        # Make expensive API call
        result = self.circuit.call(self._call_api, ...)
        cache.set(cache_key, result, timeout=TTL)
        return result
    finally:
        lock.release()  # Always release in finally block
```

**Why This Matters:**
- **Cost Savings:** 90% reduction in duplicate API calls
- **Concurrency Safety:** Prevents multiple processes from calling same API simultaneously
- **Cache Efficiency:** Ensures only one process populates cache for same request
- **Graceful Degradation:** Handles Redis unavailability without failure

**Key Implementation Details:**
- **Lock Key Naming:** Descriptive format including service, version, hash, parameters
- **Redis Ping Check:** Verify Redis is responsive before attempting locks
- **Double-Check Cache:** After lock acquisition, check cache again (another process may have completed)
- **Timeout Handling:** If lock timeout occurs, check cache one more time before fallback
- **Always Release:** Use finally block to ensure lock cleanup

**Impact on Future Reviews:**
- Expensive operations (API calls, heavy computation) will be flagged
- Reviewer will suggest distributed lock pattern
- Must verify proper lock cleanup in finally block
- Must check for cache double-check pattern

---

### 4. API Versioning with Backward Compatibility

**Pattern Extracted From:**
- File: `backend/plant_community/urls.py` (hypothetical - pattern from documentation)
- Documentation: `backend/docs/quick-wins/api-versioning.md`

**Review Check Added:**
- **Severity:** WARNING
- **Pattern:** All API routes should use versioned namespace (`/api/v1/`)
- **Detection:** `grep -n "path('api/" urls.py`
- **Validation:** Verify routes use version prefix

**Example from Documentation:**
```python
# Versioned API (correct)
path('api/v1/', include(([
    path('plant-identification/', include('apps.plant_identification.urls')),
], 'v1'))),

# Legacy unversioned (deprecated but maintained for backward compatibility)
path('api/', include([
    path('plant-identification/', include('apps.plant_identification.urls')),
])),
```

**Why This Matters:**
- **Backward Compatibility:** Breaking changes don't force all clients to update
- **Mobile App Support:** App store review delays don't block backend updates
- **Gradual Migration:** Can maintain old and new versions simultaneously
- **Third-Party Integration:** External integrations can migrate at their own pace

**Impact on Future Reviews:**
- New API endpoints without `/api/v1/` prefix will be flagged
- Reviewer will require versioned URL structure
- Cache keys should include API version for cache invalidation
- DRF configuration should use `NamespaceVersioning`

---

### 5. Rate Limiting for Quota Protection

**Pattern Extracted From:**
- File: `backend/apps/plant_identification/api/simple_views.py` (from documentation)
- Documentation: `backend/docs/quick-wins/authentication.md`

**Review Check Added:**
- **Severity:** WARNING
- **Pattern:** Different rate limits for authenticated vs anonymous users
- **Detection:** Check for `@ratelimit` decorator on public endpoints
- **Validation:** Verify rate limit key distinguishes users

**Example from Documentation:**
```python
@ratelimit(
    key=lambda request: 'anon' if not request.user.is_authenticated
                      else f'user-{request.user.id}',
    rate='10/h' if settings.DEBUG else '100/h',
    method='POST'
)
```

**Why This Matters:**
- **Quota Protection:** Prevents API quota exhaustion
- **Per-User Tracking:** Individual rate limits prevent abuse
- **Development Flexibility:** Lower limits in dev, higher in production
- **Cost Control:** Protects expensive external API calls

**Impact on Future Reviews:**
- Public endpoints with expensive operations will be checked
- Reviewer will verify rate limiting implementation
- Must use user-specific keys (not shared 'anon' key for all)
- Must have different dev/prod rates

---

### 6. Constants Management for Magic Numbers

**Pattern Extracted From:**
- File: `backend/apps/plant_identification/constants.py`
- Example: All Quick Wins use constants for timeouts, TTLs, thresholds

**Review Check Added:**
- **Severity:** WARNING
- **Pattern:** All configuration values must be in constants.py
- **Detection:** `grep -n "timeout.*=.*[0-9]\|TTL.*=.*[0-9]" service_file.py`
- **Validation:** Verify constants are imported from constants.py

**Example from Implementation:**
```python
# In constants.py
PLANT_ID_CIRCUIT_FAIL_MAX = 3
PLANT_ID_CIRCUIT_RESET_TIMEOUT = 60
CACHE_LOCK_TIMEOUT = 15
CACHE_LOCK_EXPIRE = 30
CACHE_TIMEOUT_24_HOURS = 86400

# In service.py
from ..constants import (
    CACHE_LOCK_TIMEOUT,
    CACHE_LOCK_EXPIRE,
    CACHE_TIMEOUT_24_HOURS
)
```

**Why This Matters:**
- **Centralized Configuration:** All tuning in one place
- **Maintainability:** Easy to adjust timeouts without hunting through code
- **Documentation:** Constants are self-documenting
- **Testing:** Easy to override for tests

**Impact on Future Reviews:**
- Hardcoded numeric values for timeouts/TTLs will be flagged
- Reviewer will require constants.py import
- Descriptive constant names enforced (e.g., `CACHE_TIMEOUT_24_HOURS` not `TIMEOUT`)

---

## Automated Checks Added to Reviewer

### New grep Patterns

The code-review-specialist agent now runs these additional checks on all Python files:

```bash
# Check for unprotected AllowAny permissions
grep -n "AllowAny" path/to/changed/file.py

# Check for external API calls without circuit breaker
grep -n "requests\.\(get\|post\|put\|patch\|delete\)" path/to/changed/file.py

# Check for hardcoded timeouts/TTLs
grep -n "timeout.*=.*[0-9]\|TTL.*=.*[0-9]\|expire.*=.*[0-9]" path/to/changed/file.py

# Check for API endpoints without versioning
grep -n "path('api/" path/to/changed/urls.py

# Check for expensive operations without locks
grep -n "def.*identify\|def.*process\|def.*analyze" path/to/changed/service.py
```

### Example Review Output

The agent will now provide production-readiness feedback like:

```
🚫 BLOCKERS (Must fix immediately)

views.py:12 - AllowAny permission without environment check (PRODUCTION RISK)
  Current (UNSAFE):
    permission_classes = [permissions.AllowAny]

  Fix - Add environment-aware permission:
    from django.conf import settings
    @permission_classes([
        IsAuthenticatedOrAnonymousWithStrictRateLimit if settings.DEBUG
        else IsAuthenticatedForIdentification
    ])

plant_service.py:45 - External API call without circuit breaker (CASCADING FAILURE RISK)
  Current (UNSAFE):
    response = requests.post(PLANT_API_URL, json=data, timeout=30)

  Fix - Wrap with circuit breaker:
    result = self.circuit.call(
        self._call_plant_api,
        data,
        cache_key
    )

⚠️ IMPORTANT ISSUES

plant_service.py:78 - Expensive API call without distributed lock (CACHE STAMPEDE RISK)
  Add distributed lock before API call:
    lock = redis_lock.Lock(self.redis_client, lock_key, expire=30)
    if lock.acquire(blocking=True, timeout=15):
        try:
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result
            result = self.circuit.call(self._call_api, ...)
            cache.set(cache_key, result, timeout=86400)
            return result
        finally:
            lock.release()
```

---

## Benefits of Codification

### 1. Consistent Reviews
- Every Python/Django file will be checked against these production patterns
- No more manual checklist - automated detection
- Patterns are enforced consistently across all developers

### 2. Knowledge Transfer
- New developers learn production patterns from code reviews
- Patterns include "why" and "how" with examples
- Documentation linked directly from review feedback

### 3. Prevention Over Reaction
- Catch production-readiness issues before deployment
- Block risky patterns (AllowAny, unprotected APIs) immediately
- Warn on performance concerns (locks, versioning) for discussion

### 4. Living Documentation
- Code review agent is "living documentation" of standards
- Updates automatically as patterns evolve
- Examples come from actual production code

### 5. Reduced Technical Debt
- Production patterns applied from the start
- No "we'll add that later" - it's in the review
- Cumulative improvement over time

---

## Patterns NOT Codified (Intentional Omissions)

These patterns were **not** added to automated checks:

1. **PlantNet Service Circuit Breaker:**
   - PlantNet service doesn't have circuit breaker yet (noted in analysis)
   - Will be added when PlantNet gets circuit breaker implementation
   - Not blocking - PlantNet has higher rate limits than Plant.id

2. **Specific Lock Timeout Values:**
   - Lock timeout of 15s is specific to Plant.id API (max 9s response)
   - Will vary by service and external API characteristics
   - Review warns but doesn't prescribe exact values

3. **Cache TTL Values:**
   - Cache timeouts vary by data volatility
   - Plant.id: 30 min (rapid changes), PlantNet: 24 hours (stable)
   - Review checks for constants, not specific values

---

## Next Steps

### For Future Quick Wins

When implementing future Quick Wins, follow this pattern:

1. **Document the Pattern:**
   - Write clear documentation with examples
   - Include "why" (rationale) and "how" (implementation)
   - Reference performance metrics if applicable

2. **Extract Review Criteria:**
   - Identify what makes the pattern "correct"
   - Define anti-patterns to avoid
   - Create detection strategy (grep pattern, code smell)

3. **Update Code Review Agent:**
   - Add pattern to production readiness section
   - Include severity level (BLOCKER, WARNING, SUGGESTION)
   - Provide code example in review output format

4. **Test the Review:**
   - Create code with the anti-pattern
   - Run code-review-specialist agent
   - Verify pattern is detected and flagged appropriately

### Maintenance

This codified knowledge should be updated when:

- New production patterns emerge from implementation
- Existing patterns prove ineffective or need refinement
- Team standards evolve
- Framework best practices change (Django, DRF updates)

---

## References

### Documentation
- `/backend/docs/quick-wins/authentication.md` - Environment-aware permissions
- `/backend/docs/quick-wins/circuit-breaker.md` - Circuit breaker pattern
- `/backend/docs/quick-wins/distributed-locks.md` - Cache stampede prevention
- `/backend/docs/quick-wins/api-versioning.md` - API versioning strategy

### Implementation Files
- `/backend/apps/plant_identification/permissions.py` - Permission classes
- `/backend/apps/plant_identification/services/plant_id_service.py` - Circuit breaker + locks
- `/backend/apps/plant_identification/circuit_monitoring.py` - Circuit monitoring
- `/backend/apps/plant_identification/constants.py` - Configuration constants

### Review Agent
- `/.claude/agents/code-review-specialist.md` - Updated reviewer configuration

---

## Conclusion

The Week 3 Quick Wins implementation has been successfully codified into the code-review-specialist agent. All future Python/Django code will be automatically checked against these production-readiness patterns:

1. **Environment-Aware Permissions** - Protect expensive APIs
2. **Circuit Breaker Pattern** - Prevent cascading failures
3. **Distributed Locks** - Eliminate cache stampede
4. **API Versioning** - Enable gradual migration
5. **Rate Limiting** - Control quota usage
6. **Constants Management** - Centralize configuration

These patterns represent real production lessons learned and will prevent similar issues in future development. The reviewer agent now embodies the team's production-readiness expertise and will apply it consistently across all code reviews.
