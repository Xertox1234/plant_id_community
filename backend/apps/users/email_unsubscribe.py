"""Signed email unsubscribe links (todo 408).

A link names ONE user and ONE list, signed with ``django.core.signing`` under
its own salt, and expires. It replaces ``?user=<uuid>``, which let anyone who
knew a user's UUID switch off that user's email.

A list is registered only when its unsubscribe flips a preference the web
Settings page can flip back — otherwise "unsubscribe" would be a one-way door.
That is why ``forum_reply`` turns off the reply EMAIL cell of the forum
notification matrix (todo 343), and not ``User.forum_notifications`` (which
also silences push). A list's own link turns off that ONE list, never the
account-wide ``User.email_notifications`` master switch, which web Settings
and the mobile profile both show since todo 620 (docs/notifications-policy.md).
With that master switch off, no list's email is sent, whatever the list says.

The one exception is the reader's own choice to stop everything (todo 703,
CASL and CAN-SPAM): ``stop_all_optional_email`` turns the master switch off
and leaves the blog newsletter at the account's address, in one step, with
any list's link. The ``all_optional`` list is that same action as a list, for
email such as the welcome message that belongs to no other list. Settings
turns the master switch back on, and the newsletter form signs up again.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Callable
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction

if TYPE_CHECKING:
    # The concrete class, so `User` is valid as an annotation (todo 580).
    from apps.users.models import User
else:
    User = get_user_model()

UNSUBSCRIBE_SALT = "apps.users.email_unsubscribe"
ALL_OPTIONAL = "all_optional"
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


def _forum_email_subscribed(verb: str) -> Callable[["User"], bool]:
    """Whether the member's email cell for ``verb`` is on."""

    def is_subscribed(user) -> bool:
        from wagtail_forum.preferences import wants_channel

        return bool(wants_channel(_forum_overrides(user), verb, "email"))

    return is_subscribed


def _forum_email_unsubscribe(verb: str) -> Callable[["User"], None]:
    """Turn off the member's email cell for ``verb``, and nothing else."""

    def unsubscribe(user) -> None:
        from wagtail_forum.models import ForumProfile
        from wagtail_forum.preferences import merge_preferences

        # Same merge the Settings grid's PATCH uses, under a row lock so a
        # concurrent Settings save cannot drop this cell (or this drop theirs).
        with transaction.atomic():
            profile_pk = ForumProfile.for_user(user).pk
            profile = ForumProfile.objects.select_for_update().get(pk=profile_pk)
            profile.notification_preferences = merge_preferences(
                profile.notification_preferences, {verb: {"email": False}}
            )
            profile.save(update_fields=["notification_preferences"])

    return unsubscribe


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


def _all_optional_subscribed(user) -> bool:
    """Whether any optional email can still reach the account."""
    from apps.blog.models import BlogNewsletter

    if user.email_notifications:
        return True
    if not user.email:
        return False
    # Confirmed rows only: BlogNewsletter.is_subscribed, the rows a
    # newsletter actually reaches. A pending signup receives nothing.
    return BlogNewsletter.objects.filter(
        email__iexact=user.email, is_active=True, confirmed_at__isnull=False
    ).exists()


def stop_all_optional_email(user) -> None:
    """Stop every optional email to the account (todo 703). Idempotent.

    Optional email is what docs/operations/notification-baseline.md calls
    optional: forum notification email, the forum digest and the blog
    newsletter. The master switch covers the first two; the newsletter is a
    separate subscription by address, so a row for the account's address is
    unsubscribed too. Account mail (verification, password reset, security
    notices) is not optional and still goes.
    """
    from apps.blog.models import BlogNewsletter

    # One transaction: a failure part-way must not leave the master switch
    # off with the newsletter still on.
    with transaction.atomic():
        User.objects.filter(pk=user.pk).update(email_notifications=False)
        if user.email:
            for subscriber in BlogNewsletter.objects.select_for_update().filter(
                email__iexact=user.email, is_active=True
            ):
                subscriber.unsubscribe()
                if subscriber.confirmed_at is None:
                    # A pending signup: void the confirmation links already
                    # sent, as newsletter.confirm() does, so an old link in
                    # the inbox cannot switch the newsletter back on.
                    subscriber.confirmation_sent_at = None
                    subscriber.save(update_fields=["confirmation_sent_at"])
    user.email_notifications = False


@dataclass(frozen=True)
class EmailList:
    label: str
    is_subscribed: Callable[[User], bool]
    unsubscribe: Callable[[User], None]


LISTS: dict[str, EmailList] = {
    "forum_reply": EmailList(
        label="Email for replies to topics you follow",
        is_subscribed=_forum_email_subscribed("reply"),
        unsubscribe=_forum_email_unsubscribe("reply"),
    ),
    # Optional important-event email (todo 624): each link turns off its
    # own email cell, which the Settings grid (web and mobile) turns back on.
    "forum_mention": EmailList(
        label="Email when someone mentions you",
        is_subscribed=_forum_email_subscribed("mention"),
        unsubscribe=_forum_email_unsubscribe("mention"),
    ),
    "forum_quote": EmailList(
        label="Email when someone quotes your post",
        is_subscribed=_forum_email_subscribed("quote"),
        unsubscribe=_forum_email_unsubscribe("quote"),
    ),
    "forum_solution": EmailList(
        label="Email when your answer is accepted",
        is_subscribed=_forum_email_subscribed("solution"),
        unsubscribe=_forum_email_unsubscribe("solution"),
    ),
    "forum_digest": EmailList(
        label="The weekly forum digest",
        is_subscribed=_forum_digest_subscribed,
        unsubscribe=_forum_digest_unsubscribe,
    ),
    # Every optional email at once (todo 703): the welcome message's link,
    # and what the page's "stop all" button does with any list's link.
    ALL_OPTIONAL: EmailList(
        label="All optional email: forum notifications, the forum digest and the blog newsletter",
        is_subscribed=_all_optional_subscribed,
        unsubscribe=stop_all_optional_email,
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
    except signing.SignatureExpired as exc:
        raise UnsubscribeTokenExpired from exc
    except signing.BadSignature as exc:
        raise UnsubscribeTokenInvalid from exc
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
    site_url = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
    return f"{site_url}/unsubscribe?{query}"


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
