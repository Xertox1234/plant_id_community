from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    TopicRead,
)

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
    # Unified author object (todo 257 H26): every topic/post author is the same
    # shape. `ada` has no ForumProfile row → display_name falls back to the
    # username, avatar/trust_level are null.
    assert resp.data["author"] == {
        "username": "ada",
        "display_name": "ada",
        "avatar": None,
        "trust_level": None,
    }
    assert resp.data["opening_post_id"] == opening.id
    # Anonymous is_subscribed short-circuits with zero extra queries (todo
    # 253 slice 3) — the pin below stays 5, not 6, for this request.
    assert resp.data["is_subscribed"] is False
    # Exactly 5: page-view-restriction check, topic fetch (select_related board +
    # author/last_post_author down to ForumProfile.avatar — LEFT JOINs, no extra
    # queries), opening-post id lookup, post refetch by id, and the tags prefetch
    # (todo 276 / M5).
    # Pinned EXACTLY (docs/rules/testing.md) — if this changes, explain the new count here.
    assert len(ctx.captured_queries) == 5


@pytest.mark.django_db
def test_topic_detail_is_subscribed_for_authenticated_user():
    """is_subscribed reflects the requesting user's TopicSubscription state
    (todo 253 slice 3) and costs exactly one extra query over the anonymous
    pin — the anonymous case (4, above) short-circuits before ever touching
    TopicSubscription.

    Since audit H6 an authenticated NON-AUTHOR viewer also pays the two
    permission-table queries behind `can_mark_solution` (see the pin below);
    the anonymous pin is untouched because `solution_block` short-circuits
    before the lookup."""
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
    # Pinned EXACTLY (docs/rules/testing.md): the anonymous pin (5, incl. the
    # todo-276 tags prefetch) + one TopicSubscription.objects.filter(...).exists()
    # + the two permission-table reads (user_permissions, group_permissions)
    # that `can_mark_solution` triggers via has_perm for a non-author viewer
    # (audit H6). Two, not one, and CONSTANT — Django caches the perm set on the
    # request's user instance, which is why the same lookup behind PostSerializer
    # .can_edit does not scale with page size either. The topic AUTHOR pays
    # neither: solution_block short-circuits on `user.pk == self.author_id`.
    assert len(ctx.captured_queries) == 8

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
    # for the response itself must be unchanged (still 5 — 4 plus the todo-276
    # tags prefetch).
    # This pin is about THIS TEST, not about production. django_db wraps the
    # body in an atomic block, so on_commit really does defer here (and rolls
    # back unrun) — in production, autocommit + ATOMIC_REQUESTS=False makes the
    # same callback run inline. See TopicDetailView.retrieve's comment and
    # docs/LEARNINGS.md (todo 271, 2026-07-29). Do not cite this 5 as evidence
    # that the view_count/TopicRead writes are free in production.
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
    # Same 5 as the topic-detail pin above (4 + the todo-276 tags prefetch) —
    # the point of this test is that view_count adds NO query, not the absolute.
    assert len(ctx.captured_queries) == 5


# ---- read-recording (todo 253 slice 5, H10) ---------------------------------


@pytest.mark.django_db
def test_topic_read_recorded_on_get(django_capture_on_commit_callbacks):
    board = _board(slug="tr-board")
    reader = User.objects.create_user(username="tr-reader")
    topic = Topic.objects.create(board=board, title="TR", slug="tr", live=True)
    assert not TopicRead.objects.filter(user=reader, topic=topic).exists()

    client = APIClient()
    client.force_authenticate(reader)
    with django_capture_on_commit_callbacks(execute=True):
        client.get(f"/forum/topics/{topic.id}/")

    assert TopicRead.objects.filter(user=reader, topic=topic).exists()


@pytest.mark.django_db
def test_topic_read_ensures_forum_profile_exists(django_capture_on_commit_callbacks):
    board = _board(slug="tr-board2")
    reader = User.objects.create_user(username="tr-reader2")
    topic = Topic.objects.create(board=board, title="TR2", slug="tr2", live=True)
    assert not ForumProfile.objects.filter(user=reader).exists()

    client = APIClient()
    client.force_authenticate(reader)
    with django_capture_on_commit_callbacks(execute=True):
        client.get(f"/forum/topics/{topic.id}/")

    assert ForumProfile.objects.filter(user=reader).exists()


