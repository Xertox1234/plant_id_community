"""RAG plant-care answers for the forum (todo 289 / M13).

POST /api/v1/forum/care/ask/ — premium-only. Takes a plant-care question,
retrieves passages from this site's own blog and forum (``rag_retrieval``),
and returns an answer assembled ONLY from those passages with ``[n]``
citations — or one of three honest non-answers. The answer is returned to
the asker, never auto-posted into a thread (design doc §5).

POST /api/v1/forum/care/answers/<id>/report/ — "this answer is wrong",
landing in the CMS moderation listing (design doc guardrail 5).

Host-side (not the ``wagtail_forum`` package) for the same reasons as
``compose_assist.py``: it imports the blog app's AI helpers and the users
app's premium permission.

The guardrails ARE the feature (todo 289 Notes: highest harm ceiling of any
AI feature in the repo); the order of operations in ``post()`` is the design:

1. Two-flag gate → 503 ``disabled``. M13 is a strict superset of H15, so
   ``FORUM_RAG_ENABLED`` alone is not enough — with vector search off every
   question would silently come back "no information" forever.
2. Validate the body (container before value; over-long rejected, never
   truncated — the retrieval core caps embedded text, and a silently
   truncated question would be answered as if complete).
3. Guardrail 2 — blocked classes (ingestion/toxicity/medicinal, chemical
   dosing) → static referral BEFORE any retrieval or budget peek. A product
   rule in ``rag_guardrails``, not a prompt instruction.
4. Budget peek → 429. Peeked BEFORE retrieval: no point spending an
   embedding on a question we cannot afford to answer.
5. Retrieval with the similarity floor. Nothing above it → guardrail 1:
   ``no_information`` WITHOUT an LLM call.
6. One grounded completion; consume the budget on any call that returned
   (an empty completion was still billed — the compose-assist rule).
7. Guardrail 3 — citation validation; zero valid citations (or the model's
   own ``NO_INFORMATION``) → ``passages_only``: the passages as plain search
   results, the answer suppressed. Only a cited answer is persisted, so
   ``answer_id`` (and the report button) exist only for ``answered``.

Cost posture — five independent bounds: the two flags, ``IsPremiumUser``,
the per-user ``care_ask`` throttle (10/h; it counts every attempt, so failed
provider calls are bounded per account the same way compose assist's are),
and the forum-wide ``RAG_BUDGET_LIMIT`` counter on its own key. The question
embedding is charged separately to ``EMBED_BUDGET`` inside the retrieval core.
"""

import logging

from apps.blog.services.ai_rate_limiter import AIRateLimiter
from apps.blog.wagtail_ai_v3_integration import generate_ai_text
from apps.users.permissions import IsPremiumUser
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from wagtail_forum.api.versioning import UnversionedForumAPIMixin

from . import constants
from .api import _throttled
from .compose_assist import CODE_DISABLED, CODE_UNAVAILABLE
from .models import RagAnswer, RagAnswerReport
from .rag_guardrails import (
    INGESTION,
    classify_blocked_question,
    is_no_information,
    validate_citations,
)
from .rag_retrieval import retrieve_grounding_passages
from .vector_indexes import rag_enabled

logger = logging.getLogger(__name__)


def _build_prompt(question: str, passages) -> str:
    """Number the passages exactly as the ``sources`` array does, so a ``[n]``
    the model emits resolves to the source the client shows under ``n``."""
    numbered = "\n\n".join(
        f"[{p.n}] ({p.kind}: {p.title}, {p.date})\n{p.text}" for p in passages
    )
    return constants.RAG_PROMPT_TEMPLATE.format(question=question, passages=numbered)


def _passages_only(passages) -> Response:
    return Response(
        {
            "status": "passages_only",
            "answer_id": None,
            "sources": [p.as_source() for p in passages],
            "disclaimer": constants.RAG_DISCLAIMER,
        }
    )


