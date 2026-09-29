"""Forum admin pages: reported content and pending content.

Reported content — a Wagtail admin *report* over open ``Report`` rows.

Why a ``ReportView`` and not a bespoke admin view (todo 345): Wagtail's
report framework is the package-safe extension point — it gives the listing,
column sorting, filters, pagination, CSV/XLSX export and the Reports menu
entry for free, with no template of our own to keep in step with admin
upgrades. It is deliberately a *listing*: the action/dismiss mutations stay
on the existing ``Report`` snippet inspect/edit views, which every row links
to, so there is exactly one mutation path.

Permission is the ``Report`` model's own policy — any of add/change/delete/
view on ``wagtail_forum.report``, exactly what the ``Report`` snippet index
and inspect views require — NOT superuser-only (the trust system grants
moderation below superuser, and ``AdminOnlyMenuItem`` would hide the queue
from exactly the people it is for) and NOT ``change_post`` (review of this
slice): every row links into the Report snippet views, so a gate looser than
theirs renders links that bounce, and a queue that shows reported DM
excerpts must not be readable by anyone the Report snippet itself denies.
The host's bootstrapped "Forum Moderators" group holds view/change on
reports for this reason (``forum_host/bootstrap.py``).

It is titled "Reported forum content", not "moderation queue" (todo 423):
the owner read "Forum moderation queue" as the place pending posts wait, and
it never listed them.

Pending content (todo 423) — ``PendingContentView``, one listing of every
topic and post waiting for a moderator, each with an Approve button that
publishes it; for a new topic, the topic and its opening post together. One
row per POST: a topic never runs the moderation workflow itself (the API
routes a new topic's opening post, and publishing that post publishes its
topic), so a new topic is its opening post's row. The page is gated on the
``publish`` permission on Post, the right Approve exercises.

Moderators are NOT notified when content is waiting (owner decision
2026-09-28, todo 423): no push, no email. The dashboard's pending count and
this page are the signal, which is why both read the same queryset
(``pending_posts``) and the count links here.
"""

import datetime
import json
from types import SimpleNamespace

import django_filters
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import (
    Case,
    CharField,
    Count,
    Exists,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    When,
)
from django.db.models.functions import Cast
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.http import urlencode
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.views import View
from wagtail.admin.filters import WagtailFilterSet
from wagtail.admin.menu import MenuItem
from wagtail.admin.ui.tables import Column, DateColumn, TitleColumn
from wagtail.admin.views.reports import ReportView
from wagtail.models import WorkflowState
from wagtail.permission_policies import ModelPermissionPolicy

from .models import Post, Report, Topic, TrustLevel

# The two statuses that still need a human: OPEN is untouched, AUTO_HIDDEN
# crossed REPORT_AUTO_HIDE_THRESHOLD and was unpublished by the system but a
# moderator still has to decide (restore or action). ACTIONED/DISMISSED are
# done and belong in the full snippet listing, not the queue.
QUEUE_STATUSES = (Report.OPEN, Report.AUTO_HIDDEN)

# The Report snippet's default policy and its index/inspect views' own
# `any_permission_required` list (wagtail/admin/views/generic/models.py) —
# the queue is a view over the same rows, so it opens for the same people.
queue_permission_policy = ModelPermissionPolicy(Report)
QUEUE_PERMISSIONS = ["add", "change", "delete", "view"]


def user_can_view_queue(user):
    return queue_permission_policy.user_has_any_permission(user, QUEUE_PERMISSIONS)


def _inspect_url(report):
    # Resolved, never hardcoded: the admin mount (/cms/ here) is host config
    # and this package is reusable (audit 2026-07-17 M1).
    return reverse(Report.snippet_viewset.get_url_name("inspect"), args=[report.pk])


def _trust_level_label(level):
    """Decode the `reporter_trust_level` annotation (int or None) for both
    the on-screen column and the CSV/XLSX export, so the download does not
    show a bare digit where the screen shows "Regular"."""
    return "" if level is None else TrustLevel(level).label


def _trust_label(report):
    return _trust_level_label(report.reporter_trust_level)


class ModerationQueueFilterSet(WagtailFilterSet):
    reason = django_filters.ChoiceFilter(
        choices=Report.REASON_CHOICES, label=_("Reason")
    )
    # Explicit two-choice filter: Wagtail's auto-generated one would offer
    # ACTIONED/DISMISSED too, which the queue never contains.
    status = django_filters.ChoiceFilter(
        choices=[
            (status, label)
            for status, label in Report.STATUS_CHOICES
            if status in QUEUE_STATUSES
        ],
        label=_("Status"),
    )

    class Meta:
        model = Report
        fields = ["reason", "status"]


