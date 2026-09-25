"""Proof that a local account owns its email address (todo 446).

Password registration accepts any email nobody holds yet and logs the account
in at once. Three sign-in paths later match an existing account BY EMAIL:
web Google OAuth (``oauth_views._find_or_create_user``), the allauth adapter
(``oauth_adapters.pre_social_login``) and the Firebase legacy fallback
(``firebase_auth_views.get_or_create_user_from_firebase``). Without proof of
ownership, anyone could register a victim's address first and inherit the
victim's first Google sign-in (a pre-hijack). Each of those paths now matches
only an account whose email is verified here.

The store is allauth's ``EmailAddress.verified``. With ``ACCOUNT_UNIQUE_EMAIL``
allauth adds a DB constraint that a verified address belongs to one account,
which ``User.email`` (not unique) never had. Only public allauth API is used.

Confirming is a POST from the web page the email links to, never a GET: mail
scanners prefetch links, and a prefetch of an attacker's link would verify the
attacker's account from the victim's inbox.
"""

import logging

from allauth.account.models import EmailAddress, EmailConfirmationHMAC
from allauth.account.signals import email_confirmed
from apps.core.services.email_service import EmailService
from apps.core.utils.pii_safe_logging import log_safe_user_context
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils.html import escape

logger = logging.getLogger(__name__)


def is_email_verified(user) -> bool:
    """True only if ``user``'s CURRENT email carries a verified record."""
    if not user.email:
        return False
    return EmailAddress.objects.filter(
        user=user, email__iexact=user.email, verified=True
    ).exists()


def mark_email_verified(user) -> bool:
    """Record ``user.email`` as verified, for accounts created from an email a
    provider has already verified (Google OAuth, Firebase).

    Returns False, and leaves the record unverified, when another account
    already holds this address verified: the DB allows only one.
    """
    if not user.email:
        return False
    address = _address_for(user)
    if address.verified:
        return True
    try:
        with transaction.atomic():
            address.verified = True
            address.primary = True
            address.save(update_fields=["verified", "primary"])
    except IntegrityError:
        logger.warning(
            f"[AUTH] Email already verified on another account; left unverified "
            f"for {log_safe_user_context(user)}"
        )
        return False
    return True


def verification_url(user) -> str:
    """The web page that confirms ``user``'s current email (a signed key)."""
    key = EmailConfirmationHMAC(_address_for(user)).key
    return f"{settings.SITE_URL.rstrip('/')}/verify-email?key={key}"


def send_verification_email(user) -> bool:
    """Email ``user`` a link to confirm their address. False if not sent."""
    if not user.email or is_email_verified(user):
        return False
    url = verification_url(user)
    name = user.first_name or user.username
    text = (
        f"Hi {name},\n\n"
        f"Confirm the email address for your Houseplant MD account:\n\n{url}\n\n"
        "The link works for 3 days. If you didn't create this account, ignore "
        "this email; nothing happens until someone confirms it.\n"
    )
    html = (
        f"<p>Hi {escape(name)},</p>"
        "<p>Confirm the email address for your Houseplant MD account:</p>"
        f'<p><a href="{escape(url)}">Confirm my email</a></p>'
        "<p>The link works for 3 days. If you didn't create this account, ignore "
        "this email; nothing happens until someone confirms it.</p>"
    )
    return EmailService().send_transactional_email(
        recipient=user,
        subject="Confirm your email for Houseplant MD",
        message=text,
        html_message=html,
    )


class VerificationKeyInvalid(Exception):
    """Forged, expired, already used, or for an email the account no longer has."""


def confirm_verification_key(key: str, request=None):
    """Verify the address a key names and return its user.

    Raises ``VerificationKeyInvalid`` for a bad key, a key for an address that is
    no longer the account's email, or an address another account has verified.
    """
    confirmation = EmailConfirmationHMAC.from_key(key or "")
    if confirmation is None:
        raise VerificationKeyInvalid()
    address = confirmation.email_address
    user = address.user
    if address.email.lower() != (user.email or "").lower():
        raise VerificationKeyInvalid()
    try:
        with transaction.atomic():
            if not address.set_verified(commit=True):
                raise VerificationKeyInvalid()
    except IntegrityError as exc:
        raise VerificationKeyInvalid() from exc
    # Existing receivers send the welcome email (apps/users/signals.py).
    email_confirmed.send(sender=EmailAddress, request=request, email_address=address)
    logger.info(f"[AUTH] Email verified for {log_safe_user_context(user)}")
    return user


def _address_for(user) -> EmailAddress:
    address = EmailAddress.objects.filter(user=user, email__iexact=user.email).first()
    if address is None:
        address = EmailAddress.objects.create(
            user=user,
            email=user.email,
            verified=False,
            primary=not EmailAddress.objects.filter(user=user, primary=True).exists(),
        )
    return address
