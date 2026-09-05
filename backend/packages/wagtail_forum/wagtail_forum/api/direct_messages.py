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
from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q, Subquery, Value
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
from ..models import (
    Conversation,
    ConversationKind,
    ConversationParticipant,
    ForumProfile,
    Message,
    Report,
    UserBlock,
)
from ..spam import get_spam_backend
from ..spam.heuristic import HeuristicSpamBackend
from .idempotency import fingerprint, idempotency_cache_key, remember, reserve
from .notifications import UNREAD_COUNT_SCHEMA
from .pagination import ConversationCursorPagination, MessageCursorPagination
from .serializers import (
    ConversationSerializer,
    GroupConversationCreateSerializer,
    MessageSendSerializer,
    MessageSerializer,
    ParticipantAddSerializer,
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
    """My read marker as an expression — my participant row's `read_at`
    (todo 350 moved it off the pair columns so groups share the model)."""
    return Subquery(
        ConversationParticipant.objects.filter(
            conversation=OuterRef("pk"), user=user
        ).values("read_at")[:1]
    )


def _my_conversations(user, blocked_ids=None):
    """`user`'s conversations — every kind, via the participant rows (an
    EXISTS, no join to multiply rows) — minus blocked DIRECT pairs. Block
    policy for groups (todo 350, recorded): a group stays visible to both
    sides (you cannot un-see a room you are in), the blocked member's
    messages are filtered out of MY reads, and sending into a group that
    contains anyone block-paired with me is refused."""
    qs = Conversation.objects.filter(
        Exists(
            ConversationParticipant.objects.filter(
                conversation=OuterRef("pk"), user=user
            )
        )
    )
    blocked_ids = _blocked_pair_ids(user) if blocked_ids is None else blocked_ids
    if blocked_ids:
        qs = qs.exclude(
            kind=ConversationKind.DIRECT, participant_a_id__in=blocked_ids
        ).exclude(kind=ConversationKind.DIRECT, participant_b_id__in=blocked_ids)
    return qs


def _visible_messages(conversation, user, blocked_ids=None):
    """The messages `user` may read in `conversation`: everything, minus a
    blocked member's messages inside a group."""
    qs = conversation.messages.all()
    if conversation.is_group:
        blocked_ids = _blocked_pair_ids(user) if blocked_ids is None else blocked_ids
        if blocked_ids:
            qs = qs.exclude(sender_id__in=blocked_ids)
    return qs


def _unread_conversation_count(user):
    """Conversations with at least one unread message — the badge number.
    Deliberately NOT `_inbox_queryset`: a poll (120/m per user) must not pay
    for avatar joins, preview subqueries and a GROUP BY it throws away. One
    EXISTS per row, one COUNT query (review finding, todo 339)."""
    blocked_ids = _blocked_pair_ids(user)
    newer_from_other_side = (
        Message.objects.filter(conversation=OuterRef("pk"))
        .exclude(sender=user)
        .filter(created_at__gt=Coalesce(OuterRef("my_read_at"), Value(_EPOCH)))
    )
    if blocked_ids:
        # A blocked member's group messages are never unread to me.
        newer_from_other_side = newer_from_other_side.exclude(sender_id__in=blocked_ids)
    return (
        _my_conversations(user, blocked_ids)
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
    blocked_ids = _blocked_pair_ids(user)
    newest = Message.objects.filter(conversation=OuterRef("pk")).order_by(
        "-created_at", "-id"
    )
    unread_filter = ~Q(messages__sender=user) & (
        Q(my_read_at__isnull=True) | Q(messages__created_at__gt=F("my_read_at"))
    )
    if blocked_ids:
        # Group rows: a blocked member's messages neither preview nor count.
        newest = newest.exclude(sender_id__in=blocked_ids)
        unread_filter &= ~Q(messages__sender_id__in=blocked_ids)
    return (
        _my_conversations(user, blocked_ids)
        .select_related(
            "participant_a__wagtail_forum_profile__avatar",
            "participant_b__wagtail_forum_profile__avatar",
            "created_by__wagtail_forum_profile__avatar",
        )
        .prefetch_related(
            Prefetch(
                "participants",
                queryset=ConversationParticipant.objects.select_related(
                    "user__wagtail_forum_profile__avatar"
                ),
            )
        )
        .annotate(my_read_at=_my_read_at(user))
        .annotate(
            unread_count=Count("messages", filter=unread_filter),
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
        request=GroupConversationCreateSerializer,
        responses={
            201: ConversationSerializer,
            400: dict,
            401: dict,
            409: dict,
            422: dict,
        },
        description=(
            "Create a titled GROUP conversation with 2–7 other members and its "
            "first message (a conversation only exists once a message was sent, "
            "like a direct thread). Every member must be an active user not "
            "block-paired with the caller — one generic 400 covers the missing, "
            "inactive and blocked cases. Honours Idempotency-Key."
        ),
    )
    def post(self, request):
        cache_key = idempotency_cache_key(request, "group-create")
        payload_fp = fingerprint({"body": request.data}) if cache_key else None
        replayed = _replay_or_none(cache_key, payload_fp)
        if replayed is not None:
            return replayed
        serializer = GroupConversationCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        title = serializer.validated_data["title"]
        body = serializer.validated_data["body"]
        members = _resolve_addable_members(
            request.user, serializer.validated_data["usernames"]
        )
        spam_result = _screen_dm_body(request.user, body)
        if not spam_result.is_clean:
            raise ValidationError({"detail": spam_result.reason})
        reserve(cache_key)
        with transaction.atomic():
            conversation = Conversation.create_group(request.user, title, members)
            message = Message.objects.create(
                conversation=conversation, sender=request.user, body=body
            )
            Conversation.objects.filter(pk=conversation.pk).update(
                last_message_at=message.created_at
            )
        row = _inbox_queryset(request.user).get(pk=conversation.pk)
        result = ConversationSerializer(row, context={"request": request}).data
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


def _resolve_addable_members(user, usernames):
    """The users `user` may put in a group with them: active, not `user`,
    deduped, none block-paired with `user`, and within the cap INCLUDING the
    caller. One generic 400 for every rejection — the endpoint must not be
    an oracle for who exists or who blocked whom (todo 350). Errors are
    raised under `detail`, like every other one-off message in this module:
    the envelope flattener (todo 320) prefixes a field key into the client's
    `message` ("usernames: …"), which the clients render verbatim (react
    review)."""
    wanted = []
    for name in usernames:
        if name not in wanted and name != user.get_username():
            wanted.append(name)
    max_members = get_setting("DM_GROUP_MAX_PARTICIPANTS")
    if len(wanted) < 2:
        raise ValidationError(
            {"detail": _("A group needs at least two other members.")}
        )
    if len(wanted) + 1 > max_members:
        raise ValidationError(
            {
                "detail": _("A group may have at most %(n)d members.")
                % {"n": max_members}
            }
        )
    found = list(User.objects.filter(username__in=wanted, is_active=True))
    blocked_ids = _blocked_pair_ids(user)
    if len(found) != len(wanted) or any(u.pk in blocked_ids for u in found):
        raise ValidationError({"detail": _("One of the members cannot be added.")})
    return found


def _send_to_conversation(request, conversation, cache_key, payload_fp):
    """Shared send step for the by-id endpoint: participant + block checks,
    spam screen, persist, bump activity, remember the idempotent result."""
    user = request.user
    if not conversation.is_participant(user):
        raise NotFound()
    blocked_ids = _blocked_pair_ids(user)
    if conversation.is_group:
        if blocked_ids & conversation.participant_ids():
            # Conservative policy (todo 350): any block pair in the room
            # refuses the send — explicit 403, never a silent drop.
            raise PermissionDenied(_("You cannot message this group."))
    elif conversation.other_participant_id(user) in blocked_ids:
        raise PermissionDenied(_("You cannot message this user."))
    serializer = MessageSendSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    body = serializer.validated_data["body"]
    spam_result = _screen_dm_body(user, body)
    if not spam_result.is_clean:
        raise ValidationError({"detail": spam_result.reason})
    reserve(cache_key)
    with transaction.atomic():
        message = Message.objects.create(
            conversation=conversation, sender=user, body=body
        )
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
            .filter(kind=ConversationKind.DIRECT)
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
        # Direct threads keep the zero-query membership check on the loaded
        # pair; only a group needs the participant table (cross-cutting review).
        if conversation.is_group:
            if not conversation.is_participant(user):
                raise NotFound()
        elif user.pk not in (
            conversation.participant_a_id,
            conversation.participant_b_id,
        ):
            raise NotFound()
        elif _is_blocked_pair(user.pk, conversation.other_participant_id(user)):
            raise NotFound()
        self._conversation = conversation
        return _visible_messages(conversation, user).select_related(
            "sender__wagtail_forum_profile__avatar"
        )

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        # Only reached after get_queryset resolved (and authorized) the
        # conversation — a 404 above never marks anything.
        self._conversation.mark_read(request.user)
        return response

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
            "Send a message into a conversation by id — a direct thread or a "
            "group (todo 350). 404 for a non-participant; 403 when the sender is "
            "block-paired with the other side (direct) or with ANY member "
            "(group); spam-flagged bodies are a 400 with the reason. Honours "
            "Idempotency-Key."
        ),
    )
    def post(self, request, conversation_id):
        cache_key = idempotency_cache_key(request, "conversation-send")
        payload_fp = (
            fingerprint({"conversation": conversation_id, "body": request.data})
            if cache_key
            else None
        )
        replayed = _replay_or_none(cache_key, payload_fp)
        if replayed is not None:
            return replayed
        conversation = get_object_or_404(Conversation, pk=conversation_id)
        return _send_to_conversation(request, conversation, cache_key, payload_fp)


@extend_schema(
    responses={200: ConversationSerializer, 401: dict, 404: dict},
    description=(
        "One conversation row (the same shape as the inbox list) by id — a "
        "direct thread or a group. 404 for a non-participant, a removed member, "
        "or a blocked direct pair, exactly like the messages endpoint (todo 350: "
        "lets a client open a group it was just created into or deep-linked to "
        "without walking the inbox)."
    ),
)
class ConversationDetailView(
    UnversionedForumAPIMixin, PrivateForumReadCacheMixin, APIView
):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        row = _inbox_queryset(request.user).filter(pk=conversation_id).first()
        if row is None:
            raise NotFound()
        return Response(ConversationSerializer(row, context={"request": request}).data)


def _get_group_for_manage(request, conversation_id):
    """The group `request.user` belongs to, or 404 — a direct thread and a
    stranger's group look identical from outside (no existence leak)."""
    conversation = get_object_or_404(Conversation, pk=conversation_id)
    if not conversation.is_group or not conversation.is_participant(request.user):
        raise NotFound()
    return conversation


class ConversationParticipantsView(UnversionedForumAPIMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ParticipantAddSerializer,
        responses={
            200: ConversationSerializer,
            400: dict,
            401: dict,
            403: dict,
            404: dict,
        },
        description=(
            "Add a member to a group (creator only — 403 otherwise; 404 for a "
            "direct thread or a group the caller is not in). Same member rules "
            "as creation (cap, active, not block-paired — one generic 400). "
            "Adding an existing member is a no-op 200. Returns the inbox row."
        ),
    )
    def post(self, request, conversation_id):
        conversation = _get_group_for_manage(request, conversation_id)
        if conversation.created_by_id != request.user.pk:
            raise PermissionDenied(_("Only the group's creator can add members."))
        serializer = ParticipantAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        current = conversation.participant_ids()
        already = User.objects.filter(username=username, pk__in=current).exists()
        if username != request.user.get_username() and not already:
            max_members = get_setting("DM_GROUP_MAX_PARTICIPANTS")
            if len(current) + 1 > max_members:
                raise ValidationError(
                    {
                        "detail": _("A group may have at most %(n)d members.")
                        % {"n": max_members}
                    }
                )
            member = User.objects.filter(username=username, is_active=True).first()
            if member is None or member.pk in _blocked_pair_ids(request.user):
                raise ValidationError(
                    {"detail": _("One of the members cannot be added.")}
                )
            ConversationParticipant.objects.get_or_create(
                conversation=conversation, user=member
            )
        row = _inbox_queryset(request.user).get(pk=conversation.pk)
        return Response(ConversationSerializer(row, context={"request": request}).data)


class ConversationParticipantView(UnversionedForumAPIMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={204: None, 400: dict, 401: dict, 403: dict, 404: dict},
        description=(
            "Remove a member from a group. Any member may remove THEMSELVES "
            "(leave); the creator may remove others; the creator cannot leave "
            "while others remain (400 — v1 has no ownership transfer). 404 for "
            "a direct thread, a group the caller is not in, or a non-member."
        ),
    )
    def delete(self, request, conversation_id, username):
        conversation = _get_group_for_manage(request, conversation_id)
        target = get_object_or_404(User, username=username)
        if not conversation.is_participant(target):
            raise NotFound()
        is_self = target.pk == request.user.pk
        is_creator = conversation.created_by_id == request.user.pk
        if is_self and is_creator and conversation.participants.count() > 1:
            raise ValidationError({"detail": _("Transfer or close the group first.")})
        if not is_self and not is_creator:
            raise PermissionDenied(_("Only the group's creator can remove members."))
        with transaction.atomic():
            ConversationParticipant.objects.filter(
                conversation=conversation, user=target
            ).delete()
            # The last member leaving would strand a room nobody can ever
            # reach again (django review): a memberless group is deleted with
            # its messages rather than orphaned.
            if not conversation.participants.exists():
                conversation.delete()
        return Response(status=http_status.HTTP_204_NO_CONTENT)


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
        if not conversation.is_participant(request.user):
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
