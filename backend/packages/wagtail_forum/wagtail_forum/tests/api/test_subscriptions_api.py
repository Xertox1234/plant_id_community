import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from wagtail.models import Page, PageViewRestriction
from wagtail_forum.models import ForumBoard, ForumIndex, Topic, TopicSubscription

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board(slug="general"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    return index.add_child(instance=ForumBoard(title="General", slug=slug))


def _topic(slug="t", live=True, board=None):
    board = board or _board(slug)
    return Topic.objects.create(board=board, title="T", slug=slug, live=live)


@pytest.mark.django_db
def test_subscribe_creates_subscription():
    user = User.objects.create_user(username="sub1")
    topic = _topic("sub-t1")

    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(f"/forum/topics/{topic.id}/subscription/")

    assert resp.status_code == 200
    assert resp.data == {"subscribed": True}
    assert TopicSubscription.objects.filter(user=user, topic=topic).exists()


@pytest.mark.django_db
def test_subscribe_is_idempotent():
    user = User.objects.create_user(username="sub2")
    topic = _topic("sub-t2")

    client = APIClient()
    client.force_authenticate(user)
    client.post(f"/forum/topics/{topic.id}/subscription/")
    resp = client.post(f"/forum/topics/{topic.id}/subscription/")

    assert resp.status_code == 200
    assert TopicSubscription.objects.filter(user=user, topic=topic).count() == 1


@pytest.mark.django_db
def test_unsubscribe_removes_subscription():
    user = User.objects.create_user(username="sub3")
    topic = _topic("sub-t3")
    TopicSubscription.subscribe(user, topic)

    client = APIClient()
    client.force_authenticate(user)
    resp = client.delete(f"/forum/topics/{topic.id}/subscription/")

    assert resp.status_code == 200
    assert resp.data == {"subscribed": False}
    assert not TopicSubscription.objects.filter(user=user, topic=topic).exists()


@pytest.mark.django_db
def test_unsubscribe_when_not_subscribed_is_idempotent():
    user = User.objects.create_user(username="sub4")
    topic = _topic("sub-t4")

    client = APIClient()
    client.force_authenticate(user)
    resp = client.delete(f"/forum/topics/{topic.id}/subscription/")

    assert resp.status_code == 200
    assert resp.data == {"subscribed": False}


@pytest.mark.django_db
def test_unsubscribe_succeeds_when_topic_is_no_longer_live():
    """DELETE mutates only the caller's own subscription row, so it must not
    404 once the topic they're subscribed to is unpublished — unlike POST,
    there's no existence leak to guard against (the row's mere existence
    already proves the user could see the topic when they subscribed).
    Regression test: reusing POST's visibility gate on DELETE stranded an
    existing subscriber (todo 253 slice 3 review, confirmed via repro)."""
    user = User.objects.create_user(username="sub10")
    topic = _topic("sub-t10")
    TopicSubscription.subscribe(user, topic)
    topic.live = False
    topic.save()

    client = APIClient()
    client.force_authenticate(user)
    resp = client.delete(f"/forum/topics/{topic.id}/subscription/")

    assert resp.status_code == 200
    assert resp.data == {"subscribed": False}
    assert not TopicSubscription.objects.filter(user=user, topic=topic).exists()


@pytest.mark.django_db
def test_unsubscribe_succeeds_when_board_is_restricted():
    """Same regression as above, for the board-restriction visibility path."""
    user = User.objects.create_user(username="sub11")
    board = _board("sub-b11")
    topic = _topic("sub-t11", board=board)
    TopicSubscription.subscribe(user, topic)
    PageViewRestriction.objects.create(page=board, restriction_type="login")

    client = APIClient()
    client.force_authenticate(user)
    resp = client.delete(f"/forum/topics/{topic.id}/subscription/")

    assert resp.status_code == 200
    assert not TopicSubscription.objects.filter(user=user, topic=topic).exists()


@pytest.mark.django_db
def test_unsubscribe_from_nonexistent_topic_is_a_no_op():
    """Unlike POST (which 404s a nonexistent topic_id), DELETE is a pure
    filter-delete on the user's own subscription row — no topic lookup, so
    a bogus topic_id is just another form of "not subscribed" (200, no-op)."""
    user = User.objects.create_user(username="sub12")

    client = APIClient()
    client.force_authenticate(user)
    resp = client.delete("/forum/topics/999999/subscription/")

    assert resp.status_code == 200
    assert resp.data == {"subscribed": False}


@pytest.mark.django_db
def test_subscribe_requires_auth():
    topic = _topic("sub-t5")
    resp = APIClient().post(f"/forum/topics/{topic.id}/subscription/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_unsubscribe_requires_auth():
    topic = _topic("sub-t6")
    resp = APIClient().delete(f"/forum/topics/{topic.id}/subscription/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_subscribe_to_draft_topic_404s():
    user = User.objects.create_user(username="sub7")
    topic = _topic("sub-t7", live=False)

    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(f"/forum/topics/{topic.id}/subscription/")

    assert resp.status_code == 404
    assert not TopicSubscription.objects.filter(topic=topic).exists()


@pytest.mark.django_db
def test_subscribe_to_restricted_board_topic_404s():
    """A hidden/restricted board's topic 404s, not 403s — no existence leak
    (same idiom as every other content endpoint's _visible_boards() gate)."""
    user = User.objects.create_user(username="sub8")
    board = _board("sub-b8")
    topic = _topic("sub-t8", board=board)
    PageViewRestriction.objects.create(page=board, restriction_type="login")

    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(f"/forum/topics/{topic.id}/subscription/")

    assert resp.status_code == 404
    assert not TopicSubscription.objects.filter(topic=topic).exists()


@pytest.mark.django_db
def test_subscribe_to_nonexistent_topic_404s():
    user = User.objects.create_user(username="sub9")

    client = APIClient()
    client.force_authenticate(user)
    resp = client.post("/forum/topics/999999/subscription/")

    assert resp.status_code == 404
