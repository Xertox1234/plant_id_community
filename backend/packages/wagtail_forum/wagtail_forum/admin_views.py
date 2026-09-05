"""Moderation queue — a Wagtail admin *report* over open ``Report`` rows.

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
"""

import datetime

import django_filters
from django.db.models import Case, Count, F, IntegerField, OuterRef, Subquery, When
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from wagtail.admin.filters import WagtailFilterSet
from wagtail.admin.menu import MenuItem
from wagtail.admin.ui.tables import Column, DateColumn, TitleColumn
from wagtail.admin.views.reports import ReportView
from wagtail.permission_policies import ModelPermissionPolicy

from .models import Report, TrustLevel

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
    page_title = _("Forum moderation queue")
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
