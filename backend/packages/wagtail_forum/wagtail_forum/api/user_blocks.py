"""Block/unblock another member; list your own blocks (todo 284, audit M9).

Plain APIView/generics classes, no ViewSet/router — this package uses zero
DRF ViewSets anywhere (TopicSubscriptionView, TopicBookmarkView,
PostReportView are all the same shape); follows that idiom, not a
BlockViewSet.

Keys off username, not numeric id: no numeric user id exists anywhere in the
frontend's data model (ForumAuthor carries only username), and
PublicProfileView is already users/<str:username>/ — introducing a numeric
id just for this one button would mean threading a new field through every
author object app-wide.
"""

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import UserBlock
from .serializers import serialize_forum_author
from .versioning import UnversionedForumAPIMixin
from .views import PrivateForumReadCacheMixin, extend_schema

BLOCK_SCHEMA = {
    "type": "object",
    "properties": {"blocked": {"type": "boolean"}},
}

BLOCKED_USER_SCHEMA = {
    "type": "object",
    "properties": {
        "username": {"type": "string"},
        "display_name": {"type": "string"},
        "avatar": {"type": "string", "nullable": True},
        "trust_level": {"type": "integer", "nullable": True},
        "title": {"type": "string"},
        "blocked_at": {"type": "string", "format": "date-time"},
    },
}


class UserBlockView(UnversionedForumAPIMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: BLOCK_SCHEMA, 400: dict, 404: dict},
        description=(
            "Block a user for the authenticated member (idempotent). "
            "400 on self-block; 404 for a missing/inactive username."
        ),
    )
    def post(self, request, username):
        User = get_user_model()
        target = get_object_or_404(
            User.objects.filter(is_active=True), username=username
        )
        if not UserBlock.can_block(request.user, target):
            raise ValidationError({"detail": _("You cannot block yourself.")})
        UserBlock.block(request.user, target)
        return Response({"blocked": True})

    @extend_schema(
        responses={200: BLOCK_SCHEMA},
        description="Unblock a user for the authenticated member (idempotent).",
    )
    def delete(self, request, username):
        # Deliberately NOT existence-gated — same rationale as
        # TopicSubscriptionView.delete: mutates only the caller's own block
        # row, so let a caller remove it even if the target account was
        # since deactivated.
        UserBlock.objects.filter(
            blocker=request.user, blocked__username=username
        ).delete()
        return Response({"blocked": False})


@extend_schema(
    responses={200: {"type": "array", "items": BLOCKED_USER_SCHEMA}},
    description=(
        "List the authenticated user's blocked members, most recently "
        "blocked first. Flat, unpaginated — a personal blocklist is "
        "low-cardinality, bounded by the block/unblock write throttle."
    ),
)
class MyBlocksView(UnversionedForumAPIMixin, PrivateForumReadCacheMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        entries = (
            UserBlock.objects.filter(blocker=request.user)
            .select_related("blocked__wagtail_forum_profile__avatar")
            .order_by("-created_at")
        )
        return Response(
            [
                {
                    **serialize_forum_author(entry.blocked, request),
                    "blocked_at": entry.created_at,
                }
                for entry in entries
            ]
        )
