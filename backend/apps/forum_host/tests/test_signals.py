from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()


@pytest.mark.django_db
def test_publishing_a_reply_dispatches_a_host_notification(monkeypatch):
    events = []
    from apps.forum_host import notifications

    monkeypatch.setattr(
        notifications, "dispatch", lambda event, **kw: events.append(event)
    )

    author = User.objects.create_user(username="ada", password="x")
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    topic = Topic.objects.create(board=board, title="T", slug="t", author=author)

    opening = Post.objects.create(topic=topic, author=author, is_opening_post=True)
    opening.save_revision().publish()
    # topic_created fires on the TOPIC's first publish (2026-06-10 audit M2:
    # firing it from the opening post's publish deep-linked to a draft topic).
    topic.save_revision().publish()
    reply = Post.objects.create(topic=topic, author=author, is_opening_post=False)
    reply.save_revision().publish()

    assert "topic_created" in events
    assert "reply_added" in events


# ---- push-notification routing tests ----------------------------------------


@pytest.mark.django_db
def test_reply_added_enqueues_push_for_topic_author():
    """reply_added must enqueue send_forum_push for the topic author."""
    topic_author = User.objects.create_user(username="topicowner", password="x")
    replier = User.objects.create_user(username="replier", password="x")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum2", slug="forum2"))
    board = index.add_child(instance=ForumBoard(title="General2", slug="general2"))
    topic = Topic.objects.create(
        board=board, title="T2", slug="t2", author=topic_author
    )

    with patch("apps.forum_host.tasks.send_forum_push.delay") as mock_delay:
        from apps.forum_host.notifications import dispatch

        post = Post(topic=topic, author=replier)
        dispatch("reply_added", topic=topic, post=post)

    mock_delay.assert_called_once()
    call_args = mock_delay.call_args
    assert call_args.args[0] == "reply_added"
    assert call_args.args[1] == topic_author.pk


@pytest.mark.django_db
def test_reply_added_does_not_push_for_self_reply():
    """An author replying to their own topic must not receive a push."""
    author = User.objects.create_user(username="selfie", password="x")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum3", slug="forum3"))
    board = index.add_child(instance=ForumBoard(title="General3", slug="general3"))
    topic = Topic.objects.create(board=board, title="T3", slug="t3", author=author)

    with patch("apps.forum_host.tasks.send_forum_push.delay") as mock_delay:
        from apps.forum_host.notifications import dispatch

        post = Post(topic=topic, author=author)
        dispatch("reply_added", topic=topic, post=post)

    mock_delay.assert_not_called()


@pytest.mark.django_db
def test_moderation_decided_enqueues_push_for_post_author():
    """moderation_decided must enqueue send_forum_push for the post's author."""
    author = User.objects.create_user(username="modauthor", password="x")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum4", slug="forum4"))
    board = index.add_child(instance=ForumBoard(title="General4", slug="general4"))
    topic = Topic.objects.create(board=board, title="T4", slug="t4", author=author)
    post = Post(topic=topic, author=author)

    with patch("apps.forum_host.tasks.send_forum_push.delay") as mock_delay:
        from apps.forum_host.notifications import dispatch

        dispatch("moderation_decided", topic=topic, obj=post, status="published")

    mock_delay.assert_called_once()
    call_args = mock_delay.call_args
    assert call_args.args[0] == "moderation_decided"
    assert call_args.args[1] == author.pk
    assert call_args.args[2]["status"] == "published"
