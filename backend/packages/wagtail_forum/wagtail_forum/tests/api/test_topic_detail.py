import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board(slug="general"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug=slug))


@pytest.mark.django_db
def test_topic_detail_returns_live_topic():
    board = _board()
    author = User.objects.create_user(username="ada")
    topic = Topic.objects.create(
        board=board, title="Hello", slug="hello", author=author, live=True
    )
    opening = Post.objects.create(
        topic=topic, author=author, is_opening_post=True, live=True
    )

    with CaptureQueriesContext(connection) as ctx:
        resp = APIClient().get(f"/forum/topics/{topic.id}/")

    assert resp.status_code == 200
    assert resp.data["id"] == topic.id
    assert resp.data["title"] == "Hello"
    assert resp.data["board"]["slug"] == "general"
    assert resp.data["author"] == "ada"
    assert resp.data["opening_post_id"] == opening.id
    # Anonymous is_subscribed short-circuits with zero extra queries (todo
    # 253 slice 3) — the pin below stays 4, not 5, for this request.
    assert resp.data["is_subscribed"] is False
    # Exactly 4: page-view-restriction check, topic fetch (select_related board/author),
    # opening-post id lookup, post refetch by id.
    # Pinned EXACTLY (docs/rules/testing.md) — if this changes, explain the new count here.
    assert len(ctx.captured_queries) == 4


@pytest.mark.django_db
def test_topic_detail_is_subscribed_for_authenticated_user():
    """is_subscribed reflects the requesting user's TopicSubscription state
    (todo 253 slice 3) and costs exactly one extra query over the anonymous
    pin — the anonymous case (4, above) short-circuits before ever touching
    TopicSubscription."""
    from wagtail_forum.models import TopicSubscription

    board = _board(slug="sub-board")
    author = User.objects.create_user(username="sub-author")
    subscriber = User.objects.create_user(username="sub-subscriber")
    non_subscriber = User.objects.create_user(username="sub-nonsubscriber")
    topic = Topic.objects.create(
        board=board, title="Sub", slug="sub", author=author, live=True
    )
    Post.objects.create(topic=topic, author=author, is_opening_post=True, live=True)
    TopicSubscription.subscribe(subscriber, topic)

    client = APIClient()
    client.force_authenticate(subscriber)
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(f"/forum/topics/{topic.id}/")
    assert resp.data["is_subscribed"] is True
    # Pinned EXACTLY (docs/rules/testing.md): the anonymous pin (4) + one
    # TopicSubscription.objects.filter(...).exists() query.
    assert len(ctx.captured_queries) == 5

    client.force_authenticate(non_subscriber)
    resp = client.get(f"/forum/topics/{topic.id}/")
    assert resp.data["is_subscribed"] is False


@pytest.mark.django_db
def test_topic_detail_hides_draft_topic():
    board = _board()
    topic = Topic.objects.create(board=board, title="Draft", slug="draft", live=False)
    assert APIClient().get(f"/forum/topics/{topic.id}/").status_code == 404


@pytest.mark.django_db
def test_topic_detail_hides_topic_on_unpublished_board():
    board = _board()
    board.live = False
    board.save()
    topic = Topic.objects.create(board=board, title="X", slug="x", live=True)
    assert APIClient().get(f"/forum/topics/{topic.id}/").status_code == 404


# ---- view_count tests -------------------------------------------------------


# These tests must NOT use django_db(transaction=True): its teardown flush
# deletes Wagtail's migration-seeded root page, breaking every later test that
# calls _board(). django_capture_on_commit_callbacks runs the on_commit hook
# without needing real commits.
@pytest.mark.django_db
@override_settings(WAGTAILFORUM_VIEW_COUNT_DEDUP_SECONDS=900)
def test_view_count_increments_on_get(django_capture_on_commit_callbacks):
    cache.clear()
    board = _board(slug="vc-board")
    topic = Topic.objects.create(board=board, title="VC", slug="vc", live=True)
    assert topic.view_count == 0

    with django_capture_on_commit_callbacks(execute=True):
        APIClient().get(f"/forum/topics/{topic.id}/")

    topic.refresh_from_db()
    assert topic.view_count == 1


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_VIEW_COUNT_DEDUP_SECONDS=900)
def test_view_count_does_not_double_count_within_dedup_window(
    django_capture_on_commit_callbacks,
):
    # Dedup uses cache.add() (atomic test-and-set), so concurrent same-viewer
    # requests can't both win the race the way a get/set pair would.
    cache.clear()
    board = _board(slug="vc-board2")
    topic = Topic.objects.create(board=board, title="VC2", slug="vc2", live=True)

    client = APIClient()
    with django_capture_on_commit_callbacks(execute=True):
        client.get(f"/forum/topics/{topic.id}/")
        client.get(f"/forum/topics/{topic.id}/")  # same viewer, same window

    topic.refresh_from_db()
    assert topic.view_count == 1


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_VIEW_COUNT_DEDUP_SECONDS=900)
def test_view_count_counts_different_users_independently(
    django_capture_on_commit_callbacks,
):
    cache.clear()
    board = _board(slug="vc-board3")
    topic = Topic.objects.create(board=board, title="VC3", slug="vc3", live=True)
    u1 = User.objects.create_user(username="v1")
    u2 = User.objects.create_user(username="v2")

    with django_capture_on_commit_callbacks(execute=True):
        c1 = APIClient()
        c1.force_authenticate(u1)
        c1.get(f"/forum/topics/{topic.id}/")

        c2 = APIClient()
        c2.force_authenticate(u2)
        c2.get(f"/forum/topics/{topic.id}/")

    topic.refresh_from_db()
    assert topic.view_count == 2


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_VIEW_COUNT_DEDUP_SECONDS=0)
def test_view_count_recounts_after_dedup_window_expires(
    django_capture_on_commit_callbacks,
):
    cache.clear()
    board = _board(slug="vc-board4")
    topic = Topic.objects.create(board=board, title="VC4", slug="vc4", live=True)

    client = APIClient()
    with django_capture_on_commit_callbacks(execute=True):
        client.get(f"/forum/topics/{topic.id}/")
        # TTL=0 means the cache entry expires immediately — next request is a new view.
        client.get(f"/forum/topics/{topic.id}/")

    topic.refresh_from_db()
    assert topic.view_count == 2


@pytest.mark.django_db
def test_view_count_does_not_add_queries_to_response():
    # on_commit fires AFTER the response transaction; the pinned query count
    # for the response itself must be unchanged (still 4).
    cache.clear()
    board = _board(slug="vc-board5")
    author = User.objects.create_user(username="vcq")
    topic = Topic.objects.create(
        board=board, title="VCQ", slug="vcq", author=author, live=True
    )
    Post.objects.create(topic=topic, author=author, is_opening_post=True, live=True)

    with CaptureQueriesContext(connection) as ctx:
        resp = APIClient().get(f"/forum/topics/{topic.id}/")

    assert resp.status_code == 200
    assert len(ctx.captured_queries) == 4
