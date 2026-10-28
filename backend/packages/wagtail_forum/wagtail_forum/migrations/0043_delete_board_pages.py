"""Step 3 of 4 (todo 665): delete the old board pages before their table goes.

Deleted through the historical ``ForumBoard`` model, so Django's collector
removes each board's ``wagtailcore_page`` base row (and the rows that cascade
from it) too. Dropping the table alone would leave base rows whose content
type no longer exists, and the page explorer breaks on them. Topics are safe:
0042 already moved ``Topic.board`` to ``Forum``.

Also removed: the boards' revisions (a generic relation, so nothing cascades
to them) and their reference-index rows. Historical-model deletes bypass
treebeard, so each parent's ``numchild`` is recomputed afterwards;
``manage.py fixtree`` reports nothing on the result (pinned by
``tests/test_forum_model_migration.py``).
"""

from django.db import migrations

# treebeard's MP_Node.steplen for Wagtail pages.
STEPLEN = 4


def delete_board_pages(apps, schema_editor):
    ForumBoard = apps.get_model("wagtail_forum", "ForumBoard")
    Page = apps.get_model("wagtailcore", "Page")
    Revision = apps.get_model("wagtailcore", "Revision")
    ReferenceIndex = apps.get_model("wagtailcore", "ReferenceIndex")
    ContentType = apps.get_model("contenttypes", "ContentType")

    board_ct = ContentType.objects.filter(
        app_label="wagtail_forum", model="forumboard"
    ).first()
    if board_ct is None:
        return  # no board was ever created on this database

    page_rows = Page.objects.filter(content_type=board_ct)
    parent_paths = {
        path[:-STEPLEN] for path in page_rows.values_list("path", flat=True)
    }

    ForumBoard.objects.all().delete()
    # A base row whose ForumBoard row was already gone (a half-deleted page)
    # is just as broken in the explorer; take it too.
    page_rows.delete()
    Revision.objects.filter(content_type=board_ct).delete()
    ReferenceIndex.objects.filter(content_type=board_ct).delete()
    ReferenceIndex.objects.filter(to_content_type=board_ct).delete()

    for path in parent_paths:
        depth = len(path) // STEPLEN
        children = Page.objects.filter(path__startswith=path, depth=depth + 1).count()
        Page.objects.filter(path=path).update(numchild=children)


class Migration(migrations.Migration):
    dependencies = [
        ("wagtail_forum", "0042_topic_board_forum"),
        ("wagtailcore", "0097_baselogentry_uuid_action_timestamp_indexes"),
    ]

    operations = [
        # Irreversible in data (the pages are gone); the reverse is a no-op so
        # a test can still wind the schema back past it.
        migrations.RunPython(delete_board_pages, migrations.RunPython.noop),
    ]
