"""
Plant Identification Service - Dual API Integration
Combines Kindwise (Plant.id) and PlantNet for comprehensive results
"""
import os
import requests
from typing import Dict, List, Optional

class PlantIdentificationService:
    """
    Combines multiple plant identification APIs:
    1. Kindwise (Plant.id) - AI identification + disease detection
    2. PlantNet - Open source identification + care instructions
    """
    
    def __init__(self):
        self.plant_id_api_key = os.getenv('PLANT_ID_API_KEY')
        self.plantnet_api_key = os.getenv('PLANTNET_API_KEY')
        
        self.plant_id_url = 'https://plant.id/api/v3/identification'
        self.plantnet_url = 'https://my-api.plantnet.org/v2/identify/all'
        
    def identify_plant(self, image_data: bytes) -> Dict:
        """
        Identify plant using both APIs and combine results
        
        Strategy:
        1. Use Plant.id for primary identification + disease detection
        2. Use PlantNet to enrich with care instructions
        3. Merge results for comprehensive plant information
        """
        results = {
            'primary_identification': None,
            'care_instructions': None,
            'disease_detection': None,
            'combined_suggestions': [],
            'confidence_score': 0,
        }
        
        # Primary identification with Kindwise (Plant.id)
        plant_id_results = self._identify_with_plant_id(image_data)
        if plant_id_results:
            results['primary_identification'] = plant_id_results
            results['disease_detection'] = plant_id_results.get('health_assessment')
            results['confidence_score'] = plant_id_results.get('suggestions', [{}])[0].get('probability', 0)
        
        # Supplement with PlantNet for care instructions
        plantnet_results = self._identify_with_plantnet(image_data)
        if plantnet_results:
            results['care_instructions'] = self._extract_care_info(plantnet_results)
        
        # Combine suggestions from both APIs
        results['combined_suggestions'] = self._merge_suggestions(
            plant_id_results,
            plantnet_results
        )
        
        return results
    
    def _identify_with_plant_id(self, image_data: bytes) -> Optional[Dict]:
        """
        Use Kindwise Plant.id API for identification + disease detection
        Best accuracy, includes health assessment
        """
        if not self.plant_id_api_key:
            return None
            
        try:
            headers = {
                'Api-Key': self.plant_id_api_key,
                'Content-Type': 'application/json',
            }
            
            # Plant.id expects base64 encoded image
            import base64
            encoded_image = base64.b64encode(image_data).decode('utf-8')
            
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
                'disease_details': [
                    'common_names',
                    'description',
                    'treatment',
                    'classification',
                    'url',
                ],
            }
            
            response = requests.post(
                self.plant_id_url,
                json=data,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            print(f"Plant.id API error: {e}")
            return None
    
    def _identify_with_plantnet(self, image_data: bytes) -> Optional[Dict]:
        """
        Use PlantNet API for supplemental care instructions
        Open source, good for common plants with detailed care info
        """
        if not self.plantnet_api_key:
            return None
            
        try:
            files = {'images': image_data}
            params = {
                'api-key': self.plantnet_api_key,
                'include-related-images': 'true',
            }
            
            response = requests.post(
                self.plantnet_url,
                files=files,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            print(f"PlantNet API error: {e}")
            return None
    
    def _extract_care_info(self, plantnet_results: Dict) -> Dict:
        """
        Extract care instructions from PlantNet results
        PlantNet is great for care info on common plants
        """
        care_info = {
            'watering': None,
            'light': None,
            'temperature': None,
            'humidity': None,
            'fertilizing': None,
            'pruning': None,
            'common_issues': [],
        }
        
        # PlantNet includes care data in the results
        if plantnet_results and 'results' in plantnet_results:
            top_result = plantnet_results['results'][0] if plantnet_results['results'] else {}
            
            # Extract care instructions from species data
            species = top_result.get('species', {})
            care_info['watering'] = species.get('watering')
            care_info['light'] = species.get('light_requirements')
            care_info['temperature'] = species.get('temperature')
            
        return care_info
    
    def _merge_suggestions(self, plant_id_data: Optional[Dict], plantnet_data: Optional[Dict]) -> List[Dict]:
        """
        Combine suggestions from both APIs
        Plant.id provides accuracy, PlantNet adds care details
        """
        combined = []
        
        # Add Plant.id suggestions (primary)
        if plant_id_data and 'suggestions' in plant_id_data:
            for suggestion in plant_id_data['suggestions'][:5]:  # Top 5
                combined.append({
                    'plant_name': suggestion.get('plant_name'),
                    'scientific_name': suggestion.get('plant_details', {}).get('scientific_name'),
                    'probability': suggestion.get('probability'),
                    'common_names': suggestion.get('plant_details', {}).get('common_names'),
                    'description': suggestion.get('plant_details', {}).get('description'),
                    'care_instructions': suggestion.get('plant_details', {}).get('watering'),
                    'edible_parts': suggestion.get('plant_details', {}).get('edible_parts'),
                    'similar_images': suggestion.get('similar_images', []),
                    'source': 'plant_id',
                })
        
        # Enrich with PlantNet data
        if plantnet_data and 'results' in plantnet_data:
            for result in plantnet_data['results'][:3]:  # Top 3
                species = result.get('species', {})
                
                # Check if this plant is already in our list
                scientific_name = species.get('scientificNameWithoutAuthor')
                existing = next(
                    (s for s in combined if s['scientific_name'] == scientific_name),
                    None
                )
                
                if existing:
                    # Enrich existing entry with PlantNet care data
                    existing['care_instructions_detailed'] = {
                        'watering': species.get('watering'),
                        'light': species.get('light'),
                        'temperature': species.get('temperature'),
                    }
                else:
                    # Add as new suggestion
                    combined.append({
                        'plant_name': species.get('commonNames', [None])[0],
                        'scientific_name': scientific_name,
                        'probability': result.get('score'),
                        'common_names': species.get('commonNames'),
                        'care_instructions_detailed': {
                            'watering': species.get('watering'),
                            'light': species.get('light'),
                            'temperature': species.get('temperature'),
                        },
                        'source': 'plantnet',
                    })
        
        # Sort by confidence/probability
        combined.sort(key=lambda x: x.get('probability', 0), reverse=True)
        
        return combined

# Example usage in Django view:
"""
from .services import PlantIdentificationService

def identify_plant_view(request):
    if request.method == 'POST':
        image_file = request.FILES['image']
        image_data = image_file.read()
        
        service = PlantIdentificationService()
        results = service.identify_plant(image_data)
        
        return JsonResponse({
            'success': True,
            'plant_name': results['combined_suggestions'][0]['plant_name'],
            'scientific_name': results['combined_suggestions'][0]['scientific_name'],
            'confidence': results['confidence_score'],
            'suggestions': results['combined_suggestions'],
            'care_instructions': results['care_instructions'],
            'disease_detection': results['disease_detection'],
        })
"""
