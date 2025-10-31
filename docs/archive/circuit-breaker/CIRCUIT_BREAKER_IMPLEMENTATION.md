# Circuit Breaker Implementation Guide

**Project:** Plant ID Community Backend
**Target Files:** `plant_id_service.py`, `plantnet_service.py`, `combined_identification_service.py`
**Implementation Strategy:** Phased rollout with backward compatibility

---

## Phase 1: Setup & Dependencies

### 1.1 Install pybreaker

```bash
cd backend
source venv/bin/activate
pip install pybreaker
pip freeze > requirements.txt
```

### 1.2 Update Constants

**File:** `/backend/apps/plant_identification/constants.py`

Add to the end of the file:

```python
# ============================================================================
# Circuit Breaker Configuration
# ============================================================================

# Plant.id API Circuit Breaker
PLANT_ID_CIRCUIT_FAIL_MAX = 3           # Conservative (paid tier)
PLANT_ID_CIRCUIT_RESET_TIMEOUT = 60     # 1 minute recovery window
PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD = 2  # Require 2 successes to close

# PlantNet API Circuit Breaker
PLANTNET_CIRCUIT_FAIL_MAX = 5           # More tolerant (free tier)
PLANTNET_CIRCUIT_RESET_TIMEOUT = 30     # 30 second recovery window
PLANTNET_CIRCUIT_SUCCESS_THRESHOLD = 2  # Require 2 successes to close

# Circuit Breaker Logging
CIRCUIT_LOG_STATE_CHANGES = True        # Log state transitions
CIRCUIT_LOG_FAILURES = True             # Log individual failures
CIRCUIT_LOG_SUCCESSES = False           # Only log in half-open state
```

### 1.3 Create Circuit Breaker Monitoring Module

**File:** `/backend/apps/plant_identification/circuit_monitoring.py`

```python
"""
Circuit Breaker Monitoring and Event Listeners

Provides custom listeners for logging circuit state changes
with the existing bracketed logging pattern ([CIRCUIT] prefix).
"""

import logging
from typing import Any
from pybreaker import CircuitBreakerListener

from .constants import (
    CIRCUIT_LOG_STATE_CHANGES,
    CIRCUIT_LOG_FAILURES,
    CIRCUIT_LOG_SUCCESSES,
)

logger = logging.getLogger(__name__)


class PlantAPICircuitListener(CircuitBreakerListener):
    """
    Custom circuit breaker listener for Plant API services.

    Integrates with existing bracketed logging pattern:
    - [CIRCUIT] prefix for filtering
    - State changes logged as warnings
    - Failures logged based on configuration
    - Recovery progress logged in half-open state
    """

    def state_change(self, cb: Any, old_state: Any, new_state: Any) -> None:
        """
        Log circuit state transitions.

        Args:
            cb: CircuitBreaker instance
            old_state: Previous state object
            new_state: New state object
        """
        if not CIRCUIT_LOG_STATE_CHANGES:
            return

        state_name_map = {
            'closed': 'CLOSED',
            'open': 'OPEN',
            'half-open': 'HALF-OPEN',
        }

        old_state_name = state_name_map.get(old_state.name, old_state.name.upper())
        new_state_name = state_name_map.get(new_state.name, new_state.name.upper())

        logger.warning(
            f"[CIRCUIT] {cb.name} state transition: {old_state_name} → {new_state_name} "
            f"(fail_count={cb.fail_counter}, success_count={cb.success_counter})"
        )

        # Additional context for OPEN state
        if new_state.name == 'open':
            logger.error(
                f"[CIRCUIT] {cb.name} circuit OPENED - API calls will be blocked for "
                f"{cb.reset_timeout}s (fail_max={cb.fail_max} reached)"
            )

    def failure(self, cb: Any, exc: Exception) -> None:
        """
        Log circuit breaker failures.

        Args:
            cb: CircuitBreaker instance
            exc: Exception that triggered the failure
        """
        if not CIRCUIT_LOG_FAILURES:
            return

        # Only log at failure threshold to avoid spam
        if cb.fail_counter == cb.fail_max:
            logger.error(
                f"[CIRCUIT] {cb.name} failure threshold reached "
                f"({cb.fail_max} failures) - circuit will open"
            )
        elif cb.current_state == 'half-open':
            logger.warning(
                f"[CIRCUIT] {cb.name} recovery test FAILED - circuit reopening "
                f"(error: {type(exc).__name__})"
            )

    def success(self, cb: Any) -> None:
        """
        Log successful calls in half-open state.

        Args:
            cb: CircuitBreaker instance
        """
        # Only log successes in half-open state (recovery progress)
        if cb.current_state == 'half-open' or CIRCUIT_LOG_SUCCESSES:
            logger.info(
                f"[CIRCUIT] {cb.name} recovery test SUCCESS "
                f"({cb.success_counter}/{cb.success_threshold} required)"
            )

    def before_call(self, cb: Any, func: Any, *args: Any, **kwargs: Any) -> None:
        """
        Log before protected call (optional, for debugging).

        Args:
            cb: CircuitBreaker instance
            func: Function being called
            args: Positional arguments
            kwargs: Keyword arguments
        """
        # Uncomment for verbose debugging
        # logger.debug(f"[CIRCUIT] {cb.name} calling {func.__name__} (state={cb.current_state})")
        pass


class PlantIdCircuitListener(PlantAPICircuitListener):
    """Specialized listener for Plant.id API circuit breaker."""
    pass


class PlantNetCircuitListener(PlantAPICircuitListener):
    """Specialized listener for PlantNet API circuit breaker."""
    pass
```

