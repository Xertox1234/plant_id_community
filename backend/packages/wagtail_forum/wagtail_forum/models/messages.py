from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# Shared with MessageSendSerializer.body (api/serializers.py) — single source
# so the model field and the write-serializer's validation can't drift apart.
MESSAGE_BODY_MAX_CHARS = 4000
# Inbox row preview length (ConversationSerializer.last_message.body).
MESSAGE_PREVIEW_CHARS = 140
# Group conversation title (todo 350) — shared with the create serializer.
GROUP_TITLE_MAX_CHARS = 80
# Raw length bound on a group-create invite list, checked BEFORE per-item
# validation (the cap on members is DM_GROUP_MAX_PARTICIPANTS, a setting).
MAX_GROUP_INVITE_ITEMS = 50


class ConversationKind(models.TextChoices):
    DIRECT = "direct", _("Direct")
    GROUP = "group", _("Group")


class Conversation(models.Model):
    """A private-messaging thread (todo 319, audit M10) — a canonical 1:1
    pair (`kind=direct`, `between()`) or a titled group (`kind=group`,
    todo 350). Membership for EVERY kind lives in `ConversationParticipant`
    rows (one per member, carrying that member's read marker); the direct
    pair additionally keeps `participant_a/b` so the unordered pair stays
    unique regardless of who initiated — symmetric counterpart to
    `UserBlock`'s directional blocker/blocked pair. A group has no pair
    (both null) and dedups only on the client's Idempotency-Key.
    """

    kind = models.CharField(
        max_length=8, choices=ConversationKind.choices, default=ConversationKind.DIRECT
    )
    title = models.CharField(max_length=GROUP_TITLE_MAX_CHARS, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="forum_conversations_created",
    )
    participant_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_conversations_as_a",
        null=True,
        blank=True,
    )
    participant_b = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_conversations_as_b",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # Inbox contract (todo 339). Activity ordering: bumped to the message's
    # timestamp on every send. Never null — a conversation only exists once a
    # message was sent, so it starts at that first message (migration 0032
    # backfills older rows from their newest message).
    last_message_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-last_message_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["participant_a", "participant_b"],
                name="uniq_forum_conversation_pair",
            ),
            models.CheckConstraint(
                condition=~Q(participant_a=F("participant_b")),
                name="forum_conversation_not_self",
            ),
            # A direct thread has its pair; a group has none — never half.
            models.CheckConstraint(
                condition=(
                    Q(
                        kind="direct",
                        participant_a__isnull=False,
                        participant_b__isnull=False,
                    )
                    | Q(
                        kind="group",
                        participant_a__isnull=True,
                        participant_b__isnull=True,
                    )
                ),
                name="forum_conversation_kind_shape",
            ),
        ]
        indexes = [models.Index(fields=["participant_b"])]

    def __str__(self):
        if self.kind == ConversationKind.GROUP:
            return f"group conversation {self.pk} ({self.title!r})"
        return f"conversation {self.pk} ({self.participant_a_id} <-> {self.participant_b_id})"

    @property
    def is_group(self):
        return self.kind == ConversationKind.GROUP

    @classmethod
    def between(cls, user_x, user_y):
        """Get or create the DIRECT conversation between two users,
        canonicalizing participant order by pk so `between(a, b)` and
        `between(b, a)` always resolve to the same row — and its two
        participant rows, which `for_pair`'s inbox/read machinery reads."""
        lo, hi = (user_x, user_y) if user_x.pk < user_y.pk else (user_y, user_x)
        conversation, created = cls.objects.get_or_create(
            participant_a=lo,
            participant_b=hi,
            defaults={"kind": ConversationKind.DIRECT},
        )
        if created:
            # Only on first contact: migration 0036 backfilled every existing
            # pair, so the hot send path pays no extra INSERT (cross-cutting
            # review, todo 350). ignore_conflicts covers a get_or_create race.
            ConversationParticipant.objects.bulk_create(
                [
                    ConversationParticipant(conversation=conversation, user=lo),
                    ConversationParticipant(conversation=conversation, user=hi),
                ],
                ignore_conflicts=True,
            )
        return conversation

    @classmethod
    def create_group(cls, creator, title, members):
        """A titled group with `creator` plus `members` (users, deduped,
        creator excluded). The caller validates the cap and block pairs —
        this is the persistence step only (todo 350)."""
        conversation = cls.objects.create(
            kind=ConversationKind.GROUP, title=title, created_by=creator
        )
        users = {creator.pk: creator}
        for member in members:
            users.setdefault(member.pk, member)
        ConversationParticipant.objects.bulk_create(
            [
                ConversationParticipant(conversation=conversation, user=u)
                for u in users.values()
            ]
        )
        return conversation

    def participant_ids(self):
        return set(self.participants.values_list("user_id", flat=True))

    def is_participant(self, user):
        return self.participants.filter(user_id=user.pk).exists()

    def other_participant_id(self, user):
        """Direct threads only: the other side's user id."""
        return (
            self.participant_b_id
            if user.pk == self.participant_a_id
            else self.participant_a_id
        )

    def mark_read(self, user, at=None):
        """Advance `user`'s read marker to `at` (default: now). One UPDATE by
        participant row — never a save() of a possibly-stale instance."""
        ConversationParticipant.objects.filter(
            conversation_id=self.pk, user_id=user.pk
        ).update(read_at=at or timezone.now())


class ConversationParticipant(models.Model):
    """Membership + per-member read marker for every conversation (todo 350
    moved the two `participant_x_read_at` columns here so groups and pairs
    share one read model). A message from ANOTHER member created after my
    `read_at` is unread to me; null = I never opened the thread."""

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_conversation_memberships",
    )
    joined_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["joined_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"], name="uniq_forum_conversation_member"
            )
        ]
        indexes = [models.Index(fields=["user", "conversation"])]

    def __str__(self):
        return f"member {self.user_id} of conversation {self.conversation_id}"


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
