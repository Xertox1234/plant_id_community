"""Categories endpoint and the Flutter board contract (todo 665).

``GET /forum/categories/`` is new and additive: categories in ``position``
order with their visible forums nested. ``GET /forum/boards/`` and
``/forum/boards/{slug}/topics/`` are what the Flutter app reads
(``forum_api.dart``), so their keys must not move and they must list forums
only — a category or a link there would send the app fetching topics of a row
that can hold none.
"""

from datetime import datetime
from datetime import timezone as dt_timezone

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from wagtail.models import Page, PageViewRestriction
from wagtail_forum.models import Forum, ForumIndex, Topic
from wagtail_forum.tests.factories import make_category, make_forum

pytestmark = [pytest.mark.django_db, pytest.mark.urls("wagtail_forum.tests.api.urls")]

# The page-era BoardSerializer keys, verbatim (Flutter's ForumBoard.fromJson).
BOARD_KEYS = {
    "id",
    "title",
    "slug",
    "description",
    "topic_count",
    "post_count",
    "last_post_at",
}
# TopicListSerializer's keys at the merge-base — unchanged by this slice.
TOPIC_KEYS = {
    "author",
    "id",
    "is_closed",
    "is_pinned",
    "is_solved",
    "is_unread",
    "last_post_at",
    "last_post_author",
    "locked",
    "reply_count",
    "slug",
    "solved_post_id",
    "tags",
    "title",
    "view_count",
}
CATEGORY_KEYS = {
    "id",
    "title",
    "slug",
    "description",
    "position",
    "topic_count",
    "post_count",
    "last_post_at",
    "forums",
    # Added by todos 670 (link rows) and 671 (read state).
    "links",
    "has_unread",
}
# A forum row of /forum/categories/: the board keys plus its unread flag
# (todo 671). /forum/boards/ keeps BOARD_KEYS exactly.
# Todos 674 (moderators), 678 (topic_template) and 680 (is_locked) added keys.
FORUM_ROW_KEYS = BOARD_KEYS | {
    "has_unread",
    "is_locked",
    "moderators",
    "topic_template",
}


def _at(month):
    return datetime(2026, month, 1, 12, 0, tzinfo=dt_timezone.utc)


def _categories():
    resp = APIClient().get("/forum/categories/")
    assert resp.status_code == 200
    return resp.json()["results"]


def _link(category, slug):
    return Forum.objects.create(
        forum_type=Forum.LINK, parent=category, name="Docs", slug=slug
    )


def test_board_list_keeps_its_keys_and_lists_only_forums():
    category = make_category()
    board = make_forum(name="General", slug="general", category=category)
    _link(category, "docs")

    results = APIClient().get("/forum/boards/").json()["results"]

    assert [r["id"] for r in results] == [board.pk]
    assert set(results[0]) == BOARD_KEYS
    assert results[0]["title"] == "General"


def test_board_topics_keep_their_keys_and_never_resolve_a_category_or_link():
    category = make_category(slug="plants")
    board = make_forum(name="General", slug="general", category=category)
    _link(category, "docs")
    Topic.objects.create(board=board, title="T", slug="t", live=True)
    client = APIClient()

    resp = client.get("/forum/boards/general/topics/")
    assert resp.status_code == 200
    (row,) = resp.json()["results"]
    assert set(row) == TOPIC_KEYS

    assert client.get("/forum/boards/plants/topics/").status_code == 404
    assert client.get("/forum/boards/docs/topics/").status_code == 404


def test_categories_nest_visible_forums_in_position_order_with_summed_counts():
    second = make_category(name="Pests", slug="pests", position=2)
    first = make_category(name="Plants", slug="plants", position=1)
    ferns = make_forum(
        name="Ferns",
        slug="ferns",
        category=first,
        position=2,
        topic_count=3,
        post_count=10,
    )
    palms = make_forum(
        name="Palms",
        slug="palms",
        category=first,
        position=1,
        topic_count=2,
        post_count=5,
    )
    make_forum(
        name="Staff",
        slug="staff",
        category=first,
        is_hidden=True,
        topic_count=50,
        post_count=500,
    )
    aphids = make_forum(name="Aphids", slug="aphids", category=second, topic_count=1)
    _link(first, "docs")
    Topic.objects.create(board=ferns, title="A", slug="a", last_post_at=_at(3))
    Topic.objects.create(board=palms, title="B", slug="b", last_post_at=_at(5))

    results = _categories()

    assert [c["id"] for c in results] == [first.pk, second.pk]
    plants = results[0]
    assert set(plants) == CATEGORY_KEYS
    assert plants["title"] == "Plants"
    # Hidden forum and link left out of both the list and the sums.
    assert [f["id"] for f in plants["forums"]] == [palms.pk, ferns.pk]
    assert set(plants["forums"][0]) == FORUM_ROW_KEYS
    assert (plants["topic_count"], plants["post_count"]) == (5, 15)
    assert plants["last_post_at"] == "2026-05-01T12:00:00Z"
    assert [f["id"] for f in results[1]["forums"]] == [aphids.pk]
    assert results[1]["last_post_at"] is None


