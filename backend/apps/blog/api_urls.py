"""
URL configuration for blog API endpoints.

These URLs handle auto-population requests from Wagtail admin interface.
"""

from django.urls import path
from . import api_views

app_name = 'blog_api'

urlpatterns = [
    # Plant lookup for block auto-population
    path('plant-lookup/', api_views.PlantLookupView.as_view(), name='plant_lookup'),
    
    # Auto-complete suggestions
    path('plant-suggestions/', api_views.PlantSuggestionsView.as_view(), name='plant_suggestions'),
    
    # AI content generation
    path('ai-content/', api_views.generate_ai_content, name='ai_content'),
    
    # Admin dashboard stats
    path('plant-stats/', api_views.plant_data_stats, name='plant_stats'),
]