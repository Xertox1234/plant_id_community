"""
Admin configuration for Plant Identification models.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    PlantSpecies, PlantIdentificationRequest, 
    PlantIdentificationResult, UserPlant
)


@admin.register(PlantSpecies)
class PlantSpeciesAdmin(admin.ModelAdmin):
    """Admin for Plant Species."""
    
    list_display = (
        'scientific_name', 'common_names_display', 'family', 'plant_type',
        'is_verified', 'created_at'
    )
    
    list_filter = (
        'plant_type', 'is_verified', 'light_requirements', 
        'water_requirements', 'created_at'
    )
    
    search_fields = (
        'scientific_name', 'common_names', 'family', 'genus', 'species'
    )
    
    readonly_fields = (
        'created_at', 'updated_at', 'primary_image_display'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'scientific_name', 'common_names', 'family', 
                'genus', 'species'
            )
        }),
        ('External IDs', {
            'fields': ('trefle_id', 'plantnet_id'),
            'classes': ('collapse',)
        }),
        ('Characteristics', {
            'fields': (
                'plant_type', 'growth_habit', 'mature_height_min',
                'mature_height_max', 'bloom_time', 'flower_color'
            )
        }),
        ('Care Requirements', {
            'fields': (
                'light_requirements', 'water_requirements',
                'soil_ph_min', 'soil_ph_max', 'hardiness_zone_min',
                'hardiness_zone_max'
            )
        }),
        ('Description', {
            'fields': ('description', 'native_regions')
        }),
        ('Images', {
            'fields': ('primary_image', 'primary_image_display')
        }),
        ('Verification', {
            'fields': ('is_verified', 'verification_source')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def common_names_display(self, obj):
        """Display first common name."""
        if obj.common_names:
            first_name = obj.common_names.split(',')[0].strip()
            return first_name[:50] + '...' if len(first_name) > 50 else first_name
        return '-'
    common_names_display.short_description = "Common Names"
    
    def primary_image_display(self, obj):
        """Display primary image thumbnail."""
        if obj.primary_image:
            return format_html(
                '<img src="{}" width="150" height="150" style="object-fit: cover;" />',
                obj.primary_image_thumbnail.url
            )
        return "No image"
    primary_image_display.short_description = "Image Preview"


@admin.register(PlantIdentificationRequest)
class PlantIdentificationRequestAdmin(admin.ModelAdmin):
    """Admin for Plant Identification Requests."""
    
    list_display = (
        'request_id_short', 'user', 'status', 'processed_by_ai',
        'location', 'created_at'
    )
    
    list_filter = (
        'status', 'processed_by_ai', 'plant_size', 'created_at'
    )
    
    search_fields = (
        'request_id', 'user__username', 'description', 'location'
    )
    
    readonly_fields = (
        'request_id', 'created_at', 'updated_at', 'ai_processing_date',
        'image_1_display', 'image_2_display', 'image_3_display'
    )
    
    fieldsets = (
        ('Request Info', {
            'fields': ('request_id', 'user', 'status')
        }),
        ('Images', {
            'fields': (
                'image_1', 'image_1_display',
                'image_2', 'image_2_display', 
                'image_3', 'image_3_display'
            )
        }),
        ('Location & Context', {
            'fields': (
                'location', 'latitude', 'longitude', 'habitat'
            )
        }),
        ('Plant Description', {
            'fields': ('description', 'plant_size')
        }),
        ('Processing', {
            'fields': (
                'processed_by_ai', 'ai_processing_date',
                'assigned_to_collection'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def request_id_short(self, obj):
        """Display shortened request ID."""
        return f"#{obj.request_id.hex[:8]}"
    request_id_short.short_description = "Request ID"
    
    def image_1_display(self, obj):
        """Display image 1 thumbnail."""
        if obj.image_1:
            return format_html(
                '<img src="{}" width="100" height="100" style="object-fit: cover;" />',
                obj.image_1_thumbnail.url
            )
        return "No image"
    image_1_display.short_description = "Image 1"
    
    def image_2_display(self, obj):
        """Display image 2 thumbnail."""
        if obj.image_2:
            return format_html(
                '<img src="{}" width="100" height="100" style="object-fit: cover;" />',
                obj.image_2_thumbnail.url
            )
        return "No image"
    image_2_display.short_description = "Image 2"
    
    def image_3_display(self, obj):
        """Display image 3 thumbnail."""
        if obj.image_3:
            return format_html(
                '<img src="{}" width="100" height="100" style="object-fit: cover;" />',
                obj.image_3_thumbnail.url
            )
        return "No image"
    image_3_display.short_description = "Image 3"


@admin.register(PlantIdentificationResult)
class PlantIdentificationResultAdmin(admin.ModelAdmin):
    """Admin for Plant Identification Results."""
    
    list_display = (
        'request_short', 'display_name', 'confidence_score_percent',
        'identification_source', 'vote_score', 'is_accepted', 'is_primary'
    )
    
    list_filter = (
        'identification_source', 'is_accepted', 'is_primary', 'created_at'
    )
    
    search_fields = (
        'request__request_id', 'identified_species__scientific_name',
        'suggested_scientific_name', 'suggested_common_name'
    )
    
    readonly_fields = (
        'created_at', 'updated_at', 'vote_score_display'
    )
    
    fieldsets = (
        ('Request Link', {
            'fields': ('request',)
        }),
        ('Identification', {
            'fields': (
                'identified_species', 'suggested_scientific_name',
                'suggested_common_name', 'confidence_score'
            )
        }),
        ('Source', {
            'fields': ('identification_source', 'identified_by')
        }),
        ('Community Voting', {
            'fields': ('upvotes', 'downvotes', 'vote_score_display')
        }),
        ('Status', {
            'fields': ('is_accepted', 'is_primary')
        }),
        ('Additional Info', {
            'fields': ('notes', 'api_response_data'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def request_short(self, obj):
        """Display shortened request ID."""
        return f"#{obj.request.request_id.hex[:8]}"
    request_short.short_description = "Request"
    
    def confidence_score_percent(self, obj):
        """Display confidence as percentage."""
        return f"{obj.confidence_score:.1%}"
    confidence_score_percent.short_description = "Confidence"
    
    def vote_score_display(self, obj):
        """Display vote score."""
        return obj.vote_score
    vote_score_display.short_description = "Net Votes"


@admin.register(UserPlant)
class UserPlantAdmin(admin.ModelAdmin):
    """Admin for User Plants."""
    
    list_display = (
        'display_name', 'user', 'collection', 'species',
        'is_alive', 'is_public', 'created_at'
    )
    
    list_filter = (
        'is_alive', 'is_public', 'created_at'
    )
    
    search_fields = (
        'nickname', 'user__username', 'species__scientific_name',
        'collection__name'
    )
    
    readonly_fields = (
        'created_at', 'updated_at', 'image_display'
    )
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'collection', 'species', 'nickname')
        }),
        ('Care Details', {
            'fields': (
                'acquisition_date', 'location_in_home', 'notes'
            )
        }),
        ('Status', {
            'fields': ('is_alive', 'is_public')
        }),
        ('Image', {
            'fields': ('image', 'image_display')
        }),
        ('Tracking', {
            'fields': ('from_identification_request',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def image_display(self, obj):
        """Display plant image thumbnail."""
        if obj.image:
            return format_html(
                '<img src="{}" width="100" height="100" style="object-fit: cover;" />',
                obj.image_thumbnail.url
            )
        return "No image"
    image_display.short_description = "Plant Image"