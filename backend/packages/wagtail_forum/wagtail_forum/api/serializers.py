from rest_framework import serializers
from wagtail.blocks import RichTextBlock
from wagtail.images import get_image_model
from wagtail.rich_text import expand_db_html

from ..collections import get_forum_image_collection
from ..models import (
    ForumBoard,
    ForumProfile,
    Notification,
    Post,
    Reaction,
    Report,
    Topic,
    TopicSubscription,
)
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
        "avatar": {"type": "string", "nullable": True},
        "trust_level": {"type": "integer", "nullable": True},
    },
}


def _deleted_author():
    """The single deleted-author convention (H26/M41): one `[deleted]` sentinel
    OBJECT everywhere — topics used to send `null`, posts a partial sentinel."""
    return {
        "username": "[deleted]",
        "display_name": "[deleted]",
        "avatar": None,
        "trust_level": None,
    }


def serialize_forum_author(user, request=None):
    """Unified author object for EVERY topic + post payload (H26): `author`,
    `last_post_author`, and a post's author all share this shape.

    Reads `ForumProfile` via the reverse OneToOne (`wagtail_forum_profile`);
    `getattr(..., None)` yields None (no query) for an author with no profile
    row AND issues no query when the view select_related-joined the profile.
    Avatar is the raw image file URL (absolute) — deliberately NOT a rendition,
    so a select_related-joined avatar costs zero per-row queries and the list
    query-count pins stay flat (todo 257 slice A / H7).
    """
    if user is None:
        return _deleted_author()
    profile = getattr(user, "wagtail_forum_profile", None)
    display_name = (
        (profile.display_name if profile and profile.display_name else None)
        or user.get_full_name()
        or user.get_username()
    )
    avatar = None
    # `avatar_id` (the FK column) is already loaded — gate on it so we never
    # touch `.avatar` (a query if NOT select_related-joined) for the common
    # no-avatar case.
    if profile and profile.avatar_id and profile.avatar:
        avatar = profile.avatar.file.url
        if request is not None:
            avatar = request.build_absolute_uri(avatar)
    return {
        "username": user.get_username(),
        "display_name": display_name,
        "avatar": avatar,
        "trust_level": profile.trust_level if profile else None,
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
            # The block content — the field codegen clients actually need
            # (audit 2026-07-11 H25): HTML string (paragraph), plain string
            # (heading/quote), {language, code} (code block), or the
            # {id, url, alt, width, height} rendition dict (image).
            "value": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "object", "additionalProperties": True},
                ],
                # null when an image block's Image row was deleted after
                # publish (serialize_forum_body emits value=None) — mirrors id.
                "nullable": True,
            },
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
    author = serializers.SerializerMethodField()
    last_post_author = serializers.SerializerMethodField()
    # LockableMixin field, same as the detail serializer: the write guard is
    # `is_closed OR locked`, so list clients need both to render the lock badge
    # and predict write-eligibility (audit 2026-07-11 L3).
    locked = serializers.BooleanField()
    # Always annotated by the view's queryset (_annotate_topic_unread), so a
    # plain BooleanField needs no SerializerMethodField/default fallback
    # (todo 253 slice 5, H10).
    is_unread = serializers.BooleanField(read_only=True)

    class Meta:
        model = Topic
        fields = [
            "id",
            "title",
            "slug",
            "author",
            "is_pinned",
            "is_closed",
            "locked",
            "reply_count",
            "view_count",
            "last_post_at",
            "last_post_author",
            "is_unread",
        ]

    @extend_schema_field(AUTHOR_SCHEMA)
    def get_author(self, obj):
        # Always an object; a deleted author (author_id None) → [deleted] sentinel.
        return serialize_forum_author(obj.author, self.context.get("request"))

    @extend_schema_field(AUTHOR_SCHEMA)
    def get_last_post_author(self, obj):
        # Secondary "last activity by" pointer: the object when a last poster is
        # known, else null. Unlike `author` (the topic creator, which gets the
        # [deleted] sentinel when SET_NULL'd — M41), a null here is deliberately
        # NOT the sentinel: the denormalized fields can't tell "no live posts"
        # (last_post_author_id None, last_post_at Coalesced to created_at) apart
        # from "last poster's account gone" (also last_post_author_id None) —
        # signals.py sets both the same way. Distinguishing them needs a live-post
        # existence query, which would break the flat list pin (AC: pins unchanged).
        if obj.last_post_author_id is None:
            return None
        return serialize_forum_author(obj.last_post_author, self.context.get("request"))


class TopicDetailSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    last_post_author = serializers.SerializerMethodField()
    board = serializers.SerializerMethodField()
    opening_post_id = serializers.SerializerMethodField()
    locked = serializers.BooleanField()
    is_subscribed = serializers.SerializerMethodField()

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
            "is_subscribed",
        ]

    @extend_schema_field(AUTHOR_SCHEMA)
    def get_author(self, obj):
        return serialize_forum_author(obj.author, self.context.get("request"))

    @extend_schema_field(AUTHOR_SCHEMA)
    def get_last_post_author(self, obj):
        # Null (not the [deleted] sentinel) when unknown — see the list
        # serializer's get_last_post_author for the denorm/pin rationale.
        if obj.last_post_author_id is None:
            return None
        return serialize_forum_author(obj.last_post_author, self.context.get("request"))

    @extend_schema_field(BOARD_SCHEMA)
    def get_board(self, obj):
        return {"id": obj.board.id, "slug": obj.board.slug, "title": obj.board.title}

    @extend_schema_field(OpenApiTypes.INT)
    def get_opening_post_id(self, obj):
        post = obj.posts.filter(is_opening_post=True, live=True).only("id").first()
        return post.id if post else None

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_subscribed(self, obj):
        # Anonymous short-circuits with zero queries — todo 253 slice 3.
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        return TopicSubscription.objects.filter(user=user, topic=obj).exists()


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


class PostSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()
    topic_id = serializers.IntegerField(read_only=True)
    edited_at = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    reacted = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    can_report = serializers.SerializerMethodField()

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
            "reacted",
            "can_edit",
            "can_delete",
            "can_report",
        ]

    @extend_schema_field(AUTHOR_SCHEMA)
    def get_author(self, obj):
        return serialize_forum_author(obj.author, self.context.get("request"))

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

    @extend_schema_field(
        {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [choice[0] for choice in Reaction.REACTION_CHOICES],
            },
        }
    )
    def get_reacted(self, obj):
        # Which reaction types the CURRENT user has active on this post (M23) —
        # `[]` for anonymous. On the list endpoint this reads a per-page batched
        # map from context (forum_reacted_map, built once in PostListView.list),
        # so it costs zero per-post queries and the authed list pin stays flat
        # under N posts. Single-post responses (edit/reply-create) carry no map
        # and fall back to ONE O(1) query — deliberately, so the edit response's
        # reacted state is correct and a replace-the-post client update
        # (ThreadDetailPage.handleEditSubmit) can't clobber it.
        # NB for future callers: any NEW many=True PostSerializer usage over an
        # authed request MUST seed `forum_reacted_map` in context (like
        # build_forum_image_map) — otherwise this fallback fires per row and
        # reintroduces the N+1 the batched map exists to prevent.
        user = self._request_user()
        if user is None or not user.is_authenticated:
            return []
        reacted_map = self.context.get("forum_reacted_map")
        if reacted_map is not None:
            return reacted_map.get(obj.id, [])
        return list(
            Reaction.objects.filter(post=obj, user=user).values_list(
                "reaction_type", flat=True
            )
        )

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

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_report(self, obj):
        # False for the post's own author and for anonymous viewers.
        return obj.can_be_reported_by(self._request_user())


NOTIFICATION_TOPIC_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "slug": {"type": "string"},
        "title": {"type": "string"},
        "board_id": {"type": "integer"},
        "board_slug": {"type": "string"},
    },
    "nullable": True,
}


class NotificationSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()
    topic = serializers.SerializerMethodField()
    # Deep-link target for clients (wave 1.3): the post this notification is
    # about, or null for a post-less verb.
    post_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = ["id", "verb", "actor", "topic", "post_id", "created_at", "read_at"]

    @extend_schema_field(AUTHOR_SCHEMA)
    def get_actor(self, obj):
        # Unified author object (todo 257 H26/M41): the actor shares the exact
        # shape + `[deleted]` sentinel as every topic/post author. A null actor
        # means the acting account was deleted after the notification was
        # created (SET_NULL) → serialize_forum_author returns the sentinel.
        # The queryset select_relates actor__wagtail_forum_profile__avatar so
        # this stays flat (test_notifications_api pins 2 queries).
        return serialize_forum_author(obj.actor, self.context.get("request"))

    @extend_schema_field(NOTIFICATION_TOPIC_SCHEMA)
    def get_topic(self, obj):
        if obj.topic_id is None:
            return None
        return {
            "id": obj.topic_id,
            "slug": obj.topic.slug,
            "title": obj.topic.title,
            "board_id": obj.topic.board_id,
            "board_slug": obj.topic.board.slug,
        }


