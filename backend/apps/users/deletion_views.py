"""Account deletion endpoints (Plan B task 6), under ``/api/v1/auth/``.

- ``POST account/delete/``: the mobile app, signed in with a JWT, proves a
  fresh Firebase sign-in (``auth_time`` at most 5 minutes old).
- ``POST account/delete/request/``: public. Emails a one-hour, single-use
  confirm link to the address if an active account holds it, and answers the
  same whether or not one does.
- ``POST account/delete/confirm/``: public. The link's token is the
  credential.

All three end in ``request_account_deletion(user, "self")``, which
deactivates the account and queues the erase.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from typing import Optional

from apps.core.openapi import RATE_LIMITED
from apps.core.ratelimit import client_ip_key, ratelimit
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from firebase_admin import auth as firebase_auth
from firebase_admin import exceptions as firebase_exceptions
from rest_framework import permissions, serializers, status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.request import Request
from rest_framework.response import Response

from .authentication import clear_jwt_cookies
from .constants import (
    ACCOUNT_DELETE_AUTH_TIME_SKEW_SECONDS,
    ACCOUNT_DELETE_CONTACT_SUPPORT_CODE,
    ACCOUNT_DELETE_CONTACT_SUPPORT_MESSAGE,
    ACCOUNT_DELETE_LINK_INVALID_CODE,
    ACCOUNT_DELETE_LINK_INVALID_MESSAGE,
    ACCOUNT_DELETE_REAUTH_CODE,
    ACCOUNT_DELETE_REAUTH_MAX_AGE_SECONDS,
    ACCOUNT_DELETE_REAUTH_MESSAGE,
    ACCOUNT_DELETE_REQUEST_RATE_EMAIL,
    ACCOUNT_DELETE_REQUEST_RATE_IP,
    ACCOUNT_DELETE_REQUEST_SENT_STATUS,
    ACCOUNT_DELETE_SCHEDULED_STATUS,
    DELETED_ACCOUNT_REASON_SELF,
)
from .deletion import DeletionRefused, request_account_deletion
from .deletion_links import DeletionLinkInvalid, consume_deletion_token
from .email_verification import enqueue_on_commit, get_account_by_email
from .firebase_auth_views import _ensure_firebase_initialized, redact_email

logger = logging.getLogger(__name__)

JWT_COOKIES = ("access_token", "refresh_token")


# --- Responses ---------------------------------------------------------------


def _error(code: str, message: str, status_code: int) -> Response:
    return Response({"code": code, "error": message}, status=status_code)


def _scheduled() -> Response:
    return Response(
        {"status": ACCOUNT_DELETE_SCHEDULED_STATUS}, status=status.HTTP_202_ACCEPTED
    )


def _reauth_required() -> Response:
    return _error(
        ACCOUNT_DELETE_REAUTH_CODE,
        ACCOUNT_DELETE_REAUTH_MESSAGE,
        status.HTTP_403_FORBIDDEN,
    )


def _contact_support() -> Response:
    return _error(
        ACCOUNT_DELETE_CONTACT_SUPPORT_CODE,
        ACCOUNT_DELETE_CONTACT_SUPPORT_MESSAGE,
        status.HTTP_409_CONFLICT,
    )


def _body(request: Request) -> Mapping:
    return request.data if isinstance(request.data, Mapping) else {}


# --- Schemas -----------------------------------------------------------------

_ERROR = inline_serializer(
    "AccountDeleteError",
    {"code": serializers.CharField(), "error": serializers.CharField()},
)
_SCHEDULED = OpenApiResponse(
    inline_serializer("AccountDeleteScheduled", {"status": serializers.CharField()}),
    description="The account is deactivated and its erase is queued; "
    "`status` is `scheduled`.",
)
_REFUSED = OpenApiResponse(
    _ERROR,
    description="A staff account or a blog author; `code` is `contact_support`. "
    "Nothing changed.",
)


# --- POST account/delete/ (mobile) ------------------------------------------


@extend_schema(
    request=inline_serializer(
        "AccountDeleteReauth", {"firebase_token": serializers.CharField()}
    ),
    responses={
        202: _SCHEDULED,
        403: OpenApiResponse(
            _ERROR,
            description="The Firebase token is missing, invalid, revoked, for "
            "another account, or its sign-in is more than 5 minutes old; "
            "`code` is `reauth_required`. The app signs the user in again "
            "and retries.",
        ),
        409: _REFUSED,
        503: OpenApiResponse(
            _ERROR,
            description="The token could not be checked; `code` is "
            "`verifier_unavailable`. Nothing changed.",
        ),
    },
    examples=[
        OpenApiExample(
            "Fresh Firebase ID token",
            value={"firebase_token": "example-firebase-id-token-not-real"},
            request_only=True,
        )
    ],
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def delete_account(request: Request) -> Response:
    """Delete the signed-in account after a fresh Firebase re-authentication.

    The token is verified with ``check_revoked=True``, which looks the user
    up through the Firebase Auth API, so it needs the service-account
    credentials production has. Its ``uid`` must be this account's, and its
    ``auth_time`` at most ``ACCOUNT_DELETE_REAUTH_MAX_AGE_SECONDS`` old.
    """
    token = _body(request).get("firebase_token")
    if not isinstance(token, str) or not token:
        return _reauth_required()

    _ensure_firebase_initialized()
    try:
        decoded = firebase_auth.verify_id_token(token, check_revoked=True)
    except (
        firebase_auth.InvalidIdTokenError,  # expired and revoked included
        firebase_auth.UserDisabledError,
        firebase_auth.UserNotFoundError,
    ) as exc:
        logger.info(
            f"[ACCOUNT DELETE] Re-auth refused for account {request.user.pk}: "
            f"{type(exc).__name__}"
        )
        return _reauth_required()
    # After the token clauses: UserDisabledError and UserNotFoundError are
    # FirebaseErrors too. Anything else is on our side, not the token's:
    # Google's certs unreachable (CertificateFetchError), the Admin app not
    # set up (ValueError), or check_revoked's user lookup failing (outage, or
    # a credential that may not call the Auth API).
    except (firebase_exceptions.FirebaseError, ValueError) as exc:
        logger.error(
            f"[ACCOUNT DELETE] Re-auth could not be checked: {type(exc).__name__}"
        )
        return _error(
            "verifier_unavailable",
            "Token verification is temporarily unavailable",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    uid = request.user.firebase_uid
    auth_time = decoded.get("auth_time")
    if (
        not uid
        or decoded.get("uid") != uid
        or not isinstance(auth_time, (int, float))
        or time.time() - auth_time > ACCOUNT_DELETE_REAUTH_MAX_AGE_SECONDS
        # A sign-in "from the future" beyond clock skew is not a fresh one.
        or auth_time - time.time() > ACCOUNT_DELETE_AUTH_TIME_SKEW_SECONDS
    ):
        logger.info(
            f"[ACCOUNT DELETE] Re-auth refused for account {request.user.pk}: "
            f"wrong account or stale sign-in"
        )
        return _reauth_required()

    try:
        request_account_deletion(request.user, DELETED_ACCOUNT_REASON_SELF)
    except DeletionRefused:
        return _contact_support()
    return _scheduled()


# --- POST account/delete/request/ (public) ----------------------------------


def _normalised_email(request: Request) -> str:
    email = _body(request).get("email")
    return email.strip().lower() if isinstance(email, str) else ""


def account_delete_email_key(group: Optional[str], request: HttpRequest) -> str:
    """Ratelimit key: the normalised address in the body, so case and
    whitespace variants share one bucket."""
    return _normalised_email(request)  # type: ignore[arg-type]


@extend_schema(
    request=inline_serializer("AccountDeleteLink", {"email": serializers.EmailField()}),
    responses={
        200: OpenApiResponse(
            inline_serializer(
                "AccountDeleteLinkSent", {"status": serializers.CharField()}
            ),
            description='Always `{"status": "sent"}`, whether or not an '
            "account holds the address. If an active one does, a confirm "
            "link valid for 1 hour is emailed to it.",
        ),
        429: RATE_LIMITED,
    },
    examples=[
        OpenApiExample(
            "Email address",
            value={"email": "someone@example.com"},
            request_only=True,
        )
    ],
)
@api_view(["POST"])
# The address is the only input and the mail goes to its owner, so there is no
# session to protect: no authenticator, hence no CSRF check, like the
# signed-link unsubscribe views.
@authentication_classes([])
@permission_classes([permissions.AllowAny])
@ratelimit(
    group="account_delete_request_ip",
    key=client_ip_key,
    rate=ACCOUNT_DELETE_REQUEST_RATE_IP,
    method="POST",
    block=True,
)
@ratelimit(
    group="account_delete_request_email",
    key=account_delete_email_key,
    rate=ACCOUNT_DELETE_REQUEST_RATE_EMAIL,
    method="POST",
    block=True,
)
def request_account_deletion_link(request: Request) -> Response:
    """Email a deletion confirm link if an active account holds the address.

    The answer never says whether one does, and the mail is sent from Celery
    so the response time does not either.
    """
    email = _normalised_email(request)
    user = None
    if email:
        try:
            user = get_account_by_email(email)
        except (
            get_user_model().DoesNotExist,
            get_user_model().MultipleObjectsReturned,
        ):
            user = None
    if user is not None and user.is_active:
        enqueue_on_commit(
            "send_account_delete_link_task",
            user.pk,
            context=f"account {user.pk}",
        )
        logger.info(
            f"[ACCOUNT DELETE] Deletion link requested for {redact_email(email)}"
        )
    return Response({"status": ACCOUNT_DELETE_REQUEST_SENT_STATUS})


# --- POST account/delete/confirm/ (public) ----------------------------------


@extend_schema(
    request=inline_serializer(
        "AccountDeleteConfirm", {"token": serializers.CharField()}
    ),
    responses={
        202: _SCHEDULED,
        400: OpenApiResponse(
            _ERROR,
            description="The link is invalid, expired, already used or "
            "replaced by a newer one; `code` is `link_invalid`.",
        ),
        409: _REFUSED,
    },
    examples=[
        OpenApiExample(
            "Token from the emailed link",
            value={"token": "example-signed-token-not-real"},
            request_only=True,
        )
    ],
)
@api_view(["POST"])
# The token is the credential. No authenticator, so stale JWT cookies of an
# account being deleted cannot 401 the request before it runs (and no CSRF
# check, which only guards a session).
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def confirm_account_deletion(request: Request) -> Response:
    """Delete the account an emailed link names. The link works once.

    An account that is already gone (its erase finished, or raced this
    request) is answered as scheduled: the link did what it was for.
    """
    try:
        user_pk = consume_deletion_token(_body(request).get("token"))
    except DeletionLinkInvalid:
        return _error(
            ACCOUNT_DELETE_LINK_INVALID_CODE,
            ACCOUNT_DELETE_LINK_INVALID_MESSAGE,
            status.HTTP_400_BAD_REQUEST,
        )

    User = get_user_model()
    try:
        user = User._base_manager.get(pk=user_pk)
        request_account_deletion(user, DELETED_ACCOUNT_REASON_SELF)
    except User.DoesNotExist:
        logger.info(f"[ACCOUNT DELETE] Account {user_pk} already gone at confirm")
    except DeletionRefused:
        return _contact_support()

    response = _scheduled()
    if any(name in request.COOKIES for name in JWT_COOKIES):
        clear_jwt_cookies(response)
    return response
