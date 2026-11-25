"""Forum notification fan-out is chunked at enqueue (todo 727).

Owner decision 2026-11-22: 50 recipients per batch task. A reply to a topic
with many followers used to hand every follower to ONE task per channel,
under the global 90 s / 120 s time limits. Now each channel gets one task per
``NOTIFICATION_BATCH_CHUNK_SIZE`` recipients, all under the one outbox batch
id (each task claims only its own recipients' rows), and the batch tasks
declare time limits sized to a chunk.
"""

import math

import pytest
from apps.core import constants as core_constants
from apps.core import delivery
from apps.core.models import DeliveryIntent
from apps.forum_host import constants, tasks
from django.conf import settings
from django.test import override_settings

from .test_quiet_hours_and_coalescing import (
    PUSH_ON,
    _captured,
    _member,
    _reply,
    _topic,
)

Kind = DeliveryIntent.Kind
BATCH_TASKS = {
    "send_forum_push_batch": (tasks.send_forum_push_batch, Kind.FORUM_PUSH),
    "send_forum_email_batch": (tasks.send_forum_email_batch, Kind.FORUM_EMAIL),
    "send_forum_web_push_batch": (
        tasks.send_forum_web_push_batch,
        Kind.FORUM_WEB_PUSH,
    ),
}
FOLLOWERS = 120


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_a_120_follower_reply_enqueues_one_batch_per_chunk_on_each_channel(
    django_capture_on_commit_callbacks,
):
    from apps.forum_host.notifications import dispatch

    followers = [_member(f"chunk{n:03d}") for n in range(FOLLOWERS)]
    topic, author = _topic("chunk", *followers)
    post = _reply(topic, author, "Repot into dry mix")
    expected = math.ceil(FOLLOWERS / constants.NOTIFICATION_BATCH_CHUNK_SIZE)
    assert expected == 3  # 50 per task: 50 + 50 + 20

    with _captured() as calls, django_capture_on_commit_callbacks(execute=True):
        dispatch("reply_added", topic=topic, post=post)

    follower_ids = {user.pk for user in followers}
    for name, (task, kind) in BATCH_TASKS.items():
        batches = [(args, kwargs) for called, args, kwargs in calls if called == name]
        assert len(batches) == expected, name
        chunks = [args[1] for args, _ in batches]
        assert [len(chunk) for chunk in chunks] == [50, 50, 20], name
        # Every follower is in exactly one chunk.
        flat = [pk for chunk in chunks for pk in chunk]
        assert len(flat) == len(set(flat)) == FOLLOWERS, name
        assert set(flat) == follower_ids, name
        # One outbox batch for the channel: each task claims its own rows.
        batch_ids = {kwargs.get("batch_id") for _, kwargs in batches}
        assert len(batch_ids) == 1 and None not in batch_ids, name
        rows = DeliveryIntent.objects.filter(kind=kind, batch_id=batch_ids.pop())
        assert set(rows.values_list("recipient_id", flat=True)) == follower_ids
        # Each batch task declares its own limits, sized to one chunk.
        assert task.soft_time_limit == constants.NOTIFICATION_BATCH_SOFT_TIME_LIMIT
        assert task.time_limit == constants.NOTIFICATION_BATCH_TIME_LIMIT


def test_the_batch_limits_fit_a_chunk_the_firebase_timeout_and_the_claim_lease():
    soft = constants.NOTIFICATION_BATCH_SOFT_TIME_LIMIT
    hard = constants.NOTIFICATION_BATCH_TIME_LIMIT
    # Their own, not the global per-post limits they used to inherit.
    assert soft != settings.CELERY_TASK_SOFT_TIME_LIMIT
    assert hard != settings.CELERY_TASK_TIME_LIMIT
    # One hung FCM send ends inside the soft limit, with room for more.
    assert core_constants.FIREBASE_HTTP_TIMEOUT_SECONDS * 2 <= soft < hard
    # A claim never outlives its lease while its task is still running.
    assert hard < core_constants.DELIVERY_CLAIM_LEASE_SECONDS


def test_recipient_chunks_keeps_order_and_a_small_fan_out_is_one_call():
    assert tasks.recipient_chunks([]) == []
    assert tasks.recipient_chunks([3, 1, 2]) == [[3, 1, 2]]
    size = constants.NOTIFICATION_BATCH_CHUNK_SIZE
    ids = list(range(size + 1))
    assert tasks.recipient_chunks(ids) == [ids[:size], ids[size:]]


@pytest.mark.django_db
def test_a_chunk_the_broker_refuses_does_not_stop_the_other_chunks(
    django_capture_on_commit_callbacks, caplog
):
    """Each chunk's enqueue is guarded on its own: the refused chunk is
    logged and its rows stay pending for reconciliation."""
    from unittest.mock import patch

    from apps.forum_host.notifications import dispatch

    followers = [_member(f"refuse{n:03d}") for n in range(60)]
    topic, author = _topic("refuse", *followers)
    post = _reply(topic, author, "Repot into dry mix")
    attempts: list = []

    def flaky(event, pks, payload, **kwargs):
        attempts.append(list(pks))
        if len(attempts) == 1:
            raise ConnectionError("redis://secret-host:6379 refused")

    with (
        _captured(),
        patch("apps.forum_host.tasks.send_forum_email_batch.delay", side_effect=flaky),
        django_capture_on_commit_callbacks(execute=True),
    ):
        dispatch("reply_added", topic=topic, post=post)

    assert [len(chunk) for chunk in attempts] == [50, 10]
    assert "failed to enqueue reply email batch" in caplog.text
    assert "secret-host" not in caplog.text
    pending = DeliveryIntent.objects.filter(
        kind=Kind.FORUM_EMAIL, status=DeliveryIntent.Status.PENDING
    )
    assert pending.count() == 60


@pytest.mark.django_db
def test_reconciliation_re_drives_a_big_batch_in_chunks():
    followers = [_member(f"redrive{n:03d}") for n in range(60)]
    topic, author = _topic("redrive", *followers)
    post = _reply(topic, author, "Repot into dry mix")
    payload = {"topic_id": str(topic.pk), "post_id": str(post.pk)}
    batch_id = delivery.record_batch(
        Kind.FORUM_EMAIL,
        "reply_added",
        [user.pk for user in followers],
        payload,
        subject_key=post.pk,
    )
    rows = list(DeliveryIntent.objects.filter(batch_id=batch_id))

    with _captured() as calls:
        tasks.redrive_forum_deliveries(rows)

    assert [len(args[1]) for _, args, _ in calls] == [50, 10]
    assert {kwargs["batch_id"] for _, _, kwargs in calls} == {batch_id}
