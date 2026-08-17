import hashlib
import logging

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.db.models import (
    BooleanField,
    DateTimeField,
    F,
    OuterRef,
    Q,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _
from rest_framework import generics
from rest_framework import status as http_status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from rest_framework.views import APIView
from wagtail.actions.unpublish import UnpublishAction
from wagtail.images import get_image_model
from wagtail.search.backends import get_search_backend

try:  # Schema annotations are optional — hosts without drf-spectacular still work.
    from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
except ImportError:  # pragma: no cover

    def extend_schema(**kwargs):
        def decorator(fn):
            return fn

        return decorator

    def extend_schema_view(**kwargs):
        def decorator(cls):
            return cls

        return decorator

    def OpenApiExample(*args, **kwargs):  # noqa: N802 - mirrors drf-spectacular API
        return None


from ..blocks import ForumBodyBlock
from ..collections import get_forum_image_collection
from ..conf import get_setting
from ..models import (
    ForumBoard,
    ForumIdentificationAttachment,
    ForumIndex,
    ForumProfile,
    Post,
    Reaction,
    Report,
    Topic,
    TopicRead,
)
from ..models.posts import BLOCK_FORBIDDEN
from ..workflow import submit_edit_for_moderation, submit_for_moderation
from .exceptions import Conflict, UnprocessableEntity
from .idempotency import fingerprint, idempotency_cache_key, remember, replay, reserve
from .pagination import PostCursorPagination, TopicCursorPagination
from .sanitize import serialize_forum_intro
from .serializers import (
    AUTHOR_SCHEMA,
    FORUM_BODY_SCHEMA,
    BoardSerializer,
    MeProfileSerializer,
    PostEditSerializer,
    PostSerializer,
    ReactionSerializer,
    ReplyCreateSerializer,
    ReportSerializer,
    TopicCreateSerializer,
    TopicDetailSerializer,
    TopicListSerializer,
    build_forum_image_map,
    serialize_forum_author,
    serialize_forum_body,
    serialize_image_for_api,
)
from .upload_validation import validate_image_upload
from .versioning import UnversionedForumAPIMixin

logger = logging.getLogger("wagtail_forum")

# Retries for the slug auto-dedup loop on topic create (see _create_topic).
MAX_SLUG_ATTEMPTS = 5


def _visible_boards():
    """Boards the API may expose: live AND without a Wagtail view restriction.

    `PageViewRestriction` (login/password/group privacy) is not enforced
    automatically by custom views — `.public()` is the opt-in (audit M7).
    Restricted boards are conservatively invisible to the whole API.
    """
    return ForumBoard.objects.live().public()


def _get_visible_post(post_id):
    """Fetch a live, visible post or 404 in a SINGLE query.

    Folds the no-existence-leak visibility guard (audit M6/M7) into the lookup:
    a hidden post, a post on a non-live topic, or a post on a hidden/restricted
    board is 404, never 403. Shared by PostWriteView (edit/delete) and
    ReactionToggleView so the predicate has one shape, not three.
    """
    return get_object_or_404(
        Post.objects.filter(
            live=True, topic__live=True, topic__board__in=_visible_boards()
        ).select_related("topic", "author__wagtail_forum_profile__avatar"),
        id=post_id,
    )


def _get_visible_topic(topic_id):
    """Fetch a live, visible topic or 404 in a SINGLE query.

    Same no-existence-leak visibility guard as _get_visible_post, scoped to
    Topic. Shared by PostListView.post, TopicDetailView.get_queryset-style
    lookups, and TopicSubscriptionView.post (audit M6/M7, todo 253 slice 3) —
    so the predicate has one shape, not four.
    """
    return get_object_or_404(
        Topic.objects.filter(live=True, board__in=_visible_boards()), id=topic_id
    )


def _get_board(slug):
    """Resolve a board by slug, 404ing hidden boards and 409ing ambiguity.

    Wagtail slugs are unique only among siblings, so two boards under
    different ForumIndex pages can share a slug — `.get()` would raise
    `MultipleObjectsReturned` → 500 (audit M8).
    """
    boards = list(_visible_boards().filter(slug=slug)[:2])
    if not boards:
        raise NotFound()
    if len(boards) > 1:
        raise Conflict(
            _("Board slug is ambiguous across forum trees; contact the site admin.")
        )
    return boards[0]


def _annotate_topic_unread(qs, user):
    """Annotate `is_unread` on a Topic queryset (todo 253 slice 5, H10).

    Always present — a constant for anonymous requests, the real chain for
    authenticated ones — so the serializer field needs no special-casing.

    A topic is unread when its `last_post_at` is newer than the most
    specific baseline available: this user's explicit `TopicRead` for this
    exact topic, else their `ForumProfile.read_watermark_at` (backfilled to
    launch time for existing profiles; stamped at profile-creation time for
    new ones), else the fixed `UNREAD_LAUNCH_AT` launch constant (only
    reached for a user with no profile row at all).

    Both `Subquery` lookups below fold into the single SELECT as correlated
    scalar-subquery expressions — zero added Python-level queries, so this
    does not change the endpoint's pinned query count (see
    test_topics_list.py).

    `UNREAD_LAUNCH_AT` must parse to a real datetime — a misconfigured value
    would otherwise silently degrade `is_unread` to `False` for every
    profile-less user, so this fails loud instead.
    """
    if not user.is_authenticated:
        return qs.annotate(is_unread=Value(False, output_field=BooleanField()))
    read_at = TopicRead.objects.filter(user=user, topic=OuterRef("pk")).values(
        "last_read_at"
    )[:1]
    watermark = ForumProfile.objects.filter(user=user).values("read_watermark_at")[:1]
    launch_setting = get_setting("UNREAD_LAUNCH_AT")
    launch_at = parse_datetime(launch_setting)
    if launch_at is None:
        raise ImproperlyConfigured(
            f"WAGTAILFORUM_UNREAD_LAUNCH_AT={launch_setting!r} is not a valid "
            "ISO 8601 datetime (e.g. '2026-07-16T00:00:00Z')."
        )
    if timezone.is_naive(launch_at):
        launch_at = timezone.make_aware(launch_at)
    return qs.alias(
        _read_baseline=Coalesce(
            Subquery(read_at),
            Subquery(watermark),
            Value(launch_at, output_field=DateTimeField()),
        ),
    ).annotate(is_unread=Q(last_post_at__gt=F("_read_baseline")))


def _replay_or_none(cache_key, payload_fingerprint):
    """Return a replayed Response for a remembered idempotent request.

    Reusing a key with a different payload is a client bug — reject it (422)
    instead of silently returning the previous response (audit M4). A request
    whose twin is still in flight gets 409 (IETF idempotency-key draft) —
    views call reserve() just before their mutating operation, so a request
    failing validation never wedges the key.
    """
    cached = replay(cache_key)
    if cached is None:
        return None
    if cached.get("processing"):
        raise Conflict(_("A request with this Idempotency-Key is being processed."))
    if cached["fingerprint"] != payload_fingerprint:
        raise UnprocessableEntity(
            _("Idempotency-Key was already used with a different payload.")
        )
    # Replay the ORIGINAL status (e.g. 201), not a fresh 200 — clients key on
    # 201 to detect creation (IETF idempotency-key draft).
    response = Response(cached["data"], status=cached["status"])
    # Re-attach any remembered headers (e.g. a 201's Location) so the replay is
    # response-faithful, not just body-faithful (L19).
    for header, value in cached.get("headers", {}).items():
        response[header] = value
    return response


def _created_location(request, name, **kwargs):
    """Absolute URL for a just-created resource's route, namespace-agnostic (L19).

    The forum mounts under different namespaces per host (the package sets
    app_name 'wagtail_forum_api'; a host may include it namespaced, mount its own
    throttled wrappers, or use the urlconf as a bare root with NO namespace).
    Reverse the route within the CURRENT request's namespace so a Location header
    never 500s on a NoReverseMatch.
    """
    namespace = request.resolver_match.namespace
    route = f"{namespace}:{name}" if namespace else name
    return request.build_absolute_uri(reverse(route, kwargs=kwargs))


def _apply_forum_read_cache_headers(response, request, *, public):
    """Cache-Control + Vary for a forum read endpoint (audit M42).

    When ``public`` and the request is anonymous and the response is a success:
    the payload is identical across all anonymous users — every per-user field
    (`is_unread`, `is_subscribed`, `can_edit`/`can_delete`/`can_report`,
    `reacted`) sits at its constant anonymous baseline — so a shared cache
    (Cloudflare) may store it: `public, s-maxage`. `max-age=0` keeps a
    private/browser cache revalidating, so only the CDN holds the anon copy.
    Everything else — any authenticated request, any error (>=400), and every
    request to a ``public=False`` view — gets `private, no-store`: never stored
    by a shared cache, so per-user capabilities can never leak and there is no
    edge-cached copy to serve.

    `Vary` includes both `Cookie` AND `Authorization`: `CookieJWTAuthentication`
    falls back to the Authorization header (the mobile client authenticates that
    way, cookie-less), so a shared cache keyed only on Cookie could hand the
    anonymous entry to a header-authenticated request. Both dimensions keep an
    authenticated request from ever matching the anonymous cache key.
    """
    from django.utils.cache import patch_vary_headers

    user = getattr(request, "user", None)
    is_anonymous = user is None or not user.is_authenticated
    if public and is_anonymous and response.status_code < 400:
        seconds = get_setting("PUBLIC_READ_CACHE_SECONDS")
        response["Cache-Control"] = f"public, s-maxage={seconds}, max-age=0"
    else:
        response["Cache-Control"] = "private, no-store"
    patch_vary_headers(response, ("Cookie", "Authorization"))
    return response


class PublicForumReadCacheMixin:
    """Anonymous GET/HEAD reads are shared-cacheable; authed reads are private.

    Only for reads whose sole staleness is list-level and which have NO
    per-request side effect: board list, topic list, search. Applies to GET/HEAD
    only, so a view that also serves a mutating POST (topic/post create) leaves
    its write responses untouched (no cache header at all). Topic detail and post
    list deliberately use ``PrivateForumReadCacheMixin`` instead — see there.
    """

    _forum_read_public = True

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if request.method in ("GET", "HEAD"):
            _apply_forum_read_cache_headers(
                response, request, public=self._forum_read_public
            )
        return response


class PrivateForumReadCacheMixin(PublicForumReadCacheMixin):
    """GET/HEAD reads are always `private, no-store` — never edge-cached.

    For public reads that must reach the origin every time: TopicDetailView
    (its `retrieve` increments `view_count`, a user-visible sortable metric that
    a CDN cache would undercount) and PostListView (a report-auto-hidden or
    unpublished post must stop being served immediately — there is no CDN purge
    wired, so a shared-cache TTL would keep moderated content live). Still
    explicit `no-store` rather than header-less, so a "cache everything" CDN
    rule can never heuristically store their per-user payloads.
    """

    _forum_read_public = False


def _visible_forum_index():
    """The ForumIndex whose welcome copy the board list carries (todo 278 L2).

    Wagtail lets a host mount more than one forum tree, so like `_get_board`'s
    slug-ambiguity guard this resolves deterministically instead of assuming
    uniqueness: the first live, non-restricted index in tree order. Returns
    None when the host has no forum index at all (the API is still usable —
    `intro` is simply empty).

    Note the asymmetry in the multi-tree case: `results` spans every visible
    tree (`_visible_boards()` is deliberately not scoped to one index), while
    `intro` comes from one. That is the honest shape for a single-forum host,
    which is every host today; a host that really runs two forums side by side
    wants two mount points, not one endpoint arbitrating between them.
    """
    return ForumIndex.objects.live().public().order_by("path").first()


@extend_schema(
    responses={
        200: {
            "type": "object",
            "properties": {
                "results": {"type": "array", "items": {"type": "object"}},
                "intro": {
                    "type": "string",
                    "description": (
                        "Sanitized HTML welcome copy from the ForumIndex page; "
                        "empty string when unset."
                    ),
                },
            },
        }
    },
    description=(
        "List every visible board, flat and unpaginated, plus the forum "
        "index's welcome copy. See the package README's `## List envelopes` "
        "section for why this shape is not the cursor envelope."
    ),
)
class BoardListView(
    UnversionedForumAPIMixin, PublicForumReadCacheMixin, generics.ListAPIView
):
    serializer_class = BoardSerializer
    pagination_class = None  # boards are few; return a flat results list
    # Opt out of host-configured filter backends (DEFAULT_FILTER_BACKENDS): a
    # global OrderingFilter lets any client ?ordering= replace the cursor
    # pagination's pinned-first ordering, and 500s on dotted serializer sources
    # like author__get_username (both verified) — list order is a package
    # contract, not client-selectable.
    filter_backends = []

    def get_queryset(self):
        # `last_post_at` per board (todo 278 L2) as a correlated scalar
        # subquery — same idiom as _annotate_topic_unread, so it folds into the
        # single SELECT rather than adding a GROUP BY over the Page join.
        # `last_post_at__isnull=False` is load-bearing, not defensive: Postgres
        # orders DESC as NULLS FIRST, so a live topic that never got a
        # published post would otherwise win the sort and blank the column.
        latest_activity = (
            Topic.objects.filter(
                board=OuterRef("pk"), live=True, last_post_at__isnull=False
            )
            .order_by("-last_post_at")
            .values("last_post_at")[:1]
        )
        return (
            _visible_boards()
            .annotate(last_post_at=Subquery(latest_activity))
            .order_by("path")
        )

    def list(self, request, *args, **kwargs):
        data = self.get_serializer(self.get_queryset(), many=True).data
        index = _visible_forum_index()
        # `intro` rides along with the board list rather than getting its own
        # endpoint: it is the same page's payload, always fetched together, and
        # a second round-trip would double the forum home page's cold start.
        # Documented as part of the flat envelope in the package README.
        return Response(
            {
                "results": data,
                "intro": serialize_forum_intro(index.intro) if index else "",
            }
        )


@extend_schema(
    responses={200: TopicListSerializer(many=True), 404: dict},
    description=(
        "List a board's live topics, most-recent activity first "
        "(cursor-paginated). Optional ?sort= reorders within the pinned-first "
        "contract — one of: -last_activity_at (default), -created_at, "
        "created_at, -view_count, -post_count; an unknown value is ignored. "
        "Optional ?tag= filters to topics carrying that tag — an exact, "
        "case-insensitive match on a whole tag name (not a substring search); "
        "an unknown tag returns an empty page. "
        "Returns 404 for a hidden/non-live board."
    ),
)
class TopicListView(
    UnversionedForumAPIMixin, PublicForumReadCacheMixin, generics.ListAPIView
):
    serializer_class = TopicListSerializer
    pagination_class = TopicCursorPagination
    filter_backends = []  # host filter-backend opt-out — see BoardListView
    # GET (list) is public; only the merged POST (create) needs auth — exactly
    # IsAuthenticatedOrReadOnly (also the project default), declared explicitly.
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        # Suppress drf-spectacular's "Failed to obtain model" warning: during
        # schema generation there is no `slug` kwarg to look the board up by.
        if getattr(self, "swagger_fake_view", False):
            return Topic.objects.none()
        board = _get_board(self.kwargs["slug"])
        # Join author + last_post_author down to their ForumProfile.avatar so the
        # unified author object (todo 257 H26) serializes with zero per-row
        # queries — select_related adds JOINs, not queries, so the list pin stays
        # flat (test_topics_list.py).
        qs = (
            Topic.objects.filter(board=board, live=True).select_related(
                "author__wagtail_forum_profile__avatar",
                "last_post_author__wagtail_forum_profile__avatar",
            )
            # ONE extra query for the whole page, not one per row — TopicListSerializer
            # .get_tags reads obj.tags.all() (audit M5).
            .prefetch_related("tags")
        )
        # Optional secondary-taxonomy filter (audit M5): ?tag=monstera.
        #
        # EXACT (iexact), never icontains — a substring match would make
        # `?tag=rot` also return "root rot", and these are labels, not search.
        #
        # Case-INsensitive because the API is not the only writer: the Wagtail
        # admin panel writes tags through taggit's own widget, which bypasses
        # normalize_topic_tags, and taggit's Tag.name is case-sensitive. A
        # moderator-added "Monstera" would otherwise be permanently unreachable
        # from the "#Monstera" chip the UI renders from that very name.
        # `.distinct()` goes with it: a topic carrying BOTH "Monstera" and
        # "monstera" (two distinct Tag rows) would otherwise join twice and
        # appear duplicated in the page.
        tag = self.request.query_params.get("tag")
        if tag:
            qs = qs.filter(tags__name__iexact=" ".join(tag.split())).distinct()
        qs = _annotate_topic_unread(qs, self.request.user)
        # Kept in sync with TopicCursorPagination.ordering — the paginator
        # re-applies its own ordering, so this is what unpaginated callers see.
        return qs.order_by("-is_pinned", "-last_post_at", "-id")

    @extend_schema(
        request=TopicCreateSerializer,
        responses={201: dict, 400: dict, 401: dict, 404: dict, 409: dict, 422: dict},
        examples=[
            OpenApiExample(
                "Create a topic",
                request_only=True,
                value={
                    "title": "How do I repot a monstera?",
                    "slug": "how-do-i-repot-a-monstera",
                    "body": [
                        {"type": "paragraph", "value": "<p>Roots are crowded.</p>"}
                    ],
                    "tags": ["monstera", "repotting"],
                },
            ),
            OpenApiExample(
                "Create a topic with an identification attached",
                request_only=True,
                value={
                    "title": "Is this a monstera or a philodendron?",
                    "slug": "is-this-a-monstera-or-a-philodendron",
                    "body": [{"type": "paragraph", "value": "<p>App wasn't sure.</p>"}],
                    "identification": {
                        "image_id": 42,
                        "provider": "plant_id",
                        "candidates": [
                            {
                                "name": "Swiss cheese plant",
                                "scientific_name": "Monstera deliciosa",
                                "confidence": 0.82,
                            },
                            {
                                "name": "Heartleaf philodendron",
                                "scientific_name": "Philodendron hederaceum",
                                "confidence": 0.11,
                            },
                        ],
                    },
                },
            ),
            OpenApiExample(
                "Idempotency-Key reused with a different body",
                response_only=True,
                status_codes=["422"],
                value={
                    "error": True,
                    "message": (
                        "Idempotency-Key was already used with a different payload."
                    ),
                    "code": "unprocessable",
                    "status_code": 422,
                },
            ),
        ],
        description=(
            "Create a topic (with its opening post) and route it through "
            "moderation. On success returns 201 with a Location header for the "
            "new topic. Supports an Idempotency-Key header: a retry with the "
            "same key replays the original response (original status code); "
            "reuse with a different payload returns 422. A taken slug is "
            "auto-suffixed (-2, -3, …) — read the final slug from the response. "
            "An optional `identification` object attaches a plant-ID snapshot to "
            "the topic; `image_id` must be an image the caller uploaded to the "
            "forum image collection. The snapshot is caller-supplied — it "
            "records what the app suggested to the author, not a verified "
            "determination — and is returned by the topic-detail endpoint only."
        ),
    )
    def post(self, request, slug):
        cache_key = idempotency_cache_key(request, "topic-create")
        payload_fp = (
            fingerprint({"slug": slug, "body": request.data}) if cache_key else None
        )
        replayed = _replay_or_none(cache_key, payload_fp)
        if replayed is not None:
            return replayed

        serializer = TopicCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        board = _get_board(slug)

        reserve(cache_key)  # 409 if a same-key twin is mid-flight (atomic add)
        topic, opening = self._create_topic(request, board, serializer.validated_data)

        # Route through moderation OUTSIDE the creation transaction. A pluggable
        # spam backend can raise; the draft is already live=False, so never 500 —
        # leave it as a pending draft for a moderator.
        try:
            status = submit_for_moderation(opening, request.user)
        except Exception:
            logger.exception(
                "[ERROR] submit_for_moderation failed for post %s; left as draft",
                opening.pk,
            )
            status = "pending"

        result = {"id": topic.id, "slug": topic.slug, "status": status}
        # Cache the outcome — including a backend-crash "pending" — so a client
        # retry with the same key cleanly replays instead of re-creating.
        location = _created_location(request, "topic-detail", topic_id=topic.id)
        remember(
            cache_key,
            result,
            http_status.HTTP_201_CREATED,
            payload_fp,
            headers={"Location": location},
        )
        response = Response(result, status=http_status.HTTP_201_CREATED)
        response["Location"] = location
        return response

    @staticmethod
    def _create_topic(request, board, validated):
        """Create the draft topic + opening post atomically (born live=False).

        A taken slug is auto-suffixed instead of 409ing: the unique constraint
        also covers DRAFT topics, so a conflict response would leak a hidden
        draft's existence (audit L4). Each attempt runs in its own transaction
        so an IntegrityError can't poison an outer atomic block.

        CAVEAT (audit M6): the ``except IntegrityError`` now also covers the
        identification insert. If the referenced image row is deleted between
        ``validate_image_id``'s existence check and this insert, the FK
        violation is retried as if it were a slug clash and the caller
        eventually gets "could not allocate a unique slug" rather than a bad
        image reference. Accepted: the race window is tiny, each attempt rolls
        back cleanly so no orphan rows survive, and narrowing the catch costs
        more churn than the confusing-but-rare message is worth.
        """
        base_slug = validated["slug"]
        for attempt in range(MAX_SLUG_ATTEMPTS):
            if attempt == 0:
                slug_try = base_slug
            else:
                # Truncate so base+suffix fits SlugField(max_length=255) —
                # Postgres raises DataError (500) past it; SQLite won't.
                suffix = f"-{attempt + 1}"
                slug_try = f"{base_slug[: 255 - len(suffix)]}{suffix}"
            try:
                with transaction.atomic():
                    topic = Topic(
                        board=board,
                        title=validated["title"],
                        slug=slug_try,
                        author=request.user,
                        live=False,
                    )
                    topic.save()
                    # Tags are an M2M — they need the topic's PK, so they are set
                    # after save() but inside the same transaction as the topic +
                    # opening post (audit M5). Absent key = no tags.
                    if validated.get("tags"):
                        topic.tags.set(validated["tags"])
                    opening = Post(
                        topic=topic,
                        author=request.user,
                        is_opening_post=True,
                        body=ForumBodyBlock().to_python(validated["body"]),
                        live=False,
                    )
                    opening.save()
                    # The plant-ID snapshot (audit M6), inside the same
                    # transaction as the topic + opening post: a topic whose
                    # attachment failed to write would render as an ordinary
                    # question, silently losing the thing it was asked about.
                    identification = validated.get("identification")
                    if identification:
                        ForumIdentificationAttachment.objects.create(
                            topic=topic,
                            image_id=identification.get("image_id"),
                            provider=identification.get("provider", ""),
                            candidates=identification["candidates"],
                            identification_result_id=identification.get(
                                "identification_result_id", ""
                            ),
                        )
                return topic, opening
            except IntegrityError:
                continue
        raise Conflict(_("Could not allocate a unique slug for this topic."))


@extend_schema(
    responses={200: TopicDetailSerializer, 404: dict},
    description=(
        "Retrieve a topic's detail. Returns 404 for a non-live topic or a "
        "topic on a hidden/non-live board (no existence leak)."
    ),
)
class TopicDetailView(
    UnversionedForumAPIMixin, PrivateForumReadCacheMixin, generics.RetrieveAPIView
):
    serializer_class = TopicDetailSerializer
    filter_backends = []  # host filter-backend opt-out — see BoardListView
    lookup_url_kwarg = "topic_id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Topic.objects.none()
        return (
            Topic.objects.filter(live=True, board__in=_visible_boards())
            .select_related(
                "board",
                "author__wagtail_forum_profile__avatar",
                "last_post_author__wagtail_forum_profile__avatar",
                # Reverse OneToOne + its photo, so a topic WITH an identification
                # card costs no extra query for the row itself (audit M6). The
                # rendition lookup behind serialize_image_for_api is separate and
                # only happens when a photo is actually attached.
                "identification__image",
            )
            .prefetch_related("tags")  # TopicDetailSerializer.get_tags (audit M5)
        )

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        # Increment view_count after a successful 200, deduplicated per viewer.
        #
        # on_commit timing — accepted as-is, decided 2026-07-29 (todo 271 #2).
        # Read the `on_commit` calls in this method as ordering/fail-safe
        # constructs, NOT as "this write is deferred past the request." This
        # project runs ATOMIC_REQUESTS=False and nothing wraps retrieve() in an
        # explicit atomic(), so `connection.in_atomic_block` is False here and
        # Django's autocommit branch (db/backends/base/base.py::on_commit,
        # verified against Django 6.0.7) executes the callback IMMEDIATELY,
        # inline, inside this same request. Both callbacks below are therefore
        # a real, uncounted cost on every qualifying topic-detail GET in
        # production.
        #
        # Note the asymmetry that hides this: under @pytest.mark.django_db the
        # test body IS inside an atomic block, so on_commit takes the deferring
        # branch and the callback is rolled back without ever running. That is why
        # test_topic_detail.py's read-recording tests need the
        # django_capture_on_commit_callbacks fixture at all — and why its
        # test_view_count_does_not_add_queries_to_response can legitimately pin
        # 4 queries. That pin is honest about the test and says nothing about
        # production; do not read it as evidence these callbacks are free.
        #
        # Accepted rather than wrapped in atomic() or moved to Celery: an
        # atomic() wrap buys deferral-to-commit and isolation hygiene, not a
        # smaller production query count (the work still happens in-request);
        # and the writes are two cheap dedup-gated UPDATEs on a read path with
        # no user-facing symptom.
        # `robust=True` on _mark_read is still load-bearing on this path —
        # the autocommit branch honors it (same source), so a failure logs
        # instead of turning an already-successful 200 into a 500. Revisit
        # trigger: topic-detail p99 regressing, or a third callback landing
        # here. Do not re-litigate per-slice.
        #
        # The cache key is scoped per (topic, viewer) — authenticated users key on
        # their pk; anonymous requests key on the client IP so a single browser
        # session doesn't multi-count. The TTL is host-configurable via
        # WAGTAILFORUM_VIEW_COUNT_DEDUP_SECONDS (default 15 min).
        from ..conf import get_setting

        topic_id = self.kwargs[self.lookup_url_kwarg]
        viewer = (
            request.user.pk
            if request.user.is_authenticated
            else request.META.get("REMOTE_ADDR", "anon")
        )
        dedup_key = f"forum:vc:{topic_id}:{viewer}"
        ttl = get_setting("VIEW_COUNT_DEDUP_SECONDS")
        if cache.add(dedup_key, True, ttl):

            def _increment():
                Topic.objects.filter(pk=topic_id).update(view_count=F("view_count") + 1)

            transaction.on_commit(_increment)

        # Record the read (todo 253 slice 5, H10). Deduplicated per (topic,
        # viewer, last_post_at) rather than a plain TTL like view_count above:
        # folding last_post_at into the key (free from the response already
        # built above, no extra query) means a new reply naturally rotates
        # the key instead of a same-TTL-window dedup silently swallowing it.
        # Its own setting (TOPIC_READ_DEDUP_SECONDS) — gates a distinct
        # concern from view_count's throttle above, even though the two
        # currently default to the same value.
        if request.user.is_authenticated:
            user = request.user
            read_dedup_key = (
                f"forum:tr:{topic_id}:{user.pk}:{response.data.get('last_post_at')}"
            )
            read_ttl = get_setting("TOPIC_READ_DEDUP_SECONDS")
            if cache.add(read_dedup_key, True, read_ttl):

                def _mark_read():
                    # Ensures the watermark-bearing profile row exists. Since
                    # todo 285 that row's read_watermark_at is seeded from the
                    # user's date_joined rather than "now", so this genuine
                    # read marks exactly THIS topic read (via TopicRead below)
                    # and leaves the rest of the user's backlog unread. Before
                    # 285 a first read collapsed the backlog forest-wide, which
                    # is the bug 285 fixed — see models/profiles.py. Pinned by
                    # test_first_read_leaves_a_sleepers_other_topics_unread.
                    ForumProfile.for_user(user)
                    TopicRead.mark_read(user, topic_id)

                # robust=True: an exception here must not turn an
                # already-successful 200 into a 500 (Angle E).
                transaction.on_commit(_mark_read, robust=True)
        return response


@extend_schema(
    responses={200: PostSerializer(many=True), 404: dict},
    description=(
        "List a topic's live posts, oldest first (cursor-paginated). Returns "
        "404 if the topic is non-live or on a hidden/non-live board."
    ),
)
class PostListView(
    UnversionedForumAPIMixin, PrivateForumReadCacheMixin, generics.ListAPIView
):
    serializer_class = PostSerializer
    pagination_class = PostCursorPagination
    filter_backends = []  # host filter-backend opt-out — see BoardListView
    # GET (list) is public; only the merged POST (reply) needs auth — exactly
    # IsAuthenticatedOrReadOnly (also the project default), declared explicitly.
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Post.objects.none()
        topic = get_object_or_404(
            Topic.objects.filter(live=True, board__in=_visible_boards()),
            id=self.kwargs["topic_id"],
        )
        # select_related("topic") so PostSerializer.can_edit/can_delete
        # (Post.edit_block reads obj.topic) adds no per-post query — flat, no N+1
        # for authenticated listers (todo 252).
        return topic.posts.filter(live=True).select_related(
            "author__wagtail_forum_profile__avatar", "topic"
        )

    def list(self, request, *args, **kwargs):
        # Build the page's image map ONCE (one batched query) and feed it to the
        # serializer via context, so image-block rendition serialization never
        # fans out into a per-image lookup (the post-list query count is pinned).
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        objects = page if page is not None else queryset
        # Per-page batched map of the CURRENT user's reactions (M23) so the
        # serializer's `reacted` field costs zero per-post queries — one query
        # for the whole page, like build_forum_image_map. Authed-only: an
        # anonymous list issues no reaction query, so its pin stays 3.
        reacted_map = None
        if request.user.is_authenticated:
            reacted_map = {}
            for post_id, rtype in Reaction.objects.filter(
                post__in=objects, user=request.user
            ).values_list("post_id", "reaction_type"):
                reacted_map.setdefault(post_id, []).append(rtype)
        context = {
            **self.get_serializer_context(),
            "forum_image_map": build_forum_image_map(objects),
            "forum_reacted_map": reacted_map,
        }
        serializer = self.get_serializer(objects, many=True, context=context)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @extend_schema(
        request=ReplyCreateSerializer,
        responses={201: dict, 400: dict, 401: dict, 404: dict, 409: dict, 422: dict},
        description=(
            "Reply to a topic; the reply routes through moderation. On success "
            "returns 201 with a Location header for the new post. Supports an "
            "Idempotency-Key header (a mobile retry must not create a duplicate "
            "reply); reuse with a different payload returns 422."
        ),
    )
    def post(self, request, topic_id):
        cache_key = idempotency_cache_key(request, "reply-create")
        payload_fp = (
            fingerprint({"topic": topic_id, "body": request.data})
            if cache_key
            else None
        )
        replayed = _replay_or_none(cache_key, payload_fp)
        if replayed is not None:
            return replayed

        # SECURITY: hide non-live topics and topics on hidden boards entirely
        # (404) BEFORE the closed/locked check — a 403/409 on a draft would
        # leak its existence, and a reply must never go live on a hidden
        # thread. Board liveness/privacy counts too (audit M6/M7).
        topic = get_object_or_404(
            Topic.objects.filter(live=True, board__in=_visible_boards()),
            id=topic_id,
        )
        if topic.is_closed or topic.locked:
            raise Conflict(_("Topic is closed to replies."))
        serializer = ReplyCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        reserve(cache_key)  # 409 if a same-key twin is mid-flight (atomic add)
        post = Post(
            topic=topic,
            author=request.user,
            is_opening_post=False,
            body=ForumBodyBlock().to_python(serializer.validated_data["body"]),
            live=False,  # born as a draft; published by moderation
        )
        post.save()

        # A pluggable spam backend can raise; the reply is already live=False, so
        # never 500 — leave it pending for a moderator.
        try:
            moderation_status = submit_for_moderation(post, request.user)
        except Exception:
            logger.exception(
                "[ERROR] submit_for_moderation failed for reply %s; left as draft",
                post.pk,
            )
            moderation_status = "pending"

        result = {"id": post.id, "status": moderation_status}
        location = _created_location(request, "post-detail", post_id=post.id)
        remember(
            cache_key,
            result,
            http_status.HTTP_201_CREATED,
            payload_fp,
            headers={"Location": location},
        )
        response = Response(result, status=http_status.HTTP_201_CREATED)
        response["Location"] = location
        return response


class PostWriteView(UnversionedForumAPIMixin, APIView):
    """Edit (PATCH) or soft-delete (DELETE) a single post. Author or moderator."""

    permission_classes = [IsAuthenticated]

    def _get_editable(self, request, post_id):
        # Existence gate only (single-query _get_visible_post; no existence leak,
        # audit M6/M7). The write POLICY (owner-or-mod, per-post lock, frozen
        # topic, opening-post) lives in Post.edit_block/delete_block, single-
        # sourced with PostSerializer's can_edit/can_delete (todo 252);
        # patch()/delete() enforce it via _enforce_writable.
        return _get_visible_post(post_id)

    @staticmethod
    def _enforce_writable(block):
        """Map a ``Post.edit_block``/``delete_block`` result to an HTTP rejection.

        ``None`` means allowed. ``(BLOCK_FORBIDDEN, None)`` → 403 (not owner/mod,
        no existence leak beyond the 404 gate); every other code carries a message
        and is a 409 state conflict (locked post / frozen topic / opening post).
        """
        if block is None:
            return
        code, message = block
        if code == BLOCK_FORBIDDEN:
            raise PermissionDenied()
        raise Conflict(message)

    @extend_schema(
        request=PostEditSerializer,
        responses={
            200: PostSerializer,
            400: dict,
            401: dict,
            403: dict,
            404: dict,
            409: dict,
            422: dict,
        },
        description=(
            "Edit a post (author or moderator). Re-screened by author trust: a "
            "trusted edit publishes immediately; an untrusted edit awaits "
            "moderation while the last-approved body keeps serving. Response is "
            "the post plus moderation_status (published|pending). When "
            "moderation_status is 'pending', the response body reflects the "
            "SUBMITTED revision (what you sent) — reads (GET) keep returning "
            "the last-approved live body until the edit clears moderation. "
            "409 if the topic is closed/locked. Supports an Idempotency-Key "
            "header: a retry with the same key replays the original response "
            "instead of writing a second revision / re-firing moderation and "
            "its push (409 if a same-key twin is mid-flight, 422 on payload "
            "reuse with a different body)."
        ),
    )
    def patch(self, request, post_id):
        # Idempotency (M35): a mobile retry of an edit must not re-run
        # submit_edit_for_moderation — that writes a second revision, re-emits
        # moderation_decided, and fires a DUPLICATE FCM push (no dedup downstream).
        cache_key = idempotency_cache_key(request, "post-edit")
        payload_fp = (
            fingerprint({"post": post_id, "body": request.data}) if cache_key else None
        )
        replayed = _replay_or_none(cache_key, payload_fp)
        if replayed is not None:
            return replayed

        post = self._get_editable(request, post_id)
        self._enforce_writable(post.edit_block(request.user))
        serializer = PostEditSerializer(
            data=request.data,
            context={"request": request, "existing_author_id": post.author_id},
        )
        serializer.is_valid(raise_exception=True)
        post.body = ForumBodyBlock().to_python(serializer.validated_data["body"])
        reserve(cache_key)  # 409 if a same-key twin is mid-flight (atomic add)
        # submit_edit_for_moderation owns the persistence contract: a pre-revision
        # failure propagates (never a fake 'pending'); a moderation-step failure is
        # caught there and reported truthfully as pending. Do NOT re-wrap it in a
        # blanket `except -> pending`, which would re-introduce the lie (finding #3).
        # acting_as_moderator only affects an account-deleted (author=None) post.
        # A hard delete (topic CASCADE from the admin) racing this edit makes the
        # helper's lock re-fetch raise DoesNotExist — map it to 404, not a 500.
        try:
            moderation_status = submit_edit_for_moderation(
                post,
                request.user,
                acting_as_moderator=request.user.has_perm("wagtail_forum.change_post"),
            )
        except Post.DoesNotExist:
            raise NotFound()
        # submit_edit_for_moderation already refresh_from_db()'d `post` (the same
        # instance), so it is current here — no extra round-trip needed.
        serialize_source = post
        if moderation_status == "pending":
            # The live row keeps serving the last-approved body while the edit
            # awaits moderation — but echoing that stale body back to the editor
            # renders their edit "reverting" with nothing in the response shape
            # signalling it (audit 2026-07-11 H23, execution-proven). Serialize
            # the SUBMITTED revision instead: the response reflects what the
            # client sent, moderation_status carries the pending state, and GET
            # keeps returning the live body.
            serialize_source = post.latest_revision.as_object()
        data = PostSerializer(
            serialize_source,
            context={
                "request": request,
                "forum_image_map": build_forum_image_map([serialize_source]),
            },
        ).data
        data["moderation_status"] = moderation_status
        # Cache the outcome so a mobile retry with the same key replays this 200
        # instead of re-running the edit — which would write a second revision,
        # re-fire moderation_decided, and send a duplicate push (M35).
        remember(cache_key, data, http_status.HTTP_200_OK, payload_fp)
        return Response(data)

    @extend_schema(
        responses={204: None, 403: dict, 404: dict, 409: dict},
        description=(
            "Soft-delete a post (author or moderator) by unpublishing it; the "
            "topic's reply_count recounts via the unpublish signal. 409 if the "
            "topic is closed/locked. Opening posts cannot be deleted via the "
            "API (409)."
        ),
    )
    def delete(self, request, post_id):
        post = self._get_editable(request, post_id)
        # Policy is single-sourced in Post.delete_block: frozen-topic 409 (no
        # moderator bypass — DELIBERATELY mirrors PATCH's frozen guard, so a topic
        # must be reopened before editing OR deleting in it; finding #5) plus the
        # opening-post 409 (no topic-delete endpoint exists, finding #7).
        # (The count stays correct either way — unpublish()'s recount signal is
        # topic-state-independent — so this guard is a consistency choice, not a
        # data-integrity one.) PostSerializer.can_delete reads the same predicate.
        self._enforce_writable(post.delete_block(request.user))
        # Serialize against a racing PATCH: lock the row and re-read liveness under
        # the lock so a concurrent trusted edit's publish() cannot resurrect this
        # post after we take it down (finding #13, mirrors submit_edit_for_moderation).
        with transaction.atomic():
            try:
                locked = Post.objects.select_for_update().get(pk=post.pk)
            except Post.DoesNotExist:
                raise NotFound()  # hard-deleted (topic CASCADE) between fetch and lock
            if not locked.live:
                raise NotFound()  # already taken down by a concurrent delete
            # UnpublishAction fires Wagtail's `unpublished` signal -> the forum's
            # counter receivers recount reply_count/last_post_at/board/profile. Do
            # NOT recount by hand (that double-processes). The acting user is
            # passed for audit-log attribution (snippet History) with
            # skip_permission_checks=True — the view's own guards are the
            # authority, and the DraftStateMixin.unpublish() convenience cannot
            # skip the editor permission check (audit 2026-07-11 M15). It SAVES
            # the row, so act on `locked` (the fresh under-lock instance), never
            # the pre-lock `post` read whose fields may be stale.
            UnpublishAction(locked, user=request.user).execute(
                skip_permission_checks=True
            )
        return Response(status=http_status.HTTP_204_NO_CONTENT)


def _is_forum_moderator(user):
    """The single moderator predicate for the revision endpoints.

    Mirrors the check the edit/redact path already uses
    (``PostWriteView.patch``'s ``acting_as_moderator``) rather than inventing a
    second notion of "moderator" that could drift from it.
    """
    return user.has_perm("wagtail_forum.change_post")


def _revision_privacy_block(post, user):
    """``None`` if *user* may read *post*'s revision history, else a reason.

    **The privacy decision (todo 282).** A revision is a verbatim snapshot of a
    body that may since have been redacted — a moderator editing out doxxing,
    a phone number, or abuse leaves that content sitting in the previous
    revision. Serving history unconditionally would hand every redacted string
    straight back through a new endpoint and silently undo the moderation.

    So: **moderators always; the author only while no one else has edited the
    post.** A revision written by someone other than the author IS the signal
    that something needed removing, and the thing removed is in the revisions
    before it — so the whole list goes moderator-only from that point. An
    ordinary self-edited post (the overwhelming majority) is unaffected, which
    is the case this feature exists for.

    Conservative on both edges: a revision with a NULL user counts as
    third-party (unattributable), and on an account-deleted post
    (``author_id is None``) *any* revision does — only a moderator can have
    written one.
    """
    if _is_forum_moderator(user):
        return None
    # The `author_id is None` arm is belt-and-braces — an authenticated user's
    # pk is never None, so the second comparison already covers it — but the
    # account-deleted case is the one where "author" has no meaning at all, and
    # a security gate is the wrong place to rely on that inference.
    if post.author_id is None or user.pk != post.author_id:
        return BLOCK_FORBIDDEN
    # `exclude(user_id=X)` keeps NULL-user rows (Django compiles the NULL-safe
    # form), which is what we want — an unattributable revision is third-party.
    if post.revisions.exclude(user_id=post.author_id).exists():
        return BLOCK_FORBIDDEN
    return None


def _readable_post_revisions(request, post_id):
    """Fetch the post + its revisions queryset, or raise 403/404.

    Shared by the list and detail views so the visibility gate, the privacy
    gate and the ``select_related`` chain cannot drift between them.
    """
    post = _get_visible_post(post_id)
    if _revision_privacy_block(post, request.user) is not None:
        raise PermissionDenied()
    revisions = post.revisions.select_related(
        # Same chain as the post list's author join (H7): the avatar is the raw
        # file URL, not a rendition, so this stays one query for the whole page.
        "user__wagtail_forum_profile__avatar"
    ).order_by("-created_at", "-id")
    return post, revisions


REVISION_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "created_at": {"type": "string", "format": "date-time"},
        "user": AUTHOR_SCHEMA,
    },
}
REVISION_DETAIL_SCHEMA = {
    "type": "object",
    "properties": {
        **REVISION_SCHEMA["properties"],
        "body": FORUM_BODY_SCHEMA,
    },
}


