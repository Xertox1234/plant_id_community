# Generated migration for adding NOT NULL constraints - Step 2/3
# This migration backfills any NULL/empty values with sensible defaults

from django.db import migrations


def backfill_introduction(apps, schema_editor):
    """Backfill empty introduction fields with placeholder text."""
    BlogPostPage = apps.get_model('blog', 'BlogPostPage')

    # Update NULL introduction to placeholder
    null_count = BlogPostPage.objects.filter(
        introduction__isnull=True
    ).update(introduction='<p>Introduction pending.</p>')

    # Update empty introduction to placeholder
    empty_count = BlogPostPage.objects.filter(
        introduction=''
    ).update(introduction='<p>Introduction pending.</p>')

    total = null_count + empty_count
    if total > 0:
        print(f"[MIGRATION] Backfilled {total} NULL/empty introduction values")


def backfill_reading_time(apps, schema_editor):
    """Backfill NULL reading_time values with default of 1 minute."""
    BlogPostPage = apps.get_model('blog', 'BlogPostPage')

    null_count = BlogPostPage.objects.filter(
        reading_time__isnull=True
    ).update(reading_time=1)

    if null_count > 0:
        print(f"[MIGRATION] Backfilled {null_count} NULL reading_time values with 1")


def reverse_backfill(apps, schema_editor):
    """Reverse migration - no action needed."""
    print("[MIGRATION] Reverse migration: Cannot restore original NULL values")


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0008_add_defaults_step1'),
    ]

    operations = [
        migrations.RunPython(backfill_introduction, reverse_backfill),
        migrations.RunPython(backfill_reading_time, reverse_backfill),
    ]
