"""
Views for managing user email notification preferences.

Provides user-friendly interface for controlling all email notification types
with proper GDPR compliance, and the signed-link unsubscribe endpoints the web
app's /unsubscribe page calls (todo 408).
"""

import logging

from apps.core.ratelimit import client_ip_key
from apps.core.services.notification_service import NotificationService
from apps.core.utils.pii_safe_logging import log_safe_user_context
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import permissions, serializers, status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.request import Request
from rest_framework.response import Response

from .constants import RATE_LIMIT_EMAIL_UNSUBSCRIBE
from .email_unsubscribe import LISTS, UnsubscribeTokenInvalid, read_token

logger = logging.getLogger(__name__)


@login_required
def email_preferences(request):
    """
    Display and handle email notification preferences for the logged-in user.
    """
    user = request.user
    notification_service = NotificationService()

    if request.method == "POST":
        try:
            # Update email notification preferences
            preferences = {
                "email_notifications": request.POST.get("email_notifications") == "on",
                "plant_id_notifications": request.POST.get("plant_id_notifications")
                == "on",
                "forum_notifications": request.POST.get("forum_notifications") == "on",
                "care_reminder_email": request.POST.get("care_reminder_email") == "on",
            }

            # Update user preferences
            user.email_notifications = preferences["email_notifications"]
            user.plant_id_notifications = preferences["plant_id_notifications"]
            user.forum_notifications = preferences["forum_notifications"]
            user.care_reminder_email = preferences["care_reminder_email"]
            user.save()

            # Update forum subscription preferences
            update_forum_subscriptions(user, request.POST)

            messages.success(
                request, "✅ Your email preferences have been updated successfully!"
            )
            logger.info(
                f"[EMAIL] Email preferences updated for {log_safe_user_context(user)}"
            )

        except Exception as e:
            messages.error(
                request,
                "❌ There was an error updating your preferences. Please try again.",
            )
            logger.error(
                f"[EMAIL] Error updating email preferences for {log_safe_user_context(user)}: {e}"
            )

    # Get current preferences
    current_preferences = notification_service.get_user_notification_preferences(user)

    # Get forum subscription preferences
    forum_subscriptions = get_forum_subscription_preferences(user)

    context = {
        "user": user,
        "preferences": current_preferences,
        "forum_subscriptions": forum_subscriptions,
    }

    return render(request, "users/email_preferences.html", context)


def _token_error(exc: UnsubscribeTokenInvalid) -> Response:
    message = (
        "This unsubscribe link has expired."
        if exc.code == "expired"
        else "This unsubscribe link is not valid."
    )
    return Response(
        {"code": exc.code, "message": message}, status=status.HTTP_400_BAD_REQUEST
    )


def _list_state(user, list_id: str) -> dict:
    email_list = LISTS[list_id]
    return {
        "list": list_id,
        "label": email_list.label,
        "subscribed": email_list.is_subscribed(user),
    }


_UNSUBSCRIBE_SCHEMA = extend_schema(
    request=inline_serializer(
        "EmailUnsubscribeRequest", {"token": serializers.CharField()}
    ),
    responses={
        200: inline_serializer(
            "EmailListState",
            {
                "list": serializers.CharField(),
                "label": serializers.CharField(),
                "subscribed": serializers.BooleanField(),
            },
        ),
        400: inline_serializer(
            "EmailUnsubscribeError",
            {
                "code": serializers.ChoiceField(choices=["invalid", "expired"]),
                "message": serializers.CharField(),
            },
        ),
    },
)


