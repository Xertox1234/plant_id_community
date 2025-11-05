# Generated manually for soft delete pattern on Attachment model
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0005_flaggedcontent_moderationaction_and_more'),
    ]

    operations = [
        # Add is_active field with default=True
        migrations.AddField(
            model_name='attachment',
            name='is_active',
            field=models.BooleanField(
                default=True,
                db_index=True,
                help_text="Soft delete flag. False = deleted, True = active"
            ),
        ),
        # Add deleted_at timestamp for cleanup scheduling
        migrations.AddField(
            model_name='attachment',
            name='deleted_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text="Timestamp when soft-deleted (for cleanup job)"
            ),
        ),
        # Remove old index
        migrations.RemoveIndex(
            model_name='attachment',
            name='forum_attach_post_idx',
        ),
        # Add composite index: (post, is_active, display_order)
        # This optimizes queries that filter by post and is_active
        migrations.AddIndex(
            model_name='attachment',
            index=models.Index(
                fields=['post', 'is_active', 'display_order'],
                name='forum_attach_active_idx'
            ),
        ),
    ]
