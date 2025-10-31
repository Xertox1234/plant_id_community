"""
Django REST API views for plant identification.

These views act as a proxy between the frontend and external APIs (Trefle, PlantNet),
solving CORS issues and providing a unified API interface.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction, models
from django.db.models import F
from django.conf import settings
# Rate limiting - make optional
try:
    from django_ratelimit.decorators import ratelimit
except ImportError:
    # Fallback decorator that does nothing if django-ratelimit is not installed
    def ratelimit(**kwargs):
        def decorator(func):
            return func
        return decorator
import logging

from . import constants
from .models import (
    PlantSpecies, 
    PlantIdentificationRequest, 
    PlantIdentificationResult,
    UserPlant,
    PlantDiseaseRequest,
    PlantDiseaseResult,
    PlantDiseaseDatabase,
    DiseaseCareInstructions,
    SavedDiagnosis,
    SavedCareInstructions,
    TreatmentAttempt
)
from .services.trefle_service import TrefleAPIService
from .services.plantnet_service import PlantNetAPIService
from .services.identification_service import PlantIdentificationService
from .services.disease_diagnosis_service import PlantDiseaseService
from .tasks import run_identification
from .serializers import (
    PlantSpeciesSerializer,
    PlantIdentificationRequestSerializer,
    PlantIdentificationResultSerializer,
    UserPlantSerializer,
    PlantDiseaseRequestSerializer,
    PlantDiseaseRequestCreateSerializer,
    PlantDiseaseResultSerializer,
    PlantDiseaseDatabaseSerializer,
    DiseaseCareInstructionsSerializer,
    SavedDiagnosisSerializer,
    SavedCareInstructionsSerializer,
    TreatmentAttemptSerializer,
    PlantDiseaseRequestWithResultsSerializer
)

logger = logging.getLogger(__name__)


class PlantSpeciesViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for plant species data.
    """
    queryset = PlantSpecies.objects.all()
    serializer_class = PlantSpeciesSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        queryset = PlantSpecies.objects.all()
        
        # Filter by search query
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(scientific_name__icontains=search) |
                models.Q(common_names__icontains=search) |
                models.Q(family__icontains=search)
            )
        
        # Filter by family
        family = self.request.query_params.get('family')
        if family:
            queryset = queryset.filter(family__icontains=family)
        
        return queryset.order_by('scientific_name')
    
    @action(detail=False, methods=['get'])
    def search_external(self, request):
        """
        Search for plants in external APIs (Trefle).
        """
        query = request.query_params.get('q')
        if not query:
            return Response({'error': 'Search query is required'}, status=400)
        
        try:
            trefle_service = TrefleAPIService()
            results = trefle_service.search_plants(query, limit=20)
            
            return Response({
                'results': results,
                'source': 'trefle',
                'query': query
            })
            
        except Exception as e:
            logger.error(f"External plant search failed: {str(e)}")
            return Response(
                {'error': 'External search service temporarily unavailable'}, 
                status=503
            )


class PlantIdentificationRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for plant identification requests.
    This is the main proxy endpoint for plant identification.
    """
    serializer_class = PlantIdentificationRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        return PlantIdentificationRequest.objects.filter(
            user=self.request.user
        ).order_by('-created_at')
    
    @ratelimit(
        key='user',
        rate=constants.RATE_LIMITS['authenticated']['plant_identification'],
        method='POST',
        block=True
    )
    def create(self, request, *args, **kwargs):
        """Create plant identification request with rate limiting."""
        try:
            return super().create(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error creating plant identification request: {e}", exc_info=True)
            raise
    
    def perform_create(self, serializer):
        """Create identification request and trigger async AI processing (Celery)."""
        # Save the request
        request_obj = serializer.save(user=self.request.user)

        # Decide whether to use Celery based on settings; default to synchronous
        use_celery = getattr(settings, 'CELERY_ENABLED', False)

        if use_celery:
            try:
                # Enqueue task for async processing
                run_identification.delay(str(request_obj.request_id))
                logger.info("Enqueued identification task for %s", request_obj.request_id)
            except Exception as e:
                logger.warning(f"Celery enqueue failed, processing synchronously: {str(e)}")
                from .services.identification_service import PlantIdentificationService
                identification_service = PlantIdentificationService()
                identification_service.identify_plant_from_request(request_obj)
        else:
            # Process synchronously when Celery is disabled/not used
            from .services.identification_service import PlantIdentificationService
            identification_service = PlantIdentificationService()
            identification_service.identify_plant_from_request(request_obj)
    
    def retrieve(self, request, pk=None):
        """Get identification request by UUID."""
        try:
            request_obj = get_object_or_404(
                PlantIdentificationRequest,
                request_id=pk,
                user=request.user
            )
            serializer = self.get_serializer(request_obj)
            return Response(serializer.data)
        except ValueError:
            return Response({'error': 'Invalid request ID format'}, status=400)

    @action(detail=True, methods=['get'], url_path='status')
    def status(self, request, pk=None):
        """
        Get processing status for an identification request.
        Returns only lightweight status fields for polling.
        """
        try:
            request_obj = get_object_or_404(
                PlantIdentificationRequest,
                request_id=pk,
                user=request.user
            )
            return Response({
                'request_id': str(request_obj.request_id),
                'status': request_obj.status,
                'processed_by_ai': request_obj.processed_by_ai,
                'updated_at': request_obj.updated_at,
            })
        except ValueError:
            return Response({'error': 'Invalid request ID format'}, status=400)
    
    @action(detail=True, methods=['get'])
    def results(self, request, pk=None):
        """
        Get identification results for a request.
        """
        try:
            request_obj = get_object_or_404(
                PlantIdentificationRequest,
                request_id=pk,
                user=request.user
            )
            
            results = request_obj.identification_results.all().order_by(
                '-confidence_score', '-created_at'
            )
            
            serializer = PlantIdentificationResultSerializer(results, many=True)
            
            return Response({
                'request_id': str(request_obj.request_id),
                'status': request_obj.status,
                'results': serializer.data
            })
            
        except ValueError:
            return Response({'error': 'Invalid request ID format'}, status=400)
    
    @action(detail=True, methods=['post'])
    def process_now(self, request, pk=None):
        """
        Manually trigger processing for a request (for testing).
        """
        try:
            request_obj = get_object_or_404(
                PlantIdentificationRequest,
                request_id=pk,
                user=request.user
            )
            
            if request_obj.status != 'pending':
                return Response(
                    {'error': 'Request has already been processed'}, 
                    status=400
                )
            
            # Process immediately (for testing)
            identification_service = PlantIdentificationService()
            results = identification_service.identify_plant_from_request(request_obj)
            
            # Refresh from database
            request_obj.refresh_from_db()
            serializer = self.get_serializer(request_obj)
            
            return Response({
                'message': 'Processing completed',
                'request': serializer.data,
                'results_count': len(results)
            })
            
        except ValueError:
            return Response({'error': 'Invalid request ID format'}, status=400)
        except Exception as e:
            logger.error(f"Manual processing failed: {str(e)}")
            return Response(
                {'error': 'Processing failed. Please try again.'}, 
                status=500
            )


class PlantIdentificationResultViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for plant identification results.
    """
    serializer_class = PlantIdentificationResultSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return PlantIdentificationResult.objects.filter(
            request__user=self.request.user
        ).order_by('-confidence_score', '-created_at')
    
    @action(detail=True, methods=['post'])
    def vote(self, request, pk=None):
        """
        Vote on an identification result with persistent user vote tracking.
        """
        result_obj = self.get_object()
        vote_type = request.data.get('vote_type')
        
        if vote_type not in ['upvote', 'downvote']:
            return Response({'error': 'Invalid vote type'}, status=400)
        
        if result_obj.is_accepted:
            return Response({'error': 'Cannot vote on accepted results'}, status=400)
        
        from .models import PlantIdentificationVote
        
        with transaction.atomic():
            # Get or create the user's vote
            vote, created = PlantIdentificationVote.objects.get_or_create(
                user=request.user,
                result=result_obj,
                defaults={'vote_type': vote_type}
            )
            
            previous_vote = None
            if not created:
                previous_vote = vote.vote_type
                if previous_vote == vote_type:
                    # User is voting the same way again - remove their vote
                    vote.delete()
                    # Decrease the vote count atomically using F() expressions (prevents race conditions)
                    if vote_type == 'upvote':
                        PlantIdentificationResult.objects.filter(id=result_obj.id).update(
                            upvotes=models.Case(
                                models.When(upvotes__gt=0, then=F('upvotes') - 1),
                                default=0
                            )
                        )
                    else:
                        PlantIdentificationResult.objects.filter(id=result_obj.id).update(
                            downvotes=models.Case(
                                models.When(downvotes__gt=0, then=F('downvotes') - 1),
                                default=0
                            )
                        )
                    # Refresh object from database to get updated values
                    result_obj.refresh_from_db()

                    return Response({
                        'message': f'{vote_type} removed successfully',
                        'result': self.get_serializer(result_obj, context={'request': request}).data
                    })
                else:
                    # User is changing their vote
                    vote.vote_type = vote_type
                    vote.save()

                    # Adjust vote counts atomically using F() expressions (prevents race conditions)
                    if previous_vote == 'upvote':
                        # Decrement upvotes, increment downvotes
                        PlantIdentificationResult.objects.filter(id=result_obj.id).update(
                            upvotes=models.Case(
                                models.When(upvotes__gt=0, then=F('upvotes') - 1),
                                default=0
                            ),
                            downvotes=F('downvotes') + 1
                        )
                    else:
                        # Decrement downvotes, increment upvotes
                        PlantIdentificationResult.objects.filter(id=result_obj.id).update(
                            downvotes=models.Case(
                                models.When(downvotes__gt=0, then=F('downvotes') - 1),
                                default=0
                            ),
                            upvotes=F('upvotes') + 1
                        )
                    # Refresh object from database to get updated values
                    result_obj.refresh_from_db()
                    
                    return Response({
                        'message': f'Vote changed to {vote_type} successfully',
                        'result': self.get_serializer(result_obj, context={'request': request}).data
                    })
            else:
                # New vote - increment the appropriate counter atomically (prevents race conditions)
                if vote_type == 'upvote':
                    PlantIdentificationResult.objects.filter(id=result_obj.id).update(
                        upvotes=F('upvotes') + 1
                    )
                else:
                    PlantIdentificationResult.objects.filter(id=result_obj.id).update(
                        downvotes=F('downvotes') + 1
                    )
                # Refresh object from database to get updated values
                result_obj.refresh_from_db()
                
                return Response({
                    'message': f'Vote {vote_type}d successfully',
                    'result': self.get_serializer(result_obj, context={'request': request}).data
                })
    
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """
        Accept an identification result as correct.
        """
        result_obj = self.get_object()
        
        # Check if user owns the original request
        if result_obj.request.user != request.user:
            return Response({'error': 'Permission denied'}, status=403)
        
        with transaction.atomic():
            # Mark all other results as not accepted
            PlantIdentificationResult.objects.filter(
                request=result_obj.request
            ).update(is_accepted=False)
            
            # Mark this result as accepted and primary
            result_obj.is_accepted = True
            result_obj.is_primary = True
            result_obj.save()
            
            # Update request status
            result_obj.request.status = 'identified'
            result_obj.request.save()
        
        serializer = self.get_serializer(result_obj)
        return Response({
            'message': 'Identification accepted',
            'result': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def add_to_collection(self, request, pk=None):
        """
        Add identified plant to user's collection.
        """
        result_obj = self.get_object()
        
        # Check if user owns the original request
        if result_obj.request.user != request.user:
            return Response({'error': 'Permission denied'}, status=403)
        
        collection_id = request.data.get('collection_id')
        if not collection_id:
            return Response({'error': 'Collection ID is required'}, status=400)
        
        # Get user's collection
        from apps.users.models import UserPlantCollection
        try:
            collection = UserPlantCollection.objects.get(
                id=collection_id,
                user=request.user
            )
        except UserPlantCollection.DoesNotExist:
            return Response({'error': 'Collection not found'}, status=404)
        
        # Check if plant already in collection from this result
        existing_plant = UserPlant.objects.filter(
            collection=collection,
            from_identification_result=result_obj
        ).first()
        
        if existing_plant:
            return Response({
                'message': 'Plant already in collection',
                'plant_id': existing_plant.id
            })
        
        # Create user plant with care instructions
        plant_data = {
            'user': request.user,
            'collection': collection,
            'species': result_obj.identified_species,
            'from_identification_request': result_obj.request,
            'from_identification_result': result_obj,  # Link to specific result
            'nickname': request.data.get('nickname', ''),
            'notes': request.data.get('notes', ''),
            'acquisition_date': timezone.now().date(),
            'care_instructions_json': result_obj.ai_care_instructions or {},  # Include AI care instructions
        }
        
        user_plant = UserPlant.objects.create(**plant_data)
        
        return Response({
            'message': 'Plant added to collection successfully',
            'plant_id': user_plant.id,
            'has_care_instructions': bool(result_obj.ai_care_instructions)
        })


class UserPlantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for user's plant collection.
    """
    serializer_class = UserPlantSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = UserPlant.objects.filter(user=self.request.user)
        
        # Filter by collection
        collection_id = self.request.query_params.get('collection')
        if collection_id:
            queryset = queryset.filter(collection_id=collection_id)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@ratelimit(
    key='user_or_ip',
    rate=constants.RATE_LIMITS['authenticated']['care_instructions'],
    method='GET',
    block=True
)
def get_care_instructions(request, species_id=None):
    """
    Get care instructions for a plant species.
    Can be called with either species_id parameter or scientific_name query param.
    """
    try:
        if species_id:
            # Get care instructions by species ID
            try:
                species = PlantSpecies.objects.get(id=species_id)
            except PlantSpecies.DoesNotExist:
                return Response({'error': 'Plant species not found'}, status=404)
        else:
            # Get care instructions by scientific name
            scientific_name = request.query_params.get('scientific_name')
            if not scientific_name:
                return Response({
                    'error': 'Either species_id parameter or scientific_name query parameter is required'
                }, status=400)
            
            try:
                species = PlantSpecies.objects.get(scientific_name__iexact=scientific_name)
            except PlantSpecies.DoesNotExist:
                return Response({
                    'error': f'Plant species "{scientific_name}" not found in our database'
                }, status=404)
        
        # Generate care instructions based on species data
        care_instructions = _generate_care_instructions(species)
        
        return Response({
            'plant': {
                'id': species.id,
                'scientific_name': species.scientific_name,
                'common_names': species.common_names_list,
                'family': species.family,
            },
            'care_instructions': care_instructions
        })
        
    except Exception as e:
        logger.error(f"Error getting care instructions: {str(e)}")
        return Response({
            'error': 'Unable to retrieve care instructions'
        }, status=500)


def _generate_care_instructions(species: PlantSpecies) -> dict:
    """
    Generate comprehensive care instructions based on species data.
    """
    instructions = {
        'overview': f"Care guide for {species.display_name}",
        'basic_info': {
            'scientific_name': species.scientific_name,
            'common_names': species.common_names_list,
            'family': species.family,
            'plant_type': species.get_plant_type_display() if species.plant_type else 'Unknown',
        }
    }
    
    # Light requirements
    if species.light_requirements:
        light_guide = {
            'full_sun': {
                'requirement': 'Full Sun (6+ hours direct sunlight daily)',
                'placement': 'Place in south-facing windows or outdoors in direct sunlight',
                'tips': 'Ideal for patios, gardens, or very bright indoor spaces'
            },
            'partial_sun': {
                'requirement': 'Partial Sun (4-6 hours direct sunlight daily)',
                'placement': 'East or west-facing windows work well',
                'tips': 'Morning sun is usually preferable to harsh afternoon sun'
            },
            'partial_shade': {
                'requirement': 'Partial Shade (2-4 hours direct sun, bright indirect light)',
                'placement': 'North-facing windows or filtered light through curtains',
                'tips': 'Avoid direct afternoon sun which can scorch leaves'
            },
            'full_shade': {
                'requirement': 'Full Shade (Bright indirect light, no direct sun)',
                'placement': 'Indoor locations away from windows, or shaded outdoor areas',
                'tips': 'Perfect for offices or rooms with limited natural light'
            }
        }
        
        instructions['light'] = light_guide.get(species.light_requirements, {
            'requirement': f'{species.get_light_requirements_display()}',
            'placement': 'Adjust placement based on your plant\'s specific needs',
            'tips': 'Monitor your plant for signs of too much or too little light'
        })
    
    # Watering requirements
    if species.water_requirements:
        water_guide = {
            'low': {
                'frequency': 'Water sparingly - every 2-3 weeks',
                'method': 'Allow soil to dry completely between waterings',
                'signs': 'Look for slightly wrinkled or drooping leaves as watering cues',
                'tips': 'Better to underwater than overwater. These plants store water in their tissues.'
            },
            'moderate': {
                'frequency': 'Water when top 1-2 inches of soil feels dry (usually weekly)',
                'method': 'Water thoroughly until water drains from bottom holes',
                'signs': 'Soil should feel like a wrung-out sponge',
                'tips': 'Consistency is key - try to water on a regular schedule'
            },
            'high': {
                'frequency': 'Keep soil consistently moist but not waterlogged',
                'method': 'Water every 2-3 days, checking soil daily',
                'signs': 'Soil should never completely dry out',
                'tips': 'Consider using a humidity tray or humidifier for extra moisture'
            }
        }
        
        instructions['watering'] = water_guide.get(species.water_requirements, {
            'frequency': f'{species.get_water_requirements_display()} water requirements',
            'method': 'Adjust watering based on your plant\'s response',
            'signs': 'Watch for wilting, yellowing, or dropping leaves',
            'tips': 'Environmental factors like humidity and temperature affect watering needs'
        })
    
    # Size and growth information
    if species.mature_height_min or species.mature_height_max:
        size_info = []
        if species.mature_height_min and species.mature_height_max:
            size_info.append(f"Mature height: {species.mature_height_min}m - {species.mature_height_max}m")
        elif species.mature_height_max:
            size_info.append(f"Can grow up to {species.mature_height_max}m tall")
        elif species.mature_height_min:
            size_info.append(f"Grows at least {species.mature_height_min}m tall")
        
        if species.growth_habit:
            size_info.append(f"Growth habit: {species.growth_habit}")
        
        instructions['size_and_growth'] = {
            'mature_size': size_info,
            'tips': 'Prune regularly to maintain desired size and shape'
        }
    
    # Soil and pH requirements
    soil_info = []
    if species.soil_ph_min or species.soil_ph_max:
        if species.soil_ph_min and species.soil_ph_max:
            soil_info.append(f"Soil pH: {species.soil_ph_min} - {species.soil_ph_max}")
        elif species.soil_ph_max:
            soil_info.append(f"Soil pH up to {species.soil_ph_max}")
        elif species.soil_ph_min:
            soil_info.append(f"Soil pH from {species.soil_ph_min}")
    
    if soil_info:
        instructions['soil'] = {
            'requirements': soil_info,
            'tips': 'Use well-draining potting mix appropriate for your plant type'
        }
    
    # Climate information
    if species.hardiness_zone_min or species.hardiness_zone_max:
        climate_info = []
        if species.hardiness_zone_min and species.hardiness_zone_max:
            climate_info.append(f"USDA Hardiness Zones: {species.hardiness_zone_min} - {species.hardiness_zone_max}")
        elif species.hardiness_zone_max:
            climate_info.append(f"USDA Hardiness Zone up to {species.hardiness_zone_max}")
        elif species.hardiness_zone_min:
            climate_info.append(f"USDA Hardiness Zone {species.hardiness_zone_min} and above")
        
        instructions['climate'] = {
            'hardiness': climate_info,
            'indoor_tips': 'If growing indoors, maintain temperatures between 65-75°F (18-24°C)'
        }
    
    # Additional information
    additional_tips = []
    
    if species.bloom_time:
        additional_tips.append(f"Blooming period: {species.bloom_time}")
    
    if species.flower_color:
        additional_tips.append(f"Flower colors: {species.flower_color}")
    
    if species.native_regions:
        additional_tips.append(f"Native to: {species.native_regions}")
    
    if additional_tips:
        instructions['additional_info'] = additional_tips
    
    # General care tips
    instructions['general_tips'] = [
        "Monitor your plant regularly for changes in leaves, growth, and overall health",
        "Adjust care based on seasonal changes - plants need less water and fertilizer in winter",
        "Provide good air circulation to prevent fungal issues",
        "Fertilize during growing season (spring/summer) with appropriate plant food",
        "Repot when roots become crowded, usually every 1-2 years for houseplants"
    ]
    
    # Common problems and solutions
    instructions['troubleshooting'] = {
        'yellowing_leaves': 'Often indicates overwatering or nutrient deficiency',
        'brown_leaf_tips': 'Usually caused by low humidity or fluoride in tap water',
        'dropping_leaves': 'Can indicate stress from changes in light, water, or temperature',
        'slow_growth': 'May need more light, nutrients, or larger pot',
        'pests': 'Check regularly for spider mites, aphids, or scale insects'
    }
    
    return instructions


# =============================================================================
# Disease Diagnosis ViewSets
# =============================================================================

class PlantDiseaseRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for plant disease diagnosis requests.
    Handles image-based disease identification with plant.health API integration.
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        return PlantDiseaseRequest.objects.filter(
            user=self.request.user
        ).order_by('-created_at')
    
    def get_serializer_class(self):
        """Return different serializers based on the action."""
        if self.action == 'create':
            return PlantDiseaseRequestCreateSerializer
        elif self.action == 'list':
            return PlantDiseaseRequestWithResultsSerializer
        return PlantDiseaseRequestSerializer
    
    @method_decorator(ratelimit(key='user', rate='5/m', method='POST', block=True))  # 5 disease diagnosis requests per minute per user
    def create(self, request, *args, **kwargs):
        """Create disease diagnosis request with rate limiting."""
        return super().create(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        """Create disease diagnosis request and trigger AI processing."""
        # Save the request
        request_obj = serializer.save(user=self.request.user)

        # TODO: Enqueue Celery task for async processing
        # For now, process synchronously to get immediate results
        try:
            disease_service = PlantDiseaseService()
            results = disease_service.diagnose_disease_from_request(request_obj)
            logger.info(f"Processed disease diagnosis for {request_obj.request_id}, found {len(results)} results")
        except Exception as e:
            logger.error(f"Failed to process disease diagnosis: {str(e)}")
            # Set status to failed but don't raise exception - request is still created
            request_obj.status = 'failed'
            request_obj.save()
    
    def retrieve(self, request, pk=None):
        """Get disease diagnosis request by UUID."""
        try:
            request_obj = get_object_or_404(
                PlantDiseaseRequest,
                request_id=pk,
                user=request.user
            )
            serializer = self.get_serializer(request_obj)
            return Response(serializer.data)
        except ValueError:
            return Response({'error': 'Invalid request ID format'}, status=400)

    @action(detail=True, methods=['get'], url_path='status')
    def status(self, request, pk=None):
        """Get processing status for a disease diagnosis request."""
        try:
            request_obj = get_object_or_404(
                PlantDiseaseRequest,
                request_id=pk,
                user=request.user
            )
            return Response({
                'request_id': str(request_obj.request_id),
                'status': request_obj.status,
                'processed_by_ai': request_obj.processed_by_ai,
                'updated_at': request_obj.updated_at,
            })
        except ValueError:
            return Response({'error': 'Invalid request ID format'}, status=400)
    
    @action(detail=True, methods=['get'])
    def results(self, request, pk=None):
        """Get disease diagnosis results for a request."""
        try:
            request_obj = get_object_or_404(
                PlantDiseaseRequest,
                request_id=pk,
                user=request.user
            )
            
            results = request_obj.diagnosis_results.all().order_by(
                '-confidence_score', '-created_at'
            )
            
            serializer = PlantDiseaseResultSerializer(results, many=True)
            
            return Response({
                'request_id': str(request_obj.request_id),
                'status': request_obj.status,
                'results': serializer.data
            })
            
        except ValueError:
            return Response({'error': 'Invalid request ID format'}, status=400)
    
    @action(detail=True, methods=['post'])
    def process_now(self, request, pk=None):
        """Manually trigger disease diagnosis processing (for testing)."""
        try:
            request_obj = get_object_or_404(
                PlantDiseaseRequest,
                request_id=pk,
                user=request.user
            )
            
            if request_obj.status not in ['pending', 'failed']:
                return Response(
                    {'error': 'Request has already been processed'}, 
                    status=400
                )
            
            # Process immediately
            disease_service = PlantDiseaseService()
            results = disease_service.diagnose_disease_from_request(request_obj)
            
            # Refresh from database
            request_obj.refresh_from_db()
            serializer = self.get_serializer(request_obj)
            
            return Response({
                'message': 'Disease diagnosis processing completed',
                'request': serializer.data,
                'results_count': len(results)
            })
            
        except ValueError:
            return Response({'error': 'Invalid request ID format'}, status=400)
        except Exception as e:
            logger.error(f"Manual disease diagnosis processing failed: {str(e)}")
            return Response(
                {'error': 'Processing failed. Please try again.'}, 
                status=500
            )


class PlantDiseaseResultViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for plant disease diagnosis results.
    Includes voting, treatment tracking, and community features.
    """
    serializer_class = PlantDiseaseResultSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return PlantDiseaseResult.objects.filter(
            request__user=self.request.user
        ).order_by('-confidence_score', '-created_at')
    
    @action(detail=True, methods=['post'])
    def vote(self, request, pk=None):
        """Vote on a disease diagnosis result."""
        result_obj = self.get_object()
        vote_type = request.data.get('vote_type')
        
        if vote_type not in ['upvote', 'downvote']:
            return Response({'error': 'Invalid vote type'}, status=400)
        
        # TODO: Implement proper voting system with user tracking to prevent duplicate votes
        # Use atomic F() expressions to prevent race conditions
        if vote_type == 'upvote':
            PlantDiseaseResult.objects.filter(id=result_obj.id).update(
                upvotes=F('upvotes') + 1
            )
        else:
            PlantDiseaseResult.objects.filter(id=result_obj.id).update(
                downvotes=F('downvotes') + 1
            )

        # Refresh object from database to get updated values
        result_obj.refresh_from_db()
        
        serializer = self.get_serializer(result_obj)
        return Response({
            'message': f'Vote {vote_type}d successfully',
            'result': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Accept a disease diagnosis result as correct."""
        result_obj = self.get_object()
        
        # Check if user owns the original request
        if result_obj.request.user != request.user:
            return Response({'error': 'Permission denied'}, status=403)
        
        with transaction.atomic():
            # Mark all other results as not accepted
            PlantDiseaseResult.objects.filter(
                request=result_obj.request
            ).update(is_accepted=False)
            
            # Mark this result as accepted and primary
            result_obj.is_accepted = True
            result_obj.is_primary = True
            result_obj.save()
            
            # Update request status
            result_obj.request.status = 'diagnosed'
            result_obj.request.save()
        
        serializer = self.get_serializer(result_obj)
        return Response({
            'message': 'Disease diagnosis accepted',
            'result': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def save_to_profile(self, request, pk=None):
        """Save disease diagnosis to user's saved diagnoses."""
        result_obj = self.get_object()
        
        # Check if user owns the original request
        if result_obj.request.user != request.user:
            return Response({'error': 'Permission denied'}, status=403)
        
        # Check if already saved
        if SavedDiagnosis.objects.filter(user=request.user, diagnosis_result=result_obj).exists():
            return Response({'message': 'Diagnosis already saved to your profile'})
        
        # Create saved diagnosis
        saved_diagnosis = SavedDiagnosis.objects.create(
            user=request.user,
            diagnosis_result=result_obj,
            notes=request.data.get('notes', ''),
            treatment_plan=request.data.get('treatment_plan', ''),
            is_private=request.data.get('is_private', True)
        )
        
        return Response({
            'message': 'Disease diagnosis saved to your profile',
            'saved_diagnosis_id': saved_diagnosis.id
        })
    
    @action(detail=True, methods=['get'])
    def treatment_attempts(self, request, pk=None):
        """Get treatment attempts for this diagnosis result."""
        result_obj = self.get_object()
        
        # Check if user owns the original request
        if result_obj.request.user != request.user:
            return Response({'error': 'Permission denied'}, status=403)
        
        attempts = TreatmentAttempt.objects.filter(
            diagnosis_result=result_obj,
            user=request.user
        ).order_by('-created_at')
        
        serializer = TreatmentAttemptSerializer(attempts, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_treatment_attempt(self, request, pk=None):
        """Add a treatment attempt for this diagnosis result."""
        result_obj = self.get_object()
        
        # Check if user owns the original request
        if result_obj.request.user != request.user:
            return Response({'error': 'Permission denied'}, status=403)
        
        # Validate required fields
        treatment_name = request.data.get('treatment_name')
        if not treatment_name:
            return Response({'error': 'Treatment name is required'}, status=400)
        
        # Create treatment attempt
        attempt = TreatmentAttempt.objects.create(
            user=request.user,
            diagnosis_result=result_obj,
            treatment_name=treatment_name,
            treatment_type=request.data.get('treatment_type', 'other'),
            application_method=request.data.get('application_method', ''),
            dosage_frequency=request.data.get('dosage_frequency', ''),
            notes=request.data.get('notes', ''),
            expected_duration=request.data.get('expected_duration', '')
        )
        
        serializer = TreatmentAttemptSerializer(attempt)
        return Response({
            'message': 'Treatment attempt recorded',
            'treatment_attempt': serializer.data
        })


class PlantDiseaseDatabaseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for browsing the plant disease database.
    Shows diseases that have been auto-stored from high-confidence diagnoses.
    """
    queryset = PlantDiseaseDatabase.objects.filter(diagnosis_count__gte=1).order_by('-diagnosis_count', '-confidence_score')
    serializer_class = PlantDiseaseDatabaseSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        queryset = self.queryset
        
        # Filter by disease type
        disease_type = self.request.query_params.get('type')
        if disease_type:
            queryset = queryset.filter(disease_type=disease_type)
        
        # Search by disease name
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(disease_name__icontains=search)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def disease_types(self, request):
        """Get available disease types with counts."""
        from django.db.models import Count, F
        
        types = PlantDiseaseDatabase.objects.values('disease_type').annotate(
            count=Count('id'),
            avg_confidence=models.Avg('confidence_score')
        ).order_by('-count')
        
        return Response({
            'disease_types': types,
            'total_diseases': PlantDiseaseDatabase.objects.count()
        })
    
    @action(detail=True, methods=['get'])
    def care_instructions(self, request, pk=None):
        """Get care instructions for a specific disease."""
        disease = self.get_object()
        
        instructions = DiseaseCareInstructions.objects.filter(
            disease=disease
        ).order_by('-effectiveness_score', '-created_at')
        
        serializer = DiseaseCareInstructionsSerializer(instructions, many=True)
        return Response({
            'disease': PlantDiseaseDatabaseSerializer(disease).data,
            'care_instructions': serializer.data
        })


class SavedDiagnosisViewSet(viewsets.ModelViewSet):
    """
    ViewSet for user's saved disease diagnoses.
    Personal collection of diagnosed diseases and treatments.
    """
    serializer_class = SavedDiagnosisSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return SavedDiagnosis.objects.filter(
            user=self.request.user
        ).order_by('-saved_at')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SavedCareInstructionsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for user's saved care instruction cards.
    Personal collection of plant care guides and tracking.
    """
    serializer_class = SavedCareInstructionsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return SavedCareInstructions.objects.filter(
            user=self.request.user
        ).order_by('-saved_at')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    def retrieve(self, request, *args, **kwargs):
        """Update last viewed when retrieving a care card."""
        instance = self.get_object()
        instance.update_last_viewed()
        return super().retrieve(request, *args, **kwargs)


class TreatmentAttemptViewSet(viewsets.ModelViewSet):
    """
    ViewSet for tracking treatment attempts.
    Allows users to log and track their treatment experiences.
    """
    serializer_class = TreatmentAttemptSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return TreatmentAttempt.objects.filter(
            user=self.request.user
        ).order_by('-created_at')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def update_effectiveness(self, request, pk=None):
        """Update the effectiveness rating of a treatment attempt."""
        attempt = self.get_object()
        
        effectiveness = request.data.get('effectiveness')
        if effectiveness not in ['very_effective', 'effective', 'somewhat_effective', 'not_effective']:
            return Response({'error': 'Invalid effectiveness rating'}, status=400)
        
        attempt.effectiveness = effectiveness
        attempt.completed = True
        attempt.completion_notes = request.data.get('completion_notes', '')
        attempt.save()
        
        serializer = self.get_serializer(attempt)
        return Response({
            'message': 'Treatment effectiveness updated',
            'treatment_attempt': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def vote(self, request, pk=None):
        """Vote on whether a treatment attempt was helpful."""
        attempt = self.get_object()
        
        # Users can't vote on their own treatments
        if attempt.user == request.user:
            return Response({'error': 'Cannot vote on your own treatment'}, status=400)
        
        is_helpful = request.data.get('is_helpful')
        if is_helpful is None:
            return Response({'error': 'is_helpful field is required'}, status=400)
        
        # For now, we'll just return success - you can implement actual voting logic
        # by adding a TreatmentVote model if needed for detailed tracking
        serializer = self.get_serializer(attempt)
        return Response({
            'message': 'Vote recorded',
            'treatment_attempt': serializer.data
        })


# =============================================================================
# Local Database Search API Endpoints
# =============================================================================

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticatedOrReadOnly])
@ratelimit(
    key='user_or_ip',
    rate=constants.RATE_LIMITS['authenticated']['search'],
    method='GET',
    block=True
)
def search_local_plants(request):
    """
    Search local plant database for cost-effective lookups.
    Includes auto-stored plants with ≥50% confidence from previous identifications.
    """
    query = request.query_params.get('q', '').strip()
    if not query:
        return Response({'error': 'Search query (q) is required'}, status=400)
    
    try:
        # Search auto-stored plants first (highest priority)
        auto_stored = PlantSpecies.objects.filter(
            auto_stored=True,
            scientific_name__icontains=query
        ).order_by('-identification_count', '-confidence_score')[:10]
        
        # Search all plants if we need more results
        all_plants = PlantSpecies.objects.filter(
            models.Q(scientific_name__icontains=query) |
            models.Q(common_names__icontains=query)
        ).exclude(
            id__in=auto_stored.values_list('id', flat=True)
        ).order_by('-identification_count', 'scientific_name')[:10]
        
        # Combine results
        results = list(auto_stored) + list(all_plants)
        
        serializer = PlantSpeciesSerializer(results[:20], many=True, context={'request': request})
        
        return Response({
            'results': serializer.data,
            'total': len(results),
            'auto_stored_count': len(auto_stored),
            'search_query': query,
            'source': 'local_database'
        })
        
    except Exception as e:
        logger.error(f"Local plant search failed: {str(e)}")
        return Response({'error': 'Search temporarily unavailable'}, status=500)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticatedOrReadOnly])
@ratelimit(
    key='user_or_ip',
    rate=constants.RATE_LIMITS['authenticated']['search'],
    method='GET',
    block=True
)
def search_local_diseases(request):
    """
    Search local disease database for cost-effective disease diagnosis.
    Includes diseases auto-stored from ≥50% confidence diagnoses.
    """
    query = request.query_params.get('q', '').strip()
    disease_type = request.query_params.get('type', '').strip()
    
    if not query:
        return Response({'error': 'Search query (q) is required'}, status=400)
    
    try:
        # Build query
        queryset = PlantDiseaseDatabase.objects.filter(
            disease_name__icontains=query
        )
        
        # Filter by disease type if provided
        if disease_type:
            queryset = queryset.filter(disease_type=disease_type)
        
        # Order by diagnosis count and confidence
        results = queryset.order_by('-diagnosis_count', '-confidence_score')[:15]
        
        serializer = PlantDiseaseDatabaseSerializer(results, many=True)
        
        return Response({
            'results': serializer.data,
            'total': len(results),
            'search_query': query,
            'disease_type_filter': disease_type,
            'source': 'local_database'
        })
        
    except Exception as e:
        logger.error(f"Local disease search failed: {str(e)}")
        return Response({'error': 'Disease search temporarily unavailable'}, status=500)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticatedOrReadOnly])
@ratelimit(
    key='user_or_ip',
    rate=constants.RATE_LIMITS['authenticated']['read_only'],
    method='GET',
    block=True
)
def enrich_plant_data(request):
    """
    Enrich plant data using Trefle API for comprehensive botanical information.
    Provides family information, growth requirements, characteristics, and native habitat.
    """
    scientific_name = request.query_params.get('scientific_name', '').strip()
    
    if not scientific_name:
        return Response({'error': 'scientific_name parameter is required'}, status=400)
    
    try:
        # Initialize Trefle service
        trefle_service = TrefleAPIService()
        
        # Get species data by scientific name
        species_data = trefle_service.get_species_by_scientific_name(scientific_name)
        if not species_data:
            return Response({'error': 'Plant species not found in botanical database'}, status=404)
        
        # Get detailed species information
        species_id = species_data.get('id')
        if species_id:
            detailed_data = trefle_service.get_species_details(species_id)
            if detailed_data:
                species_data = detailed_data
        
        # Extract and format enhanced information
        main_species = species_data.get('main_species', {})
        specs = main_species.get('specifications', {})
        
        enriched_data = {
            'scientific_name': species_data.get('scientific_name', scientific_name),
            'family': main_species.get('family', ''),
            'family_description': f"Member of the {main_species.get('family', '')} family" if main_species.get('family') else '',
            'plant_type': specs.get('growth_form', {}).get('type', ''),
            'growth_habit': specs.get('growth_habit', {}).get('type', ''),
            'care_requirements': {
                'light': trefle_service._map_light_requirements(specs.get('light', {}).get('type')),
                'water': trefle_service._map_water_requirements(specs.get('atmospheric_humidity', {}).get('type')),
                'temperature': f"Hardy in zones {specs.get('minimum_temperature', {}).get('deg_f', {}).get('min', 'N/A')} to {specs.get('maximum_temperature', {}).get('deg_f', {}).get('max', 'N/A')}" if specs.get('minimum_temperature') else ''
            },
            'native_habitat': ', '.join(main_species.get('distribution', {}).get('native', [])),
            'distribution': ', '.join(main_species.get('distribution', {}).get('introduced', [])) if main_species.get('distribution', {}).get('introduced') else '',
            'interesting_facts': f"This {species_data.get('scientific_name', 'plant')} is native to {', '.join(main_species.get('distribution', {}).get('native', [])[:3])} and belongs to the {main_species.get('family', '')} family." if main_species.get('distribution', {}).get('native') else '',
            'trefle_id': str(species_data.get('id', '')),
            'image_url': main_species.get('image_url'),
            'source': 'trefle_botanical_database'
        }
        
        # Clean up empty values
        enriched_data = {k: v for k, v in enriched_data.items() if v}
        
        return Response(enriched_data)
        
    except Exception as e:
        logger.error(f"Plant data enrichment failed for {scientific_name}: {str(e)}")
        return Response({'error': 'Failed to enrich plant data'}, status=500)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticatedOrReadOnly])
