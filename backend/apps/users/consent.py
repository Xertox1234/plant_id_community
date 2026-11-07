"""Sign-up consent to the Privacy Policy and Terms of Service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from .constants import (
    CONSENT_REQUIRED_CODE,
    CONSENT_REQUIRED_MESSAGE,
    LEGAL_POLICY_VERSION,
)

if TYPE_CHECKING:
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
