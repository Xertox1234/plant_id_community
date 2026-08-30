from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from wagtail.actions.unpublish import UnpublishAction


class Report(models.Model):
    SPAM = "spam"
    ABUSE = "abuse"
    OFF_TOPIC = "off_topic"
    OTHER = "other"
    REASON_CHOICES = [
        (SPAM, _("Spam")),
        (ABUSE, _("Abuse")),
        (OFF_TOPIC, _("Off topic")),
        (OTHER, _("Other")),
    ]

    OPEN = "open"
    AUTO_HIDDEN = "auto_hidden"
    ACTIONED = "actioned"
    DISMISSED = "dismissed"
    STATUS_CHOICES = [
        (OPEN, _("Open")),
        (AUTO_HIDDEN, _("Auto-hidden")),
        (ACTIONED, _("Actioned")),
        (DISMISSED, _("Dismissed")),
    ]

    # Exactly one of post/message is set (forum_report_exactly_one_target
    # below) — a report targets either a public Post or a private Message
    # (todo 319/M10), never both. Both nullable so the SAME model/flow serves
    # both surfaces, per that todo's Recommended Action ("reuse the existing
    # Report model rather than a parallel one").
    post = models.ForeignKey(
        "wagtail_forum.Post",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="reports",
    )
    message = models.ForeignKey(
        "wagtail_forum.Message",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="reports",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wagtail_forum_reports",
    )
    reason = models.CharField(max_length=16, choices=REASON_CHOICES)
    detail = models.CharField(max_length=280, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Conditioned (not the original bare 2-field constraint) now that
            # post is nullable — a NULL post must never collide with another
            # NULL-post row on this constraint. Same shape mirrored for message.
            models.UniqueConstraint(
                fields=["post", "reporter"],
                condition=Q(post__isnull=False),
                name="uniq_forum_report_per_user_post",
            ),
            models.UniqueConstraint(
                fields=["message", "reporter"],
                condition=Q(message__isnull=False),
                name="uniq_forum_report_per_user_message",
            ),
            models.CheckConstraint(
                condition=(
                    Q(post__isnull=False, message__isnull=True)
                    | Q(post__isnull=True, message__isnull=False)
                ),
                name="forum_report_exactly_one_target",
            ),
        ]

    def __str__(self):
        if self.post_id is not None:
            return f"{self.reason} report on post {self.post_id}"
        return f"{self.reason} report on message {self.message_id}"

    @property
    def message_summary(self):
        """Triage column for the CMS admin `ReportViewSet.list_display`
        (todo 319/M10) — blank for a post report (the existing `post` column
        already covers those unchanged); for a message report, sender +
        a body excerpt. `Message.__str__` alone ("message 5 in conversation
        3") gives a moderator nothing to decide on without opening a shell,
        and a `list_display` entry needs a small `str`, not a raw model
        instance — this is deliberately not `self.message` itself."""
        if self.message_id is None:
            return ""
        body = self.message.body
        excerpt = body if len(body) <= 60 else body[:57] + "..."
        return f"{self.message.sender}: {excerpt}"

    @classmethod
    def file(cls, post, reporter, reason, detail=""):
        """Create a report, bump the author's cumulative flag count, and
        auto-hide the post if open reports on it cross the threshold.

        Returns the created Report, or ``None`` if ``reporter`` already
        reported ``post`` — the unique constraint is the source of truth for
        duplicate detection; a concurrent duplicate loses the race and is
        treated identically to a pre-existing one (idempotent, never a 500).
        """
        from ..conf import get_setting
        from .posts import Post
        from .profiles import ForumProfile

        try:
            # create() and the flags_received bump share one savepoint: either
            # both land or neither does. Splitting them left a gap where a
            # crash between the two commits the report but drops the credit,
            # and a retry would then no-op on the unique constraint and never
            # get a second chance to apply it (kimi-review, forum audit).
            with transaction.atomic():
                report = cls.objects.create(
                    post=post, reporter=reporter, reason=reason, detail=detail
                )
                if post.author_id is not None:
                    # .update(), not .get()+save(): the author's profile is
                    # guaranteed to exist (created on their first write via
                    # ForumProfile.for_user in submit_for_moderation) and F()
                    # makes the increment race-free without a row lock. A
                    # missing profile (shouldn't happen) no-ops rather than
                    # crashing the report flow.
                    ForumProfile.objects.filter(user_id=post.author_id).update(
                        flags_received=F("flags_received") + 1
                    )
        except IntegrityError:
            return None

        threshold = get_setting("REPORT_AUTO_HIDE_THRESHOLD")
        with transaction.atomic():
            # Lock and re-read liveness under the lock: a concurrent second
            # report crossing the threshold at the same instant must not fire
            # UnpublishAction twice (mirrors the Post DELETE handler's guard).
            locked = Post.objects.select_for_update().get(pk=post.pk)
            if locked.live:
                open_count = cls.objects.filter(post=locked, status=cls.OPEN).count()
                if open_count >= threshold:
                    # System action, not attributed to the reporter (who lacks
                    # permission) or a moderator — mirrors workflow.start(obj,
                    # None)'s "system attribution" convention.
                    UnpublishAction(locked, user=None).execute(
                        skip_permission_checks=True
                    )
                    cls.objects.filter(post=locked, status=cls.OPEN).update(
                        status=cls.AUTO_HIDDEN, resolved_at=timezone.now()
                    )
        return report

    @classmethod
    def file_for_message(cls, message, reporter, reason, detail=""):
        """Message-report analog of `file()` (todo 319/M10).

        Bumps the SENDER's `flags_received` the same way `file()` bumps a
        Post author's — the counter is a per-user cumulative signal, not
        Post-specific. No `select_for_update`/lock around the threshold check:
        unlike `file()`, there is no `UnpublishAction`-equivalent side effect
        to guard from double-firing here, only a status flip, so a benign
        double-update race at the exact threshold instant is harmless.

        Auto-hide has no content-redaction equivalent for a DM — a Message has
        no publish/unpublish state to enforce automatically. Crossing the
        threshold marks the matching reports AUTO_HIDDEN as a
        moderator-visibility signal only; a moderator must still act manually
        to remove content. This is a deliberate scope decision (see todo
        319's Work Log), not an oversight.
        """
        from ..conf import get_setting
        from .profiles import ForumProfile

        if message.sender_id is not None:
            # get_or_create the profile BEFORE opening the atomic() block
            # below: unlike a Post/Topic author (whose ForumProfile is
            # guaranteed to exist by the time it's reportable — seeded by
            # the publish signal), a DM-only sender may have NO profile row
            # at all, since Message creation fires no equivalent signal. A
            # bare .filter().update() would then silently match zero rows —
            # the exact spammer population this credits gets zero flag
            # credit. `for_user()`'s own IntegrityError handling (concurrent
            # first-touch race) has no nested savepoint, so it must run
            # outside any atomic() this method itself opens, or a race
            # would poison that transaction.
            ForumProfile.for_user(message.sender)

        try:
            with transaction.atomic():
                report = cls.objects.create(
                    message=message, reporter=reporter, reason=reason, detail=detail
                )
                if message.sender_id is not None:
                    ForumProfile.objects.filter(user_id=message.sender_id).update(
                        flags_received=F("flags_received") + 1
                    )
        except IntegrityError:
            return None

        threshold = get_setting("REPORT_AUTO_HIDE_THRESHOLD")
        open_count = cls.objects.filter(message=message, status=cls.OPEN).count()
        if open_count >= threshold:
            cls.objects.filter(message=message, status=cls.OPEN).update(
                status=cls.AUTO_HIDDEN, resolved_at=timezone.now()
            )
        return report
