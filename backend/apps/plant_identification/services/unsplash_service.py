"""
Unsplash API integration service for plant image sourcing.

Provides high-quality plant and botanical images from Unsplash's API.
Documentation: https://unsplash.com/documentation
"""

import logging
import re
from io import BytesIO
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests
from apps.core.utils.pii_safe_logging import log_safe_api_error
from django.conf import settings
from django.core.cache import cache
from django.core.files.images import ImageFile
from wagtail.images.models import Image

logger = logging.getLogger(__name__)

# Unsplash's API guidelines require these on every link back to Unsplash
# (download tracking AND the displayed photographer credit, todo 376).
UNSPLASH_UTM_PARAMS = {"utm_source": "plant_community", "utm_medium": "referral"}


def with_unsplash_utm(url: str) -> str:
    """Append Unsplash's required referral UTM parameters to `url`."""
    separator = "&" if "?" in url else "?"
    return url + separator + urlencode(UNSPLASH_UTM_PARAMS)


# The displayed credit is "Photo by <name> on Unsplash"
# (PlantImageService.get_attribution_text). Renderers link the trailing
# "Unsplash" to UNSPLASH_HOME_URL when a credit ends with this suffix, since
# the guidelines ask for a link to the photographer AND to Unsplash (todo 438).
# `apps.blog.blocks.PlantSpotlightBlock` is the one place that derives the split
# (`credit_lead`, `unsplash_href`), for the Wagtail template and the API alike;
# the web renders the API values and never re-derives them (todo 442).
UNSPLASH_CREDIT_SUFFIX = " on Unsplash"
UNSPLASH_HOME_URL = with_unsplash_utm("https://unsplash.com/")

# An Unsplash photo id as the API issues them. `get_photo` builds a URL path
# from an id read back out of an image's tags, which editors can change in the
# CMS, so anything else is refused rather than requested.
UNSPLASH_PHOTO_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")

# `UnsplashImageService.lookup_photo` outcomes (todo 530).
PHOTO_FOUND = "found"
PHOTO_GONE = "gone"
PHOTO_LOOKUP_DISABLED = "disabled"
PHOTO_UNAVAILABLE = "unavailable"


