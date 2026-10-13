"""The delivery outbox for forum email and browser push (todo 619).

Pins the contract written in ``apps/core/delivery.py``: a durable row per
recipient written with the event, a claim before every send, one outcome per
recipient, bounded backoff for transient failures only, reconciliation of a
lost enqueue or a dead worker, and at-least-once (never exactly-once) for a
send whose acceptance was never recorded.
"""

import smtplib
from datetime import timedelta
from unittest.mock import patch

import pytest
from apps.core import constants, delivery
from apps.core.models import DeliveryIntent
from apps.forum_host import tasks
from apps.users.models import PushSubscription
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    TopicSubscription,
)

User = get_user_model()
Status = DeliveryIntent.Status
Kind = DeliveryIntent.Kind
PUSH_ON = {
    "VAPID_PUBLIC_KEY": "BPub",
    "VAPID_PRIVATE_KEY": "priv",  # pragma: allowlist secret
    "VAPID_CLAIMS_EMAIL": "ops@example.com",
}
TASKS = "apps.forum_host.tasks"
SEND = "django.core.mail.EmailMultiAlternatives.send"


@pytest.fixture(autouse=True)
def _web_push_off_unless_asked(settings):
    """Browser push off by default, whatever the developer's .env says; the
    tests that cover it turn it on with ``override_settings(**PUSH_ON)``."""
    settings.VAPID_PUBLIC_KEY = ""


def _member(username, *, browser=True):
    user = User.objects.create_user(username=username, email=f"{username}@example.com")
    ForumProfile.for_user(user)
    if browser:
        PushSubscription.objects.create(
            user=user,
            endpoint=f"https://fcm.googleapis.com/fcm/send/{username}",
            p256dh_key="BPk-key",
            auth_key="auth-secret",  # pragma: allowlist secret
        )
    return user


def _thread(prefix, subscribers=2):
    members = [_member(f"{prefix}sub{i}") for i in range(subscribers)]
    replier = _member(f"{prefix}replier")
    index = Page.objects.get(id=1).add_child(
        instance=ForumIndex(title=f"{prefix} forum", slug=f"{prefix}-forum")
    )
    board = index.add_child(
        instance=ForumBoard(title=f"{prefix} board", slug=f"{prefix}-board")
    )
    topic = Topic.objects.create(
        board=board, title="Repotting", slug=f"{prefix}-repot", author=members[0]
    )
    for member in members:
        TopicSubscription.subscribe(member, topic)
    post = Post.objects.create(
        topic=topic,
        author=replier,
        body=[{"type": "paragraph", "value": "<p>Use a bigger pot.</p>"}],
    )
    return members, topic, post


def _dispatch_reply(capture, topic, post, *, email_delay=None, web_delay=None):
    """Dispatch a reply; returns the captured (email, web) enqueue calls."""
    from apps.forum_host.notifications import dispatch

    with (
        patch(f"{TASKS}.send_forum_push_batch.delay"),
        patch(f"{TASKS}.send_forum_email_batch.delay", **(email_delay or {})) as e,
        patch(f"{TASKS}.send_forum_web_push_batch.delay", **(web_delay or {})) as w,
        capture(execute=True),
    ):
        dispatch("reply_added", topic=topic, post=post)
    return e, w


def _run(call, task):
    task(*call.args, **call.kwargs)


def _make_due():
    DeliveryIntent.objects.filter(status=Status.PENDING).update(
        next_attempt_at=timezone.now() - timedelta(seconds=1)
    )


def _reconcile():
    """Run reconciliation with its re-enqueues captured; returns them."""
    with (
        patch(f"{TASKS}.send_forum_email_batch.delay") as email,
        patch(f"{TASKS}.send_forum_web_push_batch.delay") as web,
    ):
        totals = delivery.reconcile()
    return totals, list(email.call_args_list), list(web.call_args_list)


def _statuses(kind):
    return sorted(
        DeliveryIntent.objects.filter(kind=kind).values_list("status", flat=True)
    )


