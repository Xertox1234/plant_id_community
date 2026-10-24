"""
`optimize_species_database --cleanup-duplicates` (review 2026-05-07 #908).

The duplicates query used `values("scientific_name__iexact")`, which raises
FieldError, so the cleanup (and `--all`, which runs it first) never worked.
Now that it runs, it deletes rows: every reference must move onto the kept
species first, because the FKs are SET_NULL and would silently unlink users'
plants and garden plants.
"""

import datetime
from io import StringIO
from unittest import mock

from apps.garden_calendar.models import Plant as GardenPlant
from apps.users.models import UserPlantCollection
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from ..management.commands import optimize_species_database as command_module
from ..models import PlantDiseaseDatabase, PlantSpecies, UserPlant

User = get_user_model()


def run_cleanup(*extra: str) -> str:
    out = StringIO()
    call_command(
        "optimize_species_database", "--cleanup-duplicates", *extra, stdout=out
    )
    return out.getvalue()


class SpeciesDuplicateCleanupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="grower", email="grower@example.com", password="x" * 20
        )
        self.collection = UserPlantCollection.objects.create(
            user=self.user, name="My Plants"
        )
        self.best = PlantSpecies.objects.create(
            scientific_name="Rosa damascena", identification_count=5
        )
        self.dup = PlantSpecies.objects.create(
            scientific_name="rosa damascena", identification_count=2
        )
        self.dup.tags.add("fragrant")

    def _disease(self, name: str) -> PlantDiseaseDatabase:
        return PlantDiseaseDatabase.objects.create(
            disease_name=name, disease_type="fungal", confidence_score=0.9
        )

    def test_merges_case_variants_and_moves_every_reference(self):
        user_plant = UserPlant.objects.create(
            user=self.user,
            collection=self.collection,
            species=self.dup,
            nickname="Rose",
        )
        garden_plant = GardenPlant.objects.create(
            owner=self.user,
            common_name="Damask rose",
            planted_date=datetime.date(2026, 4, 1),
            plant_species=self.dup,
        )
        only_dup = self._disease("Black spot")
        only_dup.affected_plants.add(self.dup)
        both = self._disease("Powdery mildew")
        both.affected_plants.add(self.best, self.dup)

        output = run_cleanup()

        self.assertIn("Removed 1 duplicate species", output)
        self.assertFalse(PlantSpecies.objects.filter(pk=self.dup.pk).exists())
        user_plant.refresh_from_db()
        garden_plant.refresh_from_db()
        self.assertEqual(user_plant.species, self.best)
        self.assertEqual(garden_plant.plant_species, self.best)
        self.assertEqual(list(only_dup.affected_plants.all()), [self.best])
        self.assertEqual(list(both.affected_plants.all()), [self.best])
        self.best.refresh_from_db()
        self.assertEqual(self.best.identification_count, 7)
        self.assertEqual(list(self.best.tags.names()), ["fragrant"])

    def test_dry_run_reports_references_and_changes_nothing(self):
        UserPlant.objects.create(
            user=self.user,
            collection=self.collection,
            species=self.dup,
            nickname="Rose",
        )

        output = run_cleanup("--dry-run")

        self.assertIn("plant_identification.UserPlant.species", output)
        self.assertIn("Removed 0 duplicate species", output)
        self.assertTrue(PlantSpecies.objects.filter(pk=self.dup.pk).exists())
        self.assertEqual(UserPlant.objects.get().species, self.dup)

    def test_uniqueness_clash_skips_only_that_group(self):
        # Same user, collection and nickname on both variants: moving the
        # duplicate's plant onto the kept species breaks unique_together.
        UserPlant.objects.create(
            user=self.user,
            collection=self.collection,
            species=self.best,
            nickname="Rose",
        )
        UserPlant.objects.create(
            user=self.user,
            collection=self.collection,
            species=self.dup,
            nickname="Rose",
        )
        PlantSpecies.objects.create(scientific_name="Ficus lyrata")
        other_dup = PlantSpecies.objects.create(scientific_name="FICUS LYRATA")

        output = run_cleanup()

        self.assertIn("Skipped Rosa damascena", output)
        self.assertIn("Removed 1 duplicate species", output)
        self.assertTrue(PlantSpecies.objects.filter(pk=self.dup.pk).exists())
        self.assertEqual(UserPlant.objects.filter(species=self.dup).count(), 1)
        self.assertFalse(PlantSpecies.objects.filter(pk=other_dup.pk).exists())

    def test_unmerged_relation_refuses_to_delete(self):
        UserPlant.objects.create(
            user=self.user,
            collection=self.collection,
            species=self.dup,
            nickname="Rose",
        )
        without_user_plant = tuple(
            ref
            for ref in command_module.SPECIES_FK_REFERENCES
            if ref[0] is not UserPlant
        )

        with mock.patch.object(
            command_module, "SPECIES_FK_REFERENCES", without_user_plant
        ):
            with self.assertRaisesMessage(CommandError, "Unmerged references"):
                run_cleanup()

        self.assertTrue(PlantSpecies.objects.filter(pk=self.dup.pk).exists())
        self.assertEqual(UserPlant.objects.get().species, self.dup)
