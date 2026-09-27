"""The mobile onboarding checklist (todo 412, owner decision 2026-09-26).

Each step is DERIVED from what the user has actually done, so a client can
neither tick a step it did not do nor leave a done step unticked. The only
stored input is ``OnboardingProgress.completed_checklist``: the user
dismissed the card.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Order is the order the card shows them.
CHECKLIST_STEPS = ("identify_plant", "forum_post", "profile")


def onboarding_checklist(user, progress) -> Dict[str, Any]:
    """``{"steps": [{"key", "done"}], "complete", "dismissed"}`` for ``user``."""
    from apps.plant_identification.models import PlantIdentificationRequest
    from wagtail_forum.models import Post

    done = {
        # Identification results are not persisted (todo 411), so the
        # identify endpoint records the step itself; see
        # record_first_identification.
        "identify_plant": bool(progress.first_identification_completed)
        or PlantIdentificationRequest.objects.filter(user=user).exists(),
        "forum_post": Post.objects.filter(author=user).exists(),
        # A short bio or a photo: enough for other members to recognise them.
        "profile": bool((user.bio or "").strip() or user.avatar),
    }
    steps: List[Dict[str, Any]] = [
        {"key": key, "done": done[key]} for key in CHECKLIST_STEPS
    ]
    return {
        "steps": steps,
        "complete": all(step["done"] for step in steps),
        "dismissed": bool(progress.completed_checklist),
    }


def record_first_identification(user) -> None:
    """Tick "identify a plant" after a successful identification by ``user``.

    Called by the identify endpoint. Never raises: onboarding bookkeeping
    must not fail an identification the user already has a result for.
    """
    from .models import OnboardingProgress

    try:
        progress, _ = OnboardingProgress.objects.get_or_create(user=user)
        if not progress.first_identification_completed:
            OnboardingProgress.objects.filter(pk=progress.pk).update(
                first_identification_completed=True
            )
    except Exception as exc:
        logger.error(
            "[ONBOARDING] Could not record first identification: %s",
            type(exc).__name__,
        )
