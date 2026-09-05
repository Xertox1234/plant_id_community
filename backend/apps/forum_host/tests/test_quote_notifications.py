"""QUOTE fan-out (todo 342): quoted authors get a QUOTE notification (with the
quoted post) instead of a plain REPLY; a mention of the same person wins;
blocked pairs and self-quotes get nothing; push uses the "quote" event."""

from unittest.mock import patch

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
    TopicSubscription,
    UserBlock,
)

User = get_user_model()


def _board(slug):
    root = Page.objects.get(id=1)
    index = root.add_child(
        instance=ForumIndex(title=f"Forum {slug}", slug=f"forum-{slug}")
    )
    return index.add_child(instance=ForumBoard(title=f"General {slug}", slug=slug))


def _quote(post, text="quoted"):
    return {"type": "post_quote", "value": {"post": post.pk, "text": text}}


def _dispatch(django_capture_on_commit_callbacks, event, **kwargs):
    with (
        patch("apps.forum_host.tasks.send_forum_push_batch.delay") as mock_push,
        patch("apps.forum_host.tasks.send_forum_email_batch.delay") as mock_email,
    ):
        from apps.forum_host.notifications import dispatch

        with django_capture_on_commit_callbacks(execute=True):
            dispatch(event, **kwargs)
    return mock_push, mock_email


@pytest.mark.django_db
def test_quoting_a_post_notifies_its_author_with_quote_not_reply(
    django_capture_on_commit_callbacks,
):
    board = _board("q1")
    quoted_author = User.objects.create_user(username="q1-quoted")
    plain_subscriber = User.objects.create_user(username="q1-plain")
    replier = User.objects.create_user(username="q1-replier")
    topic = Topic.objects.create(
        board=board, title="T", slug="t-q1", author=quoted_author, live=True
    )
    original = Post.objects.create(
        topic=topic,
        author=quoted_author,
        live=True,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": "<p>hi</p>"}],
    )
    TopicSubscription.subscribe(quoted_author, topic)
    TopicSubscription.subscribe(plain_subscriber, topic)
    reply = Post.objects.create(
        topic=topic,
        author=replier,
        live=True,
        body=[_quote(original), {"type": "paragraph", "value": "<p>+1</p>"}],
    )

    mock_push, mock_email = _dispatch(
        django_capture_on_commit_callbacks, "reply_added", topic=topic, post=reply
    )

    rows = Notification.objects.filter(recipient=quoted_author, post=reply)
    assert rows.count() == 1
    row = rows.get()
    assert row.verb == NotificationVerb.QUOTE and row.quoted_post_id == original.pk
    assert (
        Notification.objects.get(recipient=plain_subscriber, post=reply).verb
        == NotificationVerb.REPLY
    )
    quote_pushes = [c for c in mock_push.call_args_list if c.args[0] == "quote"]
    assert len(quote_pushes) == 1 and quote_pushes[0].args[1] == [quoted_author.pk]
    # The quoted author is not in the reply push/email batches.
    assert all(
        quoted_author.pk not in c.args[1]
        for c in mock_push.call_args_list
        if c.args[0] == "reply_added"
    )
    assert all(quoted_author.pk not in c.args[1] for c in mock_email.call_args_list)


@pytest.mark.django_db
def test_a_mention_beats_a_quote_and_blocked_or_self_quotes_notify_nobody(
    django_capture_on_commit_callbacks,
):
    board = _board("q2")
    both = User.objects.create_user(username="q2both")
    blocker = User.objects.create_user(username="q2-blocker")
    replier = User.objects.create_user(username="q2-replier")
    topic = Topic.objects.create(
        board=board, title="T", slug="t-q2", author=both, live=True
    )
    both_post = Post.objects.create(
        topic=topic,
        author=both,
        live=True,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": "<p>a</p>"}],
    )
    blocker_post = Post.objects.create(
        topic=topic,
        author=blocker,
        live=True,
        body=[{"type": "paragraph", "value": "<p>b</p>"}],
    )
    own_post = Post.objects.create(
        topic=topic,
        author=replier,
        live=True,
        body=[{"type": "paragraph", "value": "<p>c</p>"}],
    )
    UserBlock.objects.create(blocker=blocker, blocked=replier)
    reply = Post.objects.create(
        topic=topic,
        author=replier,
        live=True,
        body=[
            {"type": "paragraph", "value": "<p>@q2both see</p>"},
            _quote(both_post),
            _quote(blocker_post),
            _quote(own_post),
        ],
    )

    mock_push, _ = _dispatch(
        django_capture_on_commit_callbacks, "reply_added", topic=topic, post=reply
    )

    both_rows = Notification.objects.filter(recipient=both, post=reply)
    assert both_rows.count() == 1 and both_rows.get().verb == NotificationVerb.MENTION
    assert not Notification.objects.filter(recipient=blocker, post=reply).exists()
    assert not Notification.objects.filter(recipient=replier, post=reply).exists()
    assert not any(c.args[0] == "quote" for c in mock_push.call_args_list)


@pytest.mark.django_db
def test_an_opening_post_can_quote_too(django_capture_on_commit_callbacks):
    board = _board("q3")
    quoted_author = User.objects.create_user(username="q3-quoted")
    starter = User.objects.create_user(username="q3-starter")
    source_topic = Topic.objects.create(
        board=board, title="S", slug="s-q3", author=quoted_author, live=True
    )
    original = Post.objects.create(
        topic=source_topic,
        author=quoted_author,
        live=True,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": "<p>hi</p>"}],
    )
    topic = Topic.objects.create(
        board=board, title="N", slug="n-q3", author=starter, live=True
    )
    opening = Post.objects.create(
        topic=topic,
        author=starter,
        live=True,
        is_opening_post=True,
        body=[_quote(original)],
    )

    mock_push, _ = _dispatch(
        django_capture_on_commit_callbacks, "topic_created", topic=topic, post=opening
    )

    row = Notification.objects.get(recipient=quoted_author, post=opening)
    assert row.verb == NotificationVerb.QUOTE and row.quoted_post_id == original.pk
    assert [c.args[0] for c in mock_push.call_args_list] == ["quote"]


def test_quote_push_copy_exists():
    from apps.forum_host.notification_copy import push_content

    title, body = push_content("quote", "Monstera help", "ada")
    assert "quoted" in title and body == "ada quoted your post"