@extend_schema(
    responses={
        200: {"type": "array", "items": REVISION_SCHEMA},
        401: dict,
        403: dict,
        404: dict,
    },
    description=(
        "List a post's edit history (newest first). Author or moderator only. "
        "A post edited by anyone other than its author becomes moderator-only, "
        "because earlier revisions still hold whatever the edit removed."
    ),
)
class PostRevisionListView(
    UnversionedForumAPIMixin, PrivateForumReadCacheMixin, APIView
):
    """``GET /posts/{id}/revisions/`` — the list behind the "Edited" stamp.

    Read-only. Every edit already writes a `wagtailcore.Revision`
    (``RevisionMixin`` on ``Post``); this exposes what was already being stored.

    **Unpaginated, deliberately** — unlike ``TopicListView``/``PostListView``.
    A revision list is bounded by how many times one post has been edited,
    which is small in practice and not attacker-controlled beyond the author's
    own edit rate (already throttled on the write side). Paginating would add
    a second cursor shape to the API for no measured problem. Revisit if a
    real post ever accumulates enough revisions to matter.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, post_id):
        _post, revisions = _readable_post_revisions(request, post_id)
        return Response(
            [
                {
                    "id": revision.id,
                    "created_at": revision.created_at,
                    "user": serialize_forum_author(revision.user, request),
                }
                for revision in revisions
            ]
        )


@extend_schema(
    responses={200: REVISION_DETAIL_SCHEMA, 401: dict, 403: dict, 404: dict},
    description=(
        "One revision's body, in the same shape as the live post body so a "
        "client can diff the two directly."
    ),
)
class PostRevisionDetailView(
    UnversionedForumAPIMixin, PrivateForumReadCacheMixin, APIView
):
    """``GET /posts/{id}/revisions/{revision_id}/`` — one revision's body.

    The body goes through ``serialize_forum_body`` with a real image map, so it
    is byte-identical in shape to ``PostSerializer``'s ``body`` and the client
    can diff the two without a second renderer. Diffing is client-side by
    design — a server-side diff library is not worth it for a p3.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, post_id, revision_id):
        _post, revisions = _readable_post_revisions(request, post_id)
        revision = get_object_or_404(revisions, id=revision_id)
        # as_object() deserializes the stored JSON into a Post instance — never
        # hand-parse the revision JSON, or the body shape drifts from the live
        # one the moment a block type changes.
        snapshot = revision.as_object()
        return Response(
            {
                "id": revision.id,
                "created_at": revision.created_at,
                "user": serialize_forum_author(revision.user, request),
                "body": serialize_forum_body(
                    snapshot.body,
                    image_map=build_forum_image_map([snapshot]),
                    request=request,
                ),
            }
        )


