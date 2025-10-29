# Generated migration for adding NOT NULL constraints - Step 3/3
# This migration adds NOT NULL constraints and removes temporary defaults

from django.db import migrations, models
from django.core.validators import MinValueValidator, MaxValueValidator


class Migration(migrations.Migration):

    dependencies = [
        ('plant_identification', '0018_backfill_critical_fields_step2'),
    ]

    operations = [
        # Step 3: Add NOT NULL constraints and remove temporary defaults
        # At this point all NULL values have been backfilled

        migrations.AlterField(
            model_name='plantidentificationresult',
            name='confidence_score',
            field=models.FloatField(
                null=False,  # ✅ NOT NULL enforced
                blank=False,  # ✅ Required in forms
                validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
                help_text="Confidence score (0.0 to 1.0)"
            ),
        ),

        migrations.AlterField(
            model_name='plantidentificationresult',
            name='identification_source',
            field=models.CharField(
                max_length=20,
                null=False,  # ✅ NOT NULL enforced
                blank=False,  # ✅ Required in forms
                choices=[
                    ('ai_trefle', 'AI - Trefle API'),
                    ('ai_plantnet', 'AI - PlantNet API'),
                    ('ai_combined', 'AI - Combined APIs'),
                    ('community', 'Community Identification'),
                    ('expert', 'Expert Identification'),
                    ('user_manual', 'Manual User Entry'),
                ],
            ),
        ),
    ]
