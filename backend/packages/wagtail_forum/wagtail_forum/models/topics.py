from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from taggit.managers import TaggableManager
from wagtail.admin.panels import FieldPanel
from wagtail.models import DraftStateMixin, LockableMixin, RevisionMixin, WorkflowMixin
from wagtail.search import index

# Same 403-vs-409 block-code contract the post write path uses; solution_block
# below returns it so api/views.py::_enforce_writable-style mapping stays shared.
# Safe at module scope: posts.py refers to Topic by string, so there is no cycle.
from .posts import BLOCK_FORBIDDEN


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
        # blank=True for the same reason as Post.author (todo 338, LEARNINGS
        # 2026-07-03): save_revision() runs full_clean(), which rejects the
        # NULL that SET_NULL leaves behind on account deletion — without it a
        # moderator can never republish (hide → fix slug → publish) an
        # account-deleted author's topic. The admin panels below deliberately
        # omit `author`, so this does not expose a blank-able field to staff.
        blank=True,
        related_name="wagtail_forum_topics",
    )
    is_pinned = models.BooleanField(default=False)
    is_closed = models.BooleanField(default=False)  # no new replies

    # Accepted answer (audit H6, roadmap Wave 2 slice 2). SET_NULL, not CASCADE:
    # a hard-deleted answer must clear the badge, never take the whole topic
    # with it. `editable=False` keeps it off the CMS panel — marking a solution
    # is an API action with its own permission rule (solution_block), not a
    # free-text admin field.
    solved_post = models.ForeignKey(
        "wagtail_forum.Post",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        editable=False,
    )
    solved_at = models.DateTimeField(null=True, blank=True, editable=False)

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
        # KEEP (todo 276 / audit L8). The reader is Wagtail itself, not our code:
        # `TopicViewSet` (wagtail_hooks.py) is a SnippetViewSet with
        # `search_fields = ["title"]`, so the /cms/ Topics listing has a search
        # box, and Wagtail's generic `search_queryset`
        # (admin/views/generic/base.py) calls `search_backend.autocomplete()`
        # whenever `get_autocomplete_search_fields()` is non-empty — else it
        # falls back to whole-word `search()` and warns. Dropping this made a
        # moderator's "mons" stop matching "Monstera repotting" in the CMS.
        # Grepping this repo for `.autocomplete(` does NOT prove it has no
        # reader; the framework is the caller. Pinned by
        # tests/test_admin.py::test_topic_listing_search_matches_a_title_prefix.
        index.AutocompleteField("title"),
        index.FilterField("live"),
        # SearchView filters by visible board (`board__in`); without this a
        # real search backend raises FilterFieldError.
        index.FilterField("board_id"),
        # SearchView excludes blocked authors' topics (todo 284/M9) via
        # author_id__in=Subquery(...); same FilterFieldError without this.
        index.FilterField("author_id"),
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

    def solution_block(self, user):
        """Why *user* may not mark/unmark this topic's answer, or ``None``.

        Single source of the accept-answer policy (audit H6), the same
        block-code discipline as :meth:`Post.edit_block` so the API guard and
        the serializer affordance cannot diverge (todo 252).

        **Who:** the topic's own author, or a moderator. Moderator means
        ``wagtail_forum.change_post`` — deliberately the SAME predicate the
        edit/redact path and ``api/views.py::_is_forum_moderator`` already use,
        rather than a second notion (``change_topic``) that a moderator group
        could hold differently and silently drift from.

        **Not gated on closed/locked.** Unlike editing a post, accepting an
        answer writes topic metadata, not content — and closing a solved
        question is the normal end of its life, so a moderator who closes a
        thread must still be able to mark which reply answered it. The frozen
        guard in ``Post.edit_block`` is about content mutation and does not
        transfer here.
        """
        if user is None or not user.is_authenticated:
            return (BLOCK_FORBIDDEN, None)
        if not (
            user.pk == self.author_id or user.has_perm("wagtail_forum.change_post")
        ):
            return (BLOCK_FORBIDDEN, None)
        return None

    def can_mark_solution_by(self, user):
        """Boolean form of :meth:`solution_block` for the serializer's
        ``can_mark_solution`` affordance."""
        return self.solution_block(user) is None

    def get_absolute_url(self):
        """Relative web route, matching web/src/utils/forumUrls.ts::threadPath
        (/forum/{board.id}-{board.slug}/{topic.id}-{topic.slug}). Callers that
        need an absolute link (e.g. an email) prepend settings.SITE_URL."""
        return f"/forum/{self.board_id}-{self.board.slug}/{self.id}-{self.slug}"