def _alt_text(request) -> str:
    """Author-supplied alt text off a multipart upload (M7), bounded and safe.

    Deliberately `isinstance(str)` rather than a bare `.get("alt")`:
    ``request.data`` MERGES POST and FILES under MultiPartParser, so a client
    sending `alt` as a file part yields an ``UploadedFile`` and `.strip()` on it
    raises ``AttributeError`` — a 500 on a malformed request. Anything that is
    not a plain string is treated as no alt at all.
    """
    value = request.data.get("alt")
    if not isinstance(value, str):
        return ""
    return value.strip()[:255]


class PostImageUploadView(UnversionedForumAPIMixin, APIView):
    """Upload an inline post image (4-layer validated) into the forum collection.

    Topic-independent (Spec 2 PR-3): a new-thread composer has no topic id yet,
    and an image is scoped by collection, not topic. The body references the
    returned id via an `image` block (membership-checked in api/sanitize.py).
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "image": {"type": "string", "format": "binary"},
                    "alt": {
                        "type": "string",
                        "maxLength": 255,
                        "description": (
                            "Author-supplied alt text (M7). Optional — omit or "
                            "send empty for a decorative image. Truncated to "
                            "255 chars. Plain text by contract; never markup."
                        ),
                    },
                },
            }
        },
        responses={201: dict, 400: dict, 401: dict, 409: dict, 422: dict},
        description=(
            "Upload an inline post image (4-layer validated: extension, MIME, "
            "size, PIL decode) into the forum image collection. Returns "
            "{id, url, alt, width, height} with a Location header; reference the "
            "returned id from an `image` body block. Requires authentication. "
            "An optional `alt` part carries author-supplied alt text (M7); it is "
            "stored on the image and echoed back as `alt`. "
            "Supports an Idempotency-Key header: a retry with the same key "
            "replays the original response instead of storing a duplicate image "
            "row + file (409 if a same-key twin is mid-flight, 422 on key reuse "
            "with a different image)."
        ),
    )
    def post(self, request):
        image_file = request.FILES.get("image")
        if image_file is None:
            raise ValidationError(_("No image file provided."))
        validate_image_upload(image_file)
        # Idempotency (M36): the multipart upload is the most retry-prone shape
        # (mobile composer on a flaky network). request.data holds the
        # UploadedFile, not JSON, so fingerprint on a CONTENT hash — name+size
        # alone could collide. seek(0) before hashing (validate may have consumed
        # the stream) AND after (so .create() still stores the full file).
        #
        # `alt` is deliberately NOT in the fingerprint (M7). Including it would
        # 422 a legitimate same-key retry that happens to carry corrected alt
        # text, since key reuse with a mismatched fingerprint is a 422. The
        # consequence, accepted: remember() caches the SERIALIZED RESPONSE, so a
        # replay returns the original alt and a new one sent on the retry is
        # silently dropped. Re-authoring alt means a fresh upload (no key), which
        # is also the only way to change it — there is no alt PATCH endpoint.
        cache_key = idempotency_cache_key(request, "image-upload")
        payload_fp = None
        if cache_key:
            image_file.seek(0)
            content_hash = hashlib.sha256(image_file.read()).hexdigest()
            image_file.seek(0)
            payload_fp = fingerprint({"name": image_file.name, "sha256": content_hash})
        replayed = _replay_or_none(cache_key, payload_fp)
        if replayed is not None:
            return replayed

        reserve(cache_key)  # 409 if a same-key twin is mid-flight (atomic add)
        image = get_image_model().objects.create(
            title=(image_file.name or "forum-image")[:255],
            # Author-supplied alt (M7), stored on Wagtail's own alt-text field.
            # Truncated rather than 400'd, matching the title idiom above: a
            # too-long alt is a UI slip, not a malformed request, and the
            # column is CharField(max_length=255) so an unbounded value would
            # raise DataError. Empty is legitimate — a decorative image should
            # carry alt="", which beats a filename for a screen reader.
            description=_alt_text(request),
            file=image_file,
            collection=get_forum_image_collection(),
            uploaded_by_user=request.user,
        )
        data = serialize_image_for_api(image, request)
        remember(
            cache_key,
            data,
            http_status.HTTP_201_CREATED,
            payload_fp,
            headers={"Location": data["url"]},
        )
        response = Response(data, status=http_status.HTTP_201_CREATED)
        response["Location"] = data["url"]  # created image's absolute URL (L19)
        return response


class ReactionToggleView(UnversionedForumAPIMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ReactionSerializer,
        responses={200: dict, 400: dict, 401: dict, 404: dict, 409: dict, 422: dict},
        description=(
            "Toggle a reaction. The response's `reacted` is a BOOLEAN — the "
            "resulting state of THIS reaction type for this user (distinct from "
            "a post payload's `reacted`, which is the string[] of all the user's "
            "active types on that post). With an Idempotency-Key header a retry "
            "replays the original result instead of toggling back."
        ),
    )
    def post(self, request, post_id):
        cache_key = idempotency_cache_key(request, "reaction-toggle")
        payload_fp = (
            fingerprint({"post": post_id, "body": request.data}) if cache_key else None
        )
        replayed = _replay_or_none(cache_key, payload_fp)
        if replayed is not None:
            return replayed

        post = _get_visible_post(post_id)  # 404s hidden posts/topics/boards (M6/M7)
        serializer = ReactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reserve(cache_key)  # 409 if a same-key twin is mid-flight (atomic add)
        rtype = serializer.validated_data["type"]
        existing = Reaction.objects.filter(
            post=post, user=request.user, reaction_type=rtype
        ).first()
        if existing:
            existing.delete()
            reacted = False
        else:
            # A concurrent double-tap can race two INSERTs past the SELECT; the
            # unique constraint (post, user, reaction_type) protects integrity —
            # treat the loser as "already reacted" instead of surfacing a 500.
            try:
                with transaction.atomic():
                    Reaction.objects.create(
                        post=post, user=request.user, reaction_type=rtype
                    )
            except IntegrityError:
                pass
            reacted = True
        counts = Reaction.recount(post)
        result = {"reaction_counts": counts, "reacted": reacted}
        remember(cache_key, result, http_status.HTTP_200_OK, payload_fp)
        return Response(result, status=http_status.HTTP_200_OK)


class PostReportView(UnversionedForumAPIMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ReportSerializer,
        responses={200: dict, 400: dict, 401: dict, 404: dict, 409: dict, 422: dict},
        description=(
            "Report a post for moderator review. Idempotent per (post, "
            "reporter): reporting the same post again is a no-op, not an "
            "error. Never echoes a flag/report count — that would signal "
            "proximity to the auto-hide threshold (audit L12)."
        ),
    )
    def post(self, request, post_id):
        cache_key = idempotency_cache_key(request, "post-report")
        payload_fp = (
            fingerprint({"post": post_id, "body": request.data}) if cache_key else None
        )
        replayed = _replay_or_none(cache_key, payload_fp)
        if replayed is not None:
            return replayed

        post = _get_visible_post(post_id)  # 404s hidden posts/topics/boards (M6/M7)
        # Single-sourced on the model (can_be_reported_by) so this guard and the
        # serializer's can_report affordance cannot diverge — same discipline as
        # PostWriteView's edit_block/delete_block (todo 252).
        if not post.can_be_reported_by(request.user):
            raise ValidationError({"detail": _("You cannot report your own post.")})
        serializer = ReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reserve(cache_key)  # 409 if a same-key twin is mid-flight (atomic add)
        try:
            # A hard delete (topic CASCADE from the admin) racing this report
            # makes Report.file's lock re-fetch raise DoesNotExist — map it to
            # 404, not a 500 (mirrors PostWriteView.patch's identical guard).
            Report.file(post, request.user, **serializer.validated_data)
        except Post.DoesNotExist:
            raise NotFound()
        result = {"reported": True}
        remember(cache_key, result, http_status.HTTP_200_OK, payload_fp)
        return Response(result, status=http_status.HTTP_200_OK)


@extend_schema_view(
    get=extend_schema(
        responses={200: MeProfileSerializer, 401: dict},
        description=(
            "Retrieve the authenticated user's forum profile (bio, avatar, "
            "trust level, capabilities, and the write-only fcm_token field)."
        ),
    ),
    patch=extend_schema(
        request=MeProfileSerializer,
        responses={200: MeProfileSerializer, 400: dict, 401: dict},
        description=(
            "Update the authenticated user's forum profile (partial). Returns "
            "400 if bio exceeds 2000 chars or fcm_token exceeds 255 chars."
        ),
    ),
)
class MeProfileView(
    UnversionedForumAPIMixin, PrivateForumReadCacheMixin, generics.RetrieveUpdateAPIView
):
    serializer_class = MeProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = []  # host filter-backend opt-out — see BoardListView
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        from ..models import ForumProfile

        return ForumProfile.for_user(self.request.user)


ME_STATS_SCHEMA = {
    "type": "object",
    "properties": {
        "posts": {"type": "integer"},
        "solutions_accepted": {"type": "integer"},
        "identifications_shared": {"type": "integer"},
    },
}


class MeStatsView(UnversionedForumAPIMixin, PrivateForumReadCacheMixin, APIView):
    """All-time forum stats for the requesting user ("Your season" cards).

    All-time by design (spec §9): no season windowing, and the client's card
    sublabels must not claim one. Three cheap reads — the denormalized
    profile.post_count plus two indexed COUNTs — no server-side caching, but
    `PrivateForumReadCacheMixin` still marks the response `no-store, private`
    (round-2 review) so a per-user payload can never be heuristically stored
    by an intermediary CDN/proxy that caches everything by default — same
    reasoning as TopicDetailView, not a claim that this view itself caches.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: ME_STATS_SCHEMA},
        description="All-time forum stats for the requesting user.",
    )
    def get(self, request):
        from ..models import ForumIdentificationAttachment, ForumProfile

        profile = ForumProfile.for_user(request.user)
        return Response(
            {
                "posts": profile.post_count,
                "solutions_accepted": Topic.objects.filter(
                    solved_post__author=request.user, live=True
                ).count(),
                # Topic-level attachments (OneToOne on Topic — spec corrected
                # at plan time): attachments the user shared on their topics.
                "identifications_shared": ForumIdentificationAttachment.objects.filter(
                    topic__author=request.user, topic__live=True
                ).count(),
            }
        )


