"""What happens when a sign-in provider is first linked to an account
(todo 447 item 1).

A sign-in path links a provider (Google, GitHub, Apple through Firebase) to an
existing local account only when the account has verified its email
(``email_verification``). One residual remains: a victim who cooperated with a
squatter (forwarded the verification mail, or signed in with a password the
squatter supplied) has verified the squatter's account, and the squatter still
holds its password and a session.

So the first time a provider is linked to an account that has a usable
password, every outstanding refresh token is revoked and the address is told.
The password is left in place (owner decision, 2026-09-25): removing it would
lock out a legitimate owner who uses both, and the notice points at the reset
page instead. Access tokens are not revocable and live out their short
lifetime.

Each path decides what "first" means with its own durable marker:

- web OAuth (``oauth_views``): no ``SocialAccount`` row yet for the provider;
- allauth (``oauth_adapters.pre_social_login``): ``sociallogin.connect``;
- Firebase (``firebase_auth_views``): ``firebase_uid`` bound for the first time.

Call this BEFORE the path issues its own tokens, or they are revoked too.
"""

import logging

from apps.core.services.email_service import EmailService
from apps.core.utils.pii_safe_logging import log_safe_user_context
from django.conf import settings
from django.utils.html import escape
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

logger = logging.getLogger(__name__)

PROVIDER_NAMES = {
    "google": "Google",
    "github": "GitHub",
    "google.com": "Google",
    "apple.com": "Apple",
}


def revoke_refresh_tokens(user) -> int:
    """Blacklist every outstanding refresh token of ``user``. Returns the count."""
    outstanding = OutstandingToken.objects.filter(user=user).exclude(
        blacklistedtoken__isnull=False
    )
    created = BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=token) for token in outstanding],
        ignore_conflicts=True,
    )
    return len(created)


def on_first_provider_link(user, provider: str) -> None:
    """Revoke ``user``'s sessions and queue a notice, if it has a password.

    An account without a usable password was created by a provider, so there
    is no second credential a squatter could hold.
    """
    if not user.has_usable_password():
        return
    from .email_verification import enqueue_on_commit

    revoked = revoke_refresh_tokens(user)
    logger.info(
        f"[AUTH] First {provider} link: revoked {revoked} refresh token(s) for "
        f"{log_safe_user_context(user)}"
    )
    enqueue_on_commit(
        "send_provider_linked_notice_task",
        user.pk,
        provider,
        context=log_safe_user_context(user),
    )


def password_reset_url() -> str:
    """allauth's reset page on this API's public origin."""
    base = (getattr(settings, "API_PUBLIC_URL", "") or "").rstrip("/")
    return f"{base}/accounts/password/reset/" if base else ""


def deliver_provider_linked_notice(user, provider: str) -> bool:
    """Send the notice now. Called by the Celery task only."""
    name = PROVIDER_NAMES.get(provider, provider)
    account = user.username
    reset = password_reset_url()
    if reset:
        text_reset = f"reset the password now:\n\n{reset}\n\n"
        html_reset = f'<a href="{escape(reset)}">reset the password now</a>.'
    else:
        text_reset = (
            "reset the password now (Forgot password? on the sign-in page).\n\n"
        )
        html_reset = "reset the password now (Forgot password? on the sign-in page)."
    text = (
        f'{name} sign-in was just connected to the Houseplant MD account "{account}".\n\n'
        "As a precaution, its other devices and browsers were signed out. If "
        "this was you, there is nothing else to do.\n\n"
        "If it wasn't you, someone may know the account's password: "
        f"{text_reset}"
    )
    html = (
        f"<p>{escape(name)} sign-in was just connected to the Houseplant MD account "
        f"<strong>{escape(account)}</strong>.</p>"
        "<p>As a precaution, its other devices and browsers were signed out. If "
        "this was you, there is nothing else to do.</p>"
        "<p>If it wasn't you, someone may know the account's password: "
        f"{html_reset}</p>"
    )
    return EmailService().send_transactional_email(
        recipient=user,
        subject=f"{name} sign-in was connected to your Houseplant MD account",
        message=text,
        html_message=html,
    )
