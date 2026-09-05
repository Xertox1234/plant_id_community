"""Poll model behaviour: the constraint and the aggregation (todo 283 / M8)."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
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


def _poll(slug="p", options=("A", "B"), closes_at=None, max_choices=1):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    board = index.add_child(instance=ForumBoard(title="General", slug=slug))
    topic = Topic.objects.create(board=board, title="T", slug=slug)
    poll = Poll.objects.create(
        topic=topic, question="Q?", closes_at=closes_at, max_choices=max_choices
    )
    for index_, text in enumerate(options):
        PollOption.objects.create(poll=poll, text=text, order=index_)
    return poll


@pytest.mark.django_db
def test_unique_constraint_blocks_the_same_option_twice_at_the_db_level():
    """The storage-layer guarantee behind Poll.results: one row per (poll,
    user, option), so no caller — API or otherwise — can count twice for the
    same option. Since todo 349 a DIFFERENT option is a second row (a
    multi-choice ballot), and "one submission per voter" is PollVoteView's
    lock-guarded check, not this constraint."""
    poll = _poll("pm1")
    user = User.objects.create_user(username="pm1-user")
    first, second = poll.options.all()[0], poll.options.all()[1]
    PollVote.objects.create(poll=poll, option=first, user=user)

    with pytest.raises(IntegrityError), transaction.atomic():  # savepoint
        PollVote.objects.create(poll=poll, option=first, user=user)
    PollVote.objects.create(poll=poll, option=second, user=user)
    assert PollVote.objects.filter(poll=poll, user=user).count() == 2


@pytest.mark.django_db
def test_multi_choice_results_count_voters_once_but_every_option_they_picked():
    """total_votes is people who answered. In a multi-choice poll the option
    counts can sum past it — two voters picking (A, B) and (A) is A=2, B=1,
    total 2 — where the single-choice sum would say 3."""
    poll = _poll("pm-multi", options=("A", "B", "C"), max_choices=2)
    a, b, _c = poll.options.all()
    both = User.objects.create_user(username="pm-multi-both")
    one = User.objects.create_user(username="pm-multi-one")
    PollVote.objects.create(poll=poll, option=a, user=both)
    PollVote.objects.create(poll=poll, option=b, user=both)
    PollVote.objects.create(poll=poll, option=a, user=one)

    results = poll.results()

    assert [o["vote_count"] for o in results["options"]] == [2, 1, 0]
    assert results["total_votes"] == 2
    assert poll.serialize([a.id, b.id])["max_choices"] == 2


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


@pytest.mark.django_db
def test_poll_vote_clean_rejects_option_from_another_poll():
    """todo 320 #8: PollVoteView already filters `option` to `poll.options`
    before creating, so this invariant is never violated through the API —
    but nothing enforced it for any OTHER writer until now. Deliberately not
    wired into `save()` (see PollVote.clean's own comment on why); a future
    writer that wants this protection must call `clean()`/`full_clean()`
    itself, which this test proves actually rejects the mismatch."""
    poll_a = _poll("pm11a")
    poll_b = _poll("pm11b")
    user = User.objects.create_user(username="pm11-user")

    from django.core.exceptions import ValidationError

    vote = PollVote(poll=poll_a, option=poll_b.options.first(), user=user)

    with pytest.raises(ValidationError):
        vote.clean()
