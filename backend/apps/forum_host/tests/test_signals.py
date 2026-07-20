from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from wagtail.models import Page, PageViewRestriction
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    Notification,
    NotificationVerb,
    Post,
    Topic,
    TopicRead,
    TopicSubscription,
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
    """reply_added must enqueue send_forum_push for a topic subscriber (todo
    253 slice 3: fan-out is now subscription-driven, so the topic author only
    gets pushed if subscribed — normally automatic via topic_created, made
    explicit here since this test dispatches reply_added directly)."""
    topic_author = User.objects.create_user(username="topicowner")
    replier = User.objects.create_user(username="replier")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum2", slug="forum2"))
    board = index.add_child(instance=ForumBoard(title="General2", slug="general2"))
    topic = Topic.objects.create(
        board=board, title="T2", slug="t2", author=topic_author
    )
    TopicSubscription.subscribe(topic_author, topic)

    with (
        patch("apps.forum_host.tasks.send_forum_push_batch.delay") as mock_delay,
        # The reply_added success path also enqueues an email (todo 253 slice
        # 2, H1) via the same on_commit mechanism; mock it so this push-only
        # test doesn't attempt a real broker publish.
        patch("apps.forum_host.tasks.send_forum_email_batch.delay"),
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
    # The recipient arg is now a BATCH list (todo 268): one enqueue for the
    # whole reply fan-out, not one .delay() per subscriber.
    assert call_args.args[1] == [topic_author.pk]
    # actor_name feeds the FCM tray body line (todo 253 slice 6), resolved
    # via the host User model's display_name — the same naming policy the
    # email channel already uses.
    assert call_args.args[2]["actor_name"] == replier.display_name


@pytest.mark.django_db
def test_reply_added_enqueues_email_for_topic_author(
    django_capture_on_commit_callbacks,
):
    """reply_added must enqueue send_forum_email for a topic subscriber (todo
    253 slice 2, H1 + slice 3 subscription-driven fan-out) — mirrors
    test_reply_added_enqueues_push_for_topic_author. Rendered-content
    correctness (the two latent bugs slice 2's wiring surfaced) is covered
    separately by the task-level tests in test_tasks.py; this test only
    proves the enqueue wiring itself."""
    topic_author = User.objects.create_user(username="topicowner12")
    replier = User.objects.create_user(username="replier12")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum12", slug="forum12"))
    board = index.add_child(instance=ForumBoard(title="General12", slug="general12"))
    topic = Topic.objects.create(
        board=board, title="T12", slug="t12", author=topic_author
    )
    TopicSubscription.subscribe(topic_author, topic)

    with (
        patch("apps.forum_host.tasks.send_forum_push_batch.delay"),
        patch("apps.forum_host.tasks.send_forum_email_batch.delay") as mock_delay,
    ):
        from apps.forum_host.notifications import dispatch

        post = Post.objects.create(topic=topic, author=replier)
        with django_capture_on_commit_callbacks(execute=True):
            dispatch("reply_added", topic=topic, post=post)

    mock_delay.assert_called_once()
    call_args = mock_delay.call_args
    assert call_args.args[0] == "reply_added"
    # One batched email enqueue for the whole reply fan-out (todo 268).
    assert call_args.args[1] == [topic_author.pk]
    assert call_args.args[2]["post_id"] == str(post.pk)


@pytest.mark.django_db
def test_reply_added_fans_out_to_all_subscribers_excluding_replier(
    django_capture_on_commit_callbacks,
):
    """Todo 253 slice 3 (H2/H3): a reply notifies every topic subscriber, not
    only the original author — the old author-only rule is gone. The replier
    is a genuine subscriber too (from an earlier reply) but is excluded from
    THEIR OWN reply's fan-out."""
    topic_author = User.objects.create_user(username="fanout-author")
    subscriber_b = User.objects.create_user(username="fanout-sub-b")
    replier = User.objects.create_user(username="fanout-replier")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="ForumFO", slug="forum-fo"))
    board = index.add_child(instance=ForumBoard(title="GeneralFO", slug="general-fo"))
    topic = Topic.objects.create(
        board=board, title="TFO", slug="t-fo", author=topic_author
    )
    TopicSubscription.subscribe(topic_author, topic)
    TopicSubscription.subscribe(subscriber_b, topic)
    TopicSubscription.subscribe(replier, topic)

    with (
        patch("apps.forum_host.tasks.send_forum_push_batch.delay") as mock_push,
        patch("apps.forum_host.tasks.send_forum_email_batch.delay") as mock_email,
    ):
        from apps.forum_host.notifications import dispatch

        post = Post.objects.create(topic=topic, author=replier)
        with django_capture_on_commit_callbacks(execute=True):
            dispatch("reply_added", topic=topic, post=post)

    notified = set(
        Notification.objects.filter(post=post).values_list("recipient_id", flat=True)
    )
    assert notified == {topic_author.pk, subscriber_b.pk}

    # The reply fan-out is now a SINGLE batched enqueue each (todo 268): the
    # whole recipient set rides in one list arg, not one .delay() per user.
    mock_push.assert_called_once()
    mock_email.assert_called_once()
    pushed = set(mock_push.call_args.args[1])
    emailed = set(mock_email.call_args.args[1])
    assert pushed == {topic_author.pk, subscriber_b.pk}
    assert emailed == {topic_author.pk, subscriber_b.pk}
    # The replier is excluded from their OWN reply's fan-out even though they
    # subscribed — the discriminating property this test exists to pin.
    assert replier.pk not in pushed
    assert replier.pk not in emailed


