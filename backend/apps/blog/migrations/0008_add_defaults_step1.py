# Generated migration for adding NOT NULL constraints - Step 1/3
# This migration adds temporary defaults to allow safe constraint addition

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import wagtail.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('blog', '0007_add_performance_indexes'),
    ]

    operations = [
        # Step 1: Add temporary defaults to critical fields
        # Note: author field cannot have a default, so we'll handle it differently

        # For BlogPostPage.introduction, add blank=True temporarily
        # This allows the field to be empty during migration, then we'll backfill
        migrations.AlterField(
            model_name='blogpostpage',
            name='introduction',
            field=wagtail.fields.RichTextField(
                blank=True,  # Temporarily allow blank
                help_text="Brief introduction or excerpt"
            ),
        ),

        # For reading_time, add a sensible default
        migrations.AlterField(
            model_name='blogpostpage',
            name='reading_time',
            field=models.PositiveIntegerField(
                null=True,  # Keep nullable for now
                blank=True,
                default=1,  # Temporary default
                help_text="Estimated reading time in minutes (auto-calculated)"
            ),
        ),
    ]
