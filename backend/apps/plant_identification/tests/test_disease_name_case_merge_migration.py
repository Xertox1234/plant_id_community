"""0028 folds case-variant disease rows into one before 0029's constraint (todo 613).

`disease_name` was unique case-sensitively, so 'Black Spot' and 'black spot'
could both exist. This winds `plant_identification` back to 0027, seeds both
rows with the historical models, each with a care instruction, a diagnosis
result and an affected plant, and migrates forward through 0028 and 0029 for
real. One row must remain and carry every reference and the summed count.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

BEFORE = ("plant_identification", "0027_remove_dead_cms_and_diagnosis_models")
AFTER = ("plant_identification", "0029_disease_name_lower_unique")


def _seed_disease(old_apps, user, name, species_name, count, age_days):
    Disease = old_apps.get_model("plant_identification", "PlantDiseaseDatabase")
    Care = old_apps.get_model("plant_identification", "DiseaseCareInstructions")
    Species = old_apps.get_model("plant_identification", "PlantSpecies")
    Request = old_apps.get_model("plant_identification", "PlantDiseaseRequest")
    Result = old_apps.get_model("plant_identification", "PlantDiseaseResult")

    disease = Disease.objects.create(
        disease_name=name,
        disease_type="fungal",
        confidence_score=0.8,
        api_source="plant_health",
        diagnosis_count=count,
    )
    # auto_now_add ignores a value passed to create(); set the age after.
    Disease.objects.filter(pk=disease.pk).update(
        first_diagnosed=timezone.now() - timedelta(days=age_days)
    )
    species = Species.objects.create(scientific_name=species_name)
    disease.affected_plants.add(species)
    Care.objects.create(
        disease=disease,
        treatment_name=f"{name} treatment",
        treatment_type="organic",
        instructions="Remove affected leaves.",
    )
    request = Request.objects.create(user_id=user.pk, symptoms_description=name)
    Result.objects.create(
        request=request,
        identified_disease=disease,
        suggested_disease_name=name,
        suggested_disease_type="fungal",
        confidence_score=0.8,
        diagnosis_source="api_plant_health",
    )
    return disease.pk


# transaction=True is unavoidable for MigrationExecutor (DDL cannot run with
# pending trigger events inside the test transaction); docs/rules/testing.md
# allows this one exception, as in apps/users/tests/test_migration_0017_remap.py.
@pytest.mark.django_db(transaction=True)
def test_case_variant_diseases_merge_into_the_oldest_row():
    user = get_user_model().objects.create_user(
        username="mig-0028", email="mig-0028@example.com"
    )
    executor = MigrationExecutor(connection)
    executor.migrate([BEFORE])
    try:
        old_apps = executor.loader.project_state([BEFORE]).apps
        oldest = _seed_disease(old_apps, user, "black spot", "Rosa canina", 2, 10)
        _seed_disease(old_apps, user, "Black Spot", "Rosa gallica", 3, 1)
        # A row with no case variant is left alone.
        lone = _seed_disease(old_apps, user, "Powdery Mildew", "Rosa rugosa", 4, 5)

        executor = MigrationExecutor(connection)
        executor.migrate([AFTER])
    finally:
        # Never leave the test DB on an old schema for later tests.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    from apps.plant_identification.models import (
        DiseaseCareInstructions,
        PlantDiseaseDatabase,
        PlantDiseaseResult,
    )

    merged = PlantDiseaseDatabase.objects.filter(disease_name__iexact="black spot")
    assert list(merged.values_list("pk", flat=True)) == [oldest]
    disease = merged.get()
    assert disease.disease_name == "black spot"
    assert disease.diagnosis_count == 5
    assert sorted(
        disease.affected_plants.values_list("scientific_name", flat=True)
    ) == [
        "Rosa canina",
        "Rosa gallica",
    ]
    assert sorted(
        disease.care_instructions.values_list("treatment_name", flat=True)
    ) == [
        "Black Spot treatment",
        "black spot treatment",
    ]
    assert sorted(
        disease.diagnosis_results.values_list("suggested_disease_name", flat=True)
    ) == [
        "Black Spot",
        "black spot",
    ]
    assert (
        PlantDiseaseResult.objects.filter(identified_disease__isnull=True).count() == 0
    )
    assert DiseaseCareInstructions.objects.count() == 3

    untouched = PlantDiseaseDatabase.objects.get(pk=lone)
    assert untouched.diagnosis_count == 4
    assert PlantDiseaseDatabase.objects.count() == 2

    # 0029's constraint now refuses a new case variant.
    with pytest.raises(IntegrityError), transaction.atomic():
        PlantDiseaseDatabase.objects.create(
            disease_name="BLACK SPOT",
            disease_type="fungal",
            confidence_score=0.8,
        )
