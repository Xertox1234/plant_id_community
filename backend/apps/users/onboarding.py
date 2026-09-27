"""The mobile onboarding checklist (todo 412, owner decisions 2026-09-26).

Each step is DERIVED from what the user has actually done, so a client can
neither tick a step it did not do nor leave a done step unticked. The only
stored input is ``OnboardingProgress.completed_checklist``: the user
dismissed the card.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from .models import OnboardingProgress, User

logger = logging.getLogger(__name__)

# Order is the order the card shows them. "save_topic" replaced "profile" in
# review (owner, 2026-09-26): the mobile app cannot edit a profile yet, so
# that step could never be done from the card. Todo 455 restores it.
CHECKLIST_STEPS = ("identify_plant", "forum_post", "save_topic")


def onboarding_checklist(
    user: "User", progress: "OnboardingProgress"
) -> Dict[str, Any]:
    """``{"steps": [{"key", "done"}], "complete", "dismissed"}`` for ``user``."""
    from apps.plant_identification.models import PlantIdentificationRequest
    from wagtail_forum.models import Post, TopicBookmark

    done = {
        # Identification results are not persisted (todo 411), so the
        # identify endpoint records the step itself (see
        # record_first_identification). The request table only holds rows
        # from before todo 405 removed persistence: those users count too.
        "identify_plant": bool(progress.first_identification_completed)
        or PlantIdentificationRequest.objects.filter(user=user).exists(),
        # Live posts only: a post held for moderation or spam review is not
        # visible to anyone yet, so it does not count.
        "forum_post": Post.objects.filter(author=user, live=True).exists(),
        "save_topic": TopicBookmark.objects.filter(user=user).exists(),
    }
    steps: List[Dict[str, Any]] = [
        {"key": key, "done": done[key]} for key in CHECKLIST_STEPS
    ]
    return {
        "steps": steps,
        "complete": all(step["done"] for step in steps),
        "dismissed": bool(progress.completed_checklist),
    }


def record_first_identification(user: "User") -> None:
    """Tick "identify a plant" after a successful identification by ``user``.

    Called by the identify endpoint. One conditional UPDATE, a no-op once the
    step is set. The row is created by the users post_save signal; a missing
    one (older accounts) is created here. Never raises: onboarding
    bookkeeping must not fail an identification the user already has a
    result for.
    """
    from .models import OnboardingProgress

    try:
        updated = OnboardingProgress.objects.filter(
            user=user, first_identification_completed=False
        ).update(first_identification_completed=True)
        if not updated and not OnboardingProgress.objects.filter(user=user).exists():
            OnboardingProgress.objects.create(
                user=user, first_identification_completed=True
            )
    except Exception as exc:
        logger.error(
            "[ONBOARDING] Could not record first identification: %s",
            type(exc).__name__,
        )
