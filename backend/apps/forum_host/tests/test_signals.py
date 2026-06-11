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
