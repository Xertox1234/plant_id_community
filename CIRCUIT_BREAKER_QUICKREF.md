# Circuit Breaker Quick Reference

**Quick lookup for circuit breaker configuration, commands, and troubleshooting**

---

## Installation

```bash
cd backend
source venv/bin/activate
pip install pybreaker
pip freeze > requirements.txt
```

---

## Configuration Values

### Plant.id API (Paid Tier)
```python
fail_max=3              # Open after 3 failures (conservative)
reset_timeout=60        # Wait 60 seconds before retry
success_threshold=2     # Require 2 successes to close
```

### PlantNet API (Free Tier)
```python
fail_max=5              # Open after 5 failures (more tolerant)
reset_timeout=30        # Wait 30 seconds before retry
success_threshold=2     # Require 2 successes to close
```

---

## Circuit States

| State | Description | Behavior |
|-------|-------------|----------|
| **CLOSED** | Normal operation | All requests pass through |
| **OPEN** | Circuit tripped | All requests fail fast (CircuitBreakerError) |
| **HALF-OPEN** | Testing recovery | Limited requests allowed to test service |

---

## Log Patterns

### State Changes
```bash
[CIRCUIT] plant_id_api state transition: CLOSED → OPEN (fail_count=3, success_count=0)
[CIRCUIT] plant_id_api circuit OPENED - API calls will be blocked for 60s (fail_max=3 reached)
```

### Failures
```bash
[CIRCUIT] plant_id_api failure threshold reached (3 failures) - circuit will open
```

### Recovery
```bash
[CIRCUIT] plant_id_api state transition: OPEN → HALF-OPEN (fail_count=3, success_count=0)
[CIRCUIT] plant_id_api recovery test SUCCESS (1/2 required)
[CIRCUIT] plant_id_api recovery test SUCCESS (2/2 required)
[CIRCUIT] plant_id_api state transition: HALF-OPEN → CLOSED (fail_count=0, success_count=2)
```

### Graceful Degradation
```bash
[CIRCUIT] DEGRADED: plant_id_api circuit OPEN - using PlantNet only (no disease detection, lower accuracy)
[CIRCUIT] DEGRADED: plantnet_api circuit OPEN - using Plant.id only (no family/genus enrichment)
[CIRCUIT] DEGRADED: Both API circuits OPEN - no identification sources available
```

---

## Monitoring Commands

### Check Circuit State (Redis)
```bash
# Plant.id circuit state
redis-cli GET circuit:plant_id_api:state

# PlantNet circuit state
redis-cli GET circuit:plantnet_api:state
```

### View Circuit State Changes (Logs)
```bash
# All circuit events
grep "\[CIRCUIT\]" logs/django.log

# State transitions only
grep "\[CIRCUIT\].*state transition" logs/django.log

# Circuit opens only
grep "\[CIRCUIT\].*circuit OPENED" logs/django.log

# Degraded service events
grep "\[CIRCUIT\] DEGRADED" logs/django.log
```

### Count Circuit Opens (Last 24 Hours)
```bash
grep "\[CIRCUIT\].*circuit OPENED" logs/django.log | tail -n 1000 | wc -l
```

### API Health Check
```bash
curl http://localhost:8000/api/plant-identification/identify/health/

# Expected response (healthy):
{
  "status": "healthy",
  "plant_id_available": true,
  "plantnet_available": true,
  "circuit_breakers": {
    "plant_id": {
      "state": "closed",
      "fail_count": 0,
      "fail_max": 3
    },
    "plantnet": {
      "state": "closed",
      "fail_count": 0,
      "fail_max": 5
    }
  }
}

# Degraded response (one circuit open):
{
  "status": "degraded",
  "plant_id_available": false,
  "plantnet_available": true,
  ...
}
```

---

## Python API

### Check Circuit State
```python
from apps.plant_identification.services.plant_id_service import PlantIDAPIService
from apps.plant_identification.services.plantnet_service import PlantNetAPIService

# Check availability
PlantIDAPIService.is_available()      # True if circuit closed
PlantNetAPIService.is_available()     # True if circuit closed

# Get detailed state
plant_id_state = PlantIDAPIService.get_circuit_state()
# Returns:
# {
#   'name': 'plant_id_api',
#   'state': 'closed',
#   'fail_count': 0,
#   'success_count': 0,
#   'fail_max': 3,
#   'reset_timeout': 60,
#   'last_failure': None
# }
```

