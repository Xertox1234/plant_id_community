"""
`PlantDiseaseDatabase.diagnosis_count` must not lose increments (todo 467).

Two diagnoses of the same disease that overlap each read the row, then each
write back what they read plus one. With `count += 1` in Python the second
write overwrites the first and one diagnosis is never counted. The increment
has to happen in the database (`F("diagnosis_count") + 1`).

The overlap is reproduced deterministically: two instances of the same row are
loaded before either update runs, which is exactly the state two concurrent
requests are in.
"""

import re
from unittest import mock

from apps.plant_identification.constants import DISEASE_NAME_LOWER_UNIQUE
from apps.plant_identification.models import (
    PlantDiseaseDatabase,
    PlantDiseaseRequest,
    PlantDiseaseResult,
    PlantSpecies,
)
from apps.plant_identification.services.disease_diagnosis_service import (
    DiseaseAutostorageService,
)
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

User = get_user_model()


class DiagnosisCountIncrementTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="countuser", email="count@example.com")
        self.disease = PlantDiseaseDatabase.objects.create(
            disease_name="Powdery Mildew",
            disease_type="fungal",
            confidence_score=0.6,
            api_source="plant_health",
            diagnosis_count=1,
        )
        request = PlantDiseaseRequest.objects.create(
            user=user,
            status="diagnosed",
            symptoms_description="White powdery coating on leaves",
        )
        self.result = PlantDiseaseResult.objects.create(
            request=request,
            suggested_disease_name="Powdery Mildew",
            suggested_disease_type="fungal",
            confidence_score=0.7,
            diagnosis_source="api_plant_health",
        )
        self.service = DiseaseAutostorageService()

    def test_overlapping_updates_both_count(self):
        # Both "requests" read the row before either writes.
        first = PlantDiseaseDatabase.objects.get(pk=self.disease.pk)
        second = PlantDiseaseDatabase.objects.get(pk=self.disease.pk)

        self.service._update_existing_disease(first, self.result)
        self.service._update_existing_disease(second, self.result)

        self.disease.refresh_from_db()
        # 1 initial + 2 diagnoses. The read-modify-write version gives 2.
        self.assertEqual(self.disease.diagnosis_count, 3)

    def test_returned_instance_holds_the_stored_integer(self):
        updated = self.service._update_existing_disease(
            PlantDiseaseDatabase.objects.get(pk=self.disease.pk), self.result
        )
        # Not an unevaluated F() expression: callers log and serialize it.
        self.assertIsInstance(updated.diagnosis_count, int)
        self.assertEqual(updated.diagnosis_count, 2)

    def test_store_disease_if_qualified_increments_existing(self):
        stored = self.service.store_disease_if_qualified(self.result)

        self.assertIsNotNone(stored)
        self.assertEqual(stored.pk, self.disease.pk)
        self.disease.refresh_from_db()
        self.assertEqual(self.disease.diagnosis_count, 2)


