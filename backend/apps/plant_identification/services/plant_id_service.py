"""
Plant.id (Kindwise) API integration service.

Plant.id provides AI-powered plant identification with disease detection.
Documentation: https://plant.id/docs

Circuit Breaker Protection:
- Opens after 3 consecutive failures
- Resets after 60 seconds
- Requires 2 successes to close
"""

import requests
import logging
import base64
import hashlib
import socket
import os
import threading
import time
from typing import Dict, List, Optional, Any
from django.conf import settings
from django.core.cache import cache
from pybreaker import CircuitBreakerError
from redis import Redis

from ..constants import (
    PLANT_ID_CACHE_TIMEOUT,
    PLANT_ID_API_TIMEOUT_DEFAULT,
    CACHE_TIMEOUT_24_HOURS,
    PLANT_ID_CIRCUIT_FAIL_MAX,
    PLANT_ID_CIRCUIT_RESET_TIMEOUT,
    PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD,
    PLANT_ID_CIRCUIT_TIMEOUT,
    CACHE_LOCK_TIMEOUT,
    CACHE_LOCK_EXPIRE,
    CACHE_LOCK_AUTO_RENEWAL,
    CACHE_LOCK_BLOCKING,
    CACHE_LOCK_ID_PREFIX,
)
from ..circuit_monitoring import create_monitored_circuit
from apps.core.exceptions import ExternalAPIError
from .quota_manager import QuotaManager, QuotaExceeded

logger = logging.getLogger(__name__)

# Module-level circuit breaker (shared across all instances for proper failure tracking)
_plant_id_circuit, _plant_id_monitor, _plant_id_stats = create_monitored_circuit(
    service_name='plant_id_api',
    fail_max=PLANT_ID_CIRCUIT_FAIL_MAX,
    reset_timeout=PLANT_ID_CIRCUIT_RESET_TIMEOUT,
    success_threshold=PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD,
    timeout=PLANT_ID_CIRCUIT_TIMEOUT,
)


def get_lock_id() -> str:
    """Generate unique lock ID for debugging which process holds the lock."""
    hostname = socket.gethostname()
    pid = os.getpid()
    thread_id = threading.get_ident()
    return f"{CACHE_LOCK_ID_PREFIX}-{hostname}-{pid}-{thread_id}"


