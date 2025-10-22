"""
Garden Calendar URL Configuration

URL patterns for the garden calendar app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.views import CommunityEventViewSet, SeasonalTemplateViewSet, WeatherAlertViewSet

app_name = 'garden_calendar'

# API Router
router = DefaultRouter()
router.register(r'events', CommunityEventViewSet, basename='community-events')
router.register(r'templates', SeasonalTemplateViewSet, basename='seasonal-templates')
router.register(r'weather-alerts', WeatherAlertViewSet, basename='weather-alerts')

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
]