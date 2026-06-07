from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.fields import StreamField
from wagtail.models import DraftStateMixin, LockableMixin, RevisionMixin, WorkflowMixin
from wagtail.search import index

from ..blocks import ForumBodyBlock


class Post(
    WorkflowMixin,
    DraftStateMixin,
    LockableMixin,
    RevisionMixin,
    index.Indexed,
    models.Model,
):
    topic = models.ForeignKey(
        "wagtail_forum.Topic", on_delete=models.CASCADE, related_name="posts"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="wagtail_forum_posts",
    )
    body = StreamField(ForumBodyBlock(), blank=True)
    is_opening_post = models.BooleanField(default=False)
    edited = models.BooleanField(default=False)

    # Denormalized per-type reaction counts, e.g. {"like": 3, "thanks": 1}.
    reaction_counts = models.JSONField(default=dict, blank=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Mirror Wagtail's reference snippet (FullFeaturedSnippet): a canonical
    # GenericRelation filtering on base_content_type, overriding RevisionMixin's
    # `revisions` property. The mixin's private `_revisions` is inherited
    # unchanged for cascade-delete.
    revisions = GenericRelation(
        "wagtailcore.Revision",
        content_type_field="base_content_type",
        object_id_field="object_id",
        related_query_name="forum_post",
        for_concrete_model=False,
    )
    workflow_states = GenericRelation(
        "wagtailcore.WorkflowState",
        content_type_field="base_content_type",
        object_id_field="object_id",
        related_query_name="forum_post",
        for_concrete_model=False,
    )

    search_fields = [index.SearchField("body")]

    panels = [
        FieldPanel("topic"),
        FieldPanel("body"),
        FieldPanel("is_opening_post"),
    ]

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Post #{self.pk} in {self.topic_id}"