PUBLIC_PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "username": {"type": "string"},
        "display_name": {"type": "string"},
        "avatar": {"type": "string", "nullable": True},
        "trust_level": {"type": "integer", "nullable": True},
        "title": {"type": "string"},
        "bio": {"type": "string"},
        "signature": {"type": "string"},
        "post_count": {"type": "integer"},
        "joined_at": {"type": "string", "format": "date-time", "nullable": True},
        "recent_topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "slug": {"type": "string"},
                    "title": {"type": "string"},
                    "board_id": {"type": "integer"},
                    "board_slug": {"type": "string"},
                    "reply_count": {"type": "integer"},
                    "created_at": {"type": "string", "format": "date-time"},
                },
            },
        },
        "recent_posts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "topic_id": {"type": "integer"},
                    "topic_slug": {"type": "string"},
                    "topic_title": {"type": "string"},
                    "board_id": {"type": "integer"},
                    "board_slug": {"type": "string"},
                    "created_at": {"type": "string", "format": "date-time"},
                },
            },
        },
    },
}


class PublicProfileView(UnversionedForumAPIMixin, APIView):
    """Public forum profile: identity + trust + recent activity, read-only.

    Deliberately does NOT expose fcm_token (a credential) or flags_received (a
    moderation-proximity signal, audit L12), and NEVER creates a ForumProfile
    for an arbitrary username — a real-but-profileless user serializes to
    defaults (like serialize_forum_author); only a missing/inactive user 404s.
    Recent activity is built as lightweight dicts, NOT PostSerializer/
    TopicListSerializer: those would recompute `reacted` for the profile user
    (meaningless here) and re-trigger the body/author N+1s (todo 257 slice B).
    """

    permission_classes = [AllowAny]
    RECENT_LIMIT = 10

    @extend_schema(
        responses={200: PUBLIC_PROFILE_SCHEMA, 404: dict},
        description=(
            "Public forum profile for a username: display_name, avatar, "
            "trust_level, bio, signature, lifetime post_count, and the user's "
            "most recent live topics + replies (each bounded to 10, "
            "visibility-filtered). 404 for a missing or inactive user. Never "
            "exposes fcm_token or flags_received."
        ),
    )
    def get(self, request, username):
        User = get_user_model()
        user = get_object_or_404(
            User.objects.select_related("wagtail_forum_profile__avatar"),
            username=username,
            is_active=True,
        )
        profile = getattr(user, "wagtail_forum_profile", None)
        boards = _visible_boards()
        recent_topics = [
            {
                "id": t.id,
                "slug": t.slug,
                "title": t.title,
                "board_id": t.board_id,
                "board_slug": t.board.slug,
                "reply_count": t.reply_count,
                "created_at": t.created_at,
            }
            for t in (
                Topic.objects.filter(author=user, live=True, board__in=boards)
                .select_related("board")
                .order_by("-created_at")[: self.RECENT_LIMIT]
            )
        ]
        recent_posts = [
            {
                "id": p.id,
                "topic_id": p.topic_id,
                "topic_slug": p.topic.slug,
                "topic_title": p.topic.title,
                "board_id": p.topic.board_id,
                "board_slug": p.topic.board.slug,
                "created_at": p.created_at,
            }
            for p in (
                Post.objects.filter(
                    author=user,
                    live=True,
                    is_opening_post=False,
                    topic__live=True,
                    topic__board__in=boards,
                )
                .select_related("topic", "topic__board")
                .order_by("-created_at")[: self.RECENT_LIMIT]
            )
        ]
        return Response(
            {
                # Single-sourced identity — same absolute-URL avatar as posts.
                **serialize_forum_author(user, request),
                "bio": profile.bio if profile else "",
                "signature": profile.signature if profile else "",
                "post_count": profile.post_count if profile else 0,
                "joined_at": profile.joined_at if profile else None,
                "recent_topics": recent_topics,
                "recent_posts": recent_posts,
            }
        )


