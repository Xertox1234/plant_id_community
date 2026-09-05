import math

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from wagtail.blocks import RichTextBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images import get_image_model
from wagtail.rich_text import expand_db_html

from ..collections import get_forum_image_collection
from ..conf import get_setting
from ..embeds import embed_envelope
from ..models import (
    ForumBoard,
    ForumProfile,
    Notification,
    PollVote,
    Post,
    Reaction,
    Report,
    Topic,
    TopicBookmark,
    TopicSubscription,
    UserBlock,
    UserMute,
)
from ..models.messages import MESSAGE_BODY_MAX_CHARS, MESSAGE_PREVIEW_CHARS
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


# Hard ceiling on the RAW submitted tag list, independent of the configurable
# TOPIC_MAX_TAGS (which a host may raise). Deliberately a static constant so it
# also bounds the pre-validation payload — see _BoundedTagListField.
MAX_TAG_LIST_ITEMS = 100

# taggit's own Tag.name column width. A host that raises TOPIC_TAG_MAX_LENGTH
# past this would otherwise pass validation and then blow up on INSERT with a
# DataError (NOT an IntegrityError, so the topic-create slug retry does not catch
# it) — a 500 where a 400 belongs. Clamp instead of trusting the setting.
TAGGIT_NAME_MAX_LENGTH = 100

# Hard ceiling on the RAW submitted candidate list, independent of the
# configurable TOPIC_IDENTIFICATION_MAX_CANDIDATES — same split as
# MAX_TAG_LIST_ITEMS vs TOPIC_MAX_TAGS. See _BoundedCandidateListField.
MAX_CANDIDATE_LIST_ITEMS = 100

# Hard ceiling on the RAW submitted poll-option list, independent of the
# configurable POLL_MAX_OPTIONS — same split as the two above. See
# _BoundedOptionListField.
MAX_POLL_OPTION_LIST_ITEMS = 100


def normalize_topic_tags(value):
    """Validate + normalize a topic's tag list (audit M5).

    Read the bounds at CALL time, not import time, so a host's settings override
    (and `@override_settings` in tests) actually applies. Normalizes to trimmed,
    case-folded, de-duplicated names so "Monstera" and "monstera " are one tag
    rather than two rows in the shared Tag table.
    """
    max_tags = get_setting("TOPIC_MAX_TAGS")
    max_length = min(get_setting("TOPIC_TAG_MAX_LENGTH"), TAGGIT_NAME_MAX_LENGTH)
    # dict (not a list) for O(1) membership — a list made this loop O(n^2), which
    # an authenticated caller could drive into seconds of CPU with a large list
    # inside the 10MB body cap. dict preserves insertion order (3.7+).
    seen = {}
    for raw in value:
        name = " ".join(str(raw).split()).lower()  # collapse inner whitespace too
        if not name:
            continue
        if len(name) > max_length:
            raise serializers.ValidationError(
                _("Each tag must be at most %(n)d characters.") % {"n": max_length}
            )
        # Commas are taggit's own list separator — one submitted tag containing
        # one would silently split into several on parse.
        if "," in name:
            raise serializers.ValidationError(_("A tag cannot contain a comma."))
        seen[name] = None
    if len(seen) > max_tags:
        raise serializers.ValidationError(
            _("At most %(n)d tags per topic.") % {"n": max_tags}
        )
    return list(seen)


class _BoundedListField(serializers.ListField):
    """A ListField that rejects an oversized list BEFORE per-item validation.

    ``ListField(max_length=...)`` is enforced by a validator that DRF runs
    *after* ``to_internal_value`` has already run child validation on every
    element, so it cannot bound the work a caller triggers. Check the raw length
    first — the same "bound it before you parse it" shape as the body limits in
    api/sanitize.py (MAX_BODY_BLOCKS). Subclasses set `max_items` and
    `too_many_message`; this used to be three hand-copied classes differing
    only in those two values (todo 320 #6).
    """

    max_items: int
    too_many_message = _("Too many items.")

    def to_internal_value(self, data):
        if isinstance(data, list) and len(data) > self.max_items:
            raise serializers.ValidationError(self.too_many_message)
        return super().to_internal_value(data)


