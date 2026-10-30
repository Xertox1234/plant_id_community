"""Per-forum moderators in the Wagtail admin (todo 674).

A ``ForumModerator`` (a user, or a group the user is in) moderates one forum
through the existing admin screens: the pending queue, the reports queue and
the Topic, Post and Report snippets, scoped to their forums (owner decision
2026-10-30). Global moderators, whose Wagtail model permissions cover every
forum, are unchanged.

``ForumScopedPermissionPolicy`` gives a forum moderator the moderation
actions on a snippet model (never add or delete) and narrows instance checks
and listings to their forums. Wagtail's generic object views look objects up
by primary key without asking the policy about the instance, so
``scope_object_urls`` wraps every object URL of a snippet viewset with the
same check: an object outside the moderator's forums is 403.

Every bypass of the forum check asks for the model permission the view itself
needs (round-1 review): a forum-A moderator who also holds, say, ``view_post``
everywhere may inspect any post but still edits only forum A's, and a user
whose model permissions alone satisfy a view (``delete_post`` on the delete
view, any of add/change/delete/view on the listing) keeps exactly what the
plain model policy gave them.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import wraps
from typing import Any

from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied
from django.db.models import Model, QuerySet
from wagtail.permission_policies import ModelPermissionPolicy

from .services.forum_permissions import moderated_forum_ids

# What a forum moderator may do on a snippet in their forums.
MODERATOR_ACTIONS = frozenset(
    {"view", "change", "publish", "unpublish", "lock", "unlock"}
)

# Model permissions that let a user list a snippet (Wagtail's IndexView).
LIST_ACTIONS = ("add", "change", "delete", "view")

# The model permissions that satisfy each object view on their own (Wagtail
# 8 snippet views' ``permission_required``/``any_permission_required``). Only
# a user holding one of them skips the forum check; anyone else reaches the
# view through the moderator extension and must be in the object's forum. An
# unlisted URL needs ``change``, the strictest a moderator is given.
OBJECT_URL_ACTIONS: dict[str, tuple[str, ...]] = {
    "delete": ("delete",),
    "copy": ("add",),
    "inspect": LIST_ACTIONS,
    "history": ("add", "change", "delete"),
    "history_results": ("add", "change", "delete"),
    "unpublish": ("publish",),
    "revisions_unschedule": ("publish",),
    "lock": ("lock",),
    # The user who locked it may unlock it without ``unlock``: UnlockView
    # checks that itself, and they locked it in a forum the check passes.
    "unlock": ("unlock",),
}
DEFAULT_OBJECT_URL_ACTIONS = ("change",)

_MODERATED_CACHE_ATTR = "_wagtail_forum_moderated_forum_ids"


def forum_ids_moderated_by(user: Any) -> frozenset[int]:
    """The forums ``user`` moderates (as a user or by group), cached on the
    user object for the request."""
    if user is None or not getattr(user, "is_authenticated", False):
        return frozenset()
    cached = getattr(user, _MODERATED_CACHE_ATTR, None)
    if cached is None:
        cached = frozenset(moderated_forum_ids(user).values_list("forum_id", flat=True))
        setattr(user, _MODERATED_CACHE_ATTR, cached)
    return cached


def moderates_any_forum(user: Any) -> bool:
    return bool(forum_ids_moderated_by(user))


class ForumScopedPermissionPolicy(ModelPermissionPolicy):
    """The model's own permissions, plus the moderation actions for the
    moderators of the forum each instance is in (``forum_path``)."""

    def __init__(self, model: type[Model], forum_path: str, **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        self.forum_path = forum_path

    def _model_perm(self, user: Any, action: str) -> bool:
        """The model permission itself, never the moderator extension (the
        base class's helpers call back into the overrides below)."""
        return bool(user.has_perm(self._get_permission_name(action)))

    def has_model_perm(self, user: Any, actions: Iterable[str]) -> bool:
        """``user`` holds one of ``actions`` on the model itself (every forum),
        never through the moderator extension."""
        return any(self._model_perm(user, action) for action in actions)

    def user_has_permission(self, user: Any, action: str) -> bool:
        if self._model_perm(user, action):
            return True
        return action in MODERATOR_ACTIONS and moderates_any_forum(user)

    def user_has_any_permission(self, user: Any, actions: Iterable[str]) -> bool:
        return any(self.user_has_permission(user, action) for action in actions)

    def user_has_permission_for_instance(
        self, user: Any, action: str, instance: Model
    ) -> bool:
        if self._model_perm(user, action):
            return True
        if action not in MODERATOR_ACTIONS:
            return False
        return self.instance_in_moderated_forum(user, instance)

    def user_has_any_permission_for_instance(
        self, user: Any, actions: Iterable[str], instance: Model
    ) -> bool:
        return any(
            self.user_has_permission_for_instance(user, action, instance)
            for action in actions
        )

    def instance_in_moderated_forum(self, user: Any, instance: Model) -> bool:
        return (
            type(instance)
            ._default_manager.filter(
                pk=instance.pk,
                **{f"{self.forum_path}__in": forum_ids_moderated_by(user)},
            )
            .exists()
        )

    def scope(self, queryset: QuerySet[Any], user: Any) -> QuerySet[Any]:
        """The listing: ``queryset`` narrowed to ``user``'s forums when only
        their moderator role lets them list it. A user who moderates no forum,
        or whose model permissions alone let them list every row (Wagtail's
        index needs any of add/change/delete/view), sees what the plain model
        policy shows."""
        if not moderates_any_forum(user) or self.has_model_perm(user, LIST_ACTIONS):
            return queryset
        return queryset.filter(
            **{f"{self.forum_path}__in": forum_ids_moderated_by(user)}
        )

    def instances_user_has_permission_for(
        self, user: Any, action: str
    ) -> QuerySet[Any]:
        manager = self.model._default_manager
        qs: QuerySet[Any]
        if self._model_perm(user, action):
            qs = manager.all()
        elif action not in MODERATOR_ACTIONS:
            qs = manager.none()
        else:
            qs = manager.filter(
                **{f"{self.forum_path}__in": forum_ids_moderated_by(user)}
            )
        return qs


def _policies() -> tuple[ForumScopedPermissionPolicy, ...]:
    from .models import Post, Report, Topic

    return (
        ForumScopedPermissionPolicy(Topic, "board"),
        ForumScopedPermissionPolicy(Post, "topic__board"),
        ForumScopedPermissionPolicy(Report, "post__topic__board"),
    )


# The snippet policies (registered in wagtail_hooks) and the reports queue's.
topic_policy, post_policy, report_policy = _policies()


def scope_object_urls(
    urlpatterns: list[Any], policy: ForumScopedPermissionPolicy
) -> list[Any]:
    """Wrap every URL of ``urlpatterns`` that names an object (a ``pk``
    kwarg) so a user without the model permission that URL's view needs
    (``OBJECT_URL_ACTIONS``) gets 403 for an object outside their forums."""

    def guard(view: Callable[..., Any], actions: tuple[str, ...]) -> Callable[..., Any]:
        @wraps(view)
        def wrapped(request: Any, *args: Any, **kwargs: Any) -> Any:
            pk = kwargs.get("pk")
            user = request.user
            if pk is not None and not policy.has_model_perm(user, actions):
                visible = policy.model._default_manager.filter(
                    pk=unquote(str(pk)),
                    **{f"{policy.forum_path}__in": forum_ids_moderated_by(user)},
                )
                if not visible.exists():
                    raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    for pattern in urlpatterns:
        if "<" in str(pattern.pattern) and "pk" in str(pattern.pattern):
            actions = OBJECT_URL_ACTIONS.get(
                getattr(pattern, "name", None) or "", DEFAULT_OBJECT_URL_ACTIONS
            )
            pattern.callback = guard(pattern.callback, actions)
    return urlpatterns
