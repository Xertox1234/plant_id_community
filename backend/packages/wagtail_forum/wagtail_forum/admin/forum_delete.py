"""Safe delete and change-type screens for forum rows (todo 667; spec
2026-10-28 §2).

- **Delete** a forum: choose *move its topics to [forum]* or *delete its
  topics*; a category: choose the category its forums move to. A row with
  nothing under it deletes on a plain confirm.
- **Change type**: between category, forum and link. A forum's topics get
  the same move-or-delete choice first, so no category or link ever holds a
  topic; a category is refused while it holds forums and then needs its
  category; becoming a link needs its URL; leaving link clears it (todo 670).

Every target is checked server-side twice: the form's choice querysets admit
only a forum other than this one (topics) or a category other than this one
(forums), so a forged id for itself, a category, a link or a missing row is
an invalid choice; and ``services.forum_structure`` re-checks it inside the
transaction.
"""

from __future__ import annotations

from typing import Any

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from wagtail.admin.utils import get_valid_next_url_from_request
from wagtail.admin.views import generic
from wagtail.admin.views.generic.base import BaseObjectMixin, WagtailAdminTemplateMixin
from wagtail.admin.views.generic.permissions import PermissionCheckedMixin
from wagtail.log_actions import log

from ..models import Forum, ForumSubscription, Topic
from ..models.boards import LINK_URL_SCHEMES
from ..services import forum_structure

# The log action of a type change (registered in ``wagtail_hooks``, todo 729).
CHANGE_TYPE_LOG_ACTION = "wagtail_forum.forum.change_type"

TOPICS_ACTION_CHOICES = [
    (forum_structure.MOVE, _("Move the topics to another forum")),
    (forum_structure.DELETE, _("Delete the topics and all their posts")),
]


