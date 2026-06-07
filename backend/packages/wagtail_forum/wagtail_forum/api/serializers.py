from rest_framework import serializers

from ..models import ForumBoard, ForumProfile, Topic
from .sanitize import validate_forum_body


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


class MeProfileSerializer(serializers.ModelSerializer):
    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = ForumProfile
        fields = [
            "display_name",
            "bio",
            "signature",
            "trust_level",
            "post_count",
            "flags_received",
            "capabilities",
        ]
        read_only_fields = ["trust_level", "post_count", "flags_received"]

    def get_capabilities(self, obj):
        # v1: static all-True. Trust/lock-aware gating (e.g. can_react only at
        # trust>=1) is a documented follow-up.
        return {
            "can_react": True,
            "can_reply": True,
            "can_create_topic": True,
        }
