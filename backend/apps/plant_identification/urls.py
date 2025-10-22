"""
URL configuration for plant identification API endpoints.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.decorators import api_view
from rest_framework.response import Response
from . import views
from .api import simple_views

app_name = 'plant_identification'

@api_view(['GET'])
def health_check(request):
    """Simple health check endpoint for plant identification API."""
    return Response({
        'status': 'healthy',
        'message': 'Plant Identification API is working',
        'endpoints': {
            'plant_identification': [
                '/api/plant-identification/species/',
                '/api/plant-identification/requests/',
                '/api/plant-identification/results/',
                '/api/plant-identification/plants/',
            ],
            'disease_diagnosis': [
                '/api/plant-identification/disease-requests/',
                '/api/plant-identification/disease-results/',
                '/api/plant-identification/disease-database/',
                '/api/plant-identification/saved-diagnoses/',
                '/api/plant-identification/saved-care-instructions/',
                '/api/plant-identification/treatment-attempts/',
            ],
            'local_search': [
                '/api/plant-identification/search/plants/',
                '/api/plant-identification/search/diseases/',
            ],
            'utilities': [
                '/api/plant-identification/care-instructions/',
                '/api/plant-identification/health/',
                '/api/plant-identification/status/',
            ],
            'plant_enrichment': [
                '/api/plant-identification/enrich-plant-data/',
                '/api/plant-identification/search/species/',
                '/api/plant-identification/species/{id}/characteristics/',
                '/api/plant-identification/species/{id}/growth-info/',
            ]
        }
    })

@api_view(['GET'])
def service_status(request):
    """Check status of external API services."""
    from .services.identification_service import PlantIdentificationService
    
    try:
        service = PlantIdentificationService()
        status = service.get_service_status()
        return Response(status)
    except Exception as e:
        return Response({
            'error': str(e),
            'status': 'error'
        })

# Create router for ViewSets
router = DefaultRouter()
router.register(r'species', views.PlantSpeciesViewSet, basename='species')
router.register(r'requests', views.PlantIdentificationRequestViewSet, basename='requests')
router.register(r'results', views.PlantIdentificationResultViewSet, basename='results')
router.register(r'plants', views.UserPlantViewSet, basename='plants')

# Disease Diagnosis ViewSets
router.register(r'disease-requests', views.PlantDiseaseRequestViewSet, basename='disease-requests')
router.register(r'disease-results', views.PlantDiseaseResultViewSet, basename='disease-results')
router.register(r'disease-database', views.PlantDiseaseDatabaseViewSet, basename='disease-database')
router.register(r'saved-diagnoses', views.SavedDiagnosisViewSet, basename='saved-diagnoses')
router.register(r'saved-care-instructions', views.SavedCareInstructionsViewSet, basename='saved-care-instructions')
router.register(r'treatment-attempts', views.TreatmentAttemptViewSet, basename='treatment-attempts')

urlpatterns = [
    # Simple identification endpoint (dual API integration)
    path('identify/', simple_views.identify_plant, name='simple_identify'),
    path('identify/health/', simple_views.health_check, name='simple_health'),
    
    # Health check
    path('health/', health_check, name='health'),
    path('status/', service_status, name='service_status'),
    
    # Care instructions
    path('care-instructions/', views.get_care_instructions, name='care_instructions_by_name'),
    path('care-instructions/<int:species_id>/', views.get_care_instructions, name='care_instructions'),
    path('results/<int:result_id>/regenerate-care/', views.regenerate_care_instructions, name='regenerate_care_instructions'),
    
    # Local database search endpoints
    path('search/plants/', views.search_local_plants, name='search_local_plants'),
    path('search/diseases/', views.search_local_diseases, name='search_local_diseases'),
    
    # Plant data enrichment endpoints (Trefle API integration)
    path('enrich-plant-data/', views.enrich_plant_data, name='enrich_plant_data'),
    path('search/species/', views.search_plant_species, name='search_plant_species'),
    path('species/<int:species_id>/characteristics/', views.get_plant_characteristics, name='plant_characteristics'),
    path('species/<int:species_id>/growth-info/', views.get_plant_growth_info, name='plant_growth_info'),
    
    # Include ViewSet URLs
    path('', include(router.urls)),
]