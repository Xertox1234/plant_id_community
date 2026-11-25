"""Admin sign-in hardening: login throttle and the staff second factor.

Todo 705 M22 (audit 2026-11-10): `/cms/login/` and `/admin/login/` had no rate
limit and no second factor, and staff can delete accounts. Owner decision
2026-11-17: rate-limit both login forms, and require a django-otp TOTP code.

The second factor is enforced on every request under the admin prefixes, not
at the login form, because a Django session also comes from elsewhere: the web
OAuth callback calls ``django_login`` too, and that session reaches ``/cms/``
without ever seeing a login form.
"""

from __future__ import annotations

import logging
from typing import Any, Callable
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_ratelimit.core import get_usage

from .constants import (
    ADMIN_LOGIN_FAILURE_RATE,
    ADMIN_LOGIN_PATHS,
    ADMIN_LOGIN_RATELIMIT_GROUP,
    ADMIN_OTP_EXEMPT_PATHS,
    ADMIN_OTP_PATH_PREFIXES,
    ADMIN_OTP_SETUP_PATH,
    ADMIN_OTP_VERIFY_PATH,
)
from .ratelimit import client_ip_key

logger = logging.getLogger(__name__)


def can_open_admin(user: Any) -> bool:
    """Whether this account can reach an admin page, so needs the second factor.

    Wagtail lets in anyone with ``wagtailadmin.access_admin``, not only staff:
    the Forum Moderators group has it without ``is_staff``
    (``apps/forum_host/bootstrap.py``). Owner decision 2026-11-18: all of them
    enrol TOTP. The middleware and the two-factor pages share this check, so
    they can never disagree and redirect in a loop.
    """
    return bool(
        user.is_staff or user.is_superuser or user.has_perm("wagtailadmin.access_admin")
    )


def has_confirmed_totp(user: Any) -> bool:
    """Whether the account has an enrolled authenticator app.

    Not ``user_has_device``: the static device ``addstatictoken`` creates for
    recovery stays confirmed after its code is used, so once the lost TOTP
    device is removed it would keep the user at verify with no code that works.
    """
    return bool(TOTPDevice.objects.filter(user=user, confirmed=True).exists())


def _login_failures(request: HttpRequest, increment: bool) -> dict[str, Any] | None:
    usage: dict[str, Any] | None = get_usage(
        request,
        group=ADMIN_LOGIN_RATELIMIT_GROUP,
        key=client_ip_key,
        rate=ADMIN_LOGIN_FAILURE_RATE,
        method="POST",
        increment=increment,
    )
    return usage


class AdminLoginThrottleMiddleware:
    """429 at the admin login forms once an IP has failed too often.

    Only failures count: a sign-in that succeeds redirects (3xx), and one that
    fails re-renders the form. Once the count reaches the limit, every POST is
    refused before the password is checked, until the window ends.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method != "POST" or request.path not in ADMIN_LOGIN_PATHS:
            return self.get_response(request)

        usage = _login_failures(request, increment=False)
        if usage is not None and usage["count"] >= usage["limit"]:
            logger.warning(
                "[SECURITY] Admin sign-in throttled at %s after %s failures",
                request.path,
                usage["count"],
            )
            response = HttpResponse(
                "Too many failed sign-in attempts. Try again later.",
                status=429,
                content_type="text/plain; charset=utf-8",
            )
            response["Retry-After"] = str(max(1, int(usage["time_left"])))
            return response

        response = self.get_response(request)
        if not 300 <= response.status_code < 400:
            _login_failures(request, increment=True)
        return response


class StaffOTPRequiredMiddleware:
    """Send a signed-in, unverified user on an admin path to the second factor.

    Must come after ``django_otp.middleware.OTPMiddleware``, which gives
    ``request.user`` its ``is_verified()``. A user with a confirmed TOTP device
    is asked for a code; one without is sent to enrol one. Anonymous requests
    pass: the admin's own login redirect handles them.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if self._needs_second_factor(request):
            target = (
                ADMIN_OTP_VERIFY_PATH
                if has_confirmed_totp(request.user)
                else ADMIN_OTP_SETUP_PATH
            )
            return HttpResponseRedirect(
                f"{target}?{urlencode({'next': request.get_full_path()})}"
            )
        return self.get_response(request)

    @staticmethod
    def _needs_second_factor(request: HttpRequest) -> bool:
        if not getattr(settings, "STAFF_OTP_REQUIRED", True):
            return False
        path = request.path
        if not path.startswith(ADMIN_OTP_PATH_PREFIXES):
            return False
        if path in ADMIN_OTP_EXEMPT_PATHS:
            return False
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        # Only an account that can open the admin is asked; a regular user's
        # session is left to the admin's own refusal instead of enrolling.
        if not can_open_admin(user):
            return False
        is_verified = getattr(user, "is_verified", None)
        return not (callable(is_verified) and is_verified())
