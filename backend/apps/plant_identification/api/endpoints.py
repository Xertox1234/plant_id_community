"""
Wagtail API endpoints for plant identification snippets and pages.
"""

from wagtail.api.v2.views import BaseAPIViewSet, PagesAPIViewSet
from wagtail.api.v2.filters import FieldsFilter, OrderingFilter, SearchFilter
from rest_framework.decorators import action
from rest_framework.response import Response

from ..models import PlantSpecies
from ..models import (
    PlantCareGuide,
    PlantCategory,
    PlantSpeciesPage,
    PlantCategoryIndexPage
)
from .serializers import (
    PlantSpeciesSerializer,
    PlantCareGuideSerializer,
    PlantCategorySerializer,
    PlantSpeciesPageSerializer,
    PlantSpeciesPageListSerializer,
    PlantCategoryIndexPageSerializer
)


class PlantSpeciesAPIViewSet(BaseAPIViewSet):
    """API ViewSet for PlantSpecies snippets."""
    
    base_serializer_class = PlantSpeciesSerializer
    filter_backends = [FieldsFilter, OrderingFilter, SearchFilter]
    body_fields = [
        'id', 'uuid', 'scientific_name', 'common_names', 'family', 'genus',
        'species', 'plant_type', 'growth_habit', 'light_requirements',
        'water_requirements', 'care_difficulty'
    ]
    listing_default_fields = [
        'id', 'uuid', 'scientific_name', 'common_name', 'family', 
        'plant_type', 'light_requirements', 'water_requirements',
        'care_difficulty', 'image_url'
    ]
    nested_default_fields = ['id', 'scientific_name', 'common_name']
    name = 'plant_species'
    model = PlantSpecies
    
    known_query_parameters = BaseAPIViewSet.known_query_parameters.union([
        'plant_type',
        'family', 
        'light_requirements',
        'water_requirements',
        'hardiness_zone_min',
        'hardiness_zone_max',
        'has_care_guide'
    ])
    
    def get_queryset(self):
        """Enhanced queryset with plant-specific filtering."""
        queryset = PlantSpecies.objects.all()
        
        # Plant type filtering
        plant_type = self.request.GET.get('plant_type')
        if plant_type:
            queryset = queryset.filter(plant_type=plant_type)
        
        # Family filtering
        family = self.request.GET.get('family')
        if family:
            queryset = queryset.filter(family__icontains=family)
        
        # Care requirements filtering
        light_requirements = self.request.GET.get('light_requirements')
        if light_requirements:
            queryset = queryset.filter(light_requirements=light_requirements)
        
        water_requirements = self.request.GET.get('water_requirements')
        if water_requirements:
            queryset = queryset.filter(water_requirements=water_requirements)
        
        # Hardiness zone filtering
        hardiness_min = self.request.GET.get('hardiness_zone_min')
        hardiness_max = self.request.GET.get('hardiness_zone_max')
        if hardiness_min:
            queryset = queryset.filter(hardiness_zone_min__gte=hardiness_min)
        if hardiness_max:
            queryset = queryset.filter(hardiness_zone_max__lte=hardiness_max)
        
        # Filter by whether plant has care guide
        has_care_guide = self.request.GET.get('has_care_guide')
        if has_care_guide and has_care_guide.lower() == 'true':
            queryset = queryset.filter(care_guide__isnull=False)
        
        # Prefetch related objects for performance
        queryset = queryset.select_related('care_guide', 'species_page')
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def families(self, request):
        """Get list of plant families."""
        families = PlantSpecies.objects.values_list(
            'family', flat=True
        ).distinct().exclude(family='').order_by('family')
        
        return Response([
            {'name': family, 'count': PlantSpecies.objects.filter(family=family).count()}
            for family in families
        ])
    
    @action(detail=False, methods=['get'])
    def plant_types(self, request):
        """Get list of plant types."""
        plant_types = PlantSpecies.objects.exclude(
            plant_type=''
        ).values_list('plant_type', flat=True).distinct()
        
        # Get display names for choices
        choices_dict = dict(PlantSpecies._meta.get_field('plant_type').choices)
        
        return Response([
            {
                'value': plant_type, 
                'display': choices_dict.get(plant_type, plant_type.title()),
                'count': PlantSpecies.objects.filter(plant_type=plant_type).count()
            }
            for plant_type in plant_types
        ])


class PlantCategoryAPIViewSet(BaseAPIViewSet):
    """API ViewSet for PlantCategory snippets."""
    
    base_serializer_class = PlantCategorySerializer
    filter_backends = [FieldsFilter, OrderingFilter, SearchFilter]
    body_fields = [
        'id', 'name', 'slug', 'description', 'icon', 'color',
        'cover_image', 'is_featured', 'plant_count'
    ]
    listing_default_fields = [
        'id', 'name', 'slug', 'description', 'icon', 'color',
        'cover_image_thumb', 'is_featured', 'plant_count'
    ]
    nested_default_fields = ['id', 'name', 'slug', 'color']
    name = 'plant_categories'
    model = PlantCategory
    
    known_query_parameters = BaseAPIViewSet.known_query_parameters.union([
        'featured'
    ])
    
    def get_queryset(self):
        """Enhanced queryset with category filtering."""
        queryset = PlantCategory.objects.all()
        
        # Featured categories
        featured = self.request.GET.get('featured')
        if featured and featured.lower() == 'true':
            queryset = queryset.filter(is_featured=True)
        
        # Prefetch related objects
        queryset = queryset.prefetch_related('plant_species')
        
        return queryset