def test_a_category_with_no_visible_forum_is_omitted():
    empty = make_category(name="Empty", slug="empty")
    hidden_only = make_category(name="Hidden", slug="hidden-only")
    make_forum(name="Secret", slug="secret", category=hidden_only, is_hidden=True)
    _link(empty, "docs")
    shown = make_forum(name="General", slug="general")

    assert [c["id"] for c in _categories()] == [shown.parent_id]


def test_a_hidden_category_hides_its_forums_everywhere():
    category = make_category(name="Staff", slug="staff-cat", is_hidden=True)
    make_forum(name="Mods", slug="mods", category=category)
    client = APIClient()

    assert _categories() == []
    assert client.get("/forum/boards/").json()["results"] == []
    assert client.get("/forum/boards/mods/topics/").status_code == 404


def _forum_index():
    return Page.objects.get(id=1).add_child(
        instance=ForumIndex(title="Forum", slug="forum")
    )


@pytest.mark.parametrize("restrict", ["index", "ancestor"])
def test_privacy_on_the_forum_index_hides_the_whole_forum(restrict):
    """Privacy set on the ForumIndex page (or a page above it) still hides
    every forum and topic, as `.public()` did when boards were its child
    pages (todo 665 round-1 review)."""
    index = _forum_index()
    board = make_forum(name="General", slug="general")
    topic = Topic.objects.create(board=board, title="T", slug="t", live=True)
    client = APIClient()
    assert client.get(f"/forum/topics/{topic.id}/").status_code == 200

    page = index if restrict == "index" else index.get_parent()
    PageViewRestriction.objects.create(page=page, restriction_type="login")

    assert client.get("/forum/boards/").json()["results"] == []
    assert client.get("/forum/boards/general/topics/").status_code == 404
    assert client.get(f"/forum/topics/{topic.id}/").status_code == 404
    assert _categories() == []


def test_an_unpublished_forum_index_hides_the_whole_forum():
    index = _forum_index()
    make_forum(name="General", slug="general")
    client = APIClient()
    assert len(client.get("/forum/boards/").json()["results"]) == 1

    index.unpublish()

    assert client.get("/forum/boards/").json()["results"] == []
    assert _categories() == []


def test_a_live_public_forum_index_keeps_the_forum_visible():
    _forum_index()
    make_forum(name="General", slug="general")

    assert [b["slug"] for b in APIClient().get("/forum/boards/").json()["results"]] == [
        "general"
    ]


@pytest.mark.parametrize("closed", ["draft", "restricted"])
def test_a_stray_closed_forum_index_does_not_hide_the_forum(closed):
    """One open index keeps the forum visible: a second ForumIndex that is a
    draft (e.g. an editor's unpublished copy) or privacy-restricted must not
    close it (todo 665 round-2 review)."""
    _forum_index()
    stray = Page.objects.get(id=1).add_child(
        instance=ForumIndex(title="Forum copy", slug="forum-copy")
    )
    if closed == "draft":
        stray.unpublish()
    else:
        PageViewRestriction.objects.create(page=stray, restriction_type="login")
    board = make_forum(name="General", slug="general")
    topic = Topic.objects.create(board=board, title="T", slug="t", live=True)
    client = APIClient()

    assert [b["slug"] for b in client.get("/forum/boards/").json()["results"]] == [
        "general"
    ]
    assert client.get(f"/forum/topics/{topic.id}/").status_code == 200
    assert [c["id"] for c in _categories()] == [board.parent_id]


def test_categories_query_count_is_flat():
    """Two queries whatever the size: the categories, then one prefetch of
    their visible forums carrying the last-post subquery."""

    def count():
        with CaptureQueriesContext(connection) as ctx:
            _categories()
        return len(ctx.captured_queries)

    category = make_category(name="A", slug="cat-a")
    make_forum(name="F1", slug="f1", category=category)
    small = count()

    for n in range(2, 8):
        other = make_category(name=f"C{n}", slug=f"cat-{n}")
        board = make_forum(name=f"F{n}", slug=f"f{n}", category=other)
        Topic.objects.create(board=board, title="T", slug="t", last_post_at=_at(n))
    big = count()

    assert (small, big) == (2, 2)
