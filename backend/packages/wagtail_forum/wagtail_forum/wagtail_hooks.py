from django.contrib.contenttypes.models import ContentType
from wagtail import hooks
from wagtail.admin.site_summary import SummaryItem
from wagtail.models import WorkflowState
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from .models import ForumProfile, Post, Report, Topic


class TopicViewSet(SnippetViewSet):
    model = Topic
    icon = "form"
    menu_label = "Topics"
    list_display = ["title", "board", "author", "live", "reply_count"]
    list_filter = ["live"]
    search_fields = ["title"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if qs is None:
            qs = self.model.objects.all()
        return qs.select_related("board", "author", "last_post_author")


class PostViewSet(SnippetViewSet):
    model = Post
    icon = "comment"
    menu_label = "Posts"
    list_display = ["__str__", "topic", "author", "live"]
    list_filter = ["live"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if qs is None:
            qs = self.model.objects.all()
        return qs.select_related("topic", "author")


class ForumProfileViewSet(SnippetViewSet):
    model = ForumProfile
    icon = "user"
    menu_label = "Profiles"
    list_display = ["__str__", "trust_level", "post_count"]
    list_filter = ["trust_level"]

    def get_queryset(self, request):
        # __str__ falls back to user.get_username() — N+1 without this.
        qs = super().get_queryset(request)
        if qs is None:
            qs = self.model.objects.all()
        return qs.select_related("user")


class ReportViewSet(SnippetViewSet):
    model = Report
    icon = "warning"
    menu_label = "Reports"
    list_display = ["post", "reporter", "reason", "status", "created_at"]
    list_filter = ["status", "reason"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if qs is None:
            qs = self.model.objects.all()
        return qs.select_related("post", "reporter", "resolved_by")


class ForumViewSetGroup(SnippetViewSetGroup):
    items = (TopicViewSet, PostViewSet, ForumProfileViewSet, ReportViewSet)
    menu_icon = "group"
    menu_label = "Forum"
    menu_name = "forum"


register_snippet(ForumViewSetGroup)


def _pending_moderation_count():
    """Topics/posts with an active workflow state.

    SpamCheckTask resolves synchronously within the same request, so
    IN_PROGRESS never outlives it — Wagtail's AbstractWorkflow.start() is
    @transaction.atomic, so a mid-check crash rolls the TaskState back too;
    it does not orphan one. What DOES persist is NEEDS_CHANGES: content the
    spam check rejected, which stays a draft for a moderator to review —
    that's the "awaiting human review" signal H16 makes visible here."""
    content_types = ContentType.objects.get_for_models(Topic, Post).values()
    return WorkflowState.objects.active().filter(content_type__in=content_types).count()


class ForumModerationSummaryItem(SummaryItem):
    # SummaryItem is a Component: __init__ only takes request, and rendering
    # is template-driven (get_context_data + template_name), NOT the
    # positional-args constructor apps/blog/wagtail_hooks.py uses — that
    # older API doesn't exist on this installed Wagtail version (confirmed
    # via wagtail.images.wagtail_hooks.ImagesSummaryItem, the in-tree
    # precedent this mirrors).
    order = 210
    template_name = "wagtail_forum/homepage/site_summary_moderation.html"

    def __init__(self, request, count):
        super().__init__(request)
        self.count = count

    def get_context_data(self, parent_context):
        return {"count": self.count}


@hooks.register("construct_homepage_summary_items")
def add_forum_moderation_summary_item(request, items):
    """Mirrors the blog's "Pending Comments" summary item — same hook, same
    "N awaiting X" shape (apps/blog/wagtail_hooks.py) — so forum moderation
    gets the same homepage visibility blog content already has (audit H16)."""
    try:
        count = _pending_moderation_count()
    except Exception:
        return  # graceful degradation if forum models aren't ready
    if count > 0:
        items.append(ForumModerationSummaryItem(request, count))
