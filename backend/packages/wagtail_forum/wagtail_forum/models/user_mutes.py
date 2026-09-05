"""Member-to-member mute (todo 347) — the light tool beside ``UserBlock``.

A block is reciprocal suppression: it hides mentions, replies, DMs and
profile activity in BOTH directions and refuses DMs with 403. A mute is
one-directional and content-only: the muter stops seeing the muted member's
topics, posts and notifications, and nothing changes for the muted member —
they can still read, reply to, mention and message the muter (their DMs
still arrive, Discourse's precedent). It is the "I just don't want to hear
this person" option for members who don't want to escalate to a block.

Same shape as ``UserBlock`` on purpose (unique pair, no self-mute, a
``muted`` index for the reverse lookup the notification fan-out needs), so
the two share every filtering site — see ``api/views.py``'s
``_annotate_author_blocked``/``_exclude_blocked_authors``, which carry both.
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class UserMute(models.Model):
    muter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_mutes_made",
    )
    muted = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_mutes_received",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["muter", "muted"], name="uniq_forum_mute"),
            # DB backstop for the app-level can_mute() guard below — same
            # discipline as UserBlock's forum_block_not_self.
            models.CheckConstraint(
                condition=~Q(muter=F("muted")), name="forum_mute_not_self"
            ),
        ]
        # The UniqueConstraint's composite index covers muter-prefix lookups
        # (the muter's own filters); `muted` serves the fan-out lookup "which
        # of these recipients muted the actor" (forum_host/notifications.py).
        indexes = [models.Index(fields=["muted"])]

    def __str__(self):
        return f"UserMute(muter={self.muter_id}, muted={self.muted_id})"

    @classmethod
    def can_mute(cls, muter, muted):
        """Whether `muter` may mute `muted`: authenticated and not self."""
        if muter is None or not muter.is_authenticated or muted is None:
            return False
        return muter.pk != muted.pk

    @classmethod
    def mute(cls, muter, muted):
        """Idempotently mute `muted` for `muter` (bare get_or_create — see
        UserBlock.block for why no IntegrityError re-wrap)."""
        mute, _ = cls.objects.get_or_create(muter=muter, muted=muted)
        return mute

    @classmethod
    def unmute(cls, muter, muted):
        cls.objects.filter(muter=muter, muted=muted).delete()