---

## Phase 2: Service Integration

### 2.1 Plant.id Service Circuit Breaker

**File:** `/backend/apps/plant_identification/services/plant_id_service.py`

Add imports at the top:

```python
from pybreaker import CircuitBreaker, CircuitBreakerError
from django.conf import settings

from ..constants import (
    # ... existing imports ...
    PLANT_ID_CIRCUIT_FAIL_MAX,
    PLANT_ID_CIRCUIT_RESET_TIMEOUT,
    PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD,
)
from ..circuit_monitoring import PlantIdCircuitListener
```

Add module-level circuit breaker (after imports, before class):

```python
# Module-level circuit breaker (shared across all instances and threads)
# This ensures circuit state is consistent across ThreadPoolExecutor workers
plant_id_circuit_breaker = CircuitBreaker(
    fail_max=PLANT_ID_CIRCUIT_FAIL_MAX,
    reset_timeout=PLANT_ID_CIRCUIT_RESET_TIMEOUT,
    success_threshold=PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD,
    name='plant_id_api',
    listeners=[PlantIdCircuitListener()],
    # Exclude business exceptions (non-infrastructure failures)
    exclude=[ValueError, KeyError],  # Add other business exceptions as needed
)

logger.info(
    f"[CIRCUIT] plant_id_api circuit breaker initialized "
    f"(fail_max={PLANT_ID_CIRCUIT_FAIL_MAX}, reset_timeout={PLANT_ID_CIRCUIT_RESET_TIMEOUT}s)"
)
```

Update the `identify_plant` method:

