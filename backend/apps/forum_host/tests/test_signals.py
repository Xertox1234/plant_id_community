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
)

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
def test_reply_added_enqueues_push_for_topic_author(django_capture_on_commit_callbacks):
    """reply_added must enqueue send_forum_push for the topic author."""
    topic_author = User.objects.create_user(username="topicowner")
    replier = User.objects.create_user(username="replier")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum2", slug="forum2"))
    board = index.add_child(instance=ForumBoard(title="General2", slug="general2"))
    topic = Topic.objects.create(
        board=board, title="T2", slug="t2", author=topic_author
    )

    with (
        patch("apps.forum_host.tasks.send_forum_push.delay") as mock_delay,
        # The reply_added success path also enqueues an email (todo 253 slice
        # 2, H1) via the same on_commit mechanism; mock it so this push-only
        # test doesn't attempt a real broker publish.
        patch("apps.forum_host.tasks.send_forum_email.delay"),
    ):
        from apps.forum_host.notifications import dispatch

        # A real (saved) Post — the Notification fan-out (todo 253 slice 1)
        # needs a real pk; bulk_create rejects an unsaved related object.
        post = Post.objects.create(topic=topic, author=replier)
        # The push enqueue is now deferred to transaction.on_commit (slice 1);
        # this fixture runs captured on_commit callbacks immediately.
        with django_capture_on_commit_callbacks(execute=True):
            dispatch("reply_added", topic=topic, post=post)

    mock_delay.assert_called_once()
    call_args = mock_delay.call_args
    assert call_args.args[0] == "reply_added"
    assert call_args.args[1] == topic_author.pk


@pytest.mark.django_db
def test_reply_added_enqueues_email_for_topic_author(
    django_capture_on_commit_callbacks,
):
    """reply_added must enqueue send_forum_email for the topic author (todo
    253 slice 2, H1) — mirrors test_reply_added_enqueues_push_for_topic_author.
    Rendered-content correctness (the two latent bugs the wiring surfaced) is
    covered separately by the task-level tests in test_tasks.py; this test
    only proves the enqueue wiring itself."""
    topic_author = User.objects.create_user(username="topicowner12")
    replier = User.objects.create_user(username="replier12")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum12", slug="forum12"))
    board = index.add_child(instance=ForumBoard(title="General12", slug="general12"))
    topic = Topic.objects.create(
        board=board, title="T12", slug="t12", author=topic_author
    )

    with (
        patch("apps.forum_host.tasks.send_forum_push.delay"),
        patch("apps.forum_host.tasks.send_forum_email.delay") as mock_delay,
    ):
        from apps.forum_host.notifications import dispatch

        post = Post.objects.create(topic=topic, author=replier)
        with django_capture_on_commit_callbacks(execute=True):
            dispatch("reply_added", topic=topic, post=post)

    mock_delay.assert_called_once()
    call_args = mock_delay.call_args
    assert call_args.args[0] == "reply_added"
    assert call_args.args[1] == topic_author.pk
    assert call_args.args[2]["post_id"] == str(post.pk)


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
    # A self-reply also must not persist an in-app notification (todo 253 slice 1).
    assert not Notification.objects.filter(recipient=author).exists()


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
def test_reply_added_swallows_push_delay_failure(
    caplog, django_capture_on_commit_callbacks
):
    """A Celery/broker failure on enqueue must not propagate out of dispatch() (todo 252)."""
    topic_author = User.objects.create_user(username="topicowner2")
    replier = User.objects.create_user(username="replier2")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum6", slug="forum6"))
    board = index.add_child(instance=ForumBoard(title="General6", slug="general6"))
    topic = Topic.objects.create(
        board=board, title="T6", slug="t6", author=topic_author
    )

    with (
        patch(
            "apps.forum_host.tasks.send_forum_push.delay",
            side_effect=RuntimeError("broker unavailable"),
        ) as mock_delay,
        # The reply_added success path also enqueues an email (todo 253 slice
        # 2, H1) via the same on_commit mechanism; mock it so this push-only
        # test doesn't attempt a real broker publish.
        patch("apps.forum_host.tasks.send_forum_email.delay"),
    ):
        from apps.forum_host.notifications import dispatch

        post = Post.objects.create(topic=topic, author=replier)
        with caplog.at_level("ERROR", logger="forum_host.notifications"):
            # Executing the captured on_commit callback is what actually calls
            # .delay() now (todo 253 slice 1) — that's where the swallow happens.
            with django_capture_on_commit_callbacks(execute=True):
                dispatch("reply_added", topic=topic, post=post)  # must not raise

    mock_delay.assert_called_once()
    assert "failed to enqueue push" in caplog.text


