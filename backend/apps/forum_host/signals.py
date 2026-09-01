import logging

from apps.blog.models import BlogPostPage
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from wagtail.signals import page_published, page_unpublished
from wagtail_forum.signals import (
    moderation_decided,
    reply_added,
    solution_marked,
    topic_created,
)

from . import notifications
from .tasks import sync_blog_page_chunks

logger = logging.getLogger(__name__)


@receiver(topic_created)
def _on_topic_created(sender, topic, post, **kwargs):
    notifications.dispatch("topic_created", topic=topic, post=post)


@receiver(reply_added)
def _on_reply_added(sender, topic, post, **kwargs):
    notifications.dispatch("reply_added", topic=topic, post=post)


@receiver(moderation_decided)
def _on_moderation_decided(sender, **kwargs):
    notifications.dispatch("moderation_decided", **kwargs)


@receiver(solution_marked)
def _on_solution_marked(sender, topic, post, actor, **kwargs):
    # Named "answer_accepted" on the host side, matching the copy-table key —
    # the package signal is named for the ACTION, the host event for what the
    # recipient is told.
    notifications.dispatch("answer_accepted", topic=topic, post=post, actor=actor)


# --------------------------------------------------------------------------- #
# BlogChunks index maintenance (todo 289 / M13). Host-side, not in            #
# apps/blog/signals.py: the blog app should not know about forum RAG.         #
# --------------------------------------------------------------------------- #


def _enqueue_blog_chunk_sync(page, event: str) -> None:
    """Enqueue the per-page sync, never inline, and only AFTER COMMIT.

    Inline is out because the blog's publish handlers run under a <5ms budget.
    ``transaction.on_commit`` (the ``notifications.py`` convention) is required
    because Wagtail's admin publish and Django's ``Model.delete()`` cascade both
    fire these signals inside ``transaction.atomic()``: a task enqueued straight
    from the receiver can run on the worker before the commit and see the
    pre-publish page (a first publish would purge-only and never index) or
    re-embed a page that is mid-delete (orphan rows nothing purges again).
    Outside a transaction ``on_commit`` runs the callback immediately.

    The try/except lives INSIDE the callback: an exception there would surface
    after the commit, from whatever view triggered it, and a publish must never
    fail because the broker is down (the apps/blog/signals.py posture).
    """
    from .vector_indexes import rag_enabled

    if not isinstance(page, BlogPostPage) or not rag_enabled():
        return
    page_id = page.pk

    def enqueue():
        try:
            sync_blog_page_chunks.delay(page_id)
        except Exception:
            logger.exception(
                "[CELERY] failed to enqueue BlogChunks sync for page %s on %s",
                page_id,
                event,
            )

    transaction.on_commit(enqueue)


@receiver(page_published)
def _on_page_published(sender, instance, **kwargs):
    # page_published fires for EVERY Wagtail page type; the helper guards.
    _enqueue_blog_chunk_sync(instance, "publish")


@receiver(page_unpublished)
def _on_page_unpublished(sender, instance, **kwargs):
    _enqueue_blog_chunk_sync(instance, "unpublish")


@receiver(post_delete, sender=BlogPostPage)
def _on_blog_page_deleted(sender, instance, **kwargs):
    _enqueue_blog_chunk_sync(instance, "delete")
