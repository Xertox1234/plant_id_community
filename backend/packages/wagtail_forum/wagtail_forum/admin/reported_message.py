"""Remove a reported private message from its report (audit 2026-11-24 F84).

Reading the message is the Report inspect page (``ReportInspectView`` in
``wagtail_hooks``). Both log on the report, never with the message's text.
"""

from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseBase
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.views import View
from wagtail.admin.views.generic.base import WagtailAdminTemplateMixin
from wagtail.log_actions import log

from ..models import Report
from ..permissions import report_policy

READ_MESSAGE_LOG_ACTION = "wagtail_forum.report.read_message"
REMOVE_MESSAGE_LOG_ACTION = "wagtail_forum.report.remove_message"


def _may_remove(user: Any) -> bool:
    # The model permission itself: message reports stay with global
    # moderators, so a forum's own moderators never pass.
    return report_policy.has_model_perm(user, ("change",))


def can_remove_reported_message(user: Any, report: Report) -> bool:
    return (
        report.message is not None
        and report.message.removed_at is None
        and _may_remove(user)
    )


class RemoveReportedMessageView(WagtailAdminTemplateMixin, View):
    """GET is the confirmation page, POST removes."""

    http_method_names = ["get", "post"]
    template_name = "wagtail_forum/admin/reported_message_remove.html"
    page_title = _("Remove message")
    header_icon = "bin"

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        if not _may_remove(request.user):
            raise PermissionDenied
        self.report = get_object_or_404(
            Report.objects.select_related("message__sender"), pk=kwargs["pk"]
        )
        if self.report.message is None:
            raise Http404
        viewset = Report.snippet_viewset  # type: ignore[attr-defined]
        self.inspect_url = reverse(
            viewset.get_url_name("inspect"), args=[self.report.pk]
        )
        self.remove_url = reverse(
            viewset.get_url_name("remove_message"), args=[self.report.pk]
        )
        return super().dispatch(request, *args, **kwargs)

    def get_breadcrumbs_items(self) -> list[dict[str, Any]]:
        return [
            *super().get_breadcrumbs_items(),
            {"url": self.inspect_url, "label": str(self.report)},
            {"url": "", "label": self.get_page_title()},
        ]

    def get(self, request: HttpRequest, pk: str) -> HttpResponse:
        if not can_remove_reported_message(request.user, self.report):
            return self._already_removed(request)
        log(instance=self.report, action=READ_MESSAGE_LOG_ACTION, user=request.user)
        response: HttpResponse = self.render_to_response(
            self.get_context_data(
                report=self.report,
                remove_url=self.remove_url,
                cancel_url=self.inspect_url,
            )
        )
        return response

    def post(self, request: HttpRequest, pk: str) -> HttpResponse:
        with transaction.atomic():
            if not self.report.remove_message(request.user):
                return self._already_removed(request)
            log(
                instance=self.report,
                action=REMOVE_MESSAGE_LOG_ACTION,
                user=request.user,
            )
        messages.success(
            request, gettext("The message was removed and its reports closed.")
        )
        return redirect(self.inspect_url)

    def _already_removed(self, request: HttpRequest) -> HttpResponse:
        messages.info(request, gettext("That message was already removed."))
        return redirect(self.inspect_url)