def plain_text_excerpt(stream_value, limit: int) -> str:
    """Plain-text excerpt from a post body via ``raw_data``.

    Iterating the resolved StreamValue bulk-fetches image blocks PER POST —
    the exact N+1 the ``serialize_forum_body`` raw_data path exists to avoid —
    and slicing rendered HTML can cut a tag mid-attribute. Text-bearing block
    values are strings (paragraph HTML, heading, quote) or a dict carrying a
    ``code`` string; image blocks hold an int PK and are skipped.
    """
    parts: list[str] = []
    total = 0
    for raw in stream_value.raw_data:
        value = raw.get("value")
        if isinstance(value, str):
            text = strip_tags(value).strip()
        elif isinstance(value, dict) and isinstance(value.get("code"), str):
            text = value["code"].strip()
        else:
            continue
        if not text:
            continue
        parts.append(text)
        total += len(text)
        if total >= limit:
            break
    return " ".join(parts)[:limit]


RECENT_TOPICS_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "slug": {"type": "string"},
                    "title": {"type": "string"},
                    "board": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                            "slug": {"type": "string"},
                        },
                    },
                    "reply_count": {"type": "integer"},
                    "last_post_at": {
                        "type": "string",
                        "format": "date-time",
                        "nullable": True,
                    },
                    "is_pinned": {"type": "boolean"},
                    "thumbnail_url": {"type": "string", "nullable": True},
                },
            },
        }
    },
}


