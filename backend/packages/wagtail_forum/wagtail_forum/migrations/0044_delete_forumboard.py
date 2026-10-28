"""Step 4 of 4 (todo 665): drop the emptied ``ForumBoard`` table."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("wagtail_forum", "0043_delete_board_pages"),
    ]

    operations = [
        migrations.DeleteModel(
            name="ForumBoard",
        ),
    ]
