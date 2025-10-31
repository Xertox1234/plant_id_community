# Circuit Breaker Pattern - Research & Best Practices

**Research Date:** October 22, 2025
**Project:** Plant ID Community Backend (Django + External APIs)
**Use Case:** Plant.id (paid/rate-limited) + PlantNet (free tier) API integration

---

## Executive Summary

This document synthesizes circuit breaker best practices for the Plant ID Community Django backend, which currently uses parallel ThreadPoolExecutor calls to Plant.id and PlantNet APIs. Circuit breakers will prevent cascading failures, protect against API rate limits, and provide graceful degradation when external services fail.

**Key Recommendations:**
- **Library:** Use `pybreaker` (v1.4.1) - most mature, feature-rich, thread-safe, Redis-backed
- **Configuration:** Plant.id (fail_max=3, timeout=60s), PlantNet (fail_max=5, timeout=30s)
- **Strategy:** Per-API circuit breakers with fallback to single-API responses
- **Monitoring:** Integrate with existing bracketed logging pattern ([CIRCUIT] prefix)

---

## 1. Circuit Breaker Libraries for Python/Django

### Comparison Matrix

| Library | Version | Thread-Safe | Redis Support | Async Support | Maturity | Recommendation |
|---------|---------|-------------|---------------|---------------|----------|----------------|
| **pybreaker** | v1.4.1 | ✅ Yes | ✅ Yes (distributed) | ✅ Yes (Tornado) | Mature (2013+) | **RECOMMENDED** |
| **circuitbreaker** | 1.4.0 | ⚠️ Unclear | ❌ No | ✅ Yes | Active | Good alternative |
| **tenacity** | Latest | ✅ Yes | ❌ No | ✅ Yes | Very active | Retry-only (no circuit breaker) |

### pybreaker - Detailed Analysis

**Source:** https://github.com/danielfm/pybreaker
**PyPI:** https://pypi.org/project/pybreaker/
**Latest Version:** v1.4.1 (September 21, 2025)
**Python Requirement:** 3.10+

**Key Features:**
- ✅ Thread-safe operation (critical for ThreadPoolExecutor usage)
- ✅ Redis state storage for distributed systems (multi-worker Django deployments)
- ✅ Configurable failure thresholds and timeouts
- ✅ Exception exclusion (ignore business exceptions vs. infrastructure failures)
- ✅ Multiple event listeners per breaker
- ✅ Generator function support
- ✅ Customizable error messages (`throw_new_error_on_trip`)

**Installation:**
```bash
pip install pybreaker
pip install redis  # For distributed state
```

**Why pybreaker Over Alternatives:**
1. **Thread Safety:** Explicitly designed for concurrent use (critical for ThreadPoolExecutor)
2. **Redis Backing:** Essential for multi-worker Django deployments (Gunicorn/uWSGI)
3. **Mature & Stable:** 12+ years of production use
4. **Rich Configuration:** Most flexible API of the compared libraries
5. **Django-Friendly:** No async-only requirements, works with Django request cycle

### circuitbreaker - Alternative Option

**Source:** https://pypi.org/project/circuitbreaker/
**Latest Version:** 1.4.0

**Pros:**
- Simple decorator-based API
- Async support
- Fallback function mechanism

**Cons:**
- Thread safety not documented (risk for ThreadPoolExecutor)
- No Redis support (single-process only)
- Less mature than pybreaker

**Use Case:** Single-process Django dev environments or low-concurrency apps

### tenacity - NOT Recommended for Circuit Breaker

**Source:** https://github.com/jd/tenacity
**Purpose:** Retry logic only (exponential backoff, wait strategies)

**Why NOT Suitable:**
- Does not implement circuit breaker pattern
- Focuses on retry behavior, not failure state management
- No "open circuit" state to prevent cascading failures

**Recommendation:** Use tenacity for **retry logic** (e.g., transient network errors) in combination with pybreaker for **circuit breaking**.

---

## 2. Circuit Breaker Configuration Best Practices

