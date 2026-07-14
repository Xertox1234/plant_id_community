"""Notification list/unread-count/mark-read endpoints (todo 253 slice 1, audit C2)."""

from django.db.models import Q
from django.utils import timezone
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

try:  # Schema annotations are optional — hosts without drf-spectacular still work.
    from drf_spectacular.utils import extend_schema
except ImportError:  # pragma: no cover

    def extend_schema(**kwargs):
        def decorator(fn):
            return fn

        return decorator


from ..models import Notification
from .pagination import ForumCursorPagination
from .serializers import NotificationSerializer
from .views import _visible_boards

UNREAD_COUNT_SCHEMA = {
    "type": "object",
    "properties": {"count": {"type": "integer"}},
}
MARK_READ_SCHEMA = {
    "type": "object",
    "properties": {"updated": {"type": "integer"}},
}


def _visible_notifications(user):
    """A user's notifications, excluding ones whose topic has since been
    unpublished or hidden. A notification with no topic (a future
    non-topic-scoped verb) is never excluded by this clause — chaining
    `board__in=_visible_boards()` as a SEPARATE `.filter()` would silently
    drop null-topic rows too (a plain `__in`/lookup on a nullable FK never
    matches NULL; docs/rules/testing.md's "IN (NULL)" lesson) — it must stay
    inside the same Q as `topic__live=True`, not alongside it.

    Now includes the full `board__in=_visible_boards()` check (api/views.py)
    that gates content-listing endpoints, costing one extra query
    (`.public()`'s PageViewRestriction lookup) on every call, including this
    polled unread-count endpoint. Load-bearing since todo 253 slice 3: fan-out
    now reaches subscriber recipients beyond the topic's own author, who
    don't have slice 1's "I'm always allowed to see my own topic" standing.
    """
    return Notification.objects.filter(recipient=user).filter(
        Q(topic__isnull=True) | Q(topic__live=True, topic__board__in=_visible_boards())
    )


@extend_schema(
    responses={200: NotificationSerializer(many=True)},
    description=(
        "List the authenticated user's notifications, newest first "
        "(cursor-paginated)."
    ),
)
class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    pagination_class = ForumCursorPagination
    permission_classes = [IsAuthenticated]
    versioning_class = None
    filter_backends = []  # host filter-backend opt-out — see api/views.py BoardListView

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return _visible_notifications(self.request.user).select_related(
            "actor", "topic__board"
        )


class NotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]
    versioning_class = None

    @extend_schema(
        responses={200: UNREAD_COUNT_SCHEMA},
        description="Unread notification count for the authenticated user.",
    )
    def get(self, request):
        count = (
            _visible_notifications(request.user).filter(read_at__isnull=True).count()
        )
        return Response({"count": count})


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]
    versioning_class = None

    @extend_schema(
        request={
            "type": "object",
            "properties": {
                "ids": {"type": "array", "items": {"type": "integer"}},
            },
        },
        responses={200: MARK_READ_SCHEMA, 400: dict},
        description=(
            'Mark notifications read. Body {"ids": [...]} marks only those '
            "ids; an absent `ids` marks ALL of the user's unread "
            "notifications read; an empty list marks none. Always scoped to "
            "the requesting user — an id belonging to another user is "
            "silently excluded, never a 403/404 (no existence leak). Not "
            "topic-visibility filtered (unlike list/unread-count): marking a "
            "notification read for a since-unpublished topic leaks nothing."
        ),
    )
    def post(self, request):
        ids = request.data.get("ids")
        qs = Notification.objects.filter(recipient=request.user, read_at__isnull=True)
        if ids is not None:
            is_valid_ids = isinstance(ids, list) and all(
                isinstance(i, int) and not isinstance(i, bool) for i in ids
            )
            if not is_valid_ids:
                raise ValidationError({"ids": "Must be a list of integers."})
            qs = qs.filter(id__in=ids)
        updated = qs.update(read_at=timezone.now())
        return Response({"updated": updated})
