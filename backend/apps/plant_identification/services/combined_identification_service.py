"""
Combined Plant Identification Service - Dual API Integration

Integrates Plant.id (Kindwise) and PlantNet APIs to provide:
1. High-accuracy AI identification (Plant.id)
2. Disease detection (Plant.id)
3. A second species opinion and taxonomy (PlantNet)

Care instructions are not provided: `care_instructions` is always None
until a real per-species source exists (todo 662).
"""

import atexit
import logging
import os
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from functools import partial
from io import BytesIO
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Set,
    Tuple,
    Union,
)

from celery.exceptions import SoftTimeLimitExceeded
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
    SCAN_PLANTNET_ORGANS,
    SCAN_PROBLEM_FALLBACK_ORGAN,
    SCAN_PROBLEM_ROLE,
)
from ..provider_failures import UNKNOWN, classify_provider_failure
from .plant_id_service import PlantIDAPIService
from .plantnet_service import PlantNetAPIService, parse_plantnet_species

logger = logging.getLogger(__name__)


def normalize_scientific_name(name: Optional[str]) -> Optional[str]:
    """Reduce a scientific name to lowercase genus + epithet for matching.

    Drops an author suffix ("Ficus lyrata Warb." -> "ficus lyrata"), case,
    extra whitespace and the hybrid marker in either spelling ("Mentha x
    piperita" == "Mentha ×piperita"), so the two providers' names for one
    species compare equal (todo 661). Returns None for a missing or blank name.
    """
    if not name:
        return None
    tokens = [t.lstrip("×") for t in name.lower().split()]
    tokens = [t for t in tokens if t and t != "x"]
    return " ".join(tokens[:2]) or None


def _plantnet_top_score(result: Optional[Dict[str, Any]]) -> Optional[float]:
    """PlantNet's top-ranked score, or None when it returned no result."""
    ranked = (result or {}).get("results") or []
    score = ranked[0].get("score") if ranked else None
    return float(score) if score is not None else None


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


