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
AI feature in the repo); the order of operations is the design. Steps 1-2 are
the view's (``post()``); steps 3-7 are ``answer_question()``, which the view and
``manage.py rag_eval`` both call (todo 694) — the eval with ``persist=False,
charge=False`` and ``generate=None``, so a run writes no rows, spends none of the
RAG budget and makes no completion call:

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
from collections.abc import Callable
from dataclasses import dataclass, field

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
from .rag_retrieval import Passage, retrieve_grounding_passages
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


STATUS_REFERRAL = "referral"
STATUS_NO_INFORMATION = "no_information"
STATUS_PASSAGES_ONLY = "passages_only"
STATUS_ANSWERED = "answered"
STATUS_UNAVAILABLE = "unavailable"
STATUS_BUDGET_EXHAUSTED = "budget_exhausted"
# Only with generate=None: retrieval ran and the merged list is non-empty.
STATUS_RETRIEVED = "retrieved"


class _DefaultGenerate:
    """Sentinel type for ``answer_question``'s default ``generate``."""


_DEFAULT_GENERATE = _DefaultGenerate()


@dataclass
class RagOutcome:
    """What ``answer_question`` settled, for the view and the eval alike.

    ``passages`` are the merged passages the prompt sees (or would see), in
    citation order, each with its ``score`` and (blog) ``slug``.
    ``top_scores`` is the best raw score per index before the floor, keyed by
    index class name: ``None`` when an index searched and found nothing, no
    key when it could not search; empty when retrieval never ran (a referral,
    an exhausted budget).
    """

    status: str
    blocked_reason: str | None = None
    referral_message: str | None = None
    passages: list[Passage] = field(default_factory=list)
    top_scores: dict[str, float | None] = field(default_factory=dict)
    answer: str | None = None
    citations: list[int] = field(default_factory=list)
    answer_id: int | None = None


