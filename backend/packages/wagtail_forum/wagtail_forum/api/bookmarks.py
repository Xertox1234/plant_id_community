"""Save a topic for later (todo 283, audit M2)."""

from django.db.models import OuterRef, Subquery
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Topic, TopicBookmark
from .pagination import BookmarkCursorPagination
from .serializers import TopicListSerializer
from .versioning import UnversionedForumAPIMixin
from .views import (
    PrivateForumReadCacheMixin,
    _annotate_topic_unread,
    _get_visible_topic,
    _visible_boards,
    extend_schema,
)

BOOKMARK_SCHEMA = {
    "type": "object",
    "properties": {"bookmarked": {"type": "boolean"}},
}


class TopicBookmarkView(UnversionedForumAPIMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: BOOKMARK_SCHEMA},
        description="Bookmark a topic for the authenticated user (idempotent).",
    )
    def post(self, request, topic_id):
        # Visibility-gated: bookmarking a hidden/restricted topic 404s, no
        # existence leak — same as TopicSubscriptionView.post (audit M6/M7).
        topic = _get_visible_topic(topic_id)
        TopicBookmark.bookmark(request.user, topic)
        return Response({"bookmarked": True})

    @extend_schema(
        responses={200: BOOKMARK_SCHEMA},
        description="Remove a bookmark for the authenticated user (idempotent).",
    )
    def delete(self, request, topic_id):
        # Deliberately NOT visibility-gated: mutates only the caller's own
        # bookmark row. Same rationale as TopicSubscriptionView.delete —
        # reusing _get_visible_topic here would 404 an existing bookmarker
        # out of removing their bookmark the moment the topic is
        # unpublished/restricted, stranding it bookmarked until it returns.
        TopicBookmark.objects.filter(user=request.user, topic_id=topic_id).delete()
        return Response({"bookmarked": False})


@extend_schema(
    responses={200: TopicListSerializer(many=True)},
    description=(
        "List the authenticated user's bookmarked topics, most recently "
        "bookmarked first (cursor-paginated)."
    ),
)
class TopicBookmarkListView(
    UnversionedForumAPIMixin, PrivateForumReadCacheMixin, generics.ListAPIView
):
    serializer_class = TopicListSerializer
    pagination_class = BookmarkCursorPagination
    permission_classes = [IsAuthenticated]
    filter_backends = []  # host filter-backend opt-out — see api/views.py BoardListView

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Topic.objects.none()
        user = self.request.user
        # Correlated subquery, not a second `.filter(bookmarks__user=...)` +
        # `.order_by("bookmarks__created_at")` — chaining a filter and an
        # order_by across the same multi-valued reverse relation risks a
        # second, independently-aliased JOIN in Django's ORM, which would
        # silently break the "one row per bookmarked topic" assumption. This
        # also gives the ordering a stable, uniquely-named annotation for
        # BookmarkCursorPagination's cursor to encode/decode.
        bookmarked_at = TopicBookmark.objects.filter(
            user=user, topic=OuterRef("pk")
        ).values("created_at")[:1]
        # Same visibility guard as every other content-listing endpoint — a
        # bookmarked topic that has since been unpublished/hidden must not
        # leak into the Saved list (mirrors _visible_notifications' topic
        # clause, api/notifications.py).
        qs = (
            Topic.objects.filter(
                live=True, board__in=_visible_boards(), bookmarks__user=user
            )
            .select_related(
                "author__wagtail_forum_profile__avatar",
                "last_post_author__wagtail_forum_profile__avatar",
            )
            .prefetch_related("tags")
            .annotate(bookmarked_at=Subquery(bookmarked_at))
        )
        qs = _annotate_topic_unread(qs, user)
        # Kept in sync with BookmarkCursorPagination.ordering — this is what
        # an unpaginated caller would see (mirrors TopicListView.get_queryset).
        return qs.order_by("-bookmarked_at", "-id")
