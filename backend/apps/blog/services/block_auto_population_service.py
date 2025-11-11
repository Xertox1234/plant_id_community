"""
Service for auto-populating Wagtail block fields with plant data.

This service integrates with PlantDataLookupService to provide intelligent
auto-population of blog content blocks with plant information.
"""

import logging
from typing import Dict
from .plant_data_lookup_service import PlantDataLookupService

logger = logging.getLogger(__name__)


class BlockAutoPopulationService:
    """
    Service for auto-populating Wagtail block fields with plant data.
    """

    def __init__(self):
        self.plant_lookup = PlantDataLookupService()

    def populate_plant_spotlight_fields(self, plant_query: str, user=None) -> Dict:
        """Auto-populate Plant Spotlight block fields."""
        plant_data = self.plant_lookup.lookup_plant_data(plant_query, user)

        if not plant_data['found']:
            return {'success': False, 'message': 'Plant not found'}

        data = plant_data['data']

        return {
            'success': True,
            'source': plant_data['source'],
            'confidence': plant_data['confidence'],
            'fields': {
                'plant_name': data.get('plant_name', ''),
                'scientific_name': data.get('scientific_name', ''),
                'description': data.get('description', ''),
                'care_difficulty': data.get('care_difficulty', 'moderate'),
                'suggested_image_url': data.get('primary_image_url')
            }
        }

    def populate_care_instructions_fields(self, plant_query: str, user=None) -> Dict:
        """Auto-populate Care Instructions block fields."""
        plant_data = self.plant_lookup.lookup_plant_data(plant_query, user)

        if not plant_data['found']:
            return {'success': False, 'message': 'Plant not found'}

        data = plant_data['data']
        care_instructions = self.plant_lookup.generate_care_instructions(data)

        return {
            'success': True,
            'source': plant_data['source'],
            'confidence': plant_data['confidence'],
            'fields': {
                'care_title': f"How to Care for {data.get('plant_name', 'Your Plant')}",
                'watering': care_instructions.get('watering', ''),
                'lighting': care_instructions.get('lighting', ''),
                'temperature': care_instructions.get('temperature', ''),
                'humidity': care_instructions.get('humidity', ''),
                'fertilizing': care_instructions.get('fertilizing', ''),
                'special_notes': care_instructions.get('special_notes', '')
            }
        }
