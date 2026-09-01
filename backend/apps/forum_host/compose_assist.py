"""AI composer assist for the forum (todo 275 / M14).

POST /api/v1/forum/compose/assist/ — premium-only draft improvement. Takes the
composer's current draft, returns a cleaned-up plain-text rewrite. The client
decides whether to accept it; nothing is persisted here.

Host-side (not the ``wagtail_forum`` package) so it may import the blog app's AI
helpers and the users app's premium permission; the package forbids ``apps.*``
imports (``test_reusability.py``).

Why bespoke rather than wagtail-ai's editor machinery: verified at code level in
the 2026-07-11 audit (M14) — wagtail-ai's prompt panels are ``/cms/``-admin-only
and do not transfer to the end-user TipTap composer. Only the backend
``generate_ai_text`` substrate applies.

Cost posture (this is the most expensive AI feature per call — interactive and
uncacheable in practice, since every draft differs). Four independent bounds:

1. ``FORUM_COMPOSE_ASSIST_ENABLED`` (default False) → 503. Ships dormant, so
   merging spends nothing; enabling is a deliberate per-deployment act.
2. ``IsPremiumUser`` → 403 for everyone else.
3. ``compose_assist`` throttle (20/h, per-user) → 429 per account.
4. ``COMPOSE_BUDGET_LIMIT`` (200/h, forum-wide, its own counter) → 429 in
   aggregate, so N premium accounts cannot multiply into unbounded spend.

Unlike the summary endpoint this calls the LLM in-request: there is nothing to
poll for (the user is staring at their draft), and a 202-then-poll flow would
double the round-trips for a sub-20s call. The deadline is enforced by
``COMPOSE_TIMEOUT_SECONDS`` forwarded into the provider SDK.
"""

import logging

from apps.blog.services.ai_rate_limiter import AIRateLimiter
from apps.blog.wagtail_ai_v3_integration import generate_ai_text
from apps.users.permissions import IsPremiumUser
from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from wagtail_forum.api.versioning import UnversionedForumAPIMixin

from . import constants
from .api import _throttled
from .html_text import flatten_html

logger = logging.getLogger(__name__)

# Machine-readable discriminators on the 503 body. The endpoint returns 503 for
# THREE different reasons and only one of them is permanent, so the status code
# alone is not enough for a client to decide whether retrying can ever work:
#
#   CODE_DISABLED    - the deployment has the feature off. Permanent for the
#                      session; a client should stop offering the action.
#   CODE_UNAVAILABLE - the provider errored, timed out, or returned an empty
#                      completion. TRANSIENT; the next call may well succeed.
#
# The web client latched on the bare 503 and permanently disabled its toolbar
# button on the first provider blip (todo 275 code review). Codes, not statuses,
# because the transient/permanent split is a product fact, not an HTTP one.
CODE_DISABLED = "disabled"
CODE_UNAVAILABLE = "unavailable"


def _draft_text(raw: str) -> str:
    """Flatten the composer's HTML draft to the plain text the LLM will see.

    The composer posts TipTap HTML. Tags are stripped rather than forwarded:
    markup is pure token cost, and a model shown HTML tends to answer in HTML —
    which this endpoint's contract forbids (the client inserts the reply as a
    TEXT node). The draft's eventual publish goes through the package's own
    nh3 allowlist. Block-boundary reconstruction and entity unescaping — the
    todo 275 review's high finding — live in ``html_text.flatten_html``, shared
    with the RAG blog chunker.
    """
    return flatten_html(raw)


