"""The forum structure tree (todo 668; spec 2026-10-28 §5): the landing
screen of *Forum → Categories & forums*.

Categories in position order, each with its forums and links, and row
actions (edit, add forum, delete). Staff with the ``change`` permission
rearrange it two ways, both through the one move endpoint
(:class:`ForumMoveView`):

- **drag and drop** (a pinned SortableJS, ``static/wagtail_forum/js/``):
  reorder categories, reorder forums within a category, move a forum to
  another category. An illegal drop gets a 4xx and the row snaps back.
- **move buttons** (up, down, and "move to category"): plain forms that work
  without JavaScript and from the keyboard; with JavaScript they post the
  same way and keep focus on the button.

The endpoint takes ``forum_id``, ``parent_id`` (blank: the category level)
and ``position``; ``services.forum_structure.move_forum`` checks the type and
parent rules and renumbers both levels in one transaction. Moving a forum to
another category changes no topic URL (they carry ids only), so nothing
redirects.
"""

from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import BooleanField, ExpressionWrapper
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views import View
from django.views.generic import TemplateView
from wagtail.admin.views.generic.base import WagtailAdminTemplateMixin
from wagtail.admin.views.generic.permissions import PermissionCheckedMixin
from wagtail.admin.widgets.button import HeaderButton

from ..models import Forum
from ..services.forum_permissions import hidden_q, is_hidden_for_everyone
from ..services.forum_structure import move_forum

# A position past any level's end: move_forum clamps it to "last".
END = 2**31 - 1

TREE_TEMPLATE = "wagtail_forum/admin/forum_structure.html"


class ForumStructureView(
    PermissionCheckedMixin, WagtailAdminTemplateMixin, TemplateView
):
    """The tree. Anyone the menu admits sees it; only ``change`` gets the
    drag handles and move buttons."""

    model = Forum
    any_permission_required = ["add", "change", "delete", "view"]
    template_name = TREE_TEMPLATE
    # ModelViewSet reads this off its index view class for the ``results/``
    # route, which builds the same class; the tree has no separate results.
    results_template_name = TREE_TEMPLATE
    page_title = gettext_lazy("Categories & forums")
    header_icon = "list-ul"
    index_url_name: str | None = None
    add_url_name: str | None = None
    edit_url_name: str | None = None
    delete_url_name: str | None = None
    move_url_name: str | None = None

    def get_breadcrumbs_items(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = [
            *super().get_breadcrumbs_items(),
            {"url": "", "label": self.get_page_title()},
        ]
        return items

    @property
    def header_buttons(self) -> list[Any]:
        if not self.add_url_name or not self.user_has_permission("add"):
            return []
        return [
            HeaderButton(
                _("Add category"),
                url=f"{reverse(self.add_url_name)}?forum_type={Forum.CATEGORY}",
                icon_name="plus",
            )
        ]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context: dict[str, Any] = super().get_context_data(**kwargs)
        # `is_hidden`: neither guests nor members may list the row (its
        # grants, todo 676), the tree's "Hidden" badge.
        rows = list(
            Forum.objects.annotate(
                is_hidden=ExpressionWrapper(hidden_q(), output_field=BooleanField())
            ).order_by("position", "pk")
        )
        children: dict[int, list[Forum]] = {}
        for row in rows:
            if row.parent_id is not None:
                children.setdefault(row.parent_id, []).append(row)
        categories = [row for row in rows if row.forum_type == Forum.CATEGORY]
        tree = []
        for index, category in enumerate(categories):
            forums = children.get(category.pk, [])
            tree.append(
                {
                    "row": category,
                    "index": index,
                    "is_first": index == 0,
                    "is_last": index == len(categories) - 1,
                    "forums": [
                        {
                            "row": forum,
                            "index": i,
                            "is_first": i == 0,
                            "is_last": i == len(forums) - 1,
                        }
                        for i, forum in enumerate(forums)
                    ],
                }
            )
        context.update(
            {
                "tree": tree,
                "categories": categories,
                "can_change": self.user_has_permission("change"),
                "can_add": self.user_has_permission("add"),
                "can_delete": self.user_has_permission("delete"),
                "add_url": reverse(str(self.add_url_name)),
                "edit_url_name": self.edit_url_name,
                "delete_url_name": self.delete_url_name,
                "move_url": reverse(str(self.move_url_name)),
                "forum_type_forum": Forum.FORUM,
            }
        )
        return context


class ForumMoveView(PermissionCheckedMixin, View):
    """``POST {forum_id, parent_id, position}``, behind the ``change``
    permission and Django's CSRF check (never exempt).

    An ``X-Requested-With: XMLHttpRequest`` request (the tree's script) gets
    JSON: 200 on a move, 400 with ``message`` for an illegal one, 404 for a
    row that is gone. A plain form post (the move buttons without
    JavaScript) is redirected back to the tree with the same message."""

    model = Forum
    permission_required = "change"
    http_method_names = ["post"]
    index_url_name: str | None = None

    def post(self, request: HttpRequest) -> HttpResponse:
        wants_json = request.headers.get("x-requested-with") == "XMLHttpRequest"
        try:
            forum_id, parent_id, position = _move_fields(request)
            forum = move_forum(forum_id, parent_id, position)
        except Forum.DoesNotExist:
            return self._refused(
                request, wants_json, _("That row no longer exists."), 404
            )
        except ValidationError as error:
            return self._refused(request, wants_json, " ".join(error.messages), 400)
        message = _("“%(name)s” moved.") % {"name": forum.name}
        if wants_json:
            return JsonResponse(
                {
                    "message": message,
                    "forum_id": forum.pk,
                    "parent_id": forum.parent_id,
                    "position": forum.position,
                    "is_hidden": is_hidden_for_everyone(forum),
                }
            )
        messages.success(request, message)
        return HttpResponseRedirect(f"{self._tree_url()}#forum-row-{forum.pk}")

    def _tree_url(self) -> str:
        return reverse(str(self.index_url_name))

    def _refused(
        self, request: HttpRequest, wants_json: bool, message: str, status: int
    ) -> HttpResponse:
        if wants_json:
            return JsonResponse({"message": message}, status=status)
        messages.error(request, message)
        return HttpResponseRedirect(self._tree_url())


def _move_fields(request: HttpRequest) -> tuple[int, int | None, int]:
    """``forum_id`` is a required integer. A blank or missing ``parent_id``
    is the category level; a blank or missing ``position`` is the end of the
    level (the "move to category" form, which cannot know it without
    JavaScript)."""
    data = request.POST
    try:
        forum_id = int(data["forum_id"])
        raw_parent = (data.get("parent_id") or "").strip()
        parent_id = int(raw_parent) if raw_parent else None
        raw_position = (data.get("position") or "").strip()
        position = int(raw_position) if raw_position else END
    except (KeyError, ValueError) as error:
        raise ValidationError(_("The move was not understood.")) from error
    return forum_id, parent_id, position
