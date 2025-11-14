"""
Companion Planting Service

Provides companion planting recommendations and compatibility checks for garden planning.

This service handles:
- Checking plant compatibility (beneficial, neutral, antagonistic)
- Recommending companion plants
- Identifying plants that should not be planted together
- Suggesting garden bed layouts based on companion planting principles
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from django.core.cache import cache

from ..models import Plant, GardenBed
from ..constants import CACHE_KEY_COMPANION_PLANTS, CACHE_TIMEOUT_ANALYTICS

logger = logging.getLogger(__name__)


class CompanionPlantingService:
    """
    Service for companion planting recommendations.

    Uses hardcoded companion planting data (Phase 1).
    Future: Could integrate with external API or database.
    """

    # Companion planting data
    # Format: {plant_name: {'companions': [...], 'antagonists': [...]}}
    COMPANION_DATA = {
        'tomato': {
            'companions': ['basil', 'carrot', 'onion', 'marigold', 'parsley', 'asparagus'],
            'antagonists': ['potato', 'fennel', 'cabbage', 'corn'],
            'benefits': {
                'basil': 'Repels flies and mosquitoes, improves flavor',
                'carrot': 'Helps aerate soil for tomato roots',
                'onion': 'Deters aphids and other pests',
                'marigold': 'Repels nematodes and whiteflies',
            }
        },
        'basil': {
            'companions': ['tomato', 'pepper', 'oregano', 'parsley'],
            'antagonists': ['rue', 'sage'],
            'benefits': {
                'tomato': 'Repels pests, enhances tomato flavor',
                'pepper': 'Repels aphids and spider mites',
            }
        },
        'carrot': {
            'companions': ['tomato', 'onion', 'leek', 'rosemary', 'sage', 'pea'],
            'antagonists': ['dill', 'parsnip'],
            'benefits': {
                'onion': 'Repels carrot flies',
                'leek': 'Repels carrot flies and onion flies',
                'rosemary': 'Repels carrot flies',
            }
        },
        'pepper': {
            'companions': ['basil', 'onion', 'spinach', 'tomato'],
            'antagonists': ['fennel', 'bean'],
            'benefits': {
                'basil': 'Repels aphids, thrips, and spider mites',
                'onion': 'Deters aphids',
            }
        },
        'lettuce': {
            'companions': ['carrot', 'radish', 'strawberry', 'cucumber', 'onion'],
            'antagonists': ['parsley'],
            'benefits': {
                'radish': 'Radishes break up soil for lettuce',
                'carrot': 'Carrots help aerate soil',
            }
        },
        'cucumber': {
            'companions': ['bean', 'pea', 'radish', 'sunflower', 'lettuce'],
            'antagonists': ['potato', 'sage', 'mint'],
            'benefits': {
                'bean': 'Fixes nitrogen in soil',
                'radish': 'Deters cucumber beetles',
                'sunflower': 'Provides shade and trellis support',
            }
        },
        'bean': {
            'companions': ['carrot', 'cucumber', 'cabbage', 'corn', 'radish'],
            'antagonists': ['onion', 'garlic', 'fennel'],
            'benefits': {
                'corn': 'Corn provides trellis, beans fix nitrogen',
                'carrot': 'Carrots help aerate soil',
                'cucumber': 'Beans fix nitrogen for cucumbers',
            }
        },
        'onion': {
            'companions': ['carrot', 'tomato', 'pepper', 'lettuce', 'cabbage'],
            'antagonists': ['bean', 'pea', 'sage'],
            'benefits': {
                'carrot': 'Repels carrot flies',
                'tomato': 'Deters aphids',
                'cabbage': 'Repels cabbage worms',
            }
        },
        'cabbage': {
            'companions': ['bean', 'onion', 'celery', 'potato', 'sage'],
            'antagonists': ['tomato', 'strawberry', 'grape'],
            'benefits': {
                'onion': 'Repels cabbage worms',
                'sage': 'Repels cabbage moths',
                'celery': 'Repels cabbage worms',
            }
        },
        'potato': {
            'companions': ['bean', 'cabbage', 'corn', 'pea', 'marigold'],
            'antagonists': ['tomato', 'cucumber', 'pumpkin', 'sunflower'],
            'benefits': {
                'bean': 'Fixes nitrogen, deters Colorado potato beetle',
                'marigold': 'Repels potato beetles',
            }
        },
        'strawberry': {
            'companions': ['bean', 'lettuce', 'spinach', 'onion', 'sage'],
            'antagonists': ['cabbage', 'cauliflower'],
            'benefits': {
                'bean': 'Fixes nitrogen',
                'onion': 'Deters pests',
                'sage': 'Repels pests',
            }
        },
        'corn': {
            'companions': ['bean', 'pea', 'cucumber', 'pumpkin', 'squash'],
            'antagonists': ['tomato'],
            'benefits': {
                'bean': 'Three Sisters: corn provides support, beans fix nitrogen',
                'pumpkin': 'Three Sisters: pumpkin provides ground cover',
                'cucumber': 'Corn provides trellis support',
            }
        },
    }

    @staticmethod
    def check_compatibility(plant1_name: str, plant2_name: str) -> Dict[str, Any]:
        """
        Check compatibility between two plants.

        Args:
            plant1_name: Common name of first plant (lowercase)
            plant2_name: Common name of second plant (lowercase)

        Returns:
            Dictionary with compatibility information:
            - compatibility: 'beneficial', 'neutral', or 'antagonistic'
            - benefit: Description of benefit if beneficial
            - warning: Description of issue if antagonistic
        """
        plant1_name = plant1_name.lower().strip()
        plant2_name = plant2_name.lower().strip()

        plant1_data = CompanionPlantingService.COMPANION_DATA.get(plant1_name, {})
        plant2_data = CompanionPlantingService.COMPANION_DATA.get(plant2_name, {})

        result = {
            'plant1': plant1_name,
            'plant2': plant2_name,
            'compatibility': 'neutral',
            'benefit': None,
            'warning': None
        }

        # Check if plant2 is a companion to plant1
        if plant2_name in plant1_data.get('companions', []):
            result['compatibility'] = 'beneficial'
            result['benefit'] = plant1_data.get('benefits', {}).get(plant2_name, 'Beneficial companion pairing')

        # Check if plant2 is an antagonist to plant1
        elif plant2_name in plant1_data.get('antagonists', []):
            result['compatibility'] = 'antagonistic'
            result['warning'] = f"{plant1_name.capitalize()} and {plant2_name} should not be planted together"

        # Check reverse relationship
        elif plant1_name in plant2_data.get('companions', []):
            result['compatibility'] = 'beneficial'
            result['benefit'] = plant2_data.get('benefits', {}).get(plant1_name, 'Beneficial companion pairing')

        elif plant1_name in plant2_data.get('antagonists', []):
            result['compatibility'] = 'antagonistic'
            result['warning'] = f"{plant2_name.capitalize()} and {plant1_name} should not be planted together"

        return result

    @staticmethod
    def get_companion_recommendations(plant_name: str) -> Dict[str, Any]:
        """
        Get companion planting recommendations for a plant.

        Args:
            plant_name: Common name of plant (lowercase)

        Returns:
            Dictionary with:
            - plant: Plant name
            - companions: List of beneficial companions with benefits
            - antagonists: List of plants to avoid
            - has_data: Boolean indicating if data exists for this plant
        """
        cache_key = CACHE_KEY_COMPANION_PLANTS.format(species_id=plant_name)

        # Try cache first
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"[CACHE] HIT for companion data: {plant_name}")
            return cached_data

        plant_name = plant_name.lower().strip()
        plant_data = CompanionPlantingService.COMPANION_DATA.get(plant_name, {})

        if not plant_data:
            result = {
                'plant': plant_name,
                'companions': [],
                'antagonists': [],
                'has_data': False
            }
        else:
            # Build companion list with benefits
            companions_with_benefits = []
            for companion in plant_data.get('companions', []):
                benefit = plant_data.get('benefits', {}).get(companion, 'Beneficial companion')
                companions_with_benefits.append({
                    'name': companion,
                    'benefit': benefit
                })

            result = {
                'plant': plant_name,
                'companions': companions_with_benefits,
                'antagonists': plant_data.get('antagonists', []),
                'has_data': True
            }

        # Cache for 24 hours (companion data rarely changes)
        cache.set(cache_key, result, 86400)
        logger.info(f"[CACHE] SET companion data for {plant_name}")

        return result

    @staticmethod
    def analyze_garden_bed(garden_bed: GardenBed) -> Dict[str, Any]:
        """
        Analyze a garden bed for companion planting issues.

        Checks all plants in the bed for antagonistic pairings.

        Args:
            garden_bed: GardenBed instance

        Returns:
            Dictionary with:
            - total_plants: Number of plants in bed
            - beneficial_pairs: List of beneficial pairings
            - antagonistic_pairs: List of problematic pairings
            - recommendations: List of suggestions
        """
        logger.info(f"[COMPANION] Analyzing garden bed {garden_bed.uuid}")

        plants = garden_bed.plants.filter(is_active=True)
        plant_count = plants.count()

        if plant_count < 2:
            return {
                'total_plants': plant_count,
                'beneficial_pairs': [],
                'antagonistic_pairs': [],
                'recommendations': ['Add more plants to analyze companion planting']
            }

        beneficial_pairs = []
        antagonistic_pairs = []
        recommendations = []

        # Check all pairs
        plant_list = list(plants)
        for i, plant1 in enumerate(plant_list):
            for plant2 in plant_list[i+1:]:
                compatibility = CompanionPlantingService.check_compatibility(
                    plant1.common_name,
                    plant2.common_name
                )

                if compatibility['compatibility'] == 'beneficial':
                    beneficial_pairs.append({
                        'plant1': {
                            'uuid': str(plant1.uuid),
                            'name': plant1.common_name
                        },
                        'plant2': {
                            'uuid': str(plant2.uuid),
                            'name': plant2.common_name
                        },
                        'benefit': compatibility['benefit']
                    })

                elif compatibility['compatibility'] == 'antagonistic':
                    antagonistic_pairs.append({
                        'plant1': {
                            'uuid': str(plant1.uuid),
                            'name': plant1.common_name
                        },
                        'plant2': {
                            'uuid': str(plant2.uuid),
                            'name': plant2.common_name
                        },
                        'warning': compatibility['warning']
                    })
                    recommendations.append(
                        f"Consider separating {plant1.common_name} and {plant2.common_name} into different beds"
                    )

        # Add positive recommendations if no issues
        if not antagonistic_pairs:
            recommendations.append("No companion planting conflicts detected!")

        if beneficial_pairs:
            recommendations.append(f"Great job! {len(beneficial_pairs)} beneficial companion pairings found")

        return {
            'total_plants': plant_count,
            'beneficial_pairs': beneficial_pairs,
            'antagonistic_pairs': antagonistic_pairs,
            'recommendations': recommendations
        }

    @staticmethod
    def suggest_companions_for_plant(plant: Plant, garden_bed: Optional[GardenBed] = None) -> List[str]:
        """
        Suggest companion plants that would work well with an existing plant.

        Args:
            plant: Plant instance
            garden_bed: Optional garden bed to check for existing plants

        Returns:
            List of companion plant names (filtered to avoid antagonists already in bed)
        """
        recommendations = CompanionPlantingService.get_companion_recommendations(plant.common_name)

        if not recommendations['has_data']:
            return []

        companion_names = [c['name'] for c in recommendations['companions']]
        antagonist_names = recommendations['antagonists']

        # If garden bed specified, filter out antagonists already in the bed
        if garden_bed:
            existing_plants = garden_bed.plants.filter(is_active=True).exclude(uuid=plant.uuid)
            existing_names = [p.common_name.lower() for p in existing_plants]

            # Remove companions that are antagonists to existing plants
            for existing_name in existing_names:
                existing_data = CompanionPlantingService.COMPANION_DATA.get(existing_name, {})
                existing_antagonists = existing_data.get('antagonists', [])

                # Remove any companion that's antagonistic to existing plants
                companion_names = [
                    c for c in companion_names
                    if c not in existing_antagonists
                ]

        return companion_names

    @staticmethod
    def get_all_plant_data() -> Dict[str, Any]:
        """
        Get all companion planting data for reference.

        Returns:
            Dictionary of all companion planting relationships
        """
        return CompanionPlantingService.COMPANION_DATA
