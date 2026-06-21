import datetime

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()

pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


@pytest.mark.django_db
def test_search_returns_matching_topics():
    board = _board()
    Topic.objects.create(board=board, title="Monstera care", slug="m", live=True)

    resp = APIClient().get("/forum/search/?q=Monstera")
    assert resp.status_code == 200
    assert any(t["slug"] == "m" for t in resp.data["topics"])


@pytest.mark.django_db
def test_sync_returns_topics_changed_since():
    board = _board()
    old = Topic.objects.create(board=board, title="old", slug="old", live=True)
    Topic.objects.filter(id=old.id).update(
        updated_at=datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
    )
    Topic.objects.create(board=board, title="fresh", slug="fresh", live=True)

    since = "2021-01-01T00:00:00Z"
    resp = APIClient().get(f"/forum/sync/?since={since}&board={board.slug}")
    assert resp.status_code == 200
    slugs = [t["slug"] for t in resp.data["topics"]]
    assert "fresh" in slugs and "old" not in slugs


@pytest.mark.django_db
def test_sync_rejects_invalid_or_naive_since():
    _board()
    client = APIClient()
    # Unparseable: silently full-syncing would mask a broken client (audit M11).
    assert client.get("/forum/sync/?since=not-a-date").status_code == 400
    # Naive datetime: would be interpreted in the server TZ — silent drift.
    assert client.get("/forum/sync/?since=2026-06-10T00:00:00").status_code == 400


@pytest.mark.django_db
def test_sync_reports_truncation_and_continuation():
    board = _board()
    t = Topic.objects.create(board=board, title="a", slug="a", live=True)

    resp = APIClient().get(f"/forum/sync/?board={board.slug}")

    assert resp.data["has_more"] is False
    # next_since lets the client continue from the last row it received.
    assert resp.data["next_since"] == t.updated_at


@pytest.mark.django_db
def test_sync_truncation_sets_has_more_and_boundary_next_since(monkeypatch):
    from wagtail_forum.api import views as forum_views

    monkeypatch.setattr(forum_views.SyncView, "MAX_TOPICS", 2)
    board = _board()
    for i in range(3):
        Topic.objects.create(board=board, title=f"t{i}", slug=f"t{i}", live=True)

    resp = APIClient().get(f"/forum/sync/?board={board.slug}")

    assert len(resp.data["topics"]) == 2
    assert resp.data["has_more"] is True
    # next_since is the LAST RETURNED row's timestamp; with the >= boundary the
    # client re-receives that row and upserts by id — never loses one.
    assert resp.data["next_since"] == Topic.objects.get(slug="t1").updated_at


@pytest.mark.django_db
def test_search_returns_topics_and_posts():
    board = _board()
    author = User.objects.create_user(username="ada", password="x")
    topic = Topic.objects.create(
        board=board, title="Monstera care", slug="monstera", author=author, live=True
    )
    post = Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": "<p>watering a monstera</p>"}],
    )

    resp = APIClient().get("/forum/search/?q=monstera")

    assert resp.status_code == 200
    assert "topics" in resp.data and "posts" in resp.data
    assert any(t["id"] == topic.id for t in resp.data["topics"])
    assert any(p["id"] == post.id for p in resp.data["posts"])
