from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
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
        index.AutocompleteField("title"),
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
