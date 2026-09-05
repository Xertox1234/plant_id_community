"""Forum digest email (todo 340) — the package half.

An opt-in pull-back channel for members who don't visit daily. The package
owns the CONTENT and the send (Django's mail API, package templates a host
overrides through normal template resolution); the host owns SCHEDULING
(`manage.py send_forum_digest` from cron/beat — the package never imports
Celery) and the site origin for links.

Two sections, both filtered exactly like the API reads them:

- **watched**: topics the member follows that gained replies since the last
  digest (unread `reply` notifications), grouped per topic.
- **trending**: the most active public topics of the window the member has
  not read since their last post — so a lurker gets something too.

Visibility is the API's: live topics on live, unrestricted boards
(`_visible_boards`), authors the member blocked excluded
(`_exclude_blocked_authors`). Nothing qualifying → no email at all.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives
from django.db.models import Count, Exists, Max, OuterRef
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _

from .conf import get_setting
from .models import (
    DigestFrequency,
    ForumProfile,
    Notification,
    NotificationVerb,
    Topic,
    TopicRead,
)

logger = logging.getLogger("wagtail_forum")

TEXT_TEMPLATE = "wagtail_forum/email/digest.txt"
HTML_TEMPLATE = "wagtail_forum/email/digest.html"


@dataclass(frozen=True)
class DigestTopic:
    id: int
    title: str
    url: str
    board_title: str
    reply_count: int
    last_post_at: datetime | None
    # Replies since the member's last digest — watched section only.
    new_replies: int | None = None


@dataclass(frozen=True)
class Digest:
    user: object
    since: datetime
    display_name: str = ""
    watched: list[DigestTopic] = field(default_factory=list)
    trending: list[DigestTopic] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.watched and not self.trending


def site_url() -> str:
    """Absolute origin for links: the package setting, else the host's
    ``SITE_URL``. Neither set is a configuration error — an email full of
    relative links is dead in every mail client, and it would ship silently
    (same posture as ``UNREAD_LAUNCH_AT``'s ImproperlyConfigured)."""
    origin = get_setting("EMAIL_SITE_URL") or getattr(settings, "SITE_URL", "") or ""
    if not origin:
        raise ImproperlyConfigured(
            "Forum emails need an absolute origin: set WAGTAILFORUM_EMAIL_SITE_URL "
            "or SITE_URL."
        )
    return str(origin).rstrip("/")


def settings_url() -> str:
    return f"{site_url()}{get_setting('DIGEST_SETTINGS_PATH')}"


def digest_recipients(frequency: str = DigestFrequency.WEEKLY):
    """Profiles opted in at `frequency` whose account can receive mail."""
    return (
        ForumProfile.objects.filter(digest_frequency=frequency, user__is_active=True)
        .exclude(user__email="")
        .select_related("user")
        .order_by("pk")
    )


def _topic_row(topic, *, new_replies=None) -> DigestTopic:
    return DigestTopic(
        id=topic.pk,
        title=topic.title,
        url=f"{site_url()}{topic.get_absolute_url()}",
        board_title=topic.board.title,
        reply_count=topic.reply_count,
        last_post_at=topic.last_post_at,
        new_replies=new_replies,
    )


def build_digest(user, since: datetime, profile: ForumProfile | None = None) -> Digest:
    """Assemble `user`'s digest for activity after `since`. Read-only. Pass
    the caller's already-loaded `profile` so rendering needs no re-fetch."""
    from .api.views import _exclude_blocked_authors, _visible_boards

    if profile is None:
        profile = ForumProfile.for_user(user)

    visible_topics = Topic.objects.filter(live=True, board__in=_visible_boards())

    # Watched: unread reply notifications on visible topics since `since`,
    # minus blocked repliers, grouped per topic (newest activity first).
    notes = Notification.objects.filter(
        recipient=user,
        verb=NotificationVerb.REPLY,
        read_at__isnull=True,
        created_at__gte=since,
        topic__in=visible_topics,
    )
    notes = _exclude_blocked_authors(notes, user, author_field="actor_id")
    # The FULL set of followed topics with unread replies is what trending
    # must exclude — not just the capped rows shown — or an overflow topic
    # would resurface as "not seen" (review finding).
    followed_ids = set(notes.values_list("topic_id", flat=True).distinct())
    grouped = list(
        notes.values("topic_id")
        .annotate(new_replies=Count("pk"), latest=Max("created_at"))
        .order_by("-latest", "-topic_id")[: get_setting("DIGEST_MAX_WATCHED_TOPICS")]
    )
    counts = {row["topic_id"]: row["new_replies"] for row in grouped}
    watched_topics = {
        t.pk: t for t in Topic.objects.filter(pk__in=counts).select_related("board")
    }
    watched = [
        _topic_row(watched_topics[row["topic_id"]], new_replies=row["new_replies"])
        for row in grouped
        if row["topic_id"] in watched_topics
    ]

    # Trending: active visible topics of the window the member has not read
    # since their last post, minus the watched ones and blocked authors.
    read_since_last_post = TopicRead.objects.filter(
        user=user, topic=OuterRef("pk"), last_read_at__gte=OuterRef("last_post_at")
    )
    trending_qs = (
        visible_topics.filter(last_post_at__gte=since)
        .exclude(pk__in=followed_ids)
        .exclude(author=user)
        .annotate(seen=Exists(read_since_last_post))
        .filter(seen=False)
        .select_related("board")
    )
    trending_qs = _exclude_blocked_authors(trending_qs, user, author_field="author_id")
    trending = [
        _topic_row(t)
        for t in trending_qs.order_by("-reply_count", "-last_post_at", "-pk")[
            : get_setting("DIGEST_MAX_TRENDING_TOPICS")
        ]
    ]
    return Digest(
        user=user,
        since=since,
        display_name=profile.display_name or user.get_username(),
        watched=watched,
        trending=trending,
    )


def render_digest(digest: Digest) -> tuple[str, str, str]:
    """(subject, text body, html body) from the package templates — a host
    overrides `wagtail_forum/email/digest.txt|html` by shadowing them."""
    context = {
        "user": digest.user,
        "display_name": digest.display_name or digest.user.get_username(),
        "since": digest.since,
        "watched": digest.watched,
        "trending": digest.trending,
        "site_url": site_url(),
        "settings_url": settings_url(),
    }
    subject = _("Your weekly forum digest")
    text = render_to_string(TEXT_TEMPLATE, context)
    html = render_to_string(HTML_TEMPLATE, context)
    return subject, text, html


def send_digest(digest: Digest) -> bool:
    """Send one digest. Never raises: a render/send failure is logged with
    the `[EMAIL]` prefix and reported as False so a batch keeps going."""
    try:
        subject, text, html = render_digest(digest)
        message = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=[digest.user.email],
        )
        message.attach_alternative(html, "text/html")
        message.send(fail_silently=False)
    except Exception as exc:
        # A worker's soft time limit arrives as an Exception subclass
        # (billiard's SoftTimeLimitExceeded); it is the RUN being stopped,
        # not this member's send failing — never swallow it. Matched by name:
        # the package must not import Celery.
        if type(exc).__name__ == "SoftTimeLimitExceeded":
            raise
        logger.exception("[EMAIL] forum digest failed for user=%s", digest.user.pk)
        return False
    logger.info(
        "[EMAIL] forum digest sent to user=%s watched=%d trending=%d",
        digest.user.pk,
        len(digest.watched),
        len(digest.trending),
    )
    return True


def is_due(profile: ForumProfile, now: datetime, window_days: int) -> bool:
    """A member is due when they have never had a digest, or their last one
    is older than the window minus a day of scheduler jitter — so a weekly
    job that fires a few hours early still sends, and a job that runs twice
    in one day does not."""
    if profile.last_digest_sent_at is None:
        return True
    return profile.last_digest_sent_at <= now - timezone.timedelta(days=window_days - 1)


def since_for(profile: ForumProfile, now: datetime, window_days: int) -> datetime:
    """Activity window start: the last digest, capped at one window back."""
    floor = now - timezone.timedelta(days=window_days)
    last = profile.last_digest_sent_at
    return max(last, floor) if last else floor
