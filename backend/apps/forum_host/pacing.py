"""Quiet hours and reply coalescing for forum deliveries (todo 624).

Owner decisions, 2026-10-12:

- **Quiet hours** are opt-in (``ForumProfile.quiet_hours_enabled``), default
  window 22:00-07:00 in the zone the client reports (UTC if unknown). A push
  or email that would reach the member inside the window is held and released
  when it ends. The in-app inbox is never held. Security mail never comes
  through here: it is sent by ``apps.users`` / ``apps.core.security``, which
  never call this module.
- **Coalescing**: replies on one topic within ``REPLY_COALESCE_SECONDS``
  reach a member as ONE message per channel. Implementation reading
  (2026-10-12): the first reply goes out at once; a reply arriving while the
  member's last message about that topic on that channel is younger than the
  window is held until the window ends, then goes out as one message that
  folds every reply still waiting ("3 new replies"). A steady stream is at
  most one message per window per member, topic and channel, and a quiet
  topic gets no added latency. Mentions, quotes and accepted answers are
  never folded.
- **Read-before-send** is ``eligibility.recheck``'s ``already_read`` reason:
  it runs on every attempt, so it also applies when a held delivery is
  released.

Both holds live in the delivery outbox (``apps.core.delivery.mark_held``),
not in a Celery countdown: a quiet-hours hold can last most of a day, and a
broker message that old is redelivered by Redis's visibility timeout. A
coalescing hold additionally re-enqueues its task for the window's end (a
10-minute countdown is far inside that timeout), so the fold goes out on
time; reconciliation is the backstop for both. Every release goes back
through the owning task, which rechecks eligibility, read state, quiet hours
and the fold exactly as on a first attempt, so a preference changed while a
delivery waits is honoured when it is released.

A delivery with no outbox row (a message from before the outbox) is sent
as before, unpaced: there is nothing durable to hold it in.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from django.utils import timezone

from . import constants

logger = logging.getLogger("forum_host.pacing")

# Events a member sees in their tray or inbox: these are held by quiet
# hours. ``moderation_decided`` is a tray-silent client sync and is not.
PACED_EVENTS = frozenset({"reply_added", "mention", "quote", "answer_accepted"})
# Events folded by the coalescing window.
COALESCED_EVENTS = frozenset({"reply_added"})


@dataclass
class Send:
    """One message to send: to ``user``, for outbox row ``row`` (None when
    the task runs without the outbox), folding the ``folded`` rows (row pk ->
    post id) into it. ``count`` replies in all; ``latest`` is the newest of
    them still worth showing (None: the dispatched post itself)."""

    user: object
    row: int | None = None
    folded: dict = field(default_factory=dict)
    count: int = 1
    latest: object = None


@dataclass
class Paced:
    sends: list = field(default_factory=list)
    # (release instant, hold reason) -> [row pk, ...]
    held: dict = field(default_factory=lambda: defaultdict(list))

    @property
    def coalesce_release(self):
        """When this run's coalescing holds end, or None."""
        from apps.core import delivery

        ends = [at for at, why in self.held if why == delivery.HOLD_COALESCING]
        return max(ends) if ends else None


def quiet_releases(user_ids, now) -> dict[int, object]:
    """{user pk: release instant} for the members whose quiet hours hold a
    delivery right now. One query."""
    from wagtail_forum.models import ForumProfile
    from wagtail_forum.quiet_hours import quiet_release

    ids = list(user_ids)
    if not ids:
        return {}
    releases = {}
    for pk, start, end, zone in ForumProfile.objects.filter(
        user_id__in=ids, quiet_hours_enabled=True
    ).values_list("user_id", "quiet_hours_start", "quiet_hours_end", "time_zone"):
        release = quiet_release(True, start, end, zone, now)
        if release is not None:
            releases[pk] = release
    return releases


def quiet_release_for(user_id, now=None):
    """The release instant holding one member's delivery now, or None."""
    return quiet_releases([user_id], now or timezone.now()).get(int(user_id))


