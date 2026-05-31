"""
Garden Calendar URL Configuration

URL patterns for the garden calendar app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api.views import (  # Community features; Garden planner
    CareLogViewSet,
    CareTaskViewSet,
    CommunityEventViewSet,
    GardenBedViewSet,
    GrowingZoneViewSet,
    HarvestViewSet,
    PlantImageViewSet,
    PlantViewSet,
    SeasonalTemplateViewSet,
    WeatherAlertViewSet,
)

app_name = "garden_calendar"

# API Router
router = DefaultRouter()

# Community features
router.register(r"events", CommunityEventViewSet, basename="community-events")
router.register(r"templates", SeasonalTemplateViewSet, basename="seasonal-templates")
router.register(r"weather-alerts", WeatherAlertViewSet, basename="weather-alerts")

# Garden planner
router.register(r"garden-beds", GardenBedViewSet, basename="garden-beds")
router.register(r"plants", PlantViewSet, basename="plants")
router.register(r"care-tasks", CareTaskViewSet, basename="care-tasks")
router.register(r"care-logs", CareLogViewSet, basename="care-logs")
router.register(r"harvests", HarvestViewSet, basename="harvests")
router.register(r"plant-images", PlantImageViewSet, basename="plant-images")
router.register(r"growing-zones", GrowingZoneViewSet, basename="growing-zones")

urlpatterns = [
    # API endpoints
    path("api/", include(router.urls)),
]
