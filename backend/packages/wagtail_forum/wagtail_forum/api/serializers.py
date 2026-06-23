from rest_framework import serializers
from wagtail.blocks import RichTextBlock
from wagtail.rich_text import expand_db_html

from ..models import ForumBoard, ForumProfile, Post, Reaction, Topic
from .sanitize import validate_forum_body

try:  # Schema annotations are optional — hosts without drf-spectacular still work.
    from drf_spectacular.types import OpenApiTypes
    from drf_spectacular.utils import extend_schema_field
except ImportError:  # pragma: no cover

    def extend_schema_field(field):
        def decorator(fn):
            return fn

        return decorator

    class OpenApiTypes:
        BOOL = DATETIME = INT = STR = None


# Bio is stored in an unbounded TextField; bound it at the API boundary like
# post bodies are (MAX_BODY_CHARS) — PATCHing megabytes is storage abuse.
MAX_BIO_CHARS = 2_000

# Inline OpenAPI schemas so drf-spectacular types PostSerializer's
# SerializerMethodFields precisely instead of defaulting each to `string`
# (which also emits an "unable to resolve type hint" warning per method).
AUTHOR_SCHEMA = {
    "type": "object",
    "properties": {
        "username": {"type": "string"},
        "display_name": {"type": "string"},
        "trust_level": {"type": "integer", "nullable": True},
    },
}
BOARD_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "slug": {"type": "string"},
        "title": {"type": "string"},
    },
}
FORUM_BODY_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "type": {"type": "string"},
            "id": {"type": "string", "nullable": True},
        },
    },
}


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


class TopicDetailSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.get_username", default=None)
    last_post_author = serializers.CharField(
        source="last_post_author.get_username", default=None
    )
    board = serializers.SerializerMethodField()
    opening_post_id = serializers.SerializerMethodField()
    locked = serializers.BooleanField()

    class Meta:
        model = Topic
        fields = [
            "id",
            "title",
            "slug",
            "board",
            "author",
            "is_pinned",
            "is_closed",
            "locked",
            "reply_count",
            "view_count",
            "created_at",
            "last_post_at",
            "last_post_author",
            "opening_post_id",
        ]

    @extend_schema_field(BOARD_SCHEMA)
    def get_board(self, obj):
        return {"id": obj.board.id, "slug": obj.board.slug, "title": obj.board.title}

    @extend_schema_field(OpenApiTypes.INT)
    def get_opening_post_id(self, obj):
        post = obj.posts.filter(is_opening_post=True, live=True).only("id").first()
        return post.id if post else None


def serialize_forum_body(stream_value):
    """StreamField -> [{type, value, id}] for the React StreamFieldRenderer.

    RichText (paragraph) blocks are run through expand_db_html() so Wagtail's
    link rewriter runs (SECURITY: blocks.py:18-21) — never raw value.source.
    Phase 1 bodies contain only text blocks (heading/paragraph/quote/code);
    image-block rendition serialization arrives in Phase 3.
    """
    blocks = []
    for bound in stream_value:
        if isinstance(bound.block, RichTextBlock):
            value = expand_db_html(bound.value.source)
        else:
            value = bound.block.get_api_representation(bound.value)
        blocks.append({"type": bound.block_type, "value": value, "id": bound.id})
    return blocks


class PostAuthorSerializer(serializers.Serializer):
    username = serializers.CharField(source="get_username")
    display_name = serializers.SerializerMethodField()
    trust_level = serializers.SerializerMethodField()

    def get_display_name(self, obj):
        full = obj.get_full_name()
        return full or obj.get_username()

    def get_trust_level(self, obj):
        return None  # populated in a later plan when ForumProfile is joined


class PostSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()
    topic_id = serializers.IntegerField()
    edited_at = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "topic_id",
            "author",
            "body",
            "created_at",
            "updated_at",
            "edited_at",
            "is_opening_post",
            "status",
            "reaction_counts",
            "can_edit",
            "can_delete",
        ]

    @extend_schema_field(AUTHOR_SCHEMA)
    def get_author(self, obj):
        if obj.author is None:
            return {
                "username": "[deleted]",
                "display_name": "[deleted]",
                "trust_level": None,
            }
        return PostAuthorSerializer(obj.author).data

    @extend_schema_field(FORUM_BODY_SCHEMA)
    def get_body(self, obj):
        return serialize_forum_body(obj.body)

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_edited_at(self, obj):
        return obj.updated_at if obj.edited else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_status(self, obj):
        return "live" if obj.live else "pending"

    def _is_owner_or_mod(self, obj):
        user = self.context.get("request").user if self.context.get("request") else None
        if not user or not user.is_authenticated:
            return False
        return user == obj.author or user.has_perm("wagtail_forum.change_post")

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_edit(self, obj):
        return self._is_owner_or_mod(obj)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_delete(self, obj):
        return self._is_owner_or_mod(obj)


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


class PostEditSerializer(serializers.Serializer):
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
