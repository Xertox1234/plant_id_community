"""Per-topic follow/unfollow subscriptions (todo 253 slice 3, audit H2/H3).

Host-agnostic, alongside Topic/Notification — delivery (who gets pushed/
emailed) is decided by the fan-out call site in
``apps/forum_host/notifications.py``, which reads this model to build its
recipient list instead of hard-coding the topic author.
"""

from django.conf import settings
from django.db import IntegrityError, models


class TopicSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        # NOT "forum_subscriptions" (the legacy apps.core model already
        # claims it) and NOT "forum_notifications"/"received_forum_notifications"
        # (User.forum_notifications pref / Notification.recipient) — any of
        # those trips Django's reverse-accessor clash check at import time.
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

        get_or_create is not atomic: under concurrent first-touch requests
        (e.g. two replies from the same user racing) two callers can both
        miss the SELECT and race to INSERT, with the loser hitting the
        unique constraint. Fall back to a plain get() in that case — mirrors
        ForumProfile.for_user (models/profiles.py). get_or_create's INSERT
        runs in its own inner savepoint, so the IntegrityError rolls back
        only that savepoint; callers invoking this inside the ambient
        publish transaction (apps/forum_host/notifications.py) are safe as
        long as this exact try/except shape is preserved — a naked
        `.create()` here would poison the outer transaction instead.
        """
        try:
            subscription, _ = cls.objects.get_or_create(user=user, topic=topic)
        except IntegrityError:
            subscription = cls.objects.get(user=user, topic=topic)
        return subscription

    @classmethod
    def unsubscribe(cls, user, topic):
        cls.objects.filter(user=user, topic=topic).delete()