class RecentTopicsView(UnversionedForumAPIMixin, PublicForumReadCacheMixin, APIView):
    """Cross-board latest topics for the landing rail ("Active now").

    Owns its shape as lightweight dicts (same pattern as PublicProfileView) —
    deliberately NOT TopicListSerializer, so this never becomes a fourth hit
    builder (todo 273). Thumbnails resolve batched from the opening posts'
    first image block (StreamField raw_data — never iterate the StreamValue,
    which fires per-object image fetches; docs/LEARNINGS.md 2026-06-25), with
    the topic's identification-attachment image as fallback.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        responses={200: RECENT_TOPICS_SCHEMA},
        description=(
            "Latest live topics across all visible boards, most recent "
            "activity first. ?limit= defaults to RECENT_TOPICS_DEFAULT_LIMIT, "
            "capped at RECENT_TOPICS_MAX_LIMIT."
        ),
    )
    def get(self, request):
        from ..models import ForumIdentificationAttachment, Post

        try:
            limit = int(request.query_params.get("limit", ""))
        except ValueError:
            limit = get_setting("RECENT_TOPICS_DEFAULT_LIMIT")
        limit = max(1, min(limit, get_setting("RECENT_TOPICS_MAX_LIMIT")))

        topics = list(
            Topic.objects.filter(
                board__in=_visible_boards(), live=True, last_post_at__isnull=False
            )
            .select_related("board")
            .order_by("-last_post_at", "-id")[:limit]
        )
        topic_ids = [t.pk for t in topics]

        # First image block id per topic, from opening posts' raw stream data.
        image_id_by_topic = {}
        for post in Post.objects.filter(
            topic_id__in=topic_ids, is_opening_post=True, live=True
        ).only("topic_id", "body"):
            for block in post.body.raw_data:
                if block.get("type") == "image" and block.get("value"):
                    image_id_by_topic[post.topic_id] = block["value"]
                    break
        for att in ForumIdentificationAttachment.objects.filter(
            topic_id__in=topic_ids, image_id__isnull=False
        ).only("topic_id", "image_id"):
            image_id_by_topic.setdefault(att.topic_id, att.image_id)

        from wagtail.images import get_image_model

        # prefetch_renditions() populates AbstractImage._get_prefetched_renditions(),
        # which find_existing_renditions() consults BEFORE the per-image cache
        # backend / DB lookup (wagtail/images/models.py) — so thumb()'s
        # get_rendition() below is satisfied from this one batched query even
        # when the "renditions" cache is cold, instead of issuing one SELECT
        # per image-bearing topic (N+1 whenever Redis is cold/evicted).
        # in_bulk() chains cleanly: it internally does self.filter(id__in=...)
        # then iterates the queryset, which preserves prefetch_related.
        images = (
            get_image_model()
            .objects.prefetch_renditions("fill-80x80")
            .in_bulk(set(image_id_by_topic.values()))
        )

        def thumb(topic):
            image = images.get(image_id_by_topic.get(topic.pk))
            if image is None:
                return None
            try:
                url = image.get_rendition("fill-80x80").url
            except OSError:
                # Source file missing from disk (media wiped, Image row
                # survives — wagtail raises SourceImageIOError, an OSError
                # subclass). Don't 500 the whole endpoint over one bad
                # thumbnail; log once and omit it for this topic.
                logger.exception(
                    "[ERROR] rendition failed for image %s (topic %s); "
                    "omitting thumbnail",
                    image.pk,
                    topic.pk,
                )
                return None
            return request.build_absolute_uri(url)

        return Response(
            {
                "results": [
                    {
                        "id": t.pk,
                        "slug": t.slug,
                        "title": t.title,
                        "board": {
                            "id": t.board_id,
                            "name": t.board.title,
                            "slug": t.board.slug,
                        },
                        "reply_count": t.reply_count,
                        "last_post_at": t.last_post_at,
                        "is_pinned": t.is_pinned,
                        "thumbnail_url": thumb(t),
                    }
                    for t in topics
                ]
            }
        )


EXPERTS_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {"type": "array", "items": AUTHOR_SCHEMA},
    },
}


class ExpertsView(UnversionedForumAPIMixin, PublicForumReadCacheMixin, APIView):
    """Highest-trust active members for the landing rail.

    No presence data — deliberately (spec §9): the client renders these as
    "Community experts" with no online claim until the presence todo wires
    ForumProfile.last_seen.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        responses={200: EXPERTS_SCHEMA},
        description=(
            "Up to EXPERTS_LIMIT members at or above EXPERTS_MIN_TRUST_LEVEL, "
            "highest trust then post count first."
        ),
    )
    def get(self, request):
        from ..models import ForumProfile

        profiles = (
            ForumProfile.objects.filter(
                trust_level__gte=get_setting("EXPERTS_MIN_TRUST_LEVEL"),
                user__is_active=True,
            )
            .select_related("user", "avatar")
            .order_by("-trust_level", "-post_count", "-id")[
                : get_setting("EXPERTS_LIMIT")
            ]
        )
        return Response(
            {"results": [serialize_forum_author(p.user, request) for p in profiles]}
        )


