from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page

# Cap for the server-rendered fallback topic list (audit 2026-07-11 H17) —
# the SPA is the real UI; this bounds the fallback page's query.
SERVED_TOPICS_LIMIT = 50


class ForumIndex(Page):
    """Root forum node. Lets a host site place the forum in its page tree."""

    intro = RichTextField(blank=True)

    subpage_types = ["wagtail_forum.ForumBoard"]
    content_panels = Page.content_panels + [FieldPanel("intro")]

    def get_context(self, request, *args, **kwargs):
        # Minimal server-rendered fallback (audit 2026-07-11 H17): these pages
        # are live-routable, so direct serving (admin "View live", sitemaps,
        # crawlers) must render instead of 500ing with TemplateDoesNotExist.
        context = super().get_context(request, *args, **kwargs)
        context["boards"] = self.get_children().live().public().specific()
        return context


class ForumBoard(Page):
    """A board/category — a low-volume structural node."""

    description = models.TextField(blank=True)
    # Denormalized counters (maintained as topics/posts change; see Task 7 / Plan 1B).
    topic_count = models.PositiveIntegerField(default=0, editable=False)
    post_count = models.PositiveIntegerField(default=0, editable=False)

    parent_page_types = ["wagtail_forum.ForumIndex"]
    subpage_types = []
    content_panels = Page.content_panels + [FieldPanel("description")]

    def get_context(self, request, *args, **kwargs):
        # See ForumIndex.get_context — same H17 fallback rationale.
        context = super().get_context(request, *args, **kwargs)
        context["topics"] = self.topics.filter(live=True).order_by(
            "-is_pinned", "-last_post_at", "-id"
        )[:SERVED_TOPICS_LIMIT]
        return context
