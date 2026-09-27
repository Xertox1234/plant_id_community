"""Todo 410: plants belong to a user directly, and a bed is optional.

Houseplants have no garden bed, so Plant gains an ``owner`` FK, backfilled
from ``garden_bed.owner``, and ``garden_bed`` becomes nullable with
SET_NULL (deleting a bed keeps its plants, owner decision 2026-09-27).

Care tasks already overdue at deploy are stamped ``notification_sent`` so the
first reminder sweep does not push a backlog. The sweep only looks back 24
hours anyway; the stamp keeps those rows out of its query for good.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_plant_owner(apps, schema_editor):
    Plant = apps.get_model("garden_calendar", "Plant")
    GardenBed = apps.get_model("garden_calendar", "GardenBed")
    for bed_id, owner_id in GardenBed.objects.values_list("uuid", "owner_id"):
        Plant.objects.filter(garden_bed_id=bed_id, owner__isnull=True).update(
            owner_id=owner_id
        )


def stamp_overdue_tasks(apps, schema_editor):
    from django.utils import timezone

    CareTask = apps.get_model("garden_calendar", "CareTask")
    CareTask.objects.filter(
        scheduled_date__lt=timezone.now(),
        completed=False,
        skipped=False,
        notification_sent=False,
    ).update(notification_sent=True)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("garden_calendar", "0007_alter_plantimage_uuid"),
    ]

    operations = [
        migrations.AddField(
            model_name="plant",
            name="owner",
            field=models.ForeignKey(
                help_text="User who owns this plant",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="garden_plants",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_plant_owner, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="plant",
            name="owner",
            field=models.ForeignKey(
                help_text="User who owns this plant",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="garden_plants",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="plant",
            name="garden_bed",
            field=models.ForeignKey(
                blank=True,
                help_text="Garden bed this plant is in (optional)",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="plants",
                to="garden_calendar.gardenbed",
            ),
        ),
        migrations.AlterModelOptions(
            name="plant",
            options={
                "ordering": ["owner", "-planted_date"],
                "verbose_name": "Plant",
                "verbose_name_plural": "Plants",
            },
        ),
        migrations.RemoveIndex(
            model_name="plant",
            name="garden_cale_garden__26d93c_idx",
        ),
        migrations.AddIndex(
            model_name="plant",
            index=models.Index(
                fields=["owner", "-planted_date"], name="garden_cale_owner_i_489d89_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="plant",
            index=models.Index(
                fields=["owner", "is_active"], name="garden_cale_owner_i_30a303_idx"
            ),
        ),
        migrations.RunPython(stamp_overdue_tasks, migrations.RunPython.noop),
    ]
