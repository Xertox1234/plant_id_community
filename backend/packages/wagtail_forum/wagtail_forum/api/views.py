import logging

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics
from rest_framework import status as http_status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView
from wagtail.images import get_image_model
from wagtail.search.backends import get_search_backend

try:  # Schema annotations are optional — hosts without drf-spectacular still work.
    from drf_spectacular.utils import extend_schema
except ImportError:  # pragma: no cover

    def extend_schema(**kwargs):
        def decorator(fn):
            return fn

        return decorator


from ..blocks import ForumBodyBlock
from ..collections import get_forum_image_collection
from ..models import ForumBoard, Post, Reaction, Topic
from ..workflow import submit_edit_for_moderation, submit_for_moderation
from .exceptions import Conflict, UnprocessableEntity
from .idempotency import fingerprint, idempotency_cache_key, remember, replay, reserve
from .pagination import PostCursorPagination, TopicCursorPagination
from .serializers import (
    BoardSerializer,
    MeProfileSerializer,
    PostEditSerializer,
    PostSerializer,
    ReactionSerializer,
    ReplyCreateSerializer,
    TopicCreateSerializer,
    TopicDetailSerializer,
    TopicListSerializer,
    build_forum_image_map,
    serialize_image_for_api,
)
from .upload_validation import validate_image_upload

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
        ).select_related("topic", "author"),
        id=post_id,
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
            "Board slug is ambiguous across forum trees; contact the site admin."
        )
    return boards[0]


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
        raise Conflict("A request with this Idempotency-Key is being processed.")
    if cached["fingerprint"] != payload_fingerprint:
        raise UnprocessableEntity(
            "Idempotency-Key was already used with a different payload."
        )
    # Replay the ORIGINAL status (e.g. 201), not a fresh 200 — clients key on
    # 201 to detect creation (IETF idempotency-key draft).
    return Response(cached["data"], status=cached["status"])


class BoardListView(generics.ListAPIView):
    serializer_class = BoardSerializer
    pagination_class = None  # boards are few; return a flat results list
    # Opt out of host versioning: the package may be mounted outside a version
    # namespace, where NamespaceVersioning would 404 every request.
    versioning_class = None

    def get_queryset(self):
        return _visible_boards().order_by("path")

    def list(self, request, *args, **kwargs):
        data = self.get_serializer(self.get_queryset(), many=True).data
        return Response({"results": data})


