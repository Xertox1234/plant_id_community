"""Poll model behaviour: the constraint and the aggregation (todo 283 / M8)."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    Poll,
    PollOption,
    PollVote,
    Topic,
)

User = get_user_model()


def _poll(slug="p", options=("A", "B"), closes_at=None):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    board = index.add_child(instance=ForumBoard(title="General", slug=slug))
    topic = Topic.objects.create(board=board, title="T", slug=slug)
    poll = Poll.objects.create(topic=topic, question="Q?", closes_at=closes_at)
    for index_, text in enumerate(options):
        PollOption.objects.create(poll=poll, text=text, order=index_)
    return poll


@pytest.mark.django_db
def test_unique_constraint_blocks_a_second_vote_at_the_db_level():
    """AC 4 at the storage layer. This is what makes Poll.results trustworthy
    without a stored counter: the row count IS the answer, and no caller — API
    or otherwise — can inflate it."""
    poll = _poll("pm1")
    user = User.objects.create_user(username="pm1-user")
    first, second = poll.options.all()[0], poll.options.all()[1]
    PollVote.objects.create(poll=poll, option=first, user=user)

    # Even switching to a DIFFERENT option is blocked — the constraint is on
    # (poll, user), not (poll, user, option).
    with pytest.raises(IntegrityError):
        PollVote.objects.create(poll=poll, option=second, user=user)


@pytest.mark.django_db
def test_different_users_may_both_vote_for_the_same_option():
    poll = _poll("pm2")
    option = poll.options.first()
    for name in ("pm2-a", "pm2-b"):
        PollVote.objects.create(
            poll=poll, option=option, user=User.objects.create_user(username=name)
        )

    assert PollVote.objects.filter(poll=poll).count() == 2


@pytest.mark.django_db
def test_results_aggregate_from_rows_with_no_stored_counter():
    poll = _poll("pm3", options=("A", "B", "C"))
    a, b, _c = poll.options.all()
    for i in range(3):
        PollVote.objects.create(
            poll=poll, option=a, user=User.objects.create_user(username=f"pm3-a{i}")
        )
    PollVote.objects.create(
        poll=poll, option=b, user=User.objects.create_user(username="pm3-b0")
    )

    results = poll.results()

    assert [o["vote_count"] for o in results["options"]] == [3, 1, 0]
    assert results["total_votes"] == 4
    # There is no counter column to drift out of sync with the rows.
    assert not hasattr(PollOption, "vote_count")


@pytest.mark.django_db
def test_results_of_a_poll_with_no_votes():
    poll = _poll("pm4")

    results = poll.results()

    assert results["total_votes"] == 0
    assert [o["vote_count"] for o in results["options"]] == [0, 0]


@pytest.mark.django_db
def test_deleting_a_vote_lowers_the_count_immediately():
    """Aggregation, not a counter — so a removed row needs no compensating
    write to stay correct."""
    poll = _poll("pm5")
    user = User.objects.create_user(username="pm5-user")
    vote = PollVote.objects.create(poll=poll, option=poll.options.first(), user=user)
    assert poll.results()["total_votes"] == 1

    vote.delete()

    assert poll.results()["total_votes"] == 0


@pytest.mark.django_db
def test_deleting_a_user_removes_their_vote_and_lowers_the_count():
    poll = _poll("pm6")
    user = User.objects.create_user(username="pm6-user")
    PollVote.objects.create(poll=poll, option=poll.options.first(), user=user)

    user.delete()

    assert not PollVote.objects.exists()
    assert poll.results()["total_votes"] == 0


@pytest.mark.django_db
def test_is_closed_is_false_when_closes_at_is_null():
    assert _poll("pm7").is_closed is False


@pytest.mark.django_db
def test_is_closed_flips_at_the_close_time():
    future = _poll("pm8", closes_at=timezone.now() + timedelta(minutes=1))
    past = _poll("pm9", closes_at=timezone.now() - timedelta(minutes=1))

    assert future.is_closed is False
    assert past.is_closed is True


@pytest.mark.django_db
def test_one_poll_per_topic():
    poll = _poll("pm10")

    with pytest.raises(IntegrityError):
        Poll.objects.create(topic=poll.topic, question="Second?")