# --- durable intent + reconciliation (AC2) ---------------------------------------


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_dispatch_writes_one_row_per_recipient_and_channel(
    django_capture_on_commit_callbacks,
):
    members, topic, post = _thread("rows")

    email, web = _dispatch_reply(django_capture_on_commit_callbacks, topic, post)

    rows = DeliveryIntent.objects.all()
    assert rows.count() == 4
    assert {(r.kind, r.recipient_id) for r in rows} == {
        (kind, m.pk)
        for kind in (Kind.FORUM_EMAIL, Kind.FORUM_WEB_PUSH)
        for m in members
    }
    assert all(
        r.status == Status.PENDING and r.subject_key == str(post.pk) for r in rows
    )
    # The task is told which batch to claim; the batch is the rows'.
    assert email.call_args.kwargs["batch_id"] == str(
        rows.filter(kind=Kind.FORUM_EMAIL).first().batch_id
    )
    assert web.call_args.kwargs["batch_id"] == str(
        rows.filter(kind=Kind.FORUM_WEB_PUSH).first().batch_id
    )
    # No address, token or body in the durable payload.
    payload = rows.first().payload
    assert set(payload) == {
        "topic_id",
        "topic_title",
        "post_id",
        "actor_name",
        "actor_id",
    }


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_a_lost_enqueue_is_sent_by_reconciliation_without_another_request(
    django_capture_on_commit_callbacks,
):
    members, topic, post = _thread("lost")
    broker_down = {"side_effect": ConnectionError("broker down")}
    _dispatch_reply(
        django_capture_on_commit_callbacks,
        topic,
        post,
        email_delay=broker_down,
        web_delay=broker_down,
    )
    assert _statuses(Kind.FORUM_EMAIL) == [Status.PENDING] * 2

    # Not yet: the grace period leaves the normal path its chance.
    totals, email_calls, _ = _reconcile()
    assert totals["redriven"] == 0 and email_calls == []

    _make_due()
    totals, email_calls, web_calls = _reconcile()
    assert totals["redriven"] == 4
    [email_call] = email_calls
    with patch(
        "apps.users.services.NotificationService.send_web_push_notification",
        return_value=True,
    ) as web_send:
        _run(email_call, tasks.send_forum_email_batch)
        _run(web_calls[0], tasks.send_forum_web_push_batch)

    assert sorted(m.to[0] for m in mail.outbox) == sorted(m.email for m in members)
    assert web_send.call_count == 2
    assert _statuses(Kind.FORUM_EMAIL) == [Status.SENT] * 2
    assert _statuses(Kind.FORUM_WEB_PUSH) == [Status.SENT] * 2


@pytest.mark.django_db
def test_a_rolled_back_event_leaves_no_intent(django_capture_on_commit_callbacks):
    from apps.forum_host.notifications import dispatch
    from django.db import transaction

    members, topic, post = _thread("rollback")
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            with (
                patch(f"{TASKS}.send_forum_push_batch.delay"),
                patch(f"{TASKS}.send_forum_email_batch.delay") as email,
            ):
                dispatch("reply_added", topic=topic, post=post)
            raise RuntimeError("publish rolled back")

    assert not DeliveryIntent.objects.exists()
    email.assert_not_called()


# --- per-recipient retry, bounded (AC3) -----------------------------------------


@pytest.mark.django_db
def test_partial_batch_failure_retries_only_the_failed_recipient(
    django_capture_on_commit_callbacks,
):
    members, topic, post = _thread("partial", subscribers=3)
    email, _ = _dispatch_reply(django_capture_on_commit_callbacks, topic, post)
    failing = members[1].email
    real_send = mail.EmailMultiAlternatives.send

    def send(message, *args, **kwargs):
        if message.to == [failing]:
            raise smtplib.SMTPServerDisconnected("dropped")
        return real_send(message, *args, **kwargs)

    with patch(SEND, autospec=True, side_effect=send):
        _run(email.call_args, tasks.send_forum_email_batch)
    assert sorted(m.to[0] for m in mail.outbox) == sorted(
        [members[0].email, members[2].email]
    )
    failed_row = DeliveryIntent.objects.get(kind=Kind.FORUM_EMAIL, recipient=members[1])
    assert failed_row.status == Status.PENDING
    assert failed_row.last_error == "smtp_transient"
    assert failed_row.next_attempt_at > timezone.now()

    # Reconciliation re-drives that recipient alone, and it gets one email.
    mail.outbox.clear()
    _make_due()
    _, email_calls, _ = _reconcile()
    [retry] = email_calls
    assert retry.args[1] == [members[1].pk]
    _run(retry, tasks.send_forum_email_batch)
    assert [m.to[0] for m in mail.outbox] == [failing]
    assert _statuses(Kind.FORUM_EMAIL) == [Status.SENT] * 3