class DiagnosisMergeStaleInstanceTest(TestCase):
    """Confidence and symptoms must not be lost to a stale instance (todo 568).

    `diagnosis_count` was made atomic in todo 467, but the full-row save()
    still wrote back confidence_score and symptoms from the copy each request
    had read. The overlap is reproduced as above: both copies are loaded
    before either update runs.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="mergeuser", email="merge@example.com"
        )
        self.disease = PlantDiseaseDatabase.objects.create(
            disease_name="Leaf Spot",
            disease_type="fungal",
            confidence_score=0.6,
            api_source="plant_health",
            diagnosis_count=1,
            symptoms={"identified": ["brown spots"]},
        )
        self.service = DiseaseAutostorageService()

    def _result(self, confidence, symptoms):
        request = PlantDiseaseRequest.objects.create(
            user=self.user,
            status="diagnosed",
            symptoms_description="Spots on leaves",
        )
        return PlantDiseaseResult.objects.create(
            request=request,
            suggested_disease_name="Leaf Spot",
            suggested_disease_type="fungal",
            confidence_score=confidence,
            symptoms_identified=symptoms,
            diagnosis_source="api_plant_health",
        )

    def test_overlapping_updates_keep_both_symptoms_and_higher_confidence(self):
        high = self._result(0.9, ["yellow halo"])
        low = self._result(0.7, ["leaf drop"])
        first = PlantDiseaseDatabase.objects.get(pk=self.disease.pk)
        second = PlantDiseaseDatabase.objects.get(pk=self.disease.pk)

        self.service._update_existing_disease(first, high)
        self.service._update_existing_disease(second, low)

        self.disease.refresh_from_db()
        # The stale-copy version gives 0.7 and drops "yellow halo".
        self.assertEqual(self.disease.confidence_score, 0.9)
        self.assertEqual(
            sorted(self.disease.symptoms["identified"]),
            ["brown spots", "leaf drop", "yellow halo"],
        )
        self.assertEqual(self.disease.diagnosis_count, 3)

    def test_update_writes_only_the_merged_fields(self):
        stale = PlantDiseaseDatabase.objects.get(pk=self.disease.pk)
        PlantDiseaseDatabase.objects.filter(pk=self.disease.pk).update(
            description="Edited by a moderator"
        )

        self.service._update_existing_disease(stale, self._result(0.8, []))

        self.disease.refresh_from_db()
        self.assertEqual(self.disease.description, "Edited by a moderator")

    def test_update_sets_exactly_the_merged_columns(self):
        # The test above cannot see update_fields: the merge re-reads a fresh
        # row, so a full save() would also keep the moderator's text (todo
        # 594). Pin the UPDATE's SET list instead.
        table = PlantDiseaseDatabase._meta.db_table
        with CaptureQueriesContext(connection) as ctx:
            self.service._update_existing_disease(
                PlantDiseaseDatabase.objects.get(pk=self.disease.pk),
                self._result(0.8, ["wilting"]),
            )

        updates = [
            q["sql"]
            for q in ctx.captured_queries
            if q["sql"].lstrip().upper().startswith("UPDATE") and table in q["sql"]
        ]
        self.assertEqual(len(updates), 1, ctx.captured_queries)
        set_clause = re.search(r"\bSET\b(.*)\bWHERE\b", updates[0], re.S).group(1)
        columns = set(re.findall(r'"(\w+)"\s*=', set_clause))
        self.assertEqual(
            columns,
            {"diagnosis_count", "confidence_score", "symptoms", "updated_at"},
        )

    def test_store_disease_if_qualified_locks_the_existing_row(self):
        result = self._result(0.8, ["wilting"])

        with CaptureQueriesContext(connection) as ctx:
            stored = self.service.store_disease_if_qualified(result)

        self.assertEqual(stored.pk, self.disease.pk)
        table = PlantDiseaseDatabase._meta.db_table
        sqls = [q["sql"] for q in ctx.captured_queries]
        locks = [
            i
            for i, sql in enumerate(sqls)
            if sql.lstrip().upper().startswith("SELECT")
            and table in sql
            and "FOR UPDATE" in sql.upper()
        ]
        writes = [
            i
            for i, sql in enumerate(sqls)
            if sql.lstrip().upper().startswith("UPDATE") and table in sql
        ]
        # One lock, taken by the merge re-read, before the one merge write
        # (todo 594): the name lookup no longer takes a second one.
        self.assertEqual(len(locks), 1, sqls)
        self.assertEqual(len(writes), 1, sqls)
        self.assertLess(locks[0], writes[0], sqls)


class DiagnosisFirstCreateRaceTest(TestCase):
    """Two first diagnoses of a new disease must both be counted (todo 594).

    A row lock cannot cover a row that does not exist yet: both requests miss
    the lookup and both insert. The loser hits the disease-name constraint,
    unique ignoring case (todo 613). The race is reproduced deterministically: the lookup reports
    no row although the winner's row is already committed.
    """

    def setUp(self):
        user = User.objects.create_user(username="raceuser", email="race@example.com")
        request = PlantDiseaseRequest.objects.create(
            user=user,
            status="diagnosed",
            symptoms_description="Black spots on leaves",
        )
        self.result = PlantDiseaseResult.objects.create(
            request=request,
            suggested_disease_name="Black Spot",
            suggested_disease_type="fungal",
            confidence_score=0.9,
            symptoms_identified=["black spots"],
            diagnosis_source="api_plant_health",
        )
        self.service = DiseaseAutostorageService()

    def test_losing_create_merges_into_the_winners_row(self):
        # The winner committed between this request's lookup and its insert.
        winner = PlantDiseaseDatabase.objects.create(
            disease_name="Black Spot",
            disease_type="fungal",
            confidence_score=0.6,
            api_source="plant_health",
            diagnosis_count=1,
            symptoms={"identified": ["yellow leaves"]},
        )
        real_lookup = DiseaseAutostorageService._find_existing_disease
        calls = []

        def racing_lookup(service, name):
            calls.append(name)
            return None if len(calls) == 1 else real_lookup(service, name)

        with mock.patch.object(
            DiseaseAutostorageService,
            "_find_existing_disease",
            autospec=True,
            side_effect=racing_lookup,
        ):
            stored = self.service.store_disease_if_qualified(self.result)

        # The old code swallowed the IntegrityError and returned None.
        self.assertIsNotNone(stored)
        self.assertEqual(stored.pk, winner.pk)
        self.assertEqual(len(calls), 2)
        winner.refresh_from_db()
        self.assertEqual(winner.diagnosis_count, 2)
        self.assertEqual(winner.confidence_score, 0.9)
        self.assertEqual(
            sorted(winner.symptoms["identified"]), ["black spots", "yellow leaves"]
        )
        self.result.refresh_from_db()
        self.assertTrue(self.result.stored_to_database)
        self.assertEqual(PlantDiseaseDatabase.objects.count(), 1)

    def test_integrity_error_without_a_matching_row_is_not_a_merge(self):
        with mock.patch.object(
            DiseaseAutostorageService,
            "_create_new_disease",
            side_effect=IntegrityError("some other constraint"),
        ):
            stored = self.service.store_disease_if_qualified(self.result)

        self.assertIsNone(stored)
        self.result.refresh_from_db()
        self.assertFalse(self.result.stored_to_database)
        self.assertEqual(PlantDiseaseDatabase.objects.count(), 0)

    def test_first_diagnosis_creates_the_row(self):
        stored = self.service.store_disease_if_qualified(self.result)

        self.assertIsNotNone(stored)
        self.assertEqual(stored.disease_name, "Black Spot")
        self.assertEqual(stored.diagnosis_count, 1)


class DiseaseNameCaseFollowupsTest(TestCase):
    """Follow-ups from the PR #1059 review (todo 613)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="caseuser", email="case@example.com"
        )
        self.service = DiseaseAutostorageService()

    def _result(self, name, species=None):
        request = PlantDiseaseRequest.objects.create(
            user=self.user,
            status="diagnosed",
            symptoms_description="Spots on leaves",
            plant_species=species,
        )
        return PlantDiseaseResult.objects.create(
            request=request,
            suggested_disease_name=name,
            suggested_disease_type="fungal",
            confidence_score=0.9,
            symptoms_identified=["black spots"],
            diagnosis_source="api_plant_health",
        )

    def _disease(self, name):
        return PlantDiseaseDatabase.objects.create(
            disease_name=name,
            disease_type="fungal",
            confidence_score=0.6,
            api_source="plant_health",
            diagnosis_count=1,
        )

    def _store_racing(self, result):
        """Store `result` as if the winner committed after its first lookup."""
        real_lookup = DiseaseAutostorageService._find_existing_disease
        calls = []

        def racing_lookup(service, name):
            calls.append(name)
            return None if len(calls) == 1 else real_lookup(service, name)

        with mock.patch.object(
            DiseaseAutostorageService,
            "_find_existing_disease",
            autospec=True,
            side_effect=racing_lookup,
        ):
            return self.service.store_disease_if_qualified(result)

    def test_name_is_unique_ignoring_case(self):
        # Item 1: the case-sensitive unique let both rows in.
        self._disease("Black Spot")
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._disease("black spot")

    def test_losing_create_with_another_case_merges(self):
        # Item 1: concurrent 'black spot' and 'Black Spot' first diagnoses.
        winner = self._disease("black spot")

        stored = self._store_racing(self._result("Black Spot"))

        self.assertIsNotNone(stored)
        self.assertEqual(stored.pk, winner.pk)
        winner.refresh_from_db()
        self.assertEqual(winner.diagnosis_count, 2)
        self.assertEqual(PlantDiseaseDatabase.objects.count(), 1)

    def test_other_integrity_error_is_not_merged_into_a_same_name_row(self):
        # Item 2: only the name constraint is a merge, even if the row exists.
        existing = self._disease("Black Spot")
        result = self._result("Black Spot")

        with mock.patch.object(
            DiseaseAutostorageService,
            "_create_new_disease",
            side_effect=IntegrityError("some other constraint"),
        ):
            stored = self._store_racing(result)

        self.assertIsNone(stored)
        existing.refresh_from_db()
        self.assertEqual(existing.diagnosis_count, 1)
        result.refresh_from_db()
        self.assertFalse(result.stored_to_database)

    def test_merge_links_the_diagnosis_species(self):
        # Item 3: a merged diagnosis records its species, like a first one.
        winner = self._disease("Black Spot")
        species = PlantSpecies.objects.create(scientific_name="Rosa gallica")

        stored = self._store_racing(self._result("Black Spot", species=species))

        self.assertEqual(stored.pk, winner.pk)
        self.assertEqual(list(winner.affected_plants.all()), [species])

    def test_existing_row_merge_links_the_diagnosis_species(self):
        winner = self._disease("Black Spot")
        species = PlantSpecies.objects.create(scientific_name="Rosa canina")

        stored = self.service.store_disease_if_qualified(
            self._result("black spot", species=species)
        )

        self.assertEqual(stored.pk, winner.pk)
        self.assertEqual(list(winner.affected_plants.all()), [species])

    def test_row_deleted_after_lookup_is_created_again(self):
        # Item 4: the old code raised DoesNotExist, swallowed it, returned None.
        gone = self._disease("Black Spot")
        stale = PlantDiseaseDatabase.objects.get(pk=gone.pk)
        PlantDiseaseDatabase.objects.filter(pk=gone.pk).delete()
        calls = []

        def stale_lookup(service, name):
            calls.append(name)
            return stale if len(calls) == 1 else None

        result = self._result("Black Spot")
        with mock.patch.object(
            DiseaseAutostorageService,
            "_find_existing_disease",
            autospec=True,
            side_effect=stale_lookup,
        ):
            stored = self.service.store_disease_if_qualified(result)

        self.assertIsNotNone(stored)
        self.assertNotEqual(stored.pk, gone.pk)
        self.assertEqual(stored.diagnosis_count, 1)
        self.assertEqual(PlantDiseaseDatabase.objects.count(), 1)
        result.refresh_from_db()
        self.assertTrue(result.stored_to_database)


