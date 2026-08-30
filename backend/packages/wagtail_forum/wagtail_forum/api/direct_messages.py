"""Private messaging (DMs) between two forum members (todo 319, audit M10).

Gated behind UserBlock (todo 284/M9) shipping first — see that todo's Notes.
Block enforcement lives here, package-side, because it is a correctness
invariant (a blocked user must never receive a delivered message, or keep
reading/writing a conversation with someone who blocked them), not a host
policy decision like rate limiting (which stays host-side, as usual).

Decisions recorded (todo 319's Work Log has the full rationale):
- Blocked send -> explicit 403, never a silent success-shaped drop.
- A blocked pair's conversation is HIDDEN from both list/detail reads too,
  symmetrically — mirrors the bidirectional send-time enforcement. Once
  either party blocks the other, neither can read or continue it.
- Spam-flagged send -> explicit 400, with the backend's real `reason`
  surfaced (never a generic message) — a provider-unavailable fail-closed
  verdict and a genuine policy violation both go through the same is_clean
  check, so the reason string is the only signal distinguishing them, and no
  package-side code should hardcode a host-only reason string to special-case
  it. No moderation queue exists for DMs (no Wagtail workflow/revision state
  on Message), so there is nothing to hold a flagged message IN for review
  the way SpamCheckTask holds a Post/Topic.
- Report-a-DM reuses the `Report` model (`Report.file_for_message`), not a
  parallel `MessageReport` model, per this todo's Recommended Action.
- No automatic retention/tombstone job. Messages persist indefinitely in this
  slice — the existing Topic tombstone-prune cron (todo 261) does not apply,
  since DMs are never hard-deleted here. Revisit once a delete/moderation
  action for DMs exists.
"""

from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import generics
from rest_framework import status as http_status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Conversation, Message, Report, UserBlock
from ..spam import get_spam_backend
from .idempotency import fingerprint, idempotency_cache_key, remember, reserve
from .pagination import ConversationCursorPagination, MessageCursorPagination
from .serializers import (
    ConversationSerializer,
    MessageSendSerializer,
    MessageSerializer,
    ReportSerializer,
)
from .versioning import UnversionedForumAPIMixin
from .views import PrivateForumReadCacheMixin, _created_location, _replay_or_none

try:  # Schema annotations are optional — hosts without drf-spectacular still work.
    from drf_spectacular.utils import extend_schema
except ImportError:  # pragma: no cover

    def extend_schema(**kwargs):
        def decorator(fn):
            return fn

        return decorator


User = get_user_model()


class _SpamCheckAdapter:
    """Shapes a plain-text DM body into the object interface
    `spam.base.extract_text` expects (a `.title` and an iterable `.body` of
    objects exposing `.value`) — Message bodies are plain text, not a
    StreamField like Post/Topic, so a bare Message can't be passed to
    `extract_text` directly (it would iterate the string's CHARACTERS).
    """

    title = ""
    is_opening_post = False

    def __init__(self, text):
        self.body = [SimpleNamespace(value=text)]


def _is_blocked_pair(user_a, user_b):
    """True if either side has blocked the other. Mirrors the bidirectional
    shape of `_drop_blocked_pairs` (apps/forum_host/notifications.py) — kept
    package-side since enforcement here is a correctness invariant, not a
    host policy choice. Accepts a User instance OR a raw pk for either side
    (Django resolves a FK filter kwarg to `_id` either way), so callers that
    already have just the other side's id don't need an extra query."""
    return UserBlock.objects.filter(
        Q(blocker=user_a, blocked=user_b) | Q(blocker=user_b, blocked=user_a)
    ).exists()


def _blocked_pair_ids(user):
    """User ids blocked-paired with `user`, either direction — the set of
    'other side' ids a conversation list must exclude."""
    return set(
        UserBlock.objects.filter(blocker=user).values_list("blocked_id", flat=True)
    ) | set(UserBlock.objects.filter(blocked=user).values_list("blocker_id", flat=True))


@extend_schema(
    responses={200: ConversationSerializer(many=True)},
    description=(
        "List the authenticated user's DM conversations, newest-created "
        "first (cursor-paginated). A conversation with a blocked pair "
        "(either direction) is excluded."
    ),
)
class ConversationListView(
    UnversionedForumAPIMixin, PrivateForumReadCacheMixin, generics.ListAPIView
):
    """My conversations, most-recently-created first. Ordered by conversation
    creation, not last-message activity — an MVP simplification; a
    last-activity ordering would need a denormalized timestamp this slice
    doesn't otherwise need."""

    serializer_class = ConversationSerializer
    pagination_class = ConversationCursorPagination
    permission_classes = [IsAuthenticated]
    filter_backends = []

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Conversation.objects.none()
        user = self.request.user
        qs = Conversation.objects.filter(
            Q(participant_a=user) | Q(participant_b=user)
        ).select_related(
            "participant_a__wagtail_forum_profile__avatar",
            "participant_b__wagtail_forum_profile__avatar",
        )
        blocked_ids = _blocked_pair_ids(user)
        if blocked_ids:
            qs = qs.exclude(participant_a_id__in=blocked_ids).exclude(
                participant_b_id__in=blocked_ids
            )
        return qs


