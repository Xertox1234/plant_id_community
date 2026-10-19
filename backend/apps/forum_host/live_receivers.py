"""Turn forum writes into live events (forum live replies, slice 2).

The package stays Channels-free: these receivers listen to the package's plain
Django signals and Wagtail's generic ones, and ``live.broadcast`` waits for
commit. One receiver per source, one event each:

| Source | Event |
|---|---|
| ``reply_added`` (a reply's first publish) | ``post.created`` |
| ``published`` Post, not its first publish (edit, approved edit) | ``post.updated`` |
| ``unpublished`` Post (author delete, moderator, report auto-hide) | ``post.removed`` |
| ``post_delete`` live Post, unless its topic is being deleted | ``post.removed`` |
| ``published`` Topic, not its first publish (title, closed, restore) | ``topic.updated`` |
| ``unpublished`` / ``post_delete`` Topic | ``topic.removed`` |
| ``solution_marked`` / ``solution_unmarked`` | ``topic.updated`` |
| ``post_save`` Topic with ``"locked"`` in ``update_fields`` | ``topic.updated`` |

A topic's FIRST publish sends nothing: nobody can have it open yet.

The ``post_save`` hook is deliberately narrow. Wagtail's lock and unlock views
do ``save(update_fields=["locked", "locked_by", "locked_at"])`` and send no
signal of their own. Counters and view counts use ``.update()``, which sends
no ``post_save``, so a raw ``post_save`` hook would not flood either, but any
other Topic save (the solution fields, a full admin save) must not send twice.

Deliberately NOT visibility- or block-filtered: an event carries only ids and
goes only to sockets the consumer admitted after the same visibility check as
the REST topic read; every reader then fetches through REST as themselves.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from wagtail.signals import published, unpublished
from wagtail_forum.models import Post, Topic
from wagtail_forum.signals import (
    is_first_publish,
    is_topic_deleting,
    reply_added,
    solution_marked,
    solution_unmarked,
)

from .live import broadcast


@receiver(reply_added, dispatch_uid="forum_live.reply_added")
def _live_reply_added(sender, topic, post, **kwargs):
    broadcast("post.created", topic.pk, post.pk)


@receiver(published, dispatch_uid="forum_live.published")
def _live_published(sender, instance, **kwargs):
    if is_first_publish(instance):
        return
    if isinstance(instance, Post):
        broadcast("post.updated", instance.topic_id, instance.pk)
    elif isinstance(instance, Topic):
        broadcast("topic.updated", instance.pk)


@receiver(unpublished, dispatch_uid="forum_live.unpublished")
def _live_unpublished(sender, instance, **kwargs):
    if isinstance(instance, Post):
        broadcast("post.removed", instance.topic_id, instance.pk)
    elif isinstance(instance, Topic):
        broadcast("topic.removed", instance.pk)


@receiver(post_delete, sender=Post, dispatch_uid="forum_live.post_deleted")
def _live_post_deleted(sender, instance, **kwargs):
    # A draft was never on anyone's screen; a whole-topic delete sends one
    # topic.removed instead of one post.removed per reply.
    if not instance.live or is_topic_deleting(instance.topic_id):
        return
    broadcast("post.removed", instance.topic_id, instance.pk)


@receiver(post_delete, sender=Topic, dispatch_uid="forum_live.topic_deleted")
def _live_topic_deleted(sender, instance, **kwargs):
    broadcast("topic.removed", instance.pk)


@receiver(solution_marked, dispatch_uid="forum_live.solution_marked")
def _live_solution_marked(sender, topic, **kwargs):
    broadcast("topic.updated", topic.pk)


@receiver(solution_unmarked, dispatch_uid="forum_live.solution_unmarked")
def _live_solution_unmarked(sender, topic_id, **kwargs):
    broadcast("topic.updated", topic_id)


@receiver(post_save, sender=Topic, dispatch_uid="forum_live.topic_locked")
def _live_topic_lock_changed(sender, instance, update_fields=None, **kwargs):
    if update_fields and "locked" in update_fields:
        broadcast("topic.updated", instance.pk)
