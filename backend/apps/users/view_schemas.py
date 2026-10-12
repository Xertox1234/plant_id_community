"""OpenAPI request and response shapes for the users app's function views.

The auth views are plain ``@api_view`` functions with no serializer, so
drf-spectacular cannot guess what they take or return. CI runs
``spectacular --validate --fail-on-warn`` (todo 581), so each one declares its
shapes here. Request examples (todo 582) use obviously fake values only.

Apply a schema ABOVE ``@api_view``: it decorates the generated view class.
Every ``@ratelimit(block=True)`` view lists ``429: RATE_LIMITED`` (todo 599).
"""

from apps.core.openapi import RATE_LIMITED
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers

from .serializers import (
    UserPlantCollectionSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)

# The flat error envelope `create_error_response` builds (and
# apps.core.exceptions.custom_exception_handler emits).
ERROR_ENVELOPE = inline_serializer(
    "AuthErrorEnvelope",
    {
        "error": serializers.BooleanField(),
        "message": serializers.CharField(),
        "code": serializers.CharField(),
        "status_code": serializers.IntegerField(),
        "errors": serializers.DictField(required=False),
    },
)
_SIMPLE_ERROR = inline_serializer("AuthSimpleError", {"error": serializers.CharField()})
_MESSAGE = inline_serializer("AuthMessage", {"message": serializers.CharField()})
_MESSAGE_AND_USER = inline_serializer(
    "AuthMessageAndUser",
    {"message": serializers.CharField(), "user": UserSerializer()},
)
_MESSAGE_AND_PROFILE = inline_serializer(
    "AuthMessageAndProfile",
    {"message": serializers.CharField(), "user": UserProfileSerializer()},
)
_REFRESH_BODY = inline_serializer(
    "AuthRefreshTokenBody",
    {
        "refresh": serializers.CharField(
            required=False,
            help_text="Only for clients without the httpOnly refresh_token "
            "cookie; the cookie wins when both are sent.",
        )
    },
)
_REFRESH_EXAMPLE = OpenApiExample(
    "Refresh token in the body",
    value={"refresh": "example-refresh-token-not-real"},
    request_only=True,
)


# A placeholder in the docs, not a credential.
_FAKE_PASSWORD = "example-password-not-real"  # pragma: allowlist secret


def _example(name: str, value: dict) -> OpenApiExample:
    return OpenApiExample(name, value=value, request_only=True)


CSRF_TOKEN_SCHEMA = extend_schema(
    responses={
        200: inline_serializer("CsrfCookieSet", {"detail": serializers.CharField()})
    },
    description="Sets the csrftoken cookie for later unsafe requests.",
)

REGISTER_SCHEMA = extend_schema(
    request=UserRegistrationSerializer,
    responses={
        201: _MESSAGE_AND_USER,
        400: OpenApiResponse(
            OpenApiTypes.OBJECT, description="Field errors, keyed by field name."
        ),
        429: RATE_LIMITED,
        500: ERROR_ENVELOPE,
    },
    examples=[
        _example(
            "Register",
            {
                "username": "example_gardener",
                "email": "gardener@example.com",
                "password": _FAKE_PASSWORD,
                "password_confirm": _FAKE_PASSWORD,
                "first_name": "Example",
                "last_name": "Gardener",
                "gardening_experience": "beginner",
            },
        )
    ],
)

VERIFY_EMAIL_SCHEMA = extend_schema(
    request=inline_serializer("VerifyEmailRequest", {"key": serializers.CharField()}),
    responses={
        200: inline_serializer(
            "VerifyEmailResponse", {"verified": serializers.BooleanField()}
        ),
        400: ERROR_ENVELOPE,
        401: ERROR_ENVELOPE,
        429: RATE_LIMITED,
    },
    examples=[_example("Verify email", {"key": "example-verification-key"})],
)

RESEND_VERIFICATION_SCHEMA = extend_schema(
    request=None,
    responses={
        200: inline_serializer(
            "ResendVerificationResponse",
            {
                "verified": serializers.BooleanField(),
                "sent": serializers.BooleanField(),
                "limit_reached": serializers.BooleanField(required=False),
            },
        ),
        401: ERROR_ENVELOPE,
        429: RATE_LIMITED,
    },
)