class UnsplashImageService:
    """
    Service for sourcing plant images from Unsplash API.
    Provides free high-quality botanical photography with proper licensing.
    """

    BASE_URL = "https://api.unsplash.com"
    CACHE_TIMEOUT = 3600 * 24  # 24 hours for image search results
    RATE_LIMIT_CACHE_TIMEOUT = 3600  # 1 hour for rate limit tracking
    RATE_LIMIT_KEY = "unsplash_rate_limit"
    RATE_LIMIT = 50  # Demo limit: requests per hour

    def __init__(self, access_key: Optional[str] = None):
        """
        Initialize the Unsplash API service.

        Args:
            access_key: Unsplash API access key. If not provided, will use settings.UNSPLASH_ACCESS_KEY
        """
        self.access_key = access_key or getattr(settings, "UNSPLASH_ACCESS_KEY", None)
        if not self.access_key:
            logger.warning(
                "[UNSPLASH] Unsplash API key not configured - image search will be disabled"
            )
            self.access_key = None

        self.session = requests.Session()
        if self.access_key:
            self.session.headers.update(
                {
                    "Authorization": f"Client-ID {self.access_key}",
                    "Accept-Version": "v1",
                }
            )

    def is_rate_limited(self) -> bool:
        """True while the shared request counter is at the hourly limit."""
        return cache.get(self.RATE_LIMIT_KEY, 0) >= self.RATE_LIMIT

    def _make_request(
        self, endpoint: str, params: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Make a request to the Unsplash API with error handling and rate limiting.

        Args:
            endpoint: API endpoint (without base URL)
            params: Additional query parameters

        Returns:
            JSON response data or None if error
        """
        return self._request(endpoint, params)[1]

    def _request(
        self, endpoint: str, params: Optional[Dict] = None
    ) -> Tuple[Optional[int], Optional[Dict]]:
        """
        `_make_request` plus the HTTP status, so a caller can tell a 404 (the
        resource is gone) from a failure worth retrying (todo 530).

        Returns:
            (status_code, json): status_code is None when no response arrived
            (no key, the rate limit, a network error); json is None unless
            the request succeeded
        """
        if not self.access_key:
            logger.warning("[UNSPLASH] Unsplash API key not available")
            return None, None

        if self.is_rate_limited():
            logger.warning("[UNSPLASH] Unsplash API rate limit exceeded")
            return None, None

        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        try:
            response = self.session.get(url, params=params or {}, timeout=30)

            # Track rate limiting. Only from a header that is present and
            # numeric: defaulting a missing one to 0 remaining blocked every
            # Unsplash call for an hour (todo 530).
            try:
                remaining = int(response.headers["X-Ratelimit-Remaining"])
            except (KeyError, TypeError, ValueError):
                remaining = None
            if remaining is not None:
                cache.set(
                    self.RATE_LIMIT_KEY,
                    self.RATE_LIMIT - remaining,
                    self.RATE_LIMIT_CACHE_TIMEOUT,
                )

            if response.status_code == 404:
                logger.info(f"[UNSPLASH] Not found on Unsplash: {url}")
                return 404, None
            response.raise_for_status()
            return response.status_code, response.json()

        except requests.exceptions.RequestException as e:
            # NOT str(e): requests builds its message from the prepared URL,
            # which carries every query parameter. `url` itself is the bare
            # endpoint (params ride in `params=`), so it stays.
            logger.error(
                f"[UNSPLASH] Unsplash API request failed: {url} - {log_safe_api_error(e)}"
            )
            response = getattr(e, "response", None)
            return getattr(response, "status_code", None), None

    def search_plant_images(
        self,
        plant_name: str,
        scientific_name: Optional[str] = None,
        limit: int = 10,
        orientation: str = "landscape",
    ) -> List[Dict]:
        """
        Search for plant images on Unsplash.

        Args:
            plant_name: Common name of the plant
            scientific_name: Scientific name for more specific results
            limit: Maximum number of results (max 30)
            orientation: Image orientation ('landscape', 'portrait', 'squarish')

        Returns:
            List of image data dictionaries with URLs, descriptions, and metadata
        """
        if not self.access_key:
            return []

        # Build search query - prioritize scientific name for accuracy
        query_parts = []
        if scientific_name:
            query_parts.append(f'"{scientific_name}"')
        query_parts.append(plant_name)
        query_parts.extend(["plant", "botanical", "nature"])

        search_query = " ".join(query_parts)

        # Check cache first
        cache_key = f"unsplash_search_{search_query.replace(' ', '_').lower()}_{limit}_{orientation}"
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"[UNSPLASH] Using cached Unsplash results for: {plant_name}")
            return cached_result

        params = {
            "query": search_query,
            "per_page": min(limit, 30),  # Unsplash API limit
            "orientation": orientation,
            "content_filter": "high",  # Filter out inappropriate content
            "order_by": "relevant",
        }

        result = self._make_request("search/photos", params)
        if not result:
            return []

        photos = result.get("results", [])

        # Process and clean image data
        processed_images = []
        for photo in photos:
            image_data = self._process_photo(photo)
            if image_data is not None:
                processed_images.append(image_data)

        # Cache successful results
        cache.set(cache_key, processed_images, self.CACHE_TIMEOUT)
        logger.info(
            f"[UNSPLASH] Found {len(processed_images)} Unsplash images for: {plant_name}"
        )

        return processed_images

    @staticmethod
    def _process_photo(photo: Dict) -> Optional[Dict]:
        """
        Shape one Unsplash photo object into this service's image_data dict.

        `search/photos` (each item of `results`) and `photos/:id` return the
        same object, so the search path and `get_photo` share this. Returns
        None, after logging, when a required key is missing.

        Args:
            photo: One photo object as the Unsplash API returns it

        Returns:
            Image data dictionary or None if the object is malformed
        """
        try:
            return {
                "id": photo["id"],
                "description": photo.get("description")
                or photo.get("alt_description", ""),
                "urls": {
                    "raw": photo["urls"]["raw"],
                    "full": photo["urls"]["full"],
                    "regular": photo["urls"]["regular"],
                    "small": photo["urls"]["small"],
                    "thumb": photo["urls"]["thumb"],
                },
                "width": photo["width"],
                "height": photo["height"],
                "color": photo.get("color", "#000000"),
                "photographer": {
                    "name": photo["user"]["name"],
                    "username": photo["user"]["username"],
                    "profile_url": photo["user"]["links"]["html"],
                },
                "download_url": photo["links"]["download"],
                "attribution_url": photo["links"]["html"],
                "created_at": photo["created_at"],
                "likes": photo["likes"],
                "source": "unsplash",
            }
        except (KeyError, TypeError) as e:
            logger.error(f"[UNSPLASH] Invalid Unsplash photo data structure: {e}")
            return None

    def get_photo(self, photo_id: str) -> Optional[Dict]:
        """
        Fetch one photo's current metadata (`GET /photos/:id`).

        `lookup_photo` without the reason; see there.

        Returns:
            Image data dictionary, or None when the lookup did not find one
        """
        return self.lookup_photo(photo_id)[1]

    def lookup_photo(self, photo_id: str) -> Tuple[str, Optional[Dict]]:
        """
        Fetch one photo's current metadata (`GET /photos/:id`), and say why
        not when it can't.

        `backfill_spotlight_credits` uses it to credit a stored photo's
        photographer by name and link their profile, where the image's tags
        keep only the username (todo 442; owner decision 2026-09-28). The
        result has the same shape as a `search_plant_images` item and is
        cached for CACHE_TIMEOUT, so a `--dry-run` followed by the real run
        costs one request per image. A photo Unsplash answers 404 for is
        remembered as gone for RATE_LIMIT_CACHE_TIMEOUT, so a re-run does not
        spend the hourly budget asking again (todo 530).

        Args:
            photo_id: The Unsplash photo id (the `unsplash_id:` tag's value)

        Returns:
            (status, image_data). status is PHOTO_FOUND with the image data;
            otherwise image_data is None and status is PHOTO_LOOKUP_DISABLED
            (no access key), PHOTO_GONE (a 404, or an id that is not an
            Unsplash id: asking again cannot help) or PHOTO_UNAVAILABLE (the
            rate limit, a network or API error, a malformed response: a later
            run may succeed)
        """
        if not self.access_key:
            return PHOTO_LOOKUP_DISABLED, None
        photo_id = (photo_id or "").strip()
        if not UNSPLASH_PHOTO_ID.fullmatch(photo_id):
            logger.warning("[UNSPLASH] Refusing photo lookup for a malformed id")
            return PHOTO_GONE, None

        cache_key = f"unsplash_photo_{photo_id}"
        gone_key = f"unsplash_photo_gone_{photo_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return PHOTO_FOUND, cached
        if cache.get(gone_key) is not None:
            return PHOTO_GONE, None

        status_code, result = self._request(f"photos/{photo_id}")
        if status_code == 404:
            cache.set(gone_key, True, self.RATE_LIMIT_CACHE_TIMEOUT)
            return PHOTO_GONE, None
        if not result:
            return PHOTO_UNAVAILABLE, None
        image_data = self._process_photo(result)
        if image_data is None:
            return PHOTO_UNAVAILABLE, None
        cache.set(cache_key, image_data, self.CACHE_TIMEOUT)
        return PHOTO_FOUND, image_data

    def download_and_create_wagtail_image(
        self, image_data: Dict, title_prefix: str = "Plant Image"
    ) -> Optional[Image]:
        """
        Download an image from Unsplash and create a Wagtail Image object.

        Args:
            image_data: Image data dictionary from search_plant_images
            title_prefix: Prefix for the image title

        Returns:
            Wagtail Image object or None if failed
        """
        if not image_data or "urls" not in image_data:
            return None

        try:
            # Use 'regular' size for good quality/performance balance
            image_url = image_data["urls"]["regular"]

            # Download the image
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()

            # Create file content using BytesIO and ImageFile for proper metadata extraction
            filename = f"unsplash_{image_data['id']}.jpg"
            image_io = BytesIO(response.content)
            image_file = ImageFile(image_io, name=filename)

            # Create Wagtail Image
            title = (
                f"{title_prefix} - {image_data.get('description', 'Botanical Image')}"[
                    :255
                ]
            )

            photographer = image_data.get("photographer", {})

            wagtail_image = Image(title=title, file=image_file)
            wagtail_image.save()

            # Store additional metadata in tags (if using taggit)
            try:
                tags = [
                    "unsplash",
                    "botanical",
                    f"photographer:{photographer.get('username', 'unknown')}",
                    f"unsplash_id:{image_data['id']}",
                ]
                wagtail_image.tags.add(*tags)
            except Exception as e:
                logger.warning(f"[UNSPLASH] Could not add tags to image: {e}")

            logger.info(f"[UNSPLASH] Created Wagtail image: {title}")
            return wagtail_image

        except Exception as e:
            logger.error(f"[UNSPLASH] Failed to download/create Wagtail image: {e}")
            return None

    def get_best_plant_image(
        self, plant_name: str, scientific_name: Optional[str] = None
    ) -> Optional[Tuple[Dict, Image]]:
        """
        Get the best available plant image and create a Wagtail Image object.

        Args:
            plant_name: Common name of the plant
            scientific_name: Scientific name for more accurate results

        Returns:
            Tuple of (image_data, wagtail_image) or None if not found
        """
        images = self.search_plant_images(
            plant_name=plant_name,
            scientific_name=scientific_name,
            limit=5,  # Get top 5 to choose from
            orientation="landscape",  # Better for spotlight blocks
        )

        if not images:
            logger.info(f"[UNSPLASH] No Unsplash images found for: {plant_name}")
            return None

        # Sort by relevance factors (likes, quality, etc.)
        sorted_images = sorted(
            images,
            key=lambda x: (
                x.get("likes", 0),
                x.get("width", 0) * x.get("height", 0),  # Image size
                1 if x.get("description") else 0,  # Has description
            ),
            reverse=True,
        )

        # Try to download the best image
        for image_data in sorted_images:
            wagtail_image = self.download_and_create_wagtail_image(
                image_data, title_prefix=f"{plant_name} Plant"
            )
            if wagtail_image:
                return image_data, wagtail_image

        logger.warning(
            f"[UNSPLASH] Failed to download any Unsplash images for: {plant_name}"
        )
        return None

    def trigger_download(self, image_data: Dict) -> None:
        """
        Trigger download tracking on Unsplash (required by API terms).
        Call this when actually using an image.

        Args:
            image_data: Image data dictionary from search results
        """
        if not self.access_key or "download_url" not in image_data:
            return

        try:
            # Add UTM parameters as required by Unsplash
            download_url = with_unsplash_utm(image_data["download_url"])

            # Make request to trigger download tracking
            response = requests.get(download_url, timeout=10)
            response.raise_for_status()

            logger.info(
                f"[UNSPLASH] Triggered download tracking for Unsplash image: {image_data.get('id')}"
            )

        except Exception as e:
            logger.error(
                f"[UNSPLASH] Failed to trigger Unsplash download tracking: {e}"
            )
