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

from datetime import datetime
from datetime import timezone as dt_timezone
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Case, Count, Exists, F, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import generics
from rest_framework import status as http_status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..conf import get_setting
from ..models import Conversation, ForumProfile, Message, Report, UserBlock
from ..spam import get_spam_backend
from ..spam.heuristic import HeuristicSpamBackend
from .idempotency import fingerprint, idempotency_cache_key, remember, reserve
from .notifications import UNREAD_COUNT_SCHEMA
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


def _screen_dm_body(sender, text):
    """Screen a DM body, trust-routing the CONFIGURED backend the way
    ``workflow.py::_route_revision_by_trust`` trust-routes moderation.

    Trust gates only the CONFIGURED backend. A trusted sender falls back to the
    package's built-in heuristic (link flood, banned words) rather than skipping
    screening altogether the way the post path does — that pass is cheap,
    offline, and dropping it would trade one problem for a worse one. Untrusted
    senders reach ``get_spam_backend()`` exactly as they did before this gate,
    so their floor is whatever that backend applies: both backends shipped in
    this repo provide it (``HeuristicSpamBackend`` *is* it; the host's
    ``LLMSpamBackend`` is heuristic-first), but a third-party host that
    configures a non-chaining backend screens its untrusted senders with that
    backend alone. That is the package's existing contract, unchanged here.

    The configured backend is the gated one because on this path it is the
    expensive and failure-prone one:

    - It is the only screening surface with NO trust gate. A Post reaches the
      configured backend solely when its author is untrusted; before this gate
      a DM reached it for every sender at every trust level, so an LLM backend
      put a synchronous, billable provider call on every message an
      established member sent.
    - Fail-closed costs more here than anywhere else. A flagged Post becomes a
      pending draft a moderator can still publish; a Message has no
      revision/workflow state to hold (see this module's docstring), so the
      same verdict REJECTS the send outright and the text is gone. Spending
      that on a trusted sender because a provider timed out is the worst
      trade on this path.

    Untrusted senders — the actual DM-spam risk, and the same population the
    post path screens — still get the full configured backend.
    """
    profile = ForumProfile.for_user(sender)
    if profile.trust_level >= get_setting("TRUST_AUTOPUBLISH_LEVEL"):
        backend = HeuristicSpamBackend()
    else:
        backend = get_spam_backend()
    return backend.check(_SpamCheckAdapter(text))


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


# "Never read" compares as "everything is newer than the epoch" so the Exists
# subquery below needs no NULL branch.
_EPOCH = datetime(1970, 1, 1, tzinfo=dt_timezone.utc)


def _my_read_at(user):
    """This side's read marker as an expression (the row's a/b column)."""
    return Case(
        When(participant_a=user, then=F("participant_a_read_at")),
        default=F("participant_b_read_at"),
    )


def _my_conversations(user):
    """`user`'s conversations minus blocked pairs — no annotations, no
    joins; the base both readers build on."""
    qs = Conversation.objects.filter(Q(participant_a=user) | Q(participant_b=user))
    blocked_ids = _blocked_pair_ids(user)
    if blocked_ids:
        qs = qs.exclude(participant_a_id__in=blocked_ids).exclude(
            participant_b_id__in=blocked_ids
        )
    return qs


def _unread_conversation_count(user):
    """Conversations with at least one unread message — the badge number.
    Deliberately NOT `_inbox_queryset`: a poll (120/m per user) must not pay
    for avatar joins, preview subqueries and a GROUP BY it throws away. One
    EXISTS per row, one COUNT query (review finding, todo 339)."""
    newer_from_other_side = (
        Message.objects.filter(conversation=OuterRef("pk"))
        .exclude(sender=user)
        .filter(created_at__gt=Coalesce(OuterRef("my_read_at"), Value(_EPOCH)))
    )
    return (
        _my_conversations(user)
        .annotate(my_read_at=_my_read_at(user))
        .annotate(has_unread=Exists(newer_from_other_side))
        .filter(has_unread=True)
        .count()
    )


