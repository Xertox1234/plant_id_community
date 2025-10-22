# Circuit Breaker Pattern - Quick Win #3

## Overview

Fast-fail protection for external API failures to prevent cascading failures and thread pool exhaustion.

**Status:** ✅ Complete
**Implementation Time:** ~2 hours
**Performance Impact:** **99.97% faster** (30s → <10ms)
**Files Created:** circuit_monitoring.py (317 lines)

---

## Problem Solved

**Challenge:** When Plant.id API goes down or times out, requests wait 30-35 seconds before failing. This causes:
- Terrible user experience (30s wait for error)
- Thread pool exhaustion (all workers blocked)
- Cascading failures (entire app becomes unresponsive)
- Wasted API quota (retries on down service)

**Solution:** Implement circuit breaker pattern that fast-fails when external service is down.

---

## Implementation

### Circuit Breaker Monitoring Module

**File:** `apps/plant_identification/circuit_monitoring.py` (317 lines)

```python
"""
Circuit Breaker Event Listeners for Monitoring and Logging

Implements event handlers for pybreaker circuit state changes using
bracketed logging pattern ([CIRCUIT] prefix).
"""

import logging
from datetime import datetime
from pybreaker import CircuitBreakerListener

logger = logging.getLogger(__name__)


class CircuitMonitor(CircuitBreakerListener):
    """Circuit breaker event listener for monitoring and logging."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.last_state_change = None
        self.circuit_open_time = None
        self.consecutive_failures = 0

    def state_change(self, cb, old_state, new_state):
        """Called when circuit changes state."""
        self.last_state_change = datetime.now()

        logger.warning(
            f"[CIRCUIT] {self.service_name} state transition: "
            f"{old_state.upper()} → {new_state.upper()} "
            f"(fail_count={cb.fail_counter})"
        )

        if new_state == 'open':
            self.circuit_open_time = datetime.now()
            logger.error(
                f"[CIRCUIT] {self.service_name} circuit OPENED - "
                f"API calls blocked for {cb.reset_timeout}s"
            )

    def failure(self, cb, exception):
        """Called after failed function execution."""
        logger.error(
            f"[CIRCUIT] {self.service_name} call FAILED - "
            f"{exception.__class__.__name__}: {str(exception)[:100]} "
            f"(fail_count={cb.fail_counter}/{cb.fail_max})"
        )

        # Warn when approaching threshold
        if cb.fail_counter == cb.fail_max - 1:
            logger.warning(
                f"[CIRCUIT] {self.service_name} WARNING - "
                f"One more failure will open circuit"
            )


class CircuitStats:
    """Helper class to track circuit breaker statistics."""

    def __init__(self, circuit_breaker, monitor: CircuitMonitor):
        self.circuit = circuit_breaker
        self.monitor = monitor

    def get_status(self) -> dict:
        """Get current circuit status for health checks."""
        state = self.circuit.current_state

        return {
            'state': state,
            'service_name': self.monitor.service_name,
            'fail_count': self.circuit.fail_counter,
            'fail_max': self.circuit.fail_max,
            'reset_timeout': self.circuit.reset_timeout,
            'is_healthy': state == 'closed',
            'is_degraded': state == 'half_open',
            'is_unavailable': state == 'open',
        }


def create_monitored_circuit(
    service_name: str,
    fail_max: int,
    reset_timeout: int,
    success_threshold: int = 1,
):
    """Factory function to create circuit breaker with monitoring."""
    from pybreaker import CircuitBreaker

    monitor = CircuitMonitor(service_name)

    circuit = CircuitBreaker(
        fail_max=fail_max,
        reset_timeout=reset_timeout,
        success_threshold=success_threshold,
        exclude=[KeyboardInterrupt],
        listeners=[monitor],
    )

    stats = CircuitStats(circuit, monitor)

    logger.info(
        f"[CIRCUIT] Initialized circuit breaker for {service_name} "
        f"(fail_max={fail_max}, reset_timeout={reset_timeout}s)"
    )

    return circuit, monitor, stats
```

