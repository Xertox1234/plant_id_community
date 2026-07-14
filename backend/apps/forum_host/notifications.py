import logging

logger = logging.getLogger("forum_host.notifications")


def dispatch(event, **kwargs):
    """Route a forum signal event to FCM/email via background Celery tasks.

    Importing the task here (inside the function) keeps the module importable
    even before the Celery app is ready (e.g. during migrations).

    Supported events
    ----------------
    reply_added
        Notifies the topic's original author that someone replied to their
        thread.  kwargs: topic (Topic), post (Post). Persists a Notification
        row (todo 253 slice 1) synchronously in the ambient (publish)
        transaction — it rolls back cleanly if the publish does — and defers
        the push AND email enqueue to transaction.on_commit so neither can
        ever fire for a publish that later rolls back (fixes the
        pre-slice-253 bug where .delay() ran synchronously inside the open
        publish transaction). The email (todo 253 slice 2, H1) reuses
        NotificationService.send_forum_reply_notification, gated by the
        recipient's forum_notifications preference inside that service.

    moderation_decided
        Notifies the post's author of their content's moderation outcome.
        kwargs: obj (Post|Topic), status ("published"|"pending").

    topic_created
        No push for now — there is no board-subscriber model yet.
        Logged only so the seam is visible when that model is added.
    """
    from django.db import transaction

    from .tasks import send_forum_email, send_forum_push

    topic = kwargs.get("topic")
    topic_id = getattr(topic, "id", None)

    if event == "reply_added":
        post = kwargs.get("post")
        # Notify the topic author when someone else replies.
        topic_author = getattr(topic, "author", None)
        post_author = getattr(post, "author", None)
        if topic_author is None:
            return
        # Don't ping the author for their own replies.
        if post_author is not None and post_author.pk == topic_author.pk:
            return

        from wagtail_forum.models import NotificationVerb
        from wagtail_forum.notifications import create_notifications

        payload = {
            "topic_id": str(topic_id),
            "topic_title": topic.title if topic else "",
            "post_id": str(getattr(post, "id", "")),
        }

        def _enqueue_push():
            try:
                send_forum_push.delay(event, topic_author.pk, payload)
            except Exception:
                logger.exception(
                    "[CELERY] forum_host: failed to enqueue push for event=%s user=%s",
                    event,
                    topic_author.pk,
                )

        def _enqueue_email():
            try:
                send_forum_email.delay(event, topic_author.pk, payload)
            except Exception:
                logger.exception(
                    "[CELERY] forum_host: failed to enqueue email for event=%s user=%s",
                    event,
                    topic_author.pk,
                )

        try:
            # A nested atomic() scopes any DB failure to a savepoint: this
            # dispatch runs inside the ambient Wagtail publish transaction, and
            # an uncaught error here would poison that whole transaction (the
            # except must sit OUTSIDE the atomic() block, not inside it — see
            # docs/rules/forum.md) — the receiver chain's send_robust() only
            # swallows the PYTHON exception, not Postgres's aborted-transaction
            # state, so the very next write in the same transaction
            # (_refresh_for_post) would otherwise raise too.
            with transaction.atomic():
                create_notifications(
                    recipients=[topic_author],
                    verb=NotificationVerb.REPLY,
                    actor=post_author,
                    topic=topic,
                    post=post,
                )
            # Only registered once the write above actually succeeds — a
            # notification-write failure must not still deliver a push/email,
            # or the user gets a delivery with no corresponding in-app
            # notification.
            transaction.on_commit(_enqueue_push)
            transaction.on_commit(_enqueue_email)
        except Exception:
            logger.exception(
                "[ERROR] forum_host: failed to persist notification for event=%s user=%s",
                event,
                topic_author.pk,
            )

    elif event == "moderation_decided":
        obj = kwargs.get("obj")
        status = kwargs.get("status", "")
        author = getattr(obj, "author", None)
        if author is None:
            return
        # The moderation_decided signal never passes a `topic` kwarg — derive
        # topic_id from obj instead (Post has .topic_id, Topic has .id itself).
        from wagtail_forum.models import Post as ForumPost

        if isinstance(obj, ForumPost):
            resolved_topic_id = obj.topic_id
        else:
            resolved_topic_id = getattr(obj, "id", None)
        try:
            send_forum_push.delay(
                event,
                author.pk,
                {
                    "topic_id": (
                        str(resolved_topic_id) if resolved_topic_id is not None else ""
                    ),
                    "status": status,
                    "obj_id": str(getattr(obj, "id", "")),
                },
            )
        except Exception:
            logger.exception(
                "[CELERY] forum_host: failed to enqueue push for event=%s user=%s",
                event,
                author.pk,
            )

    elif event == "topic_created":
        # No subscriber model yet — log and return.
        logger.info("forum.topic_created topic=%s (no push subscribers yet)", topic_id)

    else:
        logger.warning("forum_host.notifications: unknown event %r", event)
