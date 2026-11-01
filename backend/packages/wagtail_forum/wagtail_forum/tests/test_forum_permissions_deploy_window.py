"""The deploy window of migrations 0047-0049 (round-1 review, todos 675-680).

Railway runs ``migrate`` while the previous release still serves. That
release's ``Forum`` model (the 0046 state) filters ``is_hidden`` on every
forum read and inserts forums without the columns 0047 adds. So after the new
migrations the ``is_hidden`` column must still exist, and every new NOT NULL
column must carry a database default (docs/rules/database.md expand/contract).

0053 is the contract half (todo 684): it drops ``is_hidden`` once every
container runs code that never selects it, so the release before 0053 (the
0052 state) must still read and write forums with the column gone.
"""

import pytest
from django.db import connection
from django.db.migrations.loader import MigrationLoader

PREVIOUS_RELEASE = ("wagtail_forum", "0052_forum_theme")
NEW_COLUMNS = (
    "password_hash",
    "prune_enabled",
    "prune_pinned",
    "prune_polls",
    "topic_template",
)

pytestmark = pytest.mark.django_db


def _old_forum_model():
    loader = MigrationLoader(connection)
    return loader.project_state(PREVIOUS_RELEASE).apps.get_model(
        "wagtail_forum", "Forum"
    )


def test_the_previous_release_still_reads_and_writes_forums():
    OldForum = _old_forum_model()

    category = OldForum.objects.create(forum_type="category", name="Old", slug="old")
    forum = OldForum.objects.create(
        forum_type="forum", parent=category, name="Kept", slug="kept"
    )

    assert OldForum.objects.filter(pk=forum.pk).exists()

    from wagtail_forum.models import Forum

    new = Forum.objects.get(pk=forum.pk)
    assert new.password_hash == "" and new.topic_template == ""
    assert new.prune_enabled is False and new.prune_pinned is False
    assert new.prune_polls is False


def test_the_is_hidden_column_is_dropped():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'wagtail_forum_forum' AND column_name = 'is_hidden'"
        )
        assert cursor.fetchone() is None


def test_every_new_column_has_a_database_default():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name, column_default FROM information_schema.columns "
            "WHERE table_name = 'wagtail_forum_forum' AND column_name = ANY(%s)",
            [list(NEW_COLUMNS)],
        )
        defaults = dict(cursor.fetchall())

    assert set(defaults) == set(NEW_COLUMNS)
    assert all(default is not None for default in defaults.values()), defaults
