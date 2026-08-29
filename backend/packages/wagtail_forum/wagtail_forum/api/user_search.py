"""User search for the @mention composer autocomplete (todo 253 slice 4, H4).

Deliberately minimal: username + display_name only, never email — this is a
new, authenticated-but-otherwise-open enumeration surface (any authenticated
user can probe usernames by prefix), so the response stays to what the
autocomplete UI needs and nothing else.
"""

from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import UserBlock
from .versioning import UnversionedForumAPIMixin
from .views import PrivateForumReadCacheMixin, _should_filter_blocks, extend_schema

MAX_RESULTS = 10

USER_SEARCH_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "username": {"type": "string"},
            "display_name": {"type": "string"},
        },
    },
}


class UserMentionSearchView(
    UnversionedForumAPIMixin, PrivateForumReadCacheMixin, APIView
):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: USER_SEARCH_SCHEMA},
        description="Search usernames by prefix, for the @mention composer autocomplete.",
    )
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response([])
        # Not vulnerable to todo 290's RecursionError: that bug is in Wagtail's
        # search-query AND-tree construction inside `backend.search(...)`
        # (SearchView, api/views.py), which nests one level per whitespace
        # term. This view never calls the modelsearch backend — it's a plain
        # `istartswith` ORM filter on the whole query string, so term count
        # doesn't matter here.
        #
        # No manual wildcard escaping here: Django's istartswith/icontains
        # lookups already auto-escape "%"/"_"/"\" in the filter VALUE before
        # building the LIKE pattern (confirmed via .query on Django 6.0.7 —
        # `username__istartswith="dave_"` compiles to `LIKE UPPER(dave\_%)`,
        # already treating "_" as literal). Escaping it again here would
        # double-escape and break real matches (e.g. "dave_" would no longer
        # find "dave_1") — the backend CLAUDE.md's escape_search_query
        # convention predates this Django behavior and is stale for this
        # lookup type; do not copy it here.
        User = get_user_model()
        users = User.objects.filter(is_active=True, username__istartswith=query)
        # HIDE, bidirectional (todo 284/M9): neither side of a block should
        # be able to @-mention the other. Chained before [:MAX_RESULTS] —
        # excluding after a slice raises AssertionError. `pk` is never NULL
        # (it's the row's own primary key), so Exists() here needs none of
        # the Subquery-vs-Exists reasoning that applies to the nullable
        # Topic/Post author FKs elsewhere (this isn't passed to Wagtail's
        # search backend either, so no FilterFieldError risk).
        # _should_filter_blocks (not the narrower per-row helpers — this
        # isn't an author-FK filter) gates BOTH directions off for a
        # moderator: the AC requires a moderator's view be unaffected by
        # ANOTHER user's blocks too, not just their own.
        if _should_filter_blocks(request.user):
            users = users.exclude(
                Exists(
                    UserBlock.objects.filter(
                        blocker=request.user, blocked=OuterRef("pk")
                    )
                )
            ).exclude(
                Exists(
                    UserBlock.objects.filter(
                        blocker=OuterRef("pk"), blocked=request.user
                    )
                )
            )
        users = users.order_by("username")[:MAX_RESULTS]
        # get_full_name()/get_username() — not a `.display_name` property,
        # which is specific to THIS host's User model and breaks the
        # package's host-agnostic contract (mirrors serialize_forum_author's
        # display_name resolution in serializers.py).
        return Response(
            [
                {
                    "username": u.get_username(),
                    "display_name": u.get_full_name() or u.get_username(),
                }
                for u in users
            ]
        )