@extend_schema(
    responses={200: TopicListSerializer(many=True)},
    description=(
        "List a board's live topics, most-recent activity first "
        "(cursor-paginated). Returns 404 for a hidden/non-live board."
    ),
)
class TopicListView(generics.ListAPIView):
    serializer_class = TopicListSerializer
    pagination_class = TopicCursorPagination
    versioning_class = None
    # GET (list) is public; only the merged POST (create) needs auth — exactly
    # IsAuthenticatedOrReadOnly (also the project default), declared explicitly.
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        # Suppress drf-spectacular's "Failed to obtain model" warning: during
        # schema generation there is no `slug` kwarg to look the board up by.
        if getattr(self, "swagger_fake_view", False):
            return Topic.objects.none()
        board = _get_board(self.kwargs["slug"])
        return (
            Topic.objects.filter(board=board, live=True)
            .select_related("author", "last_post_author")
            .order_by("-last_post_at", "-id")
        )

    @extend_schema(
        request=TopicCreateSerializer,
        responses={201: dict, 409: dict, 422: dict},
        description=(
            "Create a topic (with its opening post) and route it through "
            "moderation. Supports an Idempotency-Key header: a retry with the "
            "same key replays the original response (original status code); "
            "reuse with a different payload returns 422. A taken slug is "
            "auto-suffixed (-2, -3, …) — read the final slug from the response."
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

        serializer = TopicCreateSerializer(data=request.data)
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
        remember(cache_key, result, http_status.HTTP_201_CREATED, payload_fp)
        return Response(result, status=http_status.HTTP_201_CREATED)

    @staticmethod
    def _create_topic(request, board, validated):
        """Create the draft topic + opening post atomically (born live=False).

        A taken slug is auto-suffixed instead of 409ing: the unique constraint
        also covers DRAFT topics, so a conflict response would leak a hidden
        draft's existence (audit L4). Each attempt runs in its own transaction
        so an IntegrityError can't poison an outer atomic block.
        """
        base_slug = validated["slug"]
        for attempt in range(MAX_SLUG_ATTEMPTS):
            if attempt == 0:
                slug_try = base_slug
            else:
                # Truncate so base+suffix fits SlugField(max_length=255) —
                # Postgres raises DataError (500) past it; SQLite won't.
                suffix = f"-{attempt + 1}"
                slug_try = f"{base_slug[:255 - len(suffix)]}{suffix}"
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
                    opening = Post(
                        topic=topic,
                        author=request.user,
                        is_opening_post=True,
                        body=ForumBodyBlock().to_python(validated["body"]),
                        live=False,
                    )
                    opening.save()
                return topic, opening
            except IntegrityError:
                continue
        raise Conflict("Could not allocate a unique slug for this topic.")


@extend_schema(
    responses={200: TopicDetailSerializer, 404: dict},
    description=(
        "Retrieve a topic's detail. Returns 404 for a non-live topic or a "
        "topic on a hidden/non-live board (no existence leak)."
    ),
)
class TopicDetailView(generics.RetrieveAPIView):
    serializer_class = TopicDetailSerializer
    versioning_class = None
    lookup_url_kwarg = "topic_id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Topic.objects.none()
        return Topic.objects.filter(
            live=True, board__in=_visible_boards()
        ).select_related("board", "author", "last_post_author")


@extend_schema(
    responses={200: PostSerializer(many=True)},
    description=(
        "List a topic's live posts, oldest first (cursor-paginated). Returns "
        "404 if the topic is non-live or on a hidden/non-live board."
    ),
)
class PostListView(generics.ListAPIView):
    serializer_class = PostSerializer
    pagination_class = PostCursorPagination
    versioning_class = None
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
        return topic.posts.filter(live=True).select_related("author", "topic")

    def list(self, request, *args, **kwargs):
        # Build the page's image map ONCE (one batched query) and feed it to the
        # serializer via context, so image-block rendition serialization never
        # fans out into a per-image lookup (the post-list query count is pinned).
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        objects = page if page is not None else queryset
        context = {
            **self.get_serializer_context(),
            "forum_image_map": build_forum_image_map(objects),
        }
        serializer = self.get_serializer(objects, many=True, context=context)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @extend_schema(
        request=ReplyCreateSerializer,
        responses={201: dict, 404: dict, 409: dict, 422: dict},
        description=(
            "Reply to a topic; the reply routes through moderation. Supports "
            "an Idempotency-Key header (a mobile retry must not create a "
            "duplicate reply)."
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
            raise Conflict("Topic is closed to replies.")
        serializer = ReplyCreateSerializer(data=request.data)
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
        remember(cache_key, result, http_status.HTTP_201_CREATED, payload_fp)
        return Response(result, status=http_status.HTTP_201_CREATED)


class PostWriteView(APIView):
    """Edit (PATCH) or soft-delete (DELETE) a single post. Author or moderator."""

    permission_classes = [IsAuthenticated]
    versioning_class = None

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

        ``None`` means allowed. ``("forbidden", None)`` → 403 (not owner/mod, no
        existence leak beyond the 404 gate); every other code carries a message
        and is a 409 state conflict (locked post / frozen topic / opening post).
        """
        if block is None:
            return
        code, message = block
        if code == "forbidden":
            raise PermissionDenied()
        raise Conflict(message)

    @extend_schema(
        request=PostEditSerializer,
        responses={200: PostSerializer, 400: dict, 403: dict, 404: dict, 409: dict},
        description=(
            "Edit a post (author or moderator). Re-screened by author trust: a "
            "trusted edit publishes immediately; an untrusted edit awaits "
            "moderation while the last-approved body keeps serving. Response is "
            "the post plus moderation_status (published|pending). 409 if the "
            "topic is closed/locked."
        ),
    )
    def patch(self, request, post_id):
        post = self._get_editable(request, post_id)
        self._enforce_writable(post.edit_block(request.user))
        serializer = PostEditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post.body = ForumBodyBlock().to_python(serializer.validated_data["body"])
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
        data = PostSerializer(
            post,
            context={
                "request": request,
                "forum_image_map": build_forum_image_map([post]),
            },
        ).data
        data["moderation_status"] = moderation_status
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
        # moderator bypass — mirrors PATCH; a delete mutating a closed/locked
        # topic's reply_count/last_post_at would desync it, finding #5) plus the
        # opening-post 409 (no topic-delete endpoint exists, finding #7).
        # PostSerializer.can_delete reads the same predicate for the client.
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
            # unpublish() fires Wagtail's `unpublished` signal -> the forum's
            # counter receivers recount reply_count/last_post_at/board/profile. Do
            # NOT recount by hand (that double-processes). user=None: forum authors
            # are not Wagtail editors, matching submit_for_moderation's publish().
            # unpublish() SAVES the row, so act on `locked` (the fresh under-lock
            # instance), never the pre-lock `post` read whose fields may be stale.
            locked.unpublish(user=None)
        return Response(status=http_status.HTTP_204_NO_CONTENT)


class PostImageUploadView(APIView):
    """Upload an inline post image (4-layer validated) into the forum collection.

    Topic-independent (Spec 2 PR-3): a new-thread composer has no topic id yet,
    and an image is scoped by collection, not topic. The body references the
    returned id via an `image` block (membership-checked in api/sanitize.py).
    """

    permission_classes = [IsAuthenticated]
    versioning_class = None
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"image": {"type": "string", "format": "binary"}},
            }
        },
        responses={201: dict, 400: dict, 401: dict},
        description=(
            "Upload an inline post image (4-layer validated: extension, MIME, "
            "size, PIL decode) into the forum image collection. Returns "
            "{id, url, alt, width, height}; reference the returned id from an "
            "`image` body block. Requires authentication."
        ),
    )
    def post(self, request):
        image_file = request.FILES.get("image")
        if image_file is None:
            raise ValidationError("No image file provided.")
        validate_image_upload(image_file)
        image = get_image_model().objects.create(
            title=(image_file.name or "forum-image")[:255],
            file=image_file,
            collection=get_forum_image_collection(),
            uploaded_by_user=request.user,
        )
        return Response(
            serialize_image_for_api(image, request),
            status=http_status.HTTP_201_CREATED,
        )


class ReactionToggleView(APIView):
    permission_classes = [IsAuthenticated]
    versioning_class = None

    @extend_schema(
        request=ReactionSerializer,
        responses={200: dict, 400: dict, 404: dict},
        description=(
            "Toggle a reaction. The response includes `reacted` (the resulting "
            "state for this user). With an Idempotency-Key header a retry "
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


class MeProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = MeProfileSerializer
    permission_classes = [IsAuthenticated]
    versioning_class = None
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        from ..models import ForumProfile

        return ForumProfile.for_user(self.request.user)


class SearchView(APIView):
    versioning_class = None
    MAX_RESULTS = (
        50  # bound the result set; a high-cardinality query won't blow up memory
    )

    @extend_schema(
        responses={200: dict},
        description="Search live topic titles and post bodies. Query param: q.",
    )
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        topics, posts = [], []
        if query:
            backend = get_search_backend()
            boards = _visible_boards()
            topic_hits = backend.search(
                query, Topic.objects.filter(live=True, board__in=boards)
            )
            for t in topic_hits[: self.MAX_RESULTS]:
                topics.append({"id": t.id, "slug": t.slug, "title": t.title})
            post_hits = backend.search(
                query,
                Post.objects.filter(
                    live=True, topic__live=True, topic__board__in=boards
                ).select_related("topic"),
            )
            for p in post_hits[: self.MAX_RESULTS]:
                posts.append(
                    {
                        "id": p.id,
                        "topic_id": p.topic_id,
                        "topic_title": p.topic.title,
                        "excerpt": p.body.render_as_block()[:200] if p.body else "",
                    }
                )
        return Response({"topics": topics, "posts": posts})


class SyncView(APIView):
    versioning_class = None
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
                    {"since": "Provide an ISO-8601 datetime with a timezone offset."}
                )
        try:
            since_id = int(request.query_params.get("since_id", 0) or 0)
        except (TypeError, ValueError):
            raise ValidationError({"since_id": "Provide an integer topic id."})

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
        # Tombstones (ids deleted since `since`) require a soft-delete log added in
        # a later plan; return an empty list for now.
        return Response(
            {
                "topics": topics,
                "deleted": [],
                "has_more": has_more,
                "next_since": batch[-1].updated_at if batch else raw_since or None,
                "next_since_id": batch[-1].id if batch else (since_id or None),
            }
        )
