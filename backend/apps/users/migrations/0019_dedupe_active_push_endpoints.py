from django.db import migrations
from django.db.models import Count


def deactivate_duplicate_active_endpoints(apps, schema_editor):
    """Keep one active row per push endpoint: the newest (todo 602 item 3).

    Two concurrent subscribes of one browser by different accounts could each
    insert an active row. The next migration adds a partial unique constraint
    that refuses that, so the duplicates go first. Rows are only deactivated,
    never deleted: a deactivated row is what a released shared-browser
    subscription already looks like.
    """
    PushSubscription = apps.get_model("users", "PushSubscription")
    active = PushSubscription.objects.filter(is_active=True)
    duplicated = (
        active.values("endpoint")
        .annotate(rows=Count("pk"))
        .filter(rows__gt=1)
        .values_list("endpoint", flat=True)
    )
    for endpoint in list(duplicated):
        rows = active.filter(endpoint=endpoint)
        newest = rows.order_by("-created_at", "-pk").values_list("pk", flat=True)[0]
        rows.exclude(pk=newest).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0018_delete_demodata"),
    ]

    operations = [
        migrations.RunPython(
            deactivate_duplicate_active_endpoints, migrations.RunPython.noop
        ),
    ]