### Manual Circuit Control (Emergency)
```python
from apps.plant_identification.services.plant_id_service import plant_id_circuit_breaker

# Manually open circuit (emergency shutdown)
plant_id_circuit_breaker.open()

# Manually close circuit (force recovery)
plant_id_circuit_breaker.close()

# Check current state
plant_id_circuit_breaker.current_state  # 'closed', 'open', or 'half-open'
```

---

## Troubleshooting

### Circuit Opens Too Frequently

**Symptom:** Circuit opens multiple times per hour
**Possible Causes:**
- fail_max too low (try increasing)
- API actually unstable (check external API status)
- Timeout too aggressive (increase API timeout)

**Fix:**
```python
# In constants.py, increase fail_max
PLANT_ID_CIRCUIT_FAIL_MAX = 5  # Was 3

# OR increase API timeout
PLANT_ID_API_TIMEOUT = 45  # Was 35
```

### Circuit Never Opens (Slow Failure Detection)

**Symptom:** API failures continue without circuit opening
**Possible Causes:**
- fail_max too high
- Exceptions being excluded incorrectly
- Circuit breaker not applied to method

**Fix:**
```python
# Lower fail_max for faster detection
PLANT_ID_CIRCUIT_FAIL_MAX = 2  # Was 3

# Check exclude parameter
exclude=[ValueError, KeyError]  # Only business exceptions
```

### Circuit Stuck Open

**Symptom:** Circuit remains open despite API recovery
**Possible Causes:**
- reset_timeout too long
- success_threshold too high
- API still failing on test calls

**Fix:**
```python
# Lower reset_timeout for faster recovery tests
PLANT_ID_CIRCUIT_RESET_TIMEOUT = 30  # Was 60

# Lower success_threshold
PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD = 1  # Was 2
```

### Both Circuits Open (Total Outage)

**Symptom:** All plant identification requests fail
**Action:**
1. Check external API status pages
2. Verify network connectivity
3. Check Redis connection (circuit state storage)
4. Review recent error logs
5. Consider manual circuit reset (if API is healthy)

**Emergency Reset:**
```python
# Django shell
python manage.py shell

from apps.plant_identification.services.plant_id_service import plant_id_circuit_breaker
from apps.plant_identification.services.plantnet_service import plantnet_circuit_breaker

# Force both circuits closed
plant_id_circuit_breaker.close()
plantnet_circuit_breaker.close()

# Verify
print(plant_id_circuit_breaker.current_state)  # Should be 'closed'
print(plantnet_circuit_breaker.current_state)  # Should be 'closed'
```

---

## Testing

### Run Circuit Breaker Tests
```bash
cd backend
source venv/bin/activate

# All circuit breaker tests
python manage.py test apps.plant_identification.tests.test_circuit_breakers

# Specific test
python manage.py test apps.plant_identification.tests.test_circuit_breakers.CircuitBreakerTestCase.test_plant_id_circuit_opens_after_failures

# With verbose output
python manage.py test apps.plant_identification.tests.test_circuit_breakers -v 2
```

### Simulate Circuit Opening (Manual Test)
```python
# Django shell
python manage.py shell

from apps.plant_identification.services.plant_id_service import PlantIDAPIService, plant_id_circuit_breaker
from unittest.mock import patch
import requests

service = PlantIDAPIService()

# Mock failures
with patch.object(service, '_identify_plant_protected') as mock:
    mock.side_effect = requests.exceptions.Timeout("Test failure")

    # Trigger failures
    for i in range(3):
        result = service.identify_plant(b'test')
        print(f"Attempt {i+1}: fail_count={plant_id_circuit_breaker.fail_counter}")

    # Check state
    print(f"Circuit state: {plant_id_circuit_breaker.current_state}")  # Should be 'open'
```

---

## Performance Metrics

### Expected Impact

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **API failure response** | 30-35s (timeout) | <10ms (fast fail) | 99.97% faster |
| **Cascading failures** | High risk | Protected | N/A |
| **Resource exhaustion** | Possible | Prevented | N/A |

### Key Performance Indicators