class DiseaseMergeFollowupsTest(TestCase):
    """Follow-ups from the PR #1081 review (todo 636)."""

    def setUp(self):
        user = User.objects.create_user(
            username="followuser", email="follow@example.com"
        )
        request = PlantDiseaseRequest.objects.create(
            user=user,
            status="diagnosed",
            symptoms_description="Black spots on leaves",
        )
        self.result = PlantDiseaseResult.objects.create(
            request=request,
            suggested_disease_name="Black Spot",
            suggested_disease_type="fungal",
            confidence_score=0.9,
            symptoms_identified=["black spots"],
            diagnosis_source="api_plant_health",
        )
        self.service = DiseaseAutostorageService()

    @staticmethod
    def _collision():
        # No psycopg __cause__: the message alone names the constraint, as
        # SQLite's "UNIQUE constraint failed: index '...'" does.
        return IntegrityError(
            f"UNIQUE constraint failed: index '{DISEASE_NAME_LOWER_UNIQUE}'"
        )

    def test_name_collision_is_recognised_without_psycopg_diag(self):
        # Item 4: a driver without diag.constraint_name still merges.
        self.assertTrue(DiseaseAutostorageService._is_name_collision(self._collision()))
        self.assertFalse(
            DiseaseAutostorageService._is_name_collision(
                IntegrityError("some other constraint")
            )
        )

    def test_diag_without_a_constraint_is_not_a_collision(self):
        # Todo 646: psycopg's diag is there but names no constraint (NOT NULL,
        # for one). Its DETAIL echoes the row, so a disease name holding the
        # constraint name must not be read as a collision.
        cause = Exception("driver error")
        cause.diag = mock.Mock(constraint_name=None)
        exc = IntegrityError(
            "null value in column violates not-null constraint\n"
            f"DETAIL:  Failing row contains ({DISEASE_NAME_LOWER_UNIQUE}, null)."
        )
        exc.__cause__ = cause
        self.assertFalse(DiseaseAutostorageService._is_name_collision(exc))

        cause.diag = mock.Mock(constraint_name=DISEASE_NAME_LOWER_UNIQUE)
        self.assertTrue(DiseaseAutostorageService._is_name_collision(exc))

    def test_real_not_null_error_echoing_the_name_is_not_a_collision(self):
        # Todo 646: the same case against the real database.
        if connection.vendor != "postgresql":
            self.skipTest("psycopg diag is PostgreSQL only")
        with self.assertRaises(IntegrityError) as ctx, transaction.atomic():
            PlantDiseaseDatabase.objects.create(
                disease_name=DISEASE_NAME_LOWER_UNIQUE,
                disease_type=None,
                confidence_score=0.5,
                api_source="plant_health",
            )
        self.assertIn(DISEASE_NAME_LOWER_UNIQUE, str(ctx.exception))
        self.assertFalse(DiseaseAutostorageService._is_name_collision(ctx.exception))

    def test_collision_whose_row_is_gone_creates_it_again(self):
        # Item 3: a name collision whose re-lookup finds nothing (the winner
        # was deleted again) used to re-raise and drop the diagnosis.
        real_create = DiseaseAutostorageService._create_new_disease
        calls = []

        def colliding_create(service, result):
            calls.append(result.pk)
            if len(calls) == 1:
                raise self._collision()
            return real_create(service, result)

        with mock.patch.object(
            DiseaseAutostorageService,
            "_create_new_disease",
            autospec=True,
            side_effect=colliding_create,
        ):
            stored = self.service.store_disease_if_qualified(self.result)

        self.assertIsNotNone(stored)
        self.assertEqual(len(calls), 2)
        self.assertEqual(stored.diagnosis_count, 1)
        self.assertEqual(PlantDiseaseDatabase.objects.count(), 1)
        self.result.refresh_from_db()
        self.assertTrue(self.result.stored_to_database)

    def test_collision_whose_row_vanishes_at_the_locked_read_creates_it_again(self):
        # Item 2: the winner is found, then deleted before the locked re-read.
        # DoesNotExist reached the outer except and the diagnosis was dropped.
        gone = PlantDiseaseDatabase.objects.create(
            disease_name="Black Spot",
            disease_type="fungal",
            confidence_score=0.6,
            api_source="plant_health",
            diagnosis_count=1,
        )
        stale = PlantDiseaseDatabase.objects.get(pk=gone.pk)
        real_create = DiseaseAutostorageService._create_new_disease
        lookups = []
        creates = []

        def racing_lookup(service, name):
            lookups.append(name)
            if len(lookups) == 1:
                return None
            # The winner's row is found, then deleted before the merge.
            PlantDiseaseDatabase.objects.filter(pk=gone.pk).delete()
            return stale

        def colliding_create(service, result):
            creates.append(result.pk)
            if len(creates) == 1:
                raise self._collision()
            return real_create(service, result)

        with mock.patch.object(
            DiseaseAutostorageService,
            "_find_existing_disease",
            autospec=True,
            side_effect=racing_lookup,
        ), mock.patch.object(
            DiseaseAutostorageService,
            "_create_new_disease",
            autospec=True,
            side_effect=colliding_create,
        ):
            stored = self.service.store_disease_if_qualified(self.result)

        self.assertIsNotNone(stored)
        self.assertNotEqual(stored.pk, gone.pk)
        self.assertEqual(len(lookups), 2)
        self.assertEqual(len(creates), 2)
        self.assertEqual(PlantDiseaseDatabase.objects.count(), 1)
        self.result.refresh_from_db()
        self.assertTrue(self.result.stored_to_database)

    def test_second_collision_surfaces(self):
        with mock.patch.object(
            DiseaseAutostorageService,
            "_create_new_disease",
            side_effect=self._collision(),
        ) as create:
            stored = self.service.store_disease_if_qualified(self.result)

        # Todo 646: the first collision is retried exactly once, and the
        # second one surfaces. Re-raising on the first collision would also
        # return None, so the call count is what pins the contract.
        self.assertEqual(create.call_count, 2)
        self.assertIsNone(stored)
        self.result.refresh_from_db()
        self.assertFalse(self.result.stored_to_database)
