"""Member-to-member block/mute (todo 284, audit M9).

Host-agnostic, alongside TopicSubscription/TopicBookmark. This is the first
true user-to-user relationship model in this package — every other model
here relates a user to *content* (a topic, a post), not to another user.

Phase 1 of todo 284 only. Private messaging (M10) is explicitly gated on
this shipping and is NOT scaffolded here or anywhere else in this change.
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class UserBlock(models.Model):
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        # Mirrors TopicSubscription/TopicBookmark's related_name discipline
        # (models/subscriptions.py, models/bookmarks.py) — checked against
        # every related_name= in this package; forum_blocks_made/received
        # don't clash with anything already claimed on User.
        related_name="forum_blocks_made",
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_blocks_received",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["blocker", "blocked"], name="uniq_forum_block"
            ),
            # Django 6's CheckConstraint requires `condition=`, not `check=`
            # (checked against the installed version in this repo's venv).
            # No self-block precedent exists elsewhere in this codebase —
            # this is a new pattern, paired with the app-level can_block()
            # guard below so the DB constraint is a backstop, not the only
            # line of defense (same discipline as Post.can_be_reported_by).
            models.CheckConstraint(
                condition=~Q(blocker=F("blocked")), name="forum_block_not_self"
            ),
        ]
        # Only an index on `blocked`, not `blocker` — the UniqueConstraint's
        # own composite index already covers blocker-prefix lookups (same
        # reasoning TopicBookmark/TopicRead use to skip a redundant index).
        # The `blocked` index serves the reverse-direction lookup needed by
        # the bidirectional mention/typeahead exclusion ("has this viewer
        # been blocked by candidate X").
        indexes = [models.Index(fields=["blocked"])]

    def __str__(self):
        return f"UserBlock(blocker={self.blocker_id}, blocked={self.blocked_id})"

    @classmethod
    def can_block(cls, blocker, blocked):
        """Whether `blocker` may block `blocked`: authenticated and not
        self-block (self-block has no legitimate use). Single-sourced here so
        the write view and any serializer flag cannot diverge — same
        discipline as Post.can_be_reported_by (models/posts.py)."""
        if blocker is None or not blocker.is_authenticated or blocked is None:
            return False
        return blocker.pk != blocked.pk

    @classmethod
    def block(cls, blocker, blocked):
        """Idempotently block `blocked` for `blocker`.

        Bare get_or_create — mirrors TopicBookmark.bookmark (the newer
        model), NOT TopicSubscription.subscribe's IntegrityError-retry
        wrapper. That wrapper exists only because subscribe() runs inside an
        ambient publish transaction elsewhere; a block/unblock view call
        isn't nested in one. See docs/patterns/architecture/services.md
        ("Don't Re-Wrap get_or_create's Own Race Recovery").
        """
        block, _ = cls.objects.get_or_create(blocker=blocker, blocked=blocked)
        return block

    @classmethod
    def unblock(cls, blocker, blocked):
        cls.objects.filter(blocker=blocker, blocked=blocked).delete()