@pytest.mark.django_db
def test_first_read_leaves_a_sleepers_other_topics_unread(
    django_capture_on_commit_callbacks,
):
    """Todo 285 changed what a *genuine* first read does to the rest of the
    forest, and this is the endpoint that change lands on.

    Before 285, `ForumProfile.for_user()` stamped `read_watermark_at = now()`
    here, so a sleeper account's first read of ONE topic marked their entire
    backlog read. Now the watermark is seeded from `date_joined`, so the read
    marks exactly the topic that was read and every other topic stays unread.
    That is the intended semantics, not a side effect — pin it, because
    nothing else in the suite would notice it reverting.
    """
    board = _board(slug="tr-sleeper")
    joined = timezone.now() - timedelta(days=365)
    reader = User.objects.create_user(username="tr-sleeper")
    User.objects.filter(pk=reader.pk).update(date_joined=joined)
    # update() does not touch the in-memory instance, and force_authenticate
    # hands THAT object to the view — without this the request user still
    # carries date_joined=now and the test silently checks nothing.
    reader.refresh_from_db()
    posted_at = timezone.now() - timedelta(days=30)
    read_topic = Topic.objects.create(
        board=board, title="Read", slug="s-read", live=True, last_post_at=posted_at
    )
    other = Topic.objects.create(
        board=board, title="Other", slug="s-other", live=True, last_post_at=posted_at
    )
    assert not ForumProfile.objects.filter(user=reader).exists()

    client = APIClient()
    client.force_authenticate(reader)
    with django_capture_on_commit_callbacks(execute=True):
        client.get(f"/forum/topics/{read_topic.id}/")

    unread = {
        t["id"]: t["is_unread"]
        for t in client.get(f"/forum/boards/{board.slug}/topics/").data["results"]
    }
    assert unread[other.id] is True, "a single read collapsed the whole backlog"
    assert unread[read_topic.id] is False, "the topic actually read stayed unread"


@pytest.mark.django_db
def test_topic_read_dedup_suppresses_redundant_write_in_same_epoch(
    django_capture_on_commit_callbacks,
):
    # Keyed on (topic, viewer, last_post_at) — a second visit with no new
    # activity in between is a no-op: the row already correctly reflects
    # "read as of the first visit," so re-writing it would be wasted work.
    board = _board(slug="tr-board3")
    reader = User.objects.create_user(username="tr-reader3")
    topic = Topic.objects.create(board=board, title="TR3", slug="tr3", live=True)

    client = APIClient()
    client.force_authenticate(reader)
    # Each on_commit callback only fires when ITS OWN capture block exits, not
    # incrementally — two separate blocks so the intermediate state is real.
    with django_capture_on_commit_callbacks(execute=True):
        client.get(f"/forum/topics/{topic.id}/")
    first_read_at = TopicRead.objects.get(user=reader, topic=topic).last_read_at

    with django_capture_on_commit_callbacks(execute=True):
        client.get(f"/forum/topics/{topic.id}/")

    assert TopicRead.objects.filter(user=reader, topic=topic).count() == 1
    second_read_at = TopicRead.objects.get(user=reader, topic=topic).last_read_at
    assert second_read_at == first_read_at


@pytest.mark.django_db
def test_topic_read_updates_after_new_reply_since_last_visit(
    django_capture_on_commit_callbacks,
):
    # A new reply changes last_post_at, which rotates the dedup key — proving
    # the dedup above doesn't also swallow a visit that legitimately should
    # record a fresh read (the Efficiency-angle correctness concern).
    board = _board(slug="tr-board6")
    reader = User.objects.create_user(username="tr-reader6")
    topic = Topic.objects.create(board=board, title="TR6", slug="tr6", live=True)

    client = APIClient()
    client.force_authenticate(reader)
    with django_capture_on_commit_callbacks(execute=True):
        client.get(f"/forum/topics/{topic.id}/")
    first_read_at = TopicRead.objects.get(user=reader, topic=topic).last_read_at

    topic.last_post_at = timezone.now()
    topic.save(update_fields=["last_post_at"])

    with django_capture_on_commit_callbacks(execute=True):
        client.get(f"/forum/topics/{topic.id}/")

    assert TopicRead.objects.filter(user=reader, topic=topic).count() == 1
    second_read_at = TopicRead.objects.get(user=reader, topic=topic).last_read_at
    assert second_read_at > first_read_at


