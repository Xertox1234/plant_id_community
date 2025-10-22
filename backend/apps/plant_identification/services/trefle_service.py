"""
Trefle API integration service for plant identification.

Trefle API provides comprehensive plant species data.
Documentation: https://docs.trefle.io/
"""

import requests
import logging
import time
from typing import Dict, List, Optional, Union
from django.conf import settings
from django.core.cache import cache
from functools import wraps
from ..exceptions import RateLimitExceeded, APIUnavailable

logger = logging.getLogger(__name__)


def rate_limit(max_calls_per_hour=120):
    """
    Rate limiting decorator for Trefle API calls (120 requests/hour limit).
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            cache_key = f"trefle_rate_limit_{self.__class__.__name__}"
            current_calls = cache.get(cache_key, [])
            now = time.time()
            
            # Remove calls older than 1 hour
            current_calls = [call_time for call_time in current_calls if now - call_time < 3600]
            
            if len(current_calls) >= max_calls_per_hour:
                # Set a flag in cache to prevent further attempts
                cache.set("trefle_rate_limited", True, 300)  # Flag for 5 minutes
                remaining_time = 3600 - (now - current_calls[0])  # Time until oldest call expires
                logger.warning(f"Trefle API rate limit exceeded ({len(current_calls)}/{max_calls_per_hour}). "
                             f"Oldest call expires in {remaining_time:.0f} seconds")
                raise RateLimitExceeded(
                    f"Trefle API rate limit exceeded ({len(current_calls)}/{max_calls_per_hour} calls/hour)",
                    api_name="Trefle",
                    retry_after=max(60, int(remaining_time))
                )
            
            # Record this call
            current_calls.append(now)
            cache.set(cache_key, current_calls, 3600)  # Cache for 1 hour
            
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


def retry_on_failure(max_retries=3, backoff_factor=1):
    """
    Retry decorator with exponential backoff for API failures.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    if attempt < max_retries - 1:  # Don't sleep on last attempt
                        sleep_time = backoff_factor * (2 ** attempt)
                        logger.warning(f"API call failed (attempt {attempt + 1}/{max_retries}), retrying in {sleep_time}s: {e}")
                        time.sleep(sleep_time)
                    else:
                        logger.error(f"API call failed after {max_retries} attempts: {e}")
            
            # If all retries failed, return None or raise the last exception
            if last_exception:
                logger.error(f"Final failure after {max_retries} retries: {last_exception}")
            return None
        return wrapper
    return decorator


