"""
Combined Plant Identification Service - Dual API Integration

Integrates Plant.id (Kindwise) and PlantNet APIs to provide:
1. High-accuracy AI identification (Plant.id)
2. Disease detection (Plant.id)
3. Comprehensive care instructions (PlantNet)
"""

import logging
from typing import Dict, List, Optional
from django.conf import settings

from .plant_id_service import PlantIDAPIService
from .plantnet_service import PlantNetAPIService

logger = logging.getLogger(__name__)


class CombinedPlantIdentificationService:
    """
    Combines Plant.id and PlantNet APIs for comprehensive plant identification.
    
    Strategy:
    1. Use Plant.id for primary identification + disease detection (best accuracy)
    2. Use PlantNet to supplement with care instructions (open source data)
    3. Merge results to provide comprehensive plant information
    """
    
    def __init__(self):
        """Initialize both API services."""
        self.plant_id = None
        self.plantnet = None
        
        # Initialize Plant.id (Kindwise) service
        try:
            if getattr(settings, 'ENABLE_PLANT_ID', True):
                self.plant_id = PlantIDAPIService()
                logger.info("Plant.id service initialized")
        except Exception as e:
            logger.warning(f"Plant.id service not available: {e}")
        
        # Initialize PlantNet service
        try:
            if getattr(settings, 'ENABLE_PLANTNET', True):
                self.plantnet = PlantNetAPIService()
                logger.info("PlantNet service initialized")
        except Exception as e:
            logger.warning(f"PlantNet service not available: {e}")
        
        if not self.plant_id and not self.plantnet:
            logger.error("No plant identification APIs available")
    
    def identify_plant(self, image_file, user=None) -> Dict:
        """
        Identify a plant using both APIs and combine results.
        
        Args:
            image_file: Django file object or file bytes
            user: Optional user object for tracking
            
        Returns:
            Combined identification results
        """
        results = {
            'primary_identification': None,
            'care_instructions': None,
            'disease_detection': None,
            'combined_suggestions': [],
            'confidence_score': 0,
            'source': None,
        }
        
        # Primary identification with Plant.id (best accuracy + disease detection)
        plant_id_results = None
        if self.plant_id:
            try:
                logger.info("Identifying plant with Plant.id API...")
                plant_id_results = self.plant_id.identify_plant(
                    image_file,
                    include_diseases=True
                )
                
                if plant_id_results:
                    results['primary_identification'] = plant_id_results
                    results['disease_detection'] = plant_id_results.get('health_assessment')
                    results['confidence_score'] = plant_id_results.get('confidence', 0)
                    results['source'] = 'plant_id'
                    
                    logger.info(f"Plant.id identified: {plant_id_results.get('top_suggestion', {}).get('plant_name', 'Unknown')} "
                              f"(confidence: {results['confidence_score']:.2%})")
                    
            except Exception as e:
                logger.error(f"Plant.id identification failed: {e}")
        
        # Supplement with PlantNet for care instructions
        plantnet_results = None
        if self.plantnet:
            try:
                logger.info("Enriching with PlantNet care instructions...")
                
                # Reset file pointer if needed
                if hasattr(image_file, 'seek'):
                    image_file.seek(0)
                
                plantnet_results = self.plantnet.identify_plant(
                    image_file,
                    organs=['flower', 'leaf', 'fruit', 'bark'],  # Try multiple organs
                    include_related_images=True
                )
                
                if plantnet_results:
                    # Extract care instructions from PlantNet
                    results['care_instructions'] = self._extract_care_info(plantnet_results)
                    logger.info("PlantNet care instructions retrieved")
                    
            except Exception as e:
                logger.error(f"PlantNet enrichment failed: {e}")
        
        # Combine suggestions from both APIs
        results['combined_suggestions'] = self._merge_suggestions(
            plant_id_results,
            plantnet_results
        )
        
        # If no results from either API, return error
        if not results['combined_suggestions']:
            logger.warning("No identification results from any API")
            results['error'] = "Unable to identify plant. Please try a clearer image."
        
        return results
    
    def _extract_care_info(self, plantnet_results: Dict) -> Dict:
        """
        Extract care instructions from PlantNet results.
        
        Args:
            plantnet_results: PlantNet API response
            
        Returns:
            Care instructions dictionary
        """
        care_info = {
            'watering': 'Moderate watering recommended',
            'light': 'Bright indirect light',
            'temperature': 'Room temperature (18-24°C)',
            'humidity': 'Average humidity',
            'fertilizing': 'Monthly during growing season',
            'pruning': 'Prune as needed',
            'common_issues': [],
        }
        
        # PlantNet results structure
        if plantnet_results and 'results' in plantnet_results:
            results_list = plantnet_results.get('results', [])
            if results_list:
                top_result = results_list[0]
                species = top_result.get('species', {})
                
                # Extract care data from species information
                # Note: PlantNet API returns scientific data, care instructions
                # would need to be enriched from other sources or databases
                care_info['scientific_name'] = species.get('scientificNameWithoutAuthor')
                care_info['family'] = species.get('family', {}).get('scientificName')
                care_info['genus'] = species.get('genus', {}).get('scientificName')
        
        return care_info
    
    def _merge_suggestions(
        self,
        plant_id_results: Optional[Dict],
        plantnet_results: Optional[Dict]
    ) -> List[Dict]:
        """
        Combine suggestions from both APIs, prioritizing Plant.id.
        
        Args:
            plant_id_results: Plant.id API results
            plantnet_results: PlantNet API results
            
        Returns:
            Merged suggestions list
        """
        combined = []
        
        # Add Plant.id suggestions (primary, most accurate)
        if plant_id_results and 'suggestions' in plant_id_results:
            for suggestion in plant_id_results['suggestions'][:5]:  # Top 5
                combined.append({
                    'plant_name': suggestion.get('plant_name'),
                    'scientific_name': suggestion.get('scientific_name'),
                    'probability': suggestion.get('probability'),
                    'common_names': suggestion.get('common_names', []),
                    'description': suggestion.get('description'),
                    'taxonomy': suggestion.get('taxonomy'),
                    'edible_parts': suggestion.get('edible_parts'),
                    'watering': suggestion.get('watering'),
                    'propagation_methods': suggestion.get('propagation_methods'),
                    'similar_images': suggestion.get('similar_images', []),
                    'url': suggestion.get('url'),
                    'source': 'plant_id',
                    'rank': len(combined) + 1,
                })
        
        # Enrich with PlantNet data or add supplemental suggestions
        if plantnet_results and 'results' in plantnet_results:
            for idx, result in enumerate(plantnet_results['results'][:3]):  # Top 3
                species = result.get('species', {})
                scientific_name = species.get('scientificNameWithoutAuthor')
                
                # Check if this plant is already in our list (from Plant.id)
                existing = next(
                    (s for s in combined if s.get('scientific_name') == scientific_name),
                    None
                )
                
                if existing:
                    # Enrich existing entry with PlantNet data
                    existing['plantnet_score'] = result.get('score')
                    existing['plantnet_matched'] = True
                    existing['family'] = species.get('family', {}).get('scientificName')
                    existing['genus'] = species.get('genus', {}).get('scientificName')
                else:
                    # Add as supplemental suggestion
                    common_names = species.get('commonNames', [])
                    combined.append({
                        'plant_name': common_names[0] if common_names else scientific_name,
                        'scientific_name': scientific_name,
                        'probability': result.get('score', 0),
                        'common_names': common_names,
                        'family': species.get('family', {}).get('scientificName'),
                        'genus': species.get('genus', {}).get('scientificName'),
                        'source': 'plantnet',
                        'rank': len(combined) + 1,
                    })
        
        # Sort by probability/confidence
        combined.sort(key=lambda x: x.get('probability', 0), reverse=True)
        
        # Update ranks after sorting
        for idx, suggestion in enumerate(combined):
            suggestion['rank'] = idx + 1
        
        return combined
    
    def get_identification_summary(self, results: Dict) -> str:
        """
        Generate a human-readable summary of identification results.
        
        Args:
            results: Combined identification results
            
        Returns:
            Summary string
        """
        if not results.get('combined_suggestions'):
            return "Unable to identify plant from image."
        
        top = results['combined_suggestions'][0]
        plant_name = top.get('plant_name', 'Unknown Plant')
        scientific_name = top.get('scientific_name', '')
        confidence = top.get('probability', 0)
        
        summary = f"Identified as: {plant_name}"
        if scientific_name:
            summary += f" ({scientific_name})"
        summary += f" - Confidence: {confidence:.1%}"
        
        # Add disease warning if detected
        if results.get('disease_detection'):
            disease = results['disease_detection']
            if not disease.get('is_healthy'):
                disease_name = disease.get('disease_name', 'Unknown disease')
                summary += f"\n⚠️ Health Issue Detected: {disease_name}"
        
        return summary