```python
def identify_plant(self, image_file, include_diseases: bool = True) -> Optional[Dict[str, Any]]:
    """
    Identify a plant from an image using Plant.id API with Redis caching and circuit breaker.

    Circuit Breaker Protection:
    - Opens after 3 consecutive failures (PLANT_ID_CIRCUIT_FAIL_MAX)
    - Blocks requests for 60 seconds (PLANT_ID_CIRCUIT_RESET_TIMEOUT)
    - Requires 2 successful calls to close (PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD)

    Args:
        image_file: Django file object or file bytes
        include_diseases: Whether to include disease detection

    Returns:
        Dictionary containing identification results, or None if circuit is open

    Raises:
        CircuitBreakerError: When circuit is open (API unavailable)
    """
    try:
        # Wrap the entire method in circuit breaker
        return plant_id_circuit_breaker.call(
            self._identify_plant_protected,
            image_file,
            include_diseases
        )
    except CircuitBreakerError:
        logger.warning(
            "[CIRCUIT] plant_id_api circuit OPEN - skipping API call (fast fail)"
        )
        return None  # Graceful degradation - caller handles None


def _identify_plant_protected(self, image_file, include_diseases: bool = True) -> Dict[str, Any]:
    """
    Internal implementation of plant identification (protected by circuit breaker).

    This is the original identify_plant logic, now wrapped by the circuit breaker.
    """
    # Move existing identify_plant implementation here
    # (everything from the original method except the circuit breaker wrapper)

    try:
        # Convert image to bytes
        if hasattr(image_file, 'read'):
            image_data = image_file.read()
        else:
            image_data = image_file

        # Generate cache key from image hash (includes API version for cache invalidation)
        image_hash = hashlib.sha256(image_data).hexdigest()
        cache_key = f"plant_id:{self.API_VERSION}:{image_hash}:{include_diseases}"

        # Check cache first
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"[CACHE] HIT for image {image_hash[:8]}... (instant response)")
            return cached_result

        # Cache miss - call API
        logger.info(f"[CACHE] MISS for image {image_hash[:8]}... (calling Plant.id API)")

        encoded_image = base64.b64encode(image_data).decode('utf-8')

        # Prepare request payload
        headers = {
            'Api-Key': self.api_key,
            'Content-Type': 'application/json',
        }

        data = {
            'images': [encoded_image],
            'modifiers': ['crops', 'similar_images'],
            'plant_language': 'en',
            'plant_details': [
                'common_names',
                'taxonomy',
                'url',
                'description',
                'synonyms',
                'image',
                'edible_parts',
                'watering',
                'propagation_methods',
            ],
        }

        # Add disease detection if requested
        if include_diseases:
            data['disease_details'] = [
                'common_names',
                'description',
                'treatment',
                'classification',
                'url',
            ]

        # Make API request
        response = self.session.post(
            f"{self.BASE_URL}/identification",
            json=data,
            headers=headers,
            timeout=self.timeout
        )
        response.raise_for_status()

        result = response.json()
        formatted_result = self._format_response(result)

        logger.info(f"Plant.id identification successful: {result.get('suggestions', [{}])[0].get('plant_name', 'Unknown')}")

        # Store in cache for 24 hours
        cache.set(cache_key, formatted_result, timeout=CACHE_TIMEOUT_24_HOURS)
        logger.info(f"[CACHE] Stored result for image {image_hash[:8]}... (24h TTL)")

        return formatted_result

    except requests.exceptions.Timeout as e:
        logger.error(f"[ERROR] Plant.id API request timed out: {e}")
        raise  # Re-raise to trigger circuit breaker
    except requests.exceptions.RequestException as e:
        logger.error(f"[ERROR] Plant.id API error: {e}")
        raise  # Re-raise to trigger circuit breaker
    except Exception as e:
        logger.error(f"[ERROR] Unexpected error in Plant.id identification: {e}")
        raise  # Re-raise to trigger circuit breaker
```

Add helper method to check circuit state:

```python
@classmethod
def is_available(cls) -> bool:
    """
    Check if Plant.id API is available (circuit is closed).

    Returns:
        True if circuit is closed, False if open or half-open
    """
    return plant_id_circuit_breaker.current_state == 'closed'

@classmethod
def get_circuit_state(cls) -> Dict[str, Any]:
    """
    Get current circuit breaker state for monitoring.

    Returns:
        Dictionary with circuit state information
    """
    return {
        'name': 'plant_id_api',
        'state': plant_id_circuit_breaker.current_state,
        'fail_count': plant_id_circuit_breaker.fail_counter,
        'success_count': plant_id_circuit_breaker.success_counter,
        'fail_max': plant_id_circuit_breaker.fail_max,
        'reset_timeout': plant_id_circuit_breaker.reset_timeout,
        'last_failure': getattr(plant_id_circuit_breaker, 'last_failure_time', None),
    }
```

### 2.2 PlantNet Service Circuit Breaker

**File:** `/backend/apps/plant_identification/services/plantnet_service.py`

Add similar implementation as Plant.id:

```python
from pybreaker import CircuitBreaker, CircuitBreakerError
from django.conf import settings

from ..constants import (
    # ... existing imports ...
    PLANTNET_CIRCUIT_FAIL_MAX,
    PLANTNET_CIRCUIT_RESET_TIMEOUT,
    PLANTNET_CIRCUIT_SUCCESS_THRESHOLD,
)
from ..circuit_monitoring import PlantNetCircuitListener

# Module-level circuit breaker
plantnet_circuit_breaker = CircuitBreaker(
    fail_max=PLANTNET_CIRCUIT_FAIL_MAX,
    reset_timeout=PLANTNET_CIRCUIT_RESET_TIMEOUT,
    success_threshold=PLANTNET_CIRCUIT_SUCCESS_THRESHOLD,
    name='plantnet_api',
    listeners=[PlantNetCircuitListener()],
    exclude=[ValueError, KeyError],
)

logger.info(
    f"[CIRCUIT] plantnet_api circuit breaker initialized "
    f"(fail_max={PLANTNET_CIRCUIT_FAIL_MAX}, reset_timeout={PLANTNET_CIRCUIT_RESET_TIMEOUT}s)"
)
```

