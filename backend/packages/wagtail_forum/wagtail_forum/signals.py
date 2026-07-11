import logging
import threading

from django.db import transaction
from django.db.models import Count, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import Signal, receiver
from django.utils import timezone
from wagtail.signals import published, unpublished

logger = logging.getLogger("wagtail_forum")

# Public signals for hosts (e.g. push notifications). kwargs: post, topic.
# Fired only on FIRST publish — a moderator edit-republish must not re-notify.
# NOTE: fired synchronously inside the publish transaction; a receiver that
# hands off to async work should use transaction.on_commit itself.
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
            # Not inside an except block, so logger.exception() would log
            # "NoneType: None"; send_robust attaches __traceback__ to the
            # returned exception — hand it to exc_info explicitly.
            logger.error(
                "[ERROR] wagtail_forum signal receiver failed: %s",
                response,
                exc_info=response,
            )


def _is_first_publish(instance):
    # Wagtail stamps both timestamps with the same value on the first publish;
    # any later re-publish moves only last_published_at.
    return (
        instance.first_published_at is not None
        and instance.first_published_at == instance.last_published_at
    )


def _refresh_topic_counters(topic_id):
    """Recount a topic's denormalized fields in ONE UPDATE statement.

    The subqueries evaluate inside the UPDATE, so concurrent publishes cannot
    persist a stale read (the lost-update race a read-modify-write save() has).
    Activity (`last_post_at`) derives from first_published_at so an
    edit-republish of an old post does not corrupt topic ordering. It is
    Coalesce'd to created_at — the cursor pagination invariant is that a live
    topic NEVER has a null last_post_at (NULLS FIRST would float a gutted
    topic to the top and a None cursor position 500s).
    """
    from .models import Post, Topic

    live_posts = Post.objects.filter(
        topic=OuterRef("pk"), live=True, first_published_at__isnull=False
    )
    latest = live_posts.order_by("-first_published_at")
    Topic.objects.filter(pk=topic_id).update(
        reply_count=Coalesce(
            Subquery(
                live_posts.filter(is_opening_post=False)
                .values("topic")
                .annotate(c=Count("pk"))
                .values("c")
            ),
            Value(0),
        ),
        last_post_at=Coalesce(
            Subquery(latest.values("first_published_at")[:1]), "created_at"
        ),
        last_post_author_id=Subquery(latest.values("author_id")[:1]),
        # .update() bypasses auto_now; /sync/ depends on updated_at moving.
        updated_at=timezone.now(),
    )


def _refresh_board_counters(board_id):
    from .models import ForumBoard, Post, Topic

    ForumBoard.objects.filter(pk=board_id).update(
        post_count=Coalesce(
            Subquery(
                # topic__live too: posts of an unpublished (taken-down) topic
                # are API-invisible and must not count.
                Post.objects.filter(
                    topic__board=OuterRef("pk"), live=True, topic__live=True
                )
                .values("topic__board")
                .annotate(c=Count("pk"))
                .values("c")
            ),
            Value(0),
        ),
        topic_count=Coalesce(
            Subquery(
                Topic.objects.filter(board=OuterRef("pk"), live=True)
                .values("board")
                .annotate(c=Count("pk"))
                .values("c")
            ),
            Value(0),
        ),
    )


def _earned_level(post_count, thresholds):
    earned = 0
    # int() the keys: a host may configure this from JSON/env where dict keys are
    # strings, which would otherwise break the comparison against int levels.
    for level, min_posts in sorted((int(k), v) for k, v in thresholds.items()):
        if post_count >= min_posts:
            earned = max(earned, level)
    return earned


def _refresh_profile(author_id):
    """Recount the author's visible posts and re-derive trust — BOTH directions.

    Demotion matters: autopublish trust earned from posts later removed as spam
    must be revoked, or the moderation gate is permanently defeated. A level the
    old post_count could not have earned was granted manually (admin) — those
    are only ever promoted, never clawed back. (Stored post_count is maintained
    by these same handlers, so it reflects the pre-change state here.)
    """
    from .conf import get_setting
    from .models import ForumProfile, Post

    if author_id is None:
        return
    profile, _ = ForumProfile.objects.get_or_create(user_id=author_id)
    thresholds = get_setting("TRUST_THRESHOLDS")
    with transaction.atomic():
        locked = ForumProfile.objects.select_for_update().get(pk=profile.pk)
        old_earned = _earned_level(locked.post_count, thresholds)
        # topic__live too: posts in a taken-down topic must not keep funding
        # the author's autopublish trust.
        new_count = Post.objects.filter(
            author_id=author_id, live=True, topic__live=True
        ).count()
        new_earned = _earned_level(new_count, thresholds)
        if locked.trust_level <= old_earned:
            locked.trust_level = new_earned
        else:
            locked.trust_level = max(locked.trust_level, new_earned)
        locked.post_count = new_count
        locked.save(update_fields=["post_count", "trust_level"])


