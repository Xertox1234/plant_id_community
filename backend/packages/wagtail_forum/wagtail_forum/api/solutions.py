"""Mark/unmark a topic's accepted answer (audit H6, roadmap Wave 2 slice 2).

Its own module rather than another class in `views.py` for the same reason
`subscriptions.py` is: this is a self-contained topic sub-resource with one
serializer and one permission rule, and `views.py` is already 1700 lines.
"""

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Post, Topic
from ..models.posts import BLOCK_FORBIDDEN
from ..signals import notify, solution_marked
from .exceptions import UnprocessableEntity
from .idempotency import fingerprint, idempotency_cache_key, remember, reserve
from .versioning import UnversionedForumAPIMixin
from .views import _get_visible_topic, _replay_or_none, extend_schema

SOLUTION_SCHEMA = {
    "type": "object",
    "properties": {
        "is_solved": {"type": "boolean"},
        "solved_post_id": {"type": "integer", "nullable": True},
        "solved_at": {"type": "string", "format": "date-time", "nullable": True},
    },
}


class SolutionSerializer(serializers.Serializer):
    post_id = serializers.IntegerField()


def _solution_payload(topic):
    """The one response shape both handlers return, built from the topic's
    CURRENT state — so a client never has to infer `is_solved` from the status
    code, and mark/unmark responses are structurally identical."""
    return {
        "is_solved": topic.solved_post_id is not None,
        "solved_post_id": topic.solved_post_id,
        "solved_at": topic.solved_at,
    }


class TopicSolutionView(UnversionedForumAPIMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=SolutionSerializer,
        responses={
            200: SOLUTION_SCHEMA,
            400: dict,
            401: dict,
            403: dict,
            404: dict,
            409: dict,
            422: dict,
        },
        description=(
            "Accept a post as this topic's answer. The topic's author or a "
            "moderator may mark it; anyone else gets 403. The post must be a "
            "live reply on THIS topic — a post from another topic, a "
            "non-live one, or the topic's own opening post is 422. Marking is "
            "idempotent in effect (re-marking the same post re-stamps nothing "
            "new and re-sends no notification); an Idempotency-Key header "
            "additionally replays the original response, and reuse with a "
            "different payload returns 422."
        ),
    )
    def post(self, request, topic_id):
        cache_key = idempotency_cache_key(request, "topic-solution")
        payload_fp = (
            fingerprint({"topic": topic_id, "body": request.data})
            if cache_key
            else None
        )
        replayed = _replay_or_none(cache_key, payload_fp)
        if replayed is not None:
            return replayed

        # Visibility first: a hidden/restricted topic 404s before any
        # permission or validation error can confirm it exists (audit M6/M7).
        topic = _get_visible_topic(topic_id)
        self._enforce_can_mark(topic, request.user)
        serializer = SolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = self._resolve_answer(topic, serializer.validated_data["post_id"])

        reserve(cache_key)  # 409 if a same-key twin is mid-flight (atomic add)
        # Re-marking the post that is ALREADY the accepted answer must not
        # re-notify its author: `create_notifications` dedupes on (recipient,
        # verb, post), but the FCM push has no such backstop, so a client
        # double-tap would otherwise tray-popup twice. Decide before writing.
        already_accepted = topic.solved_post_id == post.pk
        topic.solved_post = post
        # Left untouched on a re-mark so `solved_at` means "when this answer was
        # accepted", not "when someone last tapped the button".
        if not already_accepted:
            topic.solved_at = timezone.now()
        # `.save(update_fields=...)` on a DraftStateMixin/RevisionMixin snippet
        # writes ONLY these columns — no revision, no workflow, no republish.
        # Accepting an answer is topic metadata, not a content edit.
        topic.save(update_fields=["solved_post", "solved_at", "updated_at"])

        if not already_accepted:
            # on_commit so a rolled-back mark can never deliver a push for a
            # solution that was not persisted (docs/rules/forum.md).
            transaction.on_commit(
                lambda: notify(
                    solution_marked,
                    sender=Topic,
                    topic=topic,
                    post=post,
                    actor=request.user,
                )
            )

        result = _solution_payload(topic)
        remember(cache_key, result, http_status.HTTP_200_OK, payload_fp)
        return Response(result, status=http_status.HTTP_200_OK)

    @extend_schema(
        responses={200: SOLUTION_SCHEMA, 401: dict, 403: dict, 404: dict},
        description=(
            "Clear this topic's accepted answer. Same permission rule as "
            "marking. Idempotent: unmarking an unsolved topic is a 200 no-op, "
            "not an error."
        ),
    )
    def delete(self, request, topic_id):
        # Visibility-gated unlike TopicSubscriptionView.delete: that one mutates
        # only the caller's OWN subscription row, so 404ing a subscriber out of
        # unsubscribing would strand them. This mutates SHARED topic state, so
        # the same no-existence-leak rule as post() applies.
        topic = _get_visible_topic(topic_id)
        self._enforce_can_mark(topic, request.user)
        if topic.solved_post_id is not None:
            topic.solved_post = None
            topic.solved_at = None
            topic.save(update_fields=["solved_post", "solved_at", "updated_at"])
        return Response(_solution_payload(topic), status=http_status.HTTP_200_OK)

    @staticmethod
    def _enforce_can_mark(topic, user):
        """403 unless *user* is the topic's author or a moderator.

        Single-sourced on `Topic.solution_block` so this guard and the
        serializer's `can_mark_solution` affordance cannot diverge (todo 252).
        The only code the block can currently return is FORBIDDEN; the explicit
        comparison keeps a future message-carrying code from silently
        collapsing into a 403 the way a bare `is not None` would.
        """
        blocked = topic.solution_block(user)
        if blocked is None:
            return
        code, message = blocked
        if code == BLOCK_FORBIDDEN:
            raise PermissionDenied(
                _("Only the topic's author or a moderator can accept an answer.")
            )
        raise UnprocessableEntity(message)

    @staticmethod
    def _resolve_answer(topic, post_id):
        """The post being accepted, or 422 explaining why it cannot be.

        422 (not 404) throughout: the topic itself is visible and the caller is
        authorized, so this is an unprocessable *body*, not a missing resource.
        `live=True` is part of the lookup — accepting a post still in the
        moderation queue would show readers a Solved badge over content they
        cannot see.
        """
        post = Post.objects.filter(id=post_id, topic=topic, live=True).first()
        if post is None:
            raise UnprocessableEntity(_("That post is not a live reply on this topic."))
        if post.is_opening_post:
            # The question is not its own answer. Without this a client could
            # mark the opening post and render a Solved badge pointing at the
            # question, which reads as answered but tells a reader nothing.
            raise UnprocessableEntity(
                _("The opening post cannot be marked as the answer.")
            )
        return post