### Industry Standards (Netflix Hystrix + Martin Fowler)

**Sources:**
- Martin Fowler: https://martinfowler.com/bliki/CircuitBreaker.html
- Netflix Hystrix Configuration: https://github.com/Netflix/Hystrix/wiki/Configuration

#### Netflix Hystrix Defaults (Proven at Scale)

| Parameter | Default Value | Rationale |
|-----------|---------------|-----------|
| **Error Threshold** | 50% | Circuit opens when half of requests fail |
| **Request Volume** | 20 requests minimum | Prevents premature trips from low traffic |
| **Sleep Window** | 5 seconds | Time before testing recovery (half-open state) |
| **Execution Timeout** | 1 second | Fast failure for slow dependencies |

**Key Principle (Netflix):** "Keep thread pools small to shed load effectively"
- Netflix API: 30+ thread pools at 10 workers, 2 at 20, 1 at 25

#### Martin Fowler's Guidance

**Failure Thresholds:**
- **Basic:** Count consecutive failures (e.g., 5 failures = open circuit)
- **Sophisticated:** Monitor error frequency (e.g., 50% failure rate over sliding window)
- **Differentiated:** Different limits per error type (10 for timeouts, 3 for connection failures)

**Timeout Strategies:**
- Set explicit invocation timeouts (prevent indefinite waiting)
- Use "half-open" state for periodic testing
- Consider thread pools + futures for async execution (prevent resource exhaustion)

**Monitoring:**
- Log all state changes (closed → open → half-open)
- Circuit breakers are "valuable monitoring points"
- Alert operations when circuits trip (signals environmental issues)
- Allow manual trip/reset for emergency control

---

## 3. Recommended Configuration for Plant ID Community

### Plant.id API Circuit Breaker

**Context:**
- **Tier:** Paid API (100 identifications/month free, then paid)
- **Rate Limits:** Strict monthly quota
- **Criticality:** Primary identification source (95% accuracy)
- **Current Timeout:** 35 seconds (includes 5s buffer)

**Recommended Configuration:**
```python
plant_id_breaker = CircuitBreaker(
    fail_max=3,              # Open after 3 consecutive failures
    reset_timeout=60,        # Wait 60s before testing recovery
    success_threshold=2,     # Require 2 successes to close circuit
    exclude=[BusinessException],  # Ignore non-infrastructure errors
    name='plant_id_api',
    listeners=[PlantIdCircuitListener()]  # Custom logging
)
```

**Rationale:**
- **fail_max=3:** Conservative (paid API) - protect against quota exhaustion
- **reset_timeout=60s:** Longer recovery (avoid burning API credits during outages)
- **success_threshold=2:** Require sustained recovery before trusting again
- **Low tolerance:** Fail fast to preserve quota and fallback to PlantNet

### PlantNet API Circuit Breaker

**Context:**
- **Tier:** Free API (500 requests/day)
- **Rate Limits:** Daily quota resets at midnight UTC
- **Criticality:** Secondary source (care instructions, supplemental data)
- **Current Timeout:** 20 seconds (includes 5s buffer)

**Recommended Configuration:**
```python
plantnet_breaker = CircuitBreaker(
    fail_max=5,              # Open after 5 consecutive failures
    reset_timeout=30,        # Wait 30s before testing recovery
    success_threshold=2,     # Require 2 successes to close circuit
    exclude=[BusinessException],
    name='plantnet_api',
    listeners=[PlantNetCircuitListener()]
)
```

**Rationale:**
- **fail_max=5:** More tolerant (free tier, less critical)
- **reset_timeout=30s:** Faster recovery attempts (lower stakes)
- **success_threshold=2:** Same reliability requirement as Plant.id
- **Higher tolerance:** Allow more retries before opening circuit

### Per-Error-Type Configuration (Advanced)