@_throttled("compose_assist", "POST")
class ComposeAssistView(UnversionedForumAPIMixin, APIView):
    """POST a draft, get an AI-improved plain-text rewrite (premium perk)."""

    permission_classes = [IsPremiumUser]

    @extend_schema(
        request=dict,
        responses={200: dict, 400: dict, 429: dict, 503: dict},
        description=(
            "Premium AI draft improvement for the forum composer. Body: "
            "{'text': '<the current draft, HTML or plain text>'}. Returns 200 "
            "{'text': '<plain-text rewrite>'}. 400 for a blank draft or one "
            "over COMPOSE_MAX_INPUT_CHARS; 429 when the per-user throttle or "
            "the forum-wide AI budget is exhausted (with Retry-After); 503 when "
            "composer assist is disabled for this deployment or the provider is "
            "unavailable. Requires a premium account. Nothing is persisted — the "
            "client decides whether to accept the rewrite.\n\n"
            "A 503 body carries a 'code' discriminating the two cases, because "
            "only one of them is worth giving up on: 'disabled' (the deployment "
            "has the feature off — permanent, stop offering the action) versus "
            "'unavailable' (provider error, timeout, or empty completion — "
            "TRANSIENT, a retry may succeed). Clients must branch on 'code', not "
            "on the 503 status."
        ),
    )
    def post(self, request):
        if not getattr(settings, "FORUM_COMPOSE_ASSIST_ENABLED", False):
            return Response(
                {"detail": "AI composer assist is not enabled.", "code": CODE_DISABLED},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Guard the CONTAINER before the value: a top-level JSON array, string or
        # number makes request.data a list/str/int, so `.get` would raise
        # AttributeError — which DRF's handler does not cover, giving a 500 instead
        # of a 400 (security review, todo 275).
        if not isinstance(request.data, dict) or not isinstance(
            request.data.get("text"), str
        ):
            return Response(
                {"detail": "Field 'text' is required and must be a string."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        raw = request.data["text"]
        text = _draft_text(raw)
        if not text:
            return Response(
                {"detail": "Nothing to improve — the draft is empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(text) > constants.COMPOSE_MAX_INPUT_CHARS:
            # Rejected, never truncated: a rewrite of only the first N chars
            # would look complete while silently dropping the rest of the post.
            return Response(
                {
                    "detail": (
                        "Draft is too long for AI assist "
                        f"({len(text)} of {constants.COMPOSE_MAX_INPUT_CHARS} "
                        "characters). Try improving one section at a time."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Peek, never check-and-increment: budget is consumed only after the
        # provider actually returned, so a sustained outage cannot drain the cap
        # via failed attempts and lock premium users out of a working feature.
        if not AIRateLimiter.peek_budget(
            constants.COMPOSE_BUDGET_CACHE_KEY, constants.COMPOSE_BUDGET_LIMIT
        ):
            return Response(
                {
                    "detail": (
                        "AI assist is temporarily at capacity. "
                        "Please try again later."
                    )
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(AIRateLimiter.TTL)},
            )

        prompt = constants.COMPOSE_PROMPT_TEMPLATE.format(content=text)
        try:
            reply = generate_ai_text(
                prompt,
                alias=constants.COMPOSE_ALIAS,
                timeout=constants.COMPOSE_TIMEOUT_SECONDS,
            )
        except Exception:
            # Degrade, never 500: the composer keeps working without assist.
            logger.exception("[ERROR] Forum compose assist provider call failed")
            return Response(
                {
                    "detail": "AI assist is unavailable right now.",
                    "code": CODE_UNAVAILABLE,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Charged here — on any call that RETURNED, before the emptiness check —
        # not only on a usable rewrite. An empty completion still reached the
        # provider and was still billed; skipping the charge would let a provider
        # stuck emitting blanks be called indefinitely without ever tripping the
        # forum-wide cap, which is the exact abuse case that cap exists for.
        # Mirrors find_similar_topics, which charges an empty result set for the
        # same reason. Only the exception path above stays uncharged (it may never
        # have reached the provider at all).
        AIRateLimiter.consume_budget(
            constants.COMPOSE_BUDGET_CACHE_KEY, constants.COMPOSE_BUDGET_LIMIT
        )

        improved = (reply or "").strip()
        if not improved:
            # An empty completion is a provider-side non-answer, not a valid
            # rewrite — returning it would blank the user's draft if the client
            # replaced content with it.
            logger.warning("[ERROR] Forum compose assist returned an empty rewrite")
            return Response(
                {
                    "detail": "AI assist could not improve this draft.",
                    "code": CODE_UNAVAILABLE,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Plain text, per the prompt contract — the client inserts it as a text
        # node, so any markup a model slipped in rides along as literal
        # characters rather than becoming document structure.
        return Response({"text": improved})
