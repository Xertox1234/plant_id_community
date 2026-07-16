"""Per-topic explicit read markers (todo 253 slice 5, audit H10).

Host-agnostic, alongside Topic/Notification/TopicSubscription. This is the
per-topic half of "unread" — the per-user fallback baseline for a topic
never explicitly opened lives on ``ForumProfile.read_watermark_at``. See
``wagtail_forum/api/views.py``'s ``_annotate_topic_unread`` for how the two
combine into the unread computation on the topic-list endpoint.
"""

from django.conf import settings
from django.db import IntegrityError, models
from django.utils import timezone


class TopicRead(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_topic_reads",
    )
    topic = models.ForeignKey(
        "wagtail_forum.Topic",
        on_delete=models.CASCADE,
        related_name="+",
    )
    last_read_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "topic"], name="uniq_topic_read")
        ]
        # No extra single-column index (TopicSubscription adds one on just
        # `topic`, for its "who follows this topic" fan-out query) — every
        # read here, at both call sites, is always keyed by the full
        # (user, topic) pair, already covered by the unique constraint's
        # own index.

    def __str__(self):
        return f"TopicRead(user={self.user_id}, topic_id={self.topic_id})"

    @classmethod
    def mark_read(cls, user, topic_id, when=None):
        """Idempotently record that `user` has read topic `topic_id` as of `when`.

        Takes a raw pk (not a Topic instance) — its one caller
        (TopicDetailView.retrieve) already avoids re-fetching the topic for
        the neighboring view_count update, and this mirrors that same
        id-only economy.

        update_or_create's own IntegrityError handling is defensive, not
        relied on bare — matches this package's house convention
        (ForumProfile.for_user, TopicSubscription.subscribe/unsubscribe) of
        keeping the explicit fallback so this stays safe if ever called from
        inside an ambient transaction.atomic() block.
        """
        when = when or timezone.now()
        try:
            obj, _ = cls.objects.update_or_create(
                user=user, topic_id=topic_id, defaults={"last_read_at": when}
            )
        except IntegrityError:
            obj = cls.objects.get(user=user, topic_id=topic_id)
            obj.last_read_at = when
            obj.save(update_fields=["last_read_at"])
        return obj