### Integration with PlantIDAPIService

**File:** `apps/plant_identification/services/plant_id_service.py`

```python
from pybreaker import CircuitBreakerError
from ..circuit_monitoring import create_monitored_circuit
from apps.core.exceptions import ExternalAPIError

# Module-level circuit breaker (shared across all instances)
_plant_id_circuit, _plant_id_monitor, _plant_id_stats = create_monitored_circuit(
    service_name='plant_id_api',
    fail_max=PLANT_ID_CIRCUIT_FAIL_MAX,  # 3 failures
    reset_timeout=PLANT_ID_CIRCUIT_RESET_TIMEOUT,  # 60 seconds
    success_threshold=PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD,  # 2 successes
)


class PlantIDAPIService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'PLANT_ID_API_KEY', None)
        self.circuit = _plant_id_circuit  # Reference module-level circuit
        self.circuit_stats = _plant_id_stats

    def identify_plant(self, image_file, include_diseases: bool = True) -> Dict:
        """
        Identify plant with circuit breaker protection.

        Flow:
        1. Check cache (instant if hit)
        2. Acquire distributed lock
        3. Call API through circuit breaker
        4. Fast-fail if circuit is open (503 error)
        """
        try:
            # Check cache first (40% hit rate - no circuit needed)
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info(f"[CACHE] HIT - instant response")
                return cached_result

            # Call API through circuit breaker
            result = self.circuit.call(
                self._call_plant_id_api,
                image_data, cache_key, image_hash, include_diseases
            )

            return result

        except CircuitBreakerError as e:
            # Circuit is OPEN - fast-fail without API call
            logger.error("[CIRCUIT] Plant.id circuit is OPEN - fast failing")
            raise ExternalAPIError(
                "Plant.id service is temporarily unavailable. "
                "Please try again in a few moments.",
                status_code=503
            )

    def _call_plant_id_api(
        self,
        image_data: bytes,
        cache_key: str,
        image_hash: str,
        include_diseases: bool
    ) -> Dict:
        """
        Protected API call wrapped by circuit breaker.

        Success → Circuit stays closed
        Failure → Increment fail counter, may open circuit
        """
        response = self.session.post(
            f"{self.BASE_URL}/identification",
            json=data,
            headers=headers,
            timeout=self.timeout
        )
        response.raise_for_status()  # Raises on HTTP error

        # Cache result for 24 hours
        result = self._format_response(response.json())
        cache.set(cache_key, result, timeout=CACHE_TIMEOUT_24_HOURS)

        return result
```

---

## Configuration

### Circuit Breaker Constants

**File:** `apps/plant_identification/constants.py`

```python
# Circuit Breaker Configuration
# Plant.id API (Paid Tier - Conservative Settings)
PLANT_ID_CIRCUIT_FAIL_MAX = 3            # Open circuit after 3 consecutive failures
PLANT_ID_CIRCUIT_RESET_TIMEOUT = 60      # Wait 60s before testing recovery
PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD = 2   # Require 2 successes to close circuit

# PlantNet API (Free Tier - More Tolerant)
PLANTNET_CIRCUIT_FAIL_MAX = 5            # Open after 5 failures (more tolerant)
PLANTNET_CIRCUIT_RESET_TIMEOUT = 30      # Wait 30s before retry
PLANTNET_CIRCUIT_SUCCESS_THRESHOLD = 2   # Require 2 successes to close
```

**Why Conservative for Plant.id?**
- Paid tier - failures cost money
- Limited quota - don't waste on down service
- Fast-fail protects user experience

**Why Tolerant for PlantNet?**
- Free tier - no cost per request
- Higher daily limit (500/day)
- More forgiving of transient failures

---

## State Transitions

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLOSED (Normal Operation)                     │
│  • All requests pass through to API                              │
│  • Failures increment fail_counter                               │
│  • Successes reset fail_counter to 0                             │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        │ fail_counter >= fail_max (3 failures)
                        v
