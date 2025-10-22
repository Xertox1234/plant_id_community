"""
Species lookup service with intelligent local-first strategy.

This service prioritizes local database over external APIs to minimize
rate limiting issues while maintaining data quality.
"""

import logging
from typing import Dict, List, Optional, Tuple
from django.core.cache import cache
from django.db.models import Q
from django.conf import settings

from ..models import PlantSpecies, PlantIdentificationResult, PlantIdentificationRequest
from ..exceptions import RateLimitExceeded, APIUnavailable
from .trefle_service import TrefleAPIService

logger = logging.getLogger(__name__)


class SpeciesLookupService:
    """
    Local-first species lookup service with intelligent fallback to APIs.
    
    Lookup Strategy:
    1. Check local database for frequently identified species (>= 5 identifications)
    2. Check Redis cache for API results
    3. Call Trefle API only if necessary and rate limits allow
    4. Store successful API results for future use
    """
    
    # Confidence thresholds for different data sources
    CONFIDENCE_THRESHOLDS = {
        'local_frequent': 0.7,    # Local species with many identifications
        'local_verified': 0.8,    # Expert-verified local species
        'cached_api': 0.6,        # Cached API results
        'fresh_api': 0.7,         # Fresh API results
        'local_fallback': 0.4     # Local fallback when API unavailable
    }
    
    # Minimum identification count for trusting local species
    MIN_IDENTIFICATION_COUNT = 5
    
    def __init__(self):
        """Initialize the lookup service."""
        try:
            self.trefle = TrefleAPIService()
        except ValueError:
            logger.warning("Trefle API not available")
            self.trefle = None
        
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
    
    def get_species_by_scientific_name(self, scientific_name: str) -> Optional[Dict]:
        """
        Get species information by scientific name using local-first strategy.
        
        Args:
            scientific_name: Scientific binomial name (e.g., "Rosa damascena")
            
        Returns:
            Species data dictionary or None if not found
        """
        # Strategy 1: Check local database for frequently identified species
        local_species = self._get_local_species(scientific_name)
        if local_species:
            monitor = self._get_monitor()
            if monitor:
                monitor.record_local_db_hit()
            return self._format_local_species(local_species, 'local_frequent')
        
        # Strategy 2: Check Redis cache for API results
        cached_data = self._get_cached_species(scientific_name)
        if cached_data:
            monitor = self._get_monitor()
            if monitor:
                monitor.record_cache_hit('redis')
            logger.info(f"Found {scientific_name} in cache")
            return cached_data
        
        # Strategy 3: Call API if rate limits allow
        if self._can_call_api():
            api_data = self._fetch_from_api(scientific_name)
            if api_data:
                # Cache the result for future use
                self._cache_species_data(scientific_name, api_data)
                return api_data
            else:
                monitor = self._get_monitor()
                if monitor:
                    monitor.record_cache_miss('api')
        
        # Strategy 4: Fallback to any local species (even with low identification count)
        fallback_species = self._get_local_species_fallback(scientific_name)
        if fallback_species:
            monitor = self._get_monitor()
            if monitor:
                monitor.record_local_db_hit()
            logger.info(f"Using local fallback for {scientific_name}")
            return self._format_local_species(fallback_species, 'local_fallback')
        
        logger.warning(f"No data found for species: {scientific_name}")
        monitor = self._get_monitor()
        if monitor:
            monitor.record_cache_miss('total_miss')
        return None
    
    def search_species_by_common_name(self, common_name: str, limit: int = 10) -> List[Dict]:
        """
        Search for species by common name using local-first strategy.
        
        Args:
            common_name: Common name to search for
            limit: Maximum number of results
            
        Returns:
            List of species data dictionaries
        """
        results = []
        
        # First, search local database
        local_results = self._search_local_species(common_name, limit)
        results.extend(local_results)
        
        # If we have enough local results, return them
        if len(results) >= limit:
            return results[:limit]
        
        # Otherwise, supplement with API results if available
        if self._can_call_api() and self.trefle:
            try:
                remaining = limit - len(results)
                api_results = self._search_api_species(common_name, remaining)
                results.extend(api_results)
            except RateLimitExceeded:
                logger.warning(f"Rate limit exceeded during common name search: {common_name}")
        
        return results[:limit]
    
    def _get_local_species(self, scientific_name: str) -> Optional[PlantSpecies]:
        """Get species from local database if it has sufficient confidence."""
        try:
            return PlantSpecies.objects.get(
                scientific_name__iexact=scientific_name,
                identification_count__gte=self.MIN_IDENTIFICATION_COUNT
            )
        except PlantSpecies.DoesNotExist:
            return None
    
    def _get_local_species_fallback(self, scientific_name: str) -> Optional[PlantSpecies]:
        """Get any local species as fallback, regardless of identification count."""
        try:
            return PlantSpecies.objects.get(scientific_name__iexact=scientific_name)
        except PlantSpecies.DoesNotExist:
            return None
    
    def _search_local_species(self, query: str, limit: int = 10) -> List[Dict]:
        """Search local species database by common name or scientific name."""
        results = []
        
        try:
            species_matches = PlantSpecies.objects.filter(
                Q(common_names__icontains=query) |
                Q(scientific_name__icontains=query) |
                Q(genus__icontains=query)
            ).order_by('-identification_count', '-confidence_score')[:limit]
            
            for species in species_matches:
                confidence_type = 'local_verified' if species.expert_reviewed else 'local_frequent'
                species_data = self._format_local_species(species, confidence_type)
                results.append(species_data)
                
        except Exception as e:
            logger.error(f"Error searching local species: {e}")
        
        return results
    
    def _get_cached_species(self, scientific_name: str) -> Optional[Dict]:
        """Get species data from Redis cache."""
        cache_key = f"species:api:{scientific_name.lower().replace(' ', '_')}"
        return cache.get(cache_key)
    
    def _cache_species_data(self, scientific_name: str, data: Dict, timeout: int = 86400):
        """Cache species data in Redis."""
        cache_key = f"species:api:{scientific_name.lower().replace(' ', '_')}"
        cache.set(cache_key, data, timeout)
        logger.debug(f"Cached species data for: {scientific_name}")
    
    def _can_call_api(self) -> bool:
        """Check if we can make API calls (not rate limited)."""
        return not cache.get("trefle_rate_limited", False) and self.trefle is not None
    
    def _fetch_from_api(self, scientific_name: str) -> Optional[Dict]:
        """Fetch species data from Trefle API."""
        if not self.trefle:
            return None
        
        try:
            # First try to get species by scientific name
            species_data = self.trefle.get_species_by_scientific_name(scientific_name)
            if species_data:
                # Get detailed information
                detailed_data = self.trefle.get_species_details(species_data['id'])
                if detailed_data:
                    normalized_data = self.trefle.normalize_plant_data({'main_species': detailed_data})
                    normalized_data['confidence_score'] = self.CONFIDENCE_THRESHOLDS['fresh_api']
                    normalized_data['source'] = 'trefle_api'
                    return normalized_data
            
        except RateLimitExceeded:
            logger.warning(f"Rate limit exceeded for species lookup: {scientific_name}")
            raise
        except Exception as e:
            logger.error(f"API fetch failed for {scientific_name}: {e}")
        
        return None
    
    def _search_api_species(self, query: str, limit: int) -> List[Dict]:
        """Search for species using API."""
        results = []
        
        if not self.trefle:
            return results
        
        try:
            plants = self.trefle.search_plants(query, limit=limit)
            for plant_data in plants:
                normalized_data = self.trefle.normalize_plant_data(plant_data)
                normalized_data['confidence_score'] = self.CONFIDENCE_THRESHOLDS['cached_api']
                normalized_data['source'] = 'trefle_search'
                results.append(normalized_data)
                
        except RateLimitExceeded:
            logger.warning(f"Rate limit exceeded during API search: {query}")
            raise
        except Exception as e:
            logger.error(f"API search failed for {query}: {e}")
        
        return results
    
    def _format_local_species(self, species: PlantSpecies, confidence_type: str) -> Dict:
        """Format local species data to match API response format."""
        return {
            'trefle_id': species.trefle_id or '',
            'scientific_name': species.scientific_name,
            'common_names': species.common_names,
            'family': species.family,
            'genus': species.genus,
            'plant_type': species.plant_type,
            'light_requirements': species.light_requirements,
            'water_requirements': species.water_requirements,
            'confidence_score': self.CONFIDENCE_THRESHOLDS[confidence_type],
            'source': 'local_database',
            'identification_count': species.identification_count,
            'expert_reviewed': species.expert_reviewed,
            'community_confirmed': species.community_confirmed,
        }
    
    def get_popular_species(self, limit: int = 20) -> List[PlantSpecies]:
        """Get most frequently identified species for cache warming."""
        return PlantSpecies.objects.filter(
            identification_count__gt=0
        ).order_by('-identification_count', '-confidence_score')[:limit]
    
    def warm_cache_for_popular_species(self):
        """Pre-populate cache with data for popular species."""
        if not self._can_call_api():
            logger.info("Cannot warm cache - API rate limited")
            return
        
        popular_species = self.get_popular_species(50)  # Top 50 most identified
        warmed_count = 0
        
        for species in popular_species:
            # Only warm cache if we don't have API data cached
            if not self._get_cached_species(species.scientific_name):
                try:
                    api_data = self._fetch_from_api(species.scientific_name)
                    if api_data:
                        warmed_count += 1
                        logger.debug(f"Warmed cache for {species.scientific_name}")
                except RateLimitExceeded:
                    logger.info(f"Rate limit hit during cache warming after {warmed_count} species")
                    break
                except Exception as e:
                    logger.warning(f"Failed to warm cache for {species.scientific_name}: {e}")
        
        logger.info(f"Cache warming completed: {warmed_count} species cached")
    
    def get_lookup_stats(self) -> Dict:
        """Get statistics about lookup performance and cache usage."""
        stats = {
            'local_species_count': PlantSpecies.objects.count(),
            'verified_species_count': PlantSpecies.objects.filter(expert_reviewed=True).count(),
            'popular_species_count': PlantSpecies.objects.filter(
                identification_count__gte=self.MIN_IDENTIFICATION_COUNT
            ).count(),
            'api_available': self._can_call_api(),
            'rate_limited': cache.get("trefle_rate_limited", False)
        }
        
        return stats