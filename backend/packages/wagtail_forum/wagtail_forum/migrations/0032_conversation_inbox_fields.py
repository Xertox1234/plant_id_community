"""Inbox contract for DMs (todo 339): activity ordering + per-participant
read markers. Backfills `last_message_at` from each conversation's newest
message (every conversation has at least one — it is only created on send),
falling back to `created_at` for safety."""

from django.db import migrations, models
from django.db.models import Max
from django.utils import timezone


def backfill_last_message_at(apps, schema_editor):
    Conversation = apps.get_model("wagtail_forum", "Conversation")
    qs = Conversation.objects.annotate(newest=Max("messages__created_at"))
    for conversation in qs.iterator(chunk_size=500):
        Conversation.objects.filter(pk=conversation.pk).update(
            last_message_at=conversation.newest or conversation.created_at
        )


class Migration(migrations.Migration):

    dependencies = [
        ("wagtail_forum", "0031_post_body_embed"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="last_message_at",
            field=models.DateTimeField(db_index=True, default=timezone.now),
        ),
        migrations.AddField(
            model_name="conversation",
            name="participant_a_read_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="conversation",
            name="participant_b_read_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterModelOptions(
            name="conversation",
            options={"ordering": ["-last_message_at", "-id"]},
        ),
        migrations.RunPython(backfill_last_message_at, migrations.RunPython.noop),
    ]