def _refresh_for_post(post):
    from .models import Topic

    _refresh_topic_counters(post.topic_id)
    board_id = (
        Topic.objects.filter(pk=post.topic_id)
        .values_list("board_id", flat=True)
        .first()
    )
    if board_id is not None:
        _refresh_board_counters(board_id)
    _refresh_profile(post.author_id)


def _refresh_topic_authors(topic_id):
    """Re-derive trust/post_count for every author with live posts in a topic.

    Used when the TOPIC's own liveness flips (publish/unpublish/delete): the
    posts keep live=True but their visibility — and therefore the trust they
    fund — changes. Bounded by topic size; topic-level moderation is rare.
    """
    from .models import Post

    author_ids = (
        Post.objects.filter(topic_id=topic_id, live=True, author_id__isnull=False)
        .values_list("author_id", flat=True)
        .distinct()
    )
    for author_id in author_ids:
        _refresh_profile(author_id)


@receiver(published)
def update_counters_on_publish(sender, instance, **kwargs):
    from .models import Post, Topic

    if isinstance(instance, Topic):
        # The API flow publishes the topic AFTER its opening post, so the post's
        # recount ran while the topic was still a draft — recount here too or
        # board.topic_count permanently undercounts (audit H2). Author trust is
        # also visibility-dependent (topic__live), so re-derive it.
        _refresh_board_counters(instance.board_id)
        _refresh_topic_authors(instance.pk)
        if _is_first_publish(instance):
            # Fired from the TOPIC publish (not the opening post's) so the topic
            # is already live when a host deep-links to it. `post` is None for
            # admin-created topics that have no opening post yet.
            opening = instance.posts.filter(is_opening_post=True).first()
            notify(topic_created, sender=Topic, post=opening, topic=instance)
        return
    if not isinstance(instance, Post):
        return
    post = instance
    if _is_first_publish(post) and not post.is_opening_post:
        notify(reply_added, sender=Post, post=post, topic=post.topic)
    _refresh_for_post(post)


@receiver(unpublished)
def update_counters_on_unpublish(sender, instance, **kwargs):
    from .models import Post, Topic

    if isinstance(instance, Topic):
        _refresh_board_counters(instance.board_id)
        _refresh_topic_authors(instance.pk)
    elif isinstance(instance, Post):
        _refresh_for_post(instance)


# Topic pks currently being deleted, with the author ids to reconcile after the
# cascade. Lets the per-Post delete receiver skip redundant topic/board/profile
# recounts while the parent topic's cascade is in flight (a 200-reply topic
# would otherwise recount the board 200 times). Thread-local: deletes on other
# threads must not see this thread's markers.
_deleting_topics = threading.local()


def _deleting_map():
    if not hasattr(_deleting_topics, "map"):
        _deleting_topics.map = {}
    return _deleting_topics.map


@receiver(pre_delete, sender="wagtail_forum.Topic")
def mark_topic_deleting(sender, instance, **kwargs):
    from .models import Post

    author_ids = set(
        Post.objects.filter(
            topic_id=instance.pk, live=True, author_id__isnull=False
        ).values_list("author_id", flat=True)
    )
    _deleting_map()[instance.pk] = author_ids


@receiver(post_delete, sender="wagtail_forum.Topic")
def update_counters_on_topic_delete(sender, instance, **kwargs):
    author_ids = _deleting_map().pop(instance.pk, set())
    _refresh_board_counters(instance.board_id)
    for author_id in author_ids:
        _refresh_profile(author_id)
    # Record a tombstone so delta-sync clients can evict the deleted topic
    # from their local cache without requiring a full resync (Issue 6).
    from .models.tombstones import TopicDeletedLog

    TopicDeletedLog.objects.create(topic_id=instance.pk, board_id=instance.board_id)


@receiver(post_delete, sender="wagtail_forum.Post")
def update_counters_on_post_delete(sender, instance, **kwargs):
    # Draft deletions never contributed to any counter. When the parent topic
    # is mid-cascade, its own delete receiver reconciles board + profiles once.
    if not instance.live or instance.topic_id in _deleting_map():
        return
    _refresh_for_post(instance)
