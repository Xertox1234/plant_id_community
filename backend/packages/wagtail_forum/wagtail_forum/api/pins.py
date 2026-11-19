"""Pin/unpin a topic to the top of its forum from the API.

A pinned topic already sorts first in every list (`TopicCursorPagination`)
and carries `is_pinned`; until now the flag could only be set in the Wagtail
admin. Its own module for the same reason `solutions.py` is: one topic
sub-resource with one permission rule.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import status as http_status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .versioning import UnversionedForumAPIMixin
from .views import _get_visible_topic, extend_schema

PIN_SCHEMA = {
    "type": "object",
    "properties": {"is_pinned": {"type": "boolean"}},
}


class TopicPinView(UnversionedForumAPIMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: PIN_SCHEMA, 401: dict, 403: dict, 404: dict},
        description=(
            "Pin this topic to the top of its forum. Moderators only; anyone "
            "else gets 403. Idempotent: pinning a pinned topic is a 200 no-op."
        ),
    )
    def post(self, request, topic_id):
        return self._set(request, topic_id, True)

    @extend_schema(
        responses={200: PIN_SCHEMA, 401: dict, 403: dict, 404: dict},
        description=(
            "Unpin this topic. Same permission rule as pinning. Idempotent: "
            "unpinning a topic that is not pinned is a 200 no-op."
        ),
    )
    def delete(self, request, topic_id):
        return self._set(request, topic_id, False)

    @staticmethod
    def _set(request, topic_id, pinned):
        # Visibility first: a hidden/restricted topic 404s before the
        # permission error can confirm it exists (audit M6/M7).
        topic = _get_visible_topic(topic_id, request)
        if not topic.can_pin_by(request.user):
            raise PermissionDenied(_("Only a moderator can pin a topic."))
        if topic.is_pinned != pinned:
            topic.is_pinned = pinned
            # `update_fields` on a DraftStateMixin/RevisionMixin snippet writes
            # only these columns: no revision, no workflow, no republish. A pin
            # is topic metadata, not a content edit (as in `solutions.py`).
            topic.save(update_fields=["is_pinned", "updated_at"])
        return Response({"is_pinned": topic.is_pinned}, status=http_status.HTTP_200_OK)
