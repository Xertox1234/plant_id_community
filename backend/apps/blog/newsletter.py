"""Blog newsletter double opt-in and signed-link unsubscribe (todo 409).

The old endpoint subscribed any address on request, told the caller whether
an address was already on the list, and unsubscribed any address it was
given. Now:

- **Signing up** never changes anything the caller can observe. The view
  validates the address, enqueues `send_newsletter_confirmation` and answers
  the same 202 whatever the address's state; the task decides whether to
  mail. Doing the work in the task also keeps the response time the same.
- **A subscription counts only once its confirmation link is used**
  (`confirmed_at`). The link opens the web app, which POSTs the token: mail
  scanners fetch every GET link, so a GET must never confirm.
- **Unsubscribing takes a signed token**, as for todo 408's account lists.
  Those tokens name a user; a newsletter subscriber may have no account, so
  these carry the subscriber's pk under their own salts. A confirm token is
  useless as an unsubscribe token and the other way round.
"""

import logging
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .constants import (
    NEWSLETTER_CONFIRM_MAX_AGE_SECONDS,
    NEWSLETTER_CONFIRMATION_RESEND_SECONDS,
    NEWSLETTER_UNSUBSCRIBE_MAX_AGE_SECONDS,
)
from .models import BlogNewsletter

logger = logging.getLogger(__name__)

CONFIRM_SALT = "apps.blog.newsletter.confirm"
UNSUBSCRIBE_SALT = "apps.blog.newsletter.unsubscribe"

CONFIRM_HTML_TEMPLATE = "emails/newsletter_confirm.html"
CONFIRM_TEXT_TEMPLATE = "emails/newsletter_confirm.txt"


class NewsletterTokenInvalid(Exception):
    code = "invalid"


class NewsletterTokenExpired(NewsletterTokenInvalid):
    code = "expired"


def normalize_email(email: str) -> str:
    """The stored form of an address: `email` is unique, so case must not
    make two rows for one inbox."""
    return email.strip().lower()


def _stamp(subscriber: BlogNewsletter) -> str:
    sent_at = subscriber.confirmation_sent_at
    return sent_at.isoformat() if sent_at else ""


def make_confirm_token(subscriber: BlogNewsletter) -> str:
    # The stamp ties the token to the latest confirmation email, so sending a
    # new one voids every earlier link.
    return signing.dumps(
        {"s": subscriber.pk, "t": _stamp(subscriber)}, salt=CONFIRM_SALT
    )


def make_unsubscribe_token(subscriber: BlogNewsletter) -> str:
    return signing.dumps({"s": subscriber.pk}, salt=UNSUBSCRIBE_SALT)


def _read(token, salt: str, max_age: int) -> tuple[BlogNewsletter, dict]:
    """The subscriber a genuine, unexpired token names, and its payload.

    Every failure but expiry is the same `NewsletterTokenInvalid`, a deleted
    subscriber included, so the response is no oracle.
    """
    if not isinstance(token, str) or not token:
        raise NewsletterTokenInvalid
    try:
        payload = signing.loads(token, salt=salt, max_age=max_age)
    except signing.SignatureExpired:
        raise NewsletterTokenExpired
    except signing.BadSignature:
        raise NewsletterTokenInvalid
    if not isinstance(payload, dict) or not isinstance(payload.get("s"), int):
        raise NewsletterTokenInvalid
    subscriber = BlogNewsletter.objects.filter(pk=payload["s"]).first()
    if subscriber is None:
        raise NewsletterTokenInvalid
    return subscriber, payload


def confirm(token) -> BlogNewsletter:
    """Confirm the subscription a confirmation token names. Idempotent."""
    subscriber, payload = _read(token, CONFIRM_SALT, NEWSLETTER_CONFIRM_MAX_AGE_SECONDS)
    with transaction.atomic():
        subscriber = BlogNewsletter.objects.select_for_update().get(pk=subscriber.pk)
        if subscriber.is_subscribed:
            return subscriber  # a second click on the link
        if payload.get("t") != _stamp(subscriber):
            # A newer confirmation email went out after this one, or this
            # link was already used: an unsubscribe must not be undone by
            # clicking an old confirmation link again.
            raise NewsletterTokenInvalid
        subscriber.is_active = True
        subscriber.confirmed_at = timezone.now()
        subscriber.unsubscribed_at = None
        # Clearing the stamp voids every confirmation link sent so far.
        subscriber.confirmation_sent_at = None
        subscriber.save(
            update_fields=[
                "is_active",
                "confirmed_at",
                "unsubscribed_at",
                "confirmation_sent_at",
            ]
        )
        logger.info(f"[EMAIL] newsletter subscriber={subscriber.pk} confirmed")
    return subscriber


