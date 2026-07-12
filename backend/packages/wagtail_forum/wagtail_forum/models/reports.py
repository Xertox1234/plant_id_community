from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.db.models import F
from django.utils import timezone
from wagtail.actions.unpublish import UnpublishAction


class Report(models.Model):
    SPAM = "spam"
    ABUSE = "abuse"
    OFF_TOPIC = "off_topic"
    OTHER = "other"
    REASON_CHOICES = [
        (SPAM, "Spam"),
        (ABUSE, "Abuse"),
        (OFF_TOPIC, "Off topic"),
        (OTHER, "Other"),
    ]

    OPEN = "open"
    AUTO_HIDDEN = "auto_hidden"
    ACTIONED = "actioned"
    DISMISSED = "dismissed"
    STATUS_CHOICES = [
        (OPEN, "Open"),
        (AUTO_HIDDEN, "Auto-hidden"),
        (ACTIONED, "Actioned"),
        (DISMISSED, "Dismissed"),
    ]

    post = models.ForeignKey(
        "wagtail_forum.Post", on_delete=models.CASCADE, related_name="reports"
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
            models.UniqueConstraint(
                fields=["post", "reporter"], name="uniq_forum_report_per_user_post"
            )
        ]

    def __str__(self):
        return f"{self.reason} report on post {self.post_id}"

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
