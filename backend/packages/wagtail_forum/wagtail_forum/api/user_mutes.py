"""Mute/unmute another member; list your own mutes (todo 347).

Mirrors ``api/user_blocks.py`` exactly (plain APIView, username-keyed,
idempotent, flat unpaginated list) — a mute is the one-directional, content-
only sibling of a block, so the write surface is the same shape with a
different verb. What differs is what the row DOES, and that lives in the
shared filtering sites (``views._annotate_author_blocked`` /
``_exclude_blocked_authors``, ``forum_host/notifications.py``), not here.
"""

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import UserMute
from .serializers import serialize_forum_author
from .versioning import UnversionedForumAPIMixin
from .views import PrivateForumReadCacheMixin, extend_schema

MUTE_SCHEMA = {
    "type": "object",
    "properties": {"muted": {"type": "boolean"}},
}

MUTED_USER_SCHEMA = {
    "type": "object",
    "properties": {
        "username": {"type": "string"},
        "display_name": {"type": "string"},
        "avatar": {"type": "string", "nullable": True},
        "trust_level": {"type": "integer", "nullable": True},
        "title": {"type": "string"},
        "muted_at": {"type": "string", "format": "date-time"},
    },
}


class UserMuteView(UnversionedForumAPIMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: MUTE_SCHEMA, 400: dict, 404: dict},
        description=(
            "Mute a user for the authenticated member (idempotent): their "
            "topics, posts and notifications stop reaching you; nothing changes "
            "for them, and their messages still arrive. 400 on self-mute; 404 "
            "for a missing/inactive username."
        ),
    )
    def post(self, request, username):
        User = get_user_model()
        target = get_object_or_404(
            User.objects.filter(is_active=True), username=username
        )
        if not UserMute.can_mute(request.user, target):
            raise ValidationError({"detail": _("You cannot mute yourself.")})
        UserMute.mute(request.user, target)
        return Response({"muted": True})

    @extend_schema(
        responses={200: MUTE_SCHEMA},
        description="Unmute a user for the authenticated member (idempotent).",
    )
    def delete(self, request, username):
        # Not existence-gated, like UserBlockView.delete: mutates only the
        # caller's own row, so a deactivated target can still be unmuted.
        UserMute.objects.filter(muter=request.user, muted__username=username).delete()
        return Response({"muted": False})


@extend_schema(
    responses={200: {"type": "array", "items": MUTED_USER_SCHEMA}},
    description=(
        "List the authenticated user's muted members, most recently muted "
        "first. Flat, unpaginated — a personal mute list is low-cardinality, "
        "bounded by the mute/unmute write throttle."
    ),
)
class MyMutesView(UnversionedForumAPIMixin, PrivateForumReadCacheMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        entries = (
            UserMute.objects.filter(muter=request.user)
            .select_related("muted__wagtail_forum_profile__avatar")
            .order_by("-created_at")
        )
        return Response(
            [
                {
                    **serialize_forum_author(entry.muted, request),
                    "muted_at": entry.created_at,
                }
                for entry in entries
            ]
        )
