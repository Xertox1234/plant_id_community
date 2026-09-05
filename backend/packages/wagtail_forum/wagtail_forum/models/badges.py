"""Badge engine (todo 348): CMS-curated badges awarded from a finite set of
metrics, generalizing the single hardcoded Botanist badge.

Three models, deliberately an ENGINE and not a catalog: ``Badge`` is a
Wagtail snippet a host curates in the CMS (name, slug, description, order,
active), ``BadgeRule`` is one ``metric >= threshold`` condition attached
inline (a badge with several rules is earned when ANY of them is met — rules
are alternative paths, which is what "first post OR first solution" style
badges want; a badge with no rules can never be earned), and ``UserBadge``
records an award, unique per ``(user, badge)`` so re-evaluation is
idempotent by construction.

Metrics are a closed enum (``BadgeMetric``) computed by ``wagtail_forum
.badges.user_metrics`` from data the package already maintains — the four
counters ``GET me/stats/`` shows. Adding a metric is a code change; adding a
badge is not. The package ships NO badge rows: the engine is inert until a
host seeds some (``manage.py seed_default_badges`` ships the sensible set,
including the Botanist badge migrated onto the engine).
"""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, InlinePanel


class BadgeMetric(models.TextChoices):
    # Each value names a key of `wagtail_forum.badges.user_metrics()`.
    POSTS = "posts", _("Live posts")
    SOLUTIONS_ACCEPTED = "solutions_accepted", _("Answers accepted")
    IDENTIFICATIONS_SHARED = "identifications_shared", _("Identifications shared")
    STREAK_DAYS = "streak_days", _("Day streak")


class Badge(ClusterableModel):
    name = models.CharField(max_length=60, unique=True)
    # The API/web identity — stable across renames, unlike `name`.
    slug = models.SlugField(max_length=60, unique=True)
    description = models.CharField(max_length=200, blank=True)
    # Display order on a profile; ties break by id.
    order = models.PositiveIntegerField(default=0)
    # An inactive badge is neither awarded nor shown; existing awards are
    # kept (re-activating restores them) rather than deleted.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    panels = [
        FieldPanel("name"),
        FieldPanel("slug"),
        FieldPanel("description"),
        FieldPanel("order"),
        FieldPanel("is_active"),
        InlinePanel("rules", label=_("Rules (any one earns the badge)"), min_num=1),
    ]

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class BadgeRule(models.Model):
    badge = ParentalKey(Badge, on_delete=models.CASCADE, related_name="rules")
    metric = models.CharField(max_length=32, choices=BadgeMetric.choices)
    threshold = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    panels = [FieldPanel("metric"), FieldPanel("threshold")]

    class Meta:
        constraints = [
            # One threshold per metric per badge — a second row for the same
            # metric could only be redundant or contradictory.
            models.UniqueConstraint(
                fields=["badge", "metric"], name="uniq_badge_rule_metric"
            ),
        ]

    def __str__(self):
        return f"{self.badge_id}: {self.metric} >= {self.threshold}"

    def is_met(self, metrics):
        return metrics.get(self.metric, 0) >= self.threshold


class UserBadge(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_badges",
    )
    # PROTECT, not CASCADE: UserBadge is not in Wagtail's ReferenceIndex (a
    # plain FK, not a chooser), so the snippet delete view would show no
    # "used by N" warning and a CASCADE would silently erase every member's
    # award history for the badge. Deleting a badge with awards is refused;
    # retire it with `is_active=False` instead (awards are kept, hidden).
    badge = models.ForeignKey(Badge, on_delete=models.PROTECT, related_name="awards")
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Idempotency at the storage layer: the engine's get_or_create
            # cannot double-award under repeated or concurrent signals.
            models.UniqueConstraint(fields=["user", "badge"], name="uniq_user_badge"),
        ]

    def __str__(self):
        return f"UserBadge(user={self.user_id}, badge={self.badge_id})"
