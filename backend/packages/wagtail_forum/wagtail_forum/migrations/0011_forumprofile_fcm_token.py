from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wagtail_forum", "0010_topicdeleted_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="forumprofile",
            name="fcm_token",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