class TrefleAPIService:
    """
    Service for interacting with the Trefle API.
    Provides plant species data and identification capabilities.
    """
    
    BASE_URL = "https://trefle.io/api/v1"
    CACHE_TIMEOUT = 86400  # 24 hours for better efficiency
    REQUEST_TIMEOUT = 10  # Optimized timeout
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Trefle API service.
        
        Args:
            api_key: Trefle API key. If not provided, will use settings.TREFLE_API_KEY
        """
        self.api_key = api_key or getattr(settings, 'TREFLE_API_KEY', None)
        if not self.api_key:
            logger.error("Trefle API key not configured")
            raise ValueError("TREFLE_API_KEY must be set in Django settings")
        
        self.session = requests.Session()
        self.session.params.update({'token': self.api_key})
        
        # Initialize monitoring (lazy import to avoid circular dependencies)
        self.monitor = None
        self._monitor_initialized = False
    
    def _get_monitor(self):
        """Lazy initialization of monitoring service to avoid circular imports."""
        if not self._monitor_initialized:
            try:
                from .monitoring_service import APIMonitoringService
                self.monitor = APIMonitoringService()
            except ImportError:
                self.monitor = None
                logger.warning("Monitoring service not available")
            except Exception as e:
                self.monitor = None
                logger.warning(f"Failed to initialize monitoring: {e}")
            self._monitor_initialized = True
        return self.monitor
    
    @retry_on_failure(max_retries=3, backoff_factor=1)
    @rate_limit(max_calls_per_hour=120)
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make a request to the Trefle API with enhanced error handling, rate limiting, and retries.
        
        Args:
            endpoint: API endpoint (without base URL)
            params: Additional query parameters
            
        Returns:
            JSON response data or None if error
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.get(url, params=params or {}, timeout=self.REQUEST_TIMEOUT)
            
            # Handle specific HTTP status codes
            if response.status_code == 401:
                logger.error("Trefle API authentication failed - check API key")
                monitor = self._get_monitor()
                if monitor:
                    monitor.record_api_call('trefle', endpoint, success=False)
                raise requests.exceptions.HTTPError("Authentication failed", response=response)
            elif response.status_code == 429:
                logger.warning("Trefle API rate limit exceeded by server")
                monitor = self._get_monitor()
                if monitor:
                    monitor.record_api_call('trefle', endpoint, success=False)
                raise requests.exceptions.HTTPError("Rate limit exceeded", response=response)
            elif response.status_code == 503:
                logger.warning("Trefle API service temporarily unavailable")
                monitor = self._get_monitor()
                if monitor:
                    monitor.record_api_call('trefle', endpoint, success=False)
                raise requests.exceptions.HTTPError("Service unavailable", response=response)
            
            response.raise_for_status()
            
            # Record successful API call
            monitor = self._get_monitor()
            if monitor:
                monitor.record_api_call('trefle', endpoint, success=True)
            
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.error(f"Trefle API request timed out after {self.REQUEST_TIMEOUT}s: {url}")
            monitor = self._get_monitor()
            if monitor:
                monitor.record_api_call('trefle', endpoint, success=False)
            raise
        except requests.exceptions.ConnectionError:
            logger.error(f"Trefle API connection error: {url}")
            monitor = self._get_monitor()
            if monitor:
                monitor.record_api_call('trefle', endpoint, success=False)
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Trefle API request failed: {url} - {str(e)}")
            monitor = self._get_monitor()
            if monitor:
                monitor.record_api_call('trefle', endpoint, success=False)
            raise
    
    def search_plants(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search for plants by name.
        
        Args:
            query: Search query (scientific or common name)
            limit: Maximum number of results
            
        Returns:
            List of plant data dictionaries
        """
        cache_key = f"trefle_search_{query.lower().replace(' ', '_')}_{limit}"
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for Trefle search: {query}")
            return cached_result
        
        params = {
            'q': query,
            'limit': limit
        }
        
        result = self._make_request('plants/search', params)
        if not result:
            return []
        
        plants = result.get('data', [])
        
        # Cache the results for better performance
        cache.set(cache_key, plants, self.CACHE_TIMEOUT)
        logger.debug(f"Cached Trefle search results for: {query}")
        
        return plants
    
    def get_plant_details(self, plant_id: Union[int, str]) -> Optional[Dict]:
        """
        Get detailed information about a specific plant.
        
        Args:
            plant_id: Trefle plant ID
            
        Returns:
            Plant details dictionary or None if not found
        """
        cache_key = f"trefle_plant_{plant_id}"
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for Trefle plant details: {plant_id}")
            return cached_result
        
        result = self._make_request(f'plants/{plant_id}')
        if not result:
            return None
        
        plant_data = result.get('data')
        if plant_data:
            cache.set(cache_key, plant_data, self.CACHE_TIMEOUT)
            logger.debug(f"Cached Trefle plant details for: {plant_id}")
        
        return plant_data
    
    def get_species_by_scientific_name(self, scientific_name: str) -> Optional[Dict]:
        """
        Get species information by scientific name.
        
        Args:
            scientific_name: Scientific binomial name (e.g., "Rosa damascena")
            
        Returns:
            Species data dictionary or None if not found
        """
        cache_key = f"trefle_species_{scientific_name.lower().replace(' ', '_')}"
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for Trefle species: {scientific_name}")
            return cached_result
        
        params = {
            'filter[scientific_name]': scientific_name,
            'limit': 1
        }
        
        result = self._make_request('species', params)
        if not result:
            return None
        
        species_list = result.get('data', [])
        if not species_list:
            return None
        
        species_data = species_list[0]
        cache.set(cache_key, species_data, self.CACHE_TIMEOUT)
        logger.debug(f"Cached Trefle species for: {scientific_name}")
        
        return species_data
    
    def get_species_details(self, species_id: Union[int, str]) -> Optional[Dict]:
        """
        Get detailed species information including care requirements.
        
        Args:
            species_id: Trefle species ID
            
        Returns:
            Detailed species data or None if not found
        """
        cache_key = f"trefle_species_details_{species_id}"
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for Trefle species details: {species_id}")
            return cached_result
        
        result = self._make_request(f'species/{species_id}')
        if not result:
            return None
        
        species_data = result.get('data')
        if species_data:
            cache.set(cache_key, species_data, self.CACHE_TIMEOUT)
            logger.debug(f"Cached Trefle species details for: {species_id}")
        
        return species_data
    
    def identify_by_characteristics(self, characteristics: Dict) -> List[Dict]:
        """
        Find plants based on physical characteristics.
        
        Args:
            characteristics: Dictionary of plant characteristics:
                - flower_color: Color of flowers
                - leaf_type: Type of leaves
                - growth_habit: How the plant grows
                - habitat: Where it typically grows
                
        Returns:
            List of matching plant species
        """
        params = {}
        
        # Map characteristics to Trefle API filters
        if 'flower_color' in characteristics:
            params['filter[flower_color]'] = characteristics['flower_color']
        
        if 'leaf_type' in characteristics:
            params['filter[leaf]'] = characteristics['leaf_type']
        
        if 'growth_habit' in characteristics:
            params['filter[growth_habit]'] = characteristics['growth_habit']
        
        if 'habitat' in characteristics:
            params['filter[atmospheric_humidity]'] = characteristics['habitat']
        
        params['limit'] = 50
        
        result = self._make_request('species', params)
        if not result:
            return []
        
        return result.get('data', [])
    
    def get_plant_images(self, plant_id: Union[int, str]) -> List[str]:
        """
        Get image URLs for a plant.
        
        Args:
            plant_id: Trefle plant ID
            
        Returns:
            List of image URLs
        """
        plant_data = self.get_plant_details(plant_id)
        if not plant_data:
            return []
        
        images = []
        
        # Main image
        main_image = plant_data.get('main_species', {}).get('image_url')
        if main_image:
            images.append(main_image)
        
        # Additional images from specifications
        specs = plant_data.get('main_species', {}).get('specifications', {})
        for spec_key, spec_value in specs.items():
            if isinstance(spec_value, dict) and 'image_url' in spec_value:
                if spec_value['image_url']:
                    images.append(spec_value['image_url'])
        
        return images
    
    def normalize_plant_data(self, trefle_data: Dict) -> Dict:
        """
        Normalize Trefle API data to our internal format.
        
        Args:
            trefle_data: Raw data from Trefle API
            
        Returns:
            Normalized plant data dictionary
        """
        main_species = trefle_data.get('main_species', {})
        specs = main_species.get('specifications', {})
        
        return {
            'trefle_id': str(trefle_data.get('id', '')),
            'scientific_name': trefle_data.get('scientific_name', ''),
            'common_names': ', '.join(trefle_data.get('common_names', {}).get('en', [])),
            'family': main_species.get('family', ''),
            'genus': main_species.get('genus', ''),
            'plant_type': specs.get('growth_form', {}).get('type', ''),
            'mature_height_min': specs.get('mature_height', {}).get('cm', {}).get('min'),
            'mature_height_max': specs.get('mature_height', {}).get('cm', {}).get('max'),
            'light_requirements': self._map_light_requirements(specs.get('light', {}).get('type')),
            'water_requirements': self._map_water_requirements(specs.get('atmospheric_humidity', {}).get('type')),
            'soil_ph_min': specs.get('soil_ph', {}).get('min'),
            'soil_ph_max': specs.get('soil_ph', {}).get('max'),
            'hardiness_zone_min': specs.get('minimum_temperature', {}).get('deg_f', {}).get('min'),
            'hardiness_zone_max': specs.get('maximum_temperature', {}).get('deg_f', {}).get('max'),
            'bloom_time': specs.get('bloom_months', {}).get('type', ''),
            'flower_color': specs.get('flower_color', {}).get('type', ''),
            'native_regions': ', '.join(main_species.get('distribution', {}).get('native', [])),
            'primary_image_url': main_species.get('image_url'),
        }
    
    def _map_light_requirements(self, trefle_light: Optional[str]) -> str:
        """Map Trefle light values to our choices."""
        if not trefle_light:
            return ''
        
        light_mapping = {
            'full_sun': 'full_sun',
            'part_sun': 'partial_sun', 
            'part_shade': 'partial_shade',
            'full_shade': 'full_shade',
            'sun': 'full_sun',
            'shade': 'full_shade',
        }
        
        return light_mapping.get(trefle_light.lower(), '')
    
    def _map_water_requirements(self, trefle_humidity: Optional[str]) -> str:
        """Map Trefle humidity values to our water requirement choices."""
        if not trefle_humidity:
            return ''
        
        water_mapping = {
            'low': 'low',
            'moderate': 'moderate', 
            'high': 'high',
            'dry': 'low',
            'moist': 'moderate',
            'wet': 'high',
        }
        
        return water_mapping.get(trefle_humidity.lower(), '')
    
    def get_service_status(self) -> Dict:
        """
        Check if the Trefle API service is available.
        
        Returns:
            Service status dictionary
        """
        try:
            result = self._make_request('plants', {'limit': 1})
            return {
                'status': 'available' if result else 'unavailable',
                'api_key_valid': result is not None,
                'last_check': 'now'
            }
        except Exception as e:
            return {
                'status': 'error',
                'api_key_valid': False,
                'error': str(e),
                'last_check': 'now'
            }