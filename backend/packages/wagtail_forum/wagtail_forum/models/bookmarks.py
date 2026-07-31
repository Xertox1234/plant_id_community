"""Save-for-later bookmarks on a topic (todo 283, audit M2).

Deliberately a SEPARATE model from ``TopicSubscription`` (models/
subscriptions.py) even though the two rows have an identical shape. They carry
different intent and must stay independently toggleable:

- ``TopicSubscription`` is *notification* intent — "tell me when this moves."
  It is written implicitly (replying to a topic subscribes you) and read by the
  fan-out call site to build a recipient list.
- ``TopicBookmark`` is *save-for-later* intent — "I want to find this again."
  It is only ever written by an explicit user action and is read by nothing but
  the member's own saved list.

Collapsing them would mean a member cannot save a noisy thread without also
signing up for every reply, nor mute a thread they still want to keep.
"""

from django.conf import settings
from django.db import models


class TopicBookmark(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        # Same reverse-accessor minefield documented on TopicSubscription:
        # "forum_subscriptions" is claimed by the legacy apps.core model and
        # "forum_notifications" by the User pref / Notification.recipient.
        # "forum_topic_bookmarks" follows the forum_topic_* convention already
        # set by forum_topic_subscriptions / forum_topic_reads and is unclaimed.
        related_name="forum_topic_bookmarks",
    )
    topic = models.ForeignKey(
        "wagtail_forum.Topic",
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "topic"], name="uniq_topic_bookmark"
            )
        ]
        indexes = [
            # The saved list reads "this user's bookmarks, newest first" — the
            # composite covers both the filter and the ordering in one scan.
            # NOTE the asymmetry with TopicSubscription, which indexes `topic`
            # instead: its hot read is fan-out ("who follows this topic"),
            # while nothing here ever asks "who bookmarked this topic."
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"TopicBookmark(user={self.user_id}, topic={self.topic_id})"

    @classmethod
    def add(cls, user, topic):
        """Idempotently bookmark `topic` for `user`.

        A bare `get_or_create` is the whole implementation, and that is
        deliberate. Two concurrent first-touch requests (a double-tapped
        toggle, a retried request) can both miss the SELECT and race to
        INSERT, with the loser hitting `uniq_topic_bookmark` — but Django
        already handles exactly that: `QuerySet.get_or_create` wraps its
        INSERT in `transaction.atomic()` (so the IntegrityError rolls back
        only that savepoint and leaves an ambient transaction usable) and then
        re-runs `self.get(**kwargs)`, re-raising only if that retry ALSO finds
        nothing. Verified against the installed Django 6.0.7 source.

        NOTE this differs from its neighbour `TopicSubscription.subscribe`,
        which wraps the call in `except IntegrityError: ... get()`. That
        wrapper is unreachable for the race it names and actively harmful for
        any other: an IntegrityError from a *different* constraint (a stale FK,
        say) surfaces as a confusing `DoesNotExist` instead of the real error.
        Not replicated here; the neighbour is left alone as out of scope.
        """
        bookmark, _ = cls.objects.get_or_create(user=user, topic=topic)
        return bookmark

    @classmethod
    def remove(cls, user, topic):
        cls.objects.filter(user=user, topic=topic).delete()