def pace(kind, event, data, claimed, users, *, now=None) -> Paced:
    """Split ``users`` (already rechecked as eligible) into sends now and
    holds. ``claimed`` maps user pk -> the outbox row this run owns; a user
    with no claimed row is skipped. ``claimed`` None means no outbox: every
    user is sent to, unpaced."""
    from apps.core import delivery
    from apps.core.models import DeliveryIntent

    paced = Paced()
    if claimed is None:
        paced.sends = [Send(user) for user in users]
        return paced
    now = now or timezone.now()
    mine = [user for user in users if user.pk in claimed]
    quiet = (
        quiet_releases([user.pk for user in mine], now) if event in PACED_EVENTS else {}
    )
    topic_id = str(data.get("topic_id") or "")
    coalesce = event in COALESCED_EVENTS and bool(topic_id)
    window = timedelta(seconds=constants.REPLY_COALESCE_SECONDS)
    # The member's last message about this topic on this channel, if it is
    # younger than the window: one query for the whole batch.
    last_sent: dict = {}
    if coalesce and mine:
        for pk, at in (
            DeliveryIntent.objects.filter(
                kind=kind,
                event=str(event),
                recipient_id__in=[user.pk for user in mine],
                payload__topic_id=topic_id,
                status=delivery.Status.SENT,
                updated_at__gt=now - window,
            )
            .exclude(last_error=delivery.HANDED_OFF)
            .values_list("recipient_id", "updated_at")
        ):
            last_sent[pk] = max(at, last_sent.get(pk, at))
    for user in mine:
        row = claimed[user.pk]
        release = quiet.get(user.pk)
        if release is not None:
            paced.held[(release, delivery.HOLD_QUIET_HOURS)].append(row)
            continue
        if coalesce:
            if user.pk in last_sent:
                window_end = last_sent[user.pk] + window
                paced.held[(window_end, delivery.HOLD_COALESCING)].append(row)
                continue
            folded = delivery.claim_related(
                kind, event, user.pk, topic_id, exclude=[row]
            )
            paced.sends.append(Send(user, row, folded))
            continue
        paced.sends.append(Send(user, row))
    _count_folds(paced.sends, data.get("post_id"))
    return paced


def _count_folds(sends, dispatched_id=None) -> None:
    """Set each fold's ``count`` and ``latest`` from the folded posts that
    are still visible, unread by that member and not by someone they
    blocked or muted. ``latest`` stays None when the dispatched post
    (``dispatched_id``) is newer than every folded one. A constant number of
    queries per distinct author."""
    from wagtail_forum.models import ForumProfile, Post, TopicRead

    from .eligibility import blocked_recipient_ids, visible_posts

    folding = [send for send in sends if send.folded]
    if not folding:
        return
    post_ids = {
        int(pk) for send in folding for pk in send.folded.values() if str(pk).isdigit()
    }
    # The same visibility predicate as the recheck, in one query.
    visible = visible_posts(post_ids)
    dispatched_at = None
    if str(dispatched_id or "").isdigit():
        dispatched_at = (
            Post.objects.filter(pk=int(dispatched_id))
            .values_list("first_published_at", flat=True)
            .first()
        )
    user_ids = [send.user.pk for send in folding]
    topic_ids = {post.topic_id for post in visible.values()}
    marks: dict = defaultdict(lambda: None)
    for user_id, topic_id, at in TopicRead.objects.filter(
        user_id__in=user_ids, topic_id__in=topic_ids
    ).values_list("user_id", "topic_id", "last_read_at"):
        marks[(user_id, topic_id)] = at
    watermarks = dict(
        ForumProfile.objects.filter(user_id__in=user_ids).values_list(
            "user_id", "read_watermark_at"
        )
    )
    hidden: dict[int, set[int]] = {}
    for author_id in {post.author_id for post in visible.values()}:
        hidden[author_id] = blocked_recipient_ids(author_id, user_ids)
    for send in folding:
        worth = []
        for pk in send.folded.values():
            post = visible.get(int(pk)) if str(pk).isdigit() else None
            if post is None or send.user.pk in hidden.get(post.author_id, set()):
                continue
            published = post.first_published_at
            read_marks = [
                at
                for at in (
                    marks[(send.user.pk, post.topic_id)],
                    watermarks.get(send.user.pk),
                )
                if at is not None
            ]
            if published is not None and any(at >= published for at in read_marks):
                continue
            worth.append(post)
        send.count = 1 + len(worth)
        if worth:
            newest = max(
                worth, key=lambda post: (post.first_published_at or timezone.now())
            )
            # The dispatched post can be the newer one: a reply arriving after
            # the window folds the older replies still held for it.
            if (
                dispatched_at is None
                or newest.first_published_at is None
                or newest.first_published_at > dispatched_at
            ):
                send.latest = newest