class SearchView(UnversionedForumAPIMixin, PublicForumReadCacheMixin, APIView):
    PAGE_SIZE = 20  # results per section per page; *_has_more drives client paging
    MAX_PAGE = 50  # ceiling on ?page= — bounds the SQL OFFSET (like CursorPagination.offset_cutoff)
    MAX_EXCERPT_CHARS = 200

    @extend_schema(
        responses={200: dict},
        description=(
            "Search live topic titles and post bodies. Query params: q "
            "(required, truncated to SEARCH_MAX_QUERY_CHARS chars and "
            "SEARCH_MAX_TERMS whitespace-separated terms), board (optional "
            "board slug filter), page (optional, 1-based, capped at "
            "MAX_PAGE). Each section returns up to PAGE_SIZE results plus a "
            "*_has_more flag — no silent cap on RESULTS; page through with "
            "?page=. Offset-paged over relevance-ranked results, so a "
            "concurrent topic/post write can shift the window; clients "
            "should dedup by id when appending pages."
        ),
    )
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        # Bound the query before it reaches the search backend (todo 290): a
        # many-term query recurses Wagtail's search-query AND-tree
        # construction (one nesting level per term) into a RecursionError.
        # Truncate rather than 400 — matches the semantic path's existing
        # behaviour and keeps a pasted-paragraph query usable.
        query = query[: get_setting("SEARCH_MAX_QUERY_CHARS")]
        terms = query.split()
        max_terms = get_setting("SEARCH_MAX_TERMS")
        if len(terms) > max_terms:
            query = " ".join(terms[:max_terms])
        board_slug = request.query_params.get("board", "").strip()
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        page = min(page, self.MAX_PAGE)  # bound the SQL OFFSET on a huge ?page=
        offset = (page - 1) * self.PAGE_SIZE
        topics, posts = [], []
        topics_has_more = posts_has_more = False
        if query:
            backend = get_search_backend()
            boards = _visible_boards()
            topic_qs = Topic.objects.filter(live=True, board__in=boards)
            post_qs = Post.objects.filter(
                live=True, topic__live=True, topic__board__in=boards
            )
            if board_slug:
                # Filter on board_id (declared in search_fields), not
                # board__slug — the modelsearch DB backend raises
                # FilterFieldError on an undeclared related-field lookup.
                board_ids = list(
                    boards.filter(slug=board_slug).values_list("id", flat=True)
                )
                topic_qs = topic_qs.filter(board_id__in=board_ids)
                post_qs = post_qs.filter(topic__board_id__in=board_ids)
            # Window each hit list to [offset, offset+PAGE_SIZE], pulling one
            # extra row to detect a further page without a COUNT query.
            topic_hits = backend.search(query, topic_qs.select_related("board"))
            topic_window = list(topic_hits[offset : offset + self.PAGE_SIZE + 1])
            topics_has_more = len(topic_window) > self.PAGE_SIZE
            for t in topic_window[: self.PAGE_SIZE]:
                topics.append(
                    {
                        "id": t.id,
                        "slug": t.slug,
                        "title": t.title,
                        "reply_count": t.reply_count,
                        "view_count": t.view_count,
                        # Last of the four fields M40 found dropped vs the topic
                        # list. A pinned topic is pinned wherever it surfaces —
                        # the web SearchPage renders the same ThreadCard as the
                        # board list, whose 📌 badge could never fire without it.
                        # Free: t is already loaded, no extra query.
                        "is_pinned": t.is_pinned,
                        # Same reasoning as is_pinned directly above, for the
                        # Solved badge (audit H6): SearchPage renders the same
                        # ThreadCard as the board list, so omitting this would
                        # silently show every search hit as unsolved rather
                        # than fail. Free — t is already loaded, no extra query
                        # and no join (the state is a plain column).
                        "is_solved": t.solved_post_id is not None,
                        "last_post_at": (
                            t.last_post_at.isoformat() if t.last_post_at else None
                        ),
                        "board_id": t.board_id,
                        "board_slug": t.board.slug,
                    }
                )
            post_hits = backend.search(
                query, post_qs.select_related("topic", "topic__board")
            )
            post_window = list(post_hits[offset : offset + self.PAGE_SIZE + 1])
            posts_has_more = len(post_window) > self.PAGE_SIZE
            for p in post_window[: self.PAGE_SIZE]:
                posts.append(
                    {
                        "id": p.id,
                        "topic_id": p.topic_id,
                        "topic_title": p.topic.title,
                        "topic_slug": p.topic.slug,
                        "board_id": p.topic.board_id,
                        "board_slug": p.topic.board.slug,
                        "excerpt": (
                            plain_text_excerpt(p.body, self.MAX_EXCERPT_CHARS)
                            if p.body
                            else ""
                        ),
                    }
                )
        return Response(
            {
                "topics": topics,
                "posts": posts,
                "topics_has_more": topics_has_more,
                "posts_has_more": posts_has_more,
                "page": page,
            }
        )


