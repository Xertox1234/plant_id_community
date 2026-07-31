"""Bookmark toggle, saved list, and the is_bookmarked query pin (todo 283 / M2)."""

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail.models import Page, PageViewRestriction
from wagtail_forum.api.bookmarks import MeBookmarkListView
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    Post,
    Topic,
    TopicBookmark,
    TopicRead,
)

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board(slug="general"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    return index.add_child(instance=ForumBoard(title="General", slug=slug))


def _topic(slug="t", live=True, board=None, author=None):
    board = board or _board(slug)
    return Topic.objects.create(
        board=board, title="T", slug=slug, live=live, author=author
    )


# --------------------------------------------------------------------------
# Toggle
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_bookmark_creates_row():
    user = User.objects.create_user(username="bm1")
    topic = _topic("bm-t1")

    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(f"/forum/topics/{topic.id}/bookmark/")

    assert resp.status_code == 200
    assert resp.data == {"bookmarked": True}
    assert TopicBookmark.objects.filter(user=user, topic=topic).exists()


@pytest.mark.django_db
def test_bookmark_is_idempotent_two_posts_leave_exactly_one_row():
    """AC 1. A double-tapped toggle must not create a second row, and the
    second POST must still report success rather than 4xx-ing — the client
    treats the response as the new state, not as "did something change"."""
    user = User.objects.create_user(username="bm2")
    topic = _topic("bm-t2")

    client = APIClient()
    client.force_authenticate(user)
    first = client.post(f"/forum/topics/{topic.id}/bookmark/")
    second = client.post(f"/forum/topics/{topic.id}/bookmark/")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.data == {"bookmarked": True}
    assert TopicBookmark.objects.filter(user=user, topic=topic).count() == 1


@pytest.mark.django_db
def test_unbookmark_removes_row_and_is_idempotent():
    user = User.objects.create_user(username="bm3")
    topic = _topic("bm-t3")
    TopicBookmark.add(user, topic)

    client = APIClient()
    client.force_authenticate(user)
    first = client.delete(f"/forum/topics/{topic.id}/bookmark/")
    second = client.delete(f"/forum/topics/{topic.id}/bookmark/")

    assert first.status_code == 200
    assert first.data == {"bookmarked": False}
    assert second.status_code == 200  # deleting a non-bookmark is a no-op, not 404
    assert not TopicBookmark.objects.filter(user=user, topic=topic).exists()


@pytest.mark.django_db
def test_bookmark_requires_authentication():
    topic = _topic("bm-t4")

    resp = APIClient().post(f"/forum/topics/{topic.id}/bookmark/")

    # Exactly 401, not a (401, 403) set: the project's first authentication
    # class supplies a WWW-Authenticate header, so an anonymous request to an
    # IsAuthenticated view is deterministically 401 (docs/rules/testing.md).
    assert resp.status_code == 401
    assert not TopicBookmark.objects.exists()


@pytest.mark.django_db
def test_bookmark_hidden_topic_404s_without_leaking_existence():
    """POST is visibility-gated like TopicSubscriptionView.post — a draft topic
    must 404, not 200, or the response confirms the topic exists."""
    user = User.objects.create_user(username="bm5")
    topic = _topic("bm-t5", live=False)

    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(f"/forum/topics/{topic.id}/bookmark/")

    assert resp.status_code == 404
    assert not TopicBookmark.objects.exists()


@pytest.mark.django_db
def test_unbookmark_still_works_after_topic_is_unpublished():
    """DELETE is deliberately NOT visibility-gated (mirrors
    TopicSubscriptionView.delete): a member whose bookmarked topic gets
    unpublished must still be able to clear the row, not be stranded with a
    dead entry they cannot remove."""
    user = User.objects.create_user(username="bm6")
    topic = _topic("bm-t6")
    TopicBookmark.add(user, topic)
    topic.live = False
    topic.save(update_fields=["live"])

    client = APIClient()
    client.force_authenticate(user)
    resp = client.delete(f"/forum/topics/{topic.id}/bookmark/")

    assert resp.status_code == 200
    assert not TopicBookmark.objects.filter(user=user, topic=topic).exists()


# --------------------------------------------------------------------------
# Saved list
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_me_bookmarks_returns_only_the_requesting_users_rows():
    """AC 2, first half."""
    mine = User.objects.create_user(username="bm-mine")
    theirs = User.objects.create_user(username="bm-theirs")
    board = _board("bm-list")
    my_topic = _topic("bm-list-mine", board=board)
    their_topic = _topic("bm-list-theirs", board=board)
    TopicBookmark.add(mine, my_topic)
    TopicBookmark.add(theirs, their_topic)

    client = APIClient()
    client.force_authenticate(mine)
    resp = client.get("/forum/me/bookmarks/")

    assert resp.status_code == 200
    assert [row["id"] for row in resp.data["results"]] == [my_topic.id]
    # Every row carries its own board — the saved list spans boards, and the
    # client builds each thread URL from it. Without this the links 404.
    assert resp.data["results"][0]["board"] == {
        "id": board.id,
        "slug": board.slug,
        "title": board.title,
    }


@pytest.mark.django_db
def test_me_bookmarks_401s_for_anonymous():
    """AC 2, second half. Exactly 401 — see the toggle's auth test for why the
    code is deterministic rather than a (401, 403) set."""
    resp = APIClient().get("/forum/me/bookmarks/")

    assert resp.status_code == 401


@pytest.mark.django_db
def test_me_bookmarks_orders_newest_saved_first():
    """Not the topic's own activity order — the list is the member's own
    curation, so it reads in the order they built it (BookmarkCursorPagination)."""
    user = User.objects.create_user(username="bm-order")
    board = _board("bm-order-b")
    first = _topic("bm-order-1", board=board)
    second = _topic("bm-order-2", board=board)
    third = _topic("bm-order-3", board=board)
    for topic in (first, second, third):
        TopicBookmark.add(user, topic)

    client = APIClient()
    client.force_authenticate(user)
    resp = client.get("/forum/me/bookmarks/")

    assert [row["id"] for row in resp.data["results"]] == [
        third.id,
        second.id,
        first.id,
    ]


@pytest.mark.django_db
def test_me_bookmarks_omits_a_topic_that_became_invisible():
    """A topic unpublished or moved behind a restriction AFTER being saved must
    drop out of the list rather than leak its title and author through it. The
    bookmark row survives so it reappears if the topic comes back."""
    user = User.objects.create_user(username="bm-vis")
    board = _board("bm-vis-b")
    visible = _topic("bm-vis-1", board=board)
    unpublished = _topic("bm-vis-2", board=board)
    restricted_board = _board("bm-vis-restricted")
    behind_restriction = _topic("bm-vis-3", board=restricted_board)
    for topic in (visible, unpublished, behind_restriction):
        TopicBookmark.add(user, topic)

    unpublished.live = False
    unpublished.save(update_fields=["live"])
    PageViewRestriction.objects.create(
        page=restricted_board, restriction_type=PageViewRestriction.LOGIN
    )

    client = APIClient()
    client.force_authenticate(user)
    resp = client.get("/forum/me/bookmarks/")

    assert [row["id"] for row in resp.data["results"]] == [visible.id]
    # The rows themselves are untouched — this is a read filter, not a purge.
    assert TopicBookmark.objects.filter(user=user).count() == 3


@pytest.mark.django_db
def test_me_bookmarks_rows_carry_is_unread():
    """The saved list serves a subclass of TopicListSerializer, whose
    `is_unread` is a plain read-only BooleanField fed by the view's
    `_annotate_topic_unread`. DRF SKIPS such a field silently when its
    attribute is missing, so dropping that call does not raise — the key just
    vanishes from every row, `tsc` still believes it is there, and the badge
    quietly never renders. Assert PRESENCE explicitly, not just the value.
    """
    user = User.objects.create_user(username="bm-unread")
    board = _board("bm-unread-b")
    topic = _topic("bm-unread-t", board=board)
    # Real activity: `is_unread` compares last_post_at against the viewer's
    # baseline, and a topic with a NULL last_post_at yields NULL (not False),
    # which would make this test pass for the wrong reason.
    topic.last_post_at = timezone.now()
    topic.save(update_fields=["last_post_at"])
    TopicBookmark.add(user, topic)

    client = APIClient()
    client.force_authenticate(user)
    row = client.get("/forum/me/bookmarks/").data["results"][0]

    assert "is_unread" in row
    # A topic the viewer has never opened, active since the launch baseline,
    # is unread — so this also proves the annotation is the real chain and not
    # a constant.
    assert row["is_unread"] is True

    TopicRead.objects.create(user=user, topic=topic, last_read_at=timezone.now())
    refreshed = client.get("/forum/me/bookmarks/").data["results"][0]
    assert refreshed["is_unread"] is False


@pytest.mark.django_db
def test_me_bookmarks_cursor_pages_through_without_gaps_or_duplicates():
    """BookmarkCursorPagination orders on `bookmarked_at`, a Subquery
    annotation that DRF's cursor also puts in a WHERE clause to seek. A
    3-row test never crosses the 20-row page boundary, so it cannot exercise
    that seek at all — this creates 21 and actually follows `next`.
    """
    user = User.objects.create_user(username="bm-cursor")
    board = _board("bm-cursor-b")
    topics = [_topic(f"bm-cursor-{i}", board=board) for i in range(21)]
    for topic in topics:
        TopicBookmark.add(user, topic)

    client = APIClient()
    client.force_authenticate(user)
    first = client.get("/forum/me/bookmarks/")

    assert first.status_code == 200
    assert len(first.data["results"]) == 20
    assert first.data["next"]

    second = client.get(first.data["next"])

    assert second.status_code == 200, second.data
    seen = [row["id"] for row in first.data["results"]] + [
        row["id"] for row in second.data["results"]
    ]
    # Every bookmark appears exactly once across the two pages.
    assert len(seen) == 21
    assert len(set(seen)) == 21
    assert set(seen) == {topic.id for topic in topics}
    # Newest-saved first still holds ACROSS the boundary, not just within a page.
    assert seen == [topic.id for topic in reversed(topics)]


@pytest.mark.django_db
def test_me_bookmarks_does_not_scale_queries_with_page_size():
    """The saved list serves TopicListSerializer, whose `tags` and unified
    author object are per-row reads — without the prefetch and the
    select_related chain replicated from TopicListView, this grows with the
    number of saved topics. Pinned EXACTLY (docs/rules/testing.md): comparing
    a 1-topic page against a 5-topic page proves flatness without hardcoding a
    count that unrelated middleware could shift."""
    user = User.objects.create_user(username="bm-pin")
    board = _board("bm-pin-b")
    topics = [_topic(f"bm-pin-{i}", board=board) for i in range(5)]
    TopicBookmark.add(user, topics[0])

    client = APIClient()
    client.force_authenticate(user)
    with CaptureQueriesContext(connection) as one_row:
        client.get("/forum/me/bookmarks/")

    for topic in topics[1:]:
        TopicBookmark.add(user, topic)
    with CaptureQueriesContext(connection) as five_rows:
        resp = client.get("/forum/me/bookmarks/")

    assert len(resp.data["results"]) == 5
    assert len(five_rows.captured_queries) == len(one_row.captured_queries)


@pytest.mark.django_db
def test_me_bookmarks_swagger_fake_view_short_circuits():
    """drf-spectacular never calls get_queryset() for a ListAPIView's schema,
    so no schema-content test would catch this guard being removed — and
    without it, schema generation hits `self.request.user` on a view with no
    request. Exercised directly."""
    view = MeBookmarkListView()
    view.swagger_fake_view = True

    assert not view.get_queryset().exists()


# --------------------------------------------------------------------------
# is_bookmarked on topic detail
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_topic_detail_is_bookmarked_reflects_caller_state():
    board = _board("bm-detail")
    author = User.objects.create_user(username="bm-detail-author")
    saver = User.objects.create_user(username="bm-detail-saver")
    other = User.objects.create_user(username="bm-detail-other")
    topic = _topic("bm-detail-t", board=board, author=author)
    Post.objects.create(topic=topic, author=author, is_opening_post=True, live=True)
    TopicBookmark.add(saver, topic)

    client = APIClient()
    client.force_authenticate(saver)
    assert client.get(f"/forum/topics/{topic.id}/").data["is_bookmarked"] is True

    client.force_authenticate(other)
    assert client.get(f"/forum/topics/{topic.id}/").data["is_bookmarked"] is False


@pytest.mark.django_db
def test_topic_detail_is_bookmarked_is_false_for_anonymous():
    board = _board("bm-anon")
    author = User.objects.create_user(username="bm-anon-author")
    topic = _topic("bm-anon-t", board=board, author=author)
    Post.objects.create(topic=topic, author=author, is_opening_post=True, live=True)

    resp = APIClient().get(f"/forum/topics/{topic.id}/")

    assert resp.data["is_bookmarked"] is False


@pytest.mark.django_db
def test_is_bookmarked_adds_no_queries_to_topic_detail():
    """AC 3. `is_bookmarked` is annotated via Exists(), which compiles to a
    scalar subquery inside the SELECT the view already runs — so it costs
    nothing. Pinned EXACTLY (docs/rules/testing.md) against the SAME counts
    test_topic_detail.py asserted before this field existed: 5 anonymous, 8 for
    an authenticated non-author. Those two tests are the other half of this
    assertion; if either moves, this field is no longer free and the change
    must be explained in both places.

    The topic LIST is unaffected for a different reason: the field is
    deliberately detail-only (see _annotate_topic_bookmarked), so
    TopicListSerializer never renders it and test_topics_list.py's pins are
    untouched by construction.
    """
    board = _board("bm-pin-detail")
    author = User.objects.create_user(username="bm-pin-author")
    viewer = User.objects.create_user(username="bm-pin-viewer")
    topic = _topic("bm-pin-detail-t", board=board, author=author)
    Post.objects.create(topic=topic, author=author, is_opening_post=True, live=True)
    TopicBookmark.add(viewer, topic)

    with CaptureQueriesContext(connection) as anon_ctx:
        anon_resp = APIClient().get(f"/forum/topics/{topic.id}/")
    assert anon_resp.data["is_bookmarked"] is False
    assert len(anon_ctx.captured_queries) == 5

    client = APIClient()
    client.force_authenticate(viewer)
    with CaptureQueriesContext(connection) as auth_ctx:
        auth_resp = client.get(f"/forum/topics/{topic.id}/")
    assert auth_resp.data["is_bookmarked"] is True
    assert len(auth_ctx.captured_queries) == 8
