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

    author = User.objects.create_user(username="ada")
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
    topic_author = User.objects.create_user(username="topicowner")
    replier = User.objects.create_user(username="replier")

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
    author = User.objects.create_user(username="selfie")

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
    author = User.objects.create_user(username="modauthor")

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


@pytest.mark.django_db
def test_moderation_decided_without_topic_kwarg_does_not_send_none_topic_id():
    """The real signal never passes `topic` (workflow.py calls notify(moderation_decided,
    sender=type(obj), obj=obj, status=status)) — topic_id must be derived from obj (todo 251).
    """
    author = User.objects.create_user(username="modauthor2")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum5", slug="forum5"))
    board = index.add_child(instance=ForumBoard(title="General5", slug="general5"))
    topic = Topic.objects.create(board=board, title="T5", slug="t5", author=author)
    post = Post(topic=topic, author=author)

    with patch("apps.forum_host.tasks.send_forum_push.delay") as mock_delay:
        from apps.forum_host.notifications import dispatch

        dispatch("moderation_decided", obj=post, status="published")

    mock_delay.assert_called_once()
    call_args = mock_delay.call_args
    assert call_args.args[2]["topic_id"] == str(topic.pk)
    assert call_args.args[2]["topic_id"] != "None"


@pytest.mark.django_db
def test_reply_added_swallows_push_delay_failure(caplog):
    """A Celery/broker failure on enqueue must not propagate out of dispatch() (todo 252)."""
    topic_author = User.objects.create_user(username="topicowner2")
    replier = User.objects.create_user(username="replier2")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum6", slug="forum6"))
    board = index.add_child(instance=ForumBoard(title="General6", slug="general6"))
    topic = Topic.objects.create(
        board=board, title="T6", slug="t6", author=topic_author
    )

    with patch(
        "apps.forum_host.tasks.send_forum_push.delay",
        side_effect=RuntimeError("broker unavailable"),
    ) as mock_delay:
        from apps.forum_host.notifications import dispatch

        post = Post(topic=topic, author=replier)
        with caplog.at_level("ERROR", logger="forum_host.notifications"):
            dispatch("reply_added", topic=topic, post=post)  # must not raise

    mock_delay.assert_called_once()
    assert "failed to enqueue push" in caplog.text


@pytest.mark.django_db
def test_moderation_decided_swallows_push_delay_failure(caplog):
    """A Celery/broker failure on enqueue must not propagate out of dispatch() (todo 252)."""
    author = User.objects.create_user(username="modauthor3")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum7", slug="forum7"))
    board = index.add_child(instance=ForumBoard(title="General7", slug="general7"))
    topic = Topic.objects.create(board=board, title="T7", slug="t7", author=author)
    post = Post(topic=topic, author=author)

    with patch(
        "apps.forum_host.tasks.send_forum_push.delay",
        side_effect=RuntimeError("broker unavailable"),
    ) as mock_delay:
        from apps.forum_host.notifications import dispatch

        with caplog.at_level("ERROR", logger="forum_host.notifications"):
            dispatch(
                "moderation_decided", obj=post, status="published"
            )  # must not raise

    mock_delay.assert_called_once()
    assert "failed to enqueue push" in caplog.text
