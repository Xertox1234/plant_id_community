"""Email provider feedback, suppression and click attribution (todo 625).

The deployed provider is Resend over SMTP (owner, 2026-10-12). Resend signs
each webhook with Svix; this module verifies that signature by hand (the
documented scheme: https://docs.svix.com/receiving/verifying-payloads/how-manual),
records each event once, applies it to the ``EmailNotification`` it belongs
to, and keeps the suppression list.

Suppression policy (also in docs/operations/notification-baseline.md):

- A permanent bounce, or Resend's ``email.suppressed`` (the address is on
  Resend's own suppression list), suppresses the address for ALL mail.
  Resend drops such a send anyway, so sending is futile, and recording the
  attempt as sent would claim a recovery mail went out when it did not.
- A spam complaint suppresses OPTIONAL mail only: forum notifications,
  digests and the newsletter. Mail the account needs (verification, password
  reset and sign-in notices, lockout, newsletter confirmation) still goes.
- A transient or undetermined bounce is recorded on the email and suppresses
  nothing.

Suppression only stops a message at the moment of sending. It never changes
what an account-security flow does or answers: the verification allowance,
lockout, tokens and every anti-enumeration response run exactly as before.

Message correlation: ``EmailService.send_email`` sets the Message-ID of each
tracked email itself (``<hpmd.{uuid}@{sender domain}>``) and stores it on the
row; Resend reports it as ``data.message_id``. Its own ``data.email_id`` is
stored from the first matching event, so a later event carrying only that id
still finds the row. That Resend keeps a client-set Message-ID over SMTP is
documented for its API, not yet observed for this sender (todo 638).
Address-level suppression works whether or not an event matches a row.

Click attribution (owner decision 2026-10-12): first-party signed click
redirects only, no open tracking, no pixel, no third-party analytics. See
``click_url`` and ``record_click``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from email.utils import parseaddr
from typing import Iterable, Optional
from urllib.parse import urlsplit

from django.conf import settings
from django.core import signing
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .constants import (
    EMAIL_CLICK_ATTRIBUTION_DAYS,
    EMAIL_FEEDBACK_PRUNE_BATCH,
    EMAIL_FEEDBACK_RETENTION_DAYS,
    EMAIL_WEBHOOK_TOLERANCE_SECONDS,
)

logger = logging.getLogger(__name__)

CLICK_SALT = "apps.core.email_feedback.click"

# The events this app acts on. Anything else (email.sent, delivery_delayed,
# opened, clicked, contact or domain events) is recorded and ignored: opens
# are never collected, and clicks come from our own redirect.
EVENT_DELIVERED = "email.delivered"
EVENT_BOUNCED = "email.bounced"
EVENT_COMPLAINED = "email.complained"
EVENT_SUPPRESSED = "email.suppressed"
HANDLED_EVENTS = frozenset(
    {EVENT_DELIVERED, EVENT_BOUNCED, EVENT_COMPLAINED, EVENT_SUPPRESSED}
)

PERMANENT_BOUNCE = "Permanent"


class WebhookSignatureError(Exception):
    """Missing, malformed, stale or wrong Svix signature headers."""


class MalformedEvent(ValueError):
    """A correctly signed body that is not a usable event."""


# ---------------------------------------------------------------------------
# Signature
# ---------------------------------------------------------------------------


def _secret_key(secret: str) -> bytes:
    """The HMAC key of a ``whsec_<base64>`` secret. Raises ValueError for a
    secret that is not base64: that is a configuration fault, not a bad
    request."""
    raw = secret[len("whsec_") :] if secret.startswith("whsec_") else secret
    try:
        return base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("RESEND_WEBHOOK_SECRET is not a whsec_ base64 secret") from exc


def verify_signature(
    secret: str,
    *,
    msg_id: str,
    timestamp: str,
    signature: str,
    body: bytes,
    now: Optional[float] = None,
) -> None:
    """Raise ``WebhookSignatureError`` unless ``body`` carries a valid Svix
    signature made within ``EMAIL_WEBHOOK_TOLERANCE_SECONDS`` of ``now``.

    Signed content is ``{svix-id}.{svix-timestamp}.{raw body}``, HMAC-SHA256
    with the base64-decoded secret; ``svix-signature`` is a space-separated
    list of ``v1,<base64>`` entries (several during a secret rotation). The
    time window is the replay defence for an event older than the stored
    ids (``EmailProviderEvent`` rows are pruned after 90 days).
    """
    if not (msg_id and timestamp and signature):
        raise WebhookSignatureError("missing signature headers")
    try:
        sent_at = int(timestamp)
    except ValueError as exc:
        raise WebhookSignatureError("malformed timestamp") from exc
    current = time.time() if now is None else now
    if abs(current - sent_at) > EMAIL_WEBHOOK_TOLERANCE_SECONDS:
        raise WebhookSignatureError("timestamp outside the tolerance")
    key = _secret_key(secret)
    signed = f"{msg_id}.{timestamp}.".encode() + body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest())
    for entry in signature.split(" "):
        version, _, value = entry.partition(",")
        if version == "v1" and hmac.compare_digest(value.encode(), expected):
            return
    raise WebhookSignatureError("no matching signature")


def sign(secret: str, *, msg_id: str, timestamp: str, body: bytes) -> str:
    """The ``svix-signature`` value for a body: what Resend sends. Used by
    tests and by an operator checking a captured request."""
    digest = hmac.new(
        _secret_key(secret), f"{msg_id}.{timestamp}.".encode() + body, hashlib.sha256
    ).digest()
    return "v1," + base64.b64encode(digest).decode()


# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------


def address_hash(address: str) -> str:
    """SHA-256 of the normalized bare address. A pseudonym, not anonymity: it
    lets a suppression outlive the account without storing the address."""
    bare = parseaddr(address or "")[1] or (address or "")
    return hashlib.sha256(bare.strip().lower().encode()).hexdigest()


def blocked_reasons(addresses: Iterable[str]) -> dict[str, str]:
    """{address hash: reason} for each suppressed address in ``addresses``.
    Keyed by hash, not by spelling: every spelling of one address ("Bob
    <b@x>", "B@X") must find the same row, so callers look up
    ``address_hash(address)``."""
    from .models import EmailSuppression

    hashes = {address_hash(a) for a in addresses if a}
    if not hashes:
        return {}
    return dict(
        EmailSuppression.objects.filter(address_hash__in=hashes).values_list(
            "address_hash", "reason"
        )
    )


def reason_blocks(reason: Optional[str], *, optional: bool) -> bool:
    """Whether a suppression ``reason`` stops a message. A hard bounce stops
    everything; a complaint stops optional mail only."""
    from .models import EmailSuppression

    if reason == EmailSuppression.Reason.HARD_BOUNCE:
        return True
    return optional and reason == EmailSuppression.Reason.COMPLAINT


def is_suppressed(address: str, *, optional: bool) -> bool:
    """Whether ``address`` must not get this message. Fails open: a database
    error lets the message go (Resend still drops a suppressed address) rather
    than lose account mail during an outage."""
    if not address:
        return False
    try:
        reason = blocked_reasons([address]).get(address_hash(address))
    except DatabaseError as exc:
        logger.warning(f"[EMAIL] suppression lookup failed: {type(exc).__name__}")
        return False
    return reason_blocks(reason, optional=optional)


# Set by the bulk optional-mail send sites (the forum digest, the blog
# newsletter), so the backstop classifies them as optional even when their
# unsubscribe hook failed and the message carries no List-Unsubscribe. The
# wagtail_forum package writes the same literal (it cannot import this).
OPTIONAL_MAIL_HEADER = "X-Optional-Mail"

# What a direct send path returns when the backstop dropped its only
# recipient (``message.send()`` answered 0): neither sent nor failed, so the
# caller neither stamps it sent nor counts it as a failure to recover.
SUPPRESSED = "suppressed"


def has_list_unsubscribe(message) -> bool:
    """Whether ``message`` is optional mail: it carries List-Unsubscribe (the
    forum notification types, the forum digest and the blog newsletter), or
    the explicit ``OPTIONAL_MAIL_HEADER`` marker. Account mail carries
    neither. The mail backend classifies by this."""
    headers = getattr(message, "extra_headers", None) or {}
    names = {str(name).lower() for name in headers}
    return "list-unsubscribe" in names or OPTIONAL_MAIL_HEADER.lower() in names


def filter_suppressed_messages(messages):
    """The messages still to send, each with its suppressed recipients
    removed; a message with none left is dropped. The backstop in the mail
    backend (``apps.core.mail_backends``), so a send path that never asked
    ``is_suppressed`` (the digests, the newsletter, the package's own mail)
    still honours the list."""
    messages = list(messages)
    try:
        reasons = blocked_reasons(
            {addr for m in messages for addr in m.recipients() if addr}
        )
    except DatabaseError as exc:
        logger.warning(f"[EMAIL] suppression lookup failed: {type(exc).__name__}")
        return messages
    if not reasons:
        return messages
    kept = []
    for message in messages:
        optional = has_list_unsubscribe(message)

        def keep(addresses, optional=optional):
            return [
                a
                for a in addresses
                if not (
                    a and reason_blocks(reasons.get(address_hash(a)), optional=optional)
                )
            ]

        to, cc, bcc = keep(message.to), keep(message.cc), keep(message.bcc)
        # Counted from what keep() removed, never from recipients(), which
        # leaves out blank entries keep() passes through.
        dropped = sum(
            len(before) - len(after)
            for before, after in (
                (message.to, to),
                (message.cc, cc),
                (message.bcc, bcc),
            )
        )
        if dropped > 0:
            logger.info(
                f"[EMAIL] {dropped} suppressed recipient(s) removed from a message"
            )
        if not (to or cc or bcc):
            continue
        message.to, message.cc, message.bcc = to, cc, bcc
        kept.append(message)
    return kept


def _suppress(addresses: Iterable[str], reason: str, svix_id: str) -> int:
    """Suppress each address, strengthening (never weakening) a row."""
    from .models import EmailSuppression

    rank: dict[str, int] = {
        EmailSuppression.Reason.COMPLAINT: 1,
        EmailSuppression.Reason.HARD_BOUNCE: 2,
    }
    changed = 0
    for address in addresses:
        row, created = EmailSuppression.objects.get_or_create(
            address_hash=address_hash(address),
            defaults={"reason": reason, "source_event": svix_id},
        )
        if created:
            changed += 1
        elif rank[reason] > rank.get(row.reason, 0):
            row.reason, row.source_event = reason, svix_id
            row.save(update_fields=["reason", "source_event", "updated_at"])
            changed += 1
    return changed


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedEvent:
    event_type: str
    occurred_at: datetime
    email_id: str
    message_id: str
    recipients: tuple[str, ...]
    bounce_type: str
    bounce_subtype: str


def _text(value, field: str, *, required: bool = False, limit: int = 255) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value):
        raise MalformedEvent(f"{field} must be a non-empty string")
    return value[:limit]


def parse_event(payload) -> ParsedEvent:
    """Validate a decoded webhook body. Raises ``MalformedEvent``."""
    if not isinstance(payload, dict):
        raise MalformedEvent("the body must be a JSON object")
    event_type = _text(payload.get("type"), "type", required=True, limit=40)
    occurred = parse_datetime(
        _text(payload.get("created_at"), "created_at", required=True)
    )
    if occurred is None:
        raise MalformedEvent("created_at must be an ISO 8601 time")
    if timezone.is_naive(occurred):
        occurred = timezone.make_aware(occurred, dt_timezone.utc)
    data = payload.get("data")
    if not isinstance(data, dict):
        raise MalformedEvent("data must be an object")
    recipients = data.get("to", [])
    if isinstance(recipients, str):
        recipients = [recipients]
    if not isinstance(recipients, list) or not all(
        isinstance(r, str) for r in recipients
    ):
        raise MalformedEvent("data.to must be a list of addresses")
    bounce = data.get("bounce") or {}
    if not isinstance(bounce, dict):
        raise MalformedEvent("data.bounce must be an object")
    if event_type in HANDLED_EVENTS and not recipients:
        raise MalformedEvent("data.to is empty")
    return ParsedEvent(
        event_type=event_type,
        occurred_at=occurred,
        email_id=_text(data.get("email_id"), "data.email_id", limit=64),
        message_id=_text(data.get("message_id"), "data.message_id").strip(),
        recipients=tuple(recipients),
        bounce_type=_text(bounce.get("type"), "data.bounce.type", limit=32),
        bounce_subtype=_text(bounce.get("subType"), "data.bounce.subType", limit=32),
    )


def normalize_message_id(value: str) -> str:
    """A Message-ID's comparable form: no surrounding whitespace or angle
    brackets, lowercased. A provider may report it bare ("hpmd.x@domain") or
    in another case; the stored one is ``<hpmd.x@domain>``."""
    return (value or "").strip().strip("<>").strip().lower()


def _find_notification(event: ParsedEvent):
    from .models import EmailNotification

    bare = normalize_message_id(event.message_id)
    if bare:
        # Stored lowercased in its header form (EmailService._message_id), so
        # both spellings are exact, indexed lookups.
        row = EmailNotification.objects.filter(
            message_id__in=[f"<{bare}>", bare]
        ).first()
        if row is not None:
            return row
    if event.email_id:
        return EmailNotification.objects.filter(
            provider_email_id=event.email_id
        ).first()
    return None


def _apply_to_notification(row, event: ParsedEvent) -> None:
    """Order-independent: each event sets its own timestamp once (the
    earliest wins), and the status moves only up the ladder sent < delivered
    < bounced < complained. A delivery report that arrives after the bounce,
    or twice, changes nothing it should not."""
    from .models import EmailNotification as N

    ladder = {
        N.STATUS_PENDING: 0,
        N.STATUS_FAILED: 0,
        N.STATUS_SENT: 0,
        N.STATUS_DELIVERED: 1,
        N.STATUS_BOUNCED: 2,
        N.STATUS_COMPLAINED: 3,
    }
    status, stamp = {
        EVENT_DELIVERED: (N.STATUS_DELIVERED, "delivered_at"),
        EVENT_BOUNCED: (N.STATUS_BOUNCED, "bounced_at"),
        EVENT_SUPPRESSED: (N.STATUS_BOUNCED, "bounced_at"),
        EVENT_COMPLAINED: (N.STATUS_COMPLAINED, "complained_at"),
    }[event.event_type]
    fields = []
    current = getattr(row, stamp)
    if current is None or event.occurred_at < current:
        setattr(row, stamp, event.occurred_at)
        fields.append(stamp)
    if ladder[status] > ladder.get(row.status, 0):
        row.status = status
        fields.append("status")
    if event.email_id and not row.provider_email_id:
        row.provider_email_id = event.email_id
        fields.append("provider_email_id")
    if fields:
        row.save(update_fields=fields)


def ingest(svix_id: str, event: ParsedEvent) -> str:
    """Record and apply one verified event. Returns ``duplicate`` when this
    svix id was already recorded (nothing is applied twice), ``ignored`` for
    an event this app does not act on, else ``processed``."""
    from .models import EmailNotification, EmailProviderEvent, EmailSuppression

    with transaction.atomic():
        try:
            with transaction.atomic():
                record = EmailProviderEvent.objects.create(
                    svix_id=svix_id,
                    event_type=event.event_type,
                    occurred_at=event.occurred_at,
                    provider_email_id=event.email_id,
                    bounce_type=event.bounce_type,
                    bounce_subtype=event.bounce_subtype,
                )
        except IntegrityError:
            return "duplicate"
        if event.event_type not in HANDLED_EVENTS:
            return "ignored"
        row = _find_notification(event)
        if row is not None:
            row = EmailNotification.objects.select_for_update().get(pk=row.pk)
            _apply_to_notification(row, event)
            record.notification = row
            record.save(update_fields=["notification"])
        if event.event_type == EVENT_COMPLAINED:
            _suppress(event.recipients, EmailSuppression.Reason.COMPLAINT, svix_id)
        elif event.event_type == EVENT_SUPPRESSED or (
            event.event_type == EVENT_BOUNCED and event.bounce_type == PERMANENT_BOUNCE
        ):
            _suppress(event.recipients, EmailSuppression.Reason.HARD_BOUNCE, svix_id)
    logger.info(
        f"[EMAIL] provider event {event.event_type} recorded "
        f"(matched={row is not None})"
    )
    return "processed"


# ---------------------------------------------------------------------------
# Click attribution
# ---------------------------------------------------------------------------


def _origin(url: str) -> tuple[str, str]:
    parts = urlsplit(url or "")
    return parts.scheme.lower(), parts.netloc.lower()


def is_site_url(url: str) -> bool:
    """Only links into our own web app are ever wrapped or redirected to:
    the redirect can never become an open redirect, even with a leaked key."""
    site = _origin(getattr(settings, "SITE_URL", ""))
    return bool(site[1]) and site[0] in ("http", "https") and _origin(url) == site


def click_tracking_enabled() -> bool:
    return bool(
        getattr(settings, "EMAIL_CLICK_TRACKING_ENABLED", True)
        and getattr(settings, "API_PUBLIC_URL", "")
    )


def click_url(notification_uuid, link: str, target: str) -> str:
    """``target`` behind a signed first-party redirect on the API origin, or
    ``target`` unchanged when tracking is off or it is not a site link."""
    if not (click_tracking_enabled() and is_site_url(target)):
        return target
    from django.urls import reverse

    token = signing.dumps(
        {"n": str(notification_uuid), "l": link, "u": target},
        salt=CLICK_SALT,
        compress=True,
    )
    base = settings.API_PUBLIC_URL.rstrip("/")
    return f"{base}{reverse('v1:email-click', args=[token])}"


def read_click_token(token: str) -> Optional[dict]:
    """The token's payload, or None if forged or malformed. A click token
    never expires: an old email's link keeps working; it is just no longer
    counted (``record_click``)."""
    try:
        data = signing.loads(token, salt=CLICK_SALT)
    except signing.BadSignature:
        return None
    if not (
        isinstance(data, dict)
        and all(isinstance(data.get(k), str) for k in ("n", "l", "u"))
        and is_site_url(data["u"])
    ):
        return None
    return data


def record_click(notification_uuid: str, link: str, *, now=None) -> bool:
    """Count one click. True only for the first click on this email's
    ``link`` inside ``EMAIL_CLICK_ATTRIBUTION_DAYS`` of the send: a repeat,
    a late click and a click on an unknown email are not counted. Never
    raises a database error: counting is best-effort and the reader's link
    must always work, so an outage costs the count, never the redirect."""
    try:
        return _record_click(notification_uuid, link, now=now)
    except DatabaseError as exc:
        logger.warning(f"[EMAIL] click not recorded: {type(exc).__name__}")
        return False


def _record_click(notification_uuid: str, link: str, *, now=None) -> bool:
    from .models import EmailClick, EmailNotification

    now = now or timezone.now()
    row = (
        EmailNotification.objects.filter(uuid=notification_uuid)
        .only("pk", "user", "sent_at")
        .first()
    )
    if row is None or row.sent_at is None:
        return False
    if now - row.sent_at > timedelta(days=EMAIL_CLICK_ATTRIBUTION_DAYS):
        return False
    try:
        with transaction.atomic():
            EmailClick.objects.create(
                notification=row, user_id=row.user_id, link=link[:32], clicked_at=now
            )
    except IntegrityError:
        return False
    return True


def prune(now=None) -> dict[str, int]:
    """Delete click rows and provider events older than the retention, in
    batches of ``EMAIL_FEEDBACK_PRUNE_BATCH``."""
    from .models import EmailClick, EmailProviderEvent

    cutoff = (now or timezone.now()) - timedelta(days=EMAIL_FEEDBACK_RETENTION_DAYS)
    return {
        "clicks": _delete_in_batches(EmailClick.objects.filter(clicked_at__lt=cutoff)),
        "events": _delete_in_batches(
            EmailProviderEvent.objects.filter(received_at__lt=cutoff)
        ),
    }


def _delete_in_batches(queryset) -> int:
    deleted = 0
    while True:
        pks = list(queryset.values_list("pk", flat=True)[:EMAIL_FEEDBACK_PRUNE_BATCH])
        if not pks:
            return deleted
        count, _ = queryset.model.objects.filter(pk__in=pks).delete()
        deleted += count
