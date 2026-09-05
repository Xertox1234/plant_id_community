"""Badge evaluation (todo 348): metrics in, idempotent awards out.

Two entry points:

- ``user_metrics(user_id)`` — the closed set of numbers rules can test,
  computed from data the package already maintains (the same four counters
  ``GET me/stats/`` shows). Four cheap queries, independent of history size
  (`post_count` is denormalized, the two COUNTs are indexed, the streak scan
  is bounded by STREAK_LOOKBACK_ROWS).
- ``award_badges_for_user(user_id)`` — grants every active badge whose ANY
  rule the metrics satisfy and the user does not already hold. Idempotent:
  ``UserBadge`` is unique per (user, badge) and awards go through
  ``get_or_create``, so repeated or concurrent evaluation never double-awards.
  Returns the badges awarded by THIS call, so a caller can notify.

Evaluation is triggered from the signal pipeline (``signals.py``: a post's
first publish, a topic's first publish, an accepted answer) inside
``transaction.on_commit`` so an award can never outlive a rolled-back
write, and lazily from ``GET me/stats/`` so a member who qualified before
the engine existed is caught up the first time they look. ``manage.py
award_badges --all`` is the bulk backfill for everyone else.
"""

import logging

from django.db import transaction

logger = logging.getLogger("wagtail_forum")


def user_metrics(user_id: int) -> dict[str, int]:
    """`{metric: int}` for every ``BadgeMetric`` — see ``models/badges.py``."""
    from .models import (
        ForumActivityDate,
        ForumIdentificationAttachment,
        ForumProfile,
        Topic,
    )
    from .models.badges import BadgeMetric

    post_count = (
        ForumProfile.objects.filter(user_id=user_id)
        .values_list("post_count", flat=True)
        .first()
    )
    return {
        BadgeMetric.POSTS: post_count or 0,
        BadgeMetric.SOLUTIONS_ACCEPTED: Topic.objects.filter(
            solved_post__author_id=user_id, live=True
        ).count(),
        BadgeMetric.IDENTIFICATIONS_SHARED: ForumIdentificationAttachment.objects.filter(
            topic__author_id=user_id, topic__live=True
        ).count(),
        BadgeMetric.STREAK_DAYS: ForumActivityDate.streak_for_user(user_id),
    }


def award_badges_for_user(user_id: int | None) -> list:
    """Award every active badge `user_id` now qualifies for. Returns the
    list of ``Badge`` rows newly awarded by this call (empty when nothing
    changed — the common case)."""
    from .models.badges import Badge, UserBadge

    if user_id is None:
        return []
    candidates = list(
        Badge.objects.filter(is_active=True)
        .exclude(awards__user_id=user_id)
        .prefetch_related("rules")
    )
    if not candidates:
        return []
    metrics = user_metrics(user_id)
    awarded = []
    for badge in candidates:
        if not any(rule.is_met(metrics) for rule in badge.rules.all()):
            continue
        _, created = UserBadge.objects.get_or_create(user_id=user_id, badge=badge)
        if created:
            awarded.append(badge)
    if awarded:
        from .signals import badge_awarded, notify

        for badge in awarded:
            notify(badge_awarded, sender=Badge, user_id=user_id, badge=badge)
    return awarded


BOTANIST_SLUG = "botanist"


def botanist_badge_rule():
    """The seeded Botanist badge's identifications rule, or None when the
    host has not seeded it (then the BADGE_BOTANIST_* settings still apply,
    as before the engine). One query, joined to the badge for its name."""
    from .models.badges import BadgeMetric, BadgeRule

    return (
        BadgeRule.objects.filter(
            badge__slug=BOTANIST_SLUG,
            badge__is_active=True,
            metric=BadgeMetric.IDENTIFICATIONS_SHARED,
        )
        .select_related("badge")
        .first()
    )


def award_after_commit(user_id: int | None) -> None:
    """Schedule an evaluation for when the surrounding write commits — the
    shape every signal-site caller wants (a rolled-back publish must not
    award). Wagtail's publish runs inside a transaction, so this really does
    defer to commit; with no transaction open Django runs the hook at once,
    inline in the request — and under `pytest.mark.django_db` the callback
    defers and is rolled back UNRUN, so an endpoint's pinned query count
    cannot see the evaluation's cost (a `Badge` query, plus the four metric
    queries only when there is something left to award). Not free; cheap."""
    if user_id is None:
        return
    transaction.on_commit(lambda: award_badges_for_user(user_id))
