"""Host-side forum models.

Until todo 289 this module was deliberately empty: it existed so Django's
``emit_post_migrate_signal()`` sends ``post_migrate`` for this app (it skips
app configs whose ``models_module`` is None), which is how ``bootstrap.py``'s
receiver fires — after ``wagtail_forum`` is migrated and its permissions
exist. Real models are a superset of that trick; the receiver still fires.

``RagAnswer`` / ``RagAnswerReport`` (todo 289 / M13, design doc guardrail 5)
are host-owned rather than a third target on the package's ``Report`` model:
that one hard-FKs a post or a message under an exactly-one check constraint,
its ``file()`` classmethods penalise the CONTENT AUTHOR's flag count and
auto-hide past a threshold, and the package may not import ``apps.*``
(``test_reusability``). An AI answer has no author to penalise and was never
posted; it is private to the asker. The report loop it needs is "a human
reads what the user saw and acts" — served by the CMS snippet listing in
``wagtail_hooks.py``, next to the package's own report queue.
"""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting
from wagtail_forum import conf as forum_conf
from wagtail_forum.models import TrustLevel

from . import constants


class RagAnswer(models.Model):
    """One grounded answer as it was shown to the asker.

    Persisted at answer time (only for ``status: answered``) so a moderator
    reviewing a report sees exactly the text and sources the user saw — not a
    client-supplied claim about them. ``prompt_version`` records which prompt
    produced it.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_rag_answers",
    )
    question = models.CharField(max_length=constants.RAG_QUESTION_MAX_CHARS)
    answer = models.TextField()
    sources = models.JSONField(default=list)  # the serialized `sources` array
    prompt_version = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self) -> str:
        return f"RagAnswer #{self.pk} for user {self.user_id}"


class RagAnswerReport(models.Model):
    """A "this answer is wrong" report — guardrail 5's human review loop."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACTIONED = "actioned", "Actioned"
        DISMISSED = "dismissed", "Dismissed"

    answer = models.ForeignKey(
        RagAnswer, on_delete=models.CASCADE, related_name="reports"
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_rag_answer_reports",
    )
    detail = models.CharField(
        max_length=constants.RAG_REPORT_DETAIL_MAX_CHARS, blank=True
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.OPEN
    )
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
                fields=["answer", "reporter"],
                name="uniq_forum_rag_report_per_user_answer",
            )
        ]

    def __str__(self) -> str:
        return f"Report #{self.pk} on RagAnswer #{self.answer_id}"

    @property
    def answer_question(self) -> str:
        """The asked question, truncated for the moderation list view."""
        question = self.answer.question
        limit = constants.RAG_REPORT_QUESTION_PREVIEW_CHARS
        return question if len(question) <= limit else question[: limit - 1] + "…"

    @property
    def answer_text(self) -> str:
        """The answer exactly as shown to the user (moderation inspect view)."""
        return self.answer.answer

    @property
    def answer_sources(self) -> str:
        """The cited sources, one per line, for the moderation inspect view."""
        return "\n".join(
            f"[{s.get('n')}] {s.get('kind')}: {s.get('title')} ({s.get('date')})"
            for s in self.answer.sources
        )


def _inherits(name, what):
    """Panel help text: what the field tunes, plus the value a blank field
    resolves to. Reads the settings/default layer directly (not the
    provider-aware ``get_setting``) — that layer is exactly what a blank field
    inherits, and it needs no import-order premise. Kept on the FieldPanel,
    not the model field, so a per-deployment value never lands in a migration
    (``makemigrations --check`` would flag it)."""
    value = getattr(settings, f"WAGTAILFORUM_{name}", forum_conf.DEFAULTS[name])
    if isinstance(value, list):
        shown = ", ".join(value) if value else "none"
    else:
        shown = "none" if value in (None, "") else value  # 0 is a real value
    return f"{what} Leave blank to inherit the deployment value ({shown})."


@register_setting(icon="cog")
class ForumSettings(BaseGenericSetting):
    """Admin-editable forum tunables (Wagtail quick wins, item 1).

    One row, edited under Settings → Forum settings. Every field is nullable
    and blank means *inherit*: the package's ``get_setting`` reads a value
    from here only when set, otherwise the ``WAGTAILFORUM_<NAME>`` Django
    setting, otherwise the package default. Consumed through
    ``forum_settings.provide`` (memoised — see that module for why a save
    here must go through ``.save()``/``.delete()`` and not ``.update()``,
    which fires no signal and therefore rotates no token).
    """

    report_auto_hide_threshold = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name="Report auto-hide threshold",
    )
    trust_autopublish_level = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=TrustLevel.choices,
        verbose_name="Auto-publish from trust level",
    )
    spam_max_links = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name="Spam: max links per post"
    )
    spam_banned_words = models.TextField(blank=True, verbose_name="Spam: banned words")
    experts_min_trust_level = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=TrustLevel.choices,
        verbose_name="Community experts: minimum trust level",
    )
    badge_botanist_threshold = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name="Botanist badge: identifications shared",
    )

    panels = [
        MultiFieldPanel(
            [
                FieldPanel(
                    "report_auto_hide_threshold",
                    help_text=_inherits(
                        "REPORT_AUTO_HIDE_THRESHOLD",
                        "Distinct open reports on one post before it is "
                        "auto-hidden pending moderator review.",
                    ),
                ),
                FieldPanel(
                    "trust_autopublish_level",
                    help_text=_inherits(
                        "TRUST_AUTOPUBLISH_LEVEL",
                        "Authors at or above this trust level publish "
                        "without the spam-check hold.",
                    ),
                ),
            ],
            heading="Moderation",
        ),
        MultiFieldPanel(
            [
                FieldPanel(
                    "spam_max_links",
                    help_text=_inherits(
                        "SPAM_MAX_LINKS",
                        "More links than this in one post is held as spam.",
                    ),
                ),
                FieldPanel(
                    "spam_banned_words",
                    help_text=_inherits(
                        "SPAM_BANNED_WORDS",
                        "One word or phrase per line, matched "
                        "case-insensitively anywhere in the text.",
                    ),
                ),
            ],
            heading="Spam screen",
        ),
        MultiFieldPanel(
            [
                FieldPanel(
                    "experts_min_trust_level",
                    help_text=_inherits(
                        "EXPERTS_MIN_TRUST_LEVEL",
                        'Minimum trust level for the "Community experts" rail.',
                    ),
                ),
                FieldPanel(
                    "badge_botanist_threshold",
                    help_text=_inherits(
                        "BADGE_BOTANIST_THRESHOLD",
                        "Identifications shared to earn the Botanist badge.",
                    ),
                ),
            ],
            heading="Community",
        ),
    ]

    class Meta:
        verbose_name = "Forum settings"
        verbose_name_plural = "Forum settings"
