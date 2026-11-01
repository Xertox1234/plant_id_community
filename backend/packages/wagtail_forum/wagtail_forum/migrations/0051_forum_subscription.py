# Per-forum watch levels and the new-topic notification verb (todo 672).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wagtail_forum", "0050_forum_display_settings"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="verb",
            field=models.CharField(
                choices=[
                    ("reply", "Reply"),
                    ("mention", "Mention"),
                    ("solution", "Answer accepted"),
                    ("quote", "Quoted"),
                    ("new_topic", "New topic"),
                ],
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="ForumSubscription",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "level",
                    models.CharField(
                        choices=[
                            ("watching", "Watching"),
                            ("watching_first_post", "Watching first post"),
                            ("tracking", "Tracking"),
                            ("muted", "Muted"),
                        ],
                        max_length=24,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "forum",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscriptions",
                        to="wagtail_forum.forum",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="forum_watch_levels",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["forum", "level"], name="wagtail_for_forum_i_0915f7_idx"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "forum"), name="uniq_forum_subscription"
                    )
                ],
            },
        ),
    ]
