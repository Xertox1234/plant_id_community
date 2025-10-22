# Circuit Breaker Implementation Status

## Progress: 40% Complete ✅

### Completed Steps

1. ✅ **Installed pybreaker v1.4.1**
   - Added to `requirements.txt`
   - Installed in virtual environment

2. ✅ **Added Circuit Breaker Constants** (`constants.py`)
   ```python
   # Plant.id API Circuit Breaker (Conservative)
   PLANT_ID_CIRCUIT_FAIL_MAX = 3
   PLANT_ID_CIRCUIT_RESET_TIMEOUT = 60
   PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD = 2

   # PlantNet API Circuit Breaker (Tolerant)
   PLANTNET_CIRCUIT_FAIL_MAX = 5
   PLANTNET_CIRCUIT_RESET_TIMEOUT = 30
   PLANTNET_CIRCUIT_SUCCESS_THRESHOLD = 2
   ```

3. ✅ **Created Circuit Monitoring Module** (`circuit_monitoring.py`)
   - `CircuitMonitor` class with event listeners
   - `CircuitStats` helper for health checks
   - `create_monitored_circuit()` factory function
   - Bracketed logging pattern ([CIRCUIT] prefix)

### Remaining Steps

4. ⏳ **Add Circuit Breaker to PlantIDAPIService**

   **File:** `apps/plant_identification/services/plant_id_service.py`

   **Changes needed:**
   ```python
   # At module level (after imports)
   from ..circuit_monitoring import create_monitored_circuit
   from ..constants import (
       PLANT_ID_CIRCUIT_FAIL_MAX,
       PLANT_ID_CIRCUIT_RESET_TIMEOUT,
       PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD,
       PLANT_ID_CIRCUIT_TIMEOUT,
   )

   # Create module-level circuit breaker (shared across instances)
   _plant_id_circuit, _plant_id_monitor, _plant_id_stats = create_monitored_circuit(
       service_name='plant_id_api',
       fail_max=PLANT_ID_CIRCUIT_FAIL_MAX,
       reset_timeout=PLANT_ID_CIRCUIT_RESET_TIMEOUT,
       success_threshold=PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD,
       timeout=PLANT_ID_CIRCUIT_TIMEOUT,
   )

   class PlantIDAPIService:
       def __init__(self, api_key: Optional[str] = None):
           # ... existing code ...
           self.circuit = _plant_id_circuit  # Reference module-level circuit
           self.circuit_stats = _plant_id_stats

       def identify_plant(self, image_file, include_diseases: bool = True) -> Dict:
           """Identify plant with circuit breaker protection."""
           # ... existing cache check code ...

           # Wrap API call with circuit breaker
           try:
               result = self.circuit.call(
                   self._call_api_protected,
                   image_data,
                   include_diseases,
                   cache_key,
                   image_hash
               )
               return result
           except CircuitBreakerError as e:
               logger.error(f"[CIRCUIT] Plant.id circuit is OPEN: {e}")
               raise ExternalAPIError(
                   "Plant.id service temporarily unavailable. Please try again in a few moments.",
                   status_code=503
               )

       def _call_api_protected(self, image_data, include_diseases, cache_key, image_hash):
           """Protected API call (wrapped by circuit breaker)."""
           # Move existing API call logic here
           # ... API request code ...
           # ... cache storage code ...
           return formatted_result
   ```

5. ⏳ **Add Circuit Breaker to PlantNetAPIService**

   **File:** `apps/plant_identification/services/plantnet_service.py`

   **Changes:** Same pattern as PlantIDAPIService but with PlantNet constants

6. ⏳ **Update CombinedIdentificationService with Graceful Degradation**

   **File:** `apps/plant_identification/services/combined_identification_service.py`

   **Changes needed:**
   ```python
   def _identify_parallel(self, image_data: bytes) -> Tuple[Optional[Dict], Optional[Dict]]:
       """Execute API calls with circuit-aware graceful degradation."""

       # Check circuit states before calling
       plant_id_available = self.plant_id.circuit_stats.is_healthy() if self.plant_id else False
       plantnet_available = self.plantnet.circuit_stats.is_healthy() if self.plantnet else False

       # Log degraded state
       if not plant_id_available:
           logger.warning("[CIRCUIT] DEGRADED: Plant.id circuit OPEN, using PlantNet only")
       if not plantnet_available:
           logger.warning("[CIRCUIT] DEGRADED: PlantNet circuit OPEN, using Plant.id only")
       if not plant_id_available and not plantnet_available:
           logger.error("[CIRCUIT] CRITICAL: Both circuits OPEN - no API available")
           raise ExternalAPIError(
               "Plant identification services temporarily unavailable",
               status_code=503
           )

       # Call only available APIs
       def call_plant_id() -> Optional[Dict]:
           if not plant_id_available:
               return None
           try:
               return self.plant_id.identify_plant(...)
           except CircuitBreakerError:
               logger.warning("[CIRCUIT] Plant.id circuit opened during call")
               return None

       # ... similar for PlantNet ...

       # Submit only available API calls
       future_plant_id = self.executor.submit(call_plant_id) if plant_id_available else None
       future_plantnet = self.executor.submit(call_plantnet) if plantnet_available else None
   ```

