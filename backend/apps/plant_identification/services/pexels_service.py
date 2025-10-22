"""
Pexels API integration service for plant image sourcing.

Provides high-quality plant and botanical images from Pexels API as a fallback to Unsplash.
Documentation: https://www.pexels.com/api/documentation/
"""

import requests
import logging
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.core.cache import cache
from django.core.files.images import ImageFile
from wagtail.images.models import Image
from io import BytesIO

logger = logging.getLogger(__name__)


class PexelsImageService:
    """
    Service for sourcing plant images from Pexels API.
    Provides free high-quality botanical photography as fallback option.
    """
    
    BASE_URL = "https://api.pexels.com/v1"
    CACHE_TIMEOUT = 3600 * 24  # 24 hours for image search results
    RATE_LIMIT_CACHE_TIMEOUT = 3600  # 1 hour for rate limit tracking
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Pexels API service.
        
        Args:
            api_key: Pexels API key. If not provided, will use settings.PEXELS_API_KEY
        """
        self.api_key = api_key or getattr(settings, 'PEXELS_API_KEY', None)
        if not self.api_key:
            logger.warning("Pexels API key not configured - image search will be disabled")
            self.api_key = None
        
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                'Authorization': self.api_key
            })
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make a request to the Pexels API with error handling and rate limiting.
        
        Args:
            endpoint: API endpoint (without base URL)
            params: Additional query parameters
            
        Returns:
            JSON response data or None if error
        """
        if not self.api_key:
            logger.warning("Pexels API key not available")
            return None
            
        # Check rate limits from cache (generous limits for Pexels)
        rate_limit_key = "pexels_rate_limit"
        if cache.get(rate_limit_key, 0) >= 200:  # Conservative limit
            logger.warning("Pexels API rate limit exceeded")
            return None
        
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.get(url, params=params or {}, timeout=30)
            
            # Track rate limiting (increment counter)
            current_count = cache.get(rate_limit_key, 0)
            cache.set(rate_limit_key, current_count + 1, self.RATE_LIMIT_CACHE_TIMEOUT)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Pexels API request failed: {url} - {str(e)}")
            return None
    
    def search_plant_images(self, plant_name: str, scientific_name: Optional[str] = None, 
                           limit: int = 15, orientation: str = 'landscape') -> List[Dict]:
        """
        Search for plant images on Pexels.
        
        Args:
            plant_name: Common name of the plant
            scientific_name: Scientific name for more specific results
            limit: Maximum number of results (max 80)
            orientation: Image orientation ('landscape', 'portrait', 'square')
            
        Returns:
            List of image data dictionaries with URLs, descriptions, and metadata
        """
        if not self.api_key:
            return []
            
        # Build search query - prioritize scientific name for accuracy
        query_parts = []
        if scientific_name:
            query_parts.append(f'"{scientific_name}"')
        query_parts.append(plant_name)
        query_parts.extend(['plant', 'botanical', 'nature', 'leaf'])
        
        search_query = ' '.join(query_parts)
        
        # Check cache first
        cache_key = f"pexels_search_{search_query.replace(' ', '_').lower()}_{limit}_{orientation}"
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"Using cached Pexels results for: {plant_name}")
            return cached_result
        
        params = {
            'query': search_query,
            'per_page': min(limit, 80),  # Pexels API limit
            'orientation': orientation
        }
        
        result = self._make_request('search', params)
        if not result:
            return []
        
        photos = result.get('photos', [])
        
        # Process and clean image data
        processed_images = []
        for photo in photos:
            try:
                image_data = {
                    'id': photo['id'],
                    'description': photo.get('alt', f"Botanical image of {plant_name}"),
                    'urls': {
                        'original': photo['src']['original'],
                        'large2x': photo['src']['large2x'],
                        'large': photo['src']['large'],
                        'medium': photo['src']['medium'],
                        'small': photo['src']['small'],
                        'portrait': photo['src']['portrait'],
                        'landscape': photo['src']['landscape'],
                        'tiny': photo['src']['tiny']
                    },
                    'width': photo['width'],
                    'height': photo['height'],
                    'photographer': {
                        'name': photo['photographer'],
                        'url': photo['photographer_url']
                    },
                    'attribution_url': photo['url'],
                    'avg_color': photo.get('avg_color', '#000000'),
                    'source': 'pexels'
                }
                processed_images.append(image_data)
            except KeyError as e:
                logger.error(f"Invalid Pexels photo data structure: {e}")
                continue
        
        # Cache successful results
        cache.set(cache_key, processed_images, self.CACHE_TIMEOUT)
        logger.info(f"Found {len(processed_images)} Pexels images for: {plant_name}")
        
        return processed_images
    
    def download_and_create_wagtail_image(self, image_data: Dict, 
                                        title_prefix: str = "Plant Image") -> Optional[Image]:
        """
        Download an image from Pexels and create a Wagtail Image object.
        
        Args:
            image_data: Image data dictionary from search_plant_images
            title_prefix: Prefix for the image title
            
        Returns:
            Wagtail Image object or None if failed
        """
        if not image_data or 'urls' not in image_data:
            return None
        
        try:
            # Use 'large' size for good quality/performance balance
            image_url = image_data['urls']['large']
            
            # Download the image
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Create file content using BytesIO and ImageFile for proper metadata extraction
            filename = f"pexels_{image_data['id']}.jpg"
            image_io = BytesIO(response.content)
            image_file = ImageFile(image_io, name=filename)
            
            # Create Wagtail Image
            title = f"{title_prefix} - {image_data.get('description', 'Botanical Image')}"[:255]
            
            # Build attribution text
            photographer = image_data.get('photographer', {})
            attribution = f"Photo by {photographer.get('name', 'Unknown')} from Pexels"
            
            wagtail_image = Image(
                title=title,
                file=image_file
            )
            wagtail_image.save()
            
            # Store additional metadata in tags (if using taggit)
            try:
                tags = [
                    'pexels',
                    'botanical',
                    f"photographer:{photographer.get('name', 'unknown').replace(' ', '_')}",
                    f"pexels_id:{image_data['id']}"
                ]
                wagtail_image.tags.add(*tags)
            except Exception as e:
                logger.warning(f"Could not add tags to image: {e}")
            
            logger.info(f"Created Wagtail image from Pexels: {title}")
            return wagtail_image
            
        except Exception as e:
            logger.error(f"Failed to download/create Wagtail image from Pexels: {e}")
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
            limit=8,  # Get top 8 to choose from
            orientation='landscape'  # Better for spotlight blocks
        )
        
        if not images:
            logger.info(f"No Pexels images found for: {plant_name}")
            return None
        
        # Sort by relevance factors (size, etc.)
        sorted_images = sorted(images, key=lambda x: (
            x.get('width', 0) * x.get('height', 0),  # Image size
            1 if x.get('description') and plant_name.lower() in x.get('description', '').lower() else 0,
            len(x.get('description', ''))  # Description quality
        ), reverse=True)
        
        # Try to download the best image
        for image_data in sorted_images:
            wagtail_image = self.download_and_create_wagtail_image(
                image_data, 
                title_prefix=f"{plant_name} Plant"
            )
            if wagtail_image:
                return image_data, wagtail_image
        
        logger.warning(f"Failed to download any Pexels images for: {plant_name}")
        return None