"""Per-forum permission grants and per-forum moderators (todos 674, 675).

phpBB's model, simplified (spec 2026-10-28 §2): a forum grants a *role* to a
*principal*, and a role is a fixed set of ``f_*``-style flags. The principal is
a Django/Wagtail ``Group`` or one of two pseudo-groups: guests (anonymous
readers) and members (every signed-in user). What a role allows lives in
``services.forum_permissions.ROLE_FLAGS``; this module only stores rows.

``ForumModerator`` names who may moderate one forum through the Wagtail admin
(a user or a group, owner decision 2026-10-30). Global moderators (the host's
``publish_post`` + ``publish_topic`` group) are unchanged.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class ForumRole(models.TextChoices):
    """phpBB's forum roles (owner decision 2026-10-30)."""

    FULL = "full", _("Full access")
    STANDARD_POLLS = "standard_polls", _("Standard access + polls")
    STANDARD = "standard", _("Standard access")
    LIMITED = "limited", _("Limited access")
    READ_ONLY = "read_only", _("Read only access")
    NO_ACCESS = "no_access", _("No access")


class ForumGrant(models.Model):
    """One principal's role on one forum, category or link row."""

    ANONYMOUS = "anonymous"
    MEMBERS = "members"
    GROUP = "group"
    PRINCIPAL_CHOICES = [
        (ANONYMOUS, _("Guests")),
        (MEMBERS, _("All members")),
        (GROUP, _("Group")),
    ]

    forum = models.ForeignKey(
        "wagtail_forum.Forum", on_delete=models.CASCADE, related_name="grants"
    )
    principal = models.CharField(max_length=16, choices=PRINCIPAL_CHOICES)
    # Set only for a GROUP principal (forum_grant_group_iff_group_principal).
    group = models.ForeignKey(
        "auth.Group",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="wagtail_forum_grants",
    )
    role = models.CharField(max_length=24, choices=ForumRole.choices)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(Q(principal="group") & Q(group__isnull=False))
                | (~Q(principal="group") & Q(group__isnull=True)),
                name="forum_grant_group_iff_group_principal",
            ),
            models.UniqueConstraint(
                fields=["forum", "principal"],
                condition=~Q(principal="group"),
                name="uniq_forum_grant_pseudo_group",
            ),
            models.UniqueConstraint(
                fields=["forum", "group"],
                condition=Q(principal="group"),
                name="uniq_forum_grant_group",
            ),
        ]

    def __str__(self) -> str:
        who = self.group.name if self.group_id else self.get_principal_display()  # type: ignore[union-attr]
        return f"{self.forum} · {who}: {self.get_role_display()}"


class ForumModerator(models.Model):
    """A user or a group that moderates one forum (todo 674)."""

    forum = models.ForeignKey(
        "wagtail_forum.Forum", on_delete=models.CASCADE, related_name="moderators"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="wagtail_forum_moderated",
    )
    group = models.ForeignKey(
        "auth.Group",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="wagtail_forum_moderated",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(Q(user__isnull=False) & Q(group__isnull=True))
                | (Q(user__isnull=True) & Q(group__isnull=False)),
                name="forum_moderator_user_xor_group",
            ),
            models.UniqueConstraint(
                fields=["forum", "user"],
                condition=Q(user__isnull=False),
                name="uniq_forum_moderator_user",
            ),
            models.UniqueConstraint(
                fields=["forum", "group"],
                condition=Q(group__isnull=False),
                name="uniq_forum_moderator_group",
            ),
        ]

    def __str__(self) -> str:
        who = self.user if self.user_id else self.group
        return f"{self.forum} · {who}"
