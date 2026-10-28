"""Migrations 0041-0044: boards stop being Wagtail pages (todo 665).

Winds ``wagtail_forum`` back to 0040, builds a page-era forum (board pages,
one not live, one under a view restriction, two in different trees sharing a
slug, one named ``general`` like the default category), and migrates forward
for real. The migrated rows must keep every board's id — that is what keeps
``/forum/{board.id}-{slug}/{topic.id}-{slug}`` links alive — and leave no
board page behind for the Wagtail explorer to trip on.

A board page is built in two halves, because the historical ``ForumBoard``
has no treebeard ``add_child``: the ``wagtailcore_page`` row through the real
``Page`` API (its schema is untouched by these migrations), then the child
row through the historical model with ``save_base(raw=True)``, the loaddata
path, which writes only the child table and leaves the page row as built.
"""

from io import StringIO

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from rest_framework.test import APIClient
from wagtail.coreutils import get_supported_content_language_variant
from wagtail.models import Locale, Page, PageViewRestriction

BEFORE = ("wagtail_forum", "0040_forumprofile_quiet_hours")


def _board_page(parent, board_ct, OldBoard, *, title, slug, live=True):
    page = parent.add_child(instance=Page(title=title, slug=slug, live=live))
    Page.objects.filter(pk=page.pk).update(content_type=board_ct)
    OldBoard(page_ptr_id=page.pk, description=f"{title} talk").save_base(raw=True)
    return page


def _tree_root():
    """The treebeard root. Not ``Page.objects.get(id=1)``: an earlier
    ``transaction=True`` test's teardown flush deletes the root page the
    wagtailcore data migration made (and its default Locale), and nothing
    re-creates them."""
    Locale.objects.get_or_create(
        language_code=get_supported_content_language_variant(settings.LANGUAGE_CODE)
    )
    return Page.get_first_root_node() or Page.add_root(
        instance=Page(title="Root", slug="root")
    )


def _migrate_to_leaf():
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


