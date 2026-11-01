"""Per-topic follow/unfollow subscriptions (todo 253 slice 3, audit H2/H3).

Host-agnostic, alongside Topic/Notification — delivery (who gets pushed/
emailed) is decided by the fan-out call site in
``apps/forum_host/notifications.py``, which reads this model to build its
recipient list instead of hard-coding the topic author.
"""

from django.conf import settings
from django.db import models


class TopicSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        # NOT "forum_notifications"/"received_forum_notifications"
        # (User.forum_notifications pref / Notification.recipient) — either
        # trips Django's reverse-accessor clash check at import time.
        related_name="forum_topic_subscriptions",
    )
    topic = models.ForeignKey(
        "wagtail_forum.Topic",
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "topic"], name="uniq_topic_subscription"
            )
        ]
        indexes = [
            models.Index(fields=["topic"]),  # fan-out reads "who follows this topic"
        ]

    def __str__(self):
        return f"TopicSubscription(user={self.user_id}, topic={self.topic_id})"

    @classmethod
    def subscribe(cls, user, topic):
        """Idempotently subscribe `user` to `topic`.

        Concurrent first-touch requests (e.g. two replies from the same user
        racing) can both miss the SELECT and race to INSERT. get_or_create
        owns that race: its INSERT runs in its own savepoint and an
        IntegrityError is retried as a .get() before it is re-raised, so the
        loser gets the winner's row. That savepoint — not any try/except
        here — is also what keeps callers inside the ambient publish
        transaction (apps/forum_host/notifications.py) safe: a naked
        `.create()` would poison the outer transaction, get_or_create never
        does. The former outer wrapper (audit 2026-09-04 L2) could only fire
        in the unrecoverable case and turned it into a misleading
        DoesNotExist. Mirrors ForumProfile.for_user (models/profiles.py).
        """
        subscription, _ = cls.objects.get_or_create(user=user, topic=topic)
        return subscription

    @classmethod
    def unsubscribe(cls, user, topic):
        cls.objects.filter(user=user, topic=topic).delete()


class ForumWatchLevel(models.TextChoices):
    """Per-forum notification levels (todo 672; Discourse's four, owner
    decision 2026-10-30). No row = the forum's default: topics you follow
    still notify you, nothing else does."""

    # Every post: notified of each new topic, and auto-subscribed to it so
    # its replies notify too.
    WATCHING = "watching", "Watching"
    # New topics only: notified of each new topic, not of its replies.
    WATCHING_FIRST_POST = "watching_first_post", "Watching first post"
    # Unread counts on the forum's row; no notifications.
    TRACKING = "tracking", "Tracking"
    # Left out of Recent and the digest.
    MUTED = "muted", "Muted"


# The levels that are told about a new topic.
NEW_TOPIC_LEVELS = (ForumWatchLevel.WATCHING, ForumWatchLevel.WATCHING_FIRST_POST)
# The levels whose forum row shows an unread count (Discourse: watching
# implies tracking).
COUNTED_LEVELS = (
    ForumWatchLevel.WATCHING,
    ForumWatchLevel.WATCHING_FIRST_POST,
    ForumWatchLevel.TRACKING,
)


class ForumSubscription(models.Model):
    """One member's watch level on one forum (todo 672)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_watch_levels",
    )
    forum = models.ForeignKey(
        "wagtail_forum.Forum",
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    level = models.CharField(max_length=24, choices=ForumWatchLevel.choices)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "forum"], name="uniq_forum_subscription"
            )
        ]
        indexes = [
            # The new-topic fan-out reads "who watches this forum".
            models.Index(fields=["forum", "level"]),
        ]

    def __str__(self):
        return (
            f"ForumSubscription(user={self.user_id}, forum={self.forum_id}, "
            f"level={self.level})"
        )

    @classmethod
    def muted_forum_ids(cls, user):
        """A lazy subquery of the forums ``user`` muted (empty for guests)."""
        if user is None or not getattr(user, "is_authenticated", False):
            return cls.objects.none().values("forum_id")
        return cls.objects.filter(user=user, level=ForumWatchLevel.MUTED).values(
            "forum_id"
        )
