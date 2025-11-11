"""
Blog service for intelligent plant data lookup with prioritized data sources.

This service searches multiple data sources in priority order:
1. Local PlantSpecies database (exact and fuzzy matching)
2. User's previous plant identification results
3. External APIs (Trefle, PlantNet)
4. AI content generation (via Wagtail AI)
"""

import logging
from typing import Dict, Optional, List, Union
from django.db.models import Q
from django.conf import settings
from fuzzywuzzy import fuzz
from apps.plant_identification.models import PlantSpecies
from apps.plant_identification.services.trefle_service import TrefleAPIService
from apps.plant_identification.services.plantnet_service import PlantNetAPIService

logger = logging.getLogger(__name__)


class PlantDataLookupService:
    """
    Service for intelligent plant data lookup with prioritized data sources.

    Lookup priority:
    1. Local PlantSpecies database (exact and fuzzy matching)
    2. User's previous plant identification results
    3. External APIs (Trefle, PlantNet)
    4. AI content generation (via Wagtail AI)
    """

    def __init__(self):
        try:
            self.trefle_service = TrefleAPIService()
        except Exception as e:
            logger.warning(f"Could not initialize TrefleAPIService: {e}")
            self.trefle_service = None

        try:
            self.plantnet_service = PlantNetAPIService()
        except Exception as e:
            logger.warning(f"Could not initialize PlantNetAPIService: {e}")
            self.plantnet_service = None

        self.fuzzy_match_threshold = 85  # Minimum score for fuzzy matching

    def lookup_plant_data(self, query: str, user=None) -> Dict:
        """
        Main lookup method that searches all data sources for plant information.

        Args:
            query: Scientific name, common name, or partial plant name
            user: User object for personalized results (optional)

        Returns:
            Dict containing plant data with source information
        """
        result = {
            'found': False,
            'source': None,
            'confidence': 0.0,
            'data': {}
        }

        # Step 1: Local database exact match
        local_result = self._search_local_database(query)
        if local_result['found']:
            logger.info(f"Found exact match in local database for: {query}")
            return local_result

        # Step 2: Local database fuzzy match
        fuzzy_result = self._fuzzy_search_local_database(query)
        if fuzzy_result['found']:
            logger.info(f"Found fuzzy match in local database for: {query}")
            return fuzzy_result

        # Step 3: User's previous identifications
        if user:
            user_result = self._search_user_history(query, user)
            if user_result['found']:
                logger.info(f"Found in user's previous identifications: {query}")
                return user_result

        # Step 4: External API search
        api_result = self._search_external_apis(query)
        if api_result['found']:
            logger.info(f"Found via external API for: {query}")
            return api_result

        logger.warning(f"No plant data found for query: {query}")
        return result

    def _search_local_database(self, query: str) -> Dict:
        """Search local PlantSpecies database for exact matches."""
        try:
            # Try scientific name exact match
            species = PlantSpecies.objects.filter(
                Q(scientific_name__iexact=query)
            ).first()

            if not species:
                # Try common names exact match
                species = PlantSpecies.objects.filter(
                    Q(common_names__icontains=query)
                ).first()

            if species:
                return {
                    'found': True,
                    'source': 'local_database',
                    'confidence': 1.0,
                    'data': self._format_species_data(species)
                }

        except Exception as e:
            logger.error(f"Error searching local database: {e}")

        return {'found': False, 'source': None, 'confidence': 0.0, 'data': {}}

    def _fuzzy_search_local_database(self, query: str) -> Dict:
        """Search local database using fuzzy string matching."""
        try:
            best_match = None
            best_score = 0

            # Get all species for fuzzy matching
            all_species = PlantSpecies.objects.all()

            for species in all_species:
                # Check scientific name
                score = fuzz.ratio(query.lower(), species.scientific_name.lower())
                if score > best_score and score >= self.fuzzy_match_threshold:
                    best_score = score
                    best_match = species

                # Check common names
                if species.common_names:
                    for common_name in species.common_names_list:
                        score = fuzz.ratio(query.lower(), common_name.lower())
                        if score > best_score and score >= self.fuzzy_match_threshold:
                            best_score = score
                            best_match = species

            if best_match:
                return {
                    'found': True,
                    'source': 'local_database_fuzzy',
                    'confidence': best_score / 100.0,
                    'data': self._format_species_data(best_match)
                }

        except Exception as e:
            logger.error(f"Error in fuzzy search: {e}")

        return {'found': False, 'source': None, 'confidence': 0.0, 'data': {}}

    def _search_user_history(self, query: str, user) -> Dict:
        """Search user's previous plant identification results."""
        try:
            from apps.plant_identification.models import PlantIdentificationRequest, PlantIdentificationResult

            # Search in user's accepted identifications
            user_requests = PlantIdentificationRequest.objects.filter(
                user=user,
                status='identified'
            ).prefetch_related('identification_results')

            for request in user_requests:
                for result in request.identification_results.filter(is_accepted=True):
                    if result.identified_species:
                        species = result.identified_species
                        # Check if this matches our query
                        if (query.lower() in species.scientific_name.lower() or
                            any(query.lower() in name.lower() for name in species.common_names_list)):

                            return {
                                'found': True,
                                'source': 'user_history',
                                'confidence': result.confidence_score,
                                'data': self._format_species_data(species, user_context=True)
                            }

        except Exception as e:
            logger.error(f"Error searching user history: {e}")

        return {'found': False, 'source': None, 'confidence': 0.0, 'data': {}}

    def _search_external_apis(self, query: str) -> Dict:
        """Search external APIs for plant data."""
        try:
            # Try Trefle API first (more detailed care information)
            if self.trefle_service:
                trefle_data = self.trefle_service.search_species(query)
                if trefle_data:
                    return {
                        'found': True,
                        'source': 'trefle_api',
                        'confidence': 0.8,
                        'data': self._format_trefle_data(trefle_data)
                    }
            else:
                logger.info("Trefle service not available, skipping external API search")

            # Fallback to PlantNet if available
            # Note: PlantNet requires images, so this would be limited

        except Exception as e:
            logger.error(f"Error searching external APIs: {e}")

        return {'found': False, 'source': None, 'confidence': 0.0, 'data': {}}

    def _format_species_data(self, species: PlantSpecies, user_context=False) -> Dict:
        """Format PlantSpecies model data for block auto-population."""
        data = {
            'scientific_name': species.scientific_name,
            'common_names': species.common_names_list,
            'plant_name': species.display_name,
            'family': species.family,
            'genus': species.genus,
            'description': species.description,
            'plant_type': species.plant_type,
            'growth_habit': species.growth_habit,

            # Care instructions data
            'light_requirements': species.light_requirements,
            'water_requirements': species.water_requirements,
            'soil_ph_range': f"{species.soil_ph_min}-{species.soil_ph_max}" if species.soil_ph_min and species.soil_ph_max else None,
            'hardiness_zones': f"{species.hardiness_zone_min}-{species.hardiness_zone_max}" if species.hardiness_zone_min and species.hardiness_zone_max else None,

            # Additional details
            'bloom_time': species.bloom_time,
            'flower_color': species.flower_color,
            'native_regions': species.native_regions,
            'height_range': f"{species.mature_height_min}m-{species.mature_height_max}m" if species.mature_height_min and species.mature_height_max else None,

            # Metadata
            'primary_image_url': species.primary_image.url if species.primary_image else None,
            'is_verified': species.is_verified,
            'user_context': user_context
        }

        # Determine care difficulty
        data['care_difficulty'] = self._calculate_care_difficulty(species)

        return data

    def _format_trefle_data(self, trefle_data: Dict) -> Dict:
        """Format Trefle API data for block auto-population."""
        return {
            'scientific_name': trefle_data.get('scientific_name', ''),
            'common_names': trefle_data.get('common_names', []),
            'plant_name': trefle_data.get('common_name', trefle_data.get('scientific_name', '')),
            'family': trefle_data.get('family', ''),
            'genus': trefle_data.get('genus', ''),
            'description': trefle_data.get('description', ''),
            'native_regions': ', '.join(trefle_data.get('native', [])) if trefle_data.get('native') else '',

            # API-specific data
            'trefle_id': trefle_data.get('id'),
            'api_source': 'trefle'
        }

    def _calculate_care_difficulty(self, species: PlantSpecies) -> str:
        """Calculate care difficulty based on species requirements."""
        difficulty_score = 0

        # Water requirements factor
        if species.water_requirements == 'high':
            difficulty_score += 2
        elif species.water_requirements == 'moderate':
            difficulty_score += 1

        # Light requirements factor
        if species.light_requirements in ['full_sun', 'full_shade']:
            difficulty_score += 1

        # pH sensitivity factor
        if species.soil_ph_min and species.soil_ph_max:
            ph_range = species.soil_ph_max - species.soil_ph_min
            if ph_range < 2.0:  # Narrow pH range = more difficult
                difficulty_score += 1

        # Hardiness zone factor
        if species.hardiness_zone_min and species.hardiness_zone_max:
            zone_range = species.hardiness_zone_max - species.hardiness_zone_min
            if zone_range < 3:  # Narrow zone range = more difficult
                difficulty_score += 1

        # Determine final difficulty
        if difficulty_score <= 1:
            return 'easy'
        elif difficulty_score <= 3:
            return 'moderate'
        else:
            return 'difficult'

    def generate_care_instructions(self, plant_data: Dict) -> Dict:
        """Generate detailed care instructions from plant data."""
        instructions = {}

        # Generate watering instructions
        water_req = plant_data.get('water_requirements')
        if water_req == 'high':
            instructions['watering'] = "Keep soil consistently moist but not waterlogged. Water when top inch of soil feels dry."
        elif water_req == 'moderate':
            instructions['watering'] = "Allow soil to dry out slightly between waterings. Water deeply when needed."
        elif water_req == 'low':
            instructions['watering'] = "Allow soil to dry out completely between waterings. Water sparingly."
        else:
            instructions['watering'] = "Water when soil feels dry to touch."

        # Generate lighting instructions
        light_req = plant_data.get('light_requirements')
        if light_req == 'full_sun':
            instructions['lighting'] = "Needs direct sunlight for 6+ hours daily. Place in south-facing window or outdoors."
        elif light_req == 'partial_sun':
            instructions['lighting'] = "Needs 3-6 hours of direct sunlight daily. East or west-facing windows work well."
        elif light_req == 'partial_shade':
            instructions['lighting'] = "Prefers bright, indirect light. North-facing windows or filtered light."
        elif light_req == 'full_shade':
            instructions['lighting'] = "Thrives in low light conditions. Keep away from direct sunlight."
        else:
            instructions['lighting'] = "Provide bright, indirect light for optimal growth."

        # Generate temperature instructions
        hardiness = plant_data.get('hardiness_zones')
        if hardiness:
            instructions['temperature'] = f"Hardy in USDA zones {hardiness}. Protect from extreme temperature fluctuations."
        else:
            instructions['temperature'] = "Maintain consistent room temperature between 65-75°F (18-24°C)."

        # Generate humidity instructions
        if plant_data.get('plant_type') in ['tropical', 'fern']:
            instructions['humidity'] = "Prefers high humidity (50-60%). Use humidity tray or regular misting."
        else:
            instructions['humidity'] = "Average household humidity is suitable. Monitor for dry air in winter."

        # Generate fertilizing instructions
        if plant_data.get('plant_type') == 'succulent':
            instructions['fertilizing'] = "Fertilize sparingly with diluted succulent fertilizer during growing season."
        else:
            instructions['fertilizing'] = "Feed monthly during growing season with balanced liquid fertilizer."

        # Generate special notes based on characteristics
        special_notes = []
        if plant_data.get('growth_habit') == 'climbing':
            special_notes.append("Provide support structure for climbing growth.")
        if plant_data.get('bloom_time'):
            special_notes.append(f"Blooms {plant_data['bloom_time']}.")
        if plant_data.get('is_verified'):
            special_notes.append("Care information verified by botanical experts.")

        instructions['special_notes'] = " ".join(special_notes) if special_notes else "Monitor plant regularly and adjust care as needed."

        return instructions