1. **Circuit Open Frequency:** Should be < 5 times/day in production
2. **Recovery Time:** Average < 2 minutes (2x reset_timeout)
3. **Fallback Success Rate:** > 95% when one circuit open
4. **False Positive Rate:** < 1% (circuit opens when API actually healthy)

---

## Environment Variables

### Optional Overrides

Add to `/backend/.env` to override defaults:

```bash
# Circuit Breaker Configuration
PLANT_ID_CIRCUIT_FAIL_MAX=3
PLANT_ID_CIRCUIT_RESET_TIMEOUT=60
PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD=2

PLANTNET_CIRCUIT_FAIL_MAX=5
PLANTNET_CIRCUIT_RESET_TIMEOUT=30
PLANTNET_CIRCUIT_SUCCESS_THRESHOLD=2

# Logging
CIRCUIT_LOG_STATE_CHANGES=True
CIRCUIT_LOG_FAILURES=True
CIRCUIT_LOG_SUCCESSES=False
```

Then update `constants.py` to read from environment:

```python
import os

PLANT_ID_CIRCUIT_FAIL_MAX = int(os.getenv('PLANT_ID_CIRCUIT_FAIL_MAX', 3))
PLANT_ID_CIRCUIT_RESET_TIMEOUT = int(os.getenv('PLANT_ID_CIRCUIT_RESET_TIMEOUT', 60))
```

---

## Alert Thresholds (Production)

### Critical Alerts (Immediate Response)
- Both circuits open simultaneously
- Circuit flapping (>5 opens/hour)
- Circuit stuck open (>10 minutes)

### Warning Alerts (Monitor)
- Single circuit open
- High failure rate (>10% requests)
- Degraded performance (>50% fallback usage)

### Slack Alert Example
```python
# In circuit_monitoring.py PlantAPICircuitListener

def state_change(self, cb, old_state, new_state):
    if new_state.name == 'open':
        # Send Slack alert
        requests.post(
            'https://hooks.slack.com/services/YOUR/WEBHOOK/URL',
            json={
                'text': f'🔴 {cb.name} circuit OPEN - API unavailable',
                'channel': '#plant-id-alerts'
            }
        )
```

---

## Common Scenarios

### Scenario 1: Planned API Maintenance
```python
# Before maintenance, manually open circuit
python manage.py shell
>>> from apps.plant_identification.services.plant_id_service import plant_id_circuit_breaker
>>> plant_id_circuit_breaker.open()

# After maintenance, verify API, then close
>>> plant_id_circuit_breaker.close()
```

### Scenario 2: API Rate Limit Exceeded
```python
# Circuit should open automatically
# Check state:
>>> plant_id_circuit_breaker.current_state
'open'

# Wait for reset_timeout (60s) or next billing cycle
# Circuit will test recovery automatically
```

### Scenario 3: Network Partition
```python
# Both circuits may open
# Check health endpoint:
$ curl http://localhost:8000/api/plant-identification/identify/health/

# Response will show:
{
  "status": "unhealthy",
  "plant_id_available": false,
  "plantnet_available": false
}

# Service will return 503 (Service Unavailable)
```

---

## File Locations

| File | Purpose |
|------|---------|
| `apps/plant_identification/constants.py` | Circuit breaker configuration values |
| `apps/plant_identification/circuit_monitoring.py` | Event listeners for logging |
| `apps/plant_identification/services/plant_id_service.py` | Plant.id circuit breaker implementation |
| `apps/plant_identification/services/plantnet_service.py` | PlantNet circuit breaker implementation |
| `apps/plant_identification/services/combined_identification_service.py` | Graceful degradation logic |
| `apps/plant_identification/tests/test_circuit_breakers.py` | Unit tests |
| `apps/plant_identification/api/views.py` | Health check endpoint |

---

## Additional Resources

- **Full Research:** `/CIRCUIT_BREAKER_RESEARCH.md`
- **Implementation Guide:** `/CIRCUIT_BREAKER_IMPLEMENTATION.md`
- **pybreaker Docs:** https://github.com/danielfm/pybreaker
- **Martin Fowler Circuit Breaker:** https://martinfowler.com/bliki/CircuitBreaker.html

---

**Quick Reference Version:** 1.0
**Last Updated:** October 22, 2025
