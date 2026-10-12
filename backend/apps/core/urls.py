"""``apps.core`` API routes, mounted under ``/api/v1/``."""

from django.urls import path

from .api.push_devices import register_push_device, unregister_push_device

urlpatterns = [
    path("push-devices/", register_push_device, name="push-device-register"),
    path(
        "push-devices/unregister/",
        unregister_push_device,
        name="push-device-unregister",
    ),
]
