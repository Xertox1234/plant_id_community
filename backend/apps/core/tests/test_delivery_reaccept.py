"""``delivery.record_reaccept`` (todo 652; owner decision 2026-10-16), tested
directly rather than only through the accepted-answer dispatch (review round
2, PR #1141): the first record, in-flight dedup, the cooldown, and a reopen
that reconciliation re-drives instead of expiring."""

import datetime
from unittest.mock import patch

import pytest
from apps.core import constants, delivery
from apps.core.models import DeliveryIntent
from django.contrib.auth import get_user_model
from django.utils import timezone

Kind = DeliveryIntent.Kind
Status = DeliveryIntent.Status
EVENT = "answer_accepted"


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="reaccept")


def _reaccept(user):
    return delivery.record_reaccept(
        Kind.FORUM_EMAIL, EVENT, user.pk, {"topic_id": "1"}, subject_key=7
    )


def _row(user):
    return DeliveryIntent.objects.get(kind=Kind.FORUM_EMAIL, recipient=user)


def _finish_a_day_ago(user):
    then = timezone.now() - datetime.timedelta(
        seconds=constants.FORUM_REACCEPT_COOLDOWN_SECONDS + 60
    )
    DeliveryIntent.objects.filter(recipient=user).update(
        status=Status.SENT, created_at=then, updated_at=then
    )


def test_the_first_acceptance_records_one_pending_row(user):
    batch = _reaccept(user)

    row = _row(user)
    assert (row.status, str(row.batch_id)) == (Status.PENDING, batch)


@pytest.mark.parametrize("status", [Status.PENDING, Status.CLAIMED])
def test_a_row_in_flight_dedups_and_is_never_reopened(user, status):
    first = _reaccept(user)
    DeliveryIntent.objects.filter(recipient=user).update(status=status)

    again = _reaccept(user)

    assert again not in (first, delivery.REACCEPT_COOLING)
    row = _row(user)
    assert (row.status, str(row.batch_id)) == (status, first)


def test_a_finished_row_inside_the_cooldown_stays_quiet(user):
    _reaccept(user)
    DeliveryIntent.objects.filter(recipient=user).update(status=Status.SENT)

    assert _reaccept(user) == delivery.REACCEPT_COOLING
    assert _row(user).status == Status.SENT


def test_a_finished_row_past_the_cooldown_reopens_under_a_new_batch(user):
    first = _reaccept(user)
    _finish_a_day_ago(user)

    batch = _reaccept(user)

    row = _row(user)
    assert batch not in (first, delivery.REACCEPT_COOLING)
    assert (row.status, str(row.batch_id), row.attempts) == (
        Status.PENDING,
        batch,
        0,
    )
    # Measured from the reopen: an immediate second toggle is cooling.
    assert row.created_at > timezone.now() - datetime.timedelta(minutes=1)
    DeliveryIntent.objects.filter(recipient=user).update(status=Status.SENT)
    assert _reaccept(user) == delivery.REACCEPT_COOLING


def test_a_reopened_row_whose_enqueue_was_lost_is_redriven_not_expired(user):
    _reaccept(user)
    _finish_a_day_ago(user)
    _reaccept(user)
    DeliveryIntent.objects.filter(recipient=user).update(
        next_attempt_at=timezone.now() - datetime.timedelta(seconds=1)
    )

    with patch("apps.forum_host.tasks.redrive_forum_deliveries") as redrive:
        totals = delivery.reconcile()

    assert totals["expired"] == 0
    assert [r.pk for r in redrive.call_args.args[0]] == [_row(user).pk]
    assert _row(user).status == Status.PENDING