Update `identify_plant` method:

```python
def identify_plant(self,
                  images: List[Union[str, ContentFile]],
                  project: str = 'world',
                  organs: Optional[List[str]] = None,
                  modifiers: Optional[List[str]] = None,
                  include_related_images: bool = False) -> Optional[Dict]:
    """
    Identify a plant from images using PlantNet API with circuit breaker protection.

    Circuit Breaker Protection:
    - Opens after 5 consecutive failures (PLANTNET_CIRCUIT_FAIL_MAX)
    - Blocks requests for 30 seconds (PLANTNET_CIRCUIT_RESET_TIMEOUT)
    - Requires 2 successful calls to close (PLANTNET_CIRCUIT_SUCCESS_THRESHOLD)

    Args:
        images: List of image files or paths (max 5 images)
        project: PlantNet project to use for identification
        organs: List of plant organs in images (leaf, flower, fruit, bark, habit, other)
        modifiers: List of modifiers (entire, partial, scan)
        include_related_images: Include related images in response

    Returns:
        Identification results dictionary or None if circuit is open
    """
    try:
        return plantnet_circuit_breaker.call(
            self._identify_plant_protected,
            images,
            project,
            organs,
            modifiers,
            include_related_images
        )
    except CircuitBreakerError:
        logger.warning(
            "[CIRCUIT] plantnet_api circuit OPEN - skipping API call (fast fail)"
        )
        return None


def _identify_plant_protected(self,
                              images: List[Union[str, ContentFile]],
                              project: str = 'world',
                              organs: Optional[List[str]] = None,
                              modifiers: Optional[List[str]] = None,
                              include_related_images: bool = False) -> Optional[Dict]:
    """
    Internal implementation of plant identification (protected by circuit breaker).
    """
    # Move existing identify_plant implementation here
    # ... (existing code from lines 126-217) ...

    if not images:
        logger.error("No images provided for plant identification")
        return None

    # ... rest of existing implementation ...
```

Add helper methods:

```python
@classmethod
def is_available(cls) -> bool:
    """Check if PlantNet API is available (circuit is closed)."""
    return plantnet_circuit_breaker.current_state == 'closed'

@classmethod
def get_circuit_state(cls) -> Dict[str, Any]:
    """Get current circuit breaker state for monitoring."""
    return {
        'name': 'plantnet_api',
        'state': plantnet_circuit_breaker.current_state,
        'fail_count': plantnet_circuit_breaker.fail_counter,
        'success_count': plantnet_circuit_breaker.success_counter,
        'fail_max': plantnet_circuit_breaker.fail_max,
        'reset_timeout': plantnet_circuit_breaker.reset_timeout,
        'last_failure': getattr(plantnet_circuit_breaker, 'last_failure_time', None),
    }
```

### 2.3 Combined Service Graceful Degradation

**File:** `/backend/apps/plant_identification/services/combined_identification_service.py`

Add imports:

```python
from pybreaker import CircuitBreakerError

from .plant_id_service import plant_id_circuit_breaker, PlantIDAPIService
from .plantnet_service import plantnet_circuit_breaker, PlantNetAPIService
```

Update `_identify_parallel` method:

