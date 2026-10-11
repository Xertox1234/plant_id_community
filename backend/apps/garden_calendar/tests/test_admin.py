"""Todo 457 items 9 and 10: the garden admin keeps reminders and owners sane."""

from datetime import date, timedelta

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone

from ..admin import CareTaskAdmin, GardenBedAdmin
from ..models import CareTask, GardenBed, Plant

User = get_user_model()


class CareTaskAdminRearmTest(TestCase):
    """Item 9: moving a task's date in the admin re-arms its reminder."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", email="s@x.com", is_staff=True, is_superuser=True
        )
        self.owner = User.objects.create_user(username="owner", email="o@x.com")
        plant = Plant.objects.create(
            owner=self.owner, common_name="Monstera", planted_date=date(2026, 1, 1)
        )
        self.task = CareTask.objects.create(
            plant=plant,
            created_by=self.owner,
            task_type="watering",
            title="Water",
            scheduled_date=timezone.now() - timedelta(hours=1),
            notification_sent=True,
        )
        self.admin = CareTaskAdmin(CareTask, AdminSite())
        self.request = RequestFactory().post("/")
        self.request.user = self.staff

    def _save(self, **changes):
        form_class = self.admin.get_form(self.request, self.task, change=True)
        initial = form_class(instance=self.task).initial
        data = {k: v for k, v in initial.items() if v is not None}
        scheduled = data.pop("scheduled_date")
        data["scheduled_date_0"] = scheduled.date().isoformat()
        data["scheduled_date_1"] = scheduled.time().strftime("%H:%M:%S")
        data.update(changes)
        for flag in ("is_recurring", "completed", "skipped", "notification_sent"):
            if not data.get(flag):
                data.pop(flag, None)
        form = form_class(data, instance=self.task)
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save(commit=False)
        self.admin.save_model(self.request, obj, form, change=True)
        self.task.refresh_from_db()

    def test_a_rescheduled_task_is_re_armed(self):
        later = timezone.localtime(timezone.now() + timedelta(days=2))
        self._save(
            scheduled_date_0=later.date().isoformat(),
            scheduled_date_1=later.time().strftime("%H:%M:%S"),
        )

        self.assertFalse(self.task.notification_sent)

    def test_an_edit_that_keeps_the_date_keeps_the_flag(self):
        self._save(title="Water well")

        self.assertEqual(self.task.title, "Water well")
        self.assertTrue(self.task.notification_sent)

    def _later(self):
        later = timezone.localtime(timezone.now() + timedelta(days=2))
        return {
            "scheduled_date_0": later.date().isoformat(),
            "scheduled_date_1": later.time().strftime("%H:%M:%S"),
        }

    def test_staff_setting_the_flag_with_the_new_date_keeps_it(self):
        """Todo 566 items 2/3: staff who tick notification_sent in the same
        edit that moves the date override the re-arm."""
        CareTask.objects.filter(pk=self.task.pk).update(notification_sent=False)
        self.task.refresh_from_db()

        self._save(notification_sent="on", **self._later())

        self.assertTrue(self.task.notification_sent)

    def test_an_add_is_never_re_armed(self):
        """Todo 566 items 2/3: the guard acts on a change only. On an add the
        date is always in changed_data, and save_model leaves the flag as
        given."""
        form_class = self.admin.get_form(self.request, None, change=False)
        initial = form_class(instance=self.task).initial
        data = {k: v for k, v in initial.items() if v is not None}
        scheduled = data.pop("scheduled_date")
        data["scheduled_date_0"] = scheduled.date().isoformat()
        data["scheduled_date_1"] = scheduled.time().strftime("%H:%M:%S")
        for flag in ("is_recurring", "completed", "skipped", "notification_sent"):
            if not data.get(flag):
                data.pop(flag, None)
        data.pop("notification_sent", None)
        form = form_class(data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIn("scheduled_date", form.changed_data)
        self.assertNotIn("notification_sent", form.changed_data)
        obj = form.save(commit=False)
        obj.notification_sent = True  # e.g. set by a save hook or an import

        self.admin.save_model(self.request, obj, form, change=False)

        obj.refresh_from_db()
        self.assertTrue(obj.notification_sent)


class GardenBedAdminOwnerTest(TestCase):
    """Item 10: a bed's owner cannot be changed in the admin."""

    def setUp(self):
        self.admin = GardenBedAdmin(GardenBed, AdminSite())
        self.request = RequestFactory().get("/")

    def test_the_owner_is_read_only_on_change(self):
        owner = User.objects.create_user(username="owner", email="o@x.com")
        bed = GardenBed.objects.create(owner=owner, name="Bed")

        self.assertIn("owner", self.admin.get_readonly_fields(self.request, bed))

    def test_the_owner_is_editable_on_add(self):
        self.assertNotIn("owner", self.admin.get_readonly_fields(self.request, None))
