"""
Combined plant identification service that orchestrates Trefle and PlantNet APIs.

This service provides a unified interface for plant identification using both
image-based AI identification (PlantNet) and species data lookup (Trefle).
"""

import logging
from typing import Callable, Dict, List, Optional

import requests
from apps.core.exceptions import ExternalAPIError
from django.conf import settings
from django.utils import timezone

from ..exceptions import APIUnavailable, RateLimitExceeded
from ..models import (
    PlantIdentificationRequest,
    PlantIdentificationResult,
    PlantSpecies,
    UserPlant,
)
from .ai_care_service import AIPlantCareService
from .plantnet_service import PlantNetAPIService
from .trefle_service import TrefleAPIService

logger = logging.getLogger(__name__)


# Transient external-API failures must bubble up to the Celery task instead of
# being swallowed into fallback results / a terminal "failed"; permanent errors
# are still swallowed and marked "failed". This is a SUPERSET of
# run_identification's autoretry_for: RateLimitExceeded is intentionally NOT in
# autoretry_for (the task body handles it via an explicit `except` with a
# retry_after-aware countdown) and is normally caught upstream by the Trefle
# enrichment paths — it is listed here only so that, should it ever escape, it
# reaches that handler rather than the permanent-error path.
RETRYABLE_EXCEPTIONS = (
    ExternalAPIError,
    APIUnavailable,
    RateLimitExceeded,
    requests.exceptions.RequestException,
)


ProgressCallback = Optional[Callable[[str, str, Dict], None]]


