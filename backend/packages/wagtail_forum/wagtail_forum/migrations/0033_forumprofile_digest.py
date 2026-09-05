"""Digest email preference + idempotency marker (todo 340)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wagtail_forum", "0032_conversation_inbox_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="forumprofile",
            name="digest_frequency",
            field=models.CharField(
                choices=[("off", "Off"), ("weekly", "Weekly")],
                default="off",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="forumprofile",
            name="last_digest_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
