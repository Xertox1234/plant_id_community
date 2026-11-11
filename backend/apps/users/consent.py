"""Sign-up consent to the Privacy Policy and Terms of Service."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from .constants import (
    CONSENT_REQUIRED_CODE,
    CONSENT_REQUIRED_MESSAGE,
    LEGAL_POLICY_VERSION,
    POLICY_UPDATE_REQUIRED_CODE,
    POLICY_UPDATED_MESSAGE,
)

if TYPE_CHECKING:
    from rest_framework.request import Request

    from .models import User


class ConsentRequired(Exception):
    """Raised inside account creation when consent was not given."""


def is_accepted(value: object) -> bool:
    """Only the JSON boolean ``true`` is acceptance; "true", 1 and None are not."""
    return value is True


def record_policy_acceptance(user: User) -> None:
    """Stamp the server's current policy version and the time on ``user``."""
    user.policy_version_accepted = LEGAL_POLICY_VERSION
    user.policy_accepted_at = timezone.now()
    user.save(update_fields=["policy_version_accepted", "policy_accepted_at"])


def needs_policy_acceptance(user: User) -> bool:
    """Whether ``user`` has not accepted the current policy version.

    True for an older version and for an account that never accepted one.
    """
    return user.policy_version_accepted != LEGAL_POLICY_VERSION


def confirm_current_policy(user: User, accepted: bool) -> bool:
    """Whether ``user`` may be issued tokens under the current policy.

    Call it on every path that issues tokens, after the identity is proven
    and the account is known to be active. An account on the current version
    passes untouched. Any other passes only when ``accepted`` (the request's
    ``accepted_terms`` read through ``is_accepted``), which is stamped here.
    On False, answer ``policy_updated_response()`` and issue nothing.
    """
    if not needs_policy_acceptance(user):
        return True
    if not accepted:
        return False
    record_policy_acceptance(user)
    return True


def policy_updated_response() -> Response:
    """The 428 for an existing account that must accept the current version.

    Its own ``code``, never the sign-up one: an app build that answers
    ``consent_required`` deletes the Firebase login when the person cancels.
    The client asks, then repeats the same request with
    ``accepted_terms: true``.
    """
    return Response(
        {
            "error": POLICY_UPDATED_MESSAGE,
            "code": POLICY_UPDATE_REQUIRED_CODE,
            "policy_version": LEGAL_POLICY_VERSION,
        },
        status=status.HTTP_428_PRECONDITION_REQUIRED,
    )


def consent_required_response() -> Response:
    return Response(
        {"error": CONSENT_REQUIRED_MESSAGE, "code": CONSENT_REQUIRED_CODE},
        status=status.HTTP_428_PRECONDITION_REQUIRED,
    )


def require_consent(view: Callable[..., Any]) -> Callable[..., Any]:
    """Refuse with 428 unless the body's ``accepted_terms`` is JSON ``true``.

    Stack it ABOVE ``@ratelimit`` (it then runs first), so a refusal does not
    use up the caller's sign-up quota: a stale client that never sends the flag
    would otherwise be locked out by its own 428s.
    """

    @functools.wraps(view)
    def wrapped(request: Request, *args: Any, **kwargs: Any) -> Any:
        body = request.data if isinstance(request.data, dict) else {}
        if not is_accepted(body.get("accepted_terms")):
            return consent_required_response()
        return view(request, *args, **kwargs)

    return wrapped
