"""
Plant.id (Kindwise) API integration service.

Plant.id provides AI-powered plant identification with disease detection.
Documentation: https://plant.id/docs
"""

import requests
import logging
import base64
import hashlib
from typing import Dict, List, Optional
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class PlantIDAPIService:
    """
    Service for interacting with the Plant.id (Kindwise) API.
    Provides AI-powered plant identification with disease detection.
    """

    BASE_URL = "https://plant.id/api/v3"
    API_VERSION = "v3"  # Include in cache key for version-specific caching
    CACHE_TIMEOUT = 1800  # 30 minutes
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Plant.id API service.
        
        Args:
            api_key: Plant.id API key. If not provided, will use settings.PLANT_ID_API_KEY
        """
        self.api_key = api_key or getattr(settings, 'PLANT_ID_API_KEY', None)
        if not self.api_key:
            logger.error("Plant.id API key not configured")
            raise ValueError("PLANT_ID_API_KEY must be set in Django settings")
        
        self.session = requests.Session()
        self.timeout = getattr(settings, 'PLANT_ID_API_TIMEOUT', 30)
    
    def identify_plant(self, image_file, include_diseases: bool = True) -> Dict:
        """
        Identify a plant from an image using Plant.id API with Redis caching.

        Args:
            image_file: Django file object or file bytes
            include_diseases: Whether to include disease detection

        Returns:
            Dictionary containing identification results
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

            # Check cache first
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info(f"[CACHE] HIT for image {image_hash[:8]}... (instant response)")
                return cached_result

            # Cache miss - call API
            logger.info(f"[CACHE] MISS for image {image_hash[:8]}... (calling Plant.id API)")

            encoded_image = base64.b64encode(image_data).decode('utf-8')

            # Prepare request payload
            headers = {
                'Api-Key': self.api_key,
                'Content-Type': 'application/json',
            }

            data = {
                'images': [encoded_image],
                'modifiers': ['crops', 'similar_images'],
                'plant_language': 'en',
                'plant_details': [
                    'common_names',
                    'taxonomy',
                    'url',
                    'description',
                    'synonyms',
                    'image',
                    'edible_parts',
                    'watering',
                    'propagation_methods',
                ],
            }

            # Add disease detection if requested
            if include_diseases:
                data['disease_details'] = [
                    'common_names',
                    'description',
                    'treatment',
                    'classification',
                    'url',
                ]

            # Make API request
            response = self.session.post(
                f"{self.BASE_URL}/identification",
                json=data,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()

            result = response.json()
            formatted_result = self._format_response(result)

            logger.info(f"Plant.id identification successful: {result.get('suggestions', [{}])[0].get('plant_name', 'Unknown')}")

            # Store in cache (24 hours)
            cache.set(cache_key, formatted_result, timeout=86400)
            logger.info(f"[CACHE] Stored result for image {image_hash[:8]}... (24h TTL)")

            return formatted_result

        except requests.exceptions.Timeout:
            logger.error("Plant.id API request timed out")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Plant.id API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Plant.id identification: {e}")
            raise
    
    def _format_response(self, raw_response: Dict) -> Dict:
        """
        Format Plant.id API response into a standardized structure.
        
        Args:
            raw_response: Raw API response
            
        Returns:
            Formatted response dictionary
        """
        suggestions = raw_response.get('suggestions', [])
        health_assessment = raw_response.get('health_assessment', {})
        
        formatted_suggestions = []
        for suggestion in suggestions[:5]:  # Top 5 results
            plant_details = suggestion.get('plant_details', {})
            
            formatted_suggestions.append({
                'plant_name': suggestion.get('plant_name'),
                'scientific_name': plant_details.get('scientific_name'),
                'probability': suggestion.get('probability', 0),
                'common_names': plant_details.get('common_names', []),
                'description': plant_details.get('description', {}).get('value'),
                'taxonomy': plant_details.get('taxonomy', {}),
                'edible_parts': plant_details.get('edible_parts'),
                'watering': plant_details.get('watering', {}).get('max', 'Unknown'),
                'propagation_methods': plant_details.get('propagation_methods'),
                'similar_images': suggestion.get('similar_images', []),
                'url': plant_details.get('url'),
                'source': 'plant_id',
            })
        
        # Format disease/health assessment
        disease_info = None
        if health_assessment and health_assessment.get('diseases'):
            diseases = health_assessment.get('diseases', [])
            if diseases:
                top_disease = diseases[0]
                disease_info = {
                    'is_healthy': health_assessment.get('is_healthy', True),
                    'is_plant': health_assessment.get('is_plant', True),
                    'disease_name': top_disease.get('name'),
                    'probability': top_disease.get('probability'),
                    'description': top_disease.get('disease_details', {}).get('description'),
                    'treatment': top_disease.get('disease_details', {}).get('treatment'),
                    'classification': top_disease.get('disease_details', {}).get('classification'),
                }
        
        return {
            'suggestions': formatted_suggestions,
            'health_assessment': disease_info,
            'top_suggestion': formatted_suggestions[0] if formatted_suggestions else None,
            'confidence': formatted_suggestions[0]['probability'] if formatted_suggestions else 0,
        }
    
    def get_plant_details(self, plant_name: str) -> Optional[Dict]:
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
