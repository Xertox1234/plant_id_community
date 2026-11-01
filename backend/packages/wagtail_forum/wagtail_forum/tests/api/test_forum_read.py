"""Per-forum unread markers, mark forum read, mark all read (todo 671).

A topic is unread when its last post is newer than the latest of the
viewer's floors: their ``TopicRead`` for it, their ``ForumRead`` for its
forum, and their ``ForumProfile.read_watermark_at`` ("mark all read").
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail_forum.models import ForumProfile, ForumRead, Topic, TopicRead
from wagtail_forum.tests.factories import make_category, make_forum

User = get_user_model()

pytestmark = [pytest.mark.django_db, pytest.mark.urls("wagtail_forum.tests.api.urls")]


def _ago(**delta):
    return timezone.now() - datetime.timedelta(**delta)


@pytest.fixture
def user():
    member = User.objects.create_user(username="reader", email="r@x.io")
    profile = ForumProfile.for_user(member)
    profile.read_watermark_at = _ago(days=30)
    profile.save(update_fields=["read_watermark_at"])
    return member


@pytest.fixture
def client(user):
    api = APIClient()
    api.force_authenticate(user)
    return api


def _topic(board, slug, **fields):
    fields.setdefault("last_post_at", _ago(hours=1))
    return Topic.objects.create(board=board, title=slug, slug=slug, live=True, **fields)


def _unread(client, board):
    resp = client.get(f"/forum/boards/{board.slug}/topics/")
    assert resp.status_code == 200
    return {row["slug"]: row["is_unread"] for row in resp.json()["results"]}


def _index(client):
    resp = client.get("/forum/categories/")
    assert resp.status_code == 200
    return {
        forum["slug"]: forum["has_unread"]
        for category in resp.json()["results"]
        for forum in category["forums"]
    }


# --- AC0: mark forum read clears that forum only ---


def test_marking_a_forum_read_clears_its_topics_and_not_other_forums(client, user):
    ferns = make_forum(name="Ferns", slug="ferns")
    palms = make_forum(name="Palms", slug="palms")
    _topic(ferns, "f1")
    _topic(ferns, "f2")
    _topic(palms, "p1")
    assert _unread(client, ferns) == {"f1": True, "f2": True}
    assert _index(client) == {"ferns": True, "palms": True}

    resp = client.post("/forum/boards/ferns/read/")

    assert resp.status_code == 200
    assert ForumRead.objects.filter(user=user, forum=ferns).exists()
    assert _unread(client, ferns) == {"f1": False, "f2": False}
    assert _unread(client, palms) == {"p1": True}
    assert _index(client) == {"ferns": False, "palms": True}


def test_a_reply_after_the_mark_makes_the_topic_unread_again(client):
    ferns = make_forum(name="Ferns", slug="ferns")
    topic = _topic(ferns, "f1")
    client.post("/forum/boards/ferns/read/")

    Topic.objects.filter(pk=topic.pk).update(
        last_post_at=timezone.now() + datetime.timedelta(minutes=5)
    )

    assert _unread(client, ferns) == {"f1": True}
    assert _index(client) == {"ferns": True}


def test_marking_a_forum_read_clears_a_topic_read_before_the_mark(client, user):
    """The floors combine as GREATEST, not COALESCE: an older TopicRead must
    not win over a newer forum mark."""
    ferns = make_forum(name="Ferns", slug="ferns")
    topic = _topic(ferns, "f1", last_post_at=_ago(hours=1))
    TopicRead.mark_read(user, topic.pk, when=_ago(hours=2))
    assert _unread(client, ferns) == {"f1": True}

    client.post("/forum/boards/ferns/read/")

    assert _unread(client, ferns) == {"f1": False}


def test_a_hidden_forum_or_a_category_cannot_be_marked(client):
    make_forum(name="Staff", slug="staff", is_hidden=True)
    make_category(name="Plants", slug="plants")

    assert client.post("/forum/boards/staff/read/").status_code == 404
    assert client.post("/forum/boards/plants/read/").status_code == 404
    assert not ForumRead.objects.exists()


# --- AC1: mark all read advances the watermark and clears every forum ---


def test_mark_all_read_advances_the_watermark_and_clears_every_forum(client, user):
    ferns = make_forum(name="Ferns", slug="ferns")
    palms = make_forum(name="Palms", slug="palms", category=make_category(slug="b"))
    _topic(ferns, "f1")
    read_earlier = _topic(palms, "p1")
    TopicRead.mark_read(user, read_earlier.pk, when=_ago(hours=2))
    before = ForumProfile.objects.get(user=user).read_watermark_at
    assert _index(client) == {"ferns": True, "palms": True}

    resp = client.post("/forum/read-all/")

    assert resp.status_code == 200
    after = ForumProfile.objects.get(user=user).read_watermark_at
    assert after > before
    assert after >= _ago(minutes=1)
    assert _index(client) == {"ferns": False, "palms": False}
    assert _unread(client, ferns) == {"f1": False}
    assert _unread(client, palms) == {"p1": False}
    categories = client.get("/forum/categories/").json()["results"]
    assert [c["has_unread"] for c in categories] == [False, False]


def test_mark_all_read_never_moves_the_watermark_back(client, user):
    future = timezone.now() + datetime.timedelta(days=1)
    ForumProfile.objects.filter(user=user).update(read_watermark_at=future)

    client.post("/forum/read-all/")

    assert ForumProfile.objects.get(user=user).read_watermark_at == future


def test_a_category_reports_unread_when_any_of_its_forums_does(client):
    category = make_category(name="Plants", slug="plants")
    make_forum(name="Ferns", slug="ferns", category=category)
    palms = make_forum(name="Palms", slug="palms", category=category)
    _topic(palms, "p1")

    (row,) = client.get("/forum/categories/").json()["results"]

    assert row["has_unread"] is True
    assert {f["slug"]: f["has_unread"] for f in row["forums"]} == {
        "ferns": False,
        "palms": True,
    }


# --- AC2: anonymous viewers get no markers; the endpoints need auth ---


def test_anonymous_viewers_get_no_unread_markers():
    ferns = make_forum(name="Ferns", slug="ferns")
    _topic(ferns, "f1")

    (row,) = APIClient().get("/forum/categories/").json()["results"]

    assert row["has_unread"] is False
    assert [f["has_unread"] for f in row["forums"]] == [False]


def test_the_mark_endpoints_require_auth():
    make_forum(name="Ferns", slug="ferns")
    anon = APIClient()

    assert anon.post("/forum/boards/ferns/read/").status_code in (401, 403)
    assert anon.post("/forum/read-all/").status_code in (401, 403)
    assert not ForumRead.objects.exists()


# --- AC3: the index unread computation has a fixed query count ---


def test_the_index_unread_computation_has_a_fixed_query_count(client, user):
    def count():
        with CaptureQueriesContext(connection) as ctx:
            resp = client.get("/forum/categories/")
        assert resp.status_code == 200
        return len(ctx.captured_queries)

    ferns = make_forum(name="Ferns", slug="ferns")
    _topic(ferns, "f1")
    client.get("/forum/categories/")  # warm per-request caches (permissions)
    small = count()

    for n in range(5):
        category = make_category(name=f"C{n}", slug=f"cat-{n}")
        board = make_forum(name=f"F{n}", slug=f"f{n}", category=category)
        for t in range(3):
            topic = _topic(board, f"t{t}")
            TopicRead.mark_read(user, topic.pk)
        ForumRead.mark_read(user, board.pk)
    big = count()

    assert small == big
