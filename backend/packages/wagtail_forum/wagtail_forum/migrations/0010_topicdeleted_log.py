import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wagtail_forum", "0009_alter_post_author"),
    ]

    operations = [
        migrations.CreateModel(
            name="TopicDeletedLog",
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
                ("topic_id", models.IntegerField(db_index=True)),
                ("board_id", models.IntegerField(db_index=True)),
                (
                    "deleted_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now, db_index=True
                    ),
                ),
            ],
            options={
                "ordering": ["deleted_at"],
                "app_label": "wagtail_forum",
            },
        ),
        migrations.AddIndex(
            model_name="topicdeletedlog",
            index=models.Index(
                fields=["deleted_at"], name="wf_tombstone_deleted_at_idx"
            ),
        ),
    ]
