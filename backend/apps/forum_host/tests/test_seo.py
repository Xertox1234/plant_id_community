"""Forum SEO surface (todo 256 H9): sitemap.xml + RSS feed.

The load-bearing test is visibility: a live topic on a hidden/view-restricted
board must be ABSENT from both the sitemap and the feed — a public crawl surface
must never leak restricted content.
"""

import pytest
from django.conf import settings
from rest_framework.test import APIClient
from wagtail.models import Page, PageViewRestriction
from wagtail_forum.models import ForumBoard, ForumIndex, Topic

_SITE = settings.SITE_URL.rstrip("/")


def _tree():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    return index, board


@pytest.mark.django_db
def test_sitemap_lists_index_board_and_live_topic_at_frontend_urls():
    _index, board = _tree()
    topic = Topic.objects.create(
        board=board, title="Monstera care", slug="monstera", live=True
    )

    resp = APIClient().get("/forum/sitemap.xml")
    assert resp.status_code == 200
    xml = resp.content.decode()

    # Every <loc> is the SPA frontend URL (SITE_URL), not the backend host.
    assert f"<loc>{_SITE}/forum</loc>" in xml  # index
    assert f"<loc>{_SITE}/forum/{board.id}-general</loc>" in xml  # board
    assert f"<loc>{_SITE}{topic.get_absolute_url()}</loc>" in xml  # topic


@pytest.mark.django_db
def test_sitemap_excludes_draft_topic():
    _index, board = _tree()
    draft = Topic.objects.create(board=board, title="Draft", slug="draft", live=False)
    xml = APIClient().get("/forum/sitemap.xml").content.decode()
    assert draft.get_absolute_url() not in xml


@pytest.mark.django_db
def test_sitemap_and_feed_exclude_restricted_board_topics():
    # LOAD-BEARING: a view-restricted board is invisible to the whole API
    # (_visible_boards uses .public()); its topics must not leak into the public
    # crawl surface either.
    _index, board = _tree()
    PageViewRestriction.objects.create(page=board, restriction_type="login")
    topic = Topic.objects.create(board=board, title="Secret", slug="secret", live=True)

    sitemap = APIClient().get("/forum/sitemap.xml").content.decode()
    feed = APIClient().get("/forum/rss/").content.decode()

    assert topic.get_absolute_url() not in sitemap
    assert topic.get_absolute_url() not in feed
    # The restricted board page itself is absent from the sitemap.
    assert f"/forum/{board.id}-general</loc>" not in sitemap


@pytest.mark.django_db
def test_rss_feed_lists_live_topic_with_frontend_link():
    _index, board = _tree()
    topic = Topic.objects.create(board=board, title="Fern care", slug="fern", live=True)

    resp = APIClient().get("/forum/rss/")
    assert resp.status_code == 200
    xml = resp.content.decode()

    assert "Fern care" in xml
    assert f"{_SITE}{topic.get_absolute_url()}" in xml


@pytest.mark.django_db
def test_rss_feed_excludes_draft_topic():
    # The feed's own live=True guard needs coverage — the sitemap's is covered by
    # test_sitemap_excludes_draft_topic, but the feed filters independently.
    _index, board = _tree()
    draft = Topic.objects.create(board=board, title="Draft", slug="draft", live=False)
    xml = APIClient().get("/forum/rss/").content.decode()
    assert draft.get_absolute_url() not in xml


@pytest.mark.django_db
def test_sitemap_and_feed_exclude_ancestor_restricted_topics():
    # `.public()` excludes not just directly-restricted pages but descendants of
    # a restricted ancestor. Restrict the ForumIndex and assert the board + its
    # topic vanish from both surfaces — locks in the inheritance the code relies on.
    index, board = _tree()
    PageViewRestriction.objects.create(page=index, restriction_type="login")
    topic = Topic.objects.create(board=board, title="Secret", slug="secret", live=True)

    sitemap = APIClient().get("/forum/sitemap.xml").content.decode()
    feed = APIClient().get("/forum/rss/").content.decode()

    assert topic.get_absolute_url() not in sitemap
    assert topic.get_absolute_url() not in feed
    assert f"/forum/{board.id}-general</loc>" not in sitemap
    assert "<loc>" + _SITE + "/forum</loc>" not in sitemap  # restricted index too


@pytest.mark.django_db
def test_sitemap_and_feed_query_counts_are_flat():
    # Both endpoints gate visibility via .public() (a PageViewRestriction lookup),
    # so pin the exact query count — a dropped select_related('board') or a
    # per-topic query in location()/item_link() would regress it (docs/rules).
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    _index, board = _tree()
    for i in range(5):
        Topic.objects.create(board=board, title=f"T{i}", slug=f"t{i}", live=True)

    with CaptureQueriesContext(connection) as ctx:
        assert APIClient().get("/forum/sitemap.xml").status_code == 200
    sitemap_queries = len(ctx.captured_queries)

    with CaptureQueriesContext(connection) as ctx:
        assert APIClient().get("/forum/rss/").status_code == 200
    rss_queries = len(ctx.captured_queries)

    # Flat regardless of topic count (select_related('board') covers the only FK).
    # sitemap = 8 (two sections, each with a .public() PageViewRestriction lookup);
    # rss = 2 (topics query + one .public() lookup). Exact, not <= (docs/rules).
    assert sitemap_queries == 8, sitemap_queries
    assert rss_queries == 2, rss_queries
