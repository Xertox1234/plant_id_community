from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page


class ForumIndex(Page):
    """Root forum node. Lets a host site place the forum in its page tree."""

    intro = RichTextField(blank=True)

    subpage_types = ["wagtail_forum.ForumBoard"]
    content_panels = Page.content_panels + [FieldPanel("intro")]


class ForumBoard(Page):
    """A board/category — a low-volume structural node."""

    description = models.TextField(blank=True)
    # Denormalized counters (maintained as topics/posts change; see Task 7 / Plan 1B).
    topic_count = models.PositiveIntegerField(default=0, editable=False)
    post_count = models.PositiveIntegerField(default=0, editable=False)

    parent_page_types = ["wagtail_forum.ForumIndex"]
    subpage_types = []
    content_panels = Page.content_panels + [FieldPanel("description")]