class SyncView(UnversionedForumAPIMixin, APIView):
    MAX_TOPICS = 200  # page size for the delta poll; has_more signals truncation

    @extend_schema(
        responses={200: dict, 400: dict},
        description=(
            "Mobile delta-sync. Query params: since (ISO-8601, tz-aware), "
            "since_id (int, the last id seen at `since`), board (slug). Returns "
            "topics after the compound (updated_at, id) cursor plus `has_more`, "
            "`next_since` and `next_since_id` for continuation."
        ),
    )
    def get(self, request):
        raw_since = request.query_params.get("since", "")
        since = None
        if raw_since:
            since = parse_datetime(raw_since)
            if since is None or timezone.is_naive(since):
                # A silently-ignored bad value degrades to a full resync; a
                # naive datetime is interpreted in the server TZ (audit M11).
                raise ValidationError(
                    {"since": _("Provide an ISO-8601 datetime with a timezone offset.")}
                )
        try:
            since_id = int(request.query_params.get("since_id", 0) or 0)
        except (TypeError, ValueError):
            raise ValidationError({"since_id": _("Provide an integer topic id.")})

        qs = Topic.objects.filter(live=True, board__in=_visible_boards())
        board_slug = request.query_params.get("board")
        if board_slug:
            qs = qs.filter(board__slug=board_slug)
        if since:
            # Strict compound-key cursor: advance past every (updated_at, id)
            # already seen without re-sending the boundary row and without
            # livelocking when a full page shares one updated_at (bulk import).
            # since_id defaults to 0, so a `since` with no `since_id` behaves
            # like the old >= boundary (first sync loses nothing).
            # The OR form is the ORM idiom for keyset pagination (Django has no
            # row-value tuple lookup); it still rides the partial (updated_at, id)
            # index on Topic (models/topics.py: wf_topic_sync_idx).
            qs = qs.filter(
                Q(updated_at__gt=since) | Q(updated_at=since, id__gt=since_id)
            )
        batch = list(qs.order_by("updated_at", "id")[: self.MAX_TOPICS + 1])
        has_more = len(batch) > self.MAX_TOPICS
        batch = batch[: self.MAX_TOPICS]
        topics = [
            {"id": t.id, "slug": t.slug, "title": t.title, "updated_at": t.updated_at}
            for t in batch
        ]
        # Tombstones: topic ids deleted since the client's last poll. Only
        # meaningful for a delta sync (since provided); a full resync
        # (no since) rebuilds from scratch so there are no stale ids to evict.
        deleted = []
        if since:
            from ..models.tombstones import TopicDeletedLog

            deleted = list(
                TopicDeletedLog.objects.filter(deleted_at__gt=since).values(
                    "topic_id", "board_id"
                )
            )
        return Response(
            {
                "topics": topics,
                "deleted": deleted,
                "has_more": has_more,
                "next_since": batch[-1].updated_at if batch else raw_since or None,
                "next_since_id": batch[-1].id if batch else (since_id or None),
            }
        )
