# A migration of its own: Postgres refuses to ALTER the forum table in the
# transaction that just wrote grant rows referencing it (pending FK triggers).
#
# Expand/contract (round-1 review, docs/rules/database.md): Railway runs
# `migrate` while the previous release still serves, and that release filters
# `is_hidden=False` on every forum read. So this deploy only gives the column a
# DB default (new code inserts forums without it) and removes it from Django
# state; the column itself is dropped by a later migration, once this release
# is live.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("wagtail_forum", "0048_is_hidden_to_grants")]

    operations = [
        migrations.AlterField(
            model_name="forum",
            name="is_hidden",
            field=models.BooleanField(default=False, db_default=False),
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name="forum", name="is_hidden"),
            ],
        ),
    ]
