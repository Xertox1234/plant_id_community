"""
The signed-link unsubscribe endpoints the web app's /unsubscribe page calls
(todo 408).

Email preferences themselves are edited on the web Settings page through the
`me/` API; the session-authenticated preference views that used to live here
had no client and were removed (todo 415).
"""

import logging
from urllib.parse import urlencode

from apps.core.ratelimit import client_ip_key
from apps.core.utils.pii_safe_logging import log_safe_user_context
from django_ratelimit.decorators import ratelimit
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
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


_UNSUBSCRIBE_SCHEMA_RESPONSES = {
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
}
_UNSUBSCRIBE_SCHEMA = extend_schema(
    request=inline_serializer(
        "EmailUnsubscribeRequest", {"token": serializers.CharField()}
    ),
    responses=_UNSUBSCRIBE_SCHEMA_RESPONSES,
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


@extend_schema(
    request=None,
    parameters=[OpenApiParameter("token", str, OpenApiParameter.QUERY, required=True)],
    responses=_UNSUBSCRIBE_SCHEMA_RESPONSES,
)
@api_view(["GET", "POST"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
# Keyed on the TOKEN, not the client IP: providers POST from a few shared
# egress IPs, so a per-IP limit would drop every user after the first 30 an
# hour (PR #819 review). A forged token fails the signature check before any
# DB work; a real one only unsubscribes its own user.
@ratelimit(
    key="get:token", rate=RATE_LIMIT_EMAIL_UNSUBSCRIBE, method="POST", block=True
)
def email_unsubscribe_one_click(request: Request):
    """RFC 8058 one-click unsubscribe (todo 416).

    A mail provider POSTs ``List-Unsubscribe=One-Click`` (form-encoded) to the
    List-Unsubscribe header's URL, with no cookies and no JavaScript, so the
    signed token rides in the query string and the body is ignored. Same
    token and credential model as ``email_unsubscribe``.

    A client without RFC 8058 opens the header URL with a GET instead: that
    redirects to the web page (which asks before acting) and changes
    nothing, since mail scanners prefetch GET links.
    """
    if request.method == "GET":
        from django.conf import settings
        from django.http import HttpResponseRedirect

        query = urlencode({"token": request.query_params.get("token", "")})
        return HttpResponseRedirect(
            f"{settings.SITE_URL.rstrip('/')}/unsubscribe?{query}"
        )
    try:
        user, list_id = read_token(request.query_params.get("token"))
    except UnsubscribeTokenInvalid as exc:
        return _token_error(exc)
    LISTS[list_id].unsubscribe(user)
    logger.info(
        f"[EMAIL] {log_safe_user_context(user)} unsubscribed from {list_id} via one-click"
    )
    return Response(_list_state(user, list_id))
