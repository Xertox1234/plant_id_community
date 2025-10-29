# Generated migration for adding NOT NULL constraints - Step 2/3
# This migration backfills any NULL values with sensible defaults

from django.db import migrations


def backfill_confidence_scores(apps, schema_editor):
    """Backfill NULL confidence_score values with 0.0 (minimum confidence)."""
    PlantIdentificationResult = apps.get_model('plant_identification', 'PlantIdentificationResult')

    # Update any NULL confidence scores to 0.0
    null_count = PlantIdentificationResult.objects.filter(
        confidence_score__isnull=True
    ).update(confidence_score=0.0)

    if null_count > 0:
        print(f"[MIGRATION] Backfilled {null_count} NULL confidence_score values with 0.0")


def backfill_identification_sources(apps, schema_editor):
    """Backfill NULL or empty identification_source values."""
    PlantIdentificationResult = apps.get_model('plant_identification', 'PlantIdentificationResult')

    # Update NULL identification_source to 'ai_combined'
    null_count = PlantIdentificationResult.objects.filter(
        identification_source__isnull=True
    ).update(identification_source='ai_combined')

    # Update empty identification_source to 'ai_combined'
    empty_count = PlantIdentificationResult.objects.filter(
        identification_source=''
    ).update(identification_source='ai_combined')

    total = null_count + empty_count
    if total > 0:
        print(f"[MIGRATION] Backfilled {total} NULL/empty identification_source values with 'ai_combined'")


def reverse_backfill(apps, schema_editor):
    """Reverse migration - no action needed as we can't restore original NULL values."""
    print("[MIGRATION] Reverse migration: Cannot restore original NULL values (data already migrated)")


class Migration(migrations.Migration):

    dependencies = [
        ('plant_identification', '0017_add_defaults_step1'),
    ]

    operations = [
        migrations.RunPython(backfill_confidence_scores, reverse_backfill),
        migrations.RunPython(backfill_identification_sources, reverse_backfill),
    ]