```python
def _identify_parallel(self, image_data: bytes) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Execute Plant.id and PlantNet API calls in parallel with circuit breaker awareness.

    Graceful Degradation Strategy:
    - Both circuits open: Return error (no APIs available)
    - Plant.id circuit open: Use PlantNet only
    - PlantNet circuit open: Use Plant.id only
    - Both circuits closed: Parallel execution

    Args:
        image_data: Image file bytes

    Returns:
        Tuple of (plant_id_results, plantnet_results)
    """
    api_start_time = time.time()

    # Check circuit states before attempting API calls
    plant_id_available = self.plant_id and plant_id_circuit_breaker.current_state == 'closed'
    plantnet_available = self.plantnet and plantnet_circuit_breaker.current_state == 'closed'

    # Log circuit states
    logger.info(
        f"[CIRCUIT] Circuit states: plant_id={plant_id_circuit_breaker.current_state}, "
        f"plantnet={plantnet_circuit_breaker.current_state}"
    )

    # Graceful degradation: Both circuits open
    if not plant_id_available and not plantnet_available:
        logger.error(
            "[CIRCUIT] DEGRADED: Both API circuits OPEN - no identification sources available"
        )
        # Return None, None to trigger error response in identify_plant
        return None, None

    # Graceful degradation: Plant.id circuit open
    if not plant_id_available:
        logger.warning(
            "[CIRCUIT] DEGRADED: plant_id_api circuit OPEN - using PlantNet only "
            "(no disease detection, lower accuracy)"
        )
        plantnet_results = self._call_plantnet_only(image_data)
        return None, plantnet_results

    # Graceful degradation: PlantNet circuit open
    if not plantnet_available:
        logger.warning(
            "[CIRCUIT] DEGRADED: plantnet_api circuit OPEN - using Plant.id only "
            "(no family/genus enrichment)"
        )
        plant_id_results = self._call_plant_id_only(image_data)
        return plant_id_results, None

    # Both circuits closed - proceed with parallel execution
    logger.info("[PARALLEL] Starting parallel API calls (both circuits CLOSED)")

    def call_plant_id() -> Optional[Dict[str, Any]]:
        """Call Plant.id API in a thread with circuit breaker protection."""
        try:
            plant_id_start = time.time()
            logger.info("[PARALLEL] Plant.id API call started")

            # Create BytesIO object from image data
            image_file = BytesIO(image_data)
            result = self.plant_id.identify_plant(image_file, include_diseases=True)

            duration = time.time() - plant_id_start
            logger.info(f"[SUCCESS] Plant.id completed in {duration:.2f}s")
            return result
        except CircuitBreakerError:
            logger.warning("[CIRCUIT] Plant.id circuit OPENED during execution - fast fail")
            return None
        except Exception as e:
            logger.error(f"[ERROR] Plant.id failed: {e}")
            return None

    def call_plantnet() -> Optional[Dict[str, Any]]:
        """Call PlantNet API in a thread with circuit breaker protection."""
        try:
            plantnet_start = time.time()
            logger.info("[PARALLEL] PlantNet API call started")

            # Create BytesIO object from image data
            image_file = BytesIO(image_data)
            result = self.plantnet.identify_plant(
                image_file,
                organs=['flower', 'leaf', 'fruit', 'bark'],
                include_related_images=True
            )

            duration = time.time() - plantnet_start
            logger.info(f"[SUCCESS] PlantNet completed in {duration:.2f}s")
            return result
        except CircuitBreakerError:
            logger.warning("[CIRCUIT] PlantNet circuit OPENED during execution - fast fail")
            return None
        except Exception as e:
            logger.error(f"[ERROR] PlantNet failed: {e}")
            return None

    # Initialize results
    plant_id_results = None
    plantnet_results = None

    # Submit both API calls to thread pool
    future_plant_id = None
    future_plantnet = None

    if self.plant_id:
        future_plant_id = self.executor.submit(call_plant_id)

    if self.plantnet:
        future_plantnet = self.executor.submit(call_plantnet)

    # Get results with timeout handling
    if future_plant_id:
        try:
            plant_id_results = future_plant_id.result(timeout=PLANT_ID_API_TIMEOUT)
        except FuturesTimeoutError:
            logger.error(f"[ERROR] Plant.id API timeout ({PLANT_ID_API_TIMEOUT}s)")
        except Exception as e:
            logger.error(f"[ERROR] Plant.id execution failed: {e}")

    if future_plantnet:
        try:
            plantnet_results = future_plantnet.result(timeout=PLANTNET_API_TIMEOUT)
        except FuturesTimeoutError:
            logger.error(f"[ERROR] PlantNet API timeout ({PLANTNET_API_TIMEOUT}s)")
        except Exception as e:
            logger.error(f"[ERROR] PlantNet execution failed: {e}")

    parallel_duration = time.time() - api_start_time
    logger.info(f"[PERF] Parallel API execution completed in {parallel_duration:.2f}s")

    return plant_id_results, plantnet_results


def _call_plant_id_only(self, image_data: bytes) -> Optional[Dict[str, Any]]:
    """
    Call Plant.id API only (used when PlantNet circuit is open).

    Args:
        image_data: Image file bytes

    Returns:
        Plant.id results or None
    """
    try:
        logger.info("[FALLBACK] Calling Plant.id only (PlantNet unavailable)")
        image_file = BytesIO(image_data)
        return self.plant_id.identify_plant(image_file, include_diseases=True)
    except Exception as e:
        logger.error(f"[ERROR] Plant.id fallback failed: {e}")
        return None


def _call_plantnet_only(self, image_data: bytes) -> Optional[Dict[str, Any]]:
    """
    Call PlantNet API only (used when Plant.id circuit is open).

    Args:
        image_data: Image file bytes

    Returns:
        PlantNet results or None
    """
    try:
        logger.info("[FALLBACK] Calling PlantNet only (Plant.id unavailable)")
        image_file = BytesIO(image_data)
        return self.plantnet.identify_plant(
            image_file,
            organs=['flower', 'leaf', 'fruit', 'bark'],
            include_related_images=True
        )
    except Exception as e:
        logger.error(f"[ERROR] PlantNet fallback failed: {e}")
        return None
```

