"""Signed email unsubscribe links (todo 408).

A link names ONE user and ONE list, signed with ``django.core.signing`` under
its own salt, and expires. It replaces ``?user=<uuid>``, which let anyone who
knew a user's UUID switch off that user's email.

A list is registered only when its unsubscribe flips a preference the web
Settings page can flip back — otherwise "unsubscribe" would be a one-way door.
That is why ``forum_reply`` turns off the reply EMAIL cell of the forum
notification matrix (todo 343), and not ``User.forum_notifications`` (which
also silences push) or ``User.email_notifications`` (no UI re-enables it).
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Callable
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction

User = get_user_model()

UNSUBSCRIBE_SALT = "apps.users.email_unsubscribe"
# Generous on purpose: people act on an email weeks after it arrives, and a
# dead link just sends them to Settings to do the same thing by hand. It still
# ends, so a link leaked from an old inbox does not work forever.
UNSUBSCRIBE_MAX_AGE = timedelta(days=90)


class UnsubscribeTokenInvalid(Exception):
    """Forged, malformed, for an unknown list, or for no active user."""

    code = "invalid"


class UnsubscribeTokenExpired(UnsubscribeTokenInvalid):
    """Genuine, but older than ``UNSUBSCRIBE_MAX_AGE``."""

    code = "expired"


def _forum_overrides(user):
    from wagtail_forum.models import ForumProfile

    return (
        ForumProfile.objects.filter(user=user)
        .values_list("notification_preferences", flat=True)
        .first()
    )


def _forum_reply_subscribed(user) -> bool:
    from wagtail_forum.preferences import wants_channel

    return wants_channel(_forum_overrides(user), "reply_added", "email")


def _forum_reply_unsubscribe(user) -> None:
    from wagtail_forum.models import ForumProfile
    from wagtail_forum.preferences import merge_preferences

    # Same merge the Settings grid's PATCH uses, under a row lock so a
    # concurrent Settings save cannot drop this cell (or this drop theirs).
    with transaction.atomic():
        profile_pk = ForumProfile.for_user(user).pk
        profile = ForumProfile.objects.select_for_update().get(pk=profile_pk)
        profile.notification_preferences = merge_preferences(
            profile.notification_preferences, {"reply": {"email": False}}
        )
        profile.save(update_fields=["notification_preferences"])


def _forum_digest_subscribed(user) -> bool:
    from wagtail_forum.models import ForumProfile
    from wagtail_forum.models.profiles import DigestFrequency

    frequency = (
        ForumProfile.objects.filter(user=user)
        .values_list("digest_frequency", flat=True)
        .first()
    )
    return frequency not in (None, DigestFrequency.OFF)


def _forum_digest_unsubscribe(user) -> None:
    from wagtail_forum.models import ForumProfile
    from wagtail_forum.models.profiles import DigestFrequency

    # The Settings page's "Email digest" select turns it back on.
    ForumProfile.objects.filter(user=user).update(digest_frequency=DigestFrequency.OFF)


@dataclass(frozen=True)
class EmailList:
    label: str
    is_subscribed: Callable[[User], bool]
    unsubscribe: Callable[[User], None]


LISTS: dict[str, EmailList] = {
    "forum_reply": EmailList(
        label="Email for replies to topics you follow",
        is_subscribed=_forum_reply_subscribed,
        unsubscribe=_forum_reply_unsubscribe,
    ),
    "forum_digest": EmailList(
        label="The weekly forum digest",
        is_subscribed=_forum_digest_subscribed,
        unsubscribe=_forum_digest_unsubscribe,
    ),
}


def make_token(user, list_id: str) -> str:
    if list_id not in LISTS:
        raise ValueError(f"Unknown email list: {list_id}")
    return signing.dumps({"u": str(user.uuid), "l": list_id}, salt=UNSUBSCRIBE_SALT)


def read_token(token) -> tuple:
    """Return ``(user, list_id)`` for a genuine, unexpired token.

    Every failure other than expiry raises the same ``UnsubscribeTokenInvalid``
    — including a valid signature for a user who no longer exists — so the
    response is no oracle for which accounts exist.
    """
    if not isinstance(token, str) or not token:
        raise UnsubscribeTokenInvalid
    try:
        payload = signing.loads(
            token, salt=UNSUBSCRIBE_SALT, max_age=UNSUBSCRIBE_MAX_AGE
        )
    except signing.SignatureExpired:
        raise UnsubscribeTokenExpired
    except signing.BadSignature:
        raise UnsubscribeTokenInvalid
    if not isinstance(payload, dict):
        raise UnsubscribeTokenInvalid
    user_uuid, list_id = payload.get("u"), payload.get("l")
    if not isinstance(user_uuid, str) or list_id not in LISTS:
        raise UnsubscribeTokenInvalid
    user = User.objects.filter(uuid=user_uuid, is_active=True).first()
    if user is None:
        raise UnsubscribeTokenInvalid
    return user, list_id


def unsubscribe_url(user, list_id: str, token: str | None = None) -> str:
    """The web app's unsubscribe page for this user and list (``SITE_URL`` is
    the web app's origin, as for every other link in our email)."""
    query = urlencode({"token": token or make_token(user, list_id)})
    return f"{settings.SITE_URL.rstrip('/')}/unsubscribe?{query}"


def one_click_url(user, list_id: str, token: str | None = None):
    """The RFC 8058 one-click URL on THIS API's origin, or None when
    ``API_PUBLIC_URL`` is unset. A mail provider POSTs to it with no cookies
    and no JavaScript, so it can't be the web page."""
    base = getattr(settings, "API_PUBLIC_URL", "")
    if not base:
        return None
    from django.urls import reverse

    query = urlencode({"token": token or make_token(user, list_id)})
    path = reverse("v1:users:email_unsubscribe_one_click")
    return f"{base.rstrip('/')}{path}?{query}"


def unsubscribe_headers(user, list_id: str, token: str | None = None) -> dict:
    """List-Unsubscribe headers for one email on one list (RFC 2369/8058).

    One-click needs the header's https URL to accept a bare POST, so with
    ``API_PUBLIC_URL`` set the header names the API endpoint and adds
    ``List-Unsubscribe-Post``; without it, the web page (clients open it).
    """
    one_click = one_click_url(user, list_id, token)
    if one_click:
        return {
            "List-Unsubscribe": f"<{one_click}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
    return {"List-Unsubscribe": f"<{unsubscribe_url(user, list_id, token)}>"}


def digest_unsubscribe(user) -> dict:
    """``WAGTAILFORUM_DIGEST_UNSUBSCRIBE``'s callable (todo 416)."""
    # One token for the body link and the header, so they are the same link.
    token = make_token(user, "forum_digest")
    return {
        "url": unsubscribe_url(user, "forum_digest", token),
        "headers": unsubscribe_headers(user, "forum_digest", token),
    }
