"""Create/edit screens for forum categories and forums (todo 666; spec
2026-10-28 §5), with the safe delete and change-type flows (todo 667).

A plain ``ModelViewSet`` (no revisions, no page tree) under the existing
*Forum* admin menu.

- **delete** asks first: a forum's topics are moved to another forum or
  deleted, a category's forums move to another category
  (``forum_delete.ForumDeleteView``). ``Topic.board`` and ``Forum.parent``
  stay ``PROTECT``, so nothing is ever lost to a cascade.
- **changing the type** is its own screen (``change-type/<pk>/``, a button on
  the edit page), because a forum must be emptied of topics before it can be
  a category. The type field stays disabled on the edit form, so a forged
  POST value there is ignored by the form, not merely hidden.
- **link** rows: the type and its URL field arrive with slice 670, so a new
  row can only be a category or a forum.

Validation is the model's own (``Forum.clean`` via the ModelForm's
``full_clean``, plus the partial slug ``UniqueConstraint``s through
``validate_constraints``), so a category with a parent or a forum without a
category is refused server-side whatever the browser sends.
"""

from __future__ import annotations

import json
from typing import Any

from django import forms
from django.urls import path, reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.panels import FieldPanel, ObjectList, TabbedInterface
from wagtail.admin.views import generic
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.admin.widgets.button import Button

from ..models import Forum
from ..services.forum_structure import next_position
from .forum_delete import ForumChangeTypeView, ForumDeleteView

# The types a new row may take in this slice (links: slice 670).
CREATABLE_TYPES = (Forum.CATEGORY, Forum.FORUM)


class ForumAdminForm(WagtailAdminModelForm):
    """The General tab: type, category, name, slug, description."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        type_field = self.fields["forum_type"]
        parent_field = self.fields["parent"]
        parent_field.label = _("Category")
        parent_field.help_text = _(
            "The category this forum is listed under. A category has none."
        )
        # The panel's w-rules controller hides the picker while "Category" is
        # chosen; hiding alone still posts the picked value, so a create
        # switched to Category after choosing one would fail on a field the
        # user can no longer see. Disabling the select keeps it out of the
        # POST. A forged parent is still refused by Forum.clean.
        parent_field.widget.attrs.update(
            {
                "data-w-rules-target": "enable",
                "data-w-rules-enable": json.dumps({"forum_type": [Forum.CATEGORY]}),
                "data-w-rules-enable-match": "not",
            }
        )
        allowed = list(CREATABLE_TYPES)
        if self.instance.pk:
            # Changing the type is its own screen ("Change type" in the
            # header menu): a forum must be emptied of topics first. A
            # disabled field keeps the instance's value whatever is posted.
            type_field.disabled = True
            type_field.help_text = _(
                "Use “Change type” in the actions menu to change it."
            )
            if self.instance.forum_type not in allowed:
                allowed.append(self.instance.forum_type)
            if self.instance.forum_type == Forum.CATEGORY:
                # A category never has a parent: nothing to choose.
                parent_field.disabled = True
                parent_field.widget = forms.HiddenInput()
        labels = dict(Forum.FORUM_TYPE_CHOICES)
        type_field.choices = [(value, labels[value]) for value in allowed]
        # Blank slug = derived from the name (see clean_slug).
        self.fields["slug"].required = False
        self.fields["slug"].help_text = _(
            "Used in the forum's web address. Left blank, it is made from the name."
        )

    def clean_slug(self) -> str:
        slug = self.cleaned_data.get("slug") or ""
        if not slug:
            slug = slugify(self.cleaned_data.get("name") or "")
        if not slug:
            raise forms.ValidationError(
                _("Enter a slug, or a name it can be made from.")
            )
        return slug

    def clean(self) -> dict[str, Any]:
        cleaned: dict[str, Any] = super().clean()
        slug = cleaned.get("slug")
        forum_type = cleaned.get("forum_type")
        if slug and forum_type:
            # The partial UniqueConstraints would report a duplicate only as
            # a non-field "Constraint ... is violated." error; say it on the
            # slug field instead. Category slugs are unique among categories,
            # forum and link slugs among each other (spec §4).
            clashes = Forum.objects.filter(slug=slug)
            if forum_type == Forum.CATEGORY:
                clashes = clashes.filter(forum_type=Forum.CATEGORY)
            else:
                clashes = clashes.exclude(forum_type=Forum.CATEGORY)
            if self.instance.pk:
                clashes = clashes.exclude(pk=self.instance.pk)
            if clashes.exists():
                self.add_error("slug", _("This slug is already in use."))
        return cleaned

    def save(self, commit: bool = True) -> Forum:
        instance: Forum = super().save(commit=False)
        if instance._state.adding:
            # New rows go to the end of their level (categories among
            # categories, forums within their category) rather than to the
            # top at position 0. Reordering itself is slice 668.
            instance.position = next_position(instance.parent_id)
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ForumEditView(generic.EditView):
    """Adds "Change type" to the edit page's actions menu."""

    change_type_url_name: str | None = None

    @property
    def header_more_buttons(self) -> list[Any]:
        buttons: list[Any] = list(super().header_more_buttons)
        if self.change_type_url_name and self.object.forum_type != Forum.LINK:
            buttons.append(
                Button(
                    _("Change type"),
                    url=reverse(self.change_type_url_name, args=(self.object.pk,)),
                    icon_name="resubmit",
                    priority=15,
                )
            )
        return buttons


