# Generated manually for performance optimization
# Adds partial index for efficient cleanup job queries

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('forum', '0003_add_attachment_soft_delete'),
    ]

    operations = [
        # Add partial index: (is_active, deleted_at) WHERE is_active = False
        # This significantly speeds up cleanup job queries by only indexing soft-deleted records
        migrations.AddIndex(
            model_name='attachment',
            index=models.Index(
                fields=['is_active', 'deleted_at'],
                name='forum_attach_cleanup_idx',
                condition=models.Q(is_active=False),
            ),
        ),
    ]