class _BoundedTagListField(_BoundedListField):
    max_items = MAX_TAG_LIST_ITEMS
    too_many_message = _("Too many tags.")


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
        "title": {"type": "string"},
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
        "title": "",
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
        "title": profile.title if profile else "",
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
            # (heading/quote), {language, code} (code block), the
            # {id, url, alt, width, height} rendition dict (image), the embed
            # envelope (todo 344) or the {text, post_id, available, topic_id,
            # author, is_blocked, is_muted} quote envelope (todo 342) — see
            # serialize_forum_body for the authoritative shapes.
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
TAGS_SCHEMA = {"type": "array", "items": {"type": "string"}}
IDENTIFICATION_CANDIDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "scientific_name": {"type": "string"},
        "confidence": {"type": "number", "format": "float"},
    },
}
IDENTIFICATION_SCHEMA = {
    "type": "object",
    "nullable": True,
    "properties": {
        # The {id, url, alt, width, height} rendition dict, or null when the
        # image row was deleted after posting (the card renders text-only).
        "image": {"type": "object", "additionalProperties": True, "nullable": True},
        "provider": {"type": "string"},
        "candidates": {"type": "array", "items": IDENTIFICATION_CANDIDATE_SCHEMA},
        "created_at": {"type": "string", "format": "date-time"},
    },
}
POLL_OPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "text": {"type": "string"},
        "order": {"type": "integer"},
        # Server-aggregated from PollVote rows on every read. There is no
        # stored counter and no writable path to this number.
        "vote_count": {"type": "integer"},
    },
}
POLL_SCHEMA = {
    "type": "object",
    "nullable": True,
    "properties": {
        "id": {"type": "integer"},
        "question": {"type": "string"},
        "closes_at": {"type": "string", "format": "date-time", "nullable": True},
        "is_closed": {"type": "boolean"},
        # 1 = single-choice; N = a voter may pick up to N options in their
        # one submission (todo 349).
        "max_choices": {"type": "integer"},
        "options": {"type": "array", "items": POLL_OPTION_SCHEMA},
        # People who answered (distinct voters), not vote rows — in a
        # multi-choice poll the option counts can sum to more than this.
        "total_votes": {"type": "integer"},
        # The requesting viewer's own choice(s); empty when they have not
        # voted (and always empty for anonymous). Never anyone else's.
        "my_vote_option_ids": {"type": "array", "items": {"type": "integer"}},
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
    # Annotated by BoardListView.get_queryset — the newest live topic's
    # activity timestamp, so the board list can show "last active" without a
    # per-board round-trip (todo 278 L2). Null for a board nobody has posted
    # in yet; the only caller is BoardListView, which always annotates it.
    last_post_at = serializers.DateTimeField(read_only=True, allow_null=True)

    class Meta:
        model = ForumBoard
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "topic_count",
            "post_count",
            "last_post_at",
        ]


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
    tags = serializers.SerializerMethodField()
    # Accepted answer (audit H6). Both are plain column reads — `is_solved` is
    # derived from the FK id, NOT from a liveness join, because signals.py
    # clears the state when the answer stops being visible
    # (_clear_solution_for_post). That keeps the list query pin flat.
    is_solved = serializers.SerializerMethodField()
    solved_post_id = serializers.IntegerField(read_only=True, allow_null=True)

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
            "tags",
            "is_solved",
            "solved_post_id",
        ]

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_solved(self, obj):
        return obj.solved_post_id is not None

    @extend_schema_field(TAGS_SCHEMA)
    def get_tags(self, obj):
        # Relies on the view's prefetch_related("tags") — without it this is a
        # query PER ROW (the list pin is asserted in test_topics_list.py).
        return [tag.name for tag in obj.tags.all()]

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
    # Save-for-later, distinct from is_subscribed's notify-me intent (todo
    # 283 / M2). Detail-only, like is_subscribed — see get_is_bookmarked.
    is_bookmarked = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    # Accepted answer (audit H6) — see TopicListSerializer for why `is_solved`
    # is a column read rather than a liveness join.
    is_solved = serializers.SerializerMethodField()
    solved_post_id = serializers.IntegerField(read_only=True, allow_null=True)
    can_mark_solution = serializers.SerializerMethodField()
    # The plant-ID snapshot the author attached at compose time (audit M6).
    # DETAIL-ONLY, deliberately: the card renders above the opening post and
    # nowhere else, so the topic list and both search hit-builders stay
    # untouched. See get_identification.
    identification = serializers.SerializerMethodField()
    # ANNOTATE, not HIDE (todo 284/M9) — same discipline as is_subscribed/
    # is_bookmarked above. See get_is_blocked/get_can_block.
    is_blocked = serializers.SerializerMethodField()
    is_muted = serializers.SerializerMethodField()
    can_block = serializers.SerializerMethodField()
    can_mute = serializers.SerializerMethodField()
    # The topic's poll with server-computed results (audit M8). DETAIL-ONLY,
    # like `identification` and for the same reason. See get_poll.
    poll = serializers.SerializerMethodField()

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
            "is_bookmarked",
            "tags",
            "is_solved",
            "solved_post_id",
            "solved_at",
            "can_mark_solution",
            "identification",
            "is_blocked",
            "is_muted",
            "can_mute",
            "can_block",
            "poll",
        ]

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_blocked(self, obj):
        # Read the queryset annotation when present (zero extra query,
        # correlated EXISTS via _annotate_author_blocked) — falls back to a
        # direct .exists() only for a single-object response that bypassed
        # get_queryset's annotation (mirrors get_reacted's map-vs-fallback
        # shape, api/views.py PostListView.list comment).
        annotated = getattr(obj, "author_is_blocked", None)
        if annotated is not None:
            return annotated
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated or obj.author_id is None:
            return False
        return UserBlock.objects.filter(blocker=user, blocked_id=obj.author_id).exists()

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_block(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return UserBlock.can_block(user, obj.author)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_muted(self, obj):
        # Mirrors get_is_blocked: the queryset annotation when present
        # (zero extra query), a direct .exists() only for a single-object
        # response that bypassed get_queryset's annotation (todo 347).
        annotated = getattr(obj, "author_is_muted", None)
        if annotated is not None:
            return annotated
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated or obj.author_id is None:
            return False
        return UserMute.objects.filter(muter=user, muted_id=obj.author_id).exists()

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_mute(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return UserMute.can_mute(user, obj.author)

    @extend_schema_field(TAGS_SCHEMA)
    def get_tags(self, obj):
        return [tag.name for tag in obj.tags.all()]

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
    def get_is_solved(self, obj):
        return obj.solved_post_id is not None

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_mark_solution(self, obj):
        # Whether THIS viewer may accept/clear an answer here — single-sourced
        # on the model so the button affordance matches TopicSolutionView's
        # write guard exactly (todo 252). Zero queries for the topic author;
        # anonymous short-circuits inside solution_block.
        request = self.context.get("request")
        return obj.can_mark_solution_by(getattr(request, "user", None))

    @extend_schema_field(IDENTIFICATION_SCHEMA)
    def get_identification(self, obj):
        # `identification` is a REVERSE OneToOne, so a bare attribute read
        # raises RelatedObjectDoesNotExist when absent — which is the common
        # case (most topics carry no snapshot). getattr-with-default is the
        # safe read: Django makes that exception subclass AttributeError
        # precisely so this works. Pinned by
        # test_topic_detail_identification_is_null_when_absent.
        attachment = getattr(obj, "identification", None)
        if attachment is None:
            return None
        return serialize_identification_for_api(attachment, self.context.get("request"))

    @extend_schema_field(POLL_SCHEMA)
    def get_poll(self, obj):
        """The topic's poll, its server-computed results, and the viewer's vote.

        `poll` is a REVERSE OneToOne, so a bare attribute read raises
        RelatedObjectDoesNotExist when absent — the common case. getattr-with-
        default is the safe read (Django makes that exception subclass
        AttributeError precisely so this works), the same shape as
        get_identification above.

        COST: a topic with NO poll costs zero extra queries — the view
        select_relateds `poll`, so the null check is answered by the row
        already fetched, and we return before touching options. That is what
        keeps test_topic_detail.py's 5/8 pins intact for every poll-less
        topic. A topic WITH a poll pays one query for the aggregated options
        (the distinct-voter total rides that same query as a subquery, todo
        349) and, for an authenticated viewer, one for their own vote. Deliberately
        NOT a `prefetch_related("poll__options")` on the view: a to-many
        prefetch runs its query for every request, which would move both pins
        for the overwhelmingly common poll-less case to buy nothing.
        """
        poll = getattr(obj, "poll", None)
        if poll is None:
            return None
        request = self.context.get("request")
        user = getattr(request, "user", None)
        my_votes = []
        if user is not None and user.is_authenticated:
            # Anonymous stays empty — never leak anyone else's choice. The
            # authenticated lookup stays here (not in Poll.serialize) since
            # only THIS caller knows who "the viewer" is. One query for the
            # whole ballot (N rows for a multi-choice vote, todo 349).
            my_votes = list(
                PollVote.objects.filter(poll=poll, user=user)
                .order_by("option_id")
                .values_list("option_id", flat=True)
            )
        return poll.serialize(my_votes)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_subscribed(self, obj):
        # Anonymous short-circuits with zero queries — todo 253 slice 3.
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        return TopicSubscription.objects.filter(user=user, topic=obj).exists()

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_bookmarked(self, obj):
        # Same zero-query-anonymous shape as get_is_subscribed (todo 283 / M2).
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        return TopicBookmark.objects.filter(user=user, topic=obj).exists()


def serialize_image_for_api(image, request=None):
    """An image block's API value: {id, url, alt, width, height}.

    Serves a bounded `max-1200x1200` rendition (not the 5000px-capped original).
    The URL is made absolute against the request so the web client — served from
    a different origin than the media backend — resolves it correctly.

    `alt` is the AUTHOR-SUPPLIED value on `Image.description` (M7), Wagtail's own
    alt-text field. It deliberately does NOT fall back to `image.title`: title is
    the upload filename, and filename-as-alt is an accessibility anti-pattern —
    a screen reader announcing "IMG_2481.jpg" is worse than announcing nothing,
    and `alt=""` is the correct markup for a decorative image. Rows uploaded
    before M7 have `description=""`, so historic posts now serve `alt: ""`
    instead of a filename. That is the intended improvement, not a regression.
    """
    rendition = image.get_rendition("max-1200x1200")
    url = rendition.url
    if request is not None:
        url = request.build_absolute_uri(url)
    return {
        "id": image.id,
        "url": url,
        "alt": image.description or "",
        "width": rendition.width,
        "height": rendition.height,
    }


def serialize_identification_for_api(attachment, request=None):
    """A topic's identification snapshot for the thread card (audit M6).

    `identification_result_id` is deliberately NOT serialized: it is an internal
    correlation handle pointing into private identification history, and the
    card has no use for it. Reading `attachment.image` costs a query unless the
    caller select_related-joined it (TopicDetailView does).
    """
    return {
        "image": (
            serialize_image_for_api(attachment.image, request)
            if attachment.image_id and attachment.image
            else None
        ),
        "provider": attachment.provider,
        "candidates": attachment.candidates or [],
        "created_at": attachment.created_at,
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


def build_forum_embed_map(posts):
    """Map {url: Embed} for every embed block across *posts* — one query, or
    none when there are no embed blocks or the host has embeds off. The
    embed twin of build_forum_image_map, for the same reason: the post-list
    query count must stay flat however many videos a page carries."""
    from ..embeds import cached_embeds_for

    return cached_embeds_for(
        raw.get("value")
        for post in posts
        for raw in post.body.raw_data
        if raw.get("type") == "embed"
    )


def build_forum_quote_map(posts, user=None):
    """Map {post_id: Post} for every `post_quote` block across *posts* — one
    query, or none (todo 342). Same reason as the image/embed maps: the
    post-list query count stays flat however many quotes a page carries.

    Each mapped post also carries `author_is_blocked` / `author_is_muted`
    for the VIEWER (two bounded queries per page, only when the page quotes
    anything and the viewer is a filtered one): a quote is one more surface
    rendering an author, and the block feature's contract is COLLAPSE, not
    HIDE — the client gets the same signal `PostSerializer.is_blocked` /
    `is_muted` give for the post itself. Anonymous viewers and moderators
    get constant `False`, like `_annotate_author_blocked`."""
    from ..quotes import quoted_post_ids, visible_quoted_posts
    from .views import _should_filter_blocks

    ids: list[int] = []
    for post in posts:
        for pid in quoted_post_ids(post.body.raw_data):
            if pid not in ids:
                ids.append(pid)
    quote_map = visible_quoted_posts(ids)
    blocked: set[int] = set()
    muted: set[int] = set()
    author_ids = {p.author_id for p in quote_map.values() if p.author_id}
    if author_ids and _should_filter_blocks(user):
        blocked = set(
            UserBlock.objects.filter(
                blocker_id=user.pk, blocked_id__in=author_ids
            ).values_list("blocked_id", flat=True)
        )
        muted = set(
            UserMute.objects.filter(
                muter_id=user.pk, muted_id__in=author_ids
            ).values_list("muted_id", flat=True)
        )
    for quoted in quote_map.values():
        quoted.author_is_blocked = quoted.author_id in blocked
        quoted.author_is_muted = quoted.author_id in muted
    return quote_map


def serialize_post_quote(raw_value, quote_map, request=None):
    """The API envelope of a `post_quote` block: the stored text plus a safe
    attribution resolved from the page map. A quoted post that is gone
    (unpublished, hidden, deleted) still renders its text with
    `available: false` and no attribution — never a leak of what it was."""
    value = raw_value if isinstance(raw_value, dict) else {}
    pid = value.get("post")
    quoted = quote_map.get(pid) if quote_map else None
    return {
        "text": value.get("text") or "",
        "post_id": pid,
        "available": quoted is not None,
        "topic_id": quoted.topic_id if quoted is not None else None,
        "author": (
            serialize_forum_author(quoted.author, request)
            if quoted is not None
            else None
        ),
        # Collapse signals for the viewer (see build_forum_quote_map).
        "is_blocked": bool(getattr(quoted, "author_is_blocked", False)),
        "is_muted": bool(getattr(quoted, "author_is_muted", False)),
    }


def serialize_forum_body(
    stream_value, image_map=None, request=None, embed_map=None, quote_map=None
):
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
    from ..embeds import _UNSET

    blocks = []
    for raw in stream_value.raw_data:
        block_type = raw.get("type")
        raw_value = raw.get("value")
        child = child_blocks.get(block_type)
        if block_type == "image":
            image = image_map.get(raw_value)
            value = serialize_image_for_api(image, request) if image else None
        elif isinstance(child, EmbedBlock):
            # DB-only envelope (todo 344): never `child.to_python`, whose
            # EmbedValue.html would call the provider on a cache miss —
            # inline, untimed, on a public read. With a page map the row is
            # already in hand (query-free); without one, a single lookup.
            url = raw_value or ""
            value = embed_envelope(
                url, cached=embed_map.get(url) if embed_map is not None else _UNSET
            )
        elif isinstance(child, RichTextBlock):
            value = expand_db_html(raw_value or "")
        elif block_type == "post_quote":
            value = serialize_post_quote(raw_value, quote_map or {}, request)
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
    # COLLAPSE, not HIDE (todo 284/M9) — see get_is_blocked/get_can_block.
    is_blocked = serializers.SerializerMethodField()
    is_muted = serializers.SerializerMethodField()
    can_block = serializers.SerializerMethodField()
    can_mute = serializers.SerializerMethodField()

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
            "is_blocked",
            "is_muted",
            "can_mute",
            "can_block",
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
            embed_map=self.context.get("forum_embed_map"),
            quote_map=self.context.get("forum_quote_map"),
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

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_blocked(self, obj):
        # Read the queryset annotation when present (zero extra query,
        # correlated EXISTS via _annotate_author_blocked) — falls back to a
        # direct .exists() only for a single-object response that bypassed
        # get_queryset's annotation (mirrors get_reacted's map-vs-fallback
        # shape).
        annotated = getattr(obj, "author_is_blocked", None)
        if annotated is not None:
            return annotated
        user = self._request_user()
        if user is None or not user.is_authenticated or obj.author_id is None:
            return False
        return UserBlock.objects.filter(blocker=user, blocked_id=obj.author_id).exists()

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_block(self, obj):
        return UserBlock.can_block(self._request_user(), obj.author)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_muted(self, obj):
        # Mirrors get_is_blocked (todo 347): annotation first, .exists()
        # fallback only for a single-object response.
        annotated = getattr(obj, "author_is_muted", None)
        if annotated is not None:
            return annotated
        user = self._request_user()
        if user is None or not user.is_authenticated or obj.author_id is None:
            return False
        return UserMute.objects.filter(muter=user, muted_id=obj.author_id).exists()

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_mute(self, obj):
        return UserMute.can_mute(self._request_user(), obj.author)


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
    # The post that was quoted, for QUOTE notifications (todo 342).
    quoted_post_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "verb",
            "actor",
            "topic",
            "post_id",
            "quoted_post_id",
            "created_at",
            "read_at",
        ]

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
        request = self.context.get("request")
        return validate_forum_body(
            value,
            self._allowed_uploader_ids(),
            user=request.user if request else None,
            # Edit only: quotes the stored body already carries (set by the
            # edit call site, like `existing_author_id`).
            existing_quote_ids=self.context.get("existing_quote_ids", ()),
        )

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


class _BoundedCandidateListField(_BoundedListField):
    max_items = MAX_CANDIDATE_LIST_ITEMS
    too_many_message = _("Too many identification candidates.")


class IdentificationCandidateSerializer(serializers.Serializer):
    """One suggested species in an attached identification snapshot (audit M6)."""

    name = serializers.CharField(allow_blank=False, trim_whitespace=True)
    scientific_name = serializers.CharField(
        required=False, allow_blank=True, default="", trim_whitespace=True
    )
    confidence = serializers.FloatField(min_value=0.0, max_value=1.0)

    def validate_name(self, value):
        return self._bounded_name(value)

    def validate_scientific_name(self, value):
        return self._bounded_name(value) if value else ""

    @staticmethod
    def _bounded_name(value):
        # Bounds read at CALL time so a host override (and @override_settings in
        # tests) applies — same rule as normalize_topic_tags. Inner whitespace
        # is collapsed too: without it a "name" of 200 newlines passes a length
        # check and renders as a wall in the card.
        max_length = get_setting("TOPIC_IDENTIFICATION_NAME_MAX_LENGTH")
        name = " ".join(str(value).split())
        if len(name) > max_length:
            raise serializers.ValidationError(
                _("Each name must be at most %(n)d characters.") % {"n": max_length}
            )
        return name

    def validate_confidence(self, value):
        # FloatField's min/max are `>`/`<` comparisons and EVERY comparison with
        # NaN is False, so NaN passes both bounds; stored in a JSONField it then
        # re-serializes as the literal `NaN`, which is not valid JSON and which
        # a strict client cannot parse.
        #
        # DEFENCE IN DEPTH, not the only line: DRF's JSONParser already rejects
        # the `NaN`/`Infinity` literals when STRICT_JSON is on (the default, and
        # on in this project's host). This package is reusable, so it does not
        # assume the host left that default alone — and a non-HTTP caller
        # (management command, test, another service) never passes the parser.
        if not math.isfinite(value):
            raise serializers.ValidationError(_("Confidence must be a real number."))
        return value


class TopicIdentificationSerializer(serializers.Serializer):
    """Compose-time write shape for a topic's identification snapshot (M6).

    Caller-supplied throughout — there is no server-side identification record
    to resolve (see models/identifications.py). These bounds are the whole
    defence: they cap how much unverified text one create can park on a topic.
    """

    # Optional: an identification the user ran without keeping the photo, or a
    # failed upload, still yields a useful candidate list.
    image_id = serializers.IntegerField(required=False, allow_null=True)
    provider = serializers.CharField(required=False, allow_blank=True, default="")
    candidates = _BoundedCandidateListField(
        child=IdentificationCandidateSerializer(), allow_empty=False
    )
    # No producer exists yet (the identify endpoint is stateless) — accepted so
    # a client that gains one later needs no API change. See the model field.
    identification_result_id = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=64
    )

    def validate_candidates(self, value):
        max_candidates = get_setting("TOPIC_IDENTIFICATION_MAX_CANDIDATES")
        if len(value) > max_candidates:
            raise serializers.ValidationError(
                _("At most %(n)d identification candidates.") % {"n": max_candidates}
            )
        return value

    def validate_provider(self, value):
        max_length = get_setting("TOPIC_IDENTIFICATION_PROVIDER_MAX_LENGTH")
        provider = " ".join(str(value).split())
        if len(provider) > max_length:
            raise serializers.ValidationError(
                _("Provider must be at most %(n)d characters.") % {"n": max_length}
            )
        return provider

    def validate_image_id(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        user = getattr(request, "user", None)
        # IDOR-safe, mirroring MeProfileSerializer.validate_avatar_id and the
        # inline-image membership check in api/sanitize.py: the photo must be an
        # image THIS user uploaded into the forum collection. Without it a
        # caller could point the card at any image id in the site.
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
                _(
                    "The identification photo must be an image you uploaded to the forum."
                )
            )
        return value


class _BoundedOptionListField(_BoundedListField):
    max_items = MAX_POLL_OPTION_LIST_ITEMS
    too_many_message = _("Too many poll options.")


class TopicPollSerializer(serializers.Serializer):
    """Compose-time write shape for a topic's poll (audit M8).

    Creation only — a poll is attached when the thread is composed and is not
    editable afterwards. That is deliberate for the first cut: editing a
    question or an option after votes exist silently changes what those votes
    meant.

    Note there is no `vote_count` (or any count) field here, and adding one
    would be a bug: results are aggregated from PollVote rows server-side, so
    a caller has no way to seed or influence them. Pinned by
    test_poll_vote_count_in_create_payload_is_ignored.
    """

    question = serializers.CharField()
    options = _BoundedOptionListField(child=serializers.CharField(allow_blank=True))
    # Null / omitted means the poll never closes.
    closes_at = serializers.DateTimeField(required=False, allow_null=True)
    # How many options one voter may pick (todo 349). Omitted = 1, the
    # single-choice poll; bounded to the option count in validate() below
    # (after blanks are dropped), so "pick up to 5 of 3" cannot be stored.
    max_choices = serializers.IntegerField(required=False, default=1, min_value=1)

    def validate_question(self, value):
        question = " ".join(str(value).split())
        if not question:
            raise serializers.ValidationError(_("Poll question cannot be empty."))
        max_length = get_setting("POLL_QUESTION_MAX_LENGTH")
        if len(question) > max_length:
            raise serializers.ValidationError(
                _("Poll question must be at most %(n)d characters.") % {"n": max_length}
            )
        return question

    def validate_options(self, value):
        max_length = get_setting("POLL_OPTION_MAX_LENGTH")
        options = []
        for raw in value:
            text = " ".join(str(raw).split())
            # Drop blanks rather than 400ing: a composer with a fixed number of
            # option inputs sends empties for the ones left untouched, and that
            # is a normal submission, not a malformed one. The min-count check
            # below still catches "nothing was actually filled in".
            if not text:
                continue
            if len(text) > max_length:
                raise serializers.ValidationError(
                    _("Each poll option must be at most %(n)d characters.")
                    % {"n": max_length}
                )
            options.append(text)

        min_options = get_setting("POLL_MIN_OPTIONS")
        if len(options) < min_options:
            raise serializers.ValidationError(
                _("A poll needs at least %(n)d options.") % {"n": min_options}
            )
        max_options = get_setting("POLL_MAX_OPTIONS")
        if len(options) > max_options:
            raise serializers.ValidationError(
                _("A poll may have at most %(n)d options.") % {"n": max_options}
            )
        # Case-insensitive duplicate check: two identically-labelled options
        # split the vote between choices a member cannot tell apart.
        if len({text.casefold() for text in options}) != len(options):
            raise serializers.ValidationError(_("Poll options must be unique."))
        return options

    def validate_closes_at(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError(
                _("Poll close time must be in the future.")
            )
        return value

    def validate(self, attrs):
        # Object-level: needs the normalized option list, which only exists
        # after validate_options has dropped blanks.
        if attrs["max_choices"] > len(attrs["options"]):
            raise serializers.ValidationError(
                {
                    "max_choices": [
                        _("max_choices cannot exceed the number of options (%(n)d).")
                        % {"n": len(attrs["options"])}
                    ]
                }
            )
        return attrs


class TopicCreateSerializer(_ForumBodyContract):
    title = serializers.CharField(max_length=255)
    slug = serializers.SlugField(max_length=255)
    # Optional secondary taxonomy (audit M5). Bounds live in normalize_topic_tags
    # so a host settings override applies at request time, not import time.
    tags = _BoundedTagListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )
    # Optional plant-ID snapshot (audit M6). Nested rather than flattened so the
    # whole attachment is present-or-absent — a create can't half-specify one.
    identification = TopicIdentificationSerializer(required=False, allow_null=True)
    # Optional poll (audit M8). Nested for the same reason as identification:
    # present-or-absent as a whole, so a create cannot half-specify one.
    # Composer-only — there is no reply-side or edit-side poll write.
    poll = TopicPollSerializer(required=False, allow_null=True)

    def validate_tags(self, value):
        return normalize_topic_tags(value)


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


class ConversationSerializer(serializers.Serializer):
    """A 1:1 DM conversation from the requesting user's point of view — the
    OTHER participant, not both (todo 319/M10) — plus the inbox fields (todo
    339): `unread_count`, `last_message_at`, and a `last_message` preview.
    Expects a row from `direct_messages._inbox_queryset` (annotations)."""

    id = serializers.IntegerField()
    other_participant = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    last_message_at = serializers.DateTimeField()
    # Messages from the other side newer than my read marker (own messages
    # never count).
    unread_count = serializers.IntegerField(read_only=True)
    last_message = serializers.SerializerMethodField()

    @extend_schema_field(
        {
            "type": "object",
            "nullable": True,
            "properties": {
                "body": {"type": "string", "description": "Preview, truncated"},
                "is_mine": {"type": "boolean"},
                "created_at": {"type": "string", "format": "date-time"},
            },
        }
    )
    def get_last_message(self, conversation):
        body = getattr(conversation, "last_message_body", None)
        if body is None:
            return None
        request = self.context.get("request")
        return {
            "body": body[:MESSAGE_PREVIEW_CHARS],
            "is_mine": conversation.last_message_sender_id == request.user.pk,
            # Same ISO rendering as the sibling DateTimeField, not a raw datetime.
            "created_at": self.fields["last_message_at"].to_representation(
                conversation.last_message_at
            ),
        }

    @extend_schema_field(AUTHOR_SCHEMA)
    def get_other_participant(self, conversation):
        request = self.context.get("request")
        other_id = conversation.other_participant_id(request.user)
        other_user = (
            conversation.participant_a
            if other_id == conversation.participant_a_id
            else conversation.participant_b
        )
        return serialize_forum_author(other_user, request)


class MessageSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    conversation_id = serializers.IntegerField()
    sender = serializers.SerializerMethodField()
    body = serializers.CharField()
    created_at = serializers.DateTimeField()

    @extend_schema_field(AUTHOR_SCHEMA)
    def get_sender(self, message):
        return serialize_forum_author(message.sender, self.context.get("request"))


class MessageSendSerializer(serializers.Serializer):
    body = serializers.CharField(
        max_length=MESSAGE_BODY_MAX_CHARS, trim_whitespace=True
    )

    def validate_body(self, value):
        stripped = value.strip()
        if not stripped:
            raise serializers.ValidationError(_("Message cannot be empty."))
        return stripped


NOTIFICATION_PREFERENCES_SCHEMA = {
    "type": "object",
    "description": (
        "Per-event push/email preferences (todo 343). Read: the fully resolved "
        "matrix. Write: a PARTIAL matrix merged into the stored overrides."
    ),
    "additionalProperties": {
        "type": "object",
        "properties": {"push": {"type": "boolean"}, "email": {"type": "boolean"}},
    },
}


@extend_schema_field(NOTIFICATION_PREFERENCES_SCHEMA)
class NotificationPreferencesField(serializers.Field):
    """Reads the RESOLVED matrix (defaults + overrides, every cell present)
    and accepts a PARTIAL one; the merge with the stored overrides happens in
    `MeProfileSerializer.update`, which sees the instance."""

    def to_representation(self, value):
        from ..preferences import resolve_preferences

        return resolve_preferences(value)

    def to_internal_value(self, data):
        from ..preferences import InvalidPreferences, validate_preferences

        try:
            return validate_preferences(data)
        except InvalidPreferences as exc:
            raise serializers.ValidationError(str(exc)) from exc


class MeProfileSerializer(serializers.ModelSerializer):
    capabilities = serializers.SerializerMethodField()
    notification_preferences = NotificationPreferencesField(required=False)
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
            "title",
            "trust_level",
            "post_count",
            "capabilities",
            "fcm_token",
            "avatar",
            "avatar_id",
            # Digest email preference (todo 340): "off" | "weekly".
            "digest_frequency",
            # Per-event push/email matrix (todo 343): resolved on read,
            # partial on write.
            "notification_preferences",
        ]
        read_only_fields = ["title", "trust_level", "post_count"]

    def update(self, instance, validated_data):
        from django.db import transaction

        from ..preferences import merge_preferences

        if "notification_preferences" in validated_data:
            # PATCH carries a PARTIAL matrix: merge into the stored overrides
            # so every cell the caller did not mention keeps its value.
            validated_data["notification_preferences"] = merge_preferences(
                instance.notification_preferences,
                validated_data["notification_preferences"],
            )
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
                _("Avatar must be an image you uploaded to the forum.")
            )
        return value
