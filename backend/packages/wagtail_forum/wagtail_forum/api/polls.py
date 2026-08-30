"""Cast a vote in a topic's poll (todo 283, audit M8).

Voting is the only poll mutation the API exposes. A poll is created with its
topic (TopicCreateSerializer) and never edited: changing a question or an
option after votes exist silently rewrites what those votes meant.
"""

from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Poll, PollVote
from .exceptions import Conflict
from .serializers import POLL_SCHEMA
from .versioning import UnversionedForumAPIMixin
from .views import _get_visible_topic, extend_schema


class PollVoteSerializer(serializers.Serializer):
    """The whole write shape: one option id.

    Note what is NOT here — any kind of count. Results are aggregated from
    PollVote rows on read (Poll.results), so a caller supplying `vote_count`
    or `total_votes` has those fields silently ignored by DRF and cannot
    influence the numbers. Pinned by test_forged_vote_count_is_ignored.
    """

    option_id = serializers.IntegerField()


class PollVoteView(UnversionedForumAPIMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PollVoteSerializer,
        responses={200: POLL_SCHEMA},
        description=(
            "Cast this user's vote in the topic's poll and return the poll with "
            "freshly computed results. One vote per user per poll: a second vote "
            "is REJECTED with 409 (the response names the existing choice), not "
            "silently replaced. 409 also when the poll has closed."
        ),
    )
    def post(self, request, topic_id):
        # Visibility-gated: voting in a hidden/restricted topic's poll 404s,
        # no existence leak (audit M6/M7).
        topic = _get_visible_topic(topic_id)
        serializer = PollVoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        poll = Poll.objects.filter(topic=topic).first()
        if poll is None:
            raise NotFound(_("This topic has no poll."))
        if poll.is_closed:
            raise Conflict(_("This poll has closed."))

        # The option must belong to THIS poll — without this check a caller
        # could pass any option id in the table and have their vote land on
        # another topic's poll (the unique constraint is on (poll, user), so
        # nothing else would stop it).
        option = poll.options.filter(id=serializer.validated_data["option_id"]).first()
        if option is None:
            raise ValidationError({"option_id": [_("Unknown option for this poll.")]})

        try:
            # The INSERT gets its OWN savepoint. Catching an IntegrityError
            # inside an ambient atomic() without one poisons the connection —
            # every later query in the request then raises
            # TransactionManagementError (docs/rules, forum). Nothing wraps
            # this view today (ATOMIC_REQUESTS is False), but the savepoint is
            # what makes that stay true if something ever does.
            with transaction.atomic():
                PollVote.objects.create(poll=poll, option=option, user=request.user)
        except IntegrityError:
            # uniq_poll_vote fired: this user already voted. Deliberately a
            # rejection rather than a replace — see the todo-283 Work Log for
            # the reasoning and the revisit trigger. Report the existing
            # choice so the client can render "you voted X" instead of a bare
            # error, and so a double-submitted request is indistinguishable
            # from a deliberate re-vote at the UI level.
            existing = (
                PollVote.objects.filter(poll=poll, user=request.user)
                .values_list("option_id", flat=True)
                .first()
            )
            raise Conflict(
                _("You have already voted in this poll.")
                if existing is None
                else _("You have already voted for option %(id)d in this poll.")
                % {"id": existing}
            )

        # `option.id` IS the just-recorded vote — Poll.serialize takes it
        # straight rather than re-querying PollVote for what this request
        # already knows (todo 320 #3/#4; was also hand-duplicating
        # TopicDetailSerializer.get_poll's shape here before the shared
        # `Poll.serialize` method existed).
        return Response(poll.serialize(option.id))
