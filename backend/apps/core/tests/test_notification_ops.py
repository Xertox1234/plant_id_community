"""Notification outcomes and operational alerts (todo 623).

AC1: every live email and push path reports the same send-side outcomes
(``notification_ops.Outcome``), and provider acceptance stays distinct from
delivery (provider evidence only) and from engagement (a click).

AC4: broker refusals, an outbox that is not draining, exhausted retries,
missing push configuration and missed beat runs each raise a Sentry alert
(an ERROR log, which Sentry's logging integration turns into an event, or a
Cron Monitor check-in), with no secret or address in it.
"""

import json
import logging
from datetime import timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
import sentry_sdk
from apps.core import constants, delivery, notification_ops
from apps.core.models import DeliveryIntent, EmailClick, EmailNotification
from apps.core.notification_ops import Outcome
from apps.core.services.email_service import EmailOutcome, EmailService, EmailType
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from kombu.exceptions import OperationalError as KombuOperationalError
from plant_community_backend.sentry_config import sentry_integrations

User = get_user_model()
Kind = DeliveryIntent.Kind
Status = DeliveryIntent.Status

# Fake values that must never appear in a log line or a Sentry event.
SECRET_BROKER_URL = (
    "redis://:fake-broker-password@broker.internal:6379/1"  # pragma: allowlist secret
)
ADDRESS = "reader@example.com"
DEVICE_TOKEN = "fake-device-token-abc123"


@pytest.fixture
def logs(caplog):
    """caplog for the ``apps`` logger tree too (it does not propagate)."""
    apps_logger = logging.getLogger("apps")
    apps_logger.addHandler(caplog.handler)
    caplog.set_level(logging.INFO)
    cache.clear()
    notification_ops._LAST_ALERT.clear()
    try:
        yield caplog
    finally:
        apps_logger.removeHandler(caplog.handler)
        cache.clear()


def _errors(caplog):
    return [r for r in caplog.records if r.levelno >= logging.ERROR]


def _outcome_lines(caplog):
    return [r.getMessage() for r in caplog.records if "[OUTCOME]" in r.getMessage()]


@pytest.fixture
def users(db):
    return [
        User.objects.create_user(username=f"ops{i}", email=f"ops{i}@example.com")
        for i in range(3)
    ]


def _row(user, *, kind=Kind.FORUM_EMAIL, post=1):
    delivery.record_batch(kind, "reply_added", [user.pk], {}, subject_key=post)
    return DeliveryIntent.objects.get(kind=kind, recipient=user, subject_key=str(post))


def _outcome(row):
    row.refresh_from_db()
    return notification_ops.outcome_of_intent(row.status, row.attempts, row.last_error)


# ---------------------------------------------------------------------------
# AC1: one vocabulary across every send path
# ---------------------------------------------------------------------------


class TestOutboxOutcomes:
    def test_each_outbox_state_maps_to_one_send_outcome(self, users):
        row = _row(users[0])
        assert _outcome(row) == Outcome.QUEUED

        delivery.claim_one(intent_id=row.pk)
        assert _outcome(row) == Outcome.ATTEMPTED

        delivery.mark_retry([row.pk], "SMTPServerDisconnected")
        assert _outcome(row) == Outcome.RETRYING

        delivery.claim_one(intent_id=row.pk)
        delivery.mark_sent([row.pk])
        assert _outcome(row) == Outcome.ACCEPTED

    def test_a_handed_off_push_is_attempted_not_accepted(self, users):
        row = _row(users[0], kind=Kind.FORUM_PUSH)
        delivery.claim_one(intent_id=row.pk)
        delivery.mark_sent([row.pk], delivery.HANDED_OFF)
        assert _outcome(row) == Outcome.ATTEMPTED

    def test_suppressed_and_failed_are_terminal_outcomes(self, users):
        quiet, dead = _row(users[0]), _row(users[1])
        delivery.mark_suppressed([quiet.pk], "preference_off")
        delivery.mark_failed([dead.pk], "permanent")
        assert (_outcome(quiet), _outcome(dead)) == (
            Outcome.SUPPRESSED,
            Outcome.FAILED,
        )

    def test_a_held_row_is_queued_not_retrying(self, users):
        row = _row(users[0])
        delivery.claim_one(intent_id=row.pk)
        delivery.mark_held([row.pk], timezone.now() + timedelta(hours=2))
        assert _outcome(row) == Outcome.QUEUED

    def test_a_hold_after_a_transient_failure_is_queued(self, users):
        """Review round 1: a row that failed once, then was held (quiet
        hours), is waiting by design, not backing off."""
        row = _row(users[0])
        delivery.claim_one(intent_id=row.pk)
        delivery.mark_retry([row.pk], "SMTPServerDisconnected")
        delivery.claim_one(intent_id=row.pk)
        delivery.mark_held([row.pk], timezone.now() + timedelta(hours=2))
        row.refresh_from_db()
        assert row.attempts == 1  # the failed attempt still counts
        assert _outcome(row) == Outcome.QUEUED
        assert notification_ops.outbox_outcome_counts()[Kind.FORUM_EMAIL] == {
            Outcome.QUEUED: 1
        }

    def test_every_outbox_kind_is_a_live_path_with_a_redriver(self):
        assert set(delivery.REDRIVERS) == set(Kind.values)
        for status in Status.values:
            assert notification_ops.outcome_of_intent(status, 1) in (
                notification_ops.SEND_OUTCOMES
            )

    def test_counts_by_kind_and_the_operator_command(self, users):
        sent = _row(users[0])
        delivery.claim_one(intent_id=sent.pk)
        delivery.mark_sent([sent.pk])
        _row(users[1])
        retrying = _row(users[2], kind=Kind.FORUM_WEB_PUSH)
        delivery.claim_one(intent_id=retrying.pk)
        delivery.mark_retry([retrying.pk])

        assert notification_ops.outbox_outcome_counts() == {
            Kind.FORUM_EMAIL: {Outcome.ACCEPTED: 1, Outcome.QUEUED: 1},
            Kind.FORUM_WEB_PUSH: {Outcome.RETRYING: 1},
        }
        out = StringIO()
        call_command("delivery_outcomes", "--hours", "1", stdout=out)
        text = out.getvalue()
        assert (
            "[OUTCOME] kind=forum_email queued=1 attempted=0 accepted=1 "
            "retrying=0 failed=0 suppressed=0"
        ) in text
        assert "kind=forum_web_push" in text and "retrying=1" in text
        assert "delivered" not in text