LOGIN_SCHEMA = extend_schema(
    request=inline_serializer(
        "LoginRequest",
        {
            "username": serializers.CharField(
                required=False, help_text="Username or email; one of the two."
            ),
            "email": serializers.CharField(required=False),
            "password": serializers.CharField(),
        },
    ),
    responses={
        200: _MESSAGE_AND_USER,
        400: ERROR_ENVELOPE,
        401: ERROR_ENVELOPE,
        403: ERROR_ENVELOPE,
        429: RATE_LIMITED,
    },
    examples=[
        _example(
            "Log in by email",
            {"email": "gardener@example.com", "password": _FAKE_PASSWORD},
        )
    ],
)

CURRENT_USER_SCHEMA = extend_schema(responses={200: UserProfileSerializer})

UPDATE_PROFILE_SCHEMA = extend_schema(
    request=UserProfileSerializer,
    responses={
        200: _MESSAGE_AND_PROFILE,
        400: ERROR_ENVELOPE,
        401: ERROR_ENVELOPE,
        429: RATE_LIMITED,
    },
    examples=[
        _example(
            "Update profile",
            {
                "first_name": "Example",
                "bio": "Grows tomatoes on a balcony.",
                "location": "Exampleville",
                "gardening_experience": "intermediate",
            },
        )
    ],
)

DELETE_AVATAR_SCHEMA = extend_schema(
    responses={200: _MESSAGE_AND_PROFILE, 401: ERROR_ENVELOPE, 429: RATE_LIMITED}
)

LOGOUT_SCHEMA = extend_schema(
    request=_REFRESH_BODY,
    responses={200: _MESSAGE},
    examples=[_REFRESH_EXAMPLE],
)

TOKEN_REFRESH_SCHEMA = extend_schema(
    request=_REFRESH_BODY,
    responses={
        200: _MESSAGE,
        400: ERROR_ENVELOPE,
        401: ERROR_ENVELOPE,
        429: RATE_LIMITED,
        503: ERROR_ENVELOPE,
    },
    examples=[_REFRESH_EXAMPLE],
)

_COLLECTION_EXAMPLE = {
    "name": "Windowsill herbs",
    "description": "Basil, mint and parsley.",
    "is_public": False,
}
COLLECTIONS_LIST_SCHEMA = extend_schema(
    methods=["GET"],
    operation_id="auth_me_collections_list",
    responses={200: UserPlantCollectionSerializer(many=True)},
)
COLLECTIONS_CREATE_SCHEMA = extend_schema(
    methods=["POST"],
    request=UserPlantCollectionSerializer,
    responses={201: UserPlantCollectionSerializer, 400: OpenApiTypes.OBJECT},
    examples=[_example("Create collection", _COLLECTION_EXAMPLE)],
)
COLLECTION_RETRIEVE_SCHEMA = extend_schema(
    methods=["GET"],
    responses={200: UserPlantCollectionSerializer, 404: _SIMPLE_ERROR},
)
COLLECTION_UPDATE_SCHEMA = extend_schema(
    methods=["PUT"],
    # The view saves with partial=True, so no field is required in the body.
    request=UserPlantCollectionSerializer(partial=True),
    responses={
        200: UserPlantCollectionSerializer,
        400: OpenApiTypes.OBJECT,
        404: _SIMPLE_ERROR,
    },
    description="Partial update: send only the fields to change.",
    examples=[_example("Rename collection", {"name": "Kitchen herbs"})],
)
COLLECTION_DELETE_SCHEMA = extend_schema(
    methods=["DELETE"],
    # 204 carries no body (RFC 9110 §15.3.5), and the view sends none (todo 599).
    responses={204: None, 404: _SIMPLE_ERROR},
)

PREVIOUS_SEARCHES_SCHEMA = extend_schema(
    operation_id="auth_me_searches_list",
    responses={
        200: inline_serializer(
            "PreviousSearchesPage",
            {
                "results": serializers.ListField(child=serializers.DictField()),
                "pagination": inline_serializer(
                    "PreviousSearchesPagination",
                    {
                        "current_page": serializers.IntegerField(),
                        "total_pages": serializers.IntegerField(),
                        "total_results": serializers.IntegerField(),
                        "has_next": serializers.BooleanField(),
                        "has_previous": serializers.BooleanField(),
                    },
                ),
            },
        )
    },
)

