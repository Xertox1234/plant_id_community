"""Email provider webhook and click redirect (todo 625).

``POST /api/v1/email/webhooks/resend/`` takes Resend's delivery feedback,
authenticated by its Svix signature (``RESEND_WEBHOOK_SECRET``). No session,
no CSRF token and no JWT: the signature is the only credential, checked on
the raw body before anything is parsed.

``GET /api/v1/email/click/<token>/`` is the first-party click redirect: it
counts the click (``email_feedback.record_click``) and sends the reader on to
the signed link, which is always one of the web app's own pages.

Neither view is rate-limited: the webhook refuses an unsigned request before
any database work, and the redirect writes at most one row per email and
link. Neither logs an address, a token or a URL.
"""

import json
import logging

from django.conf import settings
from django.http import HttpResponseRedirect
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import permissions, serializers
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    parser_classes,
    permission_classes,
)
from rest_framework.request import Request
from rest_framework.response import Response

from .. import email_feedback
from ..constants import EMAIL_WEBHOOK_MAX_BODY_BYTES, SVIX_ID_MAX_LENGTH

logger = logging.getLogger(__name__)

_RESULT = inline_serializer("EmailWebhookResult", {"status": serializers.CharField()})
_ERROR = inline_serializer("EmailWebhookError", {"error": serializers.CharField()})


@extend_schema(
    summary="Resend delivery feedback webhook",
    request=OpenApiTypes.OBJECT,
    responses={
        200: _RESULT,
        400: _ERROR,
        401: _ERROR,
        413: _ERROR,
        503: _ERROR,
    },
)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
# No parser: the body is read raw, since the signature covers its exact bytes.
@parser_classes([])
def resend_webhook(request: Request) -> Response:
    """Verify, record and apply one Resend event. A duplicate (Svix retries
    until it gets a 2xx) answers 200 and changes nothing."""
    secret = getattr(settings, "RESEND_WEBHOOK_SECRET", "")
    if not secret:
        return Response({"error": "disabled"}, status=503)
    length = request.META.get("CONTENT_LENGTH") or "0"
    if not length.isdigit() or int(length) > EMAIL_WEBHOOK_MAX_BODY_BYTES:
        return Response({"error": "too_large"}, status=413)
    # At most one byte past the cap, whatever the header said: a request
    # with no Content-Length (chunked, under ASGI) is never read whole into
    # memory before the signature check.
    body = request._request.read(EMAIL_WEBHOOK_MAX_BODY_BYTES + 1)
    if len(body) > EMAIL_WEBHOOK_MAX_BODY_BYTES:
        return Response({"error": "too_large"}, status=413)
    msg_id = request.headers.get("svix-id", "")
    if len(msg_id) > SVIX_ID_MAX_LENGTH:
        return Response({"error": "malformed"}, status=400)
    try:
        email_feedback.verify_signature(
            secret,
            msg_id=msg_id,
            timestamp=request.headers.get("svix-timestamp", ""),
            signature=request.headers.get("svix-signature", ""),
            body=body,
        )
    except email_feedback.WebhookSignatureError as exc:
        # INFO, not WARNING: any anonymous caller can reach this line, so at
        # WARNING it would let anyone fill the alerting logs (todo 625
        # review). A real outage shows as missing events in the baseline.
        logger.info(f"[SECURITY] Resend webhook refused: {exc}")
        return Response({"error": "invalid_signature"}, status=401)
    except ValueError:
        logger.error("[EMAIL] RESEND_WEBHOOK_SECRET is malformed; webhook disabled")
        return Response({"error": "disabled"}, status=503)
    try:
        event = email_feedback.parse_event(json.loads(body))
    except (ValueError, email_feedback.MalformedEvent) as exc:
        # MalformedEvent is a ValueError; a JSON decode error is one too.
        logger.warning(f"[EMAIL] Resend webhook body refused: {type(exc).__name__}")
        return Response({"error": "malformed"}, status=400)
    return Response({"status": email_feedback.ingest(msg_id, event)})


@extend_schema(
    summary="Email link redirect",
    request=None,
    responses={
        302: OpenApiResponse(
            description=(
                "Redirect to the linked web page; to the site home when the "
                "token is not genuine."
            )
        )
    },
)
# HEAD too: link checkers and mail scanners probe with it, and it must
# redirect without counting.
@api_view(["GET", "HEAD"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def email_click(request: Request, token: str) -> HttpResponseRedirect:
    """Count a click on an email link, then redirect to it. A HEAD request
    (a link checker) redirects without counting."""
    data = email_feedback.read_click_token(token)
    if data is None:
        return HttpResponseRedirect(f"{settings.SITE_URL.rstrip('/')}/")
    if request.method == "GET":
        email_feedback.record_click(data["n"], data["l"])
    return HttpResponseRedirect(data["u"])
