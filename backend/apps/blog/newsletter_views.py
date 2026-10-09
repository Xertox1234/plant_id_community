"""Newsletter signup, confirmation and unsubscribe endpoints (todo 409).

These replace `BlogNewsletterViewSet`, which answered differently for
subscribed and unknown addresses and unsubscribed any address it was sent.
See `apps.blog.newsletter` for the design.

No endpoint authenticates. Signup needs nothing but an address, and the
signed token is the only credential for the others, as for todo 408's
unsubscribe: a signed-in visitor's session can never change what they act
on, and no CSRF applies.

The three the web app calls parse JSON only. A JSON POST from another origin
needs a CORS preflight, which our allowlist refuses, so no other site can
make its visitors' browsers sign addresses up (a plain HTML form could, from
every visitor's IP, past the per-IP limit). One-click keeps the default
parsers: mail providers form-post it.
"""

import logging
from functools import partial
from urllib.parse import urlencode

from apps.core.ratelimit import client_ip_key
from django.conf import settings
from django.db import transaction
from django.http import HttpResponseRedirect
from django_ratelimit.decorators import ratelimit
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import permissions, serializers, status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    parser_classes,
    permission_classes,
)
from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.response import Response

from . import newsletter
from .constants import RATE_LIMIT_NEWSLETTER_SUBSCRIBE, RATE_LIMIT_NEWSLETTER_TOKEN
from .tasks import send_newsletter_confirmation

logger = logging.getLogger(__name__)

SUBSCRIBE_DETAIL = (
    "Check your inbox: if that address can join the newsletter, we have sent "
    "it a link to confirm."
)


class NewsletterSubscribeSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


def _token_error(exc: newsletter.NewsletterTokenInvalid) -> Response:
    message = (
        "This link has expired." if exc.code == "expired" else "This link is not valid."
    )
    return Response(
        {"code": exc.code, "message": message}, status=status.HTTP_400_BAD_REQUEST
    )


def _body_token(request: Request):
    """The body's `token`, or None when the JSON body is not an object."""
    return request.data.get("token") if isinstance(request.data, dict) else None


_STATE = inline_serializer(
    "NewsletterSubscriptionState", {"subscribed": serializers.BooleanField()}
)
_TOKEN_ERROR = inline_serializer(
    "NewsletterTokenError",
    {
        "code": serializers.ChoiceField(choices=["invalid", "expired"]),
        "message": serializers.CharField(),
    },
)
_TOKEN_SCHEMA = extend_schema(
    request=inline_serializer(
        "NewsletterTokenRequest", {"token": serializers.CharField()}
    ),
    responses={200: _STATE, 400: _TOKEN_ERROR},
)


@extend_schema(
    request=NewsletterSubscribeSerializer,
    responses={
        202: inline_serializer(
            "NewsletterSubscribeAccepted", {"detail": serializers.CharField()}
        )
    },
)
@api_view(["POST"])
@parser_classes([JSONParser])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
@ratelimit(
    key=client_ip_key, rate=RATE_LIMIT_NEWSLETTER_SUBSCRIBE, method="POST", block=True
)
def newsletter_subscribe(request: Request) -> Response:
    """Ask for a confirmation link. The same 202 whatever the address's state:
    the task decides whether anything is sent."""
    serializer = NewsletterSubscribeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    transaction.on_commit(
        partial(send_newsletter_confirmation.delay, serializer.validated_data["email"])
    )
    return Response({"detail": SUBSCRIBE_DETAIL}, status=status.HTTP_202_ACCEPTED)


# POST only: mail scanners fetch every GET link, and a GET that confirmed
# would let one confirm on the reader's behalf.
@_TOKEN_SCHEMA
@api_view(["POST"])
@parser_classes([JSONParser])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
@ratelimit(
    key=client_ip_key, rate=RATE_LIMIT_NEWSLETTER_TOKEN, method="POST", block=True
)
def newsletter_confirm(request: Request) -> Response:
    """Confirm the subscription the token names. Idempotent."""
    try:
        newsletter.confirm(_body_token(request))
    except newsletter.NewsletterTokenInvalid as exc:
        return _token_error(exc)
    return Response({"subscribed": True})


@_TOKEN_SCHEMA
@api_view(["POST"])
@parser_classes([JSONParser])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
@ratelimit(
    key=client_ip_key, rate=RATE_LIMIT_NEWSLETTER_TOKEN, method="POST", block=True
)
def newsletter_unsubscribe(request: Request) -> Response:
    """Unsubscribe the subscriber the token names. Idempotent."""
    try:
        newsletter.unsubscribe(_body_token(request))
    except newsletter.NewsletterTokenInvalid as exc:
        return _token_error(exc)
    return Response({"subscribed": False})


@extend_schema(
    request=None,
    parameters=[OpenApiParameter("token", str, OpenApiParameter.QUERY, required=True)],
    responses={200: _STATE, 400: _TOKEN_ERROR},
)
@api_view(["GET", "POST"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
# Keyed on the token, not the IP: mail providers POST from a few shared
# egress IPs (PR #819 review, as for the account lists' one-click).
@ratelimit(key="get:token", rate=RATE_LIMIT_NEWSLETTER_TOKEN, method="POST", block=True)
def newsletter_unsubscribe_one_click(request: Request):
    """RFC 8058 one-click unsubscribe, the List-Unsubscribe header's target.

    A provider POSTs with no cookies and no JavaScript, so the token rides in
    the query string. A GET (a client without RFC 8058, or a scanner) changes
    nothing and redirects to the web page, which asks first.
    """
    if request.method == "GET":
        query = urlencode({"token": request.query_params.get("token", "")})
        return HttpResponseRedirect(
            f"{settings.SITE_URL.rstrip('/')}/newsletter/unsubscribe?{query}"
        )
    try:
        newsletter.unsubscribe(request.query_params.get("token"))
    except newsletter.NewsletterTokenInvalid as exc:
        return _token_error(exc)
    return Response({"subscribed": False})
