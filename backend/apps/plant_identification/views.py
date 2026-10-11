"""
Django REST API views for plant identification.

Only the routes a client calls remain (todo 405 slice 2): the user's saved
plants (web My Plants) and disease-diagnosis requests (web /diagnose).
Identification itself is ``api/simple_views.identify_plant``.
"""

from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

# Rate limiting - make optional
try:
    # rate-preserving wrapper (todo 115): attaches the rate to the raised
    # Ratelimited so the exception handler emits a correct Retry-After window.
    from apps.core.ratelimit import ratelimit
except ImportError:
    # Fallback decorator that does nothing if django-ratelimit is not installed
    def ratelimit(**kwargs):
        def decorator(func):
            return func

        return decorator


import logging

from . import constants
from .models import PlantDiseaseRequest, UserPlant
from .serializers import (
    PlantDiseaseRequestCreateSerializer,
    PlantDiseaseRequestSerializer,
    PlantDiseaseRequestWithResultsSerializer,
    PlantDiseaseResultSerializer,
    UserPlantSerializer,
)
from .services.disease_diagnosis_service import PlantDiseaseService

logger = logging.getLogger(__name__)


_USER_PLANT_EXAMPLE = OpenApiExample(
    "Add a plant",
    value={
        "nickname": "Fern by the window",
        "species": 1,
        "collection": 1,
        "acquisition_date": "2026-01-15",
        "location_in_home": "Bathroom shelf",
        "notes": "Likes the humidity.",
        "is_alive": True,
        "is_public": False,
    },
    request_only=True,
)


@extend_schema_view(
    create=extend_schema(examples=[_USER_PLANT_EXAMPLE]),
    update=extend_schema(examples=[_USER_PLANT_EXAMPLE]),
    partial_update=extend_schema(
        examples=[
            OpenApiExample(
                "Update notes",
                value={"notes": "Repotted in spring."},
                request_only=True,
            )
        ]
    ),
)
class UserPlantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for user's plant collection.
    """

    serializer_class = UserPlantSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            # Schema generation runs with an AnonymousUser, which the user
            # filter below cannot take.
            return UserPlant.objects.none()
        # select_related: the serializer reads user (StringRelatedField),
        # species (nested), collection.name, and
        # from_identification_request.request_id on every row
        queryset = UserPlant.objects.filter(user=self.request.user).select_related(
            "user", "species", "collection", "from_identification_request"
        )

        # Filter by collection
        collection_id = self.request.query_params.get("collection")
        if collection_id:
            queryset = queryset.filter(collection_id=collection_id)

        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# =============================================================================
# Disease Diagnosis ViewSets
# =============================================================================


_DISEASE_REQUEST_EXAMPLE = OpenApiExample(
    "Describe the symptoms",
    value={
        "symptoms_description": "Brown spots with yellow rims on the lower leaves.",
        "plant_condition": "fair",
        "location": "Indoors, east-facing window",
        "recent_weather": "Humid",
        "recent_care_changes": "Moved it away from the radiator last week.",
    },
    description="Attach up to three photos as the `image_1`..`image_3` file parts.",
    request_only=True,
    media_type="multipart/form-data",
)


@extend_schema_view(
    create=extend_schema(examples=[_DISEASE_REQUEST_EXAMPLE]),
    update=extend_schema(examples=[_DISEASE_REQUEST_EXAMPLE]),
    partial_update=extend_schema(
        examples=[
            OpenApiExample(
                "Add a care note",
                value={"recent_care_changes": "Cut back on watering."},
                request_only=True,
                media_type="multipart/form-data",
            )
        ]
    ),
)
class PlantDiseaseRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for plant disease diagnosis requests.
    Handles image-based disease identification with plant.health API integration.
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            # Schema generation runs with an AnonymousUser, which the user
            # filter below cannot take.
            return PlantDiseaseRequest.objects.none()
        # `_results_count` annotation feeds both PlantDiseaseRequestSerializer
        # and the WithResults variant without a per-request COUNT query.
        return (
            PlantDiseaseRequest.objects.filter(user=self.request.user)
            .annotate(_results_count=Count("diagnosis_results"))
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        """Return different serializers based on the action."""
        if self.action == "create":
            return PlantDiseaseRequestCreateSerializer
        elif self.action == "list":
            return PlantDiseaseRequestWithResultsSerializer
        return PlantDiseaseRequestSerializer

    @method_decorator(
        ratelimit(
            key="user",
            rate=constants.RATE_LIMITS["authenticated"]["regenerate"],
            method="POST",
            block=True,
        )
    )
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
            logger.info(
                f"[DIAGNOSIS] Processed disease diagnosis for {request_obj.request_id}, found {len(results)} results"
            )
        except Exception as e:
            logger.error(f"[DIAGNOSIS] Failed to process disease diagnosis: {str(e)}")
            # Set status to failed but don't raise exception - request is still created
            request_obj.status = "failed"
            request_obj.save()

    def retrieve(self, request, pk=None):
        """Get disease diagnosis request by UUID."""
        try:
            request_obj = get_object_or_404(
                PlantDiseaseRequest, request_id=pk, user=request.user
            )
            serializer = self.get_serializer(request_obj)
            return Response(serializer.data)
        except ValueError:
            return Response({"error": "Invalid request ID format"}, status=400)

    @action(detail=True, methods=["get"], url_path="status")
    def status(self, request, pk=None):
        """Get processing status for a disease diagnosis request."""
        try:
            request_obj = get_object_or_404(
                PlantDiseaseRequest, request_id=pk, user=request.user
            )
            return Response(
                {
                    "request_id": str(request_obj.request_id),
                    "status": request_obj.status,
                    "processed_by_ai": request_obj.processed_by_ai,
                    "updated_at": request_obj.updated_at,
                }
            )
        except ValueError:
            return Response({"error": "Invalid request ID format"}, status=400)

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        """Get disease diagnosis results for a request."""
        try:
            request_obj = get_object_or_404(
                PlantDiseaseRequest, request_id=pk, user=request.user
            )

            results = request_obj.diagnosis_results.all().order_by(
                "-confidence_score", "-created_at"
            )

            serializer = PlantDiseaseResultSerializer(results, many=True)

            return Response(
                {
                    "request_id": str(request_obj.request_id),
                    "status": request_obj.status,
                    "results": serializer.data,
                }
            )

        except ValueError:
            return Response({"error": "Invalid request ID format"}, status=400)