@pytest.mark.django_db
def test_reply_added_notifies_subscribers_when_topic_author_is_deleted(
    django_capture_on_commit_callbacks,
):
    """Topic.author is SET_NULL — a topic whose original author account was
    deleted must still fan out to its remaining subscribers (todo 253 slice 3
    removed the old `if topic_author is None: return` guard, which used to
    silently drop ALL notifications for such a topic, subscribers included)."""
    ghost_author = User.objects.create_user(username="fanout-ghost")
    subscriber = User.objects.create_user(username="fanout-survivor")
    replier = User.objects.create_user(username="fanout-replier2")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="ForumGH", slug="forum-gh"))
    board = index.add_child(instance=ForumBoard(title="GeneralGH", slug="general-gh"))
    topic = Topic.objects.create(
        board=board, title="TGH", slug="t-gh", author=ghost_author
    )
    TopicSubscription.subscribe(subscriber, topic)
    ghost_author.delete()
    topic.refresh_from_db()
    assert topic.author_id is None

    with (
        patch("apps.forum_host.tasks.send_forum_push_batch.delay") as mock_push,
        patch("apps.forum_host.tasks.send_forum_email_batch.delay"),
    ):
        from apps.forum_host.notifications import dispatch

        post = Post.objects.create(topic=topic, author=replier)
        with django_capture_on_commit_callbacks(execute=True):
            dispatch("reply_added", topic=topic, post=post)

    assert Notification.objects.filter(recipient=subscriber, post=post).exists()
    mock_push.assert_called_once()
    assert mock_push.call_args.args[1] == [subscriber.pk]


@pytest.mark.django_db
def test_reply_added_auto_subscribes_the_replier(django_capture_on_commit_callbacks):
    """Replying auto-subscribes you to the topic (todo 253 slice 3) — doesn't
    affect THIS event (you're still excluded from your own reply's
    notification), but a subsequent reply from someone else will notify you."""
    topic_author = User.objects.create_user(username="autosub-author")
    first_replier = User.objects.create_user(username="autosub-first")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="ForumAS", slug="forum-as"))
    board = index.add_child(instance=ForumBoard(title="GeneralAS", slug="general-as"))
    topic = Topic.objects.create(
        board=board, title="TAS", slug="t-as", author=topic_author
    )

    with (
        patch("apps.forum_host.tasks.send_forum_push_batch.delay"),
        patch("apps.forum_host.tasks.send_forum_email_batch.delay"),
    ):
        from apps.forum_host.notifications import dispatch

        post = Post.objects.create(topic=topic, author=first_replier)
        with django_capture_on_commit_callbacks(execute=True):
            dispatch("reply_added", topic=topic, post=post)

    assert TopicSubscription.objects.filter(user=first_replier, topic=topic).exists()
    # Excluded from their own reply's notification despite the new subscription.
    assert not Notification.objects.filter(recipient=first_replier, post=post).exists()


