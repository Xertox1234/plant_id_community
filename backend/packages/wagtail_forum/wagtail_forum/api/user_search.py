"""User search for the @mention composer autocomplete (todo 253 slice 4, H4).

Deliberately minimal: username + display_name only, never email — this is a
new, authenticated-but-otherwise-open enumeration surface (any authenticated
user can probe usernames by prefix), so the response stays to what the
autocomplete UI needs and nothing else.
"""

from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .views import extend_schema

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


class UserMentionSearchView(APIView):
    permission_classes = [IsAuthenticated]
    versioning_class = None

    @extend_schema(
        responses={200: USER_SEARCH_SCHEMA},
        description="Search usernames by prefix, for the @mention composer autocomplete.",
    )
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response([])
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
        users = User.objects.filter(
            is_active=True, username__istartswith=query
        ).order_by("username")[:MAX_RESULTS]
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