def _unavailable(detail: str) -> Response:
    return Response(
        {"detail": detail, "code": CODE_UNAVAILABLE},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@_throttled("care_ask", "POST")
class PlantCareAskView(UnversionedForumAPIMixin, APIView):
    """POST a plant-care question, get a cited answer from site content."""

    permission_classes = [IsPremiumUser]

    @extend_schema(
        request=dict,
        responses={200: dict, 400: dict, 429: dict, 503: dict},
        description=(
            "Premium RAG plant-care answer grounded ONLY in this site's blog "
            "and forum. Body: {'question': '<text>'}. Always 200 with a "
            "'status' discriminator when the request itself is valid: "
            "'answered' ({answer, citations, sources, disclaimer, answer_id}); "
            "'no_information' (nothing in the corpus was similar enough — no "
            "LLM call was made); 'referral' (a blocked question class — "
            "ingestion/toxicity/medicinal use or chemical dosing — with a static "
            "{reason, message}); 'passages_only' (the model produced no cited "
            "answer, so only the retrieved sources are returned). Citations are "
            "'[n]' markers in 'answer' that index 'sources'; markers the model "
            "invented are removed. answer_id is set only for 'answered' and is "
            "what /care/answers/<id>/report/ takes.\n\n"
            "400 for a missing, non-string, blank or over-long question "
            "(rejected, never truncated); 429 when the per-user throttle or the "
            "forum-wide RAG budget is exhausted (with Retry-After); 503 when the "
            "feature is disabled for this deployment (code 'disabled' — "
            "permanent, stop offering the action; needs BOTH FORUM_RAG_ENABLED "
            "and FORUM_VECTOR_SEARCH_ENABLED) or the provider failed (code "
            "'unavailable' — transient). Requires a premium account. The answer "
            "is stored with the asker's account so it can be reported."
        ),
    )
    def post(self, request):
        if not rag_enabled():
            return Response(
                {
                    "detail": "Plant-care answers are not enabled.",
                    "code": CODE_DISABLED,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Guard the CONTAINER before the value: a top-level JSON array, string
        # or number makes request.data a list/str/int, so `.get` would raise.
        if not isinstance(request.data, dict) or not isinstance(
            request.data.get("question"), str
        ):
            return Response(
                {"detail": "Field 'question' is required and must be a string."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        question = request.data["question"].strip()
        if not question:
            return Response(
                {"detail": "Ask a question first."}, status=status.HTTP_400_BAD_REQUEST
            )
        if len(question) > constants.RAG_QUESTION_MAX_CHARS:
            return Response(
                {
                    "detail": (
                        "Question is too long "
                        f"({len(question)} of {constants.RAG_QUESTION_MAX_CHARS} "
                        "characters). Try asking one thing at a time."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        blocked = classify_blocked_question(question)
        if blocked is not None:
            message = (
                constants.RAG_REFERRAL_INGESTION
                if blocked == INGESTION
                else constants.RAG_REFERRAL_CHEMICAL
            )
            return Response(
                {
                    "status": "referral",
                    "answer_id": None,
                    "referral": {"reason": blocked, "message": message},
                }
            )

        # Peek, never check-and-increment (the compose-assist rule), and before
        # retrieval so an unaffordable question does not spend an embedding.
        if not AIRateLimiter.peek_budget(
            constants.RAG_BUDGET_CACHE_KEY, constants.RAG_BUDGET_LIMIT
        ):
            return Response(
                {
                    "detail": (
                        "Plant-care answers are temporarily at capacity. "
                        "Please try again later."
                    )
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(AIRateLimiter.TTL)},
            )

        # user= is safe here: this response is per-asker and never cached.
        passages = retrieve_grounding_passages(question, user=request.user)
        if passages is None:
            # No index could search (embedding budget exhausted, provider
            # down): TRANSIENT, and not a claim about the corpus. Nothing
            # charged — nothing reached a provider.
            return _unavailable("Plant-care answers are unavailable right now.")
        if not passages:
            # Guardrail 1 — refuse when unsourced. No LLM call, no charge.
            return Response(
                {"status": "no_information", "answer_id": None, "sources": []}
            )

        prompt = _build_prompt(question, passages)
        try:
            reply = generate_ai_text(
                prompt, alias=constants.RAG_ALIAS, timeout=constants.RAG_TIMEOUT_SECONDS
            )
        except Exception:
            # Degrade, never 500; nothing charged (it may never have reached
            # the provider).
            logger.exception("[ERROR] Forum plant-care answer provider call failed")
            return _unavailable("Plant-care answers are unavailable right now.")

        # Charged on any call that RETURNED, before the emptiness check — an
        # empty completion was still billed (see compose_assist.py).
        AIRateLimiter.consume_budget(
            constants.RAG_BUDGET_CACHE_KEY, constants.RAG_BUDGET_LIMIT
        )

        text = (reply or "").strip()
        if not text:
            logger.warning("[ERROR] Forum plant-care answer came back empty")
            return _unavailable("Plant-care answers are unavailable right now.")
        if is_no_information(text):
            return _passages_only(passages)

        # Guardrail 3 — drop invented [n]; suppress a citation-free answer.
        answer, citations = validate_citations(text, len(passages))
        if not citations:
            logger.info("[RAG] answer suppressed: zero valid citations")
            return _passages_only(passages)

        sources = [p.as_source() for p in passages]
        row = RagAnswer.objects.create(
            user=request.user,
            question=question,
            answer=answer,
            sources=sources,
            prompt_version=constants.RAG_PROMPT_VERSION,
        )
        return Response(
            {
                "status": "answered",
                "answer_id": row.pk,
                "answer": answer,
                "citations": citations,
                "sources": sources,
                "disclaimer": constants.RAG_DISCLAIMER,
            }
        )


@_throttled("report_create", "POST")
class PlantCareAnswerReportView(UnversionedForumAPIMixin, APIView):
    """POST "this answer is wrong" — guardrail 5's human review loop.

    Deliberately NOT flag-gated: reporting spends nothing, and turning the
    feature off after a bad answer must not stop the user reporting it. Reuses
    the ``report_create`` rate NAME with its own bucket (django-ratelimit keys
    the counter by the decorated view), like ``MessageReportView``.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=dict,
        responses={200: dict, 400: dict, 401: dict, 404: dict, 429: dict},
        description=(
            "Report a plant-care answer as wrong for moderator review. Body: "
            "{'detail': '<optional, up to 280 chars>'}. Idempotent per (answer, "
            "reporter): reporting the same answer again is a no-op 200. 404 for "
            "an answer that is not the caller's own (answers are private to the "
            "asker); 400 for an over-long or non-string detail."
        ),
    )
    def post(self, request, answer_id):
        # user= in the lookup: another user's answer 404s, never 403 — a 403
        # would confirm the id exists.
        answer = get_object_or_404(RagAnswer, pk=answer_id, user=request.user)
        data = request.data if isinstance(request.data, dict) else None
        detail = data.get("detail", "") if data is not None else None
        if (
            not isinstance(detail, str)
            or len(detail) > constants.RAG_REPORT_DETAIL_MAX_CHARS
        ):
            return Response(
                {
                    "detail": (
                        "Field 'detail' must be a string of at most "
                        f"{constants.RAG_REPORT_DETAIL_MAX_CHARS} characters."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        RagAnswerReport.objects.get_or_create(
            answer=answer, reporter=request.user, defaults={"detail": detail.strip()}
        )
        return Response({"reported": True})
