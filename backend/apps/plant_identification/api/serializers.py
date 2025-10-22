"""
Wagtail API serializers for plant identification models.

Provides headless CMS functionality for plant data, care guides,
and plant species pages through Wagtail API.
"""

from rest_framework import serializers
from wagtail.api.v2.serializers import PageSerializer, BaseSerializer
from wagtail.api.v2.utils import get_full_url
from wagtail.images.api.fields import ImageRenditionField
from wagtail.rich_text import get_text_for_indexing
from django.utils.text import Truncator

from ..models import PlantSpecies
from ..models import (
    PlantCareGuide,
    PlantCategory,
    PlantSpeciesPage,
    PlantCategoryIndexPage
)


class PlantSpeciesSerializer(BaseSerializer):
    """Serializer for PlantSpecies model as a snippet."""
    
    common_name = serializers.SerializerMethodField()
    care_difficulty = serializers.SerializerMethodField()
    care_guide_url = serializers.SerializerMethodField()
    species_page_url = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = PlantSpecies
        fields = [
            'id', 'uuid', 'scientific_name', 'common_names', 'common_name',
            'family', 'genus', 'species', 'plant_type', 'growth_habit',
            'mature_height_min', 'mature_height_max', 'light_requirements',
            'water_requirements', 'hardiness_zone_min', 'hardiness_zone_max',
            'care_difficulty', 'care_guide_url', 'species_page_url', 'image_url'
        ]
    
    def get_common_name(self, obj):
        """Get the first common name."""
        if obj.common_names:
            return obj.common_names.split(',')[0].strip()
        return obj.scientific_name
    
    def get_care_difficulty(self, obj):
        """Get care difficulty from care guide if available."""
        care_guide = getattr(obj, 'care_guide', None)
        if care_guide:
            return care_guide.get_care_difficulty_display()
        return None
    
    def get_care_guide_url(self, obj):
        """Get URL to care guide API endpoint."""
        request = self.context.get('request')
        care_guide = getattr(obj, 'care_guide', None)
        if care_guide and request:
            return get_full_url(request, f'/api/v2/care-guides/{care_guide.id}/')
        return None
    
    def get_species_page_url(self, obj):
        """Get URL to species page if available."""
        request = self.context.get('request')
        species_page = getattr(obj, 'species_page', None)
        if species_page and request:
            return get_full_url(request, species_page.get_url())
        return None
    
    def get_image_url(self, obj):
        """Get primary image URL if available."""
        species_page = getattr(obj, 'species_page', None)
        if species_page and species_page.hero_image:
            request = self.context.get('request')
            rendition = species_page.hero_image.get_rendition('fill-400x300')
            if request:
                return get_full_url(request, rendition.url)
            return rendition.url
        return None


class PlantCategorySerializer(BaseSerializer):
    """Serializer for PlantCategory snippets."""
    
    plant_count = serializers.SerializerMethodField()
    cover_image = ImageRenditionField('fill-400x300', read_only=True)
    cover_image_thumb = ImageRenditionField('fill-200x150', source='cover_image', read_only=True)
    
    class Meta:
        model = PlantCategory
        fields = [
            'id', 'name', 'slug', 'description', 'icon', 'color',
            'cover_image', 'cover_image_thumb', 'is_featured', 
            'plant_count', 'created_at'
        ]
    
    def get_plant_count(self, obj):
        """Get number of plant species in this category."""
        return obj.plant_species.count()


class PlantCareGuideSerializer(BaseSerializer):
    """Serializer for PlantCareGuide snippets."""
    
    plant_species = PlantSpeciesSerializer(read_only=True)
    care_level_description = serializers.ReadOnlyField()
    display_name = serializers.ReadOnlyField()
    tags = serializers.SerializerMethodField()
    
    class Meta:
        model = PlantCareGuide
        fields = [
            'id', 'plant_species', 'care_difficulty', 'care_level_description',
            'display_name', 'quick_care_summary', 'care_content',
            'light_description', 'watering_description', 'soil_description',
            'temperature_description', 'humidity_description', 
            'fertilizing_description', 'propagation_methods',
            'common_problems', 'seasonal_notes', 'tags',
            'is_featured', 'created_at', 'updated_at'
        ]
    
    def get_tags(self, obj):
        """Get tag names."""
        return [tag.name for tag in obj.tags.all()]


