"""Merge disease rows whose names differ only in case (todo 613).

`disease_name` was unique case-sensitively while the diagnosis service looks
names up ignoring case, so 'Black Spot' and 'black spot' could both exist.
0029 makes the name unique ignoring case; this migration first folds every
such group into its oldest row so that constraint can be built on any data.

For each group the oldest row (by `first_diagnosed`, then pk) is kept. Before
the other rows are deleted, everything that points at them moves to it:

- care instructions (FK, CASCADE: deleting first would destroy them). The
  pair (disease, treatment_name) is unique, so an extra row's instruction
  whose name the keeper already has is dropped and the keeper's is kept;
- diagnosis results (FK, SET_NULL: deleting first would orphan them);
- affected plants (M2M: the union of every row's species).

The kept row's `diagnosis_count` becomes the sum of the group's counts.

Merging cannot be undone, so the reverse does nothing.
"""

from django.db import migrations
from django.db.models import Count, F
from django.db.models.functions import Lower


def merge_case_variant_diseases(apps, schema_editor):
    Disease = apps.get_model("plant_identification", "PlantDiseaseDatabase")
    CareInstructions = apps.get_model("plant_identification", "DiseaseCareInstructions")
    DiseaseResult = apps.get_model("plant_identification", "PlantDiseaseResult")
    AffectedPlant = Disease.affected_plants.through

    duplicate_names = (
        Disease.objects.annotate(name_lower=Lower("disease_name"))
        .values("name_lower")
        .annotate(rows=Count("pk"))
        .filter(rows__gt=1)
        .values_list("name_lower", flat=True)
    )

    for name_lower in list(duplicate_names):
        group = list(
            Disease.objects.annotate(name_lower=Lower("disease_name"))
            .filter(name_lower=name_lower)
            .order_by("first_diagnosed", "pk")
        )
        keeper, extras = group[0], group[1:]
        extra_pks = [row.pk for row in extras]

        # (disease, treatment_name) is unique and the service names every
        # treatment "<Type> Treatment", so the variants usually share names.
        # The keeper's instruction wins; an extra one with a name already on
        # the keeper (or on an earlier extra row) is dropped, the rest move.
        taken = set(
            CareInstructions.objects.filter(disease_id=keeper.pk).values_list(
                "treatment_name", flat=True
            )
        )
        duplicate_care_pks = []
        for care_pk, treatment_name in (
            CareInstructions.objects.filter(disease_id__in=extra_pks)
            .order_by("pk")
            .values_list("pk", "treatment_name")
        ):
            if treatment_name in taken:
                duplicate_care_pks.append(care_pk)
            else:
                taken.add(treatment_name)
        CareInstructions.objects.filter(pk__in=duplicate_care_pks).delete()
        CareInstructions.objects.filter(disease_id__in=extra_pks).update(
            disease_id=keeper.pk
        )
        DiseaseResult.objects.filter(identified_disease_id__in=extra_pks).update(
            identified_disease_id=keeper.pk
        )

        linked = set(
            AffectedPlant.objects.filter(plantdiseasedatabase_id=keeper.pk).values_list(
                "plantspecies_id", flat=True
            )
        )
        to_link = (
            set(
                AffectedPlant.objects.filter(
                    plantdiseasedatabase_id__in=extra_pks
                ).values_list("plantspecies_id", flat=True)
            )
            - linked
        )
        AffectedPlant.objects.bulk_create(
            AffectedPlant(plantdiseasedatabase_id=keeper.pk, plantspecies_id=species)
            for species in sorted(to_link)
        )

        Disease.objects.filter(pk=keeper.pk).update(
            diagnosis_count=F("diagnosis_count")
            + sum(row.diagnosis_count for row in extras)
        )
        Disease.objects.filter(pk__in=extra_pks).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("plant_identification", "0027_remove_dead_cms_and_diagnosis_models"),
    ]

    operations = [
        migrations.RunPython(
            merge_case_variant_diseases, reverse_code=migrations.RunPython.noop
        ),
    ]
