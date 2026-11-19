"""A forum's top contributors: who has posted most in THIS forum.

The site-wide strip is `ExpertsView` (trust level, then lifetime post count).
This is the per-forum counterpart for the topic list: ranked by live posts in
the one forum, whatever the member's trust level.
"""

from django.contrib.auth import get_user_model
from django.db.models import Count
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from ..conf import get_setting
from ..models import Post
from .versioning import UnversionedForumAPIMixin
from .views import (
    AUTHOR_SCHEMA,
    PublicForumReadCacheMixin,
    _exclude_blocked_authors,
    _get_board,
    extend_schema,
    serialize_forum_author,
)

CONTRIBUTORS_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    **AUTHOR_SCHEMA["properties"],
                    "post_count": {"type": "integer"},
                },
            },
        },
    },
}


class BoardContributorsView(
    UnversionedForumAPIMixin, PublicForumReadCacheMixin, APIView
):
    # GET-only: a public read, declared as the sibling TopicListView is.
    permission_classes = [IsAuthenticatedOrReadOnly]

    @extend_schema(
        responses={200: CONTRIBUTORS_SCHEMA, 403: dict, 404: dict},
        description=(
            "The members with the most live posts in this forum (opening "
            "posts and replies), most first, up to BOARD_CONTRIBUTORS_LIMIT. "
            "Each row is the unified author object plus `post_count`, that "
            "member's live posts in THIS forum. Deleted and deactivated "
            "accounts are left out, as are members the viewer has blocked. "
            "404 for a hidden forum, 403 `forum_locked` for a password forum "
            "the viewer has not unlocked, exactly as the topic list."
        ),
    )
    def get(self, request, slug):
        board = _get_board(slug, request)
        counted = Post.objects.filter(
            live=True,
            topic__live=True,
            topic__board=board,
            author__is_active=True,
        )
        # HIDE (todo 284/M9): directly lists users. Before the slice below:
        # .exclude() after a slice raises AssertionError.
        counted = _exclude_blocked_authors(counted, request.user)
        ranked = list(
            counted.values("author_id").annotate(post_count=Count("id"))
            # author_id breaks ties so the order is stable between requests.
            .order_by("-post_count", "author_id")[
                : get_setting("BOARD_CONTRIBUTORS_LIMIT")
            ]
        )
        # ONE query for the page's users (profile + avatar joined), not one
        # per row; `ranked` keeps the order.
        users = {
            user.pk: user
            for user in get_user_model()
            .objects.filter(pk__in=[row["author_id"] for row in ranked])
            .select_related("wagtail_forum_profile__avatar")
        }
        results = []
        for row in ranked:
            author = serialize_forum_author(users[row["author_id"]], request)
            author["post_count"] = row["post_count"]
            results.append(author)
        return Response({"results": results})
