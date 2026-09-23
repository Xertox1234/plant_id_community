"""Drop the retired Garden Planner app's tables (todo 405).

apps.garden (an outdoor garden planner) was removed in todo 405: it no longer
fits the Houseplant MD product, and neither client ever called its API. Its
only live piece, the FCM bootstrap, moved to apps/core/firebase_config.py.

This migration lives in apps.core because a migration inside the deleted app
could never run: Django stops loading an app's migrations once the app leaves
INSTALLED_APPS.

Production evidence (2026-09-23, `railway ssh --service plant_id_community`
running `m.objects.count()` over every garden model): all 9 tables held 0 rows.

- ``DROP TABLE IF EXISTS``: fresh databases (CI, new dev DBs) never had these
  tables, so the drop must be a no-op there.
- No ``CASCADE``: the tables are dropped child-first. If anything unexpected
  still depends on them, the migration fails loudly instead of silently
  dropping more.
- Content types go through the ORM, so their auth permissions cascade;
  ``auth_permission.content_type_id`` has no database-level cascade.
- Irreversible by nature (the models are gone), so the reverse is a no-op.
"""

from django.db import migrations

# Child tables before the tables they reference. Written out as literal SQL,
# never built with an f-string (CLAUDE.md Critical Gotcha #3).
DROP_STATEMENTS = [
    "DROP TABLE IF EXISTS garden_journalimage;",
    "DROP TABLE IF EXISTS garden_pestimage;",
    "DROP TABLE IF EXISTS garden_journalentry;",
    "DROP TABLE IF EXISTS garden_pestissue;",
    "DROP TABLE IF EXISTS garden_carereminder;",
    "DROP TABLE IF EXISTS garden_task;",
    "DROP TABLE IF EXISTS garden_gardenplant;",
    "DROP TABLE IF EXISTS garden_garden;",
    "DROP TABLE IF EXISTS garden_plantcarelibrary;",
]


def delete_garden_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(app_label="garden").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_alter_emailnotification_user"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunSQL(
            sql=DROP_STATEMENTS,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunPython(
            delete_garden_content_types, reverse_code=migrations.RunPython.noop
        ),
        migrations.RunSQL(
            sql="DELETE FROM django_migrations WHERE app = 'garden';",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
