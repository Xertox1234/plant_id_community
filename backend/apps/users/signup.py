"""Centralized signup side-effects shared by every account-creation path.

Standard registration, OAuth, and Firebase token-exchange all create a user and
must then apply the same post-creation side-effects. The default "My Plants"
collection used to be created inline in registration and OAuth but was MISSING
from the Firebase path, so Firebase users landed without a default collection
(todo 221 / finding M7). This module is the single hook all three call, so the
side-effect can no longer drift between paths.

Username-collision handling is deliberately NOT centralized here: registration
uses a user-chosen username, OAuth resolves collisions with an incrementing
suffix, and Firebase uses a UUID suffix whose format is pinned by
`test_username_collision_handling`. Those are intentionally different and are not
"side effects" of an already-created user.
"""

import logging

from django.contrib.auth.models import Group

from .models import UserPlantCollection

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION_NAME = "My Plants"
DEFAULT_COLLECTION_DESCRIPTION = "My personal plant collection"


def create_default_plant_collection(user) -> UserPlantCollection:
    """Create the user's default "My Plants" collection.

    Idempotent (``get_or_create``) so it is safe to call from any path and from a
    retried request without creating duplicates. Returns the collection.
    """
    collection, created = UserPlantCollection.objects.get_or_create(
        user=user,
        name=DEFAULT_COLLECTION_NAME,
        defaults={
            "description": DEFAULT_COLLECTION_DESCRIPTION,
            "is_public": True,
        },
    )
    if created:
        logger.info("[SIGNUP] Created default plant collection for user id=%s", user.id)
    return collection


def join_forum_members_group(user) -> None:
    """Add the user to the "Forum Members" Wagtail permission group.

    This is what makes ``wagtail.permission_policies.collections.
    CollectionOwnershipPermissionPolicy`` treat the user as able to upload to
    the forum's image collection and, per that policy's ownership rule, to
    edit/delete images they personally uploaded there (see
    ``apps.forum_host.bootstrap._ensure_forum_image_permissions``, which
    grants the group ``add_image``/``choose_image`` on that collection).

    ``group.user_set.add()`` is a no-op if the user is already a member, so
    this is safe to call unconditionally on every signup path. The group
    itself is normally created by that same post_migrate bootstrap, but
    ``get_or_create`` here is a defensive fallback in case a request reaches
    this before that signal has run (e.g. a fresh test database signing up a
    user ahead of post_migrate) — mirrors why ``create_default_plant_
    collection`` above uses ``get_or_create`` rather than assuming its target
    already exists.
    """
    group, _ = Group.objects.get_or_create(name="Forum Members")
    group.user_set.add(user)
