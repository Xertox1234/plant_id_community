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
from apps.users.constants import VERIFICATION_EMAIL_CAP, VERIFICATION_EMAIL_WINDOW_DAYS
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import IntegrityError, transaction
from django.db.models import Case, F, Q, Value, When
from django.utils import timezone
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


def get_account_by_email(email):
    """``User.objects.get(email__iexact=email)``, except that when case variants
    of the address sit on several accounts, the one account that verified it
    wins. Registration compared emails case-exactly until todo 447, so a
    stranger could park ``Alice@x`` beside the real ``alice@x``; a plain
    ``get`` would then refuse the owner. Raises ``DoesNotExist`` /
    ``MultipleObjectsReturned`` like ``get``."""
    User = get_user_model()
    matches = list(User.objects.filter(email__iexact=email))
    if not matches:
        raise User.DoesNotExist()
    if len(matches) == 1:
        return matches[0]
    verified = [user for user in matches if is_email_verified(user)]
    if len(verified) != 1:
        raise User.MultipleObjectsReturned()
    return verified[0]


def is_address_verified(email) -> bool:
    """True if ANY account holds ``email`` verified. Creation paths refuse such
    an address: a new account could never verify it, so its owner would be
    refused on their next sign-in (todo 447)."""
    return EmailAddress.objects.filter(email__iexact=email, verified=True).exists()


def mark_email_verified(user) -> bool:
    """Record ``user.email`` as verified, for accounts created from an email a
    provider has already verified (Google OAuth, Firebase).

    Returns False, and leaves the record unverified, when another account
    already holds this address verified: the DB allows only one. Goes through
    allauth's ``set_verified`` and never takes ``primary`` from another address
    (todo 447 item 5).
    """
    if not user.email:
        return False
    address = _address_for(user)
    if address.verified:
        return True
    # allauth's own conflict check compares case-exactly (``email=``); rows
    # stored before migration 0014 may differ from ours only in case.
    taken = (
        EmailAddress.objects.filter(email__iexact=address.email, verified=True)
        .exclude(pk=address.pk)
        .exists()
    )
    try:
        with transaction.atomic():
            verified = not taken and address.set_verified(commit=True)
    except IntegrityError:
        verified = False
    if not verified:
        logger.warning(
            f"[AUTH] Email already verified on another account; left unverified "
            f"for {log_safe_user_context(user)}"
        )
        return False
    address.set_as_primary(conditional=True)
    return True


def verification_url(user) -> str:
    """The web page that confirms ``user``'s current email (a signed key)."""
    key = signing.dumps({"address": _address_for(user).pk}, salt=VERIFY_SALT)
    return f"{settings.SITE_URL.rstrip('/')}/verify-email?key={key}"


def send_verification_email(user) -> bool:
    """Queue a mail with a link that confirms ``user``'s address.

    False, with nothing queued, when there is no email, it is already
    verified, or the account has used its ``VERIFICATION_EMAIL_CAP`` mails in
    the current window: a squatter must not be able to keep mailing the
    address's real owner (todo 447 item 9). The slot is claimed in one UPDATE,
    so concurrent resends cannot overshoot the cap; a window that has passed
    restarts at this mail. The mail itself is sent by a Celery task after the
    transaction commits, so SMTP latency never lands on the request (item 11).
    """
    if not user.email or is_email_verified(user):
        return False
    User = get_user_model()
    now = timezone.now()
    new_window = Q(verification_window_started_at__isnull=True) | Q(
        verification_window_started_at__lt=_window_opened_before(now)
    )
    claimed = (
        User.objects.filter(pk=user.pk)
        .filter(new_window | Q(verification_emails_sent__lt=VERIFICATION_EMAIL_CAP))
        .update(
            verification_emails_sent=Case(
                When(new_window, then=Value(1)),
                default=F("verification_emails_sent") + 1,
            ),
            verification_window_started_at=Case(
                When(new_window, then=Value(now)),
                default=F("verification_window_started_at"),
            ),
        )
    )
    if not claimed:
        logger.warning(
            f"[AUTH] Verification mail cap reached for {log_safe_user_context(user)}"
        )
        return False
    enqueue_on_commit(
        "send_verification_email_task", user.pk, context=log_safe_user_context(user)
    )
    return True


def verification_cap_reached(user) -> bool:
    """True while ``user`` has no verification mail left in this window."""
    started = user.verification_window_started_at
    return (
        started is not None
        and started >= _window_opened_before(timezone.now())
        and user.verification_emails_sent >= VERIFICATION_EMAIL_CAP
    )


def _window_opened_before(now):
    return now - timedelta(days=VERIFICATION_EMAIL_WINDOW_DAYS)


def deliver_verification_email(user) -> bool:
    """Send the verification mail now. Called by the Celery task only, which
    skips an address verified meanwhile: a False here means the send failed
    and is retried."""
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


def enqueue_on_commit(task_name, *args, context=""):
    """Queue ``apps.users.tasks.<task_name>`` once the surrounding transaction
    commits. With no transaction open (``ATOMIC_REQUESTS`` is off) the
    ``.delay()`` runs at once, in the request; only the send is deferred, to
    the worker.

    A broker failure is logged, never raised: the request that asked for the
    mail has already succeeded and must not turn into a 500 (todo 447 item 11).
    """

    def _enqueue():
        from apps.users import tasks

        try:
            getattr(tasks, task_name).delay(*args)
        except Exception as exc:
            logger.error(f"[EMAIL] Could not queue {task_name} for {context}: {exc}")

    transaction.on_commit(_enqueue)


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
            email=user.email.lower(),
            verified=False,
            primary=not EmailAddress.objects.filter(user=user, primary=True).exists(),
        )
    return address
