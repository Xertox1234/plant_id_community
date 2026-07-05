from rest_framework import serializers
from wagtail.blocks import RichTextBlock
from wagtail.images import get_image_model
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
CAPABILITIES_SCHEMA = {
    "type": "object",
    "properties": {
        "can_react": {"type": "boolean"},
        "can_reply": {"type": "boolean"},
        "can_create_topic": {"type": "boolean"},
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


def serialize_image_for_api(image, request=None):
    """An image block's API value: {id, url, alt, width, height}.

    Serves a bounded `max-1200x1200` rendition (not the 5000px-capped original).
    The URL is made absolute against the request so the web client — served from
    a different origin than the media backend — resolves it correctly.
    """
    rendition = image.get_rendition("max-1200x1200")
    url = rendition.url
    if request is not None:
        url = request.build_absolute_uri(url)
    return {
        "id": image.id,
        "url": url,
        "alt": image.title or "",
        "width": rendition.width,
        "height": rendition.height,
    }


def build_forum_image_map(posts):
    """Map {image_id: Image} for every image block across *posts* (one query).

    Reads each post's raw StreamField data — NOT the resolved bound blocks — so
    collecting ids costs no per-image query, then batch-fetches with prefetched
    renditions. Keeps the post-list query count flat regardless of how many
    images a page references (no N+1). Returns {} when no image blocks exist, so
    a text-only page issues no extra query.
    """
    image_ids = set()
    for post in posts:
        for raw in post.body.raw_data:
            if raw.get("type") == "image" and isinstance(raw.get("value"), int):
                image_ids.add(raw["value"])
    if not image_ids:
        return {}
    images = (
        get_image_model()
        .objects.filter(id__in=image_ids)
        .prefetch_renditions("max-1200x1200")
    )
    return {img.id: img for img in images}


def serialize_forum_body(stream_value, image_map=None, request=None):
    """StreamField -> [{type, value, id}] for the React StreamFieldRenderer.

    Iterates the RAW StreamField data, never the resolved StreamValue: merely
    iterating a StreamValue makes Wagtail bulk-resolve each block type, and for
    image blocks that is an `Image.objects.in_bulk()` PER POST — an N+1 across a
    page (the whole reason build_forum_image_map batches up front). Working from
    raw data sidesteps that: image blocks resolve through *image_map*; every
    other block's to_python/get_api_representation is DB-free.

    RichText (paragraph) raw value IS the stored HTML source, run through
    expand_db_html() so Wagtail's link rewriter runs (SECURITY: blocks.py:18-21)
    — never the unrewritten source. A referenced image missing from the map
    (e.g. deleted after posting) serializes as None.
    """
    image_map = image_map or {}
    child_blocks = stream_value.stream_block.child_blocks
    blocks = []
    for raw in stream_value.raw_data:
        block_type = raw.get("type")
        raw_value = raw.get("value")
        child = child_blocks.get(block_type)
        if block_type == "image":
            image = image_map.get(raw_value)
            value = serialize_image_for_api(image, request) if image else None
        elif isinstance(child, RichTextBlock):
            value = expand_db_html(raw_value or "")
        elif child is not None:
            value = child.get_api_representation(child.to_python(raw_value))
        else:  # unknown type (cannot occur in stored data — validated on write)
            value = raw_value
        blocks.append({"type": block_type, "value": value, "id": raw.get("id")})
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
    topic_id = serializers.IntegerField(read_only=True)
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
        return serialize_forum_body(
            obj.body,
            self.context.get("forum_image_map"),
            self.context.get("request"),
        )

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_edited_at(self, obj):
        return obj.updated_at if obj.edited else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_status(self, obj):
        return "live" if obj.live else "pending"

    def _request_user(self):
        request = self.context.get("request")
        return request.user if request else None

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_edit(self, obj):
        # Full edit policy (owner-or-mod + per-post lock + frozen topic), single-
        # sourced on the model so this button affordance matches PostWriteView's
        # write guard exactly (todo 252). obj.topic is select_related in the list
        # queryset, so this adds no per-post query.
        return obj.can_be_edited_by(self._request_user())

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_delete(self, obj):
        # Same policy as can_edit plus the opening-post rule.
        return obj.can_be_deleted_by(self._request_user())


class _ForumBodyContract(serializers.Serializer):
    """Shared write-body field + validation, so the body contract
    (`validate_forum_body`) is declared ONCE across the create/edit serializers
    instead of byte-copied into three."""

    body = serializers.JSONField()

    def validate_body(self, value):
        return validate_forum_body(value)


class TopicCreateSerializer(_ForumBodyContract):
    title = serializers.CharField(max_length=255)
    slug = serializers.SlugField(max_length=255)


class ReplyCreateSerializer(_ForumBodyContract):
    pass


class PostEditSerializer(_ForumBodyContract):
    # Distinct OpenAPI component name for the edit operation; a PEER of
    # ReplyCreateSerializer off the shared body contract, not chained through it —
    # so a future reply-only field can't leak into the edit request/component.
    pass


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

    @extend_schema_field(CAPABILITIES_SCHEMA)
    def get_capabilities(self, obj):
        # v1: static all-True. Trust/lock-aware gating (e.g. can_react only at
        # trust>=1) is a documented follow-up.
        return {
            "can_react": True,
            "can_reply": True,
            "can_create_topic": True,
        }