Add method to get circuit state summary:

```python
def get_circuit_status(self) -> Dict[str, Any]:
    """
    Get circuit breaker status for both APIs.

    Returns:
        Dictionary with circuit states for monitoring
    """
    return {
        'plant_id': PlantIDAPIService.get_circuit_state() if self.plant_id else None,
        'plantnet': PlantNetAPIService.get_circuit_state() if self.plantnet else None,
        'both_available': (
            plant_id_circuit_breaker.current_state == 'closed' and
            plantnet_circuit_breaker.current_state == 'closed'
        ),
    }
```

---

## Phase 3: API Endpoint Updates

### 3.1 Health Check Endpoint

**File:** `/backend/apps/plant_identification/api/views.py`

Update health check to include circuit states:

```python
from ..services.plant_id_service import PlantIDAPIService
from ..services.plantnet_service import PlantNetAPIService
from ..services.combined_identification_service import CombinedPlantIdentificationService

@api_view(['GET'])
def health_check(request):
    """
    Health check endpoint with circuit breaker status.

    Returns:
        200: All systems operational
        503: One or more circuits open (degraded service)
    """
    service = CombinedPlantIdentificationService()
    circuit_status = service.get_circuit_status()

    plant_id_state = circuit_status.get('plant_id', {}).get('state', 'unknown')
    plantnet_state = circuit_status.get('plantnet', {}).get('state', 'unknown')

    # Determine overall health
    both_available = circuit_status.get('both_available', False)
    degraded = plant_id_state == 'open' or plantnet_state == 'open'

    response_data = {
        'status': 'healthy' if both_available else ('degraded' if degraded else 'unhealthy'),
        'plant_id_available': plant_id_state == 'closed',
        'plantnet_available': plantnet_state == 'closed',
        'circuit_breakers': {
            'plant_id': {
                'state': plant_id_state,
                'fail_count': circuit_status.get('plant_id', {}).get('fail_count', 0),
                'fail_max': circuit_status.get('plant_id', {}).get('fail_max', 0),
            },
            'plantnet': {
                'state': plantnet_state,
                'fail_count': circuit_status.get('plantnet', {}).get('fail_count', 0),
                'fail_max': circuit_status.get('plantnet', {}).get('fail_max', 0),
            },
        },
    }

    # Return 503 if both circuits are open
    if plant_id_state == 'open' and plantnet_state == 'open':
        return Response(response_data, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    return Response(response_data, status=status.HTTP_200_OK)
```

---

## Phase 4: Testing

### 4.1 Unit Tests

**File:** `/backend/apps/plant_identification/tests/test_circuit_breakers.py`