┌─────────────────────────────────────────────────────────────────┐
│                    OPEN (Fast-Fail Mode)                         │
│  • All requests fail immediately (CircuitBreakerError)           │
│  • No API calls made (99.97% faster)                             │
│  • Wait reset_timeout (60s) before testing recovery              │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        │ reset_timeout elapsed (60s)
                        v
┌─────────────────────────────────────────────────────────────────┐
│                  HALF-OPEN (Testing Recovery)                    │
│  • Limited requests allowed through (testing)                    │
│  • Success → increment success_counter                           │
│  • Failure → return to OPEN                                      │
│  • success_counter >= success_threshold → CLOSED                 │
└───────────────────────┬─────────────────────────────────────────┘
                        │
         ┌──────────────┴──────────────┐
         │                             │
         │ 2 successes                 │ 1 failure
         v                             v
    ┌─────────┐                  ┌─────────┐
    │ CLOSED  │                  │  OPEN   │
    └─────────┘                  └─────────┘
```

---

## Monitoring and Logging

### Bracketed Logging Pattern

All circuit breaker events use `[CIRCUIT]` prefix for easy filtering:

```bash
# Filter circuit breaker events
grep "[CIRCUIT]" logs/django.log
```

### Example Log Output

**Normal Operation (CLOSED):**
```
[CIRCUIT] plant_id_api call SUCCESS
[CIRCUIT] plant_id_api call SUCCESS
```

**Approaching Threshold:**
```
[CIRCUIT] plant_id_api call FAILED - Timeout (fail_count=1/3)
[CIRCUIT] plant_id_api call FAILED - ConnectionError (fail_count=2/3)
[CIRCUIT] plant_id_api WARNING - One more failure will open circuit
```

**Circuit Opens:**
```
[CIRCUIT] plant_id_api call FAILED - Timeout (fail_count=3/3)
[CIRCUIT] plant_id_api state transition: CLOSED → OPEN
[CIRCUIT] plant_id_api circuit OPENED - API calls blocked for 60s
```

**Fast-Fail (Circuit Open):**
```
[CIRCUIT] plant_id_api call BLOCKED - Circuit is OPEN, fast-failing
[CIRCUIT] plant_id_api call BLOCKED - Circuit is OPEN, fast-failing
```

**Recovery Testing (HALF-OPEN):**
```
[CIRCUIT] plant_id_api entering HALF-OPEN state - Testing service recovery
[CIRCUIT] plant_id_api recovery test SUCCESS (1 / 2 required)
[CIRCUIT] plant_id_api recovery test SUCCESS (2 / 2 required)
[CIRCUIT] plant_id_api state transition: HALF-OPEN → CLOSED
[CIRCUIT] plant_id_api circuit CLOSED - Service recovered after 65.2s downtime
```

---

## Performance Impact

### Before Circuit Breaker

**Scenario:** Plant.id API is down (connection timeout)

```
Request 1: Wait 30s → Error
Request 2: Wait 30s → Error
Request 3: Wait 30s → Error
Request 4-N: All wait 30s → Error
```

**Problems:**
- Every request waits 30-35 seconds
- Thread pool exhausted (all workers blocked)
- App becomes unresponsive
- Terrible user experience

### After Circuit Breaker

**Scenario:** Plant.id API is down (connection timeout)

```
Request 1: Wait 30s → Fail → circuit fail_counter = 1/3
Request 2: Wait 30s → Fail → circuit fail_counter = 2/3
Request 3: Wait 30s → Fail → circuit fail_counter = 3/3 → Circuit OPENS

Request 4-N: Circuit is OPEN → Fast-fail in <10ms → Return 503

... (60 seconds pass)

Circuit enters HALF-OPEN → Test request
  - If succeeds → circuit CLOSES
  - If fails → circuit stays OPEN for another 60s