def _inbox_queryset(user):
    """`user`'s visible conversations with the inbox annotations the
    ConversationSerializer reads (todo 339): `my_read_at` (this side's read
    marker), `unread_count` (messages from the other side newer than it),
    `last_message_body` / `last_message_sender_id` (newest message, via
    correlated subqueries). One query per page; blocked pairs excluded."""
    newest = Message.objects.filter(conversation=OuterRef("pk")).order_by(
        "-created_at", "-id"
    )
    return (
        _my_conversations(user)
        .select_related(
            "participant_a__wagtail_forum_profile__avatar",
            "participant_b__wagtail_forum_profile__avatar",
        )
        .annotate(my_read_at=_my_read_at(user))
        .annotate(
            unread_count=Count(
                "messages",
                filter=~Q(messages__sender=user)
                & (
                    Q(my_read_at__isnull=True)
                    | Q(messages__created_at__gt=F("my_read_at"))
                ),
            ),
            last_message_body=Subquery(newest.values("body")[:1]),
            last_message_sender_id=Subquery(newest.values("sender_id")[:1]),
        )
    )


@extend_schema(
    responses={200: ConversationSerializer(many=True)},
    description=(
        "List the authenticated user's DM conversations — the inbox: most "
        "recent activity first (cursor-paginated), each row carrying "
        "`unread_count` and a `last_message` preview. A conversation with a "
        "blocked pair (either direction) is excluded."
    ),
)
class ConversationListView(
    UnversionedForumAPIMixin, PrivateForumReadCacheMixin, generics.ListAPIView
):
    """My inbox: conversations by last activity (todo 339 replaced the
    original created-at ordering once a client existed to need an inbox),
    annotated with unread state and a preview — see `_inbox_queryset`."""

    serializer_class = ConversationSerializer
    pagination_class = ConversationCursorPagination
    permission_classes = [IsAuthenticated]
    filter_backends = []

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Conversation.objects.none()
        return _inbox_queryset(self.request.user)


@extend_schema(
    responses={200: UNREAD_COUNT_SCHEMA},
    description=(
        "Number of the authenticated user's conversations with unread "
        "messages (not the message count) — the inbox badge. Same `{count}` "
        "shape as notifications/unread-count/."
    ),
)
class ConversationUnreadCountView(
    UnversionedForumAPIMixin, PrivateForumReadCacheMixin, APIView
):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"count": _unread_conversation_count(request.user)})


@extend_schema(
    responses={200: ConversationSerializer, 404: dict},
    description=(
        "The authenticated user's conversation with `username`, or 404 when "
        "none exists yet (send a message to start one), when the user is "
        "unknown, or once either side has blocked the other. Lets a profile's "
        "'Message' action open the existing thread without listing the inbox."
    ),
)
class ConversationWithUserView(
    UnversionedForumAPIMixin, PrivateForumReadCacheMixin, APIView
):
    permission_classes = [IsAuthenticated]

    def get(self, request, username):
        other = get_object_or_404(User, username=username, is_active=True)
        if other.pk == request.user.pk:
            raise NotFound()
        conversation = (
            _inbox_queryset(request.user)
            .filter(Q(participant_a=other) | Q(participant_b=other))
            .first()
        )
        if conversation is None:
            raise NotFound()
        return Response(
            ConversationSerializer(conversation, context={"request": request}).data
        )


@extend_schema(
    responses={200: MessageSerializer(many=True), 404: dict},
    description=(
        "List messages within one conversation, NEWEST first (cursor-"
        "paginated; page older with the cursor). Reading any page marks the "
        "conversation read for the caller. 404s for a non-participant, or "
        "once either side of the conversation has blocked the other."
    ),
)
class ConversationMessagesView(
    UnversionedForumAPIMixin, PrivateForumReadCacheMixin, generics.ListAPIView
):
    """Messages within one conversation, newest first. 404s (not 403) for a
    non-participant — same existence-leak posture as `_get_visible_post`: a
    stranger gets no signal a given conversation id even exists. Also 404s
    once either side has blocked the other, symmetrically for both
    participants. A successful read advances the caller's read marker (todo
    339): opening the thread IS reading it, like the topic-read record on
    topic detail — the marker is `now`, so a message landing in the same
    instant counts as seen; acceptable at forum scale."""

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
        self._conversation = conversation
        return conversation.messages.select_related(
            "sender__wagtail_forum_profile__avatar"
        )

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        # Only reached after get_queryset resolved (and authorized) the
        # conversation — a 404 above never marks anything.
        self._conversation.mark_read(request.user)
        return response


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

        spam_result = _screen_dm_body(request.user, body)
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
            # Inbox bookkeeping (todo 339): the activity timestamp orders the
            # inbox. Sending does NOT touch the sender's read marker — only
            # reading does (ConversationMessagesView) — so a reply sent from a
            # profile without opening the thread leaves the other side's
            # earlier messages unread; own messages never count anyway.
            Conversation.objects.filter(pk=conversation.pk).update(
                last_message_at=message.created_at
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
