"""
The garden models are audited (todo 571).

``apps/garden_calendar/auditlog.py`` registered five models but nothing
imported it, so no garden model ever wrote a LogEntry. These tests go through
the real app registry: they fail if ``GardenCalendarConfig.ready()`` stops
importing the module. They also pin the owner's scope decision (2026-10-11):
free-text fields such as ``notes`` never land in a LogEntry.
"""

import re

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

    def test_overdue_reschedule_locks_the_tasks_it_reads(self):
        """Todo 606 item 3: the per-row save() above replaced an atomic
        filtered update(), so the read must lock the task rows. Unlocked, a
        task completed or skipped between the read and its save was still
        moved to tomorrow, its notes overwritten and its reminder re-armed.
        Only the task rows are locked, not the joined plant.

        What this proves is the SQL: the read ends in ``FOR UPDATE OF`` the
        task table. It runs no second transaction, so it does not show a task
        completed concurrently being left alone; that rests on PostgreSQL
        re-checking the filter of a locked row (todo 631 #5)."""
        from datetime import timedelta

        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from ..services.care_schedule_service import CareScheduleService

        task = self._task()
        CareTask.objects.filter(pk=task.pk).update(
            scheduled_date=timezone.now() - timedelta(days=10)
        )

        with CaptureQueriesContext(connection) as ctx:
            count = CareScheduleService.reschedule_overdue_tasks(self.user)

        self.assertEqual(count, 1)
        task_table = connection.ops.quote_name(CareTask._meta.db_table)
        reads = [
            q["sql"]
            for q in ctx.captured_queries
            if q["sql"].startswith("SELECT") and f"FROM {task_table}" in q["sql"]
        ]
        self.assertTrue(reads, ctx.captured_queries)
        self.assertTrue(reads[0].endswith(f"FOR UPDATE OF {task_table}"), reads[0])

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

    def test_rows_of_another_owners_plant_the_user_created_are_purged(self):
        """Todo 606 item 4: each operand of ``_garden_objects_of`` is covered.
        A task Alice created and a care log she wrote on Bob's plant are
        matched only by ``created_by=user`` and ``user=user``; Bob's own rows
        on that plant survive."""
        alice, _alices = self._garden("alice_helper")
        bob, bobs = self._garden("bob_owner")
        bob_plant = bobs[1]
        alice_task = CareTask.objects.create(
            plant=bob_plant,
            created_by=alice,
            task_type="watering",
            title="Water Bob's tomato",
            priority="medium",
            scheduled_date=timezone.now(),
        )
        alice_log = CareLog.objects.create(
            plant=bob_plant, user=alice, activity_type="watering"
        )
        alice_rows = [alice_task, alice_log]
        self.assertEqual(self._entries(alice_rows).count(), 2)
        before_bob = self._entries(bobs).count()

        alice.delete()

        self.assertFalse(self._entries(alice_rows).exists())
        self.assertEqual(self._entries(bobs).count(), before_bob)