@pytest.mark.django_db
def test_topic_created_auto_subscribes_the_author():
    author = User.objects.create_user(username="topiccreate-author")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="ForumTC", slug="forum-tc"))
    board = index.add_child(instance=ForumBoard(title="GeneralTC", slug="general-tc"))
    topic = Topic.objects.create(board=board, title="TTC", slug="t-tc", author=author)

    from apps.forum_host.notifications import dispatch

    dispatch("topic_created", topic=topic, post=None)

    assert TopicSubscription.objects.filter(user=author, topic=topic).exists()


@pytest.mark.django_db
def test_topic_created_without_author_does_not_raise():
    """An admin-created topic can have no author (Topic.author is nullable) —
    there's nobody to auto-subscribe; dispatch must not raise."""
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="ForumTC2", slug="forum-tc2"))
    board = index.add_child(instance=ForumBoard(title="GeneralTC2", slug="general-tc2"))
    topic = Topic.objects.create(board=board, title="TTC2", slug="t-tc2", author=None)

    from apps.forum_host.notifications import dispatch

    dispatch("topic_created", topic=topic, post=None)  # must not raise

    assert not TopicSubscription.objects.filter(topic=topic).exists()


@pytest.mark.django_db
def test_reply_added_marks_the_repliers_own_topic_as_read(
    django_capture_on_commit_callbacks,
):
    """Replying marks the topic as already-read for the replier (todo 253
    slice 5 review, Angle A) — otherwise their own reply would make their own
    topic show 'unread' to themselves."""
    topic_author = User.objects.create_user(username="ownread-author")
    replier = User.objects.create_user(username="ownread-replier")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="ForumOR", slug="forum-or"))
    board = index.add_child(instance=ForumBoard(title="GeneralOR", slug="general-or"))
    topic = Topic.objects.create(
        board=board, title="TOR", slug="t-or", author=topic_author
    )

    with (
        patch("apps.forum_host.tasks.send_forum_push_batch.delay"),
        patch("apps.forum_host.tasks.send_forum_email_batch.delay"),
    ):
        from apps.forum_host.notifications import dispatch

        post = Post.objects.create(topic=topic, author=replier)
        with django_capture_on_commit_callbacks(execute=True):
            dispatch("reply_added", topic=topic, post=post)

    assert TopicRead.objects.filter(user=replier, topic=topic).exists()


@pytest.mark.django_db
def test_topic_created_marks_the_authors_own_topic_as_read():
    """Creating a topic marks it as already-read for its own author (todo
    253 slice 5 review, Angle A) — mirrors the reply_added fix above."""
    author = User.objects.create_user(username="ownread-tc-author")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="ForumORTC", slug="forum-ortc"))
    board = index.add_child(
        instance=ForumBoard(title="GeneralORTC", slug="general-ortc")
    )
    topic = Topic.objects.create(
        board=board, title="TORTC", slug="t-ortc", author=author
    )
    opening = Post.objects.create(topic=topic, author=author, is_opening_post=True)

    from apps.forum_host.notifications import dispatch

    dispatch("topic_created", topic=topic, post=opening)

    assert TopicRead.objects.filter(user=author, topic=topic).exists()


@pytest.mark.django_db
def test_topic_created_with_no_opening_post_does_not_mark_read():
    """An admin-created topic with no opening post has no timestamp to stamp
    from — matches this function's own existing precedent (mention
    resolution above) of skipping post-dependent behavior when post is None."""
    author = User.objects.create_user(username="ownread-tc-noauthor")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="ForumORTC2", slug="forum-ortc2"))
    board = index.add_child(
        instance=ForumBoard(title="GeneralORTC2", slug="general-ortc2")
    )
    topic = Topic.objects.create(
        board=board, title="TORTC2", slug="t-ortc2", author=author
    )

    from apps.forum_host.notifications import dispatch

    dispatch("topic_created", topic=topic, post=None)  # must not raise

    assert not TopicRead.objects.filter(topic=topic).exists()


