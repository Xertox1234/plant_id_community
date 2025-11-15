"""
Companion Planting Service

Plant compatibility analysis and recommendations.

Provides:
- Companion plant suggestions
- Enemy plant warnings
- Spacing recommendations
- Layout validation
"""

import logging
import math
from typing import List, Dict, Any, Optional, Tuple

from ..models import GardenPlant, PlantCareLibrary, Garden
from ..constants import (
    MIN_DISTANCE_ENEMY_PLANTS_FT,
    MIN_DISTANCE_ENEMY_PLANTS_M
)

logger = logging.getLogger(__name__)


class CompanionPlantingService:
    """
    Plant compatibility and layout analysis service.

    Uses PlantCareLibrary data for companion/enemy relationships.
    Validates garden layouts for plant spacing conflicts.
    """

    @classmethod
    def calculate_distance(
        cls,
        pos1: Dict[str, float],
        pos2: Dict[str, float]
    ) -> float:
        """
        Calculate Euclidean distance between two positions.

        Args:
            pos1: {x: float, y: float}
            pos2: {x: float, y: float}

        Returns:
            Distance in same units as position coordinates
        """
        dx = pos2['x'] - pos1['x']
        dy = pos2['y'] - pos1['y']
        return math.sqrt(dx * dx + dy * dy)

    @classmethod
    def get_plant_care_data(
        cls,
        plant: GardenPlant
    ) -> Optional[PlantCareLibrary]:
        """
        Get care library data for a garden plant.

        Args:
            plant: GardenPlant instance

        Returns:
            PlantCareLibrary instance or None
        """
        if not plant.scientific_name:
            return None

        try:
            return PlantCareLibrary.objects.get(
                scientific_name__iexact=plant.scientific_name
            )
        except PlantCareLibrary.DoesNotExist:
            logger.info(
                f"[COMPANION] No care data for {plant.scientific_name}"
            )
            return None

    @classmethod
    def check_compatibility(
        cls,
        plant1: GardenPlant,
        plant2: GardenPlant
    ) -> Dict[str, Any]:
        """
        Check compatibility between two plants.

        Args:
            plant1: First GardenPlant instance
            plant2: Second GardenPlant instance

        Returns:
            Dict with:
            - compatible: bool (True if companions, False if enemies, None if unknown)
            - relationship: 'companion', 'enemy', or 'neutral'
            - distance: float (current distance between plants)
            - min_distance: float (recommended minimum distance)
            - warning: str or None (if plants are too close and incompatible)
        """
        care1 = cls.get_plant_care_data(plant1)
        care2 = cls.get_plant_care_data(plant2)

        # Calculate distance
        distance = cls.calculate_distance(plant1.position, plant2.position)

        # Get garden unit
        unit = plant1.garden.dimensions.get('unit', 'ft')
        min_distance = MIN_DISTANCE_ENEMY_PLANTS_FT if unit == 'ft' else MIN_DISTANCE_ENEMY_PLANTS_M

        # Check relationship
        relationship = 'neutral'
        compatible = None
        warning = None

        if care1:
            # Check if plant2 is in plant1's companion list
            if plant2.scientific_name in care1.companion_plants or plant2.common_name in care1.companion_plants:
                relationship = 'companion'
                compatible = True
                logger.info(
                    f"[COMPANION] {plant1.common_name} and {plant2.common_name} "
                    f"are good companions"
                )

            # Check if plant2 is in plant1's enemy list
            elif plant2.scientific_name in care1.enemy_plants or plant2.common_name in care1.enemy_plants:
                relationship = 'enemy'
                compatible = False

                # Check if too close
                if distance < min_distance:
                    warning = (
                        f"{plant1.common_name} and {plant2.common_name} "
                        f"are incompatible and should be at least {min_distance} "
                        f"{unit} apart (currently {distance:.1f} {unit})"
                    )
                    logger.warning(f"[COMPANION] {warning}")

        # Also check reverse relationship
        if care2 and relationship == 'neutral':
            if plant1.scientific_name in care2.companion_plants or plant1.common_name in care2.companion_plants:
                relationship = 'companion'
                compatible = True
            elif plant1.scientific_name in care2.enemy_plants or plant1.common_name in care2.enemy_plants:
                relationship = 'enemy'
                compatible = False

                if distance < min_distance:
                    warning = (
                        f"{plant2.common_name} and {plant1.common_name} "
                        f"are incompatible and should be at least {min_distance} "
                        f"{unit} apart (currently {distance:.1f} {unit})"
                    )
                    logger.warning(f"[COMPANION] {warning}")

        return {
            'compatible': compatible,
            'relationship': relationship,
            'distance': distance,
            'min_distance': min_distance,
            'warning': warning
        }

    @classmethod
    def validate_garden_layout(
        cls,
        garden: Garden
    ) -> Dict[str, Any]:
        """
        Validate entire garden layout for companion planting conflicts.

        Args:
            garden: Garden instance

        Returns:
            Dict with:
            - has_conflicts: bool
            - conflicts: list of conflict dicts
            - companion_pairs: list of beneficial companion pairs
            - recommendations: list of recommendation strings
        """
        plants = list(garden.plants.all())
        conflicts = []
        companion_pairs = []

        # Check all plant pairs
        for i, plant1 in enumerate(plants):
            for plant2 in plants[i+1:]:
                result = cls.check_compatibility(plant1, plant2)

                if result['relationship'] == 'enemy' and result['warning']:
                    conflicts.append({
                        'plant1': plant1.common_name,
                        'plant2': plant2.common_name,
                        'warning': result['warning'],
                        'distance': result['distance'],
                        'min_distance': result['min_distance']
                    })

                elif result['relationship'] == 'companion':
                    companion_pairs.append({
                        'plant1': plant1.common_name,
                        'plant2': plant2.common_name,
                        'distance': result['distance']
                    })

        # Generate recommendations
        recommendations = []

        if conflicts:
            recommendations.append(
                f"Found {len(conflicts)} incompatible plant combinations that should be separated"
            )

        if companion_pairs:
            recommendations.append(
                f"Found {len(companion_pairs)} beneficial companion planting combinations"
            )

        logger.info(
            f"[COMPANION] Garden {garden.id} validation: "
            f"{len(conflicts)} conflicts, {len(companion_pairs)} beneficial pairs"
        )

        return {
            'has_conflicts': len(conflicts) > 0,
            'conflicts': conflicts,
            'companion_pairs': companion_pairs,
            'recommendations': recommendations
        }

    @classmethod
    def get_companion_suggestions(
        cls,
        plant: GardenPlant
    ) -> List[Dict[str, Any]]:
        """
        Get companion plant suggestions for a specific plant.

        Args:
            plant: GardenPlant instance

        Returns:
            List of dicts with:
            - scientific_name: str
            - common_names: list
            - benefits: str (why this is a good companion)
        """
        care_data = cls.get_plant_care_data(plant)
        if not care_data or not care_data.companion_plants:
            return []

        suggestions = []

        for companion_name in care_data.companion_plants:
            # Try to find in PlantCareLibrary
            try:
                companion_care = PlantCareLibrary.objects.get(
                    scientific_name__iexact=companion_name
                )
                suggestions.append({
                    'scientific_name': companion_care.scientific_name,
                    'common_names': companion_care.common_names,
                    'benefits': f"Beneficial companion for {plant.common_name}"
                })
            except PlantCareLibrary.DoesNotExist:
                # Add as simple suggestion
                suggestions.append({
                    'scientific_name': companion_name,
                    'common_names': [companion_name],
                    'benefits': f"Beneficial companion for {plant.common_name}"
                })

        logger.info(
            f"[COMPANION] Found {len(suggestions)} companion suggestions "
            f"for {plant.common_name}"
        )

        return suggestions

    @classmethod
    def get_plants_to_avoid(
        cls,
        plant: GardenPlant
    ) -> List[Dict[str, Any]]:
        """
        Get list of plants to avoid near this plant.

        Args:
            plant: GardenPlant instance

        Returns:
            List of dicts with:
            - scientific_name: str
            - common_names: list
            - reason: str (why to avoid)
        """
        care_data = cls.get_plant_care_data(plant)
        if not care_data or not care_data.enemy_plants:
            return []

        enemies = []

        for enemy_name in care_data.enemy_plants:
            # Try to find in PlantCareLibrary
            try:
                enemy_care = PlantCareLibrary.objects.get(
                    scientific_name__iexact=enemy_name
                )
                enemies.append({
                    'scientific_name': enemy_care.scientific_name,
                    'common_names': enemy_care.common_names,
                    'reason': f"Incompatible with {plant.common_name}"
                })
            except PlantCareLibrary.DoesNotExist:
                # Add as simple warning
                enemies.append({
                    'scientific_name': enemy_name,
                    'common_names': [enemy_name],
                    'reason': f"Incompatible with {plant.common_name}"
                })

        logger.info(
            f"[COMPANION] Found {len(enemies)} plants to avoid "
            f"near {plant.common_name}"
        )

        return enemies

    @classmethod
    def suggest_optimal_position(
        cls,
        garden: Garden,
        new_plant_scientific_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Suggest optimal position for a new plant based on companions/enemies.

        Args:
            garden: Garden instance
            new_plant_scientific_name: Scientific name of plant to add

        Returns:
            Dict with:
            - suggested_position: {x: float, y: float} or None
            - near_companions: list of plant names
            - away_from_enemies: list of plant names
            - reasoning: str
        """
        # Get care data for new plant
        try:
            new_plant_care = PlantCareLibrary.objects.get(
                scientific_name__iexact=new_plant_scientific_name
            )
        except PlantCareLibrary.DoesNotExist:
            logger.info(
                f"[COMPANION] No care data for {new_plant_scientific_name}, "
                f"cannot suggest position"
            )
            return None

        existing_plants = list(garden.plants.all())
        if not existing_plants:
            # No plants in garden yet - suggest center
            width = garden.dimensions['width']
            height = garden.dimensions['height']
            return {
                'suggested_position': {'x': width / 2, 'y': height / 2},
                'near_companions': [],
                'away_from_enemies': [],
                'reasoning': 'First plant in garden - suggested center position'
            }

        # Find companion plants in garden
        companions_in_garden = []
        enemies_in_garden = []

        for plant in existing_plants:
            if plant.scientific_name in new_plant_care.companion_plants or \
               plant.common_name in new_plant_care.companion_plants:
                companions_in_garden.append(plant)

            elif plant.scientific_name in new_plant_care.enemy_plants or \
                 plant.common_name in new_plant_care.enemy_plants:
                enemies_in_garden.append(plant)

        # Calculate optimal position
        # Strategy: Near companions, far from enemies
        if companions_in_garden:
            # Average position of all companions
            avg_x = sum(p.position['x'] for p in companions_in_garden) / len(companions_in_garden)
            avg_y = sum(p.position['y'] for p in companions_in_garden) / len(companions_in_garden)

            suggested_pos = {'x': avg_x, 'y': avg_y}
            reasoning = f"Near {len(companions_in_garden)} companion plant(s)"
        else:
            # No companions - find spot far from enemies
            width = garden.dimensions['width']
            height = garden.dimensions['height']
            suggested_pos = {'x': width / 2, 'y': height / 2}
            reasoning = "No companions in garden - suggested center position"

        logger.info(
            f"[COMPANION] Suggested position for {new_plant_scientific_name}: "
            f"({suggested_pos['x']:.1f}, {suggested_pos['y']:.1f})"
        )

        return {
            'suggested_position': suggested_pos,
            'near_companions': [p.common_name for p in companions_in_garden],
            'away_from_enemies': [p.common_name for p in enemies_in_garden],
            'reasoning': reasoning
        }
