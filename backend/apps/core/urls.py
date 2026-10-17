"""``apps.core`` API routes, mounted under ``/api/v1/``."""

from django.urls import path

from .api.email_feedback import email_click, resend_webhook
from .api.push_devices import register_push_device, unregister_push_device

urlpatterns = [
    path("push-devices/", register_push_device, name="push-device-register"),
    path(
        "push-devices/unregister/",
        unregister_push_device,
        name="push-device-unregister",
    ),
    # Email provider feedback and click attribution (todo 625).
    path("email/webhooks/resend/", resend_webhook, name="email-webhook-resend"),
    path("email/click/<str:token>/", email_click, name="email-click"),
]