def unsubscribe(token) -> BlogNewsletter:
    """Unsubscribe the subscriber an unsubscribe token names. Idempotent."""
    subscriber, _ = _read(
        token, UNSUBSCRIBE_SALT, NEWSLETTER_UNSUBSCRIBE_MAX_AGE_SECONDS
    )
    if subscriber.is_active:
        subscriber.unsubscribe()
        logger.info(f"[EMAIL] newsletter subscriber={subscriber.pk} unsubscribed")
    return subscriber


def _web_url(path: str, token: str) -> str:
    # SITE_URL is the web app's origin, as for every other link in our email.
    return f"{settings.SITE_URL.rstrip('/')}{path}?{urlencode({'token': token})}"


def confirm_url(subscriber: BlogNewsletter) -> str:
    return _web_url("/newsletter/confirm", make_confirm_token(subscriber))


def unsubscribe_url(subscriber: BlogNewsletter, token: str | None = None) -> str:
    return _web_url(
        "/newsletter/unsubscribe", token or make_unsubscribe_token(subscriber)
    )


def unsubscribe_headers(subscriber: BlogNewsletter, token: str | None = None) -> dict:
    """List-Unsubscribe headers for one newsletter email (RFC 2369/8058).

    As in `apps.users.email_unsubscribe.unsubscribe_headers`: one-click needs
    an https URL that accepts a bare POST, which is this API's, so it is only
    offered when ``API_PUBLIC_URL`` is set; otherwise the web page.
    """
    token = token or make_unsubscribe_token(subscriber)
    base = getattr(settings, "API_PUBLIC_URL", "")
    if base:
        path = reverse("v1:blog:newsletter-unsubscribe-one-click")
        query = urlencode({"token": token})
        return {
            "List-Unsubscribe": f"<{base.rstrip('/')}{path}?{query}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
    return {"List-Unsubscribe": f"<{unsubscribe_url(subscriber, token)}>"}


def request_confirmation(email: str) -> bool:
    """Mail a confirmation link to `email` unless that is pointless or too soon.

    Returns whether an email was sent. Nothing is sent to an address that is
    already subscribed, or that was sent a link within
    NEWSLETTER_CONFIRMATION_RESEND_SECONDS. A failed send gives the address
    its previous stamp back, so a retry is not throttled by an email that
    never arrived.
    """
    email = normalize_email(email)
    now = timezone.now()
    with transaction.atomic():
        # get_or_create re-reads the row itself when a concurrent signup for
        # the same address wins the insert.
        row, _ = BlogNewsletter.objects.get_or_create(email=email)
        subscriber = BlogNewsletter.objects.select_for_update().get(pk=row.pk)
        if subscriber.is_subscribed:
            return False
        previous = subscriber.confirmation_sent_at
        if previous and now - previous < timedelta(
            seconds=NEWSLETTER_CONFIRMATION_RESEND_SECONDS
        ):
            return False
        subscriber.confirmation_sent_at = now
        subscriber.save(update_fields=["confirmation_sent_at"])

    if _send_confirmation_email(subscriber):
        return True
    BlogNewsletter.objects.filter(pk=subscriber.pk, confirmation_sent_at=now).update(
        confirmation_sent_at=previous
    )
    return False


def _send_confirmation_email(subscriber: BlogNewsletter) -> bool:
    """Send one confirmation email. Never raises: a failure is logged."""
    try:
        # Inside the try: a failure building the link must still undo the
        # stamp, or the address stays throttled with nothing sent.
        site_name = getattr(settings, "SITE_NAME", "Houseplant-MD")
        context = {
            "site_name": site_name,
            "confirm_url": confirm_url(subscriber),
            "confirm_days": NEWSLETTER_CONFIRM_MAX_AGE_SECONDS // (24 * 60 * 60),
        }
        message = EmailMultiAlternatives(
            subject=f"Confirm your {site_name} newsletter subscription",
            body=render_to_string(CONFIRM_TEXT_TEMPLATE, context),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=[subscriber.email],
        )
        message.attach_alternative(
            render_to_string(CONFIRM_HTML_TEMPLATE, context), "text/html"
        )
        message.send()
    except Warning:
        # A RemovedInDjango70Warning is an error under pytest.ini (todo 364)
        # and Warning subclasses Exception: never log it as a failed send
        # (todo 454).
        raise
    except Exception:
        logger.exception(
            f"[EMAIL] newsletter confirmation failed for subscriber={subscriber.pk}"
        )
        return False
    logger.info(f"[EMAIL] newsletter confirmation sent to subscriber={subscriber.pk}")
    return True
