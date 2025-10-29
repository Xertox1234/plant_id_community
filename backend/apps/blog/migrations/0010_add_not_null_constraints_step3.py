# Generated migration for adding NOT NULL constraints - Step 3/3
# This migration adds NOT NULL constraints and removes temporary defaults

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import wagtail.fields


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0009_backfill_critical_fields_step2'),
    ]

    operations = [
        # Step 3: Add NOT NULL constraints
        # At this point all NULL values have been backfilled

        # BlogPostPage.author - add null=False
        # Note: We're keeping on_delete=models.PROTECT as it's already correct
        migrations.AlterField(
            model_name='blogpostpage',
            name='author',
            field=models.ForeignKey(
                null=False,  # ✅ NOT NULL enforced (was implicitly null=False already)
                on_delete=django.db.models.deletion.PROTECT,
                to=settings.AUTH_USER_MODEL,
                help_text="Post author"
            ),
        ),

        # BlogPostPage.introduction - add blank=False
        migrations.AlterField(
            model_name='blogpostpage',
            name='introduction',
            field=wagtail.fields.RichTextField(
                blank=False,  # ✅ Required in forms
                help_text="Brief introduction or excerpt"
            ),
        ),

        # BlogPostPage.reading_time - keep nullable but remove temporary default
        # This field should remain nullable as it's auto-calculated
        migrations.AlterField(
            model_name='blogpostpage',
            name='reading_time',
            field=models.PositiveIntegerField(
                null=True,  # Keep nullable (auto-calculated field)
                blank=True,
                help_text="Estimated reading time in minutes (auto-calculated)"
            ),
        ),
    ]
