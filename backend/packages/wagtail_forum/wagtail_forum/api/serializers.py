from rest_framework import serializers

from ..models import ForumBoard, Topic


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