# The signed token in the body is the only credential (todo 408): no
# authentication class, so a signed-in visitor's session can never redirect
# the action onto their own account, and no CSRF — a cross-site POST would need
# the token, and whoever holds the token can act anyway. POST only: mail
# scanners prefetch GET links, and the token stays out of access logs.
@_UNSUBSCRIBE_SCHEMA
@api_view(["POST"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
@ratelimit(
    key=client_ip_key, rate=RATE_LIMIT_EMAIL_UNSUBSCRIBE, method="POST", block=True
)
def email_unsubscribe_check(request: Request) -> Response:
    """Describe the list a link unsubscribes from, without changing it."""
    try:
        user, list_id = read_token(request.data.get("token"))
    except UnsubscribeTokenInvalid as exc:
        return _token_error(exc)
    return Response(_list_state(user, list_id))


@_UNSUBSCRIBE_SCHEMA
@api_view(["POST"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
@ratelimit(
    key=client_ip_key, rate=RATE_LIMIT_EMAIL_UNSUBSCRIBE, method="POST", block=True
)
def email_unsubscribe(request: Request) -> Response:
    """Unsubscribe the token's user from the token's list. Idempotent."""
    try:
        user, list_id = read_token(request.data.get("token"))
    except UnsubscribeTokenInvalid as exc:
        return _token_error(exc)
    LISTS[list_id].unsubscribe(user)
    logger.info(
        f"[EMAIL] {log_safe_user_context(user)} unsubscribed from {list_id} via email link"
    )
    return Response(_list_state(user, list_id))


@login_required
@require_http_methods(["POST"])
def ajax_update_preference(request):
    """
    AJAX endpoint for updating individual email preferences.
    """
    # Define allowed preference names for security
    ALLOWED_PREFERENCES = {
        "email_notifications",
        "plant_id_notifications",
        "forum_notifications",
        "care_reminder_email",
    }

    try:
        preference_name = request.POST.get("preference")
        enabled = request.POST.get("enabled") == "true"

        # Validate preference name
        if not preference_name or preference_name not in ALLOWED_PREFERENCES:
            return JsonResponse(
                {"success": False, "error": "Invalid preference name"}, status=400
            )

        user = request.user

        # Set the preference using getattr/setattr for safety
        if hasattr(user, preference_name):
            setattr(user, preference_name, enabled)
            user.save(update_fields=[preference_name])
        else:
            return JsonResponse(
                {"success": False, "error": "User does not have this preference field"},
                status=400,
            )

        logger.info(
            f"[EMAIL] AJAX preference update: {log_safe_user_context(user)} set {preference_name} to {enabled}"
        )

        return JsonResponse({"success": True})

    except Exception as e:
        logger.error(f"[EMAIL] Error in AJAX preference update: {e}")
        return JsonResponse(
            {"success": False, "error": "An error occurred while updating preferences"},
            status=500,
        )


def update_forum_subscriptions(user, post_data):
    """Update user's forum subscription preferences."""
    from apps.core.models import ForumNotificationSubscription

    # Forum reply frequency
    reply_frequency = post_data.get("forum_reply_frequency", "instant")
    mention_frequency = post_data.get("forum_mention_frequency", "instant")
    digest_frequency = post_data.get("forum_digest_frequency", "weekly")

    # Update or create forum subscriptions
    subscription_types = [
        ("topic_reply", reply_frequency),
        ("mention", mention_frequency),
        ("digest", digest_frequency),
    ]

    for sub_type, frequency in subscription_types:
        subscription, created = ForumNotificationSubscription.objects.get_or_create(
            user=user,
            notification_type=sub_type,
            defaults={"frequency": frequency, "is_active": frequency != "never"},
        )

        if not created:
            subscription.frequency = frequency
            subscription.is_active = frequency != "never"
            subscription.save()


def get_forum_subscription_preferences(user):
    """Get user's current forum subscription preferences."""
    from apps.core.models import ForumNotificationSubscription

    subscriptions = ForumNotificationSubscription.objects.filter(user=user)

    preferences = {
        "reply_frequency": "instant",
        "mention_frequency": "instant",
        "digest_frequency": "weekly",
    }

    for sub in subscriptions:
        if sub.notification_type == "topic_reply":
            preferences["reply_frequency"] = sub.frequency
        elif sub.notification_type == "mention":
            preferences["mention_frequency"] = sub.frequency
        elif sub.notification_type == "digest":
            preferences["digest_frequency"] = sub.frequency

    return preferences