def answer_question(
    question: str,
    *,
    user=None,
    generate: Callable[..., str] | None | _DefaultGenerate = _DEFAULT_GENERATE,
    persist: bool = True,
    charge: bool = True,
    floor: float | None = None,
) -> RagOutcome:
    """The RAG pipeline after body validation (todo 694, spec §4).

    Order is the design (module docstring, steps 3-7): blocked classes →
    budget peek → retrieval with the floor → one grounded completion →
    citation validation. ``question`` must already be stripped and within
    ``RAG_QUESTION_MAX_CHARS``; the view validates it.

    - ``generate`` — the completion callable, ``generate_ai_text``'s shape.
      ``None`` makes this a retrieval-only call: it returns after retrieval,
      the floor and the passage merge with status ``retrieved`` (non-empty) or
      ``no_information`` (empty), and never calls a completion model. The
      default is ``generate_ai_text``, resolved at CALL time through a
      sentinel: a default bound at import would escape a patch of
      ``apps.forum_host.rag.generate_ai_text``.
    - ``persist=False`` writes no ``RagAnswer`` row (``answer_id`` stays None).
    - ``charge=False`` skips the ``RAG_BUDGET_LIMIT`` peek and consume. The
      question embedding is still charged to ``EMBED_BUDGET`` by retrieval.
    - ``floor`` — ``None`` means ``RAG_SIMILARITY_FLOOR``.

    Never raises for a provider failure: that is status ``unavailable``.
    """
    if isinstance(generate, _DefaultGenerate):
        generate = generate_ai_text
    blocked = classify_blocked_question(question)
    if blocked is not None:
        message = (
            constants.RAG_REFERRAL_INGESTION
            if blocked == INGESTION
            else constants.RAG_REFERRAL_CHEMICAL
        )
        return RagOutcome(
            status=STATUS_REFERRAL, blocked_reason=blocked, referral_message=message
        )

    # Peek, never check-and-increment (the compose-assist rule), and before
    # retrieval so an unaffordable question does not spend an embedding.
    if charge and not AIRateLimiter.peek_budget(
        constants.RAG_BUDGET_CACHE_KEY, constants.RAG_BUDGET_LIMIT
    ):
        return RagOutcome(status=STATUS_BUDGET_EXHAUSTED)

    top_scores: dict[str, float | None] = {}
    # user= is safe here: the ask view's response is per-asker and never cached.
    passages = retrieve_grounding_passages(
        question, user=user, floor=floor, top_scores=top_scores
    )
    if passages is None:
        # No index could search (embedding budget exhausted, provider
        # down): TRANSIENT, and not a claim about the corpus. Nothing
        # charged — nothing reached a provider.
        return RagOutcome(status=STATUS_UNAVAILABLE, top_scores=top_scores)
    if not passages:
        # Guardrail 1 — refuse when unsourced. No LLM call, no charge.
        return RagOutcome(status=STATUS_NO_INFORMATION, top_scores=top_scores)
    if generate is None:
        return RagOutcome(
            status=STATUS_RETRIEVED, passages=list(passages), top_scores=top_scores
        )

    prompt = _build_prompt(question, passages)
    try:
        reply = generate(
            prompt, alias=constants.RAG_ALIAS, timeout=constants.RAG_TIMEOUT_SECONDS
        )
    except Exception:
        # Degrade, never 500; nothing charged (it may never have reached
        # the provider).
        logger.exception("[ERROR] Forum plant-care answer provider call failed")
        return RagOutcome(
            status=STATUS_UNAVAILABLE, passages=list(passages), top_scores=top_scores
        )

    # Charged on any call that RETURNED, before the emptiness check — an
    # empty completion was still billed (see compose_assist.py).
    if charge:
        AIRateLimiter.consume_budget(
            constants.RAG_BUDGET_CACHE_KEY, constants.RAG_BUDGET_LIMIT
        )

    text = (reply or "").strip()
    if not text:
        logger.warning("[ERROR] Forum plant-care answer came back empty")
        return RagOutcome(
            status=STATUS_UNAVAILABLE, passages=list(passages), top_scores=top_scores
        )
    if is_no_information(text):
        return RagOutcome(
            status=STATUS_PASSAGES_ONLY, passages=list(passages), top_scores=top_scores
        )

    # Guardrail 3 — drop invented [n]; suppress a citation-free answer.
    answer, citations = validate_citations(text, len(passages))
    if not citations:
        logger.info("[RAG] answer suppressed: zero valid citations")
        return RagOutcome(
            status=STATUS_PASSAGES_ONLY, passages=list(passages), top_scores=top_scores
        )

    answer_id = None
    if persist:
        row = RagAnswer.objects.create(
            user=user,
            question=question,
            answer=answer,
            sources=[p.as_source() for p in passages],
            prompt_version=constants.RAG_PROMPT_VERSION,
        )
        answer_id = row.pk
    return RagOutcome(
        status=STATUS_ANSWERED,
        passages=list(passages),
        top_scores=top_scores,
        answer=answer,
        citations=citations,
        answer_id=answer_id,
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

        outcome = answer_question(question, user=request.user)
        return _response_for(outcome)


def _response_for(outcome: RagOutcome) -> Response:
    """Map an ``answer_question`` outcome to the ask view's HTTP response.

    Byte-for-byte the responses ``post()`` returned before the extraction
    (todo 694): referral / no_information / passages_only / answered are 200s
    with a ``status`` discriminator, an exhausted RAG budget is a 429 with
    ``Retry-After`` (never the 503 of ``unavailable``), a provider or retrieval
    failure is the transient 503.
    """
    if outcome.status == STATUS_REFERRAL:
        return Response(
            {
                "status": "referral",
                "answer_id": None,
                "referral": {
                    "reason": outcome.blocked_reason,
                    "message": outcome.referral_message,
                },
            }
        )
    if outcome.status == STATUS_BUDGET_EXHAUSTED:
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
    if outcome.status == STATUS_NO_INFORMATION:
        return Response({"status": "no_information", "answer_id": None, "sources": []})
    if outcome.status == STATUS_PASSAGES_ONLY:
        return _passages_only(outcome.passages)
    if outcome.status == STATUS_ANSWERED:
        return Response(
            {
                "status": "answered",
                "answer_id": outcome.answer_id,
                "answer": outcome.answer,
                "citations": outcome.citations,
                "sources": [p.as_source() for p in outcome.passages],
                "disclaimer": constants.RAG_DISCLAIMER,
            }
        )
    # STATUS_UNAVAILABLE — and STATUS_RETRIEVED, which only a generate=None
    # caller (the eval) can produce; the view always passes a generator.
    return _unavailable("Plant-care answers are unavailable right now.")


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