7. ⏳ **Update Health Check Endpoint**

   **File:** `apps/plant_identification/api/simple_views.py`

   **Changes needed:**
   ```python
   @api_view(['GET'])
   @permission_classes([AllowAny])
   def health_check(request):
       """Health check with circuit breaker status."""
       try:
           service = CombinedPlantIdentificationService()

           # Get circuit statuses
           plant_id_status = None
           plantnet_status = None

           if service.plant_id:
               plant_id_status = service.plant_id.circuit_stats.get_status()

           if service.plantnet:
               plantnet_status = service.plantnet.circuit_stats.get_status()

           # Determine overall health
           overall_health = 'healthy'
           if plant_id_status and plant_id_status['state'] == 'open':
               overall_health = 'degraded' if plantnet_status else 'unhealthy'
           if plantnet_status and plantnet_status['state'] == 'open':
               overall_health = 'degraded' if plant_id_status else 'unhealthy'

           return Response({
               'status': overall_health,
               'circuit_breakers': {
                   'plant_id': plant_id_status,
                   'plantnet': plantnet_status,
               },
               'message': 'Plant identification service is ready'
           }, status=status.HTTP_200_OK)

       except Exception as e:
           logger.error(f"Health check failed: {str(e)}")
           return Response({
               'status': 'unhealthy',
               'error': str(e)
           }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
   ```

8. ⏳ **Create Unit Tests**

   **File:** `apps/plant_identification/tests/test_circuit_breakers.py`

   **Test scenarios:**
   - Test circuit opens after N failures
   - Test circuit half-opens for recovery
   - Test circuit closes after successful recovery
   - Test graceful degradation (one API down, other works)
   - Test fast-fail when circuit is open
   - Test circuit state persistence (if using Redis storage)

### Implementation Code Snippets

#### PlantIDAPIService Circuit Breaker Integration

