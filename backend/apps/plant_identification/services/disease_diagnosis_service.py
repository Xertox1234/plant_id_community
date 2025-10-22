"""
Disease diagnosis service that orchestrates local database search and plant.health API.

This service provides a unified interface for plant disease diagnosis using both
local disease database (for cost efficiency) and plant.health API (for comprehensive coverage).
"""

import logging
from typing import Dict, List, Optional, Tuple, Union, Callable
from django.core.files.base import ContentFile
from django.utils import timezone
from django.db import transaction
from ..models import (
    PlantDiseaseRequest, PlantDiseaseResult, 
    PlantDiseaseDatabase, DiseaseCareInstructions, PlantSpecies
)
from .plant_health_service import PlantHealthAPIService

logger = logging.getLogger(__name__)

ProgressCallback = Optional[Callable[[str, str, Dict], None]]


class DiseaseAutostorageService:
    """
    Service for automatically storing high-confidence disease diagnoses (≥50%) to local database.
    """
    
    def __init__(self):
        """Initialize the auto-storage service."""
        pass
    
    def store_disease_if_qualified(self, result: 'PlantDiseaseResult') -> Optional['PlantDiseaseDatabase']:
        """
        Store disease result to local database if it meets criteria (≥50% confidence).
        
        Args:
            result: PlantDiseaseResult instance
            
        Returns:
            PlantDiseaseDatabase instance if stored, None otherwise
        """
        if not result.should_store_to_database():
            return None
        
        try:
            with transaction.atomic():
                # Check if disease already exists
                existing_disease = PlantDiseaseDatabase.objects.filter(
                    disease_name__iexact=result.suggested_disease_name
                ).first()
                
                if existing_disease:
                    # Update existing disease
                    disease = self._update_existing_disease(existing_disease, result)
                else:
                    # Create new disease entry
                    disease = self._create_new_disease(result)
                
                # Mark result as stored
                result.stored_to_database = True
                result.save()
                
                # Create care instructions from API data
                self._create_care_instructions(disease, result)
                
                logger.info(f"Auto-stored disease '{disease.disease_name}' with {result.confidence_score:.1%} confidence")
                
                return disease
                
        except Exception as e:
            logger.error(f"Failed to auto-store disease result {result.id}: {str(e)}")
            return None
    
    def _update_existing_disease(self, disease: 'PlantDiseaseDatabase', result: 'PlantDiseaseResult') -> 'PlantDiseaseDatabase':
        """Update existing disease with new diagnosis data."""
        # Increment diagnosis count
        disease.diagnosis_count += 1
        
        # Update confidence score if higher
        if result.confidence_score > disease.confidence_score:
            disease.confidence_score = result.confidence_score
        
        # Update symptoms if we have new ones
        if result.symptoms_identified:
            existing_symptoms = disease.symptoms.get('identified', [])
            new_symptoms = result.symptoms_identified
            # Merge unique symptoms
            merged_symptoms = list(set(existing_symptoms + new_symptoms))
            disease.symptoms['identified'] = merged_symptoms
        
        disease.save()
        return disease
    
    def _create_new_disease(self, result: 'PlantDiseaseResult') -> 'PlantDiseaseDatabase':
        """Create new disease database entry from result."""
        # Extract data from API response
        api_data = result.api_response_data or {}
        
        disease = PlantDiseaseDatabase.objects.create(
            disease_name=result.suggested_disease_name,
            disease_type=result.suggested_disease_type or 'fungal',
            confidence_score=result.confidence_score,
            api_source='plant_health',
            diagnosis_count=1,
            symptoms={
                'identified': result.symptoms_identified or [],
                'api_data': api_data
            },
            description=api_data.get('description', ''),
        )
        
        # Link to plant species if available
        if result.request.plant_species:
            disease.affected_plants.add(result.request.plant_species)
        
        return disease
    
    def _create_care_instructions(self, disease: 'PlantDiseaseDatabase', result: 'PlantDiseaseResult'):
        """Create care instructions from API treatment data."""
        api_data = result.api_response_data or {}
        treatments = api_data.get('treatment', {})
        
        if not treatments:
            return
        
        # Extract treatment methods from API response
        treatment_methods = []
        if isinstance(treatments, dict):
            for treatment_type, treatment_list in treatments.items():
                if isinstance(treatment_list, list):
                    for treatment_text in treatment_list:
                        treatment_methods.append({
                            'type': treatment_type,
                            'instructions': treatment_text
                        })
        
        # Create care instruction records
        for treatment in treatment_methods:
            try:
                # Check if instruction already exists
                existing = DiseaseCareInstructions.objects.filter(
                    disease=disease,
                    treatment_name__icontains=treatment['type']
                ).first()
                
                if not existing:
                    DiseaseCareInstructions.objects.create(
                        disease=disease,
                        treatment_name=f"{treatment['type'].title()} Treatment",
                        treatment_type=self._map_treatment_type(treatment['type']),
                        instructions=treatment['instructions'],
                        source='api',
                        effectiveness_score=0.7  # Default API treatment score
                    )
                    
            except Exception as e:
                logger.warning(f"Failed to create care instruction: {str(e)}")
    
    def _map_treatment_type(self, api_type: str) -> str:
        """Map API treatment type to our internal categories."""
        type_mapping = {
            'chemical': 'chemical',
            'organic': 'organic', 
            'biological': 'biological',
            'cultural': 'cultural',
            'prevention': 'preventive'
        }
        
        api_type_lower = api_type.lower()
        for key, value in type_mapping.items():
            if key in api_type_lower:
                return value
        
        return 'cultural'  # Default


