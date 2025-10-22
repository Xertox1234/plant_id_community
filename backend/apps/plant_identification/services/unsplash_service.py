"""
Unsplash API integration service for plant image sourcing.

Provides high-quality plant and botanical images from Unsplash's API.
Documentation: https://unsplash.com/documentation
"""

import requests
import logging
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.core.cache import cache
from django.core.files.images import ImageFile
from django.core.files.storage import default_storage
from wagtail.images.models import Image
from io import BytesIO
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class UnsplashImageService:
    """
    Service for sourcing plant images from Unsplash API.
    Provides free high-quality botanical photography with proper licensing.
    """
    
    BASE_URL = "https://api.unsplash.com"
    CACHE_TIMEOUT = 3600 * 24  # 24 hours for image search results
    RATE_LIMIT_CACHE_TIMEOUT = 3600  # 1 hour for rate limit tracking
    
    def __init__(self, access_key: Optional[str] = None):
        """
        Initialize the Unsplash API service.
        
        Args:
            access_key: Unsplash API access key. If not provided, will use settings.UNSPLASH_ACCESS_KEY
        """
        self.access_key = access_key or getattr(settings, 'UNSPLASH_ACCESS_KEY', None)
        if not self.access_key:
            logger.warning("Unsplash API key not configured - image search will be disabled")
            self.access_key = None
        
        self.session = requests.Session()
        if self.access_key:
            self.session.headers.update({
                'Authorization': f'Client-ID {self.access_key}',
                'Accept-Version': 'v1'
            })
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make a request to the Unsplash API with error handling and rate limiting.
        
        Args:
            endpoint: API endpoint (without base URL)
            params: Additional query parameters
            
        Returns:
            JSON response data or None if error
        """
        if not self.access_key:
            logger.warning("Unsplash API key not available")
            return None
            
        # Check rate limits from cache
        rate_limit_key = "unsplash_rate_limit"
        if cache.get(rate_limit_key, 0) >= 50:  # Demo limit
            logger.warning("Unsplash API rate limit exceeded")
            return None
        
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.get(url, params=params or {}, timeout=30)
            
            # Track rate limiting
            remaining = int(response.headers.get('X-Ratelimit-Remaining', 0))
            cache.set(rate_limit_key, 50 - remaining, self.RATE_LIMIT_CACHE_TIMEOUT)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Unsplash API request failed: {url} - {str(e)}")
            return None
    
    def search_plant_images(self, plant_name: str, scientific_name: Optional[str] = None, 
                           limit: int = 10, orientation: str = 'landscape') -> List[Dict]:
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
        query_parts.extend(['plant', 'botanical', 'nature'])
        
        search_query = ' '.join(query_parts)
        
        # Check cache first
        cache_key = f"unsplash_search_{search_query.replace(' ', '_').lower()}_{limit}_{orientation}"
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"Using cached Unsplash results for: {plant_name}")
            return cached_result
        
        params = {
            'query': search_query,
            'per_page': min(limit, 30),  # Unsplash API limit
            'orientation': orientation,
            'content_filter': 'high',  # Filter out inappropriate content
            'order_by': 'relevant'
        }
        
        result = self._make_request('search/photos', params)
        if not result:
            return []
        
        photos = result.get('results', [])
        
        # Process and clean image data
        processed_images = []
        for photo in photos:
            try:
                image_data = {
                    'id': photo['id'],
                    'description': photo.get('description') or photo.get('alt_description', ''),
                    'urls': {
                        'raw': photo['urls']['raw'],
                        'full': photo['urls']['full'],
                        'regular': photo['urls']['regular'],
                        'small': photo['urls']['small'],
                        'thumb': photo['urls']['thumb']
                    },
                    'width': photo['width'],
                    'height': photo['height'],
                    'color': photo.get('color', '#000000'),
                    'photographer': {
                        'name': photo['user']['name'],
                        'username': photo['user']['username'],
                        'profile_url': photo['user']['links']['html']
                    },
                    'download_url': photo['links']['download'],
                    'attribution_url': photo['links']['html'],
                    'created_at': photo['created_at'],
                    'likes': photo['likes'],
                    'source': 'unsplash'
                }
                processed_images.append(image_data)
            except KeyError as e:
                logger.error(f"Invalid Unsplash photo data structure: {e}")
                continue
        
        # Cache successful results
        cache.set(cache_key, processed_images, self.CACHE_TIMEOUT)
        logger.info(f"Found {len(processed_images)} Unsplash images for: {plant_name}")
        
        return processed_images
    
    def download_and_create_wagtail_image(self, image_data: Dict, 
                                        title_prefix: str = "Plant Image") -> Optional[Image]:
        """
        Download an image from Unsplash and create a Wagtail Image object.
        
        Args:
            image_data: Image data dictionary from search_plant_images
            title_prefix: Prefix for the image title
            
        Returns:
            Wagtail Image object or None if failed
        """
        if not image_data or 'urls' not in image_data:
            return None
        
        try:
            # Use 'regular' size for good quality/performance balance
            image_url = image_data['urls']['regular']
            
            # Download the image
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Create file content using BytesIO and ImageFile for proper metadata extraction
            filename = f"unsplash_{image_data['id']}.jpg"
            image_io = BytesIO(response.content)
            image_file = ImageFile(image_io, name=filename)
            
            # Create Wagtail Image
            title = f"{title_prefix} - {image_data.get('description', 'Botanical Image')}"[:255]
            
            # Build attribution text
            photographer = image_data.get('photographer', {})
            attribution = f"Photo by {photographer.get('name', 'Unknown')} on Unsplash"
            
            wagtail_image = Image(
                title=title,
                file=image_file
            )
            wagtail_image.save()
            
            # Store additional metadata in tags (if using taggit)
            try:
                tags = [
                    'unsplash',
                    'botanical',
                    f"photographer:{photographer.get('username', 'unknown')}",
                    f"unsplash_id:{image_data['id']}"
                ]
                wagtail_image.tags.add(*tags)
            except Exception as e:
                logger.warning(f"Could not add tags to image: {e}")
            
            logger.info(f"Created Wagtail image: {title}")
            return wagtail_image
            
        except Exception as e:
            logger.error(f"Failed to download/create Wagtail image: {e}")
            return None
    
    def get_best_plant_image(self, plant_name: str, scientific_name: Optional[str] = None) -> Optional[Tuple[Dict, Image]]:
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
            orientation='landscape'  # Better for spotlight blocks
        )
        
        if not images:
            logger.info(f"No Unsplash images found for: {plant_name}")
            return None
        
        # Sort by relevance factors (likes, quality, etc.)
        sorted_images = sorted(images, key=lambda x: (
            x.get('likes', 0),
            x.get('width', 0) * x.get('height', 0),  # Image size
            1 if x.get('description') else 0  # Has description
        ), reverse=True)
        
        # Try to download the best image
        for image_data in sorted_images:
            wagtail_image = self.download_and_create_wagtail_image(
                image_data, 
                title_prefix=f"{plant_name} Plant"
            )
            if wagtail_image:
                return image_data, wagtail_image
        
        logger.warning(f"Failed to download any Unsplash images for: {plant_name}")
        return None
    
    def trigger_download(self, image_data: Dict) -> None:
        """
        Trigger download tracking on Unsplash (required by API terms).
        Call this when actually using an image.
        
        Args:
            image_data: Image data dictionary from search results
        """
        if not self.access_key or 'download_url' not in image_data:
            return
            
        try:
            download_url = image_data['download_url']
            # Add UTM parameters as required by Unsplash
            utm_params = {
                'utm_source': 'plant_community',
                'utm_medium': 'referral'
            }
            
            if '?' in download_url:
                download_url += '&' + urlencode(utm_params)
            else:
                download_url += '?' + urlencode(utm_params)
            
            # Make request to trigger download tracking
            response = requests.get(download_url, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Triggered download tracking for Unsplash image: {image_data.get('id')}")
            
        except Exception as e:
            logger.error(f"Failed to trigger Unsplash download tracking: {e}")