**For Production Environments:**
```python
# Timeout errors: More tolerant (network congestion)
timeout_breaker = CircuitBreaker(fail_max=10, reset_timeout=30)

# Connection errors: Less tolerant (service outage)
connection_breaker = CircuitBreaker(fail_max=3, reset_timeout=60)

# Rate limit errors: Immediate open (quota exhausted)
ratelimit_breaker = CircuitBreaker(fail_max=1, reset_timeout=300)
```

---

## 4. Django Integration Patterns

### Pattern 1: Service-Level Decorator (Recommended)

**File:** `/backend/apps/plant_identification/services/plant_id_service.py`

```python
from pybreaker import CircuitBreaker
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

# Redis-backed circuit breaker for distributed Django deployments
plant_id_breaker = CircuitBreaker(
    fail_max=3,
    reset_timeout=60,
    success_threshold=2,
    name='plant_id_api',
    state_storage=CircuitRedisStorage(
        state=CircuitBreakerRedisState('plantid'),
        cache=cache  # Uses Django cache (Redis)
    )
)

class PlantIDAPIService:
    @plant_id_breaker
    def identify_plant(self, image_file, include_diseases=True):
        """Protected by circuit breaker - fails fast when service is down."""
        # Existing implementation...
        pass
```

**Advantages:**
- ✅ Minimal code changes (decorator pattern)
- ✅ Thread-safe (pybreaker handles locking)
- ✅ Distributed state via Redis (multi-worker deployments)
- ✅ Integrates with existing caching layer

### Pattern 2: Manual Call (Fine-Grained Control)

**For complex logic requiring custom fallback:**

```python
try:
    result = plant_id_breaker.call(
        self.plant_id.identify_plant,
        image_file,
        include_diseases=True
    )
except CircuitBreakerError:
    logger.warning("[CIRCUIT] Plant.id circuit OPEN - falling back to PlantNet only")
    result = None  # Handled by _identify_parallel fallback logic
```

### Pattern 3: Context Manager (Transaction-Style)

**For operations requiring setup/teardown:**

```python
try:
    with plant_id_breaker.calling():
        # Protected code block
        response = requests.post(url, data=payload, timeout=30)
        return response.json()
except CircuitBreakerError:
    logger.error("[CIRCUIT] Circuit OPEN - skipping API call")
    return None
```

### Thread Safety with ThreadPoolExecutor

**Critical Implementation Detail:**

```python
# ✅ CORRECT: Circuit breaker is module-level (shared across threads)
plant_id_breaker = CircuitBreaker(...)  # Module scope

def call_plant_id():
    """Executed in ThreadPoolExecutor - circuit breaker is thread-safe."""
    return plant_id_breaker.call(api_call_function)

# ❌ WRONG: Creating circuit breaker per-thread
def call_plant_id():
    breaker = CircuitBreaker(...)  # New instance per thread!
    return breaker.call(api_call_function)
```

**Why It Matters:**
- Circuit breaker state (failure count, open/closed) must be shared across threads
- Module-level singleton ensures all threads see the same circuit state
- pybreaker uses internal locks to prevent race conditions

### Redis State Storage Configuration

**File:** `/backend/plant_id_community/settings.py`

```python
# Circuit breaker state storage (uses Django cache)
CIRCUIT_BREAKER_REDIS_URL = CACHES['default']['LOCATION']

# Alternative: Dedicated Redis connection for circuit state
CIRCUIT_BREAKER_REDIS = {
    'host': 'localhost',
    'port': 6379,
    'db': 1,  # Different DB than cache
}
```

**Benefits:**
- Shared state across Gunicorn workers
- Survives process restarts (circuit state persists)
- Centralized monitoring (check Redis for circuit status)

---

## 5. Partial Failure Handling (Dual API Strategy)

### Current Architecture

```
Image Upload → CombinedPlantIdentificationService
                ↓
        [ThreadPoolExecutor]
        ↙             ↘
   Plant.id      PlantNet
   (primary)    (secondary)
        ↘             ↙
    Merged Results
```

### Circuit Breaker Enhanced Flow