@pytest.mark.django_db
def test_reply_added_read_marker_keeps_pace_with_real_publish_timing(
    django_capture_on_commit_callbacks,
):
    """Integration-level proof of the fix's actual timing property, through a
    REAL Wagtail publish chain rather than the Post.objects.create() shortcut
    the tests above use (which leaves first_published_at None, so `when`
    silently falls back to timezone.now() and never exercises the real
    value the fix relies on). Confirms TopicRead.last_read_at ends up
    strictly >= topic.last_post_at — the property the unread rule's strict
    `>` comparison depends on, and the reason post.first_published_at was
    used instead of topic.last_post_at (stale at dispatch-time)."""
    topic_author = User.objects.create_user(username="timing-author")
    replier = User.objects.create_user(username="timing-replier")

    root = Page.objects.get(id=1)
    index = root.add_child(
        instance=ForumIndex(title="ForumTiming", slug="forum-timing")
    )
    board = index.add_child(
        instance=ForumBoard(title="GeneralTiming", slug="general-timing")
    )
    topic = Topic.objects.create(
        board=board, title="TTiming", slug="t-timing", author=topic_author
    )
    opening = Post.objects.create(
        topic=topic, author=topic_author, is_opening_post=True
    )
    opening.save_revision().publish()
    # A stale in-memory `topic` here would clobber the last_post_at
    # _refresh_for_post just set, via topic.save_revision().publish()'s own
    # full-row save — see docs/LEARNINGS.md 2026-07-16 (Testing).
    topic.refresh_from_db()
    topic.save_revision().publish()

    with (
        patch("apps.forum_host.tasks.send_forum_push_batch.delay"),
        patch("apps.forum_host.tasks.send_forum_email_batch.delay"),
    ):
        reply = Post.objects.create(topic=topic, author=replier)
        with django_capture_on_commit_callbacks(execute=True):
            reply.save_revision().publish()

    topic.refresh_from_db()
    read = TopicRead.objects.get(user=replier, topic=topic)
    assert read.last_read_at >= topic.last_post_at


