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
from django.db import models

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