class ModerationQueueView(ReportView):
    page_title = _("Reported forum content")
    header_icon = "warning"
    index_url_name = "wagtail_forum_reports:moderation_queue"
    index_results_url_name = "wagtail_forum_reports:moderation_queue_results"
    filterset_class = ModerationQueueFilterSet
    permission_policy = queue_permission_policy
    any_permission_required = QUEUE_PERMISSIONS
    # Oldest first: the queue is a backlog, and the report nobody has looked
    # at for longest is the one to open next.
    default_ordering = "created_at"
    columns = [
        TitleColumn(
            "target_excerpt", label=_("Reported content"), get_url=_inspect_url
        ),
        Column(
            "reason",
            label=_("Reason"),
            accessor=lambda r: r.get_reason_display(),
            sort_key="reason",
        ),
        Column(
            "status",
            label=_("Status"),
            accessor=lambda r: r.get_status_display(),
            sort_key="status",
        ),
        # A plain username column, not UserColumn: the avatar cell resolves
        # `user.wagtail_userprofile` per row, which is one query per report
        # and would make the listing's query count scale with its length.
        Column(
            "reporter",
            label=_("Reporter"),
            accessor=lambda r: r.reporter.get_username(),
        ),
        Column(
            "reporter_trust_level", label=_("Reporter trust"), accessor=_trust_label
        ),
        Column(
            "target_open_reports",
            label=_("Open reports on target"),
            sort_key="target_open_reports",
        ),
        DateColumn("created_at", label=_("Reported"), sort_key="created_at"),
    ]
    list_export = [
        "id",
        "status",
        "reason",
        "detail",
        "target_excerpt",
        "reporter",
        "reporter_trust_level",
        "target_open_reports",
        "created_at",
    ]
    custom_field_preprocess = {
        "reporter_trust_level": {
            "csv": _trust_level_label,
            "xlsx": _trust_level_label,
        }
    }
    export_headings = {
        "id": _("ID"),
        "status": _("Status"),
        "reason": _("Reason"),
        "detail": _("Detail"),
        "target_excerpt": _("Reported content"),
        "reporter": _("Reporter"),
        "reporter_trust_level": _("Reporter trust level"),
        "target_open_reports": _("Open reports on target"),
        "created_at": _("Reported"),
    }

    @cached_property
    def no_results_message(self):
        # Keep the base class's filtered-vs-empty distinction (review of
        # this slice): a moderator who filtered the queue down to nothing
        # should not read that as "nothing is waiting".
        if self.is_searching or self.is_filtering:
            return _("No reports match your filters.")
        return _("No reports are waiting for moderation.")

    def get_filename(self):
        return "forum-moderation-queue-{}".format(
            datetime.date.today().strftime("%Y-%m-%d")
        )

    def order_queryset(self, queryset):
        # Deterministic tie-break (docs/rules/database.md): the base class
        # compiles the chosen column to a bare order_by, and two reports
        # filed in the same instant (a bulk flag, one request filing several)
        # would otherwise flip between pages of the 50-row pagination.
        ordering = self.ordering
        if not ordering:
            return queryset
        if not isinstance(ordering, (list, tuple)):
            ordering = (ordering,)
        return queryset.order_by(*ordering, "pk")

    def get_queryset(self):
        # "How many people flagged this same thing?" per row, as one
        # correlated subquery per target shape rather than a query per row.
        # A report has exactly one of post/message (forum_report_exactly_one_
        # target), so the CASE picks whichever side is populated.
        open_on_post = (
            Report.objects.filter(post=OuterRef("post"), status__in=QUEUE_STATUSES)
            .order_by()
            .values("post")
            .annotate(n=Count("pk"))
            .values("n")
        )
        open_on_message = (
            Report.objects.filter(
                message=OuterRef("message"), status__in=QUEUE_STATUSES
            )
            .order_by()
            .values("message")
            .annotate(n=Count("pk"))
            .values("n")
        )
        self.queryset = (
            Report.objects.filter(status__in=QUEUE_STATUSES)
            .select_related(
                "post",
                "post__topic",  # target_excerpt prefixes the topic title
                "message",
                "message__sender",  # message_summary
                "reporter",
            )
            .annotate(
                # LEFT JOIN: a reporter who has never written (no
                # ForumProfile row yet) still lists, with a blank level.
                reporter_trust_level=F("reporter__wagtail_forum_profile__trust_level"),
                target_open_reports=Case(
                    When(post__isnull=False, then=Subquery(open_on_post)),
                    default=Subquery(open_on_message),
                    output_field=IntegerField(),
                ),
            )
        )
        return super().get_queryset()