@pytest.mark.django_db
def test_reply_added_persists_notification_row(django_capture_on_commit_callbacks):
    """reply_added must persist a Notification row for the topic author
    (todo 253 slice 1, audit C2) — independent of whether the push succeeds."""
    topic_author = User.objects.create_user(username="topicowner9")
    replier = User.objects.create_user(username="replier9")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum9", slug="forum9"))
    board = index.add_child(instance=ForumBoard(title="General9", slug="general9"))
    topic = Topic.objects.create(
        board=board, title="T9", slug="t9", author=topic_author
    )
    post = Post.objects.create(topic=topic, author=replier)

    with (
        patch("apps.forum_host.tasks.send_forum_push.delay"),
        # The reply_added success path also enqueues an email (todo 253 slice
        # 2, H1) via the same on_commit mechanism; mock it so this
        # notification-row test doesn't attempt a real broker publish.
        patch("apps.forum_host.tasks.send_forum_email.delay"),
    ):
        from apps.forum_host.notifications import dispatch

        with django_capture_on_commit_callbacks(execute=True):
            dispatch("reply_added", topic=topic, post=post)

    notification = Notification.objects.get(recipient=topic_author)
    assert notification.verb == NotificationVerb.REPLY
    assert notification.actor_id == replier.pk
    assert notification.topic_id == topic.pk
    assert notification.post_id == post.pk
    assert notification.read_at is None


@pytest.mark.django_db
def test_reply_added_notification_and_push_roll_back_together():
    """The bug this slice fixes: previously .delay() ran synchronously inside
    the open publish transaction, so a push could fire for a reply that (from
    the DB's perspective) never happened. Now BOTH the Notification row and
    the push enqueue are transaction-scoped and must roll back together."""
    from django.db import transaction

    topic_author = User.objects.create_user(username="topicowner10")
    replier = User.objects.create_user(username="replier10")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum10", slug="forum10"))
    board = index.add_child(instance=ForumBoard(title="General10", slug="general10"))
    topic = Topic.objects.create(
        board=board, title="T10", slug="t10", author=topic_author
    )
    post = Post.objects.create(topic=topic, author=replier)

    with patch("apps.forum_host.tasks.send_forum_push.delay") as mock_delay:
        from apps.forum_host.notifications import dispatch

        with pytest.raises(RuntimeError):
            with transaction.atomic():
                dispatch("reply_added", topic=topic, post=post)
                raise RuntimeError("simulated failure after dispatch, before commit")

    assert not Notification.objects.filter(recipient=topic_author, post=post).exists()
    mock_delay.assert_not_called()


@pytest.mark.django_db
def test_reply_added_skips_push_when_notification_write_fails(
    caplog, django_capture_on_commit_callbacks
):
    """A DB error inside create_notifications() must not still deliver a push
    — kimi-review caught this: the except block logged and swallowed the
    error, but execution fell through to register the on_commit push
    regardless, so a failed notification write could still push the user
    with nothing for them to see in the bell."""
    topic_author = User.objects.create_user(username="topicowner11")
    replier = User.objects.create_user(username="replier11")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum11", slug="forum11"))
    board = index.add_child(instance=ForumBoard(title="General11", slug="general11"))
    topic = Topic.objects.create(
        board=board, title="T11", slug="t11", author=topic_author
    )
    post = Post.objects.create(topic=topic, author=replier)

    with (
        patch(
            "wagtail_forum.notifications.create_notifications",
            side_effect=RuntimeError("simulated DB error"),
        ),
        patch("apps.forum_host.tasks.send_forum_push.delay") as mock_delay,
    ):
        from apps.forum_host.notifications import dispatch

        with caplog.at_level("ERROR", logger="forum_host.notifications"):
            with django_capture_on_commit_callbacks(execute=True):
                dispatch("reply_added", topic=topic, post=post)  # must not raise

    assert "failed to persist notification" in caplog.text
    mock_delay.assert_not_called()


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
