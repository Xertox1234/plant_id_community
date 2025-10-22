"""
Plant.health API integration service for plant disease diagnosis.

Plant.health API by Kindwise provides AI-powered plant disease identification 
from images with 90 disease classes covering fungal, bacterial, viral, pest, and abiotic diseases.
Documentation: https://www.kindwise.com/plant-health
"""

import requests
import logging
from typing import Dict, List, Optional, Union
from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
import base64
import io
from PIL import Image

logger = logging.getLogger(__name__)


class PlantHealthAPIService:
    """
    Service for interacting with the plant.health API for disease diagnosis.
    Provides AI-powered plant disease identification from images.
    """
    
    BASE_URL = "https://api.plant.id"  # plant.health API endpoint
    CACHE_TIMEOUT = 3600  # 1 hour cache (disease results can be reused longer)
    
    # Disease categories available in plant.health API
    DISEASE_CATEGORIES = {
        'abiotic': 'Abiotic diseases',
        'fungal': 'Fungal diseases', 
        'bacterial': 'Bacterial diseases',
        'viral': 'Viral diseases',
        'pest': 'Pests and insects'
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the plant.health API service.
        
        Args:
            api_key: plant.health API key. If not provided, will use settings.PLANT_HEALTH_API_KEY
        """
        self.api_key = api_key or getattr(settings, 'PLANT_HEALTH_API_KEY', None)
        if not self.api_key:
            logger.error("Plant.health API key not configured")
            raise ValueError("PLANT_HEALTH_API_KEY must be set in Django settings")
        
        self.session = requests.Session()
        self.session.headers.update({
            'Api-Key': self.api_key,
            'Content-Type': 'application/json'
        })
    
    def _prepare_image(self, image_file, max_size: int = 1500) -> str:
        """
        Prepare image for plant.health API by resizing and converting to base64.
        
        Args:
            image_file: Django file object or file path
            max_size: Maximum dimension for the image
            
        Returns:
            Base64 encoded image string
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
            
            # Convert to base64
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=85, optimize=True)
            image_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            return image_b64
            
        except Exception as e:
            logger.error(f"Error preparing image for plant.health: {str(e)}")
            raise
    
    def diagnose_disease(self, 
                        images: List[Union[str, ContentFile]], 
                        modifiers: Optional[List[str]] = None,
                        disease_details: Optional[List[str]] = None,
                        language: str = 'en') -> Optional[Dict]:
        """
        Diagnose plant diseases from images using plant.health API.
        
        Args:
            images: List of image files or paths (1-5 images recommended)
            modifiers: List of modifiers (e.g., 'crop', 'similar_images', 'disease_similar_images')
            disease_details: List of disease detail fields to include
            language: Language code for results
            
        Returns:
            Disease diagnosis results dictionary or None if error
        """
        if not images:
            logger.error("No images provided for disease diagnosis")
            return None
        
        if len(images) > 10:  # API limit
            logger.warning("plant.health API supports max 10 images, using first 10")
            images = images[:10]
        
        # Default modifiers for disease diagnosis
        if modifiers is None:
            modifiers = ["disease_similar_images", "disease_details"]
        
        # Default disease details to include
        if disease_details is None:
            disease_details = [
                "local_name", 
                "description", 
                "treatment",
                "prevention",
                "classification",
                "common_names"
            ]
        
        try:
            # Prepare images for API
            image_data = []
            for image in images:
                image_b64 = self._prepare_image(image)
                image_data.append(image_b64)
            
            # Prepare request payload
            payload = {
                "images": image_data,
                "modifiers": modifiers,
                "plant_language": language,
                "plant_details": disease_details,
                "disease_details": disease_details
            }
            
            # Make API request
            url = f"{self.BASE_URL}/v2/health_assessment"
            response = self.session.post(url, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            
            # Log API usage for cost tracking
            logger.info(f"plant.health API call made - Images: {len(images)}, "
                       f"Access token used, Status: {response.status_code}")
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"plant.health API request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text[:500]}")
            return None
        except Exception as e:
            logger.error(f"Error preparing plant.health request: {str(e)}")
            return None
    
    def get_top_disease_suggestions(self, diagnosis_result: Dict, min_probability: float = 0.1) -> List[Dict]:
        """
        Extract top disease suggestions from plant.health diagnosis result.
        
        Args:
            diagnosis_result: Result from diagnose_disease method
            min_probability: Minimum probability score to include
            
        Returns:
            List of disease suggestions with scores and details
        """
        if not diagnosis_result or 'health_assessment' not in diagnosis_result:
            return []
        
        health_assessment = diagnosis_result['health_assessment']
        
        if 'diseases' not in health_assessment:
            return []
        
        suggestions = []
        for disease_data in health_assessment['diseases']:
            probability = disease_data.get('probability', 0)
            if probability >= min_probability:
                
                # Extract disease information
                disease_details = disease_data.get('disease_details', {})
                
                suggestion = {
                    'disease_name': disease_data.get('name', ''),
                    'probability': probability,
                    'confidence_score': probability,  # Alias for compatibility
                    'disease_type': self._categorize_disease(disease_data.get('name', '')),
                    'local_name': disease_details.get('local_name', ''),
                    'description': disease_details.get('description', ''),
                    'treatment': disease_details.get('treatment', {}),
                    'prevention': disease_details.get('prevention', {}),
                    'common_names': disease_details.get('common_names', []),
                    'classification': disease_details.get('classification', {}),
                    'similar_images': disease_data.get('similar_images', []),
                    'api_response_data': disease_data,  # Store full response for debugging
                }
                
                suggestions.append(suggestion)
        
        return sorted(suggestions, key=lambda x: x['probability'], reverse=True)
    
    def _categorize_disease(self, disease_name: str) -> str:
        """
        Attempt to categorize disease type based on name.
        
        Args:
            disease_name: Name of the disease
            
        Returns:
            Disease category string
        """
        disease_name_lower = disease_name.lower()
        
        # Common fungal disease indicators
        if any(term in disease_name_lower for term in ['mold', 'mildew', 'rust', 'blight', 'fungus', 'rot', 'canker']):
            return 'fungal'
        
        # Common bacterial disease indicators
        if any(term in disease_name_lower for term in ['bacterial', 'bacteria', 'fire blight', 'soft rot']):
            return 'bacterial'
        
        # Common viral disease indicators  
        if any(term in disease_name_lower for term in ['virus', 'viral', 'mosaic', 'yellows']):
            return 'viral'
        
        # Common pest indicators
        if any(term in disease_name_lower for term in ['aphid', 'mite', 'scale', 'thrips', 'whitefly', 'pest', 'insect']):
            return 'pest'
        
        # Abiotic/environmental indicators
        if any(term in disease_name_lower for term in ['burn', 'scorch', 'deficiency', 'toxicity', 'stress']):
            return 'abiotic'
        
        # Default to fungal as it's most common
        return 'fungal'
    
    def normalize_disease_data(self, suggestion: Dict) -> Dict:
        """
        Normalize plant.health disease suggestion to our internal format.
        
        Args:
            suggestion: Disease suggestion from get_top_disease_suggestions
            
        Returns:
            Normalized disease data dictionary
        """
        treatment_info = suggestion.get('treatment', {})
        prevention_info = suggestion.get('prevention', {})
        
        # Extract treatment instructions
        treatments = []
        if isinstance(treatment_info, dict):
            for treatment_type, treatment_list in treatment_info.items():
                if isinstance(treatment_list, list):
                    for treatment in treatment_list:
                        treatments.append({
                            'type': treatment_type,
                            'name': treatment,
                            'instructions': treatment  # Simple case, can be enhanced
                        })
        
        return {
            'disease_name': suggestion.get('disease_name', ''),
            'disease_type': suggestion.get('disease_type', 'fungal'),
            'confidence_score': suggestion.get('probability', 0.0),
            'description': suggestion.get('description', ''),
            'symptoms': [],  # plant.health doesn't provide structured symptoms
            'treatments': treatments,
            'prevention_tips': prevention_info.get('description', '') if isinstance(prevention_info, dict) else str(prevention_info),
            'severity_assessment': self._assess_severity(suggestion.get('probability', 0.0)),
            'api_source': 'plant_health',
            'api_response_data': suggestion.get('api_response_data', {}),
        }
    
    def _assess_severity(self, probability: float) -> str:
        """
        Assess disease severity based on probability score.
        
        Args:
            probability: Disease probability from API (0.0 to 1.0)
            
        Returns:
            Severity assessment string
        """
        if probability >= 0.8:
            return 'severe'
        elif probability >= 0.6:
            return 'moderate'
        elif probability >= 0.3:
            return 'mild'
        else:
            return 'mild'
    
    def get_service_status(self) -> Dict:
        """
        Check if the plant.health API service is available.
        
        Returns:
            Service status dictionary
        """
        try:
            # Simple health check with minimal request
            test_payload = {
                "images": [],  # Empty for health check
                "modifiers": ["crop"],
                "plant_language": "en"
            }
            
            url = f"{self.BASE_URL}/v2/health_assessment"
            response = self.session.post(url, json=test_payload, timeout=10)
            
            if response.status_code == 200:
                return {
                    'status': 'available',
                    'api_key_valid': True,
                    'disease_categories': len(self.DISEASE_CATEGORIES),
                    'last_check': 'now'
                }
            elif response.status_code == 401:
                return {
                    'status': 'unavailable',
                    'api_key_valid': False,
                    'error': 'Invalid API key',
                    'last_check': 'now'
                }
            else:
                return {
                    'status': 'unavailable',
                    'api_key_valid': False,
                    'error': f'HTTP {response.status_code}: {response.text[:100]}',
                    'last_check': 'now'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'api_key_valid': False,
                'error': str(e),
                'last_check': 'now'
            }
    
    def search_local_database(self, disease_name: str, disease_type: Optional[str] = None) -> List[Dict]:
        """
        Search local disease database before making API calls.
        
        Args:
            disease_name: Name of disease to search for
            disease_type: Optional disease type filter
            
        Returns:
            List of matching diseases from local database
        """
        from ..models import PlantDiseaseDatabase
        
        try:
            # Build query
            query = PlantDiseaseDatabase.objects.filter(
                disease_name__icontains=disease_name
            )
            
            if disease_type:
                query = query.filter(disease_type=disease_type)
            
            # Get top matches ordered by diagnosis count and confidence
            matches = query.order_by('-diagnosis_count', '-confidence_score')[:5]
            
            results = []
            for disease in matches:
                results.append({
                    'disease_name': disease.disease_name,
                    'disease_type': disease.disease_type,
                    'confidence_score': disease.confidence_score,
                    'description': disease.description,
                    'diagnosis_count': disease.diagnosis_count,
                    'source': 'local_database',
                    'uuid': str(disease.uuid)
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching local disease database: {str(e)}")
            return []
    
    def should_use_api(self, local_results: List[Dict], min_local_confidence: float = 0.7) -> bool:
        """
        Determine if we should use API or trust local database results.
        
        Args:
            local_results: Results from local database search
            min_local_confidence: Minimum confidence to trust local results
            
        Returns:
            True if should use API, False if local results are sufficient
        """
        if not local_results:
            return True  # No local results, need API
        
        # Check if we have high-confidence local matches
        high_confidence_results = [
            result for result in local_results 
            if result.get('confidence_score', 0) >= min_local_confidence
        ]
        
        if high_confidence_results:
            return False  # Trust local results
        
        return True  # Local results not confident enough, use API
    
    def get_cost_estimate(self, num_images: int) -> Dict:
        """
        Get cost estimate for API usage.
        
        Args:
            num_images: Number of images to process
            
        Returns:
            Cost estimate information
        """
        # plant.health API pricing: €0.05 per credit
        # Disease diagnosis = 2 credits per request (includes plant ID + disease diagnosis)
        credits_per_request = 2
        cost_per_credit = 0.05  # EUR
        
        total_credits = credits_per_request * 1  # One request regardless of image count
        total_cost = total_credits * cost_per_credit
        
        return {
            'credits_needed': total_credits,
            'cost_eur': total_cost,
            'cost_usd': total_cost * 1.1,  # Approximate conversion
            'images_processed': num_images,
            'note': 'Cost is per request, not per image'
        }