class ForumViewSet(ModelViewSet):
    model = Forum
    edit_view_class = ForumEditView
    delete_view_class = ForumDeleteView
    icon = "list-ul"
    menu_label = _("Categories & forums")
    menu_order = 50
    add_to_admin_menu = False  # listed inside the Forum menu group
    name = "forum_forums"
    url_prefix = "forum/forums"
    url_namespace = "wagtail_forum_forums"
    list_display = ["name", "forum_type", "parent", "slug", "is_hidden"]
    list_filter = ["forum_type", "is_hidden"]
    search_fields = ["name", "slug"]
    copy_view_enabled = False
    inspect_view_enabled = False
    # No drag reorder in this slice: the structure tree is slice 668.
    sort_order_field = None

    def get_edit_view_kwargs(self, **kwargs: Any) -> dict[str, Any]:
        view_kwargs: dict[str, Any] = super().get_edit_view_kwargs(
            change_type_url_name=self.get_url_name("change_type"), **kwargs
        )
        return view_kwargs

    edit_handler = TabbedInterface(
        [
            ObjectList(
                [
                    FieldPanel("forum_type"),
                    FieldPanel(
                        "parent",
                        # Wagtail's bundled `w-rules` controller (no inline
                        # script: the production CSP has no 'unsafe-inline')
                        # hides the category picker while "Category" is the
                        # chosen type. "not" rather than ["forum"]: on edit
                        # the type select is disabled, so it is absent from
                        # the form data and the picker must stay shown.
                        attrs={
                            "data-controller": "w-rules",
                            "data-action": "change@document->w-rules#resolve",
                            "data-w-rules-target": "show",
                            "data-w-rules": json.dumps(
                                {"forum_type": [Forum.CATEGORY]}
                            ),
                            "data-w-rules-show-match": "not",
                        },
                    ),
                    FieldPanel("name"),
                    FieldPanel("slug"),
                    FieldPanel("description"),
                    FieldPanel("is_hidden"),
                ],
                heading=_("General"),
            ),
        ],
        base_form_class=ForumAdminForm,
    )

    def get_urlpatterns(self) -> list[Any]:
        return [
            *super().get_urlpatterns(),
            path(
                f"change-type/<{self.pk_path_converter}:pk>/",
                self.change_type_view,
                name="change_type",
            ),
        ]

    @property
    def change_type_view(self) -> Any:
        return ForumChangeTypeView.as_view(
            edit_url_name=self.get_url_name("edit"),
            change_type_url_name=self.get_url_name("change_type"),
        )
