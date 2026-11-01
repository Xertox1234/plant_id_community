# Contract half of 0049's expand/contract (todo 684, docs/rules/database.md).
#
# 0049 removed `Forum.is_hidden` from Django state and gave the column a DB
# default, so the release before it could keep filtering on the column during
# the rolling deploy. 0049 shipped with #1228 on 2026-10-30, and every
# container now runs code that never selects `is_hidden`, so the column goes.
#
# Database only: Django state has had no such field since 0049. A migration of
# its own, with no RunPython row writes on the forum table (Postgres refuses
# an ALTER TABLE with pending trigger events in the same transaction).

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("wagtail_forum", "0052_forum_theme"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE wagtail_forum_forum DROP COLUMN is_hidden",
                    reverse_sql=(
                        "ALTER TABLE wagtail_forum_forum ADD COLUMN is_hidden "
                        "boolean NOT NULL DEFAULT false"
                    ),
                ),
            ],
        ),
    ]
