from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from taggit.managers import TaggableManager
from wagtail.admin.panels import FieldPanel
from wagtail.models import DraftStateMixin, LockableMixin, RevisionMixin, WorkflowMixin
from wagtail.search import index


class Topic(
    WorkflowMixin,
    DraftStateMixin,
    LockableMixin,
    RevisionMixin,
    index.Indexed,
    models.Model,
):
    board = models.ForeignKey(
        "wagtail_forum.ForumBoard", on_delete=models.CASCADE, related_name="topics"
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    # Secondary discovery axis alongside the primary board taxonomy (audit M5):
    # species/genus/symptom labels. django-taggit is already a Wagtail
    # dependency and is in INSTALLED_APPS.
    #
    # NOTE: tags are a plain M2M through taggit's generic TaggedItem, so they do
    # NOT participate in this model's RevisionMixin/DraftStateMixin history —
    # retagging a topic is immediate and unversioned. That is deliberate (tags
    # are metadata, not post content); it is not a missed integration.
    tags = TaggableManager(blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="wagtail_forum_topics",
    )
    is_pinned = models.BooleanField(default=False)
    is_closed = models.BooleanField(default=False)  # no new replies

    # Denormalized for cheap mobile list rendering.
    reply_count = models.PositiveIntegerField(default=0, editable=False)
    view_count = models.PositiveIntegerField(default=0, editable=False)
    last_post_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_post_author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Mirror Wagtail's reference snippet (FullFeaturedSnippet): a canonical
    # GenericRelation filtering on base_content_type, overriding RevisionMixin's
    # `revisions` property. The mixin's private `_revisions` (content_type, no
    # related_query_name) is inherited unchanged for cascade-delete.
    revisions = GenericRelation(
        "wagtailcore.Revision",
        content_type_field="base_content_type",
        object_id_field="object_id",
        related_query_name="forum_topic",
        for_concrete_model=False,
    )
    workflow_states = GenericRelation(
        "wagtailcore.WorkflowState",
        content_type_field="base_content_type",
        object_id_field="object_id",
        related_query_name="forum_topic",
        for_concrete_model=False,
    )

    search_fields = [
        index.SearchField("title"),
        # No AutocompleteField (todo 276 / audit L8): nothing ever called
        # `backend.autocomplete()`, and the default database backend builds a
        # separate `autocomplete` tsvector per IndexEntry row for it — cost with
        # no reader. Wave 1 already shipped header search + full-text
        # SearchView, so there is no product gap. Re-add this line (no migration
        # needed — search_fields is not a DB field) if a title typeahead is ever
        # actually wired to a suggest endpoint.
        index.FilterField("live"),
        # SearchView filters by visible board (`board__in`); without this a
        # real search backend raises FilterFieldError.
        index.FilterField("board_id"),
    ]

    panels = [
        FieldPanel("board"),
        FieldPanel("title"),
        FieldPanel("slug"),
        FieldPanel("is_pinned"),
        FieldPanel("is_closed"),
        FieldPanel("tags"),
    ]

    class Meta:
        ordering = ["-is_pinned", "-last_post_at"]
        indexes = [
            models.Index(fields=["board", "-last_post_at"]),
            # /sync/ filters live topics by updated_at and orders by
            # (updated_at, id) on every mobile poll — match the index to the
            # sort so tie-heavy timestamps don't fall back to incremental sort.
            models.Index(
                fields=["updated_at", "id"],
                name="wf_topic_sync_idx",
                condition=models.Q(live=True),
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["board", "slug"], name="uniq_topic_slug_per_board"
            )
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        """Relative web route, matching web/src/utils/forumUrls.ts::threadPath
        (/forum/{board.id}-{board.slug}/{topic.id}-{topic.slug}). Callers that
        need an absolute link (e.g. an email) prepend settings.SITE_URL."""
        return f"/forum/{self.board_id}-{self.board.slug}/{self.id}-{self.slug}"
