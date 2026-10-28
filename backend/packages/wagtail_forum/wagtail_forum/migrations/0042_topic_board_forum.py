"""Step 2 of 4 (todo 665): ``Topic.board`` points at ``Forum``, ``PROTECT``.

The ids were copied in 0041, so every existing ``board_id`` already names its
forum. ``PROTECT`` replaces ``CASCADE``: deleting a board page used to delete
every topic on it; deleting a forum with topics now raises ``ProtectedError``.
The field keeps its name and ``related_name="topics"``.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wagtail_forum", "0041_forum_model"),
    ]

    operations = [
        migrations.AlterField(
            model_name="topic",
            name="board",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="topics",
                to="wagtail_forum.forum",
            ),
        ),
    ]
