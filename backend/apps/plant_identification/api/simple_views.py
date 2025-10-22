"""
Simple API views for plant identification using dual API integration.
These are lightweight endpoints for the React frontend.

Authentication Strategy:
- Development: IsAuthenticatedOrAnonymousWithStrictRateLimit (allows testing)
- Production: IsAuthenticatedForIdentification (requires login)

Rate Limiting:
- Authenticated users: 100 requests/hour
- Anonymous users: 10 requests/hour (development only)
"""

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.conf import settings
import logging

from ..services.combined_identification_service import CombinedPlantIdentificationService
from ..permissions import (
    IsAuthenticatedOrAnonymousWithStrictRateLimit,
    IsAuthenticatedForIdentification,
)

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([
    IsAuthenticatedOrAnonymousWithStrictRateLimit if settings.DEBUG
    else IsAuthenticatedForIdentification
])
@parser_classes([MultiPartParser, FormParser])
@ratelimit(
    key=lambda request: 'anon' if not request.user.is_authenticated else f'user-{request.user.id}',
    rate='10/h' if settings.DEBUG else '100/h',
    method='POST'
)
@transaction.atomic
def identify_plant(request):
    """
    Plant identification endpoint using dual API integration.

    **Authentication:**
    - Development (DEBUG=True): Anonymous users allowed with 10 req/hour limit
    - Production (DEBUG=False): Authentication required with 100 req/hour limit

    **Endpoint:** POST /api/plant-identification/identify/

    **Request:**
    ```
    Content-Type: multipart/form-data

    image: <file>  # Image file (JPEG, PNG, WebP)
    ```

    **Response:**
    ```json
    {
        "success": true,
        "plant_name": "Monstera Deliciosa",
        "scientific_name": "Monstera deliciosa",
        "confidence": 0.95,
        "suggestions": [...],
        "care_instructions": {...},
        "disease_detection": {...}
    }
    ```

    **Rate Limits:**
    - Authenticated: 100 requests/hour
    - Anonymous (dev only): 10 requests/hour
    """
    try:
        # Validate image file
        if 'image' not in request.FILES:
            return Response({
                'success': False,
                'error': 'No image file provided. Please upload an image.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        image_file = request.FILES['image']
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
        if image_file.content_type not in allowed_types:
            return Response({
                'success': False,
                'error': f'Invalid file type: {image_file.content_type}. Allowed types: JPEG, PNG, WebP'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate file size (10MB max)
        max_size = 10 * 1024 * 1024  # 10MB
        if image_file.size > max_size:
            return Response({
                'success': False,
                'error': f'File too large: {image_file.size / 1024 / 1024:.1f}MB. Maximum size: 10MB'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"Processing plant identification request - File: {image_file.name}, Size: {image_file.size / 1024:.1f}KB")
        
        # Initialize combined identification service
        service = CombinedPlantIdentificationService()
        
        # Identify plant using dual API
        results = service.identify_plant(image_file, user=request.user if request.user.is_authenticated else None)
        
        # Check for errors
        if 'error' in results:
            return Response({
                'success': False,
                'error': results['error']
            }, status=status.HTTP_200_OK)  # Return 200 with error message
        
        # Format successful response
        top_suggestion = results['combined_suggestions'][0] if results['combined_suggestions'] else None
        
        response_data = {
            'success': True,
            'plant_name': top_suggestion.get('plant_name') if top_suggestion else 'Unknown',
            'scientific_name': top_suggestion.get('scientific_name') if top_suggestion else '',
            'confidence': results.get('confidence_score', 0),
            'suggestions': results.get('combined_suggestions', []),
            'care_instructions': results.get('care_instructions'),
            'disease_detection': results.get('disease_detection'),
            'summary': service.get_identification_summary(results),
        }
        
        logger.info(f"Identification successful: {response_data['plant_name']} ({response_data['confidence']:.2%})")
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Plant identification error: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': 'An unexpected error occurred during identification. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint to verify API services are available.
    
    GET /api/plant-identification/health/
    """
    try:
        service = CombinedPlantIdentificationService()
        
        return Response({
            'status': 'healthy',
            'plant_id_available': service.plant_id is not None,
            'plantnet_available': service.plantnet is not None,
            'message': 'Plant identification service is ready'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return Response({
            'status': 'unhealthy',
            'error': str(e)
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