SEARCH_DETAIL_SCHEMA = extend_schema(
    responses={200: OpenApiTypes.OBJECT, 404: _SIMPLE_ERROR},
    description="One identification request with its results.",
)

DASHBOARD_STATS_SCHEMA = extend_schema(
    responses={
        200: inline_serializer(
            "DashboardStats",
            {
                "forum_stats": inline_serializer(
                    "DashboardForumStats",
                    {
                        "total_topics": serializers.IntegerField(),
                        "total_posts": serializers.IntegerField(),
                        "topics_this_month": serializers.IntegerField(),
                        "posts_this_month": serializers.IntegerField(),
                    },
                ),
                "recent_activity": inline_serializer(
                    "DashboardActivity",
                    {
                        "type": serializers.CharField(),
                        "title": serializers.CharField(),
                        "description": serializers.CharField(),
                        "timestamp": serializers.DateTimeField(),
                        "url": serializers.CharField(),
                        "icon": serializers.CharField(),
                    },
                    many=True,
                ),
            },
        )
    }
)

SUBSCRIBE_PUSH_SCHEMA = extend_schema(
    request=inline_serializer(
        "PushSubscribeRequest",
        {
            "subscription": serializers.DictField(
                help_text="The browser's PushSubscription.toJSON(): an https "
                "endpoint on a known push service, and keys.p256dh / keys.auth."
            )
        },
    ),
    responses={
        201: inline_serializer(
            "PushSubscribeResponse",
            {
                "message": serializers.CharField(),
                "subscription_id": serializers.IntegerField(),
                "device_name": serializers.CharField(),
            },
        ),
        400: _SIMPLE_ERROR,
        429: RATE_LIMITED,
        500: _SIMPLE_ERROR,
    },
    examples=[
        _example(
            "Browser subscription",
            {
                "subscription": {
                    "endpoint": "https://fcm.googleapis.com/fcm/send/example-endpoint-id",
                    "keys": {
                        "p256dh": "example-p256dh-key",
                        "auth": "example-auth-secret",
                    },
                }
            },
        )
    ],
)

UNSUBSCRIBE_PUSH_SCHEMA = extend_schema(
    request=inline_serializer(
        "PushUnsubscribeRequest", {"endpoint": serializers.CharField()}
    ),
    responses={200: _MESSAGE, 400: _SIMPLE_ERROR, 404: _SIMPLE_ERROR},
    examples=[
        _example(
            "Unsubscribe a browser",
            {"endpoint": "https://fcm.googleapis.com/fcm/send/example-endpoint-id"},
        )
    ],
)

RESUBSCRIBE_PUSH_SCHEMA = extend_schema(
    request=inline_serializer(
        "PushResubscribeRequest",
        {
            "old_subscription": inline_serializer(
                "PushOldSubscription",
                {
                    "endpoint": serializers.CharField(),
                    "auth": serializers.CharField(
                        help_text="The old subscription's keys.auth secret."
                    ),
                },
            ),
            "subscription": serializers.DictField(
                help_text="The new PushSubscription.toJSON(), checked like subscribe."
            ),
        },
    ),
    responses={
        200: _MESSAGE,
        400: _SIMPLE_ERROR,
        404: _SIMPLE_ERROR,
        429: ERROR_ENVELOPE,
    },
    description="Called by the service worker when the browser replaces a push "
    "subscription (todo 456). No session: the old subscription's endpoint and "
    "auth secret prove the caller holds it. CSRF-exempt, rate-limited per IP.",
    examples=[
        _example(
            "Browser replaced its subscription",
            {
                "old_subscription": {
                    "endpoint": "https://fcm.googleapis.com/fcm/send/example-old-id",
                    "auth": "example-old-auth-secret",
                },
                "subscription": {
                    "endpoint": "https://fcm.googleapis.com/fcm/send/example-new-id",
                    "keys": {
                        "p256dh": "example-p256dh-key",
                        "auth": "example-auth-secret",
                    },
                },
            },
        )
    ],
)

PUSH_PUBLIC_KEY_SCHEMA = extend_schema(
    responses={
        200: inline_serializer(
            "PushPublicKey",
            {
                "enabled": serializers.BooleanField(),
                "public_key": serializers.CharField(),
            },
        )
    }
)

