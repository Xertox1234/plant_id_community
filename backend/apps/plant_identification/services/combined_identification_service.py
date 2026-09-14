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
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from io import BytesIO
from typing import TYPE_CHECKING, Any, Dict, List, NamedTuple, Optional, Tuple, Union

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

from apps.core.exceptions import ExternalAPIError

from ..constants import (
    CPU_CORE_MULTIPLIER,
    MAX_WORKER_THREADS,
    PLANT_ID_API_TIMEOUT,
    PLANTNET_API_TIMEOUT,
    TEMPERATURE_RANGE_CELSIUS,
)
from ..provider_failures import UNKNOWN, classify_provider_failure
from .plant_id_service import PlantIDAPIService
from .plantnet_service import PlantNetAPIService, parse_plantnet_species

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
                max_workers_env = os.getenv("PLANT_ID_MAX_WORKERS")
                if max_workers_env:
                    max_workers = int(max_workers_env)
                    if max_workers < 1:
                        logger.warning(
                            f"[IDENTIFY] Invalid PLANT_ID_MAX_WORKERS={max_workers} (must be positive), using default"
                        )
                        cpu_count = os.cpu_count() or 1
                        default_workers = cpu_count * CPU_CORE_MULTIPLIER
                        max_workers = default_workers
                else:
                    cpu_count = os.cpu_count() or 1
                    max_workers = cpu_count * CPU_CORE_MULTIPLIER
            except (ValueError, TypeError) as e:
                logger.error(
                    f"[IDENTIFY] Invalid PLANT_ID_MAX_WORKERS value: {e}, using default"
                )
                cpu_count = os.cpu_count() or 1
                max_workers = cpu_count * CPU_CORE_MULTIPLIER

            # Cap at maximum to prevent API rate limit issues
            max_workers = max(1, min(max_workers, MAX_WORKER_THREADS))

            _EXECUTOR = ThreadPoolExecutor(
                max_workers=max_workers, thread_name_prefix="plant_api_"
            )

            # Register cleanup on process exit (only once)
            if not _CLEANUP_REGISTERED:
                atexit.register(_cleanup_executor)
                _CLEANUP_REGISTERED = True

            logger.info(
                f"[INIT] ThreadPoolExecutor initialized with {max_workers} workers"
            )

        return _EXECUTOR


def _cleanup_executor() -> None:
    """Cleanup executor on process shutdown."""
    global _EXECUTOR
    if _EXECUTOR is not None:
        logger.info("[SHUTDOWN] Cleaning up ThreadPoolExecutor")
        _EXECUTOR.shutdown(wait=True, cancel_futures=False)
        _EXECUTOR = None
        logger.info("[SHUTDOWN] ThreadPoolExecutor cleanup complete")