```python
"""
Unit tests for circuit breaker functionality.
"""

import time
from unittest.mock import Mock, patch
from django.test import TestCase
from pybreaker import CircuitBreaker, CircuitBreakerError
import requests

from apps.plant_identification.services.plant_id_service import (
    PlantIDAPIService,
    plant_id_circuit_breaker,
)
from apps.plant_identification.services.plantnet_service import (
    PlantNetAPIService,
    plantnet_circuit_breaker,
)
from apps.plant_identification.services.combined_identification_service import (
    CombinedPlantIdentificationService,
)


class CircuitBreakerTestCase(TestCase):
    """Test circuit breaker behavior for Plant APIs."""

    def setUp(self):
        """Reset circuit breakers before each test."""
        # Reset Plant.id circuit
        plant_id_circuit_breaker._state = plant_id_circuit_breaker._state.__class__()
        plant_id_circuit_breaker._fail_counter = 0
        plant_id_circuit_breaker._success_counter = 0

        # Reset PlantNet circuit
        plantnet_circuit_breaker._state = plantnet_circuit_breaker._state.__class__()
        plantnet_circuit_breaker._fail_counter = 0
        plantnet_circuit_breaker._success_counter = 0

    def test_plant_id_circuit_opens_after_failures(self):
        """Plant.id circuit should open after fail_max consecutive failures."""
        service = PlantIDAPIService()

        with patch.object(service, '_identify_plant_protected') as mock_identify:
            mock_identify.side_effect = requests.exceptions.Timeout("API timeout")

            # Trigger failures (fail_max = 3)
            for i in range(3):
                result = service.identify_plant(b'fake_image_data')
                self.assertIsNone(result)
                self.assertEqual(plant_id_circuit_breaker.fail_counter, i + 1)

            # Next call should return None (circuit open, CircuitBreakerError caught)
            result = service.identify_plant(b'fake_image_data')
            self.assertIsNone(result)
            self.assertEqual(plant_id_circuit_breaker.current_state, 'open')

    def test_plantnet_circuit_opens_after_failures(self):
        """PlantNet circuit should open after fail_max consecutive failures."""
        service = PlantNetAPIService()

        with patch.object(service, '_identify_plant_protected') as mock_identify:
            mock_identify.side_effect = requests.exceptions.RequestException("API error")

            # Trigger failures (fail_max = 5)
            for i in range(5):
                result = service.identify_plant([b'fake_image'])
                self.assertIsNone(result)
                self.assertEqual(plantnet_circuit_breaker.fail_counter, i + 1)

            # Next call should return None (circuit open)
            result = service.identify_plant([b'fake_image'])
            self.assertIsNone(result)
            self.assertEqual(plantnet_circuit_breaker.current_state, 'open')

    def test_combined_service_graceful_degradation(self):
        """Combined service should handle circuit failures gracefully."""
        service = CombinedPlantIdentificationService()

        # Open Plant.id circuit manually
        plant_id_circuit_breaker._state = plant_id_circuit_breaker._open_state
        plant_id_circuit_breaker._fail_counter = plant_id_circuit_breaker.fail_max

        with patch.object(service.plantnet, 'identify_plant') as mock_plantnet:
            mock_plantnet.return_value = {
                'results': [
                    {
                        'species': {
                            'scientificNameWithoutAuthor': 'Monstera deliciosa',
                        },
                        'score': 0.8,
                    }
                ]
            }

            # Should fallback to PlantNet only
            result = service.identify_plant(b'fake_image_data')

            # Verify PlantNet was called
            mock_plantnet.assert_called_once()

            # Verify result contains PlantNet data
            self.assertIsNotNone(result)
            self.assertIsNone(result['primary_identification'])  # Plant.id unavailable
            self.assertIsNotNone(result['combined_suggestions'])  # PlantNet provided

    def test_both_circuits_open_returns_error(self):
        """When both circuits are open, service should return error."""
        service = CombinedPlantIdentificationService()

        # Open both circuits
        plant_id_circuit_breaker._state = plant_id_circuit_breaker._open_state
        plant_id_circuit_breaker._fail_counter = plant_id_circuit_breaker.fail_max
        plantnet_circuit_breaker._state = plantnet_circuit_breaker._open_state
        plantnet_circuit_breaker._fail_counter = plantnet_circuit_breaker.fail_max

        result = service.identify_plant(b'fake_image_data')

        # Verify error response
        self.assertIsNotNone(result)
        self.assertIn('error', result)
        self.assertEqual(len(result['combined_suggestions']), 0)

    def test_circuit_state_inspection(self):
        """Test circuit state inspection methods."""
        # Both circuits should start closed
        self.assertTrue(PlantIDAPIService.is_available())
        self.assertTrue(PlantNetAPIService.is_available())

        # Get state details
        plant_id_state = PlantIDAPIService.get_circuit_state()
        self.assertEqual(plant_id_state['state'], 'closed')
        self.assertEqual(plant_id_state['fail_count'], 0)
        self.assertEqual(plant_id_state['fail_max'], 3)

        plantnet_state = PlantNetAPIService.get_circuit_state()
        self.assertEqual(plantnet_state['state'], 'closed')
        self.assertEqual(plantnet_state['fail_count'], 0)
        self.assertEqual(plantnet_state['fail_max'], 5)
```