class ModerationQueueMenuItem(MenuItem):
    def is_shown(self, request):
        return user_can_view_queue(request.user)


# --- Pending content (todo 423) --------------------------------------------

pending_permission_policy = ModelPermissionPolicy(Post)
PENDING_PERMISSION = "publish"

KIND_NEW_TOPIC = _("New topic")
KIND_REPLY = _("Reply")
KIND_EDIT = _("Edit")


def user_can_moderate_pending(user):
    """Approve publishes a post, so the page opens for whoever may publish
    one: superusers and the host's forum moderator group (``publish_post``)."""
    return pending_permission_policy.user_has_permission(user, PENDING_PERMISSION)


def pending_posts():
    """Every post waiting for a moderator. The one definition the pending
    page, its Approve action and the dashboard count all share.

    - A post that was never published and is still a draft: a new topic's
      opening post or a reply that the spam check held. This also covers a
      post whose moderation step crashed or found no workflow (fail closed),
      which has no workflow state at all, the case the old state-only
      dashboard count missed.
    - The opening post of a topic that was never published, even when the
      post itself is live: the thread is still invisible (todo 422's repair
      case), and approving the row publishes the topic.
    - A post with an active workflow state: a live post whose edit the spam
      check held (the live row keeps its approved body), or the opening post
      of a topic whose own state a host started from the admin.

    A post a moderator took down (published once, now not live, no active
    state) is not pending: a moderator already decided it.
    """
    post_type = ContentType.objects.get_for_model(Post)
    topic_type = ContentType.objects.get_for_model(Topic)
    active = WorkflowState.objects.active()
    post_state = active.filter(
        content_type=post_type, object_id=Cast(OuterRef("pk"), CharField())
    )
    topic_state = active.filter(
        content_type=topic_type, object_id=Cast(OuterRef("topic_id"), CharField())
    )
    return Post.objects.filter(
        Q(live=False, first_published_at__isnull=True)
        | Q(
            is_opening_post=True,
            topic__live=False,
            topic__first_published_at__isnull=True,
        )
        | Exists(post_state)
        | (Q(is_opening_post=True) & Exists(topic_state))
    )


def _pending_kind(post):
    topic = post.topic
    topic_pending = not topic.live and topic.first_published_at is None
    if post.is_opening_post and (topic_pending or post.first_published_at is None):
        return KIND_NEW_TOPIC
    if post.first_published_at is None:
        return KIND_REPLY
    return KIND_EDIT


def _pending_body(post):
    """The body waiting for approval: the latest revision's, not the row's.
    An edit to a live post exists only as a revision (the live row keeps its
    approved body), so the row would show the moderator the wrong text."""
    revision = post.latest_revision
    if revision is not None:
        raw = revision.content.get("body")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except ValueError:
                raw = None
        if isinstance(raw, list):
            # plain_text_excerpt reads only .raw_data.
            return SimpleNamespace(raw_data=raw)
    return post.body


def _pending_excerpt(post):
    # Lazy: api.views imports the models this module's callers import.
    from .api.views import plain_text_excerpt

    return plain_text_excerpt(_pending_body(post), 120) or gettext("(no text)")


def _post_edit_url(post):
    return reverse(Post.snippet_viewset.get_url_name("edit"), args=[post.pk])


def _author_name(post):
    if post.author is None:
        return gettext("(deleted account)")
    return post.author.get_username()


def _author_trust(post):
    return _trust_level_label(post.author_trust_level)


