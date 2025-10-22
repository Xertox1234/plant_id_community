"""
URL configuration for simple Plant ID API server
"""

from django.urls import path
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

# Simple test views
@require_http_methods(["GET"])
def health_check(request):
    """Health check endpoint"""
    return JsonResponse({
        'status': 'healthy',
        'message': 'Plant ID API is running',
        'apis': {
            'plant_id': 'configured',
            'plantnet': 'configured'
        }
    })

@csrf_exempt
@require_http_methods(["POST"])
def identify_plant(request):
    """Plant identification endpoint"""
    try:
        if 'image' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No image provided'
            }, status=400)
        
        image = request.FILES['image']
        
        # Import here to avoid path issues
        import sys
        import os
        backend_dir = os.path.dirname(__file__)
        sys.path.insert(0, backend_dir)
        
        from apps.plant_identification.services.combined_identification_service import CombinedPlantIdentificationService
        
        service = CombinedPlantIdentificationService()
        results = service.identify_plant(image)
        
        if 'error' in results:
            return JsonResponse({
                'success': False,
                'error': results['error']
            })
        
        top = results['combined_suggestions'][0] if results['combined_suggestions'] else {}
        
        return JsonResponse({
            'success': True,
            'plant_name': top.get('plant_name', 'Unknown'),
            'scientific_name': top.get('scientific_name', ''),
            'confidence': results.get('confidence_score', 0),
            'suggestions': results.get('combined_suggestions', []),
            'care_instructions': results.get('care_instructions'),
            'disease_detection': results.get('disease_detection'),
            'summary': service.get_identification_summary(results),
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

urlpatterns = [
    path('api/plant-identification/identify/', identify_plant, name='identify'),
    path('api/plant-identification/identify/health/', health_check, name='health'),
]