```
Image Upload → CombinedPlantIdentificationService
                ↓
        [Check Circuit States]
                ↓
    ┌───────────────────────┐
    │ Both Open?            │ → Return error
    │ Plant.id Open?        │ → PlantNet only
    │ PlantNet Open?        │ → Plant.id only
    │ Both Closed?          │ → Parallel execution
    └───────────────────────┘
```

### Implementation Strategy

```python
def _identify_parallel(self, image_data):
    """Enhanced with circuit breaker awareness."""

    # Check circuit states before submission
    plant_id_available = (
        self.plant_id and
        plant_id_breaker.current_state == 'closed'
    )
    plantnet_available = (
        self.plantnet and
        plantnet_breaker.current_state == 'closed'
    )

    # Graceful degradation logic
    if not plant_id_available and not plantnet_available:
        logger.error("[CIRCUIT] Both APIs unavailable (circuits OPEN)")
        return None, None

    if not plant_id_available:
        logger.warning("[CIRCUIT] Plant.id circuit OPEN - using PlantNet only")
        return None, self._call_plantnet_safe(image_data)

    if not plantnet_available:
        logger.warning("[CIRCUIT] PlantNet circuit OPEN - using Plant.id only")
        return self._call_plant_id_safe(image_data), None

    # Both available - proceed with parallel execution
    return self._execute_parallel_with_breakers(image_data)
```

### Fallback Priorities

**Scenario 1: Plant.id Circuit Open**
- Primary response: PlantNet results
- User notification: "Limited identification data available"
- Missing features: Disease detection, high-accuracy AI

**Scenario 2: PlantNet Circuit Open**
- Primary response: Plant.id results
- User notification: None (Plant.id is primary source)
- Missing features: Family/genus enrichment

**Scenario 3: Both Circuits Open**
- Response: HTTP 503 Service Unavailable
- User message: "Plant identification temporarily unavailable. Please try again later."
- Retry-After header: Set to minimum of both reset_timeouts

---

## 6. Monitoring and Observability

### Logging Integration (Bracketed Pattern)

**Existing Pattern:**
```python
logger.info("[CACHE] HIT for image...")
logger.info("[PERF] Parallel API execution completed...")
logger.error("[ERROR] Plant.id failed...")
```

**New Circuit Breaker Logs:**
```python
logger.warning("[CIRCUIT] plant_id_api state: CLOSED → OPEN (3 failures)")
logger.info("[CIRCUIT] plant_id_api state: OPEN → HALF-OPEN (testing recovery)")
logger.info("[CIRCUIT] plant_id_api state: HALF-OPEN → CLOSED (2 successes)")
logger.error("[CIRCUIT] plant_id_api OPEN - skipping API call (fast fail)")
logger.info("[CIRCUIT] plant_id_api recovery test FAILED (1/2 required successes)")
```

### Custom Event Listeners

**File:** `/backend/apps/plant_identification/monitoring.py`

```python
from pybreaker import CircuitBreakerListener
import logging

logger = logging.getLogger(__name__)

class PlantIdCircuitListener(CircuitBreakerListener):
    """Custom listener for circuit state changes."""

    def state_change(self, cb, old_state, new_state):
        """Log state transitions with bracketed prefix."""
        logger.warning(
            f"[CIRCUIT] {cb.name} state: {old_state.name} → {new_state.name} "
            f"(failures: {cb.fail_counter})"
        )

    def failure(self, cb, exc):
        """Log failures without flooding logs."""
        if cb.fail_counter == cb.fail_max:
            logger.error(
                f"[CIRCUIT] {cb.name} reached failure threshold "
                f"({cb.fail_max}) - opening circuit"
            )

    def success(self, cb):
        """Log recovery progress in half-open state."""
        if cb.current_state == 'half-open':
            logger.info(
                f"[CIRCUIT] {cb.name} recovery test SUCCESS "
                f"({cb.success_counter}/{cb.success_threshold})"
            )
```

### Metrics to Track

