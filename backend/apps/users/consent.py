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