PUSH_SUBSCRIPTIONS_SCHEMA = extend_schema(
    responses={
        200: inline_serializer(
            "PushSubscriptionList",
            {
                "subscriptions": inline_serializer(
                    "PushSubscriptionSummary",
                    {
                        "id": serializers.IntegerField(),
                        "device_name": serializers.CharField(),
                        "created_at": serializers.DateTimeField(),
                        "last_used": serializers.DateTimeField(allow_null=True),
                        "endpoint": serializers.CharField(
                            help_text="Truncated to 50 characters."
                        ),
                        "endpoint_sha256": serializers.CharField(
                            help_text="SHA-256 hex of the full endpoint, so a "
                            "browser can find its own row (todo 456)."
                        ),
                    },
                    many=True,
                ),
                "total_count": serializers.IntegerField(),
            },
        )
    }
)


def _onboarding_flags(required: bool) -> dict:
    """The client-settable onboarding fields (fresh instances: a field binds to
    one serializer)."""
    return {
        "completed_welcome": serializers.BooleanField(required=required),
        "completed_first_tour": serializers.BooleanField(required=required),
        "completed_checklist": serializers.BooleanField(required=required),
        "push_notifications_enabled": serializers.BooleanField(required=required),
        "batch_identification_tried": serializers.BooleanField(required=required),
        "completed_tours": serializers.ListField(
            child=serializers.CharField(), required=required
        ),
        "onboarding_completed_at": serializers.DateTimeField(
            required=required, allow_null=required
        ),
    }


ONBOARDING_GET_SCHEMA = extend_schema(
    methods=["GET"],
    responses={
        200: inline_serializer(
            "OnboardingProgress",
            {
                "user_id": serializers.IntegerField(),
                **_onboarding_flags(required=True),
                "first_identification_completed": serializers.BooleanField(),
                "checklist": serializers.ListField(child=serializers.DictField()),
                "created_at": serializers.DateTimeField(),
                "updated_at": serializers.DateTimeField(),
            },
        )
    },
)
ONBOARDING_PATCH_SCHEMA = extend_schema(
    methods=["PATCH"],
    request=inline_serializer(
        "OnboardingProgressUpdate", _onboarding_flags(required=False)
    ),
    responses={
        200: inline_serializer(
            "OnboardingProgressUpdated",
            {
                "message": serializers.CharField(),
                "checklist": serializers.ListField(child=serializers.DictField()),
            },
        ),
        400: inline_serializer(
            "OnboardingProgressError",
            {
                "error": serializers.CharField(),
                "fields": serializers.ListField(child=serializers.CharField()),
            },
        ),
    },
    examples=[_example("Dismiss the checklist", {"completed_checklist": True})],
)

TRACK_ONBOARDING_EVENT_SCHEMA = extend_schema(
    request=inline_serializer(
        "OnboardingEventRequest",
        {
            "event_type": serializers.CharField(),
            "event_data": serializers.DictField(required=False),
            "page_url": serializers.CharField(required=False),
        },
    ),
    responses={
        200: _MESSAGE,
        400: _SIMPLE_ERROR,
        429: RATE_LIMITED,
        500: _SIMPLE_ERROR,
    },
    examples=[
        _example(
            "Step completed",
            {
                "event_type": "step_completed",
                "event_data": {"step": "welcome"},
                "page_url": "/onboarding/welcome",
            },
        )
    ],
)

OAUTH_LOGIN_SCHEMA = extend_schema(
    responses={
        200: inline_serializer(
            "OAuthLoginUrl",
            {"oauth_url": serializers.URLField(), "provider": serializers.CharField()},
        ),
        400: _SIMPLE_ERROR,
        429: RATE_LIMITED,
        500: _SIMPLE_ERROR,
    },
    description="The provider's consent-page URL for the client to open.",
)

OAUTH_CALLBACK_SCHEMA = extend_schema(
    responses={
        302: OpenApiResponse(
            description="Redirect to the web app; on success it carries the "
            "JWT cookies, on failure an `error` query parameter."
        ),
        400: _SIMPLE_ERROR,
        429: RATE_LIMITED,
    },
)