class PlantIDAPIService:
    """
    Service for interacting with the Plant.id (Kindwise) API.
    Provides AI-powered plant identification with disease detection.
    """

    BASE_URL = "https://api.plant.id/v3"  # Correct URL format per official docs
    API_VERSION = "v3"  # Include in cache key for version-specific caching
    CACHE_TIMEOUT = PLANT_ID_CACHE_TIMEOUT

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Plant.id API service with circuit breaker and distributed lock support.

        Args:
            api_key: Plant.id API key. If not provided, will use settings.PLANT_ID_API_KEY
        """
        self.api_key = api_key or getattr(settings, 'PLANT_ID_API_KEY', None)
        if not self.api_key:
            logger.error("Plant.id API key not configured")
            raise ValueError("PLANT_ID_API_KEY must be set in Django settings")

        self.session = requests.Session()
        self.timeout = getattr(settings, 'PLANT_ID_API_TIMEOUT', PLANT_ID_API_TIMEOUT_DEFAULT)

        # Reference module-level circuit breaker
        self.circuit = _plant_id_circuit
        self.circuit_stats = _plant_id_stats

        # Get Redis connection for distributed locks (cache stampede prevention)
        self.redis_client = self._get_redis_connection()

        # Initialize quota manager for API quota tracking
        self.quota_manager = QuotaManager()

    def _get_redis_connection(self) -> Optional[Redis]:
        """
        Get Redis connection from django-redis for distributed lock operations.

        Verifies Redis is responsive with a ping check to prevent silent failures.

        Returns:
            Redis client or None if Redis not configured/unresponsive
        """
        try:
            from django_redis import get_redis_connection
            redis_client = get_redis_connection("default")

            # Verify Redis is responsive (prevents silent failures)
            redis_client.ping()

            logger.info("[LOCK] Redis connection verified for distributed locks")
            return redis_client
        except Exception as e:
            logger.warning(f"[LOCK] Redis not available for distributed locks: {e}")
            return None
    
    def identify_plant(self, image_file, include_diseases: bool = True) -> Dict[str, Any]:
        """
        Identify a plant from an image using Plant.id API with circuit breaker protection.

        Circuit Breaker Pattern:
        1. Check cache (before circuit breaker - instant if cached)
        2. Acquire distributed lock to prevent cache stampede
        3. Double-check cache (another process may have populated it)
        4. Call API through circuit breaker (protected from cascading failures)
        5. Fast-fail if circuit is open (no wasted API calls)

        Cache Stampede Prevention:
        - Uses Redis distributed lock to ensure only one process calls API
        - Other concurrent requests wait for lock, then get cached result
        - Prevents duplicate API calls for same image (saves quota + money)

        Args:
            image_file: Django file object or file bytes
            include_diseases: Whether to include disease detection

        Returns:
            Dictionary containing identification results

        Raises:
            ExternalAPIError: If Plant.id service is unavailable (circuit open)
            requests.exceptions.Timeout: If API request times out
            requests.exceptions.RequestException: If API request fails
        """
        try:
            # Convert image to bytes
            if hasattr(image_file, 'read'):
                image_data = image_file.read()
            else:
                image_data = image_file

            # Generate cache key from image hash (includes API version for cache invalidation)
            image_hash = hashlib.sha256(image_data).hexdigest()
            cache_key = f"plant_id:{self.API_VERSION}:{image_hash}:{include_diseases}"

            # Check cache first (before circuit breaker check - fastest path)
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info(f"[CACHE] HIT for image {image_hash[:8]}... (instant response)")
                return cached_result

            # Cache miss - check quota before making API call
            logger.info(f"[CACHE] MISS for image {image_hash[:8]}... (checking quota)")

            # Check quota before acquiring lock and making API call
            if not self.quota_manager.can_call_plant_id():
                daily_usage = self.quota_manager.get_plant_id_daily_usage()
                logger.error(f"[QUOTA] Plant.id daily quota EXHAUSTED ({daily_usage}/3 used)")
                raise QuotaExceeded(
                    "Plant.id daily API quota exhausted. Please try again tomorrow or upgrade your plan."
                )

            # Quota available - acquire distributed lock to prevent cache stampede
            logger.info(f"[QUOTA] Plant.id quota available (acquiring lock)")

            # Use distributed lock if Redis is available
            if self.redis_client:
                import redis_lock

                lock_key = f"lock:plant_id:{self.API_VERSION}:{image_hash}:{include_diseases}"
                lock_id = get_lock_id()

                logger.info(f"[LOCK] Attempting to acquire lock for {image_hash[:8]}... (id: {lock_id})")

                lock = redis_lock.Lock(
                    self.redis_client,
                    lock_key,
                    expire=CACHE_LOCK_EXPIRE,
                    auto_renewal=CACHE_LOCK_AUTO_RENEWAL,
                    id=lock_id,
                )

                # Try to acquire lock (blocks if another process has it)
                if lock.acquire(blocking=CACHE_LOCK_BLOCKING, timeout=CACHE_LOCK_TIMEOUT):
                    try:
                        logger.info(f"[LOCK] Lock acquired for {image_hash[:8]}... (id: {lock_id})")

                        # Double-check cache (another process may have populated it)
                        cached_result = cache.get(cache_key)
                        if cached_result:
                            logger.info(
                                f"[LOCK] Cache populated by another process for {image_hash[:8]}... "
                                f"(skipping API call)"
                            )
                            return cached_result

                        # Call API through circuit breaker
                        logger.info(f"[LOCK] Calling Plant.id API for {image_hash[:8]}...")
                        result = self.circuit.call(
                            self._call_plant_id_api,
                            image_data,
                            cache_key,
                            image_hash,
                            include_diseases
                        )

                        return result

                    finally:
                        # Always release lock - wrap in try/except for error handling
                        try:
                            lock.release()
                            logger.info(f"[LOCK] Released lock for {image_hash[:8]}... (id: {lock_id})")
                        except Exception as e:
                            logger.error(
                                f"[LOCK] Failed to release lock for {image_hash[:8]}... (id: {lock_id}): {e}. "
                                f"Lock will auto-expire after {CACHE_LOCK_EXPIRE}s"
                            )
                else:
                    # Lock acquisition timed out - check cache one more time
                    # (another process may have finished and populated cache)
                    cached_result = cache.get(cache_key)
                    if cached_result:
                        logger.info(
                            f"[LOCK] Lock timeout resolved - cache populated by another process "
                            f"for {image_hash[:8]}... (skipping API call)"
                        )
                        return cached_result

                    logger.warning(
                        f"[LOCK] Lock acquisition timed out for {image_hash[:8]}... "
                        f"after {CACHE_LOCK_TIMEOUT}s (proceeding without lock - cache stampede risk)"
                    )
                    # Fall through to direct API call without lock
            else:
                logger.warning("[LOCK] Redis not available - skipping distributed lock (cache stampede possible)")

            # Fallback: Call API without lock (if Redis unavailable or lock timeout)
            # One final cache check to minimize duplicate API calls
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info(f"[CACHE] Last-chance cache hit for {image_hash[:8]}... (skipping API call)")
                return cached_result

            logger.info(f"[CACHE] Calling Plant.id API for {image_hash[:8]}... (no lock)")
            result = self.circuit.call(
                self._call_plant_id_api,
                image_data,
                cache_key,
                image_hash,
                include_diseases
            )

            return result

        except CircuitBreakerError as e:
            logger.error(f"[CIRCUIT] Plant.id circuit is OPEN - fast failing without API call")
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
    ) -> Dict[str, Any]:
        """
        Protected API call wrapped by circuit breaker.

        This method is called by the circuit breaker and will trigger
        circuit state changes on success/failure.

        Args:
            image_data: Image bytes
            cache_key: Redis cache key
            image_hash: SHA-256 hash of image (for logging)
            include_diseases: Whether to include disease detection

        Returns:
            Formatted API response

        Raises:
            requests.exceptions.RequestException: On API failure (triggers circuit)
        """
        # Encode image
        encoded_image = base64.b64encode(image_data).decode('ascii')

        # Prepare request headers
        headers = {
            'Api-Key': self.api_key,
            'Content-Type': 'application/json',
        }

        # Plant.id v3 API uses query params for details, not JSON body
        # Only images go in the JSON body
        details = ','.join([
            'common_names',
            'taxonomy',
            'url',
            'description',
            'synonyms',
            'image',
            'edible_parts',
            'watering',
            'propagation_methods',
        ])

        # Make identification API request
        response = self.session.post(
            f"{self.BASE_URL}/identification",
            params={'details': details},
            headers=headers,
            json={'images': [encoded_image]},
            timeout=self.timeout
        )
        response.raise_for_status()
        identification_result = response.json()

        # Get health assessment if requested (separate endpoint in v3)
        health_result = None
        if include_diseases:
            try:
                health_response = self.session.post(
                    f"{self.BASE_URL}/health_assessment",
                    params={'details': 'description,treatment,classification'},
                    headers=headers,
                    json={'images': [encoded_image]},
                    timeout=self.timeout
                )
                health_response.raise_for_status()
                health_result = health_response.json()
            except Exception as e:
                logger.warning(f"[HEALTH] Health assessment failed: {e}, continuing with identification only")

        # Format combined results
        formatted_result = self._format_response(identification_result, health_result)

        # Log success
        suggestions = identification_result.get('result', {}).get('classification', {}).get('suggestions', [])
        if suggestions:
            logger.info(f"Plant.id identification successful: {suggestions[0].get('name', 'Unknown')}")

        # Increment quota counter after successful API call
        self.quota_manager.increment_plant_id()

        # Store in cache for 24 hours
        cache.set(cache_key, formatted_result, timeout=CACHE_TIMEOUT_24_HOURS)
        logger.info(f"[CACHE] Stored result for image {image_hash[:8]}... (24h TTL)")

        return formatted_result
    
    def _format_response(self, identification_response: Dict[str, Any], health_response: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Format Plant.id API v3 response into a standardized structure.

        Args:
            identification_response: Raw identification API response
            health_response: Optional raw health assessment API response

        Returns:
            Formatted response dictionary
        """
        # Parse identification results (v3 structure)
        result = identification_response.get('result', {})
        classification = result.get('classification', {})
        suggestions = classification.get('suggestions', [])

        formatted_suggestions = []
        for suggestion in suggestions[:5]:  # Top 5 results
            details = suggestion.get('details', {})

            # Extract description value (can be string or dict with 'value' key)
            description = details.get('description')
            if isinstance(description, dict):
                description = description.get('value')

            formatted_suggestions.append({
                'plant_name': suggestion.get('name'),  # v3 uses 'name', not 'plant_name'
                'scientific_name': suggestion.get('name'),  # Scientific name is the 'name' field
                'probability': suggestion.get('probability', 0),
                'common_names': details.get('common_names', []),
                'description': description,
                'taxonomy': details.get('taxonomy', {}),
                'edible_parts': details.get('edible_parts'),
                'watering': details.get('watering', {}).get('max', 'Unknown') if isinstance(details.get('watering'), dict) else details.get('watering'),
                'propagation_methods': details.get('propagation_methods'),
                'similar_images': suggestion.get('similar_images', []),
                'url': details.get('url'),
                'source': 'plant_id',
            })

        # Parse health assessment if available (v3 structure)
        disease_info = None
        if health_response:
            health_result = health_response.get('result', {})
            is_healthy_info = health_result.get('is_healthy', {})
            disease_data = health_result.get('disease', {})
            disease_suggestions = disease_data.get('suggestions', [])

            if disease_suggestions:
                top_disease = disease_suggestions[0]
                disease_details = top_disease.get('details', {})

                # Extract treatment info
                treatment = disease_details.get('treatment', {})
                treatment_text = None
                if isinstance(treatment, dict):
                    # Combine biological, chemical, and prevention methods
                    methods = []
                    if treatment.get('biological'):
                        methods.extend(treatment['biological'])
                    if treatment.get('chemical'):
                        methods.extend(treatment['chemical'])
                    if treatment.get('prevention'):
                        methods.extend(treatment['prevention'])
                    treatment_text = ' '.join(methods) if methods else None
                else:
                    treatment_text = treatment

                disease_info = {
                    'is_healthy': is_healthy_info.get('binary', True),
                    'is_plant': result.get('is_plant', {}).get('binary', True),
                    'disease_name': top_disease.get('name'),
                    'probability': top_disease.get('probability'),
                    'description': disease_details.get('description'),
                    'treatment': treatment_text,
                    'classification': disease_details.get('classification', []),
                }

        return {
            'suggestions': formatted_suggestions,
            'health_assessment': disease_info,
            'top_suggestion': formatted_suggestions[0] if formatted_suggestions else None,
            'confidence': formatted_suggestions[0]['probability'] if formatted_suggestions else 0,
        }
    
    def get_plant_details(self, plant_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific plant.
        (Note: Plant.id doesn't have a direct plant details endpoint,
        this would require identification first)
        
        Args:
            plant_name: Name of the plant
            
        Returns:
            Plant details dictionary or None
        """
        # Check cache first
        cache_key = f"plant_id_details_{plant_name.lower()}"
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"Retrieved plant details from cache: {plant_name}")
            return cached_data
        
        # Plant.id doesn't have a direct search endpoint
        # Would need to use image identification instead
        logger.warning("Plant.id doesn't support direct plant name lookup")
        return None
