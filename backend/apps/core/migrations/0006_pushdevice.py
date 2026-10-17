"""PushDevice (todo 621): one row per mobile installation.

The data step copies every legacy ``ForumProfile.fcm_token`` into a row, so
devices that registered before this deploy keep receiving pushes. The legacy
column stays: an older app build still writes it, and the send path reads
both until those builds are gone (deploy skew). Reversing drops the table;
the legacy column was never changed, so nothing is lost.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def copy_legacy_tokens(apps, schema_editor):
    ForumProfile = apps.get_model("wagtail_forum", "ForumProfile")
    PushDevice = apps.get_model("core", "PushDevice")
    seen = set()
    # Newest profile first: if two profiles ever held the same token (the
    # serializer releases it, but an older bug could have left one), the
    # most recently joined account keeps it.
    rows = (
        ForumProfile.objects.exclude(fcm_token="")
        .order_by("-joined_at", "-pk")
        .values_list("user_id", "fcm_token")
    )
    devices = []
    for user_id, token in rows.iterator():
        if token in seen:
            continue
        seen.add(token)
        devices.append(PushDevice(user_id=user_id, token=token, platform="legacy"))
    PushDevice.objects.bulk_create(devices, batch_size=500, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_delete_forumnotificationsubscription"),
        ("wagtail_forum", "0039_post_body_link_preview"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PushDevice",
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
                ("token", models.CharField(max_length=255, unique=True)),
                (
                    "installation_id",
                    models.CharField(blank=True, max_length=64, null=True, unique=True),
                ),
                ("platform", models.CharField(blank=True, default="", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="push_devices",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["created_at", "pk"],
            },
        ),
        migrations.RunPython(copy_legacy_tokens, migrations.RunPython.noop),
    ]
