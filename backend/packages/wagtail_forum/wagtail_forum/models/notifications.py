"""Persisted in-app notifications (todo 253 slice 1, audit C2).

Kept in the package alongside Topic/Post so the primitive is host-agnostic;
delivery (FCM push, email) is a host concern — see
``apps/forum_host/notifications.py`` and the fan-out helper in
``wagtail_forum.notifications``.
"""

from django.conf import settings
from django.db import models


class NotificationVerb(models.TextChoices):
    REPLY = "reply", "Reply"
    # mention/moderation/subscription verbs are added by later slices of
    # todo 253 (H4, H2/H3).


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        # NOT "forum_notifications" — that name collides with the existing
        # User.forum_notifications preference BooleanField (apps/users/models.py)
        # and trips Django's reverse-accessor clash check at import time.
        related_name="received_forum_notifications",
    )
    # None for a system-generated notification with no single actor.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    verb = models.CharField(max_length=20, choices=NotificationVerb.choices)
    topic = models.ForeignKey(
        "wagtail_forum.Topic",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    post = models.ForeignKey(
        "wagtail_forum.Post",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at"]),
            models.Index(fields=["recipient", "-created_at"]),
        ]
        constraints = [
            # Idempotency backstop for the fan-out helper's bulk_create(...,
            # ignore_conflicts=True) — a signal firing twice for the same
            # reply must not duplicate a recipient's notification. NOTE:
            # Postgres never treats NULL as equal to NULL, so this does NOT
            # dedupe rows where `post` is null — every verb defined so far
            # (reply) always sets `post`; a future post-less verb needs its
            # own dedupe key.
            models.UniqueConstraint(
                fields=["recipient", "verb", "post"], name="uniq_notification_target"
            )
        ]

    def __str__(self):
        return f"Notification({self.verb}) to user {self.recipient_id}"