class _ForumBodyContract(serializers.Serializer):
    """Shared write-body field + validation, so the body contract
    (`validate_forum_body`) is declared ONCE across the create/edit serializers
    instead of byte-copied into three."""

    body = serializers.JSONField()

    def validate_body(self, value):
        return validate_forum_body(value, self._allowed_uploader_ids())

    def _allowed_uploader_ids(self):
        # An image block may reference: (a) something the acting request user
        # uploaded, and (b) on edit, whatever the post's PRE-EXISTING author
        # already uploaded — PATCH resends the whole body, so a moderator
        # editing someone else's post must not have the original author's
        # existing image blocks rejected out from under them (audit L21).
        # `existing_author_id` is only set by the edit call site.
        request = self.context.get("request")
        ids = {request.user.pk} if request else set()
        if "existing_author_id" in self.context:
            ids.add(self.context["existing_author_id"])
        return ids


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


class ReportSerializer(serializers.Serializer):
    reason = serializers.ChoiceField(choices=Report.REASON_CHOICES)
    detail = serializers.CharField(max_length=280, required=False, default="")


class MeProfileSerializer(serializers.ModelSerializer):
    capabilities = serializers.SerializerMethodField()
    bio = serializers.CharField(
        max_length=MAX_BIO_CHARS, required=False, allow_blank=True
    )
    # Write-only: the mobile app PATCHes this on login to register its FCM
    # device token. Never returned in responses — a token is a credential.
    fcm_token = serializers.CharField(
        max_length=255, required=False, allow_blank=True, write_only=True
    )
    # Read side: the absolute avatar URL (or null). Write side: `avatar_id`,
    # the id of an image the caller uploaded into the forum collection (todo
    # 257 slice A). Split fields so the response carries a ready-to-render URL
    # while the request takes a bare id — same author-object avatar contract
    # rendered on every post.
    avatar = serializers.SerializerMethodField()
    avatar_id = serializers.IntegerField(
        write_only=True, required=False, allow_null=True
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
            "fcm_token",
            "avatar",
            "avatar_id",
        ]
        read_only_fields = ["trust_level", "post_count"]

    def update(self, instance, validated_data):
        from django.db import transaction

        token = validated_data.get("fcm_token")
        if not token:
            return super().update(instance, validated_data)
        # An FCM token identifies a DEVICE, so exactly one profile may hold
        # it: registering it here releases it from any other profile.
        # Otherwise a previous account on a shared device keeps receiving
        # this device's pushes after someone else signs in (todo 253 slice 6
        # review) — and a best-effort logout clear that failed offline would
        # leave that stale claim in place forever. Release FIRST, then save:
        # under two concurrent same-token registrations, release-then-save
        # converges on last-writer-holds, whereas save-then-release could
        # blank the token on BOTH profiles (review sweep).
        with transaction.atomic():
            ForumProfile.objects.filter(fcm_token=token).exclude(pk=instance.pk).update(
                fcm_token=""
            )
            return super().update(instance, validated_data)

    @extend_schema_field(CAPABILITIES_SCHEMA)
    def get_capabilities(self, obj):
        # v1: static all-True. Trust/lock-aware gating (e.g. can_react only at
        # trust>=1) is a documented follow-up.
        return {
            "can_react": True,
            "can_reply": True,
            "can_create_topic": True,
        }

    @extend_schema_field({"type": "string", "nullable": True})
    def get_avatar(self, obj):
        if not (obj.avatar_id and obj.avatar):
            return None
        url = obj.avatar.file.url
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request is not None else url

    def validate_avatar_id(self, value):
        # None is an explicit "clear my avatar" — allowed, no ownership check.
        if value is None:
            return value
        request = self.context.get("request")
        user = getattr(request, "user", None)
        # IDOR-safe: an avatar must be an image THIS user uploaded into the
        # forum image collection — the same membership check that gates inline
        # post images (api/sanitize.py). Without it, a caller could point their
        # avatar at any image id (a blog image, another member's upload).
        owns_image = (
            get_image_model()
            .objects.filter(
                id=value,
                uploaded_by_user=user,
                collection=get_forum_image_collection(),
            )
            .exists()
        )
        if not owns_image:
            raise serializers.ValidationError(
                "Avatar must be an image you uploaded to the forum."
            )
        return value
