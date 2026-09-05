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
    menu_label = _("Topics")
    list_display = ["title", "board", "author", "live", "reply_count"]
    list_filter = ["live"]
    search_fields = ["title"]
    # CSV/XLSX download + read-only inspect page (Wagtail quick wins, item
    # 4). Export columns are the moderation-triage set: enough to spot a
    # spam wave (author, created, live) and thread health (replies, views,
    # solved) without a shell. Headings are explicit so the spreadsheet
    # doesn't depend on verbose_name drift.
    list_export = [
        "id",
        "title",
        "board",
        "author",
        "live",
        "is_pinned",
        "is_closed",
        "reply_count",
        "view_count",
        "solved_post_id",
        "created_at",
        "last_post_at",
    ]
    export_headings = {
        "id": _("ID"),
        "title": _("Title"),
        "board": _("Board"),
        "author": _("Author"),
        "live": _("Live"),
        "is_pinned": _("Pinned"),
        "is_closed": _("Closed"),
        "reply_count": _("Replies"),
        "view_count": _("Views"),
        "solved_post_id": _("Solved post ID"),
        "created_at": _("Created"),
        "last_post_at": _("Last post"),
    }
    export_filename = "forum-topics"
    inspect_view_enabled = True
    inspect_view_fields = [
        "title",
        "slug",
        "board",
        "author",
        "live",
        "is_pinned",
        "is_closed",
        "tags",
        "reply_count",
        "view_count",
        "solved_post",
        "solved_at",
        "last_post_at",
        "last_post_author",
        "created_at",
        "updated_at",
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if qs is None:
            qs = self.model.objects.all()
        return qs.select_related("board", "author", "last_post_author")


class PostViewSet(SnippetViewSet):
    model = Post
    icon = "comment"
    menu_label = _("Posts")
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
    menu_label = _("Profiles")
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
    menu_label = _("Reports")
    # "post" is unchanged from before todo 319/M10 (blank for a message
    # report, same as always). "message_summary" is additive — a report has
    # exactly one of post/message set (forum_report_exactly_one_target), so
    # exactly one of the two columns is populated per row.
    list_display = [
        "post",
        "message_summary",
        "reporter",
        "reason",
        "status",
        "created_at",
    ]
    list_filter = ["status", "reason"]
    # CSV/XLSX download + inspect page (Wagtail quick wins, item 4). Every
    # column is safe for BOTH report shapes: `topic_title` and
    # `message_summary` are model properties that return "" for the other
    # target, because the export resolves dotted paths with multigetattr
    # and a NULL post would 500 the whole download (see Report.topic_title).
    list_export = [
        "id",
        "status",
        "reason",
        "detail",
        "topic_title",
        "post",
        "message_summary",
        "reporter",
        "created_at",
        "resolved_at",
        "resolved_by",
    ]
    export_headings = {
        "id": _("ID"),
        "status": _("Status"),
        "reason": _("Reason"),
        "detail": _("Detail"),
        "topic_title": _("Topic"),
        "post": _("Post"),
        "message_summary": _("Message"),
        "reporter": _("Reporter"),
        "created_at": _("Created"),
        "resolved_at": _("Resolved at"),
        "resolved_by": _("Resolved by"),
    }
    export_filename = "forum-reports"
    inspect_view_enabled = True
    inspect_view_fields = [
        "status",
        "reason",
        "detail",
        "topic_title",
        "post",
        "message_summary",
        "reporter",
        "created_at",
        "resolved_at",
        "resolved_by",
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if qs is None:
            qs = self.model.objects.all()
        return qs.select_related(
            "post",
            "post__topic",  # topic_title (export/inspect)
            "message__sender",
            "message__conversation",
            "reporter",
            "resolved_by",
        )


class ForumViewSetGroup(SnippetViewSetGroup):
    items = (TopicViewSet, PostViewSet, ForumProfileViewSet, ReportViewSet)
    menu_icon = "group"
    menu_label = _("Forum")
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
        from django.urls import reverse

        return {
            "count": self.count,
            # Resolved, not hardcoded: the admin mount (/cms/ here) is host
            # config, and this package is reusable (audit 2026-07-17 M1).
            "moderation_url": reverse(Topic.snippet_viewset.get_url_name("list")),
        }


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
    from django.urls import reverse

    return SearchArea(
        _("Forum"),
        reverse(Topic.snippet_viewset.get_url_name("list")),
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


@hooks.register("register_admin_urls")
def register_moderation_queue_urls():
    """Mounts the moderation queue report under the admin root (todo 345).
    Wagtail wraps every hook-registered admin pattern in require_admin_access,
    so the view's own PermissionCheckedMixin only has to add the moderator
    check on top of "may enter the admin at all"."""
    from django.urls import include, path

    return [path("forum/reports/", include("wagtail_forum.admin_urls"))]


@hooks.register("register_reports_menu_item")
def register_moderation_queue_menu_item():
    """ "Forum moderation queue" under the admin Reports menu, shown to users
    holding wagtail_forum.change_post (ModerationQueueMenuItem.is_shown) —
    not AdminOnlyMenuItem, because the trust system grants moderation below
    superuser. reverse() inside the hook body, never a hardcoded /cms/ path
    (audit 2026-07-17 M1); the registry is lazy so the URLconf is loaded."""
    from django.urls import reverse

    from .admin_views import ModerationQueueMenuItem

    return ModerationQueueMenuItem(
        _("Forum moderation queue"),
        reverse("wagtail_forum_reports:moderation_queue"),
        name="forum-moderation-queue",
        icon_name="warning",
        order=1300,
    )
