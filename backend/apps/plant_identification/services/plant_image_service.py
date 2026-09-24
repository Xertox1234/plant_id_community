"""
Unified Plant Image Service.

Combines Unsplash, Pexels, and AI generation services to provide the best available
plant images with smart fallback logic and cost optimization.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple, Union

from apps.core.utils.urls import safe_http_url
from django.conf import settings
from wagtail.images.models import Image

from .ai_image_service import AIBotanicalImageService
from .pexels_service import PexelsImageService
from .unsplash_service import (
    UNSPLASH_CREDIT_SUFFIX,
    UnsplashImageService,
    with_unsplash_utm,
)

logger = logging.getLogger(__name__)


class PlantImageService:
    """
    Unified service for sourcing plant images from multiple providers.
    Implements intelligent fallback strategy: Stock Photos → AI Generation → Manual Upload
    """

    def __init__(self):
        """Initialize all image services."""
        self.unsplash = UnsplashImageService()
        self.pexels = PexelsImageService()
        self.ai_service = AIBotanicalImageService()

        # Priority order for image sources
        self.source_priority = ["unsplash", "pexels", "ai"]

        # Cost tracking
        self._daily_cost_limit = getattr(settings, "AI_IMAGE_DAILY_COST_LIMIT", 5.0)

    def search_all_sources(
        self,
        plant_name: str,
        scientific_name: Optional[str] = None,
        limit_per_source: int = 5,
    ) -> Dict[str, List[Dict]]:
        """
        Search all available image sources for plant images.

        Args:
            plant_name: Common name of the plant
            scientific_name: Scientific name for accurate results
            limit_per_source: Maximum results per source

        Returns:
            Dictionary mapping source names to image lists
        """
        results = {}

        # Search Unsplash
        try:
            unsplash_images = self.unsplash.search_plant_images(
                plant_name=plant_name,
                scientific_name=scientific_name,
                limit=limit_per_source,
                orientation="landscape",
            )
            results["unsplash"] = unsplash_images
            logger.info(
                f"[PLANT_IMAGE] Found {len(unsplash_images)} Unsplash images for {plant_name}"
            )
        except Exception as e:
            logger.error(f"[PLANT_IMAGE] Unsplash search failed for {plant_name}: {e}")
            results["unsplash"] = []

        # Search Pexels
        try:
            pexels_images = self.pexels.search_plant_images(
                plant_name=plant_name,
                scientific_name=scientific_name,
                limit=limit_per_source,
                orientation="landscape",
            )
            results["pexels"] = pexels_images
            logger.info(
                f"[PLANT_IMAGE] Found {len(pexels_images)} Pexels images for {plant_name}"
            )
        except Exception as e:
            logger.error(f"[PLANT_IMAGE] Pexels search failed for {plant_name}: {e}")
            results["pexels"] = []

        # Note: AI generation is not included in search as it's expensive
        # It's only used as a fallback when stock photos aren't suitable
        results["ai_available"] = self.ai_service.client is not None

        return results

    def get_best_plant_image(
        self,
        plant_name: str,
        scientific_name: Optional[str] = None,
        prefer_source: Optional[str] = None,
        allow_ai_generation: bool = True,
    ) -> Optional[Tuple[str, Dict, Image]]:
        """
        Get the best available plant image using intelligent fallback strategy.

        Args:
            plant_name: Common name of the plant
            scientific_name: Scientific name for accuracy
            prefer_source: Preferred source ('unsplash', 'pexels', 'ai')
            allow_ai_generation: Whether to allow AI generation as fallback

        Returns:
            Tuple of (source_name, image_data, wagtail_image) or None if not found
        """
        # Determine source order based on preference
        if prefer_source and prefer_source in self.source_priority:
            sources = [prefer_source] + [
                s for s in self.source_priority if s != prefer_source
            ]
        else:
            sources = self.source_priority.copy()

        # Remove AI from sources if not allowed
        if not allow_ai_generation:
            sources = [s for s in sources if s != "ai"]

        for source in sources:
            try:
                if source == "unsplash":
                    result = self.unsplash.get_best_plant_image(
                        plant_name, scientific_name
                    )
                    if result:
                        image_data, wagtail_image = result
                        # Trigger download tracking for Unsplash (required by ToS)
                        self.unsplash.trigger_download(image_data)
                        logger.info(
                            f"[PLANT_IMAGE] Successfully got {plant_name} image from Unsplash"
                        )
                        return "unsplash", image_data, wagtail_image

                elif source == "pexels":
                    result = self.pexels.get_best_plant_image(
                        plant_name, scientific_name
                    )
                    if result:
                        image_data, wagtail_image = result
                        logger.info(
                            f"[PLANT_IMAGE] Successfully got {plant_name} image from Pexels"
                        )
                        return "pexels", image_data, wagtail_image

                elif source == "ai":
                    # Check if AI generation is cost-effective
                    if self._should_use_ai_generation():
                        result = self.ai_service.get_best_ai_plant_image(
                            plant_name, scientific_name
                        )
                        if result:
                            image_data, wagtail_image = result
                            logger.info(
                                f"[PLANT_IMAGE] Successfully generated AI image for {plant_name}"
                            )
                            return "ai", image_data, wagtail_image
                    else:
                        logger.info(
                            f"[PLANT_IMAGE] Skipping AI generation for {plant_name} due to cost limits"
                        )

            except Exception as e:
                logger.error(
                    f"[PLANT_IMAGE] Failed to get image from {source} for {plant_name}: {e}"
                )
                continue

        logger.warning(
            f"[PLANT_IMAGE] No images found for {plant_name} from any source"
        )
        return None

    def _should_use_ai_generation(self) -> bool:
        """
        Determine if AI generation should be used based on cost and availability.

        Returns:
            True if AI generation should be used
        """
        if not self.ai_service.client:
            return False

        # Check daily cost limit
        current_cost = self.ai_service.get_daily_cost()
        estimated_cost = 0.040  # Standard DALL-E 3 cost

        return (current_cost + estimated_cost) <= self._daily_cost_limit

    @staticmethod
    def get_attribution_text(source: str, image_data: Dict) -> str:
        """
        Generate proper attribution text for an image based on its source.

        Args:
            source: Source name ('unsplash', 'pexels', 'ai')
            image_data: Image metadata

        Returns:
            Formatted attribution text
        """
        # `or {}`: a provider can send "photographer": null, and this now
        # runs BEFORE the block is saved, so a crash would drop the image
        # (PR #820 review).
        if source == "unsplash":
            photographer = image_data.get("photographer") or {}
            photographer_name = photographer.get("name") or "Unknown"
            return f"Photo by {photographer_name}{UNSPLASH_CREDIT_SUFFIX}"

        elif source == "pexels":
            photographer = image_data.get("photographer") or {}
            photographer_name = photographer.get("name") or "Unknown"
            return f"Photo by {photographer_name} from Pexels"

        elif source == "ai":
            return "AI-generated botanical image (DALL-E 3)"

        else:
            return "Image attribution unknown"

    @staticmethod
    def get_attribution_url(source: str, image_data: Dict) -> str:
        """
        Link for the displayed credit (todo 376): the photographer's page.

        Unsplash links carry the referral UTM parameters its API guidelines
        require. Returns "" when there is nothing to link (AI images) or the
        provider value is not an absolute http(s) URL — the credit then
        renders as plain text rather than as an unsafe or dead link.

        Args:
            source: Source name ('unsplash', 'pexels', 'ai')
            image_data: Image metadata

        Returns:
            An http(s) URL, or ""
        """
        photographer = image_data.get("photographer") or {}
        if source == "unsplash":
            url = photographer.get("profile_url") or ""
        elif source == "pexels":
            url = photographer.get("url") or ""
        else:
            return ""

        url = safe_http_url(url)
        if not url:
            return ""
        return with_unsplash_utm(url) if source == "unsplash" else url

    @staticmethod
    def attribution_from_image_tags(tag_names) -> Optional[Tuple[str, str]]:
        """
        Rebuild `(credit_text, credit_url)` from a stored image's taggit tags.

        For images saved before the credit was stored on the spotlight block
        (todo 438 backfill). The tag shapes are the ones each service's
        `download_and_create_wagtail_image` writes:

        - Unsplash: `unsplash`, `photographer:<username>`, `unsplash_id:<id>`.
          Only the username is kept, so the credit names the username and
          links `https://unsplash.com/@<username>` (with the UTM params).
        - Pexels: `pexels`, `photographer:<name with spaces as _>`. No
          photographer URL is kept, so the credit is text only; `_` is turned
          back into a space (lossy for a name that really contained `_`).
        - AI: `ai_generated` -> the same disclosure text as a fresh image.

        Returns None when the tags do not identify exactly one provider, or a
        stock photo has no usable photographer (both services write
        `photographer:unknown` when the provider sent none) — never a guess.
        """
        names = [str(name) for name in tag_names]
        lowered = {name.lower() for name in names}
        sources = [s for s in ("unsplash", "pexels") if s in lowered]
        if "ai_generated" in lowered:
            sources.append("ai")
        if len(sources) != 1:
            return None
        source = sources[0]
        if source == "ai":
            return PlantImageService.get_attribution_text("ai", {}), ""

        photographers = [
            name.split(":", 1)[1].strip()
            for name in names
            if name.lower().startswith("photographer:")
        ]
        if len(photographers) != 1:
            return None
        photographer = photographers[0]
        if not photographer or photographer.lower() == "unknown":
            return None

        if source == "unsplash":
            image_data = {"photographer": {"name": photographer}}
            # Unsplash usernames are [A-Za-z0-9_]; anything else is not a
            # username we can safely build a profile path from.
            if re.fullmatch(r"[A-Za-z0-9_]+", photographer):
                image_data["photographer"][
                    "profile_url"
                ] = f"https://unsplash.com/@{photographer}"
        else:
            image_data = {"photographer": {"name": photographer.replace("_", " ")}}
        return (
            PlantImageService.get_attribution_text(source, image_data),
            PlantImageService.get_attribution_url(source, image_data),
        )

    def get_source_stats(self) -> Dict:
        """
        Get statistics and availability for all image sources.

        Returns:
            Dictionary with source statistics
        """
        return {
            "unsplash": {
                "available": self.unsplash.access_key is not None,
                "rate_limit_key": "unsplash_rate_limit",
                "description": "High-quality stock photography",
            },
            "pexels": {
                "available": self.pexels.api_key is not None,
                "rate_limit_key": "pexels_rate_limit",
                "description": "Large collection of stock photos",
            },
            "ai": {
                "available": self.ai_service.client is not None,
                "daily_cost": (
                    self.ai_service.get_daily_cost() if self.ai_service.client else 0
                ),
                "cost_limit": self._daily_cost_limit,
                "description": "AI-generated botanical images",
            },
        }

    def batch_process_plants(
        self, plant_list: List[Dict], max_ai_images: int = 3
    ) -> Dict[str, Union[str, Dict]]:
        """
        Process multiple plants for image sourcing with intelligent resource management.

        Args:
            plant_list: List of plant dictionaries with 'name' and optional 'scientific_name'
            max_ai_images: Maximum number of AI images to generate in this batch

        Returns:
            Dictionary mapping plant names to results
        """
        results = {}
        ai_images_generated = 0

        for plant_info in plant_list:
            plant_name = plant_info.get("name", "")
            scientific_name = plant_info.get("scientific_name")

            if not plant_name:
                continue

            # Determine if AI generation should be allowed for this plant
            allow_ai = ai_images_generated < max_ai_images

            try:
                result = self.get_best_plant_image(
                    plant_name=plant_name,
                    scientific_name=scientific_name,
                    allow_ai_generation=allow_ai,
                )

                if result:
                    source, image_data, wagtail_image = result
                    results[plant_name] = {
                        "success": True,
                        "source": source,
                        "image_id": wagtail_image.id,
                        "image_title": wagtail_image.title,
                        "attribution": self.get_attribution_text(source, image_data),
                    }

                    # Track AI usage
                    if source == "ai":
                        ai_images_generated += 1

                    logger.info(
                        f"[PLANT_IMAGE] Successfully processed image for {plant_name} from {source}"
                    )

                else:
                    results[plant_name] = {
                        "success": False,
                        "error": "No suitable images found",
                    }
                    logger.warning(f"[PLANT_IMAGE] No images found for {plant_name}")

            except Exception:
                # Per-plant result dict, response-shaped (todo 377). The
                # underlying services are HTTP clients, so `str(e)` here can
                # carry a prepared URL with an api-key query parameter.
                results[plant_name] = {
                    "success": False,
                    "error": "Image processing failed",
                }
                logger.exception("[PLANT_IMAGE] Failed to process %s", plant_name)

        # Add batch summary
        results["_batch_summary"] = {
            "total_plants": len(plant_list),
            "successful": sum(
                1 for r in results.values() if isinstance(r, dict) and r.get("success")
            ),
            "ai_images_generated": ai_images_generated,
            "sources_used": list(
                set(
                    r.get("source")
                    for r in results.values()
                    if isinstance(r, dict) and r.get("success")
                )
            ),
        }

        return results
