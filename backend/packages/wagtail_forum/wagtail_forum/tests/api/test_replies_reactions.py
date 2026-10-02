import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Reaction, Topic
from wagtail_forum.workflow import ensure_default_workflow

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


@pytest.fixture(autouse=True)
def clear_idempotency_cache():
    """Prevent idempotency cache from bleeding between tests (LocMemCache is process-global)."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


def _live_topic(closed=False):
    board = _board()
    author = User.objects.create_user(username="op")
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=author, is_closed=closed
    )
    opening = Post.objects.create(topic=topic, author=author, is_opening_post=True)
    opening.save_revision().publish()  # makes the topic activity real; opening live
    return topic, opening


@pytest.mark.django_db
def test_reply_blocked_on_closed_topic():
    ensure_default_workflow()
    topic, _ = _live_topic(closed=True)
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(
        f"/forum/topics/{topic.id}/posts/",
        {"body": [{"type": "paragraph", "value": "<p>hi</p>"}]},
        format="json",
    )
    assert resp.status_code == 409


@pytest.mark.django_db
def test_reply_to_non_live_topic_returns_404():
    # SECURITY: a draft/hidden topic must not accept replies, and must not even
    # reveal its existence — 404, checked BEFORE the closed/locked 409.
    ensure_default_workflow()
    board = _board()
    author = User.objects.create_user(username="op")
    draft = Topic.objects.create(
        board=board, title="Hidden", slug="hidden", author=author, live=False
    )
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(
        f"/forum/topics/{draft.id}/posts/",
        {"body": [{"type": "paragraph", "value": "<p>hi</p>"}]},
        format="json",
    )
    assert resp.status_code == 404
    assert Post.objects.filter(topic=draft, is_opening_post=False).count() == 0


@pytest.mark.django_db
def test_reply_dangerous_body_is_sanitized():
    # A reply's rich-text body is sanitized on write (javascript: href + onerror
    # stripped); the reply is accepted with clean content, not rejected.
    ensure_default_workflow()
    topic, _ = _live_topic()
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(
        f"/forum/topics/{topic.id}/posts/",
        {
            "body": [
                {
                    "type": "paragraph",
                    "value": '<p><a href="javascript:alert(1)">x</a>'
                    '<img src=x onerror="alert(1)">ok</p>',
                }
            ]
        },
        format="json",
    )
    assert resp.status_code == 201
    reply = Post.objects.get(id=resp.data["id"])
    source = reply.body[0].value.source
    assert "javascript:" not in source
    assert "onerror" not in source
    assert "ok" in source


@pytest.mark.django_db
def test_reaction_toggle_returns_counts():
    ensure_default_workflow()
    _, opening = _live_topic()
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)

    on = client.post(
        f"/forum/posts/{opening.id}/reactions/", {"type": "like"}, format="json"
    )
    assert on.status_code == 200
    assert on.data["reaction_counts"] == {"like": 1}

    off = client.post(
        f"/forum/posts/{opening.id}/reactions/", {"type": "like"}, format="json"
    )
    assert off.data["reaction_counts"] == {}
    assert Reaction.objects.filter(post=opening, user=user).count() == 0


@pytest.mark.django_db
def test_reaction_rejects_invalid_type():
    ensure_default_workflow()
    _, opening = _live_topic()
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(
        f"/forum/posts/{opening.id}/reactions/", {"type": "bogus"}, format="json"
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_reaction_on_non_live_topic_post_returns_404():
    # SECURITY: a post on a draft/hidden topic must not be reactable, and must not
    # reveal its existence — 404, mirroring the reply non-live guard.
    ensure_default_workflow()
    board = _board()
    author = User.objects.create_user(username="op")
    draft = Topic.objects.create(
        board=board, title="H", slug="h", author=author, live=False
    )
    hidden_post = Post.objects.create(
        topic=draft, author=author, is_opening_post=True, live=False
    )
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(
        f"/forum/posts/{hidden_post.id}/reactions/", {"type": "like"}, format="json"
    )
    assert resp.status_code == 404
    assert Reaction.objects.filter(post=hidden_post).count() == 0


# --- Idempotency contract (2026-06-10 audit M4, L11) ---


def _reply(client, topic, key=None):
    headers = {"HTTP_IDEMPOTENCY_KEY": key} if key else {}
    return client.post(
        f"/forum/topics/{topic.id}/posts/",
        {"body": [{"type": "paragraph", "value": "<p>hi</p>"}]},
        format="json",
        **headers,
    )


@pytest.mark.django_db
def test_reply_retry_with_idempotency_key_does_not_duplicate():
    ensure_default_workflow()
    topic, _ = _live_topic()
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)

    r1 = _reply(client, topic, key="k1")
    r2 = _reply(client, topic, key="k1")  # mobile timeout retry

    assert r1.status_code == 201
    assert r2.status_code == 201  # replays the ORIGINAL status
    assert r2.data == r1.data
    # L19 (258): the 201 carries a Location for the created post, and the replay
    # carries the SAME Location (the replay path was dropping headers).
    assert r1["Location"].endswith(f"/forum/posts/{r1.data['id']}/")
    assert r2["Location"] == r1["Location"]
    assert Post.objects.filter(topic=topic, is_opening_post=False).count() == 1


@pytest.mark.django_db
def test_idempotency_key_reuse_with_different_payload_is_422():
    ensure_default_workflow()
    topic, _ = _live_topic()
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)

    assert _reply(client, topic, key="k1").status_code == 201
    r2 = client.post(
        f"/forum/topics/{topic.id}/posts/",
        {"body": [{"type": "paragraph", "value": "<p>DIFFERENT</p>"}]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="k1",
    )
    assert r2.status_code == 422
    assert Post.objects.filter(topic=topic, is_opening_post=False).count() == 1


@pytest.mark.django_db
def test_idempotency_keys_are_user_scoped():
    # User B reusing user A's key must get their OWN reply created — never a
    # replay of A's cached response.
    ensure_default_workflow()
    topic, _ = _live_topic()
    a = User.objects.create_user(username="a")
    b = User.objects.create_user(username="b")
    client = APIClient()

    client.force_authenticate(a)
    ra = _reply(client, topic, key="shared")
    client.force_authenticate(b)
    rb = _reply(client, topic, key="shared")

    assert ra.status_code == rb.status_code == 201
    assert ra.data["id"] != rb.data["id"]
    assert Post.objects.filter(topic=topic, is_opening_post=False).count() == 2


@pytest.mark.django_db
def test_reaction_retry_with_idempotency_key_replays_not_inverts():
    ensure_default_workflow()
    _, opening = _live_topic()
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)

    r1 = client.post(
        f"/forum/posts/{opening.id}/reactions/",
        {"type": "like"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="k1",
    )
    r2 = client.post(  # timeout retry — must NOT toggle the reaction back off
        f"/forum/posts/{opening.id}/reactions/",
        {"type": "like"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="k1",
    )

    assert r1.status_code == r2.status_code == 200
    assert r1.data["reacted"] is True
    assert r2.data == r1.data
    assert Reaction.objects.filter(post=opening).count() == 1


@pytest.mark.django_db
def test_reaction_response_reports_resulting_state():
    ensure_default_workflow()
    _, opening = _live_topic()
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)
    url = f"/forum/posts/{opening.id}/reactions/"

    on = client.post(url, {"type": "like"}, format="json")
    off = client.post(url, {"type": "like"}, format="json")  # no key: real toggle

    assert on.data["reacted"] is True
    assert off.data["reacted"] is False
    assert off.data["reaction_counts"] == {}


@pytest.mark.django_db
def test_simultaneous_reaction_toggles_leave_one_row_and_a_consistent_count(
    monkeypatch,
):
    """A double-tap race: two toggles by one user both run their existence
    SELECT before either INSERTs (todo 464, from 004-reaction).

    Real threads are off the table here: they need
    ``django_db(transaction=True)``, which ``docs/rules/testing.md`` bans
    because its teardown flush deletes Wagtail's seeded root page. So the
    interleaving is forced deterministically instead: request B's real SELECT
    runs and finds nothing, then request A runs to completion (INSERT +
    recount), then B carries on to its INSERT and hits the
    ``(post, user, reaction_type)`` unique constraint. The view must treat the
    loser as "already reacted" -- not a 500, and not a second row.
    """
    from django.db.models import QuerySet

    ensure_default_workflow()
    _, opening = _live_topic()
    user = User.objects.create_user(username="r")
    url = f"/forum/posts/{opening.id}/reactions/"

    def client():
        c = APIClient()
        c.force_authenticate(user)
        return c

    real_first = QuerySet.first
    raced = {}

    def first_then_let_the_other_request_win(self):
        found = real_first(self)
        if self.model is Reaction and "a" not in raced:
            raced["a"] = None  # A's own SELECT must not start a third request
            raced["a"] = client().post(url, {"type": "like"}, format="json")
        return found

    monkeypatch.setattr(QuerySet, "first", first_then_let_the_other_request_win)
    b = client().post(url, {"type": "like"}, format="json")
    monkeypatch.undo()

    # The interleave hangs off the view's existence `.first()`. If the view
    # stops calling it (`.exists()`, `.get()`), say so instead of a bare KeyError.
    assert raced.get("a") is not None, (
        "the race hook never fired: ReactionToggleView no longer checks for an "
        "existing Reaction with QuerySet.first(), so no second request ran"
    )
    a = raced["a"]
    assert a.status_code == b.status_code == 200
    assert a.data["reacted"] is True
    assert b.data["reacted"] is True  # the loser reports the state that won
    assert Reaction.objects.filter(post=opening, user=user).count() == 1
    opening.refresh_from_db()
    assert opening.reaction_counts == {"like": 1}
    assert b.data["reaction_counts"] == opening.reaction_counts


@pytest.mark.django_db
def test_reaction_toggle_recounts_under_a_post_row_lock():
    """The other half of the race above: ``Reaction.recount`` must lock the post
    row (``SELECT ... FOR UPDATE``) before its read-recount-write, or two
    concurrent toggles can persist a stale ``reaction_counts`` (todo 487).

    The race test runs both requests on one connection, so it cannot see the
    lock, and real threads need the banned ``django_db(transaction=True)``.
    The SQL can show it: the lock is taken on the post row, before the count
    is written back.
    """
    ensure_default_workflow()
    _, opening = _live_topic()
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)
    post_table = f'"{Post._meta.db_table}"'

    with CaptureQueriesContext(connection) as ctx:
        resp = client.post(
            f"/forum/posts/{opening.id}/reactions/", {"type": "like"}, format="json"
        )

    assert resp.status_code == 200
    sqls = [q["sql"] for q in ctx.captured_queries]
    inserted = [
        i
        for i, sql in enumerate(sqls)
        if sql.startswith(f'INSERT INTO "{Reaction._meta.db_table}"')
    ]
    written = [
        i
        for i, sql in enumerate(sqls)
        if sql.startswith(f"UPDATE {post_table}") and "reaction_counts" in sql
    ]
    assert inserted and written, "the toggle no longer inserts, then recounts"
    # recount's aggregate read: the COUNT over the reaction rows that the
    # written-back reaction_counts comes from.
    counted = [
        i
        for i, sql in enumerate(sqls)
        if inserted[-1] < i < written[-1]
        and sql.startswith("SELECT")
        and f'FROM "{Reaction._meta.db_table}"' in sql
        and "COUNT(" in sql
    ]
    assert counted, "recount no longer counts the reaction rows before writing"
    # The lock must come BEFORE that read (todo 508): a lock taken after the
    # COUNT leaves the count stale under READ COMMITTED. The window also
    # deliberately starts after the INSERT, pinning recount's OWN lock: the
    # SQL log cannot show transaction scope, so an earlier FOR UPDATE would
    # pass even if its transaction had ended. A future view that locks the
    # post first in an outer atomic must widen this window on purpose.
    recount_locks = [
        i
        for i, sql in enumerate(sqls)
        if inserted[-1] < i < counted[-1]
        and sql.startswith("SELECT")
        and post_table in sql
        and "FOR UPDATE" in sql
    ]
    assert recount_locks, (
        "Reaction.recount no longer locks the post row (SELECT ... FOR UPDATE) "
        "before it counts the reactions and writes reaction_counts"
    )


# --- Remaining guard branches (2026-06-10 audit L13) ---


@pytest.mark.django_db
def test_reply_blocked_on_locked_topic():
    # `locked` (LockableMixin) is the OTHER half of the closed-or-locked guard.
    ensure_default_workflow()
    topic, _ = _live_topic()
    topic.locked = True
    topic.save(update_fields=["locked"])
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(
        f"/forum/topics/{topic.id}/posts/",
        {"body": [{"type": "paragraph", "value": "<p>hi</p>"}]},
        format="json",
    )
    assert resp.status_code == 409


@pytest.mark.django_db
def test_reaction_on_draft_post_of_live_topic_returns_404():
    # The other half of the `not post.live or not topic.live` guard.
    ensure_default_workflow()
    topic, _ = _live_topic()
    author = topic.author
    draft_reply = Post.objects.create(
        topic=topic, author=author, is_opening_post=False, live=False
    )
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(
        f"/forum/posts/{draft_reply.id}/reactions/", {"type": "like"}, format="json"
    )
    assert resp.status_code == 404


@pytest.mark.django_db
def test_reply_spam_backend_crash_leaves_pending_not_500(settings):
    # The reply path duplicates the topic-create fail-safe; cover it separately.
    settings.WAGTAILFORUM_SPAM_BACKEND = (
        "wagtail_forum.tests.api.test_topic_create.RaisingSpamBackend"
    )
    ensure_default_workflow()
    topic, _ = _live_topic()
    user = User.objects.create_user(username="r")
    client = APIClient()
    client.force_authenticate(user)

    resp = _reply(client, topic)

    assert resp.status_code == 201
    assert resp.data["status"] == "pending"
    reply = Post.objects.get(id=resp.data["id"])
    assert reply.live is False