@pytest.mark.django_db
def test_transient_failures_back_off_and_stop_at_the_attempt_limit(
    django_capture_on_commit_callbacks,
):
    members, topic, post = _thread("bound", subscribers=1)
    email, _ = _dispatch_reply(django_capture_on_commit_callbacks, topic, post)
    row = DeliveryIntent.objects.get(kind=Kind.FORUM_EMAIL)
    call = email.call_args
    delays = []
    with patch(SEND, side_effect=ConnectionError("smtp down")):
        for _attempt in range(constants.DELIVERY_MAX_ATTEMPTS):
            before = timezone.now()
            _run(call, tasks.send_forum_email_batch)
            row.refresh_from_db()
            if row.status == Status.PENDING:
                delays.append(round((row.next_attempt_at - before).total_seconds()))

    assert row.status == Status.FAILED
    assert row.attempts == constants.DELIVERY_MAX_ATTEMPTS
    base = constants.DELIVERY_RETRY_BASE_SECONDS
    assert delays == [base, base * 2, base * 4, base * 8]
    # A failed row is never re-driven again.
    _make_due()
    _, email_calls, _ = _reconcile()
    assert email_calls == []


@pytest.mark.django_db
def test_a_permanent_rejection_is_not_retried(django_capture_on_commit_callbacks):
    members, topic, post = _thread("perm", subscribers=1)
    email, _ = _dispatch_reply(django_capture_on_commit_callbacks, topic, post)
    refused = smtplib.SMTPRecipientsRefused({members[0].email: (550, b"no such user")})

    with patch(SEND, side_effect=refused):
        _run(email.call_args, tasks.send_forum_email_batch)

    row = DeliveryIntent.objects.get(kind=Kind.FORUM_EMAIL)
    assert (row.status, row.last_error) == (Status.FAILED, "permanent")


@pytest.mark.django_db
def test_an_opt_out_or_missing_address_is_finished_not_retried(
    django_capture_on_commit_callbacks,
):
    members, topic, post = _thread("optout", subscribers=2)
    email, _ = _dispatch_reply(django_capture_on_commit_callbacks, topic, post)
    User.objects.filter(pk=members[0].pk).update(email_notifications=False)
    User.objects.filter(pk=members[1].pk).update(email="")

    _run(email.call_args, tasks.send_forum_email_batch)

    assert mail.outbox == []
    reasons = dict(
        DeliveryIntent.objects.filter(kind=Kind.FORUM_EMAIL).values_list(
            "recipient_id", "last_error"
        )
    )
    assert reasons == {members[0].pk: "preference_off", members[1].pk: "no_destination"}
    assert _statuses(Kind.FORUM_EMAIL) == [Status.SUPPRESSED] * 2


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_browser_push_retries_a_recipient_whose_every_browser_failed(
    django_capture_on_commit_callbacks,
):
    members, topic, post = _thread("web", subscribers=3)
    # members[2] has a second browser: one delivery is enough for them.
    PushSubscription.objects.create(
        user=members[2],
        endpoint="https://fcm.googleapis.com/fcm/send/web-second",
        p256dh_key="BPk-key",
        auth_key="auth-secret",  # pragma: allowlist secret
    )
    _, web = _dispatch_reply(django_capture_on_commit_callbacks, topic, post)
    gone = PushSubscription.objects.get(user=members[1])
    first_of_two = PushSubscription.objects.filter(user=members[2]).order_by("pk")[0]

    def send(subscription, **kwargs):
        if subscription.pk == gone.pk:
            subscription.is_active = False  # a 410: the service deactivated it
            return False
        if subscription.user_id == members[0].pk or subscription.pk == first_of_two.pk:
            return False  # transient
        return True

    with patch(
        "apps.users.services.NotificationService.send_web_push_notification",
        side_effect=send,
    ):
        _run(web.call_args, tasks.send_forum_web_push_batch)

    status = dict(
        DeliveryIntent.objects.filter(kind=Kind.FORUM_WEB_PUSH).values_list(
            "recipient_id", "status"
        )
    )
    assert status == {
        members[0].pk: Status.PENDING,  # retried with backoff
        members[1].pk: Status.FAILED,  # its only browser is gone
        members[2].pk: Status.SENT,  # reached on its second browser
    }


