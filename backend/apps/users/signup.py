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