**Redis Keys for Monitoring:**
```bash
# Circuit states (stored in Redis)
redis-cli GET circuit:plant_id_api:state        # "open", "closed", "half-open"
redis-cli GET circuit:plant_id_api:fail_count   # Current failure count
redis-cli GET circuit:plant_id_api:last_failure # Timestamp of last failure

# Custom metrics (stored via Django cache)
cache.get('circuit:plant_id_api:open_count')       # Total times circuit opened
cache.get('circuit:plant_id_api:total_failures')   # Lifetime failure count
cache.get('circuit:plant_id_api:avg_recovery_time') # Avg time to recovery
```

**Django Admin Dashboard (Future Enhancement):**
- Circuit breaker status widget (green/yellow/red)
- Failure rate charts (last 24 hours)
- Alert history (circuit open events)

### Prometheus Metrics (Production)

**For production environments with Prometheus:**

```python
from prometheus_client import Counter, Gauge

# Circuit breaker metrics
circuit_open_total = Counter(
    'circuit_breaker_open_total',
    'Total number of circuit opens',
    ['service']
)

circuit_state = Gauge(
    'circuit_breaker_state',
    'Current circuit state (0=closed, 1=half-open, 2=open)',
    ['service']
)

# Update in listener
def state_change(self, cb, old_state, new_state):
    if new_state.name == 'open':
        circuit_open_total.labels(service=cb.name).inc()

    state_value = {'closed': 0, 'half-open': 1, 'open': 2}[new_state.name]
    circuit_state.labels(service=cb.name).set(state_value)
```

---

## 7. Testing Circuit Breakers

### Unit Test Pattern

**File:** `/backend/apps/plant_identification/test_circuit_breakers.py`

```python
from django.test import TestCase
from pybreaker import CircuitBreaker
from unittest.mock import Mock, patch
import requests

class CircuitBreakerTestCase(TestCase):
    """Test circuit breaker behavior for Plant.id API."""

    def setUp(self):
        """Create test circuit breaker with low thresholds."""
        self.breaker = CircuitBreaker(
            fail_max=2,
            reset_timeout=1,  # 1 second for fast tests
            success_threshold=2,
            name='test_plant_id'
        )

    def test_circuit_opens_after_failures(self):
        """Circuit should open after fail_max consecutive failures."""
        mock_service = Mock(side_effect=requests.exceptions.Timeout)

        # Trigger failures
        for _ in range(2):
            with self.assertRaises(requests.exceptions.Timeout):
                self.breaker.call(mock_service)

        # Next call should raise CircuitBreakerError (circuit open)
        from pybreaker import CircuitBreakerError
        with self.assertRaises(CircuitBreakerError):
            self.breaker.call(mock_service)

        # Verify state
        self.assertEqual(self.breaker.current_state, 'open')

    def test_circuit_half_open_after_timeout(self):
        """Circuit should transition to half-open after reset_timeout."""
        import time

        # Open circuit
        mock_service = Mock(side_effect=Exception)
        for _ in range(2):
            with self.assertRaises(Exception):
                self.breaker.call(mock_service)

        # Wait for reset_timeout
        time.sleep(1.1)

        # Next call should be allowed (half-open state)
        self.assertEqual(self.breaker.current_state, 'half-open')

    def test_circuit_closes_after_successes(self):
        """Circuit should close after success_threshold successes."""
        import time

        # Open circuit
        mock_service = Mock(side_effect=Exception)
        for _ in range(2):
            with self.assertRaises(Exception):
                self.breaker.call(mock_service)

        # Wait for reset_timeout
        time.sleep(1.1)

        # Mock recovery (successful responses)
        mock_service = Mock(return_value={'success': True})

        # First success (half-open → half-open)
        result = self.breaker.call(mock_service)
        self.assertEqual(self.breaker.current_state, 'half-open')

        # Second success (half-open → closed)
        result = self.breaker.call(mock_service)
        self.assertEqual(self.breaker.current_state, 'closed')

    def test_partial_failure_handling(self):
        """Test graceful degradation when one API circuit is open."""
        # Simulate Plant.id circuit open
        plant_id_breaker.fail_counter = plant_id_breaker.fail_max

        # Should fallback to PlantNet only
        service = CombinedPlantIdentificationService()
        result = service.identify_plant(test_image)

        # Verify fallback worked
        self.assertIsNotNone(result)
        self.assertEqual(result['source'], 'plantnet')
```

