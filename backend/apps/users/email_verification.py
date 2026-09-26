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
which ``User.email`` (not unique) never had.

Confirming takes BOTH halves of the proof: the key from the inbox AND a
session signed in to the account the key names. The key alone is not enough.
If it were, an attacker could register the victim's address, and a victim who
clicked the link in their inbox (steered there by a refused Google sign-in)
would verify the attacker's account for them. Also:

- Confirming is a POST, never a GET, because mail scanners prefetch links.
- Keys are signed under this module's own salt, so allauth's
  ``/accounts/confirm-email/<key>/`` (which needs no session) rejects them.
  allauth's own verification mails are routed here too
  (``CustomAccountAdapter.send_confirmation_mail``).
"""

import logging
from datetime import timedelta

from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed
from apps.core.services.email_service import EmailService
from apps.core.utils.pii_safe_logging import log_safe_user_context
from django.conf import settings
from django.core import signing
from django.db import IntegrityError, transaction
from django.utils.html import escape

logger = logging.getLogger(__name__)

VERIFY_SALT = "apps.users.email_verification"
VERIFY_MAX_AGE = timedelta(days=3)


def is_email_verified(user) -> bool:
    """True only if ``user``'s CURRENT email carries a verified record."""
    if not user.email:
        return False
    return EmailAddress.objects.filter(
        user=user, email__iexact=user.email, verified=True
    ).exists()


def is_address_verified(email) -> bool:
    """True if ANY account holds ``email`` verified. Creation paths refuse such
    an address: a new account could never verify it, so its owner would be
    refused on their next sign-in (todo 447)."""
    return EmailAddress.objects.filter(email__iexact=email, verified=True).exists()


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
    key = signing.dumps({"address": _address_for(user).pk}, salt=VERIFY_SALT)
    return f"{settings.SITE_URL.rstrip('/')}/verify-email?key={key}"


def send_verification_email(user) -> bool:
    """Email ``user`` a link to confirm their address. False if not sent."""
    if not user.email or is_email_verified(user):
        return False
    url = verification_url(user)
    account = user.username
    text = (
        f'Someone created the Houseplant MD account "{account}" with this email '
        "address.\n\n"
        f'If that was you, sign in as "{account}" and open this link to confirm '
        f"the address:\n\n{url}\n\n"
        "The link works for 3 days, and only while signed in to that account.\n\n"
        "If it wasn't you, don't open the link. Nobody can use this address to sign "
        "in with Google until the account's owner confirms it.\n"
    )
    html = (
        f"<p>Someone created the Houseplant MD account <strong>{escape(account)}</strong> "
        "with this email address.</p>"
        f"<p>If that was you, sign in as <strong>{escape(account)}</strong> and open "
        "this link to confirm the address:</p>"
        f'<p><a href="{escape(url)}">Confirm my email</a></p>'
        "<p>The link works for 3 days, and only while signed in to that account.</p>"
        "<p>If it wasn't you, don't open the link. Nobody can use this address to sign "
        "in with Google until the account's owner confirms it.</p>"
    )
    return EmailService().send_transactional_email(
        recipient=user,
        subject="Confirm your email for Houseplant MD",
        message=text,
        html_message=html,
    )


class VerificationKeyInvalid(Exception):
    """Forged, expired, already used, for another account, or for an email the
    account no longer has. One exception on purpose: callers must not tell a
    stranger which of these it was."""


def confirm_verification_key(key, user, request=None):
    """Verify the address ``key`` names, for the signed-in ``user`` only.

    Raises ``VerificationKeyInvalid`` unless the key is genuine and unexpired,
    names an unverified address that belongs to ``user`` and is still their
    email, and no other account holds that address verified.
    """
    if not isinstance(key, str):
        raise VerificationKeyInvalid()
    try:
        payload = signing.loads(
            key, salt=VERIFY_SALT, max_age=VERIFY_MAX_AGE.total_seconds()
        )
        address = EmailAddress.objects.select_related("user").get(
            pk=payload["address"], verified=False
        )
    except (signing.BadSignature, EmailAddress.DoesNotExist, KeyError, TypeError):
        raise VerificationKeyInvalid()
    if address.user_id != user.pk:
        raise VerificationKeyInvalid()
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
