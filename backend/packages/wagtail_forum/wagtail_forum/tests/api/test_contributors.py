"""A forum's top contributors (`boards/<slug>/contributors/`)."""

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from wagtail_forum.models import Post, Topic
from wagtail_forum.tests.factories import make_forum

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _user(name, **kwargs):
    return User.objects.create_user(username=name, **kwargs)


def _topic(board, author, slug, *, live=True):
    topic = Topic.objects.create(
        board=board, title="T", slug=slug, author=author, live=live
    )
    Post.objects.create(topic=topic, author=author, is_opening_post=True, live=live)
    return topic


def _reply(topic, author, n=1, *, live=True):
    for _ in range(n):
        Post.objects.create(topic=topic, author=author, live=live)


def _names(resp):
    return [(row["username"], row["post_count"]) for row in resp.data["results"]]


@pytest.mark.django_db
def test_ranks_members_by_live_posts_in_this_forum_only():
    board = make_forum(name="General", slug="contrib")
    other = make_forum(name="Other", slug="contrib-other")
    ana, ben, cy = _user("ana"), _user("ben"), _user("cy")
    topic = _topic(board, ana, "c-1")  # ana: 1
    _reply(topic, ben, 3)  # ben: 3
    _reply(topic, ana, 1)  # ana: 2
    # None of these count: another forum, a non-live reply, a non-live topic.
    _reply(_topic(other, cy, "c-other"), cy, 5)
    _reply(topic, cy, 2, live=False)
    _reply(_topic(board, cy, "c-hidden", live=False), cy, 4, live=False)

    resp = APIClient().get("/forum/boards/contrib/contributors/")

    assert resp.status_code == 200
    assert _names(resp) == [("ben", 3), ("ana", 2)]
    # The unified author object, plus the count.
    assert {"username", "display_name", "avatar", "post_count"} <= set(
        resp.data["results"][0]
    )


@pytest.mark.django_db
def test_caps_at_the_limit_and_breaks_ties_stably(settings):
    settings.WAGTAILFORUM_BOARD_CONTRIBUTORS_LIMIT = 2
    board = make_forum(name="General", slug="contrib-cap")
    first, second, third = _user("tie-a"), _user("tie-b"), _user("tie-c")
    topic = _topic(board, first, "cap-1")
    _reply(topic, second, 1)
    _reply(topic, third, 1)

    resp = APIClient().get("/forum/boards/contrib-cap/contributors/")

    # All three have one post: the two lowest user ids, in id order.
    assert _names(resp) == [("tie-a", 1), ("tie-b", 1)]


@pytest.mark.django_db
def test_leaves_out_deactivated_and_deleted_authors():
    board = make_forum(name="General", slug="contrib-gone")
    kept, inactive, gone = _user("kept"), _user("inactive"), _user("gone")
    topic = _topic(board, kept, "gone-1")
    _reply(topic, inactive, 3)
    _reply(topic, gone, 3)
    User.objects.filter(pk=inactive.pk).update(is_active=False)
    Post.objects.filter(author=gone).update(author=None)

    resp = APIClient().get("/forum/boards/contrib-gone/contributors/")

    assert _names(resp) == [("kept", 1)]


@pytest.mark.django_db
def test_an_empty_forum_has_no_contributors():
    make_forum(name="General", slug="contrib-empty")

    resp = APIClient().get("/forum/boards/contrib-empty/contributors/")

    assert resp.status_code == 200
    assert resp.data == {"results": []}


@pytest.mark.django_db
def test_an_unknown_forum_is_404():
    assert APIClient().get("/forum/boards/no-such/contributors/").status_code == 404


@pytest.mark.django_db
def test_hides_members_the_viewer_has_blocked():
    from wagtail_forum.models import UserBlock

    board = make_forum(name="General", slug="contrib-block")
    viewer, loud, quiet = _user("viewer"), _user("loud"), _user("quiet")
    topic = _topic(board, quiet, "block-1")
    _reply(topic, loud, 4)
    UserBlock.objects.create(blocker=viewer, blocked=loud)
    client = APIClient()
    client.force_authenticate(viewer)

    assert _names(client.get("/forum/boards/contrib-block/contributors/")) == [
        ("quiet", 1)
    ]
    # Another viewer still sees them.
    assert _names(APIClient().get("/forum/boards/contrib-block/contributors/"))[0] == (
        "loud",
        4,
    )


@pytest.mark.django_db
def test_query_count_does_not_grow_with_contributors():
    board = make_forum(name="General", slug="contrib-q")
    topic = _topic(board, _user("q-0"), "q-1")

    def count():
        with CaptureQueriesContext(connection) as ctx:
            resp = APIClient().get("/forum/boards/contrib-q/contributors/")
        assert resp.status_code == 200
        return len(ctx)

    one = count()
    for i in range(1, 4):
        _reply(topic, _user(f"q-{i}"), 1)
    assert count() == one