class PlantCareGuideAPIViewSet(BaseAPIViewSet):
    """API ViewSet for PlantCareGuide snippets."""
    
    base_serializer_class = PlantCareGuideSerializer
    filter_backends = [FieldsFilter, OrderingFilter, SearchFilter]
    body_fields = [
        'id', 'plant_species', 'care_difficulty', 'care_level_description',
        'display_name', 'quick_care_summary', 'care_content',
        'light_description', 'watering_description', 'soil_description',
        'temperature_description', 'humidity_description', 
        'fertilizing_description', 'propagation_methods',
        'common_problems', 'seasonal_notes', 'tags', 'is_featured'
    ]
    listing_default_fields = [
        'id', 'plant_species', 'care_difficulty', 'care_level_description',
        'display_name', 'quick_care_summary', 'is_featured'
    ]
    nested_default_fields = ['id', 'display_name', 'care_difficulty']
    name = 'plant_care_guides'
    model = PlantCareGuide
    
    known_query_parameters = BaseAPIViewSet.known_query_parameters.union([
        'care_difficulty',
        'featured',
        'tag',
        'plant_type'
    ])
    
    def get_queryset(self):
        """Enhanced queryset with care guide filtering."""
        queryset = PlantCareGuide.objects.select_related('plant_species')
        
        # Care difficulty filtering
        care_difficulty = self.request.GET.get('care_difficulty')
        if care_difficulty:
            queryset = queryset.filter(care_difficulty=care_difficulty)
        
        # Featured guides
        featured = self.request.GET.get('featured')
        if featured and featured.lower() == 'true':
            queryset = queryset.filter(is_featured=True)
        
        # Tag filtering
        tag = self.request.GET.get('tag')
        if tag:
            queryset = queryset.filter(tags__name__iexact=tag)
        
        # Plant type filtering
        plant_type = self.request.GET.get('plant_type')
        if plant_type:
            queryset = queryset.filter(plant_species__plant_type=plant_type)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def difficulty_levels(self, request):
        """Get care difficulty levels with counts."""
        choices = PlantCareGuide._meta.get_field('care_difficulty').choices
        
        results = []
        for value, display in choices:
            count = PlantCareGuide.objects.filter(care_difficulty=value).count()
            results.append({
                'value': value,
                'display': display,
                'count': count
            })
        
        return Response(results)


class PlantSpeciesPageViewSet(PagesAPIViewSet):
    """ViewSet for PlantSpeciesPage pages."""
    
    def get_serializer_class(self):
        """Use different serializers for list vs detail views."""
        if self.action == 'list':
            return PlantSpeciesPageListSerializer
        return PlantSpeciesPageSerializer
    
    known_query_parameters = PagesAPIViewSet.known_query_parameters.union([
        'category',
        'category_slug',
        'plant_type',
        'family',
        'featured',
        'light_requirements',
        'water_requirements'
    ])
    
    def get_queryset(self):
        """Enhanced queryset with plant-specific filtering."""
        queryset = PlantSpeciesPage.objects.live().public().specific()
        
        # Category filtering
        category_id = self.request.GET.get('category')
        category_slug = self.request.GET.get('category_slug')
        if category_id:
            queryset = queryset.filter(categories__id=category_id)
        elif category_slug:
            queryset = queryset.filter(categories__slug=category_slug)
        
        # Plant characteristics filtering
        plant_type = self.request.GET.get('plant_type')
        if plant_type:
            queryset = queryset.filter(plant_species__plant_type=plant_type)
        
        family = self.request.GET.get('family')
        if family:
            queryset = queryset.filter(plant_species__family__icontains=family)
        
        light_requirements = self.request.GET.get('light_requirements')
        if light_requirements:
            queryset = queryset.filter(plant_species__light_requirements=light_requirements)
        
        water_requirements = self.request.GET.get('water_requirements')
        if water_requirements:
            queryset = queryset.filter(plant_species__water_requirements=water_requirements)
        
        # Featured plants
        featured = self.request.GET.get('featured')
        if featured and featured.lower() == 'true':
            queryset = queryset.filter(is_featured=True)
        
        # Prefetch related objects for performance
        queryset = queryset.select_related(
            'plant_species', 'plant_species__care_guide'
        ).prefetch_related(
            'categories', 'gallery_images'
        )
        
        return queryset.distinct()
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured plant species pages."""
        featured_plants = self.get_queryset().filter(is_featured=True)[:8]
        
        serializer = PlantSpeciesPageListSerializer(
            featured_plants, many=True, context={'request': request}
        )
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Get plants grouped by category."""
        from ..models import PlantCategory
        
        categories = PlantCategory.objects.filter(is_featured=True)
        
        result = []
        for category in categories:
            plants = self.get_queryset().filter(categories=category)[:6]
            result.append({
                'category': PlantCategorySerializer(
                    category, context={'request': request}
                ).data,
                'plants': PlantSpeciesPageListSerializer(
                    plants, many=True, context={'request': request}
                ).data
            })
        
        return Response(result)


class PlantCategoryIndexPageViewSet(PagesAPIViewSet):
    """ViewSet for PlantCategoryIndexPage."""
    
    serializer_class = PlantCategoryIndexPageSerializer
    
    def get_queryset(self):
        return PlantCategoryIndexPage.objects.live().public().specific()