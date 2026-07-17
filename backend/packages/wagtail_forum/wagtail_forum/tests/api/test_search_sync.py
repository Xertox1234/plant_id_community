import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
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
    author = User.objects.create_user(username="ada")
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
def test_search_post_excerpts_are_plain_text_with_flat_queries():
    # Audit 2026-07-11 H24: the excerpt used body.render_as_block(), which
    # resolves the StreamValue and bulk-fetches image blocks PER POST (+1 query
    # per image-bearing hit) and could slice HTML mid-tag. The raw_data excerpt
    # must keep the query count flat and emit plain text.
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    from wagtail.images import get_image_model
    from wagtail.images.tests.utils import get_test_image_file

    board = _board()
    author = User.objects.create_user(username="ada")
    image = get_image_model().objects.create(title="leaf", file=get_test_image_file())

    def make(i):
        topic = Topic.objects.create(
            board=board,
            title=f"Fern topic {i}",
            slug=f"fern-{i}",
            author=author,
            live=True,
        )
        Post.objects.create(
            topic=topic,
            author=author,
            is_opening_post=True,
            live=True,
            body=[
                {"type": "paragraph", "value": "<p>My <b>fern</b> is wilting</p>"},
                {"type": "image", "value": image.id},
            ],
        )

    make(0)
    client = APIClient()
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/forum/search/?q=fern")
    assert resp.status_code == 200
    assert len(resp.data["posts"]) == 1
    queries_one_post = len(ctx.captured_queries)

    for i in range(1, 5):
        make(i)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get("/forum/search/?q=fern")
    assert resp.status_code == 200
    assert len(resp.data["posts"]) == 5
    # Flat: 5 image-bearing hits must cost the same as 1 (no per-post
    # chooser resolution). Pinned as equality per docs/rules/testing.md.
    assert len(ctx.captured_queries) == queries_one_post

    excerpt = resp.data["posts"][0]["excerpt"]
    assert "My fern is wilting" in excerpt
    assert "<" not in excerpt  # plain text — no tags, no dangling-slice risk


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


# ---- tombstone / delta-sync tests -------------------------------------------


@pytest.mark.django_db
def test_deleted_topic_appears_in_sync_deleted_list():
    """A topic deleted after `since` must surface in the `deleted` list so
    mobile clients can evict it from their local cache (Issue 6)."""
    board = _board()
    before = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    topic = Topic.objects.create(board=board, title="gone", slug="gone", live=True)
    saved_id = topic.pk
    saved_board_id = board.pk
    topic.delete()

    resp = APIClient().get(
        "/forum/sync/", {"since": before.isoformat(), "board": board.slug}
    )
    assert resp.status_code == 200
    deleted_ids = [d["topic_id"] for d in resp.data["deleted"]]
    assert saved_id in deleted_ids
    # board_id is also returned so clients can scope the eviction
    deleted_board_ids = [d["board_id"] for d in resp.data["deleted"]]
    assert saved_board_id in deleted_board_ids


@pytest.mark.django_db
def test_full_resync_without_since_returns_empty_deleted():
    """A full resync (no `since`) always returns deleted=[] regardless of
    how many tombstones exist — clients rebuild from the topics list."""
    from wagtail_forum.models.tombstones import TopicDeletedLog

    TopicDeletedLog.objects.create(topic_id=999, board_id=1)

    resp = APIClient().get("/forum/sync/")
    assert resp.status_code == 200
    assert resp.data["deleted"] == []


@pytest.mark.django_db
def test_tombstone_not_returned_before_its_deleted_at():
    """A deletion that happened before the client's `since` must NOT appear
    in `deleted` — the client already knew about it (or never had it)."""
    from wagtail_forum.models.tombstones import TopicDeletedLog

    old_deletion = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
    TopicDeletedLog.objects.create(topic_id=42, board_id=1, deleted_at=old_deletion)
    since = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)

    resp = APIClient().get("/forum/sync/", {"since": since.isoformat()})
    assert resp.status_code == 200
    assert resp.data["deleted"] == []


@pytest.mark.django_db
def test_prune_tombstones_command_removes_old_rows(capsys):
    """prune_forum_tombstones deletes rows older than --days and leaves
    newer rows intact."""
    from django.core.management import call_command
    from wagtail_forum.models.tombstones import TopicDeletedLog

    old = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
    TopicDeletedLog.objects.create(topic_id=1, board_id=1, deleted_at=old)
    TopicDeletedLog.objects.create(topic_id=2, board_id=1)  # now — recent

    call_command("prune_forum_tombstones", days=30)

    assert not TopicDeletedLog.objects.filter(topic_id=1).exists()
    assert TopicDeletedLog.objects.filter(topic_id=2).exists()
    out = capsys.readouterr().out
    assert "Pruned 1 tombstone row(s)" in out


@pytest.mark.django_db
def test_search_topics_include_metadata_and_board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum-meta"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general-meta"))
    topic = Topic.objects.create(
        board=board, title="Monstera propagation tips", slug="monstera-meta"
    )
    topic.reply_count = 3
    topic.view_count = 7
    topic.last_post_at = timezone.now()
    topic.save()

    resp = APIClient().get("/forum/search/", {"q": "Monstera"})

    assert resp.status_code == 200
    entry = next(t for t in resp.data["topics"] if t["id"] == topic.id)
    assert entry["reply_count"] == 3
    assert entry["view_count"] == 7
    assert entry["last_post_at"] is not None
    assert entry["board_id"] == board.id
    assert entry["board_slug"] == "general-meta"


@pytest.mark.django_db
def test_search_board_filter_narrows_topics_and_posts():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum-filter"))
    board_a = index.add_child(instance=ForumBoard(title="A", slug="board-a"))
    board_b = index.add_child(instance=ForumBoard(title="B", slug="board-b"))
    topic_a = Topic.objects.create(board=board_a, title="Fern care", slug="fern-a")
    topic_b = Topic.objects.create(board=board_b, title="Fern care", slug="fern-b")
    author = User.objects.create_user(username="fern_author")
    Post.objects.create(
        topic=topic_a,
        author=author,
        body=[{"type": "paragraph", "value": "<p>Fern watering schedule</p>"}],
    )
    Post.objects.create(
        topic=topic_b,
        author=author,
        body=[{"type": "paragraph", "value": "<p>Fern watering schedule</p>"}],
    )

    resp = APIClient().get("/forum/search/", {"q": "Fern", "board": "board-a"})

    assert resp.status_code == 200
    assert {t["id"] for t in resp.data["topics"]} == {topic_a.id}
    assert all(p["board_slug"] == "board-a" for p in resp.data["posts"])
    post_entry = resp.data["posts"][0]
    assert post_entry["topic_slug"] == "fern-a"
    assert post_entry["board_id"] == board_a.id
