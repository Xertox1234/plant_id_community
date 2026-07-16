"""Per-topic explicit read markers (todo 253 slice 5, audit H10).

Host-agnostic, alongside Topic/Notification/TopicSubscription. This is the
per-topic half of "unread" — the per-user fallback baseline for a topic
never explicitly opened lives on ``ForumProfile.read_watermark_at``. See
``wagtail_forum/api/views.py``'s ``_annotate_topic_unread`` for how the two
combine into the unread computation on the topic-list endpoint.
"""

from django.conf import settings
from django.db import models
from django.db.models import DateTimeField, Value
from django.db.models.functions import Greatest
from django.utils import timezone


class TopicRead(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_topic_reads",
    )
    topic = models.ForeignKey(
        "wagtail_forum.Topic",
        on_delete=models.CASCADE,
        related_name="+",
    )
    last_read_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "topic"], name="uniq_topic_read")
        ]
        # No extra single-column index (TopicSubscription adds one on just
        # `topic`, for its "who follows this topic" fan-out query) — every
        # read here, at both call sites, is always keyed by the full
        # (user, topic) pair, already covered by the unique constraint's
        # own index.

    def __str__(self):
        return f"TopicRead(user={self.user_id}, topic_id={self.topic_id})"

    @classmethod
    def mark_read(cls, user, topic_id, when=None):
        """Idempotently record that `user` has read topic `topic_id` as of `when`.

        Takes a raw pk (not a Topic instance) — its one caller
        (TopicDetailView.retrieve) already avoids re-fetching the topic for
        the neighboring view_count update, and this mirrors that same
        id-only economy.

        Monotonic under real concurrency, not just per-caller: a call with an
        earlier `when` than what is already stored never regresses it, even
        if two calls race (e.g. this method's two real callers — a
        detail-view visit stamped at on_commit time via timezone.now(), and
        a notifications.py signal-time write stamped from a reply's own
        post.first_published_at — landing out of chronological order). The
        update uses an atomic SQL `GREATEST(last_read_at, %s)` rather than a
        read-then-conditionally-write in Python: the latter has its own
        TOCTOU window (two concurrent callers can both read the same stale
        value, both decide to write, and whichever commits last wins with
        its own `when` even if that is the earlier of the two) — the atomic
        form serializes on the row's UPDATE lock instead, so the stored
        value is always the true max of every `when` ever passed in,
        regardless of interleaving.

        Deliberately has NO custom IntegrityError recovery (unlike this
        package's usual house convention in ForumProfile.for_user /
        TopicSubscription.subscribe, which keep one): empirically confirmed
        (docs/LEARNINGS.md, 2026-07-16) that in this Django version,
        get_or_create already retries its own internal `.get()` once after a
        failed `create()`, so a lost create-race is recovered silently
        inside get_or_create and never reaches here as an exception. The
        only way an IntegrityError escapes get_or_create is when that
        internal retry ALSO found nothing (e.g. topic_id's Topic was hard-
        deleted out from under a stale caller) — Django already re-raises
        the original, correctly-typed error for that case. A caller-added
        `except IntegrityError: .get()` here would only ever fire in that
        unrecoverable case, converting a clean IntegrityError into a
        confusing masked DoesNotExist instead of surfacing it as-is.
        """
        when = when or timezone.now()
        obj, created = cls.objects.get_or_create(
            user=user, topic_id=topic_id, defaults={"last_read_at": when}
        )
        if not created:
            cls.objects.filter(pk=obj.pk).update(
                last_read_at=Greatest(
                    "last_read_at", Value(when, output_field=DateTimeField())
                )
            )
            obj.refresh_from_db(fields=["last_read_at"])
        return obj