@ratelimit(
    key='user_or_ip',
    rate=constants.RATE_LIMITS['authenticated']['search'],
    method='GET',
    block=True
)
def search_plant_species(request):
    """
    Search plant species using Trefle API for autocomplete and species lookup.
    """
    query = request.query_params.get('q', '').strip()
    limit = min(int(request.query_params.get('limit', 20)), 50)
    
    if not query:
        return Response({'error': 'Search query (q) is required'}, status=400)
    
    try:
        trefle_service = TrefleAPIService()
        results = trefle_service.search_plants(query, limit=limit)
        
        # Format results for frontend consumption
        formatted_results = []
        for plant in results:
            formatted_results.append({
                'id': plant.get('id'),
                'scientific_name': plant.get('scientific_name', ''),
                'common_names': ', '.join(plant.get('common_names', {}).get('en', [])),
                'family': plant.get('main_species', {}).get('family', ''),
                'genus': plant.get('main_species', {}).get('genus', ''),
                'image_url': plant.get('main_species', {}).get('image_url'),
                'trefle_id': str(plant.get('id', ''))
            })
        
        return Response({
            'results': formatted_results,
            'total': len(formatted_results),
            'query': query,
            'source': 'trefle_api'
        })
        
    except Exception as e:
        logger.error(f"Plant species search failed for '{query}': {str(e)}")
        return Response({'error': 'Species search temporarily unavailable'}, status=500)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticatedOrReadOnly])
