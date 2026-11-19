"""Pin/unpin a topic from the API (`topics/<id>/pin/`).

The write is one column; what is worth pinning is WHO may do it (moderators,
not even the topic's author), that a hidden topic 404s before the permission
error, and that the list order and the detail's `can_pin` follow it.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail_forum.models import Post, Topic
from wagtail_forum.tests.factories import make_forum

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _moderator(username):
    user = User.objects.create_user(username=username)
    user.user_permissions.add(
        Permission.objects.get(
            codename="change_post", content_type__app_label="wagtail_forum"
        )
    )
    return User.objects.get(pk=user.pk)  # re-fetch: perm cache is per-instance


def _topic(slug, *, board=None, live=True, author=None, title="T"):
    board = board or make_forum(name="General", slug=f"board-{slug}")
    author = author or User.objects.create_user(username=f"author-{slug}")
    topic = Topic.objects.create(
        board=board,
        title=title,
        slug=f"t-{slug}",
        author=author,
        live=live,
        last_post_at=timezone.now(),
    )
    Post.objects.create(topic=topic, author=author, is_opening_post=True, live=True)
    return topic


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


@pytest.mark.django_db
def test_a_moderator_pins_and_unpins_a_topic():
    topic = _topic("mod")
    client = _client(_moderator("mod-pin"))

    resp = client.post(f"/forum/topics/{topic.id}/pin/")
    assert resp.status_code == 200
    assert resp.data == {"is_pinned": True}
    topic.refresh_from_db()
    assert topic.is_pinned is True

    resp = client.delete(f"/forum/topics/{topic.id}/pin/")
    assert resp.status_code == 200
    assert resp.data == {"is_pinned": False}
    topic.refresh_from_db()
    assert topic.is_pinned is False


@pytest.mark.django_db
def test_pinning_twice_and_unpinning_an_unpinned_topic_are_no_ops():
    topic = _topic("idem")
    client = _client(_moderator("mod-idem"))

    assert client.delete(f"/forum/topics/{topic.id}/pin/").data == {"is_pinned": False}
    client.post(f"/forum/topics/{topic.id}/pin/")
    stamped = Topic.objects.get(pk=topic.pk).updated_at
    assert client.post(f"/forum/topics/{topic.id}/pin/").data == {"is_pinned": True}
    # The second pin wrote nothing.
    assert Topic.objects.get(pk=topic.pk).updated_at == stamped


@pytest.mark.django_db
def test_the_topics_own_author_cannot_pin_it():
    author = User.objects.create_user(username="own-author")
    topic = _topic("own", author=author)

    for method in ("post", "delete"):
        resp = getattr(_client(author), method)(f"/forum/topics/{topic.id}/pin/")
        assert resp.status_code == 403
    topic.refresh_from_db()
    assert topic.is_pinned is False


@pytest.mark.django_db
def test_a_bystander_cannot_unpin_a_pinned_topic():
    topic = _topic("bystander")
    Topic.objects.filter(pk=topic.pk).update(is_pinned=True)
    bystander = User.objects.create_user(username="bystander-pin")

    resp = _client(bystander).delete(f"/forum/topics/{topic.id}/pin/")

    assert resp.status_code == 403
    topic.refresh_from_db()
    assert topic.is_pinned is True


@pytest.mark.django_db
def test_anonymous_cannot_pin():
    topic = _topic("anon")

    resp = _client().post(f"/forum/topics/{topic.id}/pin/")

    assert resp.status_code in (401, 403)
    topic.refresh_from_db()
    assert topic.is_pinned is False


@pytest.mark.django_db
def test_a_non_live_topic_is_404_even_for_a_moderator_and_for_a_bystander():
    """Visibility before permission: a bystander must not learn from a 403
    that a hidden topic exists."""
    topic = _topic("hidden", live=False)
    bystander = User.objects.create_user(username="bystander-hidden")

    assert _client(bystander).post(f"/forum/topics/{topic.id}/pin/").status_code == 404
    assert (
        _client(_moderator("mod-hidden"))
        .post(f"/forum/topics/{topic.id}/pin/")
        .status_code
        == 404
    )
    topic.refresh_from_db()
    assert topic.is_pinned is False


@pytest.mark.django_db
def test_a_pinned_topic_moves_to_the_top_of_its_forums_list():
    board = make_forum(name="General", slug="board-order")
    older = _topic("older", board=board, title="Older")
    _topic("newer", board=board, title="Newer")
    client = _client(_moderator("mod-order"))

    before = client.get("/forum/boards/board-order/topics/").data["results"]
    assert [row["title"] for row in before] == ["Newer", "Older"]

    client.post(f"/forum/topics/{older.id}/pin/")

    after = client.get("/forum/boards/board-order/topics/").data["results"]
    assert [row["title"] for row in after] == ["Older", "Newer"]
    assert after[0]["is_pinned"] is True


@pytest.mark.django_db
def test_topic_detail_can_pin_follows_the_write_rule():
    author = User.objects.create_user(username="detail-author")
    topic = _topic("detail", author=author)

    assert _client().get(f"/forum/topics/{topic.id}/").data["can_pin"] is False
    assert _client(author).get(f"/forum/topics/{topic.id}/").data["can_pin"] is False
    assert (
        _client(_moderator("mod-detail"))
        .get(f"/forum/topics/{topic.id}/")
        .data["can_pin"]
        is True
    )
