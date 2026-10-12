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
from django.db import models
from django.db.models import Q
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

    def test_overdue_reschedule_writes_update_logentry(self):
        """Todo 586 #6: the bulk reschedule used QuerySet.update(), which
        sends no save signal, so it changed scheduled_date unaudited."""
        from datetime import timedelta

        from ..services.care_schedule_service import CareScheduleService

        task = self._task()
        CareTask.objects.filter(pk=task.pk).update(
            scheduled_date=timezone.now() - timedelta(days=10)
        )

        count = CareScheduleService.reschedule_overdue_tasks(self.user)

        self.assertEqual(count, 1)
        entries = list(_update_entries(task))
        self.assertEqual(len(entries), 1)
        self.assertIn("scheduled_date", entries[0].changes_dict)

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
            # Todo 586 #5: a prose field under any other name is a TextField
            # (or a JSON blob); the name list alone would let it through.
            for name in include:
                field = model._meta.get_field(name)
                self.assertNotIsInstance(
                    field, (models.TextField, models.JSONField), f"{model}.{name}"
                )


class GardenAuditlogPurgeOnAccountDeletionTest(TestCase):
    """Todo 586 (owner decision 2026-10-11): deleting an account purges every
    LogEntry of the user's garden objects, including the DELETE rows the
    cascade writes, and leaves other users' trails alone."""

    def _garden(self, username):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@test.com",
            password="testpass123",  # pragma: allowlist secret
        )
        bed = GardenBed.objects.create(owner=user, name=f"{username} bed")
        plant = Plant.objects.create(
            garden_bed=bed,
            common_name="Tomato",
            health_status="healthy",
            growth_stage="seedling",
            planted_date=timezone.now().date(),
        )
        task = CareTask.objects.create(
            plant=plant,
            created_by=user,
            task_type="watering",
            title="Water",
            priority="medium",
            scheduled_date=timezone.now(),
        )
        log = CareLog.objects.create(plant=plant, user=user, activity_type="watering")
        harvest = Harvest.objects.create(
            plant=plant, harvest_date=timezone.now().date(), quantity=1, unit="count"
        )
        plant.health_status = "stressed"
        plant.save()  # an UPDATE entry too
        return user, [bed, plant, task, log, harvest]

    def _entries(self, objects):
        match = Q()
        for obj in objects:
            match |= Q(
                content_type=ContentType.objects.get_for_model(type(obj)),
                object_pk=str(obj.pk),
            )
        return LogEntry.objects.filter(match)

    def test_deleting_a_user_purges_their_garden_logentries(self):
        alice, alices = self._garden("alice_purge")
        bob, bobs = self._garden("bob_keep")
        self.assertTrue(self._entries(alices).exists())
        before_bob = self._entries(bobs).count()
        self.assertGreaterEqual(before_bob, 6)  # 5 CREATE + 1 UPDATE

        alice.delete()

        # No CREATE, UPDATE or cascade-written DELETE row survives.
        self.assertFalse(self._entries(alices).exists())
        # GardenBed's object_repr carried the username. (The users app's own
        # User entries are outside the garden purge.)
        garden_types = [
            ContentType.objects.get_for_model(m)
            for m in (GardenBed, Plant, CareTask, CareLog, Harvest)
        ]
        self.assertFalse(
            LogEntry.objects.filter(
                content_type__in=garden_types, object_repr__contains="alice_purge"
            ).exists()
        )
        self.assertEqual(self._entries(bobs).count(), before_bob)

    def test_a_queryset_delete_purges_too(self):
        alice, alices = self._garden("alice_qs")

        User.objects.filter(pk=alice.pk).delete()

        self.assertFalse(self._entries(alices).exists())

    def test_deleting_a_plant_alone_keeps_its_trail(self):
        """Only account deletion purges; an ordinary delete is audited."""
        alice, alices = self._garden("alice_plant")
        plant = alices[1]
        pk = str(plant.pk)  # delete() sets plant.pk to None

        plant.delete()

        self.assertTrue(
            LogEntry.objects.filter(
                content_type=ContentType.objects.get_for_model(Plant),
                object_pk=pk,
                action=LogEntry.Action.DELETE,
            ).exists()
        )
