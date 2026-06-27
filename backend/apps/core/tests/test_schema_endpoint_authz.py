"""
Authorization tests for the OpenAPI schema / Swagger / Redoc endpoints (todo 248).

The drf-spectacular views (`/api/schema/`, `/api/docs/`, `/api/redoc/`) used to be
served with the package default `SERVE_PERMISSIONS = [AllowAny]`, exposing the full
generated schema, every endpoint path/parameter, and the interactive UIs to
anonymous users in production.

These tests pin the chosen policy: staff-only access via
`SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = [IsAdminUser]`. Anonymous (and
non-staff authenticated) requests are denied; staff/admin requests succeed.

NOTE: the spectacular views bind `permission_classes = SERVE_PERMISSIONS` at
import time, so the gating CANNOT be exercised via `@override_settings`. These
tests verify the real, configured behavior instead.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()

# The three drf-spectacular endpoints, by URL name (see plant_community_backend/urls.py).
SCHEMA_URL_NAMES = ["api-schema", "api-docs-swagger", "api-docs-redoc"]


@override_settings(DEBUG=False)
class SchemaEndpointAnonymousDenialTests(TestCase):
    """Anonymous users must not reach the schema/docs endpoints in production."""

    def test_anonymous_is_denied_on_all_three_endpoints(self):
        for name in SCHEMA_URL_NAMES:
            with self.subTest(endpoint=name):
                response = self.client.get(reverse(name))
                self.assertIn(
                    response.status_code,
                    (401, 403),
                    f"{name} must deny anonymous access (got {response.status_code})",
                )


@override_settings(DEBUG=False)
class SchemaEndpointNonStaffDenialTests(TestCase):
    """Authenticated but non-staff users are still denied (IsAdminUser, not IsAuthenticated)."""

    def setUp(self):
        # No password needed — force_login() bypasses password auth.
        self.user = User.objects.create_user(
            username="member", email="member@example.com"
        )

    def test_non_staff_user_is_denied(self):
        self.client.force_login(self.user)
        for name in SCHEMA_URL_NAMES:
            with self.subTest(endpoint=name):
                response = self.client.get(reverse(name))
                # An *authenticated* non-staff user is forbidden (403), never
                # unauthenticated (401) — pin the exact semantics here.
                self.assertEqual(
                    response.status_code,
                    403,
                    f"{name} must return 403 for non-staff users (got {response.status_code})",
                )


@override_settings(
    DEBUG=False,
    SPECTACULAR_SETTINGS={
        **settings.SPECTACULAR_SETTINGS,
        "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    },
)
class SchemaEndpointImportTimeBindingTests(TestCase):
    """The gate is fixed at import time and cannot be re-opened at runtime.

    The spectacular views read `permission_classes = SERVE_PERMISSIONS` at
    class-definition time, so flipping SERVE_PERMISSIONS back to AllowAny via
    `@override_settings` is INERT — the endpoint stays denied. This is precisely
    why the rest of the suite verifies the real configured behavior instead of
    relying on override_settings to flip the gate.
    """

    def test_runtime_serve_permissions_override_does_not_reopen_gate(self):
        response = self.client.get(reverse("api-schema"))
        self.assertIn(
            response.status_code,
            (401, 403),
            "Runtime SERVE_PERMISSIONS override must not re-open the schema endpoint "
            f"(got {response.status_code}).",
        )


class SchemaEndpointStaffAccessTests(TestCase):
    """Staff/admin users retain access to the schema and the interactive docs."""

    def setUp(self):
        # No password needed — force_login() bypasses password auth.
        self.staff = User.objects.create_user(
            username="staffer",
            email="staffer@example.com",
            is_staff=True,
        )

    def test_staff_can_reach_all_three_endpoints(self):
        self.client.force_login(self.staff)
        for name in SCHEMA_URL_NAMES:
            with self.subTest(endpoint=name):
                response = self.client.get(reverse(name))
                self.assertEqual(
                    response.status_code,
                    200,
                    f"{name} must serve staff users (got {response.status_code})",
                )


class SchemaEndpointSettingsTests(TestCase):
    """Pin the settings that drive the policy so a regression is obvious."""

    def test_serve_permissions_is_admin_only(self):
        self.assertEqual(
            settings.SPECTACULAR_SETTINGS.get("SERVE_PERMISSIONS"),
            ["rest_framework.permissions.IsAdminUser"],
            "Schema endpoints must be gated to IsAdminUser (todo 248).",
        )

    def test_persist_authorization_is_disabled(self):
        self.assertFalse(
            settings.SPECTACULAR_SETTINGS["SWAGGER_UI_SETTINGS"].get(
                "persistAuthorization"
            ),
            "persistAuthorization must be False to match the httpOnly-cookie posture.",
        )