# transaction=True is unavoidable for MigrationExecutor (DDL cannot run with
# pending trigger events inside the test transaction); docs/rules/testing.md
# allows this exception. serialized_rollback is NOT used: the host's
# post_migrate bootstrap re-creates rows the snapshot also carries (see
# apps/users/tests/test_migration_0017_remap.py).
@pytest.mark.django_db(transaction=True)
@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_boards_become_forums_with_their_ids_and_leave_no_pages():
    """AC: identical ids under one "General" category; a non-live or
    view-restricted board becomes is_hidden; a board slugged ``general``
    migrates without a constraint error; no board page rows remain; and
    ``fixtree`` reports nothing."""
    from wagtail_forum.models import Forum, ForumIndex, Topic

    author = get_user_model().objects.create_user(username="mig-665")
    root = _tree_root()
    executor = MigrationExecutor(connection)
    executor.migrate([BEFORE])
    try:
        old_apps = executor.loader.project_state([BEFORE]).apps
        OldBoard = old_apps.get_model("wagtail_forum", "ForumBoard")
        OldTopic = old_apps.get_model("wagtail_forum", "Topic")
        board_ct, _ = ContentType.objects.get_or_create(
            app_label="wagtail_forum", model="forumboard"
        )
        # ForumIndex's own schema is unchanged by 0041-0044, so the real
        # model (with treebeard) builds the page-era trees.
        index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
        other = root.add_child(instance=ForumIndex(title="Forum 2", slug="forum-2"))

        general = _board_page(
            index, board_ct, OldBoard, title="General", slug="general"
        )
        ferns = _board_page(
            index, board_ct, OldBoard, title="Ferns", slug="ferns", live=False
        )
        staff = _board_page(index, board_ct, OldBoard, title="Staff", slug="staff")
        PageViewRestriction.objects.create(page=staff, restriction_type="login")
        # A second tree's board with the same slug: legal for sibling-unique
        # page slugs, not for forum-wide forum slugs.
        twin = _board_page(other, board_ct, OldBoard, title="General 2", slug="general")
        topic = OldTopic.objects.create(
            board_id=general.pk, title="Aphids", slug="aphids", author_id=author.pk
        )
        old_url = f"/forum/{general.pk}-general/{topic.pk}-aphids"
        board_ids = [general.pk, ferns.pk, staff.pk, twin.pk]
        assert ForumIndex.objects.get(pk=index.pk).numchild == 3

        _migrate_to_leaf()
    finally:
        _migrate_to_leaf()

    # Identical ids, one "General" category over all of them.
    category = Forum.objects.get(forum_type=Forum.CATEGORY)
    assert (category.name, category.slug, category.parent_id) == (
        "General",
        "general",
        None,
    )
    forums = {f.pk: f for f in Forum.objects.filter(forum_type=Forum.FORUM)}
    assert sorted(forums) == sorted(board_ids)
    assert {f.parent_id for f in forums.values()} == {category.pk}
    assert category.pk not in board_ids

    # The board named "general" kept its slug: categories are a separate
    # slug namespace, so it never collides with the default category.
    assert forums[general.pk].slug == "general"
    assert forums[general.pk].name == "General"
    assert forums[general.pk].description == "General talk"
    # The other tree's twin is the one renamed, by its id.
    assert forums[twin.pk].slug == f"general-{twin.pk}"

    # Not live, or view-restricted, was invisible to the API: now hidden.
    assert {pk for pk, f in forums.items() if f.is_hidden} == {ferns.pk, staff.pk}

    # No board page rows remain, of any shape.
    assert not Page.objects.filter(pk__in=board_ids).exists()
    assert not Page.objects.filter(content_type=board_ct).exists()
    assert ForumIndex.objects.get(pk=index.pk).numchild == 0
    assert ForumIndex.objects.get(pk=other.pk).numchild == 0
    # `manage.py fixtree --noinput` finds nothing to fix: historical deletes
    # bypass treebeard, so 0043 recomputes numchild, and a stale count or an
    # orphaned base row is exactly what fixtree would report (and "fix").
    out = StringIO()
    call_command("fixtree", "--noinput", stdout=out)
    output = out.getvalue()
    assert "Checking page tree for problems..." in output
    assert output.count("No problems found.") == 2, output  # pages, collections
    assert "fixed" not in output.lower(), output

    # The sequence moved past the copied ids.
    assert Forum.objects.create(
        forum_type=Forum.CATEGORY, name="Next", slug="next"
    ).pk > max(board_ids)

    # The existing topic keeps its board, and its URL.
    migrated = Topic.objects.get(pk=topic.pk)
    assert migrated.board_id == general.pk
    assert migrated.get_absolute_url() == old_url


@pytest.mark.django_db
@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_a_topic_url_resolves_through_the_api_after_the_move():
    """The web app routes ``/forum/{board.id}-{slug}/{topic.id}-{slug}`` by
    the leading ids: it fetches the topic by id and finds its board in the
    board list by id. Both halves must still answer for a migrated board."""
    from wagtail_forum.models import Topic
    from wagtail_forum.tests.factories import make_forum

    board = make_forum(name="General", slug="general")
    topic = Topic.objects.create(board=board, title="Aphids", slug="aphids")
    client = APIClient()

    assert topic.get_absolute_url() == f"/forum/{board.pk}-general/{topic.pk}-aphids"
    detail = client.get(f"/forum/topics/{topic.pk}/")
    assert detail.status_code == 200
    assert detail.data["board"]["id"] == board.pk
    boards = client.get("/forum/boards/").json()["results"]
    assert [b["id"] for b in boards] == [board.pk]
    topics = client.get(f"/forum/boards/{board.slug}/topics/")
    assert [t["id"] for t in topics.json()["results"]] == [topic.pk]
