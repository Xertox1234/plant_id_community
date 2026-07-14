import pytest
from django.contrib.auth import get_user_model
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    Notification,
    NotificationVerb,
    Post,
    Topic,
)
from wagtail_forum.notifications import create_notifications

User = get_user_model()


def _topic_and_post(topic_author, post_author=None):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    topic = Topic.objects.create(board=board, title="T", slug="t", author=topic_author)
    post = Post.objects.create(topic=topic, author=post_author or topic_author)
    return topic, post


@pytest.mark.django_db
def test_create_notifications_creates_row_for_recipient():
    recipient = User.objects.create_user(username="recipient")
    actor = User.objects.create_user(username="actor")
    topic, post = _topic_and_post(recipient, actor)

    created = create_notifications(
        recipients=[recipient],
        verb=NotificationVerb.REPLY,
        actor=actor,
        topic=topic,
        post=post,
    )

    assert len(created) == 1
    notification = Notification.objects.get(recipient=recipient)
    assert notification.actor_id == actor.pk
    assert notification.verb == NotificationVerb.REPLY
    assert notification.topic_id == topic.pk
    assert notification.post_id == post.pk
    assert notification.read_at is None


@pytest.mark.django_db
def test_create_notifications_skips_self_notify():
    user = User.objects.create_user(username="selfie")
    topic, post = _topic_and_post(user)

    created = create_notifications(
        recipients=[user],
        verb=NotificationVerb.REPLY,
        actor=user,
        topic=topic,
        post=post,
    )

    assert created == []
    assert not Notification.objects.filter(recipient=user).exists()


@pytest.mark.django_db
def test_create_notifications_skips_none_recipients():
    """Defensive: a caller's recipient list may contain None (e.g. a
    denormalized author reference gone null) — must not raise."""
    actor = User.objects.create_user(username="actor2")
    recipient = User.objects.create_user(username="recipient2")
    topic, post = _topic_and_post(recipient, actor)

    created = create_notifications(
        recipients=[None, recipient],
        verb=NotificationVerb.REPLY,
        actor=actor,
        topic=topic,
        post=post,
    )

    assert len(created) == 1
    assert Notification.objects.filter(recipient=recipient).count() == 1


@pytest.mark.django_db
def test_create_notifications_is_idempotent_for_same_target():
    """Firing the same event twice (e.g. a retried signal) must not duplicate
    a recipient's notification for the same (recipient, verb, post)."""
    recipient = User.objects.create_user(username="recipient3")
    actor = User.objects.create_user(username="actor3")
    topic, post = _topic_and_post(recipient, actor)

    create_notifications(
        recipients=[recipient],
        verb=NotificationVerb.REPLY,
        actor=actor,
        topic=topic,
        post=post,
    )
    create_notifications(
        recipients=[recipient],
        verb=NotificationVerb.REPLY,
        actor=actor,
        topic=topic,
        post=post,
    )

    assert (
        Notification.objects.filter(
            recipient=recipient, verb=NotificationVerb.REPLY, post=post
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_create_notifications_allows_none_actor_for_system_events():
    recipient = User.objects.create_user(username="recipient4")
    topic, post = _topic_and_post(recipient)

    created = create_notifications(
        recipients=[recipient],
        verb=NotificationVerb.REPLY,
        actor=None,
        topic=topic,
        post=post,
    )

    assert len(created) == 1
    assert Notification.objects.get(recipient=recipient).actor_id is None


@pytest.mark.django_db
def test_create_notifications_returns_empty_list_for_no_recipients():
    topic, post = _topic_and_post(User.objects.create_user(username="lonely"))

    assert (
        create_notifications(
            recipients=[], verb=NotificationVerb.REPLY, topic=topic, post=post
        )
        == []
    )
