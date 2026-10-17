"""The delivery outbox's hold primitives (todo 624): ``mark_held``,
``release`` and ``claim_related``, tested directly rather than only through
the pacing integration tests (review round 2, PR #1132)."""

import datetime

import pytest
from apps.core import delivery
from apps.core.models import DeliveryIntent
from django.contrib.auth import get_user_model
from django.utils import timezone

Kind = DeliveryIntent.Kind
Status = DeliveryIntent.Status


def _row(user, *, topic="1", post=1, event="reply_added", kind=Kind.FORUM_PUSH):
    delivery.record_batch(kind, event, [user.pk], {"topic_id": topic}, subject_key=post)
    return DeliveryIntent.objects.get(
        kind=kind, event=event, recipient=user, subject_key=str(post)
    )


@pytest.fixture
def users(db):
    User = get_user_model()
    return [User.objects.create_user(username=f"holds{i}") for i in range(2)]


def test_mark_held_returns_the_attempt_and_never_goes_below_zero(users):
    row = _row(users[0])
    claimed = delivery.claim_one(intent_id=row.pk)
    assert claimed.attempts == 1
    release_at = timezone.now() + datetime.timedelta(hours=3)

    assert delivery.mark_held([row.pk], release_at, delivery.HOLD_COALESCING) == 1
    row.refresh_from_db()
    assert (row.status, row.attempts, row.last_error, row.claim_token) == (
        Status.PENDING,
        0,
        delivery.HOLD_COALESCING,
        None,
    )
    assert row.next_attempt_at == release_at
    # Holding an unclaimed row again cannot push attempts negative.
    delivery.mark_held([row.pk], release_at)
    row.refresh_from_db()
    assert (row.attempts, row.last_error) == (0, delivery.HOLD_QUIET_HOURS)
    assert delivery.mark_held([], release_at) == 0


def test_release_hands_a_claim_back_untouched(users):
    row = _row(users[0])
    due = row.next_attempt_at
    delivery.claim_one(intent_id=row.pk)

    assert delivery.release([row.pk]) == 1
    row.refresh_from_db()
    assert (row.status, row.attempts, row.claim_token, row.next_attempt_at) == (
        Status.PENDING,
        0,
        None,
        due,
    )
    delivery.release([row.pk])
    row.refresh_from_db()
    assert row.attempts == 0


def test_claim_related_takes_only_that_member_topic_kind_and_event(users):
    me, other = users
    dispatched = _row(me, post=1)
    sibling = _row(me, post=2)
    _row(me, post=3, topic="2")  # another topic
    _row(other, post=4)  # another member
    _row(me, post=5, kind=Kind.FORUM_EMAIL)  # another channel
    _row(me, post=6, event="mention")  # another event
    finished = _row(me, post=7)
    delivery.mark_sent([finished.pk])

    folded = delivery.claim_related(
        Kind.FORUM_PUSH, "reply_added", me.pk, "1", exclude=[dispatched.pk]
    )

    assert folded == {sibling.pk: "2"}
    sibling.refresh_from_db()
    assert sibling.status == Status.CLAIMED
    # Already claimed: a second fold gets nothing.
    assert (
        delivery.claim_related(
            Kind.FORUM_PUSH, "reply_added", me.pk, "1", exclude=[dispatched.pk]
        )
        == {}
    )