# --- idempotency and recovery contract (AC5) -------------------------------------


@pytest.mark.django_db
def test_a_duplicate_dispatch_records_nothing_and_sends_nothing_twice(
    django_capture_on_commit_callbacks,
):
    members, topic, post = _thread("dup")
    first, _ = _dispatch_reply(django_capture_on_commit_callbacks, topic, post)
    second, _ = _dispatch_reply(django_capture_on_commit_callbacks, topic, post)
    assert DeliveryIntent.objects.filter(kind=Kind.FORUM_EMAIL).count() == 2

    _run(first.call_args, tasks.send_forum_email_batch)
    _run(second.call_args, tasks.send_forum_email_batch)
    _run(first.call_args, tasks.send_forum_email_batch)  # a redelivered message

    assert sorted(m.to[0] for m in mail.outbox) == sorted(m.email for m in members)


@pytest.mark.django_db
def test_two_workers_cannot_claim_the_same_rows(django_capture_on_commit_callbacks):
    members, topic, post = _thread("race")
    email, _ = _dispatch_reply(django_capture_on_commit_callbacks, topic, post)
    batch_id = email.call_args.kwargs["batch_id"]
    ids = [m.pk for m in members]

    first = delivery.claim_batch(Kind.FORUM_EMAIL, batch_id, ids)
    second = delivery.claim_batch(Kind.FORUM_EMAIL, batch_id, ids)

    assert set(first) == set(ids)
    assert second == {}
    assert DeliveryIntent.objects.filter(
        kind=Kind.FORUM_EMAIL, attempts=1, status=Status.CLAIMED
    ).count() == len(ids)


@pytest.mark.django_db
def test_an_interrupted_worker_is_re_driven_after_its_lease(
    django_capture_on_commit_callbacks,
):
    """The worker claimed the batch, sent to the first recipient (provider
    accepted it) and died before recording the outcome. Inside the lease the
    rows are left alone; after it they are re-driven, and the recipient whose
    acceptance was never recorded is emailed again: the documented
    at-least-once window (apps/core/delivery.py), one recipient wide here
    because outcomes are recorded right after each send."""
    members, topic, post = _thread("crash")
    email, _ = _dispatch_reply(django_capture_on_commit_callbacks, topic, post)

    with (
        patch(f"{TASKS}._record", side_effect=[None, SystemExit("worker killed")]),
        pytest.raises(SystemExit),
    ):
        # _record #1 is the (empty) suppression write; #2 dies after send 1.
        _run(email.call_args, tasks.send_forum_email_batch)
    assert len(mail.outbox) == 1
    assert _statuses(Kind.FORUM_EMAIL) == [Status.CLAIMED] * 2

    totals, email_calls, _ = _reconcile()
    assert email_calls == []  # still inside the lease

    lease = timedelta(seconds=constants.DELIVERY_CLAIM_LEASE_SECONDS + 1)
    DeliveryIntent.objects.update(claimed_at=timezone.now() - lease)
    totals, email_calls, _ = _reconcile()
    assert totals["redriven"] == 2
    _run(email_calls[0], tasks.send_forum_email_batch)

    assert sorted(m.to[0] for m in mail.outbox) == sorted(
        [members[0].email, members[0].email, members[1].email]
    )
    assert _statuses(Kind.FORUM_EMAIL) == [Status.SENT] * 2


@pytest.mark.django_db
def test_a_lost_outcome_write_never_aborts_the_batch(
    django_capture_on_commit_callbacks,
):
    """An OperationalError recording an outcome must not raise into the task:
    it would trigger the batch's autoretry. The rest of the batch is still
    sent; the unrecorded row stays claimed for the lease to recover."""
    from django.db import OperationalError

    members, topic, post = _thread("opserr")
    email, _ = _dispatch_reply(django_capture_on_commit_callbacks, topic, post)
    real = delivery.mark_sent
    calls = []

    def flaky(pks):
        calls.append(pks)
        if len(calls) == 1:
            raise OperationalError("connection reset")
        return real(pks)

    with patch.object(delivery, "mark_sent", side_effect=flaky):
        _run(email.call_args, tasks.send_forum_email_batch)

    assert len(mail.outbox) == 2
    assert _statuses(Kind.FORUM_EMAIL) == [Status.CLAIMED, Status.SENT]