def apply_holds(paced: Paced) -> None:
    """Write this run's holds to the outbox. Never raises into a task that
    may already have sent: a row left claimed is re-driven after its lease."""
    from apps.core import delivery
    from django.db import OperationalError

    for (release, reason), rows in paced.held.items():
        try:
            delivery.mark_held(rows, release, reason)
        except OperationalError as exc:
            logger.error(
                "[DELIVERY] could not record a %s hold: %s", reason, type(exc).__name__
            )
    if paced.held:
        logger.info(
            "[FORUM] %d delivery(ies) held (%s)",
            sum(len(rows) for rows in paced.held.values()),
            ", ".join(sorted({reason for _, reason in paced.held})),
        )


def schedule_fold(task, event, data, batch_id, paced: Paced, recipient_ids) -> None:
    """Re-enqueue ``task`` for when this run's coalescing holds end, so the
    fold goes out on time (reconciliation is the backstop)."""
    release = paced.coalesce_release
    if release is None or not batch_id:
        return
    if _another_fold_waits(paced, release):
        # An earlier reply's task already goes out at this release and will
        # fold this one: a second countdown would race it into two messages.
        return
    countdown = max(1, int((release - timezone.now()).total_seconds()) + 1)
    try:
        task.apply_async(
            args=(event, list(recipient_ids), data),
            kwargs={"batch_id": batch_id},
            countdown=countdown,
        )
    except Exception as exc:
        # The rows are pending and due at the release: reconciliation sends
        # them. The type only: a broker error can carry its URL.
        logger.error(
            "[DELIVERY] could not schedule a coalesced send: %s", type(exc).__name__
        )


def _another_fold_waits(paced: Paced, release) -> bool:
    """Whether every row this run held for coalescing has an older held row
    for the same member, topic and channel due at the same release (whose
    own countdown folds it). One query per held row; holds are rare."""
    from apps.core import delivery
    from apps.core.models import DeliveryIntent

    rows = list(
        DeliveryIntent.objects.filter(
            pk__in=[
                pk
                for (at, why), pks in paced.held.items()
                if why == delivery.HOLD_COALESCING
                for pk in pks
            ]
        )
    )
    if not rows:
        return False
    for row in rows:
        older = DeliveryIntent.objects.filter(
            kind=row.kind,
            event=row.event,
            recipient_id=row.recipient_id,
            payload__topic_id=row.payload.get("topic_id"),
            status=delivery.Status.PENDING,
            last_error=delivery.HOLD_COALESCING,
            next_attempt_at=row.next_attempt_at,
            pk__lt=row.pk,
        ).exists()
        if not older:
            return False
    return True


def finish_folds(send: Send, delivered: bool) -> None:
    """A fold's rows share its outcome: covered by the message that went
    out, or handed back for their own attempt when it did not."""
    from apps.core import delivery
    from django.db import OperationalError

    if not send.folded:
        return
    try:
        if delivered:
            delivery.mark_suppressed(list(send.folded), "coalesced")
        else:
            delivery.release(list(send.folded))
    except OperationalError as exc:
        logger.error(
            "[DELIVERY] could not record a coalesced fold: %s", type(exc).__name__
        )


def folded_data(data: dict, send: Send) -> dict:
    """The payload for ``send``: the dispatched one, or for a fold the newest
    reply's post and author and the reply count."""
    if send.count <= 1:
        return data
    if send.latest is None:
        # The dispatched post is the newest: its own post and author.
        return {**data, "count": str(send.count)}
    author = getattr(send.latest, "author", None)
    return {
        **data,
        "post_id": str(send.latest.pk),
        "actor_name": getattr(author, "display_name", "") if author else "",
        "count": str(send.count),
    }


QUIET_FIELDS = frozenset(
    {"quiet_hours_enabled", "quiet_hours_start", "quiet_hours_end", "time_zone"}
)


def reschedule_quiet_holds(profile, now=None) -> int:
    """Move a member's quiet-hours holds to their window as it now stands
    (todo 624): turning quiet hours off, or moving the window so that now
    is outside it, makes them due now; a changed window moves them to its
    new end. Reconciliation then releases them; the owning task rechecks
    everything else on release. Returns the rows moved."""
    from apps.core import delivery
    from apps.core.models import DeliveryIntent
    from wagtail_forum.quiet_hours import profile_release

    now = now or timezone.now()
    release = profile_release(profile, now) or now
    return DeliveryIntent.objects.filter(
        recipient_id=profile.user_id,
        kind__in=[
            delivery.Kind.FORUM_EMAIL,
            delivery.Kind.FORUM_WEB_PUSH,
            delivery.Kind.FORUM_PUSH,
        ],
        status=delivery.Status.PENDING,
        last_error=delivery.HOLD_QUIET_HOURS,
    ).update(next_attempt_at=release)
