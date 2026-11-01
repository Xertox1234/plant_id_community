# Per-forum theme (todo 681); db_default for the same deploy window as 0050.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wagtail_forum", "0051_forum_subscription"),
    ]

    operations = [
        migrations.AddField(
            model_name="forum",
            name="theme",
            field=models.CharField(
                blank=True,
                choices=[
                    ("botanical", "Botanical"),
                    ("moss", "Moss"),
                    ("terracotta", "Terracotta"),
                    ("slate", "Slate"),
                ],
                db_default="",
                default="",
                help_text="A colour theme for this forum's pages.",
                max_length=16,
            ),
        ),
    ]
