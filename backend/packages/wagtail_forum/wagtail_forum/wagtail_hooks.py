from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from wagtail import hooks
from wagtail.actions.unpublish import UnpublishAction
from wagtail.admin.search import SearchArea
from wagtail.admin.site_summary import SummaryItem
from wagtail.models import WorkflowState
from wagtail.snippets.bulk_actions.snippet_bulk_action import SnippetBulkAction
from wagtail.snippets.models import register_snippet
from wagtail.snippets.permissions import get_permission_name
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
    # Post is index.Indexed with one SearchField ("body"); this list is passed
    # through to the search backend as the `fields` filter, not a separate ORM
    # icontains mechanism (audit M20; wagtail/admin/views/generic/base.py
    # search_queryset()).
    search_fields = ["body"]

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
    # ForumProfile is a plain model (not index.Indexed), so this list drives a
    # direct ORM icontains filter, not the search backend (audit M20).
    search_fields = ["user__username"]

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
    that's the "awaiting human review" signal H16 makes visible here.

    Known scope limit: a spam-BACKEND crash (not a reject — the backend
    itself raising) rolls back the WorkflowState too, so that post has no
    active state and this count misses it. It stays findable via the admin
    snippet list's live=False filter, just not in this auto-count (see
    test_moderation_decided_signal_still_fires_when_spam_backend_crashes)."""
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


@hooks.register("register_admin_search_area")
def register_forum_search_area():
    """Makes the forum visible in Wagtail's global admin search picker (audit
    M20) — mirrors the blog's register_blog_search (apps/blog/wagtail_hooks.py).
    SearchArea is a plain positional-args class (confirmed via
    wagtail.admin.search.SearchArea) — not the Component-style trap
    ForumModerationSummaryItem's docstring above warns about."""
    return SearchArea(
        "Forum",
        "/cms/snippets/wagtail_forum/topic/",
        name="forum",
        icon_name="group",
        order=300,
    )


class ForumUnpublishBulkAction(SnippetBulkAction):
    """Bulk-unpublish selected Topics/Posts from the admin snippet list, for
    spam-wave cleanup (audit M20). Reuses the same UnpublishAction(...).execute(
    skip_permission_checks=True) call the single-object DELETE view and the
    report auto-hide threshold use (api/views.py, models/reports.py) — one
    unpublish mechanism, so the `unpublished` signal's counter/trust recount
    fires identically regardless of which path triggered it.
    """

    models = [Post, Topic]
    display_name = _("Unpublish")
    action_type = "unpublish"
    aria_label = _("Unpublish selected forum items")
    template_name = "wagtail_forum/admin/bulk_actions/confirm_bulk_unpublish.html"
    action_priority = 40
    classes = {"serious"}

    def check_perm(self, obj):
        # Snippet permissions aren't per-object, so (like the built-in
        # DeleteBulkAction) check once per model per request rather than once
        # per selected row.
        if getattr(self, "_can_change", None) is None:
            self._can_change = self.request.user.has_perm(
                get_permission_name("change", self.model)
            )
        return self._can_change

    def get_execution_context(self):
        # SnippetBulkAction.get_execution_context() supplies {"self": self}
        # only — no user — so a copy-paste of the Page bulk-unpublish action
        # would silently attribute every take-down to the system instead of
        # the acting moderator (audit M20 follow-up).
        return {**super().get_execution_context(), "user": self.request.user}

    @classmethod
    def execute_action(cls, objects, user=None, **kwargs):
        for obj in objects:
            UnpublishAction(obj, user=user).execute(skip_permission_checks=True)
        return len(objects), 0

    def get_success_message(self, num_parent_objects, num_child_objects):
        return ngettext(
            "%(count)d item has been unpublished",
            "%(count)d items have been unpublished",
            num_parent_objects,
        ) % {"count": num_parent_objects}


hooks.register("register_bulk_action", ForumUnpublishBulkAction)
