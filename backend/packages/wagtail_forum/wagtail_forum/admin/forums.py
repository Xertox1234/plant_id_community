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
- **link** rows (todo 670): a row that sends readers to an http(s) URL,
  optionally counting clicks. The URL is required for a link and cleared
  for any other type (``Forum.clean``).

Validation is the model's own (``Forum.clean`` via the ModelForm's
``full_clean``, plus the partial slug ``UniqueConstraint``s through
``validate_constraints``), so a category with a parent or a forum without a
category is refused server-side whatever the browser sends.
"""

from __future__ import annotations

import json
from typing import Any

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.db import transaction
from django.urls import path, reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.panels import FieldPanel, ObjectList, TabbedInterface
from wagtail.admin.views import generic
from wagtail.admin.viewsets.model import ModelViewSet
from wagtail.admin.widgets.button import Button

from ..models import Forum, ForumModerator
from ..models.boards import FORUM_PASSWORD_MAX_LENGTH
from ..services.forum_permissions import keep_out_whoever_the_category_kept_out
from ..services.forum_structure import next_position
from .forum_delete import ForumChangeTypeView, ForumDeleteView
from .forum_permissions import ForumPermissionsView
from .forum_structure_tree import TREE_TEMPLATE, ForumMoveView, ForumStructureView

# The types a new row may take.
CREATABLE_TYPES = (Forum.CATEGORY, Forum.FORUM, Forum.LINK)


class ForumAdminForm(WagtailAdminModelForm):
    """The General tab (type, category, name, slug, description, password)
    plus the Posting, Pruning and Moderators tabs (todos 674, 678-680).
    Permissions have their own screen (``forum_permissions``)."""

    # Todo 680: write-only. A blank field keeps the current password; the
    # hash is never rendered back.
    new_password = forms.CharField(
        label=_("Password"),
        required=False,
        max_length=FORUM_PASSWORD_MAX_LENGTH,
        strip=False,
        widget=forms.PasswordInput(
            render_value=False, attrs={"autocomplete": "new-password"}
        ),
        help_text=_(
            "Readers must enter it to open this forum. Leave blank to keep "
            "the current one. Prefer permissions: a password is shared."
        ),
    )
    clear_password = forms.BooleanField(label=_("Remove the password"), required=False)
    # Todo 674: moderators are users (by username) or groups.
    moderator_users = forms.CharField(
        label=_("Moderator users"),
        required=False,
        help_text=_(
            "Usernames, separated by commas. They moderate this forum's "
            "topics, posts and reports in the admin (they also need admin access)."
        ),
    )
    moderator_groups = forms.ModelMultipleChoiceField(
        label=_("Moderator groups"),
        queryset=Group.objects.order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

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
        self.fields["link_url"].help_text = _(
            "Links only: where the row sends readers (http or https)."
        )
        self.fields["track_clicks"].help_text = _(
            "Links only: count each click through the forum's redirect."
        )
        self.fields["slug"].required = False
        self.fields["slug"].help_text = _(
            "Used in the forum's web address. Left blank, it is made from the name."
        )
        if self.instance.pk:
            moderators = ForumModerator.objects.filter(forum=self.instance)
            self.initial["moderator_users"] = ", ".join(
                sorted(
                    moderators.filter(user__isnull=False).values_list(
                        "user__username", flat=True
                    )
                )
            )
            self.initial["moderator_groups"] = list(
                moderators.filter(group__isnull=False).values_list(
                    "group_id", flat=True
                )
            )
            if self.instance.password_hash:
                self.fields["new_password"].help_text = _(
                    "This forum has a password. Enter a new one to change it."
                )

    def clean_moderator_users(self) -> list[Any]:
        raw = self.cleaned_data.get("moderator_users") or ""
        names = list(dict.fromkeys(n.strip() for n in raw.split(",") if n.strip()))
        users = list(get_user_model().objects.filter(username__in=names))
        missing = set(names) - {u.get_username() for u in users}
        if missing:
            raise forms.ValidationError(
                _("No user is called: %(names)s")
                % {"names": ", ".join(sorted(missing))}
            )
        return users

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
        # Round-2 review: a category ignores a password, and a link with one
        # could never be unlocked (only forum rows have the unlock endpoint).
        if (
            cleaned.get("new_password")
            and (forum_type or self.instance.forum_type) != Forum.FORUM
        ):
            self.add_error("new_password", _("Only a forum can have a password."))
        return cleaned

    def save(self, commit: bool = True) -> Forum:
        instance: Forum = super().save(commit=False)
        if instance._state.adding:
            # New rows go to the end of their level (categories among
            # categories, forums within their category) rather than to the
            # top at position 0. The structure tree reorders (todo 668).
            instance.position = next_position(instance.parent_id)
        # Moved to another category here rather than in the tree: whoever
        # the old category kept out stays out (round-2 review), applied with
        # the m2m step so it also runs when the caller saves later.
        self._left_category = None
        if (
            not instance._state.adding
            and "parent" in self.changed_data
            and self.initial.get("parent")
        ):
            self._left_category = Forum.objects.filter(
                pk=self.initial["parent"]
            ).first()
        password = self.cleaned_data.get("new_password")
        if self.cleaned_data.get("clear_password"):
            instance.password_hash = ""
        elif password:
            instance.password_hash = make_password(password)
        if commit:
            instance.save()
            self.save_m2m()
        return instance

    def _save_m2m(self) -> None:
        super()._save_m2m()  # type: ignore[misc]
        self._save_moderators()
        left = getattr(self, "_left_category", None)
        if left is not None:
            keep_out_whoever_the_category_kept_out(self.instance, left)

    def _save_moderators(self) -> None:
        forum = self.instance
        users = self.cleaned_data.get("moderator_users") or []
        groups = list(self.cleaned_data.get("moderator_groups") or [])
        with transaction.atomic():
            existing = ForumModerator.objects.filter(forum=forum)
            existing.filter(user__isnull=False).exclude(user__in=users).delete()
            existing.filter(group__isnull=False).exclude(group__in=groups).delete()
            for user in users:
                ForumModerator.objects.get_or_create(forum=forum, user=user)
            for group in groups:
                ForumModerator.objects.get_or_create(forum=forum, group=group)


class ForumCreateView(generic.CreateView):
    """Prefills the type and category from the query string, so the tree's
    "Add forum" (``?forum_type=forum&parent=<id>``) and "Add category" open
    the form ready. Only a starting value: the form still validates both."""

    def get_initial(self) -> dict[str, Any]:
        initial: dict[str, Any] = super().get_initial()
        forum_type = self.request.GET.get("forum_type")
        if forum_type in CREATABLE_TYPES:
            initial["forum_type"] = forum_type
        parent = self.request.GET.get("parent", "")
        if parent.isdecimal():
            initial["parent"] = int(parent)
        return initial


class ForumEditView(generic.EditView):
    """Adds "Permissions" and "Change type" to the edit page's actions menu."""

    change_type_url_name: str | None = None
    permissions_url_name: str | None = None

    @property
    def header_more_buttons(self) -> list[Any]:
        buttons: list[Any] = list(super().header_more_buttons)
        if self.permissions_url_name:
            buttons.append(
                Button(
                    _("Permissions"),
                    url=reverse(self.permissions_url_name, args=(self.object.pk,)),
                    icon_name="lock",
                    priority=10,
                )
            )
        if self.change_type_url_name:
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
    # The landing screen is the structure tree (todo 668), not a listing:
    # every row is on it, in the order the forum shows them.
    index_view_class = ForumStructureView
    index_template_name = TREE_TEMPLATE
    add_view_class = ForumCreateView
    edit_view_class = ForumEditView
    delete_view_class = ForumDeleteView
    icon = "list-ul"
    menu_label = _("Categories & forums")
    menu_order = 50
    add_to_admin_menu = False  # listed inside the Forum menu group
    name = "forum_forums"
    url_prefix = "forum/forums"
    url_namespace = "wagtail_forum_forums"
    copy_view_enabled = False
    inspect_view_enabled = False
    # Wagtail's own drag reorder handles one flat list; the tree's move
    # endpoint (``move/``) handles both levels and moves between categories.
    sort_order_field = None

    def get_edit_view_kwargs(self, **kwargs: Any) -> dict[str, Any]:
        view_kwargs: dict[str, Any] = super().get_edit_view_kwargs(
            change_type_url_name=self.get_url_name("change_type"),
            permissions_url_name=self.get_url_name("permissions"),
            **kwargs,
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
                    FieldPanel("link_url"),
                    FieldPanel("track_clicks"),
                    FieldPanel("new_password"),
                    FieldPanel("clear_password"),
                ],
                heading=_("General"),
            ),
            # Todo 678: plain text, each line a paragraph in the composer.
            ObjectList([FieldPanel("topic_template")], heading=_("Posting")),
            # Todo 679: `manage.py prune_forums` (days since last post only).
            ObjectList(
                [
                    FieldPanel("prune_enabled"),
                    FieldPanel("prune_days_since_last_post"),
                    FieldPanel("prune_pinned"),
                    FieldPanel("prune_polls"),
                ],
                heading=_("Pruning"),
            ),
            # Todo 674: who moderates this forum through the Wagtail admin.
            ObjectList(
                [FieldPanel("moderator_users"), FieldPanel("moderator_groups")],
                heading=_("Moderators"),
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
            path("move/", self.move_view, name="move"),
            path(
                f"permissions/<{self.pk_path_converter}:pk>/",
                self.permissions_view,
                name="permissions",
            ),
        ]

    def get_index_view_kwargs(self, **kwargs: Any) -> dict[str, Any]:
        view_kwargs: dict[str, Any] = super().get_index_view_kwargs(
            move_url_name=self.get_url_name("move"), **kwargs
        )
        return view_kwargs

    @property
    def move_view(self) -> Any:
        return self.construct_view(
            ForumMoveView, index_url_name=self.get_url_name("index")
        )

    @property
    def permissions_view(self) -> Any:
        return ForumPermissionsView.as_view(
            edit_url_name=self.get_url_name("edit"),
            permissions_url_name=self.get_url_name("permissions"),
        )

    @property
    def change_type_view(self) -> Any:
        return ForumChangeTypeView.as_view(
            edit_url_name=self.get_url_name("edit"),
            change_type_url_name=self.get_url_name("change_type"),
        )
