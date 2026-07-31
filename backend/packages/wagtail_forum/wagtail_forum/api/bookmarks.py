"""Save-for-later bookmarks: toggle on a topic, plus the member's saved list.

Todo 283 / audit M2. Shaped to mirror `api/subscriptions.py` — same toggle
verbs, same visibility asymmetry between POST and DELETE — because the two are
adjacent affordances on the same thread header and a client should not have to
learn two conventions.
"""

from django.db.models import OuterRef, Subquery
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Topic, TopicBookmark
from .pagination import BookmarkCursorPagination
from .serializers import BookmarkedTopicSerializer
from .versioning import UnversionedForumAPIMixin
from .views import (
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
        description="Save a topic to the authenticated user's bookmarks (idempotent).",
    )
    def post(self, request, topic_id):
        # Visibility-gated: bookmarking a hidden/restricted topic 404s, no
        # existence leak (audit M6/M7) — same guard as TopicSubscriptionView.post.
        topic = _get_visible_topic(topic_id)
        TopicBookmark.add(request.user, topic)
        return Response({"bookmarked": True})

    @extend_schema(
        responses={200: BOOKMARK_SCHEMA},
        description="Remove a topic from the authenticated user's bookmarks "
        "(idempotent).",
    )
    def delete(self, request, topic_id):
        # Deliberately NOT visibility-gated — the same reasoning that governs
        # TopicSubscriptionView.delete. This mutates only the caller's own row,
        # so there is no existence-leak risk; reusing _get_visible_topic would
        # 404 a member out of un-saving the moment their topic is unpublished
        # or restricted, stranding a dead entry in their saved list forever.
        TopicBookmark.objects.filter(user=request.user, topic_id=topic_id).delete()
        return Response({"bookmarked": False})


class MeBookmarkListView(UnversionedForumAPIMixin, generics.ListAPIView):
    """The authenticated member's saved topics, newest-saved first.

    Serves `BookmarkedTopicSerializer` — the board-list row shape plus a
    per-row `board`, which this list needs because it spans many boards at
    once (see that serializer for why it is a subclass, not a widening of
    TopicListSerializer). The shared base is exactly why `get_queryset` cannot
    be hand-rolled: `is_unread` is a plain `BooleanField(read_only=True)` that
    assumes `_annotate_topic_unread` has run — and DRF SKIPS such a field
    silently when its attribute is missing, so the key would just vanish from
    every row rather than erroring — while `get_tags` reads `obj.tags.all()`
    (one query per row without the prefetch). Both are replicated below,
    along with the author `select_related` chain.
    """

    serializer_class = BookmarkedTopicSerializer
    pagination_class = BookmarkCursorPagination
    permission_classes = [IsAuthenticated]
    # Host filter-backend opt-out: a global OrderingFilter would let any client
    # `?ordering=` replace the cursor paginator's ordering (audit Phase 6 R1).
    filter_backends = []

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Topic.objects.none()
        user = self.request.user
        qs = (
            Topic.objects.filter(
                bookmarks__user=user,
                # Visibility-gated like every other topic read: a topic hidden
                # or moved to a restricted board AFTER it was bookmarked must
                # drop out of the saved list, not leak its title and author
                # through it. The bookmark row survives, so it reappears if the
                # topic comes back.
                live=True,
                board__in=_visible_boards(),
            )
            .select_related(
                # The saved list spans many boards, so every row carries its
                # own — joined here so BookmarkedTopicSerializer.get_board
                # costs no per-row query.
                "board",
                "author__wagtail_forum_profile__avatar",
                "last_post_author__wagtail_forum_profile__avatar",
            )
            .prefetch_related("tags")
            .annotate(
                # The paginator orders on this. A correlated subquery rather
                # than `F("bookmarks__created_at")`: the filter above already
                # joins `bookmarks`, but Django is free to allocate a SECOND
                # join for an annotation over a multi-valued relation, which
                # would multiply rows. The subquery folds into the same SELECT.
                bookmarked_at=Subquery(
                    TopicBookmark.objects.filter(
                        user=user, topic=OuterRef("pk")
                    ).values("created_at")[:1]
                )
            )
        )
        # NOT optional. `is_unread` is a plain read-only BooleanField on the
        # inherited TopicListSerializer, and DRF SKIPS such a field silently
        # when its attribute is missing — so without this the key simply
        # vanishes from every row, with no error anywhere. Pinned by
        # test_me_bookmarks_rows_carry_is_unread.
        return _annotate_topic_unread(qs, user)

    @extend_schema(
        description="List the authenticated user's bookmarked topics, "
        "newest-saved first. Topics that are no longer visible to the caller "
        "are omitted.",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