class GardenAuditlogActorTest(TestCase):
    """Todo 606 item 2 (owner decision 2026-10-11): the garden API records the
    user as each LogEntry's actor, and deleting the account purges every
    garden row the user is the actor of. That covers a bed the user deleted
    before the account, which ownership can no longer match."""

    BEDS = "/api/v1/calendar/api/garden-beds/"

    def _user(self, username):
        return User.objects.create_user(
            username=username,
            email=f"{username}@test.com",
            password="testpass123",  # pragma: allowlist secret
        )

    def _client(self, user):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def _bed_entries(self, pk):
        return LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(GardenBed),
            object_pk=str(pk),
        )

    def test_the_api_records_the_user_as_actor_and_only_inside_the_request(self):
        alice = self._user("alice_actor")
        response = self._client(alice).post(
            self.BEDS, {"name": "Alice bed", "bed_type": "raised"}
        )
        self.assertEqual(response.status_code, 201, response.data)
        bed = GardenBed.objects.get(uuid=response.data["uuid"])

        created = self._bed_entries(bed.pk).get(action=LogEntry.Action.CREATE)
        self.assertEqual(created.actor, alice)

        # The request's actor does not leak into a write after it.
        bed.name = "Renamed outside a request"
        bed.save()
        updated = self._bed_entries(bed.pk).get(action=LogEntry.Action.UPDATE)
        self.assertIsNone(updated.actor)

    def test_rows_of_a_bed_deleted_before_the_account_are_purged(self):
        alice = self._user("alice_gone_bed")
        bob = self._user("bob_stays")
        alice_client = self._client(alice)
        response = alice_client.post(
            self.BEDS, {"name": "alice_gone_bed's bed", "bed_type": "raised"}
        )
        self.assertEqual(response.status_code, 201, response.data)
        bed_uuid = response.data["uuid"]
        bed_pk = GardenBed.objects.get(uuid=bed_uuid).pk
        response = alice_client.patch(f"{self.BEDS}{bed_uuid}/", {"soil_ph": "6.5"})
        self.assertEqual(response.status_code, 200, response.data)
        response = alice_client.delete(f"{self.BEDS}{bed_uuid}/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self._bed_entries(bed_pk).count(), 3)  # CREATE/UPDATE/DELETE

        response = self._client(bob).post(
            self.BEDS, {"name": "Bob bed", "bed_type": "raised"}
        )
        self.assertEqual(response.status_code, 201, response.data)
        bob_bed_pk = GardenBed.objects.get(uuid=response.data["uuid"]).pk

        alice.delete()

        self.assertFalse(self._bed_entries(bed_pk).exists())
        self.assertEqual(self._bed_entries(bob_bed_pk).count(), 1)

    # --- todo 631 #2: every audited garden viewset records the actor -------

    def test_every_garden_viewset_records_the_user_as_actor(self):
        """Todo 631 #2: the tests above drive only the bed viewset. Plant,
        CareTask, CareLog and Harvest writes must name the actor too, or their
        rows keep a NULL actor and escape the purge."""
        from ..api.audit_actor import AuditActorMixin
        from ..api.views import (
            CareLogViewSet,
            CareTaskViewSet,
            GardenBedViewSet,
            HarvestViewSet,
            PlantViewSet,
        )

        for viewset in (
            GardenBedViewSet,
            PlantViewSet,
            CareTaskViewSet,
            CareLogViewSet,
            HarvestViewSet,
        ):
            self.assertTrue(issubclass(viewset, AuditActorMixin), viewset.__name__)

        alice = self._user("alice_every_viewset")
        client = self._client(alice)
        api = "/api/v1/calendar/api/"
        today = timezone.now().date().isoformat()
        response = client.post(
            f"{api}plants/",
            {
                "common_name": "Basil",
                "health_status": "healthy",
                "growth_stage": "seedling",
                "planted_date": today,
            },
        )
        self.assertEqual(response.status_code, 201, response.data)
        plant = Plant.objects.get(uuid=response.data["uuid"])
        writes = {
            CareTask: (
                "care-tasks/",
                {
                    "plant": plant.pk,
                    "task_type": "watering",
                    "title": "Water",
                    "priority": "medium",
                    "scheduled_date": timezone.now().isoformat(),
                },
            ),
            CareLog: ("care-logs/", {"plant": plant.pk, "activity_type": "watering"}),
            Harvest: (
                "harvests/",
                {
                    "plant": plant.pk,
                    "harvest_date": today,
                    "quantity": "1",
                    "unit": "count",
                },
            ),
        }
        created = [plant]
        for model, (path, payload) in writes.items():
            response = client.post(f"{api}{path}", payload)
            self.assertEqual(response.status_code, 201, (model.__name__, response.data))
            if "uuid" in response.data:
                created.append(model.objects.get(uuid=response.data["uuid"]))
            else:
                created.append(model.objects.get(pk=response.data["id"]))

        for obj in created:
            entry = LogEntry.objects.get(
                content_type=ContentType.objects.get_for_model(type(obj)),
                object_pk=str(obj.pk),
                action=LogEntry.Action.CREATE,
            )
            self.assertEqual(entry.actor, alice, type(obj).__name__)


class GardenAuditActorContextTest(TestCase):
    """Todo 631 #4: the garden actor no longer rides on auditlog's
    ``set_actor``, whose receiver uid is ``("set_actor", time.time())``: two
    requests in one clock tick shared a receiver, and the first to finish
    disconnected it from under the other."""

    def setUp(self):
        self.alice = User.objects.create_user(username="ctx_alice", email="a@t.com")
        self.bob = User.objects.create_user(username="ctx_bob", email="b@t.com")

    def _bed(self, owner, name):
        bed = GardenBed.objects.create(owner=owner, name=name, bed_type="raised")
        return LogEntry.objects.get(
            content_type=ContentType.objects.get_for_model(GardenBed),
            object_pk=str(bed.pk),
            action=LogEntry.Action.CREATE,
        )

    def test_overlapping_requests_in_one_clock_tick_keep_their_actors(self):
        """Driven through ``AuditActorMixin`` (todo 643 #5), so the test fails
        if the mixin goes back to auditlog's ``set_actor``: with the clock
        frozen, Bob's request shares Alice's receiver uid, and his finishing
        first disconnects it before Alice writes."""
        import contextvars
        from unittest.mock import patch

        from rest_framework.permissions import IsAuthenticated
        from rest_framework.test import APIRequestFactory, force_authenticate

        def request_as(user):
            request = APIRequestFactory().post("/x/")
            force_authenticate(request, user=user)
            return request

        bob_ctx = contextvars.copy_context()
        entries = {}

        def bob_body():
            entries["bob"] = self._bed(self.bob, "Bob bed")

        bob_view = self._view(bob_body, IsAuthenticated)

        def alice_body():
            # Bob's request starts and finishes inside Alice's.
            bob_ctx.run(bob_view, request_as(self.bob))
            entries["alice"] = self._bed(self.alice, "Alice bed")

        alice_view = self._view(alice_body, IsAuthenticated)
        # Every call sees the same instant, as two requests in one tick do.
        with patch("time.time", return_value=1_700_000_000.0):
            contextvars.copy_context().run(alice_view, request_as(self.alice))

        self.assertEqual(entries["bob"].actor, self.bob)
        self.assertEqual(entries["alice"].actor, self.alice)
        self.assertEqual(entries["alice"].actor_email, "a@t.com")

    def _view(self, body, permission):
        from rest_framework.response import Response
        from rest_framework.views import APIView

        from ..api.audit_actor import AuditActorMixin

        class View(AuditActorMixin, APIView):
            permission_classes = [permission]

            def post(self, request):
                body()
                return Response(status=204)

            def handle_exception(self, exc):
                # Let it escape dispatch(), past the project's handler that
                # would turn it into a 500, so the stack unwinds on a raise.
                raise exc

        return View.as_view()

    def test_a_view_that_raises_does_not_leave_its_actor_behind(self):
        from rest_framework.permissions import IsAuthenticated
        from rest_framework.test import APIRequestFactory, force_authenticate

        from ..api.audit_actor import _garden_actor

        inside = {}

        def body():
            inside["entry"] = self._bed(self.alice, "Written then failed")
            raise ValueError("boom")

        request = APIRequestFactory().post("/x/")
        force_authenticate(request, user=self.alice)
        with self.assertRaises(ValueError):
            self._view(body, IsAuthenticated)(request)

        self.assertEqual(inside["entry"].actor, self.alice)
        self.assertIsNone(_garden_actor.get())
        self.assertIsNone(self._bed(self.alice, "After the failure").actor)

    def test_an_anonymous_request_sets_no_actor(self):
        from rest_framework.permissions import AllowAny
        from rest_framework.test import APIRequestFactory

        inside = {}

        def body():
            inside["entry"] = self._bed(self.alice, "Anonymous write")

        response = self._view(body, AllowAny)(APIRequestFactory().post("/x/"))

        self.assertEqual(response.status_code, 204)
        self.assertIsNone(inside["entry"].actor)


class GardenAuditPurgeChunkingTest(TestCase):
    """Todo 631 #6: the account-deletion purge deletes in bounded chunks, not
    one IN clause over every pk the user ever touched."""

    def test_the_purge_deletes_in_chunks_and_misses_nothing(self):
        from unittest.mock import patch

        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from .. import auditlog as garden_auditlog
        from ..api.audit_actor import garden_audit_actor

        alice = User.objects.create_user(username="chunk_alice", email="c@t.com")
        bob = User.objects.create_user(username="chunk_bob", email="d@t.com")
        gone = []
        with garden_audit_actor(alice):
            for i in range(3):  # beds deleted before the account: actor match
                bed = GardenBed.objects.create(owner=alice, name=f"gone {i}")
                gone.append(bed.pk)
                bed.delete()
            kept = [
                GardenBed.objects.create(owner=alice, name=f"kept {i}").pk
                for i in range(3)
            ]
        bob_bed = GardenBed.objects.create(owner=bob, name="bob")
        bed_type = ContentType.objects.get_for_model(GardenBed)
        alice_rows = LogEntry.objects.filter(
            content_type=bed_type, object_pk__in=[str(pk) for pk in gone + kept]
        )
        self.assertEqual(alice_rows.count(), 9)  # 3 CREATE+DELETE, 3 CREATE

        table = connection.ops.quote_name(LogEntry._meta.db_table)
        with patch.object(
            garden_auditlog, "PURGE_CHUNK_SIZE", 2
        ), CaptureQueriesContext(connection) as ctx:
            alice.delete()

        self.assertFalse(alice_rows.exists())
        self.assertTrue(
            LogEntry.objects.filter(
                content_type=bed_type, object_pk=str(bob_bed.pk)
            ).exists()
        )
        deletes = [
            q["sql"]
            for q in ctx.captured_queries
            if q["sql"].startswith(f"DELETE FROM {table}")
        ]
        # 9 actor rows (every CREATE, and the 3 earlier DELETEs) in chunks of
        # 2, then the cascade's 3 DELETE rows, which have no actor, in chunks
        # of 2: 5 + 2.
        self.assertEqual(len(deletes), 7, deletes)
        for sql in deletes:
            self.assertLessEqual(sql.count(","), 1, sql)

        # Todo 643 #6: the pk SELECTs too. Every object_pk IN list names at
        # most PURGE_CHUNK_SIZE objects, so dropping the per-slice split in
        # purge_garden_audit_entries fails here: its 3 cascade rows would be
        # one IN of 3 kept-bed pks.
        selects = [
            q["sql"]
            for q in ctx.captured_queries
            if q["sql"].startswith("SELECT") and f"FROM {table}" in q["sql"]
        ]
        object_pk_lists = [
            in_list
            for sql in selects
            for in_list in re.findall(r'"object_pk" IN \(([^)]*)\)', sql)
        ]
        # 2 slices, 2 SELECTs each (the second finds nothing left).
        self.assertEqual(len(object_pk_lists), 4, selects)
        for in_list in object_pk_lists:
            self.assertLessEqual(in_list.count(","), 1, in_list)
        # Todo 643 #4: unordered, so no chunk re-sorts the remaining rows.
        for sql in selects:
            self.assertNotIn("ORDER BY", sql, sql)
