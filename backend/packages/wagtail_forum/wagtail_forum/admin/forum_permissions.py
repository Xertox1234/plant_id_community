"""The *Permissions* screen of a category, forum or link (todo 675).

A principal × role grid (guests, all members, every Django group), plus
"Copy permissions from [row]", which overwrites this row's grants exactly
after a confirmation step. Behind the Forum ``change`` permission, like the
edit form it is opened from.

A pseudo-group left on *Default* has no grant row and gets its default role
(Standard for members, Read only for guests); a group left on *No grant*
adds nothing (``services.forum_permissions``).
"""

from __future__ import annotations

from typing import Any

from django import forms
from django.contrib import messages
from django.contrib.auth.models import Group
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.generic import TemplateView
from wagtail.admin.views.generic.base import WagtailAdminTemplateMixin
from wagtail.admin.views.generic.permissions import PermissionCheckedMixin

from ..models import Forum, ForumGrant, ForumRole
from ..services.forum_permissions import DEFAULT_ROLES, copy_permissions, set_grant

TEMPLATE = "wagtail_forum/admin/forum_permissions.html"
ACTION_SAVE = "save"
ACTION_COPY = "copy"


def _field_name(principal: str, group: Group | None = None) -> str:
    return f"group_{group.pk}" if group is not None else principal


class ForumGrantsForm(forms.Form):
    """One radio row per principal; the value is a role, or "" for none."""

    def __init__(self, *args: Any, forum: Forum, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.forum = forum
        current = {
            _field_name(grant.principal, grant.group): grant.role
            for grant in ForumGrant.objects.filter(forum=forum).select_related("group")
        }
        roles = list(ForumRole.choices)
        labels = dict(ForumRole.choices)
        self.rows: list[tuple[str, str, Group | None]] = [
            (ForumGrant.ANONYMOUS, str(_("Guests")), None),
            (ForumGrant.MEMBERS, str(_("All members")), None),
        ]
        self.rows += [
            (ForumGrant.GROUP, group.name, group)
            for group in Group.objects.order_by("name")
        ]
        for principal, label, group in self.rows:
            name = _field_name(principal, group)
            if group is None:
                blank = _("Default (%(role)s)") % {
                    "role": labels[DEFAULT_ROLES[principal]]
                }
            else:
                blank = _("No grant")
            self.fields[name] = forms.ChoiceField(
                label=label,
                choices=[("", blank), *roles],
                required=False,
                initial=current.get(name, ""),
                widget=forms.RadioSelect,
            )

    def save(self) -> None:
        with transaction.atomic():
            for principal, _label, group in self.rows:
                role = self.cleaned_data.get(_field_name(principal, group)) or None
                set_grant(self.forum, principal, role, group=group)


class CopyPermissionsForm(forms.Form):
    source = forms.ModelChoiceField(
        label=gettext_lazy("Copy permissions from"),
        queryset=Forum.objects.none(),
    )
    confirm = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args: Any, forum: Forum, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["source"].queryset = Forum.objects.exclude(pk=forum.pk).order_by(  # type: ignore[attr-defined]
            "parent__position", "position", "pk"
        )


class ForumPermissionsView(
    PermissionCheckedMixin, WagtailAdminTemplateMixin, TemplateView
):
    model = Forum
    permission_required = "change"
    template_name = TEMPLATE
    page_title = gettext_lazy("Permissions")
    header_icon = "lock"
    edit_url_name: str | None = None
    permissions_url_name: str | None = None

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any) -> None:
        super().setup(request, *args, **kwargs)
        self.object = get_object_or_404(Forum, pk=kwargs["pk"])

    def get_page_subtitle(self) -> str:
        return str(self.object)

    def _url(self) -> str:
        return reverse(str(self.permissions_url_name), args=(self.object.pk,))

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context: dict[str, Any] = super().get_context_data(**kwargs)
        grants_form = kwargs.get("grants_form") or ForumGrantsForm(forum=self.object)
        context.update(
            {
                "object": self.object,
                "grants_form": grants_form,
                "grant_rows": [
                    grants_form[_field_name(principal, group)]
                    for principal, _label, group in grants_form.rows
                ],
                "role_count": len(ForumRole.choices) + 1,
                "copy_form": kwargs.get("copy_form")
                or CopyPermissionsForm(forum=self.object),
                "action_url": self._url(),
                "edit_url": reverse(str(self.edit_url_name), args=(self.object.pk,)),
                "action_save": ACTION_SAVE,
                "action_copy": ACTION_COPY,
            }
        )
        return context

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if request.POST.get("action") == ACTION_COPY:
            return self._copy(request)
        form = ForumGrantsForm(request.POST, forum=self.object)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(grants_form=form))
        form.save()
        messages.success(
            request, _("Permissions for “%(name)s” saved.") % {"name": self.object.name}
        )
        return HttpResponseRedirect(self._url())

    def _copy(self, request: HttpRequest) -> HttpResponse:
        form = CopyPermissionsForm(request.POST, forum=self.object)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(copy_form=form))
        source = form.cleaned_data["source"]
        if not form.cleaned_data.get("confirm"):
            # Overwriting is not undoable: say what will happen first.
            return TemplateResponse(
                request,
                "wagtail_forum/admin/forum_permissions_copy_confirm.html",
                {
                    **self.get_context_data(),
                    "source": source,
                    "source_grant_count": ForumGrant.objects.filter(
                        forum=source
                    ).count(),
                },
            )
        copied = copy_permissions(source, self.object)
        messages.success(
            request,
            _("“%(target)s” now has the %(count)d permission(s) of “%(source)s”.")
            % {"target": self.object.name, "count": copied, "source": source.name},
        )
        return HttpResponseRedirect(self._url())
