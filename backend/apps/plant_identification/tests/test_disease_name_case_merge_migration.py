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


def _seed_disease(
    old_apps, user, name, species_name, count, age_days, treatment_names=None
):
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
    for treatment_name in treatment_names or [f"{name} treatment"]:
        Care.objects.create(
            disease=disease,
            treatment_name=treatment_name,
            treatment_type="organic",
            instructions=f"{name}: remove affected leaves.",
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


@pytest.mark.django_db(transaction=True)
def test_shared_treatment_name_keeps_the_keepers_instruction():
    """(disease, treatment_name) is unique, and the service names every
    treatment "<Type> Treatment", so case variants usually share one. The
    merge must not re-point a duplicate onto the keeper (IntegrityError would
    abort the deploy): the keeper's instruction stays, the extra's is dropped,
    and the extra's other instructions still move. A dropped instruction whose
    text differs is appended to the kept one, not lost (todo 636)."""
    user = get_user_model().objects.create_user(
        username="mig-0028-shared", email="mig-0028-shared@example.com"
    )
    executor = MigrationExecutor(connection)
    executor.migrate([BEFORE])
    try:
        old_apps = executor.loader.project_state([BEFORE]).apps
        oldest = _seed_disease(
            old_apps,
            user,
            "black spot",
            "Rosa canina",
            2,
            10,
            treatment_names=["Chemical Treatment"],
        )
        _seed_disease(
            old_apps,
            user,
            "Black Spot",
            "Rosa gallica",
            3,
            5,
            treatment_names=["Chemical Treatment", "Organic Treatment"],
        )
        _seed_disease(
            old_apps,
            user,
            "BLACK SPOT",
            "Rosa rugosa",
            1,
            1,
            treatment_names=["Organic Treatment", "Cultural Treatment"],
        )

        executor = MigrationExecutor(connection)
        executor.migrate([AFTER])
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    from apps.plant_identification.models import (
        DiseaseCareInstructions,
        PlantDiseaseDatabase,
    )

    disease = PlantDiseaseDatabase.objects.get(disease_name__iexact="black spot")
    assert disease.pk == oldest
    assert disease.diagnosis_count == 6
    care = dict(disease.care_instructions.values_list("treatment_name", "instructions"))
    assert care == {
        "Chemical Treatment": (
            "black spot: remove affected leaves.\n\n"
            "Black Spot: remove affected leaves."
        ),
        "Organic Treatment": (
            "Black Spot: remove affected leaves.\n\n"
            "BLACK SPOT: remove affected leaves."
        ),
        "Cultural Treatment": "BLACK SPOT: remove affected leaves.",
    }
    assert DiseaseCareInstructions.objects.count() == 3
    assert disease.diagnosis_results.count() == 3


@pytest.mark.django_db(transaction=True)
def test_merge_keeps_the_extras_fields():
    """The keeper is the oldest row, but the extras' content survives (todo
    636): the highest confidence, the union of identified symptoms, any review
    flag, and every blank field filled from the oldest extra with a value. An
    instruction with the same name and the same text is not duplicated."""
    user = get_user_model().objects.create_user(
        username="mig-0028-fields", email="mig-0028-fields@example.com"
    )
    executor = MigrationExecutor(connection)
    executor.migrate([BEFORE])
    try:
        old_apps = executor.loader.project_state([BEFORE]).apps
        Disease = old_apps.get_model("plant_identification", "PlantDiseaseDatabase")
        Care = old_apps.get_model("plant_identification", "DiseaseCareInstructions")
        oldest = _seed_disease(
            old_apps, user, "black spot", "Rosa canina", 1, 10, ["Organic Treatment"]
        )
        middle = _seed_disease(
            old_apps, user, "Black Spot", "Rosa gallica", 1, 5, ["Organic Treatment"]
        )
        newest = _seed_disease(old_apps, user, "BLACK SPOT", "Rosa rugosa", 1, 1)
        Disease.objects.filter(pk=oldest).update(
            confidence_score=0.6,
            description="Kept description.",
            symptoms={"identified": ["black spots"]},
        )
        Disease.objects.filter(pk=middle).update(
            confidence_score=0.95,
            description="Middle description.",
            prevention_tips="Water at the base.",
            expert_reviewed=True,
            symptoms={"identified": ["yellow leaves", "black spots"]},
            environmental_triggers=["humidity"],
        )
        Disease.objects.filter(pk=newest).update(
            confidence_score=0.7,
            scientific_name="Diplocarpon rosae",
            prevention_tips="Newest tips.",
            community_confirmed=True,
            reference_image="diseases/reference/black-spot.jpg",
            symptoms={"identified": ["leaf drop"], "api_data": {"id": "x"}},
        )
        # Same name and same text as the keeper's: dropped, nothing appended.
        Care.objects.filter(disease_id=middle).update(
            instructions="black spot: remove affected leaves."
        )

        executor = MigrationExecutor(connection)
        executor.migrate([AFTER])
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    from apps.plant_identification.models import PlantDiseaseDatabase

    disease = PlantDiseaseDatabase.objects.get(disease_name__iexact="black spot")
    assert disease.pk == oldest
    assert disease.diagnosis_count == 3
    assert disease.confidence_score == 0.95
    assert disease.symptoms == {
        "identified": ["black spots", "yellow leaves", "leaf drop"],
        "api_data": {"id": "x"},
    }
    # The keeper's own value wins; a blank one takes the oldest extra's.
    assert disease.description == "Kept description."
    assert disease.prevention_tips == "Water at the base."
    assert disease.scientific_name == "Diplocarpon rosae"
    assert disease.environmental_triggers == ["humidity"]
    assert disease.reference_image.name == "diseases/reference/black-spot.jpg"
    assert disease.expert_reviewed is True
    assert disease.community_confirmed is True
    care = dict(disease.care_instructions.values_list("treatment_name", "instructions"))
    assert care == {
        "Organic Treatment": "black spot: remove affected leaves.",
        "BLACK SPOT treatment": "BLACK SPOT: remove affected leaves.",
    }
