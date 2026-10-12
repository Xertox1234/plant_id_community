"""Merge disease rows whose names differ only in case (todo 613).

`disease_name` was unique case-sensitively while the diagnosis service looks
names up ignoring case, so 'Black Spot' and 'black spot' could both exist.
0029 makes the name unique ignoring case; this migration first folds every
such group into its oldest row so that constraint can be built on any data.

For each group the oldest row (by `first_diagnosed`, then pk) is kept. Before
the other rows are deleted, everything that points at them moves to it:

- care instructions (FK, CASCADE: deleting first would destroy them). The
  pair (disease, treatment_name) is unique, so an extra row's instruction
  whose name the keeper already has is not moved: its text is appended to
  the keeper's instruction of that name when it says something different,
  and the duplicate row is then dropped (todo 636);
- diagnosis results (FK, SET_NULL: deleting first would orphan them);
- affected plants (M2M: the union of every row's species).

The kept row's `diagnosis_count` becomes the sum of the group's counts. Its
own fields are merged the way the service merges a live diagnosis, so no
variant's content is lost (todo 636): the highest `confidence_score`, the
union of `symptoms['identified']`, either review flag if any row has it, and
every blank field (description, scientific name, prevention tips, reference
image, the JSON lists, a missing symptoms key) filled from the oldest extra
row that has a value.

Merging cannot be undone, so the reverse does nothing.
"""

from django.db import migrations
from django.db.models import Count, F
from django.db.models.functions import Lower

# Fields a merge fills on the keeper when blank, from the oldest extra row
# that has a value (todo 636).
FILL_IF_BLANK = (
    "scientific_name",
    "description",
    "prevention_tips",
    "reference_image",
    "severity_levels",
    "affected_plant_families",
    "seasonal_patterns",
    "environmental_triggers",
)


def _merged_fields(keeper, extras):
    """The keeper's fields with every extra row folded in (todo 636).

    Mirrors the service's live merge: the highest confidence and the union of
    identified symptoms. Beyond that, a review flag set on any row is kept and
    a blank field takes the first value an extra row has.
    """
    rows = [keeper, *extras]
    fields = {
        "confidence_score": max(row.confidence_score for row in rows),
        "expert_reviewed": any(row.expert_reviewed for row in rows),
        "community_confirmed": any(row.community_confirmed for row in rows),
    }
    for name in FILL_IF_BLANK:
        if getattr(keeper, name):
            continue
        filled = next(
            (getattr(row, name) for row in extras if getattr(row, name)), None
        )
        if filled is not None:
            # An ImageField's value is a FieldFile: store its name.
            fields[name] = getattr(filled, "name", filled)

    symptoms = dict(keeper.symptoms) if isinstance(keeper.symptoms, dict) else {}
    identified = list(symptoms.get("identified") or [])
    for row in extras:
        other = row.symptoms if isinstance(row.symptoms, dict) else {}
        for symptom in other.get("identified") or []:
            if symptom not in identified:
                identified.append(symptom)
        for key, value in other.items():
            if key != "identified" and value and not symptoms.get(key):
                symptoms[key] = value
    if identified or "identified" in symptoms:
        symptoms["identified"] = identified
    fields["symptoms"] = symptoms
    return fields


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
        # A dropped instruction whose text differs is appended to the one
        # that is kept, so its advice survives (todo 636).
        keeper_care = CareInstructions.objects.filter(disease_id=keeper.pk).values_list(
            "pk", "treatment_name", "instructions"
        )
        taken = {
            treatment_name: [care_pk, instructions]
            for care_pk, treatment_name, instructions in keeper_care
        }
        duplicate_care_pks = []
        extended = {}
        for care_pk, treatment_name, instructions in (
            CareInstructions.objects.filter(disease_id__in=extra_pks)
            .order_by("pk")
            .values_list("pk", "treatment_name", "instructions")
        ):
            if treatment_name not in taken:
                taken[treatment_name] = [care_pk, instructions]
                continue
            duplicate_care_pks.append(care_pk)
            kept = taken[treatment_name]
            text = (instructions or "").strip()
            if text and text not in kept[1]:
                kept[1] = f"{kept[1].rstrip()}\n\n{text}" if kept[1].strip() else text
                extended[kept[0]] = kept[1]
        CareInstructions.objects.filter(pk__in=duplicate_care_pks).delete()
        for care_pk, instructions in extended.items():
            CareInstructions.objects.filter(pk=care_pk).update(
                instructions=instructions
            )
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
            + sum(row.diagnosis_count for row in extras),
            **_merged_fields(keeper, extras),
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