### Integration Test with ThreadPoolExecutor

**Test thread safety:**

```python
def test_circuit_breaker_thread_safety(self):
    """Verify circuit breaker works correctly with ThreadPoolExecutor."""
    from concurrent.futures import ThreadPoolExecutor

    breaker = CircuitBreaker(fail_max=5, reset_timeout=60)

    def failing_call():
        raise Exception("Simulated failure")

    # Execute 10 concurrent calls
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(breaker.call, failing_call)
            for _ in range(10)
        ]

        # Collect results
        for future in futures:
            with self.assertRaises((Exception, CircuitBreakerError)):
                future.result()

    # Verify circuit opened after fail_max failures
    self.assertEqual(breaker.current_state, 'open')
    self.assertEqual(breaker.fail_counter, 5)  # Not 10!
```

---

## 8. Production Deployment Checklist

### Environment Variables

**Add to `/backend/.env`:**
```bash
# Circuit Breaker Configuration
PLANT_ID_CIRCUIT_FAIL_MAX=3
PLANT_ID_CIRCUIT_RESET_TIMEOUT=60
PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD=2

PLANTNET_CIRCUIT_FAIL_MAX=5
PLANTNET_CIRCUIT_RESET_TIMEOUT=30
PLANTNET_CIRCUIT_SUCCESS_THRESHOLD=2

# Redis for circuit state (uses existing REDIS_URL)
CIRCUIT_BREAKER_REDIS_URL=${REDIS_URL}
```

### Deployment Steps

1. **Install Dependencies:**
   ```bash
   pip install pybreaker
   # Already have redis and django-redis
   ```

2. **Add Constants:**
   ```python
   # apps/plant_identification/constants.py

   # Circuit Breaker Thresholds
   PLANT_ID_CIRCUIT_FAIL_MAX = 3
   PLANT_ID_CIRCUIT_RESET_TIMEOUT = 60
   PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD = 2

   PLANTNET_CIRCUIT_FAIL_MAX = 5
   PLANTNET_CIRCUIT_RESET_TIMEOUT = 30
   PLANTNET_CIRCUIT_SUCCESS_THRESHOLD = 2
   ```

3. **Update Services:**
   - Add circuit breaker decorators to `plant_id_service.py`
   - Add circuit breaker decorators to `plantnet_service.py`
   - Update `combined_identification_service.py` for fallback logic

4. **Add Monitoring:**
   - Create `monitoring.py` with custom listeners
   - Add Prometheus metrics (if applicable)
   - Update logging filters in settings.py

5. **Test in Staging:**
   - Run circuit breaker unit tests
   - Simulate API failures (network disconnect)
   - Verify logs show state transitions
   - Check Redis for state persistence

6. **Deploy to Production:**
   - Monitor circuit state changes in first 24 hours
   - Tune thresholds based on real traffic patterns
   - Set up alerts for circuit open events

### Monitoring Alerts (Production)

**Slack/Email Alerts:**
```python
def state_change(self, cb, old_state, new_state):
    if new_state.name == 'open':
        # Send alert to ops team
        send_slack_alert(
            channel='#plant-id-alerts',
            message=f'🔴 {cb.name} circuit OPEN - API unavailable'
        )
```

**Alert Thresholds:**
- Circuit opens: Immediate alert (P2 priority)
- Circuit remains open > 5 minutes: Escalate to P1
- Circuit flapping (open/close cycles): Immediate alert (configuration issue)

---

## 9. Advanced Patterns (Future Enhancements)

### Adaptive Thresholds (Machine Learning)

**Concept:** Adjust fail_max based on traffic patterns
- High traffic hours: fail_max=5 (more tolerant)
- Low traffic hours: fail_max=3 (fail fast)
- Automatic tuning based on success rate history

