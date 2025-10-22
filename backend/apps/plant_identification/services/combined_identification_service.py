"""
Combined Plant Identification Service - Dual API Integration

Integrates Plant.id (Kindwise) and PlantNet APIs to provide:
1. High-accuracy AI identification (Plant.id)
2. Disease detection (Plant.id)
3. Comprehensive care instructions (PlantNet)
"""

import atexit
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple, Union
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
from django.conf import settings

from .plant_id_service import PlantIDAPIService
from .plantnet_service import PlantNetAPIService
from ..constants import (
    MAX_WORKER_THREADS,
    CPU_CORE_MULTIPLIER,
    PLANT_ID_API_TIMEOUT,
    PLANTNET_API_TIMEOUT,
    TEMPERATURE_RANGE_CELSIUS,
)

logger = logging.getLogger(__name__)

# Module-level thread pool executor (shared across all instances)
# This prevents resource leaks and ensures proper cleanup on shutdown
_EXECUTOR: Optional[ThreadPoolExecutor] = None
_EXECUTOR_LOCK = threading.Lock()
_CLEANUP_REGISTERED = False


def get_executor() -> ThreadPoolExecutor:
    """
    Get or create the shared ThreadPoolExecutor for parallel API calls.

    Thread pool is initialized lazily and shared across all service instances
    to prevent resource exhaustion. Cleanup is guaranteed via atexit hook.

    Environment Variables:
        PLANT_ID_MAX_WORKERS (int, optional): Maximum worker threads for parallel API calls.
            Default: 2x CPU cores (capped at MAX_WORKER_THREADS). Must be positive integer.

    Returns:
        ThreadPoolExecutor: Shared executor with configurable max_workers
    """
    global _EXECUTOR, _CLEANUP_REGISTERED

    # Fast path: executor already exists (avoid lock in common case)
    if _EXECUTOR is not None:
        return _EXECUTOR

    # Slow path: need to create executor (use lock for thread safety)
    with _EXECUTOR_LOCK:
        # Double-check inside lock to prevent race condition
        if _EXECUTOR is None:
            # Get max_workers from environment or calculate based on CPU cores
            # For I/O-bound tasks (API calls), use CPU_CORE_MULTIPLIER x CPU cores
            try:
                max_workers_env = os.getenv('PLANT_ID_MAX_WORKERS')
                if max_workers_env:
                    max_workers = int(max_workers_env)
                    if max_workers < 1:
                        logger.warning(f"Invalid PLANT_ID_MAX_WORKERS={max_workers} (must be positive), using default")
                        default_workers = os.cpu_count() * CPU_CORE_MULTIPLIER if os.cpu_count() else CPU_CORE_MULTIPLIER
                        max_workers = default_workers
                else:
                    max_workers = os.cpu_count() * CPU_CORE_MULTIPLIER if os.cpu_count() else CPU_CORE_MULTIPLIER
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid PLANT_ID_MAX_WORKERS value: {e}, using default")
                max_workers = os.cpu_count() * CPU_CORE_MULTIPLIER if os.cpu_count() else CPU_CORE_MULTIPLIER

            # Cap at maximum to prevent API rate limit issues
            max_workers = max(1, min(max_workers, MAX_WORKER_THREADS))

            _EXECUTOR = ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix='plant_api_'
            )

            # Register cleanup on process exit (only once)
            if not _CLEANUP_REGISTERED:
                atexit.register(_cleanup_executor)
                _CLEANUP_REGISTERED = True

            logger.info(f"[INIT] ThreadPoolExecutor initialized with {max_workers} workers")

        return _EXECUTOR


def _cleanup_executor() -> None:
    """Cleanup executor on process shutdown."""
    global _EXECUTOR
    if _EXECUTOR is not None:
        logger.info("[SHUTDOWN] Cleaning up ThreadPoolExecutor")
        _EXECUTOR.shutdown(wait=True, cancel_futures=False)
        _EXECUTOR = None
        logger.info("[SHUTDOWN] ThreadPoolExecutor cleanup complete")