@ratelimit(
    key='user_or_ip',
    rate=constants.RATE_LIMITS['authenticated']['read_only'],
    method='GET',
    block=True
)
def get_plant_characteristics(request, species_id):
    """
    Get detailed plant characteristics for a specific species.
    """
    try:
        # Try to get from local database first
        try:
            species = PlantSpecies.objects.get(id=species_id)
            characteristics = {
                'mature_height': f"{species.mature_height_min} - {species.mature_height_max} cm" if species.mature_height_min and species.mature_height_max else '',
                'mature_width': f"{species.mature_width_min} - {species.mature_width_max} cm" if species.mature_width_min and species.mature_width_max else '',
                'flower_color': species.flower_color or '',
                'bloom_time': species.bloom_time or '',
                'plant_type': species.plant_type or '',
                'source': 'local_database'
            }
            return Response(characteristics)
        except PlantSpecies.DoesNotExist:
            pass
        
        # Fallback to Trefle API if not in local database
        trefle_service = TrefleAPIService()
        species_data = trefle_service.get_species_details(species_id)
        
        if not species_data:
            return Response({'error': 'Species not found'}, status=404)
        
        specs = species_data.get('main_species', {}).get('specifications', {})
        characteristics = {
            'mature_height': f"{specs.get('mature_height', {}).get('cm', {}).get('min', 'N/A')} - {specs.get('mature_height', {}).get('cm', {}).get('max', 'N/A')} cm" if specs.get('mature_height') else '',
            'mature_width': f"{specs.get('mature_width', {}).get('cm', {}).get('min', 'N/A')} - {specs.get('mature_width', {}).get('cm', {}).get('max', 'N/A')} cm" if specs.get('mature_width') else '',
            'flower_color': specs.get('flower_color', {}).get('type', ''),
            'bloom_time': specs.get('bloom_months', {}).get('type', ''),
            'plant_type': specs.get('growth_form', {}).get('type', ''),
            'source': 'trefle_api'
        }
        
        return Response(characteristics)
        
    except Exception as e:
        logger.error(f"Failed to get plant characteristics for species {species_id}: {str(e)}")
        return Response({'error': 'Failed to retrieve plant characteristics'}, status=500)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticatedOrReadOnly])
