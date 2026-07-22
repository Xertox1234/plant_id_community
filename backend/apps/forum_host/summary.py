"""Host-side AI thread summarization for the forum (todo 255 slice 3 / H14).

Premium-gated (IsPremiumUser), Celery-generated, content-hash cached. Lives
host-side (not the wagtail_forum package) so it may import the blog app's AI
helpers and the users app's premium permission; the package forbids apps.*
imports (test_reusability.py).

The endpoint never calls the LLM in-request: on a cache miss it enqueues a
Celery task and returns 202 {"status": "pending"}; the client polls until 200
{"status": "ready", "summary": ...}.

See docs/superpowers/specs/2026-07-22-forum-thread-summarization-design.md.
"""

import hashlib
import logging

from apps.blog.services.ai_cache_service import AICacheService
from apps.users.permissions import IsPremiumUser
from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from wagtail_forum.api.views import plain_text_excerpt
from wagtail_forum.models import Post, Topic

from . import constants
from .api import _throttled
from .tasks import generate_topic_summary

logger = logging.getLogger(__name__)


def build_summary_source(topic) -> tuple[str, int]:
    """Return ``(canonical content string, live post count)`` for a topic.

    The content string folds in the prompt version, the topic title, and each
    live post's id, ``updated_at`` and plain-text excerpt in chronological
    order, so the AICacheService content hash changes whenever the thread
    changes (a new or edited post) or the prompt is revised — a cheap, correct
    cache-invalidation key. Bounded to ``SUMMARY_MAX_CHARS`` to cap tokens/cost.

    ``Post.body`` is a StreamField; ``plain_text_excerpt`` extracts clean text
    via ``raw_data`` without the per-post image bulk-fetch that iterating the
    resolved StreamValue would trigger.
    """
    posts = list(Post.objects.filter(topic=topic, live=True).order_by("created_at"))
    parts = [f"v{constants.SUMMARY_PROMPT_VERSION}", f"title: {topic.title}"]
    for post in posts:
        excerpt = plain_text_excerpt(
            post.body, constants.SUMMARY_PER_POST_EXCERPT_CHARS
        )
        parts.append(f"[{post.id}@{post.updated_at.isoformat()}] {excerpt}")
    content = "\n".join(parts)[: constants.SUMMARY_MAX_CHARS]
    return content, len(posts)


def _pending_lock_key(content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    return f"{constants.SUMMARY_PENDING_LOCK_PREFIX}:{digest}"


@_throttled("topic_summary", "GET")
class TopicSummaryView(APIView):
    """GET a cached AI summary of a topic thread (premium perk)."""

    permission_classes = [IsPremiumUser]
    versioning_class = None  # opt out of NamespaceVersioning, like package views

    @extend_schema(
        responses={200: dict, 202: dict},
        description=(
            "Premium AI summary of a topic thread. 200 with the summary when "
            "ready (or status 'too_short' for a thread below the minimum post "
            "count); 202 status 'pending' while a background task generates it "
            "— poll until 200. Requires a premium account."
        ),
    )
    def get(self, request, topic_id):
        topic = Topic.objects.filter(pk=topic_id, live=True).first()
        if topic is None:
            return Response(
                {"detail": "Topic not found."}, status=status.HTTP_404_NOT_FOUND
            )

        content, post_count = build_summary_source(topic)
        if post_count < constants.SUMMARY_MIN_POSTS:
            return Response({"status": "too_short", "post_count": post_count})

        cached = AICacheService.get_cached_response(
            constants.SUMMARY_CACHE_FEATURE, content
        )
        if cached is not None:
            return Response({"status": "ready", **cached})

        # Cache miss: enqueue at most one task per thread state. cache.add is
        # atomic (sets only if the key is absent), so a burst of polls during a
        # slow generation bounds duplicate LLM spend to a single task; the lock
        # expires by TTL (no explicit release needed on the happy path — a
        # populated cache short-circuits above before this runs again).
        lock_key = _pending_lock_key(content)
        if cache.add(lock_key, 1, constants.SUMMARY_PENDING_LOCK_TTL):
            try:
                generate_topic_summary.delay(topic_id)
            except Exception:
                # Broker outage: release the lock so a later poll can retry, and
                # degrade to a normal pending response the client re-polls.
                logger.exception(
                    "[CELERY] Failed to enqueue topic summary for topic %s",
                    topic_id,
                )
                cache.delete(lock_key)
        return Response({"status": "pending"}, status=status.HTTP_202_ACCEPTED)