```python
# At top of file
from pybreaker import CircuitBreakerError
from ..circuit_monitoring import create_monitored_circuit
from ..constants import (
    PLANT_ID_CIRCUIT_FAIL_MAX,
    PLANT_ID_CIRCUIT_RESET_TIMEOUT,
    PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD,
    PLANT_ID_CIRCUIT_TIMEOUT,
)
from apps.core.exceptions import ExternalAPIError

# Module-level circuit breaker (shared across all instances)
_plant_id_circuit, _plant_id_monitor, _plant_id_stats = create_monitored_circuit(
    service_name='plant_id_api',
    fail_max=PLANT_ID_CIRCUIT_FAIL_MAX,
    reset_timeout=PLANT_ID_CIRCUIT_RESET_TIMEOUT,
    success_threshold=PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD,
    timeout=PLANT_ID_CIRCUIT_TIMEOUT,
)

class PlantIDAPIService:
    """Plant.id API service with circuit breaker protection."""

    def __init__(self, api_key: Optional[str] = None):
        # ... existing initialization ...
        self.circuit = _plant_id_circuit
        self.circuit_stats = _plant_id_stats

    def identify_plant(self, image_file, include_diseases: bool = True) -> Dict:
        """Identify plant with circuit breaker and caching."""
        try:
            # Convert image to bytes
            if hasattr(image_file, 'read'):
                image_data = image_file.read()
            else:
                image_data = image_file

            # Generate cache key
            image_hash = hashlib.sha256(image_data).hexdigest()
            cache_key = f"plant_id:{self.API_VERSION}:{image_hash}:{include_diseases}"

            # Check cache first (before circuit breaker)
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info(f"[CACHE] HIT for image {image_hash[:8]}...")
                return cached_result

            # Cache miss - call API with circuit breaker protection
            logger.info(f"[CACHE] MISS for image {image_hash[:8]}...")

            # Call API through circuit breaker
            result = self.circuit.call(
                self._call_plant_id_api,
                image_data,
                cache_key,
                image_hash,
                include_diseases
            )

            return result

        except CircuitBreakerError as e:
            logger.error(f"[CIRCUIT] Plant.id circuit is OPEN - fast failing")
            raise ExternalAPIError(
                "Plant.id service is temporarily unavailable. Please try again in a few moments.",
                status_code=503
            )
        except requests.exceptions.Timeout:
            logger.error("Plant.id API request timed out")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Plant.id API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Plant.id identification: {e}")
            raise

    def _call_plant_id_api(
        self,
        image_data: bytes,
        cache_key: str,
        image_hash: str,
        include_diseases: bool
    ) -> Dict:
        """
        Protected API call wrapped by circuit breaker.

        This method is called by the circuit breaker and will trigger
        state changes on success/failure.
        """
        # Encode image
        encoded_image = base64.b64encode(image_data).decode('utf-8')

        # Prepare request
        headers = {
            'Api-Key': self.api_key,
            'Content-Type': 'application/json',
        }

        data = {
            'images': [encoded_image],
            'modifiers': ['crops', 'similar_images'],
            'plant_language': 'en',
            'plant_details': [
                'common_names', 'taxonomy', 'url', 'description',
                'synonyms', 'image', 'edible_parts', 'watering',
                'propagation_methods',
            ],
        }

        if include_diseases:
            data['disease_details'] = [
                'common_names', 'description', 'treatment',
                'classification', 'url',
            ]

        # Make API request (will be timed by circuit breaker)
        response = self.session.post(
            f"{self.BASE_URL}/identification",
            json=data,
            headers=headers,
            timeout=self.timeout
        )
        response.raise_for_status()

        result = response.json()
        formatted_result = self._format_response(result)

        logger.info(f"Plant.id identification successful")

        # Cache result
        cache.set(cache_key, formatted_result, timeout=CACHE_TIMEOUT_24_HOURS)
        logger.info(f"[CACHE] Stored result for image {image_hash[:8]}...")

        return formatted_result
```

### Testing Commands

```bash
# Run Django system checks
python manage.py check

# Test circuit breaker imports
python manage.py shell
>>> from apps.plant_identification.circuit_monitoring import create_monitored_circuit
>>> circuit, monitor, stats = create_monitored_circuit('test', fail_max=3, reset_timeout=60)
>>> stats.get_status()

# Run circuit breaker tests (once created)
python manage.py test apps.plant_identification.tests.test_circuit_breakers
```

### Monitoring Circuit Breakers

```bash
# Watch logs for circuit events
tail -f logs/django.log | grep "\[CIRCUIT\]"

# Check health endpoint
curl http://localhost:8000/api/v1/plant-identification/health/ | jq

# Redis circuit state (if using Redis storage)
redis-cli
> KEYS circuit:*
> GET circuit:plant_id_api:state
```

### Next Session TODO

1. Complete PlantIDAPIService integration (refactor identify_plant method)
2. Complete PlantNetAPIService integration
3. Update CombinedIdentificationService with graceful degradation
4. Update health check endpoint
5. Create comprehensive unit tests
6. Test manually with development server
7. Run code-review-specialist agent

### Estimated Time Remaining

- PlantIDAPIService: 1 hour
- PlantNetAPIService: 1 hour
- CombinedIdentificationService: 1 hour
- Health check: 30 minutes
- Unit tests: 2 hours
- Testing & review: 1 hour

**Total: ~6.5 hours**

### Files Modified So Far

1. ✅ `backend/requirements.txt` - Added pybreaker
2. ✅ `backend/apps/plant_identification/constants.py` - Added circuit constants
3. ✅ `backend/apps/plant_identification/circuit_monitoring.py` - Created monitoring module

### Files To Modify

4. ⏳ `backend/apps/plant_identification/services/plant_id_service.py`
5. ⏳ `backend/apps/plant_identification/services/plantnet_service.py`
6. ⏳ `backend/apps/plant_identification/services/combined_identification_service.py`
7. ⏳ `backend/apps/plant_identification/api/simple_views.py`
8. ⏳ `backend/apps/plant_identification/tests/test_circuit_breakers.py` (new file)

### Benefits Achieved (After Full Implementation)

- **99.97% faster failed responses** (30s timeout → <10ms fast-fail)
- **Cascading failure prevention** (open circuit blocks calls)
- **Automatic recovery testing** (half-open state)
- **Resource protection** (no wasted API quota)
- **Visibility** (bracketed logging for monitoring)
- **Graceful degradation** (one API fails, other continues)
