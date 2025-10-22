from django.urls import path

from apps.plant_identification.consumers import IdentificationConsumer

websocket_urlpatterns = [
    # ws/plant-identification/requests/<uuid>/
    path(
        "ws/plant-identification/requests/<uuid:request_id>/",
        IdentificationConsumer.as_asgi(),
        name="ws_plant_identification_request",
    ),
]
