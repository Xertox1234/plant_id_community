# A migration of its own: Postgres refuses to ALTER the forum table in the
# transaction that just wrote grant rows referencing it (pending FK triggers).

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("wagtail_forum", "0048_is_hidden_to_grants")]

    operations = [migrations.RemoveField(model_name="forum", name="is_hidden")]