### 4.2 Integration Tests

**File:** `/backend/apps/plant_identification/tests/test_circuit_integration.py`

```python
"""
Integration tests for circuit breakers with ThreadPoolExecutor.
"""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from django.test import TestCase
import requests

from apps.plant_identification.services.combined_identification_service import (
    CombinedPlantIdentificationService,
)
from apps.plant_identification.services.plant_id_service import plant_id_circuit_breaker


class CircuitBreakerThreadSafetyTest(TestCase):
    """Test circuit breaker thread safety with ThreadPoolExecutor."""

    def setUp(self):
        """Reset circuit breakers."""
        plant_id_circuit_breaker._state = plant_id_circuit_breaker._state.__class__()
        plant_id_circuit_breaker._fail_counter = 0

    def test_circuit_breaker_thread_safety(self):
        """Verify circuit breaker handles concurrent requests correctly."""
        service = CombinedPlantIdentificationService()

        with patch.object(service.plant_id, '_identify_plant_protected') as mock_identify:
            mock_identify.side_effect = requests.exceptions.Timeout("Concurrent failure")

            # Execute 10 concurrent API calls
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [
                    executor.submit(service.identify_plant, b'fake_image')
                    for _ in range(10)
                ]

                # Collect results
                results = [future.result() for future in futures]

            # Circuit should have opened after fail_max (3) failures
            # Not all 10 calls should have incremented the counter
            self.assertEqual(plant_id_circuit_breaker.current_state, 'open')
            self.assertEqual(plant_id_circuit_breaker.fail_counter, 3)

            # Some results should be None (circuit opened mid-execution)
            none_count = sum(1 for r in results if r.get('primary_identification') is None)
            self.assertGreater(none_count, 0)
```

---

## Phase 5: Deployment

### 5.1 Pre-Deployment Checklist

- [ ] Install pybreaker: `pip install pybreaker`
- [ ] Update requirements.txt
- [ ] Add constants to `constants.py`
- [ ] Create `circuit_monitoring.py`
- [ ] Update `plant_id_service.py`
- [ ] Update `plantnet_service.py`
- [ ] Update `combined_identification_service.py`
- [ ] Update health check endpoint
- [ ] Run unit tests: `python manage.py test apps.plant_identification.tests.test_circuit_breakers`
- [ ] Run integration tests
- [ ] Test in staging environment

### 5.2 Monitoring After Deployment

**Day 1-7 Monitoring:**
- Watch for circuit open events in logs (grep `[CIRCUIT]`)
- Check Redis for circuit state: `redis-cli GET circuit:plant_id_api:state`
- Monitor API response times (should be faster with fast-fail)
- Verify graceful degradation works (disable one API temporarily)

**Metrics to Track:**
```bash
# Circuit state changes
grep "\[CIRCUIT\].*state transition" logs/django.log | wc -l

# Circuit open count
grep "\[CIRCUIT\].*circuit OPENED" logs/django.log | wc -l

# Fallback usage
grep "\[FALLBACK\]" logs/django.log | wc -l
```

### 5.3 Tuning Thresholds

**After 7 days of production data:**
1. Analyze circuit open frequency
2. Check if fail_max is too low (frequent opens) or too high (slow failure detection)
3. Adjust reset_timeout based on actual API recovery times
4. Consider per-error-type thresholds (timeout vs connection errors)

---

## Rollback Plan

If circuit breakers cause issues:

1. **Quick Disable (No Code Changes):**
   ```python
   # In settings.py
   CIRCUIT_BREAKER_ENABLED = False

   # In service files, wrap circuit breaker:
   if getattr(settings, 'CIRCUIT_BREAKER_ENABLED', True):
       return plant_id_circuit_breaker.call(...)
   else:
       return self._identify_plant_protected(...)
   ```

2. **Full Rollback:**
   - Revert service files to previous commit
   - Remove circuit breaker imports
   - Restart Django workers

---

**Implementation Version:** 1.0
**Last Updated:** October 22, 2025