@ratelimit(
    key='user_or_ip',
    rate=constants.RATE_LIMITS['authenticated']['read_only'],
    method='GET',
    block=True
)
def get_plant_growth_info(request, species_id):
    """
    Get growth information and care requirements for a specific species.
    """
    try:
        # Try to get from local database first
        try:
            species = PlantSpecies.objects.get(id=species_id)
            growth_info = {
                'light_requirements': species.get_light_requirements_display() if species.light_requirements else '',
                'water_requirements': species.get_water_requirements_display() if species.water_requirements else '',
                'temperature_range': f"Hardy zones {species.hardiness_zone_min} - {species.hardiness_zone_max}" if species.hardiness_zone_min and species.hardiness_zone_max else '',
                'soil_ph': f"pH {species.soil_ph_min} - {species.soil_ph_max}" if species.soil_ph_min and species.soil_ph_max else '',
                'source': 'local_database'
            }
            return Response(growth_info)
        except PlantSpecies.DoesNotExist:
            pass
        
        # Fallback to Trefle API
        trefle_service = TrefleAPIService()
        species_data = trefle_service.get_species_details(species_id)
        
        if not species_data:
            return Response({'error': 'Species not found'}, status=404)
        
        specs = species_data.get('main_species', {}).get('specifications', {})
        growth_info = {
            'light_requirements': trefle_service._map_light_requirements(specs.get('light', {}).get('type')),
            'water_requirements': trefle_service._map_water_requirements(specs.get('atmospheric_humidity', {}).get('type')),
            'temperature_range': f"Min: {specs.get('minimum_temperature', {}).get('deg_f', {}).get('min', 'N/A')}°F, Max: {specs.get('maximum_temperature', {}).get('deg_f', {}).get('max', 'N/A')}°F" if specs.get('minimum_temperature') else '',
            'soil_ph': f"pH {specs.get('soil_ph', {}).get('min', 'N/A')} - {specs.get('soil_ph', {}).get('max', 'N/A')}" if specs.get('soil_ph') else '',
            'source': 'trefle_api'
        }
        
        return Response(growth_info)
        
    except Exception as e:
        logger.error(f"Failed to get growth info for species {species_id}: {str(e)}")
        return Response({'error': 'Failed to retrieve growth information'}, status=500)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@ratelimit(
    key='user_or_ip',
    rate=constants.RATE_LIMITS['authenticated']['regenerate'],
    method='POST',
    block=True
)
def regenerate_care_instructions(request, result_id):
    """
    Regenerate AI care instructions for a specific identification result.
    """
    try:
        # Get the identification result
        result_obj = get_object_or_404(
            PlantIdentificationResult.objects.select_related('request', 'identified_species'),
            id=result_id
        )
        
        # Check permissions - user must own the original request
        if result_obj.request.user != request.user:
            return Response({'error': 'Permission denied'}, status=403)
        
        # Initialize AI care service
        from .services.ai_care_service import AIPlantCareService
        ai_care_service = AIPlantCareService()
        
        if not ai_care_service:
            return Response({'error': 'AI care service not available'}, status=503)
        
        # Prepare plant information
        scientific_name = result_obj.suggested_scientific_name or (
            result_obj.identified_species.scientific_name if result_obj.identified_species else ''
        )
        common_names = result_obj.suggested_common_name or (
            result_obj.identified_species.common_names if result_obj.identified_species else ''
        )
        
        if not scientific_name:
            return Response({'error': 'No plant name available for care instruction generation'}, status=400)
        
        # Get user context
        location = result_obj.request.location if result_obj.request else ''
        experience = request.user.gardening_experience if hasattr(request.user, 'gardening_experience') else 'beginner'
        
        # Generate new care instructions
        logger.info(f"Regenerating care instructions for result {result_id} - {scientific_name}")
        care_instructions = ai_care_service.generate_care_instructions(
            plant_name=scientific_name,
            common_names=common_names,
            location=location,
            experience_level=experience
        )
        
        if not care_instructions:
            return Response({'error': 'Failed to generate care instructions'}, status=500)
        
        # Update the result with new care instructions
        ai_care_service.update_result_with_care_instructions(result_obj, care_instructions)
        
        # Return the updated result
        serializer = PlantIdentificationResultSerializer(result_obj)
        
        return Response({
            'message': 'Care instructions regenerated successfully',
            'result': serializer.data,
            'care_instructions': care_instructions
        })
        
    except Exception as e:
        logger.error(f"Failed to regenerate care instructions for result {result_id}: {str(e)}")
        return Response({'error': 'Failed to regenerate care instructions'}, status=500)
