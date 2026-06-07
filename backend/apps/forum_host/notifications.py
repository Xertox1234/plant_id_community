import logging

logger = logging.getLogger("forum_host.notifications")


def dispatch(event, **kwargs):
    """Send a forum event to FCM.

    Replace the log call with the project's FCM sender (e.g. enqueue a Celery
    task that calls the Firebase Admin SDK). Kept as a single seam so the
    delivery mechanism is swappable and unit-testable.
    """
    topic = kwargs.get("topic")
    logger.info("forum.%s topic=%s", event, getattr(topic, "id", None))