class ScanAborted(Exception):
    """The scan's job left ``processing`` before a paid call; nothing was spent.

    Raised by ``scan()`` when its ``should_continue`` check says no, so a
    cancelled or expired job never makes the Plant.id call (scan-2 audit H1).
    """


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
    2. Use PlantNet as a second opinion on the species (open source data)
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

        # Read image data once to avoid file pointer issues in parallel execution
        if hasattr(image_file, "read"):
            image_data = image_file.read()
        else:
            image_data = image_file

        logger.info("[PARALLEL] Starting parallel API calls (Plant.id + PlantNet)")

        # Execute both API calls in parallel
        plant_id, plantnet = self._identify_parallel(image_data)
        return self._build_results(plant_id, plantnet, start_time)

    def _build_results(
        self,
        plant_id: "ProviderOutcome",
        plantnet: "ProviderOutcome",
        timing: float,
    ) -> Dict[str, Any]:
        """Combine both providers' outcomes into the identification payload.

        Shared by ``identify_plant`` and ``scan`` so both return the same keys.
        ``timing`` is the ``time.time()`` the request started at; the elapsed
        total is recorded under ``results["timing"]["total"]``.
        """
        start_time = timing
        results: Dict[str, Any] = {
            "primary_identification": None,
            "care_instructions": None,
            "disease_detection": None,
            "combined_suggestions": [],
            "confidence_score": 0,
            "source": None,
            # Which provider the top suggestion came from: "plant_id",
            # "plantnet", or "both" when they agree on it (todo 661).
            "top_source": None,
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

        # `care_instructions` stays None (todo 662). Neither provider returns
        # plant-specific care: the old dict was one fixed set of placeholder
        # strings for every plant, plus PlantNet's taxonomy, taken from
        # PlantNet's top result even when the returned plant was Plant.id's.
        # Clients hide the care section on null. Real care guides come with
        # Scan 2.0 part 4 (docs/superpowers/specs/2026-10-24-scan-2-0-design.md).

        # Combine suggestions from both APIs
        results["combined_suggestions"] = self._merge_suggestions(
            plant_id_results, plantnet_results
        )

        # The reported confidence belongs to the plant actually returned, not to
        # Plant.id's top answer, which may be a different plant (todo 661).
        combined = results["combined_suggestions"]
        top = combined[0] if combined else None
        results["confidence_score"] = (top.get("probability") or 0) if top else 0
        results["top_source"] = (
            None
            if top is None
            else "both" if top.get("plantnet_matched") else top.get("source")
        )
        if top is not None:
            self._log_merge(plant_id_results, plantnet_results, results["top_source"])

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
        plant_id_call = (
            partial(
                self.plant_id.identify_plant,
                BytesIO(image_data),
                include_diseases=True,
            )
            if self.plant_id
            else None
        )
        plantnet_call = (
            partial(
                self.plantnet.identify_plant,
                [BytesIO(image_data)],  # PlantNet expects a list of images
                organs=["leaf"],  # One organ per image - 'leaf' is most common
            )
            if self.plantnet
            else None
        )
        return self._run_providers(plant_id_call, plantnet_call)

    def _run_providers(
        self,
        plant_id_call: Optional[Callable[[], Any]],
        plantnet_call: Optional[Callable[[], Any]],
    ) -> Tuple["ProviderOutcome", "ProviderOutcome"]:
        """Run the given provider calls in parallel on the shared executor.

        A call of None means that provider is not configured (or not asked):
        it is never submitted and comes back ``configured=False``.
        """
        api_start_time = time.time()

        # A provider that was never configured is NOT a failure -- reporting it
        # as one would make every single-provider deployment permanently
        # "degraded" and train people to ignore the signal.
        # The submitted callables keep their historical names (call_plant_id,
        # call_plantnet): tests pick a provider's future by fn.__name__.
        future_plant_id = None
        if plant_id_call is not None:
            pid_call = plant_id_call

            def call_plant_id() -> "ProviderOutcome":
                return self._call_provider("Plant.id", pid_call)

            future_plant_id = self.executor.submit(call_plant_id)
        future_plantnet = None
        if plantnet_call is not None:
            pn_call = plantnet_call

            def call_plantnet() -> "ProviderOutcome":
                return self._call_provider("PlantNet", pn_call)

            future_plantnet = self.executor.submit(call_plantnet)

        plant_id_outcome = (
            self._gather(future_plant_id, "Plant.id", PLANT_ID_API_TIMEOUT)
            if future_plant_id
            else ProviderOutcome(None, None, configured=False)
        )
        plantnet_outcome = (
            self._gather(future_plantnet, "PlantNet", PLANTNET_API_TIMEOUT)
            if future_plantnet
            else ProviderOutcome(None, None, configured=False)
        )

        parallel_duration = time.time() - api_start_time
        logger.info(
            f"[PERF] Parallel API execution completed in {parallel_duration:.2f}s"
        )

        return plant_id_outcome, plantnet_outcome

    def _call_provider(self, name: str, invoke: Callable[[], Any]) -> "ProviderOutcome":
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
            logger.info(f"[SUCCESS] {name} completed in {time.time() - started:.2f}s")
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

    def _gather(
        self, future: "Future[ProviderOutcome]", name: str, timeout: float
    ) -> "ProviderOutcome":
        """Collect a submitted call, naming an executor-level failure too."""
        try:
            outcome: ProviderOutcome = future.result(timeout=timeout)
            return outcome
        except FuturesTimeoutError:
            logger.error(
                f"[ERROR] {name} executor timeout after {timeout}s",
                exc_info=settings.DEBUG,
            )
            return ProviderOutcome(None, "executor-timeout")
        except SoftTimeLimitExceeded:
            # The Celery task's soft limit (scan jobs run this in a worker):
            # the task classifies it as a timeout, so never swallow it here.
            raise
        except Exception as e:
            # Thread execution errors (should be caught inside the call).
            reason = classify_provider_failure(e)
            logger.error(
                f"[ERROR] {name} thread execution failed ({reason}): "
                f"{type(e).__name__}",
                exc_info=True,
            )
            return ProviderOutcome(None, reason)

    def scan(
        self,
        shots: Mapping[str, bytes],
        mode: str,
        should_continue: Callable[[], bool] = lambda: True,
    ) -> Dict[str, Any]:
        """Identify (and in diagnose mode, health-check) a multi-photo scan.

        ``shots`` maps a photo role (problem, leaf, whole, flower) to its JPEG
        bytes; ``mode`` is "diagnose" or "identify". Returns the same keys as
        ``identify_plant``.

        - PlantNet gets the leaf/whole/flower shots with their organs, in that
          fixed order; the problem close-up only when it is the sole shot.
        - diagnose: both providers in parallel. Plant.id identifies from the
          non-problem shots (or the problem shot if there are none) and runs
          the health assessment on the problem shot.
        - identify: PlantNet first. A top score at or above
          ``SCAN_PLANTNET_CONFIDENCE_FLOOR`` answers alone, and Plant.id is
          never called. Below it, Plant.id identifies without the health check,
          leaving ``PLANT_ID_DIAGNOSIS_RESERVE`` daily calls for diagnoses; if
          that fails, PlantNet's answer stands.

        ``should_continue`` is asked immediately before any Plant.id call
        (diagnose: before both providers start; identify: before the
        fallback). False raises ``ScanAborted`` and Plant.id is not called.
        A call already in flight is not interrupted.
        """
        start_time = time.time()
        problem = shots.get(SCAN_PROBLEM_ROLE)
        roles = [role for role in SCAN_PLANTNET_ORGANS if role in shots]
        others = [shots[role] for role in roles]
        if others:
            pn_images, pn_organs = others, [SCAN_PLANTNET_ORGANS[r] for r in roles]
        elif problem is not None:
            pn_images, pn_organs = [problem], [SCAN_PROBLEM_FALLBACK_ORGAN]
        else:
            raise ValueError("scan() needs at least one photo")
        id_images = others or pn_images  # pn_images is [problem] then

        plantnet_call = (
            partial(
                self.plantnet.identify_plant,
                [BytesIO(b) for b in pn_images],
                organs=list(pn_organs),
            )
            if self.plantnet
            else None
        )

        if mode == "diagnose":
            plant_id_call = (
                partial(
                    self.plant_id.identify_plant,
                    None,
                    include_diseases=True,
                    images=id_images,
                    health_images=[problem] if problem is not None else id_images,
                )
                if self.plant_id
                else None
            )
            if not should_continue():
                raise ScanAborted("job left processing before the diagnosis")
            logger.info("[SCAN] Diagnose: Plant.id + PlantNet in parallel")
            plant_id, plantnet = self._run_providers(plant_id_call, plantnet_call)
            return self._build_results(plant_id, plantnet, start_time)

        _, plantnet = self._run_providers(None, plantnet_call)
        top_score = _plantnet_top_score(plantnet.result)
        if (
            top_score is not None
            and top_score >= settings.SCAN_PLANTNET_CONFIDENCE_FLOOR
        ):
            logger.info(
                f"[SCAN] Identify: PlantNet confident ({top_score:.2f}), "
                "Plant.id skipped"
            )
            plant_id = ProviderOutcome(None, "skipped", configured=False)
        else:
            if not should_continue():
                raise ScanAborted("job left processing before the Plant.id fallback")
            logger.info("[SCAN] Identify: PlantNet unsure, asking Plant.id")
            plant_id_call = (
                partial(
                    self.plant_id.identify_plant,
                    None,
                    include_diseases=False,
                    images=id_images,
                    quota_reserve=settings.PLANT_ID_DIAGNOSIS_RESERVE,
                )
                if self.plant_id
                else None
            )
            plant_id, _ = self._run_providers(plant_id_call, None)
        return self._build_results(plant_id, plantnet, start_time)

    def _merge_suggestions(
        self,
        plant_id_results: Optional[Dict[str, Any]],
        plantnet_results: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Combine suggestions from both APIs into one ranked list.

        Plant.id's probability and PlantNet's score come from different models
        and are not on one scale, so they are never sorted against each other
        (todo 661). The interim rule, to revisit from the ``[MERGE]`` log lines:

        1. species both providers name (matched on ``normalize_scientific_name``)
           where the species is at least one provider's top answer, by Plant.id
           probability -- a 5th-place Plant.id guess matched by PlantNet's 3rd
           must not unseat a confident Plant.id answer;
        2. then the other Plant.id species, by Plant.id probability;
        3. then PlantNet-only species, by PlantNet score.

        A matched entry keeps Plant.id's fields and probability and gains
        ``plantnet_score`` / ``plantnet_matched``. Lower-ranked PlantNet
        results naming an already-listed species are dropped.

        Args:
            plant_id_results: Plant.id API results
            plantnet_results: PlantNet API results

        Returns:
            Merged suggestions list
        """
        combined: List[Dict[str, Any]] = []
        # ids of matched entries that are either provider's top answer
        promoted: Set[int] = set()

        # Plant.id suggestions first; PlantNet folds into them on a name match
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
            for pn_rank, result in enumerate(plantnet_results["results"][:3]):
                species = result.get("species", {})
                parsed = parse_plantnet_species(species)
                scientific_name = parsed["scientific_name"]

                # Is this species already listed (by Plant.id, or by a better
                # PlantNet result)?
                key = normalize_scientific_name(scientific_name)
                existing = next(
                    (
                        s
                        for s in combined
                        if key is not None
                        and normalize_scientific_name(s.get("scientific_name")) == key
                    ),
                    None,
                )

                if existing is not None and (
                    existing.get("source") == "plantnet"
                    or existing.get("plantnet_matched")
                ):
                    # A lower-ranked PlantNet duplicate: keep the first, best one.
                    continue
                if existing is not None:
                    # Enrich existing entry with PlantNet data
                    existing["plantnet_score"] = result.get("score")
                    existing["plantnet_matched"] = True
                    existing["family"] = parsed["family"]
                    existing["genus"] = parsed["genus"]
                    if pn_rank == 0 or existing is combined[0]:
                        promoted.add(id(existing))
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

        def tier(suggestion: Dict[str, Any]) -> Tuple[int, float]:
            if id(suggestion) in promoted:
                rank = 0
            elif suggestion.get("source") == "plant_id":
                rank = 1
            else:
                rank = 2
            return rank, -(suggestion.get("probability") or 0)

        combined.sort(key=tier)

        # Update ranks after sorting
        for idx, suggestion in enumerate(combined):
            suggestion["rank"] = idx + 1

        return combined

    def _log_merge(
        self,
        plant_id_results: Optional[Dict[str, Any]],
        plantnet_results: Optional[Dict[str, Any]],
        top_source: Optional[str],
    ) -> None:
        """Log each provider's own top answer and raw score (todo 661).

        These lines are the data the cross-provider rule gets calibrated from.
        Names and scores only: no image data and no user.
        """
        pid = ((plant_id_results or {}).get("suggestions") or [{}])[0]
        pn = ((plantnet_results or {}).get("results") or [{}])[0]
        pid_name = pid.get("scientific_name")
        pn_name = parse_plantnet_species(pn.get("species") or {})["scientific_name"]
        pid_key = normalize_scientific_name(pid_name)
        agree = pid_key is not None and pid_key == normalize_scientific_name(pn_name)
        logger.info(
            f"[MERGE] plant_id_top={pid_name} ({pid.get('probability')}) "
            f"plantnet_top={pn_name} ({pn.get('score')}) "
            f"agree={agree} top_source={top_source}"
        )

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
        confidence = top.get("probability") or 0

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