class _ForumRowForm(forms.Form):
    """Builds the fields a row needs: the topics choice for a forum that
    holds topics, the category target for a category that holds forums."""

    def __init__(
        self, *args: Any, forum: Forum, can_delete_topics: bool = True, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.forum = forum
        self.topic_count = Topic.objects.filter(board=forum).count()
        self.child_count = Forum.objects.filter(parent=forum).count()
        # Members with a watch level here; the rows cascade with the forum.
        self.subscriber_count = ForumSubscription.objects.filter(forum=forum).count()
        if forum.forum_type == Forum.FORUM and self.topic_count:
            self.fields["topics_action"] = forms.ChoiceField(
                label=_("Topics"),
                # Without the delete permission only "move" is offered, so a
                # posted "delete" is an invalid choice.
                choices=(
                    TOPICS_ACTION_CHOICES
                    if can_delete_topics
                    else TOPICS_ACTION_CHOICES[:1]
                ),
                widget=forms.RadioSelect,
            )
            self.fields["target"] = forms.ModelChoiceField(
                label=_("Move the topics to"),
                queryset=Forum.objects.filter(forum_type=Forum.FORUM)
                .exclude(pk=forum.pk)
                .order_by("parent__position", "position", "pk"),
                required=False,
            )

    def clean(self) -> dict[str, Any]:
        cleaned: dict[str, Any] = super().clean() or {}
        if (
            cleaned.get("topics_action") == forum_structure.MOVE
            and not cleaned.get("target")
            and "target" not in self.errors
        ):
            self.add_error("target", _("Choose the forum to move the topics to."))
        return cleaned

    def _add_category_target(self, label: Any) -> None:
        self.fields["target_category"] = forms.ModelChoiceField(
            label=label,
            queryset=Forum.objects.filter(forum_type=Forum.CATEGORY)
            .exclude(pk=self.forum.pk)
            .order_by("position", "pk"),
        )


class ForumDeleteForm(_ForumRowForm):
    def __init__(self, *args: Any, forum: Forum, **kwargs: Any) -> None:
        super().__init__(*args, forum=forum, **kwargs)
        if forum.forum_type == Forum.CATEGORY and self.child_count:
            self._add_category_target(_("Move its forums to"))


# The type a row becomes when the form names none: the conversion todo 667
# shipped first (forum <-> category), and a link becomes a forum.
DEFAULT_NEW_TYPE = {
    Forum.FORUM: Forum.CATEGORY,
    Forum.CATEGORY: Forum.FORUM,
    Forum.LINK: Forum.FORUM,
}


class ForumChangeTypeForm(_ForumRowForm):
    def __init__(self, *args: Any, forum: Forum, **kwargs: Any) -> None:
        super().__init__(*args, forum=forum, **kwargs)
        labels = dict(Forum.FORUM_TYPE_CHOICES)
        self.fields["to_type"] = forms.ChoiceField(
            label=_("New type"),
            choices=[
                (value, labels[value])
                for value in (Forum.CATEGORY, Forum.FORUM, Forum.LINK)
                if value != forum.forum_type
            ],
            initial=DEFAULT_NEW_TYPE[forum.forum_type],
            required=False,
            widget=forms.RadioSelect,
        )
        # The new type first: the fields after it depend on it.
        self.order_fields(["to_type"])
        if forum.forum_type == Forum.CATEGORY:
            self._add_category_target(_("Category the forum or link belongs to"))
        self.fields["link_url"] = forms.URLField(
            label=_("Link URL"),
            required=False,
            max_length=Forum._meta.get_field("link_url").max_length,
            validators=[URLValidator(schemes=list(LINK_URL_SCHEMES))],
            help_text=_("Only when it becomes a link: http or https."),
        )
        self.fields["track_clicks"] = forms.BooleanField(
            label=_("Track clicks"),
            required=False,
            initial=True,
            help_text=_("Only when it becomes a link."),
        )

    @property
    def new_type(self) -> str:
        cleaned = getattr(self, "cleaned_data", None) or {}
        return str(cleaned.get("to_type") or DEFAULT_NEW_TYPE[self.forum.forum_type])

    def clean_to_type(self) -> str:
        return str(
            self.cleaned_data.get("to_type") or DEFAULT_NEW_TYPE[self.forum.forum_type]
        )

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()
        if self.forum.forum_type == Forum.CATEGORY and self.child_count:
            raise ValidationError(
                _(
                    "This category still holds forums. Move or delete them "
                    "before changing its type."
                )
            )
        if (
            cleaned.get("to_type") == Forum.LINK
            and not cleaned.get("link_url")
            and "link_url" not in self.errors
        ):
            self.add_error("link_url", _("A link needs a URL."))
        return cleaned


def _can_delete_topics(view: PermissionCheckedMixin) -> bool:
    """Deleting a forum's topics needs the forum ``delete`` permission and
    the topic one: forum-structure rights alone never wipe content."""
    return bool(view.user_has_permission("delete")) and view.request.user.has_perm(
        f"{Topic._meta.app_label}.delete_topic"
    )


def _row_ref(forum: Forum | None) -> dict[str, Any] | None:
    """A forum row as log data: enough to name it after it is deleted."""
    if forum is None:
        return None
    return {"id": forum.pk, "name": forum.name}


def _add_service_error(form: forms.Form, error: ValidationError) -> None:
    for message in error.messages:
        form.add_error(None, message)


# Raised when a topic, forum or slug appears between the form's checks and
# the write (PROTECT FKs, the per-board slug constraint): the transaction is
# rolled back, so the admin is asked to retry instead of seeing a 500.
_CHANGED_MEANWHILE = (ProtectedError, IntegrityError)
_CHANGED_MEANWHILE_MESSAGE = _(
    "The forum changed while you were on this page. Check it and try again."
)


class ForumDeleteView(generic.DeleteView):
    """Wagtail's delete confirm with the move-or-delete choice."""

    form_class = ForumDeleteForm
    template_name = "wagtail_forum/admin/forum_delete.html"

    def get_usage_url(self) -> None:
        # Wagtail's usage summary marks a row with PROTECTed references
        # (Topic.board, Forum.parent) as undeletable and hides the form; the
        # whole point of this view is to clear those references first.
        return None

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = super().get_form_kwargs()
        kwargs["forum"] = self.object
        kwargs["can_delete_topics"] = _can_delete_topics(self)
        return kwargs

    @property
    def confirmation_message(self) -> str:
        return str(_("Are you sure you want to delete “%(name)s”?")) % {
            "name": self.object.name
        }

    # What the delete did to the rows under it, for the log entry.
    log_data: dict[str, Any]

    def delete_action(self) -> None:
        # One entry per forum delete, with the count and the move-or-delete
        # choice, instead of the registry action's bare ``wagtail.delete``
        # (todo 729). Logged first, while the row still exists; permission
        # is already checked by PermissionCheckedMixin.
        log(
            instance=self.object,
            action="wagtail.delete",
            user=self.request.user,
            deleted=True,
            data=self.log_data,
        )
        self.action_class(
            self.object, user=self.request.user, log_action=False
        ).execute(skip_permission_checks=True)

    def _empty(self, data: dict[str, Any]) -> dict[str, Any]:
        """Move or delete what the row holds; returns the log data."""
        forum = self.object
        if forum.forum_type == Forum.CATEGORY:
            target = data.get("target_category")
            moved = forum_structure.empty_category(forum, target)
            return {
                "forum_type": forum.forum_type,
                "forums_moved": moved,
                "forums_moved_to": _row_ref(target) if moved else None,
            }
        action = data.get("topics_action")
        target = data.get("target")
        count = forum_structure.empty_forum(forum, action, target)
        moved_topics = bool(count) and action == forum_structure.MOVE
        subscribers = ForumSubscription.objects.filter(forum=forum).count()
        carried = (
            forum_structure.carry_subscriptions(forum, target)
            if moved_topics and target is not None
            else 0
        )
        return {
            "forum_type": forum.forum_type,
            "topic_count": count,
            "topics_action": action if count else None,
            "topics_moved_to": _row_ref(target) if moved_topics else None,
            "subscriber_count": subscribers,
            "subscriptions_carried": carried,
        }

    def form_valid(self, form: forms.Form) -> HttpResponse:
        success_url = self.get_success_url()
        data = form.cleaned_data
        try:
            with transaction.atomic():
                self.log_data = self._empty(data)
                self.delete_action()
        except ValidationError as error:
            _add_service_error(form, error)
            response: HttpResponse = self.form_invalid(form)
            return response
        except _CHANGED_MEANWHILE:
            form.add_error(None, _CHANGED_MEANWHILE_MESSAGE)
            changed: HttpResponse = self.form_invalid(form)
            return changed
        messages.success(self.request, self.get_success_message())
        hook_response: HttpResponse | None = self.run_after_hook()
        if hook_response is not None:
            return hook_response
        return HttpResponseRedirect(success_url)


class ForumChangeTypeView(
    PermissionCheckedMixin, WagtailAdminTemplateMixin, BaseObjectMixin, FormView
):
    """Category, forum and link conversions, behind the ``change``
    permission. Deleting the topics on the way also needs the forum and topic
    ``delete`` permissions."""

    model = Forum
    permission_required = "change"
    form_class = ForumChangeTypeForm
    template_name = "wagtail_forum/admin/forum_change_type.html"
    page_title = _("Change type")
    header_icon = "list-ul"
    edit_url_name: str | None = None
    change_type_url_name: str | None = None

    def get_page_subtitle(self) -> str:
        return str(self.object)

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = super().get_form_kwargs()
        kwargs["forum"] = self.object
        kwargs["can_delete_topics"] = _can_delete_topics(self)
        return kwargs

    def get_success_url(self) -> str:
        return get_valid_next_url_from_request(self.request) or reverse(
            str(self.edit_url_name), args=(self.object.pk,)
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context: dict[str, Any] = super().get_context_data(**kwargs)
        context["object"] = self.object
        context["action_url"] = reverse(
            str(self.change_type_url_name), args=(self.object.pk,)
        )
        context["cancel_url"] = self.get_success_url()
        return context

    def form_valid(self, form: ForumChangeTypeForm) -> HttpResponse:
        data = form.cleaned_data
        old_type = self.object.forum_type
        had_topics = bool(form.topic_count) and old_type == Forum.FORUM
        try:
            with transaction.atomic():
                changed = forum_structure.change_type(
                    self.object,
                    form.new_type,
                    action=data.get("topics_action"),
                    target=data.get("target"),
                    category=data.get("target_category"),
                    link_url=data.get("link_url") or "",
                    track_clicks=bool(data.get("track_clicks")),
                )
                moved = had_topics and data.get("topics_action") == forum_structure.MOVE
                log(
                    instance=changed,
                    action=CHANGE_TYPE_LOG_ACTION,
                    user=self.request.user,
                    data={
                        "from_type": old_type,
                        "to_type": form.new_type,
                        "topic_count": form.topic_count if had_topics else 0,
                        "topics_action": (
                            data.get("topics_action") if had_topics else None
                        ),
                        "topics_moved_to": (
                            _row_ref(data.get("target")) if moved else None
                        ),
                    },
                )
        except ValidationError as error:
            _add_service_error(form, error)
            return self.form_invalid(form)
        except _CHANGED_MEANWHILE:
            form.add_error(None, _CHANGED_MEANWHILE_MESSAGE)
            return self.form_invalid(form)
        messages.success(
            self.request,
            str(_("“%(name)s” is now a %(type)s."))
            % {
                "name": self.object.name,
                "type": dict(Forum.FORUM_TYPE_CHOICES)[form.new_type].lower(),
            },
        )
        return HttpResponseRedirect(self.get_success_url())
