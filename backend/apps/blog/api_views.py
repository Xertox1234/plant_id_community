"""
Blog API views for block auto-population and plant data integration.

This module provides API endpoints for Wagtail admin to auto-populate
block fields with plant data from various sources.
"""

import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
# CSRF protection enabled for all admin endpoints - removed csrf_exempt for security
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views import View
from django.core.cache import cache
import json

from .services import BlockAutoPopulationService

logger = logging.getLogger(__name__)


@method_decorator(staff_member_required, name='dispatch')
class PlantLookupView(View):
    """
    API view for plant data lookup and block auto-population.
    
    This view handles AJAX requests from Wagtail admin interface
    to auto-populate block fields based on plant names.
    """
    
    def __init__(self):
        super().__init__()
        self.auto_population_service = BlockAutoPopulationService()
    
    def post(self, request):
        """
        Handle plant lookup requests.
        
        Expected POST data:
        {
            "query": "plant name or scientific name",
            "block_type": "plant_spotlight" or "care_instructions",
            "cache_duration": 300 (optional, seconds)
        }
        """
        try:
            data = json.loads(request.body)
            query = data.get('query', '').strip()
            block_type = data.get('block_type', '')
            cache_duration = data.get('cache_duration', 300)  # 5 minutes default
            
            if not query:
                return JsonResponse({
                    'success': False,
                    'error': 'Plant name/query is required'
                }, status=400)
            
            if block_type not in ['plant_spotlight', 'care_instructions']:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid block type. Must be "plant_spotlight" or "care_instructions"'
                }, status=400)
            
            # Check cache first
            cache_key = f"plant_lookup_{block_type}_{query.lower().replace(' ', '_')}"
            cached_result = cache.get(cache_key)
            
            if cached_result:
                logger.info(f"Returning cached result for query: {query}")
                cached_result['cached'] = True
                return JsonResponse(cached_result)
            
            # Get user context
            user = request.user if request.user.is_authenticated else None
            
            # Perform lookup based on block type
            if block_type == 'plant_spotlight':
                result = self.auto_population_service.populate_plant_spotlight_fields(query, user)
            else:  # care_instructions
                result = self.auto_population_service.populate_care_instructions_fields(query, user)
            
            # Cache successful results
            if result.get('success'):
                cache.set(cache_key, result, cache_duration)
                logger.info(f"Cached result for query: {query}")
            
            result['cached'] = False
            return JsonResponse(result)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error in plant lookup: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }, status=500)