@extend_schema(
    responses={200: MessageSerializer(many=True), 404: dict},
    description=(
        "List messages within one conversation, oldest first (cursor-"
        "paginated). 404s for a non-participant, or once either side of the "
        "conversation has blocked the other."
    ),
)
class ConversationMessagesView(
    UnversionedForumAPIMixin, PrivateForumReadCacheMixin, generics.ListAPIView
):
    """Messages within one conversation. 404s (not 403) for a non-participant
    — same existence-leak posture as `_get_visible_post`: a stranger gets no
    signal a given conversation id even exists. Also 404s once either side
    has blocked the other, symmetrically for both participants."""

    serializer_class = MessageSerializer
    pagination_class = MessageCursorPagination
    permission_classes = [IsAuthenticated]
    filter_backends = []

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Message.objects.none()
        conversation = get_object_or_404(
            Conversation, pk=self.kwargs["conversation_id"]
        )
        user = self.request.user
        if user.pk not in (
            conversation.participant_a_id,
            conversation.participant_b_id,
        ):
            raise NotFound()
        other_id = conversation.other_participant_id(user)
        if _is_blocked_pair(user.pk, other_id):
            raise NotFound()
        return conversation.messages.select_related(
            "sender__wagtail_forum_profile__avatar"
        )


class MessageSendView(UnversionedForumAPIMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=MessageSendSerializer,
        responses={
            201: MessageSerializer,
            400: dict,
            401: dict,
            403: dict,
            404: dict,
            409: dict,
            422: dict,
        },
        description=(
            "Send a private message to a user, creating the 1:1 conversation "
            "on first send. A blocked sender (either direction) gets an "
            "explicit 403 — never a success-shaped silent drop."
        ),
    )
    def post(self, request, username):
        cache_key = idempotency_cache_key(request, "message-send")
        payload_fp = (
            fingerprint({"username": username, "body": request.data})
            if cache_key
            else None
        )
        replayed = _replay_or_none(cache_key, payload_fp)
        if replayed is not None:
            return replayed

        recipient = get_object_or_404(User, username=username, is_active=True)
        if recipient.pk == request.user.pk:
            raise ValidationError({"detail": _("You cannot message yourself.")})
        if _is_blocked_pair(request.user, recipient):
            raise PermissionDenied(_("You cannot message this user."))

        serializer = MessageSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data["body"]

        spam_result = get_spam_backend().check(_SpamCheckAdapter(body))
        if not spam_result.is_clean:
            # Surface the backend's real reason (e.g. "Too many links", or an
            # LLM provider's fail-closed "unavailable" verdict) rather than a
            # generic message — a package-side view has no host-only reason
            # string to special-case against, and a flat message would
            # misleadingly present a transient provider outage as a content
            # decision (review finding, todo 319).
            #
            # Tradeoff: the default heuristic backend's reason for a banned
            # word is `f"Banned term: {word}"` (spam/heuristic.py) — echoing
            # it verbatim turns this endpoint into an oracle a sender could
            # use to enumerate SPAM_BANNED_WORDS one probe at a time. Latent
            # today (the setting defaults to []), and the post-report flow
            # already shows rejection reasons to authors, so this isn't a new
            # exposure class for the project — just something a host that
            # populates the banned list should know it's trading away.
            raise ValidationError({"detail": spam_result.reason})

        reserve(cache_key)  # 409 if a same-key twin is mid-flight (atomic add)
        with transaction.atomic():
            conversation = Conversation.between(request.user, recipient)
            message = Message.objects.create(
                conversation=conversation, sender=request.user, body=body
            )
        result = MessageSerializer(message, context={"request": request}).data
        location = _created_location(
            request, "conversation-messages", conversation_id=conversation.pk
        )
        remember(
            cache_key,
            result,
            http_status.HTTP_201_CREATED,
            payload_fp,
            headers={"Location": location},
        )
        response = Response(result, status=http_status.HTTP_201_CREATED)
        response["Location"] = location
        return response


class MessageReportView(UnversionedForumAPIMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ReportSerializer,
        responses={200: dict, 400: dict, 401: dict, 404: dict, 409: dict, 422: dict},
        description=(
            "Report a private message for moderator review. Reuses the "
            "Report model (Report.file_for_message) — same reason/detail "
            "shape as reporting a post."
        ),
    )
    def post(self, request, message_id):
        cache_key = idempotency_cache_key(request, "message-report")
        payload_fp = (
            fingerprint({"message": message_id, "body": request.data})
            if cache_key
            else None
        )
        replayed = _replay_or_none(cache_key, payload_fp)
        if replayed is not None:
            return replayed

        message = get_object_or_404(
            Message.objects.select_related("conversation"), pk=message_id
        )
        conversation = message.conversation
        if request.user.pk not in (
            conversation.participant_a_id,
            conversation.participant_b_id,
        ):
            raise NotFound()
        if message.sender_id == request.user.pk:
            raise ValidationError({"detail": _("You cannot report your own message.")})

        serializer = ReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reserve(cache_key)
        # No try/except Message.DoesNotExist here (unlike PostReportView's
        # analogous guard against a concurrent hard-delete): file_for_message
        # has no internal .get() call that could raise it — a Message is
        # never hard-deleted in this slice, so there is no race to guard.
        Report.file_for_message(message, request.user, **serializer.validated_data)
        result = {"reported": True}
        remember(cache_key, result, http_status.HTTP_200_OK, payload_fp)
        return Response(result, status=http_status.HTTP_200_OK)