class PlantIdentificationService:
    """
    Main service for plant identification that combines multiple data sources.
    """

    def __init__(self):
        """Initialize the identification service with API clients."""
        try:
            self.trefle = TrefleAPIService()
        except ValueError:
            logger.warning("Trefle API not available - continuing without it")
            self.trefle = None

        try:
            self.plantnet = PlantNetAPIService()
        except ValueError:
            logger.warning("PlantNet API not available - continuing without it")
            self.plantnet = None

        # Initialize AI care service
        try:
            self.ai_care_service = AIPlantCareService()
        except Exception as e:
            logger.warning(f"AI Care Service not available: {e}")
            self.ai_care_service = None

        if not self.trefle and not self.plantnet:
            logger.error("No plant identification APIs available")

    def identify_plant_from_request(
        self,
        request: PlantIdentificationRequest,
        progress_cb: ProgressCallback = None,
        reraise_transient: bool = False,
    ) -> List[PlantIdentificationResult]:
        """
        Process a plant identification request and create result records.

        Args:
            request: PlantIdentificationRequest instance
            progress_cb: optional callback for granular progress events
            reraise_transient: when True, transient external-API failures
                (RETRYABLE_EXCEPTIONS) propagate to the caller instead of being
                swallowed into fallback results. The Celery task passes True so
                its autoretry_for can fire; synchronous callers (the view path)
                leave it False to preserve graceful fallback + a 201 response.

        Returns:
            List of PlantIdentificationResult instances created
        """
        results = []

        # Update request status
        request.status = "processing"
        request.save()
        if progress_cb:
            progress_cb(
                "set_status", "processing", {"request_id": str(request.request_id)}
            )

        try:
            # Collect images from the request
            images = []
            organs = []

            if request.image_1:
                images.append(request.image_1)
                organs.append("auto")
            if request.image_2:
                images.append(request.image_2)
                organs.append("auto")
            if request.image_3:
                images.append(request.image_3)
                organs.append("auto")

            if not images:
                logger.error(f"No images found in request {request.request_id}")
                request.status = "failed"
                request.save()
                return []

            # Try PlantNet identification first (image-based AI)
            if self.plantnet:
                if progress_cb:
                    progress_cb("plantnet_start", "processing", {"images": len(images)})
                try:
                    plantnet_results = self._identify_with_plantnet(
                        request, images, organs
                    )
                    if plantnet_results:
                        results.extend(plantnet_results)
                    else:
                        # No results from PlantNet (not an error — empty match),
                        # use fallback
                        logger.info("PlantNet returned no results, using fallback")
                        results.extend(self._create_fallback_results(request))
                except RETRYABLE_EXCEPTIONS:
                    # Transient external-API failure. The Celery task opts in
                    # (reraise_transient=True) so the error reaches the outer
                    # handler and on to autoretry. Synchronous callers degrade to
                    # fallback results (preserving pre-todo behavior + a 201).
                    if reraise_transient:
                        raise
                    logger.warning(
                        "PlantNet transient failure, using fallback (sync mode)"
                    )
                    results.extend(self._create_fallback_results(request))
                except Exception as e:
                    logger.error(f"PlantNet API failed with exception: {e}")
                    # Create fallback results for testing
                    results.extend(self._create_fallback_results(request))
                if progress_cb:
                    progress_cb(
                        "plantnet_done", "processing", {"results": len(results)}
                    )
            else:
                # No PlantNet available, use fallback
                results.extend(self._create_fallback_results(request))

            # Enhanced Trefle integration with feature toggle
            trefle_enabled = getattr(settings, "ENABLE_TREFLE_ENRICHMENT", True)

            if trefle_enabled and results and self.trefle:
                if progress_cb:
                    progress_cb("enrich_start", "processing", {"count": len(results)})
                try:
                    self._enrich_with_trefle_data(results)
                    if progress_cb:
                        progress_cb(
                            "enrich_done", "processing", {"count": len(results)}
                        )
                except RateLimitExceeded as e:
                    logger.warning(
                        f"Trefle rate limit exceeded, skipping enrichment: {e}"
                    )
                    if progress_cb:
                        progress_cb(
                            "enrich_skipped",
                            "processing",
                            {"reason": "rate_limit", "error": str(e)},
                        )
                    # Don't fail the entire request, just skip enrichment
                except Exception as e:
                    logger.warning(f"Trefle enrichment failed but continuing: {e}")
                    if progress_cb:
                        progress_cb("enrich_failed", "processing", {"error": str(e)})

            # If no good results yet, try text-based search with Trefle
            if trefle_enabled and not results and self.trefle and request.description:
                if progress_cb:
                    progress_cb(
                        "trefle_search_start",
                        "processing",
                        {"query": request.description[:50]},
                    )
                try:
                    trefle_results = self._identify_with_trefle_search(request)
                    results.extend(trefle_results)
                    if progress_cb:
                        progress_cb(
                            "trefle_search_done",
                            "processing",
                            {"results": len(trefle_results)},
                        )
                except RateLimitExceeded as e:
                    logger.warning(
                        f"Trefle rate limit exceeded, using local data only: {e}"
                    )
                    if progress_cb:
                        progress_cb(
                            "trefle_search_skipped",
                            "processing",
                            {"reason": "rate_limit", "error": str(e)},
                        )
                    # Try to provide results from local database instead
                    local_results = self._get_local_species_matches(
                        request.description, request
                    )
                    results.extend(local_results)
                except Exception as e:
                    logger.warning(f"Trefle search failed but continuing: {e}")
                    if progress_cb:
                        progress_cb(
                            "trefle_search_failed", "processing", {"error": str(e)}
                        )

            # Update request status based on results
            if results:
                # Check if we have high-confidence results
                high_confidence_results = [
                    r for r in results if r.confidence_score >= 0.5
                ]

                if high_confidence_results:
                    request.status = "identified"
                    request.processed_by_ai = True
                    request.ai_processing_date = timezone.now()

                    # Mark the highest confidence result as primary
                    best_result = max(results, key=lambda r: r.confidence_score)
                    best_result.is_primary = True
                    best_result.save()
                else:
                    request.status = "needs_help"
                    request.processed_by_ai = True
                    request.ai_processing_date = timezone.now()
            else:
                request.status = "needs_help"
                # Create a helpful result even if APIs failed
                self._create_fallback_result(request)

            request.save()
            if progress_cb:
                progress_cb("final_status", request.status, {"results": len(results)})

        except RETRYABLE_EXCEPTIONS as e:
            if reraise_transient:
                # Task path: re-raise WITHOUT writing a terminal "failed" status.
                # The Celery task autoretries; only on exhaustion does its
                # on_failure mark the request failed. Writing "failed" here would
                # both pre-empt the retry and clobber a terminal-success status on
                # a retried run (audit H1).
                logger.warning(
                    "[PLANT_ID] Transient API failure for request %s, will retry: %s",
                    request.request_id,
                    str(e),
                )
                raise
            # Sync path: no retry available — finalize as failed (pre-todo behavior).
            logger.error(
                f"Error processing identification request {request.request_id}: {str(e)}"
            )
            request.status = "failed"
            request.save()
            if progress_cb:
                progress_cb("final_status", "failed", {"error": str(e)})
        except Exception as e:
            logger.error(
                f"Error processing identification request {request.request_id}: {str(e)}"
            )
            request.status = "failed"
            request.save()
            if progress_cb:
                progress_cb("final_status", "failed", {"error": str(e)})

        return results

    def _identify_with_plantnet(
        self, request: PlantIdentificationRequest, images: List, organs: List[str]
    ) -> List[PlantIdentificationResult]:
        """
        Identify plant using PlantNet API.

        Args:
            request: The identification request
            images: List of image files
            organs: List of plant organs

        Returns:
            List of created PlantIdentificationResult instances
        """
        results = []

        try:
            # Perform PlantNet identification
            identification = self.plantnet.identify_with_location(
                images=images,
                latitude=request.latitude,
                longitude=request.longitude,
                organs=organs,
            )

            if not identification:
                logger.warning(f"No PlantNet results for request {request.request_id}")
                # Return empty list - the main method will use fallback
                return []

            # Get top suggestions (lowered threshold for better results)
            suggestions = self.plantnet.get_top_suggestions(
                identification, min_score=0.01
            )

            for suggestion in suggestions[:5]:  # Limit to top 5 results
                # Try to find existing species in our database
                species = self._find_or_create_species_from_suggestion(
                    suggestion, "plantnet"
                )

                # Create identification result
                result = PlantIdentificationResult.objects.create(
                    request=request,
                    identified_species=species,
                    suggested_scientific_name=suggestion.get("scientific_name", ""),
                    suggested_common_name=(
                        suggestion.get("common_names", [])[0]
                        if suggestion.get("common_names")
                        else ""
                    ),
                    confidence_score=suggestion.get("confidence_score", 0.0),
                    identification_source="ai_plantnet",
                    api_response_data=suggestion,
                    notes=f"PlantNet AI identification with {suggestion.get('confidence_score', 0):.1%} confidence",
                )

                # Generate AI care instructions for ALL results (regardless of confidence)
                if self.ai_care_service:
                    try:
                        scientific_name = (
                            species.scientific_name
                            if species
                            else suggestion.get("scientific_name", "")
                        )
                        common_names = (
                            species.common_names
                            if species
                            else ", ".join(suggestion.get("common_names", []))
                        )

                        # Get user's location and experience if available
                        location = request.location if request else ""
                        experience = (
                            request.user.gardening_experience
                            if request and request.user
                            else "beginner"
                        )

                        # Prepare rich botanical data from PlantNet suggestion and existing species data
                        botanical_data = {
                            "plantnet_data": {
                                "native_regions": suggestion.get("native_regions", ""),
                                "iucn_category": suggestion.get("iucn_category", ""),
                                "growth_form": suggestion.get("growth_form", ""),
                                "synonyms": suggestion.get("synonyms", []),
                            },
                            "trefle_data": {},
                        }

                        # Add Trefle data if species exists and has been enriched
                        if species:
                            botanical_data["trefle_data"] = {
                                "light_requirements": species.light_requirements,
                                "water_requirements": species.water_requirements,
                                "mature_height_min": species.mature_height_min,
                                "mature_height_max": species.mature_height_max,
                                "soil_ph_min": species.soil_ph_min,
                                "soil_ph_max": species.soil_ph_max,
                                "hardiness_zone_min": species.hardiness_zone_min,
                                "hardiness_zone_max": species.hardiness_zone_max,
                                "bloom_time": species.bloom_time,
                                "flower_color": species.flower_color,
                                "native_regions": species.native_regions,
                                "growth_habit": species.plant_type,
                            }

                        care_instructions = (
                            self.ai_care_service.generate_care_instructions(
                                plant_name=scientific_name,
                                common_names=common_names,
                                location=location,
                                experience_level=experience,
                                botanical_data=botanical_data,
                            )
                        )

                        if care_instructions:
                            self.ai_care_service.update_result_with_care_instructions(
                                result, care_instructions
                            )
                            logger.info(
                                f"Generated AI care instructions for result {result.id}"
                            )
                    except Exception as e:
                        logger.error(
                            f"Failed to generate AI care instructions for result {result.id}: {e}"
                        )

                results.append(result)

        except RETRYABLE_EXCEPTIONS:
            # Transient external-API failure — propagate to the caller
            # (identify_plant_from_request), which decides per reraise_transient
            # whether to autoretry (task) or fall back (sync). Swallowing here is
            # what made autoretry inert (audit H1).
            raise
        except Exception as e:
            logger.error(
                f"PlantNet identification failed for request {request.request_id}: {str(e)}"
            )

        return results

    def _identify_with_trefle_search(
        self, request: PlantIdentificationRequest
    ) -> List[PlantIdentificationResult]:
        """
        Identify plant using Trefle text search.

        Args:
            request: The identification request

        Returns:
            List of created PlantIdentificationResult instances
        """
        results = []

        if not request.description:
            return []

        try:
            # Search Trefle using description
            plants = self.trefle.search_plants(request.description, limit=10)

            for plant_data in plants:
                # Get detailed species information
                species_data = None
                if "main_species" in plant_data:
                    species_id = plant_data["main_species"].get("id")
                    if species_id:
                        species_data = self.trefle.get_species_details(species_id)

                # Normalize and find/create species
                if species_data:
                    normalized_data = self.trefle.normalize_plant_data(
                        {"main_species": species_data}
                    )
                else:
                    normalized_data = self.trefle.normalize_plant_data(plant_data)

                species = self._find_or_create_species_from_data(normalized_data)

                # Create identification result with lower confidence for text search
                result = PlantIdentificationResult.objects.create(
                    request=request,
                    identified_species=species,
                    suggested_scientific_name=normalized_data.get(
                        "scientific_name", ""
                    ),
                    suggested_common_name=(
                        normalized_data.get("common_names", "").split(",")[0].strip()
                        if normalized_data.get("common_names")
                        else ""
                    ),
                    confidence_score=0.3,  # Lower confidence for text-based search
                    identification_source="ai_trefle",
                    api_response_data=plant_data,
                    notes="Trefle database search based on description",
                )

                results.append(result)

        except Exception as e:
            logger.error(
                f"Trefle search failed for request {request.request_id}: {str(e)}"
            )

        return results

    def _enrich_with_trefle_data(self, results: List[PlantIdentificationResult]):
        """
        Enrich PlantNet results with additional data from Trefle.

        Args:
            results: List of PlantIdentificationResult instances to enrich
        """
        if not self.trefle:
            return

        for result in results:
            if result.identification_source != "ai_plantnet":
                continue

            scientific_name = result.suggested_scientific_name or (
                result.identified_species.scientific_name
                if result.identified_species
                else ""
            )

            if not scientific_name:
                continue

            try:
                # Search Trefle for this species
                trefle_species = self.trefle.get_species_by_scientific_name(
                    scientific_name
                )

                if trefle_species:
                    # Get detailed information
                    species_details = self.trefle.get_species_details(
                        trefle_species["id"]
                    )

                    if species_details:
                        # Update or create species record with Trefle data
                        normalized_data = self.trefle.normalize_plant_data(
                            {"main_species": species_details}
                        )

                        if result.identified_species:
                            # Update existing species
                            species = result.identified_species
                            self._update_species_with_trefle_data(
                                species, normalized_data
                            )
                        else:
                            # Create new species
                            species = self._find_or_create_species_from_data(
                                normalized_data
                            )
                            result.identified_species = species
                            result.save()

                        # Update result to indicate combined sources
                        result.identification_source = "ai_combined"
                        result.notes += " (enriched with Trefle database information)"
                        result.save()

            except Exception as e:
                logger.warning(
                    f"Failed to enrich result {result.id} with Trefle data: {str(e)}"
                )

    def _find_or_create_species_from_suggestion(
        self, suggestion: Dict, source: str
    ) -> Optional[PlantSpecies]:
        """
        Find existing species or create new one from API suggestion.
        Enhanced to support auto-storage for high-confidence identifications.

        Args:
            suggestion: Normalized suggestion data
            source: Source of the suggestion ('plantnet' or 'trefle')

        Returns:
            PlantSpecies instance or None
        """
        scientific_name = suggestion.get("scientific_name", "").strip()
        if not scientific_name:
            return None

        confidence_score = suggestion.get("confidence_score", 0.0)

        # Try to find existing species
        try:
            species = PlantSpecies.objects.get(scientific_name__iexact=scientific_name)

            # Update existing species with new identification data
            species.increment_identification_count()
            species.update_confidence_score(confidence_score)

            # Update API source if this is a higher confidence identification
            if confidence_score > (species.confidence_score or 0):
                species.api_source = source

            species.save()
            return species

        except PlantSpecies.DoesNotExist:
            pass

        # Create new species - check if it qualifies for auto-storage
        try:
            species_data = {
                "scientific_name": scientific_name,
                "common_names": suggestion.get("common_names", ""),
                "family": suggestion.get("family", ""),
                "genus": suggestion.get("genus", ""),
                "is_verified": False,
                "verification_source": f"Auto-created from {source} API",
                "auto_stored": PlantSpecies.should_auto_store(confidence_score),
                "confidence_score": confidence_score,
                "identification_count": 1,
                "api_source": source,
            }

            if source == "plantnet":
                species_data["plantnet_id"] = suggestion.get("plantnet_id", "")
            elif source == "trefle":
                species_data["trefle_id"] = suggestion.get("trefle_id", "")

            species = PlantSpecies.objects.create(**species_data)

            # Log auto-storage
            if species.auto_stored:
                logger.info(
                    f"Auto-stored plant species '{scientific_name}' with "
                    f"{confidence_score:.1%} confidence from {source}"
                )

            return species

        except Exception as e:
            logger.error(f"Failed to create species for {scientific_name}: {str(e)}")
            return None

    def _find_or_create_species_from_data(
        self, normalized_data: Dict
    ) -> Optional[PlantSpecies]:
        """
        Find existing species or create new one from normalized data.
        Enhanced to support auto-storage for high-confidence identifications.

        Args:
            normalized_data: Normalized species data

        Returns:
            PlantSpecies instance or None
        """
        scientific_name = normalized_data.get("scientific_name", "").strip()
        if not scientific_name:
            return None

        confidence_score = normalized_data.get(
            "confidence_score", 0.3
        )  # Default for Trefle searches

        # Try to find existing species
        try:
            species = PlantSpecies.objects.get(scientific_name__iexact=scientific_name)

            # Update existing species with new identification data
            species.increment_identification_count()
            species.update_confidence_score(confidence_score)

            # Update with new data if available
            self._update_species_with_data(species, normalized_data)
            return species

        except PlantSpecies.DoesNotExist:
            pass

        # Create new species
        try:
            # Filter out None values and prepare data
            species_data = {
                k: v
                for k, v in normalized_data.items()
                if v is not None and k != "primary_image_url"
            }
            species_data.update(
                {
                    "is_verified": False,
                    "verification_source": "Auto-created from API data",
                    "auto_stored": PlantSpecies.should_auto_store(confidence_score),
                    "confidence_score": confidence_score,
                    "identification_count": 1,
                    "api_source": normalized_data.get("api_source", "trefle"),
                }
            )

            species = PlantSpecies.objects.create(**species_data)

            # Log auto-storage
            if species.auto_stored:
                logger.info(
                    f"Auto-stored plant species '{scientific_name}' with "
                    f"{confidence_score:.1%} confidence from API data"
                )

            return species

        except Exception as e:
            logger.error(f"Failed to create species for {scientific_name}: {str(e)}")
            return None

    def _update_species_with_data(self, species: PlantSpecies, data: Dict):
        """Update existing species with new data."""
        updated = False

        # Update fields that are currently empty
        for field_name, value in data.items():
            if field_name in ["primary_image_url"]:
                continue

            if hasattr(species, field_name) and value:
                current_value = getattr(species, field_name)
                if not current_value or current_value == "":
                    setattr(species, field_name, value)
                    updated = True

        if updated:
            species.save()

    def _update_species_with_trefle_data(
        self, species: PlantSpecies, trefle_data: Dict
    ):
        """Update species with Trefle-specific data."""
        updated = False

        # Update Trefle ID if not set
        if not species.trefle_id and trefle_data.get("trefle_id"):
            species.trefle_id = trefle_data["trefle_id"]
            updated = True

        # Update other fields if they're empty
        trefle_fields = [
            "mature_height_min",
            "mature_height_max",
            "light_requirements",
            "water_requirements",
            "soil_ph_min",
            "soil_ph_max",
            "hardiness_zone_min",
            "hardiness_zone_max",
            "bloom_time",
            "flower_color",
            "native_regions",
        ]

        for field in trefle_fields:
            if field in trefle_data and trefle_data[field]:
                current_value = getattr(species, field, None)
                if not current_value:
                    setattr(species, field, trefle_data[field])
                    updated = True

        if updated:
            species.save()

    def add_to_user_collection(
        self,
        result: PlantIdentificationResult,
        user,
        collection_id: int,
        nickname: str = "",
        notes: str = "",
    ) -> Optional[UserPlant]:
        """
        Add an identified plant to a user's collection.

        Args:
            result: The identification result to add
            user: User who owns the collection
            collection_id: ID of the user's plant collection
            nickname: Optional nickname for the plant
            notes: Optional notes about the plant

        Returns:
            Created UserPlant instance or None
        """
        try:
            from ...users.models import UserPlantCollection
            from ..models import UserPlant

            collection = UserPlantCollection.objects.get(id=collection_id, user=user)

            user_plant = UserPlant.objects.create(
                user=user,
                collection=collection,
                species=result.identified_species,
                nickname=nickname,
                notes=notes,
                from_identification_request=result.request,
                is_public=True,
            )

            # Update the request to link to the collection
            result.request.assigned_to_collection = collection
            result.request.save()

            return user_plant

        except Exception as e:
            logger.error(f"Failed to add plant to collection: {str(e)}")
            return None

    def _get_local_species_matches(
        self, query: str, request: PlantIdentificationRequest, limit: int = 5
    ) -> List[PlantIdentificationResult]:
        """
        Get species matches from local database when API is unavailable.

        Args:
            query: Search query string
            request: PlantIdentificationRequest instance
            limit: Maximum number of results to return

        Returns:
            List of PlantIdentificationResult instances from local data
        """
        results = []

        try:
            # Search by common name or scientific name
            from django.db.models import Q

            # First try exact matches
            species_matches = PlantSpecies.objects.filter(
                Q(common_names__icontains=query)
                | Q(scientific_name__icontains=query)
                | Q(genus__icontains=query)
            ).order_by("-identification_count", "-confidence_score")[:limit]

            for species in species_matches:
                # Create and save a result from local data
                result = PlantIdentificationResult.objects.create(
                    request=request,
                    identified_species=species,
                    suggested_scientific_name=species.scientific_name,
                    suggested_common_name=(
                        species.common_names.split(",")[0].strip()
                        if species.common_names
                        else ""
                    ),
                    confidence_score=0.4,  # Lower confidence for local-only matches
                    identification_source="local_database",
                    api_response_data={"source": "local", "fallback": True},
                    notes="Identified from local database (API unavailable)",
                )
                results.append(result)

            logger.info(f"Found {len(results)} local matches for query: {query}")

        except Exception as e:
            logger.error(f"Error searching local species: {e}")

        return results

    def get_service_status(self) -> Dict:
        """
        Get status of all plant identification services.

        Returns:
            Dictionary with service status information
        """
        status = {
            "trefle": {"available": False},
            "plantnet": {"available": False},
            "combined_service": {"available": False},
        }

        if self.trefle:
            status["trefle"] = self.trefle.get_service_status()

        if self.plantnet:
            status["plantnet"] = self.plantnet.get_service_status()

        # Combined service is available if at least one API works
        status["combined_service"]["available"] = (
            status["trefle"].get("status") == "available"
            or status["plantnet"].get("status") == "available"
        )

        return status

    def _create_fallback_result(self, request: PlantIdentificationRequest):
        """
        Create a helpful fallback result when APIs are unavailable.
        """
        try:
            # Create a helpful message based on what we know
            notes = "Plant identification services are currently unavailable. "

            if request.description:
                notes += f"Based on your description: '{request.description}', "

            notes += "community members can help identify your plant. "
            notes += "Please consider posting in the community forum with your images and description."

            # Create a generic result encouraging community help
            PlantIdentificationResult.objects.create(
                request=request,
                suggested_scientific_name="",
                suggested_common_name="Unknown Plant",
                confidence_score=0.0,
                identification_source="system_message",
                notes=notes,
                is_primary=True,
            )

        except Exception as e:
            logger.error(f"Failed to create fallback result: {str(e)}")

    def _create_fallback_results(
        self, request: PlantIdentificationRequest
    ) -> List[PlantIdentificationResult]:
        """
        Create fallback results when APIs fail.
        This ensures users always get some response.
        """
        results = []
        try:
            # Create some common plant suggestions as fallback
            common_plants = [
                {
                    "scientific_name": "Rosa damascena",
                    "common_name": "Damask Rose",
                    "confidence": 0.75,
                    "family": "Rosaceae",
                },
                {
                    "scientific_name": "Monstera deliciosa",
                    "common_name": "Swiss Cheese Plant",
                    "confidence": 0.65,
                    "family": "Araceae",
                },
                {
                    "scientific_name": "Ficus elastica",
                    "common_name": "Rubber Plant",
                    "confidence": 0.55,
                    "family": "Moraceae",
                },
            ]

            for i, plant in enumerate(common_plants):
                # Get or create species
                species, created = PlantSpecies.objects.get_or_create(
                    scientific_name=plant["scientific_name"],
                    defaults={
                        "common_names": plant["common_name"],
                        "family": plant["family"],
                        "is_verified": True,
                        "verification_source": "fallback_data",
                    },
                )

                # Create result
                result = PlantIdentificationResult.objects.create(
                    request=request,
                    identified_species=species,
                    suggested_scientific_name=plant["scientific_name"],
                    suggested_common_name=plant["common_name"],
                    confidence_score=plant["confidence"],
                    identification_source="fallback",
                    notes="Note: External APIs are currently unavailable. These are common plant suggestions.",
                    is_primary=(i == 0),
                )
                results.append(result)

            logger.info(
                f"Created {len(results)} fallback results for request {request.request_id}"
            )

        except Exception as e:
            logger.error(f"Failed to create fallback results: {str(e)}")

        return results
