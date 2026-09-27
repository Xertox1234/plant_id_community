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

    def test_plants_in_someone_elses_bed_stay_scoped_to_their_owner(self):
        """Ownership is Plant.owner, never the bed's owner."""
        bed = GardenBed.objects.create(owner=self.bob, name="Bob's bed")
        plant = _plant(self.alice, garden_bed=bed)
        self.client.force_authenticate(self.bob)

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