@method_decorator(staff_member_required, name='dispatch')
class PlantSuggestionsView(View):
    """
    API view for plant name auto-complete suggestions.
    
    Provides quick suggestions for plant names as user types.
    """
    
    def get(self, request):
        """
        Get plant name suggestions for auto-complete.
        
        Query parameters:
        - q: Search query
        - limit: Maximum number of suggestions (default 10)
        """
        try:
            from apps.plant_identification.models import PlantSpecies
            
            query = request.GET.get('q', '').strip()
            limit = min(int(request.GET.get('limit', 10)), 50)  # Max 50 suggestions
            
            if len(query) < 2:
                return JsonResponse({
                    'success': True,
                    'suggestions': []
                })
            
            # Check cache first
            cache_key = f"plant_suggestions_{query.lower().replace(' ', '_')}_{limit}"
            cached_suggestions = cache.get(cache_key)
            
            if cached_suggestions:
                return JsonResponse({
                    'success': True,
                    'suggestions': cached_suggestions,
                    'cached': True
                })
            
            # Search in database
            suggestions = []
            
            # Scientific names
            scientific_matches = PlantSpecies.objects.filter(
                scientific_name__icontains=query
            ).values_list('scientific_name', flat=True)[:limit//2]
            
            for name in scientific_matches:
                suggestions.append({
                    'value': name,
                    'label': name,
                    'type': 'scientific'
                })
            
            # Common names (if we have room for more suggestions)
            if len(suggestions) < limit:
                remaining_limit = limit - len(suggestions)
                
                common_matches = PlantSpecies.objects.filter(
                    common_names__icontains=query
                ).values_list('common_names', 'scientific_name')[:remaining_limit]
                
                for common_names, scientific in common_matches:
                    if common_names:
                        # Get the first matching common name
                        for common in common_names.split(','):
                            common = common.strip()
                            if query.lower() in common.lower():
                                suggestions.append({
                                    'value': common,
                                    'label': f"{common} ({scientific})",
                                    'type': 'common'
                                })
                                break
            
            # Cache results for 1 hour
            cache.set(cache_key, suggestions, 3600)
            
            return JsonResponse({
                'success': True,
                'suggestions': suggestions[:limit],
                'cached': False
            })
            
        except Exception as e:
            logger.error(f"Error getting plant suggestions: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@require_http_methods(["POST"])
@staff_member_required
def generate_ai_content(request):
    """
    Generate AI content for plant-related blocks using Wagtail AI.
    
    This endpoint integrates with the existing Wagtail AI system
    to generate plant-specific content when database lookup fails.
    """
    try:
        data = json.loads(request.body)
        plant_name = data.get('plant_name', '')
        content_type = data.get('content_type', '')  # 'description', 'care_tips', etc.
        existing_data = data.get('existing_data', {})
        
        if not plant_name:
            return JsonResponse({
                'success': False,
                'error': 'Plant name is required'
            }, status=400)
        
        # Check if Wagtail AI is available
        try:
            from wagtail_ai.utils import get_ai_text
        except ImportError:
            return JsonResponse({
                'success': False,
                'error': 'Wagtail AI not available'
            }, status=503)
        
        # Import AI prompts
        from .ai_prompts import get_ai_prompt_for_block, PlantAIPrompts
        
        # Generate content based on type using specialized prompts
        if content_type == 'description':
            prompt = PlantAIPrompts.get_plant_description_prompt(plant_name, existing_data)
            
        elif content_type == 'care_instructions':
            # This is a general care instructions prompt
            prompt = PlantAIPrompts.get_care_instructions_prompt(plant_name, 'general', existing_data)
            
        elif content_type == 'special_notes':
            prompt = PlantAIPrompts.get_care_instructions_prompt(plant_name, 'special_notes', existing_data)
            
        elif content_type in ['watering', 'lighting', 'fertilizing', 'temperature', 'humidity']:
            # Specific care instruction types
            prompt = PlantAIPrompts.get_care_instructions_prompt(plant_name, content_type, existing_data)
            
        elif content_type == 'troubleshooting':
            problem_type = existing_data.get('problem_type', 'general issues')
            prompt = PlantAIPrompts.get_troubleshooting_prompt(plant_name, problem_type)
            
        elif content_type == 'beginner_guide':
            prompt = PlantAIPrompts.get_beginner_guide_prompt(plant_name)
            
        else:
            return JsonResponse({
                'success': False,
                'error': f'Unsupported content type: {content_type}'
            }, status=400)
        
        # Generate AI content
        try:
            ai_content = get_ai_text(prompt)
            
            return JsonResponse({
                'success': True,
                'content': ai_content,
                'content_type': content_type,
                'plant_name': plant_name
            })
            
        except Exception as ai_error:
            logger.error(f"Wagtail AI generation error: {str(ai_error)}")
            return JsonResponse({
                'success': False,
                'error': f'AI content generation failed: {str(ai_error)}'
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error in AI content generation: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
@staff_member_required
def plant_data_stats(request):
    """
    Get statistics about available plant data for admin dashboard.
    
    Provides insights into data coverage and source distribution.
    """
    try:
        from apps.plant_identification.models import PlantSpecies, PlantIdentificationRequest
        
        stats = {
            'local_species_count': PlantSpecies.objects.count(),
            'verified_species_count': PlantSpecies.objects.filter(is_verified=True).count(),
            'species_with_care_data': PlantSpecies.objects.exclude(
                light_requirements='',
                water_requirements=''
            ).count(),
            'species_with_images': PlantSpecies.objects.exclude(primary_image='').count(),
            'user_identifications_count': PlantIdentificationRequest.objects.filter(
                status='identified'
            ).count(),
        }
        
        # Data completeness percentages
        total_species = stats['local_species_count']
        if total_species > 0:
            stats['verification_percentage'] = round(
                (stats['verified_species_count'] / total_species) * 100, 1
            )
            stats['care_data_percentage'] = round(
                (stats['species_with_care_data'] / total_species) * 100, 1
            )
            stats['image_percentage'] = round(
                (stats['species_with_images'] / total_species) * 100, 1
            )
        else:
            stats['verification_percentage'] = 0
            stats['care_data_percentage'] = 0
            stats['image_percentage'] = 0
        
        return JsonResponse({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting plant data stats: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# Removed: generate_blog_field_content() function
# This custom API endpoint has been replaced with Wagtail AI's native panel system.
# AI content generation now happens through PlantAITitleFieldPanel,
# PlantAIDescriptionFieldPanel, and PlantAIIntroductionFieldPanel.
# See: apps/blog/panels.py and apps/blog/wagtail_ai_integration.py