def approve_pending_post(post, user):
    """Publish a pending post as ``user``. For a new topic, publish the topic
    and its opening post together.

    What goes live is the latest revision, never a fresh copy of the row: a
    held edit exists only as a revision (todo 432). Publishing cancels the
    post's active workflow state (``WAGTAIL_WORKFLOW_CANCEL_ON_PUBLISH``), so
    the row leaves the queue and the dashboard count drops.

    The opening post going live already publishes its topic through the
    ``published`` receiver, but only for the same author: that is the IDOR
    guard an API author must not get around. Here a moderator is approving
    the thread, so a topic still unpublished afterwards is published too.
    ``skip_permission_checks``: the caller has checked ``publish`` on Post,
    and approving the thread is that decision.
    """
    with transaction.atomic():
        revision = post.latest_revision or post.save_revision(user=user)
        revision.publish(user=user, skip_permission_checks=True)
        if post.is_opening_post:
            topic = Topic.objects.get(pk=post.topic_id)
            if not topic.live and topic.first_published_at is None:
                topic.save_revision(user=user).publish(
                    user=user, skip_permission_checks=True
                )


class PendingActionsColumn(Column):
    """Approve (a POST form) and, for content never published, Reject: the
    snippet delete view, with its own confirmation page, which returns here.
    A held edit has no Reject: deleting would take down the live post, so a
    moderator opens it from the title link instead."""

    cell_template_name = "wagtail_forum/admin/pending_queue_actions.html"

    def get_cell_context_data(self, instance, parent_context):
        context = super().get_cell_context_data(instance, parent_context)
        request = parent_context.get("request")
        # Cell templates render from a plain dict, not a RequestContext, so
        # {% csrf_token %} needs the token handed over explicitly.
        context["csrf_token"] = get_token(request) if request is not None else ""
        context["approve_url"] = reverse(
            "wagtail_forum_pending:approve", args=[instance.pk]
        )
        context["reject_url"] = None
        kind = _pending_kind(instance)
        if kind != KIND_EDIT:
            # Rejecting a new topic removes the whole thread, not only its body.
            target = instance.topic if kind == KIND_NEW_TOPIC else instance
            delete_url = reverse(
                type(target).snippet_viewset.get_url_name("delete"), args=[target.pk]
            )
            query = urlencode({"next": reverse("wagtail_forum_pending:index")})
            context["reject_url"] = f"{delete_url}?{query}"
        return context


class PendingContentView(ReportView):
    page_title = _("Pending forum content")
    header_icon = "doc-empty-inverse"
    index_url_name = "wagtail_forum_pending:index"
    index_results_url_name = "wagtail_forum_pending:results"
    permission_policy = pending_permission_policy
    permission_required = PENDING_PERMISSION
    # Oldest first: the post that has waited longest is the one to open next.
    default_ordering = "submitted_at"
    columns = [
        TitleColumn(
            "excerpt",
            label=_("Pending content"),
            accessor=_pending_excerpt,
            get_url=_post_edit_url,
        ),
        Column("kind", label=_("Kind"), accessor=_pending_kind),
        Column("topic", label=_("Topic"), accessor=lambda p: p.topic.title),
        Column("author", label=_("Author"), accessor=_author_name),
        Column("author_trust_level", label=_("Author trust"), accessor=_author_trust),
        DateColumn("submitted_at", label=_("Submitted"), sort_key="submitted_at"),
        PendingActionsColumn("actions", label=_("Actions")),
    ]

    @cached_property
    def no_results_message(self):
        return _("No forum content is waiting for moderation.")

    def order_queryset(self, queryset):
        # Deterministic tie-break, as in ModerationQueueView.
        ordering = self.ordering
        if not ordering:
            return queryset
        if not isinstance(ordering, (list, tuple)):
            ordering = (ordering,)
        return queryset.order_by(*ordering, "pk")

    def get_queryset(self):
        self.queryset = (
            pending_posts()
            .select_related("topic", "author", "latest_revision")
            .annotate(
                # LEFT JOIN: an author with no ForumProfile row lists blank.
                author_trust_level=F("author__wagtail_forum_profile__trust_level"),
                submitted_at=F("latest_revision__created_at"),
            )
        )
        return super().get_queryset()


class ApprovePendingView(View):
    """POST only: publish one pending post, and its topic for a new topic.

    The lookup goes through ``pending_posts()``, so a stale form for content
    that was already decided 404s instead of publishing it again."""

    http_method_names = ["post"]

    def post(self, request, pk):
        if not user_can_moderate_pending(request.user):
            raise PermissionDenied
        post = get_object_or_404(
            pending_posts().select_related("topic", "latest_revision"), pk=pk
        )
        approve_pending_post(post, request.user)
        messages.success(
            request, gettext("Published “%(title)s”.") % {"title": post.topic.title}
        )
        return redirect("wagtail_forum_pending:index")


class PendingContentMenuItem(MenuItem):
    def is_shown(self, request):
        return user_can_moderate_pending(request.user)