@pytest.mark.django_db
def test_old_rows_expire_and_finished_rows_are_pruned(
    django_capture_on_commit_callbacks,
):
    members, topic, post = _thread("expire")
    _dispatch_reply(django_capture_on_commit_callbacks, topic, post)
    old = timezone.now() - timedelta(seconds=constants.DELIVERY_MAX_AGE_SECONDS + 1)
    DeliveryIntent.objects.update(created_at=old)

    rows = DeliveryIntent.objects.count()
    totals, email_calls, web_calls = _reconcile()
    assert totals["expired"] == rows and email_calls == web_calls == []
    assert set(DeliveryIntent.objects.values_list("status", flat=True)) == {
        Status.FAILED
    }

    stale = timezone.now() - timedelta(days=constants.DELIVERY_RETENTION_DAYS + 1)
    DeliveryIntent.objects.update(updated_at=stale)
    totals, _, _ = _reconcile()
    assert totals["pruned"] == rows
    assert not DeliveryIntent.objects.exists()


def test_a_reconcile_beat_entry_runs_the_registered_task():
    """A typo'd beat task name is silent in prod (docs/rules/celery.md)."""
    from apps.core.tasks import reconcile_deliveries
    from celery.schedules import crontab
    from django.conf import settings

    entry = settings.CELERY_BEAT_SCHEDULE["delivery-reconcile"]
    assert entry["task"] == reconcile_deliveries.name
    assert isinstance(entry["schedule"], crontab)


# --- weekly mail recovery (AC4) --------------------------------------------------


@pytest.mark.parametrize(
    "task_path,command_output",
    [
        (
            "apps.forum_host.tasks.send_forum_weekly_digest",
            "[EMAIL] digest frequency=weekly window_days=7 recipients=3 due=3 "
            "empty=1 sent=1 failed={failed}",
        ),
        (
            "apps.blog.tasks.send_blog_weekly_newsletter",
            "[EMAIL] newsletter recipients=3 due=3 empty=1 sent=1 failed={failed} "
            "pruned=0",
        ),
    ],
)
def test_a_weekly_run_with_failures_schedules_bounded_recovery(
    task_path, command_output
):
    from django.utils.module_loading import import_string

    task = import_string(task_path)

    def run(recovery, failed):
        def fake_command(name, stdout, **kwargs):
            stdout.write(command_output.format(failed=failed) + "\n")

        with (
            patch("django.core.management.call_command", side_effect=fake_command),
            patch.object(task, "apply_async") as again,
        ):
            task.apply(kwargs={"recovery": recovery} if recovery else {})
        return again

    assert run(0, 0).call_count == 0  # nothing failed: no extra run
    first = run(0, 1)
    first.assert_called_once_with(
        kwargs={"recovery": 1}, countdown=constants.WEEKLY_RECOVERY_DELAY_SECONDS
    )
    second = run(1, 1)
    second.assert_called_once_with(
        kwargs={"recovery": 2}, countdown=constants.WEEKLY_RECOVERY_DELAY_SECONDS * 2
    )
    # Bounded: the last recovery run never schedules another.
    assert run(constants.WEEKLY_RECOVERY_MAX_RUNS, 1).call_count == 0