class PlantSpeciesPageSerializer(PageSerializer):
    """Serializer for PlantSpeciesPage pages."""
    
    plant_species = PlantSpeciesSerializer(read_only=True)
    categories = PlantCategorySerializer(many=True, read_only=True)
    hero_image = ImageRenditionField('fill-800x600', read_only=True)
    hero_image_thumb = ImageRenditionField('fill-400x300', source='hero_image', read_only=True)
    gallery_images = serializers.SerializerMethodField()
    care_guide = PlantCareGuideSerializer(source='plant_species.care_guide', read_only=True)
    excerpt = serializers.SerializerMethodField()
    related_plants = serializers.SerializerMethodField()
    
    class Meta:
        model = PlantSpeciesPage
        fields = ['id', 'title', 'slug', 'url', 'meta'] + [
            'plant_species', 'introduction', 'content_blocks',
            'hero_image', 'hero_image_thumb', 'gallery_images',
            'categories', 'is_featured', 'care_guide', 'excerpt',
            'related_plants'
        ]
    
    def get_gallery_images(self, obj):
        """Get gallery image renditions."""
        request = self.context.get('request')
        images = []
        
        for image in obj.gallery_images.all():
            rendition = image.get_rendition('fill-400x300')
            thumb = image.get_rendition('fill-200x150')
            
            image_data = {
                'id': image.id,
                'title': image.title,
                'alt': image.title,
                'url': get_full_url(request, rendition.url) if request else rendition.url,
                'thumb': get_full_url(request, thumb.url) if request else thumb.url
            }
            images.append(image_data)
        
        return images
    
    def get_excerpt(self, obj):
        """Get excerpt from introduction."""
        if obj.introduction:
            text = get_text_for_indexing(obj.introduction)
            return Truncator(text).words(50)
        return ''
    
    def get_related_plants(self, obj):
        """Get related plant species pages."""
        from django.db.models import Q
        
        related_plants = PlantSpeciesPage.objects.live().public().exclude(
            id=obj.id
        ).filter(
            Q(plant_species__family=obj.plant_species.family) |
            Q(categories__in=obj.categories.all())
        ).distinct()[:4]
        
        request = self.context.get('request')
        return [{
            'id': plant.id,
            'title': plant.title,
            'slug': plant.slug,
            'url': get_full_url(request, plant.get_url()) if request else plant.get_url(),
            'scientific_name': plant.plant_species.scientific_name,
            'common_name': plant.plant_species.common_names.split(',')[0].strip() if plant.plant_species.common_names else plant.plant_species.scientific_name,
            'hero_image': self._get_plant_image(plant, request)
        } for plant in related_plants]
    
    def _get_plant_image(self, plant, request):
        """Get plant hero image URL."""
        if plant.hero_image:
            rendition = plant.hero_image.get_rendition('fill-300x200')
            if request:
                return get_full_url(request, rendition.url)
            return rendition.url
        return None


class PlantSpeciesPageListSerializer(PageSerializer):
    """Lighter serializer for plant species page lists."""
    
    plant_species = PlantSpeciesSerializer(read_only=True)
    categories = PlantCategorySerializer(many=True, read_only=True)
    hero_image_thumb = ImageRenditionField('fill-300x200', source='hero_image', read_only=True)
    excerpt = serializers.SerializerMethodField()
    
    class Meta:
        model = PlantSpeciesPage
        fields = ['id', 'title', 'slug', 'url', 'meta'] + [
            'plant_species', 'hero_image_thumb', 'categories',
            'is_featured', 'excerpt'
        ]
    
    def get_excerpt(self, obj):
        """Get short excerpt from introduction."""
        if obj.introduction:
            text = get_text_for_indexing(obj.introduction)
            return Truncator(text).words(30)
        return ''


class PlantCategoryIndexPageSerializer(PageSerializer):
    """Serializer for PlantCategoryIndexPage."""
    
    categories = serializers.SerializerMethodField()
    featured_plants = serializers.SerializerMethodField()
    
    class Meta:
        model = PlantCategoryIndexPage
        fields = ['id', 'title', 'slug', 'url', 'meta'] + [
            'introduction', 'categories_per_page', 'show_featured_plants',
            'categories', 'featured_plants'
        ]
    
    def get_categories(self, obj):
        """Get featured plant categories."""
        featured_categories = PlantCategory.objects.filter(is_featured=True)
        return PlantCategorySerializer(
            featured_categories, many=True, context=self.context
        ).data
    
    def get_featured_plants(self, obj):
        """Get featured plants if enabled."""
        if not obj.show_featured_plants:
            return []
        
        featured_plants = PlantSpeciesPage.objects.live().public().filter(
            is_featured=True
        )[:6]
        
        return PlantSpeciesPageListSerializer(
            featured_plants, many=True, context=self.context
        ).data