class PlantDiseaseService:
    """
    Main service for plant disease diagnosis that combines local database and API sources.
    """
    
    def __init__(self):
        """Initialize the disease diagnosis service."""
        try:
            self.plant_health = PlantHealthAPIService()
        except ValueError:
            logger.warning("plant.health API not available - continuing without it")
            self.plant_health = None
        
        self.auto_storage = DiseaseAutostorageService()
        
        if not self.plant_health:
            logger.error("No disease diagnosis APIs available")
    
    def diagnose_disease_from_request(self, request: PlantDiseaseRequest, progress_cb: ProgressCallback = None) -> List[PlantDiseaseResult]:
        """
        Process a disease diagnosis request and create result records.
        
        Args:
            request: PlantDiseaseRequest instance
            progress_cb: Optional progress callback function
            
        Returns:
            List of PlantDiseaseResult instances created
        """
        results = []
        
        # Update request status
        request.status = 'processing'
        request.save()
        if progress_cb:
            progress_cb('set_status', 'processing', {'request_id': str(request.request_id)})
        
        try:
            # Collect images from the request
            images = []
            if request.image_1:
                images.append(request.image_1)
            if request.image_2:
                images.append(request.image_2)
            if request.image_3:
                images.append(request.image_3)
            
            if not images:
                logger.error(f"No images found in disease request {request.request_id}")
                request.status = 'failed'
                request.save()
                return []
            
            # Step 1: Search local database first (cost-free)
            local_results = []
            if request.symptoms_description:
                if progress_cb:
                    progress_cb('local_search_start', 'processing', {'query': request.symptoms_description[:50]})
                
                local_results = self._search_local_database(request)
                
                if progress_cb:
                    progress_cb('local_search_done', 'processing', {'results': len(local_results)})
            
            # Step 2: Decide if we need API call based on local results
            use_api = True
            if self.plant_health and local_results:
                use_api = self.plant_health.should_use_api(local_results, min_local_confidence=0.7)
            
            # Step 3: Use API if needed and available
            if use_api and self.plant_health:
                if progress_cb:
                    progress_cb('api_diagnosis_start', 'processing', {'images': len(images)})
                
                api_results = self._diagnose_with_api(request, images)
                results.extend(api_results)
                
                if progress_cb:
                    progress_cb('api_diagnosis_done', 'processing', {'results': len(api_results)})
            else:
                # Use local database results
                results.extend(self._create_results_from_local_data(request, local_results))
                if progress_cb:
                    progress_cb('local_results_used', 'processing', {'results': len(results)})
            
            # Step 4: Auto-store high-confidence results
            if progress_cb:
                progress_cb('auto_storage_start', 'processing', {'results': len(results)})
            
            self._auto_store_results(results)
            
            if progress_cb:
                progress_cb('auto_storage_done', 'processing', {'stored': len([r for r in results if r.stored_to_database])})
            
            # Step 5: Update request status based on results
            if results:
                high_confidence_results = [r for r in results if r.confidence_score >= 0.5]
                
                if high_confidence_results:
                    request.status = 'diagnosed'
                    request.processed_by_ai = True
                    request.ai_processing_date = timezone.now()
                    
                    # Mark the highest confidence result as primary
                    best_result = max(results, key=lambda r: r.confidence_score)
                    best_result.is_primary = True
                    best_result.save()
                else:
                    request.status = 'needs_help'
                    request.processed_by_ai = True
                    request.ai_processing_date = timezone.now()
            else:
                request.status = 'needs_help'
                # Create a helpful fallback result
                self._create_fallback_result(request)
            
            request.save()
            if progress_cb:
                progress_cb('final_status', request.status, {'results': len(results)})
        
        except Exception as e:
            logger.error(f"Error processing disease diagnosis request {request.request_id}: {str(e)}")
            request.status = 'failed'
            request.save()
            if progress_cb:
                progress_cb('final_status', 'failed', {'error': str(e)})
        
        return results
    
    def _search_local_database(self, request: PlantDiseaseRequest) -> List[Dict]:
        """Search local disease database for matches."""
        if not self.plant_health:
            return []
        
        return self.plant_health.search_local_database(
            disease_name=request.symptoms_description,
            disease_type=None
        )
    
    def _diagnose_with_api(self, request: PlantDiseaseRequest, images: List) -> List[PlantDiseaseResult]:
        """Diagnose disease using plant.health API."""
        results = []
        
        try:
            # Perform plant.health diagnosis
            diagnosis = self.plant_health.diagnose_disease(
                images=images,
                modifiers=["disease_similar_images", "disease_details"],
                language='en'
            )
            
            if not diagnosis:
                logger.warning(f"No plant.health results for disease request {request.request_id}")
                return []
            
            # Get top suggestions
            suggestions = self.plant_health.get_top_disease_suggestions(diagnosis, min_probability=0.1)
            
            for suggestion in suggestions[:5]:  # Limit to top 5 results
                # Normalize the data
                normalized_data = self.plant_health.normalize_disease_data(suggestion)
                
                # Create diagnosis result
                result = PlantDiseaseResult.objects.create(
                    request=request,
                    suggested_disease_name=normalized_data['disease_name'],
                    suggested_disease_type=normalized_data['disease_type'],
                    confidence_score=normalized_data['confidence_score'],
                    diagnosis_source='api_plant_health',
                    symptoms_identified=normalized_data.get('symptoms', []),
                    severity_assessment=normalized_data.get('severity_assessment', ''),
                    immediate_actions=self._generate_immediate_actions(normalized_data),
                    recommended_treatments=normalized_data.get('treatments', []),
                    api_response_data=normalized_data.get('api_response_data', {}),
                    notes=f"plant.health AI diagnosis with {normalized_data['confidence_score']:.1%} confidence"
                )
                
                results.append(result)
        
        except Exception as e:
            logger.error(f"plant.health diagnosis failed for request {request.request_id}: {str(e)}")
        
        return results
    
    def _create_results_from_local_data(self, request: PlantDiseaseRequest, local_results: List[Dict]) -> List[PlantDiseaseResult]:
        """Create diagnosis results from local database matches."""
        results = []
        
        try:
            for local_result in local_results:
                # Get disease from database
                disease_uuid = local_result.get('uuid')
                if disease_uuid:
                    disease = PlantDiseaseDatabase.objects.get(uuid=disease_uuid)
                    
                    result = PlantDiseaseResult.objects.create(
                        request=request,
                        identified_disease=disease,
                        suggested_disease_name=disease.disease_name,
                        suggested_disease_type=disease.disease_type,
                        confidence_score=local_result.get('confidence_score', 0.7),
                        diagnosis_source='local_db',
                        symptoms_identified=disease.symptoms.get('identified', []),
                        notes=f"Matched from local database ({disease.diagnosis_count} previous diagnoses)"
                    )
                    
                    results.append(result)
        
        except Exception as e:
            logger.error(f"Failed to create results from local data: {str(e)}")
        
        return results
    
    def _auto_store_results(self, results: List[PlantDiseaseResult]):
        """Auto-store high-confidence results to local database."""
        for result in results:
            if result.should_store_to_database():
                stored_disease = self.auto_storage.store_disease_if_qualified(result)
                if stored_disease:
                    # Update result to reference the stored disease
                    result.identified_disease = stored_disease
                    result.save()
    
    def _generate_immediate_actions(self, normalized_data: Dict) -> str:
        """Generate immediate action recommendations based on diagnosis."""
        disease_type = normalized_data.get('disease_type', '')
        confidence = normalized_data.get('confidence_score', 0)
        
        actions = []
        
        if confidence >= 0.7:
            actions.append("High confidence diagnosis - begin treatment immediately.")
        elif confidence >= 0.5:
            actions.append("Moderate confidence diagnosis - monitor symptoms and begin treatment.")
        else:
            actions.append("Low confidence diagnosis - consider getting a second opinion.")
        
        # Type-specific actions
        if disease_type == 'fungal':
            actions.append("Improve air circulation around the plant.")
            actions.append("Reduce watering frequency and avoid wetting leaves.")
        elif disease_type == 'bacterial':
            actions.append("Remove affected plant parts immediately.")
            actions.append("Disinfect tools between cuts.")
        elif disease_type == 'viral':
            actions.append("Isolate the plant from other plants immediately.")
            actions.append("Remove affected parts carefully.")
        elif disease_type == 'pest':
            actions.append("Inspect plant thoroughly for pest presence.")
            actions.append("Consider using appropriate pest control methods.")
        
        return " ".join(actions)
    
    def _create_fallback_result(self, request: PlantDiseaseRequest):
        """Create a helpful fallback result when diagnosis fails."""
        try:
            notes = "Disease diagnosis services are currently unavailable. "
            
            if request.symptoms_description:
                notes += f"Based on your description: '{request.symptoms_description}', "
            
            notes += "community members may be able to help identify the issue. "
            notes += "Please consider posting in the plant health forum with your images and symptom description."
            
            PlantDiseaseResult.objects.create(
                request=request,
                suggested_disease_name="",
                suggested_disease_type="",
                confidence_score=0.0,
                diagnosis_source='system_message',
                notes=notes,
                is_primary=True
            )
        
        except Exception as e:
            logger.error(f"Failed to create fallback disease result: {str(e)}")
    
    def get_service_status(self) -> Dict:
        """
        Get status of disease diagnosis services.
        
        Returns:
            Dictionary with service status information
        """
        status = {
            'plant_health': {'available': False},
            'local_database': {'available': False},
            'auto_storage': {'available': True},
            'combined_service': {'available': False}
        }
        
        if self.plant_health:
            status['plant_health'] = self.plant_health.get_service_status()
        
        # Check local database
        try:
            disease_count = PlantDiseaseDatabase.objects.count()
            status['local_database'] = {
                'available': True,
                'disease_count': disease_count,
                'last_check': 'now'
            }
        except Exception as e:
            status['local_database'] = {
                'available': False,
                'error': str(e),
                'last_check': 'now'
            }
        
        # Combined service is available if either API works or local database has data
        status['combined_service']['available'] = (
            status['plant_health'].get('status') == 'available' or 
            status['local_database'].get('available', False)
        )
        
        return status