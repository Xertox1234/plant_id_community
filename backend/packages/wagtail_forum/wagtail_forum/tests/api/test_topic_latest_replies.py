"""Latest-replies peek: GET topics/<id>/latest-replies/ (forum home redesign,
task 2; spec 2026-11-02 §6.4).

The expanded home activity card shows up to 3 items (the accepted answer
first, then the newest replies), the participants and who started the thread.
It is a HIDE surface: members the viewer blocked or muted are left out
entirely, and never counted in ``more_count``.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file
from wagtail_forum.models import Forum, ForumProfile, Post, Topic, UserBlock, UserMute
from wagtail_forum.tests.factories import hide_forum, make_category, make_forum

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")

# topic lookup, visible count, solution, newest replies, participant count,
# participant ids, participant users, opening post (started_by).
EXPECTED_QUERIES = 8


def _url(topic):
    return f"/forum/topics/{topic.pk}/latest-replies/"


def _topic(board=None, starter=None, *, slug="t", **extra):
    if board is None:
        board, _ = Forum.objects.get_or_create(
            forum_type=Forum.FORUM,
            slug="general",
            defaults={"name": "General", "parent": make_category()},
        )
    if starter is None:
        starter, _ = User.objects.get_or_create(username="starter")
    topic = Topic.objects.create(
        board=board,
        title=slug,
        slug=slug,
        author=starter,
        live=True,
        last_post_at=timezone.now(),
        **extra,
    )
    opening = Post.objects.create(
        topic=topic,
        author=starter,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": "<p>Opening</p>"}],
    )
    # Before every reply (see _reply), as in a real thread.
    Post.objects.filter(pk=opening.pk).update(
        created_at=_BASE - datetime.timedelta(minutes=1)
    )
    return topic


_BASE = timezone.now() - datetime.timedelta(days=1)


def _reply(topic, author, minutes, *, text="reply", live=True):
    """A live reply whose created_at is ``minutes`` after a fixed base, so
    ordering never depends on insert timing."""
    post = Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=False,
        live=live,
        body=[{"type": "paragraph", "value": f"<p>{text}</p>"}],
    )
    Post.objects.filter(pk=post.pk).update(
        created_at=_BASE + datetime.timedelta(minutes=minutes)
    )
    return post


def _member(username):
    user = User.objects.create_user(username=username)
    client = APIClient()
    client.force_authenticate(user)
    return user, client


@pytest.mark.django_db
def test_latest_replies_returns_three_newest_newest_first():
    topic = _topic()
    author = User.objects.create_user(username="ada")
    replies = [_reply(topic, author, i) for i in range(5)]

    resp = APIClient().get(_url(topic))

    assert resp.status_code == 200
    assert [r["id"] for r in resp.data["replies"]] == [
        replies[4].pk,
        replies[3].pk,
        replies[2].pk,
    ]
    assert resp.data["solution"] is None
    assert resp.data["more_count"] == 2
    first = resp.data["replies"][0]
    assert first["author"]["username"] == "ada"
    assert first["excerpt"] == "reply"
    assert first["created_at"]


@pytest.mark.django_db
def test_latest_replies_solution_counts_toward_three():
    topic = _topic()
    author = User.objects.create_user(username="ada")
    replies = [_reply(topic, author, i) for i in range(5)]
    topic.solved_post = replies[1]
    topic.save(update_fields=["solved_post"])

    resp = APIClient().get(_url(topic))

    assert resp.data["solution"]["id"] == replies[1].pk
    assert [r["id"] for r in resp.data["replies"]] == [replies[4].pk, replies[3].pk]
    assert resp.data["more_count"] == 2


@pytest.mark.django_db
def test_latest_replies_hides_blocked_and_muted_authors():
    topic = _topic()
    viewer, client = _member("viewer")
    friend = User.objects.create_user(username="friend")
    blocked = User.objects.create_user(username="blocked")
    muted = User.objects.create_user(username="muted")
    UserBlock.objects.create(blocker=viewer, blocked=blocked)
    UserMute.objects.create(muter=viewer, muted=muted)
    visible_old = _reply(topic, friend, 0)
    _reply(topic, blocked, 1, text="blocked text")
    _reply(topic, muted, 2, text="muted text")
    visible_new = _reply(topic, friend, 3)

    resp = client.get(_url(topic))

    assert resp.status_code == 200
    assert [r["id"] for r in resp.data["replies"]] == [visible_new.pk, visible_old.pk]
    names = {p["username"] for p in resp.data["participants"]}
    assert names == {"friend", "starter"}
    assert resp.data["participant_count"] == 2
    assert resp.data["more_count"] == 0
    assert "blocked text" not in str(resp.data)
    assert "muted text" not in str(resp.data)

    # The same topic, anonymously, shows everyone: the filter is the viewer's.
    anon = APIClient().get(_url(topic))
    assert len(anon.data["replies"]) == 3
    assert anon.data["more_count"] == 1
    assert anon.data["participant_count"] == 4


@pytest.mark.django_db
def test_latest_replies_hidden_solution_author_omits_solution():
    topic = _topic()
    viewer, client = _member("viewer")
    friend = User.objects.create_user(username="friend")
    blocked = User.objects.create_user(username="blocked")
    UserBlock.objects.create(blocker=viewer, blocked=blocked)
    visible = [_reply(topic, friend, i) for i in range(4)]
    answer = _reply(topic, blocked, 10, text="hidden answer")
    topic.solved_post = answer
    topic.save(update_fields=["solved_post"])

    resp = client.get(_url(topic))

    assert resp.data["solution"] is None
    assert [r["id"] for r in resp.data["replies"]] == [
        visible[3].pk,
        visible[2].pk,
        visible[1].pk,
    ]
    assert resp.data["more_count"] == 1
    assert "hidden answer" not in str(resp.data)


@pytest.mark.django_db
def test_latest_replies_only_blocked_replies():
    topic = _topic()
    viewer, client = _member("viewer")
    blocked = User.objects.create_user(username="blocked")
    other = User.objects.create_user(username="other")
    UserBlock.objects.create(blocker=viewer, blocked=blocked)
    UserBlock.objects.create(blocker=viewer, blocked=other)
    _reply(topic, blocked, 0)
    _reply(topic, other, 1)

    resp = client.get(_url(topic))

    assert resp.data["replies"] == []
    assert resp.data["solution"] is None
    assert resp.data["more_count"] == 0
    assert [p["username"] for p in resp.data["participants"]] == ["starter"]


@pytest.mark.django_db
def test_latest_replies_no_replies():
    topic = _topic()

    resp = APIClient().get(_url(topic))

    assert resp.status_code == 200
    assert resp.data["replies"] == []
    assert resp.data["solution"] is None
    assert resp.data["more_count"] == 0
    assert resp.data["participant_count"] == 1
    assert resp.data["started_by"]["username"] == "starter"


@pytest.mark.django_db
def test_latest_replies_started_by_none_when_starter_blocked():
    topic = _topic()
    viewer, client = _member("viewer")
    UserBlock.objects.create(blocker=viewer, blocked=topic.author)

    resp = client.get(_url(topic))

    assert resp.data["started_by"] is None
    assert resp.data["participants"] == []
    assert resp.data["participant_count"] == 0


@pytest.mark.django_db
def test_latest_replies_participants_most_recent_first_and_capped():
    topic = _topic()
    authors = [User.objects.create_user(username=f"u{i}") for i in range(6)]
    for i, author in enumerate(authors):
        _reply(topic, author, i)
    _reply(topic, authors[0], 20)  # u0 posts again, latest of all

    resp = APIClient().get(_url(topic))

    assert [p["username"] for p in resp.data["participants"]] == [
        "u0",
        "u5",
        "u4",
        "u3",
        "u2",
    ]
    assert resp.data["participant_count"] == 7  # six repliers + the starter


@pytest.mark.django_db
def test_latest_replies_excludes_non_live_replies():
    topic = _topic()
    author = User.objects.create_user(username="ada")
    live = _reply(topic, author, 0)
    _reply(topic, author, 1, text="draft", live=False)

    resp = APIClient().get(_url(topic))

    assert [r["id"] for r in resp.data["replies"]] == [live.pk]
    assert resp.data["more_count"] == 0


@pytest.mark.django_db
def test_latest_replies_excerpt_plain_and_capped():
    topic = _topic()
    author = User.objects.create_user(username="ada")
    long_text = "<strong>Bold</strong> " + ("word " * 100)
    _reply(topic, author, 0, text=long_text)

    resp = APIClient().get(_url(topic))

    excerpt = resp.data["replies"][0]["excerpt"]
    assert "<" not in excerpt
    assert excerpt.startswith("Bold word")
    assert len(excerpt) <= 160


@pytest.mark.django_db
def test_latest_replies_404_when_topic_not_visible():
    board = make_forum(name="Secret", slug="secret")
    hidden = _topic(board, slug="hidden")
    hide_forum(board)
    draft = _topic(slug="draft")
    Topic.objects.filter(pk=draft.pk).update(live=False)
    _viewer, client = _member("viewer")

    for c in (APIClient(), client):
        assert c.get(_url(hidden)).status_code == 404
        assert c.get(_url(draft)).status_code == 404
    assert APIClient().get("/forum/topics/999999/latest-replies/").status_code == 404


@pytest.mark.django_db
def test_latest_replies_does_not_mark_read():
    topic = _topic()
    _reply(topic, User.objects.create_user(username="ada"), 0)
    member, client = _member("reader")
    profile = ForumProfile.for_user(member)
    profile.read_watermark_at = timezone.now() - datetime.timedelta(days=2)
    profile.save(update_fields=["read_watermark_at"])

    before = client.get("/forum/topics/recent/")
    assert {r["id"]: r["is_unread"] for r in before.data["results"]}[topic.pk] is True

    assert client.get(_url(topic)).status_code == 200

    after = client.get("/forum/topics/recent/")
    assert {r["id"]: r["is_unread"] for r in after.data["results"]}[topic.pk] is True


@pytest.mark.django_db
def test_latest_replies_query_count():
    """Flat: the same count for a topic with 3 replies and one with 30, as a
    member (the block/mute subqueries are correlated into the same queries)."""
    board = make_forum(name="General", slug="general")
    _member_user, client = _member("viewer")
    small = _topic(board, slug="small")
    large = _topic(board, User.objects.create_user(username="starter2"), slug="large")
    for i in range(3):
        _reply(small, User.objects.create_user(username=f"s{i}"), i)
    for i in range(30):
        _reply(large, User.objects.create_user(username=f"l{i}"), i)
    # Avatars on a reply author and a starter in each topic, so the pin also
    # proves the avatar join costs no per-author query.
    for username in ("s2", "starter", "l29", "starter2"):
        profile = ForumProfile.for_user(User.objects.get(username=username))
        profile.avatar = get_image_model().objects.create(
            title=f"{username}.jpg", file=get_test_image_file()
        )
        profile.save(update_fields=["avatar"])
    small.solved_post = small.posts.filter(is_opening_post=False).first()
    small.save(update_fields=["solved_post"])
    large.solved_post = large.posts.filter(is_opening_post=False).first()
    large.save(update_fields=["solved_post"])

    def measure(topic):
        client.get(_url(topic))  # warm one-time lookups
        with CaptureQueriesContext(connection) as ctx:
            resp = client.get(_url(topic))
        assert resp.status_code == 200
        avatars = [r["author"]["avatar"] for r in resp.data["replies"]]
        assert any(avatars) and resp.data["started_by"]["avatar"]
        return len(ctx)

    assert measure(small) == measure(large) == EXPECTED_QUERIES


@pytest.mark.django_db
def test_latest_replies_cache_headers():
    """Never shared-cached, even for guests: it serves reply text, and a
    reply hidden by moderation must stop being served at once (no CDN purge),
    the same reason PostListView is private."""
    topic = _topic()

    anon = APIClient().get(_url(topic))
    assert anon["Cache-Control"] == "private, no-store"
    assert "Cookie" in anon["Vary"] and "Authorization" in anon["Vary"]

    _member_user, client = _member("viewer")
    authed = client.get(_url(topic))
    assert authed["Cache-Control"] == "private, no-store"
    assert "Cookie" in authed["Vary"] and "Authorization" in authed["Vary"]

    missing = APIClient().get("/forum/topics/999999/latest-replies/")
    assert missing["Cache-Control"] == "private, no-store"
