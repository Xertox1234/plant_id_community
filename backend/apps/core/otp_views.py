"""The admin second-factor pages (todo 705 M22).

``StaffOTPRequiredMiddleware`` sends a signed-in user here before any admin
page: to ``otp_setup`` to enrol an authenticator app the first time, and to
``otp_verify`` for a code on every later sign-in.

Recovery when the phone is lost: ``python manage.py addstatictoken <username>``
(django-otp's static plugin) prints a one-time code that ``otp_verify``
accepts. Remove the old TOTP device in Django admin (OTP_TOTP) afterwards.
"""

from __future__ import annotations

import base64
import logging
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods
from django_otp import login as otp_login
from django_otp import match_token, user_has_device
from django_otp.plugins.otp_totp.models import TOTPDevice

from .constants import (
    ADMIN_OTP_ATTEMPT_RATE,
    ADMIN_OTP_DEVICE_NAME,
    ADMIN_OTP_VERIFY_PATH,
)
from .ratelimit import ratelimit

logger = logging.getLogger(__name__)

ADMIN_HOME = "/cms/"
CMS_LOGIN_URL = "/cms/login/"


def _next_url(request: HttpRequest) -> str:
    """The admin page to return to: a same-host path, else the admin home."""
    candidate = request.POST.get("next") or request.GET.get("next") or ""
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return ADMIN_HOME


def _token(request: HttpRequest) -> str:
    return "".join(str(request.POST.get("token", "")).split())


@login_required(login_url=CMS_LOGIN_URL)
@require_http_methods(["GET", "POST"])
@ratelimit(group="admin_otp", key="user", rate=ADMIN_OTP_ATTEMPT_RATE, method="POST")
def otp_setup(request: HttpRequest) -> HttpResponse:
    """Enrol a TOTP authenticator app, once.

    A user who already has a confirmed device is sent to ``otp_verify``: a
    second enrolment would let whoever holds only the password add a device.
    """
    user = request.user
    next_url = _next_url(request)
    if user_has_device(user, confirmed=True):
        return HttpResponseRedirect(
            f"{ADMIN_OTP_VERIFY_PATH}?{urlencode({'next': next_url})}"
        )

    device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
    if device is None:
        device = TOTPDevice.objects.create(
            user=user, name=ADMIN_OTP_DEVICE_NAME, confirmed=False
        )

    error = ""
    if request.method == "POST":
        if device.verify_token(_token(request)):
            device.confirmed = True
            device.save(update_fields=["confirmed"])
            otp_login(request, device)
            logger.info("[SECURITY] Admin second factor enrolled for user %s", user.pk)
            return HttpResponseRedirect(next_url)
        error = "That code did not match. Check the app and try again."

    return render(
        request,
        "core/otp/setup.html",
        {
            "secret": base64.b32encode(device.bin_key).decode("ascii"),
            "config_url": device.config_url,
            "next": next_url,
            "error": error,
        },
    )


@login_required(login_url=CMS_LOGIN_URL)
@require_http_methods(["GET", "POST"])
@ratelimit(group="admin_otp", key="user", rate=ADMIN_OTP_ATTEMPT_RATE, method="POST")
def otp_verify(request: HttpRequest) -> HttpResponse:
    """Ask for a code from the enrolled app (or a one-time recovery code)."""
    user = request.user
    next_url = _next_url(request)
    error = ""
    if request.method == "POST":
        device = match_token(user, _token(request))
        if device is not None:
            otp_login(request, device)
            return HttpResponseRedirect(next_url)
        logger.warning("[SECURITY] Wrong admin second-factor code for user %s", user.pk)
        error = "That code did not match. Try again."
    return render(request, "core/otp/verify.html", {"next": next_url, "error": error})
