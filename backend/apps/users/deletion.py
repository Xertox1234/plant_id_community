"""Account deletion helpers: blocked re-sign-up (Plan B task 1)."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from apps.core.email_feedback import address_hash
from rest_framework import status
from rest_framework.response import Response

from .constants import (
    SIGNUP_BLOCKED_CODE,
    SIGNUP_BLOCKED_MESSAGE,
    SIGNUP_BLOCKING_REASONS,
)
from .models import DeletedAccount

if TYPE_CHECKING:
    from rest_framework.request import Request


class SignupBlocked(Exception):
    """Raised at an account-create point for an address deleted for abuse/under-13."""


def email_hash(address: str) -> str:
    """The hash ``EmailSuppression`` keys on (one normaliser, not a copy)."""
    return address_hash(address)


def is_signup_blocked(address: str) -> bool:
    if not address:
        return False
    return DeletedAccount.objects.filter(
        email_hash=email_hash(address), reason__in=SIGNUP_BLOCKING_REASONS
    ).exists()


def signup_blocked_response() -> Response:
    return Response(
        {"error": SIGNUP_BLOCKED_MESSAGE, "code": SIGNUP_BLOCKED_CODE},
        status=status.HTTP_403_FORBIDDEN,
    )


def reject_blocked_signup(view: Callable[..., Any]) -> Callable[..., Any]:
    """Refuse 403 ``signup_blocked`` when the body's ``email`` is blocked.

    Stack it ABOVE ``@require_consent`` so a blocked address gets 403, never
    the 428 that asks it to accept the terms.
    """

    @functools.wraps(view)
    def wrapped(request: Request, *args: Any, **kwargs: Any) -> Any:
        body = request.data if isinstance(request.data, dict) else {}
        email = body.get("email")
        if isinstance(email, str) and is_signup_blocked(email):
            return signup_blocked_response()
        return view(request, *args, **kwargs)

    return wrapped
