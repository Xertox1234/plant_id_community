from django.dispatch import receiver
from wagtail_forum.signals import (
    moderation_decided,
    reply_added,
    solution_marked,
    topic_created,
)

from . import notifications


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