@pytest.mark.django_db
@override_settings(
    SITE_URL="https://forum.example",
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "todo-619-weekly-recovery",
        }
    },
)
def test_a_digest_recovery_run_retries_only_the_failed_and_rechecks_consent():
    """End to end through the real command: the first run mails A and fails
    B and D. D opts out before the recovery run. The recovery run mails B
    only: A's accepted send is not repeated and D's withdrawn consent holds.
    Nothing failed, so no further run is scheduled. (An empty digest staying
    silent is the command's own rule, pinned in the package's
    test_nothing_new_means_no_email_and_no_marker_write; a recovery run is
    that same command.)"""
    from wagtail_forum.models import DigestFrequency, Notification, NotificationVerb

    index = Page.objects.get(id=1).add_child(
        instance=ForumIndex(title="Digest", slug="digest-619")
    )
    board = index.add_child(instance=ForumBoard(title="Gen", slug="gen-619"))
    poster = User.objects.create_user(username="dg619poster")
    topic = Topic.objects.create(
        board=board, title="Monstera", slug="monstera-619", author=poster, live=True
    )
    Topic.objects.filter(pk=topic.pk).update(
        reply_count=1, last_post_at=timezone.now() - timedelta(hours=1)
    )

    def member(name):
        user = User.objects.create_user(username=name, email=f"{name}@example.com")
        profile = ForumProfile.for_user(user)
        profile.digest_frequency = DigestFrequency.WEEKLY
        profile.save(update_fields=["digest_frequency"])
        Notification.objects.create(
            recipient=user, actor=poster, verb=NotificationVerb.REPLY, topic=topic
        )
        return user

    a, b, d = member("dg619a"), member("dg619b"), member("dg619d")
    real_send = mail.EmailMultiAlternatives.send

    def first_run_send(message, *args, **kwargs):
        if message.to[0] in (b.email, d.email):
            raise ConnectionError("smtp down")
        return real_send(message, *args, **kwargs)

    with (
        patch(SEND, autospec=True, side_effect=first_run_send),
        patch.object(tasks.send_forum_weekly_digest, "apply_async") as recovery,
    ):
        tasks.send_forum_weekly_digest.apply()
    assert [m.to[0] for m in mail.outbox] == [a.email]
    recovery.assert_called_once_with(
        kwargs={"recovery": 1}, countdown=constants.WEEKLY_RECOVERY_DELAY_SECONDS
    )

    ForumProfile.objects.filter(user=d).update(digest_frequency=DigestFrequency.OFF)
    mail.outbox.clear()
    with patch.object(tasks.send_forum_weekly_digest, "apply_async") as again:
        tasks.send_forum_weekly_digest.apply(**recovery.call_args.kwargs)

    assert [m.to[0] for m in mail.outbox] == [b.email]
    again.assert_not_called()


# --- observability without bodies, tokens or addresses (AC7) ----------------------


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_failures_are_logged_and_recorded_without_addresses_or_bodies(
    django_capture_on_commit_callbacks, caplog
):
    """A refused address, a transient SMTP failure and a failed browser push:
    each is visible in the logs and on its outbox row, by pk and exception
    type, never by recipient address, post body or subscription secret."""
    members, topic, post = _thread("privacy", subscribers=2)
    email, web = _dispatch_reply(django_capture_on_commit_callbacks, topic, post)
    refused = smtplib.SMTPRecipientsRefused({members[0].email: (550, b"no such user")})
    sends = [refused, smtplib.SMTPServerDisconnected(members[1].email)]

    import logging

    # Some of these loggers do not propagate to the root (settings.LOGGING),
    # so caplog's handler is attached to each one directly.
    names = (
        "apps.core.services.email_service",
        "apps.core.services.notification_service",
        "apps.core.delivery",
        "apps.users.services",
        "forum_host.tasks",
        "forum_host.eligibility",
    )
    for name in names:
        logging.getLogger(name).addHandler(caplog.handler)
    with (
        caplog.at_level("DEBUG"),
        patch(SEND, side_effect=sends),
        patch(
            "apps.users.services.NotificationService.send_web_push_notification",
            return_value=False,
        ),
    ):
        _run(email.call_args, tasks.send_forum_email_batch)
        _run(web.call_args, tasks.send_forum_web_push_batch)
    for name in names:
        logging.getLogger(name).removeHandler(caplog.handler)

    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "send email forum_reply" in text and "SMTPRecipientsRefused" in text
    for member in members:
        assert member.email not in text
    assert "Use a bigger pot" not in text
    assert "auth-secret" not in text  # pragma: allowlist secret
    rows = DeliveryIntent.objects.values_list("last_error", "payload")
    stored = repr(list(rows))
    assert "permanent" in stored and "smtp_transient" in stored
    assert "web_push_failed" in stored
    for member in members:
        assert member.email not in stored