@pytest.mark.django_db
@override_settings(
    WAGTAILFORUM_VIEW_COUNT_DEDUP_SECONDS=900, WAGTAILFORUM_TOPIC_READ_DEDUP_SECONDS=0
)
def test_topic_read_dedup_ttl_is_independent_of_view_count_dedup_ttl(
    django_capture_on_commit_callbacks,
):
    """TOPIC_READ_DEDUP_SECONDS and VIEW_COUNT_DEDUP_SECONDS gate unrelated
    concerns and must be independently tunable. Same two requests, same
    (topic, viewer) key ingredients as the view_count dedup tests above, but
    a repeat visit stays deduped for view_count (TTL=900) while the repeat
    TopicRead write is NOT deduped (TTL=0, expires instantly, same technique
    as test_view_count_recounts_after_dedup_window_expires) — proving the
    two no longer share one variable."""
    cache.clear()
    board = _board(slug="tr-board7")
    reader = User.objects.create_user(username="tr-reader7")
    topic = Topic.objects.create(board=board, title="TR7", slug="tr7", live=True)

    client = APIClient()
    client.force_authenticate(reader)
    with django_capture_on_commit_callbacks(execute=True):
        client.get(f"/forum/topics/{topic.id}/")
    first_read_at = TopicRead.objects.get(user=reader, topic=topic).last_read_at

    with django_capture_on_commit_callbacks(execute=True):
        client.get(f"/forum/topics/{topic.id}/")

    topic.refresh_from_db()
    assert topic.view_count == 1  # deduped — VIEW_COUNT_DEDUP_SECONDS=900 still holds
    second_read_at = TopicRead.objects.get(user=reader, topic=topic).last_read_at
    assert (
        second_read_at > first_read_at
    )  # not deduped — its own TTL=0 expired instantly


@pytest.mark.django_db
def test_topic_read_not_recorded_for_anonymous(django_capture_on_commit_callbacks):
    board = _board(slug="tr-board4")
    topic = Topic.objects.create(board=board, title="TR4", slug="tr4", live=True)

    with django_capture_on_commit_callbacks(execute=True):
        APIClient().get(f"/forum/topics/{topic.id}/")

    assert not TopicRead.objects.filter(topic=topic).exists()


@pytest.mark.django_db
def test_topic_read_failure_does_not_5xx_the_response(
    django_capture_on_commit_callbacks, monkeypatch
):
    """robust=True (Angle E): a broken read-marking callback logs and is
    swallowed — it must never turn an already-successful 200 into a 500."""

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(TopicRead, "mark_read", _boom)

    board = _board(slug="tr-board5")
    reader = User.objects.create_user(username="tr-reader5")
    topic = Topic.objects.create(board=board, title="TR5", slug="tr5", live=True)

    client = APIClient()
    client.force_authenticate(reader)
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.get(f"/forum/topics/{topic.id}/")

    assert resp.status_code == 200


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_UNREAD_LAUNCH_AT="2020-01-01T00:00:00Z")
def test_ac5_end_to_end_open_detail_then_list_reflects_read(
    django_capture_on_commit_callbacks,
):
    """AC5 loop through both real endpoints, not hand-seeded TopicRead/
    ForumProfile rows: a topic is unread in the list, opening it via the
    detail endpoint clears that, and a new reply since re-flags it."""
    board = _board(slug="ac5-board")
    author = User.objects.create_user(username="ac5-author")
    reader = User.objects.create_user(username="ac5-reader")
    topic = Topic.objects.create(
        board=board,
        title="AC5",
        slug="ac5-topic",
        author=author,
        live=True,
        last_post_at=timezone.now(),
    )
    client = APIClient()
    client.force_authenticate(reader)

    list_before = client.get(f"/forum/boards/{board.slug}/topics/")
    assert list_before.data["results"][0]["is_unread"] is True

    with django_capture_on_commit_callbacks(execute=True):
        detail = client.get(f"/forum/topics/{topic.id}/")
    assert detail.status_code == 200

    list_after = client.get(f"/forum/boards/{board.slug}/topics/")
    assert list_after.data["results"][0]["is_unread"] is False

    # Simulate a new reply the same way the rest of this suite does — bump
    # the activity signal directly rather than re-deriving Wagtail's publish
    # chain, which this test isn't meant to exercise.
    topic.last_post_at = timezone.now()
    topic.save(update_fields=["last_post_at"])

    list_after_reply = client.get(f"/forum/boards/{board.slug}/topics/")
    assert list_after_reply.data["results"][0]["is_unread"] is True
