from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models import Q
from wagtail.admin.panels import FieldPanel
from wagtail.fields import StreamField
from wagtail.models import DraftStateMixin, LockableMixin, RevisionMixin, WorkflowMixin
from wagtail.search import index

from ..blocks import ForumBodyBlock

# Block-reason code returned by edit_block/delete_block that PostWriteView maps to
# 403 (not owner/moderator), vs the message-carrying codes that map to 409. A
# shared constant so the model producer and the view consumer (api/views.py
# _enforce_writable) can't drift a rename into a 403-leaks-as-409 bug.
BLOCK_FORBIDDEN = "forbidden"


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
        # blank=True so full_clean() (called by save_revision) accepts the NULL
        # author that SET_NULL leaves behind on account deletion — otherwise a
        # moderator can never edit/redact an account-deleted author's post.
        blank=True,
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

    search_fields = [
        index.SearchField("body"),
        # Any real-backend search over live posts filters on this; without it
        # Elasticsearch raises FilterFieldError (Topic declares it; Post must too).
        index.FilterField("live"),
        # Required so the DB search backend can filter on topic__live and
        # topic__board_id (visibility constraints in SearchView). Without this
        # declaration the backend raises FilterFieldError. No migration or
        # reindex needed for the DB backend.
        index.RelatedFields(
            "topic",
            [
                index.FilterField("live"),
                index.FilterField("board_id"),
            ],
        ),
    ]

    panels = [
        FieldPanel("topic"),
        FieldPanel("body"),
        FieldPanel("is_opening_post"),
    ]

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["topic", "created_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["topic"],
                condition=Q(is_opening_post=True),
                name="uniq_opening_post_per_topic",
            )
        ]

    def __str__(self):
        return f"Post #{self.pk} in {self.topic_id}"

    def edit_block(self, user):
        """Why ``user`` may not edit (PATCH) this post, or ``None`` if they may.

        The single source of the edit policy: owner-or-moderator, then the
        per-post lock, then the frozen (closed/locked) topic. ``PostWriteView``
        maps the returned code to an HTTP status and ``PostSerializer`` reads the
        boolean form (:meth:`can_be_edited_by`), so the button affordance and the
        write path cannot diverge (todo 252). Reads ``self.topic`` — callers that
        serialize a list must ``select_related("topic")`` to keep this flat (no
        N+1).
        """
        if user is None or not user.is_authenticated:
            return (BLOCK_FORBIDDEN, None)
        # Short-circuit like the write path: an owner never triggers the
        # permission lookup, so the post-list query count stays flat for authors.
        if not (
            user.pk == self.author_id or user.has_perm("wagtail_forum.change_post")
        ):
            return (BLOCK_FORBIDDEN, None)
        if self.locked and not user.has_perm("wagtail_forum.change_post"):
            return ("locked", "Post is locked.")
        if self.topic.is_closed or self.topic.locked:
            return ("frozen", "Topic is closed or locked.")
        return None

    def delete_block(self, user):
        """Why ``user`` may not delete (DELETE) this post, or ``None`` if they may.

        Same policy as :meth:`edit_block` plus the opening-post rule (opening
        posts are not deletable via the API).
        """
        blocked = self.edit_block(user)
        if blocked is not None:
            return blocked
        if self.is_opening_post:
            return ("opening", "Opening posts cannot be deleted via the API.")
        return None

    def can_be_edited_by(self, user):
        """Boolean form of :meth:`edit_block` for the serializer's can_edit flag."""
        return self.edit_block(user) is None

    def can_be_deleted_by(self, user):
        """Boolean form of :meth:`delete_block` for the serializer's can_delete flag."""
        return self.delete_block(user) is None

    def can_be_reported_by(self, user):
        """Whether `user` may report this post: authenticated and not its own
        author (self-report has no legitimate use). Single-sourced here so the
        serializer's can_report flag and PostReportView's write guard cannot
        diverge — same discipline as can_be_edited_by/can_be_deleted_by."""
        if user is None or not user.is_authenticated:
            return False
        return user.pk != self.author_id
