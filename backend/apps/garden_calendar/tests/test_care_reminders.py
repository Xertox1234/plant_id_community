"""Todo 410: plants belong to a user without a bed, and due CareTasks push.

Covers the ownership re-scope (Plant.owner replaces garden_bed.owner in every
queryset, permission and serializer check), the bed-delete behaviour, and the
beat sweep ``send_due_care_task_reminders``.
"""

import importlib
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from wagtail_forum.models import ForumProfile

from ..models import CareLog, CareTask, GardenBed, Harvest, Plant
from ..tasks import send_due_care_task_reminders

User = get_user_model()

PLANTS = "/api/v1/calendar/api/plants/"
CARE_TASKS = "/api/v1/calendar/api/care-tasks/"
CARE_LOGS = "/api/v1/calendar/api/care-logs/"
HARVESTS = "/api/v1/calendar/api/harvests/"


def _plant(owner, **kwargs):
    kwargs.setdefault("common_name", "Monstera")
    kwargs.setdefault("planted_date", date(2026, 1, 1))
    return Plant.objects.create(owner=owner, **kwargs)


def _task(plant, *, due, **kwargs):
    kwargs.setdefault("created_by", plant.owner)
    kwargs.setdefault("task_type", "watering")
    kwargs.setdefault("title", "Water the Monstera")
    return CareTask.objects.create(plant=plant, scheduled_date=due, **kwargs)


class BedlessPlantApiTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", email="a@x.com")
        self.bob = User.objects.create_user(username="bob", email="b@x.com")
        self.client = APIClient()

    def test_a_plant_can_be_created_without_a_bed(self):
        self.client.force_authenticate(self.alice)

        response = self.client.post(
            PLANTS,
            {"common_name": "Pothos", "planted_date": "2026-09-01"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        plant = Plant.objects.get(common_name="Pothos")
        self.assertEqual(plant.owner, self.alice)
        self.assertIsNone(plant.garden_bed)

    def test_bedless_plant_serializes_with_a_null_bed_name(self):
        plant = _plant(self.alice)
        self.client.force_authenticate(self.alice)

        listed = self.client.get(PLANTS).data["results"][0]
        detail = self.client.get(f"{PLANTS}{plant.uuid}/").data

        # Key PRESENCE, not just a falsy value: a SkipField would drop it.
        self.assertIn("garden_bed_name", listed)
        self.assertIsNone(listed["garden_bed_name"])
        self.assertTrue(detail["can_edit"])

    def test_another_users_bedless_plant_is_invisible(self):
        plant = _plant(self.alice)
        self.client.force_authenticate(self.bob)

        self.assertEqual(self.client.get(PLANTS).data["results"], [])
        self.assertEqual(
            self.client.get(f"{PLANTS}{plant.uuid}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_a_plant_cannot_sit_in_another_users_bed(self):
        """Owner and bed are separate FKs; the model keeps them agreeing."""
        from django.core.exceptions import ValidationError

        bed = GardenBed.objects.create(owner=self.bob, name="Bob's bed")
        with self.assertRaises(ValidationError):
            _plant(self.alice, garden_bed=bed)
        plant = _plant(self.alice)
        plant.garden_bed = bed
        with self.assertRaises(ValidationError):
            plant.full_clean()

    def test_a_diverged_plant_never_shows_through_the_bed(self):
        """Defense in depth (PR #853 review): even if a write bypasses save()
        (a queryset update, raw SQL), the bed's reads filter on its owner."""
        bed = GardenBed.objects.create(owner=self.bob, name="Bob's bed")
        plant = _plant(self.alice)
        Plant.objects.filter(pk=plant.pk).update(garden_bed=bed)
        _task(plant, due=timezone.now())
        self.client.force_authenticate(self.bob)

        detail = self.client.get(f"/api/v1/calendar/api/garden-beds/{bed.uuid}/")
        listed = self.client.get("/api/v1/calendar/api/garden-beds/").data["results"]
        stats = self.client.get(
            f"/api/v1/calendar/api/garden-beds/{bed.uuid}/analytics/"
        )

        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["plants"], [])
        self.assertEqual(listed[0]["plant_count"], 0)
        self.assertEqual(stats.status_code, status.HTTP_200_OK, stats.data)
        self.assertEqual(stats.data["health_status_breakdown"], {})
        self.assertEqual(stats.data["plant_count"], 0)
        self.assertEqual(stats.data["care_tasks"]["total"], 0)
        self.assertEqual(
            self.client.get(f"{PLANTS}{plant.uuid}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_a_plant_created_in_a_bed_defaults_to_the_beds_owner(self):
        bed = GardenBed.objects.create(owner=self.alice, name="Bed")
        plant = Plant.objects.create(
            garden_bed=bed, common_name="Basil", planted_date=date(2026, 1, 1)
        )
        self.assertEqual(plant.owner, self.alice)

    def test_deleting_a_bed_keeps_its_plants(self):
        """Owner decision 2026-09-27: SET_NULL, not CASCADE."""
        bed = GardenBed.objects.create(owner=self.alice, name="Bed")
        plant = _plant(self.alice, garden_bed=bed)

        bed.delete()

        plant.refresh_from_db()
        self.assertIsNone(plant.garden_bed)
        self.assertEqual(plant.owner, self.alice)
        self.assertEqual(str(plant), "Monstera")

    def test_care_task_on_a_bedless_plant(self):
        plant = _plant(self.alice)
        self.client.force_authenticate(self.alice)

        response = self.client.post(
            CARE_TASKS,
            {
                "plant": str(plant.uuid),
                "task_type": "watering",
                "title": "Water",
                "scheduled_date": timezone.now().isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        task = CareTask.objects.get(plant=plant)
        self.assertEqual(
            self.client.get(f"{CARE_TASKS}{task.uuid}/").status_code,
            status.HTTP_200_OK,
        )

    def test_rows_cannot_be_attached_to_another_users_plant(self):
        """The object permission guards detail routes only; create validates
        the plant's owner (the care-log and harvest paths had no check)."""
        plant = _plant(self.alice)
        self.client.force_authenticate(self.bob)
        now = timezone.now().isoformat()
        cases = {
            CARE_TASKS: {
                "plant": str(plant.uuid),
                "task_type": "watering",
                "title": "Water",
                "scheduled_date": now,
            },
            CARE_LOGS: {"plant": str(plant.uuid), "activity_type": "watering"},
            HARVESTS: {
                "plant": str(plant.uuid),
                "harvest_date": "2026-09-01",
                "quantity": "1",
                "unit": "count",
            },
        }
        for url, payload in cases.items():
            with self.subTest(url=url):
                response = self.client.post(url, payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("plant", response.data["errors"])
        self.assertFalse(CareTask.objects.exists())
        self.assertFalse(CareLog.objects.exists())
        self.assertFalse(Harvest.objects.exists())

    def test_rescheduling_a_task_rearms_its_reminder(self):
        plant = _plant(self.alice)
        task = _task(plant, due=timezone.now(), notification_sent=True)
        self.client.force_authenticate(self.alice)

        self.client.patch(
            f"{CARE_TASKS}{task.uuid}/", {"title": "Water well"}, format="json"
        )
        task.refresh_from_db()
        self.assertTrue(task.notification_sent)

        later = (timezone.now() + timedelta(days=2)).isoformat()
        response = self.client.patch(
            f"{CARE_TASKS}{task.uuid}/", {"scheduled_date": later}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        task.refresh_from_db()
        self.assertFalse(task.notification_sent)


class OverdueStampMigrationTest(TestCase):
    def test_overdue_open_tasks_are_stamped_and_the_rest_left_alone(self):
        migration = importlib.import_module(
            "apps.garden_calendar.migrations.0008_plant_owner_optional_garden_bed"
        )
        owner = User.objects.create_user(username="o", email="o@x.com")
        plant = _plant(owner)
        now = timezone.now()
        overdue = _task(plant, due=now - timedelta(days=3))
        done = _task(plant, due=now - timedelta(days=3), completed=True)
        upcoming = _task(plant, due=now + timedelta(days=1))

        migration.stamp_overdue_tasks(django_apps, None)

        for task, expected in ((overdue, True), (done, False), (upcoming, False)):
            task.refresh_from_db()
            self.assertEqual(task.notification_sent, expected)


class CareReminderSweepTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", email="a@x.com")
        self.plant = _plant(self.alice)
        self._set_token(self.alice, "alice-device")
        self.now = timezone.now()

    def _set_token(self, user, token):
        profile = ForumProfile.for_user(user)
        profile.fcm_token = token
        profile.save(update_fields=["fcm_token"])

    def _run(self, *, available=True, send=None):
        fcm = MagicMock()
        if send is not None:
            fcm.send.side_effect = send
        with patch(
            "apps.core.firebase_config.is_firebase_available", return_value=available
        ), patch("apps.core.firebase_config.get_fcm_client", return_value=fcm):
            send_due_care_task_reminders.run()
        return fcm

    def _sent_tokens(self, fcm):
        return [c.kwargs["token"] for c in fcm.Message.call_args_list]

    def test_a_due_task_pushes_its_owner_once(self):
        task = _task(self.plant, due=self.now - timedelta(minutes=5))

        fcm = self._run()
        self._run()  # a second sweep finds it already claimed

        self.assertEqual(fcm.send.call_count, 1)
        message = fcm.Message.call_args.kwargs
        self.assertEqual(message["token"], "alice-device")
        self.assertEqual(message["data"]["event"], "care_task_due")
        self.assertEqual(message["data"]["care_task_uuid"], str(task.uuid))
        self.assertEqual(message["data"]["plant_uuid"], str(self.plant.uuid))
        fcm.Notification.assert_called_once_with(
            title="Water the Monstera", body="Monstera is due for care."
        )
        fcm.AndroidConfig.assert_called_once_with(collapse_key="care-task-due")
        task.refresh_from_db()
        self.assertTrue(task.notification_sent)

    def test_only_open_tasks_due_in_the_lookback_window_are_claimed(self):
        stale = _task(self.plant, due=self.now - timedelta(hours=25))
        future = _task(self.plant, due=self.now + timedelta(minutes=5))
        done = _task(self.plant, due=self.now, completed=True)
        skipped = _task(self.plant, due=self.now, skipped=True)
        retired = _plant(self.alice, is_active=False)
        on_retired = _task(retired, due=self.now)

        fcm = self._run()

        fcm.send.assert_not_called()
        for task in (stale, future, done, skipped, on_retired):
            task.refresh_from_db()
            self.assertFalse(task.notification_sent, task)

    def test_the_plant_owner_is_notified_not_the_task_creator(self):
        bob = User.objects.create_user(username="bob", email="b@x.com")
        self._set_token(bob, "bob-device")
        _task(self.plant, due=self.now, created_by=bob)

        fcm = self._run()

        self.assertEqual(self._sent_tokens(fcm), ["alice-device"])

    def test_several_due_tasks_make_one_push_per_owner(self):
        bob = User.objects.create_user(username="bob", email="b@x.com")
        self._set_token(bob, "bob-device")
        for title in ("Water", "Mist", "Feed", "Repot"):
            _task(self.plant, due=self.now - timedelta(minutes=1), title=title)
        _task(_plant(bob), due=self.now)

        fcm = self._run()

        self.assertCountEqual(self._sent_tokens(fcm), ["alice-device", "bob-device"])
        titles = [c.kwargs["title"] for c in fcm.Notification.call_args_list]
        self.assertIn("4 plant care tasks are due", titles)
        bodies = [c.kwargs["body"] for c in fcm.Notification.call_args_list]
        self.assertIn("Water, Mist, Feed and 1 more", bodies)

    def test_an_opted_out_owner_gets_nothing_and_the_task_is_not_rechecked(self):
        User.objects.filter(pk=self.alice.pk).update(care_reminder_notifications=False)
        task = _task(self.plant, due=self.now)

        fcm = self._run()

        fcm.send.assert_not_called()
        task.refresh_from_db()
        self.assertTrue(task.notification_sent)

    def test_an_owner_with_no_device_gets_nothing(self):
        self._set_token(self.alice, "")
        _task(self.plant, due=self.now)

        fcm = self._run()

        fcm.send.assert_not_called()

    def test_a_transient_failure_releases_the_task_for_the_next_sweep(self):
        task = _task(self.plant, due=self.now)

        self._run(send=RuntimeError("503"))

        task.refresh_from_db()
        self.assertFalse(task.notification_sent)

    def test_a_permanent_failure_keeps_the_claim(self):
        from firebase_admin import messaging

        task = _task(self.plant, due=self.now)

        self._run(send=messaging.UnregisteredError("gone"))

        task.refresh_from_db()
        self.assertTrue(task.notification_sent)

    def test_the_soft_time_limit_unclaims_every_owner_not_reached(self):
        """Review finding: the per-owner `except Exception` swallowed
        SoftTimeLimitExceeded, and the hard kill left unreached tasks claimed
        for good."""
        from celery.exceptions import SoftTimeLimitExceeded

        bob = User.objects.create_user(username="bob", email="b@x.com")
        cat = User.objects.create_user(username="cat", email="c@x.com")
        self._set_token(bob, "bob-device")
        self._set_token(cat, "cat-device")
        tasks = {
            "alice": _task(self.plant, due=self.now - timedelta(minutes=3)),
            "bob": _task(_plant(bob), due=self.now - timedelta(minutes=2)),
            "cat": _task(_plant(cat), due=self.now - timedelta(minutes=1)),
        }
        calls = []

        def send(message):
            calls.append(message)
            if len(calls) == 2:
                raise SoftTimeLimitExceeded()
            return "ok"

        with self.assertRaises(SoftTimeLimitExceeded):
            self._run(send=send)

        self.assertEqual(len(calls), 2)  # the loop stopped at the limit
        sent_flags = {}
        for name, task in tasks.items():
            task.refresh_from_db()
            sent_flags[name] = task.notification_sent
        # Exactly one owner was pushed before the limit; the other two are
        # released for the next sweep.
        self.assertEqual(sorted(sent_flags.values()), [False, False, True])

    def test_a_db_error_after_the_claim_unclaims_the_batch_for_the_retry(self):
        """Review finding: autoretry re-ran the task, but the committed claim
        hid the batch from the retry's claim query."""
        from django.db import OperationalError

        task = _task(self.plant, due=self.now)

        with patch.object(
            User.objects, "filter", side_effect=OperationalError("db blip")
        ):
            with self.assertRaises(OperationalError):
                self._run()

        task.refresh_from_db()
        self.assertFalse(task.notification_sent)
        fcm = self._run()  # the retry finds it again
        self.assertEqual(fcm.send.call_count, 1)

    def test_rescheduling_overdue_tasks_rearms_their_reminders(self):
        from ..services.care_schedule_service import CareScheduleService

        task = _task(
            self.plant, due=self.now - timedelta(days=10), notification_sent=True
        )

        CareScheduleService.reschedule_overdue_tasks(self.alice)

        task.refresh_from_db()
        self.assertGreater(task.scheduled_date, self.now)
        self.assertFalse(task.notification_sent)

    def test_nothing_is_claimed_while_firebase_is_off(self):
        task = _task(self.plant, due=self.now)

        fcm = self._run(available=False)

        fcm.send.assert_not_called()
        task.refresh_from_db()
        self.assertFalse(task.notification_sent)


def test_care_reminders_are_scheduled_on_a_registered_task():
    """A typo'd beat task name is silent in prod (docs/rules/celery.md)."""
    from celery.schedules import crontab
    from django.conf import settings

    entry = settings.CELERY_BEAT_SCHEDULE["care-task-reminders"]
    assert entry["task"] == send_due_care_task_reminders.name
    assert isinstance(entry["schedule"], crontab)
    assert entry["schedule"].minute == {0, 15, 30, 45}


# ---- Todo 457: care-reminder follow-ups from the PR #853 review ----


class RecurrenceAfterLateCompletionTest(TestCase):
    """Item 1 (owner decision 2026-10-10): the next occurrence is dated from
    the later of the due date and the completion."""

    def setUp(self):
        self.alice = User.objects.create_user(username="alice", email="a@x.com")
        self.plant = _plant(self.alice)

    def _weekly(self, due, **kwargs):
        return _task(
            self.plant,
            due=due,
            is_recurring=True,
            recurrence_interval_days=7,
            **kwargs,
        )

    def _next(self, task):
        return CareTask.objects.exclude(pk=task.pk).get(plant=self.plant)

    def test_a_late_completion_dates_the_next_one_from_the_completion(self):
        task = self._weekly(timezone.now() - timedelta(days=9))

        task.mark_complete(self.alice)

        task.refresh_from_db()
        nxt = self._next(task)
        self.assertEqual(nxt.scheduled_date, task.completed_at + timedelta(days=7))
        # Not already overdue, so the reminder sweep will see it fall due.
        self.assertGreater(nxt.scheduled_date, timezone.now())

    def test_an_early_completion_keeps_the_schedule(self):
        due = timezone.now() + timedelta(days=2)
        task = self._weekly(due)

        task.mark_complete(self.alice)

        self.assertEqual(self._next(task).scheduled_date, due + timedelta(days=7))

    def test_the_end_date_is_checked_against_the_new_date(self):
        # Due-date + 7 would fall before the end date; completion + 7 does not.
        due = timezone.now() - timedelta(days=9)
        task = self._weekly(due, recurrence_end_date=(due + timedelta(days=8)).date())

        task.mark_complete(self.alice)

        self.assertFalse(CareTask.objects.exclude(pk=task.pk).exists())


class BedCapSerializerTest(TestCase):
    """Item 2: the bed cap counts a plant moving INTO a full bed."""

    def setUp(self):
        self.alice = User.objects.create_user(username="alice", email="a@x.com")
        self.client = APIClient()
        self.client.force_authenticate(self.alice)
        self.bed = GardenBed.objects.create(owner=self.alice, name="Bed")
        self.inside = [_plant(self.alice, garden_bed=self.bed) for _ in range(2)]
        self.cap = patch("apps.garden_calendar.constants.MAX_PLANTS_PER_GARDEN_BED", 2)
        self.cap.start()
        self.addCleanup(self.cap.stop)

    def test_a_plant_cannot_move_into_a_full_bed(self):
        outside = _plant(self.alice)

        response = self.client.patch(
            f"{PLANTS}{outside.uuid}/",
            {"garden_bed": str(self.bed.uuid)},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("garden_bed", response.data["errors"])
        outside.refresh_from_db()
        self.assertIsNone(outside.garden_bed)

    def test_a_plant_already_in_a_full_bed_can_still_be_edited(self):
        response = self.client.patch(
            f"{PLANTS}{self.inside[0].uuid}/",
            {"garden_bed": str(self.bed.uuid), "notes": "fine"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)


class OwnerFilteredBedReadsTest(TestCase):
    """Item 12: bed reads count only the bed owner's plants."""

    def setUp(self):
        self.alice = User.objects.create_user(username="alice", email="a@x.com")
        self.bob = User.objects.create_user(username="bob", email="b@x.com")
        self.bed = GardenBed.objects.create(owner=self.alice, name="Bed")
        self.mine = _plant(self.alice, garden_bed=self.bed, common_name="tomato")
        self.theirs = _plant(self.alice, garden_bed=self.bed, common_name="basil")
        # A diverged row (the shape item 10 stops the admin from creating).
        Plant.objects.filter(pk=self.theirs.pk).update(owner=self.bob)

    def test_plant_count_fallback_ignores_another_owners_plant(self):
        self.assertEqual(GardenBed.objects.get(pk=self.bed.pk).plant_count, 1)

    def test_companion_reads_ignore_another_owners_plant(self):
        from ..services.companion_planting_service import CompanionPlantingService

        analysis = CompanionPlantingService.analyze_garden_bed(self.bed)

        self.assertEqual(analysis["total_plants"], 1)


class CareReminderFollowUpSweepTest(TestCase):
    """Items 3, 4 and 5 on the beat sweep (borrows the sweep fixtures without
    inheriting, and so re-running, that class's tests)."""

    setUp = CareReminderSweepTest.setUp
    _set_token = CareReminderSweepTest._set_token
    _run = CareReminderSweepTest._run

    def _token(self, user):
        return ForumProfile.objects.get(user=user).fcm_token

    def test_a_dead_token_is_cleared(self):
        from firebase_admin import messaging

        _task(self.plant, due=self.now)

        self._run(send=messaging.UnregisteredError("gone"))

        self.assertEqual(self._token(self.alice), "")

    def test_a_credential_error_keeps_the_token(self):
        """ThirdPartyAuthError is permanent but project-wide, not the token."""
        from firebase_admin import messaging

        _task(self.plant, due=self.now)

        self._run(send=messaging.ThirdPartyAuthError("apns cert"))

        self.assertEqual(self._token(self.alice), "alice-device")

    def test_a_sender_id_mismatch_keeps_the_token_and_logs_an_error(self):
        """Todo 566 (owner decision 2026-10-11): SenderIdMismatchError means
        the server's credentials are another project's, so one bad deploy
        would wipe every token. Keep it, and log at ERROR."""
        from firebase_admin import messaging

        _task(self.plant, due=self.now)

        with self.assertLogs("apps.garden_calendar.tasks", level="ERROR") as logs:
            self._run(send=messaging.SenderIdMismatchError("other project"))

        self.assertEqual(self._token(self.alice), "alice-device")
        self.assertTrue(
            any(m.startswith("ERROR:") and "permanently" in m for m in logs.output),
            logs.output,
        )

    def test_a_dead_token_logs_a_warning_not_an_error(self):
        from firebase_admin import messaging

        _task(self.plant, due=self.now)

        with self.assertLogs("apps.garden_calendar.tasks", level="WARNING") as logs:
            self._run(send=messaging.UnregisteredError("gone"))

        permanent = [m for m in logs.output if "permanently" in m]
        self.assertEqual(len(permanent), 1, logs.output)
        self.assertTrue(permanent[0].startswith("WARNING:"), permanent)

    def test_a_token_reregistered_during_the_sweep_send_is_kept(self):
        """Todo 566 item 7: drive the sweep itself. The device registers a new
        token while the send to the old one is failing; the clear matches on
        the failed token, so the new one survives."""
        from firebase_admin import messaging

        _task(self.plant, due=self.now)

        def send(_message):
            self._set_token(self.alice, "alice-new-device")
            raise messaging.UnregisteredError("old token gone")

        self._run(send=send)

        self.assertEqual(self._token(self.alice), "alice-new-device")

    def test_an_autoretried_db_error_does_not_warn_of_an_age_out(self):
        """Todo 566 item 6: an OperationalError after the claim releases the
        batch and autoretry re-claims it within minutes, so the "will not be
        sent" warning would be false."""
        from django.db import OperationalError

        _task(self.plant, due=self.now - timedelta(hours=23, minutes=50))

        with patch(
            "apps.garden_calendar.tasks._push_to_owners",
            side_effect=OperationalError("db blip"),
        ), patch("apps.garden_calendar.tasks.logger") as log:
            with self.assertRaises(OperationalError):
                self._run()

        messages = [str(c.args[0]) for c in log.warning.call_args_list]
        self.assertFalse([m for m in messages if "will not be sent" in m], messages)

    def test_a_db_error_on_the_last_retry_still_warns_of_an_age_out(self):
        from django.db import OperationalError

        _task(self.plant, due=self.now - timedelta(hours=23, minutes=50))

        send_due_care_task_reminders.push_request(
            retries=send_due_care_task_reminders.max_retries
        )
        try:
            with patch(
                "apps.garden_calendar.tasks._push_to_owners",
                side_effect=OperationalError("db blip"),
            ), patch("apps.garden_calendar.tasks.logger") as log:
                with self.assertRaises(OperationalError):
                    self._run()
        finally:
            send_due_care_task_reminders.pop_request()

        messages = [str(c.args[0]) for c in log.warning.call_args_list]
        self.assertEqual(
            len([m for m in messages if "will not be sent" in m]), 1, messages
        )

    def test_a_token_reregistered_since_the_send_is_kept(self):
        from apps.core.fcm import clear_dead_fcm_token

        self.assertEqual(clear_dead_fcm_token(self.alice.pk, "an-older-token"), 0)
        self.assertEqual(self._token(self.alice), "alice-device")

    def test_a_released_task_about_to_age_out_is_logged(self):
        last_chance = _task(self.plant, due=self.now - timedelta(hours=23, minutes=50))
        _task(_plant(self.alice), due=self.now - timedelta(minutes=5))

        with self.assertLogs("apps.garden_calendar.tasks", level="WARNING") as logs:
            self._run(send=RuntimeError("503"))

        aging = [m for m in logs.output if "will not be sent" in m]
        self.assertEqual(len(aging), 1, logs.output)
        self.assertIn(str(last_chance.uuid), aging[0])

    def test_the_sweep_logs_carry_the_task_id(self):
        _task(self.plant, due=self.now)
        send_due_care_task_reminders.push_request(id="sweep-123")
        try:
            with self.assertLogs("apps.garden_calendar.tasks", level="INFO") as logs:
                self._run()
        finally:
            send_due_care_task_reminders.pop_request()

        self.assertTrue(any("task=sweep-123" in m for m in logs.output), logs.output)


class CareReminderAutoretryCountdownTest(TestCase):
    """Item 6: pin retry_backoff=60 for OperationalError. ``.apply()`` ignores
    countdown (docs/rules/celery.md), so fake the retry counter, mock retry()
    and patch full jitter to its maximum."""

    def test_the_countdown_is_exponential_from_60_seconds(self):
        from celery.exceptions import Retry
        from django.db import OperationalError

        for prior_retries, ceiling in ((0, 60), (1, 120), (2, 240)):
            with self.subTest(retries=prior_retries), patch(
                "apps.core.firebase_config.is_firebase_available", return_value=True
            ), patch(
                "apps.core.firebase_config.get_fcm_client", return_value=MagicMock()
            ), patch(
                "apps.garden_calendar.tasks._claim_due_tasks",
                side_effect=OperationalError("db blip"),
            ), patch(
                "celery.utils.time.random.randrange", side_effect=lambda n: n - 1
            ), patch.object(
                send_due_care_task_reminders, "retry", side_effect=Retry("retried")
            ) as mock_retry:
                send_due_care_task_reminders.push_request(retries=prior_retries)
                try:
                    with self.assertRaises(Retry):
                        send_due_care_task_reminders.run()
                finally:
                    send_due_care_task_reminders.pop_request()

                self.assertEqual(mock_retry.call_args.kwargs["countdown"], ceiling)


def test_the_sweep_interval_constant_matches_the_beat_schedule():
    """Item 4's age-out warning assumes the sweep runs every
    CARE_REMINDER_SWEEP_INTERVAL_MINUTES."""
    from django.conf import settings

    from ..constants import CARE_REMINDER_SWEEP_INTERVAL_MINUTES

    entry = settings.CELERY_BEAT_SCHEDULE["care-task-reminders"]
    assert entry["schedule"].minute == set(
        range(0, 60, CARE_REMINDER_SWEEP_INTERVAL_MINUTES)
    )
