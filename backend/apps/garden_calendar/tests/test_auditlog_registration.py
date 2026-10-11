"""
The garden models are audited (todo 571).

``apps/garden_calendar/auditlog.py`` registered five models but nothing
imported it, so no garden model ever wrote a LogEntry. These tests go through
the real app registry: they fail if ``GardenCalendarConfig.ready()`` stops
importing the module. They also pin the owner's scope decision (2026-10-11):
free-text fields such as ``notes`` never land in a LogEntry.
"""

from auditlog.models import LogEntry
from auditlog.registry import auditlog
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from ..models import CareLog, CareTask, GardenBed, Harvest, Plant

User = get_user_model()

FREE_TEXT_FIELDS = {
    "notes",
    "description",
    "materials_used",
    "weather_conditions",
    "skip_reason",
}


def _update_entries(obj):
    return LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(type(obj)),
        object_pk=str(obj.pk),
        action=LogEntry.Action.UPDATE,
    ).order_by("timestamp", "pk")


class GardenAuditlogRegistrationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="audit_user",
            email="audit@test.com",
            password="testpass123",  # pragma: allowlist secret
        )
        self.bed = GardenBed.objects.create(
            owner=self.user, name="Bed", bed_type="raised"
        )
        self.plant = Plant.objects.create(
            garden_bed=self.bed,
            common_name="Tomato",
            health_status="healthy",
            growth_stage="seedling",
            planted_date=timezone.now().date(),
        )

    def _task(self):
        return CareTask.objects.create(
            plant=self.plant,
            created_by=self.user,
            task_type="watering",
            title="Water",
            priority="medium",
            scheduled_date=timezone.now(),
        )

    def test_all_five_models_are_registered(self):
        for model in (GardenBed, Plant, CareTask, CareLog, Harvest):
            self.assertTrue(auditlog.contains(model), model.__name__)

    def test_mark_complete_writes_update_logentry_with_completed(self):
        task = self._task()
        task.mark_complete(self.user)

        entries = list(_update_entries(task))
        self.assertEqual(len(entries), 1)
        changes = entries[0].changes_dict
        self.assertIn("completed", changes)
        self.assertEqual(changes["completed"][1], "True")

    def test_mark_skip_writes_update_logentry_with_skipped(self):
        task = self._task()
        task.mark_skip(self.user, reason="It rained all week on my tomatoes")

        entries = list(_update_entries(task))
        self.assertEqual(len(entries), 1)
        changes = entries[0].changes_dict
        self.assertIn("skipped", changes)
        self.assertEqual(changes["skipped"][1], "True")
        # The skip reason is free text: it must not be audited.
        self.assertNotIn("skip_reason", changes)

    def test_plant_update_writes_update_logentry_without_notes(self):
        self.plant.health_status = "stressed"
        self.plant.notes = "Private observation about my plant"
        self.plant.save()

        entries = list(_update_entries(self.plant))
        self.assertEqual(len(entries), 1)
        changes = entries[0].changes_dict
        self.assertIn("health_status", changes)
        self.assertEqual(changes["health_status"], ["healthy", "stressed"])
        self.assertNotIn("notes", changes)

    def test_notes_only_edit_writes_no_logentry(self):
        self.plant.notes = "Only the prose changed"
        self.plant.save()

        self.assertFalse(_update_entries(self.plant).exists())

    def test_no_free_text_field_is_audited(self):
        for model in (GardenBed, Plant, CareTask, CareLog, Harvest):
            include = set(auditlog.get_model_fields(model)["include_fields"])
            concrete = {f.name for f in model._meta.concrete_fields}
            self.assertTrue(include, model.__name__)
            # Every listed field exists on the model.
            self.assertLessEqual(include, concrete, model.__name__)
            self.assertFalse(include & FREE_TEXT_FIELDS, model.__name__)
