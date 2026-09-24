"""
The signed-link unsubscribe endpoints the web app's /unsubscribe page calls
(todo 408).

Email preferences themselves are edited on the web Settings page through the
`me/` API; the session-authenticated preference views that used to live here
had no client and were removed (todo 415).
"""

import logging

from apps.core.ratelimit import client_ip_key
from apps.core.utils.pii_safe_logging import log_safe_user_context
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


def _token_error(exc: UnsubscribeTokenInvalid) -> Response:
    message = (
        "This unsubscribe link has expired."
        if exc.code == "expired"
        else "This unsubscribe link is not valid."
    )
    return Response(
        {"code": exc.code, "message": message}, status=status.HTTP_400_BAD_REQUEST
    )


def _body_token(request: Request):
    """The body's `token`, or None when the JSON body is not an object.

    DRF parses a JSON array or bare string to a list or str, which has no
    `.get` — read_token turns the None into a 400 `invalid` (todo 417).
    """
    return request.data.get("token") if isinstance(request.data, dict) else None


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
# the token, and whoever holds the token can act anyway. POST only, because
# mail scanners prefetch GET links.
#
# POST keeps the token out of THIS API's access logs only. The email link is a
# GET to the web app's /unsubscribe?token=…, so the token does reach the web
# host's logs, browser history and any Referer, and it is signed, not
# encrypted, so the user UUID inside is readable. That is accepted (todo 417):
# holding the URL lets someone turn off one user's reply emails and nothing
# else, the user can turn them back on in Settings, and the token expires
# after UNSUBSCRIBE_MAX_AGE (90 days).
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
        user, list_id = read_token(_body_token(request))
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
        user, list_id = read_token(_body_token(request))
    except UnsubscribeTokenInvalid as exc:
        return _token_error(exc)
    LISTS[list_id].unsubscribe(user)
    logger.info(
        f"[EMAIL] {log_safe_user_context(user)} unsubscribed from {list_id} via email link"
    )
    return Response(_list_state(user, list_id))
