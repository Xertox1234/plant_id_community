"""Send-time eligibility for forum deliveries (todo 619).

``notifications.dispatch`` decides who to notify when a post is published.
The FCM, browser-push and email tasks run later: seconds later normally,
minutes or hours later after a retry or a reconciliation. By then the post
may be hidden or deleted, the recipient may have blocked or muted the
author, unfollowed the topic, turned the channel off or been deactivated.
Every external send path calls ``recheck()`` on each attempt, so none of
those changes is overridden by a message that was queued before it.

The package's in-app list already filters hidden topics at read time
(``wagtail_forum.api.notifications._visible_notifications``); this is the
host-side counterpart for the channels that leave the app.

Which checks run
----------------
Recipient state always: the account exists and is active, ``forum_notifications``
is on, the per-event preference for the channel is on, and for email the
master ``email_notifications`` toggle is on and an address is on file.

Content, block/mute and subscription checks run when the payload carries
``actor_id``. ``dispatch`` always writes that key (an empty string when the
event has no actor), so every message it enqueues is fully rechecked. A
payload without it is a message enqueued before this check existed, or a
hand-built one: it has no reliable content reference to recheck.
"""

import logging
from dataclasses import dataclass, field

from wagtail_forum.preferences import wants_channel

logger = logging.getLogger("forum_host.eligibility")

# The FCM data payload and the browser payload must not carry this key: it
# is the host's recheck input, not client data.
INTERNAL_PAYLOAD_KEYS = frozenset({"actor_id"})

# Reasons a recipient is suppressed. Logged and stored on a delivery row;
# never a message body, token or address.
REASON_MISSING = "recipient_missing"
REASON_INACTIVE = "recipient_inactive"
REASON_PREFERENCE = "preference_off"
REASON_NO_DESTINATION = "no_destination"
REASON_CONTENT = "content_unavailable"
REASON_BLOCKED = "blocked_or_muted"
REASON_UNSUBSCRIBED = "unsubscribed"

# The events whose actor is the post's author when the payload names none.
_AUTHOR_IS_ACTOR = frozenset({"reply_added", "mention", "quote"})


@dataclass
class Recheck:
    """The outcome of one recheck: who may still be sent to, and why the
    rest may not."""

    eligible: list = field(default_factory=list)
    suppressed: dict = field(default_factory=dict)  # user pk -> reason
    post: object = None


def client_payload(data: dict) -> dict:
    """``data`` without the host-only recheck keys."""
    return {k: v for k, v in data.items() if k not in INTERNAL_PAYLOAD_KEYS}


def _int_or_none(value):
    text = str(value if value is not None else "").strip()
    return int(text) if text.isdigit() else None


def visible_post(post_id):
    """The post if it is still live on a live topic on a visible board, else
    None. The same predicate as the package's ``_get_visible_post``."""
    from wagtail_forum.api.views import _visible_boards
    from wagtail_forum.models import Post

    if post_id is None:
        return None
    return (
        Post.objects.filter(
            pk=post_id,
            live=True,
            topic__live=True,
            topic__board__in=_visible_boards(),
        )
        .select_related("topic__board", "author")
        .first()
    )


def blocked_recipient_ids(actor_id, recipient_ids) -> set[int]:
    """Recipients who may not hear from ``actor_id``: a block either way, or
    the recipient muted the actor (one direction). The same rule as
    ``notifications._drop_blocked_pairs``, from ids."""
    from wagtail_forum.models import UserBlock, UserMute

    ids = list(recipient_ids)
    if actor_id is None or not ids:
        return set()
    blocked = set(
        UserBlock.objects.filter(blocker_id=actor_id, blocked_id__in=ids).values_list(
            "blocked_id", flat=True
        )
    )
    blocked |= set(
        UserBlock.objects.filter(blocked_id=actor_id, blocker_id__in=ids).values_list(
            "blocker_id", flat=True
        )
    )
    blocked |= set(
        UserMute.objects.filter(muted_id=actor_id, muter_id__in=ids).values_list(
            "muter_id", flat=True
        )
    )
    return blocked


def recheck(
    event: str,
    recipient_ids,
    data: dict,
    channel: str,
    *,
    users=None,
    overrides_by_user=None,
) -> Recheck:
    """Who among ``recipient_ids`` may still be sent ``event`` on ``channel``
    ("push" or "email") right now. A constant number of queries, whatever
    the recipient count.

    ``users`` and ``overrides_by_user`` let a caller that already fetched
    them skip the query (``overrides_by_user`` maps user pk to the
    ForumProfile's ``notification_preferences``; a missing pk means
    defaults). ``Recheck.post`` is the visible post, fetched through the
    visibility predicate, when a full recheck names one.
    """
    from django.contrib.auth import get_user_model
    from wagtail_forum.models import ForumProfile, TopicSubscription

    ids = [int(pk) for pk in recipient_ids]
    result = Recheck()
    if users is None:
        users = list(get_user_model().objects.filter(pk__in=ids))
    by_pk = {user.pk: user for user in users}
    if overrides_by_user is None:
        overrides_by_user = dict(
            ForumProfile.objects.filter(user_id__in=ids).values_list(
                "user_id", "notification_preferences"
            )
        )

    full = "actor_id" in data
    content_gone = False
    blocked: set[int] = set()
    unsubscribed: set[int] = set()
    post = None
    if full:
        post_id = _int_or_none(data.get("post_id"))
        if post_id is not None:
            post = visible_post(post_id)
            content_gone = post is None
        result.post = post
        actor_id = _int_or_none(data.get("actor_id"))
        if actor_id is None and post is not None and event in _AUTHOR_IS_ACTOR:
            actor_id = post.author_id
        if not content_gone:
            blocked = blocked_recipient_ids(actor_id, by_pk)
        if not content_gone and event == "reply_added" and post is not None:
            subscribed = set(
                TopicSubscription.objects.filter(
                    topic_id=post.topic_id, user_id__in=list(by_pk)
                ).values_list("user_id", flat=True)
            )
            unsubscribed = set(by_pk) - subscribed

    for pk in ids:
        user = by_pk.get(pk)
        reason = None
        if user is None:
            reason = REASON_MISSING
        elif not user.is_active:
            reason = REASON_INACTIVE
        elif getattr(user, "forum_notifications", True) is not True:
            reason = REASON_PREFERENCE
        elif channel == "email" and not getattr(user, "email_notifications", True):
            reason = REASON_PREFERENCE
        elif not wants_channel(overrides_by_user.get(pk), event, channel):
            reason = REASON_PREFERENCE
        elif channel == "email" and not user.email:
            reason = REASON_NO_DESTINATION
        elif content_gone:
            reason = REASON_CONTENT
        elif pk in blocked:
            reason = REASON_BLOCKED
        elif pk in unsubscribed:
            reason = REASON_UNSUBSCRIBED
        if reason is None:
            result.eligible.append(user)
        else:
            result.suppressed[pk] = reason
    if result.suppressed:
        logger.info(
            "[FORUM] %s %s: %d recipient(s) no longer eligible at send time (%s)",
            event,
            channel,
            len(result.suppressed),
            ", ".join(sorted(set(result.suppressed.values()))),
        )
    return result
