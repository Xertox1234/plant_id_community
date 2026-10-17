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
from django.template.loader import render_to_string
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
    "password": "Email and password",  # pragma: allowlist secret
}


def has_password(user) -> bool:
    """True if ``user`` can sign in with a password.

    ``has_usable_password()`` alone is not enough: the Firebase path creates
    users with ``password=""``, which Django counts as usable although no
    password can match it.
    """
    return bool(user.password) and user.has_usable_password()


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
    if not has_password(user):
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
    name = PROVIDER_NAMES.get(provider, "Another")
    # Templates, not f-strings (todo 622): the shared mail-safe layout, a
    # text part of its own, and autoescape for the username.
    service = EmailService()
    context = {
        "site_name": service.site_name,
        "provider_name": name,
        "account": user.username,
        "reset_url": password_reset_url(),
    }
    # A render failure is a failed send (todo 639): False lets the task retry
    # and, at the end, log its [EMAIL] give-up, never escape the task raw.
    try:
        text = render_to_string("emails/provider_linked.txt", context)
        html = render_to_string("emails/provider_linked.html", context)
    except Exception as exc:
        # The exception's type only, never its text (todo 649): a template
        # error can echo a context value, and the context holds a signed link.
        logger.error(
            f"[EMAIL] Could not render the sign-in link notice for "
            f"{log_safe_user_context(user)}: {type(exc).__name__}"
        )
        return False
    return service.send_transactional_email(
        recipient=user,
        subject=f"{name} sign-in was connected to your {service.site_name} account",
        message=text,
        html_message=html,
    )
