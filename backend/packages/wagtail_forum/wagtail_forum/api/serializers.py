from rest_framework import serializers

from ..models import ForumBoard, ForumProfile, Reaction, Topic
from .sanitize import validate_forum_body

# Bio is stored in an unbounded TextField; bound it at the API boundary like
# post bodies are (MAX_BODY_CHARS) — PATCHing megabytes is storage abuse.
MAX_BIO_CHARS = 2_000


class BoardSerializer(serializers.ModelSerializer):
    class Meta:
        model = ForumBoard
        fields = ["id", "title", "slug", "description", "topic_count", "post_count"]


class TopicListSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.get_username", default=None)
    last_post_author = serializers.CharField(
        source="last_post_author.get_username", default=None
    )

    class Meta:
        model = Topic
        fields = [
            "id",
            "title",
            "slug",
            "author",
            "is_pinned",
            "is_closed",
            "reply_count",
            "view_count",
            "last_post_at",
            "last_post_author",
        ]


class TopicCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    slug = serializers.SlugField(max_length=255)
    body = serializers.JSONField()

    def validate_body(self, value):
        return validate_forum_body(value)


class ReplyCreateSerializer(serializers.Serializer):
    body = serializers.JSONField()

    def validate_body(self, value):
        return validate_forum_body(value)


class ReactionSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=Reaction.REACTION_CHOICES)


class MeProfileSerializer(serializers.ModelSerializer):
    capabilities = serializers.SerializerMethodField()
    bio = serializers.CharField(
        max_length=MAX_BIO_CHARS, required=False, allow_blank=True
    )

    class Meta:
        model = ForumProfile
        # flags_received deliberately NOT exposed: it would give a spammer a
        # live signal of proximity to moderation thresholds (audit L12).
        fields = [
            "display_name",
            "bio",
            "signature",
            "trust_level",
            "post_count",
            "capabilities",
        ]
        read_only_fields = ["trust_level", "post_count"]

    def get_capabilities(self, obj):
        # v1: static all-True. Trust/lock-aware gating (e.g. can_react only at
        # trust>=1) is a documented follow-up.
        return {
            "can_react": True,
            "can_reply": True,
            "can_create_topic": True,
        }
