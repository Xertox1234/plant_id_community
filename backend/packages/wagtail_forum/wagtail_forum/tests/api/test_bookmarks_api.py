"""Bookmark toggle + Saved list endpoint tests (todo 283 / M2)."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from wagtail.models import Page, PageViewRestriction
from wagtail_forum.models import ForumBoard, ForumIndex, Topic, TopicBookmark

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board(slug="general"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    return index.add_child(instance=ForumBoard(title="General", slug=slug))


def _topic(slug="t", live=True, board=None):
    board = board or _board(slug)
    return Topic.objects.create(board=board, title="T", slug=slug, live=live)


@pytest.mark.django_db
def test_bookmark_creates_bookmark():
    user = User.objects.create_user(username="bm1")
    topic = _topic("bm-t1")

    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(f"/forum/topics/{topic.id}/bookmark/")

    assert resp.status_code == 200
    assert resp.data == {"bookmarked": True}
    assert TopicBookmark.objects.filter(user=user, topic=topic).exists()


@pytest.mark.django_db
def test_bookmark_is_idempotent():
    """Two POSTs leave exactly one row — AC1."""
    user = User.objects.create_user(username="bm2")
    topic = _topic("bm-t2")

    client = APIClient()
    client.force_authenticate(user)
    client.post(f"/forum/topics/{topic.id}/bookmark/")
    resp = client.post(f"/forum/topics/{topic.id}/bookmark/")

    assert resp.status_code == 200
    assert TopicBookmark.objects.filter(user=user, topic=topic).count() == 1


@pytest.mark.django_db
def test_unbookmark_removes_bookmark():
    user = User.objects.create_user(username="bm3")
    topic = _topic("bm-t3")
    TopicBookmark.bookmark(user, topic)

    client = APIClient()
    client.force_authenticate(user)
    resp = client.delete(f"/forum/topics/{topic.id}/bookmark/")

    assert resp.status_code == 200
    assert resp.data == {"bookmarked": False}
    assert not TopicBookmark.objects.filter(user=user, topic=topic).exists()


@pytest.mark.django_db
def test_unbookmark_when_not_bookmarked_is_idempotent():
    user = User.objects.create_user(username="bm4")
    topic = _topic("bm-t4")

    client = APIClient()
    client.force_authenticate(user)
    resp = client.delete(f"/forum/topics/{topic.id}/bookmark/")

    assert resp.status_code == 200
    assert resp.data == {"bookmarked": False}


@pytest.mark.django_db
def test_unbookmark_succeeds_when_topic_is_no_longer_live():
    """DELETE mutates only the caller's own bookmark row — same rationale as
    TopicSubscriptionView's equivalent regression test (todo 253 slice 3
    review): reusing POST's visibility gate on DELETE would strand an
    existing bookmarker."""
    user = User.objects.create_user(username="bm10")
    topic = _topic("bm-t10")
    TopicBookmark.bookmark(user, topic)
    topic.live = False
    topic.save()

    client = APIClient()
    client.force_authenticate(user)
    resp = client.delete(f"/forum/topics/{topic.id}/bookmark/")

    assert resp.status_code == 200
    assert resp.data == {"bookmarked": False}
    assert not TopicBookmark.objects.filter(user=user, topic=topic).exists()


@pytest.mark.django_db
def test_bookmark_requires_auth():
    topic = _topic("bm-t5")
    resp = APIClient().post(f"/forum/topics/{topic.id}/bookmark/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_unbookmark_requires_auth():
    topic = _topic("bm-t6")
    resp = APIClient().delete(f"/forum/topics/{topic.id}/bookmark/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_bookmark_draft_topic_404s():
    user = User.objects.create_user(username="bm7")
    topic = _topic("bm-t7", live=False)

    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(f"/forum/topics/{topic.id}/bookmark/")

    assert resp.status_code == 404
    assert not TopicBookmark.objects.filter(topic=topic).exists()


@pytest.mark.django_db
def test_bookmark_restricted_board_topic_404s():
    user = User.objects.create_user(username="bm8")
    board = _board("bm-b8")
    topic = _topic("bm-t8", board=board)
    PageViewRestriction.objects.create(page=board, restriction_type="login")

    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(f"/forum/topics/{topic.id}/bookmark/")

    assert resp.status_code == 404
    assert not TopicBookmark.objects.filter(topic=topic).exists()


@pytest.mark.django_db
def test_bookmark_nonexistent_topic_404s():
    user = User.objects.create_user(username="bm9")

    client = APIClient()
    client.force_authenticate(user)
    resp = client.post("/forum/topics/999999/bookmark/")

    assert resp.status_code == 404


# --- GET /me/bookmarks/ (AC2) ---------------------------------------------


@pytest.mark.django_db
def test_bookmarks_list_requires_auth():
    resp = APIClient().get("/forum/me/bookmarks/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_bookmarks_list_returns_only_the_requesting_users_bookmarks():
    user = User.objects.create_user(username="bm20")
    other = User.objects.create_user(username="bm21")
    mine = _topic("bm-t20")
    others = _topic("bm-t21")
    TopicBookmark.bookmark(user, mine)
    TopicBookmark.bookmark(other, others)

    client = APIClient()
    client.force_authenticate(user)
    resp = client.get("/forum/me/bookmarks/")

    assert resp.status_code == 200
    ids = [row["id"] for row in resp.data["results"]]
    assert ids == [mine.id]


@pytest.mark.django_db
def test_bookmarks_list_orders_most_recently_bookmarked_first():
    """Bookmarked in the OPPOSITE order to their creation/id order — the only
    arrangement where the `-bookmarked_at` ordering and the `-id` tiebreak
    disagree. Bookmarking in id order (as an earlier version of this test
    did) would still pass if `-bookmarked_at` were dropped from
    BookmarkCursorPagination entirely, since `-id` alone gives the same
    result — this shape actually proves the annotation drives the sort."""
    user = User.objects.create_user(username="bm22")
    lower_id = _topic("bm-t22")
    higher_id = _topic("bm-t23")
    # Bookmark the HIGHER-id topic first, so bookmark-recency and id order
    # disagree.
    TopicBookmark.bookmark(user, higher_id)
    TopicBookmark.bookmark(user, lower_id)

    client = APIClient()
    client.force_authenticate(user)
    resp = client.get("/forum/me/bookmarks/")

    ids = [row["id"] for row in resp.data["results"]]
    assert ids == [lower_id.id, higher_id.id]


@pytest.mark.django_db
def test_bookmarks_list_excludes_topic_on_restricted_board():
    """Same regression class as test_bookmark_restricted_board_topic_404s,
    for the LIST path: a bookmarked topic whose BOARD is later restricted
    must not leak into the Saved list either — the `live=True` check alone
    (covered by test_bookmarks_list_excludes_unpublished_topic) doesn't catch
    this; it needs the separate `board__in=_visible_boards()` clause."""
    user = User.objects.create_user(username="bm25")
    board = _board("bm-b25")
    topic = _topic("bm-t25", board=board)
    TopicBookmark.bookmark(user, topic)
    PageViewRestriction.objects.create(page=board, restriction_type="login")

    client = APIClient()
    client.force_authenticate(user)
    resp = client.get("/forum/me/bookmarks/")

    assert resp.data["results"] == []


@pytest.mark.django_db
def test_bookmarks_list_paginates_across_pages():
    """The cursor encodes/decodes the `bookmarked_at` annotation (not a real
    model column) — proves that round-trips through a second page, not just
    that page 1 renders."""
    user = User.objects.create_user(username="bm26")
    topics = [_topic(f"bm-t26-{i}") for i in range(3)]
    for topic in topics:
        TopicBookmark.bookmark(user, topic)

    client = APIClient()
    client.force_authenticate(user)
    first_page = client.get("/forum/me/bookmarks/?page_size=2")
    assert len(first_page.data["results"]) == 2
    assert first_page.data["next"] is not None

    second_page = client.get(first_page.data["next"])
    assert second_page.status_code == 200
    second_ids = [row["id"] for row in second_page.data["results"]]
    # Ordering is most-recently-bookmarked-first, and `topics` was bookmarked
    # in list order (topics[0] first, topics[2] last) — so the FIRST-
    # bookmarked (oldest) topic is the one pushed onto the second page.
    assert second_ids == [topics[0].id]


@pytest.mark.django_db
def test_bookmarks_list_query_count_is_pinned():
    """Guards the queryset shape (subquery annotation + 2 select_related
    chains + a tags prefetch) against a silent N+1 regression. Two topics
    WITH author/last_post_author set — a single-row or author-less fixture
    can't exercise the select_related joins at all (todo 282's
    fixture-coverage lesson: an unset FK short-circuits before the join is
    ever used)."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    user = User.objects.create_user(username="bm27")
    author = User.objects.create_user(username="bm27-author")
    board = _board("bm-b27")
    first = Topic.objects.create(
        board=board, title="T1", slug="bm-t27-1", author=author, live=True
    )
    second = Topic.objects.create(
        board=board, title="T2", slug="bm-t27-2", author=author, live=True
    )
    TopicBookmark.bookmark(user, first)
    TopicBookmark.bookmark(user, second)

    client = APIClient()
    client.force_authenticate(user)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/forum/me/bookmarks/")

    assert resp.status_code == 200
    assert len(resp.data["results"]) == 2
    # Pinned EXACTLY (docs/rules/testing.md): page-view-restriction check,
    # the bookmarked-topic page fetch (select_related author/last_post_author
    # down to ForumProfile.avatar + the bookmarked_at Subquery — all JOINs/
    # correlated subqueries, no extra queries), the is_unread annotation
    # (also a correlated subquery, api/views.py._annotate_topic_unread), and
    # the tags prefetch (todo 276 / M5) — ONE extra query for the whole page,
    # not one per row. If this changes, explain the new count here.
    assert len(ctx.captured_queries) == 3, [q["sql"] for q in ctx.captured_queries]


@pytest.mark.django_db
def test_bookmarks_list_excludes_unpublished_topic():
    """A bookmarked topic that has since been unpublished must not leak into
    the Saved list — mirrors _visible_notifications' topic clause."""
    user = User.objects.create_user(username="bm23")
    topic = _topic("bm-t24")
    TopicBookmark.bookmark(user, topic)
    topic.live = False
    topic.save()

    client = APIClient()
    client.force_authenticate(user)
    resp = client.get("/forum/me/bookmarks/")

    assert resp.data["results"] == []
