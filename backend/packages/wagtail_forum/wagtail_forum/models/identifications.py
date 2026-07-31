from django.db import models
from wagtail.images import get_image_model_string


class ForumIdentificationAttachment(models.Model):
    """A topic-level **snapshot** of a plant-ID result the author attached.

    Audit M6 / roadmap Wave 2 slice 3. The forum's differentiator: a
    help-identify topic carries the photo and the app's own suggestions, so a
    reader can answer without asking "what does the app think?" first.

    **Snapshot, not a reference.** Deliberately NOT a FK into the identification
    domain, and deliberately NOT a StreamField body block:

    - No FK into a user's private identification history. Purging that history
      (GDPR posture) must never blank out or break public forum content.
    - A plain model, not a body block, so the shape can migrate normally instead
      of needing a StreamField data migration across every stored body.
    - It hangs off the *topic*, not a post: it is what the topic is *about*, so
      it survives the opening post being edited, redacted, or replaced.

    **Every field is caller-supplied and must be treated as such.** There is no
    server-side identification record to look up — the project's
    ``/plant-identification/identify/`` endpoint is stateless (it returns the AI
    result and persists nothing; ``PlantIdentificationResult`` has readers but
    no writer anywhere in the codebase). So the composer sends the snapshot it
    just received, and this row records *what the author says the app told
    them*. The API bounds it (count, lengths, confidence range — see
    ``api/serializers.py::TopicIdentificationSerializer``) and the UI labels it
    as the author's attached app result rather than an authoritative claim.
    Nothing here is a verified species determination.

    ``wagtail_forum`` is a reusable package and does not import the host's
    identification app; that separation is why the snapshot arrives over the
    API instead of being resolved server-side.
    """

    topic = models.OneToOneField(
        "wagtail_forum.Topic",
        on_delete=models.CASCADE,
        related_name="identification",
    )
    # SET_NULL, not CASCADE: a deleted image must leave the candidates readable
    # (the card renders a no-photo fallback), never take the topic's attachment
    # — or the topic — with it.
    image = models.ForeignKey(
        get_image_model_string(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    # Which identification provider produced the candidates ("plant_id",
    # "plantnet", "ai_combined", …). Free text rather than choices: the host
    # owns its provider vocabulary, and this package must not encode it.
    provider = models.CharField(max_length=50, blank=True)
    # [{name, scientific_name, confidence}, …], best first. Bounded on write.
    candidates = models.JSONField(default=list, blank=True)
    # Plain, non-FK correlation handle (roadmap "advisor amendments"): lets a
    # later analytics job line a topic up against the identification that
    # prompted it, without coupling public forum content to private history.
    #
    # NO PRODUCER EXISTS TODAY. The identify endpoint is stateless, so no client
    # has an id to send and this stays "". Kept because adding it later means a
    # migration plus a client change; keeping it costs one nullable column. It
    # is never serialized out — see TopicDetailSerializer.get_identification.
    identification_result_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "forum identification attachment"

    def __str__(self):
        return f"Identification for topic {self.topic_id}"

    @property
    def top_candidate(self):
        """The best-confidence candidate dict, or ``None`` when empty."""
        return self.candidates[0] if self.candidates else None
