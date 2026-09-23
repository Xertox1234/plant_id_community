"""
URL configuration for plant identification API endpoints.
"""

import logging

from django.urls import include, path
from rest_framework import status as http_status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter

from . import views
from .api import simple_views

app_name = "plant_identification"

logger = logging.getLogger(__name__)


@api_view(["GET"])
def health_check(request):
    """Simple health check endpoint for plant identification API."""
    return Response(
        {
            "status": "healthy",
            "message": "Plant Identification API is working",
            "endpoints": {
                "plant_identification": [
                    "/api/v1/plant-identification/identify/",
                    "/api/v1/plant-identification/plants/",
                ],
                "disease_diagnosis": [
                    "/api/v1/plant-identification/disease-requests/",
                ],
                "utilities": [
                    "/api/v1/plant-identification/health/",
                    "/api/v1/plant-identification/status/",
                ],
            },
        }
    )


@api_view(["GET"])
def service_status(request):
    """Check status of external API services."""
    from .services.identification_service import PlantIdentificationService

    try:
        service = PlantIdentificationService()
        status = service.get_service_status()
        return Response(status)
    except Exception:
        # Anonymous endpoint: log the detail, return a generic body.
        logger.exception("[PLANT_ID] service_status failed")
        return Response(
            {"error": "Service status unavailable", "status": "error"},
            status=http_status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# Create router for ViewSets. Only the routes a client calls are registered
# (todo 405 slice 2): web My Plants (plants list/create) and the /diagnose
# flow (disease-requests create + results). The species, results, care,
# disease-result, disease-database, saved-*, treatment and search routes had
# no caller, and several proxied Trefle to anonymous users with no limit.
router = DefaultRouter()
router.register(r"plants", views.UserPlantViewSet, basename="plants")
router.register(
    r"disease-requests", views.PlantDiseaseRequestViewSet, basename="disease-requests"
)

urlpatterns = [
    # Simple identification endpoint (dual API integration)
    path("identify/", simple_views.identify_plant, name="simple_identify"),
    path("identify/health/", simple_views.health_check, name="simple_health"),
    # Health check
    path("health/", health_check, name="health"),
    path("status/", service_status, name="service_status"),
    # Include ViewSet URLs
    path("", include(router.urls)),
]