class ProviderOutcome(NamedTuple):
    """What one identification provider returned, and if nothing, why.

    Todo 393. The reason is the entire point: `result is None` on its own cannot
    tell "the provider declined" from "the provider was never configured" from
    "we never asked", and that ambiguity is what let disease detection sit off in
    production with no error, no metric and no usable log line.
    """

    result: Optional[Dict[str, Any]]
    reason: Optional[str] = None
    configured: bool = True

    @property
    def failed(self) -> bool:
        """True only for a provider that was asked and did not deliver."""
        return self.configured and self.result is None

    def as_status(self) -> Dict[str, Optional[str]]:
        """Render for the API response. Additive; no existing field changes."""
        if not self.configured:
            return {"status": "not_configured", "reason": None}
        if self.result is None:
            return {"status": "failed", "reason": self.reason or UNKNOWN}
        return {"status": "ok", "reason": None}


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
            if getattr(settings, "ENABLE_PLANT_ID", True):
                self.plant_id = PlantIDAPIService()
                logger.info("[IDENTIFY] Plant.id service initialized")
        except (ImportError, AttributeError, KeyError) as e:
            # Configuration errors or missing dependencies
            logger.warning(
                f"[IDENTIFY] Plant.id service not available: {type(e).__name__}",
                exc_info=settings.DEBUG,
            )
        except Exception as e:
            # Unexpected initialization errors
            logger.error(
                f"[IDENTIFY] Unexpected error initializing Plant.id service: {type(e).__name__}",
                exc_info=True,
            )

        # Initialize PlantNet service
        try:
            if getattr(settings, "ENABLE_PLANTNET", True):
                self.plantnet = PlantNetAPIService()
                logger.info("[IDENTIFY] PlantNet service initialized")
        except (ImportError, AttributeError, KeyError) as e:
            # Configuration errors or missing dependencies
            logger.warning(
                f"[IDENTIFY] PlantNet service not available: {type(e).__name__}",
                exc_info=settings.DEBUG,
            )
        except Exception as e:
            # Unexpected initialization errors
            logger.error(
                f"[IDENTIFY] Unexpected error initializing PlantNet service: {type(e).__name__}",
                exc_info=True,
            )

        if not self.plant_id and not self.plantnet:
            logger.error("[IDENTIFY] No plant identification APIs available")

    def identify_plant(
        self,
        image_file: Union[BytesIO, InMemoryUploadedFile, TemporaryUploadedFile, bytes],
        user: Optional["AbstractBaseUser"] = None,
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

        results: Dict[str, Any] = {
            "primary_identification": None,
            "care_instructions": None,
            "disease_detection": None,
            "combined_suggestions": [],
            "confidence_score": 0,
            "source": None,
            "timing": {},
            # Todo 393. These are ADDITIVE -- every field above keeps its
            # meaning, so the React and Flutter clients are unaffected until
            # they choose to read these.
            "providers": {},
            "degraded": False,
            # "ok" means the health assessment ran. It does NOT mean a disease
            # was found: a healthy plant is "ok" with disease_detection None.
            # "unavailable" means nobody asked or nobody answered.
            "disease_detection_status": "unavailable",
            "disease_detection_reason": None,
        }

        # Read image data once to avoid file pointer issues in parallel execution
        if hasattr(image_file, "read"):
            image_data = image_file.read()
        else:
            image_data = image_file

        logger.info("[PARALLEL] Starting parallel API calls (Plant.id + PlantNet)")

        # Execute both API calls in parallel
        plant_id, plantnet = self._identify_parallel(image_data)
        plant_id_results, plantnet_results = plant_id.result, plantnet.result

        results["providers"] = {
            "plant_id": plant_id.as_status(),
            "plantnet": plantnet.as_status(),
        }
        results["degraded"] = plant_id.failed or plantnet.failed

        # Process Plant.id results
        if plant_id_results:
            results["primary_identification"] = plant_id_results
            results["disease_detection"] = plant_id_results.get("health_assessment")
            results["confidence_score"] = plant_id_results.get("confidence", 0)
            results["source"] = "plant_id"

            # Identification can succeed while the SEPARATE health_assessment
            # endpoint fails, so a successful Plant.id call does not imply
            # disease detection ran (todo 393).
            health_error = plant_id_results.get("health_assessment_error")
            if health_error:
                results["disease_detection_reason"] = health_error
            else:
                results["disease_detection_status"] = "ok"

            logger.info(
                f"[SUCCESS] Plant.id identified: "
                f"{plant_id_results.get('top_suggestion', {}).get('plant_name', 'Unknown')} "
                f"(confidence: {results['confidence_score']:.2%})"
            )
        elif plant_id.failed:
            results["disease_detection_reason"] = plant_id.reason

        # Process PlantNet results
        if plantnet_results:
            results["care_instructions"] = self._extract_care_info(plantnet_results)
            logger.info("[SUCCESS] PlantNet care instructions retrieved")

        # Combine suggestions from both APIs
        results["combined_suggestions"] = self._merge_suggestions(
            plant_id_results, plantnet_results
        )

        # A PARTIAL failure used to be completely silent: with Plant.id down and
        # PlantNet healthy, suggestions and care instructions were still
        # populated, so nothing below fired and nothing above was set. Disease
        # detection was simply off, in production, with nobody told (todo 393).
        if results["degraded"]:
            logger.error(
                "[DEGRADED] Identification ran with a failed provider: "
                + ", ".join(
                    f"{name}={info['reason']}"
                    for name, info in results["providers"].items()
                    if info["status"] == "failed"
                )
                + f" | disease_detection={results['disease_detection_status']}"
            )

        # If no results from either API, return error
        if not results["combined_suggestions"]:
            logger.warning("[ERROR] No identification results from any API")
            results["error"] = "Unable to identify plant. Please try a clearer image."

        # Record total timing
        total_time = time.time() - start_time
        results["timing"]["total"] = round(total_time, 2)
        logger.info(
            f"[PERF] Total identification time: {total_time:.2f}s (parallel processing)"
        )

        return results

    def _identify_parallel(
        self, image_data: bytes
    ) -> Tuple["ProviderOutcome", "ProviderOutcome"]:
        """
        Execute Plant.id and PlantNet API calls in parallel.

        Args:
            image_data: Image file bytes

        Returns:
            Tuple of (plant_id_outcome, plantnet_outcome). Each carries the
            result AND, when there is none, a reason token -- the reason used to
            be discarded here, which is what made a total provider failure
            indistinguishable from "never asked" everywhere downstream (todo 393).
        """
        api_start_time = time.time()

        def call(name: str, invoke) -> "ProviderOutcome":
            """Run one provider's call, converting any failure into a reason.

            The bracketed token is a LITERAL in every branch, never
            f"[{prefix}]". `scripts/check_log_prefixes.py` judges an f-string by
            its first literal chunk, so an interpolated token reads as
            UNPREFIXED -- it counted 4 violations here against a baseline todo
            388 drove from 339 to 7. The provider name stays in the message, so
            per-provider grepping is unaffected.
            """
            try:
                started = time.time()
                logger.info(f"[PARALLEL] {name} API call started")
                result = invoke()
                logger.info(
                    f"[SUCCESS] {name} completed in {time.time() - started:.2f}s"
                )
                return ProviderOutcome(result)
            except ExternalAPIError as e:
                # API is unavailable (circuit breaker open, timeout, connection
                # error). Expected in degraded scenarios - warn and continue.
                reason = classify_provider_failure(e)
                logger.warning(
                    f"[PARALLEL] {name} API unavailable ({reason}): {type(e).__name__}",
                    exc_info=settings.DEBUG,
                )
                return ProviderOutcome(None, reason)
            except (ValueError, KeyError, TypeError) as e:
                reason = classify_provider_failure(e)
                logger.error(
                    f"[ERROR] {name} response parsing failed ({reason}): "
                    f"{type(e).__name__}",
                    exc_info=True,
                )
                return ProviderOutcome(None, reason)
            except Exception as e:
                # Unexpected errors. The reason token is what makes this
                # actionable -- the previous line said only "HTTPError".
                reason = classify_provider_failure(e)
                logger.error(
                    f"[ERROR] Unexpected {name} error ({reason}): {type(e).__name__}",
                    exc_info=True,
                )
                return ProviderOutcome(None, reason)

        def call_plant_id() -> "ProviderOutcome":
            return call(
                "Plant.id",
                lambda: self.plant_id.identify_plant(
                    BytesIO(image_data), include_diseases=True
                ),
            )

        def call_plantnet() -> "ProviderOutcome":
            return call(
                "PlantNet",
                lambda: self.plantnet.identify_plant(
                    [BytesIO(image_data)],  # PlantNet expects a list of images
                    organs=["leaf"],  # One organ per image - 'leaf' is most common
                ),
            )

        def gather(future, name: str, timeout: float) -> "ProviderOutcome":
            """Collect a submitted call, naming an executor-level failure too."""
            try:
                return future.result(timeout=timeout)
            except FuturesTimeoutError:
                logger.error(
                    f"[ERROR] {name} executor timeout after {timeout}s",
                    exc_info=settings.DEBUG,
                )
                return ProviderOutcome(None, "executor-timeout")
            except Exception as e:
                # Thread execution errors (should be caught inside the call).
                reason = classify_provider_failure(e)
                logger.error(
                    f"[ERROR] {name} thread execution failed ({reason}): "
                    f"{type(e).__name__}",
                    exc_info=True,
                )
                return ProviderOutcome(None, reason)

        # A provider that was never configured is NOT a failure -- reporting it
        # as one would make every single-provider deployment permanently
        # "degraded" and train people to ignore the signal.
        future_plant_id = self.executor.submit(call_plant_id) if self.plant_id else None
        future_plantnet = self.executor.submit(call_plantnet) if self.plantnet else None

        plant_id_outcome = (
            gather(future_plant_id, "Plant.id", PLANT_ID_API_TIMEOUT)
            if future_plant_id
            else ProviderOutcome(None, None, configured=False)
        )
        plantnet_outcome = (
            gather(future_plantnet, "PlantNet", PLANTNET_API_TIMEOUT)
            if future_plantnet
            else ProviderOutcome(None, None, configured=False)
        )

        parallel_duration = time.time() - api_start_time
        logger.info(
            f"[PERF] Parallel API execution completed in {parallel_duration:.2f}s"
        )

        return plant_id_outcome, plantnet_outcome

    def _extract_care_info(self, plantnet_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract care instructions from PlantNet results.

        Args:
            plantnet_results: PlantNet API response

        Returns:
            Care instructions dictionary
        """
        care_info = {
            "watering": "Moderate watering recommended",
            "light": "Bright indirect light",
            "temperature": f"Room temperature ({TEMPERATURE_RANGE_CELSIUS})",
            "humidity": "Average humidity",
            "fertilizing": "Monthly during growing season",
            "pruning": "Prune as needed",
            "common_issues": [],
        }

        # PlantNet results structure
        if plantnet_results and "results" in plantnet_results:
            results_list = plantnet_results.get("results", [])
            if results_list:
                top_result = results_list[0]
                species = top_result.get("species", {})

                # Extract care data from species information
                # Note: PlantNet API returns scientific data, care instructions
                # would need to be enriched from other sources or databases
                care_info.update(parse_plantnet_species(species))

        return care_info

    def _merge_suggestions(
        self,
        plant_id_results: Optional[Dict[str, Any]],
        plantnet_results: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Combine suggestions from both APIs, prioritizing Plant.id.

        Args:
            plant_id_results: Plant.id API results
            plantnet_results: PlantNet API results

        Returns:
            Merged suggestions list
        """
        combined: List[Dict[str, Any]] = []

        # Add Plant.id suggestions (primary, most accurate)
        if plant_id_results and "suggestions" in plant_id_results:
            for suggestion in plant_id_results["suggestions"][:5]:  # Top 5
                combined.append(
                    {
                        "plant_name": suggestion.get("plant_name"),
                        "scientific_name": suggestion.get("scientific_name"),
                        "probability": suggestion.get("probability"),
                        "common_names": suggestion.get("common_names", []),
                        "description": suggestion.get("description"),
                        "taxonomy": suggestion.get("taxonomy"),
                        "edible_parts": suggestion.get("edible_parts"),
                        "watering": suggestion.get("watering"),
                        "propagation_methods": suggestion.get("propagation_methods"),
                        "similar_images": suggestion.get("similar_images", []),
                        "url": suggestion.get("url"),
                        "source": "plant_id",
                        "rank": len(combined) + 1,
                    }
                )

        # Enrich with PlantNet data or add supplemental suggestions
        if plantnet_results and "results" in plantnet_results:
            for idx, result in enumerate(plantnet_results["results"][:3]):  # Top 3
                species = result.get("species", {})
                parsed = parse_plantnet_species(species)
                scientific_name = parsed["scientific_name"]

                # Check if this plant is already in our list (from Plant.id)
                existing = next(
                    (
                        s
                        for s in combined
                        if s.get("scientific_name") == scientific_name
                    ),
                    None,
                )

                if existing:
                    # Enrich existing entry with PlantNet data
                    existing["plantnet_score"] = result.get("score")
                    existing["plantnet_matched"] = True
                    existing["family"] = parsed["family"]
                    existing["genus"] = parsed["genus"]
                else:
                    # Add as supplemental suggestion
                    common_names = species.get("commonNames", [])
                    combined.append(
                        {
                            "plant_name": (
                                common_names[0] if common_names else scientific_name
                            ),
                            "scientific_name": scientific_name,
                            "probability": result.get("score", 0),
                            "common_names": common_names,
                            "family": parsed["family"],
                            "genus": parsed["genus"],
                            "source": "plantnet",
                            "rank": len(combined) + 1,
                        }
                    )

        # Sort by probability/confidence
        combined.sort(key=lambda x: x.get("probability", 0), reverse=True)

        # Update ranks after sorting
        for idx, suggestion in enumerate(combined):
            suggestion["rank"] = idx + 1

        return combined

    def get_identification_summary(self, results: Dict[str, Any]) -> str:
        """
        Generate a human-readable summary of identification results.

        Args:
            results: Combined identification results

        Returns:
            Summary string
        """
        if not results.get("combined_suggestions"):
            return "Unable to identify plant from image."

        top = results["combined_suggestions"][0]
        plant_name = top.get("plant_name", "Unknown Plant")
        scientific_name = top.get("scientific_name", "")
        confidence = top.get("probability", 0)

        summary = f"Identified as: {plant_name}"
        if scientific_name:
            summary += f" ({scientific_name})"
        summary += f" - Confidence: {confidence:.1%}"

        # Add disease warning if detected
        if results.get("disease_detection"):
            disease = results["disease_detection"]
            if not disease.get("is_healthy"):
                disease_name = disease.get("disease_name", "Unknown disease")
                summary += f"\n⚠️ Health Issue Detected: {disease_name}"
        elif results.get("disease_detection_status") == "unavailable":
            # `summary` is the one field a client may render on its own, so a
            # silent omission here is exactly the "quietly thinner payload" this
            # todo is about -- the reader cannot tell a clean bill of health from
            # a check that never ran. The reason token stays out: it is for logs
            # and for `disease_detection_reason`, not for a person (todo 393).
            summary += "\nHealth check unavailable — disease detection did not run."

        return summary
