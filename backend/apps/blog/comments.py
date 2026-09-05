"""Blog comment protection (todo 352): the forum's anti-abuse services
applied to the pre-existing, previously unguarded `BlogComment` flow.

Service-level reuse only — `wagtail_forum`'s spam backend and trust levels,
never its `Topic`/`Post` models (they are forum-shaped; reusing them would
pollute forum counters, search and notifications).
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING

from apps.core.ratelimit import ratelimit  # 429-mapped by the custom exception handler
from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from rest_framework import serializers

from . import constants

if TYPE_CHECKING:  # pragma: no cover
    from .models import BlogPostPage

logger = logging.getLogger(__name__)


def _rate(name: str):
    """Resolved at request time so tests can override_settings the map."""

    def resolve(group: str, request) -> str:
        overrides = getattr(settings, "BLOG_RATELIMITS", {})
        return {**constants.DEFAULT_BLOG_RATELIMITS, **overrides}[name]

    return resolve


def comment_ratelimit(name: str, method: str = "POST"):
    """`@comment_ratelimit("comment_create")` on a ViewSet action: per-user
    key, resolved rate, 429 (not 403) via apps.core.exceptions."""
    return ratelimit(key="user", rate=_rate(name), method=method)


class _CommentSpamAdapter:
    """Shapes plain comment text into the object the forum spam backends
    read (`.title`, iterable `.body` of `.value`s) — a bare string would be
    iterated character by character (see wagtail_forum's DM adapter)."""

    title = ""
    is_opening_post = False

    def __init__(self, text: str):
        self.body = [SimpleNamespace(value=text)]


def auto_approve_trust_level() -> int:
    return getattr(
        settings,
        "BLOG_COMMENT_AUTO_APPROVE_TRUST_LEVEL",
        constants.DEFAULT_COMMENT_AUTO_APPROVE_TRUST_LEVEL,
    )


def decide_approval(user: AbstractBaseUser, content: str) -> tuple[bool, str]:
    """(is_approved, reason). Staff always pass. Below the trust threshold the
    comment is held WITHOUT calling the spam backend — the outcome is fixed,
    and the configured backend may be a billable LLM call (same reasoning as
    wagtail_forum's `_screen_dm_body`). At or above it, the configured
    backend screens the text and a flag holds the comment. Everything held
    lands in the existing admin queue."""
    from wagtail_forum.models import ForumProfile
    from wagtail_forum.spam import get_spam_backend

    if user.is_staff:
        return True, "staff"
    trust = ForumProfile.for_user(user).trust_level
    if trust < auto_approve_trust_level():
        logger.info(
            "[MODERATION] blog comment held (trust %s < %s): user=%s",
            trust,
            auto_approve_trust_level(),
            user.pk,
        )
        return False, "trust"
    result = get_spam_backend().check(_CommentSpamAdapter(content))
    if not result.is_clean:
        logger.info(
            "[MODERATION] blog comment held (spam): user=%s reason=%s",
            user.pk,
            result.reason,
        )
        return False, f"spam: {result.reason}"
    return True, "trusted"


def models_q_visible_to(user: AbstractBaseUser | None):
    """Approved comments, plus the caller's own pending ones — the one
    visibility predicate every non-staff read on this surface uses."""
    from django.db.models import Q

    visible = Q(is_approved=True)
    if user is not None and user.is_authenticated:
        visible |= Q(author=user)
    return visible


def resolve_parent(parent_id, post: "BlogPostPage", user: AbstractBaseUser):
    """The comment a reply targets, or None for a top-level comment.

    Scoped to what the caller can SEE on THIS post (approved, or their own):
    an id from another post, a nonexistent id and another member's pending
    comment all get the same generic error, so the endpoint is not an oracle
    for which comment ids exist. Thread depth is one level (a reply cannot be
    replied to) and a pending comment — only ever the caller's own here —
    cannot be replied to until approved.
    """
    from .models import BlogComment

    generic = {"parent": "That comment is not on this post."}
    if parent_id in (None, ""):
        return None
    try:
        parent_id = int(parent_id)
    except (TypeError, ValueError):
        raise serializers.ValidationError(generic)
    parent = (
        BlogComment.objects.filter(pk=parent_id, post=post)
        .filter(models_q_visible_to(user))
        .first()
    )
    if parent is None:
        raise serializers.ValidationError(generic)
    if parent.parent_id is not None:
        raise serializers.ValidationError(
            {"parent": "Replies are one level deep — reply to the top-level comment."}
        )
    if not parent.is_approved:
        raise serializers.ValidationError(
            {
                "parent": "That comment is awaiting moderation and cannot be replied to yet."
            }
        )
    return parent
