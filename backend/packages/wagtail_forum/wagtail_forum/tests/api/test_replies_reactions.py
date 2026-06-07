import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Reaction, Topic
from wagtail_forum.workflow import ensure_default_workflow

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


def _live_topic(closed=False):
    board = _board()
    author = User.objects.create_user(username="op", password="x")
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
    user = User.objects.create_user(username="r", password="x")
    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(
        f"/forum/topics/{topic.id}/posts/create/",
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
    author = User.objects.create_user(username="op", password="x")
    draft = Topic.objects.create(
        board=board, title="Hidden", slug="hidden", author=author, live=False
    )
    user = User.objects.create_user(username="r", password="x")
    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(
        f"/forum/topics/{draft.id}/posts/create/",
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
    user = User.objects.create_user(username="r", password="x")
    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(
        f"/forum/topics/{topic.id}/posts/create/",
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
    user = User.objects.create_user(username="r", password="x")
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
    user = User.objects.create_user(username="r", password="x")
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
    author = User.objects.create_user(username="op", password="x")
    draft = Topic.objects.create(
        board=board, title="H", slug="h", author=author, live=False
    )
    hidden_post = Post.objects.create(
        topic=draft, author=author, is_opening_post=True, live=False
    )
    user = User.objects.create_user(username="r", password="x")
    client = APIClient()
    client.force_authenticate(user)
    resp = client.post(
        f"/forum/posts/{hidden_post.id}/reactions/", {"type": "like"}, format="json"
    )
    assert resp.status_code == 404
    assert Reaction.objects.filter(post=hidden_post).count() == 0