```

**Benefits:**
- First 3 requests: Normal timeout (30s each)
- Remaining requests: Fast-fail (<10ms)
- **99.97% faster** for failed requests
- Thread pool not exhausted
- App remains responsive

---

## Troubleshooting

### Circuit Stuck Open

**Symptoms:**
```
[CIRCUIT] plant_id_api circuit OPENED - API calls blocked for 60s
[CIRCUIT] plant_id_api call BLOCKED - Circuit is OPEN
... (repeats indefinitely)
```

**Diagnosis:**
1. Check if Plant.id API is actually down:
   ```bash
   curl -X POST https://plant.id/api/v3/health_assessment
   ```

2. Check circuit status:
   ```python
   from apps.plant_identification.services.plant_id_service import _plant_id_stats
   print(_plant_id_stats.get_status())
   # {'state': 'open', 'fail_count': 3, 'fail_max': 3, ...}
   ```

3. Check if recovery testing is happening:
   ```bash
   # Should see HALF-OPEN state every 60s
   grep "HALF-OPEN" logs/django.log | tail -5
   ```

**Solutions:**
- **If API is down:** Wait for it to recover, circuit will auto-heal
- **If API is up but circuit stuck:** May be network issue, check connectivity
- **If need to force reset:** Restart Django (circuit is in-memory)

### Circuit Opens Too Often

**Symptoms:**
```
[CIRCUIT] plant_id_api state transition: CLOSED → OPEN
[CIRCUIT] plant_id_api state transition: OPEN → HALF-OPEN
[CIRCUIT] plant_id_api state transition: HALF-OPEN → CLOSED
[CIRCUIT] plant_id_api state transition: CLOSED → OPEN
... (oscillating)
```

**Diagnosis:**
- API is flaky (intermittent failures)
- `fail_max` too low (too sensitive)
- Timeout too short (legitimate slow requests failing)

**Solutions:**

1. **Increase fail_max:**
   ```python
   # constants.py
   PLANT_ID_CIRCUIT_FAIL_MAX = 5  # More tolerant (was 3)
   ```

2. **Increase reset_timeout:**
   ```python
   PLANT_ID_CIRCUIT_RESET_TIMEOUT = 120  # Wait longer before retry (was 60)
   ```

3. **Increase success_threshold:**
   ```python
   PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD = 3  # Require more successes (was 2)
   ```

---

## Health Check Integration

```python
# apps/plant_identification/api/simple_views.py
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Enhanced health check with circuit breaker status."""
    service = CombinedPlantIdentificationService()

    # Get circuit breaker status
    plant_id_status = service.plant_id.circuit_stats.get_status()

    return Response({
        'status': 'healthy' if plant_id_status['is_healthy'] else 'degraded',
        'services': {
            'plant_id': {
                'available': plant_id_status['is_healthy'],
                'circuit_state': plant_id_status['state'],
                'fail_count': f"{plant_id_status['fail_count']}/{plant_id_status['fail_max']}",
            },
        },
    })
```

**Example Responses:**

**Healthy (Circuit Closed):**
```json
{
  "status": "healthy",
  "services": {
    "plant_id": {
      "available": true,
      "circuit_state": "closed",
      "fail_count": "0/3"
    }
  }
}
```

**Unhealthy (Circuit Open):**
```json
{
  "status": "degraded",
  "services": {
    "plant_id": {
      "available": false,
      "circuit_state": "open",
      "fail_count": "3/3"
    }
  }
}
```

---

## Benefits

- ✅ **99.97% faster** failed API responses (30s → <10ms)
- ✅ **Prevents cascading failures** when external service is down
- ✅ **Automatic recovery testing** via half-open state
- ✅ **Resource protection** - no wasted API quota when service is down
- ✅ **Comprehensive logging** with bracketed [CIRCUIT] prefix
- ✅ **Thread pool protection** - app remains responsive during outages

---

## References

- [pybreaker Documentation](https://github.com/danielfm/pybreaker)
- [Martin Fowler - Circuit Breaker](https://martinfowler.com/bliki/CircuitBreaker.html)
- [Release It! - Stability Patterns](https://pragprog.com/titles/mnee2/release-it-second-edition/)

---

**Status:** Production Ready
**Last Updated:** October 22, 2025
