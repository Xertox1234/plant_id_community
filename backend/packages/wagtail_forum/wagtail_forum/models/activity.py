"""Per-user daily activity tracking, for the "day streak" stat (todo 300).

Host-agnostic, alongside TopicRead/TopicBookmark. One row per (user, date)
the user published a live post or topic on — see signals.py's
`update_counters_on_publish` for the write side. `date`, not `datetime`:
the streak is a calendar-day concept, and Django's `timezone.now()` is used
consistently at both the write site (signals.py) and the read site
(`streak_for_user` below) — this project runs with `TIME_ZONE = "UTC"`
(settings.py), so "today" is UTC's today throughout, not the poster's local
day. A post published near local midnight in a non-UTC timezone can land on
the "wrong" UTC day; accepted as the same platform-wide convention every
other "today"-based forum feature already uses (VIEW_COUNT_DEDUP_SECONDS,
UNREAD_LAUNCH_AT, presence's online window).
"""

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class ForumActivityDate(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        # Mirrors TopicBookmark/TopicRead's related_name discipline — must not
        # clash with forum_subscriptions/forum_notifications/
        # forum_topic_subscriptions/forum_topic_reads/forum_topic_bookmarks,
        # all already claimed on User.
        related_name="forum_activity_dates",
    )
    date = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"], name="uniq_forum_activity_date"
            )
        ]
        # No extra single-column index — every real read is keyed by `user`
        # alone (streak_for_user's ORDER BY date DESC scan), already covered
        # by the unique constraint's own composite (user, date) index (user
        # is the leading column, so it serves a user-only WHERE + ORDER BY
        # too). Same reasoning as TopicRead/TopicBookmark.

    def __str__(self):
        return f"ForumActivityDate(user={self.user_id}, date={self.date})"

    @classmethod
    def record(cls, user_id, when=None):
        """Idempotently record that `user_id` was active on `when`'s date.

        `when` is a datetime (defaults to `timezone.now()`); only its date
        component is stored.

        No `except IntegrityError` retry wrapper — get_or_create already
        recovers its own lost create-race internally in this Django version
        (see TopicBookmark.bookmark / TopicRead.mark_read for the same
        established shape and the full reasoning,
        docs/patterns/architecture/services.md).
        """
        day = (when or timezone.now()).date()
        cls.objects.get_or_create(user_id=user_id, date=day)

    @classmethod
    def streak_for_user(cls, user_id):
        """Consecutive days ending today or yesterday — 0 if the streak is broken.

        "Ending yesterday" (not just "ending today") keeps a streak alive
        through the current day until it actually lapses: a user who posted
        every day through yesterday but hasn't yet today still has a live
        streak, not a reset-to-zero, until a full day passes with no
        activity.

        Bounded (STREAK_LOOKBACK_ROWS, conf.py) rather than an unbounded
        scan — one row per active day, so this is already tiny for any real
        user, and the cap is pure defense against a pathological case, not
        a realistic limit.
        """
        from ..conf import get_setting

        today = timezone.now().date()
        dates = set(
            cls.objects.filter(user_id=user_id, date__lte=today)
            .order_by("-date")
            .values_list("date", flat=True)[: get_setting("STREAK_LOOKBACK_ROWS")]
        )
        if not dates:
            return 0
        anchor = today if today in dates else today - timedelta(days=1)
        if anchor not in dates:
            return 0
        streak = 0
        day = anchor
        while day in dates:
            streak += 1
            day -= timedelta(days=1)
        return streak