@pytest.mark.django_db
def test_reply_added_write_path_query_count_is_independent_of_subscriber_count(
    django_capture_on_commit_callbacks,
):
    """The DB write path (auto-subscribe the replier + one subscriber fetch +
    one bulk_create) must not scale with subscriber count N — that's the
    whole point of building recipients via a single query + a single
    bulk_create instead of looping N .save() calls (todo 253 slice 3,
    docs/rules/testing.md: pin fan-out writes with an exact query count).
    Compares 1 vs. 5 subscribers rather than a hardcoded literal — the
    invariant under test is "constant regardless of N", which a fixed number
    can't express as precisely."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    def _dispatch_reply(n_subscribers, slug):
        topic_author = User.objects.create_user(username=f"qc-author-{slug}")
        root = Page.objects.get(id=1)
        index = root.add_child(
            instance=ForumIndex(title=f"ForumQC{slug}", slug=f"forum-qc-{slug}")
        )
        board = index.add_child(
            instance=ForumBoard(title=f"GeneralQC{slug}", slug=f"general-qc-{slug}")
        )
        topic = Topic.objects.create(
            board=board, title="T", slug=f"t-{slug}", author=topic_author
        )
        for i in range(n_subscribers):
            sub = User.objects.create_user(username=f"qc-sub-{slug}-{i}")
            TopicSubscription.subscribe(sub, topic)
        replier = User.objects.create_user(username=f"qc-replier-{slug}")
        post = Post.objects.create(topic=topic, author=replier)

        with (
            patch("apps.forum_host.tasks.send_forum_push_batch.delay"),
            patch("apps.forum_host.tasks.send_forum_email_batch.delay"),
        ):
            from apps.forum_host.notifications import dispatch

            with CaptureQueriesContext(connection) as ctx:
                with django_capture_on_commit_callbacks(execute=True):
                    dispatch("reply_added", topic=topic, post=post)
        return len(ctx.captured_queries)

    few = _dispatch_reply(1, "few")
    many = _dispatch_reply(5, "many")

    assert few == many


@pytest.mark.django_db
def test_reply_added_does_not_notify_for_self_reply(django_capture_on_commit_callbacks):
    """An author replying to their own topic must not receive a push, email,
    or in-app notification for it — even though they ARE a subscriber (todo
    253 slice 3: exclusion is now enforced by filtering the recipient list,
    not by an early-return on topic_author-equals-post_author)."""
    author = User.objects.create_user(username="selfie")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum3", slug="forum3"))
    board = index.add_child(instance=ForumBoard(title="General3", slug="general3"))
    topic = Topic.objects.create(board=board, title="T3", slug="t3", author=author)
    TopicSubscription.subscribe(author, topic)

    with (
        patch("apps.forum_host.tasks.send_forum_push_batch.delay") as mock_push,
        patch("apps.forum_host.tasks.send_forum_email_batch.delay") as mock_email,
    ):
        from apps.forum_host.notifications import dispatch

        post = Post.objects.create(topic=topic, author=author)
        with django_capture_on_commit_callbacks(execute=True):
            dispatch("reply_added", topic=topic, post=post)

    mock_push.assert_not_called()
    mock_email.assert_not_called()
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
    TopicSubscription.subscribe(topic_author, topic)

    with (
        patch(
            "apps.forum_host.tasks.send_forum_push_batch.delay",
            side_effect=RuntimeError("broker unavailable"),
        ) as mock_delay,
        # The reply_added success path also enqueues an email (todo 253 slice
        # 2, H1) via the same on_commit mechanism; mock it so this push-only
        # test doesn't attempt a real broker publish.
        patch("apps.forum_host.tasks.send_forum_email_batch.delay"),
    ):
        from apps.forum_host.notifications import dispatch

        post = Post.objects.create(topic=topic, author=replier)
        with caplog.at_level("ERROR", logger="forum_host.notifications"):
            # Executing the captured on_commit callback is what actually calls
            # .delay() now (todo 253 slice 1) — that's where the swallow happens.
            with django_capture_on_commit_callbacks(execute=True):
                dispatch("reply_added", topic=topic, post=post)  # must not raise

    mock_delay.assert_called_once()
    # The batch enqueue logs a batch-specific message now (todo 268) — the
    # single-recipient "failed to enqueue push" wording is gone from this path.
    assert "failed to enqueue reply push batch" in caplog.text


@pytest.mark.django_db
def test_reply_added_persists_notification_row(django_capture_on_commit_callbacks):
    """reply_added must persist a Notification row for a topic subscriber
    (todo 253 slice 1, audit C2) — independent of whether the push succeeds."""
    topic_author = User.objects.create_user(username="topicowner9")
    replier = User.objects.create_user(username="replier9")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum9", slug="forum9"))
    board = index.add_child(instance=ForumBoard(title="General9", slug="general9"))
    topic = Topic.objects.create(
        board=board, title="T9", slug="t9", author=topic_author
    )
    TopicSubscription.subscribe(topic_author, topic)
    post = Post.objects.create(topic=topic, author=replier)

    with (
        patch("apps.forum_host.tasks.send_forum_push_batch.delay"),
        # The reply_added success path also enqueues an email (todo 253 slice
        # 2, H1) via the same on_commit mechanism; mock it so this
        # notification-row test doesn't attempt a real broker publish.
        patch("apps.forum_host.tasks.send_forum_email_batch.delay"),
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
    TopicSubscription.subscribe(topic_author, topic)
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
    TopicSubscription.subscribe(topic_author, topic)
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


# ---- mention notifications (todo 253 slice 4, H4) ----------------------------


@pytest.mark.django_db
def test_reply_mentioning_a_user_creates_mention_notification(
    django_capture_on_commit_callbacks,
):
    topic_author = User.objects.create_user(username="mention-author")
    mentioned = User.objects.create_user(username="mentionbob")
    replier = User.objects.create_user(username="mention-replier")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="ForumM1", slug="forum-m1"))
    board = index.add_child(instance=ForumBoard(title="GeneralM1", slug="general-m1"))
    topic = Topic.objects.create(
        board=board, title="TM1", slug="t-m1", author=topic_author
    )

    with (
        patch("apps.forum_host.tasks.send_forum_push_batch.delay") as mock_push,
        patch("apps.forum_host.tasks.send_forum_email_batch.delay") as mock_email,
    ):
        from apps.forum_host.notifications import dispatch

        post = Post.objects.create(
            topic=topic,
            author=replier,
            body=[{"type": "paragraph", "value": "<p>hi @mentionbob</p>"}],
        )
        with django_capture_on_commit_callbacks(execute=True):
            dispatch("reply_added", topic=topic, post=post)

    notification = Notification.objects.get(recipient=mentioned, post=post)
    assert notification.verb == NotificationVerb.MENTION

    # The mention push is now a batched enqueue (todo 268): args[1] is a
    # recipient LIST, so membership replaces the scalar-pk equality check.
    mention_pushes = [c for c in mock_push.call_args_list if mentioned.pk in c.args[1]]
    assert len(mention_pushes) == 1
    assert mention_pushes[0].args[0] == "mention"
    # No other subscribers exist in this fixture, and mentioned users get
    # bell + push only, never email, this slice — email must not fire at all.
    mock_email.assert_not_called()


@pytest.mark.django_db
def test_reply_mention_suppresses_duplicate_subscriber_notification(
    django_capture_on_commit_callbacks,
):
    """A user who is both a topic subscriber AND @mentioned in the same reply
    gets exactly ONE notification — the more-specific "mention", not a
    second "reply" for the same post (todo 253 slice 4 review, Trap 3). A
    SEPARATE, non-mentioned subscriber must still get the normal reply
    notification + email — proving suppression is targeted at the mentioned
    user, not that email/reply delivery is broken outright."""
    topic_author = User.objects.create_user(username="mention-sub-author")
    both = User.objects.create_user(username="mentionsubboth")
    plain_subscriber = User.objects.create_user(username="mention-sub-plain")
    replier = User.objects.create_user(username="mention-sub-replier")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="ForumM2", slug="forum-m2"))
    board = index.add_child(instance=ForumBoard(title="GeneralM2", slug="general-m2"))
    topic = Topic.objects.create(
        board=board, title="TM2", slug="t-m2", author=topic_author
    )
    TopicSubscription.subscribe(both, topic)
    TopicSubscription.subscribe(plain_subscriber, topic)

    with (
        patch("apps.forum_host.tasks.send_forum_push_batch.delay") as mock_push,
        patch("apps.forum_host.tasks.send_forum_email_batch.delay") as mock_email,
    ):
        from apps.forum_host.notifications import dispatch

        post = Post.objects.create(
            topic=topic,
            author=replier,
            body=[{"type": "paragraph", "value": "<p>@mentionsubboth check this</p>"}],
        )
        with django_capture_on_commit_callbacks(execute=True):
            dispatch("reply_added", topic=topic, post=post)

    rows = Notification.objects.filter(recipient=both, post=post)
    assert rows.count() == 1
    assert rows.get().verb == NotificationVerb.MENTION
    assert (
        Notification.objects.get(recipient=plain_subscriber, post=post).verb
        == NotificationVerb.REPLY
    )

    # args[1] is a batched recipient LIST now (todo 268) — `both` must appear
    # in exactly one enqueue and it must be the mention one.
    pushes_to_both = [c for c in mock_push.call_args_list if both.pk in c.args[1]]
    assert len(pushes_to_both) == 1
    assert pushes_to_both[0].args[0] == "mention"
    # `both` is suppressed into the mention-only path (no email); the plain
    # subscriber is untouched by suppression and still gets emailed. The reply
    # email is one batched enqueue, so union its recipient list(s).
    emailed = set()
    for c in mock_email.call_args_list:
        emailed.update(c.args[1])
    assert emailed == {plain_subscriber.pk}


@pytest.mark.django_db
def test_reply_mention_excludes_self_mention(django_capture_on_commit_callbacks):
    topic_author = User.objects.create_user(username="mentionselfauthor")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="ForumM3", slug="forum-m3"))
    board = index.add_child(instance=ForumBoard(title="GeneralM3", slug="general-m3"))
    topic = Topic.objects.create(
        board=board, title="TM3", slug="t-m3", author=topic_author
    )

    with (
        patch("apps.forum_host.tasks.send_forum_push_batch.delay"),
        patch("apps.forum_host.tasks.send_forum_email_batch.delay"),
    ):
        from apps.forum_host.notifications import dispatch

        post = Post.objects.create(
            topic=topic,
            author=topic_author,
            body=[
                {
                    "type": "paragraph",
                    "value": "<p>@mentionselfauthor note to self</p>",
                }
            ],
        )
        with django_capture_on_commit_callbacks(execute=True):
            dispatch("reply_added", topic=topic, post=post)

    assert not Notification.objects.filter(
        recipient=topic_author, post=post, verb=NotificationVerb.MENTION
    ).exists()


@pytest.mark.django_db
def test_reply_mention_on_restricted_board_does_not_notify(
    django_capture_on_commit_callbacks,
):
    topic_author = User.objects.create_user(username="mention-restricted-author")
    mentioned = User.objects.create_user(username="mentionrestrictedbob")
    replier = User.objects.create_user(username="mention-restricted-replier")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="ForumM4", slug="forum-m4"))
    board = index.add_child(instance=ForumBoard(title="GeneralM4", slug="general-m4"))
    PageViewRestriction.objects.create(page=board, restriction_type="login")
    topic = Topic.objects.create(
        board=board, title="TM4", slug="t-m4", author=topic_author
    )

    with (
        patch("apps.forum_host.tasks.send_forum_push_batch.delay") as mock_push,
        patch("apps.forum_host.tasks.send_forum_email_batch.delay"),
    ):
        from apps.forum_host.notifications import dispatch

        post = Post.objects.create(
            topic=topic,
            author=replier,
            body=[{"type": "paragraph", "value": "<p>@mentionrestrictedbob</p>"}],
        )
        with django_capture_on_commit_callbacks(execute=True):
            dispatch("reply_added", topic=topic, post=post)

    assert not Notification.objects.filter(
        recipient=mentioned, post=post, verb=NotificationVerb.MENTION
    ).exists()
    # args[1] is a batched recipient LIST now (todo 268) — the mentioned user
    # must not appear in ANY enqueued batch's recipient list. (A `!=` scalar
    # check would be trivially true against a list and silently gut this test.)
    assert all(mentioned.pk not in c.args[1] for c in mock_push.call_args_list)


@pytest.mark.django_db
def test_topic_created_mentioning_a_user_notifies_via_opening_post(
    django_capture_on_commit_callbacks,
):
    """reply_added only ever sees replies — a mention in a new topic's
    opening post needs topic_created's own handling (todo 253 slice 4)."""
    topic_author = User.objects.create_user(username="mention-topic-author")
    mentioned = User.objects.create_user(username="mentiontopicbob")

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="ForumM5", slug="forum-m5"))
    board = index.add_child(instance=ForumBoard(title="GeneralM5", slug="general-m5"))
    topic = Topic.objects.create(
        board=board, title="TM5", slug="t-m5", author=topic_author
    )

    with patch("apps.forum_host.tasks.send_forum_push_batch.delay") as mock_push:
        from apps.forum_host.notifications import dispatch

        opening = Post.objects.create(
            topic=topic,
            author=topic_author,
            is_opening_post=True,
            body=[{"type": "paragraph", "value": "<p>welcome @mentiontopicbob</p>"}],
        )
        with django_capture_on_commit_callbacks(execute=True):
            dispatch("topic_created", topic=topic, post=opening)

    notification = Notification.objects.get(recipient=mentioned, post=opening)
    assert notification.verb == NotificationVerb.MENTION
    # The mention push is a batched enqueue (todo 268): args[1] is a recipient
    # LIST, so membership replaces the scalar-pk equality check.
    mention_pushes = [c for c in mock_push.call_args_list if mentioned.pk in c.args[1]]
    assert len(mention_pushes) == 1
    assert mention_pushes[0].args[0] == "mention"


