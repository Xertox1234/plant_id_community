from django.conf import settings
from django.db import models
from django.db.models import F, Q

# Shared with MessageSendSerializer.body (api/serializers.py) — single source
# so the model field and the write-serializer's validation can't drift apart.
MESSAGE_BODY_MAX_CHARS = 4000


class Conversation(models.Model):
    """A 1:1 private-messaging thread between two forum members (todo 319,
    audit M10). Group conversations are out of scope — neither the audit
    finding nor this repo's existing forum surface motivates them.

    Participants are canonicalized by pk (`between()`) so the unordered pair
    is unique regardless of who initiated — symmetric counterpart to
    `UserBlock`'s directional blocker/blocked pair.
    """

    participant_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_conversations_as_a",
    )
    participant_b = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_conversations_as_b",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["participant_a", "participant_b"],
                name="uniq_forum_conversation_pair",
            ),
            models.CheckConstraint(
                condition=~Q(participant_a=F("participant_b")),
                name="forum_conversation_not_self",
            ),
        ]
        indexes = [models.Index(fields=["participant_b"])]

    def __str__(self):
        return f"conversation {self.pk} ({self.participant_a_id} <-> {self.participant_b_id})"

    @classmethod
    def between(cls, user_x, user_y):
        """Get or create the conversation between two users, canonicalizing
        participant order by pk so `between(a, b)` and `between(b, a)` always
        resolve to the same row."""
        lo, hi = (user_x, user_y) if user_x.pk < user_y.pk else (user_y, user_x)
        conversation, _ = cls.objects.get_or_create(participant_a=lo, participant_b=hi)
        return conversation

    def other_participant_id(self, user):
        return (
            self.participant_b_id
            if user.pk == self.participant_a_id
            else self.participant_a_id
        )


class Message(models.Model):
    """A single message within a `Conversation`. Plain text, not a
    StreamField — DM bodies don't need rich authoring/moderation-revision
    machinery, unlike Post/Topic."""

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_messages_sent",
    )
    body = models.TextField(max_length=MESSAGE_BODY_MAX_CHARS)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["conversation", "created_at"],
                name="wf_message_conv_created_idx",
            )
        ]

    def __str__(self):
        return f"message {self.pk} in conversation {self.conversation_id}"
