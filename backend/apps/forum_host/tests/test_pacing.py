"""Pacing at fan-out scale (todo 727; audit 2026-11-21 L7 and L11).

- L7: ``pacing.pace`` used to claim each recipient's fold rows with its own
  UPDATE and SELECT, about two queries a recipient. It now issues the same
  number of queries whatever the recipient count.
- L11: the pacing reads run after ``claim_batch``. An ``OperationalError``
  there used to reach the task's autoretry with the rows still claimed, so
  the retry found its own claim, did nothing, and delivery waited out the
  15-minute lease. The rows now go back to pending before the error leaves.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from apps.core import delivery
from apps.core.models import DeliveryIntent
from apps.forum_host import pacing, tasks
from django.db import OperationalError, connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from .test_quiet_hours_and_coalescing import (
    PUSH_ON,
    _channels_up,
    _member,
    _reply,
    _topic,
)

Kind = DeliveryIntent.Kind
Status = DeliveryIntent.Status
EVENT = "reply_added"


def _batch(prefix, count, kind=Kind.FORUM_EMAIL):
    """``count`` followers of one topic, each with an OLDER reply still
    pending on ``kind`` (a fold waiting) and a row for the reply being
    dispatched now. Returns (followers, payload, batch id of the new reply)."""
    followers = [_member(f"{prefix}{n:02d}") for n in range(count)]
    topic, author = _topic(prefix, *followers)
    earlier = _reply(topic, author, "First reply")
    latest = _reply(topic, author, "Second reply")
    ids = [user.pk for user in followers]
    delivery.record_batch(
        kind,
        EVENT,
        ids,
        {"topic_id": str(topic.pk), "post_id": str(earlier.pk)},
        subject_key=earlier.pk,
    )
    payload = {
        "topic_id": str(topic.pk),
        "post_id": str(latest.pk),
        "actor_id": str(author.pk),
        "actor_name": author.username,
    }
    batch_id = delivery.record_batch(kind, EVENT, ids, payload, subject_key=latest.pk)
    return followers, payload, batch_id


def _pace_queries(prefix, count):
    followers, payload, batch_id = _batch(prefix, count)
    claimed = delivery.claim_batch(
        Kind.FORUM_EMAIL, batch_id, [user.pk for user in followers]
    )
    assert len(claimed) == count
    with CaptureQueriesContext(connection) as ctx:
        paced = pacing.pace(Kind.FORUM_EMAIL, EVENT, payload, claimed, followers)
    # The work the count is taken over: every recipient is sent to now, and
    # each send folds that recipient's older pending reply.
    assert len(paced.sends) == count
    assert all(len(send.folded) == 1 for send in paced.sends)
    assert all(send.count == 2 for send in paced.sends)
    return len(ctx.captured_queries), [q["sql"] for q in ctx.captured_queries]


@pytest.mark.django_db
def test_pace_issues_the_same_number_of_queries_at_3_and_at_30_recipients():
    few, _ = _pace_queries("pacefew", 3)
    many, statements = _pace_queries("pacemany", 30)

    assert few == many, statements
    # The fold claim is ONE UPDATE for the whole batch, not one a recipient.
    claims = [sql for sql in statements if sql.startswith("UPDATE")]
    assert len(claims) == 1, claims


@pytest.mark.django_db
def test_claim_related_many_groups_each_recipients_rows_and_skips_the_excluded():
    followers, payload, batch_id = _batch("crm", 3)
    ids = [user.pk for user in followers]
    claimed = delivery.claim_batch(Kind.FORUM_EMAIL, batch_id, ids)

    folds = delivery.claim_related_many(
        Kind.FORUM_EMAIL,
        EVENT,
        ids[:2],
        payload["topic_id"],
        exclude=list(claimed.values()),
    )

    assert set(folds) == set(ids[:2])
    for pk, rows in folds.items():
        (row,) = DeliveryIntent.objects.filter(pk__in=rows)
        assert row.recipient_id == pk and row.status == Status.CLAIMED
        assert row.pk not in claimed.values()
    # The third recipient was not asked for: their older row is untouched.
    other = DeliveryIntent.objects.filter(recipient_id=ids[2]).exclude(
        pk=claimed[ids[2]]
    )
    assert [row.status for row in other] == [Status.PENDING]
    assert (
        delivery.claim_related_many(Kind.FORUM_EMAIL, EVENT, [], "1", exclude=[]) == {}
    )


BATCH_TASKS = [
    (Kind.FORUM_EMAIL, tasks.send_forum_email_batch, "l11email"),
    (Kind.FORUM_PUSH, tasks.send_forum_push_batch, "l11push"),
    (Kind.FORUM_WEB_PUSH, tasks.send_forum_web_push_batch, "l11web"),
]


@pytest.mark.django_db
@override_settings(**PUSH_ON)
@pytest.mark.parametrize(
    "kind,task,prefix", BATCH_TASKS, ids=["email", "push", "web_push"]
)
def test_an_operational_error_in_pace_after_the_claim_leaves_the_rows_pending(
    kind, task, prefix
):
    followers, payload, batch_id = _batch(prefix, 3, kind)
    ids = [user.pk for user in followers]
    mine = DeliveryIntent.objects.filter(kind=kind, batch_id=batch_id)
    claims: list = []
    real_claim = delivery.claim_batch

    def claim_then_note(*args, **kwargs):
        claimed = real_claim(*args, **kwargs)
        claims.append(dict(claimed))
        return claimed

    with (
        _channels_up() as sent,
        patch("apps.core.delivery.claim_batch", side_effect=claim_then_note),
        patch(
            "apps.forum_host.pacing.quiet_releases",
            side_effect=OperationalError("connection reset"),
        ),
        pytest.raises(OperationalError),
    ):
        task(EVENT, ids, payload, batch_id=batch_id)

    # The error really did land AFTER the claim: this run owned all three.
    assert [set(claimed) for claimed in claims] == [set(ids)]
    assert (sent.fcm, sent.web) == ([], [])
    # ...and they are handed back: pending, unclaimed, the attempt returned,
    # so the task's retry (or reconciliation) can claim them at once.
    assert {(row.status, row.claim_token, row.attempts) for row in mine} == {
        (Status.PENDING, None, 0)
    }
    assert set(real_claim(kind, batch_id, ids)) == set(ids)


@pytest.mark.django_db
def test_an_error_while_counting_folds_also_hands_back_the_fold_rows():
    followers, payload, batch_id = _batch("l11fold", 3)
    ids = [user.pk for user in followers]

    with (
        patch(
            "apps.forum_host.pacing._count_folds",
            side_effect=OperationalError("connection reset"),
        ),
        pytest.raises(OperationalError),
    ):
        tasks.send_forum_email_batch(EVENT, ids, payload, batch_id=batch_id)

    # Both the dispatched reply's rows and the older rows it had claimed to
    # fold are open again: six rows, none claimed.
    rows = DeliveryIntent.objects.filter(recipient_id__in=ids)
    assert rows.count() == 6
    assert {(row.status, row.claim_token, row.attempts) for row in rows} == {
        (Status.PENDING, None, 0)
    }


@pytest.mark.django_db
def test_a_row_already_suppressed_is_not_reopened_by_the_release():
    followers, payload, batch_id = _batch("l11supp", 3)
    gone = followers[0]
    gone.is_active = False
    gone.save(update_fields=["is_active"])
    ids = [user.pk for user in followers]

    with (
        patch(
            "apps.forum_host.pacing.quiet_releases",
            side_effect=OperationalError("connection reset"),
        ),
        pytest.raises(OperationalError),
    ):
        tasks.send_forum_email_batch(EVENT, ids, payload, batch_id=batch_id)

    mine = DeliveryIntent.objects.filter(batch_id=batch_id)
    assert mine.get(recipient=gone).status == Status.SUPPRESSED
    assert {row.status for row in mine.exclude(recipient=gone)} == {Status.PENDING}


@pytest.mark.django_db
def test_an_error_scheduling_the_fold_releases_the_sends_and_keeps_the_holds():
    """``schedule_fold``'s read runs after the holds are written: the held
    rows stay held, and only the rows about to be sent are handed back."""
    followers, payload, batch_id = _batch("l11sched", 3)
    held_user = followers[0]
    ids = [user.pk for user in followers]
    release = timezone.now() + timedelta(minutes=5)
    real_pace = pacing.pace

    def pace_with_a_hold(kind, event, data, claimed, users, **kwargs):
        paced = real_pace(kind, event, data, claimed, users, **kwargs)
        (held,) = [send for send in paced.sends if send.user.pk == held_user.pk]
        paced.sends.remove(held)
        delivery.release(list(held.folded))
        paced.held[(release, delivery.HOLD_COALESCING)].append(held.row)
        return paced

    with (
        patch("apps.forum_host.pacing.pace", side_effect=pace_with_a_hold),
        patch(
            "apps.forum_host.pacing._another_fold_waits",
            side_effect=OperationalError("connection reset"),
        ),
        pytest.raises(OperationalError),
    ):
        tasks.send_forum_email_batch(EVENT, ids, payload, batch_id=batch_id)

    mine = DeliveryIntent.objects.filter(batch_id=batch_id)
    held_row = mine.get(recipient=held_user)
    assert (held_row.status, held_row.last_error, held_row.next_attempt_at) == (
        Status.PENDING,
        delivery.HOLD_COALESCING,
        release,
    )
    others = DeliveryIntent.objects.filter(recipient_id__in=ids[1:])
    assert others.count() == 4
    assert {(row.status, row.claim_token, row.attempts) for row in others} == {
        (Status.PENDING, None, 0)
    }