### Bulkhead Pattern (Resource Isolation)

**Combine with circuit breakers:**
```python
# Separate thread pools per API (already implemented)
plant_id_executor = ThreadPoolExecutor(max_workers=5)
plantnet_executor = ThreadPoolExecutor(max_workers=5)

# Prevent one API's failures from affecting the other
```

### Rate Limiter Integration

**Coordinate with rate limiting:**
```python
# If rate limit exceeded, open circuit immediately
if response.status_code == 429:
    retry_after = int(response.headers.get('Retry-After', 300))
    circuit_breaker.reset_timeout = retry_after
    raise RateLimitExceeded  # Triggers circuit open
```

---

## 10. References & Further Reading

### Official Documentation
- **pybreaker GitHub:** https://github.com/danielfm/pybreaker
- **pybreaker PyPI:** https://pypi.org/project/pybreaker/
- **Martin Fowler - Circuit Breaker:** https://martinfowler.com/bliki/CircuitBreaker.html
- **Netflix Hystrix Configuration:** https://github.com/Netflix/Hystrix/wiki/Configuration

### Industry Best Practices
- **Release It! (Michael Nygard):** Chapter on stability patterns, circuit breakers
- **Building Microservices (Sam Newman):** Chapter 11 - Resilience
- **AWS Well-Architected Framework:** Reliability pillar - failure isolation

### Django-Specific Resources
- **Django Caching Framework:** https://docs.djangoproject.com/en/5.2/topics/cache/
- **django-redis Documentation:** https://github.com/jazzband/django-redis
- **ThreadPoolExecutor in Django:** Python concurrent.futures documentation

### Related Patterns
- **Retry Pattern:** Tenacity library (https://github.com/jd/tenacity)
- **Bulkhead Pattern:** Resource isolation for cascading failure prevention
- **Rate Limiting:** Django-ratelimit, DRF throttling

---

## Appendix A: Quick Reference - pybreaker API

### Basic Configuration
```python
from pybreaker import CircuitBreaker

breaker = CircuitBreaker(
    fail_max=5,                    # Failures before opening
    reset_timeout=60,              # Seconds before half-open
    success_threshold=2,           # Successes to close from half-open
    exclude=[BusinessException],   # Ignore these exceptions
    name='my_api',                 # Breaker identifier
    listeners=[MyListener()],      # Event listeners
)
```

### Usage Patterns
```python
# Decorator
@breaker
def api_call():
    pass

# Direct call
breaker.call(api_call, *args, **kwargs)

# Context manager
with breaker.calling():
    # protected code
    pass
```

### State Inspection
```python
breaker.current_state          # 'closed', 'open', 'half-open'
breaker.fail_counter           # Current failure count
breaker.success_counter        # Current success count (half-open)
breaker.last_failure_time      # Timestamp of last failure
```

### Redis State Storage
```python
from pybreaker import CircuitRedisStorage, CircuitBreakerRedisState
from django.core.cache import cache

storage = CircuitRedisStorage(
    state=CircuitBreakerRedisState('my_api'),
    cache=cache  # Django cache backend
)

breaker = CircuitBreaker(state_storage=storage, ...)
```

---

## Appendix B: Configuration Values Summary

| Parameter | Plant.id | PlantNet | Rationale |
|-----------|----------|----------|-----------|
| **fail_max** | 3 | 5 | Plant.id paid tier = fail fast; PlantNet free = more tolerant |
| **reset_timeout** | 60s | 30s | Plant.id costly to test; PlantNet cheaper recovery tests |
| **success_threshold** | 2 | 2 | Both require sustained recovery before closing |
| **API timeout** | 35s | 20s | Existing timeouts (includes 5s buffer) |
| **Cache TTL** | 30 min | 24 hours | Plant.id results fresher; PlantNet static data |

---

**Document Version:** 1.0
**Last Updated:** October 22, 2025
**Next Review:** After production deployment + 30 days of monitoring data
