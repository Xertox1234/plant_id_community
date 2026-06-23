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
    # Non-integer compound-cursor id: reject rather than silently reset to 0.
    assert client.get("/forum/sync/?since_id=abc").status_code == 400


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
    # next_since/next_since_id are the LAST RETURNED row's (updated_at, id); paired
    # they let the compound cursor resume strictly after it (no repeat, no loss).
    last = Topic.objects.get(slug="t1")
    assert resp.data["next_since"] == last.updated_at
    assert resp.data["next_since_id"] == last.id


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


@pytest.mark.django_db
def test_sync_compound_cursor_advances_through_same_timestamp_rows(monkeypatch):
    """AC3: >MAX_TOPICS topics sharing one updated_at must paginate, not livelock.

    The old `updated_at >= since` cursor returned the same first page forever
    when a whole page shared one timestamp (bulk import). The compound
    (updated_at, id) cursor advances by id within the tie.
    """
    from wagtail_forum.api import views as forum_views

    monkeypatch.setattr(forum_views.SyncView, "MAX_TOPICS", 2)
    board = _board()
    ids = []
    for i in range(3):
        t = Topic.objects.create(board=board, title=f"t{i}", slug=f"t{i}", live=True)
        ids.append(t.id)
    shared = datetime.datetime(2026, 6, 23, tzinfo=datetime.timezone.utc)
    Topic.objects.filter(id__in=ids).update(updated_at=shared)
    ids.sort()  # order_by("updated_at", "id") => ascending id within the tie

    client = APIClient()
    page1 = client.get("/forum/sync/", {"board": board.slug}).data
    assert [t["id"] for t in page1["topics"]] == ids[:2]
    assert page1["has_more"] is True

    # Pass the compound cursor via the data dict so the +00:00 offset is URL-
    # encoded (an f-string `since=...+00:00` decodes the `+` as a space → 400).
    since = page1["next_since"]
    if not isinstance(since, str):
        since = since.isoformat()
    page2 = client.get(
        "/forum/sync/",
        {"board": board.slug, "since": since, "since_id": page1["next_since_id"]},
    ).data
    # Progress: the third row only, never a repeat of the first page.
    assert [t["id"] for t in page2["topics"]] == [ids[2]]
    assert page2["has_more"] is False


@pytest.mark.django_db
def test_sync_without_since_id_includes_exact_boundary_row():
    """First sync (since given, no since_id) keeps the old >= boundary: a row
    stamped exactly at `since` is returned, not skipped (since_id defaults to 0).
    """
    board = _board()
    t = Topic.objects.create(board=board, title="boundary", slug="b", live=True)
    boundary = datetime.datetime(2026, 6, 23, 12, 0, tzinfo=datetime.timezone.utc)
    Topic.objects.filter(id=t.id).update(updated_at=boundary)

    resp = (
        APIClient()
        .get("/forum/sync/", {"board": board.slug, "since": boundary.isoformat()})
        .data
    )
    assert [x["id"] for x in resp["topics"]] == [t.id]
