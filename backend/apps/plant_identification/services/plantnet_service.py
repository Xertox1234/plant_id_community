"""
PlantNet API integration service for plant identification.

PlantNet API provides AI-powered plant identification from images.
Documentation: https://my.plantnet.org/
"""

import hashlib
import requests
import logging
from typing import Dict, List, Optional, Union
from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
import base64
import io
from PIL import Image

from ..constants import (
    PLANTNET_CACHE_TIMEOUT,
    PLANTNET_API_REQUEST_TIMEOUT,
    IMAGE_DOWNLOAD_TIMEOUT,
    IMAGE_DOWNLOAD_QUICK_TIMEOUT,
)

logger = logging.getLogger(__name__)


class PlantNetAPIService:
    """
    Service for interacting with the PlantNet API.
    Provides AI-powered plant identification from images.
    """

    BASE_URL = "https://my-api.plantnet.org/v2"
    API_VERSION = "v2"  # Include in cache key for version-specific caching
    CACHE_TIMEOUT = PLANTNET_CACHE_TIMEOUT
    
    # PlantNet project types - using actual project IDs from API
    # These are the valid project IDs returned by the /v2/projects endpoint
    PROJECTS = {
        'world': 'k-world-flora',        # World flora - 74043 species
        'useful': 'useful',              # Useful plants - 5457 species
        'weeds': 'weeds',                # Agricultural weeds - 1429 species
        'invasion': 'invasion',          # Invasive plants - 1088 species
        'europe': 'k-middle-europe',     # Middle Europe - 5111 species
        'north_america': 'k-northeastern-u-s-a',  # Northeastern USA - 3931 species
        'south_america': 'k-northern-south-america',  # Northern South America - 7376 species
        'africa': 'k-northern-africa',   # Northern Africa - 4392 species
        'asia': 'k-eastern-asia',        # Eastern Asia - 4630 species
        'oceania': 'k-australia',        # Australia - 4886 species
        'canada': 'k-eastern-canada',    # Eastern Canada - 2653 species
        'trees': 'eu-trees',             # European trees - 599 species
        'crops': 'eu-crops',             # Cultivated crops - 219 species
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the PlantNet API service.
        
        Args:
            api_key: PlantNet API key. If not provided, will use settings.PLANTNET_API_KEY
        """
        self.api_key = api_key or getattr(settings, 'PLANTNET_API_KEY', None)
        if not self.api_key:
            logger.error("PlantNet API key not configured")
            raise ValueError("PLANTNET_API_KEY must be set in Django settings")
        
        self.session = requests.Session()
    
    def _prepare_image(self, image_file, max_size: int = 1024) -> bytes:
        """
        Prepare image for PlantNet API by resizing and converting to JPEG.
        
        Args:
            image_file: Django file object or file path
            max_size: Maximum dimension for the image
            
        Returns:
            Processed image bytes
        """
        try:
            # Open image
            if hasattr(image_file, 'read'):
                image = Image.open(image_file)
            else:
                image = Image.open(image_file)
            
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGB')
            
            # Resize if too large
            if max(image.size) > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Save as JPEG bytes
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=85, optimize=True)
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error preparing image for PlantNet: {str(e)}")
            raise
    
    def identify_plant(self, 
                      images: List[Union[str, ContentFile]], 
                      project: str = 'world',
                      organs: Optional[List[str]] = None,
                      modifiers: Optional[List[str]] = None,
                      include_related_images: bool = False) -> Optional[Dict[str, Any]]:
        """
        Identify a plant from images using PlantNet API.
        
        Args:
            images: List of image files or paths (max 5 images)
            project: PlantNet project to use for identification
            organs: List of plant organs in images (leaf, flower, fruit, bark, habit, other)
            modifiers: List of modifiers (entire, partial, scan)
            include_related_images: Include related images in response
            
        Returns:
            Identification results dictionary or None if error
        """
        if not images:
            logger.error("No images provided for plant identification")
            return None
        
        if len(images) > 5:
            logger.warning("PlantNet API supports max 5 images, using first 5")
            images = images[:5]
        
        # Default organs if not specified - use valid organ types
        if organs is None:
            organs = ['leaf'] * len(images)  # Default to 'leaf' as it's most common
        elif len(organs) < len(images):
            # Pad with 'leaf' if not enough organs specified
            organs.extend(['leaf'] * (len(images) - len(organs)))
        
        # Prepare request
        project_key = self.PROJECTS.get(project, self.PROJECTS['world'])
        url = f"{self.BASE_URL}/identify/{project_key}"

        # Only API key goes in query params
        params = {'api-key': self.api_key}

        try:
            # Prepare multipart form data according to PlantNet API v2 specification
            files = []
            image_bytes_list = []  # Store for cache key generation

            # Add images - all use the same 'images' field name
            for i, image in enumerate(images):
                if hasattr(image, 'read'):
                    image_bytes = self._prepare_image(image)
                    filename = f"image_{i}.jpg"
                else:
                    with open(image, 'rb') as f:
                        image_bytes = self._prepare_image(f)
                    filename = f"image_{i}.jpg"

                files.append(('images', (filename, image_bytes, 'image/jpeg')))
                image_bytes_list.append(image_bytes)

            # Generate cache key from image data and parameters
            # Combine all image bytes for consistent hashing
            combined_image_data = b''.join(image_bytes_list)
            image_hash = hashlib.sha256(combined_image_data).hexdigest()
            organs_str = ':'.join(sorted(organs) if organs else ['none'])
            modifiers_str = ':'.join(sorted(modifiers) if modifiers else ['none'])
            cache_key = f"plantnet:{self.API_VERSION}:{project}:{image_hash}:{organs_str}:{modifiers_str}:{include_related_images}"

            # Check cache first
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info(f"[CACHE] HIT for PlantNet image {image_hash[:8]}... (instant response)")
                return cached_result

            logger.info(f"[CACHE] MISS for PlantNet image {image_hash[:8]}... - calling API")
            
            # Prepare multipart form data exactly like the working TypeScript implementation
            # Each organ is added separately, not as an array
            data = []
            
            # Add organ for each image
            for organ in organs:
                data.append(('organs', organ))
            
            # Add optional parameters only if needed
            if include_related_images:
                data.append(('include-related-images', 'true'))
            
            if modifiers:
                for modifier in modifiers:
                    data.append(('modifiers', modifier))
            
            # Make request using requests.post with files and data tuples
            response = self.session.post(url, params=params, files=files, data=data, timeout=PLANTNET_API_REQUEST_TIMEOUT)
            response.raise_for_status()

            result = response.json()

            # Cache the result for 24 hours (match Plant.id caching strategy)
            cache.set(cache_key, result, timeout=self.CACHE_TIMEOUT)
            logger.info(f"[CACHE] Stored PlantNet result for image {image_hash[:8]}... (TTL: {self.CACHE_TIMEOUT}s)")

            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"PlantNet API request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text[:500]}")
            return None
        except Exception as e:
            logger.error(f"Error preparing PlantNet request: {str(e)}")
            return None
    
    def get_top_suggestions(self, identification_result: Dict[str, Any], min_score: float = 0.1) -> List[Dict[str, Any]]:
        """
        Extract top plant suggestions from PlantNet identification result.
        
        Args:
            identification_result: Result from identify_plant method
            min_score: Minimum confidence score to include
            
        Returns:
            List of plant suggestions with scores
        """
        if not identification_result or 'results' not in identification_result:
            return []
        
        suggestions = []
        for result in identification_result['results']:
            score = result.get('score', 0)
            if score >= min_score:
                species = result.get('species', {})
                # Handle common names - they can be either strings or objects
                common_names = []
                for name in species.get('commonNames', []):
                    if isinstance(name, str):
                        common_names.append(name)
                    elif isinstance(name, dict):
                        common_names.append(name.get('value', ''))
                
                suggestions.append({
                    'scientific_name': species.get('scientificNameWithoutAuthor', ''),
                    'scientific_name_full': species.get('scientificName', ''),  # Full name with authorship
                    'common_names': common_names,
                    'family': species.get('family', {}).get('scientificNameWithoutAuthor', ''),
                    'genus': species.get('genus', {}).get('scientificNameWithoutAuthor', ''),
                    'confidence_score': score,
                    'plantnet_id': str(species.get('id', '')),
                    'images': self._extract_species_images(result.get('images', [])),
                    'gbif_id': result.get('gbif', {}).get('id', ''),  # GBIF ID is at result level
                    'powo_id': result.get('powo', {}).get('id', ''),   # POWO ID is at result level
                    'iucn_id': result.get('iucn', {}).get('id', ''),   # IUCN ID is at result level
                    'iucn_category': result.get('iucn', {}).get('category', ''),  # Conservation status
                })
        
        return sorted(suggestions, key=lambda x: x['confidence_score'], reverse=True)
    
    def _extract_species_images(self, image_list: List[Dict]) -> List[Dict]:
        """Extract and format species reference images."""
        images = []
        for img in image_list:
            if 'url' in img:
                images.append({
                    'url': img['url']['o'],  # Original size
                    'thumbnail': img['url'].get('s', img['url']['o']),  # Small size
                    'citation': img.get('citation', ''),
                    'author': img.get('author', ''),
                    'license': img.get('license', ''),
                })
        return images
    
    def normalize_plantnet_data(self, suggestion: Dict) -> Dict:
        """
        Normalize PlantNet suggestion data to our internal format.
        
        Args:
            suggestion: Suggestion from get_top_suggestions
            
        Returns:
            Normalized plant data dictionary
        """
        common_names_str = ', '.join(suggestion.get('common_names', [])) if suggestion.get('common_names') else ''
        
        return {
            'plantnet_id': suggestion.get('plantnet_id', ''),
            'scientific_name': suggestion.get('scientific_name', ''),
            'common_names': common_names_str,
            'family': suggestion.get('family', ''),
            'genus': suggestion.get('genus', ''),
            'confidence_score': suggestion.get('confidence_score', 0.0),
            'identification_source': 'ai_plantnet',
            'api_response_data': suggestion,
            'suggested_scientific_name': suggestion.get('scientific_name', ''),
            'suggested_common_name': common_names_str.split(',')[0].strip() if common_names_str else '',
        }
    
    def get_project_info(self, project: str = 'world') -> Optional[Dict]:
        """
        Get information about a PlantNet project from the projects list.
        
        Args:
            project: Project identifier
            
        Returns:
            Project information or None if error
        """
        # Get all projects and find the one we want
        all_projects = self.get_all_projects()
        if not all_projects:
            return None
            
        project_key = self.PROJECTS.get(project, self.PROJECTS['world'])
        
        # Find the project in the list
        for proj in all_projects:
            if proj.get('id') == project_key:
                return proj
                
        logger.warning(f"Project {project} (key: {project_key}) not found in available projects")
        return None
    
    def get_all_projects(self) -> Optional[List[Dict]]:
        """
        Get list of all available PlantNet projects.
        
        Returns:
            List of project dictionaries or None if error
        """
        url = f"{self.BASE_URL}/projects"
        params = {'api-key': self.api_key}
        
        try:
            response = self.session.get(url, params=params, timeout=IMAGE_DOWNLOAD_TIMEOUT)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"PlantNet projects request failed: {str(e)}")
            return None
    
    def get_available_projects(self) -> List[Dict]:
        """
        Get list of available PlantNet projects.
        
        Returns:
            List of project information dictionaries
        """
        projects = []
        for region, project_key in self.PROJECTS.items():
            project_info = self.get_project_info(region)
            if project_info:
                projects.append({
                    'region': region,
                    'key': project_key,
                    'name': project_info.get('name', region.title()),
                    'description': project_info.get('description', ''),
                    'species_count': project_info.get('nbSpecies', 0),
                    'image_count': project_info.get('nbImages', 0),
                })
        
        return projects
    
    def identify_with_location(self, 
                             images: List[Union[str, ContentFile]], 
                             latitude: Optional[float] = None,
                             longitude: Optional[float] = None,
                             organs: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Identify plant with location-based project selection.
        
        Args:
            images: List of image files
            latitude: GPS latitude
            longitude: GPS longitude
            organs: Plant organs in images
            
        Returns:
            Identification results with location context
        """
        # Determine best project based on location
        project = self._get_project_for_location(latitude, longitude)
        
        # Perform identification
        result = self.identify_plant(images, project=project, organs=organs)
        
        if result:
            result['location_context'] = {
                'latitude': latitude,
                'longitude': longitude,
                'project_used': project,
                'project_key': self.PROJECTS.get(project, self.PROJECTS['world'])
            }
        
        return result
    
    def _get_project_for_location(self, latitude: Optional[float], longitude: Optional[float]) -> str:
        """
        Determine the best PlantNet project based on geographic location.
        
        Args:
            latitude: GPS latitude
            longitude: GPS longitude
            
        Returns:
            Best project identifier
        """
        if latitude is None or longitude is None:
            return 'world'
        
        # Simple geographic mapping (can be enhanced with more precise boundaries)
        if 35 <= latitude <= 70 and -25 <= longitude <= 45:
            return 'europe'
        elif 25 <= latitude <= 70 and -170 <= longitude <= -50:
            return 'north_america'
        elif -55 <= latitude <= 15 and -85 <= longitude <= -35:
            return 'south_america'
        elif -35 <= latitude <= 40 and -20 <= longitude <= 55:
            return 'africa'
        elif -10 <= latitude <= 70 and 60 <= longitude <= 180:
            return 'asia'
        elif -50 <= latitude <= -10 and 110 <= longitude <= 180:
            return 'oceania'
        else:
            return 'world'
    
    def get_service_status(self) -> Dict:
        """
        Check if the PlantNet API service is available.
        
        Returns:
            Service status dictionary
        """
        try:
            # Try to get the projects list first (simpler endpoint)
            url = f"{self.BASE_URL}/projects"
            params = {'api-key': self.api_key}

            response = self.session.get(url, params=params, timeout=IMAGE_DOWNLOAD_QUICK_TIMEOUT)
            
            if response.status_code == 200:
                projects_data = response.json()
                return {
                    'status': 'available',
                    'api_key_valid': True,
                    'projects_available': len(projects_data.get('data', [])) if 'data' in projects_data else len(self.PROJECTS),
                    'last_check': 'now'
                }
            elif response.status_code == 401:
                return {
                    'status': 'unavailable',
                    'api_key_valid': False,
                    'error': 'Invalid API key',
                    'projects_available': len(self.PROJECTS),
                    'last_check': 'now'
                }
            else:
                return {
                    'status': 'unavailable',
                    'api_key_valid': False,
                    'error': f'HTTP {response.status_code}: {response.text[:100]}',
                    'projects_available': len(self.PROJECTS),
                    'last_check': 'now'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'api_key_valid': False,
                'error': str(e),
                'projects_available': len(self.PROJECTS),
                'last_check': 'now'
            }