class TestEmailServiceOutcomes:
    def test_every_email_outcome_maps(self):
        assert {
            notification_ops.outcome_of_email(o)
            for o in (
                EmailOutcome.SENT,
                EmailOutcome.SUPPRESSED,
                EmailOutcome.PERMANENT,
                EmailOutcome.TRANSIENT,
            )
        } == {Outcome.ACCEPTED, Outcome.SUPPRESSED, Outcome.FAILED, Outcome.RETRYING}
        with pytest.raises(ValueError):
            notification_ops.outcome_of_email("delivered")

    @pytest.mark.django_db
    def test_a_send_is_accepted_and_only_the_provider_says_delivered(self, settings):
        from apps.core.tests.test_email_feedback import (
            EVENT_DELIVERED,
            SECRET,
            _event,
            _post,
        )

        settings.RESEND_WEBHOOK_SECRET = SECRET
        service = EmailService()
        assert service.send_email(
            email_type=EmailType.COMMUNITY_UPDATE,
            recipient=ADDRESS,
            subject="Hello",
            template_name="generic_notification",
            context={"notification_title": "Hello", "notification_message": "Hi"},
        )
        row = EmailNotification.objects.get()
        # The provider took it. That is all a send knows.
        assert notification_ops.outcome_of_email(service.last_outcome) == (
            Outcome.ACCEPTED
        )
        assert notification_ops.outcome_of_notification(row.status) == (
            Outcome.ACCEPTED
        )
        assert row.delivered_at is None

        message_id = mail.outbox[-1].extra_headers["Message-ID"]
        _post(_event(EVENT_DELIVERED, ADDRESS, message_id=message_id), svix_id="d1")
        row.refresh_from_db()
        assert notification_ops.outcome_of_notification(row.status) == (
            Outcome.DELIVERED
        )
        assert Outcome.DELIVERED not in notification_ops.SEND_OUTCOMES

    @pytest.mark.django_db
    def test_a_click_is_engagement_and_leaves_the_outcome_alone(self):
        row = EmailNotification.objects.create(
            email_type=EmailType.FORUM_REPLY,
            recipient_email=ADDRESS,
            subject="s",
            template_name="forum_reply",
            status=EmailNotification.STATUS_SENT,
            sent_at=timezone.now(),
        )
        EmailClick.objects.create(notification=row, link="post_url")
        row.refresh_from_db()
        assert notification_ops.outcome_of_notification(row.status) == (
            Outcome.ACCEPTED
        )


class TestOutcomeLines:
    def test_a_send_run_cannot_report_delivery_or_engagement(self):
        for outcome in ("delivered", "bounced", "complained", "clicked", "opened"):
            with pytest.raises(ValueError):
                notification_ops.log_outcomes("email", "x", **{outcome: 1})

    def test_a_weekly_run_reports_its_outcomes(self, logs):
        task = MagicMock()
        output = (
            "[EMAIL] digest recipients=9 due=6 empty=1 sent=3 failed=2 suppressed=1"
        )

        assert delivery.schedule_weekly_recovery(task, output, 0, "forum weekly digest")
        assert _outcome_lines(logs) == [
            "[OUTCOME] channel=email path=forum_weekly_digest accepted=3 "
            "retrying=2 failed=0 suppressed=1"
        ]

    def test_a_recovery_run_that_cannot_be_enqueued_reports_failed(self, logs):
        task = MagicMock()
        task.apply_async.side_effect = KombuOperationalError("broker down")
        output = "[EMAIL] digest sent=3 failed=2 suppressed=0"

        assert not delivery.schedule_weekly_recovery(task, output, 0, "forum digest")
        # Logged after the decision: nothing will retry them, so failed.
        assert _outcome_lines(logs) == [
            "[OUTCOME] channel=email path=forum_digest accepted=3 retrying=0 "
            "failed=2 suppressed=0"
        ]

    def test_failures_past_the_recovery_cap_are_failed_and_alert(self, logs):
        output = "[EMAIL] newsletter sent=4 failed=1 suppressed=0 pruned=0"
        assert not delivery.schedule_weekly_recovery(
            MagicMock(), output, constants.WEEKLY_RECOVERY_MAX_RUNS, "blog newsletter"
        )
        assert _outcome_lines(logs) == [
            "[OUTCOME] channel=email path=blog_newsletter accepted=4 retrying=0 "
            "failed=1 suppressed=0"
        ]
        assert any("still failed" in r.getMessage() for r in _errors(logs))


