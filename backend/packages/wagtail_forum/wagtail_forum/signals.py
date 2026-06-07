import logging

from django.dispatch import Signal, receiver
from django.utils import timezone
from wagtail.signals import published

logger = logging.getLogger("wagtail_forum")

# Public signals for hosts (e.g. push notifications). kwargs: post, topic.
topic_created = Signal()
reply_added = Signal()
moderation_decided = Signal()


def notify(signal, **kwargs):
    """Fire a host-facing signal robustly.

    Hosts (e.g. push-notification receivers) are third-party code; a receiver
    raising must not abort the publish or corrupt our denormalized counters, so
    we use send_robust and log any receiver exception instead of propagating it.
    """
    for _receiver, response in signal.send_robust(**kwargs):
        if isinstance(response, Exception):
            logger.exception("wagtail_forum signal receiver failed: %s", response)


@receiver(published)
def update_counters_on_publish(sender, instance, **kwargs):
    from .models import ForumProfile, Post, Topic

    if not isinstance(instance, Post):
        return
    post = instance
    topic = post.topic

    if post.is_opening_post:
        notify(topic_created, sender=Post, post=post, topic=topic)
    else:
        notify(reply_added, sender=Post, post=post, topic=topic)

    topic.reply_count = topic.posts.filter(is_opening_post=False, live=True).count()
    # Wagtail stamps last_published_at on the instance just before sending the
    # published signal; use it (not wall-clock) so moderation-delayed / scheduled
    # publishes get the correct activity time.
    topic.last_post_at = post.last_published_at or timezone.now()
    topic.last_post_author = post.author
    topic.save(
        update_fields=["reply_count", "last_post_at", "last_post_author", "updated_at"]
    )

    board = topic.board
    board.post_count = Post.objects.filter(topic__board=board, live=True).count()
    board.topic_count = Topic.objects.filter(board=board, live=True).count()
    board.save(update_fields=["post_count", "topic_count"])

    if post.author_id:
        profile = ForumProfile.for_user(post.author)
        profile.post_count = Post.objects.filter(author=post.author, live=True).count()
        _maybe_promote(profile)
        profile.save(update_fields=["post_count", "trust_level"])


def _maybe_promote(profile):
    from .conf import get_setting

    thresholds = get_setting("TRUST_THRESHOLDS")
    new_level = profile.trust_level
    # int() the keys: a host may configure this from JSON/env where dict keys are
    # strings, which would otherwise break the max()/sort against int levels.
    for level, min_posts in sorted((int(k), v) for k, v in thresholds.items()):
        if profile.post_count >= min_posts:
            new_level = max(new_level, level)
    profile.trust_level = new_level
