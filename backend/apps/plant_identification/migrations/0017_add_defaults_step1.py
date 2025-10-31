# Generated migration for adding NOT NULL constraints - Step 1/3
# This migration adds temporary defaults to allow safe constraint addition

from django.db import migrations, models
from django.core.validators import MinValueValidator, MaxValueValidator


class Migration(migrations.Migration):

    dependencies = [
        ('plant_identification', '0016_update_cascade_behavior'),
    ]

    operations = [
        # Step 1: Add temporary defaults to critical fields
        # These defaults will be removed in Step 3 after NOT NULL is enforced

        migrations.AlterField(
            model_name='plantidentificationresult',
            name='confidence_score',
            field=models.FloatField(
                default=0.0,  # Temporary default for migration
                validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
                help_text="Confidence score (0.0 to 1.0)"
            ),
        ),

        migrations.AlterField(
            model_name='plantidentificationresult',
            name='identification_source',
            field=models.CharField(
                max_length=20,
                default='ai_combined',  # Temporary default for migration
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