@pytest.mark.django_db
class TestCareReminderOutcomes:
    def _owner(self, name, *, token=None, opted_in=True):
        from apps.garden_calendar.models import CareTask, Plant
        from wagtail_forum.models import ForumProfile

        owner = User.objects.create_user(username=name, email=f"{name}@example.com")
        owner.care_reminder_notifications = opted_in
        owner.save(update_fields=["care_reminder_notifications"])
        if token:
            profile = ForumProfile.for_user(owner)
            profile.fcm_token = token
            profile.save(update_fields=["fcm_token"])
        plant = Plant.objects.create(
            owner=owner, common_name="Monstera", planted_date="2026-01-01"
        )
        CareTask.objects.create(
            plant=plant,
            created_by=owner,
            task_type="watering",
            title="Water",
            scheduled_date=timezone.now() - timedelta(minutes=5),
        )
        return owner

    def _sweep(self, fcm):
        from apps.garden_calendar.tasks import send_due_care_task_reminders

        with (
            patch("apps.core.firebase_config.is_firebase_available", return_value=True),
            patch("apps.core.firebase_config.get_fcm_client", return_value=fcm),
        ):
            send_due_care_task_reminders.run()

    def test_a_sweep_reports_one_outcome_per_owner(self, logs):
        from firebase_admin import messaging

        self._owner("gets", token=DEVICE_TOKEN)
        self._owner("away", token="fake-flaky-token")
        self._owner("gone", token="fake-dead-token")
        self._owner("quiet", token="fake-quiet-token", opted_in=False)

        def send(message, *args, **kwargs):
            token = fcm.Message.call_args.kwargs["token"]
            if token == "fake-flaky-token":
                raise ConnectionError("timeout")
            if token == "fake-dead-token":
                raise messaging.UnregisteredError("gone")
            return "projects/x/messages/1"

        fcm = MagicMock()
        fcm.send.side_effect = send
        self._sweep(fcm)

        lines = _outcome_lines(logs)
        assert lines == [
            "[OUTCOME] channel=push path=care_reminder accepted=1 retrying=1 "
            "failed=1 suppressed=1"
        ]
        assert DEVICE_TOKEN not in lines[0]

    def test_a_crashed_sweep_still_reports_its_outcomes(self, logs):
        from apps.garden_calendar import tasks as care_tasks

        self._owner("crash", token=DEVICE_TOKEN)
        with patch.object(
            care_tasks, "_push_to_owners", side_effect=RuntimeError("worker died")
        ):
            with pytest.raises(RuntimeError):
                self._sweep(MagicMock())
        # Released for the next sweep: retrying, reported in the finally.
        assert _outcome_lines(logs) == [
            "[OUTCOME] channel=push path=care_reminder accepted=0 retrying=1 "
            "failed=0 suppressed=0"
        ]

    def test_a_soft_limit_after_one_device_counts_that_owner_accepted(self, logs):
        from apps.core.models import PushDevice
        from celery.exceptions import SoftTimeLimitExceeded

        owner = self._owner("twodev", token=DEVICE_TOKEN)
        PushDevice.objects.create(
            user=owner, token="fake-second-device", platform="ios"
        )
        calls = []

        def send(message, *args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise SoftTimeLimitExceeded()
            return "projects/x/messages/1"

        fcm = MagicMock()
        fcm.send.side_effect = send
        with pytest.raises(SoftTimeLimitExceeded):
            self._sweep(fcm)
        assert _outcome_lines(logs) == [
            "[OUTCOME] channel=push path=care_reminder accepted=1 retrying=0 "
            "failed=0 suppressed=0"
        ]

    def test_a_release_that_fails_reports_failed_not_retrying(self, logs):
        from apps.garden_calendar import tasks as care_tasks

        self._owner("stuck", token=DEVICE_TOKEN)
        with (
            patch.object(
                care_tasks, "_push_to_owners", side_effect=RuntimeError("worker died")
            ),
            patch.object(care_tasks, "_release", side_effect=RuntimeError("db down")),
        ):
            with pytest.raises(RuntimeError):
                self._sweep(MagicMock())
        # The claim stands, so nothing will push it: failed.
        assert _outcome_lines(logs) == [
            "[OUTCOME] channel=push path=care_reminder accepted=0 retrying=0 "
            "failed=1 suppressed=0"
        ]

    def test_a_credentials_stop_reports_every_owner(self, logs):
        from apps.core.fcm import FCM_CREDENTIALS_STOP_FAILURES
        from firebase_admin import messaging

        for i in range(FCM_CREDENTIALS_STOP_FAILURES):
            self._owner(f"cred{i}", token=f"fake-cred-token-{i}")
        self._owner("untried", token="fake-untried-token")
        self._owner("nodevice")  # untried, no token: its claim stands
        fcm = MagicMock()
        fcm.send.side_effect = messaging.ThirdPartyAuthError("apns auth")
        self._sweep(fcm)

        # The failed owners, the untried one with a device released for the
        # next sweep, and the deviceless one whose claim stands.
        assert _outcome_lines(logs) == [
            f"[OUTCOME] channel=push path=care_reminder accepted=0 retrying=1 "
            f"failed={FCM_CREDENTIALS_STOP_FAILURES} suppressed=1"
        ]


# ---------------------------------------------------------------------------
# AC4: alerts
# ---------------------------------------------------------------------------


def _assert_clean(records):
    text = "\n".join(r.getMessage() for r in records)
    for secret in ("fake-broker-password", SECRET_BROKER_URL, ADDRESS, DEVICE_TOKEN):
        assert secret not in text
    assert all(r.exc_info is None for r in records)


class TestBrokerFailure:
    def test_a_refused_enqueue_logs_an_error_without_the_broker_url(self, logs):
        log = logging.getLogger("apps.core.tests.broker")
        try:
            raise KombuOperationalError(f"Error connecting to {SECRET_BROKER_URL}")
        except Exception:
            notification_ops.log_broker_failure(
                log, "[CELERY] failed to enqueue %s", "a batch"
            )
        [record] = _errors(logs)
        assert record.getMessage() == (
            "[CELERY] failed to enqueue a batch (broker: OperationalError)"
        )
        _assert_clean([record])

    @pytest.mark.django_db
    def test_forum_dispatch_logs_the_broker_failure_cleanly(
        self, caplog, django_capture_on_commit_callbacks
    ):
        from apps.forum_host.notifications import dispatch
        from wagtail.models import Page
        from wagtail_forum.models import (
            ForumBoard,
            ForumIndex,
            Post,
            Topic,
            TopicSubscription,
        )

        author = User.objects.create_user(username="ta623", email=ADDRESS)
        replier = User.objects.create_user(username="re623")
        index = Page.objects.get(id=1).add_child(
            instance=ForumIndex(title="F623", slug="f623")
        )
        board = index.add_child(instance=ForumBoard(title="B623", slug="b623"))
        topic = Topic.objects.create(board=board, title="T", slug="t623", author=author)
        TopicSubscription.subscribe(author, topic)

        refused = KombuOperationalError(f"Error connecting to {SECRET_BROKER_URL}")
        with (
            patch(
                "apps.forum_host.tasks.send_forum_email_batch.delay",
                side_effect=refused,
            ),
            patch(
                "apps.forum_host.tasks.send_forum_push_batch.delay", side_effect=refused
            ),
            patch(
                "apps.forum_host.tasks.send_forum_web_push_batch.delay",
                side_effect=refused,
            ),
        ):
            post = Post.objects.create(topic=topic, author=replier)
            with caplog.at_level("ERROR", logger="forum_host.notifications"):
                with django_capture_on_commit_callbacks(execute=True):
                    dispatch("reply_added", topic=topic, post=post)

        errors = [r for r in _errors(caplog) if "failed to enqueue" in r.getMessage()]
        assert errors
        assert all("(broker: OperationalError)" in r.getMessage() for r in errors)
        _assert_clean(errors)
        # The outbox rows stay pending for reconciliation.
        assert DeliveryIntent.objects.filter(status=Status.PENDING).exists()

    @pytest.mark.django_db
    def test_account_mail_enqueue_logs_the_type_only(
        self, logs, django_capture_on_commit_callbacks
    ):
        from apps.users import email_verification

        with (
            patch(
                "apps.users.tasks.send_verification_email_task.delay",
                side_effect=KombuOperationalError(SECRET_BROKER_URL),
            ),
            django_capture_on_commit_callbacks(execute=True),
        ):
            email_verification.enqueue_on_commit(
                "send_verification_email_task", 1, context="user=1"
            )
        [record] = _errors(logs)
        # The shared broker-failure line (review round 2: no bound exception
        # whose text a Sentry frame local could carry).
        assert record.getMessage().endswith("(broker: OperationalError)")
        _assert_clean([record])


@pytest.mark.django_db
class TestOutboxAlerts:
    def test_an_overdue_outbox_alerts(self, users, logs):
        late, healthy = _row(users[0]), _row(users[1])
        DeliveryIntent.objects.filter(pk=late.pk).update(
            next_attempt_at=timezone.now()
            - timedelta(seconds=constants.DELIVERY_QUEUE_LAG_ALERT_SECONDS + 60)
        )
        with patch("apps.forum_host.tasks.redrive_forum_deliveries"):
            totals = delivery.reconcile()

        assert totals["overdue"] == 1
        [record] = [r for r in _errors(logs) if "overdue" in r.getMessage()]
        assert "1 delivery(ies) overdue" in record.getMessage()
        _assert_clean([record])
        # The one counted was the late row: without it, the row inside its
        # grace window is not overdue.
        DeliveryIntent.objects.filter(pk=late.pk).delete()
        healthy.refresh_from_db()
        assert healthy.status == Status.PENDING
        assert notification_ops.check_outbox_lag()["rows"] == 0

    def test_a_failing_lag_check_never_stops_the_redrive(self, users, logs):
        row = _row(users[0])
        DeliveryIntent.objects.filter(pk=row.pk).update(
            next_attempt_at=timezone.now() - timedelta(seconds=1)
        )
        with (
            patch.object(
                delivery, "check_outbox_lag", side_effect=RuntimeError("db blip")
            ),
            patch("apps.forum_host.tasks.redrive_forum_deliveries") as redrive,
        ):
            totals = delivery.reconcile()
        assert totals["redriven"] == 1
        assert totals["overdue"] == 0  # the key is always there
        redrive.assert_called_once()
        assert any("lag check failed" in r.getMessage() for r in _errors(logs))

    def test_a_draining_outbox_does_not_alert(self, users, logs):
        _row(users[0])
        assert notification_ops.check_outbox_lag()["rows"] == 0
        assert not _errors(logs)

    def test_a_held_row_is_not_overdue(self, users, logs):
        row = _row(users[0])
        delivery.claim_one(intent_id=row.pk)
        delivery.mark_held([row.pk], timezone.now() + timedelta(hours=8))
        assert notification_ops.check_outbox_lag()["rows"] == 0

    def test_exhausted_retries_alert(self, users, logs):
        row = _row(users[0])
        DeliveryIntent.objects.filter(pk=row.pk).update(
            attempts=constants.DELIVERY_MAX_ATTEMPTS, status=Status.CLAIMED
        )
        assert delivery.mark_retry([row.pk], "SMTPServerDisconnected") == (0, 1)
        [record] = _errors(logs)
        assert "failed after" in record.getMessage()
        _assert_clean([record])

    def test_expired_and_interrupted_rows_alert(self, users, logs):
        old, stuck = _row(users[0]), _row(users[1])
        long_ago = timezone.now() - timedelta(
            seconds=constants.DELIVERY_MAX_AGE_SECONDS + 60
        )
        DeliveryIntent.objects.filter(pk=old.pk).update(created_at=long_ago)
        DeliveryIntent.objects.filter(pk=stuck.pk).update(
            status=Status.CLAIMED,
            attempts=constants.DELIVERY_MAX_ATTEMPTS,
            claimed_at=timezone.now()
            - timedelta(seconds=constants.DELIVERY_CLAIM_LEASE_SECONDS + 60),
        )
        totals = delivery.reconcile()

        assert (totals["expired"], totals["interrupted"]) == (1, 1)
        [record] = [r for r in _errors(logs) if "expired" in r.getMessage()]
        assert "1 delivery(ies) expired" in record.getMessage()
        assert "1 interrupted" in record.getMessage()


@pytest.mark.django_db
class TestPushConfigAlerts:
    @staticmethod
    def _device(user, token=DEVICE_TOKEN):
        from wagtail_forum.models import ForumProfile

        profile = ForumProfile.for_user(user)
        profile.fcm_token = token
        profile.save(update_fields=["fcm_token"])

    def test_forum_mobile_push_without_firebase_alerts_once(self, users, logs):
        from apps.forum_host.tasks import send_forum_push_batch

        self._device(users[0])
        self._device(users[1], "fake-device-token-two")
        with patch(
            "apps.core.firebase_config.is_firebase_available", return_value=False
        ):
            send_forum_push_batch.run("reply_added", [users[0].pk], {})
            send_forum_push_batch.run("reply_added", [users[1].pk], {})
        [record] = _errors(logs)
        assert record.getMessage().startswith("[PUSH] FCM is not configured")
        _assert_clean([record])

    def test_forum_single_push_without_firebase_alerts(self, users, logs):
        from apps.forum_host.tasks import send_forum_push

        self._device(users[0])
        with patch(
            "apps.core.firebase_config.is_firebase_available", return_value=False
        ):
            send_forum_push.run("reply_added", users[0].pk, {})
        assert [r.getMessage()[:28] for r in _errors(logs)] == [
            "[PUSH] FCM is not configured"
        ]

    def test_browser_push_without_vapid_alerts(self, users, logs, settings):
        from apps.forum_host.tasks import send_forum_web_push_batch
        from apps.users.models import PushSubscription

        PushSubscription.objects.create(
            user=users[0],
            endpoint="https://fcm.googleapis.com/fcm/send/ops0",
            p256dh_key="BPk-key",
            auth_key="auth-value",  # pragma: allowlist secret
        )
        settings.VAPID_PRIVATE_KEY = ""
        send_forum_web_push_batch.run("reply_added", [users[0].pk], {})
        [record] = _errors(logs)
        assert "Web push (VAPID) is not configured" in record.getMessage()

    def test_no_subscription_or_device_means_no_push_alert(self, users, logs, settings):
        """Review round 1: a deployment that runs without VAPID or FCM on
        purpose must not page on ordinary forum activity."""
        from apps.forum_host.tasks import (
            send_forum_push,
            send_forum_push_batch,
            send_forum_web_push_batch,
        )

        settings.VAPID_PRIVATE_KEY = ""
        with patch(
            "apps.core.firebase_config.is_firebase_available", return_value=False
        ):
            send_forum_web_push_batch.run("reply_added", [users[0].pk], {})
            send_forum_push_batch.run("reply_added", [users[0].pk], {})
            send_forum_push.run("reply_added", users[0].pk, {})
        assert not _errors(logs)

    def test_a_cache_outage_still_alerts_but_at_most_once_per_process(self, logs):
        with patch.object(notification_ops.cache, "add", return_value=None):
            assert notification_ops.report_push_unconfigured("FCM", "x")
            assert not notification_ops.report_push_unconfigured("FCM", "x")
        with patch.object(notification_ops.cache, "add", side_effect=OSError("down")):
            assert not notification_ops.report_push_unconfigured("FCM", "x")
        assert len(_errors(logs)) == 1

    def test_a_throttled_alert_skips_the_work_probe(self, logs):
        has_work = MagicMock(return_value=True)
        assert notification_ops.report_push_unconfigured("FCM", "x", has_work=has_work)
        assert not notification_ops.report_push_unconfigured(
            "FCM", "x", has_work=has_work
        )
        # Inside the window, the throttle answers before any probe query.
        assert has_work.call_count == 1

    def test_a_due_reminder_alerts_past_any_number_of_deviceless_owners(self, logs):
        from apps.garden_calendar.models import CareTask, Plant
        from apps.garden_calendar.tasks import _pushable_due

        def owner_with_tasks(name, count):
            owner = User.objects.create_user(username=name, email=f"{name}@x.example")
            plant = Plant.objects.create(
                owner=owner, common_name="Fern", planted_date="2026-01-01"
            )
            CareTask.objects.bulk_create(
                CareTask(
                    plant=plant,
                    created_by=owner,
                    task_type="watering",
                    title="Water",
                    scheduled_date=timezone.now() - timedelta(minutes=5 + i),
                )
                for i in range(count)
            )
            return owner

        for i in range(3):
            owner_with_tasks(f"nodev{i}", 4)
        now = timezone.now()
        assert not _pushable_due(now)
        # One owner with a device among many deviceless tasks: found.
        self._device(owner_with_tasks("hasdev", 1))
        assert _pushable_due(now)

    def test_a_failing_work_probe_is_no_alert_and_no_crash(self, logs):
        assert not notification_ops.report_push_unconfigured(
            "FCM", "x", has_work=MagicMock(side_effect=RuntimeError("db"))
        )
        assert not _errors(logs)

    def test_care_reminders_without_firebase_alert_only_when_one_is_due(self, logs):
        from apps.garden_calendar.models import CareTask, Plant
        from apps.garden_calendar.tasks import send_due_care_task_reminders

        owner = User.objects.create_user(username="carer", email=ADDRESS)
        self._device(owner)
        with patch(
            "apps.core.firebase_config.is_firebase_available", return_value=False
        ):
            send_due_care_task_reminders.run()
            assert not _errors(logs)

            plant = Plant.objects.create(
                owner=owner, common_name="Fern", planted_date="2026-01-01"
            )
            task = CareTask.objects.create(
                plant=plant,
                created_by=owner,
                task_type="watering",
                title="Water",
                scheduled_date=timezone.now() - timedelta(minutes=5),
            )
            send_due_care_task_reminders.run()
        [record] = _errors(logs)
        assert "due care reminders were not pushed" in record.getMessage()
        _assert_clean([record])
        task.refresh_from_db()
        assert task.notification_sent is False  # still delivered once enabled

    def test_care_reminders_nobody_could_receive_do_not_alert(self, logs):
        from apps.garden_calendar.models import CareTask, Plant
        from apps.garden_calendar.tasks import send_due_care_task_reminders

        deviceless = User.objects.create_user(username="nodev", email=ADDRESS)
        opted_out = User.objects.create_user(username="optout", email="o@example.com")
        opted_out.care_reminder_notifications = False
        opted_out.save(update_fields=["care_reminder_notifications"])
        self._device(opted_out)
        for owner in (deviceless, opted_out):
            plant = Plant.objects.create(
                owner=owner, common_name="Fern", planted_date="2026-01-01"
            )
            CareTask.objects.create(
                plant=plant,
                created_by=owner,
                task_type="watering",
                title="Water",
                scheduled_date=timezone.now() - timedelta(minutes=5),
            )
        with patch(
            "apps.core.firebase_config.is_firebase_available", return_value=False
        ):
            send_due_care_task_reminders.run()
        assert not _errors(logs)

    def test_no_work_means_no_alert(self, logs):
        from apps.forum_host.tasks import send_forum_push_batch

        with patch(
            "apps.core.firebase_config.is_firebase_available", return_value=False
        ):
            send_forum_push_batch.run("reply_added", [], {})
        assert not _errors(logs)


# ---------------------------------------------------------------------------
# AC4: Sentry wiring (beat Cron Monitors, ERROR logs as events)
# ---------------------------------------------------------------------------


class _CaptureTransport(sentry_sdk.transport.Transport):
    def __init__(self, options=None):
        super().__init__(options)
        self.envelopes = []

    def capture_envelope(self, envelope):
        self.envelopes.append(envelope)

    def items(self, kind):
        return [
            item.payload.json
            for envelope in self.envelopes
            for item in envelope.items
            if item.type == kind
        ]


@pytest.fixture
def sentry_capture():
    transport = _CaptureTransport()
    sentry_sdk.init(
        dsn="https://public@sentry.invalid/1",
        transport=transport,
        integrations=sentry_integrations(),
        send_default_pii=False,
    )
    try:
        yield transport
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.init()


def test_settings_enable_beat_monitors():
    """settings.py's own ``sentry_sdk.init`` call (the one gated on SENTRY_DSN)
    passes ``sentry_integrations()`` and the alert scrubber, and that list
    carries the beat-monitoring Celery integration. Review round 2: calling
    ``sentry_integrations()`` alone proved nothing about settings.py. Read
    from the source, as ``test_sentry_options_drift.py`` does: the call only
    runs with a DSN, which no test has."""
    import ast
    import inspect as pyinspect

    import plant_community_backend.settings as settings_module
    from sentry_sdk.integrations.celery import CeleryIntegration

    tree = ast.parse(pyinspect.getsource(settings_module))
    [gate] = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and "SENTRY_DSN" in ast.unparse(node.test)
        and "DEBUG" in ast.unparse(node.test)
    ]
    [init] = [
        node
        for node in ast.walk(gate)
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "sentry_sdk.init"
    ]
    keywords = {kw.arg: ast.unparse(kw.value) for kw in init.keywords}
    assert keywords["integrations"] == "_sentry_integrations()"
    assert keywords["before_send"] == "_sentry_before_send"
    imported = {
        (node.module, alias.name, alias.asname)
        for node in ast.walk(gate)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert (
        "plant_community_backend.sentry_config",
        "sentry_integrations",
        "_sentry_integrations",
    ) in imported
    assert (
        "plant_community_backend.sentry_config",
        "before_send",
        "_sentry_before_send",
    ) in imported

    [celery] = [i for i in sentry_integrations() if isinstance(i, CeleryIntegration)]
    assert celery.monitor_beat_tasks is True
    assert not celery.exclude_beat_tasks


def test_every_beat_entry_gets_a_cron_monitor():
    """The SDK silently skips a schedule it cannot express: an interval under
    a minute, or a custom schedule class."""
    from plant_community_backend.celery import app
    from sentry_sdk.integrations.celery.beat import _get_monitor_config

    schedule = django_settings.CELERY_BEAT_SCHEDULE
    assert schedule
    for name, entry in schedule.items():
        config = _get_monitor_config(entry["schedule"], app, name)
        monitor = config.get("schedule", {})
        # The documented contract: a crontab, or an interval of a minute or
        # more (the SDK rounds an interval to whole minutes).
        if monitor.get("type") == "interval":
            assert monitor.get("unit") in ("minute", "hour", "day"), name
            assert int(monitor.get("value", 0)) >= 1, name
        else:
            assert monitor.get("type") == "crontab", name


def test_a_beat_run_checks_in_and_a_failed_one_reports_an_error(sentry_capture):
    from celery.beat import ScheduleEntry, Scheduler
    from celery.schedules import crontab
    from celery.signals import task_failure
    from plant_community_backend.celery import app

    scheduler = Scheduler(app=app, lazy=True)
    entry = ScheduleEntry(
        name="care-task-reminders",
        task="apps.garden_calendar.tasks.send_due_care_task_reminders",
        schedule=crontab(minute="*/15"),
        app=app,
    )
    with patch.object(Scheduler, "apply_async") as enqueue:
        scheduler.apply_entry(entry, producer=None)
    enqueue.assert_called_once()

    headers = entry.options["headers"]
    # The task the worker ran from that message, as the signal sees it.
    task = type("BeatTask", (), {"request": {"headers": dict(headers)}})()
    task_failure.send(sender=task, task_id="t1", exception=RuntimeError("boom"))
    sentry_sdk.flush()

    checkins = sentry_capture.items("check_in")
    assert [(c["monitor_slug"], c["status"]) for c in checkins] == [
        ("care-task-reminders", "in_progress"),
        ("care-task-reminders", "error"),
    ]
    assert checkins[0]["monitor_config"]["schedule"] == {
        "type": "crontab",
        "value": "*/15 * * * *",
    }


@pytest.mark.django_db
def test_an_alert_reaches_sentry_without_secrets(sentry_capture):
    try:
        raise KombuOperationalError(SECRET_BROKER_URL)
    except Exception:
        notification_ops.log_broker_failure(
            logging.getLogger("forum_host.notifications"),
            "[CELERY] forum_host: failed to enqueue %s email batch",
            "reply_added",
        )
    notification_ops.report_push_unconfigured("FCM", "forum reply_added pushes")
    sentry_sdk.flush()

    events = sentry_capture.items("event")
    messages = [e["logentry"]["formatted"] for e in events]
    assert any("(broker: OperationalError)" in m for m in messages)
    assert any("[PUSH] FCM is not configured" in m for m in messages)
    payload = json.dumps(events)
    assert "fake-broker-password" not in payload
    assert SECRET_BROKER_URL not in payload


@pytest.fixture
def sentry_prod_capture():
    """Sentry as production runs it: stack traces attached to log events and
    local variables on, with the project's before_send."""
    from plant_community_backend.sentry_config import before_send

    transport = _CaptureTransport()
    sentry_sdk.init(
        dsn="https://public@sentry.invalid/1",
        transport=transport,
        integrations=sentry_integrations(),
        send_default_pii=False,
        attach_stacktrace=True,
        include_local_variables=True,
        before_send=before_send,
    )
    try:
        yield transport
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.init()


def _frames(event):
    for key in ("exception", "threads"):
        for entry in (event.get(key) or {}).get("values") or []:
            yield from (entry.get("stacktrace") or {}).get("frames") or []


def test_alert_events_carry_no_frame_variables(sentry_prod_capture):
    """Review round 2: with attach_stacktrace and locals on, an alert must
    not ship its caller's locals (a payload, a token, the broker error)."""

    def dispatch_like(token, payload):
        try:
            raise KombuOperationalError(SECRET_BROKER_URL)
        except Exception:
            notification_ops.log_broker_failure(
                logging.getLogger("forum_host.notifications"),
                "[CELERY] forum_host: failed to enqueue %s email batch",
                "reply_added",
            )
        notification_ops.report_push_unconfigured("FCM", "forum reply_added pushes")
        # A control: an ordinary ERROR keeps its frame variables.
        logging.getLogger("apps.core.tests.control").error("[ERROR] control %s", 1)

    dispatch_like(DEVICE_TOKEN, {"actor_name": ADDRESS})
    sentry_sdk.flush()

    events = sentry_prod_capture.items("event")
    alerts = [e for e in events if "control" not in e["logentry"]["formatted"]]
    [control] = [e for e in events if "control" in e["logentry"]["formatted"]]
    assert len(alerts) == 2
    for event in alerts:
        assert list(_frames(event)), "the stack trace is still attached"
        assert not any("vars" in frame for frame in _frames(event))
    payload = json.dumps(alerts)
    for secret in (SECRET_BROKER_URL, "fake-broker-password", DEVICE_TOKEN, ADDRESS):
        assert secret not in payload
    # The scrubber is narrow: the control event still has its locals, so
    # the alerts above lost theirs to before_send, not to the SDK config.
    assert any("vars" in frame for frame in _frames(control))