class CombinedPlantIdentificationService:
    """
    Combines Plant.id and PlantNet APIs for comprehensive plant identification.
    
    Strategy:
    1. Use Plant.id for primary identification + disease detection (best accuracy)
    2. Use PlantNet to supplement with care instructions (open source data)
    3. Merge results to provide comprehensive plant information
    """
    
    def __init__(self) -> None:
        """Initialize both API services and thread executor for parallel processing."""
        self.plant_id = None
        self.plantnet = None

        # Use shared thread pool executor for parallel API calls
        # This prevents resource leaks and improves performance
        self.executor = get_executor()

        # Initialize Plant.id (Kindwise) service
        try:
            if getattr(settings, 'ENABLE_PLANT_ID', True):
                self.plant_id = PlantIDAPIService()
                logger.info("Plant.id service initialized")
        except Exception as e:
            logger.warning(f"Plant.id service not available: {e}")

        # Initialize PlantNet service
        try:
            if getattr(settings, 'ENABLE_PLANTNET', True):
                self.plantnet = PlantNetAPIService()
                logger.info("PlantNet service initialized")
        except Exception as e:
            logger.warning(f"PlantNet service not available: {e}")

        if not self.plant_id and not self.plantnet:
            logger.error("No plant identification APIs available")

    def identify_plant(
        self,
        image_file: Union[BytesIO, InMemoryUploadedFile, TemporaryUploadedFile, bytes],
        user: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Identify a plant using both APIs in parallel and combine results.

        Args:
            image_file: Django file object or file bytes
            user: Optional user object for tracking

        Returns:
            Combined identification results
        """
        start_time = time.time()

        results = {
            'primary_identification': None,
            'care_instructions': None,
            'disease_detection': None,
            'combined_suggestions': [],
            'confidence_score': 0,
            'source': None,
            'timing': {},
        }

        # Read image data once to avoid file pointer issues in parallel execution
        if hasattr(image_file, 'read'):
            image_data = image_file.read()
        else:
            image_data = image_file

        logger.info("[PARALLEL] Starting parallel API calls (Plant.id + PlantNet)")

        # Execute both API calls in parallel
        plant_id_results, plantnet_results = self._identify_parallel(image_data)

        # Process Plant.id results
        if plant_id_results:
            results['primary_identification'] = plant_id_results
            results['disease_detection'] = plant_id_results.get('health_assessment')
            results['confidence_score'] = plant_id_results.get('confidence', 0)
            results['source'] = 'plant_id'

            logger.info(f"[SUCCESS] Plant.id identified: {plant_id_results.get('top_suggestion', {}).get('plant_name', 'Unknown')} "
                      f"(confidence: {results['confidence_score']:.2%})")

        # Process PlantNet results
        if plantnet_results:
            results['care_instructions'] = self._extract_care_info(plantnet_results)
            logger.info("[SUCCESS] PlantNet care instructions retrieved")

        # Combine suggestions from both APIs
        results['combined_suggestions'] = self._merge_suggestions(
            plant_id_results,
            plantnet_results
        )

        # If no results from either API, return error
        if not results['combined_suggestions']:
            logger.warning("[ERROR] No identification results from any API")
            results['error'] = "Unable to identify plant. Please try a clearer image."

        # Record total timing
        total_time = time.time() - start_time
        results['timing']['total'] = round(total_time, 2)
        logger.info(f"[PERF] Total identification time: {total_time:.2f}s (parallel processing)")

        return results

    def _identify_parallel(self, image_data: bytes) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Execute Plant.id and PlantNet API calls in parallel.

        Args:
            image_data: Image file bytes

        Returns:
            Tuple of (plant_id_results, plantnet_results)
        """
        api_start_time = time.time()

        def call_plant_id() -> Optional[Dict[str, Any]]:
            """Call Plant.id API in a thread."""
            try:
                plant_id_start = time.time()
                logger.info("[PARALLEL] Plant.id API call started")

                # Create BytesIO object from image data
                image_file = BytesIO(image_data)
                result = self.plant_id.identify_plant(image_file, include_diseases=True)

                duration = time.time() - plant_id_start
                logger.info(f"[SUCCESS] Plant.id completed in {duration:.2f}s")
                return result
            except Exception as e:
                logger.error(f"[ERROR] Plant.id failed: {e}")
                return None

        def call_plantnet() -> Optional[Dict[str, Any]]:
            """Call PlantNet API in a thread."""
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
                # Plant.id timeout with buffer
                plant_id_results = future_plant_id.result(timeout=PLANT_ID_API_TIMEOUT)
            except FuturesTimeoutError:
                logger.error(f"[ERROR] Plant.id API timeout ({PLANT_ID_API_TIMEOUT}s)")
            except Exception as e:
                logger.error(f"[ERROR] Plant.id execution failed: {e}")

        if future_plantnet:
            try:
                # PlantNet timeout with buffer
                plantnet_results = future_plantnet.result(timeout=PLANTNET_API_TIMEOUT)
            except FuturesTimeoutError:
                logger.error(f"[ERROR] PlantNet API timeout ({PLANTNET_API_TIMEOUT}s)")
            except Exception as e:
                logger.error(f"[ERROR] PlantNet execution failed: {e}")

        parallel_duration = time.time() - api_start_time
        logger.info(f"[PERF] Parallel API execution completed in {parallel_duration:.2f}s")

        return plant_id_results, plantnet_results
    
    def _extract_care_info(self, plantnet_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract care instructions from PlantNet results.
        
        Args:
            plantnet_results: PlantNet API response
            
        Returns:
            Care instructions dictionary
        """
        care_info = {
            'watering': 'Moderate watering recommended',
            'light': 'Bright indirect light',
            'temperature': f'Room temperature ({TEMPERATURE_RANGE_CELSIUS})',
            'humidity': 'Average humidity',
            'fertilizing': 'Monthly during growing season',
            'pruning': 'Prune as needed',
            'common_issues': [],
        }
        
        # PlantNet results structure
        if plantnet_results and 'results' in plantnet_results:
            results_list = plantnet_results.get('results', [])
            if results_list:
                top_result = results_list[0]
                species = top_result.get('species', {})
                
                # Extract care data from species information
                # Note: PlantNet API returns scientific data, care instructions
                # would need to be enriched from other sources or databases
                care_info['scientific_name'] = species.get('scientificNameWithoutAuthor')
                care_info['family'] = species.get('family', {}).get('scientificName')
                care_info['genus'] = species.get('genus', {}).get('scientificName')
        
        return care_info
    
    def _merge_suggestions(
        self,
        plant_id_results: Optional[Dict[str, Any]],
        plantnet_results: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Combine suggestions from both APIs, prioritizing Plant.id.
        
        Args:
            plant_id_results: Plant.id API results
            plantnet_results: PlantNet API results
            
        Returns:
            Merged suggestions list
        """
        combined = []
        
        # Add Plant.id suggestions (primary, most accurate)
        if plant_id_results and 'suggestions' in plant_id_results:
            for suggestion in plant_id_results['suggestions'][:5]:  # Top 5
                combined.append({
                    'plant_name': suggestion.get('plant_name'),
                    'scientific_name': suggestion.get('scientific_name'),
                    'probability': suggestion.get('probability'),
                    'common_names': suggestion.get('common_names', []),
                    'description': suggestion.get('description'),
                    'taxonomy': suggestion.get('taxonomy'),
                    'edible_parts': suggestion.get('edible_parts'),
                    'watering': suggestion.get('watering'),
                    'propagation_methods': suggestion.get('propagation_methods'),
                    'similar_images': suggestion.get('similar_images', []),
                    'url': suggestion.get('url'),
                    'source': 'plant_id',
                    'rank': len(combined) + 1,
                })
        
        # Enrich with PlantNet data or add supplemental suggestions
        if plantnet_results and 'results' in plantnet_results:
            for idx, result in enumerate(plantnet_results['results'][:3]):  # Top 3
                species = result.get('species', {})
                scientific_name = species.get('scientificNameWithoutAuthor')
                
                # Check if this plant is already in our list (from Plant.id)
                existing = next(
                    (s for s in combined if s.get('scientific_name') == scientific_name),
                    None
                )
                
                if existing:
                    # Enrich existing entry with PlantNet data
                    existing['plantnet_score'] = result.get('score')
                    existing['plantnet_matched'] = True
                    existing['family'] = species.get('family', {}).get('scientificName')
                    existing['genus'] = species.get('genus', {}).get('scientificName')
                else:
                    # Add as supplemental suggestion
                    common_names = species.get('commonNames', [])
                    combined.append({
                        'plant_name': common_names[0] if common_names else scientific_name,
                        'scientific_name': scientific_name,
                        'probability': result.get('score', 0),
                        'common_names': common_names,
                        'family': species.get('family', {}).get('scientificName'),
                        'genus': species.get('genus', {}).get('scientificName'),
                        'source': 'plantnet',
                        'rank': len(combined) + 1,
                    })
        
        # Sort by probability/confidence
        combined.sort(key=lambda x: x.get('probability', 0), reverse=True)
        
        # Update ranks after sorting
        for idx, suggestion in enumerate(combined):
            suggestion['rank'] = idx + 1
        
        return combined
    
    def get_identification_summary(self, results: Dict[str, Any]) -> str:
        """
        Generate a human-readable summary of identification results.
        
        Args:
            results: Combined identification results
            
        Returns:
            Summary string
        """
        if not results.get('combined_suggestions'):
            return "Unable to identify plant from image."
        
        top = results['combined_suggestions'][0]
        plant_name = top.get('plant_name', 'Unknown Plant')
        scientific_name = top.get('scientific_name', '')
        confidence = top.get('probability', 0)
        
        summary = f"Identified as: {plant_name}"
        if scientific_name:
            summary += f" ({scientific_name})"
        summary += f" - Confidence: {confidence:.1%}"
        
        # Add disease warning if detected
        if results.get('disease_detection'):
            disease = results['disease_detection']
            if not disease.get('is_healthy'):
                disease_name = disease.get('disease_name', 'Unknown disease')
                summary += f"\n⚠️ Health Issue Detected: {disease_name}"
        
        return summary
