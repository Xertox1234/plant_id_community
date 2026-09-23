"""Remove dead Plant CMS v2 and diagnosis-side models (todo 405 slice 3).

Neither client used any of these, and slices 1-2 removed their APIs:

- Plant CMS v2 (Wagtail): PlantCareGuide and PlantCategory snippets, and the
  PlantSpeciesPage and PlantCategoryIndexPage pages.
- Diagnosis extras: PlantDiseaseVote, SavedDiagnosis and TreatmentAttempt.
- Batch identification: the four Batch* models (never had an API or admin).

Production evidence (2026-09-23, `railway ssh --service plant_id_community`
running `count()` per model): all 11 held 0 rows.

After the generated DeleteModel ops, the models' content types are removed
through the ORM, so their auth permissions cascade. Irreversible by nature,
so the reverse is a no-op.
"""

from django.db import migrations

REMOVED_MODELS = [
    "plantcareguide",
    "plantcategory",
    "plantcategoryindexpage",
    "plantdiseasevote",
    "plantspeciespage",
    "saveddiagnosis",
    "treatmentattempt",
    "batchidentificationcomparison",
    "batchidentificationimage",
    "batchidentificationrequest",
    "batchprocessingqueue",
]


def delete_removed_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(
        app_label="plant_identification", model__in=REMOVED_MODELS
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("plant_identification", "0026_add_plant_disease_vote"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        # Hand-ordered, not the autodetector's field-by-field output: that
        # removed TreatmentAttempt.saved_diagnosis after the treatments_tried
        # M2M (through TreatmentAttempt) had already dropped it from state
        # (FieldDoesNotExist). Drop the through-M2M first, then delete models
        # child-first; DeleteModel drops each table with its indexes and FKs.
        migrations.RemoveField(model_name="saveddiagnosis", name="treatments_tried"),
        migrations.DeleteModel(name="TreatmentAttempt"),
        migrations.DeleteModel(name="SavedDiagnosis"),
        migrations.DeleteModel(name="PlantDiseaseVote"),
        migrations.DeleteModel(name="PlantSpeciesPage"),
        migrations.DeleteModel(name="PlantCategoryIndexPage"),
        migrations.DeleteModel(name="PlantCategory"),
        migrations.DeleteModel(name="PlantCareGuide"),
        migrations.DeleteModel(name="BatchIdentificationComparison"),
        migrations.DeleteModel(name="BatchIdentificationImage"),
        migrations.DeleteModel(name="BatchProcessingQueue"),
        migrations.DeleteModel(name="BatchIdentificationRequest"),
        migrations.RunPython(
            delete_removed_content_types, reverse_code=migrations.RunPython.noop
        ),
    ]