@pytest.mark.django_db
def test_mention_resolution_query_count_is_independent_of_mention_count(
    django_capture_on_commit_callbacks,
):
    """Mirrors test_reply_added_write_path_query_count_is_independent_of_subscriber_count
    for the mention path — 1 vs 5 mentions in the same post must cost the same
    number of queries (a single username__in fetch, not one query per name)."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    def _dispatch_mentions(n_mentions, slug):
        topic_author = User.objects.create_user(username=f"mqc-author-{slug}")
        root = Page.objects.get(id=1)
        index = root.add_child(
            instance=ForumIndex(title=f"ForumMQC{slug}", slug=f"forum-mqc-{slug}")
        )
        board = index.add_child(
            instance=ForumBoard(title=f"GeneralMQC{slug}", slug=f"general-mqc-{slug}")
        )
        topic = Topic.objects.create(
            board=board, title="T", slug=f"t-{slug}", author=topic_author
        )
        # No hyphens — the mention regex (@(\w+)) deliberately stops at
        # sentence punctuation, hyphens included, so a hyphenated username
        # here would truncate to the same partial match for every i and
        # collapse this test's N distinct mentions into 1 after dedup.
        clean_slug = slug.replace("-", "")
        mentioned_users = [
            User.objects.create_user(username=f"mqctarget{clean_slug}{i}")
            for i in range(n_mentions)
        ]
        replier = User.objects.create_user(username=f"mqc-replier-{slug}")
        text = " ".join(f"@{u.username}" for u in mentioned_users)
        post = Post.objects.create(
            topic=topic,
            author=replier,
            body=[{"type": "paragraph", "value": f"<p>{text}</p>"}],
        )

        with (
            patch("apps.forum_host.tasks.send_forum_push_batch.delay"),
            patch("apps.forum_host.tasks.send_forum_email_batch.delay"),
        ):
            from apps.forum_host.notifications import dispatch

            with CaptureQueriesContext(connection) as ctx:
                with django_capture_on_commit_callbacks(execute=True):
                    dispatch("reply_added", topic=topic, post=post)
        return len(ctx.captured_queries)

    few = _dispatch_mentions(1, "mqc-few")
    many = _dispatch_mentions(5, "mqc-many")
    assert few == many


# ---- batch fan-out invariant (todo 268, AC3) --------------------------------


@pytest.mark.django_db
def test_reply_added_enqueue_count_is_constant_regardless_of_subscriber_count(
    django_capture_on_commit_callbacks,
):
    """AC3 (todo 268): the reply fan-out must enqueue a CONSTANT number of
    Celery tasks — exactly one push-batch + one email-batch — no matter how
    many subscribers the topic has. This pins the whole todo: the pre-batch
    code enqueued one .delay() per recipient, so the enqueue count scaled
    linearly with N and blocked the reply request thread on N broker
    round-trips. Proven by dispatching an identical reply against N=1 and
    N=50 subscribers and asserting the enqueue counts are identical (and 1) —
    AND that the single recipient-list arg for N=50 carries all 50 pks, so the
    collapse is a genuine batch, not a silent drop of recipients."""

    def _dispatch_reply(n_subscribers, slug):
        topic_author = User.objects.create_user(username=f"const-author-{slug}")
        root = Page.objects.get(id=1)
        index = root.add_child(
            instance=ForumIndex(title=f"ForumConst{slug}", slug=f"forum-const-{slug}")
        )
        board = index.add_child(
            instance=ForumBoard(
                title=f"GeneralConst{slug}", slug=f"general-const-{slug}"
            )
        )
        topic = Topic.objects.create(
            board=board, title="TC", slug=f"t-const-{slug}", author=topic_author
        )
        # Exactly N recipients: subscribe only these fresh users. topic_author
        # is deliberately NOT subscribed, and the replier is auto-subscribed
        # but excluded from their own reply — so the recipient set is precisely
        # the N subscribers.
        subscriber_pks = set()
        for i in range(n_subscribers):
            sub = User.objects.create_user(username=f"const-sub-{slug}-{i}")
            TopicSubscription.subscribe(sub, topic)
            subscriber_pks.add(sub.pk)
        replier = User.objects.create_user(username=f"const-replier-{slug}")
        # A plain reply with NO @mentions — a mention would fire a SECOND
        # push-batch (NotificationVerb.MENTION) and break the "exactly one
        # push-batch" invariant this test pins.
        post = Post.objects.create(topic=topic, author=replier)

        with (
            patch(
                "apps.forum_host.tasks.send_forum_push_batch.delay"
            ) as mock_push_batch,
            patch(
                "apps.forum_host.tasks.send_forum_email_batch.delay"
            ) as mock_email_batch,
        ):
            from apps.forum_host.notifications import dispatch

            with django_capture_on_commit_callbacks(execute=True):
                dispatch("reply_added", topic=topic, post=post)

        return mock_push_batch, mock_email_batch, subscriber_pks

    push_1, email_1, _ = _dispatch_reply(1, "one")
    push_50, email_50, subscriber_pks_50 = _dispatch_reply(50, "fifty")

    # Enqueue count is CONSTANT across N — exactly one push-batch + one
    # email-batch for the reply fan-out, never scaling with subscriber count.
    assert push_1.call_count == 1
    assert email_1.call_count == 1
    assert push_50.call_count == 1
    assert email_50.call_count == 1
    # ...and identical between N=1 and N=50 (the invariant stated as equality,
    # not just as a fixed literal).
    assert push_1.call_count == push_50.call_count
    assert email_1.call_count == email_50.call_count

    # The batch did NOT drop recipients to hit a constant count: the single
    # recipient-list arg for N=50 must contain all 50 subscriber pks — batched,
    # not lost.
    assert set(push_50.call_args.args[1]) == subscriber_pks_50
    assert set(email_50.call_args.args[1]) == subscriber_pks_50
