import logging

logger = logging.getLogger("forum_host.notifications")


def dispatch(event, **kwargs):
    """Route a forum signal event to FCM via a background Celery task.

    Importing the task here (inside the function) keeps the module importable
    even before the Celery app is ready (e.g. during migrations).

    Supported events
    ----------------
    reply_added
        Notifies the topic's original author that someone replied to their
        thread.  kwargs: topic (Topic), post (Post).

    moderation_decided
        Notifies the post's author of their content's moderation outcome.
        kwargs: obj (Post|Topic), status ("published"|"pending").

    topic_created
        No push for now — there is no board-subscriber model yet.
        Logged only so the seam is visible when that model is added.
    """
    from .tasks import send_forum_push

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
        send_forum_push.delay(
            event,
            topic_author.pk,
            {
                "topic_id": str(topic_id),
                "topic_title": topic.title if topic else "",
                "post_id": str(getattr(post, "id", "")),
            },
        )

    elif event == "moderation_decided":
        obj = kwargs.get("obj")
        status = kwargs.get("status", "")
        author = getattr(obj, "author", None)
        if author is None:
            return
        send_forum_push.delay(
            event,
            author.pk,
            {
                "topic_id": str(topic_id),
                "status": status,
                "obj_id": str(getattr(obj, "id", "")),
            },
        )

    elif event == "topic_created":
        # No subscriber model yet — log and return.
        logger.info("forum.topic_created topic=%s (no push subscribers yet)", topic_id)

    else:
        logger.warning("forum_host.notifications: unknown event %r", event)
