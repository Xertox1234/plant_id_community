"""Per-topic save-for-later bookmarks (todo 283, audit M2).

Host-agnostic, alongside Topic/TopicSubscription. Deliberately a SEPARATE
model from TopicSubscription — a bookmark is save-for-later intent, a
subscription is notify-me intent, and the two must stay distinct (todo 283
Findings; the pre-283 nearest primitive, TopicSubscription, was notification
intent only).
"""

from django.conf import settings
from django.db import models


class TopicBookmark(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        # Mirrors TopicSubscription's related_name discipline (models/subscriptions.py)
        # — must not clash with forum_subscriptions/forum_notifications/
        # forum_topic_subscriptions/forum_topic_reads, all already claimed on User.
        related_name="forum_topic_bookmarks",
    )
    topic = models.ForeignKey(
        "wagtail_forum.Topic",
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "topic"], name="uniq_topic_bookmark"
            )
        ]
        # No extra single-column index on `topic` (unlike TopicSubscription,
        # which adds one for its "who follows this topic" fan-out query) —
        # every real read here is keyed by `user` (the bookmarks list) or the
        # full (user, topic) pair (the is_bookmarked exists() check), both
        # covered by the unique constraint's own composite index. Same
        # reasoning as TopicRead (models/topic_reads.py).

    def __str__(self):
        return f"TopicBookmark(user={self.user_id}, topic={self.topic_id})"

    @classmethod
    def bookmark(cls, user, topic):
        """Idempotently bookmark `topic` for `user`.

        No `except IntegrityError` retry wrapper — deliberately, unlike this
        package's OLDER TopicSubscription.subscribe. `get_or_create` already
        catches its own `create()`'s IntegrityError and retries its own
        `.get()` internally in this Django version; a caller-added fallback
        on top only ever fires in the case that retry already found
        unrecoverable, turning a correctly-typed IntegrityError into a
        confusing masked DoesNotExist instead. See
        `docs/patterns/architecture/services.md` ("Don't Re-Wrap
        get_or_create's Own Race Recovery") and `TopicRead.mark_read`
        (models/topic_reads.py) for the same fixed shape.
        """
        bookmark, _ = cls.objects.get_or_create(user=user, topic=topic)
        return bookmark

    @classmethod
    def unbookmark(cls, user, topic):
        cls.objects.filter(user=user, topic=topic).delete()
