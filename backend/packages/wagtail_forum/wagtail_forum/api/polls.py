"""Cast a vote in a topic's poll (todo 283, audit M8; N-of-K since todo 349).

Voting is the only poll mutation the API exposes. A poll is created with its
topic (TopicCreateSerializer) and never edited: changing a question or an
option after votes exist silently rewrites what those votes meant.

**A vote is one final submission.** For a single-choice poll that is one
option; for a multi-choice poll (``Poll.max_choices > 1``) it is 1..N options
sent together. Either way a second submission is REJECTED with 409, never
replaced or merged — the todo-283 product decision (results are hidden until
you vote, so a change-vote would let a voter peek and then re-decide) carried
over unchanged to multi-choice rather than adopting Discourse's change-vote.
The todo-349 Work Log records the decision and its revisit trigger.
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
from .serializers import MAX_POLL_OPTION_LIST_ITEMS, POLL_SCHEMA, _BoundedListField
from .versioning import UnversionedForumAPIMixin
from .views import _get_visible_topic, extend_schema


class _BoundedBallotListField(_BoundedListField):
    # A ballot can never legitimately exceed the option count, and the create
    # path already refuses more than MAX_POLL_OPTION_LIST_ITEMS raw options
    # before per-item parsing — the same ceiling here, so an oversized array
    # is refused before IntegerField runs on every element (docs/rules/api.md:
    # bound it before you parse it).
    max_items = MAX_POLL_OPTION_LIST_ITEMS
    too_many_message = _("Too many options in one ballot.")


class PollVoteSerializer(serializers.Serializer):
    """The whole write shape: which option(s).

    ``option_ids`` is the contract (todo 349); ``option_id`` is accepted as
    the one-element form so a single-choice client keeps working. Exactly one
    of the two must be present, and the normalized ``option_ids`` list is what
    the view reads.

    Note what is NOT here — any kind of count. Results are aggregated from
    PollVote rows on read (Poll.results), so a caller supplying `vote_count`
    or `total_votes` has those fields silently ignored by DRF and cannot
    influence the numbers. Pinned by test_forged_vote_count_is_ignored.
    """

    option_id = serializers.IntegerField(required=False)
    option_ids = _BoundedBallotListField(
        child=serializers.IntegerField(), required=False, allow_empty=False
    )

    def validate(self, attrs):
        has_one = "option_id" in attrs
        has_many = "option_ids" in attrs
        if has_one and has_many:
            raise ValidationError(
                {"option_ids": [_("Send either option_id or option_ids, not both.")]}
            )
        if not has_one and not has_many:
            raise ValidationError({"option_ids": [_("Choose at least one option.")]})
        option_ids = [attrs["option_id"]] if has_one else attrs["option_ids"]
        if len(set(option_ids)) != len(option_ids):
            raise ValidationError(
                {"option_ids": [_("Each option may be chosen at most once.")]}
            )
        return {"option_ids": option_ids}


class PollVoteView(UnversionedForumAPIMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PollVoteSerializer,
        responses={200: POLL_SCHEMA},
        description=(
            "Cast this user's vote in the topic's poll and return the poll with "
            "freshly computed results. Send `option_ids` (1..max_choices option "
            "ids of this poll; `option_id` is accepted as the single form). A "
            "vote is ONE final submission per user per poll: a second submission "
            "is REJECTED with 409 (the response names the existing choice), not "
            "replaced. 409 also when the poll has closed; 400 for more options "
            "than max_choices, a repeated option, or an option of another poll."
        ),
    )
    def post(self, request, topic_id):
        # Visibility-gated: voting in a hidden/restricted topic's poll 404s,
        # no existence leak (audit M6/M7).
        topic = _get_visible_topic(topic_id)
        serializer = PollVoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        option_ids = serializer.validated_data["option_ids"]

        poll = Poll.objects.filter(topic=topic).first()
        if poll is None:
            raise NotFound(_("This topic has no poll."))
        if poll.is_closed:
            raise Conflict(_("This poll has closed."))
        if len(option_ids) > poll.max_choices:
            raise ValidationError(
                {
                    "option_ids": [
                        _("This poll allows at most %(n)d choice(s).")
                        % {"n": poll.max_choices}
                    ]
                }
            )

        # Every option must belong to THIS poll — without this check a caller
        # could pass any option id in the table and have their vote land on
        # another topic's poll (the unique constraint is on (poll, user,
        # option), so nothing else would stop it).
        options = list(poll.options.filter(id__in=option_ids))
        if len(options) != len(option_ids):
            raise ValidationError({"option_ids": [_("Unknown option for this poll.")]})

        # Fast path, OUTSIDE the lock: the common re-click of an already-
        # committed ballot is refused without touching the poll row. The
        # locked re-check below is the guarantee; this is only the cheap
        # answer (and what test_locked_recheck_refuses_a_ballot_the_fast_path_
        # missed monkeypatches to miss once).
        existing = _existing_ballot(poll, request.user)
        if existing:
            raise Conflict(_already_voted_message(existing))

        try:
            # One transaction for the whole ballot, its OWN savepoint if
            # something ever wraps this view (ATOMIC_REQUESTS is False today;
            # catching an IntegrityError inside an ambient atomic() without
            # one poisons the connection — docs/rules, forum). The per-poll
            # row lock serializes submissions to this poll, so two ballots
            # racing past the fast path above queue on the lock and the
            # second one's re-read here sees the first's committed rows.
            with transaction.atomic():
                Poll.objects.select_for_update().get(pk=poll.pk)
                existing = _existing_ballot(poll, request.user)
                if existing:
                    raise Conflict(_already_voted_message(existing))
                PollVote.objects.bulk_create(
                    [
                        PollVote(poll=poll, option=option, user=request.user)
                        for option in options
                    ]
                )
        except IntegrityError:
            # uniq_poll_vote_option is the last line under the lock: reached
            # only if a writer that bypassed this view (admin, a migration)
            # left a matching row. Same answer as the checked path.
            raise Conflict(_("You have already voted in this poll."))

        # The ids just written ARE this user's vote — Poll.serialize takes
        # them straight rather than re-querying PollVote for what this
        # request already knows (todo 320 #3/#4). Sorted by id, the same
        # order TopicDetailSerializer.get_poll reads the ballot back in, so
        # the two payloads stay byte-identical even once options can be
        # reordered (review of todo 349).
        return Response(poll.serialize(sorted(option.id for option in options)))


def _existing_ballot(poll: Poll, user) -> list[int]:
    """This user's recorded option ids for ``poll``, sorted — empty if they
    have not voted. Module-level (not inlined twice) so the deterministic
    interleaving test can make the fast-path read miss once."""
    return list(
        PollVote.objects.filter(poll=poll, user=user)
        .order_by("option_id")
        .values_list("option_id", flat=True)
    )


def _already_voted_message(existing_option_ids: list[int]) -> str:
    # Report the existing choice(s) so the client can render "you voted X"
    # instead of a bare error, and so a double-submitted request is
    # indistinguishable from a deliberate re-vote at the UI level.
    if len(existing_option_ids) == 1:
        return _("You have already voted for option %(id)d in this poll.") % {
            "id": existing_option_ids[0]
        }
    return _("You have already voted for options %(ids)s in this poll.") % {
        "ids": ", ".join(str(i) for i in existing_option_ids)
    }
