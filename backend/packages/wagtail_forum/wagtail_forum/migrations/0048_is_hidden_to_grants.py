"""``Forum.is_hidden`` becomes a "No access for everyone" grant set (todo
676): guests and members get *No access* on every hidden row, category or
forum. The forums of a hidden category stay hidden through the category's own
grants (a forum needs ``list`` on its category). Staff, superusers and forum
moderators still see them, as they did in the admin.

Reversed, a row whose guests and members both have *No access* is hidden
again and those two grants are removed.
"""

from django.db import migrations

PSEUDO_GROUPS = ("anonymous", "members")


def hidden_to_grants(apps, schema_editor):
    Forum = apps.get_model("wagtail_forum", "Forum")
    ForumGrant = apps.get_model("wagtail_forum", "ForumGrant")
    grants = []
    for forum_id in Forum.objects.filter(is_hidden=True).values_list("pk", flat=True):
        for principal in PSEUDO_GROUPS:
            ForumGrant.objects.filter(forum_id=forum_id, principal=principal).delete()
            grants.append(
                ForumGrant(forum_id=forum_id, principal=principal, role="no_access")
            )
    ForumGrant.objects.bulk_create(grants)


def grants_to_hidden(apps, schema_editor):
    Forum = apps.get_model("wagtail_forum", "Forum")
    ForumGrant = apps.get_model("wagtail_forum", "ForumGrant")
    closed = ForumGrant.objects.filter(principal__in=PSEUDO_GROUPS, role="no_access")
    for forum in Forum.objects.all():
        rows = closed.filter(forum=forum)
        if rows.count() == len(PSEUDO_GROUPS):
            Forum.objects.filter(pk=forum.pk).update(is_hidden=True)
            rows.delete()


class Migration(migrations.Migration):
    dependencies = [("wagtail_forum", "0047_forum_permissions")]

    operations = [migrations.RunPython(hidden_to_grants, grants_to_hidden)]
