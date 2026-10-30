"""Per-forum read marks and link redirects (forum-categories slices, spec
2026-10-28 §2).

- ``POST /forum/boards/{slug}/read/`` — mark one forum read (todo 671;
  phpBB's "Mark forum read"): every topic in it with no newer post reads as
  read. A ``ForumRead`` floor; per-topic reads are left as they are.
- ``POST /forum/read-all/`` — mark every forum read (phpBB's "Mark forums
  read"): advances ``ForumProfile.read_watermark_at``, which until now only
  profile creation ever wrote.
- ``GET /forum/links/{id}/go/`` — follow a link row (todo 670): counts the
  click atomically when the link is tracked, then 302s to its URL.
- ``PUT /forum/me/collapsed-categories/`` — store the categories the caller
  collapsed on the index (todo 673); read back on ``/forum/me/profile/``.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from django.db import DatabaseError
from django.db.models import DateTimeField, F, Value
from django.db.models.functions import Greatest
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Forum, ForumProfile, ForumRead
from ..models.boards import LINK_URL_SCHEMES
from .serializers import CollapsedCategoriesSerializer
from .versioning import UnversionedForumAPIMixin
from .views import _get_board, _visible_rows

try:  # Schema annotations are optional, as in views.py.
    from drf_spectacular.utils import extend_schema
except ImportError:  # pragma: no cover

    def extend_schema(**kwargs):  # type: ignore[misc]
        def decorator(fn):
            return fn

        return decorator


logger = logging.getLogger("wagtail_forum")

MARKED_SCHEMA = {
    "type": "object",
    "properties": {"marked_at": {"type": "string", "format": "date-time"}},
}


class ForumMarkReadView(UnversionedForumAPIMixin, APIView):
    """Mark one visible forum read for the caller (404 for a hidden forum,
    a category or a link, exactly as its topic list)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: MARKED_SCHEMA, 401: dict, 404: dict},
        description="Mark every topic in this forum read for the caller.",
    )
    def post(self, request, slug):
        board = _get_board(slug)
        mark = ForumRead.mark_read(request.user, board.pk)
        return Response({"marked_at": mark.marked_at})


class ForumMarkAllReadView(UnversionedForumAPIMixin, APIView):
    """Mark every forum read: advance the caller's read watermark to now
    (never backwards)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: MARKED_SCHEMA, 401: dict},
        description="Mark every topic in every forum read for the caller.",
    )
    def post(self, request):
        profile = ForumProfile.for_user(request.user)
        now = timezone.now()
        ForumProfile.objects.filter(pk=profile.pk).update(
            read_watermark_at=Greatest(
                F("read_watermark_at"), Value(now, output_field=DateTimeField())
            )
        )
        profile.refresh_from_db(fields=["read_watermark_at"])
        return Response({"marked_at": profile.read_watermark_at})


class ForumLinkGoView(UnversionedForumAPIMixin, APIView):
    """Redirect to a visible link row's URL, counting the click when the link
    is tracked. Never cached: a shared cache would swallow the count."""

    permission_classes = [AllowAny]

    @extend_schema(
        request=None,
        responses={302: None, 404: dict},
        description=(
            "Follow a link row: 302 to its URL, counting the click when the "
            "link tracks clicks. 404 for a hidden or unknown link."
        ),
    )
    def get(self, request, link_id):
        link = (
            _visible_rows(Forum.LINK)
            .filter(pk=link_id)
            .values("pk", "link_url", "track_clicks")
            .first()
        )
        # The scheme is re-checked here as well as at save: a row written
        # around the model's validation must never redirect to javascript:.
        if link is None or urlsplit(link["link_url"]).scheme not in LINK_URL_SCHEMES:
            raise NotFound()
        if link["track_clicks"]:
            # A bookkeeping write: a failed count never blocks the redirect.
            try:
                Forum.objects.filter(pk=link["pk"]).update(
                    click_count=F("click_count") + 1
                )
            except DatabaseError:
                logger.exception("[FORUM] link click count failed for %s", link["pk"])
        response = HttpResponseRedirect(link["link_url"])
        add_never_cache_headers(response)
        return response


class MeCollapsedCategoriesView(UnversionedForumAPIMixin, APIView):
    """Replace the caller's collapsed index categories (todo 673)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=CollapsedCategoriesSerializer,
        responses={200: CollapsedCategoriesSerializer, 400: dict, 401: dict},
        description=(
            "Replace the list of category ids the caller collapsed on the "
            "forum index. Read back as `collapsed_categories` on "
            "`/forum/me/profile/`."
        ),
    )
    def put(self, request):
        serializer = CollapsedCategoriesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["collapsed_categories"]
        profile = ForumProfile.for_user(request.user)
        ForumProfile.objects.filter(pk=profile.pk).update(collapsed_categories=ids)
        return Response({"collapsed_categories